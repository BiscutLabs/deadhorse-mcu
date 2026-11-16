// Copyright lowRISC contributors; ETH Zurich and University of Bologna.
// Licensed under Apache-2.0. SPDX-License-Identifier: Apache-2.0
// Translation of rtl/ibex_cs_registers.sv, Ibex
// 38c070939183cc10940b66c8e9e04eeca6b65470, pinned T10 configuration.
package deadhorse.perf_core

import chisel3._
import chisel3.util._
import chisel3.util.experimental.InlineInstance

class IbexCsRegisters(val DbgTriggerEn: Boolean = true, val DbgHwBreakNum: Int = 1,
    val DataIndTiming: Boolean = false, val DummyInstructions: Boolean = false,
    val ShadowCSR: Boolean = false, val ICache: Boolean = false,
    val MHPMCounterNum: Int = 0, val MHPMCounterWidth: Int = 40,
    val PMPEnable: Boolean = false, val PMPGranularity: Int = 0, val PMPNumRegions: Int = 4,
    val RV32E: Boolean = false, val RV32M: Int = 2, val RV32B: Int = 0) extends RawModule {
  require(DbgTriggerEn && DbgHwBreakNum == 1 && !DataIndTiming && !DummyInstructions &&
    !ShadowCSR && !ICache && MHPMCounterNum == 0 && MHPMCounterWidth == 40 &&
    !PMPEnable && PMPGranularity == 0 && PMPNumRegions == 4 && !RV32E && RV32M == 2 && RV32B == 0,
    "T11 implements the pinned CSR configuration")
  override def desiredName = "ibex_cs_registers"
  val clk_i=IO(Input(Clock())); val rst_ni=IO(Input(Bool()))
  val hart_id_i=IO(Input(UInt(32.W)))
  val priv_mode_id_o=IO(Output(UInt(2.W))); val priv_mode_lsu_o=IO(Output(UInt(2.W)))
  val csr_mstatus_tw_o=IO(Output(Bool())); val csr_mtvec_o=IO(Output(UInt(32.W)))
  val csr_mtvec_init_i=IO(Input(Bool())); val boot_addr_i=IO(Input(UInt(32.W)))
  val csr_access_i=IO(Input(Bool())); val csr_addr_i=IO(Input(UInt(12.W)))
  val csr_wdata_i=IO(Input(UInt(32.W))); val csr_op_i=IO(Input(UInt(2.W)))
  val csr_op_en_i=IO(Input(Bool())); val csr_rdata_o=IO(Output(UInt(32.W)))
  val irq_software_i=IO(Input(Bool())); val irq_timer_i=IO(Input(Bool()))
  val irq_external_i=IO(Input(Bool())); val irq_fast_i=IO(Input(UInt(15.W)))
  val nmi_mode_i=IO(Input(Bool())); val irq_pending_o=IO(Output(Bool()))
  val irqs_o=IO(Output(UInt(18.W))); val csr_mstatus_mie_o=IO(Output(Bool()))
  val csr_mepc_o=IO(Output(UInt(32.W))); val csr_mtval_o=IO(Output(UInt(32.W)))
  // Ascending unpacked arrays flatten with region zero in the high word.
  // All regions are tied off in the selected non-PMP configuration.
  val csr_pmp_cfg_o=IO(Output(UInt((6*PMPNumRegions).W)))
  val csr_pmp_addr_o=IO(Output(UInt((34*PMPNumRegions).W)))
  val csr_pmp_mseccfg_o=IO(Output(UInt(3.W)))
  val debug_mode_i=IO(Input(Bool())); val debug_mode_entering_i=IO(Input(Bool()))
  val debug_cause_i=IO(Input(UInt(3.W))); val debug_csr_save_i=IO(Input(Bool()))
  val csr_depc_o=IO(Output(UInt(32.W))); val debug_single_step_o=IO(Output(Bool()))
  val debug_ebreakm_o=IO(Output(Bool())); val debug_ebreaku_o=IO(Output(Bool()))
  val trigger_match_o=IO(Output(Bool()))
  val pc_if_i=IO(Input(UInt(32.W))); val pc_id_i=IO(Input(UInt(32.W))); val pc_wb_i=IO(Input(UInt(32.W)))
  val data_ind_timing_o=IO(Output(Bool())); val dummy_instr_en_o=IO(Output(Bool()))
  val dummy_instr_mask_o=IO(Output(UInt(3.W))); val dummy_instr_seed_en_o=IO(Output(Bool()))
  val dummy_instr_seed_o=IO(Output(UInt(32.W))); val icache_enable_o=IO(Output(Bool()))
  val csr_shadow_err_o=IO(Output(Bool())); val ic_scr_key_valid_i=IO(Input(Bool()))
  val csr_save_if_i=IO(Input(Bool())); val csr_save_id_i=IO(Input(Bool())); val csr_save_wb_i=IO(Input(Bool()))
  val csr_restore_mret_i=IO(Input(Bool())); val csr_restore_dret_i=IO(Input(Bool()))
  val csr_save_cause_i=IO(Input(Bool())); val csr_mcause_i=IO(Input(UInt(7.W)))
  val csr_mtval_i=IO(Input(UInt(32.W))); val illegal_csr_insn_o=IO(Output(Bool()))
  val double_fault_seen_o=IO(Output(Bool()))
  val instr_ret_i=IO(Input(Bool())); val instr_ret_compressed_i=IO(Input(Bool()))
  val instr_ret_spec_i=IO(Input(Bool())); val instr_ret_compressed_spec_i=IO(Input(Bool()))
  val iside_wait_i=IO(Input(Bool())); val jump_i=IO(Input(Bool())); val branch_i=IO(Input(Bool()))
  val branch_taken_i=IO(Input(Bool())); val mem_load_i=IO(Input(Bool())); val mem_store_i=IO(Input(Bool()))
  val dside_wait_i=IO(Input(Bool())); val mul_wait_i=IO(Input(Bool())); val div_wait_i=IO(Input(Bool()))

  // Reuse the proved CSR/counter leaves. Inlining is emission-only; the name
  // map retains each reference instance's state identity in the parent proof.
  private def csr(name: String, width: Int, reset: BigInt = 0): IbexCsr = {
    val instance=Module(new IbexCsr(width,false,reset) with InlineInstance).suggestName(name)
    instance.clk_i:=clk_i; instance.rst_ni:=rst_ni
    instance.wr_en_i:=false.B; instance.wr_data_i:=instance.rd_data_o
    instance
  }
  val u_mstatus_csr=csr("u_mstatus_csr",6,16)
  val u_mie_csr=csr("u_mie_csr",18)
  val u_mscratch_csr=csr("u_mscratch_csr",32)
  val u_mepc_csr=csr("u_mepc_csr",32)
  val u_mcause_csr=csr("u_mcause_csr",7)
  val u_mtval_csr=csr("u_mtval_csr",32)
  val u_mtvec_csr=csr("u_mtvec_csr",32,1)
  val u_dcsr_csr=csr("u_dcsr_csr",32,BigInt("40000003",16))
  val u_depc_csr=csr("u_depc_csr",32)
  val u_dscratch0_csr=csr("u_dscratch0_csr",32)
  val u_dscratch1_csr=csr("u_dscratch1_csr",32)
  val u_mstack_csr=csr("u_mstack_csr",3,4)
  val u_mstack_epc_csr=csr("u_mstack_epc_csr",32)
  val u_mstack_cause_csr=csr("u_mstack_cause_csr",7)
  val u_cpuctrlsts_part_csr=csr("u_cpuctrlsts_part_csr",8)
  val tselect=csr("gen_trigger_regs_u_tselect_csr",1)
  val tcontrol=csr("gen_trigger_regs_g_dbg_tmatch_reg_0_u_tmatch_control_csr",1)
  val tvalue=csr("gen_trigger_regs_g_dbg_tmatch_reg_0_u_tmatch_value_csr",32)
  val mstatus_q=u_mstatus_csr.rd_data_o
  val mie_q=u_mie_csr.rd_data_o
  val mepc_q=u_mepc_csr.rd_data_o
  val mcause_q=u_mcause_csr.rd_data_o
  val dcsr_q=u_dcsr_csr.rd_data_o
  val mstack_q=u_mstack_csr.rd_data_o
  val cpuctrlsts_part_q=u_cpuctrlsts_part_csr.rd_data_o
  val mcycle_counter_i=Module(new IbexCounter(64,false) with InlineInstance)
  val minstret_counter_i=Module(new IbexCounter(64,true) with InlineInstance)
  val csr_wdata_int=Wire(UInt(32.W)); val csr_we_int=Wire(Bool())
  val cpuctrlsts_part_d=WireDefault(VecInit(cpuctrlsts_part_q.asBools))
  val mstatus_d=WireDefault(VecInit(mstatus_q.asBools))
  val dcsr_d=WireDefault(VecInit(dcsr_q.asBools))
  def bits(value: Seq[Bool]): UInt = VecInit(value).asUInt
  def field(target: Seq[Bool], low: Int, value: UInt): Unit =
    (0 until value.getWidth).foreach(i => target(low+i):=value(i))
  def write(instance: IbexCsr, value: UInt): Unit = {
    instance.wr_en_i:=true.B; instance.wr_data_i:=value
  }
  withClockAndReset(clk_i,(!rst_ni).asAsyncReset) {
    val priv_lvl_q=RegInit(3.U(2.W))
    val mcountinhibit_q=RegInit(0.U(3.W))
    val mip=Cat(irq_software_i,irq_timer_i,irq_external_i,irq_fast_i)
    def irqWord(value: UInt): UInt = Cat(0.U(1.W),value(14,0),0.U(4.W),value(15),
      0.U(3.W),value(16),0.U(3.W),value(17),0.U(3.W))
    val counterLow=csr_addr_i(11,5)==="h58".U && csr_addr_i(4,0)=/=1.U
    val counterHigh=csr_addr_i(11,5)==="h5c".U && csr_addr_i(4,0)=/=1.U
    val minstret=Mux(instr_ret_spec_i && !mcountinhibit_q(2),
      minstret_counter_i.counter_val_upd_o,minstret_counter_i.counter_val_o)
    for ((counter,index) <- Seq((mcycle_counter_i,0),(minstret_counter_i,2))) {
      counter.clk_i:=clk_i; counter.rst_ni:=rst_ni
      counter.counter_inc_i:=(if(index==0) true.B else instr_ret_i) && !mcountinhibit_q(index)
      // These exact machine-counter addresses imply known, non-debug and
      // writable. Qualify their privilege locally instead of traversing the
      // unrelated debug/read-only recognition logic before the write strobes.
      val counterWrite=csr_op_i=/=0.U && csr_op_en_i && (!csr_access_i || priv_lvl_q===3.U)
      counter.counter_we_i:=counterWrite && csr_addr_i===(0xb00+index).U
      counter.counterh_we_i:=counterWrite && csr_addr_i===(0xb80+index).U
      // The selected counter's own read value is sufficient on its write
      // enable. Avoid routing counter RMW through every unrelated CSR mux.
      // Keep minstret's speculative increment exactly as on the read port.
      val ownValue=if(index==0) counter.counter_val_o else minstret
      val ownRead=Mux(csr_addr_i(7),ownValue(63,32),ownValue(31,0))
      counter.counter_val_i:=Mux(csr_op_i===2.U,csr_wdata_i|ownRead,
        Mux(csr_op_i===3.U,~csr_wdata_i&ownRead,csr_wdata_i))
    }
    val selectedCounter=Mux(csr_addr_i(4,0)===0.U,mcycle_counter_i.counter_val_o,
      Mux(csr_addr_i(4,0)===2.U,minstret,0.U(64.W)))
    val readData=WireDefault(0.U(32.W)); val known=WireDefault(false.B)
    val debugCsr=csr_addr_i >= "h7b0".U && csr_addr_i <= "h7b3".U
    val statusWord= (mstatus_q(5).asUInt<<3) | (mstatus_q(4).asUInt<<7) |
      (mstatus_q(3,2)<<11) | (mstatus_q(1).asUInt<<17) | (mstatus_q(0).asUInt<<21)
    val values=Seq(
      0xf11->0.U,0xf12->22.U,0xf13->0.U,0xf14->hart_id_i,0xf15->0.U,
      0x300->statusWord,0x310->0.U,0x30a->0.U,0x31a->0.U,0x301->"h40101104".U,
      0x304->irqWord(mie_q),0x306->0.U,0x340->u_mscratch_csr.rd_data_o,
      0x305->u_mtvec_csr.rd_data_o,0x341->mepc_q,
      0x342->Cat(mcause_q(5)||mcause_q(6),Fill(26,mcause_q(6)),mcause_q(4,0)),
      0x343->u_mtval_csr.rd_data_o,0x344->irqWord(mip),
      0x7b0->dcsr_q,0x7b1->u_depc_csr.rd_data_o,0x7b2->u_dscratch0_csr.rd_data_o,
      0x7b3->u_dscratch1_csr.rd_data_o,0x320->mcountinhibit_q,
      0x7a0->tselect.rd_data_o,0x7a1->("h28001048".U(32.W)|(tcontrol.rd_data_o<<2)),
      0x7a2->tvalue.rd_data_o,0x7a3->0.U,0x7a8->0.U,0x5a8->0.U,0x7aa->0.U,
      0x7c0->cpuctrlsts_part_q,0x7c1->0.U)
    // Disjoint address decode is a parallel selection, not a priority chain.
    // Keep the same values for every address, including unsupported counters.
    require(values.map(_._1).distinct.size==values.size)
    require(values.forall { case(address,_)=> !Set(0x58,0x5c).contains(address>>5) })
    val selections=values.map { case(address,value)=>(csr_addr_i===address.U,value.pad(32)) }
    readData:=Mux1H(selections++Seq(counterLow->selectedCounter(31,0),counterHigh->selectedCounter(63,32)))
    known:=selections.map(_._1).reduce(_||_) || counterLow || counterHigh
    when(csr_addr_i >= "h323".U && csr_addr_i <= "h33f".U) { known:=true.B }
    csr_rdata_o:=readData
    val csr_wr=csr_op_i=/=0.U
    illegal_csr_insn_o:=csr_access_i && (!known || (debugCsr && !debug_mode_i) ||
      csr_addr_i(9,8)>priv_lvl_q || (csr_addr_i(11,10)===3.U && csr_wr))
    // Each write destination has its own exact address/range decode below.
    // An unknown address selects no destination, so the global read-address
    // recognition tree need not be serial with every write enable. Privilege,
    // debug and read-only checks remain identical, including csr_access gating.
    csr_we_int:=csr_wr && csr_op_en_i && !(csr_access_i &&
      ((debugCsr && !debug_mode_i) || csr_addr_i(9,8)>priv_lvl_q || csr_addr_i(11,10)===3.U))
    csr_wdata_int:=Mux(csr_op_i===2.U,csr_wdata_i|readData,
      Mux(csr_op_i===3.U,~csr_wdata_i&readData,csr_wdata_i))
    u_mtvec_csr.wr_en_i:=csr_mtvec_init_i
    u_mtvec_csr.wr_data_i:=Cat(Mux(csr_mtvec_init_i,boot_addr_i(31,8),csr_wdata_int(31,8)),1.U(8.W))
    u_mstatus_csr.wr_data_i:=bits(mstatus_d)
    u_dcsr_csr.wr_data_i:=bits(dcsr_d)
    u_cpuctrlsts_part_csr.wr_data_i:=bits(cpuctrlsts_part_d)
    when(csr_we_int) {
      switch(csr_addr_i) {
        is("h300".U) {
          // At this exact address the read mux equals statusWord. Keep the
          // local RMW off the speculative minstret/read-mux path into MPP.
          val statusWrite=Mux(csr_op_i===2.U,csr_wdata_i|statusWord,
            Mux(csr_op_i===3.U,~csr_wdata_i&statusWord,csr_wdata_i))
          u_mstatus_csr.wr_en_i:=true.B
          field(mstatus_d,0,Cat(statusWrite(3),statusWrite(7),
            Mux(statusWrite(12,11)===3.U,3.U(2.W),0.U(2.W)),statusWrite(17),statusWrite(21)))
        }
        is("h304".U) { write(u_mie_csr,Cat(csr_wdata_int(3),csr_wdata_int(7),csr_wdata_int(11),csr_wdata_int(30,16))) }
        is("h340".U) { write(u_mscratch_csr,csr_wdata_int) }
        is("h341".U) { write(u_mepc_csr,Cat(csr_wdata_int(31,1),0.U(1.W))) }
        is("h342".U) { write(u_mcause_csr,Cat(csr_wdata_int(31,30)===3.U,csr_wdata_int(31,30)===2.U,csr_wdata_int(4,0))) }
        is("h343".U) { write(u_mtval_csr,csr_wdata_int) }
        is("h305".U) { u_mtvec_csr.wr_en_i:=true.B }
        is("h7b0".U) {
          u_dcsr_csr.wr_en_i:=true.B
          // Only ebreakm/s/u, step and a legal privilege value are writable;
          // the cause remains read-only and xdebugver is fixed to four.
          field(dcsr_d,0,(csr_wdata_int & "h0000b004".U) | "h40000000".U |
            (dcsr_q & "h000001c0".U) | Mux(csr_wdata_int(1,0)===3.U,3.U(32.W),0.U(32.W)))
        }
        is("h7b1".U) { write(u_depc_csr,Cat(csr_wdata_int(31,1),0.U(1.W))) }
        is("h7b2".U) { write(u_dscratch0_csr,csr_wdata_int) }
        is("h7b3".U) { write(u_dscratch1_csr,csr_wdata_int) }
        is("h320".U) { mcountinhibit_q:=Cat(csr_wdata_int(2),0.U(1.W),csr_wdata_int(0)) }
        is("h7c0".U) {
          u_cpuctrlsts_part_csr.wr_en_i:=true.B
          field(cpuctrlsts_part_d,0,Cat(csr_wdata_int(7,6),0.U(6.W)))
        }
      }
    }
    when(csr_we_int && debug_mode_i) {
      when(csr_addr_i==="h7a0".U) { write(tselect,0.U) }
      when(csr_addr_i==="h7a1".U && tselect.rd_data_o===0.U) { write(tcontrol,csr_wdata_int(2).asUInt) }
      when(csr_addr_i==="h7a2".U && tselect.rd_data_o===0.U) { write(tvalue,csr_wdata_int) }
    }
    double_fault_seen_o:=false.B
    when(csr_save_cause_i) {
      val exception_pc=Mux(csr_save_if_i,pc_if_i,Mux(csr_save_id_i,pc_id_i,Mux(csr_save_wb_i,pc_wb_i,pc_id_i)))
      priv_lvl_q:=3.U
      when(debug_csr_save_i) {
        field(dcsr_d,0,priv_lvl_q); field(dcsr_d,6,debug_cause_i)
        u_dcsr_csr.wr_en_i:=true.B; write(u_depc_csr,exception_pc)
      }.elsewhen(!debug_mode_i) {
        write(u_mtval_csr,csr_mtval_i); u_mstatus_csr.wr_en_i:=true.B
        mstatus_d(5):=false.B; mstatus_d(4):=mstatus_q(5); field(mstatus_d,2,priv_lvl_q)
        write(u_mepc_csr,exception_pc); write(u_mcause_csr,csr_mcause_i)
        write(u_mstack_csr,mstatus_q(4,2)); write(u_mstack_epc_csr,mepc_q); write(u_mstack_cause_csr,mcause_q)
        when(!csr_mcause_i(6) && !csr_mcause_i(5)) {
          u_cpuctrlsts_part_csr.wr_en_i:=true.B; cpuctrlsts_part_d(6):=true.B
          when(cpuctrlsts_part_q(6)) { double_fault_seen_o:=true.B; cpuctrlsts_part_d(7):=true.B }
        }
      }
    }.elsewhen(csr_restore_dret_i) { priv_lvl_q:=dcsr_q(1,0) }
      .elsewhen(csr_restore_mret_i) {
        priv_lvl_q:=mstatus_q(3,2); u_mstatus_csr.wr_en_i:=true.B; mstatus_d(5):=mstatus_q(4)
        when(mstatus_q(3,2)=/=3.U) { mstatus_d(1):=false.B }
        u_cpuctrlsts_part_csr.wr_en_i:=true.B; cpuctrlsts_part_d(6):=false.B
        when(nmi_mode_i) {
          mstatus_d(4):=mstack_q(2); field(mstatus_d,2,mstack_q(1,0))
          write(u_mepc_csr,u_mstack_epc_csr.rd_data_o); write(u_mcause_csr,u_mstack_cause_csr.rd_data_o)
        }.otherwise { mstatus_d(4):=true.B; field(mstatus_d,2,0.U(2.W)) }
      }
    priv_mode_id_o:=priv_lvl_q; priv_mode_lsu_o:=Mux(mstatus_q(1),mstatus_q(3,2),priv_lvl_q)
    irqs_o:=mip & mie_q
    // Bound the interrupt-pending reduction depth independently of the fast
    // IRQ priority encoder's shared prefixes after whole-core flattening.
    val pendingGroups=(0 until 18 by 3).map { low=>
      val group=WireDefault(irqs_o(low+2,low).orR)
      addAttribute(group,"keep = 1")
      group
    }
    irq_pending_o:=Cat(pendingGroups).orR
  }
  csr_mepc_o:=mepc_q; csr_depc_o:=u_depc_csr.rd_data_o; csr_mtvec_o:=u_mtvec_csr.rd_data_o
  csr_mtval_o:=u_mtval_csr.rd_data_o; csr_mstatus_mie_o:=mstatus_q(5); csr_mstatus_tw_o:=mstatus_q(0)
  debug_single_step_o:=dcsr_q(2); debug_ebreakm_o:=dcsr_q(15); debug_ebreaku_o:=dcsr_q(12)
  trigger_match_o:=tcontrol.rd_data_o.asBool && pc_if_i===tvalue.rd_data_o
  data_ind_timing_o:=cpuctrlsts_part_q(1); dummy_instr_en_o:=cpuctrlsts_part_q(2)
  dummy_instr_mask_o:=cpuctrlsts_part_q(5,3)
  icache_enable_o:=cpuctrlsts_part_q(0) && !(debug_mode_i || debug_mode_entering_i)
  dummy_instr_seed_en_o:=false.B; dummy_instr_seed_o:=0.U; csr_shadow_err_o:=false.B
  csr_pmp_cfg_o:=0.U; csr_pmp_addr_o:=0.U; csr_pmp_mseccfg_o:=0.U
}
