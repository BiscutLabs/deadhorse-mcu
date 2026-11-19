package deadhorse.usb

import chisel3._

/** Standalone measurement fixture for the exact production SIE parameters.
  * The clock/reset/enable fields of the cloned vendor interface are unused;
  * the actual SIE is driven by the same root clock/reset and proven cadence
  * as UsbEngine. Other vendor inputs remain external full-rate inputs.
  */
class UsbSieTiming extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val sie=Module(new UsbSie)
  val io=IO(chiselTypeOf(sie.io))
  sie.io<>io
  val cadence=Module(new UsbBitEnable)
  // Keep the exact full cadence module used by the source-bound phase proof.
  dontTouch(cadence.preEnable)
  cadence.clk:=clk;cadence.reset_n:=reset_n
  sie.io.clk_i:=clk;sie.io.rstn_i:=reset_n;sie.io.clk_gate_i:=cadence.enable
}

object EmitUsbSieTiming {
  def main(args:Array[String]):Unit={
    val path=java.nio.file.Paths.get(args(0)).toAbsolutePath.normalize
    require(path.startsWith(java.nio.file.Paths.get("build").toAbsolutePath.normalize))
    _root_.circt.stage.ChiselStage.emitSystemVerilogFile(new UsbSieTiming,
      Array("--target-dir",path.toString),Array("--disable-all-randomization","-strip-debug-info","--preserve-values=named"))
  }
}
