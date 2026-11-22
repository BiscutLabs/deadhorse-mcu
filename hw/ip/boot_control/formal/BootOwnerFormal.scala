package deadhorse.boot_control
import chisel3._
import _root_.circt.stage.ChiselStage

class BootOwnerFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val serviceReset_n=IO(Input(Bool()))
  val start=IO(Input(Bool()));val req=IO(Input(Bool()));val addr=IO(Input(UInt(32.W)))
  val data=IO(Input(UInt(32.W)));val write=IO(Input(Bool()));val be=IO(Input(UInt(4.W)))
  val origin=IO(Input(UInt(3.W)))
  val d=Module[BootControl](if(variant=="owner") new BootControl("build/t28/boot_control/boot_control_regs.json") {
    override protected def permitted(o: UInt): Bool=true.B
  } else new BootControl("build/t28/boot_control/boot_control_regs.json"))
  d.clk:=clock;d.epochReset_n:=reset_n;d.reset_n:=serviceReset_n;d.startAccepted:=start
  d.bus.req:=req;d.bus.bits.addr:=addr;d.bus.bits.wdata:=data;d.bus.bits.we:=write;d.bus.bits.be:=be
  // Explicit denied-origin stimulus; all seven denied origins remain reachable.
  d.bus.bits.origin:=Mux(origin===0.U,1.U,origin)
  withClockAndReset(clock,(!(reset_n && serviceReset_n)).asAsyncReset) {
    if(variant=="cover") {
      cover(d.bus.rvalid && d.bus.err)
      cover(d.bus.gnt && start)
    } else {
      assert(!d.released)
      assert(!d.bus.rvalid || d.bus.err)
    }
  }
}
object EmitBootOwnerFormal extends App {
  require(args.length==1)
  for(v<-Seq("correct","owner","cover")) ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new BootOwnerFormal(v)),Array("--target-dir",s"${args(0)}/$v"),
    Array("--disable-all-randomization","--disable-opt","--lint-static-asserts=false",
      "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
