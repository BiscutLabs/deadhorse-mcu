package deadhorse.i2c_host

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class I2cSerialSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t17/serial-simulation").toAbsolutePath
  }
  private val settings = Seq(
    (9000000, 100000, I2cTiming(3, 42, 39, 43)),
    (12000000, 100000, I2cTiming(4, 56, 54, 57)),
    (24000000, 100000, I2cTiming(8, 112, 114, 113)),
    (9000000, 400000, I2cTiming(3, 9, 5, 12)),
    (12000000, 400000, I2cTiming(4, 12, 8, 16)),
    (24000000, 400000, I2cTiming(8, 24, 22, 32)))

  /** UM10204 Table 11 minima, evaluated on resolved wire edges. */
  private def checkTiming(h: I2cDriver, hz: Int, ceiling: Int, timing: I2cTiming): Unit = {
    val fast = ceiling == 400000
    def ticks(us: Double): Int = math.ceil(us * hz / 1e6).toInt
    val lowMin = ticks(if(fast) 1.3 else 4.7)
    val highMin = ticks(if(fast) 0.6 else 4.0)
    val setupMin = ticks(if(fast) 0.1 else 0.25)
    val periods = h.peer.frames.flatMap(_.rises.sliding(2).map(pair => pair(1) - pair(0))).toSeq
    require(periods.nonEmpty, "I2C_TIMING_MODEL missing clocks")
    periods.foreach { period =>
      val rate = hz.toDouble / period
      require(rate <= ceiling && rate >= 0.95 * ceiling, s"I2C_TIMING_MODEL rate $rate for $hz/$ceiling")
    }
    for(f <- h.peer.frames) {
      assert(f.rises.size == 9 && f.falls.size == 9)
      for(bit <- 0 until 9) {
        require(f.falls(bit) - f.rises(bit) >= highMin, "I2C_TIMING_MODEL high minimum")
        if(bit > 0) require(f.rises(bit) - f.falls(bit - 1) >= lowMin, "I2C_TIMING_MODEL low minimum")
        val transitions = h.samples.sliding(2).collect {
          case pair if pair(0).sda != pair(1).sda && pair(1).cycle <= f.rises(bit) => pair(1).cycle
        }.toSeq
        require(transitions.nonEmpty && f.rises(bit) - transitions.last >= setupMin, "I2C_TIMING_MODEL data setup")
      }
    }
    for(start <- h.peer.starts) {
      val fall = h.peer.falls.find(_ > start).get
      require(fall - start >= ticks(if(fast) 0.6 else 4.0), "I2C_TIMING_MODEL START hold")
      h.peer.rises.filter(_ < start).lastOption.foreach { rise =>
        require(start - rise >= ticks(if(fast) 0.6 else 4.7), "I2C_TIMING_MODEL repeated START setup")
      }
      h.peer.stops.filter(_ < start).lastOption.foreach { stop =>
        require(start - stop >= ticks(if(fast) 1.3 else 4.7), "I2C_TIMING_MODEL bus free")
      }
    }
    for(stop <- h.peer.stops) {
      val rise = h.peer.rises.filter(_ < stop).last
      require(stop - rise >= ticks(if(fast) 0.6 else 4.0), "I2C_TIMING_MODEL STOP setup")
    }
    // The programmed HOLD applies to host changes after SCL falls, including
    // START completion and the READ ACK release after its ninth falling edge.
    for(pair <- h.samples.sliding(2) if pair(0).sdaLow != pair(1).sdaLow && !pair(1).scl) {
      val b = pair(1)
      val fall = h.peer.falls.filter(_ <= b.cycle).last
      require(b.cycle - fall >= timing.hold, "I2C_TIMING_MODEL programmed SDA hold")
    }
    println(s"I2C measured periods=${periods.distinct.sorted.mkString(",")} HF edges; assumed HF=$hz; nominal=$ceiling; derived rates=${periods.distinct.sorted.map(p => hz.toDouble/p).mkString(",")}")
  }

  test("wire peer checks address/data, repeated START, final NACK/STOP and Standard/Fast timing") {
    simulateRaw(new I2cBench(I2cTestFiles.json)) { d =>
      val h = new I2cDriver(d)
      for((hz, rate, timing) <- settings) {
        h.reset(); h.configure(timing)
        h.start(); h.writeByte(0xee); h.writeByte(0x10)
        h.start(); h.writeByte(0xef)
        h.readByte(0xa5, ack = true); h.wr(12, 128)
        h.readByte(0x3c, ack = false); h.wr(12, 128)
        h.stop(); h.start(); h.writeByte(0x00, ack = false); h.stop()
        assert(h.peer.starts.size == 3 && h.peer.stops.size == 2)
        checkTiming(h, hz, rate, timing)
      }
    }
  }

  test("seeded bytes survive WRITE/READ and retained READ data survives POP") {
    val seed = 0x17cafeL; println(s"I2C byte seed=$seed")
    val random = new scala.util.Random(seed)
    val bytes = Seq(0, 255, 0x55, 0xaa) ++ Seq.fill(12)(random.nextInt(256))
    simulateRaw(new I2cBench(I2cTestFiles.json)) { d =>
      val h = new I2cDriver(d); h.reset(); h.configure(I2cTiming(4, 12, 8, 16)); h.start()
      bytes.foreach(value => h.writeByte(value))
      h.start()
      for((value, index) <- bytes.zipWithIndex) {
        h.readByte(value, ack = index != bytes.size - 1)
        h.wr(12, 128)
        assert((h.rd(0x18) & 4) == 0 && h.rd(0x14) == value)
      }
      h.stop()
    }
  }

  test("target clock stretching lengthens the low interval without losing a byte") {
    simulateRaw(new I2cBench(I2cTestFiles.json)) { d =>
      val h = new I2cDriver(d); h.reset(); h.configure(I2cTiming(4, 12, 8, 16), timeout = 2048); h.start()
      val f = h.peer.arm(false, 0x96, true); h.wr(0x10, 0x96)
      h.forceScl = true
      h.wr(0x1c, 127); h.wr(12, 2); h.step(150)
      assert(f.rises.isEmpty && (h.rd(0x18) & 3) == 3 && h.high(d.clockHold))
      h.forceScl = false
      assert(h.waitEvent() == 1 && f.observed == 0x96 && f.rises.size == 9)
      assert((h.rd(0x18) & 8) != 0)
      h.stop()
    }
  }

  test("register receive oracle rejects an actual completed READ mutation") {
    simulateRaw(new I2cBench(I2cTestFiles.json, corruptRead = true)) { d =>
      val h = new I2cDriver(d); h.reset(); h.configure(); h.start()
      val failure = intercept[IllegalArgumentException] { h.readByte(0x96, ack = false) }
      assert(failure.getMessage.contains("I2C_RX_MODEL"))
    }
  }
  test("pin peer rejects a real production WRITE output fault") {
    simulateRaw(new I2cBench(I2cTestFiles.json, corrupt = true)) { d =>
      val h = new I2cDriver(d); h.reset(); h.configure(); h.start()
      val failure = intercept[IllegalArgumentException] { h.writeByte(0x00) }
      assert(failure.getMessage.contains("I2C_PEER_DATA"))
    }
  }
}
