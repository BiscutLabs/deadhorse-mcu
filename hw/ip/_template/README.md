# Block template

## Interfaces and protocol

Only the implicit clock and reset; no transaction interface or behavior.

## Timing domain

One clock domain. No crossings, combinational paths or specified delays.

## Reset behaviour

No state to reset. Specify polarity, synchronization and reset values when implementing a block.

## Area estimate

Not estimated or measured; the empty template is not a physical block.

## Status

Template only. Compilation and elaboration await T07. No behavior exists to simulate.
Future blocks must supply independent behavioral tests and formal properties.
