package deadhorse.bus_bridge

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import deadhorse.lib.CdcSync
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** A timeout cancels queued work, not only a response already on its way back. */
class BridgeCancelSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t41/bridge-cancel").toAbsolutePath
  }
  private def exercise(delayedAbort: Boolean): Unit={
    val make=()=>if(delayedAbort) new BusBridge(32) {
      override protected def transportEpoch(source: Bool,target: Bool,abort: Bool): Bool={
        val sampled=Module(new CdcSync(1))
        sampled.clk:=targetClock;sampled.reset_n:=source && target;sampled.in:=abort.asUInt
        source && target && !sampled.out.asBool
      }
    } else new BusBridge(32)
    simulateRaw(make()) {d=>
      def high(x: Bool)=x.peek().litToBoolean
      var eligible=0
      // Sweep the destination delivery phase using only externally visible
      // target.req to distinguish unissued work from permitted orphan drainage.
      for(destinationEdges<-0 to 6) {
        d.sourceReset_n.poke(false.B);d.targetReset_n.poke(false.B)
        d.source.req.poke(false.B);d.source.bits.poke(0.U.asTypeOf(d.source.bits))
        d.target.gnt.poke(false.B);d.target.rvalid.poke(false.B)
        d.target.rdata.poke(0.U);d.target.err.poke(false.B)
        d.offer.poke(false.B);d.permit.poke(false.B);d.quiescent.poke(true.B)
        for(_<-0 until 4) {d.sourceClock.step();d.targetClock.step()}
        d.sourceReset_n.poke(true.B);d.targetReset_n.poke(true.B)
        for(_<-0 until 16) {d.sourceClock.step();d.targetClock.step()}
        d.offer.poke(true.B);d.permit.poke(true.B);d.source.req.poke(true.B)
        d.source.bits.addr.poke("h30000400".U);d.source.bits.we.poke(true.B)
        d.source.bits.be.poke(15.U);d.source.bits.wdata.poke("h5a17c0de".U)
        var n=0
        while(!high(d.source.gnt) && n<16) {d.sourceClock.step();n+=1}
        assert(high(d.source.gnt),"bridge did not accept source request")
        d.sourceClock.step();d.source.req.poke(false.B);d.offer.poke(false.B)
        d.sourceClock.step(3)
        for(_<-0 until destinationEdges)d.targetClock.step()
        val offeredBeforeTimeout=high(d.target.req)
        n=0
        while(!high(d.source.rvalid) && n<64) {d.sourceClock.step();n+=1}
        assert(high(d.source.rvalid) && high(d.source.err),"source did not report timeout")
        if(!offeredBeforeTimeout) {
          eligible+=1
          for(_<-0 until 8) {
            d.targetClock.step()
            assert(!high(d.target.req),s"cancelled queued write dispatched after timeout: destination phase=$destinationEdges")
          }
        }
      }
      assert(eligible>=4,"phase sweep did not exercise queued-but-unissued cases")
    }
  }
  test("timeout cancels queued writes before a stopped target restarts") {exercise(false)}
  test("cancellation oracle rejects waiting for the target to sample abort") {
    val failure=intercept[org.scalatest.exceptions.TestFailedException] {exercise(true)}
    assert(failure.getMessage.contains("cancelled queued write dispatched after timeout"))
  }
}
