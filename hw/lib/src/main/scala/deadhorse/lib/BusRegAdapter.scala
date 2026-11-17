package deadhorse.lib

import chisel3._
import chisel3.util._

/** Registered Ibex-style local bus to the already-qualified register protocol. */
class BusRegAdapter(addressWidth: Int, base: BigInt, owner: Int) extends RawModule {
  require(addressWidth >= 2 && addressWidth <= 32 && owner >= 0 && owner < 8)
  require(base % (BigInt(1)<<addressWidth) == 0)
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val bus = IO(new LocalBus); val registers = IO(Flipped(new RegBus(addressWidth)))
  withClockAndReset(clk, (!reset_n).asAsyncReset) {
    val idle :: sending :: waiting :: Nil = Enum(3)
    val phase = RegInit(idle)
    val ready = RegInit(false.B); val request = RegInit(false.B)
    val payload = Reg(new BusPayload)
    val valid = RegInit(false.B); val result = RegInit(0.U(32.W)); val error = RegInit(false.B)
    bus.gnt := ready; bus.rvalid := valid; bus.rdata := result; bus.err := error
    registers.req_valid := request; registers.req_addr := payload.addr(addressWidth-1,0)
    registers.req_write := payload.we; registers.req_wdata := payload.wdata; registers.req_wstrb := payload.be
    registers.rsp_ready := true.B // constant consumer; no combinational backpressure path
    valid := false.B
    when(phase === idle) {
      ready := true.B
      when(bus.req && ready) {
        ready := false.B; payload := bus.bits
        val inWindow = if(addressWidth==32) true.B else bus.bits.addr(31,addressWidth) === (base>>addressWidth).U
        when(!inWindow || bus.bits.origin =/= owner.U) {
          valid := true.B; result := 0.U; error := true.B
        }.otherwise { request := true.B; phase := sending }
      }
    }
    when(phase === sending && registers.req_ready) { request := false.B; phase := waiting }
    when(phase === waiting && registers.rsp_valid) {
      valid := true.B; result := registers.rsp_rdata; error := registers.rsp_error; phase := idle
    }
  }
}
