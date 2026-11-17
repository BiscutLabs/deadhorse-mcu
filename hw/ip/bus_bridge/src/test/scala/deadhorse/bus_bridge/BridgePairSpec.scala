package deadhorse.bus_bridge

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import deadhorse.bus.{BusFabric, BusRegion}
import deadhorse.lib._
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException
import scala.collection.mutable

/** Two real fabrics, opposing bridges and the actual direction-permit crossing. */
class BridgePairTest(fault: Boolean = false) extends RawModule {
  val ac = IO(Input(Bool())); val mc = IO(Input(Bool())); val reset_n = IO(Input(Bool()))
  val cpuA = IO(new LocalBus); val cpuM = IO(new LocalBus)
  val ramA = IO(Flipped(new LocalBus)); val ramM = IO(Flipped(new LocalBus))
  val quietA = IO(Input(Bool())); val quietM = IO(Input(Bool()))
  val wake = IO(Output(Bool())); val outerIsolated = IO(Output(Bool()))
  val bridgeGrant = IO(Output(Bool())); val bridgeReply = IO(Output(Bool())); val bridgeError = IO(Output(Bool()))
  val ar = Module(new ResetRelease); val mr = Module(new ResetRelease)
  ar.clk := ac.asClock; mr.clk := mc.asClock; ar.reset_n := reset_n; mr.reset_n := reset_n
  val a = Module(new BusFabric(2, Seq(BusRegion(0x1000, 0x1000, 128), BusRegion(0x2000, 0x1000, 136))))
  val m = Module(new BusFabric(2, Seq(BusRegion(0x1000, 0x1000, 136), BusRegion(0x2000, 0x1000, 128))))
  a.clk := ac.asClock; m.clk := mc.asClock; a.reset_n := ar.released; m.reset_n := mr.released
  a.master(0) <> cpuA; m.master(0) <> cpuM
  a.target(0) <> ramA; m.target(1) <> ramM
  for (i <- 0 until 2) { a.allow(i) := true.B; m.allow(i) := true.B }
  a.admit(0) := true.B; m.admit(1) := true.B
  a.quiescent(0) := quietA; m.quiescent(1) := quietM
  val am = Module(if (fault) new BridgeBad(128) else new BusBridge(128)); val ma = Module(new BusBridge(128))
  am.sourceClock := ac.asClock; am.targetClock := mc.asClock
  ma.sourceClock := mc.asClock; ma.targetClock := ac.asClock
  am.sourceReset_n := reset_n; am.targetReset_n := reset_n
  ma.sourceReset_n := reset_n; ma.targetReset_n := reset_n
  am.source <> a.target(1); am.target <> m.master(1)
  ma.source <> m.target(0); ma.target <> a.master(1)
  am.offer := a.waiting(1); ma.offer := m.waiting(0)
  a.admit(1) := am.admit; m.admit(0) := ma.admit
  val permit = Module(new DirectionPermit)
  permit.aonClock := ac.asClock; permit.mainClock := mc.asClock
  permit.aonReset_n := reset_n; permit.mainReset_n := reset_n
  permit.requestAon := am.permitRequest; permit.requestMain := ma.permitRequest
  am.permit := permit.permitAon; ma.permit := permit.permitMain
  // Public transaction credits, not a constant acknowledgment: the remote fabric
  // owns accepted work until its response. The source-facing slots use the same rule.
  def emptyCredit(clk: Clock, reset: Bool, bus: LocalBus): Bool = {
    withClockAndReset(clk, (!reset).asAsyncReset) {
      val busy = RegInit(false.B)
      when(bus.rvalid) { busy := false.B }
      when(bus.req && bus.gnt) { busy := true.B }
      !busy
    }
  }
  am.quiescent := emptyCredit(mc.asClock, mr.released, m.master(1))
  ma.quiescent := emptyCredit(ac.asClock, ar.released, a.master(1))
  a.quiescent(1) := emptyCredit(ac.asClock, ar.released, a.target(1))
  m.quiescent(0) := emptyCredit(mc.asClock, mr.released, m.target(0))
  wake := am.clockRequest
  outerIsolated := a.isolated(1)
  bridgeGrant := am.source.gnt && am.source.req
  bridgeReply := am.source.rvalid; bridgeError := am.source.err
}

class BridgePairSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t14/bridge-pair-simulation").toAbsolutePath
  }
  private def check(fault: Boolean): Unit = {
    simulateRaw(new BridgePairTest(fault), subdirectory = Some(if (fault) "corrupt" else "pair")) { d =>
      case class Command(address: Int, data: BigInt, lanes: Int, origin: Int)
      case class Sample(grant: Boolean, reply: Boolean, data: BigInt, error: Boolean)
      def yes(b: Bool): Boolean = b.peek().litValue == 1
      def answer(c: Command, main: Boolean): BigInt = c.data ^ BigInt(c.address) ^ (if (main) BigInt("95172a3c", 16) else BigInt("36c81e42", 16))
      val expected = mutable.Map.empty[Int, Command]
      val issued = mutable.Set.empty[Int]
      var aWork: Option[(Command, Int)] = None; var mWork: Option[(Command, Int)] = None
      var freezeMain = false; var tick = 0
      var sawWake = false; var bridgeErrors = 0; var lastBridgeGrant = -1
      def initialize(bus: LocalBus): Unit = {
        bus.req.poke(false.B); bus.bits.addr.poke(0.U); bus.bits.wdata.poke(0.U)
        bus.bits.be.poke(0.U); bus.bits.we.poke(false.B); bus.bits.origin.poke(0.U)
      }
      def launch(bus: LocalBus, c: Command): Unit = {
        expected(c.address) = c
        bus.req.poke(true.B); bus.bits.addr.poke(c.address.U); bus.bits.wdata.poke(c.data.U)
        bus.bits.be.poke(c.lanes.U); bus.bits.we.poke(false.B); bus.bits.origin.poke(c.origin.U)
      }
      def sample(bus: LocalBus, running: Boolean): Sample = Sample(running && yes(bus.req) && yes(bus.gnt), running && yes(bus.rvalid), bus.rdata.peek().litValue, yes(bus.err))
      def backend(bus: LocalBus, work: Option[(Command, Int)], main: Boolean, running: Boolean): Option[(Command, Int)] = {
        val replying = work.exists(_._2 == 0) && !(main && freezeMain)
        bus.gnt.poke(work.isEmpty.B); bus.rvalid.poke(replying.B)
        bus.rdata.poke(work.map(x => answer(x._1, main)).getOrElse(BigInt(0)).U); bus.err.poke(false.B)
        if (!running) work else {
          var next = if (replying) None else work.map { case (c, n) => (c, math.max(0, n - 1)) }
          if (yes(bus.req) && yes(bus.gnt)) {
            val address = bus.bits.addr.peek().litValue.toInt
            assert(expected.contains(address), "PAIR_MODEL unsolicited target address")
            val c = expected(address)
            assert(!issued(address), "PAIR_MODEL duplicated downstream effect")
            assert(bus.bits.wdata.peek().litValue == c.data && bus.bits.be.peek().litValue == c.lanes &&
              bus.bits.origin.peek().litValue == c.origin && !yes(bus.bits.we), "PAIR_MODEL request metadata")
            assert((address >= 0x2000) == main, "PAIR_MODEL wrong endpoint")
            issued += address; next = Some((c, 3))
          }
          next
        }
      }
      def step(main: Boolean = true): (Sample, Sample) = {
        d.quietA.poke(aWork.isEmpty.B); d.quietM.poke(mWork.isEmpty.B)
        aWork = backend(d.ramA, aWork, false, true)
        mWork = backend(d.ramM, mWork, true, main)
        val a = sample(d.cpuA, true); val m = sample(d.cpuM, main)
        if (a.grant) assert(sawWake, "PAIR_MODEL CPU grant preceded wake")
        if (yes(d.wake)) sawWake = true
        if (yes(d.bridgeGrant)) { assert(sawWake, "PAIR_MODEL grant preceded wake"); lastBridgeGrant = tick }
        if (yes(d.bridgeReply) && yes(d.bridgeError)) bridgeErrors += 1
        d.ac.poke(true.B); d.mc.poke(main.B); d.wake.peek()
        d.ac.poke(false.B); d.mc.poke(false.B); d.wake.peek(); tick += 1
        if (a.grant) d.cpuA.req.poke(false.B)
        if (m.grant) d.cpuM.req.poke(false.B)
        (a, m)
      }
      d.ac.poke(false.B); d.mc.poke(false.B); d.reset_n.poke(true.B)
      initialize(d.cpuA); initialize(d.cpuM)
      for (bus <- Seq(d.ramA, d.ramM)) { bus.gnt.poke(false.B); bus.rvalid.poke(false.B); bus.rdata.poke(0.U); bus.err.poke(false.B) }
      d.quietA.poke(true.B); d.quietM.poke(true.B); d.wake.peek()
      d.reset_n.poke(false.B); d.wake.peek(); d.reset_n.poke(true.B)
      val acrossA = Command(0x2004, 0x1234, 5, 1)
      val acrossM = Command(0x1008, 0x9182, 10, 2)
      val local = Command(0x1010, 0x4356, 3, 1)
      launch(d.cpuA, acrossA); launch(d.cpuM, acrossM)
      var doneA = false; var doneM = false; var doneLocal = false; var localDuringOther = false
      for (i <- 0 until 300 if !doneLocal || !doneM) {
        val (a, m) = step(main = i >= 20)
        if (i == 19) assert(sawWake && !doneA, "PAIR_MODEL stopped-main wake")
        if (m.reply) { assert(!doneM && !m.error && m.data == answer(acrossM, false)); doneM = true }
        if (a.reply) {
          if (!doneA) {
            assert(!a.error && a.data == answer(acrossA, true), "PAIR_MODEL response data"); doneA = true
            launch(d.cpuA, local)
          } else {
            assert(!doneLocal && !a.error && a.data == answer(local, false)); doneLocal = true
            localDuringOther = !doneM
          }
        }
      }
      assert(doneA && doneM && doneLocal, "PAIR_MODEL opposing-traffic deadlock")
      assert(localDuringOther, "PAIR_MODEL local traffic did not progress while opposite crossing waited")
      for (_ <- 0 until 24) { val (a, m) = step(); assert(!a.reply && !m.reply) }
      // The inner source watchdog owns cancellation. The outer fabric budget is
      // eight edges larger and must observe its error, not quarantine prematurely.
      freezeMain = true
      val timeout = Command(0x2018, 0x7788, 15, 1)
      launch(d.cpuA, timeout)
      var timeoutDone = false; var acceptedAt = -1
      val previousErrors = bridgeErrors
      for (_ <- 0 until 220 if !timeoutDone) {
        val (a, m) = step()
        if (a.grant) acceptedAt = tick - 1
        assert(!m.reply)
        if (a.reply) {
          assert(a.error && a.data == 0, "PAIR_MODEL missing timeout error")
          assert(acceptedAt >= 0 && tick - 1 - acceptedAt <= 136, "PAIR_MODEL outer deadline")
          assert(bridgeErrors == previousErrors + 1 && lastBridgeGrant > acceptedAt && !yes(d.outerIsolated), "PAIR_MODEL premature outer timeout")
          timeoutDone = true
        }
      }
      assert(timeoutDone && issued(timeout.address))
      freezeMain = false
      for (_ <- 0 until 48) { val (a, m) = step(); assert(!a.reply && !m.reply, "PAIR_MODEL late response escaped") }
      val recovered = Command(0x2024, 0x9988, 9, 1)
      launch(d.cpuA, recovered)
      var restored = false
      for (_ <- 0 until 180 if !restored) {
        val (a, m) = step(); assert(!m.reply)
        if (a.reply) { assert(!a.error && a.data == answer(recovered, true)); restored = true }
      }
      assert(restored, "PAIR_MODEL recovery failed")
      assert(issued == expected.keySet)
    }
  }
  test("opposing crossings, stopped-clock wake, local service and nested deadlines compose") { check(false) }
  test("actual bridge data corruption is rejected by the unchanged pair model") {
    val error = intercept[TestFailedException] { check(true) }
    assert(error.getMessage.contains("PAIR_MODEL response data"))
  }
}
