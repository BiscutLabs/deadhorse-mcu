package deadhorse.perf_core.formal

import chisel3._
import circt.stage.ChiselStage

/** Actual register-file read selection and write hazards across source holding. */
class RfSourceControlProperty extends OperandOwnershipProperty {
  val rfReadAddress = IO(Input(UInt(5.W)))
  val rfWriteAddress = IO(Input(UInt(5.W)))
  val rfWriteEnable = IO(Input(Bool()))
  val rfAddressHolds = IO(Output(Bool()))
  val rfNoConflictHolds = IO(Output(Bool()))
  val rfPriorAddress = IO(Output(UInt(5.W)))
  rfNoConflictHolds := !sourceHolding || !rfWriteEnable || rfReadAddress === 0.U ||
    rfWriteAddress =/= rfReadAddress
  withClockAndReset(clock, reset.asAsyncReset) {
    val prior = RegNext(rfReadAddress,0.U(5.W))
    rfPriorAddress := prior
    rfAddressHolds := !sourceStabilityActive || rfReadAddress === prior
  }
}

object EmitRfSourceControlProperty {
  def main(args: Array[String]): Unit = {
    ChiselStage.emitSystemVerilogFile(new RfSourceControlProperty,
      Array("--target-dir", args(0)), Array("--disable-all-randomization"))
  }
}
