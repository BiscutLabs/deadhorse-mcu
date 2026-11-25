package deadhorse.lib

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage

/** Independent sequence oracle; clocks may stop and cancellation is arbitrary.
  * No fairness or DUT-state assumptions. This checks digital safety only. */
class CdcEpochFormal(variant: String) extends RawModule {
  val wc=IO(Input(Clock()));val rc=IO(Input(Clock()));val observe=IO(Input(Clock()))
  val reset_n=IO(Input(Bool()));val cancel_n=IO(Input(Bool()))
  val push=IO(Input(Bool()));val pop=IO(Input(Bool()));val data=IO(Input(UInt(8.W)))
  val wr=Module(new ResetRelease);val rd=Module(new ResetRelease)
  wr.clk:=wc;rd.clk:=rc;wr.reset_n:=reset_n;rd.reset_n:=reset_n
  val e=Module[CdcEpoch](if(variant=="early") new CdcEpoch {
    override protected def admitted(local: Bool,peer: Bool): Bool=local
  } else new CdcEpoch)
  e.aClock:=wc;e.bClock:=rc;e.aReset_n:=wr.released;e.bReset_n:=rd.released
  if(variant=="delayed") {
    val s=Module(new CdcSync(1));s.clk:=rc;s.reset_n:=rd.released;s.in:=cancel_n.asUInt
    e.cancel_n:=s.out.asBool
  } else e.cancel_n:=cancel_n
  val f=Module[CdcFifo](if(variant=="corrupt") new CdcFifo(8,qualifiedResets=true,synchronousFlush=true) {
    override protected def makeReader(): CdcRead=new CdcRead(8,2,withClear=true) {
      override protected def capture(v: UInt): UInt=v ^ 1.U
    }
  } else new CdcFifo(8,qualifiedResets=true,synchronousFlush=true))
  f.writeClock:=wc;f.readClock:=rc;f.writeReset_n:=wr.released;f.readReset_n:=rd.released
  f.writeOpen.get:=e.aOpen;f.readOpen.get:=e.bOpen
  f.push:=push;f.pop:=pop;f.in:=data
  val cleared=(!(reset_n && cancel_n)).asAsyncReset
  val put=push && f.ready;val take=pop && f.valid
  val inCount=withClockAndReset(wc,cleared) {RegInit(0.U(2.W))}
  val outCount=withClockAndReset(rc,cleared) {RegInit(0.U(2.W))}
  val words=withClockAndReset(wc,cleared) {Reg(Vec(2,UInt(8.W)))}
  val wSeen=withClockAndReset(wc,cleared) {RegNext(true.B,false.B)}
  val rSeen=withClockAndReset(rc,cleared) {RegNext(true.B,false.B)}
  val used=inCount-outCount
  withClockAndReset(wc,cleared) {
    when(put) {words(inCount(0)):=data;inCount:=inCount+1.U}
    if(variant=="cover") {cover(used===2.U);cover(put && inCount===3.U)} else {
      assert(used<=2.U,"EPOCH_CAPACITY")
      assert(!put || used<2.U,"EPOCH_NO_OVERFLOW")
    }
  }
  withClockAndReset(rc,cleared) {
    when(take) {outCount:=outCount+1.U}
    val held=RegNext(f.valid && !pop,false.B);val old=RegNext(f.out)
    if(variant=="cover") {cover(take && outCount===3.U);cover(held && take)} else {
      assert(!f.valid || used=/=0.U,"EPOCH_NO_PHANTOM")
      assert(!f.valid || f.out===words(outCount(0)),"EPOCH_DATA")
      assert(!held || f.valid && f.out===old,"EPOCH_HELD")
    }
  }
  withClockAndReset(observe,false.B) {
    if(variant=="cover") {
      cover(e.aOpen && e.bOpen)
      cover(!cancel_n && !f.ready && !f.valid)
    } else {
      assert(reset_n && cancel_n || !f.ready && !f.valid,"EPOCH_IMMEDIATE_CANCEL")
      assert(!e.aOpen || wSeen && rSeen,"EPOCH_A_ACK")
      assert(!e.bOpen || wSeen && rSeen,"EPOCH_B_ACK")
    }
  }
}

object EmitCdcEpochFormal extends App {
  for(v<-Seq("correct","early","delayed","corrupt","cover"))
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new CdcEpochFormal(v)),
      Array("--target-dir",s"${args(0)}/$v"),
      Array("--disable-all-randomization","--verification-flavor=immediate","--lower-to-core","-strip-debug-info"))
}
