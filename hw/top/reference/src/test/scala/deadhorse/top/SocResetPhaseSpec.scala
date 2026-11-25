package deadhorse.top

import chisel3._
import chisel3.simulator.{ChiselSim,Randomization,Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Real JTAG SBA transactions under production pad resets. Digital retained
  * memory behavior is checked; no physical SRAM brownout-retention claim. */
class SocResetPhaseSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t33/reset-phase-simulation").toAbsolutePath
  }
  private val settings=Settings.defaultRaw[SocResetPhaseProbe].copy(
    randomization=Randomization.random.copy(memories=false)).withLibraryPaths(Seq(Paths.get(
      "hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
  private val gate=Array("--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
    "--ckg-enable=en_i","--ckg-test-enable=test_en_i")
  private val phases=Seq("requested","grant-visible","granted","dispatch-visible","dispatched","buffered","returning")
  private case class Epoch(grants: BigInt,returns: BigInt,errors: BigInt,writes: BigInt,result: BigInt)
  private def checkEpoch(row: Epoch,cold: Boolean,effects: Int): Unit={
    assert(row.grants==1,"PHASE_DM_ACCEPTANCE")
    assert(row.returns==(if(cold) 0 else 1),"PHASE_DM_COMPLETION")
    assert(row.errors==(if(cold) 0 else 1),"PHASE_DM_ERROR")
    assert(row.writes==effects,"PHASE_COMMIT_COUNT")
    if(!cold) assert(row.result==0,"PHASE_DM_CANCEL_DATA")
  }

  for((resetKind,missingPin)<-Seq(("warm-pin",false),("brownout",false),("bypass-pin",false),("warm-pin",true)))
  test(s"production native and retained SBA reset phases: $resetKind missingPin=$missingPin") {
    def exercise(): Unit={
    simulateRaw(new SocResetPhaseProbe,settings=settings,firtoolOpts=gate) {d=>
      d.pins.uartRx.foreach(_.poke(true.B));d.pins.spiMiso.poke(false.B)
      d.pins.i2cSclIn.poke(true.B);d.pins.i2cSdaIn.poke(true.B)

      d.pins.usbVbus.poke(false.B);d.pins.usbDpRx.poke(false.B);d.pins.usbDnRx.poke(false.B)
      d.pins.aonExtraIn.poke(0.U)
      val p=d.pins.inactive;val o=d.observe
      p.qspiDqIn.poke(0.U);p.jtagTck.poke(false.B);p.jtagTms.poke(true.B);p.jtagTdi.poke(false.B)
      p.imuDrdy.poke(false.B);p.gpioIn.poke(0.U);p.timerIn.poke(0.U)
      val bypass=resetKind=="bypass-pin"
      d.porBypass.poke(bypass.B);d.aonClockSelect.poke(false.B);d.externalReset_n.poke(false.B)
      d.monitorReset_n.poke(false.B)
      val m=d.model.get;m.supplyMv.poke(0.U);m.porReference.step(3);m.lfClock.step(4)
      def high(value: Bool)=value.peek().litToBoolean
      var now=0L;var armed=false;var fired=false;var released=true;var releaseAt=0L
      var selectedPhase="";var retained=false
      var attemptGrants=BigInt(0);var attemptReturns=BigInt(0);var sourceGrants=BigInt(0);var attemptWrites=BigInt(0)
      var trace=Vector.empty[(Long,String)];var armedAt=0L
      def selectedBus=if(retained) o.retained else o.native
      def writes=if(retained) o.retainedWrites.peek().litValue else o.nativeWrites.peek().litValue
      def phaseReached: Boolean=selectedPhase match {
        case "requested"=>high(o.source.request) && !high(o.source.grant)
        case "grant-visible"=>high(o.source.request) && high(o.source.grant)
        case "granted"=>o.sourceGrants.peek().litValue>sourceGrants
        case "dispatch-visible"=>high(selectedBus.request) && high(selectedBus.grant)
        case "dispatched"=>writes>attemptWrites
        case "buffered"=>high(selectedBus.response)
        case "returning"=>high(o.source.response)
      }
      def advance(count: Int): Unit={
        var remaining=count
        while(remaining>0) {
          if(armed && phaseReached) {
            assert(o.dmGrants.peek().litValue==attemptGrants+1,"PHASE_WRONG_ACCEPTED_OPERATION")
            assert(o.dmReturns.peek().litValue==attemptReturns,"PHASE_OPERATION_ALREADY_COMPLETED")
            trace=trace:+((now-armedAt,"reset_assert"))
            armed=false;fired=true;released=false;releaseAt=now+3000
            if(resetKind=="brownout") m.supplyMv.poke(3050.U) else if(!missingPin) d.externalReset_n.poke(false.B)
            assert(!high(d.status.servicesReleased),"PHASE_RESET_ASSERTION_MISSING")
          }
          if(!released && now>=releaseAt) {
            released=true
            if(resetKind=="brownout") m.supplyMv.poke(3300.U) else d.externalReset_n.poke(true.B)
          }
          val boundary=math.min(48-(now%48).toInt,1500-(now%1500).toInt)
          val n=if(armed || !released) 1 else math.min(remaining,boundary)
          d.oscIn.step(n);now+=n;remaining-=n
          if(now%48==0) m.porReference.step()
          if(now%1500==0) m.lfClock.step()
          if(armed) {
            // The armed interval advances exactly one source cycle at a time.
            // Coincident target commit/reply observations stay visible.
            val events=Seq("dm_accept"->(o.dmGrants.peek().litValue>attemptGrants),
              "source_accept"->(o.sourceGrants.peek().litValue>sourceGrants),
              "target_commit"->(writes>attemptWrites),"target_reply"->high(selectedBus.response),
              "source_reply"->high(o.source.response))
            for((name,seen)<-events if seen && !trace.exists(_._2==name)) trace=trace:+((now-armedAt,name))
          }
        }
      }
      m.supplyMv.poke(3300.U);m.porReference.step(1002);d.externalReset_n.poke(true.B)
      advance(1500*580);d.status.servicesReleased.expect(true.B);d.monitorReset_n.poke(true.B)
      d.status.coreReady.expect(true.B)
      d.status.coreSleeping.expect(true.B) // diagnostic ROM is quiescent; no fabricated core traffic
      def tap(tms: Boolean,tdi: Boolean=false): Boolean={
        p.jtagTck.poke(false.B);p.jtagTms.poke(tms.B);p.jtagTdi.poke(tdi.B);advance(240)
        val result=high(p.jtagTdo);p.jtagTck.poke(true.B);advance(240);p.jtagTck.poke(false.B);result
      }
      def selectDmi(): Unit={
        for(_<-0 until 16) tap(true);tap(false)
        tap(true);tap(true);tap(false);tap(false)
        for(i<-0 until 5) tap(i==4,((0x11>>i)&1)!=0)
        tap(true);tap(false);for(_<-0 until 16) tap(false)
      }
      def scan(value: BigInt,inject: Boolean=false): BigInt={
        tap(true);tap(false);tap(false);var result=BigInt(0)
        for(i<-0 until 41) if(tap(i==40,value.testBit(i))) result=result.setBit(i)
        if(inject) {fired=false;armed=true;trace=Vector.empty;armedAt=now}
        tap(true);tap(false);for(_<-0 until 16) tap(false)
        result
      }
      def dmi(address: Int,value: BigInt=0,write: Boolean=false): BigInt={
        scan((BigInt(address)<<34)|(value<<2)|(if(write) 2 else 1))
        val result=scan(0);assert((result&3)==0,"PHASE_DMI_RESPONSE")
        (result>>2)&BigInt("ffffffff",16)
      }
      val clearControl=(BigInt(2)<<17)|(BigInt(1)<<22)|(BigInt(7)<<12)
      def ready(expectedError: Int=0): Unit={
        var value=dmi(0x38);var tries=0
        while(value.testBit(21) && tries<16) {value=dmi(0x38);tries+=1}
        assert(!value.testBit(21),"PHASE_SBA_BUSY")
        assert(!value.testBit(22) && ((value>>12)&7)==expectedError,"PHASE_SBA_ERROR")
      }
      def dmCounts=(o.dmGrants.peek().litValue,o.dmReturns.peek().litValue,o.dmErrors.peek().litValue)
      def normalCompletion(before: (BigInt,BigInt,BigInt),value: BigInt): Unit={
        val after=dmCounts
        assert(after._1==before._1+1 && after._2==before._2+1 && after._3==before._3,"PHASE_FRESH_COMPLETION")
        assert(o.dmLast.peek().litValue==value,"PHASE_FRESH_DATA")
      }
      def write(address: BigInt,value: BigInt): Unit={
        val before=dmCounts
        dmi(0x38,clearControl,true);dmi(0x39,address,true);dmi(0x3c,value,true);ready()
        normalCompletion(before,0)
      }
      def read(address: BigInt): BigInt={
        val before=dmCounts
        dmi(0x38,clearControl|(BigInt(1)<<20),true);dmi(0x39,address,true);ready()
        val result=dmi(0x3c);normalCompletion(before,result);result
      }
      selectDmi();dmi(0x10,1,true)
      var caseId=0
      for(route<-Seq(false,true);phase<-phases) {
        retained=route;selectedPhase=phase;caseId+=1
        val address=BigInt(if(route) "30000400" else "20003000",16)+4*caseId
        val initial=BigInt("10203000",16)+caseId
        val attempted=BigInt("51a00000",16)+caseId
        val fresh=BigInt("26b00000",16)+caseId
        write(address,initial);assert(read(address)==initial,"PHASE_INITIAL_MEMORY")
        val before=writes
        dmi(0x38,clearControl,true);dmi(0x39,address,true)
        val counts=dmCounts
        attemptGrants=counts._1;attemptReturns=counts._2;attemptWrites=before
        sourceGrants=o.sourceGrants.peek().litValue
        // Reset is a real pad/supply event, selected by passive public-bus phase.
        scan((BigInt(0x3c)<<34)|(attempted<<2)|2,inject=true)
        advance(1500*128);assert(fired && !armed,s"PHASE_NOT_REACHED $resetKind retained=$route phase=$phase")
        advance(1500*580);d.status.servicesReleased.expect(true.B)
        val committed=writes-before
        val effects=if(Set("dispatched","buffered","returning").contains(phase)) 1 else 0
        val after=dmCounts
        val observed=Epoch(after._1-counts._1,after._2-counts._2,after._3-counts._3,committed,o.dmLast.peek().litValue)
        val cold=resetKind!="warm-pin"
        checkEpoch(observed,cold,effects)
        if(effects==1) {
          val last=if(route) o.retainedLast else o.nativeLast
          last.address.expect(address.U);last.data.expect(attempted.U);last.origin.expect(2.U);last.mask.expect(15.U)
        }
        // Deliberately corrupted measured event records exercise the exact
        // checker. These are oracle controls, not internal RTL fault proofs.
        for(bad<-Seq(observed.copy(grants=observed.grants+1),observed.copy(returns=observed.returns+1),
            observed.copy(writes=observed.writes+1),observed.copy(errors=observed.errors+1))) {
          intercept[org.scalatest.exceptions.TestFailedException] {checkEpoch(bad,cold,effects)}
        }
        if(!cold) intercept[org.scalatest.exceptions.TestFailedException] {checkEpoch(observed.copy(result=1),cold,effects)}
        if(!cold) {
          intercept[org.scalatest.exceptions.TestFailedException] {checkEpoch(observed.copy(returns=0),cold,effects)}
          intercept[org.scalatest.exceptions.TestFailedException] {checkEpoch(observed.copy(errors=0),cold,effects)}
        }
        if(resetKind!="warm-pin") {selectDmi();dmi(0x10,1,true)}
        ready(expectedError=if(cold) 0 else 2)
        val expected=if(effects==1) attempted else initial
        assert(read(address)==expected,s"PHASE_RESET_EFFECT $resetKind retained=$route phase=$phase")
        write(address,fresh)
        assert(writes==before+committed+1,"PHASE_LATE_OR_DUPLICATE_WRITE")
        assert(read(address)==fresh,"PHASE_STALE_RETURN")
        info(s"covered $resetKind retained=$route phase=$phase commits=$committed trace=${trace.mkString(",")}")
      }
    }
    }
    if(missingPin) {
      // Deliberately omit the board reset pulse. This tests the pad-event
      // oracle; block-local wrong-reset-scope RTL controls remain separate.
      val e=intercept[org.scalatest.exceptions.TestFailedException] {exercise()}
      assert(e.getMessage.contains("PHASE_RESET_ASSERTION_MISSING"))
    } else exercise()
  }
}
