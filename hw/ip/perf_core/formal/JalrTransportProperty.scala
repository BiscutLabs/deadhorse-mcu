package deadhorse.perf_core.formal

import chisel3._
import circt.stage.ChiselStage

/** Observation-only ghost state. No architectural arithmetic is assumed/proved here. */
class JalrTransportProperty extends RawModule {
  val clock = IO(Input(Clock()))
  val reset = IO(Input(Bool()))
  val checkerReset = IO(Input(Bool()))
  val idValid = IO(Input(Bool()))
  val idNew = IO(Input(Bool()))
  val idClear = IO(Input(Bool()))
  val idFirst = IO(Input(Bool()))
  val idCompressed = IO(Input(Bool()))
  val idDummy = IO(Input(Bool()))
  val idInstruction = IO(Input(UInt(32.W)))
  val idPc = IO(Input(UInt(32.W)))
  val pcSet = IO(Input(Bool()))
  val pcMux = IO(Input(UInt(3.W)))
  val executeTarget = IO(Input(UInt(32.W)))
  val retireDone = IO(Input(Bool()))
  val observedNextPc = IO(Input(UInt(32.W)))
  val rvfiValid = IO(Input(Bool()))
  val rvfiInstruction = IO(Input(UInt(32.W)))
  val rvfiPc = IO(Input(UInt(32.W)))
  val rvfiNextPc = IO(Input(UInt(32.W)))
  val capture = IO(Output(Bool()))
  val retiring = IO(Output(Bool()))
  val active = IO(Output(Bool()))
  val holds = IO(Output(Bool()))
  val captureValid = IO(Output(Bool()))
  val stageValid = IO(Output(Bool()))
  val expectedTarget = IO(Output(UInt(32.W)))
  def jalr(insn: UInt): Bool = insn(6,0) === "h67".U && insn(14,12) === 0.U
  val currentJalr = idValid && !idCompressed && !idDummy && jalr(idInstruction)
  capture := !reset && currentJalr && idFirst && pcSet && pcMux === 1.U
  retiring := !reset && retireDone && currentJalr
  active := !checkerReset && rvfiValid && jalr(rvfiInstruction)
  withClockAndReset(clock, reset.asAsyncReset) {
    val capturedValid = RegInit(false.B)
    val capturedTarget = RegInit(0.U(32.W))
    val capturedInstruction = RegInit(0.U(32.W))
    val capturedPc = RegInit(0.U(32.W))
    when(idNew || !idValid || idClear || retireDone) { capturedValid := false.B }
    when(capture) {
      capturedValid := true.B
      capturedTarget := executeTarget & "hfffffffe".U(32.W)
      capturedInstruction := idInstruction
      capturedPc := idPc
    }
    val expectedValid = RegNext(retiring, false.B)
    val target = RegInit(0.U(32.W))
    val instruction = RegInit(0.U(32.W))
    val pc = RegInit(0.U(32.W))
    when(retiring) { target := capturedTarget; instruction := capturedInstruction; pc := capturedPc }
    val retirementHolds = !retiring || (capturedValid && !capture &&
      capturedInstruction === idInstruction && capturedPc === idPc && observedNextPc === capturedTarget)
    val rvfiHolds = !active || (expectedValid && instruction === rvfiInstruction &&
      pc === rvfiPc && rvfiNextPc === target)
    holds := retirementHolds && rvfiHolds && (!capture || (!idClear && !retireDone))
    captureValid := capturedValid
    stageValid := expectedValid
    expectedTarget := target
  }
}

object EmitJalrTransportProperty {
  def main(args: Array[String]): Unit = {
    ChiselStage.emitSystemVerilogFile(new JalrTransportProperty,
      Array("--target-dir", args(0)), Array("--disable-all-randomization"))
  }
}
