package deadhorse.i2c_recovery_loader

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class RecoveryLoaderSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t18/loader-simulation").toAbsolutePath
  }

  private def runPeer(corrupt: Boolean = false, capacity: Int = 32)(body: RecoveryPeer => Unit): Unit = {
    simulate(new RecoveryPeerBench(corrupt, capacity)) { d =>
      val host = new RecoveryPeer(d)
      host.initialize()
      body(host)
    }
  }

  test("a programmer can recover an empty image, start at its entry, lock it, and upload again after POR") {
    runPeer() { h =>
      val d = h.d
      assert(h.read(0, 0, 9) == Seq(0x10000, 1, 1, 32, 16, 0, 0, 1, 255))
      assert(h.read(0, 8, 9) == Seq(0L) ++ Seq.fill(7)(0xffffffffL) ++ Seq(1L))
      assert(h.read(0, 255, 9) == Seq.fill(8)(0xffffffffL) ++ Seq(0L))
      assert(h.read(1, 0, 9) == Seq(0, 0, 0, 1, 0, 0, 0, 0, 255))
      val image = Seq(0x12345678L, 0xfeebdaa3L, 0x0080ff00L, 0x72ef32cbL,
        0x5580aa01L, 0xc8184160L, 0xde87134cL, 0xffffffffL)
      h.upload(image, entry = 28)
      assert(h.read(1, 7).head == 32L)
      h.command(6)
      d.locked.expect(true.B); d.validImage.expect(true.B)
      d.starts.expect(1.U); d.lastEntry.expect(28.U)
      h.command(5); h.expectError(6); d.starts.expect(1.U)
      h.command(4); h.expectError(0)
      h.command(2, 0, 0); h.expectError(2)
      h.begin(4, 0, 0); h.expectError(2)
      d.writes.expect(8.U)
      val saved = h.memory.toVector
      // External reset and lite watchdog both drive the same whole-MCU reset
      // at this boundary. Neither removes power from the lock.
      for (_ <- Seq("external", "lite watchdog")) {
        h.reset(power = false)
        assert(h.read(1, 0, 4) == Seq(0, 0, 1, 0))
        h.begin(4, 0, 0); h.expectError(2)
        h.command(5); h.expectError(6)
        d.starts.expect(1.U); d.writes.expect(8.U)
        assert(h.memory.toVector == saved)
      }
      h.reset(power = true)
      h.upload(Seq(0xa1b2c3d4L), entry = 0)
      h.command(5)
      d.starts.expect(2.U); d.lastEntry.expect(0.U); d.locked.expect(false.B)
      h.command(4); d.locked.expect(true.B)
      d.halt.poke(true.B); h.step(); d.halt.poke(false.B); h.step()
      assert(h.read(1, 0).head == 4)
      h.reset(power = true) // Brownout of a locked, programmed image clears both.
      assert(h.read(1, 0, 4) == Seq(0, 0, 0, 1))
    }
  }

  test("full-width metadata validation, sequential offsets and CRC protect validity and memory") {
    runPeer(capacity = 20) { h =>
      import RecoveryImage.checksum
      val data = 0xbc1889fdL
      val crc = checksum(Seq(data))
      h.upload(Seq(data), 0)
      def rejected(expected: Int)(attempt: => Unit): Unit = {
        attempt
        h.expectError(expected)
        h.d.validImage.expect(true.B)
        assert(h.read(1, 6, 2) == Seq(0xdecafbadL, 4L))
        h.d.writes.expect(1.U)
      }
      for (length <- Seq(0L, 3L, 24L, 36L, 0x10000004L))
        rejected(4)(h.begin(length, 0, crc, id = 1))
      for (entry <- Seq(2L, 4L, 0xffff0000L))
        rejected(4)(h.begin(4, entry, crc, id = 1))
      rejected(5)(h.begin(4, 0, crc, abi = 0x20000))
      rejected(5)(h.begin(4, 0, crc, ram = 17))
      rejected(5)(h.begin(4, 0, crc, gpio = 1))
      rejected(5)(h.begin(4, 0, crc, channels = 1))
      h.begin(4, 0, crc ^ 1)
      h.d.validImage.expect(false.B)
      h.command(3); h.expectError(7)
      h.command(2, 0xffff0000L, data); h.expectError(4)
      h.command(2, 0, data); h.acceptWord(0, data); h.complete()
      h.command(2, 4, data); h.expectError(4)
      h.command(3); h.expectError(8)
      h.command(5); h.expectError(6); h.d.starts.expect(0.U)
      h.command(7, 1); h.expectError(4)
      h.command(9); h.expectError(5)
      h.command(10); h.expectError(5)
      h.command(0xff); h.expectError(1)
      val full = Seq(1L, 2L, 3L, 4L, 5L)
      h.upload(full, entry = 16)
      assert(h.read(1, 7).head == 20L)
    }
  }

  test("backpressure holds one memory write, and an in-flight status read keeps its captured bank") {
    runPeer() { h =>
      val d = h.d
      val data = 0x91aa4200L
      h.begin(4, 0, RecoveryImage.checksum(Seq(data)))
      h.command(2, 0, data)
      h.awaitRequest(); d.busy.expect(true.B); d.hold.expect(true.B)
      h.command(2, 0, data ^ 1); h.expectError(3)
      h.command(3); h.expectError(3)
      d.offset.expect(0.U); d.word.expect(data.U); d.writes.expect(0.U)
      assert(h.read(1, 3, 5) == Seq(0L, 1L, 3L, 0xdecafbadL, 0L))
      h.acceptWord(0, data); h.step(20)
      d.request.expect(false.B); d.busy.expect(true.B); d.writes.expect(1.U)
      assert(h.memory.forall(_ == 0xaa))
      h.selectRead(1, 0, 3)
      h.complete() // READ address was already ACKed.
      assert(h.readWords(5) == Seq(0L, 1L, 3L, 0xdecafbadL, 0L))
      assert(h.read(1, 3, 5) == Seq(1L, 0L, 3L, 0xdecafbadL, 4L))
      h.pulseDone()
      assert(h.read(1, 7).head == 4)
      d.writes.expect(1.U)
      h.command(3); h.expectError(0); d.validImage.expect(true.B)

      // Calibrate from external edges and the registered wake output. Repeat
      // that transaction with memDone on its dispatch edge and inspect busy.
      def releaseWakeStop(): Unit = {
        h.frame(Seq(8)); h.drive(false, true); h.drive(true, true)
        d.hostLow.poke(false.B)
      }
      releaseWakeStop()
      var dispatch = 0
      while (!d.wakePulse.peek().litToBoolean && dispatch < 16) { h.step(); dispatch += 1 }
      assert(dispatch > 0 && d.wakePulse.peek().litToBoolean)
      h.step(5)
      h.begin(4, 0, RecoveryImage.checksum(Seq(data)))
      h.command(2, 0, data); h.acceptWord(0, data)
      releaseWakeStop()
      h.step(dispatch - 1); h.completeOnNextEdge()
      d.wakePulse.expect(true.B); d.busy.expect(true.B)
      h.step()
      d.busy.expect(false.B)
      assert(h.read(1, 7).head == 4)
      h.command(3); h.expectError(0); d.validImage.expect(true.B)
    }
  }

  test("whole reset aborts outstanding work, flushes stale completion and requires a new valid image") {
    runPeer() { h =>
      val word = 0x80ff1186L
      h.begin(8, 4, RecoveryImage.checksum(Seq(word, word + 1)))
      h.command(2, 0, word); h.acceptWord(0, word); h.complete()
      h.command(2, 4, word + 1); h.acceptWord(4, word + 1)
      h.reset(power = false); h.pulseDone()
      assert(h.memory.take(4).toSeq == RecoveryImage.bytes(word))
      assert(h.memory.drop(4).forall(_ == 0xaa))
      assert(h.read(1, 0, 8) == Seq(0, 0, 0, 1, 0, 0, 0, 0))
      h.command(5); h.expectError(6); h.d.starts.expect(0.U)
      h.upload(Seq(word + 7), 0)
    }
  }

  test("wrong address, wake probe, timeout and malformed writes have distinct public effects") {
    runPeer() { h =>
      val word = 0x918e0022L
      h.upload(Seq(word), 0)
      h.start(); h.send(0x68, ack = false); h.stop()
      // Probe when the service clock is already running. A partial observation
      // when the clock restarts may NACK and must not constitute a command.
      h.frame(Seq.empty); h.stop()
      h.command(8); h.d.wakes.expect(1.U)
      h.frame(Seq(2)); h.drive(false, false); h.step(260); h.stop()
      assert(h.read(1, 0, 6) == Seq(2, 1, 0, 1, 0, 0))
      h.command(1); h.expectError(1)
      h.frame(Seq(4)); h.bit(false); h.bit(true); h.stop()
      h.expectError(1); h.d.locked.expect(false.B)
      h.frame(Seq.fill(33)(1)); h.send(2, ack = false); h.stop()
      h.expectError(1); h.d.validImage.expect(true.B)
      h.d.writes.expect(1.U)
    }
  }

  test("eight service edges per SCL period preserve the selected words, support mask and read snapshot") {
    runPeer() { h =>
      val reason = 0x937acf85L
      val crashes = 0x7ea01162L
      h.d.resetReason.poke(reason.U); h.d.crashCount.poke(crashes.U)
      val bank = h.fastSnapshot(6) {
        h.d.resetReason.poke((reason ^ 0xffffffffL).U)
        h.d.crashCount.poke((crashes ^ 0xffffffffL).U)
      }
      assert(bank == Seq(0L, reason, crashes) ++ Seq.fill(5)(0xffffffffL) ++ Seq(7L))
      assert(h.fastSnapshot(8)(()).head == (crashes ^ 0xffffffffL))
    }
  }

  test("the memory oracle catches a real single-bit corruption in the outgoing word") {
    runPeer(corrupt = true) { h =>
      val word = 0xa5118056L
      h.begin(4, 0, RecoveryImage.checksum(Seq(word)))
      h.command(2, 0, word)
      val fault = intercept[IllegalArgumentException](h.acceptWord(0, word))
      assert(fault.getMessage.contains("RECOVERY_MEMORY_MODEL"))
    }
  }
}
