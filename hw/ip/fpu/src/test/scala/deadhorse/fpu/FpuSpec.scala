package deadhorse.fpu

import chisel3._
import chisel3.util._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import scala.io.Source
import scala.sys.process._

class FpuTestHarness extends RawModule {
  val tick = IO(Input(Bool())); val reset_n = IO(Input(Bool()))
  val req = IO(Flipped(Decoupled(new FpuRequest)))
  val rsp = IO(Decoupled(new FpuResponse))
  val cancel = IO(Input(Bool())); val busy = IO(Output(Bool()))
  val fault = IO(Input(UInt(2.W)))
  val dut = withClockAndReset(tick.asClock, (!reset_n).asAsyncReset) { Module(new Fpu) }
  dut.io.req <> req; dut.io.rsp.ready := rsp.ready; dut.io.cancel := cancel
  busy := dut.io.busy; rsp.valid := dut.io.rsp.valid; rsp.bits := dut.io.rsp.bits
  // Verification-only real result and flag mutations at the observable boundary.
  when (fault === 1.U) { rsp.bits.result := dut.io.rsp.bits.result ^ 1.U }
  when (fault === 2.U) { rsp.bits.flags := dut.io.rsp.bits.flags ^ 1.U }
}

class FpuSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t12/scala").toAbsolutePath
  }
  case class Vector(op:Int, rm:Int, a:BigInt, b:BigInt, c:BigInt, result:BigInt, flags:BigInt)
  private lazy val vectors: Seq[Vector] = {
    assert(Process(Seq("python3","dv/fpu/vectors.py")).! == 0)
    val source=Source.fromFile("build/t12/vectors.txt")
    try source.getLines().map { line =>
      val f=line.split(" "); Vector(f(0).toInt,f(1).toInt,BigInt(f(2),16),
        BigInt(f(3),16),BigInt(f(4),16),BigInt(f(5),16),BigInt(f(6),16))
    }.toVector finally source.close()
  }
  test("FPU reference samples, cancellation/reset at every phase, and result/flag fault detection") {
    val sample=vectors.groupBy(v=>(v.op,v.rm)).toSeq.sortBy(_._1).flatMap {
      case (_,xs) => Seq(xs(31),xs(513),xs(1100))
    }
    simulateRaw(new FpuTestHarness,subdirectory=Some("protocol")) { d =>
      def edge(): Unit = {
        d.tick.poke(false.B); d.rsp.valid.peek()
        d.tick.poke(true.B); d.rsp.valid.peek()
        d.tick.poke(false.B); d.rsp.valid.peek()
      }
      def idle(): Unit = {
        d.req.ready.expect(true.B); d.busy.expect(false.B); d.rsp.valid.expect(false.B)
      }
      def reset(): Unit = {
        d.reset_n.poke(false.B); idle(); d.reset_n.poke(true.B)
      }
      def drive(v:Vector): Unit = {
        d.req.bits.op.poke(v.op.U); d.req.bits.rm.poke(v.rm.U)
        d.req.bits.a.poke(v.a.U); d.req.bits.b.poke(v.b.U); d.req.bits.c.poke(v.c.U)
      }
      def start(v:Vector): Unit = {
        idle(); drive(v); d.req.valid.poke(true.B); edge(); d.req.valid.poke(false.B)
      }
      def complete(v:Vector, fault:Int=0): Unit = {
        val limit=if(v.op<=6) 38 else if(v.op==7) 58 else if(v.op==8) 56 else
          if(v.op==20 || v.op==21) 6 else if(v.op>=22 && v.op<24) 8 else
          if(v.op>=9 && v.op<=13) 4 else 3
        var age=0
        while(!d.rsp.valid.peek().litToBoolean && age<limit) { edge(); age+=1 }
        assert(d.rsp.valid.peek().litToBoolean,"FPU completion deadline")
        val matches=d.rsp.bits.result.peek().litValue==v.result && d.rsp.bits.flags.peek().litValue==v.flags
        if(fault==0) assert(matches,s"FPU_MODEL_MISMATCH $v")
        else assert(!matches,s"FPU fault escaped: op=${v.op} fault=$fault")
        d.rsp.ready.poke(true.B); edge(); d.rsp.ready.poke(false.B); idle()
      }
      d.tick.poke(false.B); d.req.valid.poke(false.B); d.rsp.ready.poke(false.B)
      d.cancel.poke(false.B); d.fault.poke(0.U); drive(sample.head); reset()
      println("FPU samples")
      for(v<-sample) { start(v); complete(v) }
      // One result fault and one flag fault for every operation, not merely a
      // test that observes a fault-enable signal.
      println("FPU faults")
      for(op<-0 until 24; fault<-Seq(1,2)) {
        val v=sample.find(_.op==op).get
        d.fault.poke(fault.U); start(v); complete(v,fault)
      }
      d.fault.poke(0.U)
      val replacement=Vector(0,0,BigInt("3f800000",16),BigInt("40000000",16),0,
                             BigInt("40400000",16),0)
      for(op<-Seq(3,7,8,20,22); phase<-0 to (if(op==3) 40 else if(op==7) 60 else if(op==8) 58 else if(op==20) 8 else 10); useReset<-Seq(false,true)) {
        val v=vectors.find(x=>x.op==op && x.rm==0 && x.a==BigInt("3f800001",16) &&
                           x.b==BigInt("3f7fffff",16)).get
        start(v); for(_<-0 until phase) edge()
        // Include held responses, busy iterations, acceptance attempts and
        // response-ready collisions. Cancel takes precedence over both ends.
        d.req.valid.poke(true.B); d.rsp.ready.poke(true.B)
        if(useReset) reset() else { d.cancel.poke(true.B); edge(); d.cancel.poke(false.B) }
        d.req.valid.poke(false.B); d.rsp.ready.poke(false.B); idle()
        d.rsp.bits.result.expect(0.U); d.rsp.bits.flags.expect(0.U)
        start(replacement); complete(replacement)
        for(nextOp<-Seq(7,8)) {
          start(v); for(_<-0 until phase) edge()
          d.cancel.poke(true.B); edge(); d.cancel.poke(false.B)
          val next=vectors.find(x=>x.op==nextOp && x.rm==3 && x.a==BigInt("3e800000",16) &&
                                x.b==BigInt("3f800000",16)).get
          start(next); complete(next)
        }
      }
      for(op<-Seq(24,31); rm<-Seq(0,5,7)) {
        val v=Vector(op,rm,0,0,0,BigInt("7fc00000",16),16); start(v); complete(v)
      }
      drive(replacement); d.req.valid.poke(true.B); d.cancel.poke(true.B)
      edge(); d.req.valid.poke(false.B); d.cancel.poke(false.B); idle()
    }
  }
}
