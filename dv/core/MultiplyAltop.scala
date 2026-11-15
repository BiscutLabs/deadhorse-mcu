package deadhorse.reference

import chisel3._
import circt.stage.ChiselStage
import java.nio.file.{Files, Path}

/** Formal-only D44 abstraction. Never instantiated by production hardware.
  * Operations/masks are imported from the locked riscv-formal models.
  */
class MultiplyAltop(operations: Seq[(Boolean, BigInt)], captureFault: Boolean,
                    candidatePassThrough: Boolean = false) extends RawModule {
  val clk_i = IO(Input(Clock()))
  val rst_ni = IO(Input(Bool()))
  val mult_en_internal = IO(Input(Bool()))
  val sva_mul_fsm_idle = IO(Input(Bool()))
  val mult_sel_i = IO(Input(Bool()))
  val mult_valid = IO(Input(Bool()))
  val multdiv_ready_id_i = IO(Input(Bool()))
  val op_a_i = IO(Input(UInt(32.W)))
  val op_b_i = IO(Input(UInt(32.W)))
  val operator_i = IO(Input(UInt(2.W)))
  val signed_mode_i = IO(Input(UInt(2.W)))
  val result = IO(Output(UInt(32.W)))
  val real_result_i = if (candidatePassThrough) IO(Input(UInt(32.W))) else WireDefault(0.U(32.W))
  val div_sel_i = if (candidatePassThrough) IO(Input(Bool())) else WireDefault(false.B)
  override def desiredName = "DeadhorseMultiplyAltop"
  withClockAndReset(clk_i, (!rst_ni).asAsyncReset) {
    val capturedA = Reg(UInt(32.W))
    val stableA = if (captureFault) Reg(UInt(32.W)) else capturedA
    val capturedB = Reg(UInt(32.W))
    val capturedMode = Reg(UInt(2.W))
    val capturedOperator = Reg(UInt(2.W))
    val active = RegInit(false.B)
    val capture = mult_en_internal && sva_mul_fsm_idle
    when(capture) {
      capturedA := (if (captureFault) op_a_i ^ 1.U else op_a_i)
      if (captureFault) { stableA := op_a_i }
      capturedB := op_b_i
      capturedMode := signed_mode_i
      capturedOperator := operator_i
      active := true.B
    }.elsewhen(mult_valid && multdiv_ready_id_i) { active := false.B }
    // Guarantees, not assumptions: the live inputs used by Ibex's subsequent
    // partial products must remain those sampled at ALBL.
    when(active && mult_sel_i) {
      assert(op_a_i === stableA)
      assert(op_b_i === capturedB)
      assert(signed_mode_i === capturedMode)
      assert(operator_i === capturedOperator)
    }
    val selection = Mux(capturedOperator === 0.U, 0.U,
      Mux(capturedMode === 3.U, 1.U, Mux(capturedMode === 1.U, 2.U, 3.U)))
    val alternatives = operations.map { case (subtract, mask) =>
      val arithmetic = if (subtract) capturedA - capturedB else capturedA + capturedB
      arithmetic ^ mask.U(32.W)
    }
    result := Mux(div_sel_i, real_result_i, VecInit(alternatives)(selection))
  }
}

object EmitMultiplyAltop {
  def main(args: Array[String]): Unit = {
    val directory = Path.of(args(0))
    val operations = Files.readAllLines(directory.resolve("operations.tsv")).toArray.toSeq.map { line =>
      val parts = line.toString.split("\t")
      require(Set("+", "-").contains(parts(1)))
      (parts(1) == "-", BigInt(parts(2), 16))
    }
    require(operations.size == 4)
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new MultiplyAltop(operations,
      args.drop(1).contains("capture-fault"), args.drop(1).contains("candidate"))),
      Array("--target-dir", directory.toString), Array("--disable-all-randomization",
        "--verification-flavor=immediate", "--lower-to-core", "-strip-debug-info"))
  }
}
