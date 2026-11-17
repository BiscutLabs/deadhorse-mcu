# Two-way core mailbox (T14)

Status: implementation in progress. Each local endpoint uses generated T05
`RegBlock` decode from `mailbox.regmap.yaml`, behind a registered local-bus
adapter. Two shared depth-two CDC FIFOs carry words in opposite directions;
capacity includes the registered receive head. One trusted origin owns each
endpoint (defaults AON0/main1); unauthorized accesses error without side effects.
No remote alias exposes a staging register to a second concurrent writer.

TX_DATA stages a full word. A later PUSH enqueues if ready, otherwise sets sticky
overflow. RX_DATA peeks; POP consumes or sets underflow. Commands during link
recovery set the corresponding error. EVENTS is W1C, hardware set wins clear.
Nonempty raises local interrupt/wake until consumed. Sender `wakePeer` asserts
from retained FIFO pending state, so an ungated AON controller can restart the
receiver clock; it is synchronized there through the shared CDC primitive.

Either reset flushes messages. Local reset clears staging/events; peer reset
sets a sticky event in a previously initialized surviving endpoint, even if its
clock was stopped during the reset pulse. Neither side promises retention across
its own reset. Asynchronous assert and two-edge synchronous release are local.
All external responses, IRQ/wake and cross-FIFO handshake outputs are registered.
Status combines local registered flags only and is sampled by the register bank.
Area estimate: two directions of2x32-bit storage plus heads/control/registers;
the T14 combined0.05mm2 target remains assumed until measurement.
