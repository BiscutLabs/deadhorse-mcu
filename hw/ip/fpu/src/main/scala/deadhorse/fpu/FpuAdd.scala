package deadhorse.fpu

import chisel3._
import chisel3.util._

/** Two-bit local sums with balanced group carry, bounded at the chosen width. */
object FpuAdd {
  def apply(a: UInt, b: UInt, width: Int, cin: Bool = false.B): UInt = {
    def keep(x: UInt): UInt = {
      val w = WireDefault(x); addAttribute(w, "keep = 1"); w
    }
    val padded = ((width + 1) / 2) * 2
    val x = a.pad(padded)(padded - 1, 0); val y = b.pad(padded)(padded - 1, 0)
    val groups = (0 until padded by 2).map { i =>
      val ax = x(i + 1, i); val by = y(i + 1, i)
      (keep(ax +& by), keep((ax ^ by).andR.asUInt).asBool)
    }
    def prefix(gs: Seq[(UInt, Bool)]): (Bool, Bool) = {
      if(gs.size == 1) (gs.head._1(2), gs.head._2)
      else {
        val (gl,pl) = prefix(gs.take(gs.size / 2))
        val (gh,ph) = prefix(gs.drop(gs.size / 2))
        (keep((gh || (ph && gl)).asUInt).asBool, keep((ph && pl).asUInt).asBool)
      }
    }
    val sums = groups.indices.map { i =>
      val carry = if(i == 0) cin else {
        val (g,p) = prefix(groups.take(i)); g || (p && cin)
      }
      Mux(carry, keep(groups(i)._1(1,0) + 1.U(2.W)), groups(i)._1(1,0))
    }
    Cat(sums.reverse)(width - 1, 0)
  }
}
