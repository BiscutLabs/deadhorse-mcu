package deadhorse.top
import chisel3._

/** Public MMIO and dedicated source pins supply the integration oracle. */
class SocPinmuxSpec extends SocIoSpec {
  test("pin mux routes all three sources, retains raw inputs/wake and survives AON reset") {
    simulateRaw(new SocPeripheralBusTest(SocTestFiles.description,SocProduction.config(realUsb=false))) {d=>
      val memory=d.dmaMemory.get
      memory.gnt.poke(false.B);memory.rvalid.poke(false.B);memory.err.poke(false.B);memory.rdata.poke(0.U)
      reset(d)
      val gpio=BigInt(0x40012000L);val timer=gpio+0x100;val mux=gpio+0x200;val pwm=BigInt(0x40030000L)
      good(d,d.main,gpio,true,5);good(d,d.main,gpio+4,true,7)
      assert(d.pins.inactive.gpioEnable.peek().litValue==0,"PINMUX_RESET_DISCONNECTED")
      for(i<-0 until 3) good(d,d.main,mux+4*i,true,1)
      assert(d.pins.inactive.gpioOut.peek().litValue==5 && d.pins.inactive.gpioEnable.peek().litValue==7)
      good(d,d.main,gpio,true,2);assert(d.pins.inactive.gpioOut.peek().litValue==2,"PINMUX_GPIO_WRITE")
      assert(access(d,d.pins.lite,mux,true,0)._2 && good(d,d.main,mux)==1,"PINMUX_OWNER")
      for(a<-Seq(12,28,36,252)) assert(access(d,d.main,mux+a)._2,"PINMUX_HOLE")

      // Actual PWM outputs are the independent source oracle, one edge earlier.
      for(i<-0 until 3) {
        good(d,d.main,pwm+0x40+4*i,true,15+i*4)
        good(d,d.main,pwm+0xc0+4*i,true,3+i)
      }
      good(d,d.main,pwm+4,true,7);good(d,d.main,pwm,true,7)
      for(i<-0 until 3) good(d,d.main,mux+4*i,true,3)
      for(_<-0 until 100) {
        val v=d.pins.inactive.actuatorOut.peek().litValue & 7
        val e=d.pins.inactive.actuatorEnable.peek().litValue & 7
        tick(d);assert(d.pins.inactive.gpioOut.peek().litValue==(v&e) &&
          d.pins.inactive.gpioEnable.peek().litValue==e,"PINMUX_PWM_LATENCY")
      }
      good(d,d.main,gpio+12,true,1);good(d,d.main,gpio+24,true,1)
      good(d,d.main,gpio+28,true,1);good(d,d.main,gpio+32,true,1);good(d,d.main,gpio+36,true,1)
      good(d,d.main,pwm+4,true,7);tick(d,40)
      assert(d.pins.inactive.gpioEnable.peek().litValue==0,"PINMUX_SOURCE_DISABLE")
      assert(!high(d.pins.mainDemand),"PINMUX_NO_SPURIOUS_DEMAND")
      d.pins.inactive.gpioIn.poke(1.U);d.pins.aonClock.step(12)
      assert(high(d.pins.mainDemand),"PINMUX_RAW_AON_WAKE")
      tick(d,8);assert(good(d,d.main,gpio+8)==1 && d.fastIrq.peek().litValue.testBit(9),"PINMUX_RAW_INPUT_IRQ")

      good(d,d.main,timer,true,1)
      val now=good(d,d.main,timer+12)
      for(i<-0 until 3) {
        good(d,d.main,timer+0x20+4*i,true,7)
        good(d,d.main,timer+0x40+4*i,true,now+100+i*8)
        good(d,d.main,mux+4*i,true,2)
      }
      good(d,d.main,timer+8,true,7)
      assert(d.pins.inactive.timerEnable.peek().litValue==7,"PINMUX_TIMER_ENABLED")
      var observed=BigInt(0)
      for(_<-0 until 1200) {
        val v=d.pins.inactive.timerOut.peek().litValue & 7
        val e=d.pins.inactive.timerEnable.peek().litValue & 7
        tick(d);assert(d.pins.inactive.gpioOut.peek().litValue==(v&e) &&
          d.pins.inactive.gpioEnable.peek().litValue==e,"PINMUX_TIMER_LATENCY")
        observed|=v
      }
      assert(observed==7,"PINMUX_TIMER_REACHED")
      d.pins.aonServiceReset_n.poke(false.B);tick(d,4)
      for(i<-0 until 3) assert(good(d,d.main,mux+4*i)==2,"PINMUX_AON_RESET_PRESERVES")
      assert(d.pins.inactive.gpioEnable.peek().litValue==7)
      // No main edge: service reset must disable both data and output enable.
      d.mainServiceReset_n.poke(false.B)
      assert(d.pins.inactive.gpioEnable.peek().litValue==0 && d.pins.inactive.gpioOut.peek().litValue==0)
      d.mainServiceReset_n.poke(true.B);d.pins.aonServiceReset_n.poke(true.B);tick(d,40)
      assert(good(d,d.main,mux)==0 && d.pins.inactive.gpioEnable.peek().litValue==0)
    }
  }
}
