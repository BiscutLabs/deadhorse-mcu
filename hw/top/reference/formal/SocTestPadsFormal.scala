package deadhorse.top

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files,Paths}

class SocTestPadsFormal(fault: Boolean) extends RawModule {
  val clock=IO(Input(Clock()));val mode=IO(Input(Bool()));val scan=IO(Input(UInt(7.W)))
  val pins=IO(new SocPhysicalPins);val functional=IO(Flipped(new SocPhysicalPins))
  val d=Module[SocTestPads](if(fault) new SocTestPads {
    override protected def testUsbDrive: Bool=true.B
  } else new SocTestPads)
  d.testMode:=mode;d.scanOut:=scan;d.pins<>pins;d.functional<>functional
  def inputs(p: SocPhysicalPins): UInt=Cat(p.aonExtraIn,p.inactive.gpioIn,p.inactive.timerIn,
    p.inactive.qspiDqIn,p.inactive.jtagTck,p.inactive.jtagTms,p.inactive.jtagTdi,
    p.inactive.imuDrdy,p.uartRx.asUInt,p.spiMiso,p.i2cSclIn,p.i2cSdaIn,
    p.usbVbus,p.usbDpRx,p.usbDnRx)
  withClockAndReset(clock,false.B) {
    assert((mode || pins.asUInt===functional.asUInt) && inputs(pins)===inputs(functional))
    val p=pins;val q=p.inactive
    val safe=Seq(
      p.aonExtraOut===0.U,p.aonExtraEnable===0.U,q.gpioOut===0.U,q.gpioEnable===0.U,
      q.timerOut===0.U,q.timerEnable===0.U,q.actuatorOut===scan(6,3),q.actuatorEnable===15.U,
      q.jtagTdo,q.jtagTdoEnable,q.qspiDqOut===0.U,q.qspiDqEnable===0.U,
      !q.qspiSclk,!q.qspiSclkEnable,q.qspiCs_n===3.U,q.qspiCsEnable===0.U,
      p.uartTx.asUInt===scan(2,0),p.uartTxEnable.asUInt===7.U,
      !p.spiSclk,!p.spiMosi,p.spiCs_n===3.U,!p.spiEnable,
      !p.i2cSclLow,!p.i2cSdaLow,!p.i2cEnable,
      !p.usbDpTx,!p.usbDnTx,!p.usbTxEnable,!p.usbPullup,
      d.scanIn===Cat(q.timerIn,q.gpioIn)).reduce(_&&_)
    assert(!mode || safe)
    cover(mode && scan==="h55".U)
  }
}

object EmitSocTestPadsFormal extends App {
  for(fault<-Seq(false,true)) {
    val path=Paths.get(args(0),if(fault) "fault" else "correct");Files.createDirectories(path)
    ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new SocTestPadsFormal(fault)),
      Array("--target-dir",path.toString),Array("--disable-all-randomization","--disable-opt",
        "--verification-flavor=immediate","--lower-to-core","--strip-debug-info"))
  }
}
