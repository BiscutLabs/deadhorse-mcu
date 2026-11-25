package deadhorse.top

import chisel3._
import deadhorse.lib.LocalBus
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Passive event taps on public BusBridge interfaces, never internal state.
  * They select reset phases; the response oracle uses the exposed top buses.
  */
class SocI1ObservedCrossings extends SocPeripheralBusTest(SocTestFiles.description,SocProduction.config(realUsb=false)) {
  val accepted=IO(Output(Vec(1,Bool())));val dispatched=IO(Output(Vec(1,Bool())))
  for((b,i)<-Seq(toAon).zipWithIndex) {
    accepted(i):=b.source.req && b.source.gnt
    dispatched(i):=b.target.req && b.target.gnt
  }
}
class SocI1ResetBench extends RawModule {
  val mainClock=IO(Input(Clock()));val aonClock=IO(Input(Clock()))
  val reset_n=IO(Input(Bool()));val mainReset_n=IO(Input(Bool()));val aonReset_n=IO(Input(Bool()))
  val ignoreAonReset=IO(Input(Bool()));val ignoreMainReset=IO(Input(Bool()))
  val main=IO(new LocalBus);val aon=IO(new LocalBus)
  val accepted=IO(Output(Vec(1,Bool())));val dispatched=IO(Output(Vec(1,Bool())))
  val d=Module(new SocI1ObservedCrossings)
  SocTestPorts.tieIdle(d)
  SocInactiveTestInputs.tieOff(d.pins.inactive)
  d.mainClock:=mainClock;d.pins.aonClock:=aonClock;d.pins.usbClock:=mainClock
  d.coldReset_n:=reset_n;d.warmReset_n:=true.B;d.mainServiceReset_n:=mainReset_n || ignoreMainReset
  d.pins.aonServiceReset_n:=aonReset_n || ignoreAonReset;d.pins.usbServiceReset_n:=true.B
  d.pins.aonExtraIn:=0.U
  d.main<>main;d.pins.lite<>aon
  d.uartRx:=true.B;d.pins.uartRx.foreach(_:=true.B)
  d.pins.liteHalted:=true.B;d.pins.resetReason:=0.U;d.pins.crashCount:=0.U
  d.pins.spiMiso:=false.B;d.pins.spiTimeNow:=0.U
  d.pins.i2cSclIn:=true.B;d.pins.i2cSdaIn:=true.B;
  d.pins.usbVbus:=false.B;d.pins.usbDpRx:=false.B;d.pins.usbDnRx:=false.B
  accepted:=d.accepted;dispatched:=d.dispatched
}

class SocI1ResetSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t20/i1/reset-simulation").toAbsolutePath
  }
  def high(pin: Bool): Boolean=pin.peek().litToBoolean
  test("retained toAon crossings cancel once on stopped-clock peer reset and source reset drains dispatched work") {
    simulateRaw(new SocI1ResetBench) { d =>
      def tick(n: Int=1): Unit=for(_<-0 until n) {d.mainClock.step();d.aonClock.step()}
      def drive(bus: LocalBus,address: Long,write: Boolean=false,value: Long=0): Unit = {
        bus.req.poke(true.B);bus.bits.addr.poke(address.U);bus.bits.we.poke(write.B)
        bus.bits.wdata.poke(value.U);bus.bits.be.poke(15.U);bus.bits.origin.poke(7.U)
      }
      def initialize(): Unit = {
        d.ignoreAonReset.poke(false.B);d.ignoreMainReset.poke(false.B);d.reset_n.poke(false.B)
        d.mainReset_n.poke(true.B);d.aonReset_n.poke(true.B)
        drive(d.main,0);drive(d.aon,0);d.main.req.poke(false.B);d.aon.req.poke(false.B)
        tick(4);d.reset_n.poke(true.B);tick(40)
      }
      def access(bus: LocalBus,address: Long,write: Boolean=false,value: Long=0): (BigInt,Boolean) = {
        drive(bus,address,write,value);var cycles=0
        while(!high(bus.gnt)) {tick();cycles+=1;assert(cycles<256)}
        tick();bus.req.poke(false.B)
        while(!high(bus.rvalid)) {tick();cycles+=1;assert(cycles<512)}
        val result=(bus.rdata.peek().litValue,high(bus.err));tick(3);assert(!high(bus.rvalid));result
      }
      def run(direction: Int,sourceReset: Boolean,corrupt: Boolean=false): Unit = {
        initialize();assert(!access(d.aon,0x30000400L,true,0x12345678L)._2)
        d.ignoreAonReset.poke((corrupt && direction==0).B)
        d.ignoreMainReset.poke((corrupt && direction==1).B)
        val bus=if(direction==0) d.main else d.aon
        val address=if(direction==0) 0x30000400L else 0x40010000L
        val event=if(sourceReset) d.dispatched(direction) else d.accepted(direction)
        drive(bus,address)
        var taken=false;var reached=false;var cycles=0
        while(!reached && cycles<256) {
          val take=high(bus.req)&&high(bus.gnt);reached=high(event)
          assert(!high(bus.rvalid),"I1_RESET_PHASE_AFTER_RESPONSE")
          tick();if(take) {assert(!taken);taken=true;bus.req.poke(false.B)};cycles+=1
        }
        assert(reached && taken,"I1_RESET_PHASE_NOT_REACHED")
        val resetMain=if(sourceReset) direction==0 else direction==1
        val peer=if(resetMain) d.mainReset_n else d.aonReset_n
        // Both clocks stopped during the entire raw assertion/release pulse.
        peer.poke(false.B);assert(!high(peer));peer.poke(true.B)
        if(sourceReset) {
          for(_<-0 until 80) {assert(!high(bus.rvalid),"I1_RESET_SOURCE_OLD_REPLY");tick()}
        } else {
          var replies=0
          for(_<-0 until 80) {
            if(high(bus.rvalid)) {
              replies+=1;assert(high(bus.err) && bus.rdata.peek().litValue==0,"I1_PEER_RESET_ERROR")
            }
            // No destination edge can produce an ordinary endpoint reply.
            // Error must originate from peer-reset cancellation at the source.
            if(direction==0) d.mainClock.step() else d.aonClock.step()
          }
          assert(replies==1,"I1_PEER_RESET_EXACTLY_ONCE")
          for(_<-0 until 80) {assert(!high(bus.rvalid),"I1_PEER_RESET_LATE_REPLY");tick()}
        }
        val result=access(bus,address)
        if(direction==0) assert(result==(BigInt(0x12345678L),false),"I1_RESET_FRESH_READ")
        else assert(result==(BigInt(0),true),"I1_RESET_FRESH_OWNER_CHECK")
      }
      for(direction<-0 until 1;sourceReset<-Seq(false,true)) run(direction,sourceReset)
      for(direction<-0 until 1) {
        val failure=intercept[org.scalatest.exceptions.TestFailedException] {run(direction,false,corrupt=true)}
        assert(failure.getMessage.contains("I1_PEER_RESET_EXACTLY_ONCE"))
      }
    }
  }
}
