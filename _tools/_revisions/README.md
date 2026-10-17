# 75_E5p_verify.py — revision store

Kept because a recorded measurement is bound to the revision that
produced it. Without the revision, a ledger row cannot be read
against its own code path and becomes un-auditable.

| kind | file | sha256 | bytes | note |
|---|---|---|---|---|
| live | `75_E5p_verify.debef22fa2eae94f.py` | `debef22fa2eae94fd1383880852c5b61c76613b5b4681f6d2e1a060763426622` | 18461 | on disk now: 5 outcomes / 5 codes; stamped by the fixture suite |
| recovered-from-transcript | `recovered_75_THREE_65aed0542d084207.py` | `65aed0542d084207dc8002d6b09b6faa1597f0eaff9614a54244431afa80d98e` | 8585 | NOT bit-exact: rebuilt from a session transcript's Read listing |
| recovered-from-transcript | `recovered_75_THREE_f99b0df5696d79b4.py` | `f99b0df5696d79b4a2719ebbe9637a6ba7186e8fc48d762e31da54f8db2fc701` | 13417 | NOT bit-exact: rebuilt from a session transcript's Read listing |
| recovered-from-transcript | `recovered_75_UNK_30b6ae973d8ac8fd.py` | `30b6ae973d8ac8fd714474554012afbe8e7d1a027ca92025d08775263fdc34bc` | 7184 | NOT bit-exact: rebuilt from a session transcript's Read listing |
| recovered-from-transcript | `recovered_75_UNK_fae6d4f14dbb511d.py` | `fae6d4f14dbb511d0885b6d853b4f6031424ff2186e25bb16ebc94d1eaef898c` | 6094 | NOT bit-exact: rebuilt from a session transcript's Read listing |

`recovered_*` are NOT bit-exact: they are rebuilt from a Read
listing in the session transcript, so treat them as *code-path*
evidence (which branch ran) and not as hashable originals.

## 53_E5p_temporal_gnn.py — writer revisions

The writer is not frozen the way the verifier is: it is edited when a defect is
found, so the revision matters MORE here, not less. A recorded count
(`n_exact_match`, `n_where_leq_differs_from_gt`) is a statement about the
revision that computed it, and C-159 found two defects in this file that make
the old field names mean something other than what they say.

| kind | file | sha256 | bytes | note |
|---|---|---|---|---|
| pod, produced the landed E5p artefact | (not stored here) | `55d7d8f8d19c8bbe5ac7c21980e85f750c17a64b329b5faa75972d4dcb47b959` | 72392 | 1480 lines; has the ACT fix, LACKS the within-t0 additions; shares both C-159 defects |
| local, pre-fix | `53_E5p_temporal_gnn.6698953db9ff2f79.py` | `6698953db9ff2f79b72f01b54e768034fee2048eccc0d17982b1d63eab0ca98e` | 77127 | 1563 lines; has ACT fix AND within-t0 additions; shares both C-159 defects |
| was live at 2026-09-24T03:34Z (**rc2**, pid 36327) — **SUPERSEDED**, see the `077cb379` row | `53_E5p_temporal_gnn.1ebf15e85fe73026.py` | `1ebf15e85fe73026954e642cd4b4b3526f0d2bbaed675f2b4ee3017e5492f35e` | 79168 | **1594 lines; carries the C-159 self-loop fix** (self-loop indices captured BEFORE the filter, `:641`, and counted on the unfiltered frame, `:659`) **and the within-t0 additions.** ~~THE ONLY ROW HERE THAT DESCRIBES WHAT IS LIVE~~ — **that sentence was a present-tense claim about state outside this file, and it was false by 04:22Z. Superseded by `077cb379`. Kept visible rather than deleted: a sentence a reader was told to trust should not vanish quietly.** |
| pod, **LIVE at 2026-09-24T04:22Z** — produced rc4's readings, producing rc5's | `53_E5p_temporal_gnn.077cb37906477179.py` | `077cb37906477179f20a0ec6d7a6dbc230c1f294f2f078b195828bc2452a7f8f` | 80152 | 1,609 lines; **the C-174 fix**, in two parts: a **1-D guard** in `within_t0_auc` (`:461`) that raises rather than let a score matrix reach `roc_auc_score`'s multiclass branch — so it fails at second zero instead of 2,636 s into a run — and the **actual column index** in `wtauc`: `scores[m]` → `scores[m, k]` (`:1336`). |

**Line counts in this table are `wc -l + 1`** — the 1-based number of the last
line, which is what an editor reports. `wc -l` on the two stored files gives
**1562** and **1593**, so every row reads as off-by-one against that tool. The
byte counts (77,127 / 79,168) are exact. Stated because row 31 is the
authoritative row: without the convention, anyone cross-checking the table with
`wc -l` reads *every* row as wrong, and a table that looks miscalibrated
everywhere stops being checked anywhere. A count has to carry its unit.
(Row 29's `1480 lines` is unverifiable here — that file is not stored — and is
not claimed either way.)

**★The `local, pre-fix` row is NOT the live revision, and it is the row a reader lands on.**
It is the nearest row above the live one and shares two of its defects, so interpreting the rerun's `n_exact_match` from this table alone predicts the six `c_self_loops` mismatches — which the live revision's `i_sl` fix removes. The ledger would then predict a failure the running file does not have.

**Which revision the rerun reads is measured, not inferred from mtimes:** pod file mtime `2026-09-24 03:33:48Z` < process start `03:34:54Z`, size 79,168 B, sha `1ebf15e8…` ⇒ the bytes the process read are the bytes stored here. (A file untouched since before a process started is read at that content; this is containment, not a timestamp coincidence.)

**A revision that produced a measurement must be stored BEFORE the next edit.** `1ebf15e8` was copied here on 2026-09-24 while it was still live — exactly so that the rerun's artefact stays readable against its own code path after the writer is next edited.

**★★WHICH ROW IS LIVE IS DERIVED, NOT ASSERTED (2026-09-24).** Run `_tools/_check_writer_is_live.py`: it hashes the pod's live writer and every revision stored here, names the match, and **fails if a stored revision is missing from the table above**. Two checks, because the failure had two halves — this table omitted `077cb379` entirely (`grep` count 0) while the file itself sat on disk, unindexed, so a reader checking the table could not find the writer that produced the readings they were reading, and the row the table blessed as live was two revisions stale.

**A file cannot keep a present-tense claim about external state true.** It can state a *procedure*. That is what replaces the struck-out sentence above, and it is the same substitution as everywhere else in this project: replace a memory with a check.



## Field names in `feature_filter_verification` that are narrower than their names (2026-09-24)

Read line by line off the LIVE revision (`077cb379`, 80,152 B). **None of these is
fixed by editing the writer**: an edit changes its sha256, and that sha is what
names the artefact (`80_e5p_landing.py:287-293`) and what the two-way landing
control pins. Recorded here and in the ledger instead.

| field | line | what it actually is |
|---|---|---|
| `n_compared` | `:709` `int(n)` | the **SAMPLE SIZE**. `:671-676` `continue`s a row with no edges in either frame; such a row is never compared, yet it still counts here. |
| `n_mismatch` | `:710` `n - n_exact` | **`real_mismatch + n_skipped`.** The same `continue`: a skipped row adds nothing to `n_exact` while the subtrahend stays `len(addrs)`. |
| `first_mismatches` | `:694` `elif len(bad) < 5` | **CAPPED AT 5.** Its length is not a mismatch count, and `n_mismatch - len(first_mismatches)` is therefore a valid skip count ONLY below the cap. |

**Consequences a reader has to carry**

- `n_exact_match == 300` **and** `n_mismatch == 0` together are **equivalent** to
  `n_skipped == 0` -- exactly, not approximately, because `n_exact` accumulates
  only over compared rows while `n_mismatch`'s subtrahend is the fixed `n`.
- On the artefact we hold from the old writer (`55d7d8f8`), `n_mismatch = 6` and
  `len(first_mismatches) = 5`: that is **at the cap**, so the skip count is **not
  recoverable from it** and `(real_mismatch, n_skipped)` stays bracketed by
  `{(6,0), (5,1)}`. A pod-side measurement is required to close it.
- **The old writer shares both the `n_mismatch` defect and the cap.** So any fix
  must be **ADDITIVE** -- add `n_skipped`, change no existing value and no
  existing definition. Redefining `n_mismatch` would leave two delivered
  artefacts carrying a same-named field with different meanings, and the two-way
  control that compares them would silently stop comparing like with like.
