// Copyright 2026 Deadhorse contributors.
// Licensed under the Apache License, Version 2.0; SPDX-License-Identifier: Apache-2.0
package deadhorse.perf_core

import chisel3._
import chisel3.util.{Cat, Decoupled, is, switch}

class ExecuteRequest extends Bundle {
  val kind = UInt(2.W) // ALU, MUL, DIV, REM
  val a = UInt(32.W)
  val b = UInt(32.W)
  val aluOp = UInt(7.W)
  val signedMode = UInt(2.W)
  val high = Bool()
  val firstCycle = Bool()
  val constantTime = Bool()
}

class ExecuteResponse extends Bundle {
  val result = UInt(32.W)
  val adder = UInt(32.W)
  val comparison = Bool()
}

/** Single outstanding, registered execution; see EXECUTION-TIMING.md. */
class ClockedExecute extends RawModule {
  val clk_i = IO(Input(Clock()))
  val rst_ni = IO(Input(Bool()))
  val req = IO(Flipped(Decoupled(new ExecuteRequest)))
  val rsp = IO(Decoupled(new ExecuteResponse))
  val busy_o = IO(Output(Bool()))
  protected val idle = 0.U(3.W)
  protected val aluCompute = 1.U(3.W)
  protected val mulStart = 2.U(3.W)
  protected val mulWait = 3.U(3.W)
  protected val divIssue = 4.U(3.W)
  protected val divCompute = 5.U(3.W)
  protected val divAdvance = 6.U(3.W)
  protected val response = 7.U(3.W)
  protected def captureA(value: UInt): UInt = value
  protected def publish(value: UInt): UInt = value
  protected def keepResponse: Bool = !rsp.ready
  protected def resetState: UInt = 0.U(3.W)
  protected def initialState(kind: UInt): UInt = Mux(kind === 0.U, aluCompute,
    Mux(kind === 1.U,mulStart,divIssue))
  protected def sampleSum(value: UInt): UInt = value

  protected val state_q = withClockAndReset(clk_i, (!rst_ni).asAsyncReset) { RegInit(resetState) }
  protected val request_q = withClockAndReset(clk_i, (!rst_ni).asAsyncReset) { RegInit(0.U.asTypeOf(new ExecuteRequest)) }
  protected val response_q = withClockAndReset(clk_i, (!rst_ni).asAsyncReset) { RegInit(0.U.asTypeOf(new ExecuteResponse)) }
  protected val md_a_q = withClockAndReset(clk_i, (!rst_ni).asAsyncReset) { RegInit(0.U(33.W)) }
  protected val md_b_q = withClockAndReset(clk_i, (!rst_ni).asAsyncReset) { RegInit(0.U(33.W)) }
  protected val md_sum_q = withClockAndReset(clk_i, (!rst_ni).asAsyncReset) { RegInit(0.U(34.W)) }
  protected val md_zero_q = withClockAndReset(clk_i, (!rst_ni).asAsyncReset) { RegInit(false.B) }
  protected val imd0_q = withClockAndReset(clk_i, (!rst_ni).asAsyncReset) { RegInit(0.U(34.W)) }
  protected val imd1_q = withClockAndReset(clk_i, (!rst_ni).asAsyncReset) { RegInit(0.U(34.W)) }

  protected val alu = Module(new IbexAlu)
  protected val divider = Module(new IbexMultdivFast)
  protected val multiplier = Module(new IterativeMultiply)
  req.ready := state_q === idle
  rsp.valid := state_q === response
  rsp.bits := response_q
  busy_o := state_q =/= idle
  alu.operator_i := request_q.aluOp
  alu.operand_a_i := request_q.a; alu.operand_b_i := request_q.b
  alu.instr_first_cycle_i := request_q.firstCycle
  alu.imd_val_q_i := 0.U
  alu.multdiv_operand_a_i := md_a_q; alu.multdiv_operand_b_i := md_b_q
  alu.multdiv_sel_i := state_q === divCompute
  divider.clk_i := clk_i; divider.rst_ni := rst_ni
  divider.mult_en_i := false.B; divider.mult_sel_i := false.B
  divider.div_en_i := state_q === divAdvance
  divider.div_sel_i := true.B
  divider.operator_i := Cat(true.B,request_q.kind(0))
  divider.signed_mode_i := request_q.signedMode
  divider.op_a_i := request_q.a; divider.op_b_i := request_q.b
  divider.alu_adder_ext_i := md_sum_q; divider.alu_adder_i := md_sum_q(32,1)
  divider.equal_to_zero_i := md_zero_q
  divider.data_ind_timing_i := request_q.constantTime
  divider.imd_val_q_i := Cat(imd0_q,imd1_q)
  divider.multdiv_ready_id_i := state_q === divAdvance
  multiplier.clk_i := clk_i; multiplier.rst_ni := rst_ni
  multiplier.enable_i := state_q === mulStart || state_q === mulWait
  multiplier.ready_i := state_q === mulWait
  multiplier.a_i := request_q.a; multiplier.b_i := request_q.b
  multiplier.signed_mode_i := request_q.signedMode
  multiplier.high_i := request_q.high

  withClockAndReset(clk_i, (!rst_ni).asAsyncReset) {
    switch(state_q) {
      is(idle) {
        when(req.valid) {
          request_q := req.bits
          request_q.a := captureA(req.bits.a)
          state_q := initialState(req.bits.kind)
        }
      }
      is(aluCompute) {
        response_q.result := publish(alu.result_o)
        response_q.adder := alu.adder_result_o
        response_q.comparison := alu.comparison_result_o
        state_q := response
      }
      is(mulStart) { state_q := mulWait }
      is(mulWait) {
        when(multiplier.valid_o) {
          response_q.result := publish(multiplier.result_o)
          response_q.adder := 0.U; response_q.comparison := false.B
          state_q := response
        }
      }
      is(divIssue) {
        md_a_q := divider.alu_operand_a_o; md_b_q := divider.alu_operand_b_o
        state_q := divCompute
      }
      is(divCompute) {
        md_sum_q := sampleSum(alu.adder_result_ext_o)
        md_zero_q := alu.is_equal_result_o
        state_q := divAdvance
      }
      is(divAdvance) {
        when(divider.imd_val_we_o(0)) { imd0_q := divider.imd_val_d_o(67,34) }
        when(divider.imd_val_we_o(1)) { imd1_q := divider.imd_val_d_o(33,0) }
        state_q := divIssue
        when(divider.valid_o) {
          response_q.result := publish(divider.multdiv_result_o)
          response_q.adder := 0.U; response_q.comparison := false.B
          state_q := response
        }
      }
      is(response) { when(!keepResponse) { state_q := idle } }
    }
  }
}
