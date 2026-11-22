package deadhorse.usb

import chisel3._
import chisel3.util._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.{Files, Paths}
import org.scalatest.funsuite.AnyFunSuite

/** Generated from the production Yosys graph plus the exact proved observer.
  * All stimulus enters through public wire/application ports.
  */
class UsbSamplingEngine(scenario: String) extends BlackBox with HasBlackBoxPath {
  val io = IO(new Bundle {
    val clk = Input(Clock()); val reset_n = Input(Bool()); val vbus = Input(Bool())
    val dpRx = Input(Bool()); val dnRx = Input(Bool())
    val dpTx = Output(Bool()); val dnTx = Output(Bool()); val txEnable = Output(Bool()); val pullupOut = Output(Bool())
    val txData = Input(UInt(8.W)); val txValid = Input(Bool()); val txReady = Output(Bool())
    val rxData = Output(UInt(8.W)); val rxValid = Output(Bool()); val rxReady = Input(Bool())
    val configured = Output(Bool()); val frame = Output(UInt(11.W))
    val sessionReset = Output(Bool()); val attached = Output(Bool())
    val txReset = Output(Bool()); val rxReset = Output(Bool()); val txEmpty = Output(Bool()); val rxEmpty = Output(Bool())
    val violations = Output(UInt(11.W)); val coverage = Output(UInt(7.W))
  })
  val root = Paths.get(Files.readString(Paths.get("build/plan03/usb-sampling-active.txt")).trim).toAbsolutePath.normalize
  require(root.startsWith(Paths.get("build").toAbsolutePath.normalize))
  require(Set("positive", "lookahead", "outputs", "spacing", "outputs-phase", "spacing-phase")(scenario))
  addPath(root.resolve(scenario).resolve("UsbSamplingEngine.v").toString)
}

class UsbSamplingBench(scenario: String) extends Module with UsbWirePorts {
  val hostDrive = IO(Input(Bool())); val hostDp = IO(Input(Bool())); val hostDn = IO(Input(Bool()))
  val vbus = IO(Input(Bool())); val txData = IO(Input(UInt(8.W))); val txValid = IO(Input(Bool()))
  val txReady = IO(Output(Bool())); val rxData = IO(Output(UInt(8.W))); val rxValid = IO(Output(Bool()))
  val rxReady = IO(Input(Bool())); val dp = IO(Output(Bool())); val dn = IO(Output(Bool()))
  val oe = IO(Output(Bool())); val pullupEnable = IO(Output(Bool())); val configured = IO(Output(Bool()))
  val violationsSeen = IO(Output(UInt(11.W))); val coverageSeen = IO(Output(UInt(7.W)))
  val engine = Module(new UsbSamplingEngine(scenario)).io
  engine.clk := clock; engine.reset_n := !reset.asBool; engine.vbus := vbus
  engine.dpRx := Mux(engine.txEnable, engine.dpTx, Mux(hostDrive, hostDp, engine.pullupOut))
  engine.dnRx := Mux(engine.txEnable, engine.dnTx, Mux(hostDrive, hostDn, false.B))
  engine.txData := txData; engine.txValid := txValid; txReady := engine.txReady
  engine.rxReady := rxReady; rxData := engine.rxData; rxValid := engine.rxValid
  dp := engine.dpTx; dn := engine.dnTx; oe := engine.txEnable
  pullupEnable := engine.pullupOut; configured := engine.configured
  // Sample on the same edge as each original $check, before the DUT updates.
  val violations = RegInit(0.U(11.W)); violations := violations | engine.violations
  val coverage = RegInit(0.U(7.W)); coverage := coverage | engine.coverage
  violationsSeen := violations; coverageSeen := coverage
}

class UsbSamplingSpec extends AnyFunSuite with ChiselSim {
  private var scenario = "positive"
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/plan03/usb-sampling-simulation", scenario).toAbsolutePath
  }
  test("production sampling predicates hold on real control traffic and reset") {
    scenario = "positive"
    simulate(new UsbSamplingBench(scenario)) { d =>
      val h = new UsbWireHost(d); h.initialize()
      assert(h.read(0,6,0x100,18,retryFirst=true).size == 18)
      assert(h.read(0,6,0x200,255,retryFirst=true).size == 67)
      for (size <- Seq(7,9)) {
        h.setup(0, h.setupBytes(0x80,6,0x100,0,18).padTo(size,0).take(size))
        h.token(h.IN,0,0); assert(h.receive()._1 == h.STALL)
      }
      h.token(h.SETUP,0,0); h.idle(2)
      h.data(h.DATA0,h.setupBytes(0x80,6,0x100,0,18),badCrc=true); h.silence(500)
      assert(h.read(0,6,0x100,18).size == 18)
      h.write(0,5,5); h.write(5,9,1)
      assert(d.violationsSeen.peek().litValue == 0)
      val before = d.coverageSeen.peek().litValue
      h.busReset(); assert(!h.bool(d.configured))
      assert(h.read(0,6,0x100,18).size == 18)
      assert(d.violationsSeen.peek().litValue == 0)
      // New SETUP preempts a control transfer that has not completed its status.
      h.setup(0,h.setupBytes(0x80,6,0x100,0,18))
      h.setup(0,h.setupBytes(0x80,6,0x200,0,67))
      h.token(h.IN,0,0); assert(h.receive()._2.take(2) == Seq(9,2))
      d.vbus.poke(false.B); h.step(8); d.vbus.poke(true.B)
      h.step(820000); assert(h.bool(d.pullupEnable)); h.busReset()
      assert(h.read(0,6,0x100,18).size == 18)
      assert(d.violationsSeen.peek().litValue == 0)
      println(s"USB_SAMPLING_COVER before_reset=$before after_reset=${d.coverageSeen.peek().litValue} reset_release_after_traffic=1")
      assert((d.coverageSeen.peek().litValue & 63) == 63, "missing data/header/error real-wire witness")
      h.initialize(); assert(h.read(0,6,0x100,18).size == 18)
      assert(d.violationsSeen.peek().litValue == 0)
      println("USB_SAMPLING_ROOT_RESET after_traffic=1 release=1")
    }
  }
  for ((fault,mask) <- Seq(("lookahead",15), ("outputs",240), ("spacing",1792),
                          ("outputs-phase",240), ("spacing-phase",1792))) {
    test(s"real wire traffic rejects the $fault capture fault") {
      scenario = fault
      simulate(new UsbSamplingBench(scenario)) { d =>
        val h = new UsbWireHost(d); h.initialize()
        h.setup(0,h.setupBytes(0x80,6,0x100,0,18))
        h.token(h.IN,0,0); h.receive(); h.idle(30)
        val broken = d.violationsSeen.peek().litValue
        println(s"USB_SAMPLING_FAULT $fault violations=$broken")
        assert((broken & mask) != 0, s"$fault mutation escaped the unchanged sampling predicate")
      }
    }
  }
}
