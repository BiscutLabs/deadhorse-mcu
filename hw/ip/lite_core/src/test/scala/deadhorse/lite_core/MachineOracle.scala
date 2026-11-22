package deadhorse.lite_core

/** Small instruction-level oracle for the machine-control programs.
  * RV32E ALU/load/store families have the separate upstream independent oracle.
  */
class MachineOracle(val memory: Map[Long,Long],entry: Long) {
  private val mask=0xffffffffL;private val mask64=(BigInt(1)<<64)-1
  val regs=Array.fill[Long](16)(0);var pc=entry;var cycle=BigInt(0);var retired=BigInt(0)
  var enabled=false;var previousEnable=false;var externalEnable=false;var inhibit=0
  var vector=0L;var exceptionPc=0L;var cause=0L;var scratch=0L
  var firstInterrupt=false;var order=BigInt(0)
  case class Expected(insn: Long,rd: Int,data: Long,trap: Boolean,cause: Int,next: Long,intr: Boolean)
  def read(address: Int,irq: Boolean): Option[Long]=address match {
    case 0x300=>Some(0x1800L+(if(enabled)8 else 0)+(if(previousEnable)128 else 0))
    case 0x301=>Some(0x40000010L)
    case 0x304=>Some(if(externalEnable)2048L else 0L)
    case 0x305=>Some(vector)
    case 0x306|0x310|0x343=>Some(0L)
    case 0x320=>Some(inhibit.toLong)
    case 0x340=>Some(scratch)
    case 0x341=>Some(exceptionPc)
    case 0x342=>Some(cause)
    case 0x344=>Some(if(irq)2048L else 0L)
    case 0xb00=>Some((cycle & mask).toLong)
    case 0xb80=>Some((cycle>>32).toLong)
    case 0xb02=>Some((retired & mask).toLong)
    case 0xb82=>Some((retired>>32).toLong)
    case n if n>=0xf11 && n<=0xf14=>Some(0L)
    case _=>None
  }
  private def write(address: Int,value: Long): Unit=address match {
    case 0x300=>enabled=(value&8)!=0;previousEnable=(value&128)!=0
    case 0x304=>externalEnable=(value&2048)!=0
    case 0x305=>vector=value & ~3L
    case 0x320=>inhibit=(value&5).toInt
    case 0x340=>scratch=value
    case 0x341=>exceptionPc=value & ~3L
    case 0x342=>cause=value
    case 0xb00=>cycle=(cycle>>32<<32)+value
    case 0xb80=>cycle=(cycle&mask)+(BigInt(value)<<32)
    case 0xb02=>retired=(retired>>32<<32)+value
    case 0xb82=>retired=(retired&mask)+(BigInt(value)<<32)
    case _=>()
  }
  private def trap(at: Long,why: Long): Unit={
    exceptionPc=at & ~3L;cause=why;previousEnable=enabled;enabled=false;pc=vector
  }
  /** Return expected retirement from the pre-edge architecture; counters then advance. */
  def edge(hasRetirement: Boolean,interrupt: Boolean,irq: Boolean): Option[Expected]={
    val oldInhibit=inhibit;var counterWrite: Option[(Int,Long)]=None
    val expected=if(!hasRetirement) None else {
      val word=memory.getOrElse(pc,0L);val oldPc=pc;var next=(pc+4)&mask
      var dest=0;var value=0L;var fault=0;var trapped=false
      val op=(word&127).toInt;val rd=((word>>7)&31).toInt;val f=((word>>12)&7).toInt
      val rs=((word>>15)&31).toInt;val addr=((word>>20)&4095).toInt
      def illegal(): Unit={trapped=true;fault=2}
      if(op==0x37 && rd<16) {dest=rd;value=word & 0xfffff000L}
      else if(op==0x13 && f==0 && rd<16 && rs<16) {
        val immediate=(word.toInt>>20).toLong;dest=rd;value=(regs(rs)+immediate)&mask
      } else if(op==0x73 && Set(1,2,3,5,6,7)(f)) {
        val isImmediate=f>=5;val writes=(f%4==1)||rs!=0
        if(rd>=16 || (!isImmediate && rs>=16) || read(addr,irq).isEmpty || writes && addr>=0xc00) illegal()
        else {
          val old=read(addr,irq).get;val operand=if(isImmediate)rs.toLong else regs(rs)
          val updated=(f%4) match {case 1=>operand;case 2=>old|operand;case 3=>old & ~operand}
          dest=rd;value=old
          if(writes) {
            if(Set(0xb00,0xb80,0xb02,0xb82)(addr)) counterWrite=Some(addr->(updated&mask))
            else write(addr,updated&mask)
          }
        }
      } else if(word==0x30200073L) {next=exceptionPc;enabled=previousEnable;previousEnable=true}
      else if(word==0x10500073L) ()
      else if(word==0x73L || word==0x100073L) {trapped=true;fault=if(word==0x73L)11 else 3}
      else illegal()
      val intr=firstInterrupt;firstInterrupt=false
      if(trapped) {trap(oldPc,fault);dest=0;value=0;next=pc}
      else {pc=next;if(dest!=0) regs(dest)=value;if((oldInhibit&4)==0) retired=(retired+1)&mask64}
      order+=1;Some(Expected(word,if(dest==0)0 else dest,if(dest==0)0 else value,trapped,fault,next,intr))
    }
    if(interrupt) {
      require(!hasRetirement && irq && externalEnable && enabled,"ORACLE_INTERRUPT_BOUNDARY")
      trap(pc,0x8000000bL);firstInterrupt=true
    }
    if((oldInhibit&1)==0) cycle=(cycle+1)&mask64
    // Counter writes use the pre-increment value of the untouched half.
    counterWrite.foreach {case(a,v)=>
      if((a==0xb00 || a==0xb80) && (oldInhibit&1)==0) cycle=(cycle-1)&mask64
      if((a==0xb02 || a==0xb82) && (oldInhibit&4)==0) retired=(retired-1)&mask64
      write(a,v)
    }
    expected
  }
}
