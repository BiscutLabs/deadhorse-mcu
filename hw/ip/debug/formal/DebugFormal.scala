package deadhorse.debug
import chisel3._
import chisel3.util._
import deadhorse.lib._
import _root_.circt.stage.ChiselStage

/** Unconstrained source/target inputs; only initial POR is constrained by runner.
  * targetQuiet is the required integration drain contract; composition is open. */
class DebugSbaFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val request=IO(Input(Bool()));val address=IO(Input(UInt(32.W)));val data=IO(Input(UInt(32.W)))
  val write=IO(Input(Bool()));val mask=IO(Input(UInt(4.W)))
  val up=IO(Input(Bool()));val quiet=IO(Input(Bool()));val grant=IO(Input(Bool()))
  val response=IO(Input(Bool()));val readData=IO(Input(UInt(32.W)));val error=IO(Input(Bool()))
  val d=Module[DebugSba](variant match {
    case "duplicate"=>new DebugSba {override protected def responseValid(v: Bool): Bool=v || RegNext(v,false.B)}
    case "stale"=>new DebugSba {override protected def reopen(v: Bool): Bool=true.B}
    case "wrong_route"=>new DebugSba {override protected def route(v: Bool): Bool= !v}
    case "late_route"=>new DebugSba {override protected def route(v: Bool): Bool=v ^ RegNext(bus.req && bus.gnt,false.B)}
    case _=>new DebugSba
  })
  d.clk:=clock;d.reset_n:=reset_n;d.req:=request;d.address:=address;d.value:=data;d.write:=write;d.mask:=mask
  d.targetUp:=up;d.targetQuiet:=quiet;d.bus.gnt:=grant;d.bus.rvalid:=response;d.bus.rdata:=readData;d.bus.err:=error
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val live=RegInit(false.B);val expected=RegInit(0.U.asTypeOf(new BusPayload))
    val needsDrain=RegInit(false.B);val cancellation=RegInit(false.B)
    when(d.grant && request) {
      live:=true.B;cancellation:=false.B
      expected.addr:=Cat(address(31,2),0.U(2.W));expected.wdata:=data
      expected.we:=write;expected.be:=mask;expected.origin:=2.U
    }
    when(live && !up && !d.valid) {needsDrain:=true.B;cancellation:=true.B}
    when(needsDrain && up && quiet && !response) {needsDrain:=false.B}
    when(d.valid) {live:=false.B}
    val admitted=RegNext(up && quiet,false.B)
    val held=RegNext(d.bus.req && !grant && up,false.B);val oldPayload=RegNext(d.bus.bits.asUInt)
    if(variant=="cover") {
      cover(d.valid && !d.error)
      cover(d.valid && d.error && cancellation)
      cover(needsDrain && response && !d.grant)
      cover(d.bus.req && d.retained)
      cover(d.bus.req && !d.retained)
    } else {
      assert(!d.valid || live,"DBG_SBA_ONCE")
      assert(!(d.grant && request) || !live && !needsDrain && admitted,"DBG_SBA_EPOCH")
      assert(!d.bus.req || live && d.bus.bits.asUInt===expected.asUInt,"DBG_SBA_PAYLOAD")
      assert(!d.valid || !cancellation || d.error,"DBG_SBA_CANCEL")
      assert(!live || d.retained===(expected.addr(31,12)===0x30000.U && expected.addr(11,0)<3072.U),"DBG_SBA_ROUTE")
      when(held && up) {assert(d.bus.bits.asUInt===oldPayload,"DBG_SBA_HELD")}
    }
  }
}
class DebugMemoryFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new LocalBus)
  val mode=IO(Input(UInt(2.W)));val hartReset=IO(Input(UInt(2.W)))
  val command=IO(Input(UInt(20.W)));val commandBusy=IO(Input(Bool()));val readData=IO(Input(UInt(32.W)))
  val d=Module[DebugMemory](if(variant=="wrong_hart") new DebugMemory {
    override protected def authorized(value: Bool): Bool=true.B
  } else new DebugMemory)
  d.clk:=clock;d.reset_n:=reset_n;d.bus<>bus;d.hartMode:=mode;d.hartReset:=hartReset
  d.commandHart:=command;d.commandBusy:=commandBusy;d.data:=readData
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val live=RegInit(false.B);val packet=RegInit(0.U.asTypeOf(new BusPayload))
    when(bus.req && bus.gnt) {live:=true.B;packet:=bus.bits}
    when(bus.rvalid) {live:=false.B}
    val origin=packet.origin;val offset=packet.addr(11,0)
    val named=offset===0x100.U || offset===0x110.U
    val owned=(offset===0x108.U || offset===0x118.U || offset>=0x380.U && offset<0x388.U) && commandBusy && command===origin
    if(variant=="cover") {
      cover(d.req && packet.addr===0x10400.U && packet.be===2.U && origin===1.U)
      cover(bus.rvalid && bus.err)
      cover(d.req && packet.we && offset===0x108.U && origin===1.U)
    } else {
      assert(!bus.rvalid || live,"DBG_MEM_ONCE")
      assert(!d.req || live && origin<2.U && mode(origin(0)) && !hartReset(origin(0)),"DBG_MEM_HART")
      assert(!d.req || !packet.we || named && packet.wdata===origin && packet.be===15.U || owned,"DBG_MEM_WRITE")
      assert(!d.req || offset=/=0x400.U || packet.be=/=2.U || d.payload.addr===0x10401.U,"DBG_MEM_LANE")
      assert(!bus.rvalid || !hartReset(origin(0)) || bus.err,"DBG_MEM_RESET")
    }
  }
}
object EmitDebugFormal extends App {
  require(args.length==1)
  val options=Array("--disable-all-randomization","--disable-opt","--lint-static-asserts=false", "--strip-debug-info","--verification-flavor=immediate","--lower-to-core")
  for(v<-Seq("correct","duplicate","stale","wrong_route","late_route","cover")) ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new DebugSbaFormal(v)),Array("--target-dir",s"${args(0)}/sba/$v"),options)
  for(v<-Seq("correct","wrong_hart","cover")) ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new DebugMemoryFormal(v)),Array("--target-dir",s"${args(0)}/memory/$v"),options)
}
