package deadhorse.adc

import chisel3._
import _root_.circt.stage.ChiselStage

class AdcPublicationFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val sample=IO(Input(Bool()));val value=IO(Input(UInt(12.W)));val ack=IO(Input(Bool()))
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val d=Module[AdcSampleState](variant match {
      case "corrupt" => new AdcSampleState {override protected def capture(v: UInt): UInt=v^1.U}
      case "ack" => new AdcSampleState {override protected def sampleUnread(a: Bool): Bool= !a}
      case _ => new AdcSampleState
    })
    d.io.sample:=sample;d.io.value:=value;d.io.readAck:=ack
    val past=RegNext(true.B,false.B)
    val oldSample=RegNext(sample,false.B);val oldAck=RegNext(ack,false.B)
    val oldValue=RegNext(value,0.U);val oldRaw=RegNext(d.io.raw,0.U)
    val oldCount=RegNext(d.io.count,0.U);val oldUnread=RegNext(d.io.unread,false.B)
    if(variant=="cover") {
      cover(sample && ack && d.io.unread)
      cover(d.io.overrun)
      cover(!d.io.unread && d.io.count=/=0.U)
    } else {
      when(past) {
        assert(d.io.raw===Mux(oldSample,oldValue,oldRaw))
        assert(d.io.count===(oldCount+oldSample.asUInt))
        assert(d.io.unread===(oldSample || (oldUnread && !oldAck)))
      }
      assert(d.io.overrun===(sample && d.io.unread && !ack))
    }
  }
}
object EmitAdcPublicationFormal extends App {
  require(args.length==1)
  for(v<-Seq("correct","corrupt","ack","cover")) ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new AdcPublicationFormal(v)),Array("--target-dir",s"${args(0)}/$v"),
    Array("--disable-all-randomization","--disable-opt","--lint-static-asserts=false",
      "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
