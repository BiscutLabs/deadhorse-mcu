package deadhorse.gpio

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class GpioSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t21/gpio/simulation").toAbsolutePath
  }
  private val json="build/t21/gpio/gpio_regs.json"
  private var runAon=true
  def high(x: Bool): Boolean=x.peek().litToBoolean
  def tick(d: Gpio,n: Int=1): Unit=for(_<-0 until n) {d.clk.step();if(runAon) d.aonClock.step()}
  def init(d: Gpio): Unit = {
    runAon=true
    d.reset_n.poke(false.B);d.aonReset_n.poke(false.B);d.pinsIn.poke(0.U);d.owner.poke(1.U)
    d.bus.req.poke(false.B);d.bus.bits.poke(0.U.asTypeOf(d.bus.bits));tick(d,4)
    d.reset_n.poke(true.B);d.aonReset_n.poke(true.B);tick(d,24)
  }
  def access(d: Gpio,addr: Int,write: Boolean=false,value: Int=0,be: Int=15,owner: Int=1): (BigInt,Boolean) = {
    d.bus.req.poke(true.B);d.bus.bits.addr.poke(addr.U);d.bus.bits.we.poke(write.B)
    d.bus.bits.wdata.poke(value.U);d.bus.bits.be.poke(be.U);d.bus.bits.origin.poke(owner.U)
    var cycles=0
    while(!high(d.bus.gnt)) {tick(d);cycles+=1;assert(cycles<64,"GPIO_GRANT")}
    tick(d);d.bus.req.poke(false.B)
    while(!high(d.bus.rvalid)) {tick(d);cycles+=1;assert(cycles<64,"GPIO_REPLY")}
    val result=(d.bus.rdata.peek().litValue,high(d.bus.err));tick(d,2);assert(!high(d.bus.rvalid));result
  }
  def wr(d: Gpio,a: Int,v: Int,be: Int=15): Unit=assert(!access(d,a,true,v,be)._2)
  def rd(d: Gpio,a: Int): BigInt={val(v,e)=access(d,a);assert(!e);v}
  test("GPIO byte writes, synchronized input, sticky edge IRQs, denial and safe resets") {
    simulateRaw(new Gpio(json)) { d =>
      init(d);assert(d.pinsEnable.peek().litValue==0 && !high(d.irq))
      wr(d,0,5);wr(d,4,7);assert(d.pinsOut.peek().litValue==5 && d.pinsEnable.peek().litValue==7)
      wr(d,0,2,2);assert(rd(d,0)==5);wr(d,0,2,1);assert(rd(d,0)==2)
      assert(access(d,0,true,7,owner=0)._2);assert(rd(d,0)==2)
      assert(access(d,0x100)._2);assert(access(d,3)._2);assert(access(d,0x30)._2)
      wr(d,12,7);wr(d,16,7);wr(d,24,7)
      d.pinsIn.poke(5.U);tick(d,6);assert(rd(d,8)==5 && (rd(d,20)&7)==5 && high(d.irq))
      wr(d,20,7);tick(d,4);assert(!high(d.irq));d.pinsIn.poke(0.U);tick(d,6)
      assert((rd(d,20)&7)==5 && high(d.irq))
      d.reset_n.poke(false.B);assert(d.pinsEnable.peek().litValue==0 && d.pinsOut.peek().litValue==0)
      tick(d);assert(!high(d.irq))
    }
  }
  test("acknowledged AON wake works with main stopped, level wins clear and peer reset preserves GPIO") {
    simulateRaw(new Gpio(json)) { d =>
      init(d);wr(d,0,6);wr(d,4,3)
      wr(d,28,1);wr(d,32,1);wr(d,36,1);tick(d,24)
      assert((rd(d,40)&11)==10 && !high(d.clockHold) && !high(d.wake))
      d.pinsIn.poke(1.U);d.aonClock.step(6);assert(high(d.wake),"GPIO_WAKE_STOPPED_MAIN")
      tick(d,8);assert((rd(d,40)&4)==4)
      wr(d,36,2);tick(d,24);assert(high(d.wake),"GPIO_LEVEL_WINS_CLEAR")
      d.pinsIn.poke(0.U);tick(d,6);wr(d,36,2);tick(d,24);assert(!high(d.wake))
      d.aonReset_n.poke(false.B);assert(!high(d.wake))
      assert(d.pinsOut.peek().litValue==6 && d.pinsEnable.peek().litValue==3)
      d.aonReset_n.poke(true.B);tick(d,24);d.pinsIn.poke(1.U);d.aonClock.step(6)
      assert(!high(d.wake),"GPIO_STALE_WAKE_CONFIGURATION")
      wr(d,36,1);tick(d,24);assert(high(d.wake))
    }
  }
  test("actual GPIO data corruption is rejected by the output oracle") {
    simulateRaw(new Gpio(json) {override protected def outputValue(value: UInt): UInt=value^1.U}) { d =>
      init(d);wr(d,0,5)
      intercept[org.scalatest.exceptions.TestFailedException] {assert(d.pinsOut.peek().litValue==5,"GPIO_OUTPUT_MODEL")}
    }
  }
  test("wake commands during peer reset and stopped-clock release are rejected without stale replay") {
    simulateRaw(new Gpio(json)) { d =>
      init(d);wr(d,0,5);wr(d,4,7);wr(d,28,1);wr(d,32,1)
      d.aonReset_n.poke(false.B)
      wr(d,36,1);assert((rd(d,20)&8)==8,"GPIO_RESET_COMMAND_ERROR")
      assert(d.pinsOut.peek().litValue==5 && d.pinsEnable.peek().litValue==7)
      wr(d,20,8);wr(d,36,2);assert((rd(d,20)&8)==8)
      runAon=false;d.aonReset_n.poke(true.B);wr(d,20,8);wr(d,36,1)
      assert((rd(d,20)&8)==8 && (rd(d,40)&8)==0,"GPIO_RELEASE_COMMAND_ERROR")
      runAon=true;tick(d,32);d.pinsIn.poke(1.U);d.aonClock.step(6)
      assert(!high(d.wake),"GPIO_REJECTED_COMMAND_REPLAY")
      wr(d,36,1);tick(d,24);assert(high(d.wake))
    }
  }
}
