package deadhorse.lite_core

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class LiteInitializeSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t41/lite-initialize-simulation").toAbsolutePath
  }
  def exercise(d: LiteHart): Unit={
    import Assembly._
    def high(v: Bool)=v.peek().litToBoolean
    d.reset_n.poke(false.B);d.initialize.get.poke(false.B)
    d.start.poke(false.B);d.entry.poke(0.U);d.irq.poke(false.B)
    d.debug.get.request.poke(false.B);d.debug.get.allowEntry.poke(true.B);d.debug.get.stop.poke(false.B)
    d.bus.gnt.poke(false.B);d.bus.rvalid.poke(false.B);d.bus.rdata.poke(0.U);d.bus.err.poke(false.B)
    d.clk.step(3);d.reset_n.poke(true.B);d.clk.step(3)
    var cycles=0;var seen=Vector.empty[(BigInt,BigInt)]
    def tick(): Unit={
      d.clk.step();cycles+=1;assert(cycles<3000,"LITE_INIT_DEADLINE")
      if(high(d.rvfi.valid) && d.rvfi.rd_addr.peek().litValue!=0)
        seen :+= ((d.rvfi.rd_addr.peek().litValue,d.rvfi.rd_wdata.peek().litValue))
    }
    def run(program: Seq[Long]): Vector[(BigInt,BigInt)]={
      seen=Vector.empty;d.start.poke(true.B);tick();d.start.poke(false.B)
      for((insn,index)<-program.zipWithIndex) {
        while(!high(d.bus.req)) tick()
        assert(!high(d.bus.bits.we) && d.bus.bits.addr.peek().litValue==index*4,"LITE_INIT_FETCH")
        for(_<-0 until index%3) tick()
        d.bus.gnt.poke(true.B);tick();d.bus.gnt.poke(false.B)
        for(_<-0 until index%4) tick()
        d.bus.rdata.poke(insn.U);d.bus.rvalid.poke(true.B);tick();d.bus.rvalid.poke(false.B)
      }
      while(!high(d.sleeping)) tick()
      for(_<-0 until 4) tick()
      assert(!high(d.bus.req),"LITE_INIT_SLEEP_DRAIN")
      seen
    }
    val dirty=(1 to 15).map(r=>i(0x13,r,0,0,32+r)) ++ Seq(0x34009073L,0x10500073L) // mscratch=x1; WFI
    assert(run(dirty)==(1 to 15).map(r=>(BigInt(r),BigInt(32+r))).toVector)
    // The accepted work has drained. HOLD initializes state without another
    // reset tree, and the acknowledgement must follow the initialization edge.
    d.initialize.get.poke(true.B);d.initialized.get.expect(false.B)
    tick();d.initialized.get.expect(true.B);d.halted.expect(true.B)
    d.sleeping.expect(false.B);d.debug.get.mode.expect(false.B);d.bus.req.expect(false.B)
    for(_<-0 until 3) tick()
    d.initialize.get.poke(false.B);tick();d.initialized.get.expect(false.B)
    val verify=Seq(i(0x13,15,0,15,0)) ++ (1 to 14).map(r=>i(0x13,15,0,r,0)) ++
      Seq(0x340027f3L,0x10500073L) // x15=mscratch; WFI
    val result=run(verify)
    assert(result==Vector.fill(16)((BigInt(15),BigInt(0))),"LITE_INIT_STATE_SURVIVED")
    d.reset_n.poke(false.B);d.initialized.get.expect(false.B);d.halted.expect(true.B)
  }
  test("drained HOLD initializes GPRs, CSR, pipeline and RVFI restart through the production hart") {
    simulateRaw(new LiteHart(withDebug=true,withInitialize=true))(exercise)
  }
  test("a register surviving local initialization fails the same program oracle") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new LiteHart(withDebug=true,withInitialize=true) {
        override protected def makeCore(): LiteCore=new LiteCore(withDebug=true,withInitialize=true) {
          override protected def initializedRegister(index: Int): UInt=if(index==1) 1.U(32.W) else 0.U(32.W)
        }
      })(exercise)
    }
    assert(e.getMessage.contains("LITE_INIT_STATE_SURVIVED"))
  }
}
