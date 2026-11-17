package deadhorse.bus

import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files,Paths}

class FormalBadBus(limit:Int) extends BusFabric(3,Seq(BusRegion(0x1000,256,limit),BusRegion(0x2000,256,limit))) {
  override protected def response(value: UInt): UInt = value ^ 1.U
}

class BusFormal(variant: String, limit:Int=128) extends RawModule {
  val clock = IO(Input(Clock()));val reset_n = IO(Input(Bool()))
  val req = IO(Input(Vec(3,Bool())));val addr = IO(Input(Vec(3,UInt(32.W))))
  val data = IO(Input(Vec(3,UInt(32.W))));val write = IO(Input(Vec(3,Bool())))
  val be = IO(Input(Vec(3,UInt(4.W))));val allow = IO(Input(Vec(3,Bool())))
  val grantTarget = IO(Input(Vec(2,Bool())))
  val replyTarget = IO(Input(Vec(2,Bool())));val errorTarget = IO(Input(Vec(2,Bool())))
  val dataTarget = IO(Input(Vec(2,UInt(32.W))));val cancelTarget = IO(Input(Vec(2,Bool())))
  val admitTarget = IO(Input(Vec(2,Bool())))
  def design: BusFabric = if(variant=="corrupt")new FormalBadBus(limit) else new BusFabric(3,Seq(BusRegion(0x1000,256,limit),BusRegion(0x2000,256,limit)))
  val d=Module(design);d.clk:=clock;d.reset_n:=reset_n
  for(i<-0 until 3){
    d.master(i).req:=req(i);d.master(i).bits.addr:=addr(i);d.master(i).bits.wdata:=data(i)
    d.master(i).bits.we:=write(i);d.master(i).bits.be:=be(i);d.master(i).bits.origin:=i.U;d.allow(i):=allow(i)
  }
  d.admit:=admitTarget
  withClockAndReset(clock,(!reset_n).asAsyncReset){
    val held=RegInit(VecInit(Seq.fill(3)(false.B)))
    val previousAddr=Reg(Vec(3,UInt(32.W)));val previousData=Reg(Vec(3,UInt(32.W)))
    val previousWrite=Reg(Vec(3,Bool()));val previousBe=Reg(Vec(3,UInt(4.W)))
    for(i<-0 until 3){
      when(held(i)){assume(req(i));assume(addr(i)===previousAddr(i));assume(data(i)===previousData(i));assume(write(i)===previousWrite(i));assume(be(i)===previousBe(i))}
      held(i):=req(i)&& !d.master(i).gnt
      previousAddr(i):=addr(i);previousData(i):=data(i);previousWrite(i):=write(i);previousBe(i):=be(i)
    }
    for(t<-0 until 2){
      val outstanding=RegInit(false.B)
      d.target(t).gnt:=grantTarget(t)&& !outstanding
      d.target(t).rvalid:=outstanding&&replyTarget(t)
      d.target(t).rdata:=dataTarget(t);d.target(t).err:=errorTarget(t)
      d.quiescent(t):= !outstanding
      when(outstanding&&(replyTarget(t)||cancelTarget(t))){outstanding:=false.B}
      when(d.target(t).req&&d.target(t).gnt){outstanding:=true.B}
    }
    val pending=RegInit(false.B);val owner=Reg(UInt(2.W));val age=RegInit(0.U(log2Ceil(limit+2).W))
    val expected=Reg(UInt(32.W));val bad=Reg(Bool());val expectedAddr=Reg(UInt(32.W))
    val expectedData=Reg(UInt(32.W));val expectedBe=Reg(UInt(4.W));val expectedWe=Reg(Bool())
    val targetIssued=RegInit(false.B);val targetReplied=RegInit(false.B);val targetError=Reg(Bool())
    val accepted=VecInit(d.master.map(m=>m.req&&m.gnt))
    val returned=VecInit(d.master.map(_.rvalid))
    when(pending){age:=age+1.U}
    when(returned.asUInt.orR){pending:=false.B}
    for(i<-0 until 3){
      val mapped=addr(i)>=0x1000.U&&addr(i)<0x1100.U || addr(i)>=0x2000.U&&addr(i)<0x2100.U
      val isolated=Mux(addr(i)>=0x2000.U,d.isolated(1),d.isolated(0))
      when(accepted(i)){
        pending:=true.B;owner:=i.U;age:=1.U
        bad:= !mapped||addr(i)(1,0).orR|| !allow(i)||isolated
        expected:=Mux(write(i),0.U,addr(i)^"h5a13ac91".U)
        expectedAddr:=addr(i);expectedData:=data(i);expectedBe:=be(i);expectedWe:=write(i)
        targetIssued:=false.B;targetReplied:=false.B
      }
      val fairness=3*(limit+4)+4
      val waited=RegInit(0.U(log2Ceil(fairness+2).W))
      val admission=Mux(addr(i)>=0x2000.U,admitTarget(1),admitTarget(0))
      when(!req(i)||d.master(i).gnt||(mapped && !admission && !isolated)){waited:=0.U}.otherwise{waited:=waited+1.U}
      if(variant!="cover")assert(waited<fairness.U)
    }
    for(t<-0 until 2){
      when(d.target(t).req&&d.target(t).gnt){
        if(variant!="cover")assert(pending&& !targetIssued)
        targetIssued:=true.B
      }
      val matches=expectedAddr>=(0x1000*(t+1)).U && expectedAddr<(0x1000*(t+1)+256).U
      when(pending&&targetIssued&&matches&&d.target(t).rvalid){
        targetReplied:=true.B;targetError:=d.target(t).err
        expected:=Mux(expectedWe,0.U,d.target(t).rdata)
      }
    }
    if(variant!="cover"){
      assert(PopCount(accepted)<=1.U && PopCount(returned)<=1.U)
      assert(!accepted.asUInt.orR || !pending)
      assert(!pending || age<=limit.U)
      for(i<-0 until 3){when(d.master(i).rvalid){
        assert(pending&&owner===i.U)
        assert((!bad || d.master(i).err) && (!d.master(i).err || bad || age===limit.U || (targetReplied&&targetError)))
        assert(d.master(i).err || (targetIssued&&targetReplied&& !targetError))
        assert(d.master(i).rdata===Mux(d.master(i).err,0.U,expected))
      }}
      assert(PopCount(VecInit(d.target.map(_.req)))<=1.U)
      for(t<-0 until 2){when(d.target(t).req){
        assert(pending && !bad)
        assert(d.target(t).bits.addr===expectedAddr && d.target(t).bits.wdata===expectedData && d.target(t).bits.be===expectedBe && d.target(t).bits.we===expectedWe && d.target(t).bits.origin===owner)
        assert(expectedAddr>=(0x1000*(t+1)).U && expectedAddr<(0x1000*(t+1)+256).U)
      }}
      when(pending&& !bad&& !targetIssued&&age>=2.U&&age<limit.U){assert(VecInit(d.target.map(_.req)).asUInt.orR)}
    } else {
      for(i<-0 until 3)cover(d.master(i).rvalid && !d.master(i).err)
      cover(returned.asUInt.orR && bad)
      cover(returned.asUInt.orR && age===limit.U)
      cover(d.isolated.asUInt.orR && accepted.asUInt.orR)
      cover(d.isolated(0)&&d.target(0).rvalid)
      cover(d.isolated(0)&&d.quiescent(0))
      cover(returned.asUInt.orR && targetReplied && targetError)
      cover(!admitTarget(1)&&accepted.asUInt.orR)
    }
    for(t<-0 until 2){
      val matches=expectedAddr>=(0x1000*(t+1)).U && expectedAddr<(0x1000*(t+1)+256).U
      val timeoutReply=returned.asUInt.orR&&pending&& !bad&&age===limit.U&& !targetReplied&&matches
      val mustRemain=RegNext(d.isolated(t)&& !d.target(t).rvalid&& !d.quiescent(t),false.B)
      if(variant!="cover"){
        assert(!timeoutReply||d.isolated(t))
        assert(!mustRemain||d.isolated(t))
        assert(!d.isolated(t)|| !d.target(t).req)
      }
    }
  }
}

object EmitBusFormal {
  def main(args:Array[String]):Unit={
    require(args.length==2);val limit=args(0).toInt;val root=Paths.get(args(1)).toAbsolutePath.normalize
    require(root.startsWith(Paths.get("build").toAbsolutePath.normalize))
    for(v<-Seq("correct","corrupt","cover")){
      val dir=root.resolve(v);Files.createDirectories(dir)
      ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(new BusFormal(v,limit)),Array("--target-dir",dir.toString),
        Array("--disable-all-randomization","--verification-flavor=immediate","--lower-to-core","-strip-debug-info"))
    }
  }
}
