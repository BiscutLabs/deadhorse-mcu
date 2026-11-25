package deadhorse.top
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
/** Performance loading, actual RV32E execution and public bus/pad observations.
  * Loader-status fault retired under D93; boot/drain/key faults live in boot_control. */
class SocLiteSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t25/soc-simulation").toAbsolutePath
  }
  def high(v: Bool)=v.peek().litToBoolean
  def exercise(d: SocI1Peripherals): Unit={
    val io=new SocIoSpec
    io.reset(d)
    def tick(n: Int=1): Unit=io.tick(d,n)
    val mb=BigInt(0x40001000L)
    def read(a: BigInt)=io.good(d,d.main,a)
    def write(a: BigInt,v: BigInt): Unit={io.good(d,d.main,a,true,v);()}
    def reply(expected: Long): Unit={
      var n=0
      while((read(mb+12)&2)==0) {tick(8);n+=1;assert(n<100,"LITE_REPLY_DEADLINE")}
      assert(read(mb+8)==expected,"LITE_EXECUTION_ORACLE");write(mb+4,2)
    }
    assert(read(0x40000300L)==1,"LITE_INITIAL_HELD")
    d.pins.liteHalted.poke(false.B)
    io.drive(d.pins.lite,0x40001000L,true,0xdeadbeefL)
    tick(8);assert(!high(d.pins.lite.gnt) && !high(d.pins.lite.rvalid),"LITE_STANDIN_BYPASS")
    assert(read(mb+12)==5)
    val source=scala.io.Source.fromFile("build/t25/firmware/lite.hex")
    val image=try source.getLines().map(x=>java.lang.Long.parseUnsignedLong(x,16)).toVector finally source.close()
    image.zipWithIndex.foreach {case(w,i)=>write(0x30000000L+i*4,w)}
    assert(read(0x30000010L)==image(4),"LITE_GLOBAL_PROGRAM")
    write(0x40000304L,0x50455246L)
    assert(read(0x40000300L)==2,"LITE_RELEASE_STATUS")
    // The retired loader's post-START status transaction consumed >1000 AON
    // edges before this oracle. Let the unchanged 1000-tick timer elapse;
    // retain the original 100-poll reply deadline and all execution checks.
    tick(1000)
    reply(0x101) // Timer interrupt increments the retained counter from zero.
    tick(100);assert(read(0x40000300L)==2,"LITE_WFI_STATUS")
    d.pins.liteHalted.poke(true.B)
    assert(io.access(d,d.main,0x30000400L)._2,"LITE_RUNNING_OWNERSHIP")
    assert(io.access(d,d.main,0x30000000L,true,0)._2,"LITE_RUNNING_PROGRAM_WRITE")
    write(0x40000304L,0x50455246L) // Repeated release cannot restart the core.
    assert((read(0x40000308L)&1)==1,"LITE_REPEATED_RELEASE_ERROR")
    write(mb,0x200);write(mb+4,1);reply(0x202)
    // AON keeps its program/counter/WFI state while main's mailbox epoch resets.
    d.mainServiceReset_n.poke(false.B);tick(5);d.mainServiceReset_n.poke(true.B);tick(50)
    write(mb,0x300);write(mb+4,1);reply(0x303)
    assert(!high(d.pins.lite.gnt) && !high(d.pins.lite.rvalid),"LITE_STANDIN_BYPASS")
    // Common AON reset cancels the hart/fabric together and leaves SRAM intact.
    d.pins.aonServiceReset_n.poke(false.B);tick(5);d.pins.aonServiceReset_n.poke(true.B);tick(50)
    assert(read(0x30000400L)==3,"LITE_RESET_RETENTION")
    assert(read(0x30000010L)==image(4),"LITE_PROGRAM_RETENTION")
    assert(read(0x40000300L)==1,"LITE_SERVICE_HELD")
    tick(1200);assert(read(0x30000400L)==3,"LITE_RESET_AUTOSTART")
  }
  test("performance loads and releases real RV32E code; timer/mailbox IRQs and independent resets survive") {
    simulateRaw(new SocI1Peripherals(SocTestFiles.description,SocProduction.config(realUsb=false)))(exercise)
  }
}
