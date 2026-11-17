package deadhorse.lib

import chisel3._

class BusPayload extends Bundle {
  val addr = UInt(32.W)
  val wdata = UInt(32.W)
  val be = UInt(4.W)
  val we = Bool()
  val origin = UInt(3.W)
}

/** Target orientation. Metadata is supplied by trusted integration logic. */
class LocalBus extends Bundle {
  val req = Input(Bool())
  val bits = Input(new BusPayload)
  val gnt = Output(Bool())
  val rvalid = Output(Bool())
  val rdata = Output(UInt(32.W))
  val err = Output(Bool())
}
