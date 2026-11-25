package deadhorse.boot_control
import chisel3._
import _root_.circt.stage.ChiselStage

class BootResetContextFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val hold=IO(Input(Bool()));val commit=IO(Input(Bool()));val key=IO(Input(Bool()))
  val d=Module(new BootResetContext {
    override protected def initialHold: Boolean=variant!="stale"
    override protected def validCommit(k: Bool): Bool=if(variant=="key") true.B else k
  })
  d.clk:=clock;d.epochReset_n:=reset_n;d.warmReleasePending:=false.B;d.warmHold:=hold;d.commit:=commit;d.commitKey:=key
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val armed=RegInit(false.B);val expectedFresh=RegInit(false.B);val expectedReady=RegInit(false.B)
    when(!hold){armed:=true.B}
    when(hold && armed){expectedFresh:=true.B;armed:=false.B}
    when(commit && key){expectedReady:=true.B}
    val expectedError=RegNext(commit && !key,false.B)
    if(variant=="cover") {
      cover(d.freshWarmReset && !d.contextReady)
      cover(d.freshWarmReset && d.contextReady)
      cover(d.contextReady && !d.freshWarmReset)
    } else {
      assert(d.freshWarmReset===expectedFresh)
      assert(d.contextReady===expectedReady)
      assert(d.error===expectedError)
    }
  }
}
object EmitBootResetContextFormal extends App {
  require(args.length==1)
  for(v<-Seq("correct","stale","key","cover")) ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new BootResetContextFormal(v)),Array("--target-dir",s"${args(0)}/$v"),
    Array("--disable-all-randomization","--disable-opt","--lint-static-asserts=false",
      "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
