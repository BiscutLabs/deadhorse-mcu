package deadhorse.i2c_host

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class I2cControlSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t17/control-simulation").toAbsolutePath
  }
  private def until(h: I2cDriver, bound: Int = 4000)(condition: => Boolean): Unit = {
    val end = h.cycles + bound
    while(!condition && h.cycles < end) h.step()
    require(condition, "I2C_CONTROL_MODEL deadline")
  }
  private def released(h: I2cDriver): Boolean = !h.high(h.d.sclLow) && !h.high(h.d.sdaLow)

  test("register ownership, byte masks, decode and atomic configuration follow the contract") {
    simulateRaw(new I2cBench(I2cTestFiles.json)) { d =>
      val h = new I2cDriver(d); h.reset()
      assert(released(h) && !h.high(d.pinsEnable) && !h.high(d.irq) && h.high(d.quiescent))
      assert(h.rd(0) == 0 && h.rd(4) == I2cTiming(8,24,22,120).word && h.rd(8) == 65535)
      assert(h.rd(0x14) == 0 && h.rd(0x1c) == 0)
      for(origin <- 0 until 8 if origin != 3; off <- Seq(0,4,8,12,16,20,24,28,32,36,40)) {
        assert(h.access(off, origin = origin) == (BigInt(0), true))
        assert(h.access(off, true, 0xffffffffL, origin = origin) == (BigInt(0), true))
      }
      assert(h.rd(0) == 0 && h.rd(4) == I2cTiming(8,24,22,120).word)
      assert(h.rd(8) == 65535 && h.rd(0x10) == 0 && h.rd(0x1c) == 0 && h.rd(0x20) == 0)
      assert((h.rd(0x18) & 15) == 0 && released(h) && !h.high(d.pinsEnable))
      for(off <- Seq(1,2,3,0x2c,0xfc,0x100)) assert(h.access(off)._2)
      var model = h.rd(4)
      for(mask <- 0 until 16) {
        val value = BigInt("a173c952",16) ^ BigInt(mask * 0x01010101L)
        for(lane <- 0 until 4 if (mask & (1 << lane)) != 0) {
          val bits = BigInt(255) << (8 * lane)
          model = (model & ~bits) | (value & bits)
        }
        h.wr(4, value, mask); assert(h.rd(4) == model)
      }
      h.configure(); val active = h.rd(0x24)
      for((timing, timeout) <- Seq((I2cTiming(0,12,8,16),100), (I2cTiming(3,3,8,16),100),
        (I2cTiming(3,12,3,16),100), (I2cTiming(3,12,8,3),100), (I2cTiming(3,12,8,16),0))) {
        h.wr(4,timing.word); h.wr(8,timeout)
        assert(h.command(32) == 16 && h.rd(0x24) == active && h.rd(0x28) == 65535)
      }
      h.configure(I2cTiming(0,0,0,0), timeout = 0, enable = false)
      assert(h.command(1) == 16 && released(h))
      h.configure(); h.wr(0x20,16)
      assert(h.command(3) == 16 && h.high(d.irq) && released(h))
      h.wr(0x1c,16); h.step(3); assert(!h.high(d.irq))
    }
  }

  test("RX retention, pre-edge READ rejection, command conflicts and sleep draining") {
    simulateRaw(new I2cBench(I2cTestFiles.json)) { d =>
      val h = new I2cDriver(d); h.reset(); h.configure(); h.start(); h.writeByte(0x42)
      h.readByte(0x69, ack = true); h.wr(0x20,128); assert(h.high(d.irq))
      assert(h.command(1 | 2 | 128) == 16 && (h.rd(0x18) & 4) != 0)
      assert(h.command(4 | 128) == 16 && (h.rd(0x18) & 4) == 0 && h.rd(0x14) == 0x69)
      assert(!h.high(d.irq)); h.readByte(0xa7, ack = false); h.wr(12,128)
      d.sleepRequest.poke(true.B)
      h.writeByte(0x55); h.start(); h.stop()
      assert(h.command(1) == 16 && h.command(16) == 16 && released(h))
      d.sleepEnable.poke(true.B); h.start(); h.stop()
      assert(h.rd(0x14) == 0xa7 && (h.rd(0x18) & 8) != 0)
    }
  }

  test("16-bit watchdog expires on the exact 255, 256 and 257 waiting edge and retains RX/ACK") {
    simulateRaw(new I2cBench(I2cTestFiles.json)) { d =>
      val h = new I2cDriver(d)
      for(deadline <- Seq(255,256,257)) {
        h.reset(); h.configure(timeout = deadline); h.start(); h.writeByte(0x00)
        h.readByte(0x96, ack = false)
        h.forceScl = true; h.wr(0x10,0); h.wr(0x1c,127); h.wr(12,2)
        until(h)(!h.high(d.sclLow)); val began = h.cycles
        assert(h.high(d.sdaLow))
        until(h,deadline + 2)(!h.high(d.sdaLow))
        assert(h.cycles - began == deadline, s"I2C_TIMEOUT_MODEL ${h.cycles-began} != $deadline")
        assert(h.rd(0x1c) == 8 && (h.rd(0x18) & 15) == 12 && h.rd(0x14) == 0x96)
        h.step(3); assert(released(h) && !h.high(d.clockHold))
      }
    }
  }

  test("polls, POP and rejected owned-idle commands never refresh the watchdog") {
    simulateRaw(new I2cBench(I2cTestFiles.json)) { d =>
      val h = new I2cDriver(d)
      def expiry(traffic: Boolean): Int = {
        h.reset(); h.configure(timeout = 257); h.start()
        val reference = h.peer.starts.last
        if(traffic) while(h.high(d.sclLow)) {
          h.rd(0x18); h.rd(0x1c); h.wr(12,32); h.wr(12,128)
        } else until(h,300)(!h.high(d.sclLow))
        val releasedAt = h.samples.find(s => s.cycle > h.peer.falls.head && !s.sclLow).get.cycle
        assert((h.rd(0x1c) & 8) != 0 && released(h))
        releasedAt - reference
      }
      assert(expiry(false) == expiry(true))
    }
  }

  test("arbitration and unexpected high-phase SCL loss release ownership without retry") {
    simulateRaw(new I2cBench(I2cTestFiles.json)) { d =>
      val h = new I2cDriver(d); h.reset(); h.configure(); h.start()
      h.forceSda = true; h.wr(0x10,255)
      assert(h.command(2) == 4 && released(h) && (h.rd(0x18) & 3) == 0)
      h.reset(); h.configure(I2cTiming(4,12,30,16)); h.start(); h.wr(0x10,0)
      h.wr(0x1c,127); h.wr(12,2)
      until(h)(h.high(d.scl)); h.step(7); h.forceScl = true
      assert(h.waitEvent() == 64 && released(h) && (h.rd(0x18) & 3) == 0)
    }
  }

  test("three-sample filtering rejects one/two sample SCL spikes and accepts sustained changes") {
    simulateRaw(new I2cBench(I2cTestFiles.json)) { d =>
      val h = new I2cDriver(d)
      def startAt(width: Int): Int = {
        h.reset(); h.configure(I2cTiming(3,12,8,80), timeout = 2000); h.wr(0x1c,127)
        val offered = h.cycles
        h.beforeStep = cycle => { h.forceScl = cycle >= offered + 15 && cycle < offered + 15 + width }
        h.wr(12,1); assert(h.waitEvent() == 1)
        h.beforeStep = _ => (); h.forceScl = false
        h.peer.starts.head - offered
      }
      val baseline = startAt(0)
      assert(startAt(1) == baseline && startAt(2) == baseline)
      assert(startAt(3) > baseline, "I2C_FILTER_MODEL sustained low was ignored")
    }
  }

  test("RECOVER issues nine complete pulses then STOP; held-low lines cause bounded failure") {
    simulateRaw(new I2cBench(I2cTestFiles.json)) { d =>
      val h = new I2cDriver(d); h.reset(); h.configure(timeout = 512)
      h.forceSda = true; h.step(10); h.peer.starts.clear(); h.peer.rises.clear(); h.peer.falls.clear()
      h.afterStep = () => { if(h.peer.rises.size >= 3 && !h.high(d.scl)) h.forceSda = false }
      assert(h.command(16) == 33)
      assert(h.peer.rises.size == 10 && h.peer.falls.size == 10 && h.peer.starts.isEmpty && h.peer.stops.size == 1)
      assert(released(h) && !h.high(d.clockHold))
      h.reset(); h.configure(timeout = 128); h.forceSda = true
      assert(h.command(16) == 8 && released(h) && (h.rd(0x18) & 3) == 0)
      h.reset(); h.configure(timeout = 128); h.forceScl = true
      assert(h.command(16) == 8 && released(h))
    }
  }

  test("reset during an active byte releases outputs, clears state and suppresses stale work") {
    simulateRaw(new I2cBench(I2cTestFiles.json)) { d =>
      val h = new I2cDriver(d); h.reset(); h.configure(); h.start(); h.wr(0x10,0)
      h.wr(0x1c,127); h.wr(12,2); until(h)(h.high(d.sdaLow))
      h.reset()
      assert(released(h) && !h.high(d.pinsEnable) && !h.high(d.clockHold))
      assert((h.rd(0x18) & 15) == 0 && h.rd(0x14) == 0 && h.rd(0x1c) == 0)
      h.step(300); assert(h.rd(0x1c) == 0 && released(h))
    }
  }

  test("busy rejection and shadow writes cannot tear the active byte or timing") {
    simulateRaw(new I2cBench(I2cTestFiles.json)) { d =>
      val h = new I2cDriver(d); h.reset(); h.configure(); h.start()
      val active = h.rd(0x24); val f = h.peer.arm(false,0x5a,true)
      h.wr(0x10,0x5a); h.wr(0x1c,127); h.wr(12,2)
      h.wr(0x10,0xa5); h.wr(4,I2cTiming(10,90,90,90).word); h.wr(12,32); h.wr(12,1)
      until(h)(h.peer.current.isEmpty); h.step(10)
      assert(h.rd(0x1c) == 17 && f.observed == 0x5a && h.rd(0x24) == active)
      val periods = f.rises.sliding(2).map(p => p(1)-p(0)).toSeq
      require(periods.distinct.size == 1, "I2C_CONTROL_MODEL shadow update changed bit timing")
      h.stop()
    }
  }

  test("POP immediately before, on and after READ completion obeys arrival priority") {
    simulateRaw(new I2cBench(I2cTestFiles.json)) { d =>
      val h = new I2cDriver(d)
      // Calibrate the public MMIO-to-command latency using RECOVER's first
      // pull-low edge. No internal pulse or implementation counter is observed.
      h.reset(); h.configure(); h.wr(0x1c,127)
      val offered = h.cycles; h.wr(12,16)
      val commandLatency = h.peer.falls.head - offered
      assert(commandLatency > 0 && commandLatency < 12)
      for(offset <- Seq(-1,0,1)) {
        h.reset(); h.configure(I2cTiming(12,12,8,16)); h.start()
        val f = h.peer.arm(true,0x69,true); h.wr(0x1c,127); h.wr(12,4 | 64)
        until(h)(f.falls.size == 9)
        val completeAt = f.falls.last + 12
        val offerAt = completeAt + offset - commandLatency
        assert(h.cycles <= offerAt); h.step(offerAt - h.cycles); h.wr(12,128)
        assert(((h.rd(0x18) & 4) != 0) == (offset <= 0), s"I2C_POP_MODEL offset=$offset")
        assert(h.rd(0x14) == 0x69 && h.rd(0x1c) == 1)
        val release = h.samples.find(s => s.cycle >= f.falls.last && !s.sdaLow).get.cycle
        assert(release == completeAt, "I2C_POP_MODEL final ACK hold/completion edge")
      }
    }
  }

  test("phase completion on the timeout edge wins; bus chatter never extends a failed FREE wait") {
    simulateRaw(new I2cBench(I2cTestFiles.json)) { d =>
      val h = new I2cDriver(d)
      h.reset(); h.configure(I2cTiming(3,12,8,255), timeout = 255)
      assert(h.command(1) == 1 && (h.rd(0x18) & 3) == 2)
      h.reset(); h.configure(I2cTiming(3,12,8,255), timeout = 254)
      assert(h.command(1) == 8 && h.peer.starts.isEmpty && released(h))
      def failureAt(chatter: Boolean): Int = {
        h.reset(); h.configure(I2cTiming(3,12,8,80), timeout = 64)
        h.wr(0x1c,127); val offered = h.cycles
        if(chatter) h.beforeStep = cycle => { h.forceScl = ((cycle - offered) % 12) < 6 }
        h.wr(12,1); assert(h.waitEvent() == 8)
        h.beforeStep = _ => (); h.forceScl = false
        assert(h.peer.starts.isEmpty && released(h))
        h.cycles - offered
      }
      assert(failureAt(false) == failureAt(true))
    }
  }

  test("stretched-clock progress at expiry wins and one-edge-late progress times out") {
    simulateRaw(new I2cBench(I2cTestFiles.json)) { d =>
      val h = new I2cDriver(d); val timing = I2cTiming(3,12,8,16)
      h.reset(); h.configure(timing); h.start()
      val calibration = h.writeByte(0)
      // Measure feedback observation delay through the public wires; HIGH is
      // configured independently. This isolates timeout priority from latency.
      val feedback = calibration.falls.head - calibration.rises.head - timing.high
      assert(feedback > 0)
      for(late <- Seq(0,1)) {
        h.reset(); h.configure(timing, timeout = 255); h.start()
        h.forceScl = true; h.wr(0x10,0); h.wr(0x1c,127); h.wr(12,2)
        until(h)(!h.high(d.sclLow)); val began = h.cycles
        val releaseAt = began + 255 - feedback + late
        // Release after the sampled edge, matching the calibration pin-rise phase.
        h.afterStep = () => { if(h.cycles >= releaseAt) h.forceScl = false }
        until(h,270)(h.high(d.sclLow) || !h.high(d.sdaLow))
        if(late == 0) assert(h.high(d.sclLow) && h.high(d.sdaLow) && (h.rd(0x1c) & 8) == 0)
        else assert(released(h) && h.rd(0x1c) == 8)
        h.afterStep = () => ()
      }
    }
  }
  test("early SDA contention during repeated START aborts even if the dip clears before the guard ends") {
    simulateRaw(new I2cBench(I2cTestFiles.json)) { d =>
      val h = new I2cDriver(d); h.reset(); h.configure(I2cTiming(3,12,8,80), timeout = 1024); h.start()
      h.wr(0x1c,127); h.wr(12,1); until(h)(h.high(d.scl))
      val rose = h.cycles; h.step(8); h.forceSda = true; h.step(10); h.forceSda = false
      assert(h.cycles < rose + 80)
      assert(h.waitEvent() == 4 && released(h) && (h.rd(0x18) & 3) == 0)
      assert(h.samples.filter(_.cycle >= rose).forall(!_.sdaLow), "I2C_RESTART_MODEL deliberately emitted START after contention")
    }
  }
  test("control transaction oracle rejects an actual transmitted-bit mutation") {
    simulateRaw(new I2cBench(I2cTestFiles.json, corrupt = true)) { d =>
      val h = new I2cDriver(d); h.reset(); h.configure(); h.start()
      val failure = intercept[IllegalArgumentException] { h.writeByte(0) }
      assert(failure.getMessage.contains("I2C_PEER_DATA"))
    }
  }
}
