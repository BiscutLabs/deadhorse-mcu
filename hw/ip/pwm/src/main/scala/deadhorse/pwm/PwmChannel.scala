package deadhorse.pwm

import chisel3._
import chisel3.util._

class PwmSettings extends Bundle {
  val period=UInt(16.W)
  val divider=UInt(16.W)
  val high=UInt(17.W)
}

/** One independent edge-aligned PWM counter with one buffered configuration. */
class PwmChannel(formalChecks: Boolean=false) extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val settings=IO(Input(new PwmSettings));val apply=IO(Input(Bool()));val stop=IO(Input(Bool()))
  val pinOut=IO(Output(Bool()));val enabled=IO(Output(Bool()));val pending=IO(Output(Bool()))
  val rollover=IO(Output(Bool()));val error=IO(Output(Bool()))
  protected def outputValue(v: Bool): Bool=v

  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val active=RegInit(0.U.asTypeOf(new PwmSettings))
    val queued=RegInit(0.U.asTypeOf(new PwmSettings))
    val running=RegInit(false.B);val queuedValid=RegInit(false.B)
    val phase=RegInit(0.U(16.W));val count=RegInit(0.U(16.W))
    val pin=RegInit(false.B)
    val tick=phase===active.divider
    val boundary=running && tick && count===active.period
    val legal=settings.high<=(settings.period+&1.U)
    val accept=apply && legal && !queuedValid && !stop

    rollover:=RegNext(boundary && !stop,false.B)
    error:=RegNext(apply && !stop && (!legal || queuedValid),false.B)
    when(stop) {
      running:=false.B;queuedValid:=false.B;phase:=0.U;count:=0.U;pin:=false.B
      active:=0.U.asTypeOf(active);queued:=0.U.asTypeOf(queued)
    }.otherwise {
      when(running) {
        when(tick) {
          phase:=0.U
          when(boundary) {
            count:=0.U
            val next=Mux(queuedValid,queued,active)
            pin:=outputValue(next.high=/=0.U)
            when(queuedValid) {active:=queued;queuedValid:=false.B}
          }.otherwise {
            val next=count+1.U
            count:=next;pin:=outputValue(next<active.high)
          }
        }.otherwise {phase:=phase+1.U}
      }
      when(accept) {
        when(running) {queued:=settings;queuedValid:=true.B}
          .otherwise {
            active:=settings;running:=true.B;phase:=0.U;count:=0.U
            pin:=outputValue(settings.high=/=0.U)
          }
      }
    }
    pinOut:=pin;enabled:=running;pending:=queuedValid

    if(formalChecks) {
      val past=RegNext(true.B,false.B)
      val stopped=RegNext(stop,false.B)
      val started=RegNext(accept && !running,false.B)
      val captured=RegNext(accept && running,false.B)
      val transferred=RegNext(boundary && queuedValid && !stop,false.B)
      val oldActive=RegNext(active);val oldQueued=RegNext(queued);val oldSettings=RegNext(settings)
      assert(!running || count<=active.period)
      assert(!running || phase<=active.divider)
      assert(!running || active.high<=(active.period+&1.U))
      assert(!queuedValid || queued.high<=(queued.period+&1.U))
      assert(pinOut===(running && count<active.high))
      assert(!queuedValid || running)
      when(past) {
        when(stopped) {assert(!running && !queuedValid && !pinOut)}
        when(started) {assert(running && active.asUInt===oldSettings.asUInt)}
        when(captured) {assert(queuedValid && queued.asUInt===oldSettings.asUInt)}
        when(transferred) {assert(active.asUInt===oldQueued.asUInt)}
        when(!stopped && !started && !transferred) {assert(active.asUInt===oldActive.asUInt)}
        when(!stopped && !captured) {assert(queued.asUInt===oldQueued.asUInt)}
      }
    }
  }
}
