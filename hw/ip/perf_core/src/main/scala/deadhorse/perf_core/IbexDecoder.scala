// Copyright lowRISC contributors.
// Copyright 2018 ETH Zurich and University of Bologna; see upstream CREDITS.md.
// Licensed under Apache-2.0; SPDX-License-Identifier: Apache-2.0
// Translation of rtl/ibex_decoder.sv, Ibex
// 38c070939183cc10940b66c8e9e04eeca6b65470, pinned RV32IMC/no-B/no-BTALU.
package deadhorse.perf_core

import chisel3._
import chisel3.util.{Cat, Fill, is, switch}

/** Faithful combinational decoder boundary, including illegal encodings and
  * independently driven replicated instruction inputs. No new pipeline state.
  */
class IbexDecoder(val RV32E: Boolean = false, val RV32M: Int = 2,
    val RV32B: Int = 0, val BranchTargetALU: Boolean = false) extends RawModule {
  require(!RV32E && RV32M == 2 && RV32B == 0 && !BranchTargetALU,
    "T11 implements the pinned RV32IMC/no-B/no-BTALU decoder")
  override def desiredName = "ibex_decoder"
  val clk_i = IO(Input(Clock())); val rst_ni = IO(Input(Bool()))
  val instr_first_cycle_i = IO(Input(Bool()))
  val instr_rdata_i = IO(Input(UInt(32.W)))
  val instr_rdata_alu_i = IO(Input(UInt(32.W)))
  val illegal_c_insn_i = IO(Input(Bool())); val branch_taken_i = IO(Input(Bool()))
  val illegal_insn_o = IO(Output(Bool())); val ebrk_insn_o = IO(Output(Bool()))
  val mret_insn_o = IO(Output(Bool())); val dret_insn_o = IO(Output(Bool()))
  val ecall_insn_o = IO(Output(Bool())); val wfi_insn_o = IO(Output(Bool()))
  val jump_set_o = IO(Output(Bool())); val icache_inval_o = IO(Output(Bool()))
  val imm_a_mux_sel_o = IO(Output(UInt(1.W))); val imm_b_mux_sel_o = IO(Output(UInt(3.W)))
  val bt_a_mux_sel_o = IO(Output(UInt(2.W))); val bt_b_mux_sel_o = IO(Output(UInt(3.W)))
  val imm_i_type_o = IO(Output(UInt(32.W))); val imm_s_type_o = IO(Output(UInt(32.W)))
  val imm_b_type_o = IO(Output(UInt(32.W))); val imm_u_type_o = IO(Output(UInt(32.W)))
  val imm_j_type_o = IO(Output(UInt(32.W))); val zimm_rs1_type_o = IO(Output(UInt(32.W)))
  val rf_wdata_sel_o = IO(Output(UInt(1.W))); val rf_we_o = IO(Output(Bool()))
  val rf_raddr_a_o = IO(Output(UInt(5.W))); val rf_raddr_b_o = IO(Output(UInt(5.W)))
  val rf_waddr_o = IO(Output(UInt(5.W)))
  val rf_ren_a_o = IO(Output(Bool())); val rf_ren_b_o = IO(Output(Bool()))
  val alu_operator_o = IO(Output(UInt(7.W)))
  val alu_op_a_mux_sel_o = IO(Output(UInt(2.W))); val alu_op_b_mux_sel_o = IO(Output(UInt(1.W)))
  val alu_multicycle_o = IO(Output(Bool()))
  val mult_en_o = IO(Output(Bool())); val div_en_o = IO(Output(Bool()))
  val mult_sel_o = IO(Output(Bool())); val div_sel_o = IO(Output(Bool()))
  val multdiv_operator_o = IO(Output(UInt(2.W)))
  val multdiv_signed_mode_o = IO(Output(UInt(2.W)))
  val csr_access_o = IO(Output(Bool())); val csr_op_o = IO(Output(UInt(2.W)))
  val data_req_o = IO(Output(Bool())); val data_we_o = IO(Output(Bool()))
  val data_type_o = IO(Output(UInt(2.W))); val data_sign_extension_o = IO(Output(Bool()))
  val jump_in_dec_o = IO(Output(Bool())); val branch_in_dec_o = IO(Output(Bool()))

  private val instr = instr_rdata_i
  private val instr_alu = instr_rdata_alu_i
  private val rs1 = instr(19,15)
  private val funct3 = instr(14,12)
  private val af3 = instr_alu(14,12)
  private val illegal = WireDefault(false.B)
  private val rfWrite = WireDefault(false.B)
  private val dataRequest = WireDefault(false.B)
  private val dataWrite = WireDefault(false.B)
  private val jump = WireDefault(false.B)
  private val jumpSet = WireDefault(false.B)
  private val branch = WireDefault(false.B)
  private val csrAccess = WireDefault(false.B)
  private val csrOp = WireDefault(0.U(2.W))
  private def oneOf(x: UInt, values: Int*): Bool = values.map(v => x === v.U).reduce(_ || _)
  private val load = 0x03.U(7.W); private val store = 0x23.U(7.W)
  private val lui = 0x37.U(7.W); private val auipc = 0x17.U(7.W)
  private val opimm = 0x13.U(7.W); private val op = 0x33.U(7.W)
  private val jal = 0x6f.U(7.W); private val jalr = 0x67.U(7.W)
  private val br = 0x63.U(7.W); private val system = 0x73.U(7.W)
  private val fence = 0x0f.U(7.W)
  // Upstream selector enum values, retained at the module boundary.
  private val regA = 0.U(2.W); private val pc = 2.U(2.W); private val immA = 3.U(2.W)
  private val regB = 0.U(1.W); private val immB = 1.U(1.W)
  private val immI = 0.U(3.W); private val immS = 1.U(3.W); private val immBranch = 2.U(3.W)
  private val immU = 3.U(3.W); private val immJ = 4.U(3.W); private val incrPC = 5.U(3.W)

  imm_i_type_o := Cat(Fill(20,instr(31)),instr(31,20))
  imm_s_type_o := Cat(Fill(20,instr(31)),instr(31,25),instr(11,7))
  imm_b_type_o := Cat(Fill(19,instr(31)),instr(31),instr(7),instr(30,25),instr(11,8),false.B)
  imm_u_type_o := Cat(instr(31,12),0.U(12.W))
  imm_j_type_o := Cat(Fill(12,instr(31)),instr(19,12),instr(20),instr(30,21),false.B)
  zimm_rs1_type_o := rs1
  rf_raddr_a_o := rs1; rf_raddr_b_o := instr(24,20); rf_waddr_o := instr(11,7)
  rf_wdata_sel_o := 0.U; rf_ren_a_o := false.B; rf_ren_b_o := false.B
  multdiv_operator_o := 0.U; multdiv_signed_mode_o := 0.U
  data_type_o := 0.U; data_sign_extension_o := false.B
  ebrk_insn_o := false.B; ecall_insn_o := false.B; mret_insn_o := false.B
  dret_insn_o := false.B; wfi_insn_o := false.B; icache_inval_o := false.B
  val knownOpcode = oneOf(instr(6,0),0x03,0x23,0x37,0x17,0x13,0x33,0x6f,0x67,0x63,0x73,0x0f)
  illegal := !knownOpcode
  switch(instr(6,0)) {
    is(jal,jalr) {
      jump := true.B; jumpSet := instr_first_cycle_i; rfWrite := !instr_first_cycle_i
      when(instr(6,0) === jalr) { rf_ren_a_o := true.B; illegal := funct3 =/= 0.U }
    }
    is(br) { branch := true.B; rf_ren_a_o := true.B; rf_ren_b_o := true.B; illegal := oneOf(funct3,2,3) }
    is(store) {
      rf_ren_a_o := true.B; rf_ren_b_o := true.B; dataRequest := true.B; dataWrite := true.B
      illegal := instr(14) || instr(13,12) === 3.U
      when(instr(13,12) === 0.U) { data_type_o := 2.U }
      when(instr(13,12) === 1.U) { data_type_o := 1.U }
    }
    is(load) {
      rf_ren_a_o := true.B; dataRequest := true.B; data_sign_extension_o := !instr(14)
      illegal := instr(13,12) === 3.U || (instr(13,12) === 2.U && instr(14))
      when(instr(13,12) === 0.U) { data_type_o := 2.U }
      when(instr(13,12) === 1.U) { data_type_o := 1.U }
    }
    is(lui,auipc) { rfWrite := true.B }
    is(opimm) {
      rf_ren_a_o := true.B; rfWrite := true.B
      when(funct3 === 1.U) { illegal := instr(31,25) =/= 0.U }
      when(funct3 === 5.U) { illegal := !oneOf(instr(31,25),0,0x20) }
    }
    is(op) {
      rf_ren_a_o := true.B; rf_ren_b_o := true.B; rfWrite := true.B
      illegal := !(instr(31,25) === 0.U || instr(31,25) === 1.U ||
        (instr(31,25) === 0x20.U && oneOf(funct3,0,5)))
      when(instr(31,25) === 1.U) {
        multdiv_operator_o := Mux(funct3 === 0.U,0.U,Mux(!funct3(2),1.U,Mux(funct3(1),3.U,2.U)))
        multdiv_signed_mode_o := Mux(oneOf(funct3,1,4,6),3.U,Mux(funct3 === 2.U,1.U,0.U))
      }
    }
    is(fence) {
      illegal := !oneOf(funct3,0,1)
      when(funct3 === 1.U) { jump := true.B; jumpSet := instr_first_cycle_i; icache_inval_o := instr_first_cycle_i }
    }
    is(system) {
      when(funct3 === 0.U) {
        ecall_insn_o := instr(31,20) === 0.U; ebrk_insn_o := instr(31,20) === 1.U
        mret_insn_o := instr(31,20) === 0x302.U; dret_insn_o := instr(31,20) === 0x7b2.U
        wfi_insn_o := instr(31,20) === 0x105.U
        illegal := !oneOf(instr(31,20),0,1,0x302,0x7b2,0x105) || rs1 =/= 0.U || instr(11,7) =/= 0.U
      }.otherwise {
        csrAccess := true.B; rf_wdata_sel_o := 1.U; rfWrite := true.B; rf_ren_a_o := !instr(14)
        csrOp := instr(13,12); illegal := instr(13,12) === 0.U
      }
    }
  }
  val fault = illegal || illegal_c_insn_i
  illegal_insn_o := fault; rf_we_o := rfWrite && !fault
  data_req_o := dataRequest && !fault; data_we_o := dataWrite && !fault
  jump_in_dec_o := jump && !fault; jump_set_o := jumpSet && !fault
  branch_in_dec_o := branch && !fault; csr_access_o := csrAccess && !fault
  csr_op_o := Mux(csrOp(1) && rs1 === 0.U,0.U,csrOp)

  // The replicated instruction input is intentionally independent. Do not use
  // main-instruction legality to simplify these observable static selectors.
  alu_operator_o := IbexAluOp("SLTU")
  alu_op_a_mux_sel_o := immA; alu_op_b_mux_sel_o := immB
  imm_a_mux_sel_o := 1.U; imm_b_mux_sel_o := immI
  bt_a_mux_sel_o := pc; bt_b_mux_sel_o := immI
  alu_multicycle_o := false.B; mult_sel_o := false.B; div_sel_o := false.B
  switch(instr_alu(6,0)) {
    is(jal) {
      alu_op_a_mux_sel_o := pc; alu_operator_o := IbexAluOp("ADD")
      imm_b_mux_sel_o := Mux(instr_first_cycle_i,immJ,incrPC)
    }
    is(jalr) {
      alu_op_a_mux_sel_o := Mux(instr_first_cycle_i,regA,pc)
      imm_b_mux_sel_o := Mux(instr_first_cycle_i,immI,incrPC); alu_operator_o := IbexAluOp("ADD")
    }
    is(br) {
      for((f,n) <- Seq(0->"EQ",1->"NE",4->"LT",5->"GE",6->"LTU",7->"GEU")) {
        when(af3 === f.U) { alu_operator_o := IbexAluOp(n) }
      }
      alu_op_a_mux_sel_o := Mux(instr_first_cycle_i,regA,pc)
      alu_op_b_mux_sel_o := Mux(instr_first_cycle_i,regB,immB)
      when(!instr_first_cycle_i) { imm_b_mux_sel_o := Mux(branch_taken_i,immBranch,incrPC); alu_operator_o := IbexAluOp("ADD") }
    }
    is(store) {
      alu_op_a_mux_sel_o := regA; alu_op_b_mux_sel_o := regB; alu_operator_o := IbexAluOp("ADD")
      when(!instr_alu(14)) { imm_b_mux_sel_o := immS; alu_op_b_mux_sel_o := immB }
    }
    is(load) { alu_op_a_mux_sel_o := regA; alu_operator_o := IbexAluOp("ADD") }
    is(lui,auipc) {
      alu_op_a_mux_sel_o := Mux(instr_alu(6,0) === lui,immA,pc)
      imm_b_mux_sel_o := immU; alu_operator_o := IbexAluOp("ADD")
    }
    is(opimm) {
      alu_op_a_mux_sel_o := regA
      for((f,n) <- Seq(0->"ADD",1->"SLL",2->"SLT",3->"SLTU",4->"XOR",6->"OR",7->"AND")) {
        when(af3 === f.U) { alu_operator_o := IbexAluOp(n) }
      }
      when(af3 === 5.U) {
        when(instr_alu(31,27) === 0.U) { alu_operator_o := IbexAluOp("SRL") }
        when(instr_alu(31,27) === 8.U) { alu_operator_o := IbexAluOp("SRA") }
      }
    }
    is(op) {
      alu_op_a_mux_sel_o := regA; alu_op_b_mux_sel_o := regB
      when(instr_alu(31,25) === 0.U) {
        for((f,n) <- Seq(0->"ADD",1->"SLL",2->"SLT",3->"SLTU",4->"XOR",5->"SRL",6->"OR",7->"AND")) {
          when(af3 === f.U) { alu_operator_o := IbexAluOp(n) }
        }
      }
      when(instr_alu(31,25) === 0x20.U) {
        when(af3 === 0.U) { alu_operator_o := IbexAluOp("SUB") }
        when(af3 === 5.U) { alu_operator_o := IbexAluOp("SRA") }
      }
      when(instr_alu(31,25) === 1.U) {
        alu_operator_o := IbexAluOp("ADD"); mult_sel_o := !af3(2); div_sel_o := af3(2)
      }
    }
    is(fence) {
      when(af3 === 0.U) { alu_operator_o := IbexAluOp("ADD"); alu_op_a_mux_sel_o := regA }
      when(af3 === 1.U) { alu_operator_o := IbexAluOp("ADD"); alu_op_a_mux_sel_o := pc; imm_b_mux_sel_o := incrPC }
    }
    is(system) {
      alu_op_a_mux_sel_o := regA
      when(af3 =/= 0.U) { imm_a_mux_sel_o := 0.U; alu_op_a_mux_sel_o := Mux(instr_alu(14),immA,regA) }
    }
  }
  mult_en_o := mult_sel_o && !fault; div_en_o := div_sel_o && !fault
}
