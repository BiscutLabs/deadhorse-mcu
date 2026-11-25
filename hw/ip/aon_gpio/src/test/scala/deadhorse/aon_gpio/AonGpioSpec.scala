package deadhorse.aon_gpio

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import deadhorse.lib.CdcPulseCapture
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class AonGpioSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan05/aon-gpio/simulation").toAbsolutePath
  }
  def exercise(d: AonGpio): Unit={
    def high(v: Bool)=v.peek().litToBoolean
    var acknowledge=true
    def tick(n: Int=1): Unit=for(_<-0 until n) {
      if(acknowledge) d.mainAck.poke(d.ownerRequest.peek())
      d.clk.step()
    }
    d.reset_n.poke(false.B);d.bus.req.poke(false.B);d.bus.bits.addr.poke(0.U)
    d.bus.bits.we.poke(false.B);d.bus.bits.wdata.poke(0.U);d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(0.U)
    d.pinsIn.poke(0.U);d.mainEnables.poke(0.U);d.mainAck.poke(0.U);d.mainAvailable.poke(true.B)
    d.spiEnabled.poke(false.B);d.spiBusy.poke(false.B)
    tick(4);d.reset_n.poke(true.B);tick(12)
    def access(a: Int,w: Boolean=false,v: Int=0,origin: Int=0): (Int,Boolean)={
      d.bus.req.poke(true.B);d.bus.bits.addr.poke(a.U);d.bus.bits.we.poke(w.B)
      d.bus.bits.wdata.poke(v.U);d.bus.bits.origin.poke(origin.U)
      var count=0
      while(!high(d.bus.gnt)) {tick();count+=1;assert(count<32)}
      tick();d.bus.req.poke(false.B)
      while(!high(d.bus.rvalid)) {tick();count+=1;assert(count<64,"GPIO_REPLY")}
      val result=(d.bus.rdata.peek().litValue.toInt,high(d.bus.err));tick(2);result
    }
    def wr(a: Int,v: Int): Unit=assert(!access(a,true,v)._2,s"GPIO_WRITE $a")
    def rd(a: Int): Int={val(v,e)=access(a);assert(!e);v}
    assert(access(4,true,63,origin=1)._2,"GPIO_OWNER")
    wr(32,15);assert(high(d.spiSelected) && d.ownerActive.peek().litValue==7,"GPIO_MUX_ACK")
    wr(4,32);wr(8,32);assert(d.pinsOut.peek().litValue==32 && d.pinsEnable.peek().litValue==32)
    for(falling<-Seq(false,true);pin<-0 until 6) {
      wr(16,0);wr(20,63);tick(8)
      d.pinsIn.poke((if(falling) 63 else 0).U);wr(24,if(falling) 63 else 0)
      wr(16,1<<pin);tick(12);assert((rd(28)&(1<<pin))!=0,"GPIO_ARM")
      // Both transitions are evaluated with NO AON edge between them.
      // This is a sub-cycle digital pulse, not a physical minimum-width signoff.
      d.pinsIn.poke((if(falling) 63^(1<<pin) else 1<<pin).U);d.irq.peek()
      d.pinsIn.poke((if(falling) 63 else 0).U);d.irq.peek()
      tick(4)
      assert(rd(12)==(1<<pin) && high(d.irq) && high(d.wake),"GPIO_SHORT_PULSE_LOST")
      assert(access(24,true,if(falling) 0 else 63)._2,"GPIO_POLARITY_WHILE_ARMED")
      wr(20,1<<pin);tick(5);assert(rd(12)==0 && !high(d.irq),"GPIO_CLEAR")
      // An active input at the clearing edge wins, then clearing after release re-arms.
      d.pinsIn.poke((if(falling) 63^(1<<pin) else 1<<pin).U);tick(4)
      wr(20,1<<pin);assert(rd(12)==(1<<pin),"GPIO_SET_WINS_CLEAR")
      d.pinsIn.poke((if(falling) 63 else 0).U);wr(20,1<<pin);tick(5)
      assert(rd(12)==0 && (rd(28)&(1<<pin))!=0,"GPIO_REARM")
      d.bus.req.poke(true.B);d.bus.bits.addr.poke(20.U);d.bus.bits.we.poke(true.B)
      d.bus.bits.wdata.poke((1<<pin).U);d.bus.bits.origin.poke(0.U)
      var guard=0;while(!high(d.bus.gnt)) {tick();guard+=1;assert(guard<32)}
      tick();d.bus.req.poke(false.B);tick()
      // Clear is now at the generated command boundary, while pending is idle.
      d.pinsIn.poke((if(falling) 63^(1<<pin) else 1<<pin).U);d.irq.peek()
      d.pinsIn.poke((if(falling) 63 else 0).U);d.irq.peek()
      tick(6);assert(rd(12)==(1<<pin),"GPIO_IDLE_CLEAR_RACE")
      wr(20,1<<pin);tick(5)
    }
    wr(16,0);wr(8,0)
    d.mainEnables.poke(1.U);tick(4);assert(access(32,true,0)._2,"GPIO_ACTIVE_MAIN_MUX")
    d.mainEnables.poke(0.U);d.spiBusy.poke(true.B);tick(4)
    assert(access(32,true,0)._2,"GPIO_ACTIVE_SPI_MUX")
    d.spiBusy.poke(false.B);d.mainAvailable.poke(false.B)
    assert(access(32,true,0)._2,"GPIO_UNACKNOWLEDGED_MUX")
    d.mainAvailable.poke(true.B);acknowledge=false
    d.bus.req.poke(true.B);d.bus.bits.addr.poke(32.U);d.bus.bits.we.poke(true.B);d.bus.bits.wdata.poke(0.U)
    var waiting=0;while(!high(d.bus.gnt)) {tick();waiting+=1;assert(waiting<32)}
    tick();d.bus.req.poke(false.B)
    for(_<-0 until 6) {tick();assert(!high(d.bus.rvalid) && d.ownerActive.peek().litValue==7,"GPIO_EARLY_ACK")}
    acknowledge=true;waiting=0
    while(!high(d.bus.rvalid)) {tick();waiting+=1;assert(waiting<32)}
    assert(!high(d.bus.err));tick(3)
    assert(!high(d.spiSelected) && d.ownerActive.peek().litValue==0)
    d.reset_n.poke(false.B);tick(2);assert(d.pinsEnable.peek().litValue==0 && !high(d.irq))
  }
  test("all retained GPIOs capture sub-cycle edges, clear safely and arbitrate pad ownership") {
    simulateRaw(new AonGpio("build/plan05/aon_gpio/aon_gpio_regs.json"))(exercise)
  }
  test("short-pulse oracle rejects a missing asynchronous capture") {
    val error=intercept[Throwable] {
      simulateRaw(new AonGpio("build/plan05/aon_gpio/aon_gpio_regs.json") {
        override protected def capture(): CdcPulseCapture=new CdcPulseCapture {
          override protected def captureInput(value: Bool): Bool=false.B
        }
      })(exercise)
    }
    assert(Iterator.iterate(error)(_.getCause).takeWhile(_!=null).exists(e=>Option(e.getMessage).exists(_.contains("GPIO_SHORT_PULSE_LOST"))))
  }
  test("idle-clear race oracle rejects clearing an unseen event") {
    val error=intercept[Throwable] {
      simulateRaw(new AonGpio("build/plan05/aon_gpio/aon_gpio_regs.json") {
        override protected def capture(): CdcPulseCapture=new CdcPulseCapture {
          override protected def acceptedClear(command: Bool,seen: Bool): Bool=command
        }
      })(exercise)
    }
    assert(Iterator.iterate(error)(_.getCause).takeWhile(_!=null).exists(e=>Option(e.getMessage).exists(_.contains("GPIO_IDLE_CLEAR_RACE"))))
  }
}
