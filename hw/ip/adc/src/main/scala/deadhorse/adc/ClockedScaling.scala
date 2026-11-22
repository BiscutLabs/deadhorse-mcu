// SPDX-License-Identifier: Apache-2.0
package deadhorse.adc
import chisel3._
import chisel3.util._

object ClockedScaling {
  // One radix-2 step in mixed quotient/remainder form. Bounds permit at most
  // two subtractions. All divisions here are Scala elaboration-time constants.
  def step(q: UInt, r: UInt, bit: Bool, numerator: Int, denominator: Int): (UInt, UInt) = {
    val total = (r << 1) +& Mux(bit, (numerator % denominator).U, 0.U)
    val carry = Mux(total >= (2L * denominator).U, 2.U, Mux(total >= denominator.U, 1.U, 0.U))
    val remainder = Mux(carry === 2.U, total - (2L * denominator).U,
      Mux(carry === 1.U, total - denominator.U, total))
    (((q << 1) + Mux(bit, (numerator / denominator).U, 0.U) + carry)(q.getWidth-1,0), remainder)
  }
}

/** Exact constant rational scaling without a combinational multiply/divide. */
class ClockedSampleScaler(numerator: Int, denominator: Int) extends Module {
  protected def resultValue(value: UInt): UInt=value
  val io = IO(new Bundle {
    val start = Input(Bool()); val raw = Input(UInt(12.W))
    val busy = Output(Bool()); val done = Output(Bool()); val value = Output(UInt(32.W))
  })
  val active = RegInit(false.B); val raw = Reg(UInt(12.W)); val left = Reg(UInt(4.W))
  val quotient = Reg(UInt(32.W)); val remainder = Reg(UInt(log2Ceil(denominator).max(1).W))
  val (q,r) = ClockedScaling.step(quotient, remainder, raw(11), numerator, denominator)
  io.busy := active; io.done := active && left === 0.U; io.value := resultValue(q)
  when(io.start && !active) { active := true.B; raw := io.raw; left := 11.U; quotient := 0.U; remainder := 0.U }
  when(active) {
    raw := raw << 1; left := left - 1.U; quotient := q; remainder := r
    when(left === 0.U) { active := false.B }
  }
}
