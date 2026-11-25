package deadhorse.osc_ctrl

import chisel3._
import chisel3.util._

/** AON policy only. Inputs are already local/synchronized; source-clock gate
  * closure and stability are independently acknowledged by the clock boundary. */
class OscSequencer(withEpochClear: Boolean=false) extends RawModule {
  val clk=IO(Input(Clock())); val reset_n=IO(Input(Bool()))
  val initialize=if(withEpochClear) Some(IO(Input(Bool()))) else None
  val clearAck=if(withEpochClear) Some(IO(Input(UInt(2.W)))) else None
  val epochClear=if(withEpochClear) Some(IO(Output(Bool()))) else None
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
  protected def clearComplete(value: Bool): Bool=value

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
    val clearing=if(withEpochClear) Some(RegInit(true.B)) else None
    val clearReleased=if(withEpochClear) Some(RegInit(false.B)) else None
    val sourceReady=clearReleased.getOrElse(true.B) && !clearing.getOrElse(false.B)
    epochClear.foreach(_:=clearing.get)
    if(withEpochClear) {
      // The held request survives OFF. Both domains must acknowledge clearing,
      // then both acknowledgements must return low before new commands/config.
      when(phase===starting && clearing.get && clearComplete(clearAck.get.andR)) {clearing.get:=false.B}
      when(phase===starting && !clearing.get && clearAck.get===0.U) {clearReleased.get:=true.B}
    }
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
      when(!stable && sourceReady) {sawUnstable:=true.B}
      when(!failed) {
        when(!checking) {
          when(elapsed===delay-1.U && (if(withEpochClear) true.B else sawUnstable)) {checking:=true.B;elapsed:=0.U}
            .elsewhen(elapsed=/=delay-1.U) {elapsed:=elapsed+1.U}
        }.otherwise {
          when(stable && sourceReady && (if(withEpochClear) sawUnstable else true.B)) {gate:=gateAllowed(true.B);permission:=true.B;phase:=run}
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
      when(allWake.orR || forced || clearing.getOrElse(false.B) && demand) {
        when(clearing.getOrElse(false.B) || !sourceReady) {start()}
          .otherwise {gate:=true.B;phase:=run}
      }.elsewhen(clearing.getOrElse(false.B)) {
        // Closure was acknowledged before requesting this flush. Its explicit
        // source acknowledgements include gate closure, even after the old
        // completion FIFO and closed-report state have themselves been cleared.
        when(clearComplete(clearAck.map(_.andR).getOrElse(false.B))) {on:=false.B;phase:=off}
      }
        .elsewhen(shutdownReady(stopArmed && !mainHold && coreIdle)) {
          gate:=false.B
          // Reject a stale closed report from power-up or a previous stop.
          // Observe open while withdrawing the request, then fresh closure.
          // The source can finish within one AON period, so do not require an
          // intermediate open sample on a later AON edge.
          when(!gateClosed) {closurePending:=true.B}
          when(closurePending && gateClosed) {
            when(!deepSleep || oscillatorHold || stopAllowed(!demand)) {
              if(withEpochClear) {
                when(deepSleep && !oscillatorHold) {
                  clearing.get:=true.B;clearReleased.get:=false.B
                  checking:=false.B;permission:=false.B
                }.otherwise {on:=true.B;phase:=off}
              } else {
                on:= !deepSleep || oscillatorHold
                when(deepSleep && !oscillatorHold) {checking:=false.B;permission:=false.B}
                phase:=off
              }
            }
          }
        }.otherwise {gate:=true.B;closurePending:=false.B}
    }.otherwise {
      when(allWake.orR || forced || mainHold || oscillatorHold && !on) {
        when(on) {gate:=true.B;phase:=run}.otherwise {start()}
      }
    }
    initialize.foreach {clear=>when(clear) {
      phase:=starting;on:=true.B;gate:=false.B;checking:=false.B;failed:=false.B
      permission:=false.B;initialized:=false.B;sawUnstable:=false.B
      delay:=512.U;timeout:=4096.U;edges:=256.U;elapsed:=0.U
      deepSleep:=false.B;closurePending:=false.B;stopArmed:=false.B
      pending:=0.U;causes:=0.U;clearing.get:=true.B;clearReleased.get:=false.B
    }}
    oscillatorOn:=on;gateRequest:=gateOutput(gate);qualify:=checking && sourceReady;count:=edges
    authorized:=permission
    preparing:=phase===stopping || phase===off
    state:=phase;fault:=failed;lastWake:=causes;pendingWake:=pending
  }
}
