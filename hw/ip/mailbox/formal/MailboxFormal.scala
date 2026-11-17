package deadhorse.mailbox

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

class MailboxBadHead(json: String, owner: Int) extends MailboxEndpoint(json, owner) {
  override protected def readHead(value: UInt): UInt = value ^ 1.U
}

/** Endpoint proof using only public bus and FIFO-side ports. The reference is
  * the five-register software contract, not the generated register internals.
  * FIFO inputs are arbitrary: no queue or clock-progress premise is assumed.
  */
class MailboxFormal(json: String, variant: String, owner: Int) extends RawModule {
  val clock = IO(Input(Clock())); val reset_n = IO(Input(Bool()))
  val bus = IO(new deadhorse.lib.LocalBus)
  val txReady = IO(Input(Bool())); val txUp = IO(Input(Bool()))
  val rxValid = IO(Input(Bool())); val rxUp = IO(Input(Bool()))
  val rxData = IO(Input(UInt(32.W)))
  val d = Module(if (variant == "corrupt") new MailboxBadHead(json, owner) else new MailboxEndpoint(json, owner))
  d.clk := clock; d.reset_n := reset_n; d.bus <> bus
  d.txReady := txReady; d.txUp := txUp; d.rxValid := rxValid; d.rxUp := rxUp; d.rxData := rxData

  withClockAndReset(clock, (!reset_n).asAsyncReset) {
    val accept = bus.req && bus.gnt
    val window = bus.bits.addr >= "h40001000".U && bus.bits.addr < "h40001100".U
    val authorized = window && bus.bits.origin === owner.U
    val offset = bus.bits.addr(7, 0)
    val known = Seq(0, 4, 8, 12, 16).map(n => offset === n.U).reduce(_ || _)
    val partial = bus.bits.we && offset === 0.U && bus.bits.be =/= 0.U && bus.bits.be =/= 15.U
    val failed = !authorized || !known || partial
    val normal1 = RegNext(accept && authorized, false.B)
    val denied1 = RegNext(accept && !authorized, false.B)
    val normal2 = RegNext(normal1, false.B)
    val normal3 = RegNext(normal2, false.B)
    val error1 = RegNext(failed, false.B)
    val error2 = RegNext(error1, false.B)
    val error3 = RegNext(error2, false.B)
    val address1 = RegNext(offset)
    val write1 = RegNext(bus.bits.we)
    val data1 = RegNext(bus.bits.wdata)
    val be1 = RegNext(bus.bits.be)
    val legalWrite1 = normal1 && !error1 && write1

    // A register command is visible on the FIFO port two edges after the
    // local grant. Staging changes when that public strobe would be consumed.
    val push = RegNext(legalWrite1 && address1 === 4.U && be1(0) && data1(0), false.B)
    val pop = RegNext(legalWrite1 && address1 === 4.U && be1(0) && data1(1), false.B)
    val stage = RegNext(legalWrite1 && address1 === 0.U && be1 === 15.U, false.B)
    val stagedData = RegNext(data1)
    val staging = RegInit(0.U(32.W))
    when(stage) { staging := stagedData }

    val link = txUp && rxUp
    val oldLink = RegNext(link, false.B)
    val events = RegInit(VecInit(Seq.fill(3)(false.B)))
    val setting = VecInit(Seq(push && (!txReady || !link), pop && (!rxValid || !link), oldLink && !link))
    val clearing = legalWrite1 && address1 === 16.U && be1(0)
    for (i <- 0 until 3) {
      when(clearing && data1(i)) { events(i) := false.B }
      when(setting(i)) { events(i) := true.B }
    }

    val expectedRead = RegInit(0.U(32.W))
    val responseOffset = Reg(UInt(8.W))
    when(normal1) {
      responseOffset := address1
      expectedRead := 0.U
      when(!write1 && !error1) {
        when(address1 === 8.U && link && rxValid) { expectedRead := rxData }
        when(address1 === 12.U) { expectedRead := Cat(link, link && rxValid, link && txReady) }
        when(address1 === 16.U) { expectedRead := events.asUInt }
      }
    }
    val outstanding = RegInit(false.B)
    when(accept) { outstanding := true.B }
    when(bus.rvalid) { outstanding := false.B }

    if (variant != "cover") {
      assert(bus.rvalid === (denied1 || normal3))
      when(bus.rvalid) {
        assert(outstanding)
        assert(bus.err === (denied1 || error3))
        assert(bus.rdata === Mux(denied1, 0.U, expectedRead))
      }
      assert(!accept || !outstanding)
      assert(d.txPush === push)
      assert(d.rxPop === pop)
      assert(d.txData === staging)
      assert(d.irq === rxValid)
    } else {
      cover(d.txPush && txReady && link && d.txData =/= 0.U)
      cover(d.txPush && !txReady && link)
      cover(d.rxPop && !rxValid && link)
      cover(d.txPush && !link)
      cover(clearing && setting.asUInt.orR)
      for (i <- 0 until 3) cover(bus.rvalid && !bus.err && normal3 && responseOffset === 16.U && bus.rdata(i))
      cover(bus.rvalid && bus.err && denied1)
      cover(bus.rvalid && bus.err && normal3)
      cover(d.irq && d.rxPop)
    }
  }
}

object EmitMailboxFormal {
  def main(args: Array[String]): Unit = {
    require(args.length == 3, "Usage: EmitMailboxFormal <mailbox_regs.json> <owner> build/<output>")
    val owner = args(1).toInt
    val root = Paths.get(args(2)).toAbsolutePath.normalize
    require(root.startsWith(Paths.get("build").toAbsolutePath.normalize))
    for (variant <- Seq("correct", "corrupt", "cover")) {
      val dir = root.resolve(variant); Files.createDirectories(dir)
      ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new MailboxFormal(args(0), variant, owner)),
        Array("--target-dir", dir.toString),
        Array("--disable-all-randomization", "--verification-flavor=immediate", "--lower-to-core", "-strip-debug-info"))
    }
  }
}
