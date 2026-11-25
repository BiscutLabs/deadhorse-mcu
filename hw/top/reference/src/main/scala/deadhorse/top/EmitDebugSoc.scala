package deadhorse.top
import chisel3._
import chisel3.util.experimental.BoringUtils
import deadhorse.lib.ClockGateTarget
/** Production features and actual TAP, with the project's simulation clock-cell model. */
object EmitDebugSoc extends App {
  require((args.length==1 || args.length==2) && args(0).startsWith("build/") && !args(0).contains(".."))
  val variant=if(args.length==2) args(1) else "correct"
  require(Set("correct","missing-halt").contains(variant))
  val c=SocProduction.config()
  def design: SocExternalClockTest=new SocExternalClockTest("build/t20/map/soc.json",c.uart,
      "build/plan05/debug-firmware/boot.hex",gateTarget=ClockGateTarget.Model,i1Config=Some(c)) {
    override def desiredName="SocExternalClockTest"
    override protected def debugRequest(request: Bool): Bool=if(variant=="missing-halt") false.B else request
    val p=subsystem.get;val h=p.liteHart.get
    val held=BoringUtils.bore(p.liteBootHeld)
    val pending=BoringUtils.bore(p.haltLite) || BoringUtils.bore(p.litePending)
    val mode=BoringUtils.bore(h.debug.get.mode)
    val start=BoringUtils.bore(h.start);val request=BoringUtils.bore(h.core.request.valid)
    val retired=BoringUtils.bore(h.rvfi.valid)
    val resetHaltObserved=IO(Output(Bool()))
    withClockAndReset(i1.get.aonClock,(!coldReset_n || !warmReset_n).asAsyncReset) {
      val previousHeld=RegNext(held,true.B);val waiting=RegInit(false.B)
      val observed=RegInit(false.B);resetHaltObserved:=observed
      when(previousHeld && !held && pending) {observed:=true.B}
      when(previousHeld && !held && pending) {waiting:=true.B}
      when(mode || held) {waiting:=false.B}
      when((waiting || previousHeld && !held && pending) && !mode) {
        assert(!start && !request && !retired,"reset-halt must precede lite application execution")
      }
    }
  }
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(design),
    Array("--target-dir",args(0)),Array("--disable-all-randomization","--strip-debug-info",
      "--preserve-values=named","--verification-flavor=immediate","--lower-to-core",
      "--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
      "--ckg-enable=en_i","--ckg-test-enable=test_en_i"))
}
