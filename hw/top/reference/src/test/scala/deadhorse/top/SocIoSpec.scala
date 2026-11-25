package deadhorse.top
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import deadhorse.lib.LocalBus
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SocIoSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t21/soc/simulation").toAbsolutePath
  }
  def high(x: Bool): Boolean=x.peek().litToBoolean
  def tick(d: SocI1Peripherals,n: Int=1): Unit=for(_<-0 until n) {
    d.mainClock.step();d.pins.aonClock.step();d.pins.usbClock.step()
  }
  def drive(bus: LocalBus,addr: BigInt,write: Boolean=false,data: BigInt=0,be: Int=15,origin: Int=7): Unit = {
    bus.req.poke(true.B);bus.bits.addr.poke(addr.U);bus.bits.we.poke(write.B)
    bus.bits.wdata.poke(data.U);bus.bits.be.poke(be.U);bus.bits.origin.poke(origin.U)
  }
  def reset(d: SocI1Peripherals): Unit = {
    SocTestPorts.idle(d)
    drive(d.main,0);drive(d.pins.lite,0);d.main.req.poke(false.B);d.pins.lite.req.poke(false.B)
    d.coldReset_n.poke(false.B);d.warmReset_n.poke(false.B);d.mainServiceReset_n.poke(false.B)
    d.pins.aonServiceReset_n.poke(false.B);d.pins.usbServiceReset_n.poke(false.B)
    d.uartRx.poke(true.B);d.pins.uartRx.foreach(_.poke(true.B))
    d.pins.spiMiso.poke(false.B);d.pins.spiTimeNow.poke(0.U)
    d.pins.i2cSclIn.poke(true.B);d.pins.i2cSdaIn.poke(true.B)

    d.pins.usbVbus.poke(false.B);d.pins.usbDpRx.poke(false.B);d.pins.usbDnRx.poke(false.B)
    d.pins.liteHalted.poke(true.B);d.pins.resetReason.poke(0.U);d.pins.crashCount.poke(0.U)
    SocInactiveTestInputs.drive(d.pins.inactive,0)
    tick(d,4)
    d.coldReset_n.poke(true.B);d.warmReset_n.poke(true.B);d.mainServiceReset_n.poke(true.B)
    d.pins.aonServiceReset_n.poke(true.B);d.pins.usbServiceReset_n.poke(true.B);tick(d,40)
  }
  def access(d: SocI1Peripherals,bus: LocalBus,address: BigInt,write: Boolean=false,data: BigInt=0,
             be: Int=15): (BigInt,Boolean,Int) = {
    drive(bus,address,write,data,be)
    var cycles=0
    while(!high(bus.gnt)) {tick(d);cycles+=1;assert(cycles<256,"I1_GRANT_TIMEOUT")}
    val period=1
    // Acceptance and a one-cycle response are measured in the requester's
    // clock domain, including when AON is slower than the main test clock.
    tick(d,period);bus.req.poke(false.B)
    while(!high(bus.rvalid)) {tick(d);cycles+=1;assert(cycles<512,"I1_RESPONSE_TIMEOUT")}
    val result=(bus.rdata.peek().litValue,high(bus.err),cycles)
    tick(d,2*period);assert(!high(bus.rvalid),"I1_DUPLICATE_REPLY");result
  }
  def good(d: SocI1Peripherals,bus: LocalBus,address: BigInt,write: Boolean=false,data: BigInt=0,be: Int=15): BigInt = {
    val(v,e,_)=access(d,bus,address,write,data,be);assert(!e,s"I1_BUS_ERROR $address");v
  }
  test("functional I/O decode, ownership, pad outputs and timer IRQ") {
    simulateRaw(new SocPeripheralBusTest(SocTestFiles.description,SocProduction.config(realUsb=false))) { d =>
      reset(d)
      val gpio=BigInt(0x40012000L);val timer=BigInt(0x40030000L)
      for(i<-0 until 3) good(d,d.main,0x40012200L+4*i,true,1)
      good(d,d.main,gpio,true,5);good(d,d.main,gpio+4,true,7)
      assert(d.pins.inactive.gpioOut.peek().litValue==5 && d.pins.inactive.gpioEnable.peek().litValue==7)
      assert(access(d,d.pins.lite,gpio,true,0)._2);assert(good(d,d.main,gpio)==5)
      good(d,d.main,gpio+12,true,1);good(d,d.main,gpio+24,true,1)
      d.pins.inactive.gpioIn.poke(1.U);tick(d,6);assert(d.fastIrq.peek().litValue.testBit(9))
      good(d,d.main,gpio+20,true,7);tick(d,4);assert(!d.fastIrq.peek().litValue.testBit(9))
      // General timer 0/channel 0 output compare, routed to the first timer pad.
      good(d,d.main,0x40012264L,true,0)
      good(d,d.main,timer+0x30,true,0) // Explicit stop acknowledges the reset break.
      good(d,d.main,timer,true,1)
      val now=good(d,d.main,timer+4);tick(d,80)
      assert(good(d,d.main,timer+4)>now,"IO_MICROSECOND_TIMEBASE")
      good(d,d.main,timer+0x40,true,799)
      good(d,d.main,timer+0x80,true,6);good(d,d.main,timer+0xc0,true,100)
      good(d,d.main,timer+0x14,true,1);good(d,d.main,timer+0x1c,true,1)
      good(d,d.main,timer+0x30,true,1)
      assert(d.pins.inactive.timerEnable.peek().litValue==1 && high(d.mainHold))
      tick(d,120);assert(d.pins.inactive.timerOut.peek().litValue==1 && d.fastIrq.peek().litValue.testBit(10))
      good(d,d.main,timer+0x30,true,0);good(d,d.main,timer,true,0)
      assert(d.pins.inactive.timerEnable.peek().litValue==0)
      for(a<-Seq(0x40012080L,0x40012180L,0x400122fcL,0x400004fcL,0x40020200L))
        assert(access(d,d.main,a)._2,"IO_HOLE")
      assert(access(d,d.main,0x40000020L,true,100)._2 && access(d,d.main,0x40020000L,true,1)._2)
      d.mainServiceReset_n.poke(false.B);tick(d,2)
      assert(d.pins.inactive.gpioEnable.peek().litValue==0 && d.pins.inactive.timerEnable.peek().litValue==0)
    }
  }
  test("AON deadline and GPIO level wake with main stopped; independent reset scopes") {
    simulateRaw(new SocPeripheralBusTest(SocTestFiles.description,SocProduction.config(realUsb=false))) { d =>
      reset(d);val gpio=BigInt(0x40012000L);val aon=BigInt(0x40000000L)
      for(i<-0 until 3) good(d,d.main,0x40012200L+4*i,true,1)
      good(d,d.main,gpio,true,6);good(d,d.main,gpio+4,true,3)
      good(d,d.main,gpio+28,true,1);good(d,d.main,gpio+32,true,1);good(d,d.main,gpio+36,true,1)
      tick(d,32);good(d,d.pins.lite,aon+8,true,1);good(d,d.pins.lite,aon+12,true,1)
      good(d,d.pins.lite,aon+32,true,200);good(d,d.pins.lite,aon,true,1)
      d.pins.aonClock.step(220);assert(high(d.pins.mainDemand) && high(d.pins.aonIrq))
      tick(d,8);assert(d.fastIrq.peek().litValue.testBit(11))
      d.mainServiceReset_n.poke(false.B);d.pins.aonClock.step(4)
      d.mainServiceReset_n.poke(true.B);tick(d,48)
      assert(d.fastIrq.peek().litValue.testBit(11),"AON_IRQ_REASSERTS_AFTER_MAIN_RESET")
      good(d,d.pins.lite,aon+4,true,1);tick(d,40);assert(!high(d.pins.mainDemand))
      // Main reset flushed GPIO wake; reinstall before the stopped-main check.
      for(i<-0 until 3) good(d,d.main,0x40012200L+4*i,true,1)
      good(d,d.main,gpio,true,6);good(d,d.main,gpio+4,true,3)
      good(d,d.main,gpio+28,true,1);good(d,d.main,gpio+32,true,1);good(d,d.main,gpio+36,true,1);tick(d,32)
      d.pins.inactive.gpioIn.poke(1.U);d.pins.aonClock.step(12);assert(high(d.pins.mainDemand))
      d.pins.aonServiceReset_n.poke(false.B);d.pins.aonClock.step(4)
      // Production pinmux drives disabled pads low, even when the GPIO data
      // register retains a one. Check the exact physical value while main is stopped.
      assert(d.pins.inactive.gpioOut.peek().litValue==2 && d.pins.inactive.gpioEnable.peek().litValue==3)
      assert(!high(d.pins.aonIrq));d.pins.aonServiceReset_n.poke(true.B);tick(d,48)
      assert(!high(d.pins.mainDemand),"IO_WAKE_CONFIG_FLUSH")
      // Preserve the original raw GPIO retention obligation, including the
      // disabled bit, without adding main edges before the wake-flush check.
      assert(good(d,d.main,gpio)==6 && good(d,d.main,gpio+4)==3,"IO_GPIO_STATE_RETAINED")
    }
  }
}
