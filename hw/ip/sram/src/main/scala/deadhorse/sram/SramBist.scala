package deadhorse.sram

import chisel3._
import chisel3.util._
import deadhorse.lib._

/** Custom DMI target. Transport reset flushes replies/commands which have not
  * reached RegBlock; it never resets the independent destructive-test owner. */
class SramDmi(json: String) extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val epoch_n=IO(Input(Bool()))
  val request=IO(Flipped(Decoupled(UInt(41.W))));val response=IO(Decoupled(UInt(34.W)))
  val start=IO(Output(Bool()));val keyed=IO(Output(Bool()))
  val busy=IO(Input(Bool()));val done=IO(Input(Bool()));val failed=IO(Input(Bool()))
  val rejected=IO(Input(Bool()));val resetAck=IO(Input(Bool()))
  val failAddress=IO(Input(UInt(32.W)));val result=IO(Input(new MarchResult))
  val regs=Module(new RegBlock(json));regs.clk:=clk;regs.rst_n:=reset_n
  val commandLive=withClockAndReset(clk,(!(reset_n && epoch_n)).asAsyncReset) {
    val live=RegInit(false.B);when(request.fire) {live:=true.B};live
  }
  start:=regs.hw("command_key_we").asBool && commandLive && epoch_n
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
    request.ready:=state===idle;response.valid:=state===reply;response.bits:=value
    regs.bus.req_valid:=state===issue;regs.bus.req_write:=payload(33,32)===2.U
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
  }
}

/** Owns the test reset from authorized start through remote port release.
  * epoch_n includes cold and external-pin reset, never ndmreset/testHold.
  * All cross-domain data uses the shared FIFO, levels the shared synchronizer. */
class SramBist(mainWords: Int=4096,aonWords: Int=768) extends RawModule {
  val clk=IO(Input(Clock()));val aonClock=IO(Input(Clock()));val epoch_n=IO(Input(Bool()))
  val start=IO(Input(Bool()));val keyed=IO(Input(Bool()));val authorized=IO(Input(Bool()))
  val mainReset_n=IO(Input(Bool()));val aonReset_n=IO(Input(Bool()))
  val main=IO(new SramPort(12));val aon=IO(new SramPort(12))
  val mainOwn=IO(Output(Bool()));val aonOwn=IO(Output(Bool()))
  val resetHold=IO(Output(Bool()));val busy=IO(Output(Bool()));val done=IO(Output(Bool()))
  val failed=IO(Output(Bool()));val rejected=IO(Output(Bool()));val resetAck=IO(Output(Bool()))
  val failAddress=IO(Output(UInt(32.W)));val result=IO(Output(new MarchResult))
  def release(clock: Clock): Bool={
    val r=Module(new ResetRelease);r.clk:=clock;r.reset_n:=epoch_n;r.released
  }
  val mainUp=release(clk);val aonUp=release(aonClock)
  def sync(value: Bool,clock: Clock,reset: Bool): Bool={
    val s=Module(new CdcSync(1));s.clk:=clock;s.reset_n:=reset;s.in:=value.asUInt;s.out.asBool
  }
  // Synchronize asserted reset (not deasserted reset) so resetAck starts false.
  val remoteReset=sync(!aonReset_n,clk,mainUp)
  val ready= !mainReset_n && remoteReset
  resetAck:=ready
  val run=WireDefault(false.B)
  val remoteRun=sync(run,aonClock,aonUp)
  val m=Module(new SramMarch(mainWords));val a=Module(new SramMarch(aonWords))
  m.clk:=clk;m.reset_n:=mainUp;m.run:=run;m.permitted:= !mainReset_n
  a.clk:=aonClock;a.reset_n:=aonUp;a.run:=remoteRun;a.permitted:= !aonReset_n
  main<>m.memory;aon<>a.memory
  mainOwn:=run;aonOwn:=remoteRun
  val remoteBusy=sync(a.busy,clk,mainUp)
  val fifo=Module(new CdcFifo((new MarchResult).getWidth))
  fifo.writeClock:=aonClock;fifo.readClock:=clk
  fifo.writeReset_n:=epoch_n;fifo.readReset_n:=epoch_n
  withClockAndReset(aonClock,(!aonUp).asAsyncReset) {
    val sent=RegInit(false.B)
    fifo.push:=a.done && !sent;fifo.in:=a.result.asUInt
    when(fifo.push && fifo.ready) {sent:=true.B}
    when(!remoteRun) {sent:=false.B}
  }
  withClockAndReset(clk,(!mainUp).asAsyncReset) {
    val idle :: running :: relinquish :: Nil=Enum(3)
    val state=RegInit(idle);val remoteDone=RegInit(false.B)
    val remoteResult=RegInit(0.U.asTypeOf(new MarchResult))
    val finished=RegInit(false.B);val bad=RegInit(false.B);val denied=RegInit(false.B)
    val record=RegInit(0.U.asTypeOf(new MarchResult));val address=RegInit(0.U(32.W))
    run:=state===running;resetHold:=state=/=idle;busy:=state=/=idle
    done:=finished;failed:=bad;rejected:=denied;result:=record;failAddress:=address
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
    assert(!main.enable || resetHold && !mainReset_n)
    // ready is delayed admission evidence and can transiently reflect a prior
    // reset release. Ownership itself must hold both actual service resets.
    assert(state===idle || !mainReset_n && !aonReset_n)
    assert(!finished || state===idle)
  }
}
