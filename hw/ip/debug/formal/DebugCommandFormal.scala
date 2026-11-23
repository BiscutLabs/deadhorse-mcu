package deadhorse.debug
import chisel3._
import chisel3.util._
import java.nio.file.Paths

/** Actual adopted command controller, at the production two-hart parameters.
  * Inputs are arbitrary: the safety claims do not trust hart-written status. */
class DebugCommandMemory extends BlackBox(Map("NrHarts"->2,"BusWidth"->32,
    "DmBaseAddress"->0x10000,"MaxRegisterAccessWidth"->32,"HartResetExtension"->1)) with HasBlackBoxPath {
  override def desiredName="dm_mem"
  val io=IO(new Bundle {
    val clk_i=Input(Clock());val rst_ni=Input(Bool());val dmactive_i=Input(Bool())
    val hart_reset_i=Input(UInt(2.W));val ndmreset_i=Input(Bool());val hartsel_i=Input(UInt(20.W))
    val haltreq_i=Input(UInt(2.W));val resumereq_i=Input(UInt(2.W));val clear_resumeack_i=Input(UInt(2.W))
    val progbuf_i=Input(UInt(256.W));val data_i=Input(UInt(64.W));val data_o=Output(UInt(64.W))
    val data_valid_o=Output(Bool());val cmd_valid_i=Input(Bool());val cmd_i=Input(UInt(32.W))
    val cmderror_valid_o=Output(Bool());val cmderror_o=Output(UInt(3.W));val cmdbusy_o=Output(Bool())
    val command_hart_o=Output(UInt(20.W));val command_busy_o=Output(Bool())
    val debug_req_o=Output(UInt(2.W));val halted_o=Output(UInt(2.W));val resuming_o=Output(UInt(2.W))
    val req_i=Input(Bool());val we_i=Input(Bool());val addr_i=Input(UInt(32.W))
    val wdata_i=Input(UInt(32.W));val be_i=Input(UInt(4.W));val rdata_o=Output(UInt(32.W))
  })
  for(file<-Seq("src/dm_pkg.sv","debug_rom/debug_rom.sv","debug_rom/debug_rom_one_scratch.sv","src/dm_mem.sv"))
    addPath(Paths.get("build/vendor/riscv_dbg/riscv-dbg",file).toAbsolutePath.toString)
}
class DebugCommandFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val active=IO(Input(Bool()));val ndmReset=IO(Input(Bool()));val hartReset=IO(Input(UInt(2.W)))
  val selected=IO(Input(Bool()));val halt=IO(Input(UInt(2.W)));val resume=IO(Input(UInt(2.W)))
  val clear=IO(Input(UInt(2.W)));val command=IO(Input(UInt(32.W)));val valid=IO(Input(Bool()))
  val req=IO(Input(Bool()));val write=IO(Input(Bool()));val address=IO(Input(UInt(32.W)))
  val data=IO(Input(UInt(32.W)));val mask=IO(Input(UInt(4.W)))
  val progbuf=IO(Input(UInt(256.W)));val registers=IO(Input(UInt(64.W)))
  val d=Module(new DebugCommandMemory)
  d.io.clk_i:=clock;d.io.rst_ni:=reset_n;d.io.dmactive_i:=active;d.io.ndmreset_i:=ndmReset
  d.io.hart_reset_i:=(if(variant=="lost_reset") 0.U else if(variant=="cross_reset") Fill(2,hartReset.orR) else hartReset)
  d.io.hartsel_i:=(if(variant=="wrong_hart") Mux(hartReset.orR,selected,!selected) else selected).asUInt
  d.io.haltreq_i:=halt;d.io.resumereq_i:=resume;d.io.clear_resumeack_i:=clear
  d.io.cmd_valid_i:=valid;d.io.cmd_i:=command;d.io.req_i:=req;d.io.we_i:=write
  d.io.addr_i:=address;d.io.wdata_i:=data;d.io.be_i:=mask;d.io.progbuf_i:=progbuf;d.io.data_i:=registers
  val busy=d.io.command_busy_o;val owner=d.io.command_hart_o
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val wasBusy=RegNext(busy,false.B);val wasOwner=RegNext(owner,0.U)
    val wasSelected=RegNext(selected,false.B);val wasReset=RegNext(hartReset,0.U)
    val cancels=Mux(busy,hartReset(owner(0)),valid && hartReset(selected))
    val wasCancel=RegNext(cancels || ndmReset,false.B)
    val completion=req && write && address(11,0)===0x100.U && data===owner
    val mustRemain=RegNext(busy && !hartReset(owner(0)) && !ndmReset && !completion,false.B)
    if(variant=="cover") {
      cover(busy && owner===0.U)
      cover(busy && owner===1.U)
      cover(busy && owner=/=selected.asUInt)
      cover(busy && cancels && req && write && address(11,0)===0x100.U && data===owner)
      cover(!busy && valid && hartReset(selected))
      cover(busy && !hartReset(owner(0)) && hartReset.orR)
    } else {
      assert(!busy || wasBusy || owner===wasSelected.asUInt,"DBG_COMMAND_SELECTED")
      assert(!wasBusy || owner===wasOwner,"DBG_COMMAND_HELD")
      assert(!wasCancel || !busy,"DBG_COMMAND_CANCELLED")
      assert(!cancels || d.io.cmderror_valid_o && d.io.cmderror_o===4.U,"DBG_COMMAND_RESET_PRIORITY")
      assert((d.io.halted_o & wasReset)===0.U,"DBG_HALT_RESET")
      assert((d.io.resuming_o & wasReset)===0.U,"DBG_RESUME_RESET")
      assert(!mustRemain || busy,"DBG_OTHER_HART_RESET_SURVIVES")
    }
  }
}
object EmitDebugCommandFormal extends App {
  for(v<-Seq("correct","wrong_hart","lost_reset","cross_reset","cover")) _root_.circt.stage.ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new DebugCommandFormal(v)),Array("--target-dir",s"${args(0)}/$v"),
    Array("--disable-all-randomization","--disable-opt","--lint-static-asserts=false","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
