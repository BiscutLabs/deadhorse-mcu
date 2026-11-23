// SPDX-License-Identifier: Apache-2.0
// Adopted ClockedCore sequencing/ISA state; extended machine control is Deadhorse work.
package deadhorse.lite_core
import chisel3._
import chisel3.util._

/** One instruction in flight; registered memory boundary and precise machine traps. */
class LiteDebugPort extends Bundle {
  val request=Input(Bool());val allowEntry=Input(Bool());val stop=Input(Bool())
  val mode=Output(Bool());val stopped=Output(Bool())
}
class LiteCore(withDebug: Boolean=false,debugBase: BigInt=0x10000) extends RawModule {
  val debug=if(withDebug) Some(IO(new LiteDebugPort)) else None
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val start=IO(Input(Bool()));val entry=IO(Input(UInt(32.W)));val irq=IO(Input(Bool()))
  val request=IO(Decoupled(new MemoryRequest));val response=IO(Flipped(Decoupled(new MemoryResponse)))
  val halted=IO(Output(Bool()));val sleeping=IO(Output(Bool()));val clockHold=IO(Output(Bool()))
  val trace=IO(Output(new Retirement));val rvfi=IO(Output(new LiteRvfi));val interruptTaken=IO(Output(Bool()))
  protected def writeback(value: UInt): UInt=value
  protected def requestAddress(value: UInt): UInt=value
  protected def retiredPc(value: UInt): UInt=value
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val running=RegInit(false.B);val asleep=RegInit(false.B)
    val boundary :: offer :: waiting :: Nil=Enum(3);val phase=RegInit(boundary)
    val pc=RegInit(0.U(32.W));val operation=RegInit(Operation.Fetch.U(2.W))
    val instruction=RegInit(0.U(32.W));val address=RegInit(0.U(32.W))
    val storeData=RegInit(0.U(32.W));val mask=RegInit(0.U(4.W))
    val registers=RegInit(VecInit(Seq.fill(15)(0.U(32.W))))
    val csr=RegInit(0.U.asTypeOf(new LiteMachineState));val nextCsr=WireDefault(csr)
    when(!csr.inhibitCycle) {nextCsr.cycle:=csr.cycle+1.U}
    val debugMode=RegInit(false.B);val debugPc=RegInit(0.U(32.W))
    val debugScratch=RegInit(VecInit(Seq.fill(2)(0.U(32.W))))
    val debugCause=RegInit(0.U(3.W));val ebreakMachine=RegInit(false.B)
    val haltRequest=debug.map(d=>d.request && d.allowEntry).getOrElse(false.B)
    val stopRequest=debug.map(_.stop).getOrElse(false.B)
    val preciseBoundary=phase===boundary && operation===Operation.Fetch.U
    debug.foreach {d=>d.mode:=debugMode;d.stopped:=preciseBoundary && stopRequest}
    val pendingInterrupt=irq && csr.meie && !debugMode
    val requestValid=RegInit(false.B);val requestBits=RegInit(0.U.asTypeOf(new MemoryRequest))
    val responseReady=RegInit(false.B)
    request.valid:=requestValid;request.bits:=requestBits;response.ready:=responseReady
    request.bits.address:=requestAddress(requestBits.address)
    val retired=RegInit(0.U.asTypeOf(new Retirement));retired.valid:=false.B;trace:=retired
    val report=RegInit(0.U.asTypeOf(new LiteRvfi));report.valid:=false.B;rvfi:=report
    val order=RegInit(0.U(64.W));val firstAfterInterrupt=RegInit(false.B)
    val irqEvent=RegInit(false.B);irqEvent:=false.B;interruptTaken:=irqEvent
    val notStarted=RegInit(true.B);halted:=notStarted;sleeping:=asleep
    clockHold:=RegNext(running && (!asleep || pendingInterrupt),false.B)
    def read(index: UInt): UInt=MuxLookup(index,0.U(32.W))((1 to 15).map(i=>i.U->registers(i-1)))
    val state=Wire(new CoreState)
    state.pc:=pc;state.operation:=operation;state.instruction:=instruction;state.address:=address
    state.storeData:=storeData;state.mask:=mask;state.writeback:=0.U.asTypeOf(new RegisterWrite)
    val insn=response.bits.data;val opcode=insn(6,0);val f3=insn(14,12);val rd=insn(11,7);val rs1=insn(19,15)
    val rs2=insn(24,20);val a=read(rs1);val b=read(rs2)
    val result=Execute.step(state,response.bits,a,b)
    val n=WireDefault(result.state);val t=WireDefault(result.trace)
    val csrInstruction=opcode==="h73".U && f3=/=0.U && f3=/=4.U
    val csrAddress=insn(31,20);val(machineCsrExists,machineCsrValue)=LiteMachine.read(csr,csrAddress,irq)
    val debugCsrs=Seq(0x7b0.U->("h40000003".U | (debugCause.asUInt<<6) | (ebreakMachine.asUInt<<15)),
      0x7b1.U->debugPc,0x7b2.U->debugScratch(0),0x7b3.U->debugScratch(1))
    val isDebugCsr=debugMode && debugCsrs.map(x=>csrAddress===x._1).reduce(_||_)
    val csrExists=machineCsrExists || isDebugCsr
    val csrValue=Mux(isDebugCsr,MuxLookup(csrAddress,0.U(32.W))(debugCsrs),machineCsrValue)
    val csrOperand=Mux(f3(2),Cat(0.U(27.W),rs1),a)
    val csrWrites=f3(1,0)===1.U || rs1=/=0.U
    val csrIllegal= !csrExists || rd(4) || (!f3(2) && rs1(4)) || (csrWrites && csrAddress(11,10)===3.U)
    val csrNewValue=MuxLookup(f3(1,0),csrOperand)(Seq(2.U->(csrValue|csrOperand),3.U->(csrValue & ~csrOperand)))
    val isMret=insn==="h30200073".U;val isWfi=insn==="h10500073".U
    val isDret=debugMode && insn==="h7b200073".U
    val isDebugEbreak=insn==="h00100073".U && (debugMode || ebreakMachine)
    val special=operation===Operation.Fetch.U && !response.bits.error
    val acceptedCsr=special && csrInstruction && !csrIllegal
    when(acceptedCsr || special && (isMret || isWfi || isDret || isDebugEbreak)) {
      t:=0.U.asTypeOf(new Retirement);t.valid:=true.B;t.pc:=pc;t.instruction:=insn
      n.operation:=Operation.Fetch.U;n.pc:=Mux(isDret,debugPc,Mux(isDebugEbreak,(debugBase+0x800).U,Mux(isMret,csr.mepc,pc+4.U)))
      n.writeback:=0.U.asTypeOf(new RegisterWrite)
      when(acceptedCsr && rd=/=0.U) {
        n.writeback.enable:=true.B;n.writeback.rd:=rd(3,0);n.writeback.data:=csrValue
        t.writeRegister:=true.B;t.rd:=rd(3,0);t.data:=csrValue
      }
    }
    // Register-source metadata survives the intervening data transaction.
    val source1=RegInit(0.U(5.W));val source2=RegInit(0.U(5.W))
    val value1=RegInit(0.U(32.W));val value2=RegInit(0.U(32.W))
    val usesA=Seq(0x67,0x63,0x13,0x33,0x03,0x23).map(x=>opcode===x.U).reduce(_||_) || csrInstruction && !f3(2)
    val usesB=Seq(0x63,0x33,0x23).map(x=>opcode===x.U).reduce(_||_)
    val currentA=Mux(usesA,rs1,0.U);val currentB=Mux(usesB,rs2,0.U)
    when(start && !running && !haltRequest && !stopRequest && !entry(1,0).orR) {
      pc:=entry;running:=true.B;notStarted:=false.B;asleep:=false.B
    }
    when(haltRequest && !debugMode && preciseBoundary && !stopRequest) {
      debugPc:=Mux(running,pc,entry);debugCause:=3.U;debugMode:=true.B
      pc:=(debugBase+0x800).U;running:=true.B;asleep:=false.B
    }
    when(running && phase===boundary && !(preciseBoundary && (stopRequest || haltRequest && !debugMode))) {
      when(operation===Operation.Fetch.U && pendingInterrupt) {asleep:=false.B}
      when(operation===Operation.Fetch.U && pendingInterrupt && csr.mie) {
        LiteMachine.trap(nextCsr,csr,pc,"h8000000b".U)
        pc:=csr.mtvec;asleep:=false.B;irqEvent:=true.B;firstAfterInterrupt:=true.B
      }.elsewhen(!asleep || pendingInterrupt) {
        requestBits:=Execute.request(state);requestValid:=true.B;phase:=offer
      }
    }
    when(request.fire) {requestValid:=false.B;responseReady:=true.B;phase:=waiting}
    when(response.fire) {
      responseReady:=false.B;phase:=boundary
      pc:=retiredPc(n.pc);operation:=n.operation;instruction:=n.instruction
      address:=n.address;storeData:=n.storeData;mask:=n.mask
      when(operation===Operation.Fetch.U) {
        source1:=currentA;source2:=currentB;value1:=Mux(usesA,a,0.U);value2:=Mux(usesB,b,0.U)
      }
      for(i<-1 to 15) when(n.writeback.enable && n.writeback.rd===i.U && !t.trap) {
        registers(i-1):=writeback(n.writeback.data)
      }
      when(t.valid) {
        retired:=t
        when(!t.trap && !csr.inhibitRetired) {nextCsr.retired:=csr.retired+1.U}
        report:=0.U.asTypeOf(new LiteRvfi);report.valid:=true.B;report.order:=order;order:=order+1.U
        report.insn:=t.instruction;report.trap:=t.trap;report.intr:=firstAfterInterrupt
        firstAfterInterrupt:=false.B;report.mode:=3.U;report.ixl:=1.U
        report.pc_rdata:=pc;report.pc_wdata:=Mux(t.trap,csr.mtvec,retiredPc(n.pc))
        report.rd_addr:=Mux(t.writeRegister,t.rd,0.U);report.rd_wdata:=Mux(t.writeRegister,writeback(t.data),0.U)
        report.rs1_addr:=Mux(operation===Operation.Fetch.U,currentA,source1)
        report.rs2_addr:=Mux(operation===Operation.Fetch.U,currentB,source2)
        report.rs1_rdata:=Mux(operation===Operation.Fetch.U,Mux(usesA,a,0.U),value1)
        report.rs2_rdata:=Mux(operation===Operation.Fetch.U,Mux(usesB,b,0.U),value2)
        when(operation===Operation.Read.U || operation===Operation.Write.U) {
          report.mem_addr:=Cat(address(31,2),0.U(2.W));report.mem_rmask:=Mux(operation===Operation.Read.U,mask,0.U)
          report.mem_wmask:=Mux(operation===Operation.Write.U,mask,0.U)
          report.mem_rdata:=response.bits.data;report.mem_wdata:=storeData
        }
      }
      when(t.trap) {
        when(debugMode) {pc:=(debugBase+0x810).U}.otherwise {
          LiteMachine.trap(nextCsr,csr,pc,t.cause);pc:=csr.mtvec
        }
        operation:=Operation.Fetch.U;asleep:=false.B
      }.otherwise {
        when(acceptedCsr && csrWrites) {
          when(isDebugCsr) {
            switch(csrAddress) {
              is(0x7b0.U) {ebreakMachine:=csrNewValue(15)}
              is(0x7b1.U) {debugPc:=Cat(csrNewValue(31,2),0.U(2.W))}
              is(0x7b2.U) {debugScratch(0):=csrNewValue}
              is(0x7b3.U) {debugScratch(1):=csrNewValue}
            }
          }.otherwise {LiteMachine.write(nextCsr,csr,csrAddress,csrNewValue)}
        }
        when(special && isDret) {debugMode:=false.B}
        when(special && isDebugEbreak && !debugMode) {debugPc:=pc;debugCause:=1.U;debugMode:=true.B}
        when(special && isMret) {nextCsr.mie:=csr.mpie;nextCsr.mpie:=true.B}
        when(special && isWfi && !debugMode) {asleep:= !pendingInterrupt}
      }
    }
    if(withDebug) {
      when(response.fire && debugMode) {retired.valid:=false.B;report.valid:=false.B;order:=order}
      assert(!debugMode || running)
      assert(!debug.map(_.stopped).get || !requestValid && !responseReady)
    }
    csr:=nextCsr
  }
}
