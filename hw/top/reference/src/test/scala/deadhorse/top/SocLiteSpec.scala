package deadhorse.top
import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Real loader wires, actual RV32E execution and public bus/pad observations. */
class SocLiteSpec extends AnyFunSuite with ChiselSim {
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
    var hostLow=false
    def wireStep(n: Int): Unit=for(_<-0 until n) {
      d.pins.recoverySda.poke((!hostLow && !high(d.pins.recoverySdaLow)).B);tick()
      d.pins.recoverySda.poke((!hostLow && !high(d.pins.recoverySdaLow)).B)
    }
    def line(scl: Boolean,low: Boolean): Unit={hostLow=low;d.pins.recoveryScl.poke(scl.B);wireStep(5)}
    def send(v: Int): Unit={
      for(bit<-7 to 0 by -1) {val low=(v&(1<<bit))==0;line(false,low);line(true,low);line(false,low)}
      line(false,false);line(true,false);assert(!high(d.pins.recoverySda),"LITE_LOADER_ACK");line(false,false)
    }
    def bytes(v: Long): Seq[Int]=(0 until 4).map(i=>((v>>>(8*i))&255).toInt)
    def command(op: Int,words: Long*): Unit={
      line(true,false);line(true,true);line(false,true);send(0x6a);send(op)
      words.flatMap(bytes).foreach(send)
      line(false,true);line(true,true);line(true,false);wireStep(8)
    }
    def loaderMode(): Long={
      line(true,false);line(true,true);line(false,true)
      Seq(0x6a,0,1,0,0).foreach(send) // SELECT loader service, word zero.
      line(true,false);line(true,true);line(false,true);send(0x6b)
      val result=(0 until 4).map {i=>
        var byte=0
        for(_<-0 until 8) {
          line(false,false);line(true,false);byte=(byte<<1)|(if(high(d.pins.recoverySda))1 else 0)
          line(false,false)
        }
        line(false,i<3);line(true,i<3);line(false,i<3);line(false,false)
        byte.toLong<<(8*i)
      }.reduce(_|_)
      line(false,true);line(true,true);line(true,false);wireStep(8);result
    }
    def reply(expected: Long): Unit={
      var n=0
      while((read(mb+12)&2)==0) {tick(8);n+=1;assert(n<100,"LITE_REPLY_DEADLINE")}
      assert(read(mb+8)==expected,"LITE_EXECUTION_ORACLE");write(mb+4,2)
    }
    // Invalid START cannot give the core ownership. The old external master and
    // its halted input are deliberately hostile throughout actual execution.
    command(5);assert(!high(d.pins.loaderProgrammed))
    d.pins.liteHalted.poke(false.B)
    io.drive(d.pins.lite,0x40001000L,true,0xdeadbeefL)
    tick(8);assert(!high(d.pins.lite.gnt) && !high(d.pins.lite.rvalid),"LITE_STANDIN_BYPASS")
    assert(read(mb+12)==5)
    val source=scala.io.Source.fromFile("build/t25/firmware/lite.hex")
    val image=try source.getLines().map(x=>java.lang.Long.parseUnsignedLong(x,16)).toVector finally source.close()
    val crc=new java.util.zip.CRC32;image.flatMap(bytes).foreach(crc.update)
    command(1,image.size*4,16,crc.getValue,0x10000,16,0,0,0x2025)
    image.zipWithIndex.foreach {case(w,i)=>command(2,i*4,w)};command(3)
    assert(high(d.pins.loaderProgrammed),"LITE_LOADER_COMMIT")
    assert(read(0x30000010L)==image(4),"LITE_GLOBAL_PROGRAM")
    command(6);assert(high(d.pins.loaderLocked),"LITE_LOADER_LOCK")
    assert(loaderMode()==3,"LITE_START_STATUS")
    reply(0x101) // Timer interrupt increments the retained counter from zero.
    tick(100);assert(loaderMode()==3,"LITE_WFI_STATUS")
    d.pins.liteHalted.poke(true.B)
    assert(io.access(d,d.main,0x30000800L)._2,"LITE_RUNNING_OWNERSHIP")
    command(5) // Repeated start cannot reset the running core's counter.
    write(mb,0x200);write(mb+4,1);reply(0x202)
    // AON keeps its program/counter/WFI state while main's mailbox epoch resets.
    d.mainServiceReset_n.poke(false.B);tick(5);d.mainServiceReset_n.poke(true.B);tick(50)
    write(mb,0x300);write(mb+4,1);reply(0x303)
    assert(!high(d.pins.lite.gnt) && !high(d.pins.lite.rvalid),"LITE_STANDIN_BYPASS")
    // Common AON reset cancels the hart/fabric together and leaves SRAM intact.
    d.pins.aonServiceReset_n.poke(false.B);tick(5);d.pins.aonServiceReset_n.poke(true.B);tick(50)
    assert(read(0x30000800L)==3,"LITE_RESET_RETENTION")
    assert(read(0x30000010L)==image(4),"LITE_PROGRAM_RETENTION")
    assert(high(d.pins.loaderLocked),"LITE_SERVICE_UNLOCK")
    tick(1200);assert(read(0x30000800L)==3,"LITE_RESET_AUTOSTART")
  }
  test("recovery START runs retained RV32E code, timer/mailbox IRQs and independent resets") {
    simulateRaw(new SocI1Peripherals(SocTestFiles.description,SocProduction.config(realUsb=false)))(exercise)
  }
  test("wrong START handoff status is rejected on the public loader wire") {
    val e=intercept[org.scalatest.exceptions.TestFailedException] {
      simulateRaw(new SocI1Peripherals(SocTestFiles.description,SocProduction.config(realUsb=false)) {
        override protected def loaderHalted(halted: Bool,starting: Bool): Bool=halted
      })(exercise)
    };assert(e.getMessage.contains("LITE_START_STATUS"))
  }
}
