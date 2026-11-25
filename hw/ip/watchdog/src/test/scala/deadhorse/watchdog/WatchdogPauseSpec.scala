package deadhorse.watchdog
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class WatchdogPauseSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan05/watchdog-pause/simulation").toAbsolutePath
  }
  test("dormant time consumes no watchdog budget and first wake edge cannot expire") {
    simulateRaw(new WatchdogChannel(withPause=true)) { d=>
      def high(v: Bool)=v.peek().litToBoolean
      d.por_n.poke(false.B);d.reset_n.poke(false.B);d.pause.get.poke(false.B)
      d.start.poke(false.B);d.feed.poke(false.B);d.period.poke(19.U);d.window.poke(4.U);d.warning.poke(3.U)
      d.clk.step(3);d.por_n.poke(true.B);d.reset_n.poke(true.B)
      d.start.poke(true.B);d.clk.step();d.start.poke(false.B);d.clk.step(5)
      val budget=d.remaining.peek().litValue
      d.pause.get.poke(true.B)
      for(i<-0 until 300) {
        d.feed.poke((i==100).B);d.clk.step()
        assert(d.remaining.peek().litValue==budget && !high(d.resetHold),"WATCHDOG_DORMANT_BUDGET")
      }
      d.feed.poke(false.B);d.pause.get.poke(false.B);d.clk.step()
      assert(d.remaining.peek().litValue==budget && !high(d.resetHold),"WATCHDOG_WAKE_GRACE")
      d.clk.step((budget-1).toInt);assert(d.remaining.peek().litValue==1)
      d.pause.get.poke(true.B);d.clk.step(20)
      assert(d.remaining.peek().litValue==1 && !high(d.resetHold),"WATCHDOG_PAUSE_AT_EXPIRY")
      d.pause.get.poke(false.B);d.clk.step();assert(!high(d.resetHold),"WATCHDOG_WAKE_IMMEDIATE_EXPIRY")
      d.clk.step();assert(high(d.resetHold) && high(d.cause) && d.crashes.peek().litValue==1,"WATCHDOG_RESUMED_DEADLINE")
    }
  }
}
