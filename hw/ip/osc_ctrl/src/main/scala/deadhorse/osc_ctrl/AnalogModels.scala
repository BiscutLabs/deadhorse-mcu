package deadhorse.osc_ctrl

import chisel3._
import chisel3.util._
import chisel3.experimental.Analog

/** Physical interface only. T34 supplies characterized analog views, not RTL. */
class LfRcMacro extends BlackBox {
  val io=IO(new Bundle {
    val vdd=Analog(1.W);val vss=Analog(1.W)
    val enable=Input(Bool());val trim=Input(UInt(6.W));val test=Input(Bool())
    val clock=Output(Clock());val ready=Output(Bool())
  })
}

class PorBrownoutMacro extends BlackBox {
  val io=IO(new Bundle {
    val vdd=Analog(1.W);val vss=Analog(1.W)
    val threshold=Input(UInt(2.W));val test=Input(Bool())
    val supplyReset_n=Output(Bool())
    // Initial-power epoch is distinct from a later brownout, for cause capture.
    val powerOn_n=Output(Bool());val brownout=Output(Bool())
  })
}

/** Simulation supplies LF edges; this model does not synthesize an oscillator.
  * enable changes only while consumers are reset. Trim accuracy is not modeled. */
class LfRcModel extends RawModule {
  val source=IO(Input(Clock()));val power_n=IO(Input(Bool()));val enable=IO(Input(Bool()))
  val ready=IO(Output(Bool()));val out=IO(Output(Clock()))
  // Output remains the supplied oscillator, even before ready; consumers qualify.
  out:=source
  withClockAndReset(source,(!power_n).asAsyncReset) {
    val count=RegInit(0.U(3.W));val running=RegInit(false.B)
    when(!enable) {count:=0.U;running:=false.B}
      .elsewhen(count===3.U) {running:=true.B}
      .otherwise {count:=count+1.U}
    ready:=running
  }
}

/** Digital voltage model only. reference is an assumed 1 MHz simulation clock.
  * Default assumed thresholds: assert below 3.10 V, release at/above 3.20 V
  * after 1000 reference edges (estimated 1 ms). T34 must qualify safe limits. */
class PorBrownoutModel(releaseEdges: Int=1000) extends RawModule {
  require(releaseEdges>=1)
  val reference=IO(Input(Clock()));val supplyMv=IO(Input(UInt(12.W)))
  val threshold=IO(Input(UInt(2.W)))
  val supplyReset_n=IO(Output(Bool()));val powerOn_n=IO(Output(Bool()))
  val brownout=IO(Output(Bool()))
  // Reserved encodings retain the conservative default. T33 owns selection.
  protected def selectedThreshold(value: UInt): UInt=value
  protected def thresholdChanged(value: Bool): Bool=value
  val chosen=selectedThreshold(threshold)
  val falling=Mux(chosen===1.U,3200.U,3100.U)
  val rising=Mux(chosen===1.U,3300.U,3200.U)
  val ready=Wire(Bool())
  withClockAndReset(reference,(supplyMv<falling).asAsyncReset) {
    val released=RegInit(false.B);val count=RegInit(0.U(log2Ceil(releaseEdges+1).W))
    val previous=RegInit(0.U(2.W));previous:=chosen
    when(!released) {
      when(supplyMv>=rising) {
        // D85: never reuse qualification samples from another threshold.
        // This edge is the first sample under the new setting.
        when(thresholdChanged(previous=/=chosen)) {
          count:=1.U
          if(releaseEdges==1) {released:=true.B}
        }.elsewhen(count===(releaseEdges-1).U) {released:=true.B}
          .otherwise {count:=count+1.U}
      }.otherwise {count:=0.U}
    }
    ready:=released
  }
  withClockAndReset(reference,(supplyMv<100.U).asAsyncReset) {
    val powered=RegInit(false.B);val brown=RegInit(false.B)
    when(ready) {powered:=true.B}
    when(powered && !ready) {brown:=true.B}
    powerOn_n:=powered;brownout:=brown
  }
  supplyReset_n:=ready
}
