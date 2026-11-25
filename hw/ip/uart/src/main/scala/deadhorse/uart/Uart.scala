package deadhorse.uart

import chisel3._
import chisel3.util._
import deadhorse.lib._

/** Parallel upper-byte candidates avoid a full sixteen-bit carry dependency.
  * This remains a complete 17-bit unsigned sum, without a cycle or range change. */
object UartPhase {
  def add(left: UInt, right: UInt): UInt = {
    require(left.getWidth == 16 && right.getWidth == 16)
    val low = left(7, 0) +& right(7, 0)
    val highZero = left(15, 8) +& right(15, 8)
    val highOne = Wire(UInt(9.W))
    highOne := highZero + 1.U // Maximum is 255 + 255 + 1, exactly nine bits.
    Cat(Mux(low(8), highOne, highZero), low(7, 0))
  }
}

/** Single HF-domain, owner-checked fractional 8N1 UART. */
class Uart(json: String, fifoDepth: Int = 8, base: BigInt = 0) extends RawModule {
  require(fifoDepth >= 2 && fifoDepth <= 16)
  require(base >= 0 && base < (BigInt(1) << 32) && base % 256 == 0)
  protected def txValue(value: Bool): Bool = value
  protected def accessAllowed(origin: UInt, selected: UInt): Bool = origin === selected

  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val bus = IO(new LocalBus); val owner = IO(Input(UInt(3.W)))
  val rx = IO(Input(Bool())); val tx = IO(Output(Bool())); val txEnable = IO(Output(Bool()))
  val sleepRequest = IO(Input(Bool())); val sleepMode = IO(Input(UInt(2.W)))
  val irq = IO(Output(Bool())); val dmaTxRequest = IO(Output(Bool())); val dmaRxRequest = IO(Output(Bool()))
  val clockHold = IO(Output(Bool())); val quiescent = IO(Output(Bool()))

  val regs = Module(new RegBlock(json))
  val adapter = Module(new BusRegAdapter(8, base, 0))
  regs.clk := clk; regs.rst_n := reset_n
  adapter.clk := clk; adapter.reset_n := reset_n
  adapter.bus.req := bus.req; adapter.bus.bits := bus.bits
  adapter.bus.bits.origin := Mux(accessAllowed(bus.bits.origin, owner), 0.U, 7.U)
  bus.gnt := adapter.bus.gnt; bus.rvalid := adapter.bus.rvalid
  bus.rdata := adapter.bus.rdata; bus.err := adapter.bus.err
  regs.bus <> adapter.registers

  val synchronizer = Module(new CdcSync(1))
  synchronizer.clk := clk; synchronizer.reset_n := reset_n

  withClockAndReset(clk, (!reset_n).asAsyncReset) {
    val activeTx = RegInit(false.B); val activeRx = RegInit(false.B)
    val activeInvert = RegInit(false.B); val increment = RegInit(0.U(16.W))
    val upperIncrementNext = RegInit(1.U(8.W))
    // Inactive reset value prevents false starts for either physical polarity.
    synchronizer.in := ((!rx) ^ activeInvert).asUInt
    val serialRx = !synchronizer.out.asBool
    val settle = RegInit(0.U(2.W))
    when(settle =/= 0.U) { settle := settle - 1.U }

    val pointerWidth = log2Ceil(fifoDepth)
    val countWidth = log2Ceil(fifoDepth + 1)
    def advance(pointer: UInt): UInt = Mux(pointer === (fifoDepth - 1).U, 0.U, pointer + 1.U)
    val txStorage = Reg(Vec(fifoDepth, UInt(8.W)))
    val rxStorage = Reg(Vec(fifoDepth, UInt(8.W)))
    val txRead = RegInit(0.U(pointerWidth.W)); val txWrite = RegInit(0.U(pointerWidth.W))
    val rxRead = RegInit(0.U(pointerWidth.W)); val rxWrite = RegInit(0.U(pointerWidth.W))
    val txCount = RegInit(0.U(countWidth.W)); val rxCount = RegInit(0.U(countWidth.W))

    val txBusy = RegInit(false.B); val rxBusy = RegInit(false.B)
    val txPin = RegInit(true.B)
    val txFrame = Reg(UInt(10.W)); val txIndex = RegInit(0.U(4.W))
    val rxFrame = RegInit(0.U(8.W)); val rxIndex = RegInit(0.U(4.W))
    val txLow = RegInit(0.U(8.W)); val txHigh = RegInit(0.U(8.W))
    val rxLow = RegInit(0.U(8.W)); val rxHigh = RegInit(0.U(8.W))
    val txLowCarry = RegInit(false.B); val rxLowCarry = RegInit(false.B)
    val txTick = RegInit(false.B); val rxTick = RegInit(false.B)
    val waitIdle = RegInit(false.B)
    tx := txPin; txEnable := activeTx

    val apply = regs.hw("command_apply_pulse").asBool
    val txPush = regs.hw("tx_data_value_we").asBool
    val rxPop = regs.hw("command_rx_pop_pulse").asBool
    val txFlush = regs.hw("command_tx_flush_pulse").asBool
    val rxFlush = regs.hw("command_rx_flush_pulse").asBool
    val shadowTx = regs.hw("configuration_tx_enable_q").asBool
    val shadowRx = regs.hw("configuration_rx_enable_q").asBool
    val shadowInvert = regs.hw("configuration_invert_q").asBool
    val shadowIncrement = regs.hw("baud_increment_q")
    val enginesIdle = !txBusy && !rxBusy
    val empty = txCount === 0.U && rxCount === 0.U
    val baudValid = !(shadowTx || shadowRx) || (shadowIncrement =/= 0.U && shadowIncrement <= 8192.U)
    val applied = apply && enginesIdle && empty && baudValid
    when(applied) {
      activeTx := shadowTx; activeRx := shadowRx; activeInvert := shadowInvert
      increment := shadowIncrement; txPin := txValue(true.B ^ shadowInvert)
      upperIncrementNext := shadowIncrement(15, 8) + 1.U
      txLow := 0.U; txHigh := 0.U; txLowCarry := false.B; txTick := false.B
      rxLow := 0.U; rxHigh := 0.U; rxLowCarry := false.B; rxTick := false.B
      settle := 2.U; waitIdle := false.B
    }

    val txLaunch = !txBusy && txCount =/= 0.U && activeTx && !txFlush && !applied
    val txEnqueue = txPush && txCount < fifoDepth.U && !txFlush
    // Byte sums use the same full-domain helper, but never form a sixteen-bit
    // feedback carry chain. The low byte runs one step ahead of the high byte.
    def byteSum(left: UInt, right: UInt): UInt =
      UartPhase.add(Cat(0.U(8.W), left), Cat(0.U(8.W), right))(8, 0)
    def highSum(high: UInt, carry: Bool): UInt = Mux(carry,
      byteSum(high, upperIncrementNext), byteSum(high, increment(15, 8)))
    val txLowSum = byteSum(txLow, increment(7, 0))
    val txHighSum = highSum(txHigh, txLowCarry)
    val txDone = txBusy && txTick && txIndex === 9.U
    when(txLaunch) {
      txBusy := true.B; txFrame := Cat(1.U(1.W), txStorage(txRead), 0.U(1.W))
      // P(n)=seed+n*increment. Seed high=hi(P1), low=lo(P2), and
      // lowCarry=carry(lo(P1)+increment_lo). Old tick is carry(P0+increment).
      // Each busy edge advances that invariant and consumes the old tick.
      txIndex := 0.U; txHigh := increment(15, 8)
      txLow := Cat(increment(6, 0), 0.U(1.W)); txLowCarry := increment(7)
      txTick := false.B
      txPin := txValue(false.B ^ activeInvert)
    }.elsewhen(txBusy) {
      txLow := txLowSum(7, 0); txLowCarry := txLowSum(8)
      txHigh := txHighSum(7, 0); txTick := txHighSum(8)
      when(txTick) {
        when(txIndex === 9.U) {
          txBusy := false.B; txPin := txValue(true.B ^ activeInvert)
        }.otherwise {
          txIndex := txIndex + 1.U
          txPin := txValue(txFrame(1) ^ activeInvert)
          txFrame := Cat(1.U(1.W), txFrame(9, 1))
        }
      }
    }
    when(txFlush) {
      txRead := 0.U; txWrite := 0.U; txCount := 0.U
    }.otherwise {
      when(txEnqueue) { txStorage(txWrite) := regs.hw("tx_data_value_wdata"); txWrite := advance(txWrite) }
      when(txLaunch) { txRead := advance(txRead) }
      when(txEnqueue && !txLaunch) { txCount := txCount + 1.U }
        .elsewhen(txLaunch && !txEnqueue) { txCount := txCount - 1.U }
    }

    val receiveMode = !sleepRequest || sleepMode === 2.U
    val allowReceive = activeRx && receiveMode
    val rxLaunch = !rxBusy && !waitIdle && allowReceive && settle === 0.U && !serialRx && !applied
    val rxLowSum = byteSum(rxLow, increment(7, 0))
    val rxHighSum = highSum(rxHigh, rxLowCarry)
    val rxStop = rxBusy && rxTick && rxIndex === 9.U
    val rxComplete = rxStop && serialRx
    val framingError = rxStop && !serialRx
    when(waitIdle && serialRx) { waitIdle := false.B }
    when(rxLaunch) {
      // Half-bit seed differs only in the high byte. Enabled increments are
      // at most 8192, making 0x80|increment_hi exact and initial tick false.
      rxBusy := true.B; rxIndex := 0.U; rxHigh := 128.U | increment(15, 8)
      rxLow := Cat(increment(6, 0), 0.U(1.W)); rxLowCarry := increment(7)
      rxTick := false.B; rxFrame := 0.U
    }.elsewhen(rxBusy) {
      rxLow := rxLowSum(7, 0); rxLowCarry := rxLowSum(8)
      rxHigh := rxHighSum(7, 0); rxTick := rxHighSum(8)
      when(rxTick) {
        when(rxIndex === 0.U) {
          when(serialRx) { rxBusy := false.B }
            .otherwise { rxIndex := 1.U }
        }.elsewhen(rxIndex === 9.U) {
          rxBusy := false.B
          when(!serialRx) { waitIdle := true.B }
        }.otherwise {
          rxFrame := Cat(serialRx, rxFrame(7, 1))
          rxIndex := rxIndex + 1.U
        }
      }
    }
    val rxDequeue = rxPop && rxCount =/= 0.U && !rxFlush
    val rxRoom = rxCount < fifoDepth.U || rxDequeue
    val rxEnqueue = rxComplete && rxRoom && !rxFlush
    when(rxFlush) {
      rxRead := 0.U; rxWrite := 0.U; rxCount := 0.U
    }.otherwise {
      when(rxEnqueue) { rxStorage(rxWrite) := rxFrame; rxWrite := advance(rxWrite) }
      when(rxDequeue) { rxRead := advance(rxRead) }
      when(rxEnqueue && !rxDequeue) { rxCount := rxCount + 1.U }
        .elsewhen(rxDequeue && !rxEnqueue) { rxCount := rxCount - 1.U }
    }

    regs.hw("rx_data_value_d") := Mux(rxCount =/= 0.U, rxStorage(rxRead), 0.U)
    regs.hw("status_tx_ready_d") := (txCount < fifoDepth.U).asUInt
    regs.hw("status_rx_valid_d") := (rxCount =/= 0.U).asUInt
    regs.hw("status_tx_busy_d") := txBusy.asUInt
    regs.hw("status_rx_busy_d") := rxBusy.asUInt
    regs.hw("status_idle_d") := enginesIdle.asUInt
    regs.hw("status_tx_count_d") := txCount
    regs.hw("status_rx_count_d") := rxCount
    regs.hw("active_tx_enable_d") := activeTx.asUInt
    regs.hw("active_rx_enable_d") := activeRx.asUInt
    regs.hw("active_invert_d") := activeInvert.asUInt
    regs.hw("active_increment_d") := increment
    regs.hw("events_tx_overflow_set") := (txPush && txCount === fifoDepth.U).asUInt
    regs.hw("events_rx_overflow_set") := (rxComplete && !rxRoom).asUInt
    regs.hw("events_rx_underflow_set") := (rxPop && rxCount === 0.U).asUInt
    regs.hw("events_framing_error_set") := framingError.asUInt
    regs.hw("events_config_error_set") := (apply && !applied).asUInt
    regs.hw("events_tx_done_set") := txDone.asUInt

    val errorEvents = Seq("tx_overflow", "rx_overflow", "rx_underflow", "framing_error", "config_error")
      .map(name => regs.hw(s"events_${name}_q").asBool).reduce(_ || _)
    irq := RegNext((regs.hw("irq_enable_rx_valid_q").asBool && rxCount =/= 0.U) ||
      (regs.hw("irq_enable_tx_ready_q").asBool && txCount < fifoDepth.U) ||
      (regs.hw("irq_enable_errors_q").asBool && errorEvents) ||
      (regs.hw("irq_enable_tx_done_q").asBool && regs.hw("events_tx_done_q").asBool), false.B)
    dmaTxRequest := RegNext(activeTx && txCount < fifoDepth.U, false.B)
    dmaRxRequest := RegNext(rxCount =/= 0.U, false.B)
    val receiveNext = Mux(applied, shadowRx, activeRx) && receiveMode
    clockHold := RegNext(txBusy || txCount =/= 0.U || txPush || rxBusy || receiveNext, false.B)
    quiescent := RegNext(enginesIdle && txCount === 0.U && !txPush && !rxLaunch, false.B)
  }
}

/** Independent AON monitor; no HF clock or asynchronous event latch required. */
class UartWake(qualifiedReset: Boolean=false) extends RawModule {
  protected def wakeValue(value: Bool): Bool = value
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val rx = IO(Input(Bool())); val armed = IO(Input(Bool()))
  val invert = IO(Input(Bool())); val clear = IO(Input(Bool()))
  val wake = IO(Output(Bool())); val clockRequest = IO(Output(Bool()))
  val localUp=if(qualifiedReset) reset_n else {
    val r=Module(new ResetRelease);r.clk:=clk;r.reset_n:=reset_n;r.released
  }
  val synchronizer = Module(new CdcSync(1))
  synchronizer.clk := clk; synchronizer.reset_n := localUp
  synchronizer.in := ((!rx) ^ invert).asUInt
  withClockAndReset(clk, (!localUp).asAsyncReset) {
    val pending = RegInit(false.B)
    pending := wakeValue((pending && !clear) || (armed && synchronizer.out.asBool))
    wake := pending; clockRequest := pending
  }
}

/** Three independent HF endpoints; clocks, ownership and pins remain explicit. */
class UartBank(json: String, fifoDepth: Int = 8, bases: Seq[BigInt] = Seq.fill(3)(BigInt(0))) extends RawModule {
  require(bases.size == 3)
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val bus = IO(Vec(3, new LocalBus)); val owner = IO(Input(Vec(3, UInt(3.W))))
  val rx = IO(Input(Vec(3, Bool()))); val tx = IO(Output(Vec(3, Bool())))
  val txEnable = IO(Output(Vec(3, Bool())))
  val sleepRequest = IO(Input(Vec(3, Bool()))); val sleepMode = IO(Input(Vec(3, UInt(2.W))))
  val irq = IO(Output(Vec(3, Bool()))); val dmaTxRequest = IO(Output(Vec(3, Bool())))
  val dmaRxRequest = IO(Output(Vec(3, Bool()))); val clockHold = IO(Output(Vec(3, Bool())))
  val quiescent = IO(Output(Vec(3, Bool())))
  for (index <- 0 until 3) {
    val uart = Module(new Uart(json, fifoDepth, bases(index)))
    uart.clk := clk; uart.reset_n := reset_n; uart.bus <> bus(index)
    uart.owner := owner(index); uart.rx := rx(index)
    uart.sleepRequest := sleepRequest(index); uart.sleepMode := sleepMode(index)
    tx(index) := uart.tx; txEnable(index) := uart.txEnable; irq(index) := uart.irq
    dmaTxRequest(index) := uart.dmaTxRequest; dmaRxRequest(index) := uart.dmaRxRequest
    clockHold(index) := uart.clockHold; quiescent(index) := uart.quiescent
  }
}
