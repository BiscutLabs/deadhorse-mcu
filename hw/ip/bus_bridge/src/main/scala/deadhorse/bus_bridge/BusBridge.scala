package deadhorse.bus_bridge

import chisel3._
import chisel3.util._
import deadhorse.lib._

class BusBridge(limit: Int = 131072, qualifiedResets: Boolean=false) extends RawModule {
  protected def sourceEndpoint(): BridgeSource = new BridgeSource(limit)
  protected def transportEpoch(source: Bool,target: Bool,abort: Bool): Bool=source && target && !abort
  require(limit >= 32)
  val sourceClock = IO(Input(Clock())); val targetClock = IO(Input(Clock()))
  val sourceReset_n = IO(Input(Bool())); val targetReset_n = IO(Input(Bool()))
  val source = IO(new LocalBus); val target = IO(Flipped(new LocalBus))
  val offer = IO(Input(Bool())); val permit = IO(Input(Bool()))
  val permitRequest = IO(Output(Bool())); val admit = IO(Output(Bool()))
  val clockRequest = IO(Output(Bool())); val quiescent = IO(Input(Bool()))
  val targetClockHold = IO(Output(Bool()))
  val isolated = IO(Output(Bool()))
  def localRelease(clock: Clock,reset: Bool): Bool = if(qualifiedResets) reset else {
    val r=Module(new ResetRelease);r.clk:=clock;r.reset_n:=reset;r.released
  }
  val sourceUp=localRelease(sourceClock,sourceReset_n)
  val targetUp=localRelease(targetClock,targetReset_n)
  val producer = Module(sourceEndpoint()); val consumer = Module(new BridgeTarget)
  val abort = producer.abort
  val transportReset_n = transportEpoch(sourceReset_n,targetReset_n,abort)
  val transport = Module(new CdcEpoch)
  transport.aClock := sourceClock; transport.bClock := targetClock
  transport.aReset_n := sourceUp; transport.bReset_n := targetUp
  transport.cancel_n := transportReset_n
  val requests = Module(new CdcFifo(72,qualifiedResets=true,synchronousFlush=true))
  val responses = Module(new CdcFifo(33,qualifiedResets=true,synchronousFlush=true))
  requests.writeClock := sourceClock; requests.readClock := targetClock
  responses.writeClock := targetClock; responses.readClock := sourceClock
  requests.writeReset_n := sourceUp; requests.readReset_n := targetUp
  responses.writeReset_n := targetUp; responses.readReset_n := sourceUp
  requests.writeOpen.get := transport.aOpen; requests.readOpen.get := transport.bOpen
  responses.writeOpen.get := transport.bOpen; responses.readOpen.get := transport.aOpen
  val abortAck = consumer.abortAck
  val ackSync = Module(new CdcSync(1))
  ackSync.clk := sourceClock; ackSync.reset_n := sourceUp; ackSync.in := abortAck.asUInt
  val targetDemand = consumer.needClock
  targetClockHold := targetDemand
  val drainSync = Module(new CdcSync(1))
  drainSync.clk := sourceClock; drainSync.reset_n := sourceUp; drainSync.in := targetDemand.asUInt
  producer.clk := sourceClock; producer.reset_n := sourceUp
  consumer.clk := targetClock; consumer.reset_n := targetUp
  producer.source <> source; consumer.target <> target
  producer.offer := offer; producer.permit := permit; producer.linkUp := transport.aOpen
  producer.requestReady := requests.ready; requests.push := producer.requestPush; requests.in := producer.requestData
  producer.responseValid := responses.valid; producer.responseData := responses.out; responses.pop := producer.responsePop
  producer.abortAcknowledged := ackSync.out.asBool; producer.targetNeedsClock := drainSync.out.asBool
  permitRequest := producer.permitRequest; admit := producer.admit; clockRequest := producer.clockRequest
  consumer.linkUp := transport.bOpen; consumer.quiescent := quiescent; isolated := consumer.isolated
  consumer.requestValid := requests.valid; consumer.requestData := requests.out; requests.pop := consumer.requestPop
  consumer.responseReady := responses.ready; responses.push := consumer.responsePush; responses.in := consumer.responseData

}

class DirectionPermit(qualifiedResets: Boolean=false) extends RawModule {
  protected def arbiter(): DirectionArbiter = new DirectionArbiter
  val aonClock = IO(Input(Clock())); val mainClock = IO(Input(Clock()))
  val aonReset_n = IO(Input(Bool())); val mainReset_n = IO(Input(Bool()))
  val requestAon = IO(Input(Bool())); val requestMain = IO(Input(Bool()))
  val permitAon = IO(Output(Bool())); val permitMain = IO(Output(Bool()))
  def localRelease(clock: Clock,reset: Bool): Bool = if(qualifiedResets) reset else {
    val r=Module(new ResetRelease);r.clk:=clock;r.reset_n:=aonReset_n && mainReset_n;r.released
  }
  val aonUp=localRelease(aonClock,aonReset_n);val mainUp=localRelease(mainClock,mainReset_n)
  val mainReq = Module(new CdcSync(1)); val mainGrant = Module(new CdcSync(1))
  val returnedGrant = Module(new CdcSync(1))
  mainReq.clk := aonClock; mainReq.reset_n := aonUp; mainReq.in := requestMain.asUInt
  mainGrant.clk := mainClock; mainGrant.reset_n := mainUp
  returnedGrant.clk := aonClock; returnedGrant.reset_n := aonUp; returnedGrant.in := mainGrant.out
  val control = Module(arbiter())
  control.clk := aonClock; control.reset_n := aonUp
  control.requestAon := requestAon; control.requestMain := mainReq.out.asBool
  control.returnedMain := returnedGrant.out.asBool
  permitAon := control.permitAon; mainGrant.in := control.grantMain.asUInt
  permitMain := mainGrant.out.asBool
}
