package deadhorse.perf_core

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException
import scala.collection.mutable

/** A byte-memory and architectural interpreter independent of the pipeline. */
class CoreSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t11/simulation").toAbsolutePath
  }
  private val mask=BigInt("ffffffff",16)
  private def runProgram(d: IbexCore, corrupt: Boolean): Unit = {
    def addi(rd: Int, rs: Int, imm: Int): BigInt =
      BigInt(((imm & 4095).toLong<<20)|(rs<<15)|(rd<<7)|0x13)
    def r(rd: Int, a: Int, b: Int, funct3: Int, funct7: Int=0): BigInt =
      BigInt((funct7.toLong<<25)|(b<<20)|(a<<15)|(funct3<<12)|(rd<<7)|0x33)
    // Integer arithmetic, all multiply high signedness variants, DIV/REM,
    // division by zero, misaligned word store/load, taken branch and CSR R/W.
    val words=Seq(addi(1,0,37),addi(2,0,-5),r(3,1,2,0),r(4,1,2,0,1),
      r(5,4,2,4,1),r(6,4,1,6,1),r(7,2,1,1,1),r(8,2,1,2,1),r(9,2,1,3,1),
      r(10,1,0,5,1),r(11,2,0,7,1),addi(12,0,0x301),
      BigInt("00462023",16),BigInt("00062683",16), // SW x4,0(x12); LW x13,0(x12)
      BigInt("00468463",16),addi(14,0,99),addi(14,0,7), // BEQ x13,x4,+8
      BigInt("340717f3",16),BigInt("34002873",16), // CSRRW x15,mscratch,x14; CSRRS x16,mscratch,x0
      r(17,1,2,4),r(18,1,2,6),r(19,1,2,7),BigInt("00100073",16)) // EBREAK trap
    val code=mutable.Map.empty[BigInt,Int]
    for((word,index)<-words.zipWithIndex; byte<-0 until 4) code(BigInt(0x80+index*4+byte))=((word>>(8*byte))&255).toInt
    // A trap handler self-loop is fetched but the test ends at EBREAK retirement.
    for(byte<-0 until 4) code(BigInt(byte))=((BigInt(0x6f)>>(8*byte))&255).toInt
    val memory=mutable.Map.empty[BigInt,Int].withDefaultValue(0)
    val modelMemory=mutable.Map.empty[BigInt,Int].withDefaultValue(0)
    val physical=Array.fill(32)(BigInt(0)); val arch=Array.fill(32)(BigInt(0))
    var expectedPc=BigInt(0x80); var scratch=BigInt(0); var retired=0; var done=false
    def wordAt(bytes: collection.Map[BigInt,Int], addr: BigInt): BigInt =
      (0 until 4).map(i=>BigInt(bytes.getOrElse(addr+i,0))<<(8*i)).reduce(_|_)
    def signed(x: BigInt): BigInt=if(x.testBit(31)) x-(BigInt(1)<<32) else x
    def check(port: UInt,value: BigInt): Unit = assert(port.peek().litValue==value,"CORE_MODEL_MISMATCH")
    def retire(): Unit = if(d.rvfi_valid.peek().litToBoolean) {
      val instruction=wordAt(code,expectedPc)
      check(d.rvfi_pc_rdata,expectedPc); check(d.rvfi_insn,instruction)
      check(d.rvfi_order,BigInt(retired+1)); d.rvfi_halt.expect(false.B); d.rvfi_intr.expect(false.B)
      val opcode=(instruction&127).toInt; val rd=((instruction>>7)&31).toInt
      val f3=((instruction>>12)&7).toInt; val a=((instruction>>15)&31).toInt
      val b=((instruction>>20)&31).toInt; val f7=((instruction>>25)&127).toInt
      var result: Option[BigInt]=None; var next=expectedPc+4
      opcode match {
        case 0x13 => result=Some((arch(a)+signed((instruction>>20) | (if(instruction.testBit(31)) BigInt("fffff000",16) else BigInt(0))))&mask)
        case 0x33 =>
          val x=arch(a); val y=arch(b)
          val value=if(f7==1) f3 match {
            case 0 => x*y
            case 1 => (signed(x)*signed(y))>>32
            case 2 => (signed(x)*y)>>32
            case 3 => (x*y)>>32
            case 4 => if(y==0) mask else signed(x)/signed(y)
            case 5 => if(y==0) mask else x/y
            case 6 => if(y==0) x else signed(x)%signed(y)
            case 7 => if(y==0) x else x%y
          } else f3 match { case 0=>x+y; case 4=>x^y; case 6=>x|y; case 7=>x&y }
          result=Some(value&mask)
        case 0x23 =>
          val address=arch(a); for(i<-0 until 4) modelMemory(address+i)=((arch(b)>>(8*i))&255).toInt
          check(d.rvfi_mem_addr,address); check(d.rvfi_mem_wdata,arch(b)); check(d.rvfi_mem_wmask,15)
        case 0x03 => result=Some(wordAt(modelMemory,arch(a))); check(d.rvfi_mem_addr,arch(a))
        case 0x63 => if(arch(a)==arch(b)) next=expectedPc+8
        case 0x73 if f3!=0 =>
          result=Some(scratch); if(f3==1) scratch=arch(a)
        case 0x73 => d.rvfi_trap.expect(true.B); done=true
        case other=>fail(s"unsupported test instruction $other")
      }
      if(!done) d.rvfi_trap.expect(false.B)
      result.foreach { value=>
        check(d.rvfi_rd_addr,rd)
        val observed=d.rvfi_rd_wdata.peek().litValue ^ (if(corrupt) BigInt(1) else BigInt(0))
        assert(observed==(if(rd==0) BigInt(0) else value),"CORE_MODEL_MISMATCH")
        if(rd!=0) arch(rd)=value
      }
      expectedPc=next; retired+=1
    }
    d.hart_id_i.poke(0.U); d.boot_addr_i.poke(0.U); d.fetch_enable_i.poke(5.U)
    d.instr_gnt_i.poke(false.B); d.instr_rvalid_i.poke(false.B); d.instr_rdata_i.poke(0.U); d.instr_err_i.poke(false.B)
    d.data_gnt_i.poke(false.B); d.data_rvalid_i.poke(false.B); d.data_rdata_i.poke(0.U); d.data_err_i.poke(false.B)
    d.rf_rdata_a_ecc_i.poke(0.U); d.rf_rdata_b_ecc_i.poke(0.U)
    d.ic_tag_rdata_i.poke(0.U); d.ic_data_rdata_i.poke(0.U); d.ic_scr_key_valid_i.poke(false.B)
    d.irq_software_i.poke(false.B); d.irq_timer_i.poke(false.B); d.irq_external_i.poke(false.B)
    d.irq_fast_i.poke(0.U); d.irq_nm_i.poke(false.B); d.debug_req_i.poke(false.B)
    d.rst_ni.poke(false.B); d.clk_i.step(2); d.rst_ni.poke(true.B)
    val instructions=mutable.Queue.empty[(Int,BigInt)]
    val data=mutable.Queue.empty[(Int,BigInt)]
    var ticks=0
    while(!done && ticks<1500) {
      d.instr_gnt_i.poke((ticks%4!=1).B); d.data_gnt_i.poke((ticks%3!=1).B)
      val instructionResponse=instructions.headOption.filter(_._1<=ticks)
      d.instr_rvalid_i.poke(instructionResponse.nonEmpty.B)
      d.instr_rdata_i.poke(instructionResponse.map(p=>wordAt(code,p._2)).getOrElse(BigInt(0)).U)
      val dataResponse=data.headOption.filter(_._1<=ticks)
      d.data_rvalid_i.poke(dataResponse.nonEmpty.B); d.data_rdata_i.poke(dataResponse.map(_._2).getOrElse(BigInt(0)).U)
      d.rf_rdata_a_ecc_i.poke(physical(d.rf_raddr_a_o.peek().litValue.toInt).U)
      d.rf_rdata_b_ecc_i.poke(physical(d.rf_raddr_b_o.peek().litValue.toInt).U)
      if(instructionResponse.nonEmpty) instructions.dequeue()
      if(dataResponse.nonEmpty) data.dequeue()
      if(d.instr_req_o.peek().litToBoolean && ticks%4!=1)
        instructions.enqueue((ticks+1+ticks%3,d.instr_addr_o.peek().litValue))
      if(d.data_req_o.peek().litToBoolean && ticks%3!=1) {
        val address=d.data_addr_o.peek().litValue
        if(d.data_we_o.peek().litToBoolean) {
          val value=d.data_wdata_o.peek().litValue; val enables=d.data_be_o.peek().litValue
          for(i<-0 until 4 if enables.testBit(i)) memory(address+i)=((value>>(8*i))&255).toInt
        }
        data.enqueue((ticks+2+ticks%3,wordAt(memory,address)))
      }
      if(d.rf_we_wb_o.peek().litToBoolean) {
        val address=d.rf_waddr_wb_o.peek().litValue.toInt
        if(address!=0) physical(address)=d.rf_wdata_wb_ecc_o.peek().litValue
      }
      d.clk_i.step(); retire(); ticks+=1
    }
    assert(done,"CORE_PROGRAM_TIMEOUT")
    assert(retired==words.size-1,"taken branch must skip exactly one instruction")
    assert(arch(5)==37 && arch(13)==((BigInt(-185))&mask) && arch(14)==7 && arch(16)==7)
    d.alert_minor_o.expect(false.B); d.alert_major_internal_o.expect(false.B); d.alert_major_bus_o.expect(false.B)
  }
  test("faithful core retires against an architectural model through delayed memory") {
    simulateRaw(new IbexCore) { d=>runProgram(d,false) }
  }
  test("core architectural checker rejects a corrupted retirement value") {
    val error=intercept[TestFailedException] { simulateRaw(new IbexCore) { d=>runProgram(d,true) } }
    assert(error.getMessage.contains("CORE_MODEL_MISMATCH"))
  }
  test("registered execution core retires against the same architectural model") {
    simulateRaw(new IbexCore(RegisteredExecution=true)) { d=>runProgram(d,false) }
  }
}
