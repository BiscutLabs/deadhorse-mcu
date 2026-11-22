package deadhorse.pinmux
import chisel3._

class PinmuxWatchdogSpec extends PinmuxSpec {
  test("watchdog stops only PWM-selected pads without a main edge; all handovers remain disabled") {
    simulateRaw(new PinmuxPad(watchdog=true)) {d=>
      d.reset_n.poke(false.B);d.watchdogReset_n.get.poke(true.B)
      d.select.poke(0.U);d.values.poke(7.U);d.enables.poke(7.U);d.clk.step(2);d.reset_n.poke(true.B)
      for(s<-Seq(1,2,3,2,1,3)) {
        d.watchdogReset_n.get.poke(true.B);d.select.poke(s.U);d.clk.step()
        assert(!high(d.enable) && !high(d.value),"WATCHDOG_PINMUX_HANDOVER")
        d.clk.step();assert(high(d.enable) && high(d.value))
        d.watchdogReset_n.get.poke(false.B)
        assert(high(d.enable)==(s!=3) && high(d.value)==(s!=3),"WATCHDOG_PINMUX_SCOPE")
        d.clk.step(2);assert(high(d.enable)==(s!=3))
      }
    }
  }
}
