package deadhorse.top
import chisel3._
import chisel3.util._
import deadhorse.lib._

/** Registered split before a leaf debug bridge; all ordinary addresses retain
  * their existing fabric decode/ownership policy. One accepted request at a time. */
class SocDebugRoute(base: BigInt=0x10000,size: BigInt=0x1000) extends RawModule {
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new LocalBus)
  val debug=IO(Flipped(new LocalBus));val ordinary=IO(Flipped(new LocalBus));val busy=IO(Output(Bool()))
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val idle :: grant :: offer :: waiting :: reply :: Nil=Enum(5)
    val state=RegInit(idle);val packet=RegInit(0.U.asTypeOf(new BusPayload));val selected=RegInit(false.B)
    val data=RegInit(0.U(32.W));val error=RegInit(false.B)
    bus.gnt:=state===grant;bus.rvalid:=state===reply;bus.rdata:=data;bus.err:=error;busy:=state=/=idle
    debug.bits:=packet;ordinary.bits:=packet
    debug.req:=state===offer && selected;ordinary.req:=state===offer && !selected
    when(state===idle && bus.req) {state:=grant}
    when(state===grant) {
      when(bus.req) {packet:=bus.bits;selected:=bus.bits.addr>=base.U && bus.bits.addr<(base+size).U;state:=offer}
        .otherwise {state:=idle}
    }
    when(state===offer && Mux(selected,debug.gnt,ordinary.gnt)) {state:=waiting}
    when(state===waiting && Mux(selected,debug.rvalid,ordinary.rvalid)) {
      data:=Mux(selected,debug.rdata,ordinary.rdata);error:=Mux(selected,debug.err,ordinary.err);state:=reply
    }
    when(state===reply) {state:=idle}
    assert(!(debug.req && ordinary.req))
  }
}
