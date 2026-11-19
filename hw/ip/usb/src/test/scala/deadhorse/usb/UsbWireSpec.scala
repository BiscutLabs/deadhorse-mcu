package deadhorse.usb

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class UsbWireSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t19/wire-simulation").toAbsolutePath
  }
  test("enumeration, descriptor retry and deferred address/configuration") {
    simulate(new UsbWireBench) { d=>
      val host=new UsbWireHost(d);host.initialize()
      assert(host.crc16(Seq.empty)==Seq(0,0));assert(host.crc5(0)==2)
      val device=Seq(18,1,0,2,2,0,0,8,0,0,0,0,0x10,1,0,0,0,1)
      assert(host.read(0,6,0x100,18,retryFirst=true)==device)
      host.write(0,5,5)
      val configuration=Seq(9,2,67,0,2,1,0,0x80,0x32,9,4,0,0,1,2,2,1,0,
        5,0x24,0,0x10,1,5,0x24,1,0,1,4,0x24,2,0,5,0x24,6,0,1,
        7,5,0x82,3,8,0,255,9,4,1,0,2,0x0a,0,0,0,7,5,1,2,16,0,0,7,5,0x81,2,16,0,0)
      assert(host.read(5,6,0x200,255,retryFirst=true)==configuration)
      host.setup(5,host.setupBytes(0,9,1,0,0));host.statusWrite(5,ack=false)
      assert(!host.bool(d.configured),"configuration committed before ACK")
      assert(host.read(5,6,0x100,18)==device)
      assert(!host.bool(d.configured),"replacement SETUP committed old configuration")
      host.write(5,9,1);assert(host.bool(d.configured))
      assert(host.read(5,8,0,1)==Seq(1))
      host.write(5,9,0);assert(!host.bool(d.configured))
    }
  }
  test("bulk bytes, stuffing, CRC rollback, ACK replay and session flush") {
    simulate(new UsbWireBench) { d=>
      val host=new UsbWireHost(d);host.initialize();host.write(0,5,5);host.write(5,9,1)
      val incoming=(0 until 64).map(i=>if(i%3==0)255 else (i*73)&255)
      val received=incoming.grouped(16).zipWithIndex.flatMap { case(bytes,index)=>
        val pid=if(index%2==0)host.DATA0 else host.DATA1
        host.token(host.OUT,5,1);host.idle(2);host.data(pid,bytes,badCrc=true)
        host.silence(500);assert(!host.bool(d.rxValid),"bad CRC published bytes")
        host.token(host.OUT,5,1);host.idle(2);host.data(pid,bytes)
        assert(host.receive()._1==host.ACK);host.idle(30)
        host.drain(bytes.size)
      }.toSeq
      assert(received==incoming,"OUT stream corrupted or reordered")
      host.idle(50);assert(!host.bool(d.rxValid),"OUT duplicated bytes")
      val outgoing=(0 until 64).map(i=>(i*117+31)&255)
      for(bytes<-outgoing.grouped(16)) {
        host.enqueue(bytes)
        host.token(host.IN,5,1);val first=host.receive()
        assert(first==(host.DATA0,bytes),s"IN packet mismatch $first")
        host.idle(4);host.token(host.IN,5,1)
        assert(host.receive()==first,"bulk lost-ACK replay changed")
        host.idle(2);host.packet(host.ACK);host.idle(30)
        // Each drained exact-MPS transfer still requires its terminal ZLP.
        host.token(host.IN,5,1);assert(host.receive()==(host.DATA1,Seq.empty),"missing exact-MPS terminal ZLP")
        host.idle(2);host.packet(host.ACK);host.idle(30)
        host.token(host.IN,5,1);assert(host.receive()._1==host.NAK,"ACK did not reclaim IN packet")
      }
      host.token(host.OUT,5,1);host.idle(2);host.data(host.DATA0,Seq(3,1,4,1,5))
      assert(host.receive()._1==host.ACK);host.enqueue(Seq(9,2,6,5))
      host.write(5,9,1);host.idle(30)
      assert(!host.bool(d.rxValid),"repeated configuration retained RX bytes")
      host.token(host.IN,5,1);assert(host.receive()._1==host.NAK,"repeated configuration retained TX bytes")
      d.vbus.poke(false.B)
      assert(!host.bool(d.oe)&& !host.bool(d.pullupEnable),"VBUS loss must immediately disable pads")
    }
  }
  test("wire-to-byte oracle rejects deliberate receive-data corruption") {
    simulate(new UsbWireBench(corrupt=true)) { d=>
      val h=new UsbWireHost(d);h.initialize();h.write(0,5,5);h.write(5,9,1)
      val bytes=Seq(0xa5,0,255,0x36)
      h.token(h.OUT,5,1);h.idle(2);h.data(h.DATA0,bytes);assert(h.receive()._1==h.ACK);h.idle(30)
      val observed=h.drain(bytes.length)
      val failure=intercept[org.scalatest.exceptions.TestFailedException] {
        assert(observed==bytes,"USB_DATA_ORACLE mismatch")
      }
      assert(failure.getMessage.contains("USB_DATA_ORACLE"))
    }
  }
  test("bulk packet buffers wrap, reject full packets, retry and flush on USB reset") {
    simulate(new UsbWireBench) { d=>
      val h=new UsbWireHost(d);h.initialize();h.write(0,5,5);h.write(5,9,1)
      val stream=(0 until 4).flatMap(round=>(0 until 64).map(i=>(i+round*47)&255))
      for((bytes,round)<-stream.grouped(16).zipWithIndex) {
        val pid=if(round%2==0)h.DATA0 else h.DATA1
        h.token(h.OUT,5,1);h.idle(2);h.data(pid,bytes);assert(h.receive()._1==h.ACK);h.idle(20)
        val nextPid=if(pid==h.DATA0)h.DATA1 else h.DATA0
        h.token(h.OUT,5,1);h.idle(2);h.data(nextPid,Seq.fill(8)(0xee));assert(h.receive()._1==h.NAK)
        assert(h.drain(bytes.size)==bytes,"full packet overwrite or ring wrap")
        h.idle(20);assert(!h.bool(d.rxValid))
      }
      h.enqueue(Seq(7,8,9));h.busReset();assert(!h.bool(d.rxValid) && !h.bool(d.configured))
      h.write(0,5,5);h.write(5,9,1);h.token(h.IN,5,1);assert(h.receive()._1==h.NAK)
    }
  }
  test("ACM control writes, malformed SETUP recovery, PID/token CRC rejection and directional clear-halt") {
    simulate(new UsbWireBench) { d=>
      val h=new UsbWireHost(d);h.initialize();h.write(0,5,5);h.write(5,9,1)
      h.setup(5,h.setupBytes(0x21,0x20,0,0,7))
      h.token(h.OUT,5,0);h.idle(2);h.data(h.DATA1,Seq(0,0xc2,1,0,0,0,8))
      assert(h.receive()._1==h.ACK);h.idle(4);h.statusWrite(5)
      assert(h.read(5,0x21,0,7,kind=0xa1)==Seq.fill(7)(0),"retained dummy line-coding contract")
      h.setup(5,h.setupBytes(0x21,0x22,3,0,0));h.statusWrite(5)
      for(header<-Seq(h.setupBytes(0xa5,0x21,0,0,7),h.setupBytes(0x80,6,0x100,0,18).take(7))) {
        h.setup(5,header);h.token(h.IN,5,0);assert(h.receive()._1==h.STALL)
        assert(h.read(5,8,0,1)==Seq(1),"new SETUP failed to recover from STALL")
      }
      val token=5|(1<<7);val payload=Seq(token&255,((token>>8)&7)|(h.crc5(token)<<3))
      h.packet(h.IN,payload,corruptPid=true);h.silence(300)
      h.packet(h.IN,Seq(payload.head,payload(1)^8));h.silence(300)
      h.enqueue(Seq(9,8,7))
      h.token(h.OUT,5,1);h.idle(2);h.data(h.DATA0,Seq(1,2,3));assert(h.receive()._1==h.ACK);h.idle(30)
      h.setup(5,h.setupBytes(2,1,0,1,0));h.statusWrite(5);h.idle(20)
      assert(!h.bool(d.rxValid),"OUT clear-halt retained receive bytes")
      h.token(h.IN,5,1);assert(h.receive()==(h.DATA0,Seq(9,8,7)),"OUT clear-halt destroyed opposite-direction TX")
      h.idle(2);h.packet(h.ACK);h.idle(20)
      h.token(h.OUT,5,1);h.idle(2);h.data(h.DATA0,Seq(4,5,6));assert(h.receive()._1==h.ACK);h.idle(20)
      h.enqueue(Seq(11,12));h.setup(5,h.setupBytes(2,1,0,0x81,0));h.statusWrite(5);h.idle(20)
      assert(h.drain(3)==Seq(4,5,6),"IN clear-halt destroyed opposite-direction RX")
      h.token(h.IN,5,1);assert(h.receive()._1==h.NAK,"IN clear-halt retained transmit bytes")
    }
  }
}
