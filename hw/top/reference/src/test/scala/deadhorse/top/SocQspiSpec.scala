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
      def lite(a: Int,w: Boolean=false,v: Long=0)=io.good(d,d.pins.lite,base+a,w,v)
      def main(a: Int,w: Boolean=false,v: Long=0)=io.good(d,d.main,base+a,w,v)
      assert(io.access(d,d.main,base)._2,"QSPI_SOC_OWNER")
      lite(8,true,6);lite(4,true,255);lite(36,true,0x4f574e01L)
      assert(io.access(d,d.pins.lite,base)._2);assert(main(8)==6 && main(28)==2)
      main(20,true,0x51535049L)
      assert(pins.qspiCs_n.peek().litValue==2 && pins.qspiCsEnable.peek().litValue==3,"QSPI_SOC_PADS")
      // Performance reset supervision and independent AON service reset preserve main transfer.
      val perf=BigInt(0x40000100L)
      io.good(d,d.main,perf,true,64);io.good(d,d.main,perf+12,true,0x57445354L)
      var sawReset=false
      for(_<-0 until 100) {
        tick();sawReset ||= high(d.supervision.get.performanceReset)
        assert(pins.qspiCs_n.peek().litValue==2,"QSPI_PERFORMANCE_ABORT")
      }
      assert(sawReset,"QSPI_WATCHDOG_TRIGGER")
      d.pins.aonServiceReset_n.poke(false.B);tick(3)
      assert(pins.qspiCs_n.peek().litValue==2,"QSPI_AON_ABORT")
      d.pins.aonServiceReset_n.poke(true.B);tick(8)
      assert(high(d.mainHold) && high(d.pins.mainDemand),"QSPI_SOC_DEMAND")
      var cycles=0
      while(pins.qspiCs_n.peek().litValue!=3) {tick();cycles+=1;assert(cycles<5000)}
      tick(260);assert(main(28)==2 && (main(32)&1)==1)
      // Reset with main stopped must disable outputs immediately and restore lite ownership.
      main(20,true,0x51535049L);assert(pins.qspiCs_n.peek().litValue==2)
      d.mainServiceReset_n.poke(false.B)
      assert(pins.qspiCsEnable.peek().litValue==0 && pins.qspiDqEnable.peek().litValue==0,"QSPI_SOC_RESET")
      tick(3);d.mainServiceReset_n.poke(true.B);tick(40)
      assert(io.access(d,d.main,base)._2 && lite(28)==0 && lite(32)==0)
      assert(io.access(d,d.main,0x10000000L)._2,"QSPI_XIP_STUB")
  }
  test("lite bridge ownership handoff, shared service containment and physical pin binding") {
    simulateRaw(new SocPeripheralBusTest(SocTestFiles.description,SocProduction.config(realUsb=false)))(exercise)
  }
  test("wrongly widening QSPI reset to the AON service cohort is rejected") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new SocPeripheralBusTest(SocTestFiles.description,SocProduction.config(realUsb=false)) {
        override protected def qspiServiceReset(main: Bool,aon: Bool): Bool=main && aon
      })(exercise)
    };assert(e.getMessage.contains("QSPI_AON_ABORT"))
  }
}
