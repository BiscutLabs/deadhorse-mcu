package deadhorse.top

import chisel3._

/** Provisional logical functions; physical pad assignment remains open. */
class SocInactivePins extends Bundle {
  val qspiDqIn=Input(UInt(4.W));val qspiDqOut=Output(UInt(4.W));val qspiDqEnable=Output(UInt(4.W))
  val qspiSclk=Output(Bool());val qspiSclkEnable=Output(Bool())
  val qspiCs_n=Output(UInt(2.W));val qspiCsEnable=Output(UInt(2.W))
  val actuatorOut=Output(UInt(9.W));val actuatorEnable=Output(UInt(9.W))
  val jtagTck=Input(Bool());val jtagTms=Input(Bool());val jtagTdi=Input(Bool())
  val jtagTdo=Output(Bool());val jtagTdoEnable=Output(Bool())
  val imuDrdy=Input(Bool())
  val gpioIn=Input(UInt(3.W));val gpioOut=Output(UInt(3.W));val gpioEnable=Output(UInt(3.W))
  val timerIn=Input(UInt(4.W));val timerOut=Output(UInt(4.W));val timerEnable=Output(UInt(4.W))
  val adcMiso=Input(Bool());val adcSclk=Output(Bool());val adcCs_n=Output(Bool())
  val adcSclkEnable=Output(Bool());val adcCsEnable=Output(Bool())
}

/** Static tie-offs remain safe even with every service clock stopped. */
class SocInactivePads extends RawModule {
  val pins=IO(new SocInactivePins)
  protected def actuatorEnableValue: UInt=0.U(9.W)
  protected def gpioEnableValue: UInt=0.U(3.W)
  protected def timerEnableValue: UInt=0.U(4.W)
  protected def adcEnableValue: Bool=false.B
  pins.qspiDqOut:=0.U;pins.qspiDqEnable:=0.U
  pins.qspiSclk:=false.B;pins.qspiSclkEnable:=false.B
  pins.qspiCs_n:=3.U;pins.qspiCsEnable:=0.U
  pins.actuatorOut:=0.U;pins.actuatorEnable:=actuatorEnableValue
  pins.jtagTdo:=false.B;pins.jtagTdoEnable:=false.B
  pins.gpioOut:=0.U;pins.gpioEnable:=gpioEnableValue
  pins.timerOut:=0.U;pins.timerEnable:=timerEnableValue
  pins.adcSclk:=false.B;pins.adcCs_n:=true.B
  pins.adcSclkEnable:=adcEnableValue;pins.adcCsEnable:=adcEnableValue
}
