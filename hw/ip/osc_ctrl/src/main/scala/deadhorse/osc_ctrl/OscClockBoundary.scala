package deadhorse.osc_ctrl

import chisel3._
import chisel3.util._
import deadhorse.lib._

/** Production configuration is a retained shared-FIFO head in this source
  * domain. Qualify remains synchronized locally; count is captured once. */
class OscStability(qualifiedReset: Boolean=false) extends RawModule {
  protected def clearRemaining: Boolean=false
  protected def clearedReady: Bool=false.B
  val clk=IO(Input(Clock())); val reset_n=IO(Input(Bool()))
  val clear=if(qualifiedReset) Some(IO(Input(Bool()))) else None
  val oscillatorOn=IO(Input(Bool())); val qualify=IO(Input(Bool()))
  val count=IO(Input(UInt(16.W))); val stable=IO(Output(Bool()))
  protected def decrement(value: UInt): UInt=Cat((0 until 4).reverse.map { nibble=>
    val low=nibble*4
    val word=value(low+3,low)
    val decremented=WireDefault(word-1.U(4.W))
    val borrow=WireDefault(if(low==0) true.B else value(low-1,0)===0.U)
    // Preserve the parallel carry-select shape, as in the core's qualified
    // address incrementer. The mapper otherwise rebuilds a long borrow chain.
    addAttribute(decremented,"keep = 1");addAttribute(borrow,"keep = 1")
    Mux(borrow,decremented,word)
  })
  val up=if(qualifiedReset) reset_n else {
    val release=Module(new ResetRelease)
    release.clk:=clk;release.reset_n:=reset_n && oscillatorOn;release.released
  }
  val request=Module(new CdcSync(1,withClear=qualifiedReset))
  request.clear.foreach(_:=clear.get)
  request.clk:=clk;request.reset_n:=up;request.in:=qualify.asUInt
  withClockAndReset(clk,(!up).asAsyncReset) {
    val active=RegInit(false.B);val ready=RegInit(false.B)
    val remaining=RegInit(0.U(16.W))
    when(!request.out.asBool) {active:=false.B;ready:=false.B}
      .elsewhen(!active) {
        active:=true.B;remaining:=Mux(count===0.U,1.U,count)
      }.elsewhen(!ready) {
        when(remaining===1.U) {ready:=true.B}
          .otherwise {remaining:=decrement(remaining)}
      }
    // An inactive count is unobservable and the next activation reloads it.
    // Keep clear off the wide countdown mux; cold reset still initializes it.
    clear.foreach(c=>when(c) {
      active:=false.B;ready:=clearedReady
      if(clearRemaining) remaining:=0.U
    })
    stable:=ready
  }
}

/** Source-edge-only /6. Reset completes an in-progress high phase, then parks
  * low. Its two non-reset flops initialize within four source edges of held
  * reset; domain reset asserts asynchronously and startup keeps the ICG shut.
  * No reset event can shorten a previously qualified high pulse. */
class OscDivider extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val divided=IO(Output(Clock()))
  protected def terminal(value: Bool): Bool=value
  withClockAndReset(clk,false.B) {
    val phase=Reg(UInt(2.W));val level=Reg(Bool())
    when(!reset_n) {
      when(!level || phase===2.U) {phase:=0.U;level:=false.B}
        .otherwise {phase:=phase+1.U}
    }.elsewhen(terminal(phase===2.U)) {phase:=0.U;level:= !level}
      .otherwise {phase:=phase+1.U}
    divided:=level.asClock
  }
}

/** Source-local command executor, clocked by ungated /6. Requests arrive from
  * the shared FIFO, so a command is consumed exactly once. A close can be
  * rejected by local work; a successful close stays closed until a new command.
  * Completion is held until consumed by the return FIFO. */
class OscMainGate(target: ClockGateTarget=ClockGateTarget.Model,withClear: Boolean=false) extends RawModule {
  protected def closure(value: Bool): Bool=value
  protected def gateEnable(value: Bool): Bool=value
  protected def workActive: Bool=localHold || !coreIdle
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val clear=if(withClear) Some(IO(Input(Bool()))) else None
  val request=IO(Input(Bool()));val verified=IO(Input(Bool()))
  val command=IO(Input(Bool()));val ready=IO(Output(Bool()))
  val completed=IO(Output(Bool()));val result=IO(Output(Bool()));val consume=IO(Input(Bool()))
  val localHold=IO(Input(Bool()));val coreIdle=IO(Input(Bool()))
  val closed=IO(Output(Bool()));val gated=IO(Output(Clock()))
  val valid=Module(new CdcSync(1,withClear))
  valid.clear.foreach(_:=clear.get)
  valid.clk:=clk;valid.reset_n:=reset_n;valid.in:=verified.asUInt
  val cell=Module(new ClockGate(target));cell.clk_i:=clk;cell.test_en_i:=false.B
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val open=RegInit(false.B);val wasClosed=RegInit(false.B);val ack=RegInit(false.B)
    val draining=RegInit(false.B);val wasOpen=RegInit(false.B)
    val done=RegInit(false.B);val reply=RegInit(false.B)
    ready:= !clear.getOrElse(false.B) && !draining && !done && (!request || valid.out.asBool)
    completed:=done && !clear.getOrElse(false.B);result:=reply
    when(done && consume) {done:=false.B}
    when(command && ready) {
      when(request) {
        open:=true.B;ack:=false.B;done:=true.B;reply:=false.B
      }.elsewhen(open && workActive) {
        // Reject rather than stall cancellation behind a future WFI.
        done:=true.B;reply:=false.B
      }.otherwise {
        wasOpen:=open;open:=false.B;wasClosed:=false.B;draining:=true.B
      }
    }
    when(draining) {
      when(wasOpen && workActive) {
        open:=valid.out.asBool;ack:=false.B;draining:=false.B;done:=true.B;reply:=false.B
      }.elsewhen(wasClosed) {
        ack:=true.B;draining:=false.B;done:=true.B;reply:=true.B
      }.otherwise {wasClosed:=true.B}
    }
    clear.foreach(c=>when(c) {
      open:=false.B;wasClosed:=false.B;ack:=false.B;draining:=false.B
      wasOpen:=false.B;done:=false.B;reply:=false.B
    })
    cell.en_i:=gateEnable(open);closed:=closure(ack);gated:=cell.clk_o
  }
}
