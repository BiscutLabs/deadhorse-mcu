package deadhorse.pwm
import chisel3._

class PwmWatchdogSpec extends PwmSpec {
  test("watchdog disables execution asynchronously, retains shadows, rejects hold-time APPLY and needs fresh APPLY") {
    simulateRaw(new Pwm(json,watchdog=true)) {d=>
      d.watchdogReset_n.get.poke(true.B);d.performanceReady.get.poke(true.B);init(d);wr(d,4,511)
      wr(d,0x40,999);wr(d,0xc0,500);wr(d,0,1)
      assert(d.pinsEnable.peek().litValue==1)
      d.watchdogReset_n.get.poke(false.B)
      assert(d.pinsEnable.peek().litValue==0 && d.pinsOut.peek().litValue==0,"WATCHDOG_ASYNC_PWM")
      wr(d,0,1);assert((rd(d,16)&512)!=0)
      d.watchdogReset_n.get.poke(true.B);d.clk.step(20)
      assert(rd(d,0x40)==999 && rd(d,0xc0)==500 && rd(d,8)==0 && rd(d,12)==0)
      wr(d,0,1);assert(rd(d,8)==0,"WATCHDOG_DMA_APPLY_INHIBITED")
      d.performanceReady.get.poke(false.B);wr(d,4,1)
      d.performanceReady.get.poke(true.B);d.clk.step(3);wr(d,0,1)
      assert(rd(d,8)==0,"WATCHDOG_STALE_UPSTREAM_STOP")
      wr(d,4,1);wr(d,0,1);assert(rd(d,8)==1)
      // Stop main precisely when the generated APPLY pulse becomes live.
      d.bus.req.poke(true.B);d.bus.bits.addr.poke(0.U);d.bus.bits.we.poke(true.B)
      d.bus.bits.wdata.poke(1.U);d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(1.U)
      while(!high(d.bus.gnt)) d.clk.step()
      d.clk.step();d.bus.req.poke(false.B)
      d.watchdogReset_n.get.poke(false.B)
      assert(d.pinsEnable.peek().litValue==0,"WATCHDOG_ASSERT_WITHOUT_EDGE")
      d.watchdogReset_n.get.poke(true.B)
      d.clk.step(10);assert(rd(d,8)==0 && rd(d,12)==0,"WATCHDOG_STALE_APPLY")
      wr(d,4,1);wr(d,0,1);assert(rd(d,8)==1)
    }
  }
}
