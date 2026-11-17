package deadhorse.uart

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class UartSleepSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t15/sleep-simulation").toAbsolutePath
  }
  test("receive mode holds HF; disabled and wake-only retain unread data and finish an existing RX frame") {
    simulateRaw(new UartBench(UartTestFiles.json)) { d =>
      val h=new UartDriver(d);h.reset();h.configure(0,4096)
      for(mode <- Seq(0,1,2,3)) {
        d.sleepRequest(0).poke(false.B);h.step(8)
        h.send(0,Seq(0x40+mode),16.0)
        d.sleepMode(0).poke(mode.U);d.sleepRequest(0).poke(true.B);h.step(8)
        assert(h.high(d.quiescent(0)))
        assert(h.high(d.clockHold(0))==(mode==2))
        h.send(0,Seq(0x70+mode),16.0)
        val expected=if(mode==2)Seq(0x40+mode,0x70+mode) else Seq(0x40+mode)
        h.checkBytes(0,expected)
      }
      d.sleepRequest(0).poke(false.B);h.step(8)
      val length=h.schedule(0,Seq(0x31,0x59),16.0)
      h.step(36)
      assert((h.rd(0,0x14)&8)!=0)
      d.sleepMode(0).poke(0.U);d.sleepRequest(0).poke(true.B)
      assert(h.high(d.clockHold(0)))
      h.step(length+32)
      h.checkBytes(0,Seq(0x31))
      assert(!h.high(d.clockHold(0)) && h.high(d.quiescent(0)))
    }
  }
  test("asynchronous reset aborts active TX and RX and removes all queued work") {
    simulateRaw(new UartBench(UartTestFiles.json)) { d =>
      val h=new UartDriver(d);h.reset();h.configure(0,2048)
      h.wr(0,0x0c,0x55);h.wr(0,0x0c,0xaa)
      h.schedule(0,Seq(0x42),32.0);h.step(64)
      assert((h.rd(0,0x14)&12)!=0)
      d.reset_n.poke(false.B)
      assert(!h.high(d.txEnable(0)) && h.high(d.tx(0)))
      assert(!h.high(d.bus(0).rvalid) && !h.high(d.irq(0)))
      h.reset()
      assert(h.rd(0,0x20)==0 && h.rd(0,0x18)==0)
      assert(((h.rd(0,0x14)>>8)&0x1f1f)==0)
      h.configure(0,4096);h.send(0,Seq(0x91),16.0);h.checkBytes(0,Seq(0x91))
      // Reset a granted request before its registered response is presented.
      val p=d.bus(0)
      p.bits.addr.poke(BigInt("40010014",16).U);p.bits.we.poke(false.B)
      p.bits.be.poke(15.U);p.bits.origin.poke(1.U);p.req.poke(true.B)
      for(_ <- 0 until 16 if !h.high(p.gnt))h.step()
      assert(h.high(p.gnt));h.step();p.req.poke(false.B)
      d.reset_n.poke(false.B);assert(!h.high(p.rvalid))
      h.step(2);d.reset_n.poke(true.B)
      for(_ <- 0 until 12) {h.step();assert(!h.high(p.rvalid),"UART_RESET_MODEL stale response")}
      assert(h.rd(0,0x20)==0)
    }
  }
  test("AON wake survives stopped HF, captures over clear, honors inversion handoff and never fabricates idle wake") {
    simulateRaw(new UartBench(UartTestFiles.json)) { d =>
      val h=new UartDriver(d);h.reset()
      // Armed on reset release with idle-high wire must not wake from CDC reset.
      d.wakeReset_n.poke(false.B);d.armed.poke(true.B);d.rx(0).poke(true.B)
      d.aon.step(2);d.wakeReset_n.poke(true.B)
      for(_ <- 0 until 12) {d.aon.step();assert(!h.high(d.wake))}
      h.configure(0,4096,tx=false)
      h.send(0,Seq(0x77),16.0)
      d.sleepRequest(0).poke(true.B);d.sleepMode(0).poke(1.U);h.step(8)
      assert(!h.high(d.clockHold(0)) && h.high(d.quiescent(0)))
      val stoppedAt=h.clocks
      // A pulse entirely between AON edges is intentionally not edge-latched.
      d.rx(0).poke(false.B);d.rx(0).poke(true.B);d.aon.step(5)
      assert(!h.high(d.wake))
      d.rx(0).poke(false.B);d.aon.step(4)
      assert(h.high(d.wake) && h.high(d.wakeClockRequest))
      assert(h.clocks==stoppedAt)
      d.clear.poke(true.B);d.aon.step(2)
      assert(h.high(d.wake),"UART_WAKE_MODEL capture must win clear")
      d.clear.poke(false.B);d.armed.poke(false.B);d.rx(0).poke(true.B);d.aon.step(4)
      assert(h.high(d.wake),"UART_WAKE_MODEL disarming erased pending wake")
      d.clear.poke(true.B);d.aon.step();assert(!h.high(d.wake));d.clear.poke(false.B)
      // Restarted HF retains the earlier byte; preamble is not a new RX credit.
      h.step(32);h.checkBytes(0,Seq(0x77))
      d.sleepRequest(0).poke(false.B);h.step(20)
      h.send(0,Seq(0xa6),16.0);h.checkBytes(0,Seq(0xa6))
      // Inversion changes only while disarmed, followed by four AON settle edges.
      d.invert.poke(true.B);d.rx(0).poke(false.B);d.aon.step(4)
      d.armed.poke(true.B);d.aon.step(5);assert(!h.high(d.wake))
      d.rx(0).poke(true.B);d.aon.step(4);assert(h.high(d.wake))
      d.wakeReset_n.poke(false.B);assert(!h.high(d.wake) && !h.high(d.wakeClockRequest))
    }
  }
}
