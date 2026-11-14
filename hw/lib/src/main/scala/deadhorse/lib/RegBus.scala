package deadhorse.lib

import chisel3._

/** Target view; use Flipped(new RegBus(addressWidth)) for an initiator. */
class RegBus(val addressWidth: Int) extends Bundle {
  val req_valid = Input(Bool())
  val req_ready = Output(Bool())
  val req_write = Input(Bool())
  val req_addr = Input(UInt(addressWidth.W))
  val req_wdata = Input(UInt(32.W))
  val req_wstrb = Input(UInt(4.W))
  val rsp_valid = Output(Bool())
  val rsp_ready = Input(Bool())
  val rsp_rdata = Output(UInt(32.W))
  val rsp_error = Output(Bool())
}
