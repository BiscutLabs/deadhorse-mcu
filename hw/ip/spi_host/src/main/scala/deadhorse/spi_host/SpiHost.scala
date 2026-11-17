package deadhorse.spi_host

import chisel3._
import chisel3.util._
import deadhorse.lib._

/** Bounded, owner-checked SPI host. SCLK is data, never an RTL clock. */
class SpiHost(json: String, fifoDepth: Int = 16, base: BigInt = 0) extends RawModule {
  require(fifoDepth >= 2 && fifoDepth <= 16)
  require(base >= 0 && base < (BigInt(1) << 32) && base % 256 == 0)
  protected def outputBit(value: Bool): Bool = value
  protected def allowed(origin: UInt, owner: UInt): Bool = origin === owner
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val bus = IO(new LocalBus); val owner = IO(Input(UInt(3.W)))
  val miso = IO(Input(Bool())); val sclk = IO(Output(Bool())); val mosi = IO(Output(Bool()))
  val cs_n = IO(Output(UInt(2.W))); val pinsEnable = IO(Output(Bool()))
  val timeNow = IO(Input(UInt(32.W)))
  val sleepRequest = IO(Input(Bool())); val sleepEnable = IO(Input(Bool()))
  val irq = IO(Output(Bool())); val dmaTxRequest = IO(Output(Bool())); val dmaRxRequest = IO(Output(Bool()))
  val clockHold = IO(Output(Bool())); val quiescent = IO(Output(Bool()))

  val regs = Module(new RegBlock(json))
  val adapter = Module(new BusRegAdapter(8, base, 0))
  regs.clk := clk; regs.rst_n := reset_n
  adapter.clk := clk; adapter.reset_n := reset_n
  adapter.bus.req := bus.req; adapter.bus.bits := bus.bits
  adapter.bus.bits.origin := Mux(allowed(bus.bits.origin, owner), 0.U, 7.U)
  bus.gnt := adapter.bus.gnt; bus.rvalid := adapter.bus.rvalid
  bus.rdata := adapter.bus.rdata; bus.err := adapter.bus.err
  regs.bus <> adapter.registers
  val sync = Module(new CdcSync(1))
  sync.clk := clk; sync.reset_n := reset_n; sync.in := miso.asUInt

  withClockAndReset(clk, (!reset_n).asAsyncReset) {
    val idle :: transfer :: hold :: gap :: Nil = Enum(4)
    val state = RegInit(idle)
    val enabled = RegInit(false.B); val mode3 = RegInit(false.B); val selected = RegInit(false.B)
    val halfPeriod = RegInit(3.U(8.W))
    val clockPin = RegInit(false.B); val dataPin = RegInit(false.B); val selectPins = RegInit(3.U(2.W))
    sclk := clockPin; mosi := dataPin; cs_n := selectPins; pinsEnable := enabled
    val timestamp = RegInit(0.U(32.W))
    val timer = RegInit(0.U(8.W)); val edge = RegInit(0.U(4.W))
    val remaining = RegInit(0.U(5.W))
    val txShift = RegInit(0.U(8.W)); val rxShift = RegInit(0.U(8.W))
    val pointerWidth = log2Ceil(fifoDepth); val countWidth = log2Ceil(fifoDepth + 1)
    val txWords = Reg(Vec(fifoDepth, UInt(8.W))); val rxWords = Reg(Vec(fifoDepth, UInt(8.W)))
    val txRead = RegInit(0.U(pointerWidth.W)); val txWrite = RegInit(0.U(pointerWidth.W))
    val rxRead = RegInit(0.U(pointerWidth.W)); val rxWrite = RegInit(0.U(pointerWidth.W))
    val txCount = RegInit(0.U(countWidth.W)); val rxCount = RegInit(0.U(countWidth.W))
    def next(p: UInt): UInt = Mux(p === (fifoDepth - 1).U, 0.U, p + 1.U)
    def pulse(name: String): Bool = regs.hw(s"command_${name}_pulse").asBool
    val conflict = pulse("start") && (pulse("apply") || pulse("tx_flush") || pulse("rx_flush"))
    val apply = pulse("apply") && !conflict
    val pop = pulse("rx_pop") && !conflict
    val txFlush = pulse("tx_flush") && !conflict && state === idle
    val rxFlush = pulse("rx_flush") && !conflict && state === idle
    val push = regs.hw("tx_data_value_we").asBool
    val shadowEnable = regs.hw("configuration_enable_q").asBool
    val shadowMode = regs.hw("configuration_mode3_q").asBool
    val shadowSelect = regs.hw("configuration_chip_select_q").asBool
    val shadowHalf = regs.hw("divider_half_period_q")
    val length = regs.hw("length_bytes_q")
    val applied = apply && state === idle && txCount === 0.U && rxCount === 0.U &&
      (!shadowEnable || shadowHalf >= 3.U)
    val started = pulse("start") && !conflict && state === idle && enabled &&
      (!sleepRequest || sleepEnable) && length =/= 0.U && length <= fifoDepth.U &&
      txCount >= length && (rxCount +& length) <= fifoDepth.U
    val tick = state === transfer && timer === 0.U
    val trailing = edge(0)
    val byteEnd = tick && edge === 15.U
    val consume = started || (byteEnd && remaining > 1.U)
    val txRoom = txCount < fifoDepth.U || consume
    val enqueue = push && txRoom && !txFlush
    val dequeue = pop && rxCount =/= 0.U && !rxFlush
    val rxRoom = rxCount < fifoDepth.U || dequeue
    val received = byteEnd && rxRoom && !rxFlush
    val rxNext = Cat(rxShift(6, 0), sync.out.asBool)
    val finished = state === hold && timer === 0.U

    when(applied) {
      enabled := shadowEnable; mode3 := shadowMode; selected := shadowSelect
      halfPeriod := shadowHalf; clockPin := shadowMode; dataPin := false.B
    }
    when(started) {
      state := transfer; timer := halfPeriod - 1.U; edge := 0.U; remaining := length
      selectPins := Mux(selected, 1.U, 2.U); timestamp := timeNow
      txShift := txWords(txRead); rxShift := 0.U
      dataPin := outputBit(Mux(mode3, false.B, txWords(txRead)(7)))
    }
    when(state =/= idle) {
      when(timer =/= 0.U) { timer := timer - 1.U }
        .otherwise {
          timer := halfPeriod - 1.U
          when(state === transfer) {
            clockPin := Mux(trailing, mode3, !mode3)
            edge := edge + 1.U
            when(trailing === mode3) { rxShift := rxNext }
            when(!trailing && mode3) {
              dataPin := outputBit(txShift(7)); txShift := Cat(txShift(6, 0), 0.U(1.W))
            }
            when(trailing && !mode3 && !byteEnd) {
              dataPin := outputBit(txShift(6)); txShift := Cat(txShift(6, 0), 0.U(1.W))
            }
            when(byteEnd) {
              remaining := remaining - 1.U; rxShift := 0.U
              when(remaining === 1.U) { state := hold }
                .otherwise {
                  txShift := txWords(txRead)
                  when(!mode3) { dataPin := outputBit(txWords(txRead)(7)) }
                }
            }
          }.elsewhen(state === hold) {
            selectPins := 3.U; dataPin := false.B; state := gap
          }.otherwise { state := idle }
        }
    }
    when(txFlush) { txRead := 0.U; txWrite := 0.U; txCount := 0.U }
      .otherwise {
        when(enqueue) { txWords(txWrite) := regs.hw("tx_data_value_wdata"); txWrite := next(txWrite) }
        when(consume) { txRead := next(txRead) }
        // A consume itself guarantees room; avoid feeding its room/acceptance
        // decode back through the count-direction decision.
        when(push && txCount < fifoDepth.U && !consume) { txCount := txCount + 1.U }
          .elsewhen(consume && !push) { txCount := txCount - 1.U }
      }
    when(rxFlush) { rxRead := 0.U; rxWrite := 0.U; rxCount := 0.U }
      .otherwise {
        when(received) { rxWords(rxWrite) := Mux(mode3, rxNext, rxShift); rxWrite := next(rxWrite) }
        when(dequeue) { rxRead := next(rxRead) }
        when(byteEnd && rxCount < fifoDepth.U && !dequeue) { rxCount := rxCount + 1.U }
          .elsewhen(dequeue && !byteEnd) { rxCount := rxCount - 1.U }
      }

    regs.hw("rx_data_value_d") := Mux(rxCount =/= 0.U, rxWords(rxRead), 0.U)
    regs.hw("status_tx_ready_d") := (txCount < fifoDepth.U).asUInt
    regs.hw("status_rx_valid_d") := (rxCount =/= 0.U).asUInt
    regs.hw("status_busy_d") := (state =/= idle).asUInt
    regs.hw("status_tx_count_d") := txCount; regs.hw("status_rx_count_d") := rxCount
    regs.hw("active_enable_d") := enabled.asUInt; regs.hw("active_mode3_d") := mode3.asUInt
    regs.hw("active_chip_select_d") := selected.asUInt; regs.hw("active_half_period_d") := halfPeriod
    regs.hw("timestamp_value_d") := timestamp
    regs.hw("events_tx_overflow_set") := (push && !txRoom).asUInt
    regs.hw("events_rx_overflow_set") := (byteEnd && !rxRoom).asUInt
    regs.hw("events_rx_underflow_set") := (pop && rxCount === 0.U).asUInt
    regs.hw("events_command_error_set") := (conflict || (apply && !applied) ||
      (pulse("start") && !started) || ((pulse("tx_flush") || pulse("rx_flush")) && state =/= idle)).asUInt
    regs.hw("events_done_set") := finished.asUInt
    val errors = Seq("tx_overflow", "rx_overflow", "rx_underflow", "command_error")
      .map(n => regs.hw(s"events_${n}_q").asBool).reduce(_ || _)
    irq := RegNext((regs.hw("irq_enable_rx_valid_q").asBool && rxCount =/= 0.U) ||
      (regs.hw("irq_enable_tx_ready_q").asBool && txCount < fifoDepth.U) ||
      (regs.hw("irq_enable_errors_q").asBool && errors) ||
      (regs.hw("irq_enable_done_q").asBool && regs.hw("events_done_q").asBool), false.B)
    dmaTxRequest := RegNext(enabled && txCount < fifoDepth.U, false.B)
    dmaRxRequest := RegNext(rxCount =/= 0.U, false.B)
    clockHold := RegNext(state =/= idle || txCount =/= 0.U || push || started, false.B)
    quiescent := RegNext(state === idle && txCount === 0.U && !push && !started, false.B)
  }
}
