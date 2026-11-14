package deadhorse.lib

import chisel3._
import chisel3.util._
import scala.collection.immutable.ListMap

case class RegField(register: String, offset: BigInt, name: String, lsb: Int,
                    msb: Int, access: String, resetValue: BigInt) {
  val width: Int = msb - lsb + 1
  val key: String = s"${register}_${name}"
  val byteMask: Int = (lsb / 8 to msb / 8).map(1 << _).sum
  val stored: Boolean = Set("rw", "rwh", "w1c")(access)
  def ports: Seq[(String, Int, Boolean)] = access match {
    case "rw" => Seq(("q", width, false))
    case "ro" => Seq(("d", width, true))
    case "w1c" => Seq(("q", width, false), ("set", width, true))
    case "w1p" => Seq(("pulse", width, false))
    case "rwh" => Seq(("q", width, false), ("d", width, true), ("we", 1, true))
    case "wo" => Seq(("wdata", width, false), ("we", 1, false))
  }
}

/** Reads only the validated, expanded interchange format, never YAML. */
class RegDescription(json: String) {
  private val doc = ujson.read(os.read(os.Path(json, os.pwd)))
  val addressWidth: Int = doc("address_width").num.toInt
  val offsets: Seq[BigInt] = doc("registers").arr.toSeq.map(r => BigInt(r("offset").str))
  val fields: Seq[RegField] = doc("registers").arr.toSeq.flatMap { r =>
    r("fields").arr.toSeq.map { f =>
      RegField(r("name").str, BigInt(r("offset").str), f("name").str,
        f("lsb").num.toInt, f("msb").num.toInt, f("access").str,
        f.obj.get("reset").map(v => BigInt(v.num.toLong)).getOrElse(BigInt(0)))
    }
  }
}

class RegHardware(val fields: Seq[RegField]) extends Record {
  val elements: ListMap[String, Data] = ListMap.from(fields.flatMap { f =>
    f.ports.map { case (suffix, width, input) =>
      s"${f.key}_$suffix" -> (if (input) Input(UInt(width.W)) else Output(UInt(width.W)))
    }
  })
  def apply(name: String): UInt = elements(name).asInstanceOf[UInt]
}

/** Single-domain registered target with asynchronous active-low reset. */
class RegBlock(json: String) extends RawModule {
  def this(json: os.Path) = this(json.toString)
  val description = new RegDescription(json)
  val clk = IO(Input(Clock()))
  val rst_n = IO(Input(Bool()))
  val bus = IO(new RegBus(description.addressWidth))
  val hw = IO(new RegHardware(description.fields))

  // Overridden only by deliberate fault modules in the formal harness.
  protected def strobes: UInt = bus.req_wstrb
  protected def initialValue(f: RegField): BigInt = f.resetValue
  protected def readResult(value: UInt): UInt = value

  withClockAndReset(clk, (!rst_n).asAsyncReset) {
    val ready = RegInit(true.B)
    val valid = RegInit(false.B)
    val response = RegInit(0.U(32.W))
    val responseError = RegInit(false.B)
    bus.req_ready := ready
    bus.rsp_valid := valid
    bus.rsp_rdata := response
    bus.rsp_error := responseError
    val accept = bus.req_valid && ready
    val hit = description.offsets.map(o => o -> (bus.req_addr === o.U)).toMap
    val mapped = hit.values.foldLeft(false.B)(_ || _)
    val partialAt = description.offsets.map { offset =>
      offset -> description.fields.filter(f => f.offset == offset && f.access == "wo").map { f =>
        val enabled = strobes & f.byteMask.U(4.W)
        enabled.orR && enabled =/= f.byteMask.U
      }.foldLeft(false.B)(_ || _)
    }.toMap
    val partialCommand = description.offsets.map(o => hit(o) && partialAt(o))
      .foldLeft(false.B)(_ || _)
    val error = !mapped || bus.req_addr(1, 0).orR || (bus.req_write && partialCommand)
    val write = accept && bus.req_write
    val writeMask = Cat((3 to 0 by -1).map(i => Fill(8, strobes(i))))
    val readFields = description.fields.map { f =>
      // Full decode implies mapped/aligned. Keep command-error qualification
      // local so the global response-error reduction does not drive storage.
      val selected = write && hit(f.offset) && !partialAt(f.offset)
      val data = bus.req_wdata(f.msb, f.lsb)
      val mask = writeMask(f.msb, f.lsb)
      val stored = if (f.stored) Some(RegInit(initialValue(f).U(f.width.W))) else None
      stored.foreach(q => hw(f.key + "_q") := q)
      f.access match {
        case "rw" | "rwh" =>
          val q = stored.get
          when(selected) { q := (q & ~mask) | (data & mask) }
          if (f.access == "rwh") {
            when(hw(f.key + "_we").asBool) { q := hw(f.key + "_d") }
          }
        case "w1c" =>
          val q = stored.get
          val clear = Mux(selected, data & mask, 0.U(f.width.W))
          q := (q & ~clear) | hw(f.key + "_set")
        case "w1p" =>
          hw(f.key + "_pulse") := RegNext(Mux(selected, data & mask, 0.U(f.width.W)), 0.U(f.width.W))
        case "wo" =>
          val issue = selected && (strobes & f.byteMask.U(4.W)).orR
          hw(f.key + "_we") := RegNext(issue, false.B).asUInt
          hw(f.key + "_wdata") := RegNext(Mux(issue, data, 0.U(f.width.W)), 0.U(f.width.W))
        case "ro" => ()
      }
      val read = if (f.stored) stored.get else if (f.access == "ro") hw(f.key + "_d") else 0.U(f.width.W)
      Mux(hit(f.offset), (read.pad(32) << f.lsb)(31, 0), 0.U(32.W))
    }
    val readData = readFields.foldLeft(0.U(32.W))(_ | _)
    when(valid && bus.rsp_ready) {
      valid := false.B
      ready := true.B
    }
    when(accept) {
      valid := true.B
      ready := false.B
      // The one-hot read mux already returns zero for unmapped/misaligned
      // addresses. Command errors only occur on writes, which return zero.
      response := Mux(bus.req_write, 0.U, readResult(readData))
      responseError := error
    }
  }
}
