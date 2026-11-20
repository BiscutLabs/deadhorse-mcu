package deadhorse.usb

import chisel3._
import chisel3.util._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** A deliberately wrong full-rate consumer, alongside the actual USB engine.
  * Its reference flag is the original packetFlag transition, driven by real SIE
  * outputs. No internal state or producer data is forced by the test.
  */
class UsbPreEnableObserver extends UsbEngine {
  val mismatchSeen=IO(Output(Bool()));val mismatchPhase=IO(Output(UInt(6.W)))
  withClockAndReset(clk,(!engineReset).asAsyncReset) {
    val original=RegNext(sie.io.in_ready_o && sie.io.endp_o===1.U,false.B)
    val originalConsumer=RegNext(original,false.B)
    val wrongConsumer=RegNext(in.consume,false.B)
    val consumedOnEnable=RegNext(cadence.enable,false.B)
    val seen=RegInit(false.B);val phase=RegInit(0.U(6.W))
    when(consumedOnEnable){assert(originalConsumer===wrongConsumer)}
    when(originalConsumer=/=wrongConsumer && !seen) {
      seen:=true.B
      phase:=Cat(cadence.enable,consumedOnEnable,original,in.consume,originalConsumer,wrongConsumer)
    }
    mismatchSeen:=seen;mismatchPhase:=phase
  }
}
class UsbPreEnableBench extends UsbWireBench(engineFactory=()=>new UsbPreEnableObserver) {
  val mismatchSeen=IO(Output(Bool()));val mismatchPhase=IO(Output(UInt(6.W)))
  mismatchSeen:=engine.asInstanceOf[UsbPreEnableObserver].mismatchSeen
  mismatchPhase:=engine.asInstanceOf[UsbPreEnableObserver].mismatchPhase
}
class UsbPreEnableSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t19/preenable-simulation").toAbsolutePath
  }
  test("real EP1 traffic rejects a consumer outside bitEnable") {
    simulate(new UsbPreEnableBench) { d=>
      val h=new UsbWireHost(d);h.initialize();h.write(0,5,5);h.write(5,9,1)
      h.enqueue(Seq(0x19,0x58,0xa5));h.token(h.IN,5,1)
      assert(h.receive()==(h.DATA0,Seq(0x19,0x58,0xa5)))
      assert(d.mismatchSeen.peek().litValue==1,"OFF_ENABLE_CONSUMER fault was not detected")
      println(s"OFF_ENABLE_CONSUMER rejected on real EP1 traffic; phase=${d.mismatchPhase.peek().litValue}")
    }
  }
}
