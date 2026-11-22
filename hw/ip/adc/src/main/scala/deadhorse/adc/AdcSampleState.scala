package deadhorse.adc

import chisel3._

/** Atomic sample publication. Event pulses feed the wrapper's sticky registers. */
class AdcSampleState extends Module {
  protected def sampleUnread(ack: Bool): Bool = true.B
  protected def capture(value: UInt): UInt = value
  val io=IO(new Bundle {
    val sample=Input(Bool());val value=Input(UInt(12.W));val readAck=Input(Bool())
    val raw=Output(UInt(12.W));val count=Output(UInt(32.W));val unread=Output(Bool())
    val overrun=Output(Bool())
  })
  val raw=RegInit(0.U(12.W));val count=RegInit(0.U(32.W));val unread=RegInit(false.B)
  when(io.readAck) {unread:=false.B}
  when(io.sample) {raw:=capture(io.value);count:=count+1.U;unread:=sampleUnread(io.readAck)}
  io.raw:=raw;io.count:=count;io.unread:=unread
  // A simultaneous ACK retires the old sample. The new sample remains unread.
  io.overrun:=io.sample && unread && !io.readAck
}
