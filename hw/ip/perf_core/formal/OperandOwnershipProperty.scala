package deadhorse.perf_core.formal

import chisel3._
import circt.stage.ChiselStage

/** Actual request payload classification, retention and architectural source stability. */
class OperandOwnershipProperty extends PhaseStabilityProperty {
  val incomingA = IO(Input(UInt(32.W)))
  val incomingB = IO(Input(UInt(32.W)))
  val incomingOp = IO(Input(UInt(7.W)))
  val operandIssueHolds = IO(Output(Bool()))
  val operandRetentionHolds = IO(Output(Bool()))
  val sourceHolding = IO(Output(Bool()))
  val sourceStabilityActive = IO(Output(Bool()))
  val sourceStabilityHolds = IO(Output(Bool()))
  val sourceNow = IO(Output(UInt(32.W)))
  val sourceBefore = IO(Output(UInt(32.W)))
  val ownerA = IO(Output(UInt(32.W)))
  val ownerB = IO(Output(UInt(32.W)))
  val ownerOp = IO(Output(UInt(7.W)))
  val ownerSource = IO(Output(UInt(32.W)))
  operandIssueHolds := !issueActive || (incomingOp === 0.U &&
    incomingA === normalizedSource && incomingB === offset)
  sourceHolding := holding && (issueActive || (ownerValid && ownerJalr))
  sourceNow := normalizedSource
  withClockAndReset(clock, reset.asAsyncReset) {
    val a = RegInit(0.U(32.W)); val b = RegInit(0.U(32.W))
    val op = RegInit(0.U(7.W)); val source = RegInit(0.U(32.W))
    when(accepted) {
      a := incomingA; b := incomingB; op := incomingOp; source := normalizedSource
    }
    ownerA := a; ownerB := b; ownerOp := op; ownerSource := source
    operandRetentionHolds := reset || !ownerValid ||
      (requestA === a && requestB === b && requestOp === op)
    val priorSourceHolding = RegNext(sourceHolding, false.B)
    val priorSource = RegNext(normalizedSource, 0.U(32.W))
    sourceBefore := priorSource
    sourceStabilityActive := !reset && priorSourceHolding
    sourceStabilityHolds := !sourceStabilityActive || normalizedSource === priorSource
  }
}

object EmitOperandOwnershipProperty {
  def main(args: Array[String]): Unit = {
    ChiselStage.emitSystemVerilogFile(new OperandOwnershipProperty,
      Array("--target-dir", args(0)), Array("--disable-all-randomization"))
  }
}
