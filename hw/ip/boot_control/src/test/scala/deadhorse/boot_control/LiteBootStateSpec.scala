package deadhorse.boot_control

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class LiteBootStateSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan05/lite-boot/simulation").toAbsolutePath
  }
  def exercise(d: LiteBootState): Unit={
    d.epochReset_n.poke(false.B);d.serviceReset_n.poke(false.B)
    d.releaseCommand.poke(false.B);d.holdCommand.poke(false.B)
    d.releaseKey.poke(true.B);d.holdKey.poke(true.B);d.quiet.poke(false.B);d.debugOwned.poke(false.B)
    d.clk.step(2);d.epochReset_n.poke(true.B);d.serviceReset_n.poke(true.B)
    d.held.expect(true.B);d.released.expect(false.B)
    d.releaseCommand.poke(true.B);d.clk.step();d.releaseCommand.poke(false.B)
    d.held.expect(false.B);d.released.expect(true.B)
    d.holdCommand.poke(true.B);d.clk.step();d.holdCommand.poke(false.B)
    for(_<-0 until 8) {d.clk.step();d.held.expect(false.B,"BOOT_DRAIN_REQUIRED");d.draining.expect(true.B)}
    d.quiet.poke(true.B);d.clk.step();d.held.expect(true.B);d.released.expect(false.B)
    d.debugOwned.poke(true.B);d.releaseCommand.poke(true.B);d.clk.step()
    d.held.expect(true.B);d.error.expect(true.B)
    d.releaseCommand.poke(false.B);d.debugOwned.poke(false.B);d.clk.step()
    d.releaseCommand.poke(true.B);d.clk.step();d.releaseCommand.poke(false.B)
    d.serviceReset_n.poke(false.B);d.clk.step(3);d.released.expect(true.B)
    d.epochReset_n.poke(false.B);d.clk.step();d.held.expect(true.B)
  }
  test("lite reset follows the acknowledged instruction-boundary drain") {
    simulateRaw(new LiteBootState)(exercise)
  }
  test("premature drain completion is rejected") {
    val error=intercept[Throwable] {
      simulateRaw(new LiteBootState {override protected def drainComplete(q: Bool): Bool=true.B})(exercise)
    }
    assert(Iterator.iterate(error)(_.getCause).takeWhile(_!=null).exists(e=>Option(e.getMessage).exists(_.contains("BOOT_DRAIN_REQUIRED"))))
  }
}
