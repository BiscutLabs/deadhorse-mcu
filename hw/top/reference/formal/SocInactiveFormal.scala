package deadhorse.top

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files,Paths}

class BadInactivePads extends SocInactivePads {
  override protected def actuatorEnableValue: UInt=1.U(9.W)
}
class BadGpioPads extends SocInactivePads { override protected def gpioEnableValue: UInt=1.U(3.W) }
class BadTimerPads extends SocInactivePads { override protected def timerEnableValue: UInt=1.U(4.W) }
class BadAdcPads extends SocInactivePads { override protected def adcEnableValue: Bool=true.B }
class SocInactiveFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val pins=IO(new SocInactivePins)
  val d=Module(variant match {
    case "corrupt"=>new BadInactivePads
    case "gpio_fault"=>new BadGpioPads
    case "timer_fault"=>new BadTimerPads
    case "adc_fault"=>new BadAdcPads
    case _=>new SocInactivePads
  })
  d.pins<>pins
  // No reset masking or assumptions: constants must be safe at every sample.
  withClockAndReset(clock,false.B) {
    assert(!pins.qspiSclk && !pins.qspiSclkEnable && pins.qspiDqOut===0.U &&
      pins.qspiDqEnable===0.U && pins.qspiCs_n===3.U && pins.qspiCsEnable===0.U,"I1_QSPI_SAFE")
    assert(pins.actuatorOut===0.U && pins.actuatorEnable===0.U,"I1_ACTUATOR_SAFE")
    assert(!pins.jtagTdo && !pins.jtagTdoEnable,"I1_JTAG_SAFE")
    assert(pins.gpioOut===0.U && pins.gpioEnable===0.U,"I1_GPIO_SAFE")
    assert(pins.timerOut===0.U && pins.timerEnable===0.U,"I1_TIMER_SAFE")
    assert(!pins.adcSclk && pins.adcCs_n && !pins.adcSclkEnable && !pins.adcCsEnable,"I1_ADC_SAFE")
    if(variant=="cover") cover(pins.qspiDqIn.andR && pins.jtagTck && pins.jtagTms && pins.jtagTdi &&
      pins.imuDrdy && pins.gpioIn.andR && pins.timerIn.andR && pins.adcMiso)
  }
}
object EmitSocInactiveFormal extends App {
  require(args.length==1)
  for(variant<-Seq("correct","cover","corrupt","gpio_fault","timer_fault","adc_fault")) {
    val directory=Paths.get(args(0),variant);Files.createDirectories(directory)
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new SocInactiveFormal(variant)),
      Array("--target-dir",directory.toString),
      Array("--disable-all-randomization","--disable-opt","--lint-static-asserts=false",
        "--verification-flavor=immediate","--lower-to-core","-strip-debug-info"))
  }
}
