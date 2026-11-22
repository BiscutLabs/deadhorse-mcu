package deadhorse.top

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

object SocInactiveTestInputs extends chisel3.simulator.PeekPokeAPI {
  def tieOff(p: SocInactivePins): Unit = {
    p.qspiDqIn:=0.U;p.jtagTck:=false.B;p.jtagTms:=false.B;p.jtagTdi:=false.B;p.imuDrdy:=false.B
    p.gpioIn:=0.U;p.timerIn:=0.U;p.adcMiso:=false.B
  }
  def drive(p: SocInactivePins,n: Int): Unit = {
    p.qspiDqIn.poke((n&15).U);p.jtagTck.poke(((n&16)!=0).B)
    p.jtagTms.poke(((n&32)!=0).B);p.jtagTdi.poke(((n&64)!=0).B);p.imuDrdy.poke(((n&128)!=0).B)
    p.gpioIn.poke(((n>>8)&7).U);p.timerIn.poke(((n>>11)&15).U);p.adcMiso.poke(((n&32768)!=0).B)
  }
  def check(p: SocInactivePins): Unit = {
    assert(p.qspiDqOut.peek().litValue==0 && p.qspiDqEnable.peek().litValue==0,"I1_QSPI_SAFE")
    assert(!p.qspiSclk.peek().litToBoolean && !p.qspiSclkEnable.peek().litToBoolean,"I1_QSPI_SAFE")
    assert(p.qspiCs_n.peek().litValue==3 && p.qspiCsEnable.peek().litValue==0,"I1_QSPI_SAFE")
    assert(p.actuatorOut.peek().litValue==0 && p.actuatorEnable.peek().litValue==0,"I1_ACTUATOR_SAFE")
    assert(!p.jtagTdo.peek().litToBoolean && !p.jtagTdoEnable.peek().litToBoolean,"I1_JTAG_SAFE")
    assert(p.gpioOut.peek().litValue==0 && p.gpioEnable.peek().litValue==0,"I1_GPIO_SAFE")
    assert(p.timerOut.peek().litValue==0 && p.timerEnable.peek().litValue==0,"I1_TIMER_SAFE")
    assert(!p.adcSclk.peek().litToBoolean && p.adcCs_n.peek().litToBoolean &&
      !p.adcSclkEnable.peek().litToBoolean && !p.adcCsEnable.peek().litToBoolean,"I1_ADC_SAFE")
  }
}

class SocInactiveSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t20/i1/inactive-simulation").toAbsolutePath
  }
  test("I1 elaboration rejects YAML width drift at the physical stub boundary") {
    for((name,width)<-Seq("qspi_dq"->3,"gpio"->2,"timer"->3)) {
    val path=os.Path(s"build/t20/i1/inactive-width-fault-$name.json",os.pwd)
    val document=ujson.read(os.read(os.Path("build/t20/map/soc.json",os.pwd)))
    document("pins")(name)("width")=width
    os.write.over(path,ujson.write(document))
    val e=intercept[IllegalArgumentException] {
      _root_.circt.stage.ChiselStage.emitCHIRRTL(new SocI1Peripherals(new SocDescription(path.toString),SocProduction.config(realUsb=false)))
    }
    assert(e.getMessage.contains(s"I1 inactive port width differs: $name"))
    }
  }
  test("inactive pads remain safe through exhaustive original and new input-bank sweeps without service clocks") {
    simulateRaw(new SocInactivePads) { d =>
      for(n<-0 until 256) {SocInactiveTestInputs.drive(d.pins,n);SocInactiveTestInputs.check(d.pins)}
      for(n<-0 until 256) {SocInactiveTestInputs.drive(d.pins,(n<<8)|0xa5);SocInactiveTestInputs.check(d.pins)}
    }
  }
  test("the safety oracle rejects an actual enabled actuator output") {
    simulateRaw(new SocInactivePads {
      override protected def actuatorEnableValue: UInt=1.U(9.W)
    }) { d =>
      SocInactiveTestInputs.drive(d.pins,0)
      val e=intercept[AssertionError] {SocInactiveTestInputs.check(d.pins)}
      assert(e.getMessage.contains("I1_ACTUATOR_SAFE"))
    }
  }
  for(group<-Seq("GPIO","TIMER","ADC")) test(s"the safety oracle rejects an actual enabled $group output") {
    simulateRaw(new SocInactivePads {
      override protected def gpioEnableValue: UInt=(if(group=="GPIO") 1 else 0).U(3.W)
      override protected def timerEnableValue: UInt=(if(group=="TIMER") 1 else 0).U(4.W)
      override protected def adcEnableValue: Bool=(group=="ADC").B
    }) { d =>
      SocInactiveTestInputs.drive(d.pins,65535)
      val e=intercept[AssertionError] {SocInactiveTestInputs.check(d.pins)}
      assert(e.getMessage.contains(s"I1_${group}_SAFE"))
    }
  }
}
