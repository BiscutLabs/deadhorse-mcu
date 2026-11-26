package deadhorse.top

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SocTestAccessEarly extends SocTestAccess {
  override protected def lastBit: UInt=30.U(5.W)
}

class SocTestAccessBench(early: Boolean=false) extends RawModule {
  val tckLevel=IO(Input(Bool()));val externalReset_n=IO(Input(Bool()))
  val tms=IO(Input(Bool()));val tdi=IO(Input(Bool()))
  val porBypass=IO(Input(Bool()));val aonClockSelect=IO(Input(Bool()))
  val scanReset_n=IO(Input(Bool()));val testMode=IO(Output(Bool()))
  val access=Module(if(early) new SocTestAccessEarly else new SocTestAccess)
  access.tck:=tckLevel.asClock;access.externalReset_n:=externalReset_n
  access.tms:=tms;access.tdi:=tdi;access.porBypass:=porBypass
  access.aonClockSelect:=aonClockSelect;access.scanReset_n:=scanReset_n
  testMode:=access.testMode
}

class SocTestAccessSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t37/access-simulation").toAbsolutePath
  }
  val key="11010011011110100110110010010101".map(_=='1')
  def tick(d: SocTestAccessBench): Unit={
    d.tckLevel.poke(false.B);d.testMode.peek()
    d.tckLevel.poke(true.B);d.testMode.peek()
    d.tckLevel.poke(false.B);d.testMode.peek()
  }
  def reset(d: SocTestAccessBench): Unit={
    d.externalReset_n.poke(false.B);d.tms.poke(true.B);d.tdi.poke(false.B)
    d.porBypass.poke(true.B);d.aonClockSelect.poke(true.B);d.scanReset_n.poke(false.B)
    for(_<-0 until 3) tick(d)
    d.testMode.expect(false.B)
    d.externalReset_n.poke(true.B);for(_<-0 until 2) tick(d)
    d.testMode.expect(false.B)
  }
  def send(d: SocTestAccessBench,bits: Seq[Boolean],expectEntry: Boolean): Unit={
    for((bit,index)<-bits.zipWithIndex) {
      d.tdi.poke(bit.B)
      d.tckLevel.poke(true.B);d.testMode.expect(false.B,"TEST_ENTRY_PHASE")
      d.tckLevel.poke(false.B)
      d.testMode.expect((expectEntry && index==31).B,"TEST_ENTRY_WINDOW")
    }
  }
  test("exact key enters once; capture and test reset cannot leave; external reset exits") {
    simulateRaw(new SocTestAccessBench) {d=>
      reset(d);send(d,key,true)
      for(i<-0 until 64) {
        d.tms.poke((i%3==0).B);d.tdi.poke((i%5==0).B)
        d.scanReset_n.poke((i%2==0).B);tick(d);d.testMode.expect(true.B)
      }
      d.externalReset_n.poke(false.B);d.testMode.expect(false.B)
      reset(d);send(d,key,true)
    }
  }
  test("each wrong key bit permanently closes the finite window") {
    simulateRaw(new SocTestAccessBench) {d=>
      for(bit<-0 until 32) {
        reset(d);send(d,key.updated(bit,!key(bit)),false)
        send(d,key,false)
      }
    }
  }
  test("each sampled entry qualifier is mandatory and failure cannot be retried") {
    simulateRaw(new SocTestAccessBench) {d=>
      for(which<-0 until 4;bit<-Seq(0,15,31)) {
        reset(d)
        for(i<-0 until 32) {
          d.tms.poke((which!=0 || i!=bit).B)
          d.porBypass.poke((which!=1 || i!=bit).B)
          d.aonClockSelect.poke((which!=2 || i!=bit).B)
          d.scanReset_n.poke((which==3 && i==bit).B)
          d.tdi.poke(key(i).B);tick(d);d.testMode.expect(false.B)
        }
        d.tms.poke(true.B);d.porBypass.poke(true.B)
        d.aonClockSelect.poke(true.B);d.scanReset_n.poke(false.B)
        send(d,key,false)
      }
    }
  }
  test("negative control: accepting a short key is caught") {
    val e=intercept[Throwable] {simulateRaw(new SocTestAccessBench(early=true)) {d=>reset(d);send(d,key,true)}}
    assert(Iterator.iterate(e)(_.getCause).takeWhile(_!=null)
      .exists(x=>Option(x.getMessage).exists(_.contains("TEST_ENTRY_WINDOW"))))
  }
}
