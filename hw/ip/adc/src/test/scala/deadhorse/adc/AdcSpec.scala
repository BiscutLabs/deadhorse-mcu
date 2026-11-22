package deadhorse.adc

import chisel3._
import chisel3.simulator.{ChiselSim,PeekPokeAPI}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** External device model: drive before first rise, advance only on pad falls. */
class AdcPeer(clk: Clock,cs_n: Bool,sclk: Bool,miso: Bool,enabled: Bool,held: Bool) extends PeekPokeAPI {
  def this(d: Adc)=this(d.clk,d.cs_n,d.sclk,d.miso,d.pinsEnable,d.clockHold)
  var value=0;var frames=0
  private var selected=false;private var previousClock=false;private var rises=0
  def step(): Unit = {
    observe();clk.step()
  }
  def observe(): Unit = {
    val cs=cs_n.peek().litToBoolean;val clock=sclk.peek().litToBoolean
    if(!cs && !selected) {selected=true;rises=0;miso.poke(((value&0x8000)!=0).B)}
    if(selected && !cs && clock && !previousClock) {rises+=1;assert(rises<=16,"ADC_EXTRA_CLOCK")}
    if(selected && !cs && !clock && previousClock && rises<16)
      miso.poke(((value & (1<<(15-rises)))!=0).B)
    if(cs && selected) {assert(rises==16,"ADC_FRAME_LENGTH");frames+=1;selected=false}
    if(selected) assert(enabled.peek().litToBoolean && held.peek().litToBoolean,"ADC_FRAME_CLOCK_HOLD")
    previousClock=clock
  }
}

class AdcSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t21/adc/simulation").toAbsolutePath
  }
  val json="build/t21/adc/adc_regs.json"
  def high(x: Bool): Boolean=x.peek().litToBoolean
  def init(d: Adc): AdcPeer = {
    d.reset_n.poke(false.B);d.owner.poke(0.U);d.miso.poke(false.B)
    d.bus.req.poke(false.B);d.bus.bits.poke(0.U.asTypeOf(d.bus.bits));d.clk.step(4)
    assert(high(d.cs_n) && !high(d.sclk) && !high(d.pinsEnable))
    d.reset_n.poke(true.B);d.clk.step(8);new AdcPeer(d)
  }
  def access(d: Adc,h: AdcPeer,a: Int,write: Boolean=false,value: Int=0,owner: Int=0,be: Int=15): (BigInt,Boolean) = {
    d.bus.req.poke(true.B);d.bus.bits.addr.poke(a.U);d.bus.bits.we.poke(write.B)
    d.bus.bits.wdata.poke((BigInt(value)&BigInt("ffffffff",16)).U);d.bus.bits.be.poke(be.U);d.bus.bits.origin.poke(owner.U)
    var cycles=0
    while(!high(d.bus.gnt)) {h.step();cycles+=1;assert(cycles<64,"ADC_GRANT")}
    h.step();d.bus.req.poke(false.B)
    while(!high(d.bus.rvalid)) {h.step();cycles+=1;assert(cycles<64,"ADC_REPLY")}
    val answer=(d.bus.rdata.peek().litValue,high(d.bus.err));h.step();h.step();assert(!high(d.bus.rvalid));answer
  }
  def wr(d: Adc,h: AdcPeer,a: Int,v: Int,be: Int=15): Unit=assert(!access(d,h,a,true,v,be=be)._2)
  def rd(d: Adc,h: AdcPeer,a: Int): BigInt={val(v,e)=access(d,h,a);assert(!e);v}
  def convert(d: Adc,h: AdcPeer,value: Int): Unit = {
    val expected=h.frames+1;h.value=0xa000|value;wr(d,h,8,2)
    var edges=0
    while(h.frames<expected || (rd(d,h,12)&1)!=0) {
      h.step();edges+=1;assert(edges<1024,"ADC_CONVERSION_DEADLINE")
    }
    for(_<-0 until 8) h.step()
  }
  for(half<-Seq(4,5)) test(s"mode0 raw wire data, discarded first conversion, retired register and events at halfperiod $half") {
    simulateRaw(new Adc(json,AdcParameters(halfPeriodCycles=half))) { d =>
      val h=init(d);wr(d,h,0,1);wr(d,h,8,1);wr(d,h,32,15)
      convert(d,h,1234);assert(rd(d,h,24)==0 && (rd(d,h,12)&8)!=0 && !high(d.irq),"ADC_FIRST_DISCARD")
      for((raw,index)<-Seq(0,4095,1,2048,0xa53).zipWithIndex) {
        convert(d,h,raw)
        assert(rd(d,h,16)==raw,"ADC_RAW_MODEL")
        assert(access(d,h,20)._2,"ADC_RETIRED_READ")
        assert(access(d,h,20,true,raw)._2,"ADC_RETIRED_WRITE")
        assert(access(d,h,20,true,0,be=0)._2,"ADC_RETIRED_ZERO_STROBE")
        assert(rd(d,h,24)==index+1 && (rd(d,h,12)&16)!=0 && high(d.irq))
        wr(d,h,8,4);wr(d,h,28,15);assert((rd(d,h,12)&16)==0)
      }
      convert(d,h,3);convert(d,h,9);assert((rd(d,h,28)&2)!=0,"ADC_OVERRUN")
      assert(access(d,h,0,true,0,owner=1)._2);assert(rd(d,h,0)==1)
      assert(access(d,h,0x100)._2);assert(access(d,h,3)._2)
      wr(d,h,4,42,be=0);assert(rd(d,h,4)==100000)
      wr(d,h,8,3);assert((rd(d,h,28)&4)!=0,"ADC_APPLY_START_CONFLICT")
      val prior=h.frames;for(_<-0 until 32)h.step();assert(h.frames==prior)
      wr(d,h,28,4);assert((rd(d,h,28)&4)==0)
      wr(d,h,4,1);wr(d,h,8,1);assert((rd(d,h,28)&4)!=0 && (rd(d,h,12)&2)!=0)
      d.reset_n.poke(false.B);assert(high(d.cs_n) && !high(d.pinsEnable) && !high(d.sclk))
    }
  }
  test("continuous mode retains clock, counts frames and rejects live reconfiguration") {
    simulateRaw(new Adc(json,AdcParameters(halfPeriodCycles=4))) { d =>
      val h=init(d);h.value=0x0567;wr(d,h,4,161);wr(d,h,0,3);wr(d,h,8,1)
      var previousCs=high(d.cs_n);var starts=Vector.empty[Int]
      for(edge<-0 until 1000) {
        h.step();assert(high(d.clockHold),"ADC_CONTINUOUS_CLOCK")
        val cs=high(d.cs_n);if(!cs && previousCs) starts=starts:+edge;previousCs=cs
      }
      val periods=starts.sliding(2).collect {case v if v.size==2 => v(1)-v(0)}.toVector
      assert(periods.nonEmpty && periods.forall(_>=32*4+161),"ADC_IDLE_GAP_CONTRACT")
      println(s"ADC_CADENCE measured AON edges: halfPeriod=4 idleGap=161 startIntervals=${periods.mkString(",")}")
      assert(h.frames>=3 && rd(d,h,24)>=2 && rd(d,h,16)==0x567)
      wr(d,h,8,2);assert((rd(d,h,28)&8)!=0,"ADC_CONTINUOUS_MANUAL_REJECTED")
      var waits=0
      while((rd(d,h,12)&1)==0) {h.step();waits+=1;assert(waits<1024)}
      wr(d,h,0,0);wr(d,h,28,4);assert((rd(d,h,28)&4)==0)
      wr(d,h,8,1);assert((rd(d,h,28)&4)!=0 && (rd(d,h,12)&6)==6,"ADC_BUSY_APPLY_REJECTED")
      waits=0
      while((rd(d,h,12)&1)!=0) {h.step();waits+=1;assert(waits<1024)}
      wr(d,h,8,1);assert((rd(d,h,12)&6)==0)
      val stopped=h.frames
      for(_<-0 until 400) {h.step();assert(!high(d.clockHold) && !high(d.pinsEnable))}
      assert(h.frames==stopped,"ADC_DISABLE_DRAINS_AND_STOPS")
      // Reset may terminate a frame; the normal completed-frame oracle is not applied to an abort.
      d.reset_n.poke(false.B);assert(high(d.cs_n) && !high(d.pinsEnable));d.clk.step(2)
      assert(!high(d.clockHold))
    }
  }
  test("wire/MMIO oracle rejects actual stored sample corruption") {
    simulateRaw(new Adc(json,AdcParameters(halfPeriodCycles=4)) {
      override protected def rawValue(value: UInt): UInt=value^1.U
    }) { d =>
      val h=init(d);wr(d,h,0,1);wr(d,h,8,1);convert(d,h,1);convert(d,h,0x456)
      intercept[org.scalatest.exceptions.TestFailedException] {assert(rd(d,h,16)==0x456,"ADC_RAW_MODEL")}
    }
  }
  test("wire publication coincides with READ_ACK and sticky event clear") {
    simulateRaw(new Adc(json,AdcParameters(halfPeriodCycles=4))) { d=>
      val h=init(d);wr(d,h,0,1);wr(d,h,8,1)
      convert(d,h,0);convert(d,h,111)
      for((ack,index)<-Seq(true,false).zipWithIndex) {
        wr(d,h,28,15);val oldCount=rd(d,h,24);h.value=0xb000|(222+index);wr(d,h,8,2)
        var rises=0;var previous=high(d.sclk);var edges=0
        while(rises<16) {
          h.step();val current=high(d.sclk)
          if(current && !previous) rises+=1
          previous=current;edges+=1;assert(edges<160,"ADC_COLLISION_FRAME")
        }
        // The last pad rise precedes publication by four edges. The local
        // adapter accepts now, RegBlock accepts next edge, and W1P reaches
        // the publication register one edge later. W1C acts at RegBlock accept.
        for(_<-0 until (if(ack) 1 else 2)) h.step()
        assert(high(d.bus.gnt),"ADC_COLLISION_BUS_IDLE")
        wr(d,h,if(ack) 8 else 28,if(ack) 4 else 15)
        assert(rd(d,h,24)==oldCount+1 && rd(d,h,16)==222+index,"ADC_COLLISION_ATOMIC")
        assert((rd(d,h,12)&16)!=0,"ADC_COLLISION_NEW_UNREAD")
        val events=rd(d,h,28)
        assert((events&1)!=0,"ADC_EVENT_SET_WINS_CLEAR")
        assert(((events&2)!=0)== !ack,"ADC_COLLISION_OVERRUN")
      }
    }
  }
}
