package deadhorse.sram

import chisel3._
import chisel3.util._
import deadhorse.lib._

/** Custom DMI target. Transport reset flushes replies/commands which have not
  * reached RegBlock; it never resets the independent destructive-test owner. */
class SramDmi(json: String) extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val epoch_n=IO(Input(Bool()))
  val clear=IO(Input(Bool()))
  val request=IO(Flipped(Decoupled(UInt(41.W))));val response=IO(Decoupled(UInt(34.W)))
  val start=IO(Output(Bool()));val keyed=IO(Output(Bool()))
  val busy=IO(Input(Bool()));val done=IO(Input(Bool()));val failed=IO(Input(Bool()))
  val rejected=IO(Input(Bool()));val resetAck=IO(Input(Bool()))
  val failAddress=IO(Input(UInt(32.W)));val result=IO(Input(new MarchResult))
  val clearing=clear
  val regs=Module(new RegBlock(json,withClear=true));regs.clk:=clk;regs.rst_n:=reset_n;regs.clear.get:=clearing
  val commandLive=withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val live=RegInit(false.B);when(request.fire) {live:=true.B};when(clearing || !epoch_n) {live:=false.B};live
  }
  start:=regs.hw("command_key_we").asBool && commandLive && !clearing && epoch_n
  keyed:=regs.hw("command_key_wdata")==="h42535431".U
  regs.hw("status_busy_d"):=busy;regs.hw("status_done_d"):=done
  regs.hw("status_failed_d"):=failed;regs.hw("status_rejected_d"):=rejected
  regs.hw("status_reset_ack_d"):=resetAck
  regs.hw("fail_address_value_d"):=failAddress
  regs.hw("expected_value_d"):=result.expected;regs.hw("observed_value_d"):=result.observed
  regs.hw("phase_value_d"):=result.phase
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val idle :: issue :: waitReply :: reply :: Nil=Enum(4)
    val state=RegInit(idle);val payload=Reg(UInt(41.W));val value=RegInit(0.U(34.W))
    request.ready:=state===idle && !clearing;response.valid:=state===reply && !clearing;response.bits:=value
    regs.bus.req_valid:=state===issue && !clearing;regs.bus.req_write:=payload(33,32)===2.U
    regs.bus.req_addr:=Cat(payload(37,34),0.U(2.W))
    regs.bus.req_wdata:=payload(31,0);regs.bus.req_wstrb:=15.U;regs.bus.rsp_ready:=state===waitReply
    when(request.fire) {
      payload:=request.bits
      when(request.bits(33,32)===1.U || request.bits(33,32)===2.U) {state:=issue}
        .otherwise {value:=2.U;state:=reply}
    }
    when(regs.bus.req_valid && regs.bus.req_ready) {state:=waitReply}
    when(regs.bus.rsp_valid && regs.bus.rsp_ready) {
      value:=Cat(regs.bus.rsp_rdata,Mux(regs.bus.rsp_error,2.U(2.W),0.U(2.W)));state:=reply
    }
    when(response.fire) {state:=idle}
    when(clearing) {state:=idle;value:=0.U}
  }
}

/** Owns the test reset from authorized start through remote port release.
  * epoch_n includes cold and external-pin reset, never ndmreset/testHold.
  * All cross-domain data uses the shared FIFO, levels the shared synchronizer. */
class SramBist(mainWords: Int=4096,aonWords: Int=768,qualifiedResets: Boolean=false,sharedPinFence: Boolean=false) extends RawModule {
  val clk=IO(Input(Clock()));val aonClock=IO(Input(Clock()));val epoch_n=IO(Input(Bool()))
  val cold_n=IO(Input(Bool()))
  val domainReset=if(qualifiedResets) Some(IO(Input(new Bundle {val main=Bool();val aon=Bool()}))) else None
  val pinFence=if(sharedPinFence) Some(IO(Input(new Bundle {val main=Bool();val aon=Bool()}))) else None
  require(!sharedPinFence || qualifiedResets)
  val commandOpen=IO(Output(Bool()))
  val start=IO(Input(Bool()));val keyed=IO(Input(Bool()));val authorized=IO(Input(Bool()))
  val mainReset_n=IO(Input(Bool()));val aonReset_n=IO(Input(Bool()))
  val main=IO(new SramPort(12));val aon=IO(new SramPort(12))
  val mainOwn=IO(Output(Bool()));val aonOwn=IO(Output(Bool()))
  val resetHold=IO(Output(Bool()));val busy=IO(Output(Bool()));val done=IO(Output(Bool()))
  val failed=IO(Output(Bool()));val rejected=IO(Output(Bool()));val resetAck=IO(Output(Bool()))
  val failAddress=IO(Output(UInt(32.W)));val result=IO(Output(new MarchResult))
  def release(clock: Clock): Bool={
    val r=Module(new ResetRelease);r.clk:=clock;r.reset_n:=cold_n;r.released
  }
  val mainUp=domainReset.map(_.main).getOrElse(release(clk))
  val aonUp=domainReset.map(_.aon).getOrElse(release(aonClock))
  val openings=pinFence.map(p=>(p.main,p.aon)).getOrElse {
    val fence=Module(new CdcEpoch)
    fence.aClock:=clk;fence.bClock:=aonClock;fence.aReset_n:=mainUp;fence.bReset_n:=aonUp;fence.cancel_n:=epoch_n
    (fence.aOpen,fence.bOpen)
  }
  val(mainOpen,aonOpen)=openings;commandOpen:=mainOpen
  def sync(value: Bool,clock: Clock,reset: Bool,open: Bool): Bool={
    val s=Module(new CdcSync(1,withClear=true));s.clk:=clock;s.reset_n:=reset
    s.clear.get:= !open;s.in:=value.asUInt;s.out.asBool
  }
  // Synchronize asserted reset (not deasserted reset) so resetAck starts false.
  val remoteReset=sync(!aonReset_n,clk,mainUp,mainOpen)
  val ready=mainOpen && !mainReset_n && remoteReset
  resetAck:=ready
  val run=WireDefault(false.B)
  val remoteRun=aonOpen && sync(run,aonClock,aonUp,aonOpen)
  val m=Module(new SramMarch(mainWords,withClear=true));val a=Module(new SramMarch(aonWords,withClear=true))
  m.clear.get:= !mainOpen;a.clear.get:= !aonOpen
  m.clk:=clk;m.reset_n:=mainUp;m.run:=run;m.permitted:= !mainReset_n
  a.clk:=aonClock;a.reset_n:=aonUp;a.run:=remoteRun;a.permitted:= !aonReset_n
  main<>m.memory;aon<>a.memory
  mainOwn:=run;aonOwn:=remoteRun
  val remoteBusy=sync(a.busy,clk,mainUp,mainOpen)
  val fifo=Module(new CdcFifo((new MarchResult).getWidth,qualifiedResets=true,synchronousFlush=true))
  fifo.writeClock:=aonClock;fifo.readClock:=clk
  fifo.writeReset_n:=aonUp;fifo.readReset_n:=mainUp
  fifo.writeOpen.get:=aonOpen;fifo.readOpen.get:=mainOpen
  withClockAndReset(aonClock,(!aonUp).asAsyncReset) {
    val sent=RegInit(false.B)
    fifo.push:=a.done && !sent;fifo.in:=a.result.asUInt
    when(fifo.push && fifo.ready) {sent:=true.B}
    when(!remoteRun) {sent:=false.B}
    when(!aonOpen) {sent:=false.B}
  }
  withClockAndReset(clk,(!mainUp).asAsyncReset) {
    val idle :: running :: relinquish :: Nil=Enum(3)
    val state=RegInit(idle);val remoteDone=RegInit(false.B)
    val remoteResult=RegInit(0.U.asTypeOf(new MarchResult))
    val finished=RegInit(false.B);val bad=RegInit(false.B);val denied=RegInit(false.B)
    val record=RegInit(0.U.asTypeOf(new MarchResult));val address=RegInit(0.U(32.W))
    run:=mainOpen && state===running;resetHold:=mainOpen && state=/=idle;busy:=resetHold
    done:=mainOpen && finished;failed:=mainOpen && bad;rejected:=mainOpen && denied;result:=record;failAddress:=address
    fifo.pop:=fifo.valid
    when(state===running && fifo.valid) {
      remoteResult:=fifo.out.asTypeOf(new MarchResult);remoteDone:=true.B
    }
    when(start) {
      when(keyed && authorized && ready && state===idle && fifo.readUp && !fifo.valid) {
        state:=running;remoteDone:=false.B;finished:=false.B;bad:=false.B;denied:=false.B
        record:=0.U.asTypeOf(record);address:=0.U
      }.otherwise {denied:=true.B}
    }
    when(state===running && m.done && remoteDone && remoteBusy) {
      bad:=m.result.failed || remoteResult.failed
      record:=Mux(m.result.failed,m.result,remoteResult)
      address:=Mux(m.result.failed,"h20000000".U+(m.result.address<<2),
        Mux(remoteResult.failed,"h30000000".U+(remoteResult.address<<2),0.U))
      state:=relinquish
    }
    when(state===relinquish && !m.busy && !remoteBusy) {state:=idle;finished:=true.B}
    when(!mainOpen) {
      state:=idle;remoteDone:=false.B;remoteResult:=0.U.asTypeOf(remoteResult)
      finished:=false.B;bad:=false.B;denied:=false.B;record:=0.U.asTypeOf(record);address:=0.U
    }
    assert(!main.enable || resetHold && !mainReset_n)
    // ready is delayed admission evidence and can transiently reflect a prior
    // reset release. Ownership itself must hold both actual service resets.
    assert(!resetHold || !mainReset_n && !aonReset_n)
    assert(!finished || state===idle)
  }
}
