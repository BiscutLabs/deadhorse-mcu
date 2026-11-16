# Proposed JALR harness consolidation

Proposal only, requested on 2026-11-16. No script, test, monitor or evidence is
retired or consolidated in this change. Implementation needs approval.

## Proposed tools

1. `formal_model.py`: parameterized emission, source/port manifests and exact
   instrumentation projection/binding. Property names and profiles are data,
   not separate runners.
2. `formal_checks.py`: common solver jobs, original-checker qualification,
   concrete covers, actual fault controls and result/witness parsing. Preserve
   each property's guard, assumptions, depth, engine and acceptance label.
3. `formal_compose.py`: exact reset/transition/final implications, explicitly
   authenticated premise graphs and the complete original-assertion ledger.
   It must distinguish proved, bounded, abstracted, covered and unresolved.

The existing generic `assertion_partitions.py`, `critical_isa_witness.py` and
budgeted `formal_triage.py` remain shared facilities. The proposal is code
organization, not permission for new induction or more proof attempts.

## Existing tools and evidence to preserve

| Would merge / eventually retire wrappers | Evidence currently carried |
| --- | --- |
| `check_jalr_strengthened.py`, `jalr_invariant.py`, `audit_jalr_invariant.py` | Source-address invariant, exact original line171 qualification, concrete activity/faults; other diagnostic attempts retain their timeout status. |
| `check_jalr_link.py` | Link value and original line177, original guards and real result fault. |
| `check_jalr_target.py`, `check_jalr_transport.py`, `audit_jalr_transport.py` | Original target predicate and timed-out direct attempt; separately proved capture/retirement transport with concrete target fault. |
| `check_jalr_capture.py`, `audit_jalr_capture.py` | Source correspondence, exact qualification and real source fault; historical capture-arithmetic timeout is not a pass. |
| `check_jalr_request.py`, `split_jalr_alignment.py` | Accepted-request alignment, response validity and original six-condition union; earlier kind/alignment timeouts. |
| `check_jalr_ownership.py`, `audit_jalr_ownership.py`, `split_jalr_ownership.py`, `strengthen_jalr_ownership.py`, `qualify_owner_valid.py` | Issue classification, retention, retained kind and capture-valid; exact ownership splits/bindings, concrete and explicitly labelled ghost faults, historical unresolved global attempts. |
| `check_phase_stability.py`, `audit_phase_stability.py`, `compose_jalr_ownership.py` | No-write/no-clear/tag stability and exact ownership base/step/final composition with every premise discharged. |
| `compose_jalr_request_kind.py`, `audit_request_kind.py`, `check_jalr_execute_only.py`, `induct_jalr_execute.py` | Saved kind/phase, actual execute ADD reset/D-pin argument and fault; full-core ADD timeout preserved. |
| `check_jalr_operands.py`, `audit_jalr_operands.py`, `check_rf_source_control.py`, `audit_rf_source_control.py`, `compose_rf_source_stability.py`, `compose_jalr_operands.py` | Operand selection/retention, normalized RF source stability and arithmetic composition; real RF/operand faults, source-zero/negative/odd covers, exact inherited-model bindings. |
| `compose_jalr_target.py` | Exact target composition closes original line178, with all premises, concrete x0/odd/negative covers and real RVFI PC fault. |
| `complete_jalr_inventory.py`, `split_remaining_jalr.py`, `audit_remaining_jalr.py`, `check_jalr_metadata.py`, `aggregate_jalr_inventory.py` | Disjoint accounting of all33 original assertions; six singleton results, address/link/target, remaining22 and destination/trap qualification; concrete full-checker coverage/fault and preserved failed24-group attempt. |
| `jalr_receipts.py` | Historical input hashes, exact executed-source archives and controlled relocation of unchanged evidence. |

Corresponding `test_*.py` files would become parameterized test tables grouped
by model transformation, receipt/witness handling, exact assertion accounting and
composition. Keep each current positive/negative fixture as a named case; do
not replace them with source-text matching or discard cases because another
fixture looks similar. `test_assertion_partitions.py` and the generic timeout
triage fixtures continue covering shared policy independently.

## Migration and acceptance proposal

- First add parameterized APIs with the old entry points as thin compatibility
  wrappers. Freeze the current source version and preserve all raw receipts.
- Compare generated models/configurations and source inventories against the
  current accepted jobs. Semantic model equality must include assertions,
  assumptions, clocks, reset values, state and outputs, not just port names.
- Re-run the small harness/negative fixture suites and representative concrete
  witness parsing. Reuse solver outcomes only when exact model, tool and source
  identity is established; no blanket reclassification of historical timeouts.
- Keep the original33 assertion union and every mutation/cover role mandatory.
  A generic tool must reject missing premises, unknown statuses, stale inputs,
  vacuous target activity and lost original guards.
- Retire wrappers only after independent review and explicit approval of the
  migration. Historical manifests must still resolve to their original source
  version and artifacts. No proof sweep is proposed merely to rename tools.

The risk is evidence loss during refactoring: source-path changes can invalidate
strict fingerprints even when logic is identical. Retaining immutable historical
sources and checking generated-model identity is required before migration.
