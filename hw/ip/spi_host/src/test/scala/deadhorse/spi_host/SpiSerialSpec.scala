package deadhorse.spi_host

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SpiSerialSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t16/serial-simulation").toAbsolutePath
  }
  test("independent delayed-edge peer checks modes, selects, all byte values and IMU read deadline") {
    simulateRaw(new SpiBench(SpiTestFiles.json)) { d =>
      val h=new SpiDriver(d);h.reset();h.stampBase=BigInt("fffffff0",16)
      for(mode <- Seq(false,true); cs <- 0 to 1; group <- 0 until 4) {
        val sent=(0 until 16).map(i => (if(mode)128 else 0)+cs*64+group*16+i)
        val reply=sent.map(_ ^ 0xa5)
        val p=h.prepare(sent,reply,mode,cs,3);h.wr(12,2);h.finish(p)
        assert(p.end-p.start==771)
        for(hz <- Seq(9000000,12000000,24000000)) {
          val micros=(p.end-p.start)*1e6/hz
          assert(micros<150.0,"SPI_DEADLINE_MODEL")
          println(s"SPI measured edges=${p.end-p.start}; assumed HF=$hz; derived us=$micros; SCLK=${hz/(2.0*p.half)}")
        }
        assert(h.rd(0x28)==((h.stampBase+p.start-1)&BigInt("ffffffff",16)))
        assert((h.rd(0x1c)&16)!=0 && (h.rd(0x1c)&15)==0)
        h.checkRx(reply);h.wr(0x1c,31)
      }
    }
  }
  test("maximum divider and non-power-of-two FIFO preserve byte order and exact CS intervals") {
    for(depth <- Seq(2,3,16)) simulateRaw(new SpiBench(SpiTestFiles.json,depth),subdirectory=Some(s"depth-$depth")) { d =>
      val h=new SpiDriver(d);h.reset()
      for(round <- 0 until 3) {
        val sent=(0 until depth).map(i => (i*31+round)&255);val reply=sent.reverse
        val half=if(depth==2)255 else 7
        val p=h.prepare(sent,reply,round%2!=0,round%2,half)
        h.wr(12,2);h.finish(p);h.checkRx(reply)
        assert(p.end-p.start==(16*depth+1)*half)
      }
    }
  }
  test("pin model rejects a real corrupted production MOSI update") {
    simulateRaw(new SpiBench(SpiTestFiles.json,corrupt=true)) { d =>
      val h=new SpiDriver(d);h.reset()
      val p=h.prepare(Seq(0x69,0xa5),Seq(0x12,0x34))
      val failure=intercept[IllegalArgumentException] {h.wr(12,2);h.finish(p)}
      assert(failure.getMessage.contains("SPI_PIN_MODEL"))
    }
  }
}
