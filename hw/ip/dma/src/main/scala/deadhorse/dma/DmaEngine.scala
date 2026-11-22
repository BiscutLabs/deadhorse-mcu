package deadhorse.dma

import chisel3._
import chisel3.util._
import deadhorse.lib._

case class DmaEndpoints(data: Seq[BigInt],command: Seq[BigInt],commandValue: Seq[BigInt],
                        period: Seq[BigInt],pending: BigInt) {
  require(data.size==17 && command.size==17 && commandValue.size==17 && period.size==9)
  require((data++command++period:+pending).forall(a=>a>=0 && a<=(BigInt(1)<<32)-4 && a%4==0))
}
class DmaSettings extends Bundle {
  val address=UInt(32.W);val count=UInt(16.W);val endpoint=UInt(5.W)
}

/** A shared bus transaction engine; per-channel partial items yield between responses. */
class DmaEngine(endpoints: DmaEndpoints,memoryBase: BigInt,memorySize: BigInt,
                memoryOrigin: Int=1,formalChecks: Boolean=false) extends RawModule {
  require(memoryBase>=0 && memoryBase%4==0 && memorySize>0 && memorySize%4==0 && memoryBase+memorySize<(BigInt(1)<<32))
  val clk=IO(Input(Clock()));val reset_n=IO(Input(Bool()));val owner=IO(Input(UInt(3.W)))
  val settings=IO(Input(Vec(4,new DmaSettings)));val start=IO(Input(UInt(4.W)));val abort=IO(Input(UInt(4.W)))
  val requests=IO(Input(UInt(17.W)));val pwmAck=IO(Output(UInt(9.W)))
  val memory=IO(Flipped(new LocalBus));val peripheral=IO(Flipped(new LocalBus))
  val busy=IO(Output(UInt(4.W)));val remaining=IO(Output(Vec(4,UInt(16.W))))
  val current=IO(Output(Vec(4,UInt(32.W))));val fault=IO(Output(Vec(4,UInt(4.W))))
  val done=IO(Output(UInt(4.W)));val failed=IO(Output(UInt(4.W)))
  val rejected=IO(Output(UInt(4.W)));val aborted=IO(Output(UInt(4.W)));val clockHold=IO(Output(Bool()))
  protected def copied(value: UInt): UInt=value
  protected def busOrigin(value: UInt): UInt=value

  withClockAndReset(clk,(!reset_n).asAsyncReset) {
    val fresh=0.U(3.W);val txWrite=1.U(3.W);val rxStore=2.U(3.W);val rxPop=3.U(3.W)
    val pwmPeriod=4.U(3.W);val pwmWrite=5.U(3.W);val pwmPending=6.U(3.W);val pwmApply=7.U(3.W)
    val idle :: offerMem :: waitMem :: offerPer :: waitPer :: Nil=Enum(5)
    val state=RegInit(idle);val selected=RegInit(0.U(2.W));val operation=RegInit(fresh)
    val priority=RegInit(0.U(2.W))
    val active=RegInit(VecInit(Seq.fill(4)(false.B)));val stopping=RegInit(VecInit(Seq.fill(4)(false.B)))
    val address=RegInit(VecInit(Seq.fill(4)(0.U(32.W))))
    val left=RegInit(VecInit(Seq.fill(4)(0.U(16.W))))
    val selector=RegInit(VecInit(Seq.fill(4)(0.U(5.W))))
    val origin=RegInit(VecInit(Seq.fill(4)(0.U(3.W))))
    val stage=RegInit(VecInit(Seq.fill(4)(fresh)))
    val data=RegInit(VecInit(Seq.fill(4)(0.U(32.W))))
    val errors=RegInit(VecInit(Seq.fill(4)(0.U(4.W))))
    val completion=RegInit(VecInit(Seq.fill(4)(false.B)));val failure=RegInit(VecInit(Seq.fill(4)(false.B)))
    val configError=RegInit(VecInit(Seq.fill(4)(false.B)));val cancellation=RegInit(VecInit(Seq.fill(4)(false.B)))
    val ack=RegInit(0.U(9.W));ack:=0.U
    Seq(completion,failure,configError,cancellation).foreach(_.foreach(_:=false.B))
    val mReq=RegInit(false.B);val pReq=RegInit(false.B);val payload=Reg(new BusPayload)
    memory.req:=mReq;peripheral.req:=pReq;memory.bits:=payload;peripheral.bits:=payload
    busy:=active.asUInt;remaining:=left;current:=address;fault:=errors;pwmAck:=ack
    done:=completion.asUInt;failed:=failure.asUInt;rejected:=configError.asUInt;aborted:=cancellation.asUInt
    clockHold:=RegNext(active.asUInt.orR || state=/=idle,false.B)

    val accepted=Wire(Vec(4,Bool()))
    for(i<-0 until 4) {
      val c=settings(i);val wide=c.endpoint>=8.U
      val span=Mux(wide,c.count<<2,c.count)
      val end=c.address+&span
      val duplicate=(0 until 4).filter(_!=i).map(j=>active(j) && selector(j)===c.endpoint).reduce(_||_) ||
        (0 until i).map(j=>accepted(j) && settings(j).endpoint===c.endpoint).foldLeft(false.B)(_||_)
      val valid=c.endpoint<17.U && c.count=/=0.U && owner===memoryOrigin.U &&
        (!wide || c.address(1,0)===0.U) && c.address>=memoryBase.U && end<=(memoryBase+memorySize).U
      accepted(i):=start(i) && !abort(i) && !active(i) && valid && !duplicate
      when(start(i) && !abort(i)) {
        when(accepted(i)) {
          active(i):=true.B;stopping(i):=false.B;address(i):=c.address;left(i):=c.count
          selector(i):=c.endpoint;origin(i):=owner;stage(i):=fresh;errors(i):=0.U
        }.otherwise {configError(i):=true.B}
      }
      when(abort(i) && active(i)) {
        when(stage(i)===fresh && !(state=/=idle && selected===i.U)) {
          active(i):=false.B;stopping(i):=false.B;cancellation(i):=true.B
        }.otherwise {stopping(i):=true.B}
      }
    }
    val eligible=VecInit((0 until 4).map {i=>
      val needsHint=stage(i)===fresh || stage(i)===txWrite
      active(i) && !(stage(i)===fresh && (abort(i)||stopping(i))) && (!needsHint || requests(selector(i)))
    })
    val found=WireDefault(false.B);val chosen=WireDefault(0.U(2.W))
    for(offset<-(0 until 4).reverse) {
      val index=(priority+offset.U)(1,0)
      when(eligible(index)) {found:=true.B;chosen:=index}
    }
    when(state===idle && found) {
      val sel=selector(chosen);val step=stage(chosen);val wide=sel>=8.U
      val receiving= !wide && sel(0)
      val first=step===fresh
      val mem=(first && !receiving) || step===rxStore
      val write=step===txWrite || step===rxStore || step===rxPop || step===pwmWrite || step===pwmApply
      val dataAddress=VecInit(endpoints.data.map(_.U(32.W)))(sel)
      val commandAddress=VecInit(endpoints.command.map(_.U(32.W)))(sel)
      val commandData=VecInit(endpoints.commandValue.map(_.U(32.W)))(sel)
      val pwmIndex=(sel-8.U)(3,0)
      val peripheralAddress=Mux(step===rxPop || step===pwmApply,commandAddress,
        Mux(step===pwmPeriod,VecInit(endpoints.period.map(_.U(32.W)))(pwmIndex),
          Mux(step===pwmPending,endpoints.pending.U,dataAddress)))
      val lane=address(chosen)(1,0)
      val writeData=Mux(step===rxPop || step===pwmApply,commandData,
        Mux(step===rxStore,data(chosen)<<(lane<<3),data(chosen)))
      payload.addr:=Mux(mem,address(chosen)&"hfffffffc".U,peripheralAddress)
      payload.we:=write;payload.origin:=busOrigin(origin(chosen))
      payload.wdata:=copied(writeData)
      payload.be:=Mux(step===rxStore,1.U<<lane,Mux(step===txWrite || step===rxPop,1.U,15.U))
      selected:=chosen;operation:=step;mReq:=mem;pReq:= !mem
      state:=Mux(mem,offerMem,offerPer)
    }
    when(state===offerMem && memory.gnt) {mReq:=false.B;state:=waitMem}
    when(state===offerPer && peripheral.gnt) {pReq:=false.B;state:=waitPer}
    val response=(state===waitMem && memory.rvalid) || (state===waitPer && peripheral.rvalid)
    when(response) {
      val value=Mux(state===waitMem,memory.rdata,peripheral.rdata)
      val error=Mux(state===waitMem,memory.err,peripheral.err)
      val sel=selector(selected);val wide=sel>=8.U;val receiving= !wide && sel(0)
      state:=idle;priority:=selected+1.U
      def fail(code: UInt): Unit={
        active(selected):=false.B;stopping(selected):=false.B;stage(selected):=fresh
        errors(selected):=code;failure(selected):=true.B
      }
      def finish(): Unit={
        left(selected):=left(selected)-1.U;address(selected):=address(selected)+Mux(wide,4.U,1.U)
        stage(selected):=fresh
        when(left(selected)===1.U || stopping(selected) || abort(selected)) {
          active(selected):=false.B;stopping(selected):=false.B
          when(stopping(selected)||abort(selected)) {cancellation(selected):=true.B}
            .otherwise {completion(selected):=true.B}
        }
      }
      when(error) {fail(operation+&1.U)}.otherwise {
        switch(operation) {
          is(fresh) {
            when(wide) {data(selected):=value;stage(selected):=pwmPeriod}
              .elsewhen(receiving) {data(selected):=value(7,0);stage(selected):=rxStore}
              .otherwise {data(selected):=(value>>(address(selected)(1,0)<<3))(7,0);stage(selected):=txWrite}
          }
          is(txWrite) {finish()}
          is(rxStore) {stage(selected):=rxPop}
          is(rxPop) {finish()}
          is(pwmPeriod) {
            when(data(selected)>(value(15,0)+&1.U)) {fail(9.U)}
              .otherwise {stage(selected):=pwmWrite}
          }
          is(pwmWrite) {stage(selected):=pwmPending}
          is(pwmPending) {when(!value(sel-8.U)) {stage(selected):=pwmApply}}
          is(pwmApply) {finish();ack:=1.U<<(sel-8.U)}
        }
      }
    }
    if(formalChecks) {
      val past=RegNext(true.B,false.B);val heldM=RegNext(memory.req && !memory.gnt,false.B)
      val heldP=RegNext(peripheral.req && !peripheral.gnt,false.B);val oldPayload=RegNext(payload)
      assert(!(memory.req && peripheral.req))
      when(memory.req || peripheral.req) {assert(payload.origin===memoryOrigin.U);assert(payload.addr(1,0)===0.U)}
      when(memory.req) {assert(payload.addr>=memoryBase.U && payload.addr<(memoryBase+memorySize).U)}
      when(past && heldM) {assert(memory.req && payload.asUInt===oldPayload.asUInt)}
      when(past && heldP) {assert(peripheral.req && payload.asUInt===oldPayload.asUInt)}
      for(i<-0 until 4) {when(active(i)) {assert(left(i)=/=0.U && selector(i)<17.U)}}
    }
  }
}
