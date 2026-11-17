package deadhorse.uart

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

object UartTestFiles {
  def json: String = {
    os.proc("python3","hw/regmap/regmap.py","hw/ip/uart/uart.regmap.yaml","--out","build/t15/test-regmap").call()
    "build/t15/test-regmap/uart_regs.json"
  }
}

class UartSerialSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t15/serial-simulation").toAbsolutePath
  }
  test("minimum baud increment preserves every TX carry boundary and receives a batched 8N1 frame") {
    simulateRaw(new UartBench(UartTestFiles.json)) { d =>
      val h=new UartDriver(d);h.reset();h.configure(0,1,rx=false)
      val before=h.clocks
      h.beginCapture();h.wr(0,0x0c,0x55)
      val startOffset=h.traces(0).indexWhere(level => !level)
      assert(startOffset>=0,"UART_MIN_MODEL missing start")
      val started=before+startOffset
      val frame=UartPinModel.frame(0x55)
      h.capture=false
      for(boundary <- 1 to 10) {
        val beforeEdge=started+boundary*65536-1
        assert(beforeEdge>=h.clocks)
        h.step(beforeEdge-h.clocks)
        assert(h.high(d.tx(0))==frame(boundary-1),s"UART_MIN_MODEL early boundary $boundary")
        assert(!h.high(d.quiescent(0)),s"UART_MIN_MODEL early completion $boundary")
        h.step()
        val next=if(boundary<10)frame(boundary) else true
        assert(h.high(d.tx(0))==next,s"UART_MIN_MODEL late boundary $boundary")
      }
      h.step(4)
      assert(h.high(d.quiescent(0)) && (h.rd(0,0x18)&32)!=0)
      h.configure(0,1,tx=false)
      // Independent fixed-period peer; batch each bit instead of 655k peeks.
      for(level <- UartPinModel.frame(0xa6)) {d.rx(0).poke(level.B);h.step(65536)}
      d.rx(0).poke(true.B);h.step(32)
      h.checkBytes(0,Seq(0xa6))
      assert((h.rd(0,0x18)&31)==0)
    }
  }
  test("8N1 fractional TX and independent RX peers at 9, 12 and 24 MHz, inversion and one percent mismatch") {
    val seed=0x15baL
    println(s"UART serial seed=$seed")
    val random=new scala.util.Random(seed)
    val bytes=Seq(0,255,0x55,0xaa)++Seq.fill(4)(random.nextInt(256))
    simulateRaw(new UartBench(UartTestFiles.json)) { d =>
      val h=new UartDriver(d)
      for(hz <- Seq(9000000,12000000,24000000); inverted <- Seq(false,true)) {
        h.reset()
        val increment=UartPinModel.increment(hz)
        val period=65536.0/increment
        h.configure(0,increment,inverted=inverted)
        h.beginCapture()
        bytes.foreach(byte => h.wr(0,0x0c,byte))
        h.step(math.ceil(bytes.size*(10*period+8)).toInt)
        UartPinModel.check(h.traces(0).toSeq,increment,inverted,bytes)
        h.capture=false
        assert((h.rd(0,0x18)&32)!=0)
        assert(h.high(d.dmaTxRequest(0)))
        // Peer period derives from requested baud, not DUT accumulator state.
        for(error <- Seq(-0.01,0.0,0.01); phase <- Seq(0.0,0.25,0.5,0.75)) {
          h.send(0,bytes,hz/(921600.0*(1+error)),inverted,phase=phase)
          assert(h.high(d.dmaRxRequest(0)))
          h.checkBytes(0,bytes)
          assert(!h.high(d.dmaRxRequest(0)))
          assert((h.rd(0,0x18)&0x1f)==0,"UART_SERIAL_MODEL unexpected error")
        }
      }
    }
  }
  test("all byte values survive pin receive and the checker rejects corrupted real observations") {
    simulateRaw(new UartBench(UartTestFiles.json)) { d =>
      val h=new UartDriver(d);h.reset();h.configure(0,4096)
      for(bytes <- (0 until 256).grouped(8)) {h.send(0,bytes,16.0);h.checkBytes(0,bytes)}
      h.beginCapture();h.wr(0,0x0c,0x69);h.step(180)
      UartPinModel.check(h.traces(0).toSeq,4096,false,Seq(0x69))
      val damaged=h.traces(0).toArray
      val start=damaged.indexWhere(v => !v)
      damaged(start+24)= !damaged(start+24) // Actual observed first data-bit center.
      val failure=intercept[IllegalArgumentException] {
        UartPinModel.check(damaged.toSeq,4096,false,Seq(0x69))
      }
      assert(failure.getMessage.contains("UART_PIN_MODEL"))
      h.capture=false;h.send(0,Seq(0x3c),16.0)
      val realHead=h.rd(0,0x10)
      UartPinModel.checkHead(0x3c,realHead)
      val badHead=intercept[IllegalArgumentException] {UartPinModel.checkHead(0x3c,realHead ^ 1)}
      assert(badHead.getMessage.contains("UART_QUEUE_MODEL"))
      h.pop(0)
    }
  }
  test("three independently configured UARTs transmit and receive concurrently without cross-talk") {
    simulateRaw(new UartBench(UartTestFiles.json)) { d =>
      val h=new UartDriver(d);h.reset()
      val increments=Seq(2048,4096,8192)
      for(i <- 0 until 3) h.configure(i,increments(i),inverted=i==1)
      h.beginCapture()
      for(i <- 0 until 3) h.wr(i,0x0c,0x21+i*0x31)
      val duration=(0 until 3).map(i => h.schedule(i,Seq(0xa0+i,0x7e-i),65536.0/increments(i),i==1)).max
      h.step(duration+40)
      for(i <- 0 until 3) {
        UartPinModel.check(h.traces(i).toSeq,increments(i),i==1,Seq(0x21+i*0x31))
        h.checkBytes(i,Seq(0xa0+i,0x7e-i))
        assert((h.rd(i,0x18)&31)==0)
      }
    }
  }
}
