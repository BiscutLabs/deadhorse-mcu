package deadhorse.usb

import chisel3._
import deadhorse.lib.LocalBus
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import scala.collection.mutable
import org.scalatest.funsuite.AnyFunSuite

/** Boolean clock controls are verification ports, not production clock logic. */
class UsbThroughputBench extends Module with UsbWirePorts {
  val appLevel=IO(Input(Bool()));val aonLevel=IO(Input(Bool()))
  val bus=IO(new LocalBus)
  val hostDrive=IO(Input(Bool()));val hostDp=IO(Input(Bool()));val hostDn=IO(Input(Bool()))
  val vbus=IO(Input(Bool()));val txData=IO(Input(UInt(8.W)));val txValid=IO(Input(Bool()))
  val txReady=IO(Output(Bool()));val rxData=IO(Output(UInt(8.W)))
  val rxValid=IO(Output(Bool()));val rxReady=IO(Input(Bool()))
  val dp=IO(Output(Bool()));val dn=IO(Output(Bool()));val oe=IO(Output(Bool()))
  val pullupEnable=IO(Output(Bool()));val configured=IO(Output(Bool()))
  val usb=Module(new Usb("build/t19/regmap/usb_regs.json"))
  usb.usbClock:=clock;usb.appClock:=appLevel.asClock;usb.aonClock:=aonLevel.asClock
  usb.appReset_n:= !reset.asBool;usb.usbReset_n:= !reset.asBool;usb.aonReset_n:= !reset.asBool
  usb.bus<>bus;usb.owner:=2.U;usb.vbus:=vbus
  usb.dpRx:=Mux(usb.txEnable,usb.dpTx,Mux(hostDrive,hostDp,usb.pullupEnable))
  usb.dnRx:=Mux(usb.txEnable,usb.dnTx,Mux(hostDrive,hostDn,false.B))
  dp:=usb.dpTx;dn:=usb.dnTx;oe:=usb.txEnable;pullupEnable:=usb.pullupEnable
  txReady:=false.B;rxData:=0.U;rxValid:=false.B;configured:=false.B
}

/** All measured time passes through this scheduler: USB48 MHz and app/AON12 MHz.
  * Public bus handshakes run concurrently with every host packet and idle gap.
  */
class UsbScheduledHost(d: UsbThroughputBench, initialPhase: Int, serviceGap: Int)
    extends UsbWireHost(d,checkConfiguredReset=false) {
  private case class Request(offset: Int,write: Boolean,value: Int,done: Int=>Unit)
  private val requests=mutable.Queue.empty[Request]
  private var active: Option[Request]=None
  private var granted=false
  private var gap=0
  private var phase=initialPhase
  var running=false
  private var background=false
  private var preferRx=true
  private var txIndex=0
  private var txBytes=Seq.empty[Int]
  private var expectedRx=Seq.empty[Int]
  val observedRx=mutable.ArrayBuffer.empty[Int]
  var busTransactions=0L

  d.appLevel.poke(false.B);d.aonLevel.poke(false.B)
  d.bus.req.poke(false.B);d.bus.bits.addr.poke(0.U);d.bus.bits.we.poke(false.B)
  d.bus.bits.wdata.poke(0.U);d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(2.U)

  private def queue(offset: Int,write: Boolean=false,value: Int=0)(done: Int=>Unit): Unit=
    requests.enqueue(Request(offset,write,value,done))

  override def step(n: Int=1): Unit={
    if(!running) super.step(n)
    else {var remaining=n;while(remaining>0) {
      var take=false
      var reply: Option[Int]=None
      if(phase==0) {
        if(gap>0) gap-=1
        if(active.isEmpty && requests.nonEmpty && gap==0) {
          active=Some(requests.dequeue());val r=active.get
          d.bus.bits.addr.poke((0x40040800L+r.offset).U);d.bus.bits.we.poke(r.write.B)
          d.bus.bits.wdata.poke(r.value.U);d.bus.req.poke(true.B)
        }
        take=bool(d.bus.req) && bool(d.bus.gnt)
        if(bool(d.bus.rvalid)) {
          assert(active.nonEmpty && granted,"unexpected MMIO response")
          assert(!bool(d.bus.err),"throughput MMIO access rejected")
          reply=Some(d.bus.rdata.peek().litValue.toInt)
        }
      }
      if(phase%2==0) {
        d.appLevel.poke((phase<2).B);d.aonLevel.poke((phase>=2).B)
      }
      val advance=math.min(remaining,2-phase%2)
      super.step(advance)
      if(take) {assert(!granted);granted=true;d.bus.req.poke(false.B)}
      reply.foreach { value=>
        val r=active.get;active=None;granted=false;gap=serviceGap;busTransactions+=1
        r.done(value)
      }
      phase=(phase+advance)%4;remaining-=advance
    }}
  }

  def access(offset: Int,write: Boolean=false,value: Int=0): Int={
    var done=false;var result=0
    queue(offset,write,value){v=>result=v;done=true}
    var waited=0
    while(!done && waited<10000){step();waited+=1}
    assert(done,"MMIO service deadline");result
  }
  private def poll(): Unit=if(background) {
    queue(0x10) { status=>
      val canTx=(status&1)!=0 && txIndex<txBytes.size
      val canRx=(status&2)!=0
      if(canRx && (preferRx || !canTx)) {
        queue(0xc) { value=>
          val byte=value&255
          assert(observedRx.size<expectedRx.size,"unexpected extra OUT byte")
          assert(byte==expectedRx(observedRx.size),s"OUT byte mismatch at ${observedRx.size}")
          queue(8,true,1) {_=>observedRx+=byte;preferRx=false;poll()}
        }
      } else if(canTx) {
        queue(4,true,txBytes(txIndex)){_=>txIndex+=1;preferRx=true;poll()}
      } else poll()
    }
  }
  def startStreams(tx: Seq[Int],rx: Seq[Int]): Unit={
    assert(!background && active.isEmpty && requests.isEmpty)
    txBytes=tx;expectedRx=rx;background=true;poll()
  }
  def stopStreams(): Unit={background=false}
}

class UsbThroughputSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t19/throughput-simulation").toAbsolutePath
  }
  private case class Rates(in: Double,out: Double)
  private def requireRate(r: Rates,sendIn: Boolean,sendOut: Boolean): Unit={
    if(sendIn) assert(r.in>=1000000.0,s"USB_PAYLOAD_RATE IN ${r.in}")
    if(sendOut) assert(r.out>=1000000.0,s"USB_PAYLOAD_RATE OUT ${r.out}")
  }
  private def measure(sendIn: Boolean,sendOut: Boolean,phase: Int,gap: Int,frames: Int): Rates={
    var measured=Rates(0,0)
    simulate(new UsbThroughputBench) { d=>
      val h=new UsbScheduledHost(d,phase,gap)
      // Enumeration/attach are outside the steady-state measurement window.
      h.initialize(()=>{h.running=true;h.step(32);h.access(0,true,1);h.running=false})
      h.running=true;h.write(0,5,5);h.write(5,9,1)
      assert((h.access(0x10)&12)==12,"USB did not configure")
      val random=new scala.util.Random(0x1653L+phase)
      def bytes(n: Int)=Vector.tabulate(n)(i=>if(i%5==0)255 else random.nextInt(256))
      val tx=bytes(if(sendIn)frames*128 else 0)
      val rx=bytes(if(sendOut)frames*128 else 0)
      var inCount=0;var outCount=0;var inPid=h.DATA0;var outPid=h.DATA0
      var inPackets=0;var fullPackets=0;var shortPackets=0;var zlp=0;var retries=0;var naks=0
      def flip(pid: Int)=if(pid==h.DATA0)h.DATA1 else h.DATA0
      val start=h.elapsedSamples
      val initialMmio=h.busTransactions
      h.startStreams(tx,rx)
      def receiveIn(): Unit={
        h.token(h.IN,5,1);val response=h.receive()
        if(response._1==h.NAK) naks+=1
        else {
          assert(response._1==inPid,s"IN toggle mismatch $response")
          assert(response._2.size<=16,"bulk endpoint exceeded advertised16-byte MPS")
          assert(response._2==tx.slice(inCount,inCount+response._2.size),"IN byte stream mismatch")
          if(response._2.nonEmpty && inPackets%11==3) {
            h.idle(4);h.token(h.IN,5,1);assert(h.receive()==response,"lost-ACK retry changed payload")
            retries+=1
          }
          h.idle(2);h.packet(h.ACK);h.idle(4)
          inCount+=response._2.size;inPid=flip(inPid);inPackets+=1
          if(response._2.isEmpty)zlp+=1
          else if(response._2.size==16)fullPackets+=1 else shortPackets+=1
        }
        h.idle(2)
      }
      def transmitOut(): Unit={
        val payload=rx.slice(outCount,outCount+16)
        h.token(h.OUT,5,1);h.idle(2);h.data(outPid,payload)
        val response=h.receive()
        if(response._1==h.NAK)naks+=1
        else {assert(response._1==h.ACK);outCount+=payload.size;outPid=flip(outPid)}
        h.idle(4)
      }
      for(frame<-0 until frames) {
        val frameStart=start+frame*48000L;val frameEnd=frameStart+48000L
        assert(h.elapsedSamples==frameStart,"host frame scheduling drift")
        val token=frame&2047
        h.packet(5,Seq(token&255,((token>>8)&7)|(h.crc5(token)<<3)));h.idle(4)
        val inGoal=if(sendIn)(frame+1)*128 else 0
        val outGoal=if(sendOut)(frame+1)*128 else 0
        while((inCount<inGoal || outCount<outGoal) && h.elapsedSamples<frameEnd-2400) {
          if(outCount<outGoal)transmitOut()
          if(inCount<inGoal && h.elapsedSamples<frameEnd-2400)receiveIn()
        }
        assert(h.elapsedSamples<=frameEnd,"transaction crossed reserved SOF boundary")
        h.step((frameEnd-h.elapsedSamples).toInt)
      }
      // Include final transport/drain work in elapsed time, including terminal ZLP.
      val finishLimit=h.elapsedSamples+2000000L
      var nextFrame=start+frames*48000L
      var frameNumber=frames
      def reserveTransaction(): Unit={
        if(h.elapsedSamples>=nextFrame-2400) {
          assert(h.elapsedSamples<=nextFrame,"tail transaction crossed SOF boundary")
          h.step((nextFrame-h.elapsedSamples).toInt)
          val token=frameNumber&2047
          h.packet(5,Seq(token&255,((token>>8)&7)|(h.crc5(token)<<3)));h.idle(4)
          frameNumber+=1;nextFrame+=48000L
        }
      }
      while((inCount<tx.size || outCount<rx.size) && h.elapsedSamples<finishLimit) {
        if(outCount<rx.size){reserveTransaction();transmitOut()}
        if(inCount<tx.size){reserveTransaction();receiveIn()}
      }
      assert(inCount==tx.size && outCount==rx.size,"bounded host service failed to finish")
      if(sendIn) {
        reserveTransaction()
        h.idle(40);h.token(h.IN,5,1);val last=h.receive()
        if(last._1!=h.NAK) {
          assert(last==(inPid,Seq.empty),"final IN payload was not ACK-committed")
          h.idle(2);h.packet(h.ACK);h.idle(4);zlp+=1
        }
      }
      while(h.observedRx.size<rx.size && h.elapsedSamples<finishLimit){reserveTransaction();h.step(4)}
      assert(h.observedRx.toSeq==rx,"MMIO OUT stream did not drain intact")
      assert(h.elapsedSamples<=nextFrame,"final transaction crossed SOF boundary")
      val elapsed=h.elapsedSamples-start
      measured=Rates(inCount*8.0*48000000/elapsed,h.observedRx.size*8.0*48000000/elapsed)
      println(s"USB_THROUGHPUT seed=${0x1653L+phase} app_hz=12000000 usb_hz=48000000 phase=$phase service_gap=$gap frames=$frames samples=$elapsed in_bytes=$inCount out_bytes=${h.observedRx.size} in_bps=${measured.in} out_bps=${measured.out} mmio=${h.busTransactions-initialMmio} full_in=$fullPackets short_in=$shortPackets retries=$retries naks=$naks zlps=$zlp")
      h.stopStreams()
    }
    measured
  }
  test("16-byte bulk payload exceeds1Mbit per second through MMIO and CDC") {
    requireRate(measure(true,false,0,0,10),true,false)
    requireRate(measure(false,true,1,0,10),false,true)
    requireRate(measure(true,true,1,0,10),true,true)
  }
  test("payload rate oracle rejects throttled MMIO service without corrupting bytes") {
    val slow=measure(true,true,0,64,2)
    val failure=intercept[org.scalatest.exceptions.TestFailedException] {
      requireRate(slow,true,true)
    }
    assert(failure.getMessage.contains("USB_PAYLOAD_RATE"))
  }
}
