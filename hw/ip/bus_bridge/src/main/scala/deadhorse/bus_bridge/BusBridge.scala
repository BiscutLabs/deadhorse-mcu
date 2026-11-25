package deadhorse.bus_bridge

import chisel3._
import chisel3.util._
import deadhorse.lib._

class BusBridge(limit: Int = 131072) extends RawModule {
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
  val localSourceReset = Module(new ResetRelease); val localTargetReset = Module(new ResetRelease)
  localSourceReset.clk := sourceClock; localSourceReset.reset_n := sourceReset_n
  localTargetReset.clk := targetClock; localTargetReset.reset_n := targetReset_n
  val producer = Module(sourceEndpoint()); val consumer = Module(new BridgeTarget)
  val abort = producer.abort
  val transportReset_n = transportEpoch(sourceReset_n,targetReset_n,abort)
  val sourceTransport = Module(new ResetRelease); val targetTransport = Module(new ResetRelease)
  sourceTransport.clk := sourceClock; targetTransport.clk := targetClock
  sourceTransport.reset_n := transportReset_n; targetTransport.reset_n := transportReset_n
  val requests = Module(new CdcFifo(72)); val responses = Module(new CdcFifo(33))
  requests.writeClock := sourceClock; requests.readClock := targetClock
  responses.writeClock := targetClock; responses.readClock := sourceClock
  requests.writeReset_n := transportReset_n; requests.readReset_n := transportReset_n
  responses.writeReset_n := transportReset_n; responses.readReset_n := transportReset_n
  val abortAck = consumer.abortAck
  val ackSync = Module(new CdcSync(1))
  ackSync.clk := sourceClock; ackSync.reset_n := localSourceReset.released; ackSync.in := abortAck.asUInt
  val targetDemand = consumer.needClock
  targetClockHold := targetDemand
  val drainSync = Module(new CdcSync(1))
  drainSync.clk := sourceClock; drainSync.reset_n := localSourceReset.released; drainSync.in := targetDemand.asUInt
  producer.clk := sourceClock; producer.reset_n := localSourceReset.released
  consumer.clk := targetClock; consumer.reset_n := localTargetReset.released
  producer.source <> source; consumer.target <> target
  producer.offer := offer; producer.permit := permit; producer.linkUp := sourceTransport.released
  producer.requestReady := requests.ready; requests.push := producer.requestPush; requests.in := producer.requestData
  producer.responseValid := responses.valid; producer.responseData := responses.out; responses.pop := producer.responsePop
  producer.abortAcknowledged := ackSync.out.asBool; producer.targetNeedsClock := drainSync.out.asBool
  permitRequest := producer.permitRequest; admit := producer.admit; clockRequest := producer.clockRequest
  consumer.linkUp := targetTransport.released; consumer.quiescent := quiescent; isolated := consumer.isolated
  consumer.requestValid := requests.valid; consumer.requestData := requests.out; requests.pop := consumer.requestPop
  consumer.responseReady := responses.ready; responses.push := consumer.responsePush; responses.in := consumer.responseData

}

class DirectionPermit extends RawModule {
  protected def arbiter(): DirectionArbiter = new DirectionArbiter
  val aonClock = IO(Input(Clock())); val mainClock = IO(Input(Clock()))
  val aonReset_n = IO(Input(Bool())); val mainReset_n = IO(Input(Bool()))
  val requestAon = IO(Input(Bool())); val requestMain = IO(Input(Bool()))
  val permitAon = IO(Output(Bool())); val permitMain = IO(Output(Bool()))
  val ar = Module(new ResetRelease); val mr = Module(new ResetRelease)
  ar.clk := aonClock; mr.clk := mainClock
  ar.reset_n := aonReset_n && mainReset_n; mr.reset_n := aonReset_n && mainReset_n
  val mainReq = Module(new CdcSync(1)); val mainGrant = Module(new CdcSync(1))
  val returnedGrant = Module(new CdcSync(1))
  mainReq.clk := aonClock; mainReq.reset_n := ar.released; mainReq.in := requestMain.asUInt
  mainGrant.clk := mainClock; mainGrant.reset_n := mr.released
  returnedGrant.clk := aonClock; returnedGrant.reset_n := ar.released; returnedGrant.in := mainGrant.out
  val control = Module(arbiter())
  control.clk := aonClock; control.reset_n := ar.released
  control.requestAon := requestAon; control.requestMain := mainReq.out.asBool
  control.returnedMain := returnedGrant.out.asBool
  permitAon := control.permitAon; mainGrant.in := control.grantMain.asUInt
  permitMain := mainGrant.out.asBool
}
