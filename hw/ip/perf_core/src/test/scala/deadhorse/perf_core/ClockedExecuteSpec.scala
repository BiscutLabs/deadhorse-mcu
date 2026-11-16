package deadhorse.perf_core

import chisel3._
import chisel3.util.Decoupled
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException

class ExecuteTestHarness(corrupt: Boolean = false) extends RawModule {
  val tick = IO(Input(Bool())); val reset_n = IO(Input(Bool()))
  val req = IO(Flipped(Decoupled(new ExecuteRequest)))
  val rsp = IO(Decoupled(new ExecuteResponse))
  val dut = Module(new ClockedExecute)
  dut.clk_i := tick.asClock; dut.rst_ni := reset_n
  dut.req <> req
  dut.rsp.ready := rsp.ready
  rsp.valid := dut.rsp.valid
  rsp.bits := dut.rsp.bits
  rsp.bits.result := dut.rsp.bits.result ^ (if(corrupt) dut.rsp.valid.asUInt else 0.U)
}

class ClockedExecuteSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t11/simulation").toAbsolutePath
  }
  private val word = BigInt(1)<<32
  private val mask = word-1
  private case class Request(kind: Int, a: BigInt, b: BigInt, op: String="ADD", mode: Int=0,
      high: Boolean=false, first: Boolean=true, constant: Boolean=false)
  private def signed(x: BigInt, on: Boolean): BigInt = if(on && x.testBit(31)) x-word else x
  private def expected(r: Request): (BigInt,BigInt,Boolean) = {
    val x=signed(r.a,(r.mode&1)!=0); val y=signed(r.b,(r.mode&2)!=0)
    if(r.kind!=0) {
      val value=r.kind match {
        case 1 => if(r.high) (x*y)>>32 else x*y
        case 2 => if(y==0) mask else x/y
        case 3 => if(y==0) r.a else x%y
      }
      (value&mask,BigInt(0),false)
    } else {
      val sx=signed(r.a,true); val sy=signed(r.b,true)
      val subtract=Set("SUB","EQ","NE","GE","GEU","LT","LTU","SLT","SLTU").contains(r.op)
      val adder=(if(subtract) r.a-r.b else r.a+r.b)&mask
      val comparison=r.op match {
        case "EQ" => r.a==r.b
        case "NE" => r.a!=r.b
        case "GE" => sx>=sy
        case "GEU" => r.a>=r.b
        case "LT"|"SLT" => sx<sy
        case "LTU"|"SLTU" => r.a<r.b
        case _ => adder==0
      }
      val n=if(r.first) (r.b&31).toInt else ((-r.b)&31).toInt
      val value=r.op match {
        case "ADD"|"SUB" => adder
        case "XOR" => r.a^r.b
        case "OR" => r.a|r.b
        case "AND" => r.a&r.b
        case "SLL" => r.a<<n
        case "SRL" => r.a>>n
        case "SRA" => sx>>n
        case _ => if(comparison) BigInt(1) else BigInt(0)
      }
      (value&mask,adder,comparison)
    }
  }
  private def check(d: ExecuteTestHarness, resetSweep: Boolean): Unit = {
    val random=new scala.util.Random(0xced111L)
    println("ClockedExecute seed=0xced111")
    def edge(): Unit = { d.tick.poke(true.B); d.rsp.valid.peek(); d.tick.poke(false.B) }
    def drive(r: Request): Unit = {
      d.req.bits.kind.poke(r.kind.U); d.req.bits.a.poke(r.a.U); d.req.bits.b.poke(r.b.U)
      d.req.bits.aluOp.poke(IbexAluOp(r.op)); d.req.bits.signedMode.poke(r.mode.U)
      d.req.bits.high.poke(r.high.B); d.req.bits.firstCycle.poke(r.first.B)
      d.req.bits.constantTime.poke(r.constant.B)
    }
    def reset(): Unit = {
      d.reset_n.poke(false.B); d.rsp.valid.expect(false.B); d.req.ready.expect(true.B)
      d.rsp.bits.result.expect(0.U); d.reset_n.poke(true.B)
    }
    def transaction(r: Request): Unit = {
      val (value,adder,comparison)=expected(r)
      d.req.ready.expect(true.B); d.rsp.valid.expect(false.B)
      drive(r); d.req.valid.poke(true.B); d.rsp.ready.poke(false.B); edge()
      // Every request field changes while busy. None may replace captured data.
      drive(Request(3-r.kind,r.a^mask,r.b^mask,"XOR",3-r.mode,!r.high,!r.first,!r.constant))
      d.req.ready.expect(false.B)
      val deadline=if(r.kind==0) 1 else if(r.kind==1) 36 else if(r.b==0 && !r.constant) 6 else 111
      for(_ <- 0 until deadline) {
        d.rsp.valid.expect(false.B); d.req.ready.expect(false.B)
        d.rsp.ready.poke(random.nextBoolean().B); edge()
      }
      d.rsp.valid.expect(true.B); d.req.ready.expect(false.B)
      d.req.valid.poke(false.B); d.rsp.ready.poke(false.B)
      for(_ <- 0 until 3) {
        assert(d.rsp.bits.result.peek().litValue==value,"EXECUTE_MODEL_MISMATCH")
        d.rsp.bits.adder.expect(adder.U); d.rsp.bits.comparison.expect(comparison.B)
        edge(); d.rsp.valid.expect(true.B)
      }
      d.rsp.ready.poke(true.B); edge(); d.rsp.valid.expect(false.B); d.req.ready.expect(true.B)
      edge(); d.rsp.valid.expect(false.B)
    }
    d.tick.poke(false.B); d.reset_n.poke(true.B); d.req.valid.poke(false.B)
    d.rsp.ready.poke(false.B); drive(Request(0,0,0)); reset()
    if(resetSweep) {
      for(kind <- Seq(1,2); phase <- 0 to (if(kind==1) 37 else 112)) {
        d.req.valid.poke(true.B); d.rsp.ready.poke(false.B)
        drive(Request(kind,mask,7,mode=3,high=true,constant=true))
        for(_ <- 0 until phase) edge()
        reset(); d.req.valid.poke(false.B)
        transaction(Request(0,7,11))
      }
    }
    val edges=Seq(BigInt(0),BigInt(1),BigInt(2),mask,word/2,word/2-1)
    val pairs=(for(a<-edges;b<-edges) yield (a,b)) ++ (0 until 32).map(_=>(BigInt(32,random),BigInt(32,random)))
    for((a,b)<-pairs) {
      for(op<-Seq("ADD","SUB","AND","OR","XOR","SLL","SRL","SRA","EQ","NE","GE","GEU","LT","LTU","SLT","SLTU");
          first<-Seq(true,false)) transaction(Request(0,a,b,op=op,first=first))
      for((mode,high)<-Seq((0,false),(0,true),(1,true),(3,true))) transaction(Request(1,a,b,mode=mode,high=high))
      for(kind<-Seq(2,3); mode<-Seq(0,3); constant<-Seq(false,true))
        transaction(Request(kind,a,b,mode=mode,constant=constant))
    }
  }
  test("registered execution matches integer model with exact progress, capture, backpressure and reset") {
    simulateRaw(new ExecuteTestHarness,subdirectory=Some("clocked_execute"))(d=>check(d,true))
  }
  test("registered execution checker rejects corrupt results") {
    val failure=intercept[TestFailedException] {
      simulateRaw(new ExecuteTestHarness(true),subdirectory=Some("clocked_execute_fault"))(d=>check(d,false))
    }
    assert(failure.getMessage.contains("EXECUTE_MODEL_MISMATCH"))
  }
}
