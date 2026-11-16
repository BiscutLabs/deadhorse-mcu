package deadhorse.perf_core

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException

class CounterHarness(width: Int, updated: Boolean, corrupt: Boolean = false) extends RawModule {
  val tick = IO(Input(Bool()))
  val reset_n = IO(Input(Bool()))
  val increment = IO(Input(Bool()))
  val writeLow = IO(Input(Bool()))
  val writeHigh = IO(Input(Bool()))
  val data = IO(Input(UInt(32.W)))
  val value = IO(Output(UInt(64.W)))
  val next = IO(Output(UInt(64.W)))
  val dut = Module(new IbexCounter(width, updated))
  dut.clk_i := tick.asClock
  dut.rst_ni := reset_n
  dut.counter_inc_i := increment
  dut.counter_we_i := writeLow
  dut.counterh_we_i := writeHigh
  dut.counter_val_i := data
  value := dut.counter_val_o ^ (if (corrupt) 1.U else 0.U)
  next := dut.counter_val_upd_o
}

class CsrHarness extends RawModule {
  val tick = IO(Input(Bool()))
  val reset_n = IO(Input(Bool()))
  val enable = IO(Input(Bool()))
  val data = IO(Input(UInt(8.W)))
  val value = IO(Output(UInt(8.W)))
  val error = IO(Output(Bool()))
  val dut = Module(new IbexCsr(8, true, 0xa5))
  dut.clk_i := tick.asClock
  dut.rst_ni := reset_n
  dut.wr_en_i := enable
  dut.wr_data_i := data
  value := dut.rd_data_o
  error := dut.rd_error_o
}

class LeafSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t11/simulation").toAbsolutePath
  }
  private def counterCheck(dut: CounterHarness, width: Int, updated: Boolean): Unit = {
    // Integer state model, with high/low word writes and arithmetic modulo 2^width.
    val modulus = BigInt(1) << width
    val word = BigInt(1) << 32
    var model = BigInt(0)
    def observe(): Unit = {
      assert(dut.value.peek().litValue == model, "COUNTER_MODEL_MISMATCH")
      assert(dut.next.peek().litValue == (if (updated) (model + 1) % modulus else BigInt(0)))
    }
    dut.tick.poke(false.B)
    dut.increment.poke(false.B)
    dut.writeHigh.poke(false.B)
    dut.writeLow.poke(false.B)
    dut.data.poke(0.U)
    dut.reset_n.poke(true.B)
    dut.value.peek()
    dut.reset_n.poke(false.B)
    observe()
    dut.reset_n.poke(true.B)
    observe()
    val random = new scala.util.Random(0x11c0L)
    val vectors = Seq((true, true, true, word - 1), (false, true, true, word - 1),
      (false, false, true, BigInt(0)), (false, false, true, BigInt(0))) ++
      (0 until 256).map(_ => (random.nextBoolean(), random.nextBoolean(),
        random.nextBoolean(), BigInt(32, random)))
    for ((high, low, inc, data) <- vectors) {
      dut.writeHigh.poke(high.B)
      dut.writeLow.poke(low.B)
      dut.increment.poke(inc.B)
      dut.data.poke(data.U)
      observe() // Inputs cannot update stored state before the edge.
      model = (if (high) data * word + model % word
        else if (low) model / word * word + data
        else if (inc) model + 1 else model) % modulus
      dut.tick.poke(true.B)
      observe()
      dut.tick.poke(false.B)
      observe()
    }
    dut.reset_n.poke(false.B)
    model = 0
    observe() // Reset an active counter without a clock edge.
  }

  for ((width, updated) <- Seq((32, false), (64, false), (64, true))) {
    test(s"counter width=$width updated=$updated: writes, priority, wrap, hold and async reset") {
      simulateRaw(new CounterHarness(width, updated), subdirectory = Some(s"counter_${width}_$updated")) {
        dut => counterCheck(dut, width, updated)
      }
    }
  }
  test("counter model rejects corrupt output") {
    val failure = intercept[TestFailedException] {
      simulateRaw(new CounterHarness(64, true, true), subdirectory = Some("counter_fault")) {
        dut => counterCheck(dut, 64, true)
      }
    }
    assert(failure.getMessage.contains("COUNTER_MODEL_MISMATCH"))
  }
  test("shadow CSR reset, hold and write sequence") {
    simulateRaw(new CsrHarness, subdirectory = Some("shadow_csr")) { dut =>
      var model = BigInt(0xa5)
      def observe(): Unit = {
        assert(dut.value.peek().litValue == model)
        assert(dut.error.peek().litValue == 0)
      }
      dut.tick.poke(false.B)
      dut.enable.poke(false.B)
      dut.data.poke(0.U)
      dut.reset_n.poke(true.B)
      dut.value.peek()
      dut.reset_n.poke(false.B)
      observe()
      dut.reset_n.poke(true.B)
      for (data <- 0 until 256; enable <- Seq(false, true)) {
        dut.data.poke(data.U)
        dut.enable.poke(enable.B)
        observe()
        if (enable) model = data
        dut.tick.poke(true.B)
        observe()
        dut.tick.poke(false.B)
        observe()
      }
      dut.reset_n.poke(false.B)
      model = 0xa5
      observe()
    }
  }
}
