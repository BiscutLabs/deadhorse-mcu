package deadhorse.perf_core.formal

import chisel3._
import circt.stage.ChiselStage

/** RV32 JALR target: x0 normalization, signed immediate, wrapping add, bit0 clear.
  * Activation/violation are qualified against the pinned ISA checker.
  */
class JalrTargetProperty extends RawModule {
  val reset = IO(Input(Bool()))
  val valid = IO(Input(Bool()))
  val instruction = IO(Input(UInt(32.W)))
  val sourceValue = IO(Input(UInt(32.W)))
  val reportedPc = IO(Input(UInt(32.W)))
  val active = IO(Output(Bool()))
  val holds = IO(Output(Bool()))
  val coverZero = IO(Output(Bool()))
  val coverOdd = IO(Output(Bool()))
  val coverNegative = IO(Output(Bool()))
  val faultActive = IO(Output(Bool()))
  val zeroSource = instruction(19, 15) === 0.U
  val base = Mux(zeroSource, 0.U(32.W), sourceValue)
  val offset = instruction(31, 20).asSInt.pad(32).asUInt
  val sum = base + offset
  val expected = sum & "hfffffffe".U(32.W)
  active := !reset && valid && instruction(6, 0) === "h67".U && instruction(14, 12) === 0.U
  holds := !active || reportedPc === expected
  coverZero := active && zeroSource
  coverOdd := active && !zeroSource && sum(0)
  coverNegative := active && instruction(31)
  faultActive := active && !zeroSource
}

object EmitJalrTargetProperty {
  def main(args: Array[String]): Unit = {
    ChiselStage.emitSystemVerilogFile(new JalrTargetProperty,
      Array("--target-dir", args(0)), Array("--disable-all-randomization"))
  }
}
