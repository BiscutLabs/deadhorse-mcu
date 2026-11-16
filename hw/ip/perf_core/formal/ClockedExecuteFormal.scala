// Copyright 2026 Deadhorse contributors. Apache-2.0.
package deadhorse.perf_core

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

/** No operand, backpressure or reset-release assumptions beyond startup reset.
  * The divider reference advances once per architectural divider step, using
  * its own combinational arithmetic and intermediate registers.
  */
class ClockedExecuteFormal(val coversOnly: Boolean = false) extends ClockedExecute {
  override def desiredName = "ClockedExecuteFormal"
  val checking = IO(Input(Bool()))
  val reference_divider = Module(new IbexMultdivFast)
  val ref0 = withClockAndReset(clk_i, (!rst_ni).asAsyncReset) { RegInit(0.U(34.W)) }
  val ref1 = withClockAndReset(clk_i, (!rst_ni).asAsyncReset) { RegInit(0.U(34.W)) }
  val refSum = reference_divider.alu_operand_a_o +& reference_divider.alu_operand_b_o
  reference_divider.clk_i := clk_i; reference_divider.rst_ni := rst_ni
  reference_divider.mult_en_i := false.B; reference_divider.mult_sel_i := false.B
  reference_divider.div_en_i := state_q === divAdvance
  reference_divider.div_sel_i := true.B
  reference_divider.operator_i := Cat(true.B,request_q.kind(0))
  reference_divider.signed_mode_i := request_q.signedMode
  reference_divider.op_a_i := request_q.a; reference_divider.op_b_i := request_q.b
  reference_divider.alu_adder_ext_i := refSum
  reference_divider.alu_adder_i := refSum(32,1)
  // Ibex equality is equality of the low 32-bit adder result.
  reference_divider.equal_to_zero_i := refSum(32,1) === 0.U
  reference_divider.data_ind_timing_i := request_q.constantTime
  reference_divider.imd_val_q_i := Cat(ref0,ref1)
  reference_divider.multdiv_ready_id_i := state_q === divAdvance
  val age = withClockAndReset(clk_i, (!rst_ni).asAsyncReset) { RegInit(0.U(7.W)) }
  val pending = withClockAndReset(clk_i, (!rst_ni).asAsyncReset) { RegInit(false.B) }
  withClockAndReset(clk_i, (!rst_ni).asAsyncReset) {
    when(req.fire) { pending := true.B }
    when(rsp.fire) { pending := false.B }
    when(req.fire) { age := 0.U }
      .elsewhen(pending && !rsp.valid) { age := age + 1.U }
    when(state_q === divAdvance) {
      when(reference_divider.imd_val_we_o(0)) { ref0 := reference_divider.imd_val_d_o(67,34) }
      when(reference_divider.imd_val_we_o(1)) { ref1 := reference_divider.imd_val_d_o(33,0) }
    }
  }
  withClockAndReset(clk_i, false.B) {
    val released = RegNext(rst_ni)
    val priorState = RegNext(state_q)
    val priorRequest = RegNext(request_q.asUInt)
    val accepted = RegNext(req.fire)
    val offered = RegNext(req.bits.asUInt)
    val offeredKind = RegNext(req.bits.kind)
    val held = RegNext(rsp.valid && !rsp.ready)
    val priorResponse = RegNext(rsp.bits.asUInt)
    val priorAlu = RegNext(alu.result_o)
    val priorAdder = RegNext(alu.adder_result_o)
    val priorComparison = RegNext(alu.comparison_result_o)
    val priorMulValid = RegNext(multiplier.valid_o)
    val priorMulResult = RegNext(multiplier.result_o)
    val priorDivValid = RegNext(reference_divider.valid_o)
    val priorDivResult = RegNext(reference_divider.multdiv_result_o)
    val priorReady = RegNext(rsp.ready)
    if (coversOnly) {
      for(k <- 0 until 4) {
        cover(checking && rst_ni && rsp.valid && request_q.kind === k.U)
      }
      cover(checking && rst_ni && held && rsp.valid)
      cover(checking && rst_ni && rsp.valid && request_q.kind === 2.U && request_q.constantTime && request_q.b === 0.U)
      for(k <- 2 until 4) {
        cover(checking && rst_ni && rsp.valid && request_q.kind === k.U && request_q.b =/= 0.U && request_q.signedMode === 3.U && request_q.a(31))
      }
    } else {
      when(checking && !released) {
        assert(req.ready && !rsp.valid && !busy_o)
        assert(request_q.asUInt === 0.U && rsp.bits.asUInt === 0.U)
        assert(imd0_q === 0.U && imd1_q === 0.U)
      }
      when(checking && rst_ni && released) {
        assert(req.ready === !busy_o)
        assert(pending === busy_o)
        when(state_q === aluCompute) { assert(request_q.kind === 0.U && age === 0.U) }
        when(state_q === mulStart || state_q === mulWait) { assert(request_q.kind === 1.U) }
        when(state_q === divIssue || state_q === divCompute || state_q === divAdvance) { assert(request_q.kind >= 2.U) }
        assert(!(req.ready && rsp.valid))
        when(accepted) {
          assert(request_q.asUInt === offered)
          assert(state_q === Mux(offeredKind === 0.U,aluCompute,Mux(offeredKind === 1.U,mulStart,divIssue)))
        }
          .otherwise { assert(request_q.asUInt === priorRequest) }
        when(held) { assert(rsp.valid && rsp.bits.asUInt === priorResponse) }
        when(priorState === idle) {
          assert(!rsp.valid)
          when(!accepted) { assert(state_q === idle) }
        }
        when(priorState === response) { assert(Mux(priorReady, req.ready, rsp.valid)) }
        when(priorState === aluCompute) {
          assert(rsp.valid && rsp.bits.result === priorAlu)
          assert(rsp.bits.adder === priorAdder && rsp.bits.comparison === priorComparison)
        }
        when(priorState === mulStart) { assert(state_q === mulWait) }
        when(priorState === mulWait) {
          assert(rsp.valid === priorMulValid)
          when(priorMulValid) { assert(rsp.bits.result === priorMulResult && rsp.bits.adder === 0.U && !rsp.bits.comparison) }
            .otherwise { assert(state_q === mulWait) }
        }
        when(priorState === divIssue) { assert(state_q === divCompute) }
        when(priorState === divCompute) { assert(state_q === divAdvance) }
        when(priorState === divAdvance) {
          assert(rsp.valid === priorDivValid)
          when(priorDivValid) { assert(rsp.bits.result === priorDivResult && rsp.bits.adder === 0.U && !rsp.bits.comparison) }
            .otherwise { assert(state_q === divIssue) }
        }
        assert(imd0_q === ref0 && imd1_q === ref1)
        assert(divider.valid_o === reference_divider.valid_o)
        when(state_q === divCompute || state_q === divAdvance) {
          assert(md_a_q === reference_divider.alu_operand_a_o)
          assert(md_b_q === reference_divider.alu_operand_b_o)
        }
        when(state_q === divAdvance) {
          assert(md_sum_q === refSum)
          assert(md_zero_q === (refSum(32,1) === 0.U))
          assert(divider.multdiv_result_o === reference_divider.multdiv_result_o)
          assert(divider.imd_val_we_o === reference_divider.imd_val_we_o)
          assert(divider.imd_val_d_o === reference_divider.imd_val_d_o)
        }
        // A producer deadline never assumes receiver readiness.
        when(pending && !rsp.valid) {
          assert(age < Mux(request_q.kind === 0.U,1.U,
            Mux(request_q.kind === 1.U,36.U,
              Mux(request_q.b === 0.U && !request_q.constantTime,6.U,111.U))))
        }
      }
    }
  }
}
class ExecuteWrongCapture extends ClockedExecuteFormal { override protected def captureA(x: UInt) = x ^ 1.U }
class ExecuteWrongResult extends ClockedExecuteFormal { override protected def publish(x: UInt) = x ^ 1.U }
class ExecuteWrongHold extends ClockedExecuteFormal { override protected def keepResponse = false.B }
class ExecuteWrongReset extends ClockedExecuteFormal { override protected def resetState = 7.U(3.W) }
class ExecuteWrongDispatch extends ClockedExecuteFormal { override protected def initialState(k: UInt) = 0.U(3.W) }
class ExecuteWrongFeedback extends ClockedExecuteFormal { override protected def sampleSum(x: UInt) = x ^ 2.U }

object EmitClockedExecuteFormal {
  def main(args: Array[String]): Unit = {
    require(args.length == 2)
    val output = Paths.get(args(0)).toAbsolutePath.normalize
    require(output.startsWith(Paths.get("build").toAbsolutePath.normalize))
    Files.createDirectories(output)
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(args(1) match {
      case "capture" => new ExecuteWrongCapture
      case "result" => new ExecuteWrongResult
      case "hold" => new ExecuteWrongHold
      case "reset" => new ExecuteWrongReset
      case "dispatch" => new ExecuteWrongDispatch
      case "feedback" => new ExecuteWrongFeedback
      case "cover" => new ClockedExecuteFormal(true)
      case "normal" => new ClockedExecuteFormal
      case other => throw new IllegalArgumentException(other)
    }), Array("--target-dir",output.toString),
      Array("--disable-all-randomization","--verification-flavor=immediate","--lower-to-core","-strip-debug-info","--preserve-values=named"))
  }
}
