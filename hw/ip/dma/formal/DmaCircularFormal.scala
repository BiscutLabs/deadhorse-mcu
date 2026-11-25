package deadhorse.dma
import chisel3._
import chisel3.util._
import deadhorse.lib._

/** Real wrapper, arbitrary MMIO/bus replies. No shadow-stability assumption. */
class DmaCircularChecked(variant: String) extends Dma("build/t23/dma/dma_regs.json",
  DmaStandalone.endpoints,DmaStandalone.memoryBase,DmaStandalone.memorySize) {
  override protected def shadowLocked(v: Bool): Bool=if(variant=="lock") false.B else v
  override protected def makeEngine(): DmaEngine=new DmaEngine(DmaStandalone.endpoints,
    DmaStandalone.memoryBase,DmaStandalone.memorySize,circularChecks=variant!="cover") {
    override protected def reloadAddress(v: UInt): UInt=if(variant=="reload") v+1.U else v
    override protected def halfItem(n: UInt,c: UInt): Bool=if(variant=="half") n===((c>>1)+1.U) else super.halfItem(n,c)
    override protected def terminalDone(r: Bool): Bool=if(variant=="done") true.B else super.terminalDone(r)
  }
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val ep=DmaStandalone.endpoints
    val pending=RegInit(false.B);val pop=RegInit(0.U(4.W))
    val stopping=RegInit(VecInit(Seq.fill(4)(false.B)))
    when(peripheral.req && peripheral.gnt) {
      pending:=true.B
      pop:=VecInit((0 until 4).map(i=>engine.busy(i) && engine.circular(i) && peripheral.bits.we &&
        peripheral.bits.addr===VecInit(ep.command.map(_.U(32.W)))(engine.settings(i).endpoint))).asUInt
    }
    when(pending && peripheral.rvalid) {pending:=false.B}
    val finished=Mux(pending && peripheral.rvalid && !peripheral.err,pop,0.U)
    for(i<-0 until 4) {
      when(!engine.busy(i)) {stopping(i):=false.B}.elsewhen(engine.abort(i)) {stopping(i):=true.B}
      val q=engine.settings(i)
      val old=RegNext(q);val wasRing=RegNext(engine.busy(i) && engine.circular(i),false.B)
      // Independent checker state: one item retires per successful UART POP.
      // These proof-only copies are not production descriptor storage.
      val referenceLeft=RegInit(0.U(16.W));val referenceCount=RegInit(0.U(16.W))
      val referenceBase=RegInit(0.U(32.W))
      when(!wasRing && engine.busy(i) && engine.circular(i)) {
        referenceLeft:=q.count;referenceCount:=q.count;referenceBase:=q.address
      }
      val reload=referenceLeft===1.U && !stopping(i) && !engine.abort(i)
      when(finished(i)) {referenceLeft:=Mux(reload,referenceCount,referenceLeft-1.U)}
      val expectedHalf=RegNext(finished(i) && referenceLeft-1.U===(referenceCount>>1),false.B)
      val expectedWrap=RegNext(finished(i) && reload,false.B)
      val wasCircular=RegNext(engine.circular(i),false.B)
      if(variant!="cover") {
        when(wasRing) {assert(q.asUInt===old.asUInt)}
        assert(engine.half(i)===expectedHalf)
        assert(engine.wrap(i)===expectedWrap)
        when(wasCircular) {assert(!engine.done(i))}
        when(wasRing && engine.busy(i) && engine.circular(i)) {
          assert(engine.remaining(i)===referenceLeft &&
            engine.current(i)===(referenceBase+referenceCount-referenceLeft))
        }
      }
    }
    if(variant!="cover") {
      // Adapter serializes register accesses; a new shadow acceptance cannot
      // overlap the preceding command's registered START pulse.
      assert(!(engine.start.orR && regs.bus.req_valid && regs.bus.req_ready))
    } else {
      cover(engine.wrap.orR)
      cover(engine.half.orR && engine.settings(0).count===3.U)
      cover(engine.aborted.orR && engine.remaining(0)===0.U)
      cover(regs.hw("events_config_error_q").orR && engine.circular.orR && engine.busy.orR)
      cover(engine.wrap.orR && (engine.busy & (engine.busy-1.U)).orR)
    }
  }
}
class DmaCircularFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val owner=IO(Input(UInt(3.W)))
  val requests=IO(Input(UInt(17.W)));val bus=IO(new LocalBus)
  val memory=IO(Flipped(new LocalBus));val peripheral=IO(Flipped(new LocalBus))
  val d=Module(new DmaCircularChecked(variant))
  d.clk:=clock;d.reset_n:=reset_n;d.owner:=owner;d.requests:=requests
  d.bus<>bus;memory<>d.memory;peripheral<>d.peripheral
}
object EmitDmaCircularFormal extends App {
  require(args.length==1)
  for(v<-Seq("correct","cover","lock","reload","half","done")) {
    _root_.circt.stage.ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new DmaCircularFormal(v)),
      Array("--target-dir",s"${args(0)}/$v"),Array("--disable-all-randomization","--disable-opt",
        "--lint-static-asserts=false","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
  }
}
