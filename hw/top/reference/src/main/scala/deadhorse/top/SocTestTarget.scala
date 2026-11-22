package deadhorse.top

import chisel3._
import chisel3.util._
import deadhorse.lib.LocalBus

/** Verification-only QEMU marker/finisher/MSIP target, behind the real fabric.
  * No host interception, memory responder or instruction-result substitution.
  */
class SocTestTarget(base: BigInt, interrupt: Boolean) extends RawModule {
  val clk=IO(Input(Clock())); val reset_n=IO(Input(Bool()))
  val bus=IO(new LocalBus); val msip=IO(Output(Bool()))
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val pending=RegInit(false.B); val grant=RegInit(false.B)
    val reply=RegInit(false.B); val result=RegInit(0.U(32.W)); val bad=RegInit(false.B)
    val software=RegInit(false.B)
    bus.gnt:=grant; bus.rvalid:=reply; bus.rdata:=result; bus.err:=bad; msip:=software
    grant:=false.B; reply:=false.B
    when(!pending && !reply && bus.req) { grant:=true.B; pending:=true.B }
    val fire=grant && bus.req
    when(fire) {
      val valid=bus.bits.origin===1.U && !bus.bits.addr(1,0).orR &&
        bus.bits.addr>=base.U && bus.bits.addr<(base+16).U
      reply:=true.B; pending:=false.B; bad:= !valid
      result:=Mux(valid && !bus.bits.we,software.asUInt,0.U)
      if(interrupt) {
        when(valid && bus.bits.addr===base.U && bus.bits.we && bus.bits.be(0)) { software:=bus.bits.wdata(0) }
      }
    }
    assert(!reply || !grant)
    assert(!fire || pending)
  }
}
