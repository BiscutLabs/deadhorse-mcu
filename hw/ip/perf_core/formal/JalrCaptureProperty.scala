package deadhorse.perf_core.formal

import chisel3._
import circt.stage.ChiselStage

/** Capture-time arithmetic and source identity, separate from target transport. */
class JalrCaptureProperty extends JalrTransportProperty {
  val sourceValue = IO(Input(UInt(32.W)))
  val rvfiSource = IO(Input(UInt(32.W)))
  val arithmeticHolds = IO(Output(Bool()))
  val sourceHolds = IO(Output(Bool()))
  val captureExpected = IO(Output(UInt(32.W)))
  val expectedSource = IO(Output(UInt(32.W)))
  val normalizedSource = Mux(idInstruction(19,15) === 0.U, 0.U(32.W), sourceValue)
  val offset = idInstruction(31,20).asSInt.pad(32).asUInt
  val rawSum = Wire(UInt(32.W))
  rawSum := normalizedSource + offset
  captureExpected := rawSum & "hfffffffe".U(32.W)
  arithmeticHolds := !capture || (executeTarget & "hfffffffe".U(32.W)) === captureExpected
  withClockAndReset(clock, reset.asAsyncReset) {
    val capturedSource = RegInit(0.U(32.W))
    val stagedSource = RegInit(0.U(32.W))
    when(capture) { capturedSource := normalizedSource }
    when(retiring) { stagedSource := capturedSource }
    expectedSource := stagedSource
    val reported = Mux(rvfiInstruction(19,15) === 0.U, 0.U(32.W), rvfiSource)
    sourceHolds := !active || (stageValid && reported === stagedSource)
  }
  val sourceZero = IO(Output(Bool()))
  val sourceAlias = IO(Output(Bool()))
  val arithmeticNegative = IO(Output(Bool()))
  val arithmeticOdd = IO(Output(Bool()))
  val sourceFaultActive = IO(Output(Bool()))
  sourceZero := active && rvfiInstruction(19,15) === 0.U
  sourceAlias := active && rvfiInstruction(19,15) =/= 0.U && rvfiInstruction(19,15) === rvfiInstruction(11,7)
  arithmeticNegative := capture && idInstruction(31)
  arithmeticOdd := capture && rawSum(0)
  sourceFaultActive := active && rvfiInstruction(19,15) =/= 0.U
}

object EmitJalrCaptureProperty {
  def main(args: Array[String]): Unit = {
    ChiselStage.emitSystemVerilogFile(new JalrCaptureProperty,
      Array("--target-dir", args(0)), Array("--disable-all-randomization"))
  }
}
