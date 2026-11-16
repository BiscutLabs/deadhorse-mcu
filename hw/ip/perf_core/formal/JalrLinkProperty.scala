package deadhorse.perf_core.formal

import chisel3._
import circt.stage.ChiselStage

/** RV32 JALR link value, independent of the core's reported trap and rs1.
  * The proof runner qualifies this predicate against the pinned ISA checker.
  */
class JalrLinkProperty extends RawModule {
  val reset = IO(Input(Bool()))
  val valid = IO(Input(Bool()))
  val instruction = IO(Input(UInt(32.W)))
  val retiredPc = IO(Input(UInt(32.W)))
  val reportedValue = IO(Input(UInt(32.W)))
  val active = IO(Output(Bool()))
  val holds = IO(Output(Bool()))
  val coverZero = IO(Output(Bool()))
  val coverLink = IO(Output(Bool()))
  val expected = Mux(instruction(11, 7) === 0.U, 0.U(32.W), retiredPc + 4.U(32.W))
  active := !reset && valid && instruction(6, 0) === "h67".U && instruction(14, 12) === 0.U
  holds := !active || reportedValue === expected
  coverZero := active && instruction(11, 7) === 0.U
  coverLink := active && instruction(11, 7) =/= 0.U
}

object EmitJalrLinkProperty {
  def main(args: Array[String]): Unit = {
    ChiselStage.emitSystemVerilogFile(new JalrLinkProperty,
      Array("--target-dir", args(0)), Array("--disable-all-randomization"))
  }
}
