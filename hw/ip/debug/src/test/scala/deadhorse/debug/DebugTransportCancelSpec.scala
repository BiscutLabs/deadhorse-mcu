package deadhorse.debug

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import deadhorse.lib.CdcSync
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** T41: an unaccepted request belongs to the old DMI epoch even when main stops.
  * Observe only public ready/valid ports; no internal FIFO state is inspected.
  */
class DebugTransportCancelSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t41/debug-cancel").toAbsolutePath
  }
  private def exercise(delayedClear: Boolean): Unit={
    val make=()=>if(delayedClear) new DebugTransport {
      override protected def requestReset(por: Bool,epoch: Bool): Bool={
        val sampled=Module(new CdcSync(1))
        sampled.clk:=mainClock;sampled.reset_n:=por;sampled.in:=epoch.asUInt
        por && sampled.out.asBool
      }
    } else new DebugTransport
    simulateRaw(make()) {d=>
      def high(x: Bool)=x.peek().litToBoolean
      d.por_n.poke(false.B);d.clear_n.poke(false.B)
      d.scanRequest.valid.poke(false.B);d.scanRequest.bits.poke(0.U)
      d.scanResponse.ready.poke(false.B);d.request.ready.poke(false.B)
      d.response.valid.poke(false.B);d.response.bits.poke(0.U)
      for(_<-0 until 4) {d.tck.step();d.mainClock.step()}
      d.por_n.poke(true.B);d.clear_n.poke(true.B)
      for(_<-0 until 16) {d.tck.step();d.mainClock.step()}
      assert(high(d.scanRequest.ready),"DMI transport did not become ready")
      val payload=BigInt("123456789",16)
      d.scanRequest.bits.poke(payload.U);d.scanRequest.valid.poke(true.B)
      d.tck.step();d.scanRequest.valid.poke(false.B)
      var edges=0
      while(!high(d.request.valid) && edges<16) {d.mainClock.step();edges+=1}
      assert(high(d.request.valid),"request did not reach the stopped consumer")
      assert(d.request.bits.peek().litValue==payload)
      // No main edge between seeing a pending request and observing clear.
      d.clear_n.poke(false.B);d.tck.step(2)
      assert(!high(d.request.valid),"queued DMI request survived sampled hard-clear with main stopped")
      d.request.ready.poke(true.B);d.mainClock.step()
      assert(!high(d.request.valid),"cancelled DMI request was offered after restart")
      d.clear_n.poke(true.B)
      for(_<-0 until 16) {d.tck.step();d.mainClock.step()}
      assert(!high(d.request.valid),"cancelled DMI request reappeared in the new epoch")
      assert(high(d.scanRequest.ready),"new DMI epoch failed to reopen")
    }
  }
  test("hard-clear cancels an unaccepted request while main is stopped") {exercise(false)}
  test("cancellation oracle rejects delaying the clear until main samples it") {
    val failure=intercept[org.scalatest.exceptions.TestFailedException] {exercise(true)}
    assert(failure.getMessage.contains("queued DMI request survived sampled hard-clear"))
  }
}
