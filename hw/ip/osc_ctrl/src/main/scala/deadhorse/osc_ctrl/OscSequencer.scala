package deadhorse.osc_ctrl

import chisel3._
import chisel3.util._

/** AON policy only. Inputs are already local/synchronized; source-clock gate
  * closure and stability are independently acknowledged by the clock boundary. */
class OscSequencer extends RawModule {
  val clk=IO(Input(Clock())); val reset_n=IO(Input(Bool()))
  val sleep=IO(Input(Bool())); val deep=IO(Input(Bool()))
  val forceRun=IO(Input(Bool())) // Internal reset is an unmaskable sleep cancellation.
  val mainHold=IO(Input(Bool())); val oscillatorHold=IO(Input(Bool()))
  val coreIdle=IO(Input(Bool())); val gateClosed=IO(Input(Bool()))
  val stable=IO(Input(Bool())); val wake=IO(Input(UInt(8.W)))
  val wakeEnable=IO(Input(UInt(8.W)))
  val delayTicks=IO(Input(UInt(16.W))); val timeoutTicks=IO(Input(UInt(16.W)))
  val stableEdges=IO(Input(UInt(16.W)))
  val oscillatorOn=IO(Output(Bool())); val gateRequest=IO(Output(Bool()))
  val qualify=IO(Output(Bool())); val count=IO(Output(UInt(16.W)))
  val authorized=IO(Output(Bool()))
  val preparing=IO(Output(Bool())); val state=IO(Output(UInt(2.W)))
  val fault=IO(Output(Bool())); val lastWake=IO(Output(UInt(8.W)))
  val pendingWake=IO(Output(UInt(8.W)))
  protected def stopAllowed(value: Bool): Bool=value
  protected def gateAllowed(value: Bool): Bool=value
  protected def capturedWake(value: UInt): UInt=value
  protected def shutdownReady(value: Bool): Bool=value
  protected def gateOutput(value: Bool): Bool=value
  protected def resetOn: Bool=true.B
  protected def forcedRun(value: Bool): Bool=value

  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val run :: stopping :: off :: starting :: Nil=Enum(4)
    val phase=RegInit(starting)
    val on=RegInit(resetOn); val gate=RegInit(false.B)
    val checking=RegInit(false.B); val failed=RegInit(false.B)
    val permission=RegInit(false.B)
    val initialized=RegInit(false.B); val sawUnstable=RegInit(false.B)
    val delay=RegInit(512.U(16.W)); val timeout=RegInit(4096.U(16.W))
    val edges=RegInit(256.U(16.W)); val elapsed=RegInit(0.U(16.W))
    val deepSleep=RegInit(false.B)
    val closurePending=RegInit(false.B)
    val stopArmed=RegInit(false.B)
    val pending=RegInit(0.U(8.W)); val causes=RegInit(0.U(8.W))
    val forced=forcedRun(forceRun)
    val incoming=wake & wakeEnable
    val allWake=pending | incoming
    val demand=mainHold || oscillatorHold
    def nonzero(value: UInt): UInt=Mux(value===0.U,1.U,value)
    def start(): Unit = {
      on:=true.B;gate:=false.B;checking:=false.B;sawUnstable:=false.B;permission:=false.B
      elapsed:=0.U;delay:=nonzero(delayTicks);timeout:=nonzero(timeoutTicks)
      edges:=nonzero(stableEdges);phase:=starting
    }
    pending:=capturedWake(allWake)
    when(!initialized) {
      initialized:=true.B;delay:=nonzero(delayTicks);timeout:=nonzero(timeoutTicks)
      edges:=nonzero(stableEdges)
    }.elsewhen(phase===starting) {
      when(!stable) {sawUnstable:=true.B}
      when(!failed) {
        when(!checking) {
          when(elapsed===delay-1.U && sawUnstable) {checking:=true.B;elapsed:=0.U}
            .elsewhen(elapsed=/=delay-1.U) {elapsed:=elapsed+1.U}
        }.otherwise {
          when(stable) {gate:=gateAllowed(true.B);permission:=true.B;phase:=run}
            .elsewhen(elapsed===timeout-1.U) {failed:=true.B}
            .otherwise {elapsed:=elapsed+1.U}
        }
      }
    }.elsewhen(phase===run) {
      closurePending:=false.B;stopArmed:=false.B
      when(allWake.orR) {causes:=allWake;pending:=0.U}
      when(sleep && !allWake.orR && !forced) {deepSleep:=deep;phase:=stopping}
    }.elsewhen(phase===stopping) {
      // Allow the new sleep transfer to register its hold before requesting
      // gate closure. Thereafter its FIFO read acknowledgement keeps us safe.
      stopArmed:=true.B
      when(allWake.orR || forced) {gate:=true.B;phase:=run}
        .elsewhen(shutdownReady(stopArmed && !mainHold && coreIdle)) {
          gate:=false.B
          // Reject a stale closed report from power-up or a previous stop.
          // Observe open while withdrawing the request, then fresh closure.
          // The source can finish within one AON period, so do not require an
          // intermediate open sample on a later AON edge.
          when(!gateClosed) {closurePending:=true.B}
          when(closurePending && gateClosed) {
            when(!deepSleep || oscillatorHold || stopAllowed(!demand)) {
              on:= !deepSleep || oscillatorHold
              when(deepSleep && !oscillatorHold) {checking:=false.B;permission:=false.B}
              phase:=off
            }
          }
        }.otherwise {gate:=true.B;closurePending:=false.B}
    }.otherwise {
      when(allWake.orR || forced || mainHold || oscillatorHold && !on) {
        when(on) {gate:=true.B;phase:=run}.otherwise {start()}
      }
    }
    oscillatorOn:=on;gateRequest:=gateOutput(gate);qualify:=checking;count:=edges
    authorized:=permission
    preparing:=phase===stopping || phase===off
    state:=phase;fault:=failed;lastWake:=causes;pendingWake:=pending
  }
}
