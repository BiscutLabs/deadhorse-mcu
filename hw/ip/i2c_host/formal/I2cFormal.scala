package deadhorse.i2c_host

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

/** Mutation points are identity functions in every production instance. */
class I2cFault(json: String, role: String) extends I2cHost(json) {
  override protected def allowed(origin: UInt, owner: UInt): Bool =
    if(role == "denied") true.B else origin === owner
  override protected def outputBit(value: Bool): Bool = if(role == "write") !value else value
  override protected def receiveByte(value: UInt): UInt = if(role == "read") value ^ 1.U else value
  override protected def recoveryDone(value: Bool): Bool = if(role == "recover") false.B else value
  override protected def timeoutExpired(value: Bool): Bool = if(role == "timeout") false.B else value
}

/** Scripted public-MMIO master and independent wired-AND pin peer. No DUT
  * internals are read. Bounded claims deliberately use one legal timing tuple. */
class I2cProtocolFormal(json: String, variant: String, role: String) extends RawModule {
  val clock = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val payload = IO(Input(UInt(8.W))); val ack = IO(Input(Bool()))
  val sleeping = IO(Input(Bool())); val stuckClock = IO(Input(Bool()))
  val d = Module(if(variant == "corrupt") new I2cFault(json, role) else new I2cHost(json))
  d.clk := clock; d.reset_n := reset_n; d.owner := 0.U; d.sleepEnable := false.B
  withClockAndReset(clock, (!reset_n).asAsyncReset) {
    val normal = role == "write" || role == "read"
    val pc = RegInit(0.U(4.W)); val waiting = RegInit(false.B)
    val byte = RegInit(0.U(8.W)); val readAck = RegInit(false.B)
    val stuck = RegInit(false.B); val active = RegInit(false.B)
    val complete = RegInit(false.B); val age = RegInit(0.U(9.W))
    val status = RegInit(0.U(32.W)); val received = RegInit(0.U(8.W))
    val events = RegInit(0.U(7.W))
    when(age =/= 511.U) { age := age + 1.U }
    val commandPc = if(normal) 7 else 4
    val statusPc = if(normal) 8 else 5
    val dataPc = if(normal) 9 else 6
    val eventsPc = if(normal) 10 else 7
    val command = if(role == "write") 2.U else if(role == "read")
      Mux(readAck, 68.U, 4.U) else if(role == "recover") 16.U else 1.U
    val addresses = Seq(0.U -> 0.U, 1.U -> 4.U, 2.U -> 8.U, 3.U -> 12.U) ++
      (if(normal) Seq(4.U -> 16.U, 5.U -> 12.U, 6.U -> 24.U) else Seq.empty) ++
      Seq(commandPc.U -> 12.U, statusPc.U -> 24.U, dataPc.U -> 20.U, eventsPc.U -> 28.U)
    val values = Seq(0.U -> 1.U, 1.U -> "h04040401".U, 2.U -> (if(role == "timeout") 8.U else 64.U),
      3.U -> 32.U) ++ (if(normal) Seq(4.U -> byte.pad(32), 5.U -> 1.U) else Seq.empty) ++
      Seq(commandPc.U -> command)
    val reading = pc === statusPc.U || pc === dataPc.U || pc === eventsPc.U || (normal.B && pc === 6.U)
    d.bus.req := !complete && !waiting
    d.bus.bits.addr := MuxLookup(pc, 0.U)(addresses)
    d.bus.bits.wdata := MuxLookup(pc, 0.U)(values)
    d.bus.bits.we := !reading; d.bus.bits.be := 15.U; d.bus.bits.origin := 0.U
    when(d.bus.req && d.bus.gnt) {
      waiting := true.B
      when(pc === 0.U) { stuck := stuckClock; byte := payload; readAck := ack }
      when(pc === commandPc.U) { active := true.B }
    }
    when(d.bus.rvalid) {
      waiting := false.B
      when(normal.B && pc === 6.U) {
        when(!d.bus.rdata(0) && d.bus.rdata(1)) { pc := 7.U }
      }.elsewhen(pc === statusPc.U) {
        when(!d.bus.rdata(0)) { status := d.bus.rdata; pc := (statusPc + 1).U }
      }.elsewhen(pc === dataPc.U) { received := d.bus.rdata(7, 0); pc := (dataPc + 1).U }
        .elsewhen(pc === eventsPc.U) { events := d.bus.rdata(6, 0); complete := true.B }
        .otherwise { pc := pc + 1.U }
    }
    val admitted = RegInit(false.B)
    val sawSleep = RegInit(false.B)
    when(active && d.clockHold) { admitted := true.B }
    when(admitted && sleeping && d.clockHold) { sawSleep := true.B }
    d.sleepRequest := sleeping && admitted

    // The peer advances only after an externally observed falling edge. It
    // drives WRITE ACK, or symbolic READ data, and otherwise releases SDA.
    val scl = !d.sclLow
    val oldScl = RegNext(scl, true.B)
    val rise = active && !complete && scl && !oldScl
    val fall = active && !complete && !scl && oldScl
    val rises = RegInit(0.U(5.W)); val falls = RegInit(0.U(5.W))
    when(rise) { rises := rises + 1.U }
    when(fall && rises =/= 0.U) { falls := falls + 1.U }
    val peerLow = if(role == "write") active && falls === 8.U
      else if(role == "read") active && falls < 8.U && !byte(7.U - falls(2, 0))
      else false.B
    val resolvedSda = !d.sdaLow && !peerLow
    d.sclIn := (if(role == "timeout") scl && !stuck else scl)
    d.sdaIn := (if(role == "timeout") resolvedSda && stuck else resolvedSda)
    val oldSda = RegNext(resolvedSda, true.B)
    val stopSeen = RegInit(false.B)
    when(active && scl && oldScl && !oldSda && resolvedSda) { stopSeen := true.B }
    val highAge = RegInit(0.U(9.W)); val lowAge = RegInit(0.U(9.W))
    when(scl) { highAge := Mux(highAge === 511.U, highAge, highAge + 1.U); lowAge := 0.U }
      .otherwise { lowAge := Mux(lowAge === 511.U, lowAge, lowAge + 1.U); highAge := 0.U }

    val common = Seq(!d.bus.rvalid || waiting, !d.bus.rvalid || !d.bus.err)
    val deadline = if(normal) 310 else if(role == "recover") 245 else 145
    val completion = age =/= deadline.U || complete
    val outcomes = if(role == "write") Seq(
      !complete || (rises === 9.U && falls === 9.U && status(1) && status(3)),
      !complete || events === 1.U,
      !rise || rises >= 8.U || resolvedSda === byte(7.U - rises(2, 0)),
      !rise || rises =/= 8.U || !resolvedSda)
    else if(role == "read") Seq(
      !complete || (rises === 9.U && falls === 9.U && status(1) && status(2)),
      !complete || received === byte, !complete || events === 1.U,
      !rise || rises >= 8.U || !d.sdaLow,
      !rise || rises =/= 8.U || d.sdaLow === readAck)
    else if(role == "recover") Seq(
      !complete || (rises === 10.U && falls === 9.U && stopSeen && !status(1)),
      !complete || events === 33.U,
      !rise || rises >= 9.U || !d.sdaLow,
      !complete || (!d.sclLow && !d.sdaLow))
    else Seq(!complete || events === 9.U, !complete || !status(1),
      !complete || (!d.sclLow && !d.sdaLow))
    val waveform = if(role == "timeout") Seq.empty else Seq(
      !fall || rises === 0.U || highAge >= 4.U,
      !rise || lowAge >= 5.U,
      !active || complete || !scl || !oldScl || oldSda === resolvedSda || (role == "recover").B)
    if(variant == "cover") {
      if(role == "timeout") { cover(complete && stuck); cover(complete && !stuck) }
      else {
        cover(complete && byte === "ha5".U); cover(complete && sawSleep)
        if(role == "read") { cover(complete && readAck); cover(complete && !readAck) }
      }
    } else {
      // One conjunction retains every named obligation without relying on the
      // number of separately optimized assertion cells as the specification.
      assert((common ++ Seq(completion) ++ outcomes ++ waveform).reduce(_ && _))
    }
  }
}

class I2cDeniedFormal(json: String, variant: String) extends RawModule {
  val clock = IO(Input(Clock())); val reset_n = IO(Input(Bool())); val bus = IO(new deadhorse.lib.LocalBus)
  val d = Module(if(variant == "corrupt") new I2cFault(json, "denied") else new I2cHost(json))
  d.clk := clock; d.reset_n := reset_n; d.owner := 0.U; d.sclIn := true.B; d.sdaIn := true.B
  d.sleepRequest := false.B; d.sleepEnable := false.B; d.bus <> bus
  d.bus.bits.origin := Mux(bus.bits.origin === 0.U, 1.U, bus.bits.origin)
  withClockAndReset(clock, (!reset_n).asAsyncReset) {
    val granted = RegNext(bus.req && bus.gnt, false.B)
    if(variant == "cover") {
      cover(bus.rvalid && bus.err); cover(bus.rvalid && bus.err && bus.req)
    } else {
      assert(bus.rvalid === granted && (!bus.rvalid || (bus.err && bus.rdata === 0.U)) &&
        !d.pinsEnable && !d.sclLow && !d.sdaLow && !d.irq && !d.clockHold && d.quiescent)
    }
  }
}

object EmitI2cFormal {
  def main(args: Array[String]): Unit = {
    require(args.length == 3, "EmitI2cFormal <json> <write|read|recover|timeout|denied> build/<output>")
    require(Set("write", "read", "recover", "timeout", "denied").contains(args(1)))
    val root = Paths.get(args(2)).toAbsolutePath.normalize
    require(root.startsWith(Paths.get("build").toAbsolutePath.normalize))
    for(variant <- Seq("correct", "corrupt", "cover")) {
      val directory = root.resolve(variant); Files.createDirectories(directory)
      def design: RawModule = if(args(1) == "denied") new I2cDeniedFormal(args(0), variant)
        else new I2cProtocolFormal(args(0), variant, args(1))
      ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(design),
        Array("--target-dir", directory.toString),
        Array("--disable-all-randomization", "--verification-flavor=immediate", "--lower-to-core", "-strip-debug-info"))
    }
  }
}
