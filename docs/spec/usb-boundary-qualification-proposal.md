# USB asynchronous boundary qualification — approved D77

The user approved this contract on 2026-11-22 (D77). PLAN03 B3 qualification
work resumes; approval alone does not close any check. Numerical limits and
all acceptance outside the narrowly identified asynchronous sinks remain intact.

## Evidence and problem

The source-bound routed candidate has no class-budget failures across fifteen
PVT/RC cases. Its raw worst hold is **measured −3.811670 ns**, `dnRx` to
`_7547_/D` (`engine.sie.u_phy_rx.dn_q`). Worst removal is **measured
−2.490135 ns**, `vbus` to `_6357_/RN` (`engine._release_released`, the second
flop of the engine reset-release chain). These are not missing internal delay
buffers. D+/D− and VBUS may change at arbitrary clock phase; a positive pad
delay cannot create a synchronous phase guarantee. See the commands, source
binding and limits in [the physical report](usb-physical-validation.md).

The existing structural audit lists the application, USB and AON wrapper
release chains. That list is insufficient to qualify the engine VBUS release
chain, packet reset chains or every CDC boundary. No blanket exception is
justified by the three already-audited wrapper chains.

## Approved scope

Authorize a narrowly enumerated asynchronous-boundary acceptance contract for
digital USB/fast-tier qualification:

1. Only the D pins of actual first-stage asynchronous data samplers and the
   asynchronous reset pins of identified reset-release chains are candidates.
   Both stages of a reset-release chain can have asynchronous reset pins;
   they require explicit classification. Reject missing, mixed or downstream
   aliases. Ordinary application bus pins are not included.
2. Retain raw setup, hold, recovery and removal reports. For those specifically
   qualified asynchronous sinks, assess safety through CDC/RDC structure,
   isolation, reset assertion/release behavior and positive interstage and
   downstream timing, instead of requiring an impossible source-clock phase
   relationship. Keep all other path limits and checks unchanged. Actual
   bypass/leakage, wrong-clock and reset-release faults must be rejected.
3. Keep physical pad/board qualification, reset pulse/glitch characterization
   and metastability evidence as explicit **unclosed tape-out obligations**.
   Digital CI acceptance would not claim those physical obligations passed.
   Quantitative MTBF must use characterized parameters; no invented phase,
   MTBF or pulse-width assumption is allowed.
4. Application-bus hold requires a real upstream launch/clock/load contract
   and remains an ordinary check. If that contract or required digital CDC/RDC
   evidence cannot be established, stop and report it.

This changes acceptance treatment under the explicit D77 user decision.
Implementation and independent evidence review remain required. Approval does
not itself close a failing row or grant physical signoff.

Independent review confirmed the remaining issue and the limits of existing
approvals. The sealed candidate remains `failed-validation`.
