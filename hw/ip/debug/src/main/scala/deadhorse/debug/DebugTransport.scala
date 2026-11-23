package deadhorse.debug
import chisel3._
import chisel3.util._
import deadhorse.lib.{CdcFifo,ResetRelease}

/** The TAP's interface-only vendor patch makes both handshake sides TCK-local.
  * Only shared FIFOs cross payloads; common reset flushes both directions. */
class DebugTransport extends RawModule {
  protected def requestFifo(): CdcFifo=new CdcFifo(41)
  protected def responseReset(por: Bool,epoch: Bool): Bool=por && epoch
  val mainClock=IO(Input(Clock()));val tck=IO(Input(Clock()));val por_n=IO(Input(Bool()))
  val clear_n=IO(Input(Bool()))
  val scanRequest=IO(Flipped(Decoupled(UInt(41.W))))
  val scanResponse=IO(Decoupled(UInt(34.W)))
  val request=IO(Decoupled(UInt(41.W)));val response=IO(Flipped(Decoupled(UInt(34.W))))
  val coreUp=IO(Output(Bool()));val pending=IO(Output(Bool()))
  val tckRelease=Module(new ResetRelease);tckRelease.clk:=tck;tckRelease.reset_n:=por_n
  val epoch=withClockAndReset(tck,(!tckRelease.released).asAsyncReset) {RegNext(clear_n,false.B)}
  val req=Module(requestFifo());val resp=Module(new CdcFifo(34))
  req.writeClock:=tck;req.readClock:=mainClock
  resp.writeClock:=mainClock;resp.readClock:=tck
  req.writeReset_n:=por_n && epoch;req.readReset_n:=por_n && epoch
  resp.writeReset_n:=responseReset(por_n,epoch);resp.readReset_n:=responseReset(por_n,epoch)
  req.push:=scanRequest.valid;req.in:=scanRequest.bits;scanRequest.ready:=req.ready
  request.valid:=req.valid;request.bits:=req.out;req.pop:=request.ready
  resp.push:=response.valid;resp.in:=response.bits;response.ready:=resp.ready
  scanResponse.valid:=resp.valid;scanResponse.bits:=resp.out;resp.pop:=scanResponse.ready
  coreUp:=req.readUp && resp.writeUp
  withClockAndReset(tck,(!(por_n && epoch)).asAsyncReset) {
    val waiting=RegInit(false.B)
    when(scanRequest.fire) {waiting:=true.B}
    when(scanResponse.fire) {waiting:=false.B}
    pending:=waiting || req.writePending
    assert(!scanRequest.fire || !waiting)
    assert(!scanResponse.fire || waiting)
  }
}
