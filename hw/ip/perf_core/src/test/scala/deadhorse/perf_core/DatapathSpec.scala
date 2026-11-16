package deadhorse.perf_core

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException

class RegisterFileHarness(corrupt: Boolean = false) extends RawModule {
  val tick = IO(Input(Bool()))
  val reset_n = IO(Input(Bool()))
  val write = IO(Input(Bool()))
  val destination = IO(Input(UInt(5.W)))
  val data = IO(Input(UInt(32.W)))
  val sourceA = IO(Input(UInt(5.W)))
  val sourceB = IO(Input(UInt(5.W)))
  val valueA = IO(Output(UInt(32.W)))
  val valueB = IO(Output(UInt(32.W)))
  val error = IO(Output(Bool()))
  val dut = Module(new IbexRegisterFile)
  dut.clk_i := tick.asClock
  dut.rst_ni := reset_n
  dut.test_en_i := false.B
  dut.dummy_instr_id_i := false.B
  dut.dummy_instr_wb_i := false.B
  dut.we_a_i := write
  dut.waddr_a_i := destination
  dut.wdata_a_i := data
  dut.raddr_a_i := sourceA
  dut.raddr_b_i := sourceB
  valueA := dut.rdata_a_o ^ (if (corrupt) 1.U else 0.U)
  valueB := dut.rdata_b_o
  error := dut.err_o
}

class DatapathSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t11/simulation").toAbsolutePath
  }
  private val modulus = BigInt(1) << 32
  private val mask = modulus - 1
  private def signed(x: BigInt): BigInt = if (x.testBit(31)) x - modulus else x

  test("RV32I ALU integer model: arithmetic, comparison, shifts and multdiv sum") {
    simulateRaw(new IbexAlu, subdirectory = Some("alu_model")) { dut =>
      // Independent integer operations; no reuse of RTL carry/shift helpers.
      val random = new scala.util.Random(0xa1L)
      val edges = Seq(BigInt(0), BigInt(1), mask, modulus / 2, modulus / 2 - 1)
      val pairs = (for (a <- edges; b <- edges) yield (a, b)) ++
        (0 until 200).map(_ => (BigInt(32, random), BigInt(32, random)))
      dut.imd_val_q_i.poke(0.U)
      dut.multdiv_sel_i.poke(false.B)
      dut.multdiv_operand_a_i.poke(0.U)
      dut.multdiv_operand_b_i.poke(0.U)
      for ((a, b) <- pairs; code <- Seq(0, 1, 2, 3, 4, 8, 9, 10, 25, 26, 27, 28, 29, 30, 43, 44);
           first <- Seq(true, false)) {
        val shift = (if (first) b.toInt else -b.toInt) & 31
        val expected: BigInt = code match {
          case 0 => a + b
          case 1 => a - b
          case 2 => a ^ b
          case 3 => a | b
          case 4 => a & b
          case 8 => signed(a) >> shift
          case 9 => a >> shift
          case 10 => a << shift
          case 25 | 43 => if (signed(a) < signed(b)) BigInt(1) else BigInt(0)
          case 26 | 44 => if (a < b) BigInt(1) else BigInt(0)
          case 27 => if (signed(a) >= signed(b)) BigInt(1) else BigInt(0)
          case 28 => if (a >= b) BigInt(1) else BigInt(0)
          case 29 => if (a == b) BigInt(1) else BigInt(0)
          case 30 => if (a != b) BigInt(1) else BigInt(0)
        }
        dut.operator_i.poke(code.U)
        dut.operand_a_i.poke(a.U)
        dut.operand_b_i.poke(b.U)
        dut.instr_first_cycle_i.poke(first.B)
        assert(dut.result_o.peek().litValue == (expected & mask), s"ALU_MODEL_MISMATCH op=$code a=$a b=$b")
        val subtract = Set(1, 25, 26, 27, 28, 29, 30, 43, 44)(code)
        val arithmetic = (if (subtract) a - b else a + b) & mask
        assert(dut.adder_result_o.peek().litValue == arithmetic)
        assert(dut.is_equal_result_o.peek().litValue == (if (arithmetic == 0) BigInt(1) else BigInt(0)))
        assert(dut.imd_val_d_o.peek().litValue == 0 && dut.imd_val_we_o.peek().litValue == 0)
      }
      dut.multdiv_sel_i.poke(true.B)
      for (_ <- 0 until 256) {
        val a = BigInt(33, random)
        val b = BigInt(33, random)
        dut.multdiv_operand_a_i.poke(a.U)
        dut.multdiv_operand_b_i.poke(b.U)
        assert(dut.adder_result_ext_o.peek().litValue == a + b)
        assert(dut.adder_result_o.peek().litValue == ((a + b) >> 1 & mask))
        assert(dut.is_equal_result_o.peek().litValue == (if (((a + b) >> 1 & mask) == 0) BigInt(1) else BigInt(0)))
      }
    }
  }

  private def registerCheck(dut: RegisterFileHarness): Unit = {
    val model = Array.fill[BigInt](32)(0)
    def observe(a: Int, b: Int): Unit = {
      dut.sourceA.poke(a.U)
      dut.sourceB.poke(b.U)
      assert(dut.valueA.peek().litValue == model(a), "REGISTER_MODEL_MISMATCH")
      assert(dut.valueB.peek().litValue == model(b), "REGISTER_MODEL_MISMATCH")
      assert(dut.error.peek().litValue == 0)
    }
    dut.tick.poke(false.B)
    dut.write.poke(false.B)
    dut.destination.poke(0.U)
    dut.data.poke(0.U)
    dut.sourceA.poke(0.U)
    dut.sourceB.poke(0.U)
    dut.reset_n.poke(true.B)
    dut.valueA.peek()
    dut.reset_n.poke(false.B)
    for (a <- 0 until 32) observe(a, 31 - a)
    dut.reset_n.poke(true.B)
    val random = new scala.util.Random(0x11fL)
    for (iteration <- 0 until 512) {
      val destination = if (iteration < 32) iteration else random.nextInt(32)
      val enable = iteration < 32 || random.nextBoolean()
      val data = BigInt(32, random)
      val source = random.nextInt(32)
      dut.write.poke(enable.B)
      dut.destination.poke(destination.U)
      dut.data.poke(data.U)
      observe(destination, source) // No write-through before a rising edge.
      if (enable && destination != 0) model(destination) = data
      dut.tick.poke(true.B)
      observe(destination, source)
      dut.tick.poke(false.B)
      observe(source, destination)
    }
    dut.reset_n.poke(false.B)
    for (index <- model.indices) model(index) = 0
    for (a <- 0 until 32) observe(a, 31 - a)
  }
  test("register array model: x0, dual reads, edge writes, hold and asynchronous reset") {
    simulateRaw(new RegisterFileHarness, subdirectory = Some("register_model"))(registerCheck)
  }
  test("register array checker rejects a corrupted output") {
    val failure = intercept[TestFailedException] {
      simulateRaw(new RegisterFileHarness(true), subdirectory = Some("register_fault"))(registerCheck)
    }
    assert(failure.getMessage.contains("REGISTER_MODEL_MISMATCH"))
  }
}
