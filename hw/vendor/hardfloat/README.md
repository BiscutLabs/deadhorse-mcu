# Selective HardFloat reuse

The lock records unmodified BSD-3-Clause Chisel source files from Berkeley
HardFloat. Only selected arithmetic modules and their helpers are compiled.
No upstream build, tests, Verilog, double-precision unit or full FPU is imported.
Deadhorse supplies the clocked transaction controller and serial multiplier.
Any compatibility or timing adaptation is recorded as a patch and applied to
build output; `upstream/` remains byte-for-byte locked.

The patched raw divider is an internal implementation component, not a drop-in
upstream interface: a request's operands, operation and rounding mode must
remain stable through the following commit edge. Its completion indication
can remain high across two clocks. The FPU wrapper holds those inputs and
captures only the first completion indication. Cancel clears the phase and
queued request as well as counter/valid control; payload is not securely erased.
T13 must connect the FPU transaction interface, not this engine.
