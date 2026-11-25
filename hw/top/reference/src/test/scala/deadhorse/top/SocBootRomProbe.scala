package deadhorse.top
import chisel3._
import chisel3.util.experimental.BoringUtils

/** Passive observation only; production interfaces/features are unchanged. */
class SocBootRomProbe(rom: String) extends SocOscFlight(rom) {
  val liteHeld=IO(Output(Bool()));val liteResetReleased=IO(Output(Bool()))
  val liteStart=IO(Output(Bool()));val liteReleaseCommand=IO(Output(Bool()))
  val bootControl=digital.subsystem.get.bootControlBlock
  liteReleaseCommand:=BoringUtils.bore(bootControl.state.releaseCommand) && BoringUtils.bore(bootControl.state.releaseKey)
  val dmaActive=IO(Output(Bool()));val warmActive=IO(Output(Bool()))
  warmActive:= !BoringUtils.bore(digital.serviceUp)
  val liteWriteOffer=IO(Output(Bool()))
  val dataRequest=BoringUtils.bore(digital.memory.data.req)
  val dataWrite=BoringUtils.bore(digital.memory.data.bits.we)
  val dataAddress=BoringUtils.bore(digital.memory.data.bits.addr)
  liteWriteOffer:=dataRequest && dataWrite && (dataAddress >= "h30000000".U) && (dataAddress < "h30000400".U)
  liteHeld:=BoringUtils.bore(digital.subsystem.get.liteBootHeld)
  liteResetReleased:=BoringUtils.bore(digital.subsystem.get.liteHart.get.reset_n)
  liteStart:=BoringUtils.bore(digital.subsystem.get.liteHart.get.start)
  dmaActive:=BoringUtils.bore(digital.subsystem.get.dmaHold)
  // T42 passive timing taps. No stimulus, state or production interface changes.
  val transfer=IO(Output(new Bundle {
    val aonClock=Bool()
    val offer=Bool();val ask=Bool();val permit=Bool();val admit=Bool()
    val sourceReq=Bool();val sourceGrant=Bool();val sourceReply=Bool()
    val address=UInt(32.W);val write=Bool()
    val requestPush=Bool();val requestPop=Bool()
    val targetReq=Bool();val targetGrant=Bool();val targetReply=Bool()
    val ramReq=Bool();val ramGrant=Bool();val ramReply=Bool()
    val responsePush=Bool();val responsePop=Bool()
    val cpuReq=Bool();val cpuGrant=Bool();val cpuReply=Bool();val cpuAddress=UInt(32.W)
    val cpuWrite=Bool()
  }))
  val bridge=digital.subsystem.get.toAon
  val ram=digital.subsystem.get.retained
  transfer.aonClock:=BoringUtils.bore(bridge.targetClock).asBool
  transfer.offer:=BoringUtils.bore(bridge.offer)
  transfer.ask:=BoringUtils.bore(bridge.permitRequest)
  transfer.permit:=BoringUtils.bore(bridge.permit)
  transfer.admit:=BoringUtils.bore(bridge.admit)
  transfer.sourceReq:=BoringUtils.bore(bridge.source.req)
  transfer.sourceGrant:=BoringUtils.bore(bridge.source.gnt)
  transfer.sourceReply:=BoringUtils.bore(bridge.source.rvalid)
  transfer.address:=BoringUtils.bore(bridge.source.bits.addr)
  transfer.write:=BoringUtils.bore(bridge.source.bits.we)
  transfer.requestPush:=BoringUtils.bore(bridge.requests.push) && BoringUtils.bore(bridge.requests.ready)
  transfer.requestPop:=BoringUtils.bore(bridge.requests.pop) && BoringUtils.bore(bridge.requests.valid)
  transfer.targetReq:=BoringUtils.bore(bridge.target.req)
  transfer.targetGrant:=BoringUtils.bore(bridge.target.gnt)
  transfer.targetReply:=BoringUtils.bore(bridge.target.rvalid)
  transfer.ramReq:=BoringUtils.bore(ram.bus.req)
  transfer.ramGrant:=BoringUtils.bore(ram.bus.gnt)
  transfer.ramReply:=BoringUtils.bore(ram.bus.rvalid)
  transfer.responsePush:=BoringUtils.bore(bridge.responses.push) && BoringUtils.bore(bridge.responses.ready)
  transfer.responsePop:=BoringUtils.bore(bridge.responses.pop) && BoringUtils.bore(bridge.responses.valid)
  transfer.cpuReq:=dataRequest;transfer.cpuWrite:=dataWrite;transfer.cpuAddress:=dataAddress
  transfer.cpuGrant:=BoringUtils.bore(digital.memory.data.gnt)
  transfer.cpuReply:=BoringUtils.bore(digital.memory.data.rvalid)
}
object EmitBootRomProbe extends App {
  require(args.length==2)
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(new SocBootRomProbe(args(1)),
    Array("--target-dir",args(0)),Array("--disable-all-randomization","--strip-debug-info",
      "--preserve-values=named","--verification-flavor=immediate","--lower-to-core",
      "--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
      "--ckg-enable=en_i","--ckg-test-enable=test_en_i"))
}
