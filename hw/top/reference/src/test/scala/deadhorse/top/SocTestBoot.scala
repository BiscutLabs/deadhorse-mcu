package deadhorse.top

import chisel3._
import chisel3.simulator.PeekPokeAPI

/** Real recovery-wire upload and real lite firmware release for focused tests.
  * Keep performance externally reset during setup so no observed work is lost.
  */
object SocTestBoot extends PeekPokeAPI {
  def release(d: SocCoreAssembly, tick: () => Unit): Unit = {
    val p=d.i1.get
    def high(b: Bool)=b.peek().litToBoolean
    d.mainCoreReset_n.poke(false.B)
    var hostLow=false
    def wireStep(n: Int): Unit=for(_<-0 until n) {
      p.recoverySda.poke((!hostLow && !high(p.recoverySdaLow)).B);tick()
      p.recoverySda.poke((!hostLow && !high(p.recoverySdaLow)).B)
    }
    wireStep(40)
    def line(scl: Boolean,low: Boolean): Unit={hostLow=low;p.recoveryScl.poke(scl.B);wireStep(5)}
    def send(v: Int): Unit={
      for(bit<-7 to 0 by -1) {val low=(v&(1<<bit))==0;line(false,low);line(true,low);line(false,low)}
      line(false,false);line(true,false);assert(!high(p.recoverySda),"PRODUCTION_BOOT_ACK");line(false,false)
    }
    def bytes(v: Long): Seq[Int]=(0 until 4).map(i=>((v>>>(8*i))&255).toInt)
    def command(op: Int,words: Long*): Unit={
      line(true,false);line(true,true);line(false,true);send(0x6a);send(op)
      words.flatMap(bytes).foreach(send)
      line(false,true);line(true,true);line(true,false);wireStep(8)
    }
    val source=scala.io.Source.fromFile("build/t28/firmware/lite.hex")
    val image=try source.getLines().map(x=>java.lang.Long.parseUnsignedLong(x,16)).toVector finally source.close()
    val crc=new java.util.zip.CRC32;image.flatMap(bytes).foreach(crc.update)
    command(1,image.size*4,16,crc.getValue,0x10000,16,0,0,0x2025)
    image.zipWithIndex.foreach {case(w,i)=>command(2,i*4,w)};command(3)
    assert(high(p.loaderProgrammed),"PRODUCTION_BOOT_IMAGE")
    command(6);assert(high(p.loaderLocked),"PRODUCTION_BOOT_LOCK")
    wireStep(5000)
    assert(!high(d.coreReady),"PRODUCTION_BOOT_EXTERNAL_HOLD")
    d.mainCoreReset_n.poke(true.B)
  }
}
