package deadhorse.timers
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class TimerDmaSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan05/timers/dma-simulation").toAbsolutePath
  }
  test("DMA collisions follow a per-channel pending-event model; seed 22") {
    simulateRaw(new TimerDmaRequests) {d=>
      d.reset_n.poke(false.B);d.events.poke(0.U);d.mask.poke(0.U);d.acknowledge.poke(0.U);d.clk.step()
      d.reset_n.poke(true.B)
      var pending=Set.empty[Int];val random=new scala.util.Random(22)
      for(_<-0 until 1000) {
        val event=random.nextInt(512);val mask=random.nextInt(512);val ack=random.nextInt(512)
        val over=(0 until 9).filter(i=>pending(i) && ((event>>i)&1)==1 && ((mask>>i)&1)==1 && ((ack>>i)&1)==0).toSet
        pending=(0 until 9).filter(i=>((mask>>i)&1)==1 && (((event>>i)&1)==1 || (pending(i) && ((ack>>i)&1)==0))).toSet
        d.events.poke(event.U);d.mask.poke(mask.U);d.acknowledge.poke(ack.U);d.clk.step()
        assert(d.request.peek().litValue==pending.toSeq.map(1<<_).sum)
        assert(d.overrun.peek().litValue==over.toSeq.map(1<<_).sum)
      }
    }
  }
}
