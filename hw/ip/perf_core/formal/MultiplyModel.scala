// Verification-only mathematical transaction machine, not production RTL.
package deadhorse.perf_core

import chisel3._
import chisel3.util.Cat
import circt.stage.ChiselStage

class MultiplyModel extends RawModule {
  override def desiredName = "IterativeMultiply"
  val clk_i = IO(Input(Clock()))
  val rst_ni = IO(Input(Bool()))
  val enable_i = IO(Input(Bool()))
  val ready_i = IO(Input(Bool()))
  val a_i = IO(Input(UInt(32.W)))
  val b_i = IO(Input(UInt(32.W)))
  val signed_mode_i = IO(Input(UInt(2.W)))
  val high_i = IO(Input(Bool()))
  val result_o = IO(Output(UInt(32.W)))
  val valid_o = IO(Output(Bool()))
  withClockAndReset(clk_i, (!rst_ni).asAsyncReset) {
    val state_q = RegInit(0.U(3.W))
    val count_q = RegInit(0.U(5.W))
    val a_q = RegInit(0.U(32.W))
    val b_q = RegInit(0.U(32.W))
    val hi_q = RegInit(0.U(32.W))
    val lo_q = RegInit(0.U(32.W))
    val sign_q = RegInit(0.U(2.W))
    val high_q = RegInit(false.B)
    val result_q = RegInit(0.U(32.W))
    // Mathematical recurrence over the entire unsigned accumulator. Unlike
    // the DUT this has no shared correction adder or explicit carry network.
    val c = Cat(hi_q, lo_q)
    val step = (c.pad(65) + Mux(c(0), a_q.pad(65) << 32, 0.U))(64,1)
    val correctedA = c - Mux(sign_q(0), Cat(b_q, 0.U(32.W)), 0.U)
    val correctedB = c - Mux(sign_q(1), Cat(a_q, 0.U(32.W)), 0.U)
    when(enable_i && state_q === 0.U) {
      a_q := a_i; b_q := b_i; hi_q := 0.U; lo_q := b_i
      sign_q := signed_mode_i & Cat(b_i(31), a_i(31))
      high_q := high_i; count_q := 0.U; state_q := 1.U
    }
    when(enable_i && state_q === 1.U) {
      hi_q := step(63,32); lo_q := step(31,0)
      count_q := count_q + 1.U
      state_q := Mux(count_q === 31.U, 2.U, 1.U)
    }
    when(enable_i && state_q === 2.U) { hi_q := correctedA(63,32); state_q := 3.U }
    when(enable_i && state_q === 3.U) {
      hi_q := correctedB(63,32)
      result_q := Mux(high_q, correctedB(63,32), c(31,0))
      state_q := 4.U
    }
    when(enable_i && ready_i && state_q === 4.U) { state_q := 0.U }
    valid_o := state_q === 4.U
    result_o := result_q
  }
}

object EmitMultiplyModel {
  def main(args: Array[String]): Unit = {
    require(args.length == 1 && args(0).startsWith("build/"))
    ChiselStage.emitSystemVerilogFile(new MultiplyModel,
      Array("--target-dir", args(0)), Array("--disable-all-randomization", "-strip-debug-info", "--preserve-values=named"))
  }
}
