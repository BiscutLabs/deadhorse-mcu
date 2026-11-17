package deadhorse.perf_core

import chisel3._
import chisel3.util._
import deadhorse.fpu.{Fpu,FpuOp}

class FloatDecoded extends Bundle {
  val recognized=Bool(); val legal=Bool(); val arithmetic=Bool()
  val load=Bool(); val store=Bool(); val writeFloat=Bool(); val writeInteger=Bool()
  val useInteger=Bool(); val useF1=Bool(); val useF2=Bool(); val useF3=Bool()
  val op=UInt(5.W); val rm=UInt(3.W)
  val rs1=UInt(5.W); val rs2=UInt(5.W); val rs3=UInt(5.W); val rd=UInt(5.W)
  val substitute=UInt(32.W)
}

/** Architectural decode; no floating arithmetic is duplicated here. */
object FloatInstruction {
  def apply(i:UInt,frm:UInt,fs:UInt,directIntegerRead:Boolean=false):FloatDecoded = {
    val d=WireDefault(0.U.asTypeOf(new FloatDecoded))
    val opcode=i(6,0); val f3=i(14,12); val f7=i(31,25)
    val encoding=WireDefault(false.B); val rounding=WireDefault(false.B)
    d.rs1:=i(19,15); d.rs2:=i(24,20); d.rs3:=i(31,27); d.rd:=i(11,7)
    d.rm:=Mux(f3===7.U,frm,f3)
    val fused=opcode==="h43".U || opcode==="h47".U || opcode==="h4b".U || opcode==="h4f".U
    d.recognized:=fused || opcode==="h53".U || opcode==="h07".U || opcode==="h27".U
    when(opcode==="h07".U || opcode==="h27".U) {
      encoding:=f3===2.U; d.load:=opcode==="h07".U; d.store:=opcode==="h27".U
      d.writeFloat:=d.load; d.useF2:=d.store
    }
    when(fused) {
      encoding:=i(26,25)===0.U; rounding:=true.B; d.arithmetic:=true.B
      d.useF1:=true.B; d.useF2:=true.B; d.useF3:=true.B; d.writeFloat:=true.B
      d.op:=MuxLookup(opcode,FpuOp("MADD"))(Seq("h47".U->FpuOp("MSUB"),
        "h4b".U->FpuOp("NMSUB"),"h4f".U->FpuOp("NMADD")))
    }
    when(opcode==="h53".U) {
      d.arithmetic:=true.B; d.useF1:=true.B; d.useF2:=true.B; d.writeFloat:=true.B
      switch(f7) {
        is(0.U,4.U,8.U,12.U) {
          encoding:=true.B; rounding:=true.B
          d.op:=MuxLookup(f7,FpuOp("ADD"))(Seq(4.U->FpuOp("SUB"),8.U->FpuOp("MUL"),12.U->FpuOp("DIV")))
        }
        is(44.U) { encoding:=d.rs2===0.U; rounding:=true.B; d.op:=FpuOp("SQRT"); d.useF2:=false.B }
        is(16.U) {
          encoding:=f3<=2.U
          d.op:=MuxLookup(f3,FpuOp("SGNJ"))(Seq(1.U->FpuOp("SGNJN"),2.U->FpuOp("SGNJX")))
        }
        is(20.U) { encoding:=f3<=1.U; d.op:=Mux(f3===0.U,FpuOp("MIN"),FpuOp("MAX")) }
        is(80.U) {
          encoding:=f3<=2.U; d.writeFloat:=false.B; d.writeInteger:=true.B
          d.op:=MuxLookup(f3,FpuOp("LE"))(Seq(1.U->FpuOp("LT"),2.U->FpuOp("EQ")))
        }
        is(96.U) {
          encoding:=d.rs2<=1.U; rounding:=true.B; d.useF2:=false.B
          d.writeFloat:=false.B; d.writeInteger:=true.B
          d.op:=Mux(d.rs2===0.U,FpuOp("TO_I"),FpuOp("TO_U"))
        }
        is(104.U) {
          encoding:=d.rs2<=1.U; rounding:=true.B; d.useInteger:=true.B
          d.useF1:=false.B; d.useF2:=false.B
          d.op:=Mux(d.rs2===0.U,FpuOp("FROM_I"),FpuOp("FROM_U"))
        }
        is(112.U) {
          encoding:=d.rs2===0.U && f3<=1.U; d.useF2:=false.B
          d.writeFloat:=false.B; d.writeInteger:=true.B
          d.op:=Mux(f3===0.U,FpuOp("MV_X_W"),FpuOp("CLASS"))
        }
        is(120.U) {
          encoding:=d.rs2===0.U && f3===0.U; d.useInteger:=true.B
          d.useF1:=false.B; d.useF2:=false.B; d.op:=FpuOp("MV_W_X")
        }
      }
    }
    d.legal:=encoding && fs=/=0.U && (!rounding || d.rm<=4.U)
    when(!rounding) { d.rm:=0.U }
    // Reuse the established address/CSR/integer-control path, while retaining
    // the original instruction separately for exceptions and retirement.
    // A faithful pipeline can read the raw rs1 address unconditionally. Only
    // useInteger operations consume that value; trace read-enables stay exact.
    d.substitute:=Cat(0.U(12.W),if(directIntegerRead) d.rs1 else Mux(d.useInteger,d.rs1,0.U(5.W)),0.U(3.W),
      Mux(d.writeInteger,d.rd,0.U(5.W)),"h33".U(7.W))
    when(d.load) { d.substitute:=Cat(i(31,12),0.U(5.W),"h03".U(7.W)) }
    when(d.store) { d.substitute:=Cat(i(31,7),"h23".U(7.W)) }
    d
  }
}

/** FP state and operand staging, within the core's single gated clock domain. */
class FloatExecution extends Module with RequireAsyncReset {
  val io=IO(new Bundle {
    val decoded=Input(new FloatDecoded); val integerOperand=Input(UInt(32.W))
    val request=Input(Bool()); val commitArithmetic=Input(Bool()); val commitLoad=Input(Bool())
    val loadData=Input(UInt(32.W)); val cancel=Input(Bool())
    val valid=Output(Bool()); val result=Output(UInt(32.W)); val flags=Output(UInt(5.W))
    val source1=Output(UInt(32.W)); val source2=Output(UInt(32.W)); val source3=Output(UInt(32.W))
    val dirty=Output(Bool()); val write=Output(Bool()); val writeAddress=Output(UInt(5.W))
    val writeData=Output(UInt(32.W)); val registers=Output(UInt(1024.W))
  })
  val registers=Reg(Vec(32,UInt(32.W)))
  val d=io.decoded
  val source1=RegNext(registers(d.rs1)); val source2=RegNext(registers(d.rs2))
  val source3=RegNext(registers(d.rs3)); val integerOperand=RegNext(io.integerOperand)
  val op=RegNext(d.op); val rm=RegNext(d.rm); val useInteger=RegNext(d.useInteger)
  val fpu=Module(new Fpu)
  fpu.io.req.valid:=io.request && d.legal && d.arithmetic && !io.cancel
  fpu.io.req.bits.op:=op; fpu.io.req.bits.rm:=rm
  fpu.io.req.bits.a:=Mux(useInteger,integerOperand,source1)
  fpu.io.req.bits.b:=source2; fpu.io.req.bits.c:=source3
  fpu.io.rsp.ready:=io.commitArithmetic && !io.cancel
  fpu.io.cancel:=io.cancel
  val destination=RegEnable(d.rd,fpu.io.req.fire)
  val writesFloat=RegEnable(d.writeFloat,fpu.io.req.fire)
  val arithmeticCommit=fpu.io.rsp.fire
  val loadCommit=io.commitLoad && !io.cancel
  val write=loadCommit || (arithmeticCommit && writesFloat)
  val address=Mux(loadCommit,d.rd,destination)
  val data=Mux(loadCommit,io.loadData,fpu.io.rsp.bits.result)
  when(write) { registers(address):=data }
  io.valid:=fpu.io.rsp.valid; io.result:=fpu.io.rsp.bits.result
  io.flags:=fpu.io.rsp.bits.flags
  io.source1:=source1; io.source2:=source2; io.source3:=source3
  io.dirty:=write || (arithmeticCommit && io.flags.orR)
  io.write:=write; io.writeAddress:=address; io.writeData:=data
  io.registers:=registers.asUInt
}
