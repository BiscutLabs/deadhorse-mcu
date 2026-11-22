package deadhorse.qspi_xip
import chisel3._
import scala.collection.mutable.ArrayBuffer

/** Independent byte-addressed flash peer. Only public pins are observed.
  * Call observe immediately before each main sample edge. */
class FlashPeer(cs: UInt,sclk: Bool,out: UInt,en: UInt,in: UInt,reset_n: Bool,
                memory: Long=>Int, formats: Map[Int,(Int,Boolean,Boolean,Int)]=Map(3->(3,false,false,0),19->(4,false,false,0))) extends chisel3.simulator.PeekPokeAPI {
  val frames=ArrayBuffer.empty[(Int,Int,Long)]
  private var previousCs=3;private var previousClock=false
  private var selected=0;private var phase=0;private var count=0;private var opcode=0;private var address=0L
  private var addressBytes=0;private var qa=false;private var qd=false;private var dummy=0;private var dataSymbol=0
  private def high(v: Bool)=v.peek().litToBoolean
  def observe(): Unit={
    val nowCs=cs.peek().litValue.toInt;val clock=high(sclk)
    if(previousCs==3 && nowCs!=3) {
      assert(nowCs==1 || nowCs==2,"FLASH_CS");selected=if(nowCs==2)0 else 1
      phase=0;count=0;opcode=0;address=0;dataSymbol=0
    }
    if(nowCs!=3 && !previousClock && clock) {
      val pins=out.peek().litValue.toInt;val enabled=en.peek().litValue.toInt
      phase match {
        case 0=>
          assert(enabled==13,"FLASH_OPCODE_DIRECTION");opcode=(opcode<<1)|(pins&1);count+=1
          if(count==8) {
            count=0
            if(selected==1 && opcode==6) phase=4
            else {val f=formats.getOrElse(opcode,throw new AssertionError(s"FLASH_OPCODE $opcode"))
              addressBytes=f._1;qa=f._2;qd=f._3;dummy=f._4;phase=1}
          }
        case 1=>
          assert(enabled==(if(qa)15 else 13),"FLASH_ADDRESS_DIRECTION")
          val width=if(qa)4 else 1;address=(address<<width)|(pins&((1<<width)-1));count+=width
          if(count==addressBytes*8) {count=0;phase=if(dummy==0)3 else 2}
        case 2=>
          assert(enabled==0,"FLASH_DUMMY_DIRECTION");count+=1;if(count==dummy) {count=0;phase=3}
        case 3=>
          assert(enabled==(if(qd)0 else 12),"FLASH_READ_DIRECTION")
          dataSymbol+=1;if(dataSymbol==(if(qd)8 else 32)) phase=4
        case _=>throw new AssertionError("FLASH_EXTRA_CLOCK")
      }
    }
    if(nowCs!=3 && previousClock && !clock && phase==3) {
      val perByte=if(qd)2 else 8;val b=memory(address+dataSymbol/perByte)&255
      val shift=if(qd)4*(1-dataSymbol%2) else 7-dataSymbol%8
      val v=(b>>>shift)&(if(qd)15 else 1)
      in.poke((if(qd)v else v<<1).U)
    }
    if(previousCs!=3 && nowCs==3) {
      if(high(reset_n)) {assert(phase==4,"FLASH_TRUNCATED");frames+=((selected,opcode,address))}
      in.poke(0.U)
    }
    previousCs=nowCs;previousClock=clock
  }
}
