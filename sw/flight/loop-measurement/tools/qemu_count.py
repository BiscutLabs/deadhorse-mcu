#!/usr/bin/env python3
"""Count instructions QEMU executed in the program: lines 'Trace ...' (one insn per TB with -singlestep),
excluding the boot ROM (pc < 0x80000000) and everything from the first visit of the final spin loop on."""
import re, sys
pcs = []
for l in open(sys.argv[1]):
    if l.startswith("Trace"):
        pcs.append(int(re.search(r"\[[0-9a-f]+/([0-9a-f]+)/", l).group(1), 16))
last = pcs[-1]
end = pcs.index(last)               # first visit of the terminal spin loop
# QEMU logs a TB twice when an MMIO store forces it to be re-entered (observed: the UART stores in the
# harness); drop consecutive duplicate PCs (the program has no 1-instruction spin loops before its end).
prog = [p for p in pcs[:end] if p >= 0x80000000]
dedup = [p for i, p in enumerate(prog) if i == 0 or p != prog[i - 1]]
print(len(dedup))
