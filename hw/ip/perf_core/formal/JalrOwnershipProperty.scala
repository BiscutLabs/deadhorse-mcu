package deadhorse.perf_core.formal

import chisel3._
import circt.stage.ChiselStage

/** Observe every real execute handshake; no internal relation is assumed. */
class JalrOwnershipProperty extends JalrRequestProperty {
  val reqValid = IO(Input(Bool()))
  val reqReady = IO(Input(Bool()))
  val incomingKind = IO(Input(UInt(2.W)))
  val rspReady = IO(Input(Bool()))
  val accepted = IO(Output(Bool()))
  val consumed = IO(Output(Bool()))
  val issueActive = IO(Output(Bool()))
  val issueHolds = IO(Output(Bool()))
  val retentionHolds = IO(Output(Bool()))
  val retainedKindHolds = IO(Output(Bool()))
  val ownershipHolds = IO(Output(Bool()))
  val ownerValid = IO(Output(Bool()))
  val ownerKind = IO(Output(UInt(2.W)))
  val ownerFirst = IO(Output(Bool()))
  val ownerJalr = IO(Output(Bool()))
  val ownerInstruction = IO(Output(UInt(32.W)))
  val ownerPc = IO(Output(UInt(32.W)))
  val responseCover = IO(Output(Bool()))
  val captureZero = IO(Output(Bool()))
  val captureReplacement = IO(Output(Bool()))
  accepted := !reset && reqValid && reqReady
  consumed := !reset && responseValid && rspReady
  issueActive := accepted && currentJalr && idFirst
  issueHolds := !issueActive || incomingKind === 0.U
  withClockAndReset(clock, reset.asAsyncReset) {
    val valid = RegInit(false.B)
    val kind = RegInit(0.U(2.W))
    val first = RegInit(false.B)
    val isJalr = RegInit(false.B)
    val instruction = RegInit(0.U(32.W))
    val pc = RegInit(0.U(32.W))
    val seenOther = RegInit(false.B)
    val followsOther = RegInit(false.B)
    when(consumed) { valid := false.B }
    when(accepted) {
      valid := true.B
      kind := incomingKind
      first := idFirst
      isJalr := currentJalr && idFirst
      instruction := idInstruction
      pc := idPc
      followsOther := seenOther
      when(!(currentJalr && idFirst)) { seenOther := true.B }
    }
    ownerValid := valid; ownerKind := kind; ownerFirst := first
    ownerJalr := isJalr; ownerInstruction := instruction; ownerPc := pc
    retentionHolds := reset || (!(accepted && consumed) &&
      (!responseValid || valid) && (!valid || (kind === requestKind && first === requestFirst)))
    retainedKindHolds := reset || !valid || !isJalr || kind === 0.U
    ownershipHolds := !capture || (valid && isJalr && first &&
      instruction === idInstruction && pc === idPc)
    responseCover := !reset && valid && responseValid && isJalr
    captureZero := capture && idInstruction(19,15) === 0.U
    captureReplacement := capture && followsOther && idInstruction(19,15) =/= 0.U && normalizedSource =/= 0.U
  }
}

object EmitJalrOwnershipProperty {
  def main(args: Array[String]): Unit = {
    ChiselStage.emitSystemVerilogFile(new JalrOwnershipProperty,
      Array("--target-dir", args(0)), Array("--disable-all-randomization"))
  }
}
