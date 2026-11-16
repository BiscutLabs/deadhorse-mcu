// Copyright lowRISC contributors.
// Copyright 2018 ETH Zurich and University of Bologna, see also upstream CREDITS.md.
// Licensed under the Apache License, Version 2.0; SPDX-License-Identifier: Apache-2.0
// Translation of rtl/ibex_compressed_decoder.sv,
// Ibex 38c070939183cc10940b66c8e9e04eeca6b65470.
package deadhorse.perf_core

import chisel3._
import chisel3.util.{Cat, Fill, switch, is}

class IbexCompressedDecoder extends RawModule {
  override def desiredName = "ibex_compressed_decoder"
  // The reference uses these three pins only for simulation assertions.
  val clk_i = IO(Input(Clock()))
  val rst_ni = IO(Input(Bool()))
  val valid_i = IO(Input(Bool()))
  val instr_i = IO(Input(UInt(32.W)))
  val instr_o = IO(Output(UInt(32.W)))
  val is_compressed_o = IO(Output(Bool()))
  val illegal_instr_o = IO(Output(Bool()))
  private def u(value: Int, width: Int) = value.U(width.W)
  private val i = instr_i
  private val opImm = u(0x13, 7)
  private val op = u(0x33, 7)
  private val load = u(0x03, 7)
  private val store = u(0x23, 7)
  private val jal = u(0x6f, 7)
  private val jalr = u(0x67, 7)
  private val branch = u(0x63, 7)
  private val lui = u(0x37, 7)
  instr_o := i
  illegal_instr_o := false.B
  is_compressed_o := i(1, 0) =/= 3.U
  switch(i(1, 0)) {
    is(0.U) {
      illegal_instr_o := !(i(15, 13) === 0.U || i(15, 13) === 2.U || i(15, 13) === 6.U)
      switch(i(15, 13)) {
        is(0.U) {
          instr_o := Cat(u(0, 2), i(10, 7), i(12, 11), i(5), i(6), u(0, 2),
            u(2, 5), u(0, 3), u(1, 2), i(4, 2), opImm)
          illegal_instr_o := i(12, 5) === 0.U
        }
        is(2.U) {
          instr_o := Cat(u(0, 5), i(5), i(12, 10), i(6), u(0, 2),
            u(1, 2), i(9, 7), u(2, 3), u(1, 2), i(4, 2), load)
        }
        is(6.U) {
          instr_o := Cat(u(0, 5), i(5), i(12), u(1, 2), i(4, 2), u(1, 2),
            i(9, 7), u(2, 3), i(11, 10), i(6), u(0, 2), store)
        }
      }
    }
    is(1.U) {
      switch(i(15, 13)) {
        is(0.U) {
          instr_o := Cat(Fill(6, i(12)), i(12), i(6, 2), i(11, 7), u(0, 3), i(11, 7), opImm)
        }
        is(1.U, 5.U) {
          instr_o := Cat(i(12), i(8), i(10, 9), i(6), i(7), i(2), i(11), i(5, 3),
            Fill(9, i(12)), u(0, 4), !i(15), jal)
        }
        is(2.U) {
          instr_o := Cat(Fill(6, i(12)), i(12), i(6, 2), u(0, 5), u(0, 3), i(11, 7), opImm)
        }
        is(3.U) {
          instr_o := Cat(Fill(15, i(12)), i(6, 2), i(11, 7), lui)
          when(i(11, 7) === 2.U) {
            instr_o := Cat(Fill(3, i(12)), i(4, 3), i(5), i(2), i(6), u(0, 4),
              u(2, 5), u(0, 3), u(2, 5), opImm)
          }
          illegal_instr_o := Cat(i(12), i(6, 2)) === 0.U
        }
        is(4.U) {
          switch(i(11, 10)) {
            is(0.U, 1.U) {
              instr_o := Cat(false.B, i(10), u(0, 5), i(6, 2), u(1, 2), i(9, 7),
                u(5, 3), u(1, 2), i(9, 7), opImm)
              illegal_instr_o := i(12)
            }
            is(2.U) {
              instr_o := Cat(Fill(6, i(12)), i(12), i(6, 2), u(1, 2), i(9, 7),
                u(7, 3), u(1, 2), i(9, 7), opImm)
            }
            is(3.U) {
              illegal_instr_o := i(12)
              switch(Cat(i(12), i(6, 5))) {
                is(0.U) {
                  instr_o := Cat(u(1, 2), u(0, 5), u(1, 2), i(4, 2), u(1, 2),
                    i(9, 7), u(0, 3), u(1, 2), i(9, 7), op)
                }
                is(1.U) {
                  instr_o := Cat(u(0, 7), u(1, 2), i(4, 2), u(1, 2), i(9, 7),
                    u(4, 3), u(1, 2), i(9, 7), op)
                }
                is(2.U) {
                  instr_o := Cat(u(0, 7), u(1, 2), i(4, 2), u(1, 2), i(9, 7),
                    u(6, 3), u(1, 2), i(9, 7), op)
                }
                is(3.U) {
                  instr_o := Cat(u(0, 7), u(1, 2), i(4, 2), u(1, 2), i(9, 7),
                    u(7, 3), u(1, 2), i(9, 7), op)
                }
              }
            }
          }
        }
        is(6.U, 7.U) {
          instr_o := Cat(Fill(4, i(12)), i(6, 5), i(2), u(0, 5), u(1, 2), i(9, 7),
            u(0, 2), i(13), i(11, 10), i(4, 3), i(12), branch)
        }
      }
    }
    is(2.U) {
      illegal_instr_o := i(13) // All odd funct3 encodings are unsupported.
      switch(i(15, 13)) {
        is(0.U) {
          instr_o := Cat(u(0, 7), i(6, 2), i(11, 7), u(1, 3), i(11, 7), opImm)
          illegal_instr_o := i(12)
        }
        is(2.U) {
          instr_o := Cat(u(0, 4), i(3, 2), i(12), i(6, 4), u(0, 2), u(2, 5),
            u(2, 3), i(11, 7), load)
          illegal_instr_o := i(11, 7) === 0.U
        }
        is(4.U) {
          when(!i(12)) {
            when(i(6, 2) =/= 0.U) {
              instr_o := Cat(u(0, 7), i(6, 2), u(0, 5), u(0, 3), i(11, 7), op)
            }.otherwise {
              instr_o := Cat(u(0, 12), i(11, 7), u(0, 3), u(0, 5), jalr)
              illegal_instr_o := i(11, 7) === 0.U
            }
          }.otherwise {
            when(i(6, 2) =/= 0.U) {
              instr_o := Cat(u(0, 7), i(6, 2), i(11, 7), u(0, 3), i(11, 7), op)
            }.otherwise {
              when(i(11, 7) === 0.U) { instr_o := "h00100073".U }.otherwise {
                instr_o := Cat(u(0, 12), i(11, 7), u(0, 3), u(1, 5), jalr)
              }
            }
          }
        }
        is(6.U) {
          instr_o := Cat(u(0, 4), i(8, 7), i(12), i(6, 2), u(2, 5), u(2, 3),
            i(11, 9), u(0, 2), store)
        }
      }
    }
  }
}
