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
}
object EmitBootRomProbe extends App {
  require(args.length==2)
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(new SocBootRomProbe(args(1)),
    Array("--target-dir",args(0)),Array("--disable-all-randomization","--strip-debug-info",
      "--preserve-values=named","--verification-flavor=immediate","--lower-to-core",
      "--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
      "--ckg-enable=en_i","--ckg-test-enable=test_en_i"))
}
