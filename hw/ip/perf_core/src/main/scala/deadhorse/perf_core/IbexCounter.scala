// Copyright lowRISC contributors.
// Licensed under the Apache License, Version 2.0; SPDX-License-Identifier: Apache-2.0
// Translation of rtl/ibex_counter.sv, Ibex 38c070939183cc10940b66c8e9e04eeca6b65470.
package deadhorse.perf_core

import chisel3._
import chisel3.util.{Cat, addAttribute}

class IbexCounter(val CounterWidth: Int = 32, val ProvideValUpd: Boolean = false)
    extends RawModule {
  require(CounterWidth > 0 && CounterWidth <= 64)
  override def desiredName = "ibex_counter"
  val clk_i = IO(Input(Clock()))
  val rst_ni = IO(Input(Bool()))
  val counter_inc_i = IO(Input(Bool()))
  val counterh_we_i = IO(Input(Bool()))
  val counter_we_i = IO(Input(Bool()))
  val counter_val_i = IO(Input(UInt(32.W)))
  val counter_val_o = IO(Output(UInt(64.W)))
  val counter_val_upd_o = IO(Output(UInt(64.W)))

  withClockAndReset(clk_i, (!rst_ni).asAsyncReset) {
    val counter_q = RegInit(0.U(CounterWidth.W))
    val counter = counter_q.pad(64)
    // T11 approved same-state repair: parallel local increments with carry
    // selection implement exactly (counter_q + 1) modulo width.
    val counter_upd = if (!ProvideValUpd) {
      val slices = (0 until CounterWidth by 8).map { low =>
        val high = math.min(low + 7, CounterWidth - 1)
        val slice = counter_q(high, low)
        val carry = if (low == 0) true.B else counter_q(low - 1, 0).andR
        Mux(carry, slice + 1.U((high - low + 1).W), slice)
      }
      Cat(slices.reverse)
    } else {
      val groupPropagates = (0 until CounterWidth by 4).map { low =>
        val propagate = WireDefault(counter_q(math.min(low + 3, CounterWidth - 1), low).andR)
        addAttribute(propagate, "keep = 1")
        propagate
      }
      val prefix = Iterator.iterate(1)(_ * 2).takeWhile(_ < groupPropagates.size)
        .foldLeft(groupPropagates) { (previous, distance) =>
          previous.indices.map { index =>
            if (index < distance) previous(index) else {
              val propagate = WireDefault(previous(index) && previous(index - distance))
              addAttribute(propagate, "keep = 1")
              propagate
            }
          }
        }
      val slices = (0 until CounterWidth by 4).map { low =>
        val high = math.min(low + 3, CounterWidth - 1)
        val slice = counter_q(high, low)
        val carry = if (low == 0) true.B else prefix(low / 4 - 1)
        val incremented = WireDefault(slice + 1.U((high - low + 1).W))
        addAttribute(incremented, "keep = 1")
        Mux(carry, incremented, slice)
      }
      Cat(slices.reverse)
    }
    val counter_load = Mux(counterh_we_i,
      Cat(counter_val_i, counter(31, 0)), Cat(counter(63, 32), counter_val_i))
    val counter_d = Mux(counter_we_i || counterh_we_i, counter_load(CounterWidth - 1, 0),
      Mux(counter_inc_i, counter_upd, counter_q))
    counter_q := counter_d
    counter_val_o := counter
    counter_val_upd_o := (if (ProvideValUpd) counter_upd.pad(64) else 0.U(64.W))
  }
}
