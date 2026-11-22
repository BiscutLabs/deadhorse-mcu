package deadhorse.lite_core

import chisel3._
import chisel3.util._
import deadhorse.lib.LocalBus

/** Common service-reset epoch. LocalBus replies occur after their grant edge. */
class LiteBusAdapter(origin: Int=0) extends RawModule {
  require(origin>=0 && origin<8)
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val request=IO(Flipped(Decoupled(new MemoryRequest)))
  val response=IO(Decoupled(new MemoryResponse))
  val bus=IO(Flipped(new LocalBus));val halted=IO(Output(Bool()))
  val busy=IO(Output(Bool()))
  protected def returned(data: UInt): UInt=data
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val idle :: offered :: waiting :: returning :: stopped :: Nil=Enum(5)
    val phase=RegInit(idle);val ready=RegInit(false.B)
    val offeredRequest=RegInit(false.B);val reply=RegInit(false.B)
    val payload=RegInit(0.U.asTypeOf(chiselTypeOf(bus.bits)))
    val result=RegInit(0.U.asTypeOf(new MemoryResponse))
    val stoppedFlag=RegInit(false.B)
    request.ready:=ready;response.valid:=reply;response.bits:=result
    bus.req:=offeredRequest;bus.bits:=payload;halted:=stoppedFlag
    busy:=RegNext(phase=/=idle && phase=/=stopped || request.valid,false.B)
    when(phase===idle) {
      ready:=true.B
      when(request.fire) {
        ready:=false.B
        when(request.bits.operation===Operation.Halt.U) {phase:=stopped;stoppedFlag:=true.B}
          .otherwise {
            payload.addr:=Cat(request.bits.address(31,2),0.U(2.W))
            payload.we:=request.bits.operation===Operation.Write.U
            payload.wdata:=request.bits.data;payload.be:=request.bits.mask;payload.origin:=origin.U
            offeredRequest:=true.B;phase:=offered
          }
      }
    }
    when(phase===offered && bus.gnt) {offeredRequest:=false.B;phase:=waiting}
    when(phase===waiting && bus.rvalid) {
      result.data:=returned(bus.rdata);result.error:=bus.err;reply:=true.B;phase:=returning
    }
    when(phase===returning && response.ready) {reply:=false.B;phase:=idle}
  }
}
