package deadhorse.top
import chisel3._
import chisel3.simulator.{ChiselSim,Randomization,Settings}
import chisel3.testing.HasTestingDirectory
import deadhorse.lib._
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Real SRAM/controller/fabrics/endpoints; software bus substitutes for the CPU.
  * UART and SPI pads have explicit digital loopbacks, not mocked FIFO requests. */
class SocDmaHarness(config: SocI1Config=SocProduction.config(realUsb=false),bypassWatchdogEpoch: Boolean=false) extends RawModule {
  require(!bypassWatchdogEpoch || config.watchdog.isDefined)
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val coreReset_n=IO(Input(Bool()))
  val aonReset_n=IO(Input(Bool()));val bus=IO(new LocalBus);val lite=IO(new LocalBus)
  val irq=IO(Output(UInt(15.W)));val hold=IO(Output(Bool()));val pwm=IO(Output(UInt(9.W)))
  val pwmEnable=IO(Output(UInt(9.W)));val uartTx=IO(Output(Bool()))
  val stallPeripheral=config.watchdog.map(_=>IO(Input(Bool())))
  val epochReady=config.watchdog.map(_=>IO(Output(Bool())))
  val watchdogReset=config.watchdog.map(_=>IO(Output(Bool())))
  val p=Module(new SocPeripheralBusTest(SocTestFiles.description,config))
  val whole=p.supervision.map(_.wholeReset).getOrElse(false.B)
  val performance=p.supervision.map(_.performanceReset).getOrElse(false.B)
  val up=Module(new ResetRelease);up.clk:=clk;up.reset_n:=reset_n && !whole
  val core=Module(new ResetRelease);core.clk:=clk;core.reset_n:=reset_n && coreReset_n && !whole && !performance
  val mem=Module(new SocLocalMemory(SocTestFiles.description,SocTestFiles.memoryRom,dmaEnabled=true,xipEnabled=true))
  mem.clk:=clk;mem.serviceReset_n:=up.released;mem.clientReset_n:=core.released
  mem.data<>bus;mem.dma.get<>p.dmaMemory.get
  mem.xip.get<>p.nativeXip.get
  if(config.watchdog.isDefined) {
    p.main.req:=mem.peripheral.req && !stallPeripheral.get;p.main.bits:=mem.peripheral.bits
    mem.peripheral.gnt:=p.main.gnt && !stallPeripheral.get
    mem.peripheral.rvalid:=p.main.rvalid;mem.peripheral.rdata:=p.main.rdata;mem.peripheral.err:=p.main.err
    p.performanceReady.get:=(if(bypassWatchdogEpoch) true.B else mem.epochReady)
    epochReady.get:=mem.epochReady;watchdogReset.get:=performance
  } else mem.peripheral<>p.main
  mem.instruction.req:=false.B;mem.instruction.bits:=0.U.asTypeOf(new BusPayload)
  p.mainClock:=clk;p.coldReset_n:=reset_n;p.warmReset_n:=true.B;p.mainServiceReset_n:=true.B
  p.pins.aonClock:=clk;p.pins.usbClock:=clk;p.pins.aonServiceReset_n:=aonReset_n;p.pins.usbServiceReset_n:=true.B
  p.pins.lite<>lite;p.pins.liteHalted:=true.B;p.pins.resetReason:=0.U;p.pins.crashCount:=0.U
  p.uartRx:=p.uartTx;p.pins.uartRx.foreach(_:=true.B);uartTx:=p.uartTx
  p.pins.spiMiso:=p.pins.spiMosi;p.pins.spiTimeNow:=0.U
  p.pins.i2cSclIn:=true.B;p.pins.i2cSdaIn:=true.B;p.pins.recoveryScl:=true.B;p.pins.recoverySda:=true.B
  p.pins.usbVbus:=false.B;p.pins.usbDpRx:=false.B;p.pins.usbDnRx:=false.B
  p.pins.inactive.qspiDqIn:=0.U;p.pins.inactive.jtagTck:=false.B;p.pins.inactive.jtagTms:=false.B
  p.pins.inactive.jtagTdi:=false.B;p.pins.inactive.imuDrdy:=false.B;p.pins.inactive.gpioIn:=0.U
  p.pins.inactive.timerIn:=0.U
  irq:=p.fastIrq;hold:=p.mainHold;pwm:=p.pins.inactive.actuatorOut;pwmEnable:=p.pins.inactive.actuatorEnable
}

class SocDmaSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/t23/soc-simulation").toAbsolutePath
  }
  val settings=Settings.defaultRaw[SocDmaHarness].copy(randomization=Randomization.random.copy(memories=false))
  def high(v: Bool)=v.peek().litToBoolean
  val ram=BigInt(0x20000000L);val dma=BigInt(0x40011000L);val uart=BigInt(0x40010000L)
  val spi=BigInt(0x40010300L);val pwm=BigInt(0x40030000L)
  def init(d: SocDmaHarness): Unit={
    d.stallPeripheral.foreach(_.poke(false.B))
    Seq(d.bus,d.lite).foreach {p=>p.req.poke(false.B);p.bits.poke(0.U.asTypeOf(new BusPayload))}
    d.reset_n.poke(false.B);d.coreReset_n.poke(false.B);d.aonReset_n.poke(false.B);d.clk.step(4)
    d.reset_n.poke(true.B);d.coreReset_n.poke(true.B);d.aonReset_n.poke(true.B);d.clk.step(40)
  }
  def access(d: SocDmaHarness,a: BigInt,w: Boolean=false,v: BigInt=0,remote: Boolean=false): (BigInt,Boolean)={
    val p=if(remote) d.lite else d.bus;p.req.poke(true.B);p.bits.addr.poke(a.U);p.bits.we.poke(w.B)
    p.bits.wdata.poke(v.U);p.bits.be.poke(15.U);p.bits.origin.poke((if(remote) 7 else 1).U)
    var n=0;while(!high(p.gnt)) {d.clk.step();n+=1;assert(n<512,"SOC_DMA_GRANT")}
    d.clk.step();p.req.poke(false.B)
    while(!high(p.rvalid)) {d.clk.step();n+=1;assert(n<1024,"SOC_DMA_RESPONSE")}
    val r=(p.rdata.peek().litValue,high(p.err));d.clk.step(2);r
  }
  def wr(d: SocDmaHarness,a: BigInt,v: BigInt): Unit=assert(!access(d,a,true,v)._2,s"DMA_MMIO_WRITE $a")
  def rd(d: SocDmaHarness,a: BigInt): BigInt={val(v,e)=access(d,a);assert(!e,s"DMA_MMIO_READ $a");v}
  def channel(d: SocDmaHarness,i: Int,offset: Int,count: Int,ep: Int): Unit={
    wr(d,dma+0x20+4*i,ram+offset);wr(d,dma+0x30+4*i,count);wr(d,dma+0x40+4*i,ep)
  }
  def completed(d: SocDmaHarness,mask: Int): Unit={
    var n=0;while((rd(d,dma+8)&mask)!=0) {d.clk.step(50);n+=1;assert(n<300,"SOC_DMA_COMPLETION")}
    assert((rd(d,dma+12)&mask)==mask && (rd(d,dma+12)&0xff0)==0,"SOC_DMA_EVENTS")
  }
  test("real UART and SPI DMA loopbacks, packed SRAM, ownership and IRQ8") {
    simulateRaw(new SocDmaHarness,settings=settings) {d=>
      init(d);wr(d,ram,BigInt("b3a29180",16));wr(d,ram+4,BigInt("f7e6d5c4",16))
      wr(d,ram+0x100,0);wr(d,ram+0x104,0);wr(d,ram+0x108,0)
      wr(d,uart,3);wr(d,uart+4,4096);wr(d,uart+8,1)
      assert(rd(d,uart+0x20)==(BigInt(4096)<<16)+3,"DMA_UART_CONFIG_ACCEPTED")
      channel(d,0,1,6,0);channel(d,1,0x101,6,1);wr(d,dma+0x10,3)
      assert(access(d,dma,true,3,remote=true)._2,"DMA_REMOTE_OWNER")
      assert(rd(d,dma+8)==0);wr(d,dma,3);completed(d,3)
      assert(rd(d,ram+0x100)==BigInt("b3a29100",16) && rd(d,ram+0x104)==BigInt("e6d5c4",16),"DMA_UART_WIRE")
      assert(d.irq.peek().litValue.testBit(8));wr(d,dma+12,0xffff);d.clk.step(5)
      assert(!d.irq.peek().litValue.testBit(8));assert((rd(d,uart+0x18)&31)==0)
      wr(d,spi,1);wr(d,spi+4,15);wr(d,spi+8,6);wr(d,spi+12,1)
      channel(d,0,1,6,6);channel(d,1,0x201,6,7);wr(d,ram+0x200,0);wr(d,ram+0x204,0)
      wr(d,dma,3)
      var n=0;while((rd(d,dma+8)&1)!=0) {n+=1;assert(n<80)}
      wr(d,spi+12,2);completed(d,3)
      assert(rd(d,ram+0x200)==BigInt("b3a29100",16) && rd(d,ram+0x204)==BigInt("e6d5c4",16),"DMA_SPI_WIRE")
      assert((rd(d,spi+0x1c)&15)==0)
      for(off<-Seq(0x14,0x80,0x100,0xffc)) assert(access(d,dma+off)._2,"DMA_EXACT_DECODE")
    }
  }
  test("PWM DMA updates survive held core/AON resets; service reset cancels") {
    simulateRaw(new SocDmaHarness,settings=settings) {d=>
      init(d);wr(d,pwm+4,1);wr(d,pwm+0x40,999);wr(d,pwm+0xc0,0);wr(d,pwm+0x18,1);wr(d,pwm,1)
      wr(d,ram+0x300,250);wr(d,ram+0x304,500);wr(d,ram+0x308,750)
      channel(d,0,0x300,3,8);wr(d,dma,1)
      d.coreReset_n.poke(false.B);d.aonReset_n.poke(false.B);d.clk.step(5000)
      val samples=(0 until 2000).map {_=>val v=d.pwm.peek().litValue;d.clk.step();v}
      assert(samples.count(_.testBit(0))==1500 && samples.drop(1000)==samples.dropRight(1000),"DMA_PWM_WIRE_RESET")
      d.coreReset_n.poke(true.B);d.aonReset_n.poke(true.B);d.clk.step(40);completed(d,1)
      assert(rd(d,dma+0x50)==0 && rd(d,dma+0x60)==ram+0x30c)
      wr(d,pwm+4,1);wr(d,ram+0x300,1001);channel(d,0,0x300,1,8);wr(d,dma+12,0xffff)
      wr(d,pwm,1);wr(d,dma,1);d.clk.step(2000)
      assert((rd(d,dma+12)&16)!=0 && rd(d,dma+0x70)==9 && rd(d,pwm+0xc0)==750,"DMA_INVALID_PWM_NO_WRITE")
      channel(d,0,0x300,100,0);wr(d,dma,1);d.reset_n.poke(false.B)
      assert(d.pwmEnable.peek().litValue==0);d.clk.step(3);d.reset_n.poke(true.B);d.clk.step(40)
      assert(rd(d,dma+8)==0 && rd(d,dma+12)==0 && rd(d,pwm+8)==0,"DMA_SERVICE_RESET")
    }
  }
}
