package deadhorse.timers

import chisel3._
import chisel3.util._
import deadhorse.lib._

class MainTimers(json: String,mainMHz: Int,base: BigInt=0,formalChecks: Boolean=false) extends RawModule {
  require(Set(8,9).contains(mainMHz))
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new LocalBus);val owner=IO(Input(UInt(3.W)))
  val captureIn=IO(Input(UInt(4.W)));val imuDrdy=IO(Input(Bool()))
  val compareOut=IO(Output(UInt(4.W)));val pinsEnable=IO(Output(UInt(4.W)));val timeNow=IO(Output(UInt(32.W)))
  val irq=IO(Output(Bool()));val clockHold=IO(Output(Bool()))
  protected def timeValue(value: UInt): UInt=value
  val regs=Module(new RegBlock(json));regs.clk:=clk;regs.rst_n:=reset_n
  val adapter=Module(new BusRegAdapter(8,base,0));adapter.clk:=clk;adapter.reset_n:=reset_n
  adapter.bus.req:=bus.req;adapter.bus.bits:=bus.bits;adapter.bus.bits.origin:=Mux(bus.bits.origin===owner,0.U,7.U)
  bus.gnt:=adapter.bus.gnt;bus.rvalid:=adapter.bus.rvalid;bus.rdata:=adapter.bus.rdata;bus.err:=adapter.bus.err;regs.bus<>adapter.registers
  val sync=Module(new CdcSync(5));sync.clk:=clk;sync.reset_n:=reset_n;sync.in:=Cat(imuDrdy,captureIn)
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val time=RegInit(0.U(32.W));val phase=RegInit(0.U(log2Ceil(mainMHz).W))
    val run=regs.hw("control_run_q").asBool;val load=regs.hw("command_load_time_pulse").asBool
    val tick=run && phase===(mainMHz-1).U
    val effective=Mux(tick,time+1.U,time)
    when(!run) {
      phase:=0.U;when(load) {time:=regs.hw("preload_value_q")}
    }.otherwise {time:=effective;phase:=Mux(tick,0.U,phase+1.U)}
    timeNow:=timeValue(time);regs.hw("time_value_value_d"):=timeValue(time)
    regs.hw("events_load_error_set"):=(load && run).asUInt
    val previous=RegNext(sync.out,0.U)
    val rise=sync.out & ~previous;val fall= ~sync.out & previous
    val mode=RegInit(VecInit(Seq.fill(4)(0.U(2.W))))
    val deadline=Reg(Vec(4,UInt(32.W)));val captured=RegInit(VecInit(Seq.fill(4)(0.U(32.W))))
    val armed=RegInit(VecInit(Seq.fill(4)(false.B)))
    val output=RegInit(VecInit(Seq.fill(4)(false.B)));val enabled=RegInit(VecInit(Seq.fill(4)(false.B)))
    val pendingSet=Wire(Vec(4,Bool()));val overrun=Wire(Vec(4,Bool()));val rejected=Wire(Vec(4,Bool()))
    for(i<-0 until 4) {
      val apply=regs.hw("command_apply_pulse")(i)
      val nextMode=regs.hw(s"channel_mode${i}_mode_q");val nextEnable=regs.hw(s"channel_mode${i}_output_enable_q").asBool
      val target=regs.hw(s"deadline${i}_value_q");val delta=(target-effective)(31,0)
      val allowed=run && (!nextEnable || nextMode===3.U) &&
        (nextMode=/=3.U || (delta=/=0.U && !delta(31)))
      val applied=apply && allowed
      rejected(i):=apply && !allowed;pendingSet(i):=false.B;overrun(i):=false.B
      when(!run) {mode(i):=0.U;armed(i):=false.B;enabled(i):=false.B;output(i):=false.B}
        .elsewhen(applied) {
          mode(i):=nextMode;deadline(i):=target;armed(i):=nextMode===3.U
          enabled(i):=nextEnable;output(i):=false.B
        }.otherwise {
          val capture=(mode(i)===1.U && rise(i)) || (mode(i)===2.U && fall(i))
          when(capture) {
            captured(i):=effective;pendingSet(i):=true.B
            overrun(i):=regs.hw("events_pending_q")(i)
          }
          when(armed(i) && effective===deadline(i)) {armed(i):=false.B;output(i):=true.B;pendingSet(i):=true.B}
        }
      regs.hw(s"captured${i}_value_d"):=captured(i)
    }
    val imuTime=RegInit(0.U(32.W));val imu=run && rise(4)
    when(imu) {imuTime:=effective}
    regs.hw("imu_capture_value_d"):=imuTime;regs.hw("events_imu_set"):=imu.asUInt
    regs.hw("events_pending_set"):=pendingSet.asUInt;regs.hw("events_overrun_set"):=overrun.asUInt
    regs.hw("events_config_error_set"):=rejected.asUInt;regs.hw("status_armed_d"):=armed.asUInt
    compareOut:=output.asUInt;pinsEnable:=enabled.asUInt
    val events=Cat(regs.hw("events_load_error_q"),regs.hw("events_imu_q"),regs.hw("events_config_error_q"),
      regs.hw("events_overrun_q"),regs.hw("events_pending_q"))
    irq:=RegNext((events & regs.hw("irq_enable_events_q")).orR,false.B);clockHold:=RegNext(run,false.B)
    if(formalChecks) {
      val past=RegNext(true.B,false.B)
      val expected=RegNext(Mux(!run && load,regs.hw("preload_value_q"),effective),0.U)
      when(past) {assert(timeNow===expected);assert(clockHold===RegNext(run,false.B))}
      for(i<-0 until 4) {assert(!enabled(i) || mode(i)===3.U)}
    }
  }
}
