package deadhorse.boot_control
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class BootModeStrapSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan05/boot-strap/simulation").toAbsolutePath
  }
  def check(d: BootModeStrap): Unit={
    for(value<-Seq(false,true,false)) {
      d.wholeReset_n.poke(false.B);d.qualified.poke(false.B);d.pad.poke(value.B);d.clk.step(3)
      assert(!d.frozen.peek().litToBoolean && !d.value.peek().litToBoolean)
      d.wholeReset_n.poke(true.B);d.clk.step(2);assert(!d.frozen.peek().litToBoolean)
      d.qualified.poke(true.B);d.clk.step();assert(d.frozen.peek().litToBoolean && d.value.peek().litToBoolean==value)
      for(i<-0 until 12) {
        d.pad.poke((i%2==0).B);d.clk.step()
        assert(d.value.peek().litToBoolean==value,"BOOT_STRAP_CHANGED_AFTER_FREEZE")
      }
    }
  }
  test("sample both values through qualification and retain until whole reset") {simulateRaw(new BootModeStrap)(check)}
  test("raw-pad bypass is rejected") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new BootModeStrap {override protected def heldValue(held: Bool,raw: Bool): Bool=raw})(check)
    };assert(e.getMessage.contains("BOOT_STRAP_CHANGED_AFTER_FREEZE"))
  }
}
