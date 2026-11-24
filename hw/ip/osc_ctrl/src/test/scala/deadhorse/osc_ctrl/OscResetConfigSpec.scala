package deadhorse.osc_ctrl

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class OscResetConfigProbe extends OscCtrl("build/t20/i1/osc_ctrl/osc_ctrl_regs.json") {
  val observedDelay=IO(Output(UInt(16.W)));observedDelay:=regs.hw("startup_delay_ticks_q")
  val phase=IO(Output(UInt(2.W)));phase:=control.state
}

/** These are reset-ordering and exact snapshot tests, not metastability simulation. */
class OscResetConfigSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t33/reset-config-simulation").toAbsolutePath
  }
  def access(d: OscResetConfigProbe,offset: Int,write: Boolean=false,data: Int=0,
      advance: Int=>Unit = _=>()): BigInt={
    def edge(): Unit={d.clk.step();advance(1)}
    d.bus.req.poke(true.B);d.bus.bits.addr.poke((0x40000400L+offset).U)
    d.bus.bits.we.poke(write.B);d.bus.bits.wdata.poke(data.U)
    var n=0
    while(!d.bus.gnt.peek().litToBoolean && n<32) {edge();n+=1}
    assert(n<32,"RESET_CONFIG_GRANT")
    edge();d.bus.req.poke(false.B);n=0
    while(!d.bus.rvalid.peek().litToBoolean && n<32) {edge();n+=1}
    assert(n<32,"RESET_CONFIG_RESPONSE");d.bus.err.expect(false.B)
    val value=d.bus.rdata.peek().litValue;edge();value
  }
  def exercise(d: OscResetConfigProbe): Unit=for(resetEdges<-Seq(2,4);wakeEdge<-0 until 4) {
    d.reset_n.poke(false.B);d.epochReset_n.poke(false.B)
    d.mainHold.poke(false.B);d.oscillatorHold.poke(false.B);d.coreIdle.poke(true.B)
    d.gateClosed.poke(false.B);d.stable.poke(false.B);d.wake.poke(0.U)
    d.bus.req.poke(false.B);d.bus.bits.addr.poke(0.U);d.bus.bits.we.poke(false.B)
    d.bus.bits.wdata.poke(0.U);d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(0.U)
    d.clk.step(3);d.reset_n.poke(true.B);d.epochReset_n.poke(true.B)
    d.clk.step(520);d.qualify.expect(true.B);d.stable.poke(true.B);d.clk.step(3)
    d.phase.expect(0.U);d.gateRequest.expect(true.B)
    access(d,8,true,0x1234);access(d,40,true,0x5678);access(d,12,true,0x2345)
    access(d,4,true,1);access(d,28,true,1);access(d,0,true,1)
    var n=0
    while(d.gateRequest.peek().litToBoolean && n<20) {d.clk.step();n+=1}
    assert(n<20,"RESET_CONFIG_STOP");d.clk.step(2)
    d.gateClosed.poke(true.B);d.clk.step(2);d.phase.expect(2.U);d.oscillatorOn.expect(false.B)
    d.stable.poke(false.B);d.reset_n.poke(false.B)
    // Raw service reset closes MMIO now, but cannot asynchronously tear the
    // multi-bit configuration retained by the independently clocked policy.
    assert(d.observedDelay.peek().litValue==0x1234,"RESET_CONFIG_ASYNC_DATA")
    d.bus.gnt.expect(false.B);d.bus.rvalid.expect(false.B)
    for(edge<-0 until 4) {
      if(edge==resetEdges) d.reset_n.poke(true.B)
      d.wake.poke((if(edge==wakeEdge) 1 else 0).U);d.clk.step()
    }
    d.phase.expect(3.U);d.oscillatorOn.expect(true.B);d.gateRequest.expect(false.B)
    // Wake before the synchronized reset captures the old coherent settings.
    // Once reset is observed, mandatory restart selects the existing defaults.
    val captured=if(wakeEdge<2) 0x2345 else 256
    d.count.expect(captured.U);d.observedDelay.expect(512.U)
    d.wake.poke(0.U);d.reset_n.poke(true.B)
    val startedOn=if(wakeEdge<2) wakeEdge+1 else 3
    var sinceStart=4-startedOn
    def advance(n: Int): Unit={sinceStart+=n}
    // Offer a fresh transaction immediately. It must wait for config readiness,
    // return the reset default, and subsequent accepted writes must persist.
    assert(access(d,8,advance=advance)==512,"RESET_CONFIG_DEFAULT")
    access(d,8,true,9,advance);assert(access(d,8,advance=advance)==9,"RESET_CONFIG_FRESH_WRITE_LOST")
    d.count.expect(captured.U) // An already-started qualification snapshot survives.
    // Independently count from the OFF->START edge, without reading the DUT's
    // timer registers. A wrong forced delay or timeout must fail too.
    val delay=if(wakeEdge<2) 0x1234 else 512
    val timeout=if(wakeEdge<2) 0x5678 else 4096
    val remaining=delay-sinceStart
    assert(remaining>1,"RESET_CONFIG_ORACLE_WINDOW")
    assert(!d.qualify.peek().litToBoolean,"RESET_CONFIG_QUALIFY_EARLY");d.clk.step(remaining-1)
    assert(!d.qualify.peek().litToBoolean,"RESET_CONFIG_QUALIFY_EARLY");d.fault.expect(false.B)
    d.clk.step();assert(d.qualify.peek().litToBoolean,"RESET_CONFIG_QUALIFY_LATE");d.fault.expect(false.B)
    d.clk.step(timeout-1);assert(!d.fault.peek().litToBoolean,"RESET_CONFIG_TIMEOUT_EARLY")
    d.clk.step();assert(d.fault.peek().litToBoolean,"RESET_CONFIG_TIMEOUT_LATE");d.gateRequest.expect(false.B)
    d.authorized.expect(false.B)
  }
  test("independent wake/reset ordering retains coherent settings and reopens MMIO after defaults") {
    simulateRaw(new OscResetConfigProbe)(exercise)
  }
  test("asynchronous configuration reset fault fails the same cohort oracle") {
    val error=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new OscResetConfigProbe {
        override protected def configurationReset(value: Bool): Bool=reset_n
      })(exercise)
    }
    assert(error.getMessage.contains("RESET_CONFIG_ASYNC_DATA"))
  }
  test("wrong startup delay fails the independent edge oracle") {
    val error=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new OscResetConfigProbe {
        override protected def delayValue(value: UInt): UInt=value+1.U
      })(exercise)
    }
    assert(error.getMessage.contains("RESET_CONFIG_QUALIFY_LATE"))
  }
  test("wrong startup timeout fails the independent edge oracle") {
    val error=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new OscResetConfigProbe {
        override protected def timeoutValue(value: UInt): UInt=value+1.U
      })(exercise)
    }
    assert(error.getMessage.contains("RESET_CONFIG_TIMEOUT_LATE"))
  }
  test("retained startup fault is reported after delayed configuration reset and remains W1C") {
    simulateRaw(new OscResetConfigProbe) {d=>
      d.reset_n.poke(false.B);d.epochReset_n.poke(false.B)
      d.mainHold.poke(false.B);d.oscillatorHold.poke(false.B);d.coreIdle.poke(true.B)
      d.gateClosed.poke(false.B);d.stable.poke(false.B);d.wake.poke(0.U)
      d.bus.req.poke(false.B);d.bus.bits.addr.poke(0.U);d.bus.bits.we.poke(false.B)
      d.bus.bits.wdata.poke(0.U);d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(0.U)
      d.clk.step(3);d.reset_n.poke(true.B);d.epochReset_n.poke(true.B);d.clk.step(4700)
      d.fault.expect(true.B);assert(access(d,20)==1,"RESET_CONFIG_INITIAL_FAULT")
      d.reset_n.poke(false.B);d.clk.step(3);d.reset_n.poke(true.B)
      assert(access(d,20)==1,"RESET_CONFIG_FAULT_REPORT_LOST")
      access(d,20,true,1);assert(access(d,20)==0,"RESET_CONFIG_FAULT_W1C")
      d.fault.expect(true.B);d.authorized.expect(false.B);d.gateRequest.expect(false.B)
    }
  }
}
