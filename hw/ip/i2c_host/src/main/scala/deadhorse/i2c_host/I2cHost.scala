package deadhorse.i2c_host

import chisel3._
import chisel3.util._
import deadhorse.lib._

/** Single-controller byte engine. Pin clocks are data, never RTL clocks. */
class I2cHost(json: String, base: BigInt = 0) extends RawModule {
  require(base >= 0 && base < (BigInt(1) << 32) && base % 256 == 0)
  protected def allowed(origin: UInt, owner: UInt): Bool = origin === owner
  protected def outputBit(pullLow: Bool): Bool = pullLow
  protected def receiveByte(value: UInt): UInt = value
  protected def recoveryDone(value: Bool): Bool = value
  protected def timeoutExpired(value: Bool): Bool = value
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val bus = IO(new LocalBus); val owner = IO(Input(UInt(3.W)))
  val sclIn = IO(Input(Bool())); val sdaIn = IO(Input(Bool()))
  val sclLow = IO(Output(Bool())); val sdaLow = IO(Output(Bool()))
  val pinsEnable = IO(Output(Bool())); val irq = IO(Output(Bool()))
  val clockHold = IO(Output(Bool())); val quiescent = IO(Output(Bool()))
  val sleepRequest = IO(Input(Bool())); val sleepEnable = IO(Input(Bool()))
  val regs = Module(new RegBlock(json)); val adapter = Module(new BusRegAdapter(8, base, 0))
  regs.clk := clk; regs.rst_n := reset_n; adapter.clk := clk; adapter.reset_n := reset_n
  adapter.bus.req := bus.req; adapter.bus.bits := bus.bits
  adapter.bus.bits.origin := Mux(allowed(bus.bits.origin, owner), 0.U, 7.U)
  bus.gnt := adapter.bus.gnt; bus.rvalid := adapter.bus.rvalid
  bus.rdata := adapter.bus.rdata; bus.err := adapter.bus.err; regs.bus <> adapter.registers
  val sclSync = Module(new CdcSync(1)); val sdaSync = Module(new CdcSync(1))
  for(s <- Seq(sclSync, sdaSync)) { s.clk := clk; s.reset_n := reset_n }
  sclSync.in := sclIn.asUInt; sdaSync.in := sdaIn.asUInt

  withClockAndReset(clk, (!reset_n).asAsyncReset) {
    def filtered(input: Bool): Bool = {
      val level = RegInit(false.B); val count = RegInit(0.U(2.W))
      when(input === level) { count := 0.U }
        .elsewhen(count === 2.U) { level := input; count := 0.U }
        .otherwise { count := count + 1.U }
      level
    }
    val scl = filtered(sclSync.out.asBool); val sda = filtered(sdaSync.out.asBool)
    val idle :: freeWait :: startHold :: bitHold :: bitLow :: bitWait :: bitHigh :: finishHold :: specialHold :: specialLow :: specialWait :: specialHigh :: stopFree :: Nil = Enum(13)
    val state = RegInit(idle); val owned = RegInit(false.B); val enabled = RegInit(false.B)
    val clockPull = RegInit(false.B); val dataPull = RegInit(false.B)
    sclLow := clockPull; sdaLow := dataPull; pinsEnable := enabled
    val holdCycles = RegInit(8.U(8.W)); val lowCycles = RegInit(24.U(8.W))
    val highCycles = RegInit(22.U(8.W)); val freeCycles = RegInit(120.U(8.W))
    val timeoutCycles = RegInit(65535.U(16.W))
    val watchLow = RegInit(254.U(8.W)); val watchHigh = RegInit(255.U(8.W))
    val timer = RegInit(0.U(8.W)); val bit = RegInit(0.U(4.W))
    val writeOp = 0.U(2.W); val readOp = 1.U(2.W); val recoverOp = 2.U(2.W)
    val op = RegInit(writeOp); val stopSpecial = RegInit(false.B); val recovering = RegInit(false.B)
    val finishingByte = RegInit(false.B); val readAck = RegInit(false.B)
    val txShift = RegInit(0.U(8.W)); val rxShift = RegInit(0.U(8.W))
    val rxData = RegInit(0.U(8.W)); val rxValid = RegInit(false.B); val lastAck = RegInit(false.B)
    val busy = state =/= idle
    def pulse(name: String): Bool = regs.hw(s"command_${name}_pulse").asBool
    val action = Seq("start", "write", "read", "stop", "recover", "apply").map(pulse)
    val conflict = PopCount(VecInit(action)) > 1.U
    val requested = action.reduce(_ || _)
    val accepted = WireDefault(false.B); val progress = WireDefault(false.B)
    val done = WireDefault(false.B); val nack = WireDefault(false.B)
    val lost = WireDefault(false.B); val timedOut = WireDefault(false.B)
    val recovered = WireDefault(false.B); val busFault = WireDefault(false.B)
    val waiting = state === freeWait || state === bitWait || state === specialWait ||
      state === stopFree || (state === idle && owned)
    val shadowEnable = regs.hw("configuration_enable_q").asBool
    val timingLegal = regs.hw("timing_hold_q") >= 1.U && regs.hw("timing_low_q") >= 4.U &&
      regs.hw("timing_high_q") >= 4.U && regs.hw("timing_free_q") >= 4.U && regs.hw("timeout_cycles_q") >= 1.U
    def abort(): Unit = {
      state := idle; owned := false.B; clockPull := false.B; dataPull := false.B
      recovering := false.B
    }
    when(pulse("pop") && !conflict) { rxValid := false.B }
    when(!busy && !conflict) {
      when(pulse("apply") && !owned && (!shadowEnable || timingLegal)) {
        enabled := shadowEnable; holdCycles := regs.hw("timing_hold_q")
        lowCycles := regs.hw("timing_low_q"); highCycles := regs.hw("timing_high_q")
        freeCycles := regs.hw("timing_free_q"); timeoutCycles := regs.hw("timeout_cycles_q")
        accepted := true.B; done := true.B
      }
      when(enabled) {
        when(pulse("start") && (owned || !sleepRequest || sleepEnable)) {
          accepted := true.B; progress := true.B; finishingByte := false.B; recovering := false.B
          when(owned) { stopSpecial := false.B; state := specialHold; timer := holdCycles - 1.U }
            .otherwise { state := freeWait; timer := freeCycles - 1.U }
        }
        when((pulse("write") || (pulse("read") && !rxValid)) && owned) {
          accepted := true.B; progress := true.B; state := bitHold; timer := holdCycles - 1.U
          op := Mux(pulse("write"), writeOp, readOp); bit := 0.U; rxShift := 0.U
          txShift := regs.hw("tx_data_value_q"); readAck := pulse("ack"); finishingByte := true.B
        }
        when(pulse("stop") && owned) {
          accepted := true.B; progress := true.B; state := specialHold; timer := holdCycles - 1.U
          stopSpecial := true.B; recovering := false.B
        }
        when(pulse("recover") && !owned && (!sleepRequest || sleepEnable)) {
          accepted := true.B; progress := true.B; state := bitHold; timer := holdCycles - 1.U
          op := recoverOp; bit := 0.U; clockPull := true.B; dataPull := false.B
          recovering := true.B; finishingByte := true.B
        }
      }
    }
    switch(state) {
      is(freeWait) {
        when(!scl || !sda) { timer := freeCycles - 1.U }
          .elsewhen(timer === 0.U) {
            dataPull := true.B; owned := true.B; state := startHold; timer := freeCycles - 1.U; progress := true.B
          }.otherwise { timer := timer - 1.U }
      }
      is(startHold) {
        when(!scl) { busFault := true.B; abort() }
          .elsewhen(timer === 0.U) { clockPull := true.B; state := finishHold; timer := holdCycles - 1.U }
          .otherwise { timer := timer - 1.U }
      }
      is(bitHold) {
        when(timer === 0.U) {
          dataPull := Mux(op === writeOp && bit < 8.U, outputBit(!txShift(7)),
            op === readOp && bit === 8.U && readAck)
          state := bitLow; timer := lowCycles - 1.U
        }.otherwise { timer := timer - 1.U }
      }
      is(bitLow) {
        when(timer === 0.U) { clockPull := false.B; state := bitWait }
          .otherwise { timer := timer - 1.U }
      }
      is(bitWait) {
        when(scl) { progress := true.B; state := bitHigh; timer := highCycles - 1.U }
      }
      is(bitHigh) {
        when(!scl) { busFault := true.B; abort() }
          .elsewhen(timer === 0.U) {
            val sendingOne = (op === writeOp && bit < 8.U && txShift(7)) ||
              (op === readOp && bit === 8.U && !readAck)
            when(sendingOne && !sda) { lost := true.B; abort() }
              .otherwise {
                clockPull := true.B
                when(bit < 8.U) {
                  when(op === readOp) { rxShift := Cat(rxShift(6, 0), sda) }
                  txShift := Cat(txShift(6, 0), 0.U(1.W)); bit := bit + 1.U
                  state := bitHold; timer := holdCycles - 1.U
                }.otherwise {
                  when(op === writeOp) { lastAck := !sda; nack := sda }
                  state := finishHold; timer := holdCycles - 1.U
                }
              }
          }.otherwise { timer := timer - 1.U }
      }
      is(finishHold) {
        when(timer === 0.U) {
          dataPull := false.B
          when(finishingByte && op === recoverOp) {
            state := specialHold; stopSpecial := true.B; timer := holdCycles - 1.U
          }.otherwise {
            state := idle; done := true.B
            when(finishingByte && op === readOp) { rxData := receiveByte(rxShift); rxValid := true.B }
          }
        }.otherwise { timer := timer - 1.U }
      }
      is(specialHold) {
        when(timer === 0.U) { dataPull := stopSpecial; state := specialLow; timer := lowCycles - 1.U }
          .otherwise { timer := timer - 1.U }
      }
      is(specialLow) {
        when(timer === 0.U) { clockPull := false.B; state := specialWait }
          .otherwise { timer := timer - 1.U }
      }
      is(specialWait) {
        when(scl) { progress := true.B; state := specialHigh; timer := freeCycles - 1.U }
      }
      is(specialHigh) {
        when(!scl) { busFault := true.B; abort() }
          .elsewhen(!stopSpecial && !sda) { lost := true.B; abort() }
          .elsewhen(timer === 0.U) {
            when(stopSpecial) { dataPull := false.B; state := stopFree; timer := freeCycles - 1.U }
              .otherwise { dataPull := true.B; state := startHold; timer := freeCycles - 1.U; finishingByte := false.B }
          }.otherwise { timer := timer - 1.U }
      }
      is(stopFree) {
        when(!scl || !sda) { timer := freeCycles - 1.U }
          .elsewhen(timer === 0.U) {
            state := idle; owned := false.B; done := true.B; progress := true.B
            recovered := recoveryDone(recovering); recovering := false.B
          }.otherwise { timer := timer - 1.U }
      }
    }
    // Byte counters preserve the exact 16-bit deadline without a long shared
    // mux-before-subtract path from protocol completion through all 16 bits.
    when(!waiting || progress) {
      watchLow := timeoutCycles(7, 0) - 1.U
      watchHigh := timeoutCycles(15, 8) - (timeoutCycles(7, 0) === 0.U).asUInt
    }.elsewhen(timeoutExpired(watchLow === 0.U && watchHigh === 0.U)) {
      timedOut := true.B; abort()
    }.otherwise {
      watchLow := watchLow - 1.U
      when(watchLow === 0.U) { watchHigh := watchHigh - 1.U }
    }

    regs.hw("rx_data_value_d") := rxData
    regs.hw("status_busy_d") := busy.asUInt; regs.hw("status_owned_d") := owned.asUInt
    regs.hw("status_rx_valid_d") := rxValid.asUInt; regs.hw("status_last_ack_d") := lastAck.asUInt
    regs.hw("status_scl_d") := scl.asUInt; regs.hw("status_sda_d") := sda.asUInt
    regs.hw("status_enabled_d") := enabled.asUInt
    regs.hw("active_timing_hold_d") := holdCycles; regs.hw("active_timing_low_d") := lowCycles
    regs.hw("active_timing_high_d") := highCycles; regs.hw("active_timing_free_d") := freeCycles
    regs.hw("active_timeout_cycles_d") := timeoutCycles
    val eventNames = Seq("done", "nack", "arbitration_lost", "timeout", "command_error", "recovered", "bus_fault")
    val eventValues = Seq(done, nack, lost, timedOut, conflict || (requested && !accepted), recovered, busFault)
    for((name, value) <- eventNames.zip(eventValues)) regs.hw(s"events_${name}_set") := value.asUInt
    val eventBits = VecInit(eventNames.map(n => regs.hw(s"events_${n}_q").asBool)).asUInt
    irq := RegNext((eventBits & regs.hw("irq_enable_mask_q")).orR ||
      (rxValid && regs.hw("irq_enable_rx_valid_q").asBool), false.B)
    clockHold := RegNext(busy || owned || (accepted && !pulse("apply")), false.B)
    quiescent := RegNext(!busy && !owned && !(accepted && !pulse("apply")), true.B)
  }
}
