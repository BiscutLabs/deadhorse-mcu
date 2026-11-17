package deadhorse.bus

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import deadhorse.lib._
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException
import scala.util.Random

class BusWrong extends BusFabric(3, Seq(BusRegion(0x1000,256,16),BusRegion(0x2000,256,16))) {
  override protected def response(value: UInt): UInt = value ^ 1.U
}
class BusTest(wrong: Boolean) extends RawModule {
  val clockPin = IO(Input(Bool())); val reset_n = IO(Input(Bool()))
  val master = IO(Vec(3,new LocalBus)); val target = IO(Vec(2,Flipped(new LocalBus)))
  val admit = IO(Input(Vec(2,Bool()))); val allow = IO(Input(Vec(3,Bool())))
  val quiescent = IO(Input(Vec(2,Bool()))); val isolated = IO(Output(Vec(2,Bool())))
  def design: BusFabric = if(wrong) new BusWrong else new BusFabric(3,Seq(BusRegion(0x1000,256,16),BusRegion(0x2000,256,16)))
  val dut = Module(design)
  dut.clk := clockPin.asClock; dut.reset_n := reset_n
  dut.master <> master; dut.target <> target
  dut.admit := admit; dut.allow := allow; dut.quiescent := quiescent
  isolated := dut.isolated
}

class BusSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t14/bus-simulation").toAbsolutePath
  }
  case class Request(addr: Int, data: BigInt, be: Int, write: Boolean, origin: Int, allowed: Boolean)
  def check(d: BusTest): Unit = {
    val random = new Random(0xb051401); println("BUS seed=0xb051401")
    val offered = Array.fill[Option[Request]](3)(None)
    val owed = Array.fill[Option[(Request,Int)]](3)(None)
    val replies = Array.fill[Option[(Request,Int)]](2)(None)
    var transfers = 0
    def yes(x: Bool) = x.peek().litValue == 1
    def image(addr: Int): BigInt = BigInt(addr) ^ BigInt("5a13ac91",16)
    def region(a: Int): Int = if(a>=0x1000 && a<0x1100) 0 else if(a>=0x2000 && a<0x2100) 1 else -1
    def fails(r: Request): Boolean = region(r.addr)<0 || (r.addr&3)!=0 || !r.allowed || (r.addr&0x3c)==0x3c
    def drive(port: LocalBus, r: Request): Unit = {
      port.bits.addr.poke(r.addr.U);port.bits.wdata.poke(r.data.U);port.bits.be.poke(r.be.U)
      port.bits.we.poke(r.write.B);port.bits.origin.poke(r.origin.U)
    }
    def edge(): Unit = {
      d.clockPin.poke(true.B);d.master(0).gnt.peek()
      d.clockPin.poke(false.B);d.master(0).gnt.peek()
    }
    d.clockPin.poke(false.B);d.reset_n.poke(true.B)
    for(i<-0 until 3){d.master(i).req.poke(false.B);drive(d.master(i),Request(0,0,0,false,0,true));d.allow(i).poke(true.B)}
    for(t<-0 until 2){d.admit(t).poke(true.B);d.quiescent(t).poke(false.B);d.target(t).gnt.poke(false.B);d.target(t).rvalid.poke(false.B);d.target(t).rdata.poke(0.U);d.target(t).err.poke(false.B)}
    d.master(0).gnt.peek();d.reset_n.poke(false.B);d.master(0).gnt.peek();d.reset_n.poke(true.B)
    for(cycle<-0 until 1800){
      for(i<-0 until 3){
        if(cycle<1600 && offered(i).isEmpty && owed(i).isEmpty && random.nextInt(3)==0){
          val base=Seq(0x1000,0x2000,0x6000)(random.nextInt(3))
          val addr=base+4*random.nextInt(16)+(if(random.nextInt(7)==0)1 else 0)
          offered(i)=Some(Request(addr,BigInt(32,random),random.nextInt(16),random.nextBoolean(),i,random.nextInt(5)!=0))
        }
        d.master(i).req.poke(offered(i).isDefined.B)
        offered(i).foreach(r=>drive(d.master(i),r))
        d.allow(i).poke(offered(i).orElse(owed(i).map(_._1)).forall(_.allowed).B)
      }
      d.admit(0).poke(true.B); d.admit(1).poke((cycle%23>=7).B)
      for(t<-0 until 2){
        d.target(t).gnt.poke((replies(t).isEmpty && cycle%4!=0).B)
        val reply=replies(t).filter(_._2==0)
        d.target(t).rvalid.poke(reply.isDefined.B)
        d.target(t).rdata.poke(reply.map(x=>image(x._1.addr)).getOrElse(BigInt(0)).U)
        d.target(t).err.poke(reply.exists(x=>(x._1.addr&0x3c)==0x3c).B)
      }
      for(i<-0 until 3){
        if(yes(d.master(i).rvalid)){
          assert(owed(i).isDefined,"BUS_MODEL_MISMATCH unsolicited response")
          val(r,start)=owed(i).get
          assert(cycle>start && cycle-start<=16,"BUS_MODEL_MISMATCH deadline")
          assert(yes(d.master(i).err)==fails(r),"BUS_MODEL_MISMATCH error")
          assert(d.master(i).rdata.peek().litValue==(if(fails(r)||r.write)BigInt(0) else image(r.addr)),"BUS_MODEL_MISMATCH data")
          owed(i)=None;transfers+=1
        }
        if(yes(d.master(i).gnt)){
          assert(offered(i).isDefined && owed(i).isEmpty,"BUS_MODEL_MISMATCH grant")
          owed(i)=Some((offered(i).get,cycle));offered(i)=None
        }
      }
      for(t<-0 until 2){
        replies(t)=replies(t).filter(_._2>0).map{case(r,n)=>(r,n-1)}
        if(yes(d.target(t).req)&&yes(d.target(t).gnt)){
          val matches=owed.toSeq.flatten.map(_._1).filter(r=>r.addr==d.target(t).bits.addr.peek().litValue.toInt)
          assert(matches.size==1,"BUS_MODEL_MISMATCH target without owner")
          val r=matches.head
          assert(region(r.addr)==t && r.allowed && (r.addr&3)==0,"BUS_MODEL_MISMATCH unauthorized target")
          assert(d.target(t).bits.wdata.peek().litValue==r.data && d.target(t).bits.be.peek().litValue==r.be &&
            yes(d.target(t).bits.we)==r.write && d.target(t).bits.origin.peek().litValue==r.origin,"BUS_MODEL_MISMATCH payload")
          replies(t)=Some((r,random.nextInt(3)))
        }
      }
      assert(owed.count(_.isDefined)<=1,"BUS_MODEL_MISMATCH multiple outstanding")
      edge()
    }
    assert(transfers>100 && owed.forall(_.isEmpty) && offered.forall(_.isEmpty))
    println(s"PASS BUS $transfers transactions")
  }
  test("round-robin registered bus matches independent transactions with denial and delayed targets"){
    simulateRaw(new BusTest(false),subdirectory=Some("normal"))(check)
  }
  test("bus checker rejects corrupted actual response datapath"){
    val failure=intercept[TestFailedException]{simulateRaw(new BusTest(true),subdirectory=Some("corrupt"))(check)}
    assert(failure.getMessage.contains("BUS_MODEL_MISMATCH"))
  }
  test("timeout quarantines late replies, explicit quiescence reopens, final-edge reply wins and arbitration rotates"){
    simulateRaw(new BusTest(false),subdirectory=Some("recovery")){d=>
      def yes(b:Bool)=b.peek().litValue==1
      def edge():Unit={d.clockPin.poke(true.B);d.master(0).gnt.peek();d.clockPin.poke(false.B);d.master(0).gnt.peek()}
      d.clockPin.poke(false.B);d.reset_n.poke(true.B)
      for(i<-0 until 3){
        d.master(i).req.poke(false.B);d.master(i).bits.addr.poke(0x1000.U);d.master(i).bits.wdata.poke(0.U)
        d.master(i).bits.be.poke(15.U);d.master(i).bits.we.poke(false.B);d.master(i).bits.origin.poke(i.U);d.allow(i).poke(true.B)
      }
      for(t<-0 until 2){d.admit(t).poke(true.B);d.quiescent(t).poke(false.B);d.target(t).gnt.poke(true.B);d.target(t).rvalid.poke(false.B);d.target(t).rdata.poke(0.U);d.target(t).err.poke(false.B)}
      d.master(0).gnt.peek();d.reset_n.poke(false.B);d.master(0).gnt.peek();d.reset_n.poke(true.B)
      def access(finalReply:Boolean,expectedError:Boolean):Unit={
        d.master(0).req.poke(true.B)
        var accepted=false;var age=0;var done=false
        for(_<-0 until 32 if !done){
          if(accepted)age+=1
          d.target(0).rvalid.poke((finalReply&&accepted&&age==15).B);d.target(0).rdata.poke(0x76543210.U)
          val take=yes(d.master(0).gnt)&&yes(d.master(0).req)
          if(yes(d.master(0).rvalid)){
            assert(accepted && yes(d.master(0).err)==expectedError,"BUS_RECOVERY_MISMATCH response")
            assert(d.master(0).rdata.peek().litValue==(if(expectedError)BigInt(0) else BigInt("76543210",16)))
            done=true
          }
          edge();if(take){accepted=true;age=0;d.master(0).req.poke(false.B)}
        }
        assert(done);d.target(0).rvalid.poke(false.B);for(_<-0 until 3)edge()
      }
      access(false,true);assert(yes(d.isolated(0)))
      access(false,true);assert(yes(d.isolated(0)))
      // Late response drains, but produces no extra master response.
      d.target(0).rvalid.poke(true.B);edge();d.target(0).rvalid.poke(false.B)
      assert(!yes(d.isolated(0)) && !yes(d.master(0).rvalid))
      access(true,false)
      access(false,true);d.quiescent(0).poke(true.B);edge();d.quiescent(0).poke(false.B)
      assert(!yes(d.isolated(0)));access(true,false)
      d.reset_n.poke(false.B);d.master(0).gnt.peek();d.reset_n.poke(true.B)
      for(i<-0 until 3){d.master(i).bits.addr.poke(0x6000.U);d.master(i).req.poke(true.B)}
      var turns=Vector.empty[Int]
      for(_<-0 until 100 if turns.size<18){
        for(i<-0 until 3 if yes(d.master(i).gnt))turns=turns:+i
        edge()
      }
      assert(turns==(0 until 18).map(_%3).toVector,"BUS_RECOVERY_MISMATCH starvation/order")
    }
  }
}
