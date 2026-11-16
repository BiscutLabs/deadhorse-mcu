package deadhorse.lib

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException
import circt.stage.ChiselStage
import scala.sys.process._

class ClockGateProbe(target: ClockGateTarget) extends RawModule {
  val phase=IO(Input(Bool())); val enable=IO(Input(Bool())); val testEnable=IO(Input(Bool()))
  val pulse=IO(Output(Bool()))
  val gate=Module(new ClockGate(target))
  gate.clk_i:=phase.asClock; gate.en_i:=enable; gate.test_en_i:=testEnable; pulse:=gate.clk_o.asBool
}

class FpgaEnableProbe extends RawModule {
  val clk=IO(Input(Clock())); val reset_n=IO(Input(Bool()))
  val enable=IO(Input(Bool())); val testEnable=IO(Input(Bool())); val count=IO(Output(UInt(8.W)))
  val gate=Module(new FpgaClockEnable)
  gate.clk_i:=clk; gate.en_i:=enable; gate.test_en_i:=testEnable
  withClockAndReset(gate.clk_o,(!reset_n).asAsyncReset) {
    val value=RegInit(0.U(8.W)); when(gate.enable_o) { value:=value+1.U }; count:=value
  }
}

class ClockGateSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory=Paths.get("build/t11/clock_gate/simulation").toAbsolutePath
  }
  private def phaseCheck(binding: String, negative: Boolean=false): Unit = {
    val dir=s"build/t11/clock_gate/scalatest/$binding-${if(negative) "negative" else "positive"}"
    val options=Array("--disable-all-randomization","-strip-debug-info","--preserve-values=named")
    val flags=if(binding=="model") Array("--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i",
      "--ckg-output=clk_o","--ckg-enable=en_i","--ckg-test-enable=test_en_i") else Array.empty[String]
    ChiselStage.emitSystemVerilogFile(new ClockGate(if(binding=="model") ClockGateTarget.Model else ClockGateTarget.Asic),
      Array("--target-dir",s"$dir/emit"),options++flags)
    val command=Seq("python3","hw/lib/formal/clock_gate_sim.py","--emitted",s"$dir/emit",
      "--output",s"$dir/check","--binding",binding)++(if(negative) Seq("--negative") else Seq.empty)
    assert(Process(command).! == 0,"Icarus phase checker must pass (or reject the injected fault)")
  }
  test("clock gate model preserves pulses and captures test/functional enables") {
    phaseCheck("model")
  }
  test("pinned GF180 cell matches phase model") {
    phaseCheck("asic")
  }
  test("clock-gate checker rejects a corrupted pulse") {
    phaseCheck("model",negative=true)
  }
  test("FPGA consumer uses enable and preserves asynchronous reset") {
    simulateRaw(new FpgaEnableProbe) { d=>
      d.enable.poke(false.B); d.testEnable.poke(false.B); d.reset_n.poke(false.B)
      d.clk.step(); d.reset_n.poke(true.B); var count=0
      for(i<-0 until 64) {
        val en=i%3==0; val test=i%7==0
        d.enable.poke(en.B); d.testEnable.poke(test.B); d.clk.step()
        if(en || test) count+=1
        d.count.expect(count.U)
      }
      d.enable.poke(false.B); d.testEnable.poke(false.B); d.reset_n.poke(false.B); d.count.expect(0.U)
    }
  }
}
