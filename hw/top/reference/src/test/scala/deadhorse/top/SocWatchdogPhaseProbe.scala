package deadhorse.top

import chisel3._
import chisel3.util.experimental.BoringUtils
import java.nio.file.Paths

/** Passive public-interface monitor; the watchdog expires from real firmware. */
class SocWatchdogPhaseProbe(badKey: Boolean=false,offered: Boolean=false,earlyWrite: Boolean=false) extends SocAnalogModelTest(
    "build/t20/map/soc.json",SocProduction.config().uart,
    Paths.get(s"build/t33/watchdog-phase-firmware/${if(offered && earlyWrite) "early" else if(offered) "offered" else if(badKey) "bad" else "boot"}.hex").toAbsolutePath.toString) {
  val monitorReset_n=IO(Input(Bool()))
  val observe=IO(Output(new Bundle {
    val resetHold=Bool();val cause=Bool();val crashes=UInt(32.W)
    val clientUp=Bool();val ready=Bool();val mainUp=Bool();val aonUp=Bool()
    val clientAccepted=UInt(8.W);val targetCommitted=UInt(8.W)
    val commitData=UInt(32.W);val commitMask=UInt(4.W);val targetOrigin=UInt(3.W)
    val downstreamPending=Bool();val downstreamResponse=Bool();val clientResponse=Bool()
    val returned=UInt(8.W);val staleResponses=UInt(8.W);val earlyReady=UInt(8.W)
    val acceptedCycle=UInt(32.W);val expiryCycle=UInt(32.W);val dispatchedCycle=UInt(32.W);val dispatches=UInt(8.W)
    val offered=Bool()
  }))
  val peripherals=digital.subsystem.get
  val watchdog=peripherals.watchdogBlocks.head
  val regs=watchdog.regs
  val data=digital.memory.data;val bus=digital.memory.peripheral
  val up=BoringUtils.bore(digital.memory.clientReset_n)
  val ready=BoringUtils.bore(digital.memory.epochReady)
  val startAddress=(if(offered) "h40000104".U else "h4000010c".U)
  observe.resetHold:=BoringUtils.bore(watchdog.resetHold)
  observe.cause:=BoringUtils.bore(watchdog.cause);observe.crashes:=BoringUtils.bore(watchdog.crashes)
  observe.clientUp:=up;observe.ready:=ready
  observe.mainUp:=BoringUtils.bore(peripherals.mainUp);observe.aonUp:=BoringUtils.bore(peripherals.aonUp)
  val accept=BoringUtils.bore(data.req) && BoringUtils.bore(data.gnt) &&
    BoringUtils.bore(data.bits.we) && BoringUtils.bore(data.bits.addr)===startAddress
  val anyClientAccept=BoringUtils.bore(data.req) && BoringUtils.bore(data.gnt)
  val anyDispatch=BoringUtils.bore(bus.req) && BoringUtils.bore(bus.gnt)
  val startDispatch=anyDispatch && BoringUtils.bore(bus.bits.we) && BoringUtils.bore(bus.bits.addr)===startAddress
  observe.offered:=BoringUtils.bore(bus.req) && BoringUtils.bore(bus.bits.we) && BoringUtils.bore(bus.bits.addr)===startAddress
  val reply=BoringUtils.bore(bus.rvalid)
  val clientReply=BoringUtils.bore(data.rvalid)
  withClockAndReset(clocks.mainClock,(!monitorReset_n).asAsyncReset) {
    // Live ownership cancels asynchronously with the real warm release, even
    // when the main clock stops. Historical counts use only monitor reset.
    val pending=withReset((!(monitorReset_n && up)).asAsyncReset) {RegInit(false.B)}
    val accepted=RegInit(0.U(8.W));val returned=RegInit(0.U(8.W))
    val sawReset=RegInit(false.B);val stale=RegInit(0.U(8.W));val early=RegInit(0.U(8.W))
    val returnTail=RegNext(pending && reply,false.B)
    val oldReturnWindow=withReset((!(monitorReset_n && up)).asAsyncReset) {RegInit(false.B)}
    val clientOwned=withReset((!(monitorReset_n && up)).asAsyncReset) {RegInit(false.B)}
    // The passive monitor is enabled while boot is polling GPIO. An initial
    // reply may belong to a request accepted before the monitor was enabled.
    // Arm on its first observed acceptance; retain this across warm reset.
    val ownershipStarted=RegInit(false.B)
    when(anyClientAccept) {ownershipStarted:=true.B}
    val cycle=RegInit(0.U(32.W));val acceptedCycle=RegInit(0.U(32.W));val expiryCycle=RegInit(0.U(32.W))
    val dispatchedCycle=RegInit(0.U(32.W));val dispatches=RegInit(0.U(8.W));cycle:=cycle+1.U
    when(accept) {acceptedCycle:=cycle}
    when(observe.resetHold && !sawReset) {expiryCycle:=cycle}
    when(startDispatch) {dispatches:=dispatches+1.U;dispatchedCycle:=cycle}
    observe.acceptedCycle:=acceptedCycle;observe.expiryCycle:=expiryCycle;observe.dispatchedCycle:=dispatchedCycle;observe.dispatches:=dispatches
    when(anyDispatch) {oldReturnWindow:=startDispatch}
    when(accept) {pending:=true.B;accepted:=accepted+1.U}
    when(pending && reply) {pending:=false.B}
    when(oldReturnWindow && reply) {returned:=returned+1.U}
    when(observe.resetHold) {sawReset:=true.B}
    when(clientReply) {clientOwned:=false.B}
    when(up && anyClientAccept) {clientOwned:=true.B}
    when(ownershipStarted && clientReply && (!up || !clientOwned)) {stale:=stale+1.U}
    when(anyClientAccept && (!up || !ready)) {early:=early+1.U}
    observe.clientAccepted:=accepted;observe.returned:=returned
    observe.downstreamPending:=pending;observe.downstreamResponse:=pending && reply
    observe.clientResponse:=pending && clientReply
    observe.staleResponses:=stale;observe.earlyReady:=early
  }
  withClockAndReset(clocks.aonClock,(!monitorReset_n).asAsyncReset) {
    val count=RegInit(0.U(8.W));val value=RegInit(0.U(32.W));val mask=RegInit(0.U(4.W));val origin=RegInit(0.U(3.W))
    when(BoringUtils.bore(watchdog.bus.req) && BoringUtils.bore(watchdog.bus.gnt) &&
        BoringUtils.bore(watchdog.bus.bits.addr)===startAddress) {origin:=BoringUtils.bore(watchdog.bus.bits.origin)}
    when(BoringUtils.bore(regs.rst_n) && BoringUtils.bore(regs.bus.req_valid) &&
        BoringUtils.bore(regs.bus.req_ready) && BoringUtils.bore(regs.bus.req_write) &&
        BoringUtils.bore(regs.bus.req_addr)===(if(offered) 4.U else 12.U)) {
      count:=count+1.U;value:=BoringUtils.bore(regs.bus.req_wdata);mask:=BoringUtils.bore(regs.bus.req_wstrb)
    }
    observe.targetCommitted:=count;observe.commitData:=value;observe.commitMask:=mask;observe.targetOrigin:=origin
  }
}
