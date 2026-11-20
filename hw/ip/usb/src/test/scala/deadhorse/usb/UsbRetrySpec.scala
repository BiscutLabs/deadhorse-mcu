package deadhorse.usb

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Packet identity is a host contract: an unacknowledged DATA packet must
  * repeat its PID, length and bytes even while the application queues more.
  */
class UsbRetrySpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t19/retry-simulation").toAbsolutePath
  }
  private def ack(h: UsbWireHost): Unit={h.idle(2);h.packet(h.ACK);h.idle(30)}
  private def packet(h: UsbWireHost): (Int,Seq[Int])={h.token(h.IN,5,1);h.receive()}
  test("short IN retry freezes payload while subsequent bytes queue") {
    simulate(new UsbWireBench) { d=>
      val h=new UsbWireHost(d);h.initialize();h.write(0,5,5);h.write(5,9,1)
      assert(packet(h)._1==h.NAK,"empty request must not lock future data")
      h.enqueue(Seq(0x7e));val first=packet(h)
      assert(first==(h.DATA0,Seq(0x7e)))
      h.enqueue(Seq(0xd6));assert(packet(h)==first,"RETRY_IDENTITY appended data")
      h.enqueue(Seq(0x39));assert(packet(h)==first,"RETRY_IDENTITY repeated retry")
      ack(h)
      assert(packet(h)==(h.DATA1,Seq(0xd6,0x39)),"ACK discarded queued next packet")
      ack(h);assert(packet(h)._1==h.NAK)
    }
  }
  test("maximum IN retry preserves queued byte through ACK and ring wrap") {
    simulate(new UsbWireBench) { d=>
      val h=new UsbWireHost(d);h.initialize();h.write(0,5,5);h.write(5,9,1)
      for(round<-0 until 3) {
        val bytes=(0 until 16).map(i=>(i+round*23)&255)
        h.enqueue(bytes);val first=packet(h);assert(first==(h.DATA0,bytes))
        h.enqueue(Seq(0x91+round));assert(packet(h)==first,"RETRY_IDENTITY full packet")
        ack(h);assert(packet(h)==(h.DATA1,Seq(0x91+round)),"full ACK lost staged byte")
        ack(h);assert(packet(h)._1==h.NAK)
      }
    }
  }
  test("terminal ZLP retries retain identity with newly queued data") {
    simulate(new UsbWireBench) { d=>
      val h=new UsbWireHost(d);h.initialize();h.write(0,5,5);h.write(5,9,1)
      val bytes=(0 until 16).map(i=>i*11)
      h.enqueue(bytes);assert(packet(h)==(h.DATA0,bytes));ack(h)
      val zlp=packet(h);assert(zlp==(h.DATA1,Seq.empty))
      h.idle(4);h.token(5,1,0);h.idle(4) // SOF must not retire the offered packet.
      assert(packet(h)==zlp,"RETRY_IDENTITY terminal ZLP became NAK")
      h.enqueue(Seq(0x62));assert(packet(h)==zlp,"RETRY_IDENTITY terminal ZLP gained data")
      ack(h);assert(packet(h)==(h.DATA0,Seq(0x62)),"ZLP ACK consumed queued data")
      ack(h);assert(packet(h)._1==h.NAK)
    }
  }
  test("pending data and ZLP flush on reset, reconfiguration and directional clear-halt") {
    simulate(new UsbWireBench) { d=>
      val h=new UsbWireHost(d);h.initialize();h.write(0,5,5);h.write(5,9,1)
      for(zlp<-Seq(false,true);flush<-Seq("reset","configure","clear-halt")) {
        h.enqueue(if(zlp) (0 until 16) else Seq(0x41))
        val first=packet(h);assert(first._1==h.DATA0)
        if(zlp){ack(h);assert(packet(h)==(h.DATA1,Seq.empty))}
        h.enqueue(Seq(0x82))
        flush match {
          case "reset"=>h.busReset();h.write(0,5,5);h.write(5,9,1)
          case "configure"=>h.write(5,9,1)
          case "clear-halt"=>h.setup(5,h.setupBytes(2,1,0,0x81,0));h.statusWrite(5)
        }
        h.idle(30);assert(packet(h)._1==h.NAK,s"$flush retained pending data/ZLP: zlp=$zlp")
        h.enqueue(Seq(0xc3));assert(packet(h)==(h.DATA0,Seq(0xc3)),s"$flush did not start a fresh packet")
        ack(h)
        // Restore DATA0 independently for the next scenario.
        h.write(5,9,1)
      }
    }
  }
  test("application write phase sweep preserves initial and retry packet boundaries") {
    simulate(new UsbWireBench) { d=>
      val h=new UsbWireHost(d) {
        private var at = -1L
        def injectAfter(samples: Int): Unit={at=elapsedSamples+samples}
        override def step(n: Int=1): Unit={
          var left=n
          while(left>0) {
            if(at==elapsedSamples) {
              assert(bool(d.txReady),"phase-sweep write unexpectedly backpressured")
              d.txData.poke(0xd6.U);d.txValid.poke(true.B);super.step(1)
              d.txValid.poke(false.B);at = -1L;left-=1
            } else {
              val count=if(at<0) left else math.min(left.toLong,at-elapsedSamples).toInt
              super.step(count);left-=count
            }
          }
        }
      }
      h.initialize();h.write(0,5,5);h.write(5,9,1)
      var pid=h.DATA0
      def acknowledged(): Unit={ack(h);pid=if(pid==h.DATA0)h.DATA1 else h.DATA0}
      // One-sample sweep crosses the token decode/request and ACK sampling
      // boundaries; the oracle uses only the first packet observed on wires.
      for(offset<-120 to 240) {
        h.enqueue(Seq(0x7e));h.injectAfter(offset)
        val first=packet(h)
        assert(first._1==pid && Set(Seq(0x7e),Seq(0x7e,0xd6)).contains(first._2))
        h.idle(60);assert(packet(h)==first,s"RETRY_IDENTITY request offset=$offset")
        acknowledged()
        if(first._2.size==1){assert(packet(h)==(pid,Seq(0xd6)));acknowledged()}
        assert(packet(h)._1==h.NAK)
      }
      for(offset<-120 to 240) {
        h.enqueue(Seq(0x7e));val first=packet(h);assert(first==(pid,Seq(0x7e)))
        h.injectAfter(offset);assert(packet(h)==first,s"RETRY_IDENTITY retry offset=$offset")
        h.idle(60);acknowledged()
        assert(packet(h)==(pid,Seq(0xd6)),s"retry lost concurrent write offset=$offset")
        acknowledged();assert(packet(h)._1==h.NAK)
      }
      for(offset<-0 to 140) {
        h.enqueue(Seq(0x7e));assert(packet(h)==(pid,Seq(0x7e)))
        h.injectAfter(offset);acknowledged()
        assert(packet(h)==(pid,Seq(0xd6)),s"ACK lost concurrent write offset=$offset")
        acknowledged();assert(packet(h)._1==h.NAK)
      }
    }
  }
}
