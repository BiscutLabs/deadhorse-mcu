package deadhorse.debug

import chisel3._
import chisel3.util._

/** Input-only sequence oracle for the actual depth-two bridge FIFO.
  * Counters describe accepted interface transfers, not DUT pointers.
  * Both domains reset on the actual transport reset, including abort.
  */
class DebugFifoOracle(width: Int) extends RawModule {
  val wc=IO(Input(Clock())); val rc=IO(Input(Clock()))
  val wn=IO(Input(Bool())); val rn=IO(Input(Bool()))
  val push=IO(Input(Bool())); val data=IO(Input(UInt(width.W)))
  val ready=IO(Input(Bool())); val pop=IO(Input(Bool()))
  val valid=IO(Input(Bool())); val result=IO(Input(UInt(width.W)))
  val reset=(!(wn && rn)).asAsyncReset
  val written=withClockAndReset(wc,reset){RegInit(0.U(2.W))}
  val read=withClockAndReset(rc,reset){RegInit(0.U(2.W))}
  val saved=withClockAndReset(wc,reset){Reg(Vec(2,UInt(width.W)))}
  val occupancy=written-read
  withClockAndReset(wc,reset) {
    when(push && ready) {saved(written(0)):=data;written:=written+1.U}
    assert(occupancy<=2.U,"FIFO_CAPACITY")
    assert(!(push && ready) || occupancy<2.U,"FIFO_NO_OVERWRITE")
  }
  withClockAndReset(rc,reset) {
    when(pop && valid) {read:=read+1.U}
    assert(!valid || occupancy=/=0.U,"FIFO_NO_UNWRITTEN_READ")
    assert(!valid || result===saved(read(0)),"FIFO_ORDERED_DATA")
  }
}

object EmitDebugFifoOracle extends App {
  for(width<-Seq(72,33)) _root_.circt.stage.ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new DebugFifoOracle(width)),Array("--target-dir",s"${args(0)}/w$width"),
    Array("--disable-all-randomization","--disable-opt","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
