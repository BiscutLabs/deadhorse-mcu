package deadhorse.mailbox

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import deadhorse.lib._
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException

class MailboxBadEndpoint(json: String, owner: Int) extends MailboxEndpoint(json,owner) {
  override protected def readHead(value: UInt): UInt = value ^ 1.U
}
class MailboxBad(json: String) extends Mailbox(json) {
  override protected def endpoint(owner: Int): MailboxEndpoint = new MailboxBadEndpoint(json,owner)
}
class MailboxTest(json: String, corrupt: Boolean = false) extends RawModule {
  val ac = IO(Input(Bool())); val mc = IO(Input(Bool()))
  val an = IO(Input(Bool())); val mn = IO(Input(Bool()))
  val a = IO(new LocalBus); val m = IO(new LocalBus)
  val irq = IO(Output(Vec(2,Bool()))); val wake = IO(Output(Vec(2,Bool())))
  def design: Mailbox = if(corrupt)new MailboxBad(json) else new Mailbox(json)
  val dut = Module(design)
  dut.aonClock := ac.asClock; dut.mainClock := mc.asClock; dut.aonReset_n := an; dut.mainReset_n := mn
  dut.aon <> a; dut.main <> m; irq := dut.irq; wake := dut.wakePeer
}

class MailboxSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t14/mailbox-simulation").toAbsolutePath
  }
  def runCase(corrupt:Boolean): Unit = {
    os.proc("python3","hw/regmap/regmap.py","hw/ip/mailbox/mailbox.regmap.yaml","--out","build/t14/mailbox-regmap").call()
    simulateRaw(new MailboxTest("build/t14/mailbox-regmap/mailbox_regs.json",corrupt),subdirectory=Some(if(corrupt)"corrupt" else "registers")){ d =>
      def yes(b: Bool)=b.peek().litValue==1
      var mainStopped=false
      def step(): Unit = {
        d.ac.poke(true.B);d.mc.poke((!mainStopped).B);d.irq(0).peek()
        d.ac.poke(false.B);d.mc.poke(false.B);d.irq(0).peek()
      }
      d.ac.poke(false.B);d.mc.poke(false.B);d.an.poke(true.B);d.mn.poke(true.B)
      for(p<-Seq(d.a,d.m)){
        p.req.poke(false.B);p.bits.addr.poke(0.U);p.bits.wdata.poke(0.U);p.bits.be.poke(0.U)
        p.bits.we.poke(false.B);p.bits.origin.poke(0.U)
      }
      d.irq(0).peek();d.an.poke(false.B);d.mn.poke(false.B);d.irq(0).peek()
      d.an.poke(true.B);d.mn.poke(true.B);for(_<-0 until 12)step()
      def access(side: Int,offset: Int,write: Boolean=false,value: BigInt=0,be: Int=15,origin: Int = -1): (BigInt,Boolean) = {
        val p=if(side==0)d.a else d.m
        p.req.poke(true.B);p.bits.addr.poke((BigInt("40001000",16)+offset).U)
        p.bits.wdata.poke(value.U);p.bits.we.poke(write.B);p.bits.be.poke(be.U)
        p.bits.origin.poke((if(origin<0)side else origin).U)
        var granted=false;var done=false;var result=BigInt(0);var error=false
        for(_<-0 until 20 if !done){
          val accept=yes(p.gnt)&&yes(p.req);val valid=yes(p.rvalid)
          if(valid){assert(granted,"MAILBOX_MODEL_MISMATCH unsolicited response");result=p.rdata.peek().litValue;error=yes(p.err);done=true}
          step()
          if(accept){assert(!granted);granted=true;p.req.poke(false.B)}
        }
        assert(done,"MAILBOX_MODEL_MISMATCH bus deadline")
        p.req.poke(false.B);step();(result,error)
      }
      def wr(side:Int,offset:Int,value:BigInt):Unit=assert(!access(side,offset,true,value)._2)
      def rd(side:Int,offset:Int):BigInt={val(v,e)=access(side,offset);assert(!e);v}
      assert(rd(0,12)==5 && rd(1,12)==5)
      mainStopped=true
      for(word<-Seq(BigInt("12345678",16),BigInt("fedcba98",16))){wr(0,0,word);wr(0,4,1)}
      assert(yes(d.wake(0)),"MAILBOX_MODEL_MISMATCH missing stopped-receiver wake")
      assert((rd(0,12)&1)==0)
      wr(0,0,0xdead);wr(0,4,1);assert((rd(0,16)&1)==1)
      mainStopped=false;for(_<-0 until 10)step()
      assert(yes(d.irq(1)))
      for(word<-Seq(BigInt("12345678",16),BigInt("fedcba98",16))){
        assert(rd(1,8)==word,"MAILBOX_MODEL_MISMATCH word");assert(rd(1,8)==word) // reads never consume
        wr(1,4,2)
      }
      for(_<-0 until 8)step()
      assert(!yes(d.irq(1)) && !yes(d.wake(0)))
      wr(1,4,2);assert((rd(1,16)&2)==2)
      wr(0,16,1);wr(1,16,2);assert(rd(0,16)==0 && rd(1,16)==0)
      assert(access(0,0,true,0x1111,15,origin=1)._2)
      assert(access(0,0,true,0x2222,3)._2) // partial WO is a command error
      assert(access(0,1,true,0x3333)._2)
      wr(1,0,0x55667788);wr(1,4,1);assert(rd(0,8)==BigInt("55667788",16));wr(0,4,2)
      wr(0,0,0x99);wr(0,4,1)
      // Reset pulse with both clocks stopped flushes queued data and is retained.
      d.mn.poke(false.B);d.irq(0).peek();d.mn.poke(true.B);d.irq(0).peek()
      for(_<-0 until 12)step()
      assert((rd(0,16)&4)==4 && rd(1,8)==0 && !yes(d.irq(1)))
      wr(0,16,4);assert(rd(0,16)==0)
      wr(0,0,0x1357);wr(0,4,1);assert(rd(1,8)==0x1357);wr(1,4,2)
    }
  }
  test("generated mailbox registers preserve ordered words, ownership, overflow, wake and peer reset"){runCase(false)}
  test("mailbox checker rejects an actual read datapath fault"){
    val failure=intercept[TestFailedException]{runCase(true)}
    assert(failure.getMessage.contains("MAILBOX_MODEL_MISMATCH word"))
  }
}
