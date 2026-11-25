package deadhorse.top

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.{Files,Paths}
import org.scalatest.funsuite.AnyFunSuite

/** Early PLAN05 measurement at the production CPU boundary. Actual lite hart,
  * memories, fabrics and peripherals; clock-boundary acknowledgements are a
  * test model. This does not replace the complete two-core dormant test. */
class SocWatcherPathSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan05/watcher-path/simulation").toAbsolutePath
  }
  test("real AON watcher checks radio packets with main and USB clocks stopped") {
    simulateRaw(new SocI1Peripherals(SocTestFiles.description,SocProduction.config(realUsb=false))) {d=>
      val io=new SocIoSpec
      def high(b: Bool)=b.peek().litToBoolean
      d.pins.aonExtraIn.poke(0.U);io.reset(d)
      d.performanceReset_n.poke(true.B)
      io.tick(d,600);d.pins.clockControl.stable.poke(true.B);io.tick(d,12)
      assert(high(d.pins.clockControl.authorized),"WATCHER_CLOCK_START")
      def write(a: Long,v: BigInt): Unit={io.good(d,d.main,BigInt(a),true,v);()}
      val image=Files.readAllBytes(Paths.get("build/plan05/watcher-opt05/watcher.bin"))
      val receipt=ujson.read(Files.readString(Paths.get("build/plan05/watcher-opt05/measurement.json")))
      def hash(path: String)=SocDebugLint.digest(Files.readAllBytes(Paths.get(path)))
      require(hash("build/plan05/watcher-opt05/watcher.bin")==receipt("artifacts")("watcher.bin").str,"WATCHER_BINARY_DRIFT")
      for((path,digest)<-receipt("sources").obj if path.startsWith("sw/lite/watcher/"))
        require(hash(path)==digest.str,s"WATCHER_FIRMWARE_SOURCE_DRIFT $path")
      require(image.length<=1024)
      for((bytes,i)<-image.grouped(4).zipWithIndex) {
        val value=bytes.zipWithIndex.map {case(b,n)=>BigInt(b&255)<<(8*n)}.foldLeft(BigInt(0))(_|_)
        write(0x30000000L+4*i,value)
      }
      write(0x40000304L,BigInt("50455246",16));io.tick(d,2400)
      assert(d.pins.aonExtraEnable.peek().litValue.testBit(2) && d.pins.aonExtraOut.peek().litValue.testBit(2),"WATCHER_RADIO_POWER")
      assert(d.pins.inactive.gpioEnable.peek().litValue==3,"WATCHER_SPI_MUX")
      d.pins.clockControl.coreIdle.poke(true.B)
      write(0x40000404L,64);write(0x4000041cL,1);write(0x40000400L,1)
      var stop=0
      while(high(d.pins.clockControl.gateRequest)) {io.tick(d);stop+=1;assert(stop<256,"WATCHER_STOP_HOLDS")}
      d.pins.clockControl.closed.poke(true.B);d.pins.clockControl.stable.poke(false.B)
      d.pins.aonClock.step(8);assert(!high(d.pins.clockControl.oscillatorOn),"WATCHER_OSC_OFF")
      def crc(bytes: Seq[Int]): Int={
        var value=0xffff
        for(b<-bytes) {value^=b<<8;for(_<-0 until 8) value=if((value&0x8000)!=0) ((value<<1)^0x1021)&0xffff else (value<<1)&0xffff}
        value
      }
      def packet(kind: Int): Vector[Int]={
        val body=Vector(if(kind==0) 0x49 else 0x48,0x44,1,7,0x12,0x34)
        val sum=crc(body)^(if(kind==1) 1 else 0)
        body++Vector(sum>>8,sum&255)
      }
      for(kind<-0 to 2) {
        val valid=kind==2
        val bytes=packet(kind);var selected=false;var oldClock=false;var bits=0;var frames=0;var cycles=0
        def miso(): Unit={
          val bit=if(bits<64) (bytes(bits/8)>>(7-bits%8))&1 else 0
          d.pins.inactive.gpioIn.poke((bit<<2).U)
        }
        def edge(): Unit={
          d.pins.aonClock.step();cycles+=1
          val cs= !d.pins.aonExtraOut.peek().litValue.testBit(0)
          val ck=d.pins.inactive.gpioOut.peek().litValue.testBit(0)
          assert(d.pins.aonExtraEnable.peek().litValue.testBit(0) &&
            (d.pins.inactive.gpioEnable.peek().litValue&3)==3,"WATCHER_SPI_PAD_DRIVE")
          if(cs && !selected) {bits=0;miso()}
          if(cs && selected && !oldClock && ck) {
            assert(!d.pins.inactive.gpioOut.peek().litValue.testBit(1),"WATCHER_RADIO_TX");bits+=1
          }
          if(cs && selected && oldClock && !ck) miso()
          if(!cs && selected) {frames+=1;assert(bits==64,"WATCHER_RADIO_FRAME")}
          selected=cs;oldClock=ck
          if(!valid) assert(!high(d.pins.clockControl.oscillatorOn),"INVALID_PACKET_WOKE_MAIN")
        }
        // Capture a pulse with no AON edge between its transitions.
        d.pins.aonExtraIn.poke(2.U);d.pins.aonIrq.peek()
        d.pins.aonExtraIn.poke(0.U);d.pins.aonIrq.peek()
        if(valid) {
          while(!high(d.pins.clockControl.oscillatorOn) && cycles<8000) edge()
          println(s"WATCHER_IRQ_TO_OSC_EN cycles=$cycles estimated_ms=${cycles*1000.0/32000}")
          assert(frames==1 && high(d.pins.clockControl.oscillatorOn),"VALID_PACKET_NO_WAKE")
          assert(cycles<=3200,"WATCHER_VALID_OVER_100MS")
        } else {
          for(_<-0 until 5000) edge()
          assert(frames==1 && !high(d.pins.aonDemand),"INVALID_PACKET_NOT_IDLE")
        }
      }
      // Complete the modeled clock handshake, then verify the public mailbox
      // and wake cause rather than treating any oscillator demand as success.
      var startup=0
      while(!high(d.pins.clockControl.qualify)) {d.pins.aonClock.step();startup+=1;assert(startup<1024)}
      d.pins.clockControl.stable.poke(true.B);d.pins.aonClock.step(4)
      assert(high(d.pins.clockControl.gateRequest));d.pins.clockControl.closed.poke(false.B)
      io.tick(d,16)
      assert(io.good(d,d.main,0x40000418L)==64,"WATCHER_MAILBOX_WAKE_CAUSE")
      assert((io.good(d,d.main,0x4000100cL)&2)!=0,"WATCHER_MAILBOX_PUBLISHED")
      assert(io.good(d,d.main,0x40001008L)==BigInt("57071234",16),"WATCHER_MAILBOX_PAYLOAD")
    }
  }
}
