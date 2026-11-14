# T14 Whole-chip bus, domain bridge and mailbox

## Goal

Specify and build the bus fabric that replaces the NoC (D43): one simple
request/response bus per clock domain, a reviewed bridge between domains, a
two-way mailbox between the cores, and the contract for the gateway as a bus
master. The retired interconnect is outside this task.

## Read first

- [../../../AGENTS.md](../../../AGENTS.md)
- [../03-architecture.md](../03-architecture.md), Buses and ownership
- [../10-decisions-and-risks.md](../10-decisions-and-risks.md), D7/D24/D25/D37/D43
- [../06-power-clock-reset.md](../06-power-clock-reset.md)
- [../12-formal-verification.md](../12-formal-verification.md)
- [../14-timing-design-rules.md](../14-timing-design-rules.md)
- T10's report for the Ibex memory interface, when available

## Inputs and readiness

Requires T07 and T09. The shared CDC FIFO must exist and be proved first; if
no brief has delivered it, it is the first deliverable here. Commands below
are interfaces to create, not run yet.

## May change

`docs/spec/bus.md`, `docs/spec/gateway-protocol.md`, `hw/lib/` bus bundles
and CDC primitives, `hw/ip/bus/`, `hw/ip/bus_bridge/`, `hw/ip/mailbox/`,
their tests and formal files, build and CI registration, formal ledger,
report and own status line. No peripheral, core or SoC integration.

## Steps and deliverables

1. **Write `docs/spec/bus.md` first and get it reviewed.** Use the Ibex
   memory interface signals chip-wide: request, grant, address, write
   enable, byte enables, write data, response valid, read data, error. State
   the rules: one response per granted request, in order; error responses for
   unmapped addresses and failed ownership or memory checks; maximum wait.
2. In the same document, list masters and slaves per domain, the address
   map regions, and which accesses cross the bridge. Reserve one address
   window and one interrupt line for a future NoC bridge; nothing is built
   behind it.
3. **Bus fabric (`hw/ip/bus/`):** parameterized decoder and response
   multiplexer with registered boundaries, fixed-priority or round-robin
   arbitration stated in the spec, and a default error slave.
4. **Domain bridge (`hw/ip/bus_bridge/`):** carries one transaction at a
   time between the always-on and main domains through the shared CDC
   implementation. A request toward a stopped clock must raise that domain's
   clock request and wake through an always-available path, then complete;
   it must never be lost or duplicated. Reset of either side cancels the
   transaction with an error response on the surviving side.
5. **Mailbox (`hw/ip/mailbox/`):** one small FIFO in each direction with
   interrupt and wake on non-empty, status and overflow flags. Registers
   described in the register-map format once T05 exists; until then use a
   hand-written fixture marked for regeneration.
6. **Write `docs/spec/gateway-protocol.md`:** the host byte protocol for
   reset, register read and write, and image load over UART (and USB when
   present), with the gateway acting as a bus master subject to the same
   ownership and memory checks. Specification only; the gateway block is a
   later brief. It replaces the withdrawn interconnect draft.
7. Tests against independent reference models; negative controls. Formal:
   one response per request, data and address preserved across the bridge,
   no lost wake, cancel on reset, mailbox ordering and no silent overflow.
8. Report area and timing through T09.

## Acceptance checks

Proposed interfaces, **not yet run**:

```sh
python3 tools/sbt.py "hw/testOnly deadhorse.bus.* deadhorse.bus_bridge.* deadhorse.mailbox.*"
python3 tools/formal.py --blocks bus,bus_bridge,mailbox --output build/t14/formal
python3 tools/ci.py
```

Report proved versus bounded for every property, the negative controls,
mapped area and timing. The bridge plus mailbox plus fabric is expected to be
about 0.05 mm2 mapped (assumed, not measured); report the measured figure.

## Stop and ask

The lite core cannot reach a required resource while the main clock is
stopped without a path this brief does not allow; a wake or cancel property
is only bounded; the bus rules conflict with the Ibex interface or with D24.
