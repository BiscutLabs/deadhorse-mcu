package deadhorse.top

import chisel3._
import chisel3.simulator.{ChiselSim,Randomization,Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SocClientPhaseSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t33/client-phase-simulation").toAbsolutePath
  }
  private val settings=Settings.defaultRaw[SocClientPhaseProbe].copy(
    randomization=Randomization.random.copy(memories=false)).withLibraryPaths(Seq(Paths.get(
      "hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
  private val gates=Array("--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
    "--ckg-enable=en_i","--ckg-test-enable=test_en_i")
  private val storePhases=Seq("client-visible","client-accepted","downstream-visible","downstream-accepted",
    "target-visible","access-visible","committed","target-response","bridge-return","client-buffered")
  private val readPhases=Seq("register-response","target-response","bridge-return","client-buffered")
  private val flagNames=storePhases++Seq("register-response")

  for((lite,missingPin)<-Seq((false,false),(true,false),(false,true)))
  test(s"real client reset phases lite=$lite missingPin=$missingPin") {
    def exercise(): Unit=simulateRaw(new SocClientPhaseProbe(lite),settings=settings,firtoolOpts=gates) {d=>
      val p=d.pins.inactive;val o=d.observe;val m=d.model.get
      d.pins.uartRx.foreach(_.poke(true.B));d.pins.spiMiso.poke(false.B)
      d.pins.i2cSclIn.poke(true.B);d.pins.i2cSdaIn.poke(true.B)
      d.pins.recoveryScl.poke(true.B);d.pins.recoverySda.poke(true.B)
      d.pins.usbVbus.poke(false.B);d.pins.usbDpRx.poke(false.B);d.pins.usbDnRx.poke(false.B)
      p.qspiDqIn.poke(0.U);p.jtagTck.poke(false.B);p.jtagTms.poke(true.B);p.jtagTdi.poke(false.B)
      p.imuDrdy.poke(false.B);p.gpioIn.poke(0.U);p.timerIn.poke(0.U)
      d.porBypass.poke(false.B);d.aonClockSelect.poke(false.B)
      val address=BigInt(if(lite) "4001300c" else "40000100",16)
      val value=BigInt(if(lite) "51a03110" else "51a00110",16)
      val owner=if(lite) 0 else 1
      def high(x: Bool)=x.peek().litToBoolean
      var now=0L;var armed=false;var fired=false;var released=true;var releaseAt=0L
      var selectedRead=false;var phase="";var hostLow=false
      var trace=Vector.empty[(Long,String)];var armedAt=0L
      var phaseFlags=BigInt(0)
      def phaseReached: Boolean=phaseFlags.testBit(flagNames.indexOf(phase))
      def advance(count: Int): Unit={
        var remaining=count
        while(remaining>0) {
          if(armed && phaseReached) {
            assert(o.clientConsumed.peek().litValue==0,"CLIENT_ALREADY_CONSUMED")
            if(selectedRead && phase=="client-buffered") o.clientData.expect(value.U)
            trace=trace:+((now-armedAt,"reset_assert"));armed=false;fired=true;released=false;releaseAt=now+3000
            if(!missingPin) d.externalReset_n.poke(false.B)
            assert(!high(d.status.servicesReleased),"CLIENT_RESET_ASSERTION_MISSING")
          }
          if(!released && now>=releaseAt) {released=true;d.externalReset_n.poke(true.B)}
          val n=if(armed || !released) 1 else math.min(remaining,1500-(now%1500).toInt)
          val before=now;d.oscIn.step(n);now+=n;remaining-=n
          // Fixed valid supply during warm-reset sweeps. POR model reference
          // ticks are grouped between observations; analog phase is not tested.
          val references=(now/48-before/48).toInt;if(references>0) m.porReference.step(references)
          if(now%1500==0) m.lfClock.step()
          if(armed) {
            phaseFlags=o.phaseFlags.peek().litValue
            for((name,index)<-flagNames.zipWithIndex if phaseFlags.testBit(index) && !trace.exists(_._2==name))
              trace=trace:+((now-armedAt,name))
          }
        }
      }
      def coldBoot(read: Boolean): Unit={
        armed=false;fired=false;released=true;selectedRead=read;d.trackRead.poke(read.B)
        hostLow=false;d.pins.recoveryScl.poke(true.B);d.pins.recoverySda.poke(true.B)
        d.monitorReset_n.poke(false.B);d.externalReset_n.poke(false.B)
        m.supplyMv.poke(0.U);m.porReference.step(3);advance(6000)
        m.supplyMv.poke(3300.U);m.porReference.step(1002);d.externalReset_n.poke(true.B)
        advance(1500*580);d.status.servicesReleased.expect(true.B);d.status.coreReady.expect(false.B)
        o.loaderLocked.expect(false.B);o.loaderProgrammed.expect(false.B);o.liteHalted.expect(true.B)
        o.invalidated.expect(false.B)
        d.monitorReset_n.poke(true.B)
      }
      def wireStep(n: Int): Unit=for(_<-0 until n if !fired) {
        d.pins.recoverySda.poke((!hostLow && !high(d.pins.recoverySdaLow)).B)
        advance(1500)
        d.pins.recoverySda.poke((!hostLow && !high(d.pins.recoverySdaLow)).B)
      }
      def line(scl: Boolean,low: Boolean): Unit=if(!fired) {
        hostLow=low;d.pins.recoveryScl.poke(scl.B);wireStep(5)
      }
      def send(byte: Int,armLast: Boolean=false): Unit={
        for(bit<-7 to 0 by -1 if !fired) {
          val low=(byte&(1<<bit))==0;line(false,low)
          if(bit==0 && armLast) {armed=true;armedAt=now;trace=Vector.empty;phaseFlags=o.phaseFlags.peek().litValue}
          line(true,low);line(false,low)
        }
        if(!fired) {
          line(false,false);line(true,false)
          if(!fired) assert(!high(d.pins.recoverySda),"CLIENT_LOADER_ACK")
          line(false,false)
        }
      }
      def bytes(v: Long): Seq[Int]=(0 until 4).map(i=>((v>>>(8*i))&255).toInt)
      def command(op: Int,words: Seq[Long]=Seq.empty,arm: Boolean=false): Unit={
        line(true,false);line(true,true);line(false,true);send(0x6a);send(op,arm)
        words.flatMap(bytes).foreach(b=>send(b))
        line(false,true);line(true,true);line(true,false);wireStep(8)
        // A deliberate reset may abort START's final ACK/STOP. The host then
        // releases the wires; no ACK is required from a chip held in reset.
        if(fired) {hostLow=false;d.pins.recoveryScl.poke(true.B);d.pins.recoverySda.poke(true.B)}
      }
      val source=scala.io.Source.fromFile(s"build/t33/client-firmware/${if(lite) "lite" else "release"}.hex")
      val image=try source.getLines().map(x=>java.lang.Long.parseUnsignedLong(x,16)).toVector finally source.close()
      val crc=new java.util.zip.CRC32;image.flatMap(bytes).foreach(crc.update)
      def load(arm: Boolean): Unit={
        command(1,Seq(image.size*4L,16,crc.getValue,0x10000,16,0,0,0x2025))
        image.zipWithIndex.foreach {case(word,index)=>command(2,Seq(index*4L,word))}
        command(3);command(6,arm=arm)
      }
      def until(condition: =>Boolean,limit: Int,label: String): Unit={
        var elapsed=0;while(!condition && elapsed<limit) {advance(1500);elapsed+=1}
        if(!condition) println(s"CLIENT_DIAGNOSTIC lite=$lite label=$label ready=${high(d.status.coreReady)} epoch=${high(o.clientEpoch)} sleeping=${high(o.sleeping)} trap=${high(o.trap)} liteHalted=${high(o.liteHalted)} accepted=${o.clientAccepted.peek().litValue} consumed=${o.clientConsumed.peek().litValue} commits=${o.committed.peek().litValue} loads=${o.loadRetirements.peek().litValue} data=${o.loadData.peek().litValue} shadow=${o.shadow.peek().litValue} flags=${o.phaseFlags.peek().litValue}")
        assert(condition,label)
      }
      println(s"CLIENT_BEGIN lite=$lite missingPin=$missingPin")
      coldBoot(read=true);load(arm=false)
      until(high(o.sleeping) && o.loadRetirements.peek().litValue==1,1000,"CLIENT_BASELINE_PROGRESS")
      o.loadData.expect(value.U);o.shadow.expect(value.U);o.committed.expect(1.U)
      o.clientAccepted.expect(1.U);o.clientConsumed.expect(1.U);o.targetOrigin.expect(owner.U)
      o.commitData.expect(value.U);o.commitMask.expect(15.U);o.trap.expect(false.B)
      info(s"baseline lite=$lite matched actual load retirement and WFI")
      println(s"CLIENT_BASELINE_PASS lite=$lite missingPin=$missingPin")
      for((read,boundary)<-storePhases.map(false->_)++readPhases.map(true->_)) {
        phase=boundary;coldBoot(read);load(arm=true)
        until(fired,1000,s"CLIENT_PHASE_NOT_REACHED lite=$lite read=$read phase=$phase")
        advance(1500*580);d.status.servicesReleased.expect(true.B)
        o.mainUp.expect(true.B);o.aonUp.expect(true.B)
        d.status.coreReady.expect(false.B);o.liteHalted.expect(true.B)
        o.loaderLocked.expect(true.B);o.loaderProgrammed.expect(false.B)
        o.clientEpoch.expect(lite.B);o.invalidated.expect(true.B)
        val expectedClient=if(phase=="client-visible") 0 else 1
        val expectedTarget=if(Set("client-visible","client-accepted","downstream-visible","downstream-accepted","target-visible").contains(phase)) 0 else 1
        val expectedCommits=if(read || Set("committed","target-response","bridge-return","client-buffered").contains(phase)) 1 else 0
        def counts(client: BigInt,consumed: BigInt,target: BigInt,commits: BigInt): Unit={
          assert(client==expectedClient && consumed==0,"CLIENT_EPOCH_RESPONSE")
          assert(target==expectedTarget,"CLIENT_TARGET_ACCEPTANCE")
          assert(commits==expectedCommits,"CLIENT_COMMIT_COUNT")
        }
        val observed=(o.clientAccepted.peek().litValue,o.clientConsumed.peek().litValue,o.targetAccepted.peek().litValue,o.committed.peek().litValue)
        counts(observed._1,observed._2,observed._3,observed._4)
        intercept[org.scalatest.exceptions.TestFailedException] {counts(observed._1,1,observed._3,observed._4)}
        intercept[org.scalatest.exceptions.TestFailedException] {counts(observed._1,observed._2,observed._3,observed._4+1)}
        o.lateReturns.expect(0.U);o.lateRetirements.expect(0.U);o.loadRetirements.expect(0.U)
        o.shadow.expect(0.U)
        if(expectedTarget==1) o.targetOrigin.expect(owner.U)
        if(expectedCommits==1) {o.commitData.expect(value.U);o.commitMask.expect(15.U)}
        advance(1500*32);counts(o.clientAccepted.peek().litValue,o.clientConsumed.peek().litValue,o.targetAccepted.peek().litValue,o.committed.peek().litValue)
        o.lateReturns.expect(0.U);o.lateRetirements.expect(0.U)
        info(s"covered client lite=$lite read=$read phase=$phase commits=$expectedCommits trace=${trace.mkString(",")}")
      }
    }
    if(missingPin) {
      val e=intercept[org.scalatest.exceptions.TestFailedException] {exercise()}
      assert(e.getMessage.contains("CLIENT_RESET_ASSERTION_MISSING"))
    } else exercise()
  }
}
