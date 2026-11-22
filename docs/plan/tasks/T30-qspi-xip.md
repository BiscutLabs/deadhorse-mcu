# T30 Native QSPI read path

## Goal and read first

Continue assigned RTL on main, no CI. Implement the planned memory-mapped
flash read path as an opt-in T29 extension, preserving older profiles.
Read AGENTS, plan README/STATUS/task index/skills15, plans03/04/06/07/11–14/16,
bus/SoC contracts, T20/T28/T29 reports, local memory and shared reset/register
primitives, QSPI README/engine/tests. Skills: task execution, clocked Chisel,
regmap, reference testing, formal properties, timeout triage and GF180 timing.

## Deliverables

1. Independently reviewed XIP/register/reset contract before RTL. Reuse the
   T29 engine and shared primitives; no new flash PHY or vendor edits.
2. One native read slot and one captured command slot, bounded round-robin
   frame arbitration, little-endian memory results, explicit access errors,
   idle-only keyed configuration. Separate XIP permission from MMIO owner.
3. Local instruction/data routing with ordered replies, SRAM/ROM fast-path
   behavior preserved, DMA confined to SRAM, client-reset orphan draining
   before epochReady. No peripheral-watchdog or existing limit changes.
4. Opt-in full-SoC binding, independent flash model and actual core execution;
   tests for range/permission, competing commands, mixed local traffic, all
   reset phases and faults. Control/response formal properties/covers/faults
   under existing120s caps; classify bounded results honestly.
5. Fresh mapped9MHz screen, four8/9MHz × stub/real-USB tops, frozen focused
   checks, independent review and report. Neither CI tier runs.

## May change and stop conditions

hw/ip/qspi narrow optional integration, hw/ip/qspi_xip, narrow local-memory/
SoC/map/test bindings, dv/soc preparation/firmware/focused checks, own tracking,
affected contracts/ledgers. Preserve inherited dirty work and tests. No new
cache, speculative flash prefetch, flash-image ABI, clock source, interrupt or
DMA endpoint. Production two-image boot and physical qualification remain
separate. Stop for substantive contract conflicts, limit/assumption changes
or proof-budget exhaustion; report without waiving acceptance.
