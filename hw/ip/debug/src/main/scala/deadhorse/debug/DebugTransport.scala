package deadhorse.debug
import chisel3._
import chisel3.util._
import deadhorse.lib.{CdcFifo,CdcEpoch,ResetRelease}

/** The TAP's interface-only vendor patch makes both handshake sides TCK-local.
  * D106 quarantines immediately, then flushes both directions on local clocks. */
class DebugTransport(qualifiedResets: Boolean=false) extends RawModule {
  protected def requestFifo(): CdcFifo=new CdcFifo(41,qualifiedResets=true,synchronousFlush=true)
  protected def requestReset(por: Bool,epoch: Bool): Bool=por && epoch
  protected def responseReset(por: Bool,epoch: Bool): Bool=por && epoch
  val mainClock=IO(Input(Clock()));val tck=IO(Input(Clock()));val por_n=IO(Input(Bool()))
  val clear_n=IO(Input(Bool()))
  val scanRequest=IO(Flipped(Decoupled(UInt(41.W))))
  val scanResponse=IO(Decoupled(UInt(34.W)))
  val request=IO(Decoupled(UInt(41.W)));val response=IO(Flipped(Decoupled(UInt(34.W))))
  val coreUp=IO(Output(Bool()));val pending=IO(Output(Bool()))
  val domainReset=if(qualifiedResets) Some(IO(Input(new Bundle {val main=Bool();val scan=Bool()}))) else None
  def localRelease(clock: Clock,provided: Option[Bool]): Bool=provided.getOrElse {
    val r=Module(new ResetRelease);r.clk:=clock;r.reset_n:=por_n;r.released
  }
  val tckUp=localRelease(tck,domainReset.map(_.scan));val mainUp=localRelease(mainClock,domainReset.map(_.main))
  val epoch=withClockAndReset(tck,(!tckUp).asAsyncReset) {RegNext(clear_n,false.B)}
  val fence=Module(new CdcEpoch)
  fence.aClock:=tck;fence.bClock:=mainClock
  fence.aReset_n:=tckUp;fence.bReset_n:=mainUp
  fence.cancel_n:=requestReset(por_n,epoch)
  val req=Module(requestFifo());val resp=Module(new CdcFifo(34,qualifiedResets=true,synchronousFlush=true))
  req.writeClock:=tck;req.readClock:=mainClock
  resp.writeClock:=mainClock;resp.readClock:=tck
  req.writeReset_n:=tckUp;req.readReset_n:=mainUp
  resp.writeReset_n:=mainUp;resp.readReset_n:=tckUp
  req.writeOpen.get:=fence.aOpen;req.readOpen.get:=fence.bOpen
  resp.writeOpen.get:=responseReset(mainUp,fence.bOpen)
  resp.readOpen.get:=responseReset(tckUp,fence.aOpen)
  req.push:=scanRequest.valid;req.in:=scanRequest.bits;scanRequest.ready:=req.ready
  request.valid:=req.valid;request.bits:=req.out;req.pop:=request.ready
  resp.push:=response.valid;resp.in:=response.bits;response.ready:=resp.ready
  scanResponse.valid:=resp.valid;scanResponse.bits:=resp.out;resp.pop:=scanResponse.ready
  coreUp:=req.readUp && resp.writeUp
  withClockAndReset(tck,(!tckUp).asAsyncReset) {
    val waiting=RegInit(false.B)
    when(scanRequest.fire) {waiting:=true.B}
    when(scanResponse.fire) {waiting:=false.B}
    when(!fence.aOpen) {waiting:=false.B}
    // A sampled hard-clear must clock main long enough to acknowledge the flush,
    // including when dmactive was never set. No demand before TCK has run.
    pending:=tckUp && (!fence.aOpen || waiting || req.writePending)
    assert(!scanRequest.fire || !waiting)
    assert(!scanResponse.fire || waiting)
  }
}
