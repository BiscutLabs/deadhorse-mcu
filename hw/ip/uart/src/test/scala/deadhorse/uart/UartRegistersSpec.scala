package deadhorse.uart

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class UartRegistersSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t15/register-simulation").toAbsolutePath
  }
  test("FIFO minimum, maximum and non-power-of-two depths wrap without aliasing") {
    for(depth <- Seq(2,3,16)) simulateRaw(new UartBench(UartTestFiles.json,depth),subdirectory=Some(s"depth-$depth")) { d =>
      val h=new UartDriver(d);h.reset();h.configure(0,4096,tx=false)
      for(round <- 0 until 3) {
        val expected=(0 until depth).map(i => (round*31+i)&255)
        h.send(0,expected :+ 0xfe,16.0)
        assert(((h.rd(0,0x14)>>16)&31)==depth && (h.rd(0,0x18)&2)!=0)
        h.checkBytes(0,expected);h.wr(0,0x18,63)
        for(byte <- expected)h.wr(0,0x0c,byte)
        h.wr(0,0x0c,0xfe)
        assert(((h.rd(0,0x14)>>8)&31)==depth && (h.rd(0,0x18)&1)!=0)
        h.wr(0,8,4);h.wr(0,0x18,63)
      }
    }
  }
  test("generated registers enforce origin, alignment, masks, configuration and FIFO command rules") {
    simulateRaw(new UartBench(UartTestFiles.json)) { d =>
      val h=new UartDriver(d);h.reset()
      assert(h.rd(0,0)==0 && h.rd(0,4)==0 && h.rd(0,0x20)==0)
      assert(!h.high(d.txEnable(0)) && h.high(d.tx(0)) && !h.high(d.irq(0)))
      assert(!h.high(d.dmaTxRequest(0)) && !h.high(d.dmaRxRequest(0)))
      for(origin <- 0 until 8 if origin!=1) {
        assert(h.access(0,0,true,7,15,origin)._2)
        assert(h.access(0,0x0c,true,0x55,15,origin)._2)
        assert(h.access(0,0,origin=origin)._2)
      }
      assert(h.rd(0,0)==0 && ((h.rd(0,0x14)>>8)&31)==0)
      for(offset <- Seq(1,2,3,0x24,0xfc,0x100)) assert(h.access(0,offset,true,1)._2)
      for(mask <- 0 until 16) {
        h.wr(0,4,0x1234)
        h.wr(0,4,0xabcd,mask)
        val expected=(if((mask&1)!=0)0xcd else 0x34)|(if((mask&2)!=0)0xab00 else 0x1200)
        assert(h.rd(0,4)==expected,s"UART_REGISTER_MODEL byte mask $mask")
      }
      h.wr(0,0,7,0);assert(h.rd(0,0)==0)
      h.wr(0,0x10,0xff);assert(h.rd(0,0x10)==0) // RO write ignored.
      for(badBaud <- Seq(0,8193,65535)) {
        h.wr(0,0,3);h.wr(0,4,badBaud);h.wr(0,8,1)
        assert(h.rd(0,0x20)==0 && (h.rd(0,0x18)&16)!=0)
        h.wr(0,0x18,16)
      }
      h.configure(0,65535,tx=false,rx=false)
      assert(h.rd(0,4)==65535 && h.rd(0,0x20)==(BigInt(65535)<<16))
      h.wr(0,0,3);h.wr(0,8,1)
      assert(h.rd(0,0x20)==(BigInt(65535)<<16) && (h.rd(0,0x18)&16)!=0)
      assert(!h.high(d.txEnable(0)) && !h.high(d.dmaRxRequest(0)))
      h.wr(0,0x18,16)
      h.configure(0,1,rx=false) // Minimum-period pin timing is covered by UartSerialSpec.
      h.configure(0,0,tx=false,rx=false)
      h.wr(0,0x1c,4);h.pop(0)
      assert((h.rd(0,0x18)&4)!=0 && h.high(d.irq(0)))
      h.wr(0,0x18,4,0);assert((h.rd(0,0x18)&4)!=0)
      h.wr(0,0x18,4);assert(!h.high(d.irq(0)))
      // Every TX byte-enable combination; only lane zero delivers a command.
      for(mask <- 0 until 16) {
        h.wr(0,8,4);h.wr(0,0x0c,0x1200+mask,mask)
        assert(((h.rd(0,0x14)>>8)&31)==(mask&1))
        assert(h.rd(0,0x0c)==0)
      }
      h.wr(0,8,4)
      for(byte <- 0 until 8)h.wr(0,0x0c,byte)
      h.wr(0,0x0c,0x99)
      assert(((h.rd(0,0x14)>>8)&31)==8 && (h.rd(0,0x18)&1)!=0)
      assert(h.high(d.clockHold(0)) && !h.high(d.quiescent(0)))
      h.wr(0,0,1);h.wr(0,4,4096);h.wr(0,8,1,0)
      assert(h.rd(0,0x20)==0 && ((h.rd(0,0x14)>>8)&31)==8)
      h.wr(0,8,5) // APPLY+flush sees pre-edge nonempty.
      assert(h.rd(0,0x20)==0 && (h.rd(0,0x18)&16)!=0)
      assert(((h.rd(0,0x14)>>8)&31)==0)
      h.wr(0,8,1);assert(h.rd(0,0x20)==((BigInt(4096)<<16)|1))
      h.wr(0,0x18,63);h.wr(0,0x1c,2)
      assert(h.high(d.dmaTxRequest(0)) && h.high(d.irq(0)))
    }
  }
  test("TX queues drain across sleep, preserve order, reject full writes and retain active frame on flush") {
    simulateRaw(new UartBench(UartTestFiles.json)) { d =>
      val h=new UartDriver(d);h.reset();h.configure(0,512,rx=false)
      h.wr(0,0x1c,8);h.beginCapture()
      for(byte <- 0 to 8)h.wr(0,0x0c,byte)
      h.wr(0,0x0c,0xee)
      assert(((h.rd(0,0x14)>>8)&31)==8 && (h.rd(0,0x18)&1)!=0)
      assert(!h.high(d.dmaTxRequest(0)))
      h.wr(0,0,0);h.wr(0,8,1)
      assert((h.rd(0,0x20)&1)==1 && (h.rd(0,0x18)&16)!=0)
      d.sleepRequest(0).poke(true.B);d.sleepMode(0).poke(1.U)
      assert(h.high(d.clockHold(0)))
      h.step(9*1280+64)
      UartPinModel.check(h.traces(0).toSeq,512,false,0 to 8)
      assert(h.high(d.quiescent(0)) && !h.high(d.clockHold(0)))
      assert(h.high(d.irq(0)) && (h.rd(0,0x18)&32)!=0)
      h.wr(0,0x18,63);assert(!h.high(d.irq(0)))
      d.sleepRequest(0).poke(false.B)
      h.beginCapture();h.wr(0,0x0c,0x5a);h.wr(0,0x0c,0xa5);h.wr(0,8,4)
      h.step(1400)
      UartPinModel.check(h.traces(0).toSeq,512,false,Seq(0x5a))
    }
  }
  test("RX FIFO preserves peek/pop order, overflow, bad-stop and false-start handling") {
    simulateRaw(new UartBench(UartTestFiles.json)) { d =>
      val h=new UartDriver(d);h.reset();h.configure(0,4096,tx=false)
      h.wr(0,0x1c,1)
      h.send(0,0 until 10,16.0)
      assert(((h.rd(0,0x14)>>16)&31)==8 && (h.rd(0,0x18)&2)!=0)
      assert(h.high(d.irq(0)) && h.high(d.dmaRxRequest(0)))
      h.wr(0,8,2,0);h.wr(0,8,2,2);h.wr(0,0x18,2,2)
      assert(((h.rd(0,0x14)>>16)&31)==8 && (h.rd(0,0x18)&2)!=0)
      h.checkBytes(0,0 until 8)
      assert(!h.high(d.irq(0)) && !h.high(d.dmaRxRequest(0)))
      h.wr(0,0x18,63)
      d.rx(0).poke(false.B);h.step(2);d.rx(0).poke(true.B);h.step(40)
      assert(h.rd(0,0x10)==0 && h.rd(0,0x18)==0)
      h.send(0,Seq(0x47),16.0,goodStop=false)
      assert(h.rd(0,0x10)==0 && (h.rd(0,0x18)&8)!=0)
      h.wr(0,0x18,8);h.send(0,Seq(0xc3),16.0);h.checkBytes(0,Seq(0xc3))
      // Flush during reception removes queued old bytes, not the active frame.
      h.send(0,Seq(0x11),16.0)
      val duration=h.schedule(0,Seq(0x22),16.0)
      h.step(32);h.wr(0,8,8);h.step(duration)
      h.checkBytes(0,Seq(0x22))
      h.send(0,Seq(0x33),16.0)
      h.wr(0,0,0);h.wr(0,8,9) // APPLY+RX flush still rejects pre-edge data.
      assert((h.rd(0,0x20)&2)!=0 && (h.rd(0,0x18)&16)!=0)
      assert(h.rd(0,0x10)==0)
    }
  }
}
