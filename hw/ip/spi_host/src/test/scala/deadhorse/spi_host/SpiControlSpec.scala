package deadhorse.spi_host

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SpiControlSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t16/control-simulation").toAbsolutePath
  }
  test("owner checked generated registers reject invalid commands and honor strobes and queue boundaries") {
    simulateRaw(new SpiBench(SpiTestFiles.json)) { d =>
      val h=new SpiDriver(d);h.reset()
      assert(d.cs_n.peek().litValue==3 && !h.high(d.pinsEnable) && !h.high(d.sclk) && !h.high(d.mosi))
      assert(h.rd(0)==0 && h.rd(4)==3 && h.rd(8)==1 && h.rd(0x28)==0)
      for(origin <- 0 until 8 if origin!=3) {
        assert(h.access(0,true,7,15,origin)._2)
        assert(h.access(0x10,true,0x55,15,origin)._2)
        assert(h.access(0,origin=origin)._2)
      }
      for(offset <- Seq(1,2,3,0x2c,0xfc,0x100))assert(h.access(offset,true,1)._2)
      for(mask <- 0 until 16) {
        h.wr(4,7);h.wr(4,19,mask);assert(h.rd(4)==(if((mask&1)!=0)19 else 7))
        h.wr(12,8);h.wr(0x10,0x55,mask);assert(((h.rd(0x18)>>8)&31)==(mask&1))
      }
      h.wr(12,8)
      h.wr(0,1)
      for(half <- 0 until 3) {h.wr(4,half);h.wr(12,1);assert((h.rd(0x1c)&8)!=0 && !h.high(d.pinsEnable));h.wr(0x1c,31)}
      h.configure(half=0,enable=false);h.wr(12,2)
      assert((h.rd(0x1c)&8)!=0 && h.rd(0x28)==0)
      h.configure();h.wr(0x1c,31);h.wr(0x20,4)
      h.wr(12,4);assert((h.rd(0x1c)&4)!=0 && h.high(d.irq))
      h.wr(0x1c,4,0);assert(h.high(d.irq));h.wr(0x1c,4);assert(!h.high(d.irq))
      for(byte <- 0 until 16)h.wr(0x10,byte)
      assert(!h.high(d.dmaTxRequest));h.wr(0x10,0xee)
      assert(((h.rd(0x18)>>8)&31)==16 && (h.rd(0x1c)&1)!=0)
      for(length <- Seq(0,17,31)) {h.wr(8,length);h.wr(12,2);assert((h.rd(0x1c)&8)!=0 && d.cs_n.peek().litValue==3)}
      h.wr(8,16);h.wr(12,2|8|4) // Entire conflicting command is inert.
      assert(((h.rd(0x18)>>8)&31)==16 && (h.rd(0x1c)&4)==0 && h.rd(0x28)==0)
      h.wr(0,3);h.wr(12,1|8) // APPLY uses old nonempty state; flush still legal.
      assert((h.rd(0x24)&7)==1 && ((h.rd(0x18)>>8)&31)==0)
      h.wr(12,1);assert((h.rd(0x24)&7)==3 && h.high(d.sclk))
    }
  }
  test("busy start flush apply and shadow updates cannot tear a transfer; sleep drains and DMA IRQ reflect queues") {
    simulateRaw(new SpiBench(SpiTestFiles.json)) { d =>
      val h=new SpiDriver(d);h.reset()
      val tx=Seq(0x13,0x57,0x9b,0xdf);val rx=Seq(0xe1,0xa5,0x69,0x2d)
      val p=h.prepare(tx,rx,half=16);h.wr(0x20,8);h.wr(12,2)
      d.sleepRequest.poke(true.B);h.step(2);assert(h.high(d.clockHold))
      h.wr(12,2);h.wr(12,8|16);h.wr(0,7);h.wr(4,3);h.wr(8,1);h.wr(12,1)
      assert((h.rd(0x24)&0xffff)==0x1001 && (h.rd(0x1c)&8)!=0)
      h.finish(p);assert(h.high(d.irq) && h.high(d.dmaRxRequest) && h.high(d.dmaTxRequest))
      assert(!h.high(d.clockHold));h.checkRx(rx);assert(!h.high(d.dmaRxRequest))
      h.wr(0x1c,31);assert(!h.high(d.irq))
      h.peer=None;h.configure();h.wr(0x10,0xa6);h.wr(8,1)
      val prior=h.rd(0x28);h.wr(12,2)
      assert(d.cs_n.peek().litValue==3 && h.rd(0x28)==prior && h.high(d.clockHold))
      d.sleepEnable.poke(true.B)
      val q=new SpiPeer(false,0,3,Seq(0xa6),Seq(0x3c));h.peer=Some(q)
      h.wr(12,2);h.finish(q);h.checkRx(Seq(0x3c))
    }
  }
  test("RX reservation uses pre-edge occupancy and rejected START allows independent POP; reset cancels bus and pins") {
    simulateRaw(new SpiBench(SpiTestFiles.json,2)) { d =>
      val h=new SpiDriver(d);h.reset()
      val p=h.prepare(Seq(0xa5,0x5a),Seq(0x11,0x22));h.wr(12,2);h.finish(p)
      h.wr(0x10,0x44);h.wr(8,1);val old=h.rd(0x28)
      h.wr(12,2|4) // Full RX rejects START despite simultaneous POP.
      assert(h.rd(0x28)==old && ((h.rd(0x18)>>8)&31)==1 && ((h.rd(0x18)>>16)&31)==1)
      assert(h.rd(0x14)==0x22 && (h.rd(0x1c)&8)!=0)
      val q=new SpiPeer(false,0,3,Seq(0x44),Seq(0x33));h.peer=Some(q)
      h.wr(12,2);h.finish(q);h.checkRx(Seq(0x22,0x33))
      h.configure(half=16);h.wr(0x10,0x69);h.wr(12,2);h.step(20)
      assert(d.cs_n.peek().litValue!=3);d.reset_n.poke(false.B)
      assert(d.cs_n.peek().litValue==3 && !h.high(d.pinsEnable) && !h.high(d.irq))
      h.reset();assert(h.rd(0x28)==0 && h.rd(0x1c)==0 && ((h.rd(0x18)>>8)&0x1f1f)==0)
      // Accepted bus transaction is abandoned by reset; no old response leaks.
      d.bus.req.poke(true.B);d.bus.bits.addr.poke(BigInt("40011018",16).U)
      d.bus.bits.we.poke(false.B);d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(3.U)
      for(_ <- 0 until 16 if !h.high(d.bus.gnt))h.step()
      assert(h.high(d.bus.gnt));h.step();d.bus.req.poke(false.B);d.reset_n.poke(false.B)
      assert(!h.high(d.bus.rvalid));h.step(2);d.reset_n.poke(true.B)
      for(_ <- 0 until 12) {h.step();assert(!h.high(d.bus.rvalid))}
    }
  }
}
