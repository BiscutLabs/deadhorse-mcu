package deadhorse.aon_timer

import chisel3._
import chisel3.util._
import deadhorse.lib._

class AonTimers(json: String,base: BigInt=0,formalChecks: Boolean=false) extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new LocalBus);val owner=IO(Input(UInt(3.W)))
  val irq=IO(Output(Bool()));val wake=IO(Output(Bool()));val clockHold=IO(Output(Bool()))
  protected def loadedDuration(value: UInt): UInt=value
  val regs=Module(new RegBlock(json));regs.clk:=clk;regs.rst_n:=reset_n
  val adapter=Module(new BusRegAdapter(8,base,0));adapter.clk:=clk;adapter.reset_n:=reset_n
  adapter.bus.req:=bus.req;adapter.bus.bits:=bus.bits;adapter.bus.bits.origin:=Mux(bus.bits.origin===owner,0.U,7.U)
  bus.gnt:=adapter.bus.gnt;bus.rvalid:=adapter.bus.rvalid;bus.rdata:=adapter.bus.rdata;bus.err:=adapter.bus.err;regs.bus<>adapter.registers
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val remaining=RegInit(VecInit(Seq.fill(4)(0.U(32.W))))
    val expired=Wire(Vec(4,Bool()));val rejected=Wire(Vec(4,Bool()))
    for(i<-0 until 4) {
      val arm=regs.hw("command_arm_pulse")(i);val cancel=regs.hw("command_cancel_pulse")(i)
      val duration=regs.hw(s"duration${i}_ticks_q")
      val allowed=duration=/=0.U && !duration(31)
      val applied=arm && allowed && !cancel
      rejected(i):=arm && !cancel && !allowed
      expired(i):=remaining(i)===1.U && !cancel && !applied
      when(cancel) {remaining(i):=0.U}
        .elsewhen(applied) {remaining(i):=loadedDuration(duration)}
        .elsewhen(remaining(i)=/=0.U) {remaining(i):=remaining(i)-1.U}
      regs.hw(s"remaining${i}_ticks_d"):=remaining(i)
      if(formalChecks) {
        val past=RegNext(true.B,false.B)
        val expected=RegNext(Mux(cancel,0.U,Mux(applied,duration,Mux(remaining(i)=/=0.U,remaining(i)-1.U,0.U))),0.U)
        when(past) {assert(remaining(i)===expected)}
      }
    }
    regs.hw("events_pending_set"):=expired.asUInt;regs.hw("events_config_error_set"):=rejected.asUInt
    val active=VecInit(remaining.map(_=/=0.U)).asUInt;regs.hw("status_active_d"):=active
    val pending=regs.hw("events_pending_q")
    val interrupt=(pending & regs.hw("irq_enable_channels_q")).orR
    val request=(pending & regs.hw("wake_enable_channels_q")).orR
    irq:=RegNext(interrupt,false.B);wake:=RegNext(request,false.B)
    clockHold:=RegNext(active.orR || interrupt || request,false.B)
  }
}
