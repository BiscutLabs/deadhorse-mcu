# Clocked lite core (T25)

Status: baseline, machine-mode RTL and opt-in AON integration implemented;
full T25 qualification remains open. See the task report and formal ledger
for exact evidence, including unresolved checks. Neither CI tier runs.
The source is RISCay-MCU commit
`4671317186003740ceb61360ba08c59bbdf10136`, Apache-2.0, adopted once with a
file/blob manifest. Only ClockedCore and the shared combinational ISA schema
are production inputs. No upstream or asynchronous build dependency.

## Staged contract

First retain the pinned RV32E, IALIGN32 semantics, including terminal fault
notification, in a faithful baseline. The approved production extension adds
minimal machine-mode traps, one level interrupt and WFI; its exact CSR and
trap behavior was independently reviewed before implementation. Baseline
equivalence does not qualify the extension.

The core and bus adapter use the AON service clock. Reset assertion is
asynchronous, release comes from the shared reset-release block. Ordinary
AON service reset cancels both core and fabric epoch; a core-only reset is
not exposed. Main-core/service reset must preserve AON execution. No internal
clock divider, gate or new crossing is introduced. Clock-demand outputs do
not by themselves establish a complete sleep controller.

The registered adapter accepts the adopted Decoupled memory protocol and
offers one stable LocalBus request until grant, then captures one response
before returning it to the core. Address is word-aligned at the LocalBus
boundary; store data/byte masks remain lane-aligned. Bus origin is the fixed
lite origin, never supplied by software. Halt operation is consumed locally
without issuing a bus request or fabric response. No address translation or
alias is added. Its two independently registered boundaries break combinational
ready paths. One outstanding transfer is sufficient for this single-issue core.

The opt-in recovery-driven profile waits for the existing loader START and
aligned entry offset, then start at retained-SRAM base plus that offset.
Existing programming-lock, program/data permissions and physical memory size
remain unchanged. There is no new trusted loader bypass. This profile does
not implement production boot ROM, QSPI, JTAG, lite-first performance release
or power/reset policy. Existing stand-in profiles remain available.

Estimated baseline register-file state: 15 × 32 = 480 bits, excluding control,
retirement trace, adapter and CSR state. Measured mapped timing/area and the
reviewed conservative timing basis are recorded in the T25 report. The main
clock trial does not define the lite core's frequency.

## Production extension contract

Machine-only RV32E with Zicsr, IALIGN32, no C/M/F, lower privilege, MMU or PMP.
Use standard CSR instruction encodings, ECALL/EBREAK, MRET and WFI. No custom
instruction or application policy. Machine trap/interrupt/WFI semantics follow
the [RISC-V machine specification](https://docs.riscv.org/reference/isa/priv/machine.html).

| CSR | Implemented behavior |
| --- | --- |
| mstatus 0x300 | MIE/MPIE writable; MPP fixed M; other fields zero |
| misa 0x301 | Fixed RV32E, writes ignored |
| mie 0x304 | MEIE bit11 only |
| mtvec 0x305 | Direct mode only; aligned base writable |
| mcounteren 0x306, mstatush 0x310 | Read zero, writes ignored |
| mcountinhibit 0x320 | CY bit0 and IR bit2 |
| mscratch 0x340 | Full-width scratch |
| mepc 0x341 | Aligned writable PC |
| mcause 0x342 | Full-width writable cause; trap entry writes standard cause |
| mtval 0x343 | Read zero, writes ignored; optional diagnostic information omitted |
| mip 0x344 | MEIP reflects synchronous level input, writes ignored |
| mcycle/minstret 0xb00/0xb02, high halves 0xb80/0xb82 | Writable 64-bit counters; inhibit controls; CSR write wins increment |
| mvendorid/marchid/mimpid/mhartid 0xf11..0xf14 | Read-only zero, hart0 |

All unspecified CSRs and writes to read-only CSRs trap illegal instruction.
CSRRS/CSRRC suppress writes only for encoded rs1=x0 (or zimm=0 for immediate
variants), not for a nonzero register containing zero. Immediate variants use
the full five-bit immediate, while register operands must be x0..x15. MRET restores
MIE from MPIE and sets MPIE. Exceptions save the faulting PC; external interrupt
cause is 0x8000000b and saves the next instruction PC. Synchronous instruction
or memory fault completes before an interrupt is considered. Interrupts are
taken only between whole instructions, never after a bus offer or halfway
through a load/store. No offered request is withdrawn on IRQ.
Trap entry copies MIE to MPIE and clears MIE. mcycle counts clock edges unless
inhibited, including while WFI is waiting on an externally running clock.
minstret counts successful retirement only, excluding faulting instructions,
ECALL/EBREAK and interrupt entry. A counter CSR write overrides the entire
64-bit increment on that edge while retaining the unaddressed half.

WFI retires and advances PC before sleeping. A locally enabled interrupt wakes
it even when global MIE is zero; trap entry additionally requires global MIE.
Core halted means not started, not WFI. No bus request may remain outstanding
when sleeping. Actual clock gating/wake capture remains in the later controller.

Reset clears core/CSR/adapter control and register file; mtvec/PC reset zero
but no fetch is issued before START. START is accepted once while not running,
only with programmed image, quiescent loader, aligned entry offset below the
existing 2KiB program limit. It sets PC to 0x30000000 plus the offset. Further
START pulses while running are ignored. The loader already validates the
entry against actual image length; this binding rechecks aperture/alignment.
Core reset and adapter/fabric cancellation share AON service reset. Main reset
does not stop the core. The externally supplied clock remains running in this
profile; no production lite-first boot sequence is inferred.

Retain the existing main-9MHz GF180 logic screen used for T21 AON blocks as a
conservative implementation check, with its unchanged 66.666667ns estimated
budget. The profile's assumed fastest AON input is 1MHz; `0.60 * 1000 = 600ns`
is only its derived budget, not permission to relax the conservative screen.
Neither figure qualifies a later faster lite clock, physical timing or I3.

RVFI uses the pinned riscv-formal `RISCV_FORMAL_ALIGNED_MEM` convention:
word-aligned memory address with physical byte-lane masks/data. Architectural
source operands and trace order are retained across the separate data transfer.
RVFI emission alone does not establish instruction or interrupt qualification.

`SocLiteFiles` / `EmitSocLite` extends the pin-mux profile with the actual
hart. Its old external lite-master input is inert and cannot override halted
status or ownership. The registered loader START handoff suppresses the old
halted status for that one edge so loader mode stays RUN, including WFI;
retained-memory permissions always use actual core halted status. Common AON
service reset cancels core, adapter and fabric together. Main reset preserves
execution. No independent core reset is exposed.

Focused commands in the pinned environment:

```sh
python3 dv/soc/prepare_lite.py
python3 hw/ip/lite_core/check_provenance.py
python3 dv/soc/check_lite.py --output build/t25/fresh-check
python3 hw/ip/lite_core/formal/state_equivalence.py --output build/t25/fresh-baseline
python3 hw/ip/lite_core/formal/check.py --cases adapter control --output build/t25/fresh-control
python3 hw/ip/lite_core/check_timing.py --top LiteHart --output build/t25/fresh-timing
```

The earlier output-only baseline PDR timeout is retained as diagnostic evidence;
do not rerun it unchanged. The exact named-state baseline proof covers resets,
every next-state function and outputs. It does not prove the machine extension.
