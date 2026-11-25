package deadhorse.timers

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class GeneralTimersSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan05/timers/simulation").toAbsolutePath
  }
  val json="build/t21/timers/timers_regs.json"
  def exercise(d: GeneralTimers,mode: Int): Unit={
    def high(x: Bool)=x.peek().litToBoolean
    d.reset_n.poke(false.B);d.bus.req.poke(false.B);d.bus.bits.addr.poke(0.U)
    d.bus.bits.we.poke(false.B);d.bus.bits.wdata.poke(0.U);d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(1.U)
    d.owner.poke(1.U);d.captureIn.poke(0.U);d.captureValid.poke(4095.U);d.dmaAck.poke(0.U)
    d.clk.step(3);d.reset_n.poke(true.B);d.clk.step(3)
    def access(a: Int,w: Boolean=false,v: BigInt=0,origin: Int=1): (BigInt,Boolean)={
      d.bus.req.poke(true.B);d.bus.bits.addr.poke(a.U);d.bus.bits.we.poke(w.B)
      d.bus.bits.wdata.poke(v.U);d.bus.bits.origin.poke(origin.U)
      var n=0;while(!high(d.bus.gnt)) {d.clk.step();n+=1;assert(n<32)}
      d.clk.step();d.bus.req.poke(false.B)
      while(!high(d.bus.rvalid)) {d.clk.step();n+=1;assert(n<32)}
      val r=(d.bus.rdata.peek().litValue,high(d.bus.err));d.clk.step(2);r
    }
    def wr(a: Int,v: BigInt): Unit=assert(!access(a,true,v)._2,s"TIMER_WRITE $a")
    def rd(a: Int): BigInt={val(v,e)=access(a);assert(!e);v}
    assert(access(48,true,7,origin=0)._2,"TIMER_OWNER")
    if(mode==3) {
      wr(8,0x1234);wr(12,1);assert(rd(4)==0x1234,"TIME_LOAD")
      wr(0,1);val before=d.timeNow.peek().litValue;d.clk.step(80)
      assert(d.timeNow.peek().litValue-before==10,"TIMEBASE_RATE")
    }
    for(c<-0 until 12) {
      val t=c/4;val bit=1<<c
      wr(48,0);wr(64+4*t,7);wr(80+4*t,1)
      wr(128+4*c,mode | (if(mode==3) 0 else 4));wr(192+4*c,3);wr(20,bit)
      wr(48,1<<t);assert(high(d.clockHold),"TIMER_HOLD")
      assert(access(64+4*t,true,9)._2 && rd(64+4*t)==7,"RUNNING_CONFIG_CHANGED")
      if(mode<3) {
        assert((d.pinsEnable.peek().litValue & bit)!=0,"TIMER_ENABLE")
        def widths(edges: Int): (Vector[Int],Vector[Int])={
          var last=(d.pinsOut.peek().litValue & bit)!=0
          var rise= -1;var previousRise= -1;var lastTransition= -1
          var highs=Vector.empty[Int];var periods=Vector.empty[Int]
          for(i<-0 until edges) {
            d.clk.step();val now=(d.pinsOut.peek().litValue & bit)!=0
            if(now!=last) {
              if(mode==2 && lastTransition>=0) periods :+= i-lastTransition
              lastTransition=i
              if(now) {
                if(mode==1 && previousRise>=0) periods :+= i-previousRise
                rise=i;previousRise=i
              } else if(rise>=0) highs :+= i-rise
            }
            last=now
          }
          (highs,periods)
        }
        val (highs,periods)=widths(96)
        if(mode==1) {
          assert(highs.nonEmpty && highs.forall(_==6) && periods.nonEmpty && periods.forall(_==16),"PWM_WIDTH_PERIOD")
          wr(192+4*c,5);wr(20,bit)
          val(nextHighs,nextPeriods)=widths(96)
          assert(nextHighs.contains(10) && nextHighs.forall(n=>n==6 || n==10) && nextPeriods.forall(_==16),"PWM_BOUNDARY_UPDATE")
        } else assert(periods.nonEmpty && periods.forall(_==16),"COMPARE_EDGES")
      } else {
        assert((d.pinsEnable.peek().litValue & bit)==0,"CAPTURE_NO_DRIVE")
        assert(access(0,true,0)._2,"CAPTURE_TIMEBASE_STOP")
        d.captureIn.poke(0.U);d.clk.step(3);d.captureIn.poke(bit.U);d.clk.step()
        val expected=d.timeNow.peek().litValue
        assert(rd(256+4*c)==expected,"CAPTURE_TIMESTAMP")
        assert((rd(24)&bit)!=0,"CAPTURE_EVENT")
        wr(48,0);wr(128+4*c,11);wr(48,1<<t)
        d.captureIn.poke(bit.U);d.clk.step(3);d.captureIn.poke(0.U);d.clk.step()
        val fallingTime=d.timeNow.peek().litValue
        assert(rd(256+4*c)==fallingTime,"CAPTURE_FALLING")
      }
      wr(48,0);assert((d.pinsEnable.peek().litValue&bit)==0,"TIMER_STOP")
      wr(128+4*c,0);wr(24,4095)
    }
    wr(0,0);d.clk.step(3);assert(!high(d.clockHold),"TIMER_IDLE_HOLD")
  }
  for(mode<-1 to 3) test(s"all twelve channels in mode $mode preserve the timer contract") {
    simulateRaw(new GeneralTimers(json))(d=>exercise(d,mode))
  }
  for(mode<-1 to 3) test(s"mode $mode oracle catches its injected fault") {
    val error=intercept[Throwable] {
      simulateRaw(new GeneralTimers(json) {
        override protected def output(value: Bool): Bool=if(mode==1) !value else value
        override protected def compareMatch(value: Bool): Bool=if(mode==2) false.B else value
        override protected def timestamp(value: UInt): UInt=if(mode==3) value ^ 1.U else value
      })(d=>exercise(d,mode))
    }
    val label=Map(1->"PWM_WIDTH_PERIOD",2->"COMPARE_EDGES",3->"CAPTURE_TIMESTAMP")(mode)
    assert(Iterator.iterate(error)(_.getCause).takeWhile(_!=null).exists(e=>Option(e.getMessage).exists(_.contains(label))))
  }
}
