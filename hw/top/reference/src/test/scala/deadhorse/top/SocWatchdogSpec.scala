package deadhorse.top
import chisel3._

/** Both bus masters are controllable here; the emitted production profile uses LiteHart. */
class SocWatchdogSpec extends SocIoSpec {
  val profile=SocProduction.config(realUsb=false)
  val pwm=BigInt(0x40030000L);val gpio=BigInt(0x40012000L);val mux=gpio+512
  val perf=BigInt(0x40000100L);val lite=BigInt(0x40000200L);val dma=BigInt(0x40011000L)
  def initialize(d: SocI1Peripherals): Unit={
    d.performanceReady.get.poke(true.B)
    d.dmaMemory.get.gnt.poke(false.B);d.dmaMemory.get.rvalid.poke(false.B)
    d.dmaMemory.get.rdata.poke(0.U);d.dmaMemory.get.err.poke(false.B);reset(d)
    tick(d,600);d.pins.clockControl.stable.poke(true.B);tick(d,12)
    assert(high(d.pins.clockControl.gateRequest),"WATCHDOG_CONTINUOUS_CLOCK_READY")
  }
  def performanceScope(d: SocI1Peripherals): Unit={
    initialize(d)
    good(d,d.main,pwm+48,true,0);good(d,d.main,mux+0x40,true,0);good(d,d.main,pwm+128,true,5);good(d,d.main,pwm+0x40,true,999)
    good(d,d.main,pwm+0xc0,true,1000);good(d,d.main,pwm+20,true,1);good(d,d.main,pwm+48,true,1)
    good(d,d.main,gpio,true,2);good(d,d.main,gpio+4,true,2)
    good(d,d.main,mux,true,3);good(d,d.main,mux+4,true,1)
    good(d,d.main,dma+0x20,true,0x20000100L);good(d,d.main,dma+0x30,true,1)
    good(d,d.main,dma+0x40,true,8);good(d,d.main,pwm+32,true,1)
    good(d,d.pins.lite,0x30000400L,true,0x12345678)
    assert(d.pins.inactive.gpioEnable.peek().litValue==3)
    assert(access(d,d.pins.lite,perf,true,500)._2,"WATCHDOG_SOC_OWNER")
    good(d,d.main,perf,true,500);good(d,d.main,perf+8,true,250)
    // Establish the real PWM request before arming the watchdog: its warning
    // already breaks PWM and prevents a new request. Then stop main while AON
    // advances, preserving the native fabric's 128-running-cycle deadline.
    good(d,d.main,dma,true,1)
    var waitMemory=0
    while(!high(d.dmaMemory.get.req)) {tick(d);waitMemory+=1;assert(waitMemory<1500,"WATCHDOG_DMA_PENDING")}
    good(d,d.main,perf+12,true,0x57445354L)
    var n=0
    while(!high(d.supervision.get.warning)) {
      d.pins.aonClock.step();n+=1
      // The NMI observation crosses back to main. Supply sparse main edges
      // for that synchronizer without spending 250 native-fabric wait cycles.
      if(n%16==0) d.mainClock.step()
      assert(n<500,"WATCHDOG_SOC_NMI")
    }
    assert(high(d.pins.mainDemand) && high(d.pins.aonDemand))
    // Main stopped: AON expiry must still disable dedicated and muxed PWM.
    n=0
    while(!high(d.supervision.get.performanceReset)) {d.pins.aonClock.step();n+=1;assert(n<500)}
    assert(high(d.supervision.get.wholeReset),"WATCHDOG_CONTAINMENT")
    d.performanceReady.get.poke(false.B)
    assert(d.pins.inactive.actuatorEnable.peek().litValue==0)
    assert(d.pins.inactive.gpioEnable.peek().litValue==0 && d.pins.inactive.gpioOut.peek().litValue==0)
    assert(!high(d.dmaMemory.get.req),"WATCHDOG_CANCEL_DMA_REQUEST")
    for(_<-0 until 3) {d.pins.aonClock.step();assert(high(d.supervision.get.performanceReset))}
    d.pins.aonClock.step();assert(!high(d.supervision.get.performanceReset))
    tick(d,20)
    d.performanceReady.get.poke(true.B);tick(d,5)
    assert(good(d,d.main,dma+0x20)==0 && good(d,d.main,dma+0x30)==0)
    assert(!high(d.dmaMemory.get.req),"WATCHDOG_CANCEL_DMA_REQUEST")
    assert(good(d,d.main,pwm+0x40)==0 && good(d,d.main,pwm+0xc0)==0)
    assert(good(d,d.main,dma+8)==0 && good(d,d.main,dma+12)==0,"WATCHDOG_DMA_RESET_STATE")
    assert(d.pins.inactive.actuatorEnable.peek().litValue==0,"WATCHDOG_DMA_CANNOT_RESTART")
    assert(good(d,d.pins.lite,0x30000400L)==0x12345678)
    assert(good(d,d.main,perf+28)==1 && good(d,d.main,perf+20)==8)
    // Warm cleared the complete timer and pad configuration. Reinitialize it
    // explicitly before software may enable outputs again.
    good(d,d.main,pwm+48,true,0);good(d,d.main,mux+0x40,true,0)
    good(d,d.main,pwm+128,true,5);good(d,d.main,pwm+0x40,true,999);good(d,d.main,pwm+0xc0,true,1000)
    good(d,d.main,gpio,true,2);good(d,d.main,gpio+4,true,2)
    good(d,d.main,mux,true,3);good(d,d.main,mux+4,true,1)
    good(d,d.main,pwm+20,true,1);good(d,d.main,pwm+48,true,1)
    assert(d.pins.inactive.actuatorEnable.peek().litValue==1 && d.pins.inactive.gpioEnable.peek().litValue==3)
    assert((good(d,d.main,0x40000500L)&8)!=0,"POWER_PERFORMANCE_RESET_REASON")
  }
  test("performance watchdog resets ordinary state, retains RAM/causes and disables PWM with main stopped") {
    simulateRaw(new SocPeripheralBusTest(SocTestFiles.description,profile))(performanceScope)
  }
  test("wrongly narrowing performance watchdog warm reset is rejected") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new SocPeripheralBusTest(SocTestFiles.description,profile) {
        override protected def wholeWatchdogReset(p: Bool,l: Bool): Bool=l
      })(performanceScope)
    };assert(e.getMessage.contains("WATCHDOG_CONTAINMENT"))
  }
  test("lite watchdog resets all ordinary services but retains causes and SRAM") {
    simulateRaw(new SocPeripheralBusTest(SocTestFiles.description,profile)) {d=>
      initialize(d);good(d,d.main,dma+0x30,true,29);good(d,d.pins.lite,0x30000400L,true,0x76543210)
      assert(access(d,d.main,lite,true,100)._2)
      good(d,d.pins.lite,lite,true,100);good(d,d.pins.lite,lite+12,true,0x57445354L)
      var n=0;while(!high(d.supervision.get.wholeReset)) {tick(d);n+=1;assert(n<150)}
      assert(d.pins.inactive.actuatorEnable.peek().litValue==0 && d.pins.inactive.gpioEnable.peek().litValue==0)
      for(_<-0 until 3) {tick(d);assert(high(d.supervision.get.wholeReset))}
      tick(d,40);assert(!high(d.supervision.get.wholeReset))
      assert(good(d,d.main,dma+0x30)==0 && good(d,d.pins.lite,lite+28)==1)
      assert(good(d,d.pins.lite,0x30000400L)==0x76543210)
      assert((good(d,d.main,0x40000500L)&16)!=0,"POWER_LITE_RESET_REASON")
    }
  }
}
