package deadhorse.top
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SocBootStrapSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan05/soc-boot-strap/simulation").toAbsolutePath
  }
  test("BOOT_MODE resamples on warm reset and ignores live pads and unauthorized writes") {
    simulateRaw(new SocPeripheralBusTest(SocTestFiles.description,SocProduction.config(realUsb=false))) {d=>
      val io=new SocIoSpec;io.reset(d)
      def read=io.good(d,d.main,0x40000310L)
      def whole(value: Boolean): Unit={
        d.warmReset_n.poke(false.B);d.pins.inactive.gpioIn.poke((if(value) 2 else 0).U)
        assert(d.pins.inactive.gpioEnable.peek().litValue==0 && d.pins.aonExtraEnable.peek().litValue==0,"BOOT_STRAP_PAD_DRIVE")
        io.tick(d,4);d.warmReset_n.poke(true.B);io.tick(d,40)
        assert(read==(if(value) 1 else 0),"BOOT_STRAP_READBACK")
      }
      for(value<-Seq(false,true)) {
        whole(value)
        d.pins.inactive.gpioIn.poke((if(value) 0 else 2).U);io.tick(d,12)
        assert(read==(if(value) 1 else 0),"BOOT_STRAP_RAW_PAD")
        whole(!value)
        d.pins.inactive.gpioIn.poke((if(value) 2 else 0).U);io.tick(d,12)
        assert(read==(if(value) 0 else 1),"BOOT_STRAP_WARM_LIVE_PAD")
        io.good(d,d.main,0x40000310L,true,if(value) 1 else 0)
        assert(read==(if(value) 0 else 1),"BOOT_STRAP_READ_ONLY")
        assert(io.access(d,d.pins.lite,0x40000310L)._2,"BOOT_STRAP_OWNER")
      }
      whole(false)
    }
  }
}
