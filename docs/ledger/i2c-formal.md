# T17 I2C formal ledger

Base `6764ef8` plus T17 changes. The final aggregate receipt binds the
input sources, emitted models, formal jobs and child receipts. Initial evidence
is retained in `build/t17/formal-initial/result.json`; corrected-model attempts
are in `build/t17/formal-final/result.json`. Final acceptance command,
executed by fast CI: `python tools/env/run.py run -- python3
hw/ip/i2c_host/check.py --output build/t17/ci-fast/fast/i2c-host`.
Its formal child receipt is `build/t17/ci-fast/fast/i2c-host/formal/result.json`.
All seven active jobs pass; eight retained jobs remain explicitly unproved.

| Property | Method and scope | Current evidence |
| --- | --- | --- |
| WRITE byte, ninth-clock ACK, completion and waveform minima | BTOR btormc, bounded 320 edges | Correct and cover jobs timed out; unproved. Actual WRITE fault rejected |
| READ byte, selected ACK/NACK, received byte/valid and waveform minima | BTOR btormc, bounded 320 edges | Correct, cover and actual fault jobs timed out; unproved |
| Nine recovery clocks then STOP/free and recovered event | BTOR btormc, bounded 256 edges | Correct, cover and actual fault jobs timed out; unproved |
| Stuck-pin START exits, releases pins/ownership and records timeout | BTOR btormc, bounded 160 edges | Bounded; both stuck-pin covers reached and expiry-suppression fault rejected |
| Denied accesses return errors/zero and preserve observable disabled state | ABC PDR, unbounded; configured depth 32 | Proved; covers reached and owner-bypass fault rejected |

Measured correct-job wall times in that final receipt: TIMEOUT **32.715187
seconds**, DENIED **0.515329 seconds**. The aggregate independently verifies
fresh models and original timeout evidence before retaining the eight deferred
jobs. Primary and independent-agent audits authenticated every source/receipt
hash and the concrete active witnesses; no retained job is counted as rerun.

## Assumptions and limits

- Initial reset is low and subsequently arbitrary. One HF clock and qualified
  domain reset; physical reset recovery/removal and clock distribution excluded.
- Protocol models use scripted legal MMIO setup, HOLD1/LOW4/HIGH4/FREE4 and
  timeout64, except timeout8 in the stuck-pin case. WRITE/READ payload and READ
  ACK/NACK choice are captured at the public grant and held stable.
- The independent wired-AND peer ACKs WRITE and supplies an arbitrary READ
  byte. It releases both lines for recovery; the timeout case holds exactly
  one arbitrarily selected pin low. External stretching is not modeled here.
- Sleep may vary after public clockHold confirms admission; sleepEnable is
  false. These are external stimulus restrictions, not internal DUT assumptions.
- Denial fixes owner0 and maps origin0 to1, covering all denied origins1..7
  with arbitrary requests, addresses, data and strobes in the disabled state.
- One assertion conjunction retains every obligation per model; the runner
  checks its cell count. Completion deadlines prevent vacuous non-completion.
  WRITE/READ/RECOVER have completion and admitted-sleep covers; READ also covers
  ACK/NACK separately. TIMEOUT covers each stuck pin. Denial covers an error
  response, including while another request is present.
- Actual production mutations invert WRITE pull-low data, corrupt received
  bit0, suppress recovered, suppress timeout expiry or bypass owner comparison.
  A timed-out negative control is unverified, not a rejected fault.
- Bounded results do not prove arbitrary firmware, all timing tuples, exact
  timeout boundaries, ownership transfer or multi-controller interoperability.
  Public-pin simulation separately tests broader sampled scenarios, including
  stretching, recovery, filtering, deadline races and actual WRITE/READ faults.
- Digital evidence does not qualify analog filtering, pads, pull-ups, board
  timing, oscillator tolerance or metastability/MTBF.

## Timeout retention

The approved per-job limit remains 120 seconds. Existing user direction defers
timeouts explicitly as unproved and prohibits unchanged retries. The reviewed
`hw/ip/i2c_host/formal/deferrals.json` records actual timeout provenance. Each
invocation freshly emits the model and matches all source hashes, job identity,
depth, engine, property count, formal flow and pinned environment. A mismatch
fails closed for review and a justified changed-model attempt.
The environment-lock digest alone normalizes LF/CRLF to CRLF, preserving the
reviewed historical identity across Git checkouts while binding every other
byte. Emitted-model and evidence hashes remain raw. The dedicated regression
rejects content, whitespace, final-newline and standalone-CR changes.

Original receipt/status/log hashes are checked whenever those ignored build
artifacts are available. Their absence on a fresh checkout is reported
explicitly; the retained entry is still unproved and requires the exact model
and job identity. Retained rows say `solver_rerun=false` and do not fabricate
solver output, witnesses or a successful result. Successful jobs keep running.

The initial WRITE/READ emissions preceded the repeated-START SDA guard repair;
their old-model timeouts cannot qualify the corrected model. The initial
RECOVER, TIMEOUT and DENIED emissions already include that repair. RECOVER's
three matching-model timeouts are retained; corrected WRITE/READ received one
fresh attempt in `formal-final`. Its five actual WRITE/READ timeouts are also
retained. Model/job tampering, malformed policy and absent-history reporting
have dedicated runner tests. Fresh TIMEOUT requires solver exit code8; all
eight original attempts satisfy that condition.

Measured original attempt wall times, including tool startup/teardown, from
the command `python tools/env/run.py run -- python3 hw/ip/i2c_host/formal/check.py
--json build/t17/regmap/i2c_host_regs.json --output build/t17/<run>` at the
base and source identities above:

| Deferred ID | Run | Measured seconds |
| --- | --- | ---: |
| T17-WRITE-COVER | formal-final | 121.374405 |
| T17-WRITE-CORRECT | formal-final | 121.819230 |
| T17-READ-COVER | formal-final | 121.116270 |
| T17-READ-CORRUPT | formal-final | 121.762975 |
| T17-READ-CORRECT | formal-final | 121.362707 |
| T17-RECOVER-COVER | formal-initial | 121.583578 |
| T17-RECOVER-CORRUPT | formal-initial | 121.377125 |
| T17-RECOVER-CORRECT | formal-initial | 121.977066 |

Independent witness inspection of the corrected-model run confirmed WRITE's
first-bit mismatch, both completed stuck-pin choices, and failure to complete
by edge145 with timeout expiry suppressed. The owner-bypass fault violates the
required next-edge denial response after a granted non-owner request. An
initial audit expected a later error-free response; the concrete trace instead
fails response accounting first. The corrected audit checks that actual
violation without changing any solver, property or RTL; both audit attempts
are retained under `build/t17/formal-final/`.
