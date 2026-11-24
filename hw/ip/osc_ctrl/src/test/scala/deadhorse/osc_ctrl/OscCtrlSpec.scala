package deadhorse.osc_ctrl

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class OscCtrlSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan04/mmio-simulation").toAbsolutePath
  }
  test("service reset cannot clear a failed oscillator epoch or authorize a late source") {
    simulateRaw(new OscCtrl("build/t20/i1/osc_ctrl/osc_ctrl_regs.json")) {d=>
      d.reset_n.poke(false.B);d.epochReset_n.poke(false.B)
      d.mainHold.poke(false.B);d.oscillatorHold.poke(false.B);d.coreIdle.poke(true.B)
      d.gateClosed.poke(true.B);d.stable.poke(false.B);d.wake.poke(0.U)
      d.bus.req.poke(false.B);d.bus.bits.addr.poke(0.U);d.bus.bits.we.poke(false.B)
      d.bus.bits.wdata.poke(0.U);d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(0.U)
      d.clk.step(3);d.reset_n.poke(true.B);d.epochReset_n.poke(true.B)
      d.clk.step(4700);d.fault.expect(true.B);d.gateRequest.expect(false.B)
      for(late<-Seq(false,true)) {
        d.reset_n.poke(false.B);d.stable.poke(late.B)
        for(_<-0 until 4) {
          d.clk.step();d.fault.expect(true.B);d.authorized.expect(false.B)
          d.gateRequest.expect(false.B);d.oscillatorOn.expect(true.B)
        }
        d.reset_n.poke(true.B)
        d.clk.step(16);d.fault.expect(true.B);d.authorized.expect(false.B)
        d.gateRequest.expect(false.B);d.oscillatorOn.expect(true.B)
      }
      // Only a new cold/pin epoch can discard the fault, and it still needs
      // the complete fresh qualification before the gate request returns.
      d.epochReset_n.poke(false.B);d.stable.poke(false.B);d.clk.step(2)
      d.fault.expect(false.B);d.gateRequest.expect(false.B)
      d.epochReset_n.poke(true.B);d.clk.step(520);d.qualify.expect(true.B)
      d.gateRequest.expect(false.B);d.stable.poke(true.B);d.clk.step(3)
      d.authorized.expect(true.B);d.gateRequest.expect(true.B)
    }
  }
  test("service reset flushes transport without discarding a qualified oscillator epoch") {
    simulateRaw(new OscCtrl("build/t20/i1/osc_ctrl/osc_ctrl_regs.json")) {d=>
      d.reset_n.poke(false.B);d.epochReset_n.poke(false.B)
      d.mainHold.poke(false.B);d.oscillatorHold.poke(false.B);d.coreIdle.poke(true.B)
      d.gateClosed.poke(false.B);d.stable.poke(false.B);d.wake.poke(0.U)
      d.bus.req.poke(false.B);d.bus.bits.addr.poke(0x40000408L.U);d.bus.bits.we.poke(false.B)
      d.bus.bits.wdata.poke(0.U);d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(0.U)
      d.clk.step(3);d.reset_n.poke(true.B);d.epochReset_n.poke(true.B)
      d.clk.step(520);d.qualify.expect(true.B);d.stable.poke(true.B);d.clk.step(3)
      d.gateRequest.expect(true.B);d.authorized.expect(true.B)
      // Reset at every edge of request/grant/return without changing policy reset.
      // The requester resets too, so no pre-reset reply may reappear afterward.
      for(phase<-0 until 12) {
        d.bus.req.poke(true.B)
        for(_<-0 until phase) {
          val granted=d.bus.gnt.peek().litToBoolean
          d.clk.step();if(granted) d.bus.req.poke(false.B)
        }
        d.reset_n.poke(false.B);d.bus.req.poke(false.B)
        d.clk.step(3);d.gateRequest.expect(true.B);d.authorized.expect(true.B)
        d.bus.gnt.expect(false.B);d.bus.rvalid.expect(false.B)
        d.reset_n.poke(true.B)
        for(_<-0 until 12) {d.clk.step();d.bus.rvalid.expect(false.B);d.gateRequest.expect(true.B)}
      }
      d.fault.expect(false.B)
    }
  }
  test("lite owns the controller, settings honor byte masks and holes have no effects") {
    simulateRaw(new OscCtrl("build/t20/i1/osc_ctrl/osc_ctrl_regs.json")) {d=>
      d.reset_n.poke(false.B);d.epochReset_n.poke(false.B)
      d.mainHold.poke(false.B);d.oscillatorHold.poke(false.B)
      d.coreIdle.poke(true.B);d.gateClosed.poke(false.B);d.stable.poke(false.B);d.wake.poke(0.U)
      d.bus.req.poke(false.B);d.bus.bits.addr.poke(0.U);d.bus.bits.we.poke(false.B)
      d.bus.bits.wdata.poke(0.U);d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(0.U)
      d.clk.step(2);d.oscillatorOn.expect(true.B);d.reset_n.poke(true.B);d.epochReset_n.poke(true.B);d.clk.step(3)
      def access(offset: Int,write: Boolean=false,data: Int=0,mask: Int=15,owner: Int=0): (BigInt,Boolean)={
        d.bus.req.poke(true.B);d.bus.bits.addr.poke((0x40000400L+offset).U)
        d.bus.bits.we.poke(write.B);d.bus.bits.wdata.poke(data.U)
        d.bus.bits.be.poke(mask.U);d.bus.bits.origin.poke(owner.U)
        var n=0
        while(!d.bus.gnt.peek().litToBoolean && n<32) {d.clk.step();n+=1}
        assert(n<32,"OSC_MMIO_GRANT")
        d.clk.step();d.bus.req.poke(false.B);n=0
        while(!d.bus.rvalid.peek().litToBoolean && n<32) {d.clk.step();n+=1}
        assert(n<32,"OSC_MMIO_RESPONSE")
        val result=(d.bus.rdata.peek().litValue,d.bus.err.peek().litToBoolean)
        d.clk.step();result
      }
      for((offset,value)<-Seq(4->0,8->512,12->256,20->0,28->0,32->0,36->0,40->4096))
        assert(access(offset)==(BigInt(value),false),"OSC_MMIO_DEFAULT")
      assert(!access(8,true,0xabcd)._2)
      assert(!access(8,true,0x1200,2)._2)
      assert(access(8)==(BigInt(0x12cd),false),"OSC_MMIO_BYTE_MASK")
      for(owner<-1 to 7) {
        assert(access(8,true,0,owner=owner)._2,"OSC_MMIO_OWNER")
        assert(access(8)==(BigInt(0x12cd),false),"OSC_MMIO_DENIED_EFFECT")
      }
      assert(access(0x30,true,1)._2);assert(access(9,true,1)._2)
      assert(access(8)==(BigInt(0x12cd),false),"OSC_MMIO_HOLE_EFFECT")
    }
  }
}
