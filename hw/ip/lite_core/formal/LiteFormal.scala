package deadhorse.lite_core
import chisel3._
import chisel3.util._
import deadhorse.lib.LocalBus

class LiteBaselineEquivalence(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val ready=IO(Input(Bool()));val valid=IO(Input(Bool()))
  val data=IO(Input(UInt(32.W)));val error=IO(Input(Bool()))
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val a=Module[ClockedCore](if(variant=="corrupt") new ClockedCore {
      trace.data:=retired.data ^ 1.U
    } else new ClockedCore)
    val b=Module(new lite_reference.ClockedCore)
    a.request.ready:=ready;b.request.ready:=ready
    a.response.valid:=valid;b.response.valid:=valid
    a.response.bits.data:=data;b.response.bits.data:=data
    a.response.bits.error:=error;b.response.bits.error:=error
    if(variant=="cover") {
      cover(a.traceEvent && a.trace.writeRegister)
      cover(a.request.fire && a.request.bits.operation===Operation.Read.U)
      cover(a.request.fire && a.request.bits.operation===Operation.Write.U)
      cover(a.request.fire && a.request.bits.operation===Operation.Halt.U)
    } else {
      assert(a.request.valid===b.request.valid);assert(a.request.bits.asUInt===b.request.bits.asUInt)
      assert(a.response.ready===b.response.ready);assert(a.traceEvent===b.traceEvent)
      when(a.traceEvent) {assert(a.trace.asUInt===b.trace.asUInt)}
    }
  }
}

class LiteAdapterFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val request=IO(Flipped(Decoupled(new MemoryRequest)))
  val response=IO(Decoupled(new MemoryResponse));val bus=IO(Flipped(new LocalBus))
  val d=Module[LiteBusAdapter](if(variant=="corrupt") new LiteBusAdapter {
    override protected def returned(value: UInt): UInt=value ^ 1.U
  } else new LiteBusAdapter)
  d.clk:=clock;d.reset_n:=reset_n;d.request<>request;response<>d.response;bus<>d.bus
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val phase=RegInit(0.U(3.W)) // idle, offered, granted, response, terminal
    val saved=Reg(new MemoryRequest);val returned=Reg(new MemoryResponse)
    when(request.fire) {
      saved:=request.bits;phase:=Mux(request.bits.operation===3.U,4.U,1.U)
    }
    when(bus.req && bus.gnt) {phase:=2.U}
    when(phase===2.U && bus.rvalid) {returned.data:=bus.rdata;returned.error:=bus.err;phase:=3.U}
    when(response.fire) {phase:=0.U}
    if(variant=="cover") {
      cover(response.fire && !response.bits.error)
      cover(response.fire && response.bits.error)
      cover(bus.req && !bus.gnt);cover(response.valid && !response.ready);cover(d.halted)
    } else {
      when(request.fire) {assert(phase===0.U)}
      assert(bus.req===(phase===1.U));assert(response.valid===(phase===3.U))
      assert(d.halted===(phase===4.U))
      when(bus.req) {
        assert(bus.bits.addr===Cat(saved.address(31,2),0.U(2.W)))
        assert(bus.bits.be===saved.mask);assert(bus.bits.wdata===saved.data)
        assert(bus.bits.we===(saved.operation===2.U));assert(bus.bits.origin===0.U)
      }
      when(response.valid) {assert(response.bits.asUInt===returned.asUInt)}
    }
  }
}
object EmitLiteFormal extends App {
  require(args.length==2)
  for(v<-Seq("correct","corrupt","cover")) {
    _root_.circt.stage.ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(args(0) match {
      case "baseline"=>new LiteBaselineEquivalence(v)
      case "adapter"=>new LiteAdapterFormal(v)
      case "control"=>new LiteControlFormal(v)
    }),Array("--target-dir",s"${args(1)}/$v"),Array("--disable-all-randomization","--disable-opt",
      "--lint-static-asserts=false","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
  }
}

/** Whole production core, arbitrary memory/IRQ stimulus and repeated reset.
  * This establishes interface/control safety, not ISA/CSR correctness.
  */
class LiteControlFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val start=IO(Input(Bool()));val entry=IO(Input(UInt(32.W)));val irq=IO(Input(Bool()))
  val ready=IO(Input(Bool()));val valid=IO(Input(Bool()))
  val data=IO(Input(UInt(32.W)));val error=IO(Input(Bool()))
  val d=Module[LiteCore](if(variant=="corrupt") new LiteCore {
    override protected def requestAddress(value: UInt): UInt=value ^ Mux(irq,4.U,0.U)
  } else new LiteCore)
  d.clk:=clock;d.reset_n:=reset_n;d.start:=start;d.entry:=entry;d.irq:=irq
  d.request.ready:=ready;d.response.valid:=valid;d.response.bits.data:=data;d.response.bits.error:=error
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val started=RegInit(false.B)
    when(start && !entry(1,0).orR) {started:=true.B}
    val outstanding=RegInit(false.B)
    when(d.request.fire) {outstanding:=true.B}
    when(d.response.fire) {outstanding:=false.B}
    val stalled=RegNext(d.request.valid && !ready,false.B)
    val previous=RegNext(d.request.bits.asUInt)
    val replied=RegNext(d.response.fire,false.B)
    if(variant=="cover") {
      cover(d.request.fire && d.request.bits.operation===0.U)
      cover(d.request.fire && d.request.bits.operation===1.U)
      cover(d.request.fire && d.request.bits.operation===2.U)
      cover(d.trace.valid && d.trace.trap)
      cover(d.sleeping)
      cover(d.interruptTaken)
    } else {
      assert(d.halted=== !started)
      assert(!d.request.valid || started && !outstanding)
      assert(d.response.ready===outstanding)
      assert(!d.sleeping || !d.request.valid && !outstanding)
      assert(!d.interruptTaken || !d.request.valid && !outstanding && !d.sleeping)
      assert(!d.rvfi.valid || replied)
      assert(d.rvfi.valid===d.trace.valid)
      assert(!stalled || d.request.valid)
      assert(!stalled || d.request.bits.asUInt===previous)
    }
  }
}

/** Same asynchronous wrapper on both sides; every named state element is matched. */
class LiteStateModel(reference: Boolean) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val request=IO(Decoupled(new MemoryRequest));val response=IO(Flipped(Decoupled(new MemoryResponse)))
  val trace=IO(Output(new Retirement));val traceEvent=IO(Output(Bool()))
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    if(reference) {
      val core=Module(new lite_reference.ClockedCore)
      request.valid:=core.request.valid;request.bits:=core.request.bits.asUInt.asTypeOf(new MemoryRequest)
      core.request.ready:=request.ready;core.response.valid:=response.valid
      core.response.bits:=response.bits.asUInt.asTypeOf(chiselTypeOf(core.response.bits));response.ready:=core.response.ready
      trace:=core.trace.asUInt.asTypeOf(new Retirement);traceEvent:=core.traceEvent
    } else {
      val core=Module(new ClockedCore)
      request<>core.request;core.response<>response;trace:=core.trace;traceEvent:=core.traceEvent
    }
  }
}
object EmitLiteStateModels extends App {
  require(args.length==1)
  for((name,reference)<-Seq("gold"->true,"candidate"->false))
    _root_.circt.stage.ChiselStage.emitSystemVerilogFile(new LiteStateModel(reference),
      Array("--target-dir",s"${args(0)}/$name"),Array("--disable-all-randomization","--preserve-values=named",
        "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
