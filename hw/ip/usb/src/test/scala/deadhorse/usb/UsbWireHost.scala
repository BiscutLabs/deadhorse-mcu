package deadhorse.usb

import chisel3._
import chisel3.util._
import scala.collection.mutable.ArrayBuffer

trait UsbWirePorts { this: Module =>
  val hostDrive: Bool;val hostDp: Bool;val hostDn: Bool;val vbus: Bool
  val txData: UInt;val txValid: Bool;val txReady: Bool
  val rxData: UInt;val rxValid: Bool;val rxReady: Bool
  val dp: Bool;val dn: Bool;val oe: Bool;val pullupEnable: Bool;val configured: Bool
}
class UsbWireBench(corrupt: Boolean = false) extends Module with UsbWirePorts {
  val hostDrive=IO(Input(Bool())); val hostDp=IO(Input(Bool())); val hostDn=IO(Input(Bool()))
  val vbus=IO(Input(Bool()))
  val txData=IO(Input(UInt(8.W))); val txValid=IO(Input(Bool())); val txReady=IO(Output(Bool()))
  val rxData=IO(Output(UInt(8.W))); val rxValid=IO(Output(Bool())); val rxReady=IO(Input(Bool()))
  val dp=IO(Output(Bool())); val dn=IO(Output(Bool())); val oe=IO(Output(Bool()))
  val pullupEnable=IO(Output(Bool())); val configured=IO(Output(Bool())); val sessionReset=IO(Output(Bool()))
  val engine=Module(new UsbEngine)
  engine.clk:=clock; engine.reset_n := !reset.asBool; engine.vbus:=vbus
  engine.dpRx:=Mux(engine.txEnable,engine.dpTx,Mux(hostDrive,hostDp,engine.pullup))
  engine.dnRx:=Mux(engine.txEnable,engine.dnTx,Mux(hostDrive,hostDn,false.B))
  engine.txData:=txData; engine.txValid:=txValid; txReady:=engine.txReady
  engine.rxReady:=rxReady; rxData:=(if(corrupt) engine.rxData ^ 1.U else engine.rxData); rxValid:=engine.rxValid
  dp:=engine.dpTx; dn:=engine.dnTx; oe:=engine.txEnable; pullupEnable:=engine.pullup
  configured:=engine.configured; sessionReset:=engine.sessionReset
}

/** Independent wire host: USB polynomial CRC, LSB serialization, NRZI and bit stuffing.
  * It observes public pins/byte ports, never implementation state.
  */
class UsbWireHost(d: Module with UsbWirePorts, checkConfiguredReset: Boolean=true) extends chisel3.simulator.PeekPokeAPI {
  val ACK=2; val NAK=10; val STALL=14; val DATA0=3; val DATA1=11; val IN=9; val OUT=1; val SETUP=13
  def bool(x: Bool): Boolean=x.peek().litValue==1
  def step(n: Int=1): Unit=d.clock.step(n)
  def idle(bits: Int=4): Unit={d.hostDrive.poke(false.B); step(bits*4)}
  def initialize(afterReset: ()=>Unit=()=>()): Unit={
    d.hostDrive.poke(false.B); d.hostDp.poke(true.B); d.hostDn.poke(false.B)
    d.vbus.poke(false.B); d.txData.poke(0.U); d.txValid.poke(false.B); d.rxReady.poke(false.B)
    d.reset.poke(true.B); step(8); d.reset.poke(false.B); d.vbus.poke(true.B)
    afterReset()
    step(820000); assert(bool(d.pullupEnable),"USB pull-up failed to attach")
    busReset()
  }
  def busReset(): Unit={
    d.hostDrive.poke(true.B); d.hostDp.poke(false.B); d.hostDn.poke(false.B)
    step(1000); idle(100)
    if(checkConfiguredReset) assert(!bool(d.configured),"USB reset must deconfigure")
  }
  def crc16(bytes: Seq[Int]): Seq[Int]={
    var crc=0xffff
    for(byte<-bytes;bit<-0 until 8){val mix=(crc^(byte>>bit))&1;crc=crc>>>1;if(mix!=0)crc^=0xa001}
    Seq((~crc)&255,((~crc)>>>8)&255)
  }
  def crc5(value: Int): Int={
    var crc=31
    for(bit<-0 until 11){val mix=(crc^(value>>bit))&1;crc=crc>>>1;if(mix!=0)crc^=0x14}
    (~crc)&31
  }
  def packet(pid: Int,payload: Seq[Int]=Seq.empty,corruptPid: Boolean=false): Unit={
    val bytes=Seq((pid|((~pid&15)<<4))^(if(corruptPid)16 else 0))++payload
    val raw=bytes.flatMap(b=>(0 until 8).map(i=>((b>>i)&1)!=0))
    val bits=ArrayBuffer(false,false,false,false,false,false,false,true)
    var ones=0
    raw.foreach { b=> bits+=b; if(b){ones+=1;if(ones==6){bits+=false;ones=0}}else ones=0 }
    var j=true
    d.hostDrive.poke(true.B)
    for(bit<-bits){if(!bit)j = !j;d.hostDp.poke(j.B);d.hostDn.poke((!j).B);step(4)}
    d.hostDp.poke(false.B);d.hostDn.poke(false.B);step(8)
    d.hostDp.poke(true.B);d.hostDn.poke(false.B);step(4)
    d.hostDrive.poke(false.B)
  }
  def token(pid: Int,address: Int,endpoint: Int): Unit={
    val bits=address|(endpoint<<7);packet(pid,Seq(bits&255,((bits>>8)&7)|(crc5(bits)<<3)))
  }
  def data(pid: Int,bytes: Seq[Int],badCrc: Boolean=false): Unit={
    val crc=crc16(bytes);packet(pid,bytes++Seq(crc.head^(if(badCrc)1 else 0),crc(1)))
  }
  def receive(limit: Int=4000): (Int,Seq[Int])={
    var waited=0
    while(!bool(d.oe)&&waited<limit){step();waited+=1}
    assert(bool(d.oe),s"USB response timeout after $limit samples")
    step(2)
    val line=ArrayBuffer.empty[Boolean]
    var samples=0
    while((bool(d.dp)||bool(d.dn))&&samples<1200){
      assert(bool(d.dp)!=bool(d.dn),"USB illegal SE1")
      line+=bool(d.dp);step(4);samples+=1
    }
    assert(samples<1200,"USB packet never ended")
    while(bool(d.oe)){step()}
    val raw=ArrayBuffer.empty[Boolean];var prev=true
    line.foreach{j=>raw+=(j==prev);prev=j}
    assert(raw.take(8)==Seq(false,false,false,false,false,false,false,true),s"USB sync mismatch ${raw.take(8)}")
    val bits=ArrayBuffer.empty[Boolean];var ones=0;var stuffed=false
    raw.drop(8).foreach{b=>
      if(stuffed){assert(!b,"USB stuffing error");stuffed=false;ones=0}
      else {bits+=b;if(b){ones+=1;if(ones==6)stuffed=true}else ones=0}
    }
    assert(bits.size%8==0,s"USB partial byte ${bits.size}")
    val bytes=bits.grouped(8).map(bs=>bs.zipWithIndex.map{case(b,i)=>if(b)1<<i else 0}.sum).toSeq
    assert(bytes.nonEmpty,"USB empty packet")
    val pid=bytes.head&15
    assert((bytes.head>>4)==(~pid&15),"USB PID complement")
    if(pid==DATA0||pid==DATA1){
      val body=bytes.tail.dropRight(2);assert(bytes.takeRight(2)==crc16(body),s"USB CRC mismatch $bytes")
      (pid,body)
    }else{assert(bytes.size==1,s"USB handshake payload $bytes");(pid,Seq.empty)}
  }
  def setupBytes(kind: Int,request: Int,value: Int,index: Int,length: Int): Seq[Int]=
    Seq(kind,request,value&255,value>>8,index&255,index>>8,length&255,length>>8)
  def setup(address: Int,bytes: Seq[Int]): Unit={
    token(SETUP,address,0);idle(2);data(DATA0,bytes)
    assert(receive()._1==ACK,"SETUP must ACK");idle(4)
  }
  def statusWrite(address: Int,ack: Boolean=true): Unit={
    token(IN,address,0);val result=receive();assert(result==(DATA1,Seq.empty),s"status $result")
    if(ack){idle(2);packet(ACK);idle(12)}
  }
  def write(address: Int,request: Int,value: Int): Unit={
    setup(address,setupBytes(0,request,value,0,0));statusWrite(address)
  }
  def enqueue(bytes: Seq[Int]): Unit={
    for(byte<-bytes){
      d.txData.poke(byte.U);d.txValid.poke(true.B)
      var wait=0;while(!bool(d.txReady)&&wait<1000){step();wait+=1}
      assert(bool(d.txReady),"application TX backpressure deadline")
      step();d.txValid.poke(false.B)
    }
    idle(40)
  }
  def drain(count: Int): Seq[Int]={
    val bytes=ArrayBuffer.empty[Int];d.rxReady.poke(true.B);var wait=0
    while(bytes.size<count&&wait<4000){if(bool(d.rxValid))bytes+=d.rxData.peek().litValue.toInt;step();wait+=1}
    d.rxReady.poke(false.B)
    assert(bytes.size==count,s"application RX timeout: ${bytes.size}/$count")
    bytes.toSeq
  }
  def silence(samples: Int): Unit={
    for(_<-0 until samples){assert(!bool(d.oe),"unexpected USB response");step()}
  }
  def read(address: Int,request: Int,value: Int,length: Int,retryFirst: Boolean=false,kind: Int=0x80,index: Int=0): Seq[Int]={
    setup(address,setupBytes(kind,request,value,index,length))
    val bytes=ArrayBuffer.empty[Int];var toggle=DATA1;var done=false
    while(!done&&bytes.size<length){
      token(IN,address,0);val response=receive();assert(response._1==toggle,s"EP0 PID $response expected $toggle")
      if(retryFirst&&bytes.isEmpty){idle(4);token(IN,address,0);assert(receive()==response,"EP0 lost-ACK replay changed")}
      bytes++=response._2;idle(2);packet(ACK);idle(4)
      done=response._2.size<8;toggle=if(toggle==DATA1)DATA0 else DATA1
    }
    token(OUT,address,0);idle(2);data(DATA1,Seq.empty)
    assert(receive()._1==ACK,"EP0 OUT status must ACK");idle(4)
    bytes.toSeq
  }
}
