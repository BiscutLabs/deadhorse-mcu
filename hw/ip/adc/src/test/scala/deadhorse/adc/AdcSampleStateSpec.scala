package deadhorse.adc

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class AdcSampleStateSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t27/publication-simulation").toAbsolutePath
  }
  def exercise(d: AdcSampleState): Unit={
    var latest=0;var serial=BigInt(0);var pending=List.empty[Int]
    val rng=new scala.util.Random(0xadc71L)
    val inputs=Seq((true,false,1,false),(true,true,2,false),(false,true,0,false),
      (true,false,3,false),(true,false,4,false))++Seq.fill(512)(
      (rng.nextBoolean(),rng.nextBoolean(),rng.nextInt(4096),rng.nextInt(31)==0))
    d.reset.poke(true.B);d.io.sample.poke(false.B);d.io.readAck.poke(false.B);d.io.value.poke(0.U);d.clock.step()
    for((sample,ack,value,reset)<-inputs) {
      d.reset.poke(reset.B);d.io.sample.poke(sample.B);d.io.readAck.poke(ack.B);d.io.value.poke(value.U)
      if(!reset) assert(d.io.overrun.peek().litToBoolean==(sample && pending.nonEmpty && !ack),"ADC_PUBLICATION_OVERRUN")
      if(reset) {latest=0;serial=0;pending=Nil}
      else {
        if(ack) pending=Nil
        if(sample) {latest=value;serial=(serial+1)%(BigInt(1)<<32);pending=List(value)}
      }
      d.clock.step()
      assert(d.io.raw.peek().litValue==latest,"ADC_PUBLICATION_RAW")
      assert(d.io.count.peek().litValue==serial,"ADC_PUBLICATION_COUNT")
      assert(d.io.unread.peek().litToBoolean==pending.nonEmpty,"ADC_PUBLICATION_ACK_PRIORITY")
    }
  }
  test("atomic raw publication, acknowledgement collision, overrun, hold and reset") {
    simulate(new AdcSampleState)(exercise)
  }
  test("oracle rejects acknowledgement that discards a simultaneously arriving sample") {
    simulate(new AdcSampleState {override protected def sampleUnread(ack: Bool): Bool= !ack}) { d=>
      val e=intercept[org.scalatest.exceptions.TestFailedException](exercise(d))
      assert(e.getMessage.contains("ADC_PUBLICATION_ACK_PRIORITY"))
    }
  }
  test("oracle rejects actual publication data corruption") {
    simulate(new AdcSampleState {override protected def capture(v: UInt): UInt=v^1.U}) { d=>
      val e=intercept[org.scalatest.exceptions.TestFailedException](exercise(d))
      assert(e.getMessage.contains("ADC_PUBLICATION_RAW"))
    }
  }
}
