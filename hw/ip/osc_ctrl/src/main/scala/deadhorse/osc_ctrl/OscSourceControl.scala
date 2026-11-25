package deadhorse.osc_ctrl

import chisel3._
import chisel3.util.Cat
import deadhorse.lib._

/** T41 source executors use shared cold releases. Epoch invalidation is an
  * acknowledged synchronous clear, completed before external oscillator stop.
  * Nothing here depends on the gated main clock or on warm reset release.
  */
class OscSourceControl(target: ClockGateTarget=ClockGateTarget.Model) extends RawModule {
  val source=IO(Input(Clock()));val divided=IO(Input(Clock()));val aon=IO(Input(Clock()))
  val coldSource=IO(Input(Bool()));val coldDivided=IO(Input(Bool()));val coldAon=IO(Input(Bool()))
  val pinAon=IO(Input(Bool()));val aonQualified=IO(Input(Bool()));val initialize=IO(Input(Bool()))
  val epochClear=IO(Input(Bool()));val clearAck=IO(Output(UInt(2.W)))
  val gateRequest=IO(Input(Bool()));val authorized=IO(Input(Bool()))
  val qualify=IO(Input(Bool()));val count=IO(Input(UInt(16.W)))
  val localHold=IO(Input(Bool()));val coreIdle=IO(Input(Bool()))
  val main=IO(Output(Clock()));val stable=IO(Output(Bool()));val closed=IO(Output(Bool()))
  val mainQualified=IO(Output(Bool()));val usbQualified=IO(Output(Bool()))
  def synchronize(value: Bool,clock: Clock,reset: Bool): Bool={
    val s=Module(new CdcSync(1));s.clk:=clock;s.reset_n:=reset;s.in:=value.asUInt;s.out.asBool
  }
  val sourceClear=synchronize(epochClear,source,coldSource)
  val dividedClear=synchronize(epochClear,divided,coldDivided)
  def acknowledged(clear: Bool,clock: Clock,reset: Bool): Bool=
    withClockAndReset(clock,(!reset).asAsyncReset) {
      // The second edge is after the ICG's intervening closing low phase.
      // One edge alone would report before the cell has latched gate closure.
      RegNext(RegNext(clear,false.B),false.B)
    }
  val sourceAck=synchronize(acknowledged(sourceClear,source,coldSource),aon,coldAon)
  val dividedAck=synchronize(acknowledged(dividedClear,divided,coldDivided),aon,coldAon)
  clearAck:=Cat(sourceAck,dividedAck)
  def queue(width: Int,wc: Clock,rc: Clock,wr: Bool,rr: Bool,wo: Bool,ro: Bool): CdcFifo={
    val f=Module(new CdcFifo(width,qualifiedResets=true,synchronousFlush=true))
    f.writeClock:=wc;f.readClock:=rc;f.writeReset_n:=wr;f.readReset_n:=rr
    f.writeOpen.get:=wo;f.readOpen.get:=ro;f
  }
  val commands=queue(1,aon,divided,coldAon,coldDivided,!epochClear,!dividedClear)
  val completions=queue(1,divided,aon,coldDivided,coldAon,!dividedClear,!epochClear)
  val gate=Module(new OscMainGate(target,withClear=true))
  gate.clk:=divided;gate.reset_n:=coldDivided;gate.clear.get:=dividedClear
  gate.command:=commands.valid;gate.request:=commands.out.asBool;gate.verified:=authorized
  commands.pop:=commands.valid && gate.ready
  completions.push:=gate.completed && completions.ready;completions.in:=gate.result.asUInt
  gate.consume:=completions.ready;gate.localHold:=localHold;gate.coreIdle:=coreIdle;main:=gate.gated
  withClockAndReset(aon,(!coldAon).asAsyncReset) {
    val busy=RegInit(false.B);val issued=RegInit(false.B)
    val known=RegInit(false.B);val applied=RegInit(false.B);val safelyClosed=RegInit(false.B)
    val closedReport=RegInit(false.B)
    val push= !epochClear && !busy && commands.ready && (!known || gateRequest=/=applied || !gateRequest && !safelyClosed)
    commands.push:=push;commands.in:=gateRequest.asUInt
    when(push || gateRequest) {closedReport:=false.B}
    when(push) {busy:=true.B;issued:=gateRequest;known:=false.B}
    completions.pop:=busy && completions.valid
    when(busy && completions.valid) {
      busy:=false.B;known:=true.B;applied:=issued;safelyClosed:=completions.out.asBool
      closedReport:= !issued && !gateRequest && completions.out.asBool
    }
    when(epochClear) {
      busy:=false.B;issued:=false.B;known:=false.B;applied:=false.B
      safelyClosed:=false.B;closedReport:=false.B
    }
    closed:=closedReport
  }
  val configuration=queue(16,aon,source,coldAon,coldSource,!epochClear,!sourceClear)
  withClockAndReset(aon,(!coldAon).asAsyncReset) {
    val sent=RegInit(false.B)
    val push= !epochClear && qualify && !sent && configuration.ready
    configuration.push:=push;configuration.in:=count
    when(push) {sent:=true.B};when(epochClear) {sent:=false.B}
  }
  configuration.pop:=false.B
  val counter=Module(new OscStability(qualifiedReset=true))
  counter.clk:=source;counter.reset_n:=coldSource;counter.clear.get:=sourceClear
  counter.oscillatorOn:=true.B;counter.qualify:=configuration.valid;counter.count:=configuration.out
  stable:=synchronize(counter.stable,aon,coldAon)
  withClockAndReset(aon,(!coldAon).asAsyncReset) {
    val mainDone=RegInit(false.B);val usbDone=RegInit(false.B);val usbArmed=RegInit(false.B)
    when(authorized) {mainDone:=true.B}
    when(initialize) {mainDone:=false.B}
    // Preserve T19's old pin/cold qualification epoch. Other warm sources
    // cannot reset USB through main's newly cleared qualification state.
    when(!authorized) {usbArmed:=true.B}
    when(usbArmed && authorized) {usbDone:=true.B}
    when(!pinAon) {usbDone:=false.B;usbArmed:=false.B}
    mainQualified:=aonQualified && mainDone
    usbQualified:=aonQualified && usbDone
  }
}
