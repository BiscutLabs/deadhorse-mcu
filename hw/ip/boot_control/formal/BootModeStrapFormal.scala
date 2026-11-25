package deadhorse.boot_control
import chisel3._
import _root_.circt.stage.ChiselStage

class BootModeStrapFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val qualified=IO(Input(Bool()));val pad=IO(Input(Bool()))
  val d=Module[BootModeStrap](if(variant=="raw") new BootModeStrap {
    override protected def heldValue(held: Bool,raw: Bool): Bool=raw
  } else new BootModeStrap)
  d.clk:=clock;d.wholeReset_n:=reset_n;d.qualified:=qualified;d.pad:=pad
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val seen=RegInit(false.B);val expected=RegInit(false.B)
    when(!seen && qualified) {seen:=true.B;expected:=pad}
    if(variant=="cover") {
      cover(seen && expected && !pad)
      cover(seen && !expected && pad)
    } else {
      assert(d.frozen===seen)
      assert(d.value===expected)
    }
  }
}
object EmitBootModeStrapFormal extends App {
  require(args.length==1)
  for(v<-Seq("correct","raw","cover")) ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new BootModeStrapFormal(v)),Array("--target-dir",s"${args(0)}/$v"),
    Array("--disable-all-randomization","--disable-opt","--lint-static-asserts=false",
      "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
