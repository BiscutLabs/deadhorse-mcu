package deadhorse.aon_gpio
import chisel3._
import chisel3.util._
import deadhorse.lib.CdcPulseCapture
import _root_.circt.stage.ChiselStage

/** Four formal sampling edges per AON period. The pad may pulse for only one
  * sampling edge (shorter than one AON cycle); enable/polarity are configured
  * constants, matching the documented armed-capture protocol. Reset and clear
  * remain independent and arbitrary. No assumption about pulse timing. */
class AonCaptureFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val pad=IO(Input(Bool()));val clear=IO(Input(Bool()))
  val phase=withClockAndReset(clock,(!reset_n).asAsyncReset) {val p=RegInit(0.U(2.W));p:=p+1.U;p}
  val d=Module[CdcPulseCapture](if(variant=="missing") new CdcPulseCapture {
    override protected def captureInput(value: Bool): Bool=false.B
  } else if(variant=="early_clear") new CdcPulseCapture {
    override protected def acceptedClear(command: Bool,seen: Bool): Bool=command
  } else new CdcPulseCapture)
  d.clk:=phase(1).asClock;d.reset_n:=reset_n;d.input:=pad;d.enable:=true.B
  d.falling:=(variant=="falling").B;d.clear:=clear
  // Status/clear are sampled on their actual AON edge. Using the faster monitor
  // edge would miss a legal clear between monitor edges during a derived-clock
  // transition and incorrectly claim that the acknowledged status must persist.
  withClockAndReset(phase(1).asClock,(!reset_n).asAsyncReset) {
    val held=RegInit(false.B)
    val priorPending=RegNext(d.pending,false.B)
    when(d.pending && !priorPending) {held:=true.B}
    // Acknowledgement authorizes the later synchronizer-delayed fall; the
    // still-high status during that delay must not create a second obligation.
    when(d.pending && clear) {held:=false.B}
    assert(!held || d.pending)
  }
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val tracking=RegInit(false.B);val elapsed=RegInit(0.U(4.W));val shortened=RegInit(false.B)
    // With enable/polarity fixed, initialization is the only arming epoch.
    // An idle clear may lower the public rearm indication but cannot cancel an
    // unseen edge; do not condition that obligation on !clear via d.armed.
    val initialized=RegInit(false.B);when(d.armed) {initialized:=true.B}
    val active=pad ^ (variant=="falling").B
    when(initialized && active && !d.pending && !tracking) {tracking:=true.B;elapsed:=0.U;shortened:=false.B}
    when(tracking) {
      elapsed:=elapsed+1.U
      when(!active && elapsed<4.U) {shortened:=true.B}
      when(d.pending) {tracking:=false.B}
      assert(d.pending || elapsed<12.U)
    }
    cover(tracking && d.pending && shortened)
    cover(tracking && clear && !d.pending)
  }
}
object EmitAonCaptureFormal extends App {
  require(args.length==1)
  for(v<-Seq("correct","falling","missing","early_clear")) ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new AonCaptureFormal(v)),Array("--target-dir",s"${args(0)}/$v"),
    Array("--disable-all-randomization","--disable-opt","--lint-static-asserts=false",
      "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
