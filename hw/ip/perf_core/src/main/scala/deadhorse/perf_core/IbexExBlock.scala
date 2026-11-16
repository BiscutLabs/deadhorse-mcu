// Copyright lowRISC contributors.
// Copyright 2018 ETH Zurich and University of Bologna, see upstream CREDITS.md.
// Licensed under the Apache License, Version 2.0; SPDX-License-Identifier: Apache-2.0
// Translation of rtl/ibex_ex_block.sv at Ibex 38c070939183cc10940b66c8e9e04eeca6b65470.
package deadhorse.perf_core

import chisel3._
import chisel3.util.Cat

class IbexExBlock(val iterativeMultiply: Boolean = false,
    val localDivisionArithmetic: Boolean = false, val RegisteredExecution: Boolean = false) extends RawModule {
  override def desiredName = "ibex_ex_block"
  val clk_i = IO(Input(Clock())); val rst_ni = IO(Input(Bool()))
  val alu_operator_i = IO(Input(UInt(7.W)))
  val alu_operand_a_i = IO(Input(UInt(32.W))); val alu_operand_b_i = IO(Input(UInt(32.W)))
  val alu_instr_first_cycle_i = IO(Input(Bool()))
  val bt_a_operand_i = IO(Input(UInt(32.W))); val bt_b_operand_i = IO(Input(UInt(32.W)))
  val multdiv_operator_i = IO(Input(UInt(2.W)))
  val mult_en_i = IO(Input(Bool())); val div_en_i = IO(Input(Bool()))
  val mult_sel_i = IO(Input(Bool())); val div_sel_i = IO(Input(Bool()))
  val multdiv_signed_mode_i = IO(Input(UInt(2.W)))
  val multdiv_operand_a_i = IO(Input(UInt(32.W))); val multdiv_operand_b_i = IO(Input(UInt(32.W)))
  val multdiv_ready_id_i = IO(Input(Bool())); val data_ind_timing_i = IO(Input(Bool()))
  val imd_val_we_o = IO(Output(UInt(2.W))); val imd_val_d_o = IO(Output(UInt(68.W)))
  val imd_val_q_i = IO(Input(UInt(68.W)))
  val alu_adder_result_ex_o = IO(Output(UInt(32.W))); val result_ex_o = IO(Output(UInt(32.W)))
  val branch_target_o = IO(Output(UInt(32.W))); val branch_decision_o = IO(Output(Bool()))
  val ex_valid_o = IO(Output(Bool()))
  val execute_req_i = if(RegisteredExecution) Some(IO(Input(Bool()))) else None
  val execute_consume_i = if(RegisteredExecution) Some(IO(Input(Bool()))) else None
  val clocked_execute=if(RegisteredExecution) Some(Module(new ClockedExecute)) else None
  if(RegisteredExecution) {
    val execute=clocked_execute.get
    execute.clk_i:=clk_i; execute.rst_ni:=rst_ni
    execute.req.valid:=execute_req_i.get
    execute.req.bits.kind:=Mux(mult_sel_i,1.U,Mux(div_sel_i,Mux(multdiv_operator_i(0),3.U,2.U),0.U))
    execute.req.bits.a:=Mux(mult_sel_i || div_sel_i,multdiv_operand_a_i,alu_operand_a_i)
    execute.req.bits.b:=Mux(mult_sel_i || div_sel_i,multdiv_operand_b_i,alu_operand_b_i)
    execute.req.bits.aluOp:=alu_operator_i
    execute.req.bits.signedMode:=multdiv_signed_mode_i
    execute.req.bits.high:=multdiv_operator_i=/=0.U
    execute.req.bits.firstCycle:=alu_instr_first_cycle_i
    execute.req.bits.constantTime:=data_ind_timing_i
    execute.rsp.ready:=execute_consume_i.get
    ex_valid_o:=execute.rsp.valid; result_ex_o:=execute.rsp.bits.result
    alu_adder_result_ex_o:=execute.rsp.bits.adder; branch_target_o:=execute.rsp.bits.adder
    branch_decision_o:=execute.rsp.bits.comparison
    imd_val_we_o:=0.U; imd_val_d_o:=0.U
  } else {
  // Fixed pinned configuration: RV32MFast, RV32BNone, BranchTargetALU=false.
  val alu_i = Module(new IbexAlu(normalResultOnly = localDivisionArithmetic))
  val gen_multdiv_fast_multdiv_i = Module(new IbexMultdivFast(iterativeMultiply = iterativeMultiply,
    localDivisionArithmetic = localDivisionArithmetic))
  val md = gen_multdiv_fast_multdiv_i
  val multdiv_sel = mult_sel_i || div_sel_i
  alu_i.operator_i := alu_operator_i
  alu_i.operand_a_i := alu_operand_a_i; alu_i.operand_b_i := alu_operand_b_i
  alu_i.instr_first_cycle_i := alu_instr_first_cycle_i
  alu_i.multdiv_operand_a_i := md.alu_operand_a_o; alu_i.multdiv_operand_b_i := md.alu_operand_b_o
  alu_i.multdiv_sel_i := multdiv_sel
  alu_i.imd_val_q_i := Cat(imd_val_q_i(65,34),imd_val_q_i(31,0))
  md.clk_i := clk_i; md.rst_ni := rst_ni
  md.mult_en_i := mult_en_i; md.div_en_i := div_en_i
  md.mult_sel_i := mult_sel_i; md.div_sel_i := div_sel_i
  md.operator_i := multdiv_operator_i; md.signed_mode_i := multdiv_signed_mode_i
  md.op_a_i := multdiv_operand_a_i; md.op_b_i := multdiv_operand_b_i
  md.multdiv_ready_id_i := multdiv_ready_id_i; md.data_ind_timing_i := data_ind_timing_i
  md.alu_adder_ext_i := alu_i.adder_result_ext_o; md.alu_adder_i := alu_i.adder_result_o
  md.equal_to_zero_i := alu_i.is_equal_result_o
  md.imd_val_q_i := imd_val_q_i
  imd_val_we_o := Mux(multdiv_sel,md.imd_val_we_o,alu_i.imd_val_we_o)
  imd_val_d_o := Mux(multdiv_sel,md.imd_val_d_o,
    Cat(0.U(2.W),alu_i.imd_val_d_o(63,32),0.U(2.W),alu_i.imd_val_d_o(31,0)))
  alu_adder_result_ex_o := alu_i.adder_result_o
  result_ex_o := Mux(multdiv_sel,md.multdiv_result_o,alu_i.result_o)
  branch_target_o := alu_i.adder_result_o
  branch_decision_o := alu_i.comparison_result_o
  ex_valid_o := Mux(multdiv_sel,md.valid_o,!alu_i.imd_val_we_o.orR)
  }
}
