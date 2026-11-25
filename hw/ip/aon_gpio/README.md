# AON GPIO

Six lite-owned GPIO pads, four with SPI alternatives. GPIO and short-pulse
capture operate with OSC_IN stopped. The [integration contract](../../../docs/spec/plan05-integration.md)
defines polarity, clear/rearm, mux ownership and the assumed physical pulse
width. Radio IRQ wakes lite; the validated watcher uses mailbox to wake main.

AON ownership of shared pads is acknowledged by main before the AON driver
opens. A mode change requires disabled/disarmed GPIO, idle SPI and main
availability. The shared `CdcPulseCapture` uses an asynchronously asserted
flip-flop and shared synchronizers, with sticky/coalescing event semantics.
Idle clear cannot erase an event that has not reached the synchronized status.

`AonGpioSpec` exercises short pulses without an intervening AON edge, both
polarities, clear/rearm/coalescing, ownership and actual fault controls. Complete
formal qualification is deferred: the current checker confuses an acknowledged
pipeline echo with a new unacknowledged event. No RTL failure was demonstrated
by that trace, and no passing full formal result is claimed. See
[formal scope](formal/README.md). Phase-end acceptance remains open.
