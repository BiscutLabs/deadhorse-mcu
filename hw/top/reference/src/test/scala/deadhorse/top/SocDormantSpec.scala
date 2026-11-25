package deadhorse.top
import chisel3._
import chisel3.util.Cat
import chisel3.util.experimental.BoringUtils
import chisel3.simulator.{ChiselSim,Randomization,Settings}
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite

/** Passive architectural-retirement and block-output observations only. */
class SocDormantProbe(rom: String="build/plan05/dormant-firmware/boot.hex",realUsb: Boolean=false) extends SocAnalogModelTest("build/t20/map/soc.json",SocProduction.config().uart,
    Plan05Firmware.checked(rom),
    i1Config=Some(SocProduction.config(realUsb=realUsb))) {
  val holds=IO(Output(UInt(3.W)))
  holds:=Cat(BoringUtils.bore(digital.subsystem.get.pins.usbClockRequest),
    BoringUtils.bore(digital.subsystem.get.dmaHold),BoringUtils.bore(digital.subsystem.get.timers.clockHold))
  val stage=IO(Output(UInt(32.W)));val entries=IO(Output(UInt(16.W)))
  val liteWatchdogLeft=IO(Output(UInt(32.W)));val liteWatchdogReset=IO(Output(Bool()))
  val liteWatchdogCause=IO(Output(Bool()));val liteHeld=IO(Output(Bool()))
  liteWatchdogLeft:=BoringUtils.bore(digital.subsystem.get.watchdogBlocks(1).channel.remaining)
  liteWatchdogReset:=BoringUtils.bore(digital.subsystem.get.watchdogBlocks(1).resetHold)
  liteWatchdogCause:=BoringUtils.bore(digital.subsystem.get.watchdogBlocks(1).channel.cause)
  liteHeld:=BoringUtils.bore(digital.subsystem.get.liteBootHeld)
  val watchdogLeft=IO(Output(UInt(32.W)));val watchdogReset=IO(Output(Bool()))
  val trace=digital.rvfi
  val valid=BoringUtils.bore(trace("rvfi_valid").asUInt.asBool)
  val address=BoringUtils.bore(trace("rvfi_mem_addr").asUInt)
  val mask=BoringUtils.bore(trace("rvfi_mem_wmask").asUInt)
  val data=BoringUtils.bore(trace("rvfi_mem_wdata").asUInt)
  withClockAndReset(clocks.mainClock,(!externalReset_n).asAsyncReset) {
    val last=RegInit(0.U(32.W));val boots=RegInit(0.U(16.W))
    when(valid && address==="h20003f00".U && mask===15.U) {
      last:=data;when(data==="h51050001".U) {boots:=boots+1.U}
    }
    stage:=last;entries:=boots
  }
  watchdogLeft:=BoringUtils.bore(digital.subsystem.get.watchdogBlocks.head.channel.remaining)
  watchdogReset:=BoringUtils.bore(digital.subsystem.get.watchdogBlocks.head.resetHold)
}

class SocDormantSpec extends AnyFunSuite with ChiselSim with SocDebugLintConfiguration {
  implicit val outputDirectory: HasTestingDirectory=new HasTestingDirectory {
    def getDirectory=Paths.get("build/plan05/dormant/simulation").toAbsolutePath
  }
  private val settings=Settings.defaultRaw[SocDormantProbe].copy(randomization=Randomization.random.copy(memories=false))
    .withLibraryPaths(Seq(Paths.get("hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv").toAbsolutePath.toString))
  private val gates=Array("--ckg-name=prim_generic_clock_gating","--ckg-input=clk_i","--ckg-output=clk_o",
    "--ckg-enable=en_i","--ckg-test-enable=test_en_i")
  test("production clock wrapper retains the performance core while the real watcher rejects and accepts radio packets") {
    simulateRaw(new SocDormantProbe,settings=settings,firtoolOpts=gates) {d=>
      def high(b: Bool)=b.peek().litToBoolean
      val p=d.pins;val analog=d.model.get
      p.uartRx.foreach(_.poke(true.B));p.spiMiso.poke(false.B);p.i2cSclIn.poke(true.B);p.i2cSdaIn.poke(true.B)
      
      p.usbVbus.poke(false.B);p.usbDpRx.poke(false.B);p.usbDnRx.poke(false.B);p.aonExtraIn.poke(0.U)
      SocInactiveTestInputs.drive(p.inactive,32)
      d.aonClockSelect.poke(false.B);d.porBypass.poke(false.B);d.externalReset_n.poke(false.B)
      analog.supplyMv.poke(0.U);analog.porReference.step(3);analog.lfClock.step(3);d.oscIn.step(6)
      analog.supplyMv.poke(3300.U);analog.porReference.step(1002);d.externalReset_n.poke(true.B)
      var ticks=0;var copyStart= -1;var copyEnd= -1
      def step(): Unit={
        // The external oscillator model produces NO edges while OSC_EN is low.
        if(high(d.oscEn)) d.oscIn.step(1500)
        analog.porReference.step(32);analog.lfClock.step();ticks+=1
        val stage=d.stage.peek().litValue
        if(stage==BigInt("51050001",16) && copyStart<0) copyStart=ticks
        if(stage==BigInt("51050002",16) && copyEnd<0) copyEnd=ticks
        assert(stage!=BigInt("0bad0505",16),"DORMANT_FIRMWARE_ORACLE")
      }
      while(high(d.oscEn) && ticks<24000) step()
      assert(!high(d.oscEn) && d.stage.peek().litValue==BigInt("51050003",16),"DORMANT_ENTER")
      assert(copyStart>=0 && copyEnd>copyStart,"LITE_COPY_MARKERS")
      println(s"DORMANT_LITE_COPY aon_ticks=${copyEnd-copyStart} estimated_ms=${(copyEnd-copyStart)*1000.0/32000}")
      assert(copyEnd-copyStart<=8000,"LITE_COPY_OVER_250MS")
      assert(d.entries.peek().litValue==1 && high(d.status.coreSleeping),"DORMANT_WFI_ENTRY")
      val remaining=d.watchdogLeft.peek().litValue;assert(remaining>0)
      def crc(body: Seq[Int]): Int={
        var value=0xffff
        for(b<-body) {value^=b<<8;for(_<-0 until 8) value=if((value&0x8000)!=0) ((value<<1)^0x1021)&0xffff else (value<<1)&0xffff}
        value
      }
      for(valid<-Seq(false,true)) {
        val body=Vector(0x48,0x44,1,7,0x12,0x34);val sum=crc(body)^(if(valid) 0 else 1)
        val packet=body++Vector(sum>>8,sum&255)
        var selected=false;var previous=false;var bits=0;var frames=0;var count=0
        def miso(): Unit=p.inactive.gpioIn.poke((if(bits<64) ((packet(bits/8)>>(7-bits%8))&1)<<2 else 0).U)
        def watch(): Unit={
          step();count+=1
          val cs= !p.aonExtraOut.peek().litValue.testBit(0);val ck=p.inactive.gpioOut.peek().litValue.testBit(0)
          assert(p.aonExtraEnable.peek().litValue.testBit(0) && (p.inactive.gpioEnable.peek().litValue&3)==3,"DORMANT_RADIO_PAD_DRIVE")
          if(cs && !selected) {bits=0;miso()}
          if(cs && selected && !previous && ck) {assert(!p.inactive.gpioOut.peek().litValue.testBit(1));bits+=1}
          if(cs && selected && previous && !ck) miso()
          if(!cs && selected) {frames+=1;assert(bits==64,"DORMANT_RADIO_FRAME")}
          selected=cs;previous=ck
          assert(d.watchdogLeft.peek().litValue==remaining && !high(d.watchdogReset),"DORMANT_WATCHDOG_COUNTS")
          if(!valid) assert(!high(d.oscEn),"DORMANT_INVALID_WAKE")
        }
        p.aonExtraIn.poke(2.U);d.oscEn.peek();p.aonExtraIn.poke(0.U);d.oscEn.peek()
        if(valid) {
          while(!high(d.oscEn) && count<8000) watch()
          println(s"DORMANT_IRQ_TO_OSC_EN aon_ticks=$count estimated_ms=${count*1000.0/32000}")
          assert(high(d.oscEn) && count<=3200,"DORMANT_VALID_PACKET_LATENCY")
        } else for(_<-0 until 5000) watch()
        assert(frames==1,"DORMANT_ONE_RADIO_FRAME")
      }
      var wake=0
      while(d.stage.peek().litValue!=BigInt("51050004",16) && wake<256) {step();wake+=1}
      assert(d.stage.peek().litValue==BigInt("51050004",16),"DORMANT_RESUMED_FIRMWARE")
      assert(d.entries.peek().litValue==1 && !high(d.watchdogReset),"DORMANT_REENTERED_ROM")
      println(s"DORMANT_OSC_EN_TO_RESUME aon_ticks=$wake estimated_ms=${wake*1000.0/32000}")
    }
  }
}
