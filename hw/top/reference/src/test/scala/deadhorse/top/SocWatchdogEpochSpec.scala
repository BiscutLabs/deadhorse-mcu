package deadhorse.top
import chisel3._

class SocWatchdogEpochSpec extends SocDmaSpec {
  def checkEpoch(d: SocDmaHarness): Unit={
      d.stallPeripheral.get.poke(false.B);init(d)
      wr(d,pwm+4,1);wr(d,pwm+0x40,999);wr(d,pwm+0xc0,500);wr(d,pwm,1)
      val wd=BigInt(0x40000100L)
      wr(d,wd,400);wr(d,wd+12,0x57445354L)
      // The client request is accepted by real SocLocalMemory but cannot yet
      // reach the peripheral fabric. Its accepted MMIO slot survives core reset.
      d.stallPeripheral.get.poke(true.B)
      d.bus.req.poke(true.B);d.bus.bits.addr.poke((pwm+4).U);d.bus.bits.we.poke(true.B)
      d.bus.bits.be.poke(15.U);d.bus.bits.wdata.poke(1.U);d.bus.bits.origin.poke(1.U)
      var n=0;while(!high(d.bus.gnt)) {d.clk.step();n+=1;assert(n<64)}
      d.clk.step();d.bus.req.poke(false.B)
      n=0;while(!high(d.watchdogReset.get)) {d.clk.step();n+=1;assert(n<500)}
      d.clk.step(20)
      assert(!high(d.epochReady.get) && d.pwmEnable.peek().litValue==0,"WATCHDOG_EPOCH_DRAIN_GUARD")
      d.stallPeripheral.get.poke(false.B)
      n=0;while(!high(d.epochReady.get)) {d.clk.step();n+=1;assert(n<512)}
      wr(d,pwm,1);assert(rd(d,pwm+8)==0,"WATCHDOG_OLD_STOP_CANNOT_ACK")
      wr(d,pwm+4,1);wr(d,pwm,1);assert(rd(d,pwm+8)==1)
  }
  test("retained pre-watchdog STOP drains before break acknowledgment is enabled") {
    simulateRaw(new SocDmaHarness(SocProduction.config(realUsb=false)),settings=settings)(checkEpoch)
  }
  test("bypassing actual epoch readiness is caught by the retained STOP scenario") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new SocDmaHarness(SocProduction.config(realUsb=false),bypassWatchdogEpoch=true),
        settings=settings)(checkEpoch)
    }
    assert(e.getMessage.contains("WATCHDOG_OLD_STOP_CANNOT_ACK"))
  }
}
