package deadhorse.debug
import chisel3._
import chisel3.util._
import deadhorse.lib.{CdcFifo,CdcEpoch,ResetRelease}

/** The TAP's interface-only vendor patch makes both handshake sides TCK-local.
  * D106 quarantines immediately, then flushes both directions on local clocks. */
class DebugTransport extends RawModule {
  protected def requestFifo(): CdcFifo=new CdcFifo(41,qualifiedResets=true,synchronousFlush=true)
  protected def requestReset(por: Bool,epoch: Bool): Bool=por && epoch
  protected def responseReset(por: Bool,epoch: Bool): Bool=por && epoch
  val mainClock=IO(Input(Clock()));val tck=IO(Input(Clock()));val por_n=IO(Input(Bool()))
  val clear_n=IO(Input(Bool()))
  val scanRequest=IO(Flipped(Decoupled(UInt(41.W))))
  val scanResponse=IO(Decoupled(UInt(34.W)))
  val request=IO(Decoupled(UInt(41.W)));val response=IO(Flipped(Decoupled(UInt(34.W))))
  val coreUp=IO(Output(Bool()));val pending=IO(Output(Bool()))
  val tckRelease=Module(new ResetRelease);tckRelease.clk:=tck;tckRelease.reset_n:=por_n
  val mainRelease=Module(new ResetRelease);mainRelease.clk:=mainClock;mainRelease.reset_n:=por_n
  val epoch=withClockAndReset(tck,(!tckRelease.released).asAsyncReset) {RegNext(clear_n,false.B)}
  val fence=Module(new CdcEpoch)
  fence.aClock:=tck;fence.bClock:=mainClock
  fence.aReset_n:=tckRelease.released;fence.bReset_n:=mainRelease.released
  fence.cancel_n:=requestReset(por_n,epoch)
  val req=Module(requestFifo());val resp=Module(new CdcFifo(34,qualifiedResets=true,synchronousFlush=true))
  req.writeClock:=tck;req.readClock:=mainClock
  resp.writeClock:=mainClock;resp.readClock:=tck
  req.writeReset_n:=tckRelease.released;req.readReset_n:=mainRelease.released
  resp.writeReset_n:=mainRelease.released;resp.readReset_n:=tckRelease.released
  req.writeOpen.get:=fence.aOpen;req.readOpen.get:=fence.bOpen
  resp.writeOpen.get:=responseReset(mainRelease.released,fence.bOpen)
  resp.readOpen.get:=responseReset(tckRelease.released,fence.aOpen)
  req.push:=scanRequest.valid;req.in:=scanRequest.bits;scanRequest.ready:=req.ready
  request.valid:=req.valid;request.bits:=req.out;req.pop:=request.ready
  resp.push:=response.valid;resp.in:=response.bits;response.ready:=resp.ready
  scanResponse.valid:=resp.valid;scanResponse.bits:=resp.out;resp.pop:=scanResponse.ready
  coreUp:=req.readUp && resp.writeUp
  withClockAndReset(tck,(!tckRelease.released).asAsyncReset) {
    val waiting=RegInit(false.B)
    when(scanRequest.fire) {waiting:=true.B}
    when(scanResponse.fire) {waiting:=false.B}
    when(!fence.aOpen) {waiting:=false.B}
    // A sampled hard-clear must clock main long enough to acknowledge the flush,
    // including when dmactive was never set. No demand before TCK has run.
    pending:=tckRelease.released && (!fence.aOpen || waiting || req.writePending)
    assert(!scanRequest.fire || !waiting)
    assert(!scanResponse.fire || waiting)
  }
}
