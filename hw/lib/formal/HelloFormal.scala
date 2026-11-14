package deadhorse.lib

import chisel3._
import chisel3.util._

/** Sampled-clock formal contract; startup reset is constrained by the runner. */
class HelloFormal(variant: String) extends RawModule {
  val clock = IO(Input(Clock()))
  val reset_n = IO(Input(Bool()))
  val in = IO(Input(UInt(8.W)))
  // Formal-driver history-valid bit: false at step zero, true thereafter.
  val checking = IO(Input(Bool()))
  val dut = Module(variant match {
    case "wrong_increment" => new HelloWrongIncrement
    case "wrong_reset" => new HelloWrongReset
    case _ => new Hello
  })
  dut.clock := clock
  dut.reset_n := reset_n
  dut.in := in

  // Verification must run during reset too; do not implicitly disable it.
  withClockAndReset(clock, false.B) {
    val priorInput = RegNext(in)
    val priorReleased = RegNext(reset_n)
    // Independent inverse relation: except at wraparound, a successor's
    // predecessor equals the previous sample. No hardware increment copied.
    val successorCorrect = Mux(priorInput === 255.U, dut.out === 0.U,
      dut.out =/= 0.U && (dut.out - 1.U) === priorInput)
    val wrapReached = checking && reset_n && priorReleased && priorInput === 255.U && dut.out === 0.U
    if (variant == "cover") {
      cover(wrapReached)
    } else if (variant == "cover_query") {
      // BTOR2 has bad states, not cover statements: SAT witnesses this target.
      assert(!wrapReached)
    } else {
      when(checking && !priorReleased) { assert(dut.out === 0.U) }
      when(checking && reset_n && priorReleased) { assert(successorCorrect) }
    }
  }
}
