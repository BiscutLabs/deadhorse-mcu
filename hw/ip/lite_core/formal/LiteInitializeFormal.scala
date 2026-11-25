package deadhorse.lite_core

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage

/** Local registered HOLD initialization versus the former client reset.
  * No memory/protocol or ISA assumptions: identical arbitrary ports drive both.
  * The producer registers clear in this clock domain, as the boot owner does.
  */
class LiteInitializeFormal(fault: Boolean=false,covers: Boolean=false) extends Module {
  val initializeRequest=IO(Input(Bool()));val start=IO(Input(Bool()));val entry=IO(Input(UInt(32.W)))
  val irq=IO(Input(Bool()));val debugRequest=IO(Input(Bool()));val debugAllow=IO(Input(Bool()));val debugStop=IO(Input(Bool()))
  val ready=IO(Input(Bool()));val response=IO(Input(new MemoryResponse));val valid=IO(Input(Bool()))
  val initialize=RegNext(initializeRequest,false.B)
  val old=Module(new LiteCore(withDebug=true))
  val now=Module[LiteCore](if(fault) new LiteCore(withDebug=true,withInitialize=true) {
    override protected def initializedRegister(index: Int): UInt=if(index==1) 1.U(32.W) else 0.U(32.W)
  } else new LiteCore(withDebug=true,withInitialize=true))
  for(d<-Seq(old,now)) {
    d.clk:=clock;d.start:=start;d.entry:=entry;d.irq:=irq
    d.debug.get.request:=debugRequest;d.debug.get.allowEntry:=debugAllow;d.debug.get.stop:=debugStop
    d.request.ready:=ready;d.response.valid:=valid;d.response.bits:=response
  }
  old.reset_n:= !reset.asBool && !initialize
  now.reset_n:= !reset.asBool;now.initialize.get:=initialize
  val seen=RegInit(false.B);when(initialize) {seen:=true.B}
  when(!initialize) {
    if(covers) {
      cover(seen && now.trace.valid)
      cover(seen && now.debug.get.mode)
    } else {
      assert(now.request.asUInt===old.request.asUInt,"LITE_INIT_REQUEST")
      assert(now.response.ready===old.response.ready,"LITE_INIT_RESPONSE")
      assert(now.trace.asUInt===old.trace.asUInt,"LITE_INIT_TRACE")
      assert(now.rvfi.asUInt===old.rvfi.asUInt,"LITE_INIT_RVFI")
      assert(now.halted===old.halted && now.sleeping===old.sleeping && now.clockHold===old.clockHold,"LITE_INIT_STATUS")
      assert(now.debug.get.mode===old.debug.get.mode && now.debug.get.stopped===old.debug.get.stopped,"LITE_INIT_DEBUG")
      assert(now.interruptTaken===old.interruptTaken,"LITE_INIT_IRQ")
    }
  }
}

object EmitLiteInitializeFormal extends App {
  for(v<-Seq("correct","corrupt","cover"))
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new LiteInitializeFormal(v=="corrupt",v=="cover")),
      Array("--target-dir",s"${args(0)}/$v"),
      Array("--disable-all-randomization","--verification-flavor=immediate","--lower-to-core","-strip-debug-info"))
}
