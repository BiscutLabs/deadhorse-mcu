package deadhorse.usb

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files,Paths}

class UsbEarlyEnable extends UsbBitEnable {
  override protected def pulse(count: UInt): Bool=count(0)
}
class UsbLostWake extends UsbResume(17) {
  override protected def retain(value: Bool): Bool=false.B
}
class UsbWrongOwner(json: String) extends UsbRegisters(json) {
  override protected def allowed(origin: UInt,selected: UInt): Bool=true.B
}
class UsbUnsafePads extends UsbPadSafety {
  override protected def permitted(reset: Bool,power: Bool): Bool=power
}
class UsbPadsFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val vbus=IO(Input(Bool()))
  val drive=IO(Input(Bool()));val attach=IO(Input(Bool()))
  val d=Module(if(variant=="corrupt") new UsbUnsafePads else new UsbPadSafety)
  d.reset_n:=reset_n;d.vbus:=vbus;d.requestedDrive:=drive;d.requestedPullup:=attach
  // Observe even while reset is asserted. The vendor requests are arbitrary:
  // this over-approximates all vendor states without assuming their safety.
  withClockAndReset(clock,false.B) {
    if(variant=="cover") {cover(d.drive && d.pullupEnable);cover(!reset_n && drive && attach && vbus)}
    else {
      when(!reset_n || !vbus){assert(!d.drive);assert(!d.pullupEnable)}
      when(reset_n && vbus){assert(d.drive===drive);assert(d.pullupEnable===attach)}
    }
  }
}
class UsbCadenceFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val d=Module(if(variant=="corrupt") new UsbEarlyEnable else new UsbBitEnable)
  d.clk:=clock;d.reset_n:=reset_n
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    // Specification shift schedule, independent of the DUT binary counter.
    val schedule=RegInit(1.U(4.W));schedule:=Cat(schedule(2,0),schedule(3))
    val up=RegNext(true.B,false.B)
    val history=RegInit(0.U(3.W));history:=Cat(history(1,0),d.enable)
    if(variant=="cover") {cover(d.enable && history===0.U);cover(history(2) && !d.enable)}
    else {assert(d.enable === (up && schedule(0)));assert(!d.enable || !history.orR)}
  }
}
class UsbResumeFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val dp=IO(Input(Bool()));val dn=IO(Input(Bool()));val attached=IO(Input(Bool()))
  val driving=IO(Input(Bool()));val clear=IO(Input(Bool()))
  val d=Module(if(variant=="corrupt") new UsbLostWake else new UsbResume(17))
  d.clk:=clock;d.reset_n:=reset_n;d.dp:=dp;d.dn:=dn;d.attached:=attached;d.driving:=driving;d.clear:=clear
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val wasPending=RegNext(d.pending,false.B);val wasClear=RegNext(clear,false.B)
    // A conservative public-input witness: settled idle followed by settled K.
    // No assumption constrains the DUT's input or internal state.
    val jHistory=RegInit(0.U(24.W));val armedHistory=RegInit(0.U(28.W))
    jHistory:=Cat(jHistory(22,0),dp && !dn)
    armedHistory:=Cat(armedHistory(26,0),attached && !driving)
    val trigger=RegInit(0.U(4.W));trigger:=Cat(trigger(2,0),jHistory.andR && !dp && dn)
    val kHistory=RegInit(0.U(4.W));kHistory:=Cat(kHistory(2,0),!dp && dn)
    if(variant=="cover") {
      cover(trigger(3) && kHistory.andR && armedHistory.andR && d.pending)
      cover(wasPending && !attached && d.pending)
    } else {
      when(wasPending && !wasClear) {assert(d.pending)}
      when(trigger(3) && kHistory.andR && armedHistory.andR && !wasClear) {assert(d.pending)}
    }
  }
}
class UsbDeniedFormal(json: String,variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new deadhorse.lib.LocalBus)
  val d=Module(if(variant=="corrupt") new UsbWrongOwner(json) else new UsbRegisters(json))
  d.clk:=clock;d.reset_n:=reset_n;d.bus<>bus;d.owner:=0.U
  d.bus.bits.origin:=Mux(bus.bits.origin===0.U,1.U,bus.bits.origin)
  d.txReady:=true.B;d.rxValid:=true.B;d.rxData:=0xa5.U;d.configured:=true.B;d.connected:=true.B
  d.frame:=123.U;d.sessionReset:=false.B;d.resume:=false.B
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val grant=RegNext(bus.req && bus.gnt,false.B)
    if(variant=="cover") {cover(bus.rvalid && bus.err);cover(bus.rvalid && bus.req && bus.err)}
    else {
      assert(bus.rvalid===grant)
      when(bus.rvalid){assert(bus.err);assert(bus.rdata===0.U)}
      assert(!d.txPush);assert(!d.rxPop);assert(!d.wakeAck);assert(!d.enabled);assert(!d.irq)
    }
  }
}
object EmitUsbFormal {
  def main(args: Array[String]): Unit={
    require(args.length==3)
    val root=Paths.get(args(2)).toAbsolutePath.normalize
    require(root.startsWith(Paths.get("build").toAbsolutePath.normalize))
    for(variant<-(if(args(1)=="in" || args(1).startsWith("in_bit")) Seq("correct","corrupt","cover","withheld") else Seq("correct","corrupt","cover"))) {
      val dir=root.resolve(variant);Files.createDirectories(dir)
      def design: RawModule=args(1) match {
        case "cadence"=>new UsbCadenceFormal(variant)
        case "resume"=>new UsbResumeFormal(variant)
        case "denied"=>new UsbDeniedFormal(args(0),variant)
        case "in"=>new UsbInFormal(variant)
        case "out"=>new UsbOutFormal(variant)
        case "pads"=>new UsbPadsFormal(variant)
        case "control"=>new UsbControlFormal(variant)
        case n if n.startsWith("in_bit")=>new UsbInFormal(variant,Some(n.stripPrefix("in_bit").toInt))
        case n if n.startsWith("out_bit")=>new UsbOutFormal(variant,Some(n.stripPrefix("out_bit").toInt))
      }
      ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(design),
        Array("--target-dir",dir.toString),Array("--disable-all-randomization","--verification-flavor=immediate","--lower-to-core","-strip-debug-info"))
    }
  }
}
