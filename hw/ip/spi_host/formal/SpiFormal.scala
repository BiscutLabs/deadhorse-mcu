package deadhorse.spi_host

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

class SpiFaultData(json: String) extends SpiHost(json,2) {
  override protected def outputBit(value: Bool): Bool = !value
}
class SpiFaultOwner(json: String) extends SpiHost(json,2) {
  override protected def allowed(origin: UInt, owner: UInt): Bool = true.B
}

/** Port-only configured frame specification. The expected waveform comes from
  * elapsed edge arithmetic, not any internal state in the production host. */
class SpiFrameFormal(json: String, variant: String, mode3: Boolean) extends RawModule {
  val clock=IO(Input(Clock())); val reset_n=IO(Input(Bool()))
  val payload=IO(Input(UInt(8.W))); val sleeping=IO(Input(Bool()))
  val dut=Module(if(variant=="corrupt")new SpiFaultData(json) else new SpiHost(json,2))
  dut.clk:=clock;dut.reset_n:=reset_n;dut.owner:=0.U;dut.miso:=true.B;dut.timeNow:=0.U
  dut.sleepEnable:=false.B
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val script=RegInit(0.U(3.W));val waiting=RegInit(false.B)
    val byte=RegInit(0.U(8.W));val previouslySelected=RegInit(false.B)
    val seen=RegInit(false.B);val completed=RegInit(false.B)
    val age=RegInit(0.U(7.W))
    val selected=dut.cs_n=/=3.U
    dut.sleepRequest:=sleeping && seen
    dut.bus.req:=script<6.U && !waiting
    dut.bus.bits.addr:=MuxLookup(script,0.U)(Seq(0.U->0.U,1.U->4.U,2.U->8.U,3.U->12.U,4.U->16.U,5.U->12.U))
    dut.bus.bits.we:=true.B;dut.bus.bits.be:=15.U;dut.bus.bits.origin:=0.U
    dut.bus.bits.wdata:=MuxLookup(script,0.U)(Seq(0.U->(if(mode3)7.U else 1.U),
      1.U->3.U,2.U->1.U,3.U->1.U,4.U->payload.pad(32),5.U->2.U))
    when(dut.bus.req && dut.bus.gnt) {waiting:=true.B;when(script===4.U){byte:=payload}}
    when(dut.bus.rvalid) {waiting:=false.B;script:=script+1.U}
    previouslySelected:=selected
    when(selected) {age:=age+1.U;seen:=true.B}.otherwise{age:=0.U}
    when(previouslySelected && !selected){completed:=true.B}
    val bitsElapsed=if(mode3)(age-3.U)/6.U else age/6.U
    val index=Mux(bitsElapsed>7.U,7.U,bitsElapsed)(2,0)
    val expectedData=if(mode3) Mux(age<3.U,false.B,byte(7.U-index)) else byte(7.U-index)
    val expectedClock=(age/3.U)(0) ^ mode3.B
    val outstanding=RegInit(false.B)
    when(dut.bus.req && dut.bus.gnt){outstanding:=true.B}
    when(dut.bus.rvalid){outstanding:=false.B}
    if(variant=="cover") {
      cover(completed && byte==="ha5".U)
      cover(selected && age===30.U && sleeping)
    } else {
      assert(dut.cs_n=/=0.U)
      when(dut.bus.rvalid){assert(outstanding);assert(!dut.bus.err)}
      when(selected){
        assert(dut.cs_n=== (if(mode3)1.U else 2.U))
        assert(age<51.U);assert(dut.sclk===expectedClock);assert(dut.mosi===expectedData)
        when(age>0.U){assert(dut.clockHold)}
      }
      when(previouslySelected && !selected){assert(age===51.U)}
    }
  }
}

/** All denied origins, arbitrary traffic, observable reset-state preservation. */
class SpiDeniedFormal(json: String, variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val bus=IO(new deadhorse.lib.LocalBus)
  val dut=Module(if(variant=="corrupt")new SpiFaultOwner(json) else new SpiHost(json,2))
  dut.clk:=clock;dut.reset_n:=reset_n;dut.owner:=0.U;dut.miso:=false.B;dut.timeNow:=0.U
  dut.sleepRequest:=false.B;dut.sleepEnable:=false.B;dut.bus<>bus
  dut.bus.bits.origin:=Mux(bus.bits.origin===0.U,1.U,bus.bits.origin)
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val granted=RegNext(bus.req && bus.gnt,false.B)
    if(variant=="cover") {
      cover(bus.rvalid && bus.err);cover(bus.rvalid && bus.err && bus.req)
    } else {
      assert(bus.rvalid===granted)
      when(bus.rvalid){assert(bus.err);assert(bus.rdata===0.U)}
      assert(!dut.pinsEnable);assert(!dut.sclk);assert(!dut.mosi);assert(dut.cs_n===3.U)
      assert(!dut.irq);assert(!dut.dmaTxRequest);assert(!dut.dmaRxRequest);assert(!dut.clockHold)
    }
  }
}

object EmitSpiFormal {
  def main(args: Array[String]): Unit = {
    require(args.length==3,"EmitSpiFormal <json> <frame0|frame3|denied> build/<output>")
    val root=Paths.get(args(2)).toAbsolutePath.normalize
    require(root.startsWith(Paths.get("build").toAbsolutePath.normalize))
    for(variant<-Seq("correct","corrupt","cover")) {
      val dir=root.resolve(variant);Files.createDirectories(dir)
      def design: RawModule=args(1) match {
        case "frame0" => new SpiFrameFormal(args(0),variant,false)
        case "frame3" => new SpiFrameFormal(args(0),variant,true)
        case "denied" => new SpiDeniedFormal(args(0),variant)
      }
      ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(design),
        Array("--target-dir",dir.toString),Array("--disable-all-randomization","--verification-flavor=immediate","--lower-to-core","-strip-debug-info"))
    }
  }
}
