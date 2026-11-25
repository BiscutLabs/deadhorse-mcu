package deadhorse.boot_control
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class BootResetContextSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t36/reset-context/simulation").toAbsolutePath
  }
  def exercise(d: BootResetContext): Unit={
    d.epochReset_n.poke(false.B);d.performanceHold.poke(true.B)
    d.commit.poke(false.B);d.commitKey.poke(false.B);d.clk.step(2)
    d.epochReset_n.poke(true.B);d.clk.step(5)
    d.freshPerformanceReset.expect(false.B,"STALE_HOLD_IS_NOT_FRESH")
    d.contextReady.expect(false.B)
    d.performanceHold.poke(false.B);d.clk.step()
    d.commit.poke(true.B);d.clk.step();d.contextReady.expect(false.B,"CONTEXT_KEY_REQUIRED")
    d.error.expect(true.B)
    d.commitKey.poke(true.B);d.clk.step();d.contextReady.expect(true.B);d.error.expect(false.B)
    d.commit.poke(false.B);d.performanceHold.poke(true.B);d.clk.step()
    d.freshPerformanceReset.expect(true.B);d.contextReady.expect(true.B)
    d.performanceHold.poke(false.B);d.clk.step(5)
    d.freshPerformanceReset.expect(true.B);d.contextReady.expect(true.B)
    // Whole reset wins even if a context commit is arriving concurrently.
    d.commit.poke(true.B);d.epochReset_n.poke(false.B);d.performanceHold.poke(true.B);d.clk.step()
    d.freshPerformanceReset.expect(false.B);d.contextReady.expect(false.B)
    d.commit.poke(false.B);d.epochReset_n.poke(true.B);d.clk.step(3)
    d.freshPerformanceReset.expect(false.B);d.contextReady.expect(false.B)
    d.performanceHold.poke(false.B);d.clk.step();d.performanceHold.poke(true.B);d.clk.step()
    d.freshPerformanceReset.expect(true.B);d.contextReady.expect(false.B)
  }
  test("fresh watchdog reset, context commit and whole-reset dominance") {
    simulateRaw(new BootResetContext)(exercise)
  }
  for((fault,label)<-Seq("hold"->"STALE_HOLD_IS_NOT_FRESH","key"->"CONTEXT_KEY_REQUIRED")) {
    test(s"reject $fault reset-context fault") {
      val e=intercept[Throwable] {
        simulateRaw(new BootResetContext {
          override protected def initialHold: Boolean=fault!="hold"
          override protected def validCommit(key: Bool): Bool=if(fault=="key") true.B else key
        })(exercise)
      }
      assert(Iterator.iterate(e)(_.getCause).takeWhile(_!=null).exists(x=>Option(x.getMessage).exists(_.contains(label))))
    }
  }
}
