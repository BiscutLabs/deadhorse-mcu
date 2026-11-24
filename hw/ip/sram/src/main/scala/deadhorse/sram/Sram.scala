package deadhorse.sram

import chisel3._
import chisel3.util._
import chisel3.util.experimental.loadMemoryFromFileInline
import java.nio.file.Paths

sealed trait SramTarget
object SramTarget {
  case object Model extends SramTarget
  case object Asic extends SramTarget
  case object VendorSimulation extends SramTarget
}

/** Single rising-edge port. No ready chain and no reset-initialized RAM. */
class SramPort(val addressBits: Int) extends Bundle {
  val enable=Output(Bool());val write=Output(Bool());val address=Output(UInt(addressBits.W))
  val data=Output(UInt(32.W));val mask=Output(UInt(4.W));val result=Input(UInt(32.W))
}

/** The physical pin names and sources are byte-exact pinned upstream views. */
class Gf180Sram(functionalModel: Boolean=false) extends BlackBox with HasBlackBoxPath {
  override def desiredName="gf180mcu_ocd_ip_sram__sram1024x8m8wm1"
  val io=IO(new Bundle {
    val CLK=Input(Clock());val CEN=Input(Bool());val GWEN=Input(Bool())
    val WEN=Input(UInt(8.W));val A=Input(UInt(10.W));val D=Input(UInt(8.W));val Q=Output(UInt(8.W))
  })
  if(functionalModel) addPath(Paths.get("build/vendor/gf180_sram/cells",desiredName,desiredName+".v").toAbsolutePath.toString)
}

/** Independent masked word model or four byte-wide hard macros. Test fixtures
  * may use other depths/preload; the ASIC binding requires a physical row bank.
  * Reset belongs to the port owner, never to the SRAM contents. */
class SramWordBank(depth: Int=1024,target: SramTarget=SramTarget.Model,image: Option[String]=None) extends RawModule {
  require(depth>1)
  require(target==SramTarget.Model || depth==1024 && image.isEmpty)
  val clk=IO(Input(Clock()));val port=IO(Flipped(new SramPort(log2Ceil(depth))))
  protected def lane(index: Int): Int=index
  val physical=if(target==SramTarget.Model) Seq.empty else
    (0 until 4).map(_=>Module(new Gf180Sram(target==SramTarget.VendorSimulation)))
  if(target==SramTarget.Model) {
    withClock(clk) {
      val memory=SyncReadMem(depth,Vec(4,UInt(8.W)))
      image.foreach(loadMemoryFromFileInline(memory,_))
      val raw=memory.readWrite(port.address,port.data.asTypeOf(Vec(4,UInt(8.W))),
        port.mask.asBools,port.enable,port.write).asUInt
      // Model Q holding across writes/disabled cycles without initializing RAM.
      val read=RegNext(port.enable && !port.write)
      val held=Reg(UInt(32.W));when(read) {held:=raw}
      port.result:=Mux(read,raw,held)
    }
  } else {
    val bytes=physical.zipWithIndex.map {case(cell,i)=>
      cell.io.CLK:=clk;cell.io.CEN:= !port.enable;cell.io.GWEN:= !port.write
      cell.io.WEN:=Fill(8,!port.mask(lane(i)))
      cell.io.A:=port.address;cell.io.D:=port.data(8*lane(i)+7,8*lane(i));cell.io.Q
    }
    port.result:=Cat(bytes.reverse)
  }
}

class MarchResult extends Bundle {
  val failed=Bool();val address=UInt(12.W);val expected=UInt(32.W)
  val observed=UInt(32.W);val phase=UInt(3.W)
}

/** March C- with explicit synchronous-read comparison and a level handshake.
  * run stays asserted through completion; dropping it relinquishes the port.
  * Functional reset must remain asserted for every destructive operation. */
class SramMarch(words: Int) extends RawModule {
  require(words>=2 && words<=4096)
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()))
  val run=IO(Input(Bool()));val permitted=IO(Input(Bool()))
  val busy=IO(Output(Bool()));val done=IO(Output(Bool()));val result=IO(Output(new MarchResult))
  val memory=IO(new SramPort(12))
  protected def completed(last: Bool): Bool=last
  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val idle :: write :: read :: compare :: complete :: Nil=Enum(5)
    val state=RegInit(idle);val address=RegInit(0.U(12.W));val phase=RegInit(0.U(3.W))
    val failure=RegInit(0.U.asTypeOf(new MarchResult))
    val descending=phase===3.U || phase===4.U
    val expected=Mux(phase===2.U || phase===4.U,"hffffffff".U,0.U)
    memory.enable:=reset_n && run && permitted && (state===write || state===read)
    memory.write:=state===write;memory.address:=address;memory.mask:=15.U
    memory.data:=Mux(phase===1.U || phase===3.U,"hffffffff".U,0.U)
    busy:=state=/=idle;done:=state===complete;result:=failure
    def advance(): Unit={
      val last=Mux(descending,address===0.U,address===(words-1).U)
      when(completed(last)) {
        when(phase===5.U) {state:=complete}
          .otherwise {
            phase:=phase+1.U
            address:=Mux(phase===2.U || phase===3.U,(words-1).U,0.U)
            state:=read
          }
      }.otherwise {address:=Mux(descending,address-1.U,address+1.U);state:=Mux(phase===0.U,write,read)}
    }
    when(state===idle && run && permitted) {
      address:=0.U;phase:=0.U;failure:=0.U.asTypeOf(failure);state:=write
    }
    when(state===write && run && permitted) {advance()}
    when(state===read && run && permitted) {state:=compare}
    when(state===compare && run && permitted) {
      when(memory.result=/=expected && !failure.failed) {
        failure.failed:=true.B;failure.address:=address;failure.expected:=expected
        failure.observed:=memory.result;failure.phase:=phase
      }
      when(phase===5.U) {advance()}.otherwise {state:=write}
    }
    when(!run) {state:=idle}
    assert(!memory.enable || permitted && run)
    assert(!memory.enable || address<words.U)
    assert(!done || phase===5.U)
  }
}
