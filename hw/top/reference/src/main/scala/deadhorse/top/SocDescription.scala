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
  def pinWidth(name: String): Int = document("pins")(name)("width").num.toInt
  def origin(name: String): Int = document("masters")(name)("origin").num.toInt
  def watchdogRegion(index: Int): Region = {
    val p=document("watchdog");require(index>=0 && index<p("count").num.toInt)
    require(p("clock").str=="aon" && p("reset").str=="warm")
    require(p("owners").arr.map(_.str).toSeq==Seq("performance","lite"))
    val size=BigInt(p("size").num.toLong)
    Region(s"watchdog$index",region(p("parent").str).base+BigInt(p("offset").num.toLong)+index*size,size)
  }
  def bootControlRegion: Region = {
    val p=document("boot_control")
    require(p("clock").str=="aon" && p("reset").str=="warm" && p("owner").str=="performance")
    Region("boot_control",region(p("parent").str).base+BigInt(p("offset").num.toLong),BigInt(p("size").num.toLong))
  }
  def powerResetRegion: Region = {
    val p=document("power_reset")
    require(p("clock").str=="aon" && p("reset").str=="warm" && p("owner").str=="performance")
    Region("power_reset",region(p("parent").str).base+BigInt(p("offset").num.toLong),BigInt(p("size").num.toLong))
  }
  def oscControlRegion: Region = {
    val p=document("osc_ctrl")
    require(p("clock").str=="aon" && p("reset").str=="warm" && p("owner").str=="performance")
    Region("osc_ctrl",region(p("parent").str).base+BigInt(p("offset").num.toLong),BigInt(p("size").num.toLong))
  }
  def qspiRegion: Region = {
    val p=document("qspi")
    require(p("clock").str=="main" && p("reset").str=="warm" && p("reset_owner").str=="performance")
    require(p("owners").arr.map(_.str).toSeq==Seq("performance"))
    region(p("region").str)
  }
  def xipRegion: Region = {
    val p=document("qspi_xip")
    require(p("clock").str=="main" && p("reset").str=="warm" && p("owner").str=="performance")
    require(p("control").str=="qspi_control")
    val r=region(p("region").str)
    require(r.base==BigInt("10000000",16) && r.size==BigInt("10000000",16))
    r
  }
  def retainedProgramBytes: Int=document("retained_layout")("program_bytes").num.toInt
  def pwmRegion: Region = {
    val p=document("general_timers")
    require(p("reset").str=="warm" && p("clock").str=="main" && p("owner").str=="performance")
    val parent=region(p("parent").str)
    Region("pwm",parent.base+BigInt(p("offset").num.toLong),BigInt(p("size").num.toLong))
  }
  def dmaEndpoints: deadhorse.dma.DmaEndpoints = {
    val p=document("dma")
    require(p("reset").str=="warm" && p("owner").str=="performance" && p("memory").str=="performance_sram")
    val e=document("dma_endpoints")
    def values(name: String)=e(name).arr.toSeq.map(v=>BigInt(v.num.toLong))
    deadhorse.dma.DmaEndpoints(values("data"),values("command"),values("command_value"),values("period"),BigInt(e("pending").num.toLong))
  }
  def pinmuxRegion: Region = {
    val p=document("pinmux")
    require(p("clock").str=="main" && p("reset").str=="warm" && p("owner").str=="performance")
    require(p("sources").arr.map(_.str).toSeq==Seq("disconnected","gpio","timer_compare","pwm"))
    require(p("channels").arr.map(_.num.toInt).toSeq==Seq(0,1,2))
    Region("pinmux",region(p("parent").str).base+BigInt(p("offset").num.toLong),BigInt(p("size").num.toLong))
  }
  def ioRegion(name: String): Region = {
    val p=document("flight_io")(name);val parent=region(p("parent").str)
    Region(name,parent.base+BigInt(p("offset").num.toLong),BigInt(p("size").num.toLong))
  }
  def group(name: String): Seq[String] = document("groups")(name)("members").arr.toSeq.map(_.str)
  def fabric(domain: String): Seq[String] = document("fabrics")(domain).arr.toSeq.map(_.str)
  def aperture(name: String): Region = if(document.obj.get("groups").exists(_.obj.contains(name))) {
    val r=document("groups")(name)
    Region(name, BigInt(r("base").num.toLong), BigInt(r("size").num.toLong))
  } else { val r=region(name); r.copy(size=BigInt(1) << (r.size-1).bitLength) }
  def expanded(name: String): Seq[Region] = if(document("groups").obj.contains(name)) group(name).map(region) else Seq(region(name))
}
