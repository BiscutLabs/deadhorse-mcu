package deadhorse.perf_core.formal

import chisel3._
import circt.stage.ChiselStage

/** Separate saved-request alignment from local ADD response arithmetic. */
class JalrRequestProperty extends JalrCaptureProperty {
  val requestA = IO(Input(UInt(32.W)))
  val requestB = IO(Input(UInt(32.W)))
  val requestKind = IO(Input(UInt(2.W)))
  val requestOp = IO(Input(UInt(7.W)))
  val requestFirst = IO(Input(Bool()))
  val responseValid = IO(Input(Bool()))
  val alignmentHolds = IO(Output(Bool()))
  val executeActive = IO(Output(Bool()))
  val executeAddHolds = IO(Output(Bool()))
  val alignmentZero = IO(Output(Bool()))
  val alignmentNegative = IO(Output(Bool()))
  val executeCorner = IO(Output(Bool()))
  alignmentHolds := !capture || (responseValid && requestKind === 0.U &&
    requestOp === 0.U && requestFirst && requestA === normalizedSource && requestB === offset)
  executeActive := !reset && responseValid && requestKind === 0.U && requestOp === 0.U
  val sum = Wire(UInt(32.W))
  sum := requestA + requestB
  executeAddHolds := !executeActive || executeTarget === sum
  alignmentZero := capture && idInstruction(19,15) === 0.U
  alignmentNegative := capture && idInstruction(19,15) =/= 0.U && idInstruction(31)
  executeCorner := executeActive && requestA(31) && requestB(31) && sum(0)
}

object EmitJalrRequestProperty {
  def main(args: Array[String]): Unit = {
    ChiselStage.emitSystemVerilogFile(new JalrRequestProperty,
      Array("--target-dir", args(0)), Array("--disable-all-randomization"))
  }
}
