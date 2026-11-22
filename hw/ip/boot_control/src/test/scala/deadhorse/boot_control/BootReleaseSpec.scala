package deadhorse.boot_control
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import deadhorse.lib.ResetRelease
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class BootResetBench extends RawModule {
  val aon=IO(Input(Clock()));val main=IO(Input(Clock()))
  val epoch=IO(Input(Bool()));val service=IO(Input(Bool()))
  val start=IO(Input(Bool()));val command=IO(Input(Bool()));val key=IO(Input(Bool()))
  val open=IO(Output(Bool()));val ready=IO(Output(Bool()))
  val b=Module(new BootRelease);b.clk:=aon;b.epochReset_n:=epoch;b.serviceReset_n:=service
  b.startAccepted:=start;b.command:=command;b.keyGood:=key;open:=b.released
  val r=Module(new ResetRelease);r.clk:=main;r.reset_n:=epoch && b.released;ready:=r.released
}
class BootReleaseSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t28/reset-simulation").toAbsolutePath
  }
  test("whole reset asserts with stopped clocks, release waits for destination edges") {
    simulateRaw(new BootResetBench) {d=>
      def high(b: Bool)=b.peek().litToBoolean
      d.epoch.poke(false.B);d.service.poke(false.B);d.start.poke(false.B)
      d.command.poke(false.B);d.key.poke(true.B);d.aon.step(2);d.main.step(2)
      d.epoch.poke(true.B);d.service.poke(true.B)
      d.start.poke(true.B);d.command.poke(true.B);d.aon.step()
      assert(!high(d.open),"BOOT_SAME_EDGE")
      d.start.poke(false.B);d.aon.step();assert(high(d.open) && !high(d.ready))
      d.command.poke(false.B);d.aon.step(5);assert(!high(d.ready))
      d.main.step();assert(!high(d.ready));d.main.step();assert(high(d.ready))
      d.service.poke(false.B);assert(high(d.open) && high(d.ready))
      d.aon.step(3);d.service.poke(true.B);assert(high(d.ready))
      d.epoch.poke(false.B);assert(!high(d.open) && !high(d.ready),"BOOT_ASYNC_ASSERT")
      d.epoch.poke(true.B);d.main.step(5);d.aon.step(5);assert(!high(d.ready))
    }
  }
}
