package deadhorse.lib

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import scala.collection.mutable

class EpochFifoTest(delayed: Boolean=false,missingAck: Boolean=false) extends RawModule {
  val wc=IO(Input(Bool()));val rc=IO(Input(Bool()));val reset_n=IO(Input(Bool()));val cancel_n=IO(Input(Bool()))
  val push=IO(Input(Bool()));val pop=IO(Input(Bool()));val data=IO(Input(UInt(8.W)))
  val ready=IO(Output(Bool()));val valid=IO(Output(Bool()));val out=IO(Output(UInt(8.W)))
  val wu=IO(Output(Bool()));val ru=IO(Output(Bool()))
  val wr=Module(new ResetRelease);val rd=Module(new ResetRelease)
  wr.clk:=wc.asClock;rd.clk:=rc.asClock;wr.reset_n:=reset_n;rd.reset_n:=reset_n
  val epoch=Module[CdcEpoch](if(missingAck) new CdcEpoch {
    override protected def admitted(local: Bool,peer: Bool): Bool=local
  } else new CdcEpoch)
  epoch.aClock:=wc.asClock;epoch.bClock:=rc.asClock;epoch.aReset_n:=wr.released;epoch.bReset_n:=rd.released
  if(delayed) {
    val bad=Module(new CdcSync(1));bad.clk:=rc.asClock;bad.reset_n:=reset_n;bad.in:=cancel_n.asUInt
    epoch.cancel_n:=bad.out.asBool
  } else epoch.cancel_n:=cancel_n
  val fifo=Module(new CdcFifo(8,qualifiedResets=true,synchronousFlush=true))
  fifo.writeClock:=wc.asClock;fifo.readClock:=rc.asClock
  fifo.writeReset_n:=wr.released;fifo.readReset_n:=rd.released
  fifo.writeOpen.get:=epoch.aOpen;fifo.readOpen.get:=epoch.bOpen
  fifo.push:=push;fifo.in:=data;fifo.pop:=pop
  ready:=fifo.ready;valid:=fifo.valid;out:=fifo.out;wu:=fifo.writeUp;ru:=fifo.readUp
}

class CdcEpochSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t41/cdc-epoch").toAbsolutePath
  }
  private def exercise(d: EpochFifoTest): Unit={
    def high(x: Bool)=x.peek().litToBoolean
    val q=mutable.Queue.empty[Int];val random=new scala.util.Random(4101)
    var accepted=0;var consumed=0
    d.wc.poke(false.B);d.rc.poke(false.B);d.reset_n.poke(false.B);d.cancel_n.poke(true.B)
    d.push.poke(false.B);d.pop.poke(false.B);d.data.poke(0.U)
    def step(w: Boolean,r: Boolean,put: Boolean=false,take: Boolean=false): Unit={
      val data=random.nextInt(256);d.data.poke(data.U);d.push.poke(put.B);d.pop.poke(take.B)
      if(high(d.valid)) {assert(q.nonEmpty,"EPOCH unexpected data");assert(d.out.peek().litValue==q.front,"EPOCH corrupt data")}
      if(r && take && high(d.valid)) {q.dequeue();consumed+=1}
      if(w && put && high(d.ready)) {q.enqueue(data);accepted+=1}
      d.wc.poke(w.B);d.rc.poke(r.B);d.valid.peek()
      d.wc.poke(false.B);d.rc.poke(false.B);d.valid.peek()
      assert(q.size<=2,"EPOCH overflow")
    }
    for(_<-0 until 4)step(true,true)
    d.reset_n.poke(true.B)
    for(_<-0 until 24)step(true,true)
    assert(high(d.ready))
    step(true,false,put=true)
    for(_<-0 until 12)step(true,true)
    assert(high(d.valid) && q.size==1)
    // A complete cancellation pulse with neither clock running must be retained.
    d.cancel_n.poke(false.B);q.clear()
    assert(!high(d.valid) && !high(d.ready),"EPOCH cancellation was delayed")
    d.cancel_n.poke(true.B)
    for(_<-0 until 16) {step(true,false);assert(!high(d.ready) && !high(d.valid),"EPOCH reopened before stopped peer cleared")}
    for(_<-0 until 24)step(true,true)
    assert(high(d.ready) && !high(d.valid))
    // Reverse skew: neither endpoint may reopen while the writer is stopped.
    d.cancel_n.poke(false.B);q.clear();d.valid.peek();d.cancel_n.poke(true.B)
    for(_<-0 until 16) {step(false,true);assert(!high(d.wu) && !high(d.ru),"EPOCH reopened before stopped writer cleared")}
    for(_<-0 until 24)step(true,true)
    assert(high(d.wu) && high(d.ru))
    // A second event cancels an incomplete reopening, including peer history.
    d.cancel_n.poke(false.B);d.valid.peek();d.cancel_n.poke(true.B)
    step(true,true);step(true,true);step(true,false)
    d.cancel_n.poke(false.B);d.valid.peek();d.cancel_n.poke(true.B)
    for(_<-0 until 16) {step(true,false);assert(!high(d.wu) && !high(d.ru),"EPOCH repeated cancel lost peer acknowledgement")}
    for(_<-0 until 24)step(true,true)
    assert(high(d.wu) && high(d.ru))
    for(i<-0 until 700) {
      if(i%89==0) {d.cancel_n.poke(false.B);q.clear();assert(!high(d.valid) && !high(d.ready));d.cancel_n.poke(true.B)}
      step(random.nextBoolean(),i%37>7 && random.nextBoolean(),random.nextBoolean(),random.nextBoolean())
    }
    for(_<-0 until 40)step(true,true,take=true)
    assert(q.isEmpty && !high(d.valid));assert(accepted>20 && consumed>10)
  }
  test("shared epoch flush preserves queued-byte order and stopped-clock cancellation") {
    simulateRaw(new EpochFifoTest)(exercise)
  }
  test("epoch oracle rejects a delayed asynchronous cancellation") {
    val error=intercept[org.scalatest.exceptions.TestFailedException] {simulateRaw(new EpochFifoTest(true))(exercise)}
    assert(error.getMessage.contains("EPOCH cancellation was delayed"))
  }
  test("epoch oracle rejects reopening without the stopped peer acknowledgement") {
    val error=intercept[org.scalatest.exceptions.TestFailedException] {simulateRaw(new EpochFifoTest(missingAck=true))(exercise)}
    assert(error.getMessage.contains("EPOCH reopened before stopped peer cleared"))
  }
}
