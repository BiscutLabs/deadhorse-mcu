package deadhorse.lite_core
import chisel3._
import chisel3.util._

/** Pinned, unmodified riscv-formal instruction semantics. */
class LiteInstructionModel(name: String) extends BlackBox {
  override def desiredName=s"rvfi_insn_$name"
  val io=IO(new Bundle {
    val rvfi_valid=Input(Bool());val rvfi_insn=Input(UInt(32.W));val rvfi_pc_rdata=Input(UInt(32.W))
    val rvfi_rs1_rdata=Input(UInt(32.W));val rvfi_rs2_rdata=Input(UInt(32.W));val rvfi_mem_rdata=Input(UInt(32.W))
    val spec_valid=Output(Bool());val spec_trap=Output(Bool())
    val spec_rs1_addr=Output(UInt(5.W));val spec_rs2_addr=Output(UInt(5.W));val spec_rd_addr=Output(UInt(5.W))
    val spec_rd_wdata=Output(UInt(32.W));val spec_pc_wdata=Output(UInt(32.W));val spec_mem_addr=Output(UInt(32.W))
    val spec_mem_rmask=Output(UInt(4.W));val spec_mem_wmask=Output(UInt(4.W));val spec_mem_wdata=Output(UInt(32.W))
  })
}
/** All-cycle instruction semantics, without a fixed startup window or input assumptions.
  * RVE high-register legality and memory error responses extend the RV32I model.
  * CSR/IRQ entry and register-file consistency are separate obligations.
  */
class LiteInstructionFormal(name: String,variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val start=IO(Input(Bool()));val entry=IO(Input(UInt(32.W)));val irq=IO(Input(Bool()))
  val ready=IO(Input(Bool()));val valid=IO(Input(Bool()));val data=IO(Input(UInt(32.W)));val error=IO(Input(Bool()))
  val d=Module[LiteCore](if(variant=="corrupt") new LiteCore {
    override protected def retiredPc(value: UInt): UInt=value ^ 4.U
  } else new LiteCore)
  d.clk:=clock;d.reset_n:=reset_n;d.start:=start;d.entry:=entry;d.irq:=irq
  d.request.ready:=ready;d.response.valid:=valid;d.response.bits.data:=data;d.response.bits.error:=error
  val model=Module(new LiteInstructionModel(name));val s=model.io;val r=d.rvfi
  s.rvfi_valid:=r.valid;s.rvfi_insn:=r.insn;s.rvfi_pc_rdata:=r.pc_rdata
  s.rvfi_rs1_rdata:=r.rs1_rdata;s.rvfi_rs2_rdata:=r.rs2_rdata;s.rvfi_mem_rdata:=r.mem_rdata
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val accessError=RegNext(d.response.fire && error,false.B)
    val expectedTrap=s.spec_trap || s.spec_rs1_addr(4) || s.spec_rs2_addr(4) || s.spec_rd_addr(4) || accessError
    if(variant=="cover") {
      cover(s.spec_valid && !expectedTrap && !r.trap)
      cover(s.spec_valid && expectedTrap && r.trap)
    } else {
      when(s.spec_valid) {
        assert(r.trap===expectedTrap)
        when(!expectedTrap) {
          assert(r.rs1_addr===s.spec_rs1_addr);assert(r.rs2_addr===s.spec_rs2_addr)
          assert(r.rd_addr===s.spec_rd_addr);assert(r.rd_wdata===s.spec_rd_wdata)
          assert(r.pc_wdata===s.spec_pc_wdata)
          when((s.spec_mem_rmask|s.spec_mem_wmask).orR) {assert(r.mem_addr===s.spec_mem_addr)}
          assert(r.mem_rmask===s.spec_mem_rmask);assert(r.mem_wmask===s.spec_mem_wmask)
          for(lane<-0 until 4) when(s.spec_mem_wmask(lane)) {
            assert(r.mem_wdata(8*lane+7,8*lane)===s.spec_mem_wdata(8*lane+7,8*lane))
          }
        }.otherwise {assert(r.rd_addr===0.U && r.rd_wdata===0.U)}
      }
    }
  }
}
object EmitLiteInstruction extends App {
  require(args.length==2)
  for(v<-Seq("correct","corrupt","cover"))
    _root_.circt.stage.ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new LiteInstructionFormal(args(0),v)),
      Array("--target-dir",s"${args(1)}/$v"),Array("--disable-all-randomization","--disable-opt",
        "--lint-static-asserts=false","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
