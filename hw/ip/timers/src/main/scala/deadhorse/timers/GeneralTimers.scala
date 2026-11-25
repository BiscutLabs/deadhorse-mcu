package deadhorse.timers

import chisel3._
import chisel3.util._
import deadhorse.lib._

/** Three shared-period timers; four conventional channels per timer. */
class GeneralTimers(json: String,mainMHz: Int=8,base: BigInt=0,watchdog: Boolean=false,formalChecks: Boolean=false) extends RawModule {
  require(Set(8,9).contains(mainMHz))
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new LocalBus)
  val owner=IO(Input(UInt(3.W)));val captureIn=IO(Input(UInt(12.W)));val captureValid=IO(Input(UInt(12.W)))
  val pinsOut=IO(Output(UInt(12.W)));val pinsEnable=IO(Output(UInt(12.W)));val running=IO(Output(UInt(12.W)))
  val timeNow=IO(Output(UInt(32.W)));val irq=IO(Output(UInt(3.W)));val clockHold=IO(Output(Bool()))
  val dmaAck=IO(Input(UInt(9.W)));val dmaRequest=IO(Output(UInt(9.W)))
  val watchdogReset_n=if(watchdog) Some(IO(Input(Bool()))) else None
  val performanceReady=if(watchdog) Some(IO(Input(Bool()))) else None
  protected def allowed(origin: UInt): Bool=origin===owner
  protected def adoptCompare(value: Bool): Bool=value
  protected def timeValue(value: UInt): UInt=value
  protected def holdValue(value: Bool): Bool=value
  protected def output(value: Bool): Bool=value
  protected def timestamp(value: UInt): UInt=value
  protected def compareMatch(value: Bool): Bool=value
  val regs=Module(new RegBlock(json));regs.clk:=clk;regs.rst_n:=reset_n
  val adapter=Module(new BusRegAdapter(10,base,0));adapter.clk:=clk;adapter.reset_n:=reset_n
  adapter.bus.req:=bus.req;adapter.bus.bits:=bus.bits
  adapter.bus.bits.origin:=Mux(allowed(bus.bits.origin),0.U,7.U)
  bus.gnt:=adapter.bus.gnt;bus.rvalid:=adapter.bus.rvalid;bus.rdata:=adapter.bus.rdata;bus.err:=adapter.bus.err
  regs.bus<>adapter.registers
  def q(name: String): UInt=regs.hw(name+"_q")
  def offset(name: String): UInt=regs.description.fields.find(_.register==name).get.offset.U
  val request=adapter.registers
  val events=Wire(Vec(12,Bool()));val errors=Wire(Vec(3,Bool()))
  val irqs=Wire(Vec(3,Bool()));val dmaEvents=Wire(Vec(9,Bool()))
  val pending=Wire(Vec(12,Bool()));val values=Wire(Vec(12,Bool()));val enables=Wire(Vec(12,Bool()))
  val run=q("timer_run_timers");val timeRun=q("time_control_run").asBool
  val captureRunning=(0 until 12).map(c=>run(c/4) && q(s"channel_mode${c}_mode")===3.U).reduce(_||_)
  val invalidStart=Wire(Vec(3,Bool()));val configBusy=Wire(Vec(3,Bool()))
  val startCompare=Wire(Vec(12,UInt(17.W)))
  for(t<-0 until 3) {
    val invalid=(4*t until 4*t+4).map {c=>
      val m=q(s"channel_mode${c}_mode");val compare=startCompare(c)
      (q(s"channel_mode${c}_output_enable").asBool && (m===0.U || m===3.U)) ||
        (m===3.U && !timeRun) || (m===1.U && compare>(q(s"period${t}_value")+&1.U)) ||
        (m===2.U && compare>q(s"period${t}_value"))
    }.reduce(_||_)
    invalidStart(t):=request.req_addr===offset("timer_run") && request.req_wstrb(0) &&
      request.req_wdata(t) && !run(t) && invalid
    configBusy(t):=run(t) && (Seq(s"period$t",s"prescaler$t").map(n=>request.req_addr===offset(n)) ++
      (4*t until 4*t+4).map(c=>request.req_addr===offset(s"channel_mode$c"))).reduce(_||_)
  }
  val timeError=captureRunning && (request.req_addr===offset("time_control") && request.req_wstrb(0) && !request.req_wdata(0) ||
    request.req_addr===offset("time_command") && request.req_wstrb(0) && request.req_wdata(0))
  val loadError=timeRun && request.req_addr===offset("time_command") && request.req_wstrb(0) && request.req_wdata(0)
  val deny=request.req_write && (invalidStart.asUInt.orR || configBusy.asUInt.orR || timeError || loadError)
  regs.bus.req_addr:=Mux(deny,1023.U,request.req_addr)
  val accept=request.req_valid && regs.bus.req_ready
  val stopWrite=accept && request.req_write && !deny && request.req_addr===offset("timer_run") && request.req_wstrb(0)
  val executionReset=reset_n && watchdogReset_n.getOrElse(true.B)
  val permit=if(watchdog) {
    val guard=Module(new TimerBreak);guard.clk:=clk;guard.reset_n:=executionReset
    guard.epochReady:=performanceReady.get
    guard.idle:=bus.gnt && !bus.req && !request.req_valid
    guard.stop:=Mux(stopWrite,~request.req_wdata(2,0),0.U)
    guard.permit
  } else 7.U(3.W)
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val time=RegInit(0.U(32.W));val timePhase=RegInit(0.U(log2Ceil(mainMHz).W))
    val tick=timeRun && timePhase===(mainMHz-1).U
    val effectiveTime=Mux(tick,time+1.U,time)
    when(timeRun) {time:=effectiveTime;timePhase:=Mux(tick,0.U,timePhase+1.U)}
      .otherwise {timePhase:=0.U;when(regs.hw("time_command_load_pulse").asBool) {time:=q("time_preload_value")}}
    timeNow:=timeValue(time);regs.hw("time_value_value_d"):=timeValue(time)
    val previous=RegNext(captureIn,0.U);val qualified=RegNext(captureValid,0.U) & captureValid
    val rising=captureIn & ~previous & qualified;val falling= ~captureIn & previous & qualified
    val active=RegInit(VecInit(Seq.fill(12)(0.U(17.W))))
    val queued=Reg(Vec(12,UInt(17.W)));val waiting=RegInit(VecInit(Seq.fill(12)(false.B)))
    val captured=RegInit(VecInit(Seq.fill(12)(0.U(32.W))))
    val compareOut=RegInit(VecInit(Seq.fill(12)(false.B)))
    val wave=Wire(Vec(12,Bool()));val drive=Wire(Vec(12,Bool()))
    for(t<-0 until 3) {
      val count=RegInit(0.U(16.W));val phase=RegInit(0.U(16.W))
      val wasRunning=RegNext(run(t),false.B);val start=run(t) && !wasRunning
      val stopped= !run(t);val advance=run(t) && phase===q(s"prescaler${t}_value")
      val rollover=advance && count===q(s"period${t}_value")
      val nextCount=Mux(stopped || start || rollover,0.U,Mux(advance,count+1.U,count))
      count:=nextCount
      phase:=Mux(stopped || start || advance,0.U,phase+1.U)
      regs.hw(s"counter${t}_value_d"):=count
      val rejected=Wire(Vec(4,Bool()))
      for(c<-4*t until 4*t+4) {
        val mode=q(s"channel_mode${c}_mode");val shadow=q(s"compare${c}_value")
        val apply=regs.hw("apply_channels_pulse")(c)
        val valid=(mode=/=1.U || shadow<=(q(s"period${t}_value")+&1.U)) &&
          (mode=/=2.U || shadow<=q(s"period${t}_value"))
        val commit=apply && valid && permit(t)
        startCompare(c):=Mux(commit,shadow,Mux(waiting(c),queued(c),active(c)))
        val stopNow=stopWrite && !request.req_wdata(t)
        rejected(c%4):=apply && (!valid || !permit(t))
        val adopt=adoptCompare(rollover || start || stopped) && (waiting(c) || commit) && !stopNow
        val nextCompare=Mux(adopt,Mux(commit,shadow,queued(c)),active(c))
        when(commit && !stopNow) {queued(c):=shadow;waiting(c):=true.B}
        when(adopt) {active(c):=nextCompare;waiting(c):=false.B}
        when(stopNow || !permit(t)) {waiting(c):=false.B}
        val capture=run(t) && mode===3.U && Mux(q(s"channel_mode${c}_falling").asBool,falling(c),rising(c))
        when(capture) {captured(c):=timestamp(effectiveTime)}
        val matchCount=compareMatch(advance && !start && nextCount===nextCompare)
        when(stopped || start) {compareOut(c):=false.B}
          .elsewhen(mode===2.U && matchCount) {compareOut(c):= !compareOut(c)}
        events(c):=RegNext(!stopNow && run(t) && (mode===1.U && rollover || mode===2.U && matchCount || capture),false.B)
        wave(c):=run(t) && (mode===1.U && nextCount<nextCompare || mode===2.U && Mux(matchCount,!compareOut(c),compareOut(c)))
        drive(c):=run(t) && permit(t) && q(s"channel_mode${c}_output_enable").asBool && (mode===1.U || mode===2.U)
        regs.hw(s"captured${c}_value_d"):=captured(c);pending(c):=waiting(c)
        if(c<9) dmaEvents(c):=RegNext(rollover && !stopNow,false.B)
        if(formalChecks) {
          val pastValid=RegNext(true.B,false.B)
          val pastActive=RegNext(active(c),0.U)
          val allowedChange=RegNext(rollover || start || stopped,false.B)
          val captureExpected=RegNext(effectiveTime,0.U)
          val capturedEdge=RegNext(capture,false.B)
          when(pastValid && !allowedChange) {assert(active(c)===pastActive)}
          when(capturedEdge) {assert(captured(c)===captureExpected)}
          val expectedDrive=RegNext(drive(c),false.B)
          val expectedValue=RegNext(wave(c) && drive(c),false.B)
          assert(enables(c)===expectedDrive)
          assert(values(c)===expectedValue)
          cover(run(t) && rollover && active(c)=/=0.U)
        }
      }
      errors(t):=RegNext(accept && request.req_write && (invalidStart(t) || configBusy(t) || timeError || loadError),false.B) || rejected.asUInt.orR
    }
    withReset((!executionReset).asAsyncReset) {
      for(c<-0 until 12) {
        values(c):=RegNext(output(wave(c) && drive(c)),false.B)
        enables(c):=RegNext(drive(c),false.B)
      }
    }
    for(t<-0 until 3) {
      val channelIrq=(q("events_channels")(4*t+3,4*t) & q("irq_enable_events")(4*t+3,4*t)).orR
      val errorIrq=q("config_error_timers")(t) && q("irq_enable_events")(12+t)
      val dmaIrq=(0 until 9).filter(_/4==t).map(c=>q("dma_overrun_channels")(c) && q("irq_enable_events")(15+c)).reduce(_||_)
      irqs(t):=RegNext(channelIrq || errorIrq || dmaIrq,false.B)
    }
    clockHold:=holdValue(RegNext(timeRun || run.orR || dmaRequest.orR,false.B))
    if(formalChecks) {
      val past=RegNext(true.B,false.B)
      val expectedTime=RegNext(Mux(!timeRun && regs.hw("time_command_load_pulse").asBool,q("time_preload_value"),effectiveTime),0.U)
      val expectedHold=RegNext(timeRun || run.orR || dmaRequest.orR,false.B)
      when(past) {assert(timeNow===expectedTime);assert(clockHold===expectedHold)}
    }
  }
  pinsOut:=values.asUInt;pinsEnable:=enables.asUInt
  irq:=irqs.asUInt;running:=VecInit((0 until 12).map(c=>run(c/4))).asUInt
  regs.hw("pending_channels_d"):=pending.asUInt;regs.hw("events_channels_set"):=events.asUInt
  regs.hw("config_error_timers_set"):=errors.asUInt
  val dma=Module(new TimerDmaRequests);dma.clk:=clk;dma.reset_n:=reset_n
  val activeChannels=VecInit((0 until 9).map(c=>run(c/4))).asUInt
  val stopChannels=VecInit((0 until 9).map(c=>stopWrite && !request.req_wdata(c/4))).asUInt
  dma.events:=dmaEvents.asUInt;dma.mask:=q("dma_enable_channels") & activeChannels & ~stopChannels
  dma.acknowledge:=dmaAck | regs.hw("dma_ack_channels_pulse")
  dmaRequest:=dma.request;regs.hw("dma_pending_channels_d"):=dma.request
  regs.hw("dma_overrun_channels_set"):=dma.overrun
}
