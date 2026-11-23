package deadhorse.debug
import chisel3._
import chisel3.util._
import deadhorse.lib._
import _root_.circt.stage.ChiselStage

/** Actual independent clocks. The producer is the DTM's single-outstanding
  * transaction contract; the consumer returns one arbitrary response per request.
  * No clock progress or target response-time assumption is made for safety. */
class DebugTransportFormal(variant: String) extends RawModule {
  val tck=IO(Input(Clock()));val main=IO(Input(Clock()));val por_n=IO(Input(Bool()))
  val clear_n=IO(Input(Bool()));val offer=IO(Input(Bool()));val value=IO(Input(UInt(41.W)))
  val takeRequest=IO(Input(Bool()));val offerResponse=IO(Input(Bool()));val reply=IO(Input(UInt(34.W)))
  val takeResponse=IO(Input(Bool()))
  val d=Module[DebugTransport](variant match {
    case "corrupt"=>new DebugTransport {
      override protected def requestFifo(): CdcFifo=new CdcFifo(41) {
        override protected def makeReader(): CdcRead=new CdcRead(41,2) {
          override protected def capture(v: UInt): UInt=v ^ 1.U
        }
      }
    }
    case "stale"=>new DebugTransport {override protected def responseReset(p: Bool,e: Bool): Bool=p}
    case _=>new DebugTransport
  })
  d.mainClock:=main;d.tck:=tck;d.por_n:=por_n;d.clear_n:=clear_n
  // Independent epoch observer samples synchronous TCK clear. The DUT's extra
  // POR-release qualification may delay initial readiness, but never transfers.
  val sampledClear=withClockAndReset(tck,(!por_n).asAsyncReset) {RegNext(clear_n,false.B)}
  val epochReset=(!(por_n && sampledClear)).asAsyncReset
  val put=withClockAndReset(tck,epochReset) {RegInit(false.B)}
  val got=withClockAndReset(main,epochReset) {RegInit(false.B)}
  val sent=withClockAndReset(main,epochReset) {RegInit(false.B)}
  val done=withClockAndReset(tck,epochReset) {RegInit(false.B)}
  val expected=withClockAndReset(tck,epochReset) {Reg(UInt(41.W))}
  val expectedReply=withClockAndReset(main,epochReset) {Reg(UInt(34.W))}
  d.scanRequest.valid:=offer && put===done;d.scanRequest.bits:=value
  d.request.ready:=takeRequest
  d.response.valid:=offerResponse && got=/=sent;d.response.bits:=expectedReply
  d.scanResponse.ready:=takeResponse
  withClockAndReset(tck,epochReset) {
    when(d.scanRequest.fire) {put:= !put;expected:=value}
    when(d.scanResponse.fire) {done:= !done}
    val held=RegNext(d.scanResponse.valid && !takeResponse,false.B);val old=RegNext(d.scanResponse.bits)
    if(variant=="cover") {
      cover(d.scanResponse.fire)
      cover(held && d.scanResponse.fire)
    } else {
      assert(!d.scanResponse.valid || sent=/=done,"DBG_DMI_RESPONSE_ONCE")
      assert(!d.scanResponse.valid || d.scanResponse.bits===expectedReply,"DBG_DMI_RESPONSE_DATA")
      assert(!held || d.scanResponse.valid && d.scanResponse.bits===old,"DBG_DMI_RESPONSE_HELD")
    }
  }
  withClockAndReset(main,epochReset) {
    when(d.request.fire) {got:= !got;expectedReply:=reply}
    when(d.response.fire) {sent:= !sent}
    val held=RegNext(d.request.valid && !takeRequest,false.B);val old=RegNext(d.request.bits)
    if(variant=="cover") {cover(d.request.fire);cover(held && d.request.fire)} else {
      assert(!d.request.valid || put=/=got,"DBG_DMI_REQUEST_ONCE")
      assert(!d.request.valid || d.request.bits===expected,"DBG_DMI_REQUEST_DATA")
      assert(!held || d.request.valid && d.request.bits===old,"DBG_DMI_REQUEST_HELD")
    }
  }
}
object EmitDebugTransportFormal extends App {
  for(v<-Seq("correct","corrupt","stale","cover")) ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new DebugTransportFormal(v)),Array("--target-dir",s"${args(0)}/$v"),
    Array("--disable-all-randomization","--disable-opt","--lint-static-asserts=false", "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
