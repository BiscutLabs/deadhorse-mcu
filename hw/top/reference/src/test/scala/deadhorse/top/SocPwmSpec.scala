package deadhorse.top
import chisel3._

/** Reuse the public bus/pin driver and preserve its existing I/O regressions. */
class SocPwmSpec extends SocIoSpec {
  test("PWM profile pins, IRQ10, clock demand, holes, denial and independent resets") {
    simulateRaw(new SocPeripheralBusTest(SocTestFiles.description,SocProduction.config(realUsb=false))) {d=>
      reset(d);val base=BigInt(0x40030000L)
      good(d,d.main,0x40012240L,true,0)
      good(d,d.main,base+0x30,true,0) // Explicit stop acknowledges the reset break.
      good(d,d.main,base+0x40,true,15);good(d,d.main,base+0x80,true,5)
      good(d,d.main,base+0xc0,true,8);good(d,d.main,base+0x14,true,1)
      good(d,d.main,base+0x30,true,1)
      good(d,d.main,base+0xc0,true,4);good(d,d.main,base+0x14,true,1)
      assert(good(d,d.main,base+0x30)==1 && d.pins.inactive.actuatorEnable.peek().litValue==1)
      d.pins.aonServiceReset_n.poke(false.B);tick(d,4)
      assert(good(d,d.main,base+0x30)==1 && d.pins.inactive.actuatorEnable.peek().litValue==1)
      d.pins.aonServiceReset_n.poke(true.B);tick(d,40)
      assert(access(d,d.pins.lite,base+0x30,true,1)._2,"PWM_REMOTE_OWNER")
      for(a<-Seq(0x38,0x180,0xffc)) assert(access(d,d.main,base+a)._2,"PWM_WINDOW_HOLE")
      good(d,d.main,base+0x1c,true,1);tick(d,64)
      assert(d.fastIrq.peek().litValue.testBit(10) && high(d.mainHold) && high(d.pins.mainDemand))
      val wave=(0 until 160).map {_=>val v=d.pins.inactive.actuatorOut.peek().litValue;tick(d);v}
      assert(wave.count(_.testBit(0))==40 && wave.drop(16)==wave.dropRight(16),"SOC_PWM_PINS")
      // Assert service reset without an edge: pads must disable asynchronously.
      d.mainServiceReset_n.poke(false.B)
      assert(d.pins.inactive.actuatorEnable.peek().litValue==0 && d.pins.inactive.actuatorOut.peek().litValue==0)
      d.mainServiceReset_n.poke(true.B);tick(d,40)
      assert(good(d,d.main,base+0x30)==0 && good(d,d.main,base+0x10)==0,"PWM_RESET_NO_RESTART")
    }
  }
}
