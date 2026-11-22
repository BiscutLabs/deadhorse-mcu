package deadhorse.top

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import deadhorse.lib.LocalBus
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

class WrongI1Irq(d: SocDescription,c: SocI1Config) extends SocPeripheralBusTest(d,c) {
  override protected def interruptIndex(name: String): Int=if(name=="uart1") 12 else super.interruptIndex(name)
}

/** Public bus/pin integration checks; not gateway/four-target acceptance. */
class SocI1Spec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t20/i1/simulation").toAbsolutePath
  }
  def high(x: Bool): Boolean=x.peek().litToBoolean
  private var beforeMain: () => Unit=()=>()
  private var afterMain: () => Unit=()=>()
  private var aonPeriod=1
  private var sample=0
  def tick(d: SocI1Peripherals,n: Int=1): Unit=for(_<-0 until n) {
    SocInactiveTestInputs.drive(d.pins.inactive,sample&65535)
    SocInactiveTestInputs.check(d.pins.inactive)
    beforeMain();d.mainClock.step();afterMain();sample+=1
    if(sample%aonPeriod==0) d.pins.aonClock.step()
    d.pins.usbClock.step()
  }
  def drive(bus: LocalBus,addr: BigInt,write: Boolean=false,data: BigInt=0,be: Int=15,origin: Int=7): Unit = {
    bus.req.poke(true.B);bus.bits.addr.poke(addr.U);bus.bits.we.poke(write.B)
    bus.bits.wdata.poke(data.U);bus.bits.be.poke(be.U);bus.bits.origin.poke(origin.U)
  }
  def reset(d: SocI1Peripherals): Unit = {
    SocTestPorts.idle(d)
    drive(d.main,0);drive(d.pins.lite,0);d.main.req.poke(false.B);d.pins.lite.req.poke(false.B)
    d.coldReset_n.poke(false.B);d.warmReset_n.poke(false.B);d.mainServiceReset_n.poke(false.B)
    d.pins.aonServiceReset_n.poke(false.B);d.pins.usbServiceReset_n.poke(false.B)
    d.uartRx.poke(true.B);d.pins.uartRx.foreach(_.poke(true.B))
    d.pins.spiMiso.poke(false.B);d.pins.spiTimeNow.poke(0.U)
    d.pins.i2cSclIn.poke(true.B);d.pins.i2cSdaIn.poke(true.B)
    d.pins.recoveryScl.poke(true.B);d.pins.recoverySda.poke(true.B)
    d.pins.usbVbus.poke(false.B);d.pins.usbDpRx.poke(false.B);d.pins.usbDnRx.poke(false.B)
    d.pins.liteHalted.poke(true.B);d.pins.resetReason.poke(0.U);d.pins.crashCount.poke(0.U)
    tick(d,4)
    d.coldReset_n.poke(true.B);d.warmReset_n.poke(true.B);d.mainServiceReset_n.poke(true.B)
    d.pins.aonServiceReset_n.poke(true.B);d.pins.usbServiceReset_n.poke(true.B);tick(d,40)
  }
  def access(d: SocI1Peripherals,bus: LocalBus,address: BigInt,write: Boolean=false,data: BigInt=0,
             be: Int=15): (BigInt,Boolean,Int) = {
    drive(bus,address,write,data,be)
    var cycles=0
    while(!high(bus.gnt)) {tick(d);cycles+=1;assert(cycles<256,"I1_GRANT_TIMEOUT")}
    val period=if(bus eq d.pins.lite) aonPeriod else 1
    // Acceptance and a one-cycle response are measured in the requester's
    // clock domain, including when AON is slower than the main test clock.
    tick(d,period);bus.req.poke(false.B)
    while(!high(bus.rvalid)) {tick(d);cycles+=1;assert(cycles<512,"I1_RESPONSE_TIMEOUT")}
    val result=(bus.rdata.peek().litValue,high(bus.err),cycles)
    tick(d,2*period);assert(!high(bus.rvalid),"I1_DUPLICATE_REPLY");result
  }
  def good(d: SocI1Peripherals,bus: LocalBus,address: BigInt,write: Boolean=false,data: BigInt=0,be: Int=15): BigInt = {
    val(v,e,_)=access(d,bus,address,write,data,be);assert(!e,s"I1_BUS_ERROR $address");v
  }
  def irqCheck(d: SocI1Peripherals): Unit = {
    reset(d)
    for(i<-0 until 3) {
      val irqEnable=BigInt(0x4001001cL+i*0x100)
      good(d,d.main,irqEnable,true,2) // TX-ready, independent register contract.
      tick(d,4);assert(d.fastIrq.peek().litValue==(1<<i),"I1_IRQ_MAP")
      good(d,d.main,irqEnable,true,0);tick(d,4);assert(d.fastIrq.peek().litValue==0)
    }
  }
  test("serial endpoints, ownership, exact decode, all stub windows and IRQ wiring") {
    simulateRaw(new SocPeripheralBusTest(SocTestFiles.description,SocProduction.config(realUsb=false))) { d =>
      irqCheck(d)
      val bases=Seq(0x40010000L,0x40010100L,0x40010200L,0x40010300L,0x40010400L)
      for(base<-bases) {
        assert(good(d,d.main,base)==0)
        good(d,d.main,base,true,1);assert(good(d,d.main,base)==1)
        val(_,denied,_)=access(d,d.pins.lite,base,true,0) // forged origin7 is replaced by lite0
        assert(denied,"I1_OWNER_BYPASS");assert(good(d,d.main,base)==1)
        good(d,d.main,base,true,0)
      }
      // These were stub apertures in I1; production exposes their registers.
      // Keep the error oracle on the reserved padding in each aperture.
      val errors=Seq(0x40000400L,0x40011100L,0x40012300L,0x40013200L,0x40020000L,0x40020100L,0x4002fffcL,
        0x40030100L,0x40040000L,0x40040800L,0x60000000L,0x40010500L,0x40040900L,0xffffffffL)
      for(address<-errors;bus<-Seq(d.main,d.pins.lite)) {
        val(v,e,_)=access(d,bus,address);assert(e && v==0,s"I1_STUB_OR_HOLE $address")
      }
      for(bus<-Seq(d.main,d.pins.lite)) {
        val(v,e,_)=access(d,bus,0x40020000L,write=true,data=1)
        assert(e && v==0,"RETIRED_ADC_WINDOW_WRITE")
      }
      assert(!high(d.pins.usbTxEnable) && !high(d.pins.usbPullup))
      assert(!high(d.pins.spiEnable) && d.pins.spiCs_n.peek().litValue==3)
    }
  }
  test("mailbox round trip, retained byte lanes, denied program writes and independent service reset") {
    simulateRaw(new SocPeripheralBusTest(SocTestFiles.description,SocProduction.config(realUsb=false))) { d =>
      reset(d)
      val mailbox=BigInt(0x40001000L)
      good(d,d.main,mailbox,true,0x12345678);good(d,d.main,mailbox+4,true,1)
      tick(d,30);assert(high(d.pins.aonIrq));assert(good(d,d.pins.lite,mailbox+8)==0x12345678)
      good(d,d.pins.lite,mailbox+4,true,2)
      good(d,d.pins.lite,mailbox,true,0x76543210);good(d,d.pins.lite,mailbox+4,true,1)
      tick(d,30);assert(d.fastIrq.peek().litValue.testBit(5));assert(good(d,d.main,mailbox+8)==0x76543210)
      good(d,d.main,mailbox+4,true,2)
      val working=BigInt(0x30000800L)
      good(d,d.pins.lite,working,true,0x11223344)
      good(d,d.main,working,true,0xaabbccddL,5)
      assert(good(d,d.pins.lite,working)==0x11bb33ddL)
      for(bus<-Seq(d.main,d.pins.lite)) {
        assert(access(d,bus,0x30000000L,true,0xdeadbeefL)._2,"I1_PROGRAM_WRITE_BYPASS")
        assert(access(d,bus,0x30000c00L)._2,"I1_RETAINED_PADDING")
      }
      d.pins.liteHalted.poke(false.B)
      assert(access(d,d.main,working)._2,"I1_RUNNING_REMOTE_MEMORY")
      assert(good(d,d.pins.lite,working)==0x11bb33ddL)
      d.pins.liteHalted.poke(true.B)
      d.mainServiceReset_n.poke(false.B);tick(d,3);d.mainServiceReset_n.poke(true.B);tick(d,45)
      assert(good(d,d.main,working)==0x11bb33ddL)
      assert((good(d,d.pins.lite,mailbox+16)&4)!=0,"I1_MAILBOX_PEER_RESET")
    }
  }
  test("opposite-direction traffic completes without circular bridge admission") {
    simulateRaw(new SocPeripheralBusTest(SocTestFiles.description,SocProduction.config(realUsb=false))) { d =>
      aonPeriod=3
      try {
      reset(d);good(d,d.pins.lite,0x30000800L,true,0x1234)
      drive(d.main,0x30000800L);drive(d.pins.lite,0x40010000L)
      var mg=false;var ag=false;var mr=false;var ar=false;var cycles=0
      while(!mr || !ar) {
        val aonEdge=(sample+1)%aonPeriod==0
        val mt= !mg && high(d.main.gnt);val at= !ag && high(d.pins.lite.gnt) && aonEdge
        if(high(d.main.rvalid)) {assert(mg && !mr);assert(!high(d.main.err));assert(d.main.rdata.peek().litValue==0x1234);mr=true}
        if(high(d.pins.lite.rvalid) && aonEdge) {assert(ag && !ar);assert(high(d.pins.lite.err));ar=true}
        tick(d);if(mt) {mg=true;d.main.req.poke(false.B)};if(at) {ag=true;d.pins.lite.req.poke(false.B)}
        cycles+=1;assert(cycles<512,"I1_DIRECTION_DEADLOCK")
      }
      } finally {aonPeriod=1}
    }
  }
  test("wrong generated interrupt connection is detected") {
    simulateRaw(new WrongI1Irq(SocTestFiles.description,SocProduction.config(realUsb=false))) { d =>
      val failure=intercept[org.scalatest.exceptions.TestFailedException] {irqCheck(d)}
      assert(failure.getMessage.contains("I1_IRQ_MAP"))
    }
  }
  test("real USB recovers after an outer timeout while its service reset blocks admission") {
    simulateRaw(new SocPeripheralBusTest(SocTestFiles.description,SocProduction.config(realUsb=true))) { d =>
      reset(d)
      val usb=BigInt(0x40040800L)
      assert(good(d,d.main,usb)==0)
      d.pins.usbServiceReset_n.poke(false.B);tick(d,4)
      val(value,error,cycles)=access(d,d.main,usb,true,1)
      assert(error && value==0,"I1_USB_RESET_TIMEOUT_ERROR")
      assert(cycles<=130,"I1_USB_ROOT_DEADLINE") // includes request arbitration edges
      d.pins.usbServiceReset_n.poke(true.B);tick(d,40)
      assert(good(d,d.main,usb)==0,"I1_USB_CANCELLED_WRITE_REPLAYED")
      good(d,d.main,usb,true,1);assert(good(d,d.main,usb)==1,"I1_USB_QUARANTINE_STUCK")
      good(d,d.main,usb,true,0)
    }
  }
  test("recovery I2C wire loads actual retained SRAM, rejects bad CRC and preserves lock across warm reset") {
    simulateRaw(new SocPeripheralBusTest(SocTestFiles.description,SocProduction.config(realUsb=false))) { d =>
      reset(d)
      var hostLow=false;var starts=0
      def wireStep(n: Int): Unit=for(_<-0 until n) {
        d.pins.recoverySda.poke((!hostLow && !high(d.pins.recoverySdaLow)).B)
        tick(d)
        d.pins.recoverySda.poke((!hostLow && !high(d.pins.recoverySdaLow)).B)
        if(high(d.pins.liteStart)) starts+=1
      }
      def line(scl: Boolean,low: Boolean): Unit = {
        hostLow=low;d.pins.recoveryScl.poke(scl.B);wireStep(5)
      }
      def start(): Unit={line(true,false);line(true,true);line(false,true)}
      def stop(): Unit={line(false,true);line(true,true);line(true,false);wireStep(8)}
      def send(value: Int): Unit = {
        for(bit<-7 to 0 by -1) {
          val low=(value&(1<<bit))==0;line(false,low);line(true,low);line(false,low)
        }
        line(false,false);line(true,false)
        assert(!high(d.pins.recoverySda),"I1_RECOVERY_WIRE_ACK")
        line(false,false)
      }
      def bytes(value: Long): Seq[Int]=(0 until 4).map(i=>((value>>>(i*8))&255).toInt)
      def command(op: Int,words: Long*): Unit = {
        start();send(0x6a);send(op);words.flatMap(bytes).foreach(send);stop()
      }
      def crc(words: Seq[Long]): Long = {
        val c=new java.util.zip.CRC32;words.flatMap(bytes).foreach(c.update);c.getValue
      }
      def upload(words: Seq[Long],checksum: Long): Unit = {
        command(1,words.size*4,0,checksum,0x10000,16,0,0,0x2011)
        words.zipWithIndex.foreach {case(w,i)=>command(2,i*4,w)}
        command(3)
      }
      val image=Seq(0x13579bdfL,0x2468ace0L,0xff00aa55L,0x01234567L)
      upload(image,crc(image)^1);assert(!high(d.pins.loaderProgrammed),"I1_RECOVERY_BAD_CRC")
      command(5);assert(starts==0,"I1_RECOVERY_INVALID_START")
      upload(image,crc(image));assert(high(d.pins.loaderProgrammed),"I1_RECOVERY_COMMIT")
      for((word,i)<-image.zipWithIndex)
        assert(good(d,d.pins.lite,BigInt(0x30000000L+i*4))==word,"I1_RECOVERY_MEMORY_MODEL")
      command(6);assert(starts==1 && high(d.pins.loaderLocked),"I1_RECOVERY_START_LOCK")
      d.warmReset_n.poke(false.B);tick(d,4);d.warmReset_n.poke(true.B);tick(d,40)
      assert(high(d.pins.loaderLocked),"I1_RECOVERY_WARM_UNLOCK")
      command(1,4,0,0,0x10000,16,0,0,0x2012)
      command(2,0,0);command(5)
      assert(starts==1,"I1_RECOVERY_LOCKED_START")
      assert(good(d,d.pins.lite,0x30000000L)==image.head,"I1_RECOVERY_LOCKED_WRITE")
    }
  }
  test("integrated SPI reads a BMI270 chip-ID wire fixture and detects corrupted MISO") {
    simulateRaw(new SocPeripheralBusTest(SocTestFiles.description,SocProduction.config(realUsb=false))) { d =>
      reset(d)
      val base=BigInt(0x40010300L)
      def wr(offset: Int,value: Int): Unit={good(d,d.main,base+offset,true,value);()}
      def rd(offset: Int): BigInt=good(d,d.main,base+offset)
      wr(0,1);wr(4,3);wr(12,1);wr(0x20,8)
      // BMI270 already selected/awake: address with read bit, dummy byte, ID.
      // Bosch BST-BMI270-DS000-08, sections CHIP_ID and SPI read protocol.
      def readId(corrupt: Boolean): Unit = {
        Seq(0x80,0,0).foreach(v=>wr(0x10,v));wr(8,3)
        val peer=new deadhorse.spi_host.SpiPeer(false,0,3,Seq(0x80,0,0),Seq(0xa5,0x5a,0x24))
        var cycles=0
        afterMain=()=> {
          cycles+=1
          peer.edge(cycles,high(d.pins.spiSclk),high(d.pins.spiMosi),d.pins.spiCs_n.peek().litValue.toInt)
            .foreach(v=>d.pins.spiMiso.poke((v ^ corrupt).B))
        }
        try {
          wr(12,2)
          while(peer.end<0 && cycles<256) tick(d)
          assert(peer.end>=0,"I1_SPI_WIRE_DEADLINE");tick(d,8)
        } finally {afterMain=()=>()}
        assert(d.fastIrq.peek().litValue.testBit(3),"I1_SPI_INTERRUPT")
        val received=(0 until 3).map { _=>val v=rd(0x14);wr(12,4);v }
        wr(0x1c,16)
        assert(received.last==0x24,"I1_BMI270_ID")
      }
      readId(false)
      val failure=intercept[org.scalatest.exceptions.TestFailedException] {readId(true)}
      assert(failure.getMessage.contains("I1_BMI270_ID"))
    }
  }
  test("integrated I2C reads a BMP390 chip-ID wire fixture and detects a corrupted reply") {
    simulateRaw(new SocPeripheralBusTest(SocTestFiles.description,SocProduction.config(realUsb=false))) { d =>
      reset(d)
      val base=BigInt(0x40010400L);val peer=new deadhorse.i2c_host.I2cPeer
      var cycles=0
      def resolve(): Unit = {
        d.pins.i2cSclIn.poke((!high(d.pins.i2cSclLow)).B)
        d.pins.i2cSdaIn.poke((!high(d.pins.i2cSdaLow) && !peer.dataLow).B)
      }
      beforeMain=()=>resolve()
      afterMain=()=> {
        cycles+=1;resolve();peer.observe(cycles,high(d.pins.i2cSclIn),high(d.pins.i2cSdaIn))
        resolve();peer.settled(high(d.pins.i2cSclIn),high(d.pins.i2cSdaIn))
      }
      def wr(offset: Int,value: BigInt): Unit={good(d,d.main,base+offset,true,value);()}
      def rd(offset: Int): BigInt=good(d,d.main,base+offset)
      def command(value: Int): Unit = {
        wr(0x1c,127);wr(12,value)
        val deadline=cycles+1000
        var event=rd(0x1c)
        while(event==0 && cycles<deadline) {tick(d);event=rd(0x1c)}
        assert(event==1,"I1_I2C_COMMAND_RESULT")
      }
      def send(value: Int): Unit = {
        peer.arm(false,value,true);wr(0x10,value);command(2)
        assert(peer.current.isEmpty,"I1_I2C_UNFINISHED_BYTE")
      }
      try {
        wr(0,1);wr(4,new deadhorse.i2c_host.I2cTiming(3,12,8,16).word);wr(12,32);wr(0x20,128)
        // BMP390 address0x76, register0x00, repeated START, ID0x60.
        // Bosch BST-BMP390-DS002-07 sections4.3.1 and5.2.
        def readId(value: Int): Unit = {
          command(1);send(0xec);send(0);command(1);send(0xed)
          peer.arm(true,value,false);command(4)
          val received=rd(0x14)
          assert(d.fastIrq.peek().litValue.testBit(4),"I1_I2C_INTERRUPT")
          wr(12,128);command(8)
          assert(received==0x60,"I1_BMP390_ID")
        }
        readId(0x60)
        val failure=intercept[org.scalatest.exceptions.TestFailedException] {readId(0x61)}
        assert(failure.getMessage.contains("I1_BMP390_ID"))
      } finally {beforeMain=()=>();afterMain=()=>()}
    }
  }
}
