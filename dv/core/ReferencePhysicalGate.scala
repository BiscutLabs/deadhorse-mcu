package deadhorse.reference

import chisel3._
import circt.stage.ChiselStage
import deadhorse.lib.{ClockGate,ClockGateTarget}
import java.nio.file.{Files,Paths}

/** Benchmark-only technology binding; pinned CPU source is unchanged. */
class ReferencePhysicalGate extends RawModule {
  override def desiredName="prim_clock_gating"
  val clk_i=IO(Input(Clock())); val en_i=IO(Input(Bool()))
  val test_en_i=IO(Input(Bool())); val clk_o=IO(Output(Clock()))
  val gate=Module(new ClockGate(ClockGateTarget.Asic))
  gate.clk_i:=clk_i; gate.en_i:=en_i; gate.test_en_i:=test_en_i; clk_o:=gate.clk_o
}

object EmitReferencePhysicalGate {
  def main(args:Array[String]):Unit={
    require(args.length==1)
    val output=Paths.get(args(0)).toAbsolutePath.normalize
    require(output.startsWith(Paths.get("build").toAbsolutePath.normalize))
    Files.createDirectories(output)
    ChiselStage.emitSystemVerilogFile(new ReferencePhysicalGate,
      Array("--target-dir",output.toString),Array("--disable-all-randomization","-strip-debug-info"))
  }
}
