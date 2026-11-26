package deadhorse.top

import chisel3._
import chisel3.util._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Aggregate stimulus covers every bit in each direction; the test-mode oracle
  * explicitly lists package-visible ownership from the reviewed contract.
  */
class SocTestPadsBench(fault: Boolean=false) extends RawModule {
  val mode=IO(Input(Bool()));val scan=IO(Input(UInt(7.W)))
  val value=IO(Input(Bool()))
  val seen=IO(Output(UInt(7.W)));val pins=IO(new SocPhysicalPins)
  val d=Module[SocTestPads](if(fault) new SocTestPads {override protected def testUsbDrive: Bool=true.B} else new SocTestPads)
  d.testMode:=mode;d.scanOut:=scan;seen:=d.scanIn
  d.pins<>pins
  // Functional outputs use opposite data/enables in each pass. Inputs are
  // separately driven through the real pad bundle in the test.
  d.functional.aonExtraOut:=Fill(3,value);d.functional.aonExtraEnable:=Fill(3,value)
  val f=d.functional.inactive
  f.gpioOut:=Fill(3,value);f.gpioEnable:=Fill(3,value)
  f.timerOut:=Fill(4,value);f.timerEnable:=Fill(4,value)
  f.actuatorOut:=Fill(9,value);f.actuatorEnable:=Fill(9,value)
  f.jtagTdo:=value;f.jtagTdoEnable:=value
  f.qspiDqOut:=Fill(4,value);f.qspiDqEnable:=Fill(4,value)
  f.qspiSclk:=value;f.qspiSclkEnable:=value;f.qspiCs_n:=Fill(2,value);f.qspiCsEnable:=Fill(2,value)
  for(i<-0 until 3) {d.functional.uartTx(i):=value;d.functional.uartTxEnable(i):=value}
  d.functional.spiSclk:=value;d.functional.spiMosi:=value;d.functional.spiCs_n:=Fill(2,value);d.functional.spiEnable:=value
  d.functional.i2cSclLow:=value;d.functional.i2cSdaLow:=value;d.functional.i2cEnable:=value
  d.functional.usbDpTx:=value;d.functional.usbDnTx:=value;d.functional.usbTxEnable:=value;d.functional.usbPullup:=value
}

class SocTestPadsSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t37/pads-simulation").toAbsolutePath
  }
  def exercise(d: SocTestPadsBench): Unit={
      d.pins.aonExtraIn.poke(0.U);d.pins.inactive.qspiDqIn.poke(0.U)
      d.pins.inactive.jtagTck.poke(false.B);d.pins.inactive.jtagTms.poke(false.B)
      d.pins.inactive.jtagTdi.poke(false.B);d.pins.inactive.imuDrdy.poke(false.B)
      for(i<-0 until 3) d.pins.uartRx(i).poke(true.B)
      d.pins.spiMiso.poke(false.B);d.pins.i2cSclIn.poke(true.B);d.pins.i2cSdaIn.poke(true.B)
      d.pins.usbVbus.poke(false.B);d.pins.usbDpRx.poke(false.B);d.pins.usbDnRx.poke(false.B)
      for(mode<-Seq(false,true);v<-Seq(false,true);scan<-0 until 128) {
        d.mode.poke(mode.B);d.value.poke(v.B);d.scan.poke(scan.U)
        d.pins.inactive.gpioIn.poke((scan&7).U);d.pins.inactive.timerIn.poke((scan>>3).U)
        d.seen.expect(scan.U)
        def word(width: Int): UInt=(if(v) (1<<width)-1 else 0).U
        val p=d.pins;val q=p.inactive
        q.gpioEnable.expect(if(mode) 0.U else word(3));q.timerEnable.expect(if(mode) 0.U else word(4))
        q.gpioOut.expect(if(mode) 0.U else word(3));q.timerOut.expect(if(mode) 0.U else word(4))
        q.actuatorOut.expect(if(mode) (scan>>3).U else word(9))
        q.actuatorEnable.expect(if(mode) 15.U else word(9))
        q.jtagTdo.expect((mode||v).B);q.jtagTdoEnable.expect((mode||v).B)
        q.qspiDqOut.expect(if(mode) 0.U else word(4));q.qspiDqEnable.expect(if(mode) 0.U else word(4))
        q.qspiSclk.expect((!mode&&v).B);q.qspiSclkEnable.expect((!mode&&v).B)
        q.qspiCs_n.expect(if(mode) 3.U else word(2));q.qspiCsEnable.expect(if(mode) 0.U else word(2))
        p.aonExtraOut.expect(if(mode) 0.U else word(3));p.aonExtraEnable.expect(if(mode) 0.U else word(3))
        for(i<-0 until 3) {
          p.uartTx(i).expect((if(mode) ((scan>>i)&1)==1 else v).B)
          p.uartTxEnable(i).expect((mode||v).B)
        }
        p.spiSclk.expect((!mode&&v).B);p.spiMosi.expect((!mode&&v).B)
        p.spiCs_n.expect(if(mode) 3.U else word(2));p.spiEnable.expect((!mode&&v).B)
        p.i2cSclLow.expect((!mode&&v).B);p.i2cSdaLow.expect((!mode&&v).B);p.i2cEnable.expect((!mode&&v).B)
        p.usbDpTx.expect((!mode&&v).B);p.usbDnTx.expect((!mode&&v).B)
        p.usbTxEnable.expect((!mode&&v).B,"SCAN_USB_DRIVE_SAFE");p.usbPullup.expect((!mode&&v).B)
      }
  }
  test("pad ownership persists in test mode for every scan pattern and functional drive value") {
    simulateRaw(new SocTestPadsBench)(exercise)
  }
  test("negative control: USB drive left enabled is caught") {
    val e=intercept[Throwable] {simulateRaw(new SocTestPadsBench(fault=true))(exercise)}
    assert(Iterator.iterate(e)(_.getCause).takeWhile(_!=null)
      .exists(x=>Option(x.getMessage).exists(_.contains("SCAN_USB_DRIVE_SAFE"))))
  }
}
