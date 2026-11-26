package deadhorse.osc_ctrl

import chisel3._
import chisel3.util._
import deadhorse.lib.{CdcSync,ResetRelease}

/** Clocked qualification inside the D111 physical POR macro.
  * rawGood is the analog comparison using qualified release as hysteresis
  * feedback. cold_n comes from the independent power-epoch initializer.
  * Neither signal is synthesized from the digital voltage model.
  */
class PorQualifierPhysical(releaseEdges: Int=1000) extends RawModule {
  require(releaseEdges>=2)
  protected def complete(count: UInt): Bool=count===(releaseEdges-1).U
  val reference=IO(Input(Clock()))
  val cold_n=IO(Input(Bool()))
  val rawGood=IO(Input(Bool()))
  val threshold=IO(Input(UInt(2.W)))
  val higher=IO(Output(Bool()))
  val supplyReset_n=IO(Output(Bool()))
  val powerOn_n=IO(Output(Bool()))
  val brownout=IO(Output(Bool()))

  // Apply the actual analog setting immediately. Synchronized bits below
  // acknowledge stability only; they never select an analog threshold.
  higher:=threshold===1.U
  val code=UIntToOH(threshold,4)
  val observed=Wire(Vec(4,Bool()))
  for(i<-0 until 4) {
    val sync=Module(new CdcSync(1))
    sync.clk:=reference;sync.reset_n:=cold_n;sync.in:=code(i).asUInt
    observed(i):=sync.out.asBool
  }
  // A partially synchronized one-hot transition is not a valid third code.
  // Equality with the raw one-hot word is required throughout qualification.
  val pending=observed.asUInt=/=code
  val valid=cold_n && rawGood
  val stable=Module(new ResetRelease)
  stable.clk:=reference
  stable.reset_n:=valid && !pending
  val count=withClockAndReset(reference,(!(valid && !pending)).asAsyncReset) {
    val value=RegInit(0.U(log2Ceil(releaseEdges).W))
    when(!stable.released) {value:=0.U}
      .elsewhen(!complete(value)) {value:=value+1.U}
    value
  }
  val released=withClockAndReset(reference,(!valid).asAsyncReset) {
    val value=RegInit(false.B)
    // Explicit pending guard: never depend only on counter-reset propagation.
    when(stable.released && !pending && complete(count)) {value:=true.B}
    value
  }
  withClockAndReset(reference,(!cold_n).asAsyncReset) {
    val powered=RegInit(false.B)
    val brown=RegInit(false.B)
    when(released) {powered:=true.B}
    when(powered && !released) {brown:=true.B}
    powerOn_n:=powered;brownout:=brown
  }
  supplyReset_n:=released
}

object EmitPorPhysical extends App {
  require(args.length==1)
  _root_.circt.stage.ChiselStage.emitSystemVerilogFile(new PorQualifierPhysical,
    Array("--target-dir",args(0)),Array("--disable-all-randomization",
      "--strip-debug-info","--preserve-values=named","--lower-to-core"))
}
