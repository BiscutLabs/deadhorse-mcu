# T32 scoped proof-composition experiment

Historical authored recipes from the user-approved focused attempt, not an
acceptance command or a closed proof. Run through the pinned environment from
the repository root with fresh output paths; do not overwrite historical jobs.
The complete returned-data property remains unresolved. No original assertion,
environment assumption, watchdog value, proof depth or job cap was changed.

Dependencies are the authenticated `epoch05` emission, `epoch-partition01`
control proof, `current-binding01`, and the observers under
`hw/ip/debug/formal`. The preparation recipe produces `epoch-lanes02/raw.json`.
Its model hash and all emitted-source hashes are checked by subsequent recipes.
The original model and solver-copy bindings were independently reviewed.

| Recipe | Historical output and result |
| --- | --- |
| `t32_epoch_lanes.py 8` | `epoch-data-lanes8-02`: four disjoint byte predicates whose conjunction is exactly the original word predicate; all time out. Production widths stay unchanged. |
| `t32_epoch_strengthened.py 1` | `epoch-data-strengthened1-01`: bit-zero diagnostic using the proved original control assertions; times out. No complete word proof is claimed. |
| `t32_epoch_fifo.py` | `epoch-fifo02`: literal actual request/response FIFO cell subsets, arbitrary boundary inputs, original release/synchronizer/pointer logic. Both sequence-oracle components prove; composing their guarantees with the original bit-zero predicate still times out. |
| `t32_epoch_fifo_fault.py` | Actual FIFO head-flop D-bit corruption. Both correct data properties reject concrete faults. The historical generic fault-name parser rejected the hierarchical names; `epoch-fifo-fault01/qualification.json` qualifies those same witnesses without a solver rerun. This archived recipe has the exact-name parser correction. |
| `t32_epoch_links.py` | `epoch-links01`: additional stage invariants plus the original complete data assertion; unresolved. No candidate stage invariant is accepted or assumed. |
| `t32_epoch_links_partition.py` | `epoch-links-partition01`: first source-staging property times out; the dependent sequence stops. |

Two further diagnostic models are literal observer-only transformations of
`epoch-links01/model.json`: `epoch-links-global01` clears `TRG_ENABLE` on the
nine new `links.*` assertion cells, strengthening them to every formal step.
`epoch-state-invariants01` additionally appends every original assertion under
`state_invariant.*`, also with `TRG_ENABLE=0`. The original assertions remain
unchanged. Both jobs time out; the strengthened properties are **unproved**.
Their `qualification.json`, exact SBY files and model diffs preserve the recipe.

These scripts intentionally retain historical paths. Before any future proof
receipt reuse, authenticate the exact model, all copied solver inputs, configuration,
assertion selection and upstream PASS receipts. The component extraction and
instantiation map are checked component composition, not a claim that the
standalone FIFO has the same whole-model hash as the SoC. Current receipts have
independent graph/configuration audits; the historical FIFO script alone is not
a general-purpose receipt authenticator.

The proposed next step is a local accepted-payload invariant on the actual
production-timeout `BridgeSource`, followed by a checked instance binding.
The global latest-debug-payload comparison is too broad across reset epochs.
Do not substitute the earlier short-timeout T14 model or assume the new lemma.
