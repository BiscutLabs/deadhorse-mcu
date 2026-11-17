package deadhorse.lib

import chisel3._
import chisel3.simulator.ChiselSim
import chisel3.testing.HasTestingDirectory
import java.nio.file.Paths
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.exceptions.TestFailedException
import scala.collection.mutable
import scala.util.Random

class CdcTest(width: Int, depth: Int, corrupt: Boolean = false) extends RawModule {
  val wc = IO(Input(Bool())); val rc = IO(Input(Bool()))
  val wn = IO(Input(Bool())); val rn = IO(Input(Bool()))
  val push = IO(Input(Bool())); val data = IO(Input(UInt(width.W)))
  val pop = IO(Input(Bool())); val ready = IO(Output(Bool()))
  val valid = IO(Output(Bool())); val out = IO(Output(UInt(width.W)))
  val pending = IO(Output(Bool())); val wu = IO(Output(Bool())); val ru = IO(Output(Bool()))
  val dut = Module(new CdcFifo(width, depth))
  dut.writeClock := wc.asClock; dut.readClock := rc.asClock
  dut.writeReset_n := wn; dut.readReset_n := rn
  dut.push := push; dut.in := data; dut.pop := pop
  ready := dut.ready; valid := dut.valid
  out := (if (corrupt) dut.out ^ 1.U else dut.out)
  pending := dut.writePending; wu := dut.writeUp; ru := dut.readUp
}

class CdcSpec extends AnyFunSuite with ChiselSim {
  implicit val outputDirectory: HasTestingDirectory = new HasTestingDirectory {
    def getDirectory = Paths.get("build/t14/cdc-simulation").toAbsolutePath
  }
  def check(d: CdcTest, width: Int, depth: Int): Unit = {
    val seed = 0xcdc1401L; val random = new Random(seed)
    println(s"CDC seed=$seed width=$width depth=$depth")
    val q = mutable.Queue.empty[BigInt]
    var accepted = 0; var consumed = 0
    def value(b: Bool) = b.peek().litValue == 1
    def observe(): Unit = {
      if (value(d.valid)) {
        assert(q.nonEmpty, "CDC_MODEL_MISMATCH empty read")
        assert(d.out.peek().litValue == q.front, "CDC_MODEL_MISMATCH corrupt/reordered word")
      }
      assert(q.size <= depth, "CDC_MODEL_MISMATCH overflow")
    }
    d.wc.poke(false.B); d.rc.poke(false.B)
    d.wn.poke(true.B); d.rn.poke(true.B)
    d.push.poke(false.B); d.pop.poke(false.B); d.data.poke(0.U)
    d.valid.peek()
    def reset(writer: Boolean): Unit = {
      if (writer) d.wn.poke(false.B) else d.rn.poke(false.B)
      q.clear()
      assert(!value(d.valid) && !value(d.ready), "CDC_MODEL_MISMATCH asynchronous flush")
      assert(!value(d.wu) && !value(d.ru), "CDC_MODEL_MISMATCH release")
      if (writer) d.wn.poke(true.B) else d.rn.poke(true.B)
      assert(!value(d.valid) && !value(d.ready), "CDC_MODEL_MISMATCH stopped reset release")
    }
    reset(true)
    def step(w: Boolean, r: Boolean, put: Boolean, take: Boolean): Unit = {
      val data = BigInt(width, random)
      d.push.poke(put.B); d.pop.poke(take.B); d.data.poke(data.U)
      observe()
      val pop = r && take && value(d.valid)
      val push = w && put && value(d.ready)
      if (pop) { q.dequeue(); consumed += 1 }
      if (push) { q.enqueue(data); accepted += 1 }
      d.wc.poke(w.B); d.rc.poke(r.B); d.valid.peek()
      d.wc.poke(false.B); d.rc.poke(false.B); d.valid.peek()
      observe()
    }
    // No receiving edge: fills exactly depth, asserts sender-side wake.
    for (_ <- 0 until 16) step(true, false, true, false)
    assert(q.size == depth && !value(d.ready) && value(d.pending))
    for (_ <- 0 until 30) step(true, true, false, true)
    assert(q.isEmpty && !value(d.pending))
    // Arbitrary clock ratios, stopped-clock spans, simultaneous edges and resets.
    for (i <- 0 until 1600) {
      if (i % 173 == 0) reset((i / 173) % 2 == 0)
      val w = i % 97 >= 19 && random.nextBoolean()
      val r = i % 89 >= 23 && random.nextBoolean()
      step(w, r, random.nextInt(4) != 0, random.nextBoolean())
    }
    for (_ <- 0 until 40) step(true, true, false, true)
    assert(q.isEmpty && !value(d.valid) && !value(d.pending))
    assert(accepted > 50 && consumed > 30)
    reset(false)
  }
  for ((width, depth) <- Seq((32, 2), (72, 2), (8, 4))) {
    test(s"CDC queue model with independent clocks, held head, wrap and either-side reset $width/$depth") {
      simulateRaw(new CdcTest(width, depth), subdirectory = Some(s"w${width}d$depth"))(check(_, width, depth))
    }
  }
  test("CDC queue checker rejects corrupted delivered data") {
    val failure = intercept[TestFailedException] {
      simulateRaw(new CdcTest(32, 2, true), subdirectory = Some("corrupt"))(check(_, 32, 2))
    }
    assert(failure.getMessage.contains("CDC_MODEL_MISMATCH"))
  }
}
