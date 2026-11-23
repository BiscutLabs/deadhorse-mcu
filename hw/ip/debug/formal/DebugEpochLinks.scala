package deadhorse.debug
import chisel3._

/** Candidate stage invariants, all assertions, never environmental premises. */
class DebugEpochLinks extends RawModule {
  val main=IO(Input(Clock()));val aon=IO(Input(Clock()))
  val mainUp=IO(Input(Bool()));val aonUp=IO(Input(Bool()));val transportUp=IO(Input(Bool()))
  val captured=IO(Input(UInt(72.W)));val expected=IO(Input(UInt(32.W)))
  val requestPush=IO(Input(Bool()));val requestData=IO(Input(UInt(72.W)))
  val requestValid=IO(Input(Bool()));val requestOut=IO(Input(UInt(72.W)))
  val phase=IO(Input(UInt(2.W)));val linkUp=IO(Input(Bool()));val poison=IO(Input(Bool()))
  val packet=IO(Input(UInt(72.W)));val active=IO(Input(Bool()));val endpointResult=IO(Input(UInt(32.W)))
  val targetValid=IO(Input(Bool()));val targetError=IO(Input(Bool()));val targetData=IO(Input(UInt(32.W)))
  val replyPending=IO(Input(Bool()));val reply=IO(Input(UInt(33.W)))
  val responseValid=IO(Input(Bool()));val responseData=IO(Input(UInt(33.W)))
  val sourceValid=IO(Input(Bool()));val sourceError=IO(Input(Bool()));val sourceData=IO(Input(UInt(32.W)))
  val fabricValid=IO(Input(Bool()));val fabricError=IO(Input(Bool()));val fabricData=IO(Input(UInt(32.W)))
  withClockAndReset(main,(!mainUp).asAsyncReset) {
    assert(!requestPush || requestData===captured,"LINK_SOURCE_STAGING")
    assert(!responseValid || responseData(32) || responseData(31,0)===expected,"LINK_RESPONSE_FIFO")
    assert(!sourceValid || sourceError || sourceData===expected,"LINK_SOURCE_RETURN")
    assert(!fabricValid || fabricError || fabricData===expected,"LINK_FABRIC_RETURN")
  }
  withClockAndReset(aon,(!aonUp).asAsyncReset) {
    assert(!requestValid || requestOut===captured,"LINK_REQUEST_FIFO")
    assert(!linkUp || phase===0.U || packet===captured,"LINK_TARGET_PACKET")
    assert(!linkUp || poison || phase=/=2.U || !active || endpointResult===(captured(71,40)^captured(39,8)),"LINK_ENDPOINT_DATA")
    assert(!linkUp || phase=/=2.U || !targetValid || targetError || targetData===expected,"LINK_TARGET_RETURN")
    assert(!linkUp || !replyPending || reply(32) || reply(31,0)===expected,"LINK_REPLY_STAGING")
  }
}
object EmitDebugEpochLinks extends App {
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new DebugEpochLinks),
    Array("--target-dir",args(0)),Array("--disable-all-randomization","--disable-opt","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
