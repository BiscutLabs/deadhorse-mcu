package deadhorse.top

import chisel3._
import chisel3.util._

/** Manufacturing-only pad ownership; mode is unscanned and persists in capture.
  * Combinational clamps are intentional: scanned state must not delay safety.
  */
class SocTestPads extends RawModule {
  val functional=IO(Flipped(new SocPhysicalPins))
  val pins=IO(new SocPhysicalPins)
  val testMode=IO(Input(Bool()));val scanOut=IO(Input(UInt(7.W)))
  val scanIn=IO(Output(UInt(7.W)))
  protected def testUsbDrive: Bool=false.B
  functional<>pins
  scanIn:=Cat(pins.inactive.timerIn,pins.inactive.gpioIn)
  when(testMode) {
    pins.aonExtraOut:=0.U;pins.aonExtraEnable:=0.U
    pins.inactive.gpioOut:=0.U;pins.inactive.gpioEnable:=0.U
    pins.inactive.timerOut:=0.U;pins.inactive.timerEnable:=0.U
    pins.inactive.actuatorOut:=Cat(0.U(5.W),scanOut(6,3))
    pins.inactive.actuatorEnable:="h00f".U
    pins.inactive.jtagTdo:=true.B;pins.inactive.jtagTdoEnable:=true.B
    pins.inactive.qspiDqOut:=0.U;pins.inactive.qspiDqEnable:=0.U
    pins.inactive.qspiSclk:=false.B;pins.inactive.qspiSclkEnable:=false.B
    pins.inactive.qspiCs_n:=3.U;pins.inactive.qspiCsEnable:=0.U
    for(i<-0 until 3) {pins.uartTx(i):=scanOut(i);pins.uartTxEnable(i):=true.B}
    pins.spiSclk:=false.B;pins.spiMosi:=false.B;pins.spiCs_n:=3.U;pins.spiEnable:=false.B
    pins.i2cSclLow:=false.B;pins.i2cSdaLow:=false.B;pins.i2cEnable:=false.B
    pins.usbDpTx:=false.B;pins.usbDnTx:=false.B;pins.usbTxEnable:=testUsbDrive;pins.usbPullup:=false.B
  }
}
