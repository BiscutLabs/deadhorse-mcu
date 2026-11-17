package deadhorse.bus_bridge

import chisel3._

/** AON-domain four-phase direction arbitration; crossing stays in DirectionPermit. */
class DirectionArbiter extends RawModule {
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val requestAon = IO(Input(Bool())); val requestMain = IO(Input(Bool()))
  val returnedMain = IO(Input(Bool()))
  val permitAon = IO(Output(Bool())); val grantMain = IO(Output(Bool()))
  // Overridden only by an actual arbitration fault in the formal/test harness.
  protected def mayAllocate(revoking: Bool): Bool = !revoking
  protected def favorMain(nextMain: Bool): Bool = nextMain
  withClockAndReset(clk, (!reset_n).asAsyncReset) {
    val a = RegInit(false.B); val m = RegInit(false.B); val nextMain = RegInit(false.B)
    val seenMain = RegInit(false.B); val revoking = RegInit(false.B)
    when(m && returnedMain) { seenMain := true.B }
    when(a && !requestAon) { a := false.B; nextMain := true.B }
    when(m && !requestMain && seenMain) { m := false.B; nextMain := false.B; revoking := true.B; seenMain := false.B }
    when(revoking && !returnedMain) { revoking := false.B }
    when(!a && !m && mayAllocate(revoking)) {
      when(requestAon && (!requestMain || !favorMain(nextMain))) { a := true.B }
        .elsewhen(requestMain) { m := true.B }
    }
    permitAon := a; grantMain := m
  }
}
