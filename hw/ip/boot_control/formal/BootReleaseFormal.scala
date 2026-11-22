package deadhorse.boot_control
import chisel3._
import _root_.circt.stage.ChiselStage

/** No protocol assumptions. Independent service/whole resets remain arbitrary. */
class BootReleaseFormal(variant: String) extends RawModule {
  val clock=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val serviceReset_n=IO(Input(Bool()))
  val start=IO(Input(Bool()));val command=IO(Input(Bool()));val key=IO(Input(Bool()))
  val d=Module[BootRelease](variant match {
    case "early"=>new BootRelease {override protected def eligible(seen: Bool,key: Bool): Bool=key}
    case "key"=>new BootRelease {override protected def eligible(seen: Bool,key: Bool): Bool=seen}
    case _=>new BootRelease
  })
  d.clk:=clock;d.epochReset_n:=reset_n;d.serviceReset_n:=serviceReset_n
  d.startAccepted:=start;d.command:=command;d.keyGood:=key
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val past=RegNext(true.B,false.B)
    val oldStart=RegNext(start,false.B);val oldService=RegNext(serviceReset_n,false.B)
    val oldCommand=RegNext(command,false.B);val oldKey=RegNext(key,false.B)
    val oldSeen=RegNext(d.bootSeen,false.B);val oldOpen=RegNext(d.released,false.B)
    if(variant=="cover") {
      cover(d.bootSeen && !d.released)
      cover(d.released && !serviceReset_n)
      cover(d.error)
    } else {
      when(past) {
        assert(d.bootSeen===(oldSeen || (oldService && oldStart)))
        assert(d.released===(oldOpen || (oldService && oldCommand && oldSeen && oldKey)))
        assert(d.error===(serviceReset_n && oldService && oldCommand && (!oldSeen || !oldKey)))
      }
      assert(!d.released || d.bootSeen)
    }
  }
}
object EmitBootReleaseFormal extends App {
  require(args.length==1)
  for(v<-Seq("correct","early","key","cover")) ChiselStage.emitSystemVerilogFile(
    chisel3.layer.elideBlocks(new BootReleaseFormal(v)),Array("--target-dir",s"${args(0)}/$v"),
    Array("--disable-all-randomization","--disable-opt","--lint-static-asserts=false",
      "--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
}
