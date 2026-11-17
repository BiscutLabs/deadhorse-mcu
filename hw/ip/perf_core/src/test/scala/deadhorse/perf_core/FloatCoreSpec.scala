package deadhorse.perf_core

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.{Files,Paths}
import org.scalatest.funsuite.AnyFunSuite
import scala.collection.mutable
import scala.sys.process._

/** Architectural known answers, driven and observed exclusively at core ports. */
class FloatCoreSpec extends FloatCoreBehavior(true, "registered")
class FaithfulFloatCoreSpec extends FloatCoreBehavior(false, "faithful")

abstract class FloatCoreBehavior(registered: Boolean, profile: String) extends AnyFunSuite with ChiselSim {
  private val directory=Paths.get(s"build/t13/core-tests/$profile").toAbsolutePath
  implicit val outputDirectory:HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=directory
  }
  private case class Image(bytes:Array[Byte], labels:Map[String,BigInt])
  private def assemble(name:String,body:String):Image={
    val dir=directory.resolve(name); Files.createDirectories(dir)
    val src=dir.resolve("program.S"); val elf=dir.resolve("program.elf"); val bin=dir.resolve("program.bin")
    Files.writeString(src,".option norvc\n.option norelax\n.global _start\n_start:\n"+body)
    assert(Seq("riscv64-unknown-elf-gcc","-march=rv32imfc_zicsr","-mabi=ilp32f",
      "-nostdlib","-Wl,--no-relax","-Wl,-Ttext=0x80",src.toString,"-o",elf.toString).! == 0)
    assert(Seq("riscv64-unknown-elf-objcopy","-O","binary",elf.toString,bin.toString).! == 0)
    val labels=Seq("riscv64-unknown-elf-nm","--defined-only",elf.toString).!!.linesIterator.flatMap { line=>
      val fields=line.trim.split("\\s+")
      if(fields.length==3) Some(fields(2)->BigInt(fields(0),16)) else None
    }.toMap
    Image(Files.readAllBytes(bin),labels)
  }
  private val setup="li x1,0x2000\ncsrw mstatus,x1\nli x1,0x3f800000\nfmv.w.x f1,x1\nli x1,0x40000000\nfmv.w.x f2,x1\n"
  private case class Retirement(pc:BigInt,nextPc:BigInt,trap:Boolean,fs:BigInt,fcsr:BigInt,
      fregs:Vector[BigInt],write:Boolean,rd:BigInt,value:BigInt)
  private class Rig(d:IbexCore,image:Image,delay:Int=1,grantEvery:Int=1,dataDelay:Int=1) {
    val x=Array.fill(32)(BigInt(0)); val rows=mutable.ArrayBuffer.empty[Retirement]
    val memory=mutable.Map.empty[BigInt,Int]
    image.bytes.zipWithIndex.foreach {case(b,i)=>memory(BigInt(0x80+i))=b&255}
    var timer=false; var debug=false; var nmi=false; var failData=false
    var unsolicitedError=false; var allowDataGrant=true; var errorWithoutResponse=false
    var failDataAt=Set.empty[Int]
    var fetchFault:Option[BigInt]=None
    var ticks=0
    var dataRequests=0
    private val pending=mutable.Queue.empty[(Int,BigInt)]
    private val dataPending=mutable.Queue.empty[(Int,BigInt,Boolean)]
    private var held:Option[BigInt]=None
    def word(a:BigInt):BigInt=(0 until 4).map(i=>BigInt(memory.getOrElse(a+i,0))<<(8*i)).reduce(_|_)
    d.hart_id_i.poke(0.U); d.boot_addr_i.poke(0.U); d.fetch_enable_i.poke(5.U)
    d.instr_gnt_i.poke(false.B); d.instr_rvalid_i.poke(false.B); d.instr_rdata_i.poke(0.U); d.instr_err_i.poke(false.B)
    d.data_gnt_i.poke(false.B); d.data_rvalid_i.poke(false.B); d.data_rdata_i.poke(0.U); d.data_err_i.poke(false.B)
    d.rf_rdata_a_ecc_i.poke(0.U); d.rf_rdata_b_ecc_i.poke(0.U)
    d.ic_tag_rdata_i.poke(0.U); d.ic_data_rdata_i.poke(0.U); d.ic_scr_key_valid_i.poke(true.B)
    d.irq_software_i.poke(false.B); d.irq_external_i.poke(false.B); d.irq_fast_i.poke(0.U)
    d.irq_nm_i.poke(false.B); d.irq_timer_i.poke(false.B); d.debug_req_i.poke(false.B)
    def reset():Unit={
      d.rst_ni.poke(false.B); d.clk_i.step(2); d.rst_ni.poke(true.B)
      x.indices.foreach(i=>x(i)=0); rows.clear(); pending.clear(); dataPending.clear(); held=None; ticks=0; dataRequests=0
    }
    reset()
    def step():Unit={
      d.debug_req_i.poke(debug.B); d.irq_timer_i.poke(timer.B); d.irq_nm_i.poke(nmi.B)
      val response=if(pending.headOption.exists(_._1<=ticks)) Some(pending.dequeue()._2) else None
      val grant=ticks%grantEvery==0
      d.instr_gnt_i.poke(grant.B); d.instr_rvalid_i.poke(response.nonEmpty.B)
      d.instr_rdata_i.poke(response.map(a=>if(memory.contains(a)) word(a) else BigInt(0x6f)).getOrElse(BigInt(0)).U)
      d.instr_err_i.poke(response.exists(a=>fetchFault.contains(a)).B)
      val dataResponse=if(dataPending.headOption.exists(_._1<=ticks)) Some(dataPending.dequeue()) else None
      val dataGrant=grant && allowDataGrant
      d.data_gnt_i.poke(dataGrant.B); d.data_rvalid_i.poke((dataResponse.nonEmpty || unsolicitedError).B)
      d.data_rdata_i.poke(dataResponse.map(_._2).getOrElse(BigInt(0)).U)
      d.data_err_i.poke(dataResponse.map(_._3).getOrElse(unsolicitedError || errorWithoutResponse).B)
      d.rf_rdata_a_ecc_i.poke(x(d.rf_raddr_a_o.peek().litValue.toInt).U)
      d.rf_rdata_b_ecc_i.poke(x(d.rf_raddr_b_o.peek().litValue.toInt).U)
      val request=d.instr_req_o.peek().litToBoolean; val address=d.instr_addr_o.peek().litValue
      held.foreach(a=>assert(request && address==a,"FP_FETCH_HOLD"))
      if(request && grant) pending.enqueue((ticks+delay,address))
      held=if(request && !grant) Some(address) else None
      if(d.data_req_o.peek().litToBoolean && dataGrant) {
        dataRequests+=1
        val error=failData || failDataAt.contains(dataRequests)
        val a=d.data_addr_o.peek().litValue & ~BigInt(3)
        val old=word(a)
        if(d.data_we_o.peek().litToBoolean && !error) {
          val mask=d.data_be_o.peek().litValue.toInt; val value=d.data_wdata_o.peek().litValue
          for(i<-0 until 4 if (mask&(1<<i))!=0) memory(a+i)=((value>>(8*i))&255).toInt
        }
        dataPending.enqueue((ticks+dataDelay,old,error))
      }
      if(d.rf_we_wb_o.peek().litToBoolean) {
        val rd=d.rf_waddr_wb_o.peek().litValue.toInt
        if(rd!=0) x(rd)=d.rf_wdata_wb_ecc_o.peek().litValue
      }
      d.clk_i.step(); ticks+=1
      if(d.rvfi_valid.peek().litToBoolean) {
        val all=d.rvfi_ext_fregs.get.peek().litValue
        rows+=Retirement(d.rvfi_pc_rdata.peek().litValue,d.rvfi_pc_wdata.peek().litValue,d.rvfi_trap.peek().litToBoolean,
          d.rvfi_ext_fs.get.peek().litValue,d.rvfi_ext_fcsr.get.peek().litValue,
          Vector.tabulate(32)(i=>(all>>(32*i))&BigInt("ffffffff",16)),
          d.rvfi_frd_wen.get.peek().litToBoolean,d.rvfi_frd_addr.get.peek().litValue,
          d.rvfi_frd_wdata.get.peek().litValue)
        assert(d.rvfi_order.peek().litValue==rows.size,"FP_RETIREMENT_ORDER")
      }
      assert(ticks<6000,s"FP_CORE_TIMEOUT ${rows.takeRight(8)}")
    }
    def until(p: =>Boolean):Unit={while(!p) step()}
    def reached(label:String):Boolean=rows.exists(_.pc==image.labels(label))
    def row(label:String):Retirement=rows.find(_.pc==image.labels(label)).get
  }

  test("unsolicited bus errors cannot trap or cancel an FP operation") {
    val image=assemble("unsolicited",setup+"""
      before: nop
      divide: fdiv.s f0,f1,f2
      after: fmv.x.w x10,f0
      done: nop
      j .
    """)
    simulateRaw(new IbexCore(RegisteredExecution=registered,WithF=true)) { d=>
      val rig=new Rig(d,image)
      rig.until(rig.reached("before")); rig.unsolicitedError=true
      while(!rig.reached("done")) {
        rig.step()
        assert(rig.rows.forall(!_.trap),"UNOWNED_RESPONSE_TRAP")
      }
      assert(rig.dataRequests==0 && rig.x(10)==0x3f000000L)
      assert(rig.rows.count(_.pc==image.labels("divide"))==1)
      assert(rig.row("divide").write && rig.row("divide").fcsr==0)
    }
  }

  test("owned bus responses preserve aligned and split loads, stores and real errors") {
    val cases=for(op<-Seq("lw","sw","flw","fsw"); offset<-Seq(0,1)) yield {
      val operand=if(op.startsWith("f")) "f0" else "x10"
      val image=assemble(s"owned-$op-$offset",setup+s"""
        li x1,0x200
        csrw mtvec,x1
        li x10,99
        fmv.w.x f0,x1
        li x1,${0x600+offset}
        before: nop
        access: $op $operand,0(x1)
        after: nop
        j done
        .org 0x180
        handler: csrr x17,mcause
        csrr x18,mtval
        csrr x19,mepc
        done: nop
        j .
      """)
      (op,offset,image)
    }
    simulateRaw(new IbexCore(RegisteredExecution=registered,WithF=true)) { d=>
      for((op,offset,image)<-cases; latency<-Seq(1,4);
          badBeat<-0 to (if(offset==0) 1 else 2)) {
        val rig=new Rig(d,image,dataDelay=latency)
        val address=BigInt(0x600+offset)
        val initial=BigInt("12345678",16)
        for(b<-0 until 4) rig.memory(address+b)=((initial>>(8*b))&255).toInt
        rig.failDataAt=if(badBeat==0) Set.empty else Set(badBeat)
        rig.allowDataGrant=false
        rig.until(rig.reached("before"))
        // Exercise unsolicited responses while a memory instruction waits for
        // a grant, including its eventual grant cycle. Neither owns a response.
        rig.unsolicitedError=true
        for(_<-0 until 10) rig.step()
        assert(rig.dataRequests==0 && !rig.reached("handler"))
        rig.allowDataGrant=true
        rig.until(rig.dataRequests==1)
        rig.unsolicitedError=false; rig.errorWithoutResponse=true
        rig.until(rig.reached("done"))
        val label=s"$op offset=$offset latency=$latency badBeat=$badBeat"
        assert(rig.dataRequests==(if(offset==0) 1 else 2),label)
        if(badBeat==0) {
          assert(rig.rows.forall(!_.trap) && !rig.reached("handler"),label)
          if(op=="lw") assert(rig.x(10)==initial,label)
          if(op=="flw") assert(rig.row("access").fregs(0)==initial,label)
          if(op=="sw" || op=="fsw") assert(rig.word(address)==(if(op=="sw") 99 else 0x200),label)
        } else {
          assert(rig.x(17)==(if(op.endsWith("lw")) 5 else 7),label)
          assert(rig.x(19)==image.labels("access"),label)
          assert(rig.x(18)==(if(badBeat==1) address else BigInt(0x604)),label)
          assert(!rig.reached("after"),label)
          if(op=="lw") assert(rig.x(10)==99,label)
          if(op=="flw") assert(rig.row("access").fregs(0)==0x200 && !rig.row("access").write,label)
        }
      }
      // Reset with both split grants outstanding, before either returns.
      // Old responses arriving after reset must not be assigned to the restart.
      val resetImage=cases.find(c=>c._1=="lw" && c._2==1).get._3
      val resetRig=new Rig(d,resetImage,dataDelay=6)
      for(b<-0 until 4) resetRig.memory(BigInt(0x601+b))=((0x12345678L>>(8*b))&255).toInt
      resetRig.until(resetRig.dataRequests==2)
      assert(!resetRig.reached("access"))
      resetRig.reset(); resetRig.allowDataGrant=false
      resetRig.until(resetRig.reached("before"))
      // Hold old responses until exception entry is observable after boot;
      // otherwise stale credits could drain unnoticed in the reset states.
      resetRig.unsolicitedError=true
      for(_<-0 until 10) resetRig.step()
      assert(resetRig.dataRequests==0 && !resetRig.reached("handler") && resetRig.rows.forall(!_.trap))
      resetRig.unsolicitedError=false; resetRig.allowDataGrant=true
      resetRig.until(resetRig.reached("done"))
      assert(resetRig.rows.forall(!_.trap) && resetRig.x(10)==0x12345678L && resetRig.dataRequests==2)
    }
  }

  test("F decode preserves dependencies, f0, CSR aliases and compressed memory under backpressure") {
    val image=assemble("dependencies",setup+"""
      sum: fadd.s f0,f1,f2
      integer: addi x10,x0,17
      move: fmv.x.w x11,f0
      flags: csrwi fflags,1
      rounding: csrwi frm,3
      csr: csrr x12,fcsr
      csrr x13,misa
      csrw mscratch,x10
      csrr x14,mscratch
      li x1,0x33800000
      fmv.w.x f3,x1
      dynamic: fadd.s f4,f1,f3,dyn
      li sp,0x600
      fsw f4,0(sp)
      flw f5,0(sp)
      .option rvc
      c.fswsp f5,4(sp)
      stack: c.flwsp f0,4(sp)
      mv x8,sp
      c.flw f8,0(x8)
      c.fsw f8,8(x8)
      .option norvc
      fused: fmadd.s f6,f1,f2,f0
      branch: beq x0,x0,done
      fmv.w.x f0,x0
      done: addi x20,x0,1
      j .
    """)
    simulateRaw(new IbexCore(RegisteredExecution=registered,WithF=true)) { d=>
      for((delay,grant)<-Seq((1,1),(5,3))) {
        val rig=new Rig(d,image,delay,grant); rig.until(rig.reached("done"))
        assert(rig.rows.forall(!_.trap)); assert(rig.x(10)==17 && rig.x(11)==0x40400000L)
        assert(rig.x(12)==0x61 && rig.x(13)==0x40101124L && rig.x(14)==17); assert(rig.row("sum").fregs(0)==0x40400000L)
        assert(rig.row("dynamic").fregs(4)==0x3f800001L && rig.row("dynamic").fcsr==0x61)
        assert(rig.row("stack").write && rig.row("stack").rd==0)
        assert(rig.row("stack").fregs(0)==0x3f800001L)
        assert(rig.word(0x608)==0x3f800001L)
        assert(rig.row("fused").fregs(6)==0x40400001L && rig.row("fused").fs==3)
        // Deliberate trace mutation must fail the same architectural comparison.
        def check(row:Retirement):Unit=assert(row.fregs(0)==0x40400000L,"FP_KNOWN_SUM")
        check(rig.row("sum"))
        intercept[org.scalatest.exceptions.TestFailedException] {
          check(rig.row("sum").copy(fregs=rig.row("sum").fregs.updated(0,0)))
        }
      }
    }
  }

  test("FS Off, invalid rounding, fetch and load faults cause precise traps without FP writes") {
    val initialized=setup+"fmv.w.x f0,x1\nli x10,99\n"
    val cases=Seq(
      ("fs-off",initialized+"csrw mstatus,x0\n", "fadd.s f0,f1,f2",false,false),
      ("csr-off",initialized+"csrw mstatus,x0\n", "csrr x10,fcsr",false,false),
      ("reserved-rm",initialized+"csrwi frm,5\n", "fadd.s f0,f1,f2,dyn",false,false),
      ("unknown-csr",initialized, "csrr x10,0x555",false,false),
      ("readonly-csr",initialized, "csrrw x10,mhartid,x1",false,false),
      ("user-csr",initialized+"la x1,fault\ncsrw mepc,x1\nli x1,0x6000\ncsrw mstatus,x1\nmret\n",
        "csrr x10,mstatus",false,false),
      ("load-fault",initialized+"li x1,0x600\n", "flw f0,0(x1)",true,false),
      ("fetch-fault",initialized, "fadd.s f0,f1,f2",false,true))
    val images=cases.map {case(name,init,op,_,_)=>assemble(name,init+s"fault: $op\nafter: addi x20,x0,1\nj .\n")}
    simulateRaw(new IbexCore(RegisteredExecution=registered,WithF=true)) { d=>
      for(((name,_,_,data,fetch),image)<-cases.zip(images)) {
        val rig=new Rig(d,image); rig.failData=data
        if(fetch) rig.fetchFault=Some(image.labels("fault") & ~BigInt(3))
        rig.until(rig.rows.exists(_.trap))
        val row=rig.rows.find(_.trap).get
        assert(row.pc==image.labels("fault"),name); assert(!row.write && rig.x(20)==0 && rig.x(10)==99,name)
        assert(row.fregs(0)==0x40000000L,"fault must preserve actual FP payload: "+name)
        assert(row.fcsr==(if(name=="reserved-rm") 0xa0 else 0),name)
        assert(row.fs==(if(name.endsWith("off")) 0 else 3),name)
      }
    }
  }

  test("illegal F encodings cannot issue memory, write X, or count as retired") {
    val cases=Seq(("off-flw",false,0x0000a507L),("off-fsw",false,0x0020a027L),
      ("bad-load-width",true,0x00008507L),("bad-store-width",true,0x00208027L),
      ("bad-to-int-rm",true,0xc000d553L))
    val images=cases.map {case(name,enabled,encoding)=>
      assemble(name,(if(enabled) "li x1,0x2000\ncsrw mstatus,x1\n" else "")+s"""
        li x1,0x200
        csrw mtvec,x1
        li x10,99
        li x1,0x600
        csrr x15,minstret
      fault: .word 0x${encoding.toHexString}
        j .
        .org 0x180
      handler: csrr x16,minstret
        csrr x17,mcause
        csrr x18,mtval
      done: j .
      """)
    }
    simulateRaw(new IbexCore(RegisteredExecution=registered,WithF=true)) { d=>
      for(((name,_,encoding),image)<-cases.zip(images)) {
        val rig=new Rig(d,image)
        rig.until(rig.reached("done"))
        assert(rig.dataRequests==0 && rig.x(10)==99,name)
        assert(rig.x(16)==rig.x(15)+1,s"$name illegal instruction counted in minstret")
        assert(rig.x(17)==2 && rig.x(18)==encoding,name)
        assert(rig.row("fault").trap && !rig.row("fault").write,name)
      }
    }
  }

  test("timer, NMI and debug during divide finish exactly once; reset cancels in flight") {
    val image=assemble("events",setup+"""
      li x1,0x200
      csrw mtvec,x1
      li x1,128
      csrw mie,x1
      csrsi mstatus,8
      before: nop
      divide: fdiv.s f0,f1,f2
      after: fmv.x.w x10,f0
      done: nop
      j .
      .org 0x19c
      timer_handler: csrr x21,mepc
      csrr x22,mcause
      mret
      .org 0x1fc
      nmi_handler: csrr x21,mepc
      csrr x22,mcause
      mret
    """)
    simulateRaw(new IbexCore(RegisteredExecution=registered,WithF=true)) { d=>
      val baseline=new Rig(d,image,3,2)
      baseline.until(baseline.reached("divide"))
      val commitTick=baseline.ticks
      for(event<-Seq("timer","nmi","debug","reset"); offset<-Seq(10,25,-1)) {
        val rig=new Rig(d,image,3,2)
        // The debug ROM uses the configured architectural entry address.
        val debugCode=Seq(0x7b102af3L,0x7b200073L) // csrr x21,dpc; dret
        for((word,index)<-debugCode.zipWithIndex; b<-0 until 4)
          rig.memory(BigInt("1a110800",16)+4*index+b)=((word>>(8*b))&255).toInt
        rig.until(rig.reached("before"))
        if(offset<0) rig.until(rig.ticks==commitTick-1)
        else for(_<-0 until offset) rig.step()
        assert(!rig.reached("divide"),"event must precede divide completion")
        event match {
          case "reset"=>rig.reset()
          case "timer"=>rig.timer=true
          case "nmi"=>rig.nmi=true
          case "debug"=>rig.debug=true
        }
        if(event!="reset") {
          val handler=if(event=="debug") BigInt("1a110800",16) else image.labels(event+"_handler")
          rig.until(rig.rows.exists(_.pc==handler)); rig.timer=false; rig.nmi=false; rig.debug=false
          assert(rig.x(21)==image.labels("after"),event)
        }
        rig.until(rig.reached("done"))
        if(event!="reset") {
          val returnPc=if(event=="debug") BigInt("1a110804",16) else image.labels(event+"_handler")+8
          assert(rig.rows.find(_.pc==returnPc).get.nextPc==image.labels("after"),"return RVFI target")
        }
        assert(rig.x(10)==0x3f000000L && rig.rows.count(_.pc==image.labels("divide"))==1,event)
        assert(rig.row("divide").write && rig.row("divide").fs==3 && rig.row("divide").fcsr==0,event)
        assert(rig.rows.forall(!_.trap),event)
      }
    }
  }
}
