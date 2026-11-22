package deadhorse.dma
import chisel3._
import _root_.circt.stage.ChiselStage
import deadhorse.lib.LocalBus

/** Bus replies are unconstrained; safety does not rely on eventual service. */
class DmaSafetyFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val owner=IO(Input(UInt(3.W)));val settings=IO(Input(Vec(4,new DmaSettings)))
  val start=IO(Input(UInt(4.W)));val abort=IO(Input(UInt(4.W)));val requests=IO(Input(UInt(17.W)))
  val memory=IO(Flipped(new LocalBus));val peripheral=IO(Flipped(new LocalBus))
  val d=Module[DmaEngine](if(variant=="corrupt") new DmaEngine(DmaStandalone.endpoints,
    DmaStandalone.memoryBase,DmaStandalone.memorySize,formalChecks=true) {
      override protected def busOrigin(value: UInt): UInt=0.U
    } else new DmaEngine(DmaStandalone.endpoints,DmaStandalone.memoryBase,DmaStandalone.memorySize,
      formalChecks=variant!="cover"))
  d.clk:=clock;d.reset_n:=reset_n;d.owner:=owner;d.settings:=settings
  d.start:=start;d.abort:=abort;d.requests:=requests;memory<>d.memory;peripheral<>d.peripheral
  if(variant=="cover") withClockAndReset(clock,(!reset_n).asAsyncReset) {
    cover(d.done.orR);cover(d.failed.orR);cover(d.aborted.orR)
    cover(d.memory.req && d.memory.bits.we);cover(d.pwmAck.orR)
  }
}
class DmaDeniedFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new LocalBus)
  val d=Module[Dma](if(variant=="corrupt") new Dma("build/t23/dma/dma_regs.json",
    DmaStandalone.endpoints,DmaStandalone.memoryBase,DmaStandalone.memorySize) {
      override protected def allowed(origin: UInt): Bool=true.B
    } else new Dma("build/t23/dma/dma_regs.json",DmaStandalone.endpoints,DmaStandalone.memoryBase,DmaStandalone.memorySize))
  d.clk:=clock;d.reset_n:=reset_n;d.owner:=1.U;d.requests:="h1ffff".U;d.bus<>bus
  d.bus.bits.origin:=Mux(bus.bits.origin===1.U,0.U,bus.bits.origin)
  Seq(d.memory,d.peripheral).foreach {p=>p.gnt:=true.B;p.rvalid:=false.B;p.rdata:=0.U;p.err:=false.B}
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val accepted=RegNext(bus.req && bus.gnt,false.B)
    if(variant=="cover") {cover(bus.rvalid && bus.err)} else {
      assert(bus.rvalid===accepted)
      when(bus.rvalid) {assert(bus.err);assert(bus.rdata===0.U)}
      assert(!d.memory.req);assert(!d.peripheral.req);assert(!d.irq);assert(d.pwmAck===0.U)
    }
  }
}
object EmitDmaFormal extends App {
  require(args.length==2)
  for(v<-Seq("correct","corrupt","cover")) {
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(args(0) match {
      case "safety"=>new DmaSafetyFormal(v)
      case "denied"=>new DmaDeniedFormal(v)
    }),Array("--target-dir",s"${args(1)}/$v"),Array("--disable-all-randomization","--disable-opt",
      "--lint-static-asserts=false","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
  }
}
