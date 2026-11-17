package deadhorse.spi_host

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SpiBoundarySpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t16/boundary-simulation").toAbsolutePath
  }

  /** Calibrate only the public MMIO transport delay from request to visible CS.
    * SPI edge positions still come from the independent pin protocol model. */
  private def launch(h: SpiDriver, p: SpiPeer): Int = {
    val offered = h.cycles
    h.wr(12, 2)
    val commandDelay = p.start - offered
    require(commandDelay > 0, "SPI_BOUNDARY_MODEL missing START effect")
    commandDelay
  }

  private def at(h: SpiDriver, cycle: Int)(command: => Unit): Unit = {
    require(h.cycles <= cycle, "SPI_BOUNDARY_MODEL missed scheduled command")
    h.step(cycle - h.cycles)
    command
  }

  private def count(h: SpiDriver, receive: Boolean = false): Int =
    ((h.rd(0x18) >> (if(receive) 16 else 8)) & 31).toInt

  private def checkCount(expected: Int, observed: Int): Unit =
    require(expected == observed, s"SPI_BOUNDARY_MODEL count $observed != $expected")

  /** The standard driver's finish requires an empty TX queue. This transaction
    * intentionally leaves queued work, whose retained demand is also checked. */
  private def finishWithQueuedTx(h: SpiDriver, p: SpiPeer): Unit = {
    val deadline = h.cycles + (16 * p.sent.size + 5) * p.half + 32
    while(p.end < 0 && h.cycles < deadline) h.step()
    require(p.end >= 0, "SPI_BOUNDARY_MODEL missing completion")
    h.step(p.half + 3)
    h.peer = None
    require(h.d.cs_n.peek().litValue == 3 && h.high(h.d.clockHold) && !h.high(h.d.quiescent),
      "SPI_BOUNDARY_MODEL queued TX lost clock demand")
  }

  test("full TX accepts a write on byte consumption, rejects one edge early, and preserves queued order") {
    simulateRaw(new SpiBench(SpiTestFiles.json, 2)) { d =>
      val h = new SpiDriver(d)
      for(mode <- Seq(false, true); offset <- Seq(-1, 0, 1)) {
        h.reset()
        val p = h.prepare(Seq(0x19, 0xa6), Seq(0x72, 0x8d), mode3 = mode, half = 16)
        val delay = launch(h, p)
        h.wr(0x10, 0x35) // Replace the byte consumed by START: FIFO is full again.
        checkCount(2, count(h))
        h.wr(0x1c, 31)
        val firstByteEnd = p.start + 16 * p.half
        at(h, firstByteEnd - delay + offset) { h.wr(0x10, 0xca) }
        val observed = count(h)
        val overflow = (h.rd(0x1c) & 1) != 0
        checkCount(if(offset < 0) 1 else 2, observed)
        assert(overflow == (offset < 0), "SPI_BOUNDARY_MODEL full TX acceptance edge")
        if(offset < 0) {
          // Negative timing control: the exact-coincidence oracle must reject
          // the actual observation from a write deliberately issued early.
          val failure = intercept[IllegalArgumentException] { checkCount(2, observed) }
          assert(failure.getMessage.contains("SPI_BOUNDARY_MODEL"))
        }
        finishWithQueuedTx(h, p)
        h.checkRx(Seq(0x72, 0x8d))
        val survivors = if(offset < 0) Seq(0x35) else Seq(0x35, 0xca)
        val replies = survivors.map(_ ^ 0xff)
        h.wr(8, survivors.size)
        val q = new SpiPeer(mode, 0, 16, survivors, replies)
        h.peer = Some(q)
        h.wr(12, 2)
        h.finish(q)
        h.checkRx(replies)
      }
    }
  }

  test("nonempty RX POP on byte arrival removes the old head and retains the arriving byte") {
    simulateRaw(new SpiBench(SpiTestFiles.json, 2)) { d =>
      val h = new SpiDriver(d)
      for(mode <- Seq(false, true)) {
        h.reset()
        val p = h.prepare(Seq(0x3c, 0xc3), Seq(0x56, 0xab), mode3 = mode, half = 16)
        val delay = launch(h, p)
        h.step(p.start + 16 * p.half + 1 - h.cycles)
        checkCount(1, count(h, receive = true))
        assert(h.rd(0x14) == 0x56)
        at(h, p.start + 32 * p.half - delay) { h.wr(12, 4) }
        checkCount(1, count(h, receive = true))
        assert(h.rd(0x14) == 0xab && (h.rd(0x1c) & 6) == 0)
        h.finish(p)
        h.checkRx(Seq(0xab))
      }
    }
  }

  test("empty RX POP cannot consume a coincident arrival but can consume it one edge later") {
    simulateRaw(new SpiBench(SpiTestFiles.json, 2)) { d =>
      val h = new SpiDriver(d)
      for(mode <- Seq(false, true); offset <- Seq(-1, 0, 1)) {
        h.reset()
        val p = h.prepare(Seq(0x69), Seq(0x96), mode3 = mode, half = 16)
        val delay = launch(h, p)
        at(h, p.start + 16 * p.half - delay + offset) { h.wr(12, 4) }
        checkCount(if(offset <= 0) 1 else 0, count(h, receive = true))
        assert(((h.rd(0x1c) & 4) != 0) == (offset <= 0), "SPI_BOUNDARY_MODEL empty POP acceptance edge")
        assert((h.rd(0x1c) & 2) == 0)
        h.finish(p)
        h.checkRx(if(offset <= 0) Seq(0x96) else Seq.empty)
      }
    }
  }
}
