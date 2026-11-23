package deadhorse.top

import chisel3._
import deadhorse.lib.LocalBus
import deadhorse.usb.{UsbWireHost,UsbWirePorts}
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Only public I1 MMIO and pads are exposed. No stream bypass or private tap.
  * Host serialization is the unchanged independent T19 wire model.
  */
class SocI1UsbBench extends Module with UsbWirePorts {
  val app=IO(Input(Clock()));val aon=IO(Input(Clock()))
  val mainReset_n=IO(Input(Bool()));val usbReset_n=IO(Input(Bool()));val aonReset_n=IO(Input(Bool()))
  val bus=IO(new LocalBus);val corruptRead=IO(Input(Bool()))
  val hostDrive=IO(Input(Bool()));val hostDp=IO(Input(Bool()));val hostDn=IO(Input(Bool()));val vbus=IO(Input(Bool()))
  // The wire-host interface contains optional stream pins; none reaches I1.
  val txData=IO(Input(UInt(8.W)));val txValid=IO(Input(Bool()));val txReady=IO(Output(Bool()))
  val rxData=IO(Output(UInt(8.W)));val rxValid=IO(Output(Bool()));val rxReady=IO(Input(Bool()))
  val dp=IO(Output(Bool()));val dn=IO(Output(Bool()));val oe=IO(Output(Bool()))
  val pullupEnable=IO(Output(Bool()));val configured=IO(Output(Bool()))
  val wake=IO(Output(Bool()));val demand=IO(Output(Bool()));val irq=IO(Output(UInt(15.W)))
  val d=Module(new SocI1Peripherals(SocTestFiles.description,SocProduction.config(realUsb=true)))
  d.performanceDebugMode:=false.B;d.performanceReset_n:=false.B
  SocTestPorts.tieIdle(d)
  SocInactiveTestInputs.tieOff(d.pins.inactive)
  d.mainClock:=app;d.coldReset_n:= !reset.asBool;d.warmReset_n:=true.B;d.mainServiceReset_n:=mainReset_n
  d.pins.aonClock:=aon;d.pins.usbClock:=clock
  d.pins.aonServiceReset_n:=aonReset_n;d.pins.usbServiceReset_n:=usbReset_n
  d.main<>bus
  // Deliberate fixture wiring fault, only on the RX register's returned byte.
  bus.rdata:=d.main.rdata ^ Mux(corruptRead && bus.bits.addr==="h4004080c".U,1.U,0.U)
  d.pins.lite.req:=false.B;d.pins.lite.bits:=0.U.asTypeOf(d.pins.lite.bits)
  d.pins.liteHalted:=true.B;d.pins.resetReason:=0.U;d.pins.crashCount:=0.U
  d.uartRx:=true.B;d.pins.uartRx.foreach(_:=true.B)
  d.pins.spiMiso:=false.B;d.pins.spiTimeNow:=0.U
  d.pins.i2cSclIn:=true.B;d.pins.i2cSdaIn:=true.B
  d.pins.recoveryScl:=true.B;d.pins.recoverySda:=true.B
  d.pins.usbVbus:=vbus
  d.pins.usbDpRx:=Mux(d.pins.usbTxEnable,d.pins.usbDpTx,Mux(hostDrive,hostDp,d.pins.usbPullup))
  d.pins.usbDnRx:=Mux(d.pins.usbTxEnable,d.pins.usbDnTx,Mux(hostDrive,hostDn,false.B))
  dp:=d.pins.usbDpTx;dn:=d.pins.usbDnTx;oe:=d.pins.usbTxEnable;pullupEnable:=d.pins.usbPullup
  wake:=d.pins.usbWake;demand:=d.pins.mainDemand;irq:=d.fastIrq
  txReady:=false.B;rxData:=0.U;rxValid:=false.B;configured:=false.B
}

class SocI1UsbSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t20/i1/usb-wire-simulation").toAbsolutePath
  }
  test("USB wire/MMIO loopback crosses I1 fabrics, wakes stopped main and recovers independent resets") {
    simulate(new SocI1UsbBench) { d =>
      val h=new UsbWireHost(d,checkConfiguredReset=false)
      def high(b: Bool): Boolean=b.peek().litToBoolean
      d.mainReset_n.poke(true.B);d.usbReset_n.poke(true.B);d.aonReset_n.poke(true.B)
      d.corruptRead.poke(false.B);d.bus.req.poke(false.B);d.bus.bits.poke(0.U.asTypeOf(d.bus.bits))
      var appEdges=0
      def step(n: Int=1): Unit=for(_<-0 until n) {
        d.app.step();h.step(6);appEdges+=1;if(appEdges%8==0) d.aon.step()
      }
      def access(offset: Int,write: Boolean=false,value: Int=0): Int = {
        d.bus.req.poke(true.B);d.bus.bits.addr.poke((0x40040800L+offset).U)
        d.bus.bits.we.poke(write.B);d.bus.bits.wdata.poke(value.U);d.bus.bits.be.poke(15.U);d.bus.bits.origin.poke(7.U)
        var grant=false;var done=false;var answer=0;var sinceGrant=0;var waited=0
        while(!done && waited<256) {
          val take=high(d.bus.req)&&high(d.bus.gnt)
          if(high(d.bus.rvalid)) {
            assert(grant,"I1_USB_UNSOLICITED_REPLY");assert(!high(d.bus.err),"I1_USB_MMIO_ERROR")
            answer=d.bus.rdata.peek().litValue.toInt;done=true
          }
          if(grant) {sinceGrant+=1;assert(sinceGrant<=128,"I1_USB_MMIO_DEADLINE")}
          step();if(take) {assert(!grant);grant=true;d.bus.req.poke(false.B)};waited+=1
        }
        assert(done,"I1_USB_ADMISSION_DEADLINE");step(2);assert(!high(d.bus.rvalid));answer
      }
      def rd(offset: Int): Int=access(offset)
      def wr(offset: Int,value: Int): Unit={assert(access(offset,true,value)==0);()}
      h.initialize(()=>{step(80);wr(0,1)})
      def enumerate(): Unit = {
        val device=Seq(18,1,0,2,2,0,0,8,0,0,0,0,0x10,1,0,0,0,1)
        assert(h.read(0,6,0x100,18,retryFirst=true)==device,"I1_USB_DESCRIPTOR")
        h.write(0,5,5);h.write(5,9,1);step(80)
        assert((rd(0x10)&12)==12,"I1_USB_CONFIGURED_STATUS")
      }
      enumerate();wr(0x18,1)
      wr(0x14,15);wr(8,2);step(160)
      assert(!high(d.wake) && !high(d.demand),"I1_USB_WAKE_BASELINE")
      val payload=Seq(0x31,0xa5,0xff,0,0x72,0x18,0xfe)
      h.token(h.OUT,5,1);h.idle(2);h.data(h.DATA0,payload)
      assert(h.receive()._1==h.ACK);h.idle(30)
      // Main remains stopped throughout host traffic and these AON edges.
      d.aon.step(12);assert(high(d.wake) && high(d.demand),"I1_USB_WAKE_TO_MAIN")
      val received=payload.map { expected =>
        var polls=0
        while((rd(0x10)&2)==0 && polls<16) {step();polls+=1}
        assert((rd(0x10)&2)!=0,"I1_USB_RX_DEADLINE")
        assert(d.irq.peek().litValue.testBit(6),"I1_USB_INTERRUPT_MAP")
        val value=rd(0x0c);assert(rd(0x0c)==value,"I1_USB_HELD_RX")
        d.corruptRead.poke(true.B)
        val damaged=rd(0x0c)
        val failure=intercept[org.scalatest.exceptions.TestFailedException] {
          assert(damaged==expected,"I1_USB_DATA_ORACLE")
        }
        assert(failure.getMessage.contains("I1_USB_DATA_ORACLE"));d.corruptRead.poke(false.B)
        wr(8,1);value
      }
      assert(received==payload,"I1_USB_DATA_ORACLE")
      for(value<-received) {assert((rd(0x10)&1)!=0);wr(4,value)}
      h.idle(40);h.token(h.IN,5,1);val first=h.receive()
      assert(first==(h.DATA0,payload),"I1_USB_LOOPBACK")
      h.idle(4);h.token(h.IN,5,1);assert(h.receive()==first,"I1_USB_RETRY_CHANGED")
      h.idle(2);h.packet(h.ACK);h.idle(30)
      h.token(h.IN,5,1);assert(h.receive()._1==h.NAK,"I1_USB_REPLAY_AFTER_ACK")
      // Independent AON service reset must not discard the live USB session.
      d.aonReset_n.poke(false.B);d.aon.step(3);d.aonReset_n.poke(true.B);d.aon.step(12)
      assert((rd(0x10)&12)==12,"I1_AON_RESET_DESTROYED_USB")
      // Raw USB reset asserts pad safety without any USB or main edge.
      wr(4,0x99);d.usbReset_n.poke(false.B)
      assert(!high(d.oe) && !high(d.pullupEnable),"I1_USB_ASYNC_RESET_PADS")
      d.app.step(3);d.usbReset_n.poke(true.B);step(80)
      assert(rd(0)==0 && (rd(0x10)&3)==0,"I1_USB_RESET_RETAINED_TRANSPORT")
      wr(0,1);h.step(820000);h.busReset();enumerate()
      h.token(h.IN,5,1);assert(h.receive()._1==h.NAK,"I1_USB_RESET_REPLAYED_OLD_BYTE")
    }
  }
}
