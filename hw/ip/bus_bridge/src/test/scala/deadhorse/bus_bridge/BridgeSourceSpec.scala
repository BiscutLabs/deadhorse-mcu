package deadhorse.bus_bridge

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import deadhorse.lib._
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException

/** Port-only event accounting lets the simulator batch long watchdog waits. */
class BridgeSourceWatchdogTest(corrupt: Boolean) extends RawModule {
  val clk = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val source = IO(new LocalBus)
  val offer = IO(Input(Bool())); val permit = IO(Input(Bool())); val linkUp = IO(Input(Bool()))
  val responseValid = IO(Input(Bool())); val responseData = IO(Input(UInt(33.W)))
  val acknowledged = IO(Input(Bool())); val targetNeedsClock = IO(Input(Bool()))
  val ask = IO(Output(Bool())); val abort = IO(Output(Bool())); val wake = IO(Output(Bool()))
  val grants = IO(Output(UInt(8.W))); val replies = IO(Output(UInt(8.W))); val enqueues = IO(Output(UInt(8.W)))
  val badCredit = IO(Output(Bool())); val lostWake = IO(Output(Bool()))
  val d = Module(if (corrupt) new BridgeBadSource(131072) else new BridgeSource(131072))
  d.clk := clk; d.reset_n := reset_n; d.source <> source
  d.offer := offer; d.permit := permit; d.linkUp := linkUp; d.requestReady := true.B
  d.responseValid := responseValid; d.responseData := responseData
  d.abortAcknowledged := acknowledged; d.targetNeedsClock := targetNeedsClock
  ask := d.permitRequest; abort := d.abort; wake := d.clockRequest
  withClockAndReset(clk, (!reset_n).asAsyncReset) {
    val accepted = RegInit(0.U(8.W)); val returned = RegInit(0.U(8.W)); val sent = RegInit(0.U(8.W))
    val pending = RegInit(false.B); val creditError = RegInit(false.B); val wakeError = RegInit(false.B)
    when(source.req && source.gnt) {
      accepted := accepted + 1.U; pending := true.B
      when(pending) { creditError := true.B }
    }
    when(source.rvalid) {
      returned := returned + 1.U; pending := false.B
      when(!pending) { creditError := true.B }
    }
    when(d.requestPush && d.requestReady) { sent := sent + 1.U }
    when((pending || d.abort) && !d.clockRequest) { wakeError := true.B }
    grants := accepted; replies := returned; enqueues := sent
    badCredit := creditError; lostWake := wakeError
  }
}

class BridgeSourceSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t14/bridge-source-simulation").toAbsolutePath
  }
  private val limit = 131072
  private val answer = BigInt("ca53e719", 16)

  private def runCase(corrupt: Boolean): Unit = {
    simulateRaw(new BridgeSourceWatchdogTest(corrupt), subdirectory = Some(if(corrupt) "corrupt" else "watchdog")) { d =>
      def yes(b: Bool) = b.peek().litValue == 1
      def count(u: UInt) = u.peek().litValue.toInt
      def healthy(): Unit = {
        assert(!yes(d.badCredit), "WATCHDOG_MODEL_MISMATCH unsolicited/duplicate credit")
        assert(!yes(d.lostWake), "WATCHDOG_MODEL_MISMATCH lost clock request")
      }
      d.source.req.poke(false.B); d.source.bits.addr.poke(0x2340.U)
      d.source.bits.wdata.poke(0x87654321L.U); d.source.bits.be.poke(15.U)
      d.source.bits.we.poke(false.B); d.source.bits.origin.poke(1.U)
      d.offer.poke(false.B); d.permit.poke(false.B); d.linkUp.poke(true.B)
      d.responseValid.poke(false.B); d.responseData.poke(0.U)
      d.acknowledged.poke(false.B); d.targetNeedsClock.poke(false.B)
      d.reset_n.poke(false.B); d.clk.step(2); d.reset_n.poke(true.B); d.clk.step(2)

      def accept(): Unit = {
        val before = count(d.grants)
        d.offer.poke(true.B); d.source.req.poke(true.B)
        for(_ <- 0 until 8 if !yes(d.ask)) d.clk.step()
        assert(yes(d.ask) && yes(d.wake), "WATCHDOG_MODEL_MISMATCH offer wake")
        d.permit.poke(true.B)
        for(_ <- 0 until 8 if !yes(d.source.gnt)) d.clk.step()
        assert(yes(d.source.gnt), "WATCHDOG_MODEL_MISMATCH grant")
        d.clk.step() // accepted grant is edge one of the completion window
        d.source.req.poke(false.B); d.offer.poke(false.B)
        assert(count(d.grants) == before + 1)
      }
      def waitToLastEdge(): Unit = {
        val before = count(d.replies)
        d.clk.step(limit - 2)
        assert(count(d.replies) == before && !yes(d.source.rvalid),
          "WATCHDOG_MODEL_MISMATCH premature response")
        assert(yes(d.wake) && !yes(d.abort)); healthy()
      }
      def observeReply(error: Boolean, data: BigInt): Unit = {
        assert(yes(d.source.rvalid) && yes(d.source.err) == error,
          "WATCHDOG_MODEL_MISMATCH final-edge response")
        assert(d.source.rdata.peek().litValue == data, "WATCHDOG_MODEL_MISMATCH read data")
        val before = count(d.replies)
        d.responseValid.poke(false.B); d.clk.step()
        assert(!yes(d.source.rvalid) && count(d.replies) == before + 1)
        d.clk.step(32)
        assert(count(d.replies) == before + 1, "WATCHDOG_MODEL_MISMATCH duplicate reply")
        healthy()
      }
      def release(aborted: Boolean): Unit = {
        if(aborted) {
          assert(yes(d.abort) && yes(d.wake))
          d.acknowledged.poke(true.B); d.clk.step()
          assert(!yes(d.abort))
        }
        d.acknowledged.poke(false.B); d.permit.poke(false.B); d.linkUp.poke(true.B)
        d.clk.step(4)
        assert(!yes(d.ask) && !yes(d.wake)); healthy()
      }

      accept(); waitToLastEdge(); d.clk.step()
      observeReply(error = true, data = 0); release(aborted = true)
      assert(count(d.grants) == 1 && count(d.enqueues) == 1 && count(d.replies) == 1)

      // Valid data on the final allowed edge takes priority over expiry.
      accept(); waitToLastEdge()
      d.responseData.poke(answer.U); d.responseValid.poke(true.B); d.clk.step()
      assert(!yes(d.abort), "WATCHDOG_MODEL_MISMATCH final-edge response aborted")
      observeReply(error = false, data = answer); release(aborted = false)
      assert(count(d.grants) == 2 && count(d.enqueues) == 2 && count(d.replies) == 2)

      // A peer-link reset cancels exactly once, then acknowledgement permits reuse.
      accept(); d.clk.step(17); d.linkUp.poke(false.B); d.clk.step()
      observeReply(error = true, data = 0); release(aborted = true)
      assert(count(d.grants) == 3 && count(d.enqueues) == 3 && count(d.replies) == 3)

      // Local reset discards local credit; a late old response must not create one.
      accept(); d.clk.step(17); d.reset_n.poke(false.B)
      assert(!yes(d.source.rvalid) && !yes(d.source.gnt) && !yes(d.abort))
      d.source.req.poke(false.B); d.offer.poke(false.B); d.permit.poke(false.B)
      d.clk.step(2); d.reset_n.poke(true.B); d.clk.step(2)
      d.responseValid.poke(true.B); d.responseData.poke(answer.U); d.clk.step(4)
      d.responseValid.poke(false.B)
      assert(count(d.grants) == 0 && count(d.replies) == 0 && !yes(d.source.rvalid)); healthy()
      d.targetNeedsClock.poke(true.B); d.clk.step()
      assert(yes(d.wake), "WATCHDOG_MODEL_MISMATCH orphan clock demand")
      d.targetNeedsClock.poke(false.B); d.clk.step()
      accept(); d.clk.step(3); d.responseValid.poke(true.B); d.clk.step()
      observeReply(error = false, data = answer); release(aborted = false)
      assert(count(d.grants) == 1 && count(d.enqueues) == 1 && count(d.replies) == 1)
    }
  }

  test("production watchdog expires exactly, final-edge response wins, and reset recovers") { runCase(false) }
  test("production watchdog suite rejects actual read-path corruption") {
    val failure = intercept[TestFailedException] { runCase(true) }
    assert(failure.getMessage.contains("WATCHDOG_MODEL_MISMATCH read data"))
  }
}
