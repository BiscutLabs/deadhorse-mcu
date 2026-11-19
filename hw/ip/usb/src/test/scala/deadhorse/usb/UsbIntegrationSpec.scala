package deadhorse.usb

import chisel3._
import deadhorse.lib.LocalBus
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Uses only public Usb ports. Application and AON edges are independently driven. */
class UsbIntegrationBench(included: Boolean=true) extends Module with UsbWirePorts {
  val app=IO(Input(Clock()));val aon=IO(Input(Clock()));val appReset_n=IO(Input(Bool()))
  val peerReset_n=IO(Input(Bool()));val bus=IO(new LocalBus);val owner=IO(Input(UInt(3.W)))
  val hostDrive=IO(Input(Bool()));val hostDp=IO(Input(Bool()));val hostDn=IO(Input(Bool()));val vbus=IO(Input(Bool()))
  // Stream ports are intentionally unavailable on the MMIO integration boundary.
  val txData=IO(Input(UInt(8.W)));val txValid=IO(Input(Bool()));val txReady=IO(Output(Bool()))
  val rxData=IO(Output(UInt(8.W)));val rxValid=IO(Output(Bool()));val rxReady=IO(Input(Bool()))
  val dp=IO(Output(Bool()));val dn=IO(Output(Bool()));val oe=IO(Output(Bool()))
  val pullupEnable=IO(Output(Bool()));val configured=IO(Output(Bool()))
  val wake=IO(Output(Bool()));val request=IO(Output(Bool()));val irq=IO(Output(Bool()))
  val d=Module(new Usb("build/t19/regmap/usb_regs.json",included=included))
  d.appClock:=app;d.usbClock:=clock;d.aonClock:=aon
  d.appReset_n:=appReset_n && !reset.asBool;d.usbReset_n:=peerReset_n && !reset.asBool;d.aonReset_n:= !reset.asBool
  d.bus<>bus;d.owner:=owner;d.vbus:=vbus
  d.dpRx:=Mux(d.txEnable,d.dpTx,Mux(hostDrive,hostDp,d.pullupEnable))
  d.dnRx:=Mux(d.txEnable,d.dnTx,Mux(hostDrive,hostDn,false.B))
  dp:=d.dpTx;dn:=d.dnTx;oe:=d.txEnable;pullupEnable:=d.pullupEnable
  wake:=d.wake;request:=d.usbClockRequest;irq:=d.irq
  txReady:=false.B;rxData:=0.U;rxValid:=false.B;configured:=false.B
}

class UsbIntegrationSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t19/integration-simulation").toAbsolutePath
  }
  test("MMIO byte crossings, stopped application wake, peer reset and reset owner handoff") {
    simulate(new UsbIntegrationBench) { d=>
      val h=new UsbWireHost(d,checkConfiguredReset=false)
      def high(b: Bool)=b.peek().litValue==1
      d.appReset_n.poke(true.B);d.peerReset_n.poke(true.B);d.owner.poke(2.U)
      d.bus.req.poke(false.B);d.bus.bits.addr.poke(0.U);d.bus.bits.we.poke(false.B)
      d.bus.bits.wdata.poke(0.U);d.bus.bits.be.poke(0.U);d.bus.bits.origin.poke(0.U)
      def step(): Unit={d.app.step();d.clock.step(3);d.aon.step()}
      def access(offset: Int,write: Boolean=false,value: Int=0,origin: Int=2):(Int,Boolean)={
        d.bus.req.poke(true.B);d.bus.bits.addr.poke((BigInt("40040800",16)+offset).U)
        d.bus.bits.we.poke(write.B);d.bus.bits.wdata.poke(value.U);d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(origin.U)
        var granted=false;var done=false;var data=0;var error=false
        for(_<-0 until 32 if !done) {
          val take=high(d.bus.req)&&high(d.bus.gnt)
          if(high(d.bus.rvalid)){assert(granted);done=true;data=d.bus.rdata.peek().litValue.toInt;error=high(d.bus.err)}
          step();if(take){assert(!granted);granted=true;d.bus.req.poke(false.B)}
        }
        assert(done);for(_<-0 until 4)step();(data,error)
      }
      def rd(offset: Int): Int={val(v,e)=access(offset);assert(!e);v}
      def wr(offset: Int,value: Int): Unit=assert(!access(offset,true,value)._2)
      h.initialize(()=>{for(_<-0 until 8)step();wr(0,1)})
      h.write(0,5,5);h.write(5,9,1)
      for(_<-0 until 10)step();assert((rd(0x10)&12)==12)
      val payload=Seq(0x31,0xa5,0xff,0,0x72)
      for(byte<-payload){assert((rd(0x10)&1)!=0);wr(4,byte)}
      h.idle(30);h.token(h.IN,5,1);assert(h.receive()==(h.DATA0,payload));h.idle(2);h.packet(h.ACK);h.idle(30)
      h.token(h.OUT,5,1);h.idle(2);h.data(h.DATA0,payload);assert(h.receive()._1==h.ACK);h.idle(30)
      // No application edges occur during the wire exchange or these AON edges.
      d.aon.step(8);assert(high(d.wake),"RX work failed to wake stopped application")
      val received=payload.map { _=>
        for(_<-0 until 16 if (rd(0x10)&2)==0)step()
        assert((rd(0x10)&2)!=0);val value=rd(0xc);assert(rd(0xc)==value);wr(8,1);value
      }
      assert(received==payload)
      wr(0x14,15);wr(8,2);for(_<-0 until 12)step()
      h.idle(36010);d.hostDrive.poke(true.B);d.hostDp.poke(false.B);d.hostDn.poke(true.B);h.step(12)
      d.aon.step(8);assert(high(d.wake),"host resume failed to wake stopped application")
      h.idle(10);for(_<-0 until 12)step();assert((rd(0x14)&8)!=0)
      wr(8,2);wr(0x14,15);for(_<-0 until 12)step()
      assert(!high(d.wake),"acknowledged wake did not clear")
      wr(4,0x99)
      d.peerReset_n.poke(false.B)
      assert(!high(d.oe) && !high(d.pullupEnable),"peer reset with stopped USB clock did not disable pads")
      d.app.step(3);d.peerReset_n.poke(true.B);for(_<-0 until 12)step()
      assert(rd(0)==0 && (rd(0x10)&3)==0,"peer reset retained transport state")
      d.appReset_n.poke(false.B);d.owner.poke(4.U);d.app.step(3);d.appReset_n.poke(true.B)
      for(_<-0 until 12)step()
      assert(access(0,true,1,2)._2);assert(!access(0,true,1,4)._2)
    }
  }
  test("omitted USB keeps pads and AON requests safe through resets and register writes") {
    simulate(new UsbIntegrationBench(included=false)) { d=>
      d.appReset_n.poke(true.B);d.peerReset_n.poke(true.B);d.owner.poke(0.U)
      d.bus.req.poke(false.B);d.bus.bits.addr.poke(0.U);d.bus.bits.we.poke(false.B)
      d.bus.bits.wdata.poke(0.U);d.bus.bits.be.poke(0.U);d.bus.bits.origin.poke(0.U)
      d.vbus.poke(true.B);d.hostDrive.poke(false.B);d.hostDp.poke(true.B);d.hostDn.poke(false.B)
      d.txData.poke(0.U);d.txValid.poke(false.B);d.rxReady.poke(false.B)
      d.reset.poke(true.B);d.clock.step(3);d.app.step(3);d.aon.step(3);d.reset.poke(false.B)
      d.app.step(8);d.bus.req.poke(true.B);d.bus.bits.addr.poke(0x40040800L.U)
      d.bus.bits.we.poke(true.B);d.bus.bits.wdata.poke(1.U);d.bus.bits.be.poke(15.U)
      d.app.step();d.bus.req.poke(false.B);d.app.step(8);d.aon.step(8);d.clock.step(20)
      assert(d.oe.peek().litValue==0 && d.pullupEnable.peek().litValue==0)
      assert(d.wake.peek().litValue==0 && d.request.peek().litValue==0)
    }
  }
}
