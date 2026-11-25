# Lite boot control and BOOT_MODE properties

PLAN05 replaces the historical lite-first BootRelease model. Run
`python hw/ip/boot_control/formal/check.py --output build/plan05/boot-formal-N`
in the pinned environment, with a fresh output directory. No CI is invoked.

| Model | Property | Assumptions |
| --- | --- | --- |
| LiteBootStateFormal | Held/running/draining states and error agree with an independent three-state machine; hold waits for quiet; service reset retains the boot epoch | Initial epoch reset asserted, all inputs and independent service reset arbitrary thereafter; one AON clock |
| BootOwnerFormal | All seven denied origins error, cannot release lite and cannot mark context ready | Initial reset asserted; origin is one of0,2..7; arbitrary requests |
| BootResetContextFormal | Fresh watchdog edge, keyed context commit and error agree with an independent event model; stale hold across reset is not fresh | Initial epoch reset asserted; hold/commit/key and later reset arbitrary; one AON clock |
| BootModeStrapFormal | First qualified sample is frozen until whole reset, independent of later pad changes | Initial whole reset asserted; pad and qualification arbitrary thereafter |

All four positive jobs use unbounded ABC PDR with the existing120-second cap.
Negative controls bypass drain completion, release key, owner check or strap
freezing, stale reset-hold detection or context key checking. Covers and concrete negative witnesses use depth12; this witness
bound does not limit the positive proof. No software-sequencing assumption is
made. Sampled proofs do not qualify analog recovery/removal or physical strap
setup. BOOT_MODE is sampled during whole-reset qualification, not main-only or
service reset.

Measured by the command above with `--output build/plan05/boot-formal02` on
main29cab7e5 plus receipt-hashed working sources: all10 historical jobs passed before the context addition. The current owner/context
checks require fresh evidence; `--cases owner,context` selects those affected jobs
without claiming a full block replay. Separate
BootControlSpec, BootModeStrapSpec, SocBootStrapSpec and SocBootReleaseSpec
exercise MMIO, reset scopes and the actual performance-first load/release path.
Historical T28 loader/START evidence is retained in its report, not reused as
PLAN05 boot acceptance. Final phase receipts remain required.
