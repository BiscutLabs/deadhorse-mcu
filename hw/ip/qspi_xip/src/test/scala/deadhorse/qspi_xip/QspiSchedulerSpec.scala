package deadhorse.qspi_xip
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class QspiSchedulerSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t30/scheduler-simulation").toAbsolutePath
  }
  def exercise(d: QspiScheduler): Unit={
    def high(v: Bool)=v.peek().litToBoolean
    d.reset_n.poke(false.B);d.enabled.poke(true.B);d.commandValid.poke(false.B)
    d.engineBusy.poke(false.B);d.engineDone.poke(false.B);d.engineResult.poke(0x12345678.U)
    d.command.poke(0.U.asTypeOf(d.command));d.command.select.poke(true.B)
    d.readConfig.poke(0.U.asTypeOf(d.readConfig));d.readConfig.addressBytes.poke(3.U)
    d.xip.req.poke(false.B);d.xip.bits.poke(0.U.asTypeOf(d.xip.bits))
    d.xip.bits.addr.poke(0x10000000L.U);d.xip.bits.origin.poke(1.U)
    d.clk.step(3);d.reset_n.poke(true.B);d.clk.step(3)
    // Start a raw command, then continuously refill both single-entry queues.
    d.commandValid.poke(true.B)
    var left=0;var frames=Vector.empty[Boolean];var reads=0;var commands=0
    for(_<-0 until 100) {
      if(high(d.engineStart)) {
        assert(left==0,"XIP_FRAME_OVERLAP")
        frames :+= high(d.engineCommand.select);left=6
        d.xip.req.poke(true.B)
      }
      if(high(d.xip.rvalid)) {assert(!high(d.xip.err));reads+=1}
      if(high(d.commandDone))commands+=1
      d.engineBusy.poke((left>0).B);d.engineDone.poke((left==1).B)
      d.clk.step();if(left>0)left-=1
      if(frames.size>=2)assert(!frames(1),"XIP_ROUND_ROBIN")
    }
    assert(reads>=4 && commands>=4,"XIP_BOTH_PRODUCERS_PROGRESS")
    assert(frames.sliding(2).forall(p=>p.size<2 || p(0)!=p(1)),"XIP_ROUND_ROBIN")
  }
  test("simultaneously replenished producer queues alternate complete frames") {
    simulateRaw(new QspiScheduler)(exercise)
  }
  test("raw-command preference starvation is rejected") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new QspiScheduler {
        override protected def nextPreference(wasRead: Bool): Bool=false.B
      })(exercise)
    };assert(e.getMessage.contains("XIP_ROUND_ROBIN"))
  }
}
