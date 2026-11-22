package deadhorse.adc

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class AdcRawSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t27/raw-simulation").toAbsolutePath
  }
  def high(x: Bool): Boolean=x.peek().litToBoolean
  def initialize(d: ClockedSpiAdc): Unit={
    d.io.allow.poke(true.B);d.io.start.poke(false.B);d.io.miso.poke(false.B)
    d.reset.poke(true.B);d.clock.step(2);d.reset.poke(false.B)
    assert(!high(d.io.busy) && !high(d.io.done) && !high(d.io.primed) && high(d.io.csN))
  }
  def frame(d: ClockedSpiAdc,word: Int,half: Int,first: Boolean): Unit={
    d.io.miso.poke(((word & 0x8000)!=0).B)
    d.io.start.poke(true.B);d.clock.step();d.io.start.poke(false.B)
    assert(!high(d.io.csN) && high(d.io.busy))
    var rises=0;var falls=0;var previous=false
    for(edge<-1 to 32*half) {
      // Repeated requests during active receive cannot create an extra frame.
      d.io.start.poke((edge%7==0).B)
      d.clock.step()
      val current=high(d.io.sclk)
      if(current && !previous) rises+=1
      if(!current && previous) {
        falls+=1
        if(falls<16) d.io.miso.poke(((word & (1<<(15-falls)))!=0).B)
      }
      assert(current==((edge/half)%2==1),"ADC_RAW_CLOCK_CADENCE")
      assert(high(d.io.done)==(edge==32*half),"ADC_RAW_COMPLETION")
      assert(high(d.io.result.valid)==(!first && edge==32*half),"ADC_RAW_DISCARD")
      previous=current
    }
    assert(rises==16 && falls==16 && high(d.io.csN) && high(d.io.busy))
    assert(d.io.result.bits.value.peek().litValue==(word & 4095),"ADC_RAW_DATA")
    assert(!high(d.io.result.bits.calibrated))
    d.io.start.poke(true.B);d.clock.step() // Completion still rejects START.
    d.io.start.poke(false.B)
    assert(!high(d.io.done) && !high(d.io.result.valid) && !high(d.io.busy) && high(d.io.primed))
    for(_<-0 until 13) {
      d.clock.step();assert(high(d.io.csN) && !high(d.io.done) && !high(d.io.result.valid))
      assert(d.io.result.bits.value.peek().litValue==(word & 4095),"ADC_RAW_HELD")
    }
  }
  for(half<-Seq(4,5)) test(s"raw frames, arbitrary prefix, completion and reset at halfperiod $half") {
    simulate(new ClockedSpiAdc(AdcParameters(halfPeriodCycles=half),autonomous=false,rawOnly=true)) { d=>
      initialize(d)
      val rng=new scala.util.Random(0xadc27L)
      val words=Seq(0,65535,0xa001,0x5800)++Seq.fill(24)(rng.nextInt(65536))
      for((word,index)<-words.zipWithIndex) frame(d,word,half,index==0)
      d.io.start.poke(true.B);d.clock.step();d.io.start.poke(false.B);d.clock.step(half*9)
      initialize(d);frame(d,0xfabc,half,first=true);frame(d,0x0123,half,first=false)
      d.io.allow.poke(false.B);d.io.start.poke(true.B);d.clock.step(32*half+2)
      assert(high(d.io.csN) && !high(d.io.done) && !high(d.io.busy),"ADC_RAW_DISABLED")
    }
  }
  test("raw wire oracle rejects actual captured-code corruption") {
    simulate(new ClockedSpiAdc(AdcParameters(halfPeriodCycles=4),autonomous=false,rawOnly=true) {
      override protected def rawResult(v: UInt): UInt=v^1.U
    }) { d=>
      initialize(d)
      val failure=intercept[org.scalatest.exceptions.TestFailedException] {frame(d,0x1234,4,first=true)}
      assert(failure.getMessage.contains("ADC_RAW_DATA"))
    }
  }
}
