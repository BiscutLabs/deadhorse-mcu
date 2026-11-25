# AON GPIO formal qualification — deferred

`check.py` retains the attempted real shared-CdcPulseCapture harness and failed
checker evidence. Initial reset is asserted; reset, pad and clear are arbitrary
thereafter. Four formal sampling steps represent each AON period; rising and
falling polarity are separate cases. Analog minimum pulse width and metastability
remain physical obligations, not modeled guarantees.

Earlier eventual-capture checks proved, but did not reject the idle-clear fault.
The stronger sticky checker then failed because acknowledged/coalesced pipeline
residue was interpreted as a new event. Receipt `aon-capture-formal05` is failed,
not a proof waiver. A sound future monitor must track armed/rearm capture through
acknowledgement, rather than treating every pending rise as a fresh event. Do not
rerun unchanged or add assumptions excluding legal pulse/clear overlap. Under the
user's minimal-proof policy, this qualification is deferred; the independent
short-pulse and idle-clear simulation fault tests remain required.
