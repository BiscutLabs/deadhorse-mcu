package deadhorse.top
import chisel3._

/** Both bus masters are controllable here; the emitted production profile uses LiteHart. */
class SocWatchdogSpec extends SocIoSpec {
  val profile=SocWatchdogFiles.config().copy(liteCore=false)
  val pwm=BigInt(0x40030000L);val gpio=BigInt(0x40012000L);val mux=gpio+512
  val perf=BigInt(0x40000100L);val lite=BigInt(0x40000200L);val dma=BigInt(0x40011000L)
  def initialize(d: SocI1Peripherals): Unit={
    d.performanceReady.get.poke(true.B)
    d.dmaMemory.get.gnt.poke(false.B);d.dmaMemory.get.rvalid.poke(false.B)
    d.dmaMemory.get.rdata.poke(0.U);d.dmaMemory.get.err.poke(false.B);reset(d)
  }
  def performanceScope(d: SocI1Peripherals): Unit={
    initialize(d)
    good(d,d.main,pwm+4,true,511);good(d,d.main,pwm+0x40,true,999)
    good(d,d.main,pwm+0xc0,true,1000);good(d,d.main,pwm,true,1)
    good(d,d.main,gpio,true,2);good(d,d.main,gpio+4,true,2)
    good(d,d.main,mux,true,3);good(d,d.main,mux+4,true,1)
    good(d,d.main,dma+0x20,true,0x20000100L);good(d,d.main,dma+0x30,true,1)
    good(d,d.main,dma+0x40,true,8);good(d,d.main,pwm+0x18,true,1);good(d,d.main,dma,true,1)
    var waitMemory=0
    while(!high(d.dmaMemory.get.req)) {tick(d);waitMemory+=1;assert(waitMemory<1500,"WATCHDOG_DMA_PENDING")}
    good(d,d.pins.lite,0x30000800L,true,0x12345678)
    assert(d.pins.inactive.gpioEnable.peek().litValue==3)
    assert(access(d,d.pins.lite,perf,true,500)._2,"WATCHDOG_SOC_OWNER")
    good(d,d.main,perf,true,500);good(d,d.main,perf+8,true,250);good(d,d.main,perf+12,true,0x57445354L)
    var n=0
    while(!high(d.supervision.get.warning)) {tick(d);n+=1;assert(n<500,"WATCHDOG_SOC_NMI")}
    assert(high(d.pins.mainDemand) && high(d.pins.aonDemand))
    // Main stopped: AON expiry must still disable dedicated and muxed PWM.
    n=0
    while(!high(d.supervision.get.performanceReset)) {d.pins.aonClock.step();n+=1;assert(n<500)}
    assert(!high(d.supervision.get.wholeReset),"WATCHDOG_CONTAINMENT")
    d.performanceReady.get.poke(false.B)
    assert(d.pins.inactive.actuatorEnable.peek().litValue==0)
    assert(d.pins.inactive.gpioEnable.peek().litValue==2 && d.pins.inactive.gpioOut.peek().litValue==2)
    for(_<-0 until 3) {d.pins.aonClock.step();assert(high(d.supervision.get.performanceReset))}
    d.pins.aonClock.step();assert(!high(d.supervision.get.performanceReset))
    tick(d,20)
    // A retained pre-reset CPU STOP drains while the upstream epoch is closed.
    good(d,d.main,pwm+4,true,1)
    d.performanceReady.get.poke(true.B);tick(d,5)
    assert(good(d,d.main,dma+0x20)==0x20000100L && good(d,d.main,dma+0x30)==1)
    assert(high(d.dmaMemory.get.req),"WATCHDOG_PRESERVE_DMA_REQUEST")
    assert(good(d,d.main,pwm+0x40)==999 && good(d,d.main,pwm+0xc0)==1000)
    assert(good(d,d.pins.lite,0x30000800L)==0x12345678)
    assert(good(d,d.main,perf+28)==1 && good(d,d.main,perf+20)==8)
    // Complete the real DMA's pre-fault memory read only after watchdog release.
    d.dmaMemory.get.gnt.poke(true.B);tick(d);d.dmaMemory.get.gnt.poke(false.B)
    d.dmaMemory.get.rdata.poke(750.U);d.dmaMemory.get.rvalid.poke(true.B);tick(d)
    d.dmaMemory.get.rvalid.poke(false.B);tick(d,150)
    assert(good(d,d.main,dma+8)==0 && (good(d,d.main,dma+12)&1)==1,"WATCHDOG_DMA_COMPLETES")
    assert(good(d,d.main,pwm+0xc0)==750 && good(d,d.main,pwm+8)==0,"WATCHDOG_DMA_CANNOT_RESTART")
    good(d,d.main,pwm+4,true,1);good(d,d.main,pwm,true,1)
    assert(good(d,d.main,pwm+8)==1 && d.pins.inactive.gpioEnable.peek().litValue==3)
  }
  test("performance watchdog preserves shared state and disables all PWM routes while main is stopped") {
    simulateRaw(new SocI1Peripherals(SocTestFiles.description,profile))(performanceScope)
  }
  test("wrongly widening performance watchdog reset is rejected") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new SocI1Peripherals(SocTestFiles.description,profile) {
        override protected def wholeWatchdogReset(p: Bool,l: Bool): Bool=p || l
      })(performanceScope)
    };assert(e.getMessage.contains("WATCHDOG_CONTAINMENT"))
  }
  test("lite watchdog resets all ordinary services but retains causes and SRAM") {
    simulateRaw(new SocI1Peripherals(SocTestFiles.description,profile)) {d=>
      initialize(d);good(d,d.main,dma+0x30,true,29);good(d,d.pins.lite,0x30000800L,true,0x76543210)
      assert(access(d,d.main,lite,true,100)._2)
      good(d,d.pins.lite,lite,true,100);good(d,d.pins.lite,lite+12,true,0x57445354L)
      var n=0;while(!high(d.supervision.get.wholeReset)) {tick(d);n+=1;assert(n<150)}
      assert(d.pins.inactive.actuatorEnable.peek().litValue==0 && d.pins.inactive.gpioEnable.peek().litValue==0)
      for(_<-0 until 3) {tick(d);assert(high(d.supervision.get.wholeReset))}
      tick(d,40);assert(!high(d.supervision.get.wholeReset))
      assert(good(d,d.main,dma+0x30)==0 && good(d,d.pins.lite,lite+28)==1)
      assert(good(d,d.pins.lite,0x30000800L)==0x76543210)
    }
  }
}
