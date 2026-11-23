package deadhorse.debug

import chisel3._
import chisel3.util._

/** Input-only observers. ownership.py binds these to production graph identities.
  * They do not drive the DUT or impose environment assumptions. */
class DebugEntryObserver(coverOnly: Boolean) extends RawModule {
  val clock=IO(Input(Clock())); val reset_n=IO(Input(Bool())); val epoch=IO(Input(Bool()))
  val normalBoot=IO(Input(Bool())); val mode=IO(Input(Bool())); val entered=IO(Input(Bool()))
  val owned=IO(Input(Bool())); val debugFetch=IO(Input(Bool())); val fetch=IO(Input(UInt(4.W)))
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val observed=withReset((!epoch).asAsyncReset) { RegInit(false.B) }
    when(mode) { observed:=true.B }
    if(coverOnly) {
      cover(epoch && !normalBoot && mode)
      cover(epoch && !normalBoot && observed && fetch===5.U)
    } else {
      assert(!entered || observed,"DBG_ENTRY_OBSERVED")
      assert(!debugFetch || owned && observed,"DBG_ENTRY_OWNED")
      assert(normalBoot || observed || mode || fetch=/=5.U,"DBG_PREBOOT_FETCH_ADMISSION")
    }
  }
}

class DebugLoaderObserver(coverOnly: Boolean) extends RawModule {
  val clock=IO(Input(Clock())); val reset_n=IO(Input(Bool()))
  val owned=IO(Input(Bool())); val loaderWrite=IO(Input(Bool())); val retainedHalted=IO(Input(Bool()))
  val inhibit=IO(Input(Bool())); val frameValid=IO(Input(Bool())); val opcode=IO(Input(UInt(8.W)))
  val phase=IO(Input(UInt(2.W))); val start=IO(Input(Bool()))
  val metadata=IO(Input(UInt(102.W)))
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val forbidden=frameValid && inhibit && opcode>=1.U && opcode<=6.U
    val priorForbidden=RegNext(forbidden,false.B)
    val idleForbidden=RegNext(forbidden && phase===0.U,false.B)
    val previous=RegNext(metadata)
    if(coverOnly) {
      cover(forbidden && opcode===1.U)
      cover(forbidden && opcode===2.U)
      cover(forbidden && opcode===5.U)
      cover(owned && !retainedHalted)
    } else {
      assert(!owned || !retainedHalted,"DBG_LOADER_PERMISSION")
      assert(!owned || !loaderWrite,"DBG_LOADER_WRITE_EXCLUSION")
      assert(!priorForbidden || !start,"DBG_LOADER_START_INHIBITED")
      assert(!idleForbidden || phase===0.U,"DBG_LOADER_WORK_INHIBITED")
      assert(!idleForbidden || metadata===previous,"DBG_LOADER_METADATA_INHIBITED")
    }
  }
}

class DebugLiteEntryObserver(coverOnly: Boolean) extends RawModule {
  val clock=IO(Input(Clock())); val reset_n=IO(Input(Bool()))
  val start=IO(Input(Bool())); val notStarted=IO(Input(Bool())); val mode=IO(Input(Bool()))
  val retired=IO(Input(Bool()))
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val sawStart=RegInit(false.B); val sawDebug=RegInit(false.B)
    when(start) { sawStart:=true.B }; when(mode) { sawDebug:=true.B }
    val held=RegNext(notStarted && !start,false.B)
    if(coverOnly) {
      cover(mode && notStarted)
      cover(!notStarted && sawStart)
    } else {
      assert(!held || notStarted,"DBG_LITE_DEBUG_NOT_START")
      assert(sawStart || sawDebug || mode || !retired,"DBG_LITE_PREENTRY_RETIREMENT")
    }
  }
}

/** Sample the actual core clock, including arbitrary stopped-clock intervals.
  * No application work is allowed before the first normal boot or debug entry
  * in this core-reset epoch. Normal boot may subsequently revoke its permit. */
class DebugPerfFirstEntryObserver(coverOnly: Boolean) extends RawModule {
  val clock=IO(Input(Clock())); val reset_n=IO(Input(Bool()))
  val normalBoot=IO(Input(Bool())); val mode=IO(Input(Bool()))
  val request=IO(Input(Bool())); val retired=IO(Input(Bool()))
  withClockAndReset(clock,(!reset_n).asAsyncReset) {
    val sawBoot=RegInit(false.B); val sawDebug=RegInit(false.B)
    when(normalBoot) { sawBoot:=true.B }; when(mode) { sawDebug:=true.B }
    val admitted=normalBoot || sawBoot || mode || sawDebug
    if(coverOnly) {
      cover(!sawBoot && mode)
      cover(sawDebug && request)
    } else {
      assert(admitted || !request,"DBG_PERF_PREENTRY_FETCH")
      assert(admitted || !retired,"DBG_PERF_PREENTRY_RETIREMENT")
    }
  }
}

object EmitDebugOwnership extends App {
  for(c<-Seq(false,true)) {
    val suffix=if(c) "cover" else "correct"
    for((name,make)<-Seq[(String,()=>RawModule)](
      "entry"->(()=>new DebugEntryObserver(c)),
      "loader"->(()=>new DebugLoaderObserver(c)),
      "lite"->(()=>new DebugLiteEntryObserver(c)),
      "perf"->(()=>new DebugPerfFirstEntryObserver(c)))) {
      _root_.circt.stage.ChiselStage.emitSystemVerilogFile(chisel3.layer.elideBlocks(make()),
        Array("--target-dir",s"${args(0)}/$name/$suffix"),
        Array("--disable-all-randomization","--disable-opt","--strip-debug-info","--verification-flavor=immediate","--lower-to-core"))
    }
  }
}
