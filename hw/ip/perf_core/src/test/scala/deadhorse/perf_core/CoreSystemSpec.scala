package deadhorse.perf_core

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import scala.collection.mutable

/** Port-only system sequencing with a ROM and independent architectural RF. */
class CoreSystemSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t11/system-simulation").toAbsolutePath
  }
  private def addi(rd:Int,value:Int):BigInt=BigInt(((value&4095).toLong<<20)|(rd<<7)|0x13)
  private class Rig(d:IbexCore, code:Map[BigInt,BigInt], failLoads:Boolean=false,
      instructionDelay:Int=1, grantPeriod:Int=1) {
    val registers=Array.fill(32)(BigInt(0))
    val retired=mutable.ArrayBuffer.empty[(BigInt,BigInt)]
    val traps=mutable.ArrayBuffer.empty[BigInt]
    val nextPcs=mutable.ArrayBuffer.empty[BigInt]
    val accesses=mutable.ArrayBuffer.empty[(BigInt,Boolean)]
    private val pending=mutable.Queue.empty[(Int,BigInt)]
    private var heldRequest:Option[BigInt]=None
    private var dataPending:Option[Boolean]=None
    private var ticks=0
    var debug=false; var timer=false
    d.hart_id_i.poke(0.U); d.boot_addr_i.poke(0.U); d.fetch_enable_i.poke(5.U)
    d.instr_gnt_i.poke(true.B); d.instr_rvalid_i.poke(false.B); d.instr_rdata_i.poke(0.U); d.instr_err_i.poke(false.B)
    d.data_gnt_i.poke(false.B); d.data_rvalid_i.poke(false.B); d.data_rdata_i.poke(0.U); d.data_err_i.poke(false.B)
    d.rf_rdata_a_ecc_i.poke(0.U); d.rf_rdata_b_ecc_i.poke(0.U)
    d.ic_tag_rdata_i.poke(0.U); d.ic_data_rdata_i.poke(0.U); d.ic_scr_key_valid_i.poke(true.B)
    d.irq_software_i.poke(false.B); d.irq_external_i.poke(false.B); d.irq_fast_i.poke(0.U)
    d.irq_nm_i.poke(false.B); d.irq_timer_i.poke(false.B); d.debug_req_i.poke(false.B)
    def reset():Unit={
      d.rst_ni.poke(false.B); d.clk_i.step(2); d.rst_ni.poke(true.B)
      for(i<-registers.indices) registers(i)=BigInt(0)
      pending.clear(); heldRequest=None; dataPending=None
      retired.clear(); nextPcs.clear(); traps.clear(); accesses.clear()
    }
    reset()
    def step():Unit={
      d.debug_req_i.poke(debug.B); d.irq_timer_i.poke(timer.B)
      val response=if(pending.headOption.exists(_._1<=ticks)) Some(pending.dequeue()._2) else None
      val grant=ticks%grantPeriod==0
      d.instr_gnt_i.poke(grant.B)
      d.instr_rvalid_i.poke(response.nonEmpty.B)
      d.instr_rdata_i.poke(response.map(a=>code.getOrElse(a,BigInt("0000006f",16))).getOrElse(BigInt(0)).U)
      d.data_gnt_i.poke(failLoads.B); d.data_rvalid_i.poke(dataPending.nonEmpty.B)
      d.data_err_i.poke(dataPending.getOrElse(false).B)
      d.rf_rdata_a_ecc_i.poke(registers(d.rf_raddr_a_o.peek().litValue.toInt).U)
      d.rf_rdata_b_ecc_i.poke(registers(d.rf_raddr_b_o.peek().litValue.toInt).U)
      val request=d.instr_req_o.peek().litToBoolean
      val address=d.instr_addr_o.peek().litValue
      heldRequest.foreach(old=>assert(request && address==old,"fetch request must hold until grant"))
      if(request && grant) pending.enqueue((ticks+instructionDelay,address))
      heldRequest=if(request && !grant) Some(address) else None
      dataPending=if(failLoads && d.data_req_o.peek().litToBoolean) {
        val write=d.data_we_o.peek().litToBoolean
        accesses+=((d.data_addr_o.peek().litValue,write)); Some(!write)
      } else None
      if(d.rf_we_wb_o.peek().litToBoolean) {
        val rd=d.rf_waddr_wb_o.peek().litValue.toInt
        if(rd!=0) registers(rd)=d.rf_wdata_wb_ecc_o.peek().litValue
      }
      d.clk_i.step(); ticks+=1
      if(d.rvfi_valid.peek().litToBoolean) {
        retired+=((d.rvfi_pc_rdata.peek().litValue,d.rvfi_insn.peek().litValue))
        nextPcs+=d.rvfi_pc_wdata.peek().litValue
        if(d.rvfi_trap.peek().litToBoolean) traps+=d.rvfi_pc_rdata.peek().litValue
        assert(d.rvfi_order.peek().litValue==retired.size,"SYSTEM_RETIREMENT_ORDER")
      }
      assert(ticks<3000,s"SYSTEM_TEST_TIMEOUT retired=${retired.takeRight(12)}")
    }
    def until(predicate: =>Boolean):Unit={while(!predicate) step()}
  }
  for((delay,grantEvery)<-Seq((1,1),(3,2),(5,3))) {
    test(s"registered jump redirects preserve links and discard delayed fetches, latency=$delay grant=$grantEvery") {
      simulateRaw(new IbexCore(RegisteredExecution=true)) { d=>
        val code=Map(0x80->addi(1,0xb0),0x84->BigInt("010002ef",16),
          0x88->addi(20,1),0x8c->addi(20,2),0x90->addi(20,3),
          0x94->BigInt("00008367",16),0x98->addi(20,4),
          0xb0->addi(7,7),0xb4->BigInt("9002a011",16),
          0xb8->BigInt("04130001",16),0xbc->BigInt("a0010090",16))
          .map{case(a,v)=>BigInt(a)->v}
        val rig=new Rig(d,code,instructionDelay=delay,grantPeriod=grantEvery)
        rig.until(rig.retired.exists(_._1==0xba))
        assert(rig.retired.map(_._1)==Seq(0x80,0x84,0x94,0xb0,0xb4,0xb8,0xba).map(BigInt(_)))
        assert(rig.nextPcs==Seq(0x84,0x94,0xb0,0xb4,0xb8,0xba,0xbe).map(BigInt(_)))
        assert(rig.registers(5)==0x88 && rig.registers(6)==0x98)
        assert(rig.registers(7)==7 && rig.registers(8)==9 && rig.registers(20)==0)
        assert(rig.traps.isEmpty)
      }
    }
  }
  for(interruptPoint<-Seq("multiply","redirect")) {
    test(s"enabled timer IRQ saves and resumes the registered boundary after $interruptPoint") {
      simulateRaw(new IbexCore(RegisteredExecution=true)) { d=>
        val code=Map(0x80->addi(1,0x100),0x84->BigInt("30509073",16),
          0x88->addi(2,128),0x8c->BigInt("30411073",16),
          0x90->addi(3,8),0x94->BigInt("3001a073",16),
          0x98->addi(1,37),0x9c->addi(2,5),0xa0->BigInt("02208333",16),
          0xa4->BigInt("00000463",16),0xa8->addi(22,99),0xac->addi(4,9),
          0x11c->BigInt("34102a73",16),0x120->BigInt("34202af3",16),
          0x124->BigInt("30200073",16)).map{case(a,v)=>BigInt(a)->v}
        val rig=new Rig(d,code,instructionDelay=3,grantPeriod=2)
        if(interruptPoint=="multiply") {
          rig.until(rig.retired.exists(_._1==0x9c))
          for(_<-0 until 6) rig.step()
          assert(!rig.retired.exists(_._1==0xa0),"IRQ must be raised before MUL retirement")
        } else { rig.until(rig.retired.exists(_._1==0xa4)) }
        rig.timer=true
        rig.until(rig.retired.exists(_._1==0x11c))
        rig.timer=false
        rig.until(rig.retired.exists(_._1==0xac))
        assert(rig.registers(20)==(if(interruptPoint=="multiply") 0xa4 else 0xac),"saved interrupt PC")
        assert(rig.registers(21)==BigInt("80000007",16),"machine timer interrupt cause")
        assert(rig.registers(6)==185 && rig.registers(4)==9 && rig.registers(22)==0)
        assert(rig.retired.count(_._1==0xa0)==1 && rig.retired.count(_._1==0xa4)==1)
        assert(rig.retired.count(_._1==0x124)==1,"MRET must resume once")
        assert(rig.traps.isEmpty)
      }
    }
  }
  for(registered<-Seq(false,true)) {
    test(s"MRET and timer wake after WFI, registered=$registered") {
      simulateRaw(new IbexCore(RegisteredExecution=registered)) { d=>
        // MRET restores MPP; explicitly select machine mode for the subsequent
        // privileged MIE write rather than relying on the reset MPP value.
        val code=Map(0x80->addi(5,3),0x84->BigInt("00b29293",16),0x88->BigInt("30029073",16),
          0x8c->addi(1,0xc0),0x90->BigInt("34109073",16),0x94->BigInt("30200073",16),
          0xc0->addi(2,128),0xc4->BigInt("30411073",16),0xc8->BigInt("10500073",16),0xcc->addi(3,7))
          .map{case(a,v)=>BigInt(a)->v}
        val rig=new Rig(d,code)
        rig.until(d.core_busy_o.peek().litValue==10)
        for(_<-0 until 20) rig.step()
        assert(rig.registers(3)==0,"WFI must hold the following instruction")
        rig.timer=true
        rig.until(rig.registers(3)==7 && rig.retired.exists(_._1==0xcc))
        assert(rig.retired.take(10).map(_._1)==Seq(0x80,0x84,0x88,0x8c,0x90,0x94,0xc0,0xc4,0xc8,0xcc).map(BigInt(_)))
      }
    }
    test(s"debug request during multiply returns through DRET, registered=$registered") {
      simulateRaw(new IbexCore(RegisteredExecution=registered)) { d=>
        val code=Map(BigInt(0x80)->addi(1,37),BigInt(0x84)->addi(2,5),
          BigInt(0x88)->BigInt("022081b3",16),BigInt(0x8c)->addi(4,9),
          BigInt("1a110800",16)->addi(20,55),BigInt("1a110804",16)->BigInt("7b200073",16))
        val rig=new Rig(d,code)
        rig.until(rig.retired.exists(_._1==0x84))
        rig.step(); rig.debug=true
        rig.until(rig.retired.exists(_._1==BigInt("1a110800",16)))
        rig.debug=false
        rig.until(rig.registers(4)==9 && rig.retired.exists(_._1==0x8c))
        assert(rig.registers(3)==185 && rig.registers(20)==55)
        assert(rig.retired.count(_._1==0x88)==1,"multiply must retire exactly once across debug")
        assert(rig.retired.exists(_._2==BigInt("7b200073",16)),"DRET must retire")
      }
    }
    test(s"ordinary and CSR instructions followed by precise exceptions, registered=$registered") {
      simulateRaw(new IbexCore(RegisteredExecution=registered)) { d=>
        for(trap<-Seq("000022f3","00000073","00100073")) {
          val code=Map(BigInt(0x80)->addi(1,7),BigInt(0x84)->BigInt("34009073",16),
            BigInt(0x88)->addi(2,9),BigInt(0x8c)->BigInt(trap,16),BigInt(0x90)->addi(3,11))
          val rig=new Rig(d,code)
          rig.until(rig.retired.exists(_._1==0))
          assert(rig.traps.toSeq==Seq(BigInt(0x8c)))
          assert(rig.retired.take(4).map(_._1)==Seq(0x80,0x84,0x88,0x8c).map(BigInt(_)))
          assert(rig.registers(1)==7 && rig.registers(2)==9 && rig.registers(3)==0 && rig.registers(5)==0)
        }
      }
    }
    test(s"split load error flushes before handler store, registered=$registered") {
      simulateRaw(new IbexCore(RegisteredExecution=registered)) { d=>
        val code=Map(BigInt(0x80)->addi(1,0x303),BigInt(0x84)->BigInt("00009103",16),
          BigInt(0)->addi(3,8),BigInt(4)->BigInt("0001a023",16),BigInt(8)->addi(4,9))
        val rig=new Rig(d,code,failLoads=true)
        rig.until(rig.retired.exists(_._1==8))
        assert(rig.traps.toSeq==Seq(BigInt(0x84)))
        assert(rig.registers(2)==0 && rig.registers(4)==9)
        assert(rig.accesses.filter(_._2).toSeq==Seq((BigInt(8),true)),"handler must issue exactly its own store")
      }
    }
  }
  test("reset cancels a pending registered multiply and restarts retirement order") {
    simulateRaw(new IbexCore(RegisteredExecution=true)) { d=>
      val code=Map(BigInt(0x80)->addi(1,37),BigInt(0x84)->addi(2,5),
        BigInt(0x88)->BigInt("022081b3",16),BigInt(0x8c)->addi(4,9))
      val rig=new Rig(d,code)
      rig.until(rig.retired.exists(_._1==0x84))
      for(_<-0 until 8) rig.step()
      assert(!rig.retired.exists(_._1==0x88),"reset stimulus must precede multiply completion")
      rig.reset()
      rig.until(rig.retired.exists(_._1==0x8c))
      assert(rig.retired.take(4).map(_._1)==Seq(0x80,0x84,0x88,0x8c).map(BigInt(_)))
      assert(rig.registers(3)==185 && rig.registers(4)==9)
    }
  }
}
