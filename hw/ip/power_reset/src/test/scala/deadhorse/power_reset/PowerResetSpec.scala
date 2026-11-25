package deadhorse.power_reset

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class PowerResetSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t33/mmio-simulation").toAbsolutePath
  }
  val json="build/t20/i1/power_reset/power_reset_regs.json"
  def initialize(d: PowerReset): Unit={
    d.reset_n.poke(false.B);d.causes.poke(0.U);d.bus.req.poke(false.B)
    d.bus.bits.addr.poke(0.U);d.bus.bits.we.poke(false.B);d.bus.bits.wdata.poke(0.U)
    d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(0.U)
    d.clk.step(3);d.threshold.expect(0.U);d.reset_n.poke(true.B);d.clk.step(3)
  }
  def access(d: PowerReset,offset: Int,write: Boolean=false,data: BigInt=0,
      mask: Int=15,owner: Int=1): (BigInt,Boolean)={
    d.bus.bits.addr.poke((0x40000500L+offset).U);d.bus.bits.we.poke(write.B)
    d.bus.bits.wdata.poke(data.U);d.bus.bits.be.poke(mask.U);d.bus.bits.origin.poke(owner.U)
    d.bus.req.poke(true.B)
    var n=0
    while(!d.bus.gnt.peek().litToBoolean && n<32) {d.clk.step();n+=1}
    assert(n<32,"POWER_GRANT");d.clk.step();d.bus.req.poke(false.B);n=0
    while(!d.bus.rvalid.peek().litToBoolean && n<32) {d.clk.step();n+=1}
    assert(n<32,"POWER_RESPONSE")
    val result=(d.bus.rdata.peek().litValue,d.bus.err.peek().litToBoolean)
    d.clk.step();result
  }
  def wrongKey(d: PowerReset): Unit={
    initialize(d)
    assert(!access(d,4,true,1)._2)
    assert(!access(d,8,true,0x42524f56L)._2)
    assert(access(d,12)==(BigInt(0),false),"POWER_BAD_KEY_CHANGED_THRESHOLD")
    assert(access(d,16)==(BigInt(1),false),"POWER_BAD_KEY_NOT_RECORDED")
  }
  test("threshold commit, ownership, masks and cause reporting follow independent register transactions") {
    simulateRaw(new PowerReset(json)) {d=>
      initialize(d)
      for(offset<-Seq(0,4,8,12,16)) assert(access(d,offset)==(BigInt(0),false))
      // The software oracle keeps shadow and active separate until a legal key.
      for(selection<-Seq(1,0,1,3,2,0)) {
        val before=access(d,12)._1
        assert(!access(d,4,true,selection)._2)
        assert(access(d,12)._1==before,"POWER_SHADOW_APPLIED_EARLY")
        assert(!access(d,8,true,0x42524f57L)._2)
        val expected=if(selection<2) BigInt(selection) else before
        assert(access(d,12)._1==expected,"POWER_SELECTION")
        d.threshold.expect(expected.U)
        if(selection>=2) {
          assert(access(d,16)._1==1,"POWER_RESERVED_SELECTOR")
          assert(!access(d,16,true,1)._2);assert(access(d,16)._1==0)
        }
      }
      assert(!access(d,4,true,1)._2)
      for(mask<-Seq(0,1,2,3,7,8,14)) {
        val response=access(d,8,true,0x42524f57L,mask)
        assert(response._2==(mask!=0),"POWER_PARTIAL_KEY")
        d.threshold.expect(0.U)
      }
      for(owner<-0 to 7 if owner!=1) {
        assert(access(d,8,true,0x42524f57L,owner=owner)._2,"POWER_OWNER")
        d.threshold.expect(0.U)
      }
      for(offset<-Seq(0x14,0xfc,5)) assert(access(d,offset,true,1)._2,"POWER_HOLE")
      for(reason<-0 until 64) {
        d.causes.poke(reason.U);d.clk.step(2)
        assert(access(d,0)==(BigInt(reason),false),"POWER_REASON")
      }
      assert(!access(d,8,true,0x42524f57L)._2);d.threshold.expect(1.U)
      d.reset_n.poke(false.B);d.threshold.expect(0.U)
      d.clk.step(2);d.reset_n.poke(true.B);d.clk.step(3)
      assert(access(d,4)._1==0);assert(access(d,12)._1==0)
      assert(access(d,0)._1==63,"POWER_UPSTREAM_REASON_RETENTION")
    }
  }
  test("wrong key has no effect") {simulateRaw(new PowerReset(json))(wrongKey)}
  test("actual key-check fault fails the same oracle") {
    val failure=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new PowerReset(json) {
        override protected def makeSelector(): BrownoutSelect=new BrownoutSelect {
          override protected def acceptKey(value: Bool): Bool=true.B
        }
      })(wrongKey)
    }
    assert(failure.getMessage.contains("POWER_BAD_KEY_CHANGED_THRESHOLD"))
  }
}
