package deadhorse.debug
import chisel3._
import chisel3.util._
import chisel3.util.experimental.BoringUtils
import deadhorse.lib._
import deadhorse.bus.{BusFabric,BusRegion}
import deadhorse.bus_bridge.{BusBridge,DirectionPermit,BridgeSource}
import deadhorse.top.{SocDrainCredit,SocErrorTarget}

/** Actual transport/fabric composition at production timeout values.
  * The independent delayed target is an echo oracle for transport integrity,
  * not a model of retained-memory contents. No fairness or quiet-is-empty premise.
  * Source/target clocks and resets are independent, including stopped clocks. */
class DebugEpochFormal(variant: String) extends RawModule {
  val main=IO(Input(Clock()));val aon=IO(Input(Clock()));val por_n=IO(Input(Bool()))
  val main_n=IO(Input(Bool()));val aon_n=IO(Input(Bool()))
  val offer=IO(Input(Bool()));val offset=IO(Input(UInt(12.W)));val data=IO(Input(UInt(32.W)))
  val write=IO(Input(Bool()));val allow=IO(Input(Bool()));val reply=IO(Input(Bool()));val bad=IO(Input(Bool()))
  val mask=IO(Input(UInt(4.W)))
  val otherBusy=IO(Input(Bool()));val otherPermit=IO(Input(Bool()))
  def released(clock: Clock,raw: Bool): Bool={val r=Module(new ResetRelease);r.clk:=clock;r.reset_n:=raw;r.released}
  val mainRaw=por_n && main_n;val aonRaw=por_n && aon_n
  val up=released(main,mainRaw);val aonUp=released(aon,aonRaw);val debugUp=released(main,por_n)
  val d=Module(new DebugSba);d.clk:=main;d.reset_n:=debugUp
  val f=Module(new BusFabric(1,Seq(BusRegion(0x30000000L,4096,131080))))
  f.clk:=main;f.reset_n:=up;f.allow(0):=true.B;f.admit(0):=true.B;f.quiescent(0):=false.B
  val native=Module(new SocErrorTarget);native.clk:=main;native.reset_n:=up
  DebugSbaRouting.connect(d.bus,d.retained,f.master(0),native.bus)
  val bridge=Module[BusBridge](if(variant=="corrupt") new BusBridge {
    override protected def sourceEndpoint(): BridgeSource=new BridgeSource(131072) {
      override protected def readResult(v: UInt): UInt=v ^ 1.U
    }
  } else new BusBridge)
  bridge.sourceClock:=main;bridge.targetClock:=aon;bridge.sourceReset_n:=mainRaw;bridge.targetReset_n:=aonRaw
  bridge.source<>f.target(0);bridge.offer:=f.waiting(0);f.admit(0):=bridge.admit
  // Fault: lose the error bit on a canceled/stale bridge completion.
  if(variant=="stale") f.target(0).err:=false.B
  val permit=Module(new DirectionPermit);permit.mainClock:=main;permit.aonClock:=aon
  permit.mainReset_n:=mainRaw;permit.aonReset_n:=aonRaw
  permit.requestMain:=bridge.permitRequest;permit.requestAon:=otherPermit;bridge.permit:=permit.permitMain
  val targetFabric=Module(new BusFabric(1,Seq(BusRegion(0x30000000L,4096,128))))
  targetFabric.clk:=aon;targetFabric.reset_n:=aonUp
  targetFabric.master(0)<>bridge.target;targetFabric.allow(0):=true.B;targetFabric.admit(0):=true.B
  val credit=Module(new SocDrainCredit);credit.clk:=aon;credit.reset_n:=aonUp
  credit.accepted:=bridge.target.gnt && (if(variant=="lost_credit") bridge.target.req else true.B)
  credit.response:=bridge.target.rvalid
  bridge.quiescent:=credit.empty && !bridge.target.rvalid && !targetFabric.isolated(0)
  d.targetUp:=up
  // Other production busy terms only prevent admission. They are arbitrary
  // blockers here, not an assumption that remote accepted work disappeared.
  d.targetQuiet:=up && !f.waiting(0) && !f.isolated(0) && !d.bus.rvalid && !bridge.clockRequest && !otherBusy
  val live=withClockAndReset(main,(!debugUp).asAsyncReset){RegInit(false.B)}
  val expected=withClockAndReset(main,(!debugUp).asAsyncReset){Reg(UInt(32.W))}
  val captured=withClockAndReset(main,(!debugUp).asAsyncReset){Reg(new BusPayload)}
  val cancelled=withClockAndReset(main,(!(por_n && up)).asAsyncReset){RegInit(true.B)}
  d.req:=offer && !live;d.address:=Cat(0x30000.U(20.W),offset);d.value:=data;d.write:=write;d.mask:=mask
  withClockAndReset(main,(!debugUp).asAsyncReset) {
    val forwarded=RegInit(false.B)
    val cancelBeforeReply=RegNext(live && cancelled,false.B)
    when(d.grant && d.req) {
      live:=true.B;expected:=Mux(write,0.U,data ^ Cat(0x30000.U(20.W),offset(11,2),0.U(2.W)));cancelled:=false.B
      captured.addr:=Cat(0x30000.U(20.W),offset(11,2),0.U(2.W));captured.wdata:=data
      captured.we:=write;captured.be:=mask;captured.origin:=2.U;forwarded:=false.B
    }
    when(d.valid){live:=false.B}
    if(variant=="cover") {
      cover(d.valid && !d.error)
      cover(d.valid && d.error && cancelBeforeReply)
      cover(d.grant && d.req && otherBusy)
    } else {
      assert(!d.valid || live,"DBG_EPOCH_ONCE")
      assert(!d.valid || d.error || d.result===expected,"DBG_EPOCH_DATA")
      assert(!d.valid || !cancelBeforeReply || d.error,"DBG_EPOCH_CANCEL")
    }
    when(bridge.source.req && bridge.source.gnt) {
      if(variant!="cover") {
        assert(live && !forwarded,"DBG_EPOCH_SOURCE_ONCE")
        assert(bridge.source.bits.asUInt===captured.asUInt,"DBG_EPOCH_SOURCE_DATA")
      }
      forwarded:=true.B
    }
  }
  // Remote reset cancels an uncommitted source ticket. A response published
  // before reset remains legal; error must survive the main fabric and SBA.
  val remoteCancel=withClockAndReset(main,(!(mainRaw && aonRaw)).asAsyncReset){RegInit(true.B)}
  withClockAndReset(main,(!up).asAsyncReset) {
    val pending=RegInit(false.B);val failed=RegInit(false.B)
    val before=RegNext(pending && remoteCancel,false.B)
    when(bridge.source.req && bridge.source.gnt){pending:=true.B;remoteCancel:=false.B;failed:=false.B}
    when(bridge.source.rvalid){pending:=false.B;failed:=bridge.source.err}
    when(d.valid){failed:=false.B}
    if(variant!="cover") {
      assert(!bridge.source.rvalid || !before || bridge.source.err,"DBG_REMOTE_CANCEL")
      assert(!d.valid || !failed || d.error,"DBG_REMOTE_ERROR_PROPAGATION")
    } else {cover(bridge.source.rvalid && before && bridge.source.err)}
  }
  // Legal untagged endpoint: holds its accepted value until arbitrary response;
  // main reset does not clear it. An accepted write can finish once after cancel.
  withClockAndReset(aon,(!aonUp).asAsyncReset) {
    val active=RegInit(false.B);val result=Reg(UInt(32.W))
    val credit=RegInit(false.B);val forwarded=RegInit(false.B);val payload=Reg(new BusPayload)
    val offered=RegNext(bridge.target.req,false.B);val offeredPayload=RegNext(bridge.target.bits)
    val port=targetFabric.target(0)
    port.gnt:=allow && !active;port.rvalid:=active && reply;port.rdata:=result;port.err:=bad
    targetFabric.quiescent(0):= !active && !port.rvalid
    when(port.req && port.gnt) {active:=true.B;result:=port.bits.wdata ^ port.bits.addr}
    when(port.rvalid) {active:=false.B}
    when(bridge.target.rvalid){credit:=false.B}
    // BusFabric captures before publishing its registered grant. A transport
    // flush can withdraw req in between; that committed work still must drain.
    when(bridge.target.gnt){
      if(variant!="cover") {assert(offered,"DBG_TARGET_COMMITTED_OFFER")}
      credit:=true.B;forwarded:=false.B;payload:=offeredPayload
    }
    when(port.req && port.gnt) {
      if(variant!="cover") {
        assert(credit && !forwarded,"DBG_TARGET_ONCE")
        assert(port.bits.asUInt===payload.asUInt,"DBG_TARGET_DATA")
      }
      forwarded:=true.B
    }
    if(variant=="cover") {cover(active && !main_n);cover(active && !main_n && reply)}
    // This observation is only a cover, never an asynchronous functional path.
    if(variant=="cover") {
      cover(active && d.req && d.grant && main_n)
      cover(bridge.target.gnt && !bridge.target.req)
    }
  }
  // Public endpoint observations independently check one dispatch per transported
  // ticket. FIFO storage/pointers are not used as an assumed reference model.
  val link=BoringUtils.bore(bridge.consumer.linkUp)
  val ticketValid=BoringUtils.bore(bridge.consumer.requestValid)
  val pop=BoringUtils.bore(bridge.consumer.requestPop)
  val packet=BoringUtils.bore(bridge.consumer.requestData)
  val pushReply=BoringUtils.bore(bridge.consumer.responsePush)
  val takeReply=BoringUtils.bore(bridge.consumer.responseReady)
  withClockAndReset(aon,(!aonUp).asAsyncReset) {
    val owned=RegInit(false.B);val dispatched=RegInit(false.B);val saved=Reg(UInt(72.W))
    when(!link || pushReply && takeReply){owned:=false.B}
    when(ticketValid && pop){owned:=true.B;dispatched:=false.B;saved:=packet}
    when(bridge.target.req && bridge.target.gnt) {
      if(variant!="cover") {
        assert(owned && !dispatched,"DBG_EPOCH_DISPATCH_ONCE")
        assert(bridge.target.bits.asUInt===saved,"DBG_EPOCH_DISPATCH_DATA")
      }
      dispatched:=true.B
    }
  }
}
object EmitDebugEpochFormal extends App {
  for(v<-Seq("correct","corrupt","stale","lost_credit","cover")) _root_.circt.stage.ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new DebugEpochFormal(v)),Array("--target-dir",s"${args(0)}/$v"),
    Array("--disable-all-randomization","--disable-opt","--lint-static-asserts=false","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
