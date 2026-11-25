package deadhorse.debug
import chisel3._
import chisel3.util._
import deadhorse.lib._
import deadhorse.sram._

/** POR-owned transport/module. Target service resets never reset the DM. */
class Debug(retainedBase: BigInt=0x30000000L, retainedSize: BigInt=3072,
    bistJson: Option[String]=None,qualifiedResets: Boolean=false) extends RawModule {
  val clk=IO(Input(Clock()));val tck=IO(Input(Clock()));val por_n=IO(Input(Bool()))
  val tms=IO(Input(Bool()));val tdi=IO(Input(Bool()));val tdo=IO(Output(Bool()));val tdoEnable=IO(Output(Bool()))
  val hartReset=IO(Input(UInt(2.W)));val unavailable=IO(Input(UInt(2.W)));val hartMode=IO(Input(UInt(2.W)))
  val halt=IO(Output(UInt(2.W)));val active=IO(Output(Bool()));val ndmReset=IO(Output(Bool()))
  val ndmAck=IO(Input(Bool()));val pendingTck=IO(Output(Bool()));val hold=IO(Output(Bool()))
  val memoryReset_n=IO(Input(Bool()));val memory=IO(new LocalBus);val system=IO(Flipped(new LocalBus));val systemUp=IO(Input(Bool()));val systemQuiet=IO(Input(Bool()))
  val systemRetained=IO(Output(Bool()))
  val bist=bistJson.map(_=>IO(new Bundle {
    val epoch_n=Input(Bool());val start=Output(Bool());val keyed=Output(Bool())
    val busy=Input(Bool());val done=Input(Bool());val failed=Input(Bool());val rejected=Input(Bool())
    val resetAck=Input(Bool());val failAddress=Input(UInt(32.W));val result=Input(new MarchResult)
  }))
  val domainReset=if(qualifiedResets) Some(IO(Input(new Bundle {val main=Bool();val scan=Bool()}))) else None
  def localRelease(clock: Clock,provided: Option[Bool]): Bool=provided.getOrElse {
    val r=Module(new ResetRelease);r.clk:=clock;r.reset_n:=por_n;r.released
  }
  val mainUp=localRelease(clk,domainReset.map(_.main));val tckUp=localRelease(tck,domainReset.map(_.scan))
  val tap=Module(new DebugTap);val dm=Module(new DebugModule);val transport=Module(new DebugTransport(qualifiedResets=true))
  transport.domainReset.get.main:=mainUp;transport.domainReset.get.scan:=tckUp
  tap.io.clk_i:=tck;tap.io.rst_ni:=tckUp;tap.io.testmode_i:=false.B
  tap.io.tck_i:=tck;tap.io.trst_ni:=tckUp;tap.io.tms_i:=tms;tap.io.td_i:=tdi
  tdo:=tap.io.td_o;tdoEnable:=tap.io.tdo_oe_o
  transport.mainClock:=clk;transport.tck:=tck;transport.por_n:=por_n;transport.clear_n:=tap.io.dmi_rst_no
  transport.scanRequest.valid:=tap.io.dmi_req_valid_o;transport.scanRequest.bits:=tap.io.dmi_req_o
  tap.io.dmi_req_ready_i:=transport.scanRequest.ready
  tap.io.dmi_resp_i:=transport.scanResponse.bits;tap.io.dmi_resp_valid_i:=transport.scanResponse.valid
  transport.scanResponse.ready:=tap.io.dmi_resp_ready_o;pendingTck:=transport.pending
  dm.io.clk_i:=clk;dm.io.rst_ni:=mainUp;dm.io.testmode_i:=false.B;dm.io.next_dm_addr_i:=0.U
  dm.io.hart_reset_i:=hartReset;dm.io.unavailable_i:=unavailable
  // Nonzero DM base cannot be encoded in hartinfo's signed 12-bit address.
  // Advertise two scratch CSRs but no directly addressable scratch data.
  val info=BigInt(2)<<20
  dm.io.hartinfo_i:=((info<<32)|info).U
  dm.io.ndmreset_ack_i:=ndmAck;ndmReset:=dm.io.ndmreset_o;halt:=dm.io.debug_req_o;active:=dm.io.dmactive_o
  dm.io.dmi_rst_ni:=transport.coreUp;dm.io.dmi_req_i:=transport.request.bits
  bistJson match {
    case None =>
      dm.io.dmi_req_valid_i:=transport.request.valid;transport.request.ready:=dm.io.dmi_req_ready_o
      transport.response.valid:=dm.io.dmi_resp_valid_o;transport.response.bits:=dm.io.dmi_resp_o
      dm.io.dmi_resp_ready_i:=transport.response.ready
    case Some(json) =>
      val custom=Module(new SramDmi(json));custom.clk:=clk
      custom.reset_n:=mainUp;custom.clear:= !transport.coreUp;custom.epoch_n:=bist.get.epoch_n
      bist.get.start:=custom.start;bist.get.keyed:=custom.keyed
      custom.busy:=bist.get.busy;custom.done:=bist.get.done;custom.failed:=bist.get.failed
      custom.rejected:=bist.get.rejected;custom.resetAck:=bist.get.resetAck
      custom.failAddress:=bist.get.failAddress;custom.result:=bist.get.result
      withClockAndReset(clk,(!mainUp).asAsyncReset) {
        val pending=RegInit(false.B);val owner=RegInit(false.B)
        val select=transport.request.bits(40,38)===7.U
        custom.request.bits:=transport.request.bits
        custom.request.valid:=transport.request.valid && !pending && select
        dm.io.dmi_req_valid_i:=transport.request.valid && !pending && !select
        transport.request.ready:= !pending && Mux(select,custom.request.ready,dm.io.dmi_req_ready_o)
        transport.response.valid:=pending && Mux(owner,custom.response.valid,dm.io.dmi_resp_valid_o)
        transport.response.bits:=Mux(owner,custom.response.bits,dm.io.dmi_resp_o)
        custom.response.ready:=pending && owner && transport.response.ready
        dm.io.dmi_resp_ready_i:=pending && !owner && transport.response.ready
        when(transport.request.fire) {pending:=true.B;owner:=select}
        when(transport.response.fire) {pending:=false.B}
        when(!transport.coreUp) {pending:=false.B;owner:=false.B}
      }
  }
  val mem=Module(new DebugMemory);mem.clk:=clk;mem.reset_n:=memoryReset_n
  mem.bus<>memory;mem.hartMode:=hartMode;mem.hartReset:=hartReset
  mem.commandHart:=dm.io.command_hart_o;mem.commandBusy:=dm.io.command_busy_o
  dm.io.slave_req_i:=mem.req;dm.io.slave_addr_i:=mem.payload.addr;dm.io.slave_we_i:=mem.payload.we
  dm.io.slave_be_i:=mem.payload.be;dm.io.slave_wdata_i:=mem.payload.wdata;mem.data:=dm.io.slave_rdata_o
  val sba=Module(new DebugSba(retainedBase,retainedSize));sba.clk:=clk;sba.reset_n:=mainUp;sba.targetUp:=systemUp;sba.targetQuiet:=systemQuiet
  sba.req:=dm.io.master_req_o;sba.address:=dm.io.master_add_o;sba.write:=dm.io.master_we_o
  sba.value:=dm.io.master_wdata_o;sba.mask:=dm.io.master_be_o
  dm.io.master_gnt_i:=sba.grant;dm.io.master_r_valid_i:=sba.valid;dm.io.master_r_rdata_i:=sba.result
  dm.io.master_r_err_i:=sba.error;dm.io.master_r_other_err_i:=false.B
  system<>sba.bus;systemRetained:=sba.retained;hold:=dm.io.dmactive_o || sba.busy || mem.busy
}

/** A registered, origin-checked memory port. No untrusted written hart ID enters DM. */
class DebugMemory extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new LocalBus)
  val hartMode=IO(Input(UInt(2.W)));val hartReset=IO(Input(UInt(2.W)))
  val commandHart=IO(Input(UInt(20.W)));val commandBusy=IO(Input(Bool()))
  val req=IO(Output(Bool()));val payload=IO(Output(new BusPayload));val data=IO(Input(UInt(32.W)))
  val busy=IO(Output(Bool()))
  protected def authorized(value: Bool): Bool=value
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val idle :: grant :: issue :: collect :: reply :: Nil=Enum(5)
    val state=RegInit(idle);val packet=RegInit(0.U.asTypeOf(new BusPayload));val bad=RegInit(false.B)
    val result=RegInit(0.U(32.W));val error=RegInit(false.B)
    bus.gnt:=state===grant;bus.rvalid:=state===reply;bus.rdata:=Mux(hartReset(packet.origin(0)),0.U,result);bus.err:=error || hartReset(packet.origin(0))
    payload:=packet;busy:=state=/=idle
    // PULP's flags byte is addressed by hart, while LocalBus carries aligned words.
    when(!packet.we && packet.addr(11,0)>=0x400.U && packet.addr(11,0)<0x800.U) {
      payload.addr:=packet.addr | PriorityEncoder(packet.be)
    }
    val origin=packet.origin;val offset=packet.addr(11,0)
    val realHart=origin<2.U;val live=realHart && hartMode(origin(0)) && !hartReset(origin(0))
    val named=offset===0x100.U || offset===0x110.U
    val command=offset===0x108.U || offset===0x118.U || (offset>=0x380.U && offset<0x388.U)
    val allowedWrite=(named && packet.wdata===origin && packet.be===15.U) ||
      (command && commandBusy && commandHart===origin)
    val allowed=authorized(live && packet.addr(31,12)===0x10.U && !packet.addr(1,0).orR &&
      (!packet.we || allowedWrite))
    req:=state===issue && allowed
    when(state===idle && bus.req) {state:=grant}
    when(state===grant) {when(bus.req) {packet:=bus.bits;state:=issue}.otherwise {state:=idle}}
    when(state===issue) {bad:= !allowed;state:=collect}
    when(state===collect) {result:=Mux(bad || !live || packet.we,0.U,data);error:=bad || !live;state:=reply}
    when(state===reply) {state:=idle}
    assert(!req || realHart && !hartReset(origin(0)))
  }
}

/** Captures SBA payload before offering it; accepted work survives DM deactivation. */
class DebugSba(retainedBase: BigInt=0x30000000L, retainedSize: BigInt=3072) extends RawModule {
  require(retainedBase>=0 && retainedSize>0 && retainedBase+retainedSize<=(BigInt(1)<<32))
  protected def responseValid(value: Bool): Bool=value
  protected def reopen(value: Bool): Bool=value
  protected def route(value: Bool): Bool=value
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val targetUp=IO(Input(Bool()));val targetQuiet=IO(Input(Bool()))
  val req=IO(Input(Bool()));val address=IO(Input(UInt(32.W)));val write=IO(Input(Bool()))
  val value=IO(Input(UInt(32.W)));val mask=IO(Input(UInt(4.W)))
  val grant=IO(Output(Bool()));val valid=IO(Output(Bool()));val result=IO(Output(UInt(32.W)))
  val error=IO(Output(Bool()));val busy=IO(Output(Bool()));val bus=IO(Flipped(new LocalBus))
  val retained=IO(Output(Bool()))
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val idle :: accept :: offer :: waitReply :: reply :: quarantine :: Nil=Enum(6)
    val state=RegInit(idle);val packet=RegInit(0.U.asTypeOf(new BusPayload))
    val selected=RegInit(false.B);retained:=route(selected)
    val readData=RegInit(0.U(32.W));val failed=RegInit(false.B);val cancelled=RegInit(false.B)
    grant:=state===accept;valid:=responseValid(state===reply);result:=readData;error:=failed;busy:=state=/=idle
    bus.req:=state===offer && targetUp;bus.bits:=packet
    when(state===idle && req && reopen(targetUp && targetQuiet)) {state:=accept}
    when(state===accept) {
      when(req) {
        packet.addr:=Cat(address(31,2),0.U(2.W));packet.we:=write;packet.be:=mask;packet.wdata:=value;packet.origin:=2.U
        val aligned=Cat(address(31,2),0.U(2.W))
        selected:=aligned>=retainedBase.U && aligned<(retainedBase+retainedSize).U
        state:=offer;readData:=0.U;failed:=false.B;cancelled:=false.B
      }.otherwise {state:=idle}
    }
    when(state===offer && bus.gnt) {state:=waitReply}
    when(state===waitReply && bus.rvalid) {readData:=Mux(bus.err || packet.we,0.U,bus.rdata);failed:=bus.err;state:=reply}
    when((state===offer || state===waitReply) && !targetUp) {readData:=0.U;failed:=true.B;cancelled:=true.B;state:=reply}
    when(state===reply) {state:=Mux(cancelled,quarantine,idle)}
    when(state===quarantine && reopen(targetUp && targetQuiet && !bus.rvalid)) {state:=idle}
    val held=RegNext(state===offer || state===waitReply,false.B);val previous=RegNext(packet.asUInt)
    when(held) {assert(packet.asUInt===previous)}
    assert(!bus.req || packet.origin===2.U)
  }
}

/** Selection and payload are held by DebugSba until its registered reply.
  * Both downstream fabrics supply registered grants/responses; no extra owner
  * or payload copy is needed between them and the SBA transaction owner. */
object DebugSbaRouting {
  def connect(source: LocalBus, retainedSelect: Bool, retained: LocalBus, native: LocalBus): Unit = {
    retained.req:=source.req && retainedSelect;native.req:=source.req && !retainedSelect
    retained.bits:=source.bits;native.bits:=source.bits
    source.gnt:=Mux(retainedSelect,retained.gnt,native.gnt)
    source.rvalid:=Mux(retainedSelect,retained.rvalid,native.rvalid)
    source.rdata:=Mux(retainedSelect,retained.rdata,native.rdata)
    source.err:=Mux(retainedSelect,retained.err,native.err)
  }
}
object EmitDebug extends App {
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(new Debug,Array("--target-dir",args(0)),
    Array("--disable-all-randomization","--strip-debug-info","--preserve-values=named","--verification-flavor=immediate","--lower-to-core"))
}
