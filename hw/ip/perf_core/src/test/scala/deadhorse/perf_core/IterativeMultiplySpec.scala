package deadhorse.perf_core

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException

class IterativeMultiplyHarness(corrupt: Boolean = false) extends RawModule {
  val tick = IO(Input(Bool()))
  val reset_n = IO(Input(Bool()))
  val enable = IO(Input(Bool()))
  val ready = IO(Input(Bool()))
  val a = IO(Input(UInt(32.W)))
  val b = IO(Input(UInt(32.W)))
  val mode = IO(Input(UInt(2.W)))
  val high = IO(Input(Bool()))
  val valid = IO(Output(Bool()))
  val result = IO(Output(UInt(32.W)))
  val dut = Module(new IterativeMultiply)
  dut.clk_i := tick.asClock; dut.rst_ni := reset_n
  dut.enable_i := enable; dut.ready_i := ready
  dut.a_i := a; dut.b_i := b; dut.signed_mode_i := mode; dut.high_i := high
  valid := dut.valid_o
  result := dut.result_o ^ (if (corrupt) dut.valid_o.asUInt else 0.U)
}

class IterativeMultiplySpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t11/simulation").toAbsolutePath
  }
  private def check(d: IterativeMultiplyHarness, resetSweep: Boolean): Unit = {
    val word = BigInt(1) << 32
    val mask = word-1
    val random = new scala.util.Random(0x17132L)
    println("IterativeMultiply seed=0x17132")
    def edge(): Unit = { d.tick.poke(true.B); d.valid.peek(); d.tick.poke(false.B) }
    def reset(): Unit = {
      d.reset_n.poke(false.B); d.valid.expect(false.B); d.result.expect(0.U)
      d.reset_n.poke(true.B)
    }
    d.tick.poke(false.B); d.reset_n.poke(true.B)
    d.enable.poke(false.B); d.ready.poke(false.B)
    d.a.poke(0.U); d.b.poke(0.U); d.mode.poke(0.U); d.high.poke(false.B)
    reset()
    def transaction(a: BigInt, b: BigInt, mode: Int, high: Boolean): Unit = {
      def signed(x: BigInt, on: Boolean) = if (on && x.testBit(31)) x-word else x
      val p = signed(a, (mode&1)!=0) * signed(b, (mode&2)!=0)
      val expected = (if (high) p >> 32 else p) & mask
      d.valid.expect(false.B)
      d.a.poke(a.U); d.b.poke(b.U); d.mode.poke(mode.U); d.high.poke(high.B)
      d.enable.poke(true.B); d.ready.poke(false.B); edge() // capture
      for (i <- 0 until 34) {
        // A captured operation must be independent of live inputs.
        d.a.poke(BigInt(32, random).U); d.b.poke(BigInt(32, random).U)
        d.mode.poke(random.nextInt(4).U); d.high.poke(random.nextBoolean().B)
        d.valid.expect(false.B)
        if (i%4 == 2) {
          d.enable.poke(false.B); edge(); edge(); d.valid.expect(false.B)
        }
        d.enable.poke(true.B); edge()
      }
      d.valid.expect(true.B)
      for (i <- 0 until 6) {
        assert(d.result.peek().litValue == expected, "ITERATIVE_MODEL_MISMATCH")
        d.enable.poke((i%2==0).B); d.ready.poke((i%2!=0).B)
        edge(); d.valid.expect(true.B)
      }
      d.enable.poke(true.B); d.ready.poke(true.B); edge(); d.valid.expect(false.B)
      d.enable.poke(false.B); edge(); edge(); d.valid.expect(false.B)
    }
    if (resetSweep) {
      for (phase <- 0 to 35) {
        d.enable.poke(true.B); d.ready.poke(false.B)
        d.a.poke(mask.U); d.b.poke(mask.U); d.mode.poke(3.U); d.high.poke(true.B)
        for (_ <- 0 until phase) edge()
        reset()
        transaction(7, 11, 0, false)
      }
    }
    val corners = Seq(BigInt(0), BigInt(1), BigInt(2), mask, word/2, word/2-1,
      BigInt("55555555",16), BigInt("aaaaaaaa",16))
    val vectors = (for (a <- corners; b <- corners) yield (a,b)) ++
      (0 until 192).map(_ => (BigInt(32,random), BigInt(32,random)))
    for ((a,b) <- vectors; mode <- 0 until 4; high <- Seq(false,true))
      transaction(a,b,mode,high)
  }
  test("iterative product integer model, capture, exact progress, stalls and reset at every phase") {
    simulateRaw(new IterativeMultiplyHarness, subdirectory=Some("iterative_model"))(d => check(d,true))
  }
  test("iterative checker rejects a corrupt result") {
    val failure = intercept[TestFailedException] {
      simulateRaw(new IterativeMultiplyHarness(true), subdirectory=Some("iterative_fault"))(d => check(d,false))
    }
    assert(failure.getMessage.contains("ITERATIVE_MODEL_MISMATCH"))
  }
}
