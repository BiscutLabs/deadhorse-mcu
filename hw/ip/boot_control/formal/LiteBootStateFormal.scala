package deadhorse.boot_control
import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage

/** Three-state specification, independent of the implementation's two flags.
  * Service resets flush commands only; epoch reset returns to held. */
class LiteBootStateFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val serviceReset_n=IO(Input(Bool()))
  val release=IO(Input(Bool()));val hold=IO(Input(Bool()));val releaseKey=IO(Input(Bool()));val holdKey=IO(Input(Bool()))
  val quiet=IO(Input(Bool()));val debug=IO(Input(Bool()))
  val d=Module[LiteBootState](if(variant=="early") new LiteBootState {
    override protected def drainComplete(value: Bool): Bool=true.B
  } else new LiteBootState)
  d.clk:=clock;d.epochReset_n:=reset_n;d.serviceReset_n:=serviceReset_n
  d.releaseCommand:=release;d.holdCommand:=hold;d.holdKey:=holdKey
  d.releaseKey:= (if(variant=="key") true.B else releaseKey)
  d.quiet:=quiet;d.debugOwned:=debug
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val held :: running :: draining :: Nil=Enum(3)
    val state=RegInit(held)
    val validRelease=releaseKey && state===held && !debug && !hold
    val validHold=holdKey && !debug && !release
    when(serviceReset_n) {
      when(state===held && release && validRelease) {state:=running}
      when(state===running && hold && validHold) {state:=draining}
    }
    when(state===draining && quiet) {state:=held}
    val error=withReset((!(reset_n && serviceReset_n)).asAsyncReset) {
      RegNext(serviceReset_n && (release && !validRelease || hold && !validHold),false.B)
    }
    if(variant=="cover") {
      cover(state===draining && !quiet)
      cover(state===running && !serviceReset_n)
      cover(error)
    } else {
      assert(d.held===(state===held))
      assert(d.released===(state=/=held))
      assert(d.draining===(state===draining))
      assert(d.error===error)
    }
  }
}
object EmitLiteBootStateFormal extends App {
  require(args.length==1)
  for(v<-Seq("correct","early","key","cover")) ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new LiteBootStateFormal(v)),Array("--target-dir",s"${args(0)}/$v"),
    Array("--disable-all-randomization","--disable-opt","--lint-static-asserts=false",
      "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
