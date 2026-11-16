package deadhorse.perf_core

import chisel3._
import chisel3.util.Cat
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException

class MultdivHarness(corrupt: Boolean = false, iterative: Boolean = false, execution: Boolean = false) extends RawModule {
  val tick = IO(Input(Bool()))
  val reset_n = IO(Input(Bool()))
  val enable = IO(Input(Bool()))
  val ready = IO(Input(Bool()))
  val operation = IO(Input(UInt(2.W)))
  val signedMode = IO(Input(UInt(2.W)))
  val a = IO(Input(UInt(32.W)))
  val b = IO(Input(UInt(32.W)))
  val constantTime = IO(Input(Bool()))
  val result = IO(Output(UInt(32.W)))
  val valid = IO(Output(Bool()))
  if (execution) {
    val dut = Module(new IbexExBlock(iterativeMultiply = true, localDivisionArithmetic = true))
    dut.clk_i := tick.asClock; dut.rst_ni := reset_n
    dut.alu_operator_i := IbexAluOp("ADD")
    dut.alu_operand_a_i := 0.U; dut.alu_operand_b_i := 0.U
    dut.alu_instr_first_cycle_i := true.B
    dut.bt_a_operand_i := 0.U; dut.bt_b_operand_i := 0.U
    dut.multdiv_operator_i := operation
    dut.mult_en_i := enable && !operation(1); dut.div_en_i := enable && operation(1)
    dut.mult_sel_i := !operation(1); dut.div_sel_i := operation(1)
    dut.multdiv_signed_mode_i := signedMode
    dut.multdiv_operand_a_i := a; dut.multdiv_operand_b_i := b
    dut.multdiv_ready_id_i := ready; dut.data_ind_timing_i := constantTime
    withClockAndReset(tick.asClock, (!reset_n).asAsyncReset) {
      val word0 = RegInit(0.U(34.W)); val word1 = RegInit(0.U(34.W))
      when(dut.imd_val_we_o(0)) { word0 := dut.imd_val_d_o(67,34) }
      when(dut.imd_val_we_o(1)) { word1 := dut.imd_val_d_o(33,0) }
      dut.imd_val_q_i := Cat(word0,word1)
    }
    result := dut.result_ex_o ^ (if (corrupt) 1.U else 0.U)
    valid := dut.ex_valid_o
  } else {
    val dut = Module(new IbexMultdivFast(iterativeMultiply = iterative))
    dut.clk_i := tick.asClock
    dut.rst_ni := reset_n
    dut.mult_en_i := enable && !operation(1)
    dut.div_en_i := enable && operation(1)
    dut.mult_sel_i := !operation(1)
    dut.div_sel_i := operation(1)
    dut.operator_i := operation
    dut.signed_mode_i := signedMode
    dut.op_a_i := a
    dut.op_b_i := b
    dut.data_ind_timing_i := constantTime
    dut.multdiv_ready_id_i := ready
    // Environment supplies the ALU and two intermediate registers, as the
    // execution/ID stages do. The checker below uses only integer arithmetic.
    val sum = dut.alu_operand_a_o +& dut.alu_operand_b_o
    dut.alu_adder_ext_i := sum
    dut.alu_adder_i := sum(32, 1)
    dut.equal_to_zero_i := sum(32, 1) === 0.U
    withClockAndReset(tick.asClock, (!reset_n).asAsyncReset) {
      val word0 = RegInit(0.U(34.W))
      val word1 = RegInit(0.U(34.W))
      when(dut.imd_val_we_o(0)) { word0 := dut.imd_val_d_o(67, 34) }
      when(dut.imd_val_we_o(1)) { word1 := dut.imd_val_d_o(33, 0) }
      dut.imd_val_q_i := Cat(word0, word1)
    }
    result := dut.multdiv_result_o ^ (if (corrupt) 1.U else 0.U)
    valid := dut.valid_o
  }
}

class MultdivSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t11/simulation").toAbsolutePath
  }
  private def check(dut: MultdivHarness): Unit = {
    val modulus = BigInt(1) << 32
    val mask = modulus - 1
    def interpret(value: BigInt, signed: Boolean): BigInt =
      if (signed && value.testBit(31)) value - modulus else value
    def edge(): Unit = {
      dut.tick.poke(true.B)
      dut.valid.peek()
      dut.tick.poke(false.B)
    }
    dut.tick.poke(false.B)
    dut.reset_n.poke(true.B)
    dut.enable.poke(false.B)
    dut.ready.poke(false.B)
    dut.operation.poke(0.U)
    dut.signedMode.poke(0.U)
    dut.a.poke(0.U)
    dut.b.poke(0.U)
    dut.constantTime.poke(false.B)
    dut.valid.peek()
    dut.reset_n.poke(false.B)
    dut.valid.peek()
    dut.reset_n.poke(true.B)
    val edges = Seq(BigInt(0), BigInt(1), BigInt(2), mask, modulus / 2, modulus / 2 - 1)
    val random = new scala.util.Random(0x11dL)
    val vectors = (for (a <- edges; b <- edges) yield (a, b)) ++
      (0 until 96).map(_ => (BigInt(32, random), BigInt(32, random)))
    for ((a, b) <- vectors; operation <- 0 until 4;
         mode <- (if (operation < 2) Seq(0, 1, 2, 3) else Seq(0, 3));
         constant <- (if (operation < 2) Seq(false) else Seq(false, true))) {
      val x = interpret(a, (mode & 1) != 0)
      val y = interpret(b, (mode & 2) != 0)
      val expected = (operation match {
        case 0 => x * y
        case 1 => (x * y) >> 32
        case 2 => if (y == 0) mask else x / y
        case 3 => if (y == 0) a else x % y
      }) & mask
      dut.a.poke(a.U)
      dut.b.poke(b.U)
      dut.operation.poke(operation.U)
      dut.signedMode.poke(mode.U)
      dut.constantTime.poke(constant.B)
      dut.ready.poke(false.B)
      dut.enable.poke(true.B)
      var cycles = 0
      while (dut.valid.peek().litValue == 0 && cycles < 160) {
        dut.enable.poke((cycles % 5 != 3).B)
        edge()
        cycles += 1
      }
      assert(dut.valid.peek().litValue == 1, "MULTDIV_COMPLETION_TIMEOUT")
      dut.enable.poke(true.B)
      for (_ <- 0 until 3) {
        assert(dut.result.peek().litValue == expected,
          s"MULTDIV_MODEL_MISMATCH op=$operation mode=$mode a=$a b=$b")
        edge() // Backpressure must retain completion and result.
        assert(dut.valid.peek().litValue == 1)
      }
      dut.ready.poke(true.B)
      edge()
      dut.enable.poke(false.B)
    }
  }
  test("multiply/divide integer model, signs, zero, overflow, enable stalls and backpressure") {
    simulateRaw(new MultdivHarness, subdirectory = Some("multdiv_model"))(check)
  }
  test("iterative multiply and unchanged divide obey the integer model and shared interface") {
    simulateRaw(new MultdivHarness(iterative = true), subdirectory = Some("multdiv_iterative_model"))(check)
  }
  test("execution stage multiply/divide integer model with Chisel ALU feedback") {
    simulateRaw(new MultdivHarness(execution = true), subdirectory = Some("ex_multdiv_model"))(check)
  }
  test("execution stage checker rejects corrupt results") {
    val failure = intercept[TestFailedException] {
      simulateRaw(new MultdivHarness(corrupt = true, execution = true), subdirectory = Some("ex_multdiv_fault"))(check)
    }
    assert(failure.getMessage.contains("MULTDIV_MODEL_MISMATCH"))
  }
  test("multiply/divide checker rejects corrupt results") {
    val failure = intercept[TestFailedException] {
      simulateRaw(new MultdivHarness(true), subdirectory = Some("multdiv_fault"))(check)
    }
    assert(failure.getMessage.contains("MULTDIV_MODEL_MISMATCH"))
  }
}
