package deadhorse.top

/** Only consumes the validated JSON generated from soc.yaml. */
class SocDescription(path: String) {
  private val document = ujson.read(os.read(os.Path(path, os.pwd)))
  require(document("schema").num == 1)
  case class Region(name: String, base: BigInt, size: BigInt)
  val regions: Seq[Region] = document("regions").arr.toSeq.map { r =>
    Region(r("name").str, BigInt(r("base").num.toLong), BigInt(r("size").num.toLong))
  }
  require(regions.map(_.name).distinct.size == regions.size)
  def region(name: String): Region = regions.find(_.name == name).getOrElse(
    throw new IllegalArgumentException("Missing SoC region " + name))
  def interrupt(name: String): Int = document("interrupts")(name).num.toInt
  def origin(name: String): Int = document("masters")(name)("origin").num.toInt
}
