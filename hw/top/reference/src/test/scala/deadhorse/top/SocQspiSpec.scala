package deadhorse.top
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class SocQspiSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t29/soc-simulation").toAbsolutePath
  }
  def exercise(d: SocI1Peripherals): Unit={
      val io=new SocIoSpec
      d.performanceReady.get.poke(true.B);d.dmaMemory.get.gnt.poke(false.B);d.dmaMemory.get.rvalid.poke(false.B)
      d.dmaMemory.get.rdata.poke(0.U);d.dmaMemory.get.err.poke(false.B);io.reset(d)
      val base=BigInt(0x40013000L);val pins=d.pins.inactive
      def tick(n: Int=1): Unit=io.tick(d,n)
      def high(b: Bool)=b.peek().litToBoolean
      def main(a: Int,w: Boolean=false,v: Long=0)=io.good(d,d.main,base+a,w,v)
      assert(io.access(d,d.pins.lite,base)._2,"QSPI_SOC_OWNER")
      main(8,true,6);main(4,true,255);main(36,true,0x4f574e01L)
      assert(io.access(d,d.pins.lite,base)._2);assert(main(8)==6 && main(28)==2)
      main(20,true,0x51535049L)
      assert(pins.qspiCs_n.peek().litValue==2 && pins.qspiCsEnable.peek().litValue==3,"QSPI_SOC_PADS")
      // Performance watchdog is warm and must abort an active transfer even
      // with main stopped. No surviving-QSPI ROM drain is required under T41.
      tick(520);d.pins.clockControl.stable.poke(true.B);tick(8)
      val perf=BigInt(0x40000100L)
      io.good(d,d.main,perf,true,64);io.good(d,d.main,perf+12,true,0x57445354L)
      var elapsed=0
      while(!high(d.supervision.get.performanceReset)) {
        d.pins.aonClock.step();elapsed+=1;assert(elapsed<100,"QSPI_WATCHDOG_TRIGGER")
      }
      assert(pins.qspiCsEnable.peek().litValue==0 && pins.qspiDqEnable.peek().litValue==0,"QSPI_WARM_ABORT")
      tick(40);assert(main(28)==2 && main(32)==0 && main(8)==0)
      assert(io.access(d,d.pins.lite,base)._2,"QSPI_SOC_OWNER")
      main(8,true,6);main(4,true,255);main(20,true,0x51535049L)
      assert(high(d.mainHold) && high(d.pins.mainDemand),"QSPI_SOC_DEMAND")
      var cycles=0
      while(pins.qspiCs_n.peek().litValue!=3) {tick();cycles+=1;assert(cycles<5000)}
      tick(260);assert(main(28)==2 && (main(32)&1)==1)
      // Reset with main stopped must disable outputs immediately and restore performance ownership.
      main(20,true,0x51535049L);assert(pins.qspiCs_n.peek().litValue==2)
      d.warmReset_n.poke(false.B)
      assert(pins.qspiCsEnable.peek().litValue==0 && pins.qspiDqEnable.peek().litValue==0,"QSPI_SOC_RESET")
      tick(3);d.warmReset_n.poke(true.B);tick(40)
      assert(io.access(d,d.pins.lite,base)._2 && main(28)==2 && main(32)==0)
      assert(io.access(d,d.main,0x10000000L)._2,"QSPI_XIP_STUB")
  }
  test("performance-owned QSPI, warm abort and physical pin binding") {
    simulateRaw(new SocPeripheralBusTest(SocTestFiles.description,SocProduction.config(realUsb=false)))(exercise)
  }
  test("wrongly retaining QSPI across warm reset is rejected") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new SocPeripheralBusTest(SocTestFiles.description,SocProduction.config(realUsb=false)) {
        override protected def qspiServiceReset(main: Bool,aon: Bool): Bool=coldReset_n
      })(exercise)
    };assert(e.getMessage.contains("QSPI_WARM_ABORT"))
  }
}
