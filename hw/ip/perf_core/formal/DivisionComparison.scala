// Verification-only selected-operation boundary; reference RTL never enters production.
package deadhorse.perf_core

import chisel3._
import chisel3.util.Cat
import circt.stage.ChiselStage

class MultdivComparisonTarget extends BlackBox {
  override def desiredName = "ibex_multdiv_fast"
  val io = IO(new Bundle {
    val clk_i = Input(Clock()); val rst_ni = Input(Bool())
    val mult_en_i = Input(Bool()); val div_en_i = Input(Bool())
    val mult_sel_i = Input(Bool()); val div_sel_i = Input(Bool())
    val operator_i = Input(UInt(2.W)); val signed_mode_i = Input(UInt(2.W))
    val op_a_i = Input(UInt(32.W)); val op_b_i = Input(UInt(32.W))
    val alu_adder_ext_i = Input(UInt(34.W)); val alu_adder_i = Input(UInt(32.W))
    val equal_to_zero_i = Input(Bool()); val data_ind_timing_i = Input(Bool())
    val alu_operand_a_o = Output(UInt(33.W)); val alu_operand_b_o = Output(UInt(33.W))
    val imd_val_q_i = Input(UInt(68.W)); val imd_val_d_o = Output(UInt(68.W))
    val imd_val_we_o = Output(UInt(2.W)); val multdiv_ready_id_i = Input(Bool())
    val multdiv_result_o = Output(UInt(32.W)); val valid_o = Output(Bool())
  })
}

class DivisionComparison extends RawModule {
  val clk_i = IO(Input(Clock())); val rst_ni = IO(Input(Bool()))
  val enable_i = IO(Input(Bool())); val remainder_i = IO(Input(Bool()))
  val signed_mode_i = IO(Input(UInt(2.W)))
  val op_a_i = IO(Input(UInt(32.W))); val op_b_i = IO(Input(UInt(32.W)))
  val alu_adder_ext_i = IO(Input(UInt(34.W))); val alu_adder_i = IO(Input(UInt(32.W)))
  val equal_to_zero_i = IO(Input(Bool())); val data_ind_timing_i = IO(Input(Bool()))
  val imd_val_q_i = IO(Input(UInt(68.W))); val ready_i = IO(Input(Bool()))
  val alu_operand_a_o = IO(Output(UInt(33.W))); val alu_operand_b_o = IO(Output(UInt(33.W)))
  val imd_val_d_o = IO(Output(UInt(68.W))); val imd_val_we_o = IO(Output(UInt(2.W)))
  val result_o = IO(Output(UInt(32.W))); val valid_o = IO(Output(Bool()))
  val target = Module(new MultdivComparisonTarget)
  target.io.clk_i := clk_i; target.io.rst_ni := rst_ni
  target.io.mult_en_i := false.B; target.io.mult_sel_i := false.B
  target.io.div_en_i := enable_i; target.io.div_sel_i := true.B
  target.io.operator_i := Cat(true.B,remainder_i)
  target.io.signed_mode_i := signed_mode_i
  target.io.op_a_i := op_a_i; target.io.op_b_i := op_b_i
  target.io.alu_adder_ext_i := alu_adder_ext_i; target.io.alu_adder_i := alu_adder_i
  target.io.equal_to_zero_i := equal_to_zero_i; target.io.data_ind_timing_i := data_ind_timing_i
  target.io.imd_val_q_i := imd_val_q_i; target.io.multdiv_ready_id_i := ready_i
  alu_operand_a_o := target.io.alu_operand_a_o; alu_operand_b_o := target.io.alu_operand_b_o
  imd_val_d_o := target.io.imd_val_d_o; imd_val_we_o := target.io.imd_val_we_o
  result_o := target.io.multdiv_result_o; valid_o := target.io.valid_o
}

object EmitDivisionComparison {
  def main(args: Array[String]): Unit = {
    require(args.length==1 && args(0).startsWith("build/"))
    ChiselStage.emitSystemVerilogFile(new DivisionComparison,
      Array("--target-dir",args(0)),Array("--disable-all-randomization","-strip-debug-info","--preserve-values=named"))
  }
}
