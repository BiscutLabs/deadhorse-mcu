package deadhorse.sram

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SramSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t35/unit").toAbsolutePath
  }
  implicit val backendSettings: svsim.BackendSettingsModifications={
    case s: svsim.verilator.Backend.CompilationSettings =>
      s.withTiming(Some(svsim.verilator.Backend.CompilationSettings.Timing.TimingEnabled))
    case s=>s
  }
  // Input audit, not an RTL behavior test. Preserve fatal diagnostics except
  // the exact diagnostics of this byte-exact vendor functional model.
  implicit val commonSettings: svsim.CommonSettingsModifications=s=>{
    val dir=outputDirectory.getDirectory
    val depth=if(java.nio.file.Files.exists(dir.resolve("primary-sources/gf180mcu_ocd_ip_sram__sram512x8m8wm1.v"))) 512 else 1024
    val name=s"gf180mcu_ocd_ip_sram__sram${depth}x8m8wm1.v"
    val source=dir.resolve("primary-sources").resolve(name)
    if(!java.nio.file.Files.exists(source)) s else {
      val raw=java.nio.file.Files.readAllBytes(Paths.get(s"build/vendor/gf180_sram/cells/gf180mcu_ocd_ip_sram__sram${depth}x8m8wm1",name))
      val hash=java.security.MessageDigest.getInstance("SHA-256").digest(raw).map(b=>f"${b & 255}%02x").mkString
      val expectedHash=if(depth==512) "59c431f0f36cb939bb9d12a3818a735959cac77f1b9ab39c439f986387f07be4" else "9b3f0403197df34186eddab06c0f887cbc83f8732a806fb5f0c4ac6403dab4cb"
      require(hash==expectedHash,"SRAM_VENDOR_DRIFT")
      val expected=new String(raw,java.nio.charset.StandardCharsets.UTF_8).replace("\r\n","\n")
      val emitted=java.nio.file.Files.readString(source).replace("\r\n","\n")
      require(emitted==expected+"\n","SRAM_EMITTED_VENDOR_DRIFT")
      val path=dir.resolve("workdir-verilator/../primary-sources").resolve(name)
      java.nio.file.Files.writeString(dir.resolve("primary-sources/sram-model.vlt"),
        "`verilator_config\n"+
        s"lint_off -rule SPECIFYIGN -file \"$path\" -match \"Ignoring unsupported: specify block construct*\"\n"+
        s"lint_off -rule MINTYPMAXDLY -file \"$path\" -match \"Unsupported: minimum/typical/maximum delay expressions. Using the typical delay*\"\n"+
        s"lint_off -rule LATCH -file \"$path\" -match \"Latch inferred for signal 'cen_fell' (not all control paths of combinational always assign a value)*\"\n"+
        s"lint_off -rule WIDTHEXPAND -file \"$path\" -match \"Operator ASSIGN expects 10 bits on the Assign RHS, but Assign RHS's CONST '9'h0' generates 9 bits.*\"\n")
      s.copy(fileFilter={case f if f.getName=="sram-model.vlt"=>true
        case f=>s.fileFilter.applyOrElse(f,(_: java.io.File)=>true)})
    }
  }
  private val mask32=BigInt("ffffffff",16)
  private def high(b: Bool)=b.peek().litToBoolean
  for(depth<-Seq(1024,512);target<-Seq(SramTarget.Model,SramTarget.VendorSimulation)) {
    test(s"$target depth=$depth all rows and byte masks match an independent word array") {
      simulateRaw(new SramWordBank(depth,target=target)) {d=>
        // Vendor timescale is 1 ps: use the production 125 ns period so its
        // 100/200 ps scheduling delays finish before sampling. Functional only.
        def tick(n: Int=1): Unit=d.clk.step(n,if(target==SramTarget.VendorSimulation) 125000 else 10)
        val random=new scala.util.Random(0x351024)
        val words=Array.fill[BigInt](depth)(0)
        d.port.enable.poke(false.B);d.port.write.poke(false.B);d.port.address.poke(0.U)
        d.port.data.poke(0.U);d.port.mask.poke(0.U);tick(3)
        def access(a: Int,w: Boolean=false,data: BigInt=0,mask: Int=15): Unit={
          d.port.enable.poke(true.B);d.port.write.poke(w.B);d.port.address.poke(a.U)
          d.port.data.poke(data.U);d.port.mask.poke(mask.U);tick()
          if(w) {
            val bits=(0 until 4).filter(i=>(mask&(1<<i))!=0).map(i=>BigInt(255)<<(8*i)).foldLeft(BigInt(0))(_|_)
            words(a)=(words(a)&(mask32^bits))|(data&bits)
          } else d.port.result.expect(words(a).U,"SRAM_ARRAY_ORACLE")
        }
        // Never rely on the vendor model's power-up zeros.
        for(a<-words.indices) access(a,true,BigInt(32,random))
        for(a<-words.indices.reverse) access(a)
        for(mask<-0 until 16;a<-Seq(0,1,255,256,511,512,767,768,1023).filter(_<depth)) {
          access(a,true,BigInt(32,random),mask);access(a)
          val held=words(a);d.port.enable.poke(false.B);tick(2);d.port.result.expect(held.U)
        }
        for(_<-0 until 400) {
          val a=random.nextInt(depth);access(a,true,BigInt(32,random),random.nextInt(16));access(a)
        }
      }
    }
  }

  test("512-word vendor lane-swap negative control is detected") {
    val error=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new SramWordBank(512,SramTarget.VendorSimulation) {
        override protected def lane(index: Int): Int=3-index
      }) {d=>
        d.port.enable.poke(false.B);d.port.write.poke(false.B);d.port.address.poke(511.U)
        d.port.data.poke(0.U);d.port.mask.poke(15.U);d.clk.step(3,125000)
        d.port.enable.poke(true.B);d.port.write.poke(true.B);d.port.data.poke(0x12345678L.U)
        d.clk.step(1,125000);d.port.write.poke(false.B);d.clk.step(1,125000)
        assert(d.port.result.peek().litValue==0x12345678L,"SRAM_RETAINED_LANE_ORACLE")
      }
    }
    assert(error.getMessage.contains("SRAM_RETAINED_LANE_ORACLE"))
  }

  private def march(words: Int,fault: String,early: Boolean=false): Unit={
    simulateRaw(new SramMarch(words) {
      override protected def completed(last: Bool): Bool=if(early) true.B else last
    }) {d=>
      val random=new scala.util.Random(35);val data=Array.fill(words)(BigInt(32,random))
      val sequence=Seq((0 until words,false,0),(0 until words,true,0),
        (0 until words,true,1),((0 until words).reverse,true,0),
        ((0 until words).reverse,true,1),(0 until words,false,0))
      // Independently enumerate the required operations, not the DUT state.
      val expected=sequence.zipWithIndex.flatMap {case((addresses,paired,bit),phase)=>
        addresses.flatMap {a=>
          if(phase==0) Seq((a,true,BigInt(0)))
          else if(paired) Seq((a,false,if(bit==0) BigInt(0) else mask32),
            (a,true,if(bit==0) mask32 else BigInt(0)))
          else Seq((a,false,BigInt(0)))
        }
      }
      d.reset_n.poke(false.B);d.run.poke(false.B);d.permitted.poke(false.B);d.memory.result.poke(0.U)
      d.clk.step(3);d.reset_n.poke(true.B);d.permitted.poke(true.B);d.run.poke(true.B)
      var operations=0;var clocks=0
      while(!high(d.done) && clocks<words*20+10) {
        var read: Option[BigInt]=None
        if(high(d.memory.enable)) {
          assert(operations<expected.size,"MARCH_EXTRA_OPERATION")
          val a=d.memory.address.peek().litValue.toInt;val w=high(d.memory.write)
          val value=d.memory.data.peek().litValue;val e=expected(operations)
          assert(a==e._1 && w==e._2 && (!w || value==e._3),"MARCH_SEQUENCE")
          d.memory.mask.expect(15.U)
          val physical=if(fault=="alias") a & ~1 else a
          if(w) {
            data(physical)=fault match {
              case "stuck0"=>value & (mask32^1)
              case "stuck1"=>value | 1
              case "rise"=>value & (mask32^1) | (data(physical)&1)
              case "fall"=>value | (data(physical)&1)
              case _=>value
            }
          } else read=Some(data(physical))
          operations+=1
        }
        d.clk.step();read.foreach(v=>d.memory.result.poke(v.U));clocks+=1
      }
      assert(high(d.done),"MARCH_PROGRESS")
      assert(operations==10*words,"MARCH_COMPLETE_COVERAGE")
      d.result.failed.expect((fault!="none").B,"MARCH_FAULT_DETECTION")
      if(fault!="none") assert(d.result.observed.peek().litValue!=d.result.expected.peek().litValue)
      d.run.poke(false.B);d.clk.step();d.busy.expect(false.B);d.memory.enable.expect(false.B)
    }
  }
  for(words<-Seq(4096,512)) test(s"March covers every operation in the $words-word production memory") {march(words,"none")}
  for(fault<-Seq("stuck0","stuck1","rise","fall","alias")) test(s"March rejects $fault and records the observed mismatch") {march(16,fault)}
  test("independent operation oracle rejects premature completion") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {march(16,"none",early=true)}
    assert(e.getMessage.contains("MARCH_SEQUENCE") || e.getMessage.contains("MARCH_COMPLETE_COVERAGE"))
  }

  test("ownership survives debugger reset release and waits for the slower AON agent") {
    simulateRaw(new SramBist(16,8)) {d=>
      d.cold_n.poke(false.B);d.epoch_n.poke(false.B);d.start.poke(false.B);d.keyed.poke(false.B);d.authorized.poke(false.B)
      d.mainReset_n.poke(true.B);d.aonReset_n.poke(true.B)
      d.main.result.poke(0.U);d.aon.result.poke(0.U)
      val main=Array.fill[BigInt](16)(0);val aon=Array.fill[BigInt](8)(0)
      def port(p: SramPort,m: Array[BigInt]): Option[BigInt]={
        if(!high(p.enable)) None else {
          d.resetHold.expect(true.B,"BIST_OWNERSHIP")
          val a=p.address.peek().litValue.toInt
          if(high(p.write)) {m(a)=p.data.peek().litValue;None} else Some(m(a))
        }
      }
      var ndm=false;var ticks=0
      def step(n: Int=1,remote: Boolean=true): Unit=for(_<-0 until n) {
        val reset=ndm || high(d.resetHold)
        d.mainReset_n.poke((!reset).B);d.aonReset_n.poke((!reset).B)
        val r=port(d.main,main);d.clk.step();r.foreach(v=>d.main.result.poke(v.U))
        if(remote && ticks%5==0) {val a=port(d.aon,aon);d.aonClock.step();a.foreach(v=>d.aon.result.poke(v.U))}
        ticks+=1
      }
      step(30);d.cold_n.poke(true.B);d.epoch_n.poke(true.B);step(35)
      d.keyed.poke(true.B);d.start.poke(true.B);step();d.start.poke(false.B);step(2)
      d.rejected.expect(true.B);d.resetHold.expect(false.B)
      ndm=true;d.authorized.poke(true.B);step(30);d.resetAck.expect(true.B)
      d.start.poke(true.B);step();d.start.poke(false.B);step(4)
      ndm=false;d.authorized.poke(false.B)
      step(300,remote=false);d.resetHold.expect(true.B);d.done.expect(false.B)
      var timeout=0;while(!high(d.done) && timeout<2000) {step();timeout+=1}
      assert(high(d.done),"BIST_COMPLETION");d.failed.expect(false.B);d.resetHold.expect(false.B)
      // Reacquire, then abort both clock-domain epochs while AON is stopped.
      ndm=true;d.authorized.poke(true.B);step(30);d.start.poke(true.B);step();d.start.poke(false.B);step(12)
      d.epoch_n.poke(false.B);step(3,remote=false);d.resetHold.expect(false.B);d.done.expect(false.B)
      d.epoch_n.poke(true.B);ndm=false;d.authorized.poke(false.B);step(80)
      d.resetHold.expect(false.B);d.done.expect(false.B);d.main.enable.expect(false.B);d.aon.enable.expect(false.B)
    }
  }
}
