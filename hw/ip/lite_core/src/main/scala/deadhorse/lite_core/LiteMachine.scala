package deadhorse.lite_core
import chisel3._
import chisel3.util._

/** Pure CSR decisions inside the clocked hart, not a separate combinational block. */
class LiteMachineState extends Bundle {
  val mie=Bool();val mpie=Bool();val meie=Bool()
  val mtvec=UInt(32.W);val scratch=UInt(32.W);val mepc=UInt(32.W);val cause=UInt(32.W)
  val cycle=UInt(64.W);val retired=UInt(64.W);val inhibitCycle=Bool();val inhibitRetired=Bool()
}
object LiteMachine {
  def read(s: LiteMachineState,address: UInt,irq: Bool): (Bool,UInt)={
    val values=Seq(
      0x300->(0x1800.U(32.W) | s.mie.asUInt<<3 | s.mpie.asUInt<<7),
      0x301->"h40000010".U(32.W),0x304->(s.meie.asUInt<<11),0x305->s.mtvec,
      0x306->0.U(32.W),0x310->0.U(32.W),
      0x320->(s.inhibitCycle.asUInt | s.inhibitRetired.asUInt<<2),
      0x340->s.scratch,0x341->s.mepc,0x342->s.cause,0x343->0.U(32.W),0x344->(irq.asUInt<<11),
      0xb00->s.cycle(31,0),0xb80->s.cycle(63,32),0xb02->s.retired(31,0),0xb82->s.retired(63,32)) ++
      (0xf11 to 0xf14).map(_->0.U(32.W))
    (values.map(x=>address===x._1.U).reduce(_||_),MuxLookup(address,0.U(32.W))(values.map {case(a,v)=>a.U->v}))
  }
  def write(n: LiteMachineState,s: LiteMachineState,address: UInt,value: UInt): Unit={
    switch(address) {
      is(0x300.U) {n.mie:=value(3);n.mpie:=value(7)}
      is(0x304.U) {n.meie:=value(11)}
      is(0x305.U) {n.mtvec:=Cat(value(31,2),0.U(2.W))}
      is(0x320.U) {n.inhibitCycle:=value(0);n.inhibitRetired:=value(2)}
      is(0x340.U) {n.scratch:=value}
      is(0x341.U) {n.mepc:=Cat(value(31,2),0.U(2.W))}
      is(0x342.U) {n.cause:=value}
      is(0xb00.U) {n.cycle:=Cat(s.cycle(63,32),value)}
      is(0xb80.U) {n.cycle:=Cat(value,s.cycle(31,0))}
      is(0xb02.U) {n.retired:=Cat(s.retired(63,32),value)}
      is(0xb82.U) {n.retired:=Cat(value,s.retired(31,0))}
    }
  }
  def trap(n: LiteMachineState,s: LiteMachineState,pc: UInt,cause: UInt): Unit={
    n.mepc:=Cat(pc(31,2),0.U(2.W));n.cause:=cause;n.mpie:=s.mie;n.mie:=false.B
  }
}

class LiteRvfi extends Bundle {
  val valid=Bool();val order=UInt(64.W);val insn=UInt(32.W)
  val trap=Bool();val halt=Bool();val intr=Bool();val mode=UInt(2.W);val ixl=UInt(2.W)
  val rs1_addr=UInt(5.W);val rs2_addr=UInt(5.W);val rs1_rdata=UInt(32.W);val rs2_rdata=UInt(32.W)
  val rd_addr=UInt(5.W);val rd_wdata=UInt(32.W);val pc_rdata=UInt(32.W);val pc_wdata=UInt(32.W)
  val mem_addr=UInt(32.W);val mem_rmask=UInt(4.W);val mem_wmask=UInt(4.W)
  val mem_rdata=UInt(32.W);val mem_wdata=UInt(32.W)
}
