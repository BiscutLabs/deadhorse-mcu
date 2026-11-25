package deadhorse.osc_ctrl

import chisel3._
import deadhorse.lib._

/** Production digital clock/reset boundary. The first qualification releases
  * domain resets; subsequent sleep gates clocks without resetting state. */
class OscClockReset(target: ClockGateTarget=ClockGateTarget.Model,consolidated: Boolean=false) extends RawModule {
  protected def epochReset(qualified: Bool,bootstrap: Bool): Bool=qualified
  protected def makeCounter(): OscStability=new OscStability
  protected def makeGate(): OscMainGate=new OscMainGate(target)
  protected def configurationValue(value: UInt): UInt=value
  protected def dividerResetValue(local: Bool,raw: Bool): Bool=local
  val oscIn=IO(Input(Clock()));val rcClock=IO(Input(Clock()));val aonClockIn=IO(Input(Clock()))
  val externalReset_n=IO(Input(Bool()));val supplyReset_n=IO(Input(Bool()))
  val aonClockSelect=IO(Input(Bool()));val porBypass=IO(Input(Bool()))
  val oscillatorOn=IO(Input(Bool()));val gateRequest=IO(Input(Bool()))
  val authorized=IO(Input(Bool()));val qualify=IO(Input(Bool()));val count=IO(Input(UInt(16.W)))
  val localHold=IO(Input(Bool()));val coreIdle=IO(Input(Bool()))
  val aonClock=IO(Output(Clock()));val mainClock=IO(Output(Clock()))
  val aonReset_n=IO(Output(Bool()));val coldReset_n=IO(Output(Bool()));val warmReset_n=IO(Output(Bool()))
  val serviceReset_n=IO(Output(Bool()));val stable=IO(Output(Bool()));val closed=IO(Output(Bool()))
  val ungatedClock=IO(Output(Clock()));val usbServiceReset_n=IO(Output(Bool()))
  val shared=if(consolidated) Some(IO(Input(new Bundle {
    val coldAon=Bool();val coldMain=Bool();val coldSource=Bool();val pinAon=Bool();val initialize=Bool()
  }))) else None
  val epochClear=if(consolidated) Some(IO(Input(Bool()))) else None
  val clearAck=if(consolidated) Some(IO(Output(UInt(2.W)))) else None
  val bootstrap=Module(new ResetBootstrap(qualifiedResets=consolidated))
  if(consolidated) {bootstrap.releases.get.cold:=shared.get.coldAon;bootstrap.releases.get.pin:=shared.get.pinAon}
  bootstrap.rcClock:=rcClock;bootstrap.externalAonClock:=aonClockIn
  bootstrap.externalReset_n:=externalReset_n;bootstrap.supplyReset_n:=supplyReset_n
  bootstrap.selectExternal:=aonClockSelect;bootstrap.bypassPor:=porBypass
  aonClock:=bootstrap.aonClock;aonReset_n:=bootstrap.aonReset_n
  coldReset_n:=bootstrap.coldReset_n;warmReset_n:=bootstrap.warmReset_n
  val divider=Module(new OscDivider)
  // The divider consumes reset as DATA to finish a high phase. Synchronize
  // both transitions; an asynchronously asserting ResetRelease output would
  // still be asynchronous data at this boundary. These synchronizer flops
  // intentionally have no reset. Their initial values may be arbitrary,
  // including when a stopped source misses the complete bootstrap reset.
  // Raw domain/gate resets and startup qualification quarantine that interval.
  val dividerRelease=Module(new CdcSync(1))
  dividerRelease.clk:=oscIn;dividerRelease.reset_n:=true.B
  dividerRelease.in:=bootstrap.aonReset_n.asUInt
  val dividerReset=WireDefault(dividerResetValue(dividerRelease.out.asBool,bootstrap.aonReset_n))
  divider.clk:=oscIn;divider.reset_n:=dividerReset
  ungatedClock:=divider.divided
  private val legacy = if(consolidated) {
    val executor=Module(new OscSourceControl(target))
    executor.source:=oscIn;executor.divided:=divider.divided;executor.aon:=bootstrap.aonClock
    executor.coldSource:=shared.get.coldSource;executor.coldDivided:=shared.get.coldMain
    executor.coldAon:=shared.get.coldAon;executor.pinAon:=shared.get.pinAon
    executor.aonQualified:=bootstrap.aonReset_n;executor.initialize:=shared.get.initialize
    executor.epochClear:=epochClear.get;clearAck.get:=executor.clearAck
    executor.gateRequest:=gateRequest;executor.authorized:=authorized
    executor.qualify:=qualify;executor.count:=count
    executor.localHold:=localHold;executor.coreIdle:=coreIdle
    mainClock:=executor.main;stable:=executor.stable;closed:=executor.closed
    serviceReset_n:=executor.mainQualified;usbServiceReset_n:=executor.usbQualified
    None
  } else {
  // Preserved boundary reference used by focused pre-consolidation fixtures.
  usbServiceReset_n:=serviceReset_n
  val gateReset=Module(new ResetRelease)
  // Clear stale source-domain authorization asynchronously before the source
  // stops. New main work must not reopen a gate using the previous epoch.
  gateReset.clk:=divider.divided
  gateReset.reset_n:=epochReset(bootstrap.aonReset_n && oscillatorOn,bootstrap.aonReset_n)
  val gate=Module(makeGate())
  val commands=Module(new CdcFifo(1));val completions=Module(new CdcFifo(1))
  commands.writeClock:=bootstrap.aonClock;commands.readClock:=divider.divided
  completions.writeClock:=divider.divided;completions.readClock:=bootstrap.aonClock
  for(f<-Seq(commands,completions)) {
    f.writeReset_n:=bootstrap.aonReset_n && oscillatorOn
    f.readReset_n:=bootstrap.aonReset_n && oscillatorOn
  }
  gate.clk:=divider.divided
  gate.reset_n:=gateReset.released && commands.readUp && completions.writeUp
  gate.command:=commands.valid;gate.request:=commands.out.asBool
  commands.pop:=commands.valid && gate.ready
  completions.push:=gate.completed && completions.ready;completions.in:=gate.result.asUInt
  gate.consume:=completions.ready;gate.verified:=authorized
  gate.localHold:=localHold;gate.coreIdle:=coreIdle;mainClock:=gate.gated
  withClockAndReset(bootstrap.aonClock,(!(commands.writeUp && completions.readUp)).asAsyncReset) {
    val busy=RegInit(false.B);val issued=RegInit(false.B)
    val known=RegInit(false.B);val applied=RegInit(false.B);val safelyClosed=RegInit(false.B)
    val closedReport=RegInit(false.B)
    val push= !busy && commands.ready && (!known || gateRequest=/=applied || !gateRequest && !safelyClosed)
    commands.push:=push;commands.in:=gateRequest.asUInt
    when(push || gateRequest) {closedReport:=false.B}
    when(push) {busy:=true.B;issued:=gateRequest;known:=false.B}
    completions.pop:=busy && completions.valid
    when(busy && completions.valid) {
      busy:=false.B;known:=true.B;applied:=issued;safelyClosed:=completions.out.asBool
      closedReport:= !issued && !gateRequest && completions.out.asBool
    }
    // Cleared before any open command can cross; a source close is held until
    // such a command arrives. The reply cannot describe an earlier transaction.
    closed:=closedReport
  }
  val counter=Module(makeCounter())
  counter.clk:=oscIn;counter.reset_n:=bootstrap.aonReset_n
  // One coherent source-domain payload per oscillator epoch. Retain the FIFO
  // head through light sleep; deep OFF resets both endpoints before reuse.
  // writePending is intentionally not a sleep hold for this retained payload.
  val configuration=Module(new CdcFifo(16))
  configuration.writeClock:=bootstrap.aonClock;configuration.readClock:=oscIn
  configuration.writeReset_n:=bootstrap.aonReset_n && oscillatorOn
  configuration.readReset_n:=bootstrap.aonReset_n && oscillatorOn
  withClockAndReset(bootstrap.aonClock,(!configuration.writeUp).asAsyncReset) {
    val sent=RegInit(false.B)
    val push=qualify && !sent && configuration.ready
    configuration.push:=push;configuration.in:=count
    when(push) {sent:=true.B}
  }
  configuration.pop:=false.B
  counter.oscillatorOn:=oscillatorOn
  counter.qualify:=configuration.valid;counter.count:=configurationValue(configuration.out)
  def toAon(value: Bool): Bool={
    val s=Module(new CdcSync(1));s.clk:=bootstrap.aonClock
    s.reset_n:=bootstrap.aonReset_n;s.in:=value.asUInt;s.out.asBool
  }
  stable:=toAon(counter.stable)
  withClockAndReset(bootstrap.aonClock,(!bootstrap.aonReset_n).asAsyncReset) {
    val bootDone=RegInit(false.B)
    when(authorized) {bootDone:=true.B}
    // Raw reset assertion propagates without needing any oscillator edges.
    serviceReset_n:=bootstrap.aonReset_n && bootDone
  }
    Some((counter,configuration))
  }
  // Passive access for the retained reference's formal transfer/count oracle.
  // No extra hardware is elaborated in either configuration.
  def counter: OscStability=legacy.get._1
  def configuration: CdcFifo=legacy.get._2
}
