package deadhorse.perf_core.formal

import chisel3._
import chisel3.util.Cat
import circt.stage.ChiselStage

/** Check the transition across an outstanding integer execute request. */
class PhaseStabilityProperty extends JalrOwnershipProperty {
  val instructionWrite = IO(Input(Bool()))
  val holding = IO(Output(Bool()))
  val noWriteHolds = IO(Output(Bool()))
  val noClearHolds = IO(Output(Bool()))
  val stabilityActive = IO(Output(Bool()))
  val stabilityHolds = IO(Output(Bool()))
  val currentTag = IO(Output(UInt(68.W)))
  val previousTag = IO(Output(UInt(68.W)))
  holding := !reset && (ownerValid || accepted) && !consumed
  noWriteHolds := !holding || !instructionWrite
  noClearHolds := !holding || !idClear
  currentTag := Cat(idInstruction,idPc,idValid,idFirst,idCompressed,idDummy)
  withClockAndReset(clock, reset.asAsyncReset) {
    val priorHolding = RegNext(holding,false.B)
    val priorTag = RegNext(currentTag,0.U(68.W))
    previousTag := priorTag
    stabilityActive := !reset && priorHolding
    stabilityHolds := !stabilityActive || currentTag === priorTag
  }
}

object EmitPhaseStabilityProperty {
  def main(args: Array[String]): Unit = {
    ChiselStage.emitSystemVerilogFile(new PhaseStabilityProperty,
      Array("--target-dir", args(0)), Array("--disable-all-randomization"))
  }
}
