package deadhorse.timing

import chisel3._
import circt.stage.ChiselStage
import deadhorse.lib.{ClockGate,ClockGateTarget}
import java.nio.file.{Files,Paths}

/** Physical-flow fixture: root and gated registers with an actual library ICG. */
class GatedTiming extends RawModule {
  val clk=IO(Input(Clock())); val reset_n=IO(Input(Bool()))
  val enable=IO(Input(Bool())); val test_enable=IO(Input(Bool()))
  val data=IO(Input(UInt(8.W))); val out=IO(Output(UInt(8.W)))
  val gate=Module(new ClockGate(ClockGateTarget.Asic))
  gate.clk_i:=clk; gate.test_en_i:=test_enable
  withClockAndReset(clk,(!reset_n).asAsyncReset) { gate.en_i:=RegNext(enable,false.B) }
  withClockAndReset(gate.clk_o,(!reset_n).asAsyncReset) { out:=RegNext(data,0.U) }
}

object EmitGatedTiming {
  def main(args:Array[String]):Unit={
    require(args.length==1)
    val output=Paths.get(args(0)).toAbsolutePath.normalize
    require(output.startsWith(Paths.get("build").toAbsolutePath.normalize))
    Files.createDirectories(output)
    ChiselStage.emitSystemVerilogFile(new GatedTiming,Array("--target-dir",output.toString),
      Array("--disable-all-randomization","-strip-debug-info"))
  }
}
