# 16 — E5p: the predictive half of the plan's E5 (temporal GNN vs GraphSAGE vs MLP)

**Status: RUN COMPLETED — AND THE RUN'S OWN LEAKAGE CRITERIA DID NOT ALL PASS.
The plan's E5 is therefore NOT satisfied.** The run finished with an observed
`RSC_EXIT=0` at 03:29 UTC (2,667 s, `status: "ok"`), and it wrote
`53_E5p_result.json` / `.txt`. Those artefacts were then renamed on the pod to
`53_E5p_result.oldwriter_55d7d8f8.{json,txt}` — the name is somebody else's
bookkeeping, not one of mine, and I did not choose it or verify what it means.
**`results/53_E5p_result.json` does not exist under that name**, locally or on
the pod. What I hold and report from is the renamed file, pulled byte-for-byte
(sha256 `b07dfc093b217999…`, 195,651 B).

The three arms have numeric AUCs (§4). **They are nonetheless not admissible**,
because two of the run's own pre-registered leakage criteria failed:

| criterion | required | measured | verdict |
|---|---|---|---|
| `shuffled_control_at_chance` | test AUC ≈ 0.5 | **0.8107 / 0.8254 / 0.8393** | **FAIL** |
| `feature_filter_verification_exact` | exact on all samples | **294 / 300**, all 6 on `c_self_loops` | **FAIL** |

The driver agrees: **`run_pipeline.py`'s `ev_require` returns `False` on this
artefact** (measured by running the real predicate against the real file, not
against a synthetic fixture), so E5p reads **NOT DONE**. §6 states what that
does and does not license; §1 and §7 give the diagnosis of each failure. The
short version is that **the shuffled-label control is the one that matters**: a
model trained on *random labels* scores 0.81–0.84 against a real arm's
0.846–0.868, so most of the arms' apparent skill is not attributable to
label-driven learning on the evidence collected here. The cause is **not
established** and the discriminating measurement that would settle it has not
been run.

Code `_server/53_E5p_temporal_gnn.py` (byte-identical on pod and local, sha256
`1ebf15e85fe73026…` — so the `55d7d8f8` suffix is *not* this script's hash),
`_server/53d_tgn_wire.py` (TGN wiring test, passed), `_server/53c_bench.py`
(cost envelope, run by the coordinator).

---

## 0. What the plan asked for, and what is delivered

The plan's E5 (v5, line 89) asks for:

> `TGN / TGAT 时序图神经网络，预测节点在 t+Δ 是否存续（AUC 对比 GraphSAGE、MLP 特征基线）`

— a temporal GNN predicting, at a horizon Δ, whether a node is still present,
scored by AUC against a GraphSAGE baseline and a feature-only MLP.

`05_E5fin_recurrence.md` delivered the **measurement** half (recurrence) and no
model, and said so. **This report covers the prediction half**: three arms
trained and evaluated, at Δ ∈ {1, 3, 5}, each with a bootstrapped AUC on a
held-out address split. The plan's E5 will be **satisfied** when the three arms'
AUCs exist in `results/53_E5p_result.json` from a run that completed; **as of
this writing it is satisfied in construction, not in result** — the run is
mid-training and the artefact does not exist. That distinction is the whole of
the status line above, and it is not a formality: the project's standing rule is
that a number not measured is not reported, and "the harness is built and
running" is not "the experiment is done". Four things about how it was run are
load-bearing and are stated here rather than buried:

1. **Δ is not specified by the plan, so it is a free parameter.** It is
   pre-registered as {1, 3, 5} and reported for all three. Δ = 1 is the
   degenerate end of that axis and is *exactly* `05_`'s recurrence label
   (`t1 - t0 ≥ 1` ⇔ `n_steps_observed ≥ 2`; the run asserts the two counts are
   equal). A single Δ shown alone would not be interpretable, and the censoring
   table extends to Δ = 20 so the trade-off is visible past the pre-registered
   range.

2. **The plan's MLP baseline cannot be built the way the plan describes it, and
   the leak is measured here, not asserted.** `wallets_features.csv` has 55
   non-key, non-time columns and **all 55 are constant within address** — the
   file is not a per-step panel, it is address-level *lifetime* aggregates
   repeated on every row. `num_timesteps_appeared_in` **is** `n_steps_observed`,
   which at Δ = 1 **is** the label. So an MLP on the provided table is not a
   baseline, it is a measurement of the leak, and the leak is near-total at
   **every** Δ, not only at the degenerate one.
   **Instrument note (added 2026-09-24):** this sentence previously read
   "it reaches **AUC 1.0000 at Δ = 1** (§4, and `naive_leaking_baseline` in the
   JSON)" — a number stated without the run that produced it. That `1.0000` is
   §4**(ii)**'s value, the **`--quick`** wiring-check reading on a 30,000-address
   subsample, which §4 itself says is **not** the reading to quote; and this
   report's opening rule bars filling anything from the `--quick` run. The same
   token is also ambiguous in the body, since `1.0000` is separately the
   `Time step` positive control (§3). The full-population reading belongs to
   (i) and is filled from the result JSON, not from here.
   This matters more than
   bookkeeping, because the plan's own risk table fires a fallback ("降级为
   GraphSAGE + 手工时序特征") when the temporal GNN "improves little" over the
   baseline. Against the leaking baseline **every honest arm would look weak**,
   and the fallback would fire on an artefact of the baseline rather than on a
   property of the GNN. Both real arms therefore stand on the same
   point-in-time footing: every feature is rebuilt from the edge stream
   truncated at t0.

3. **The population is all 822,942 addresses, not the labelled cohort.** The
   survival label is defined for the "unknown" class too, so taking the full
   population removes `05_`'s scope problem (its cohort is the least-persistent
   32% of the dataset) from this arm. The class-1/2 numbers are reported as a
   *subset of the same predictions* — no separate model — for comparability with
   `05_`.

4. **The cost envelope was measured before the run, not guessed.** The TGN
   memory pass is 2.51 s per time step at full scale (123 s per 49-step pass),
   and GraphSAGE's first full-scale epoch took 328 s. The run was given
   `--epochs 6 --eval-every 2`. **The epoch budget is the main limitation of
   this report** and is stated in §6 rather than discovered by the reader.

---

## 1. The leakage rule, and how it is enforced rather than promised

Everything the model sees at t0 must have been knowable at t0. An address that
enters at t0 has at most `49 - t0` steps of room, and entry timing differs by
class, so any quantity computed over the full 49-step window encodes the answer.

The measurement that decided the whole feature design:

| question | answer |
|---|---|
| non-key, non-time columns of `wallets_features.csv` | 55 |
| columns **constant within address** | **55** |
| columns varying within address | **0** |
| positive control: "Time step" varies within address | **1.0000** on the addresses with ≥ 2 steps |
| `num_timesteps_appeared_in` vs `n_steps_observed` | **0 mismatches** over 822,942 addresses |

So **not one column of that file is usable as a feature**: not "the obviously
leaky ones are dropped", all of them are. The only thing read from it is
`Time step`, and only to define t0/t1 and therefore the label. Every model
feature is rebuilt causally from `AddrTx × TxAddr × txs_features['Time step']`,
filtered to `step ≤ t0`.

Two points about that table are corrections to my own earlier work and are
recorded as such:

- **The positive control was missing.** The first version of this check excluded
  `Time step` *by name*, so `columns_varying_within_address` was empty **by
  construction** and the instrument had never been shown able to return a
  nonzero value. "55/55 constant" was therefore a statement about the check, not
  about the file. Running the same instrument on `Time step` makes it return
  1.0000 on multi-step addresses, which is what licenses the 0-of-55 reading.
- **`c_distinct_out`/`c_distinct_in` are the cumulative *sum* of per-step
  distinct-counterparty counts, not the distinct count over all steps ≤ t0.**
  The true count is not available from a cumsum; the sum is, and it is causal.
  The verification recomputes the same quantity, so the two are not confused.

### The check itself

`leakage_check` in the JSON carries five blocks. **Two of them failed**; they are
listed with their measured values, not their intentions:

| block | required | **measured** | verdict | what it does **not** establish |
|---|---|---|---|---|
| (a) leak control: MLP on `t1 - t0` | AUC ≈ 1.0 | **1.0 / 1.0 / 1.0** | PASS | says nothing about the real arms |
| (b) shuffled-label control | test AUC ≈ 0.5 | **0.8107 / 0.8254 / 0.8393** | **FAIL** | nothing — and see below, this is the failure that matters |
| (c) feature recomputation from raw CSVs | exact on all sampled | **294 / 300**; all 6 differ only on `c_self_loops` | **FAIL** | a **sample of 300 addresses**; 300 clean points calibrate those 300, not the 301st |
| (c′) the same under a **wrong** `step > t0` filter | must differ | 294 / 300 differ (**0.98**) | PASS | that the equality above is not vacuous — it is not inert, so (c) is not a tautology |
| (d) named-column denial | none present | **0 present** in model matrices | PASS | — |
| (e) `num_timesteps_appeared_in == n_steps_observed` | 0 mismatches | **0 / 822,942** | PASS | — |

### Diagnosis of failure (b) — the one that costs the result

A control trained on **permuted** labels scoring 0.81–0.84 instead of ~0.5 means
the model was not learning from the labels. Against that, the comparison in §4
shows the graph arms are matched or beaten by the control. **The cause is NOT
ESTABLISHED.** Two candidates, and I have not run the measurement that separates
them:

1. **Selection on true validation labels.** Early stopping keeps the epoch with
   the best **validation** AUC, and validation labels are *not* permuted. A model
   trained on noise still emits a score that is monotone in its strongest input
   direction; over ~5 epochs the one that best ranks the true val labels gets
   kept. The strongest input direction here is plausibly `room = 49 − t0`, which
   §5 shows carries a large share of the pooled AUC.
2. **The permutation is not fully effective** — applied to a copy, or to the
   wrong index set, leaving the real labels in place for part of training.

**These are distinguishable and the test is cheap: report the shuffled control's
*within-t0* AUC, and give it a fixed epoch budget with no val-based selection.**
If the within-t0 AUC is ≈ 0.5 while the pooled one is ≈ 0.81, candidate 1 is the
cause and the control is mis-specified rather than the features leaking. I did not
run this, so I do not claim it. Note also that the control used
`max(mlp_epochs // 4, 3) = 5` epochs against the real MLP's 20, so the two are
**not budget-matched** and the 0.035 gap between them is not a clean contrast.

### Diagnosis of failure (c) — the verifier's self-loop channel is inert

All six mismatches differ on **exactly one** feature, `c_self_loops`, and in the
**same direction every time**: the pipeline stored 1 or 2, the recomputation
returned 0. The other four compared features — `c_out_edges`, `c_in_edges`,
`c_distinct_out`, `c_distinct_in` — matched **exactly on all 300** samples.

Stored `[1,0,1,1,0]` vs recomputed `[1,0,0,1,0]`; stored `[2,1,2,2,1]` vs
`[2,1,0,2,1]`. A feature whose recomputation is **0 for every mismatch, in one
direction only**, is the same shape as the missing positive control in §1's
variance block: the verifier's self-loop path is scoring zero by construction.
The likely mechanism (not confirmed) is that the verifier recomputes from the
address→address edge list, where self-loops were **dropped by design** (45,981 of
them, §2), while the pipeline counts `c_self_loops` from the transaction-level
join *before* that drop. If so, the mismatch is a **verifier** defect, not a
feature defect — but that reading is exactly what the verifier was supposed to
rule out, so **it cannot be assumed and the discrepancy stands as a failure**.
Also worth noting: `first_mismatches` stores only 5 of the 6.

What this failure does **not** mean: it is not evidence of leakage in
`c_out_edges`, `c_in_edges`, `c_distinct_out`, or `c_distinct_in`, all of which
verified exactly. Those four carry the leakage-relevant content.

---

## 2. What was measured on the data before anything was modelled

| quantity | value |
|---|---|
| addresses in `wallets_classes` | 822,942 (class 1: 14,266 · class 2: 251,088 · class 3: 557,588) |
| addresses with ≥ 1 observed step | 822,942 (**0 dropped**) |
| `AddrTx × TxAddr × txs` joined rows | 2,868,964 |
| self-loops dropped | 45,981 |
| timed address→address edges | 2,822,983 |
| distinct `(src, dst, step)` triples | 2,801,409 (dedup shrink **0.0076**) |
| undirected edges used for message passing | 5,602,818 |
| distinct `(address, step)` cells | 920,691 |

This reproduces `53a_E5p_probe.py` and `05_` exactly — 2,868,964 / 45,981 /
2,822,983 / 920,691 are the same four numbers those reports carry, so the join
closes here as it did there.

**Δ = 1 is the recurrence label.** `label_Δ = 1[t1 − t0 ≥ Δ]`; at Δ = 1 that is
`1[t1 > t0]` ⇔ `n_steps_observed ≥ 2`. The run asserts the two counts are equal
(`delta1_equals_recurrence`).

### Censoring is computed, not assumed

An address can satisfy `t1 − t0 ≥ Δ` only if a step at or after `t0 + Δ` exists
inside the 49-step window, i.e. iff `t0 ≤ 49 − Δ`. Addresses failing that are
**excluded** from that Δ's eligible set, never relabelled 0.

| Δ | eligible | excluded (censored) | excluded share | survival rate (eligible) |
|---|---|---|---|---|
| 1 | 811,269 | 11,673 | 0.01418 | 0.07579 |
| 3 | 775,403 | 47,539 | 0.05777 | 0.06124 |
| 5 | 738,194 | 84,748 | 0.10298 | 0.05119 |
| 10 | 620,835 | 202,107 | 0.24559 | 0.03884 |
| 20 | 474,120 | 348,822 | 0.42387 | 0.02196 |

All five `(excluded count, excluded share, survival rate)` triples agree
**exactly** with the reference values the coordinator computed independently —
including Δ = 1's 11,673. That agreement is a genuine independent replication:
the reference was produced by a different route, and the integers match, not just
the rounded shares.

**A withdrawn claim, recorded because it is a recurrence of a known failure
mode.** An earlier draft of this section asserted that Δ = 1's excluded count
"differs by a handful of addresses" from the reference. It did not. I had
*inferred* an integer from a **rounded share** (0.01418), got 11,670, and
reported the 3-address difference between that inference and 11,673 as a
discrepancy in the data. The actual count is 11,673, identical to the reference.
The error is the library's oldest one in a new costume: **reading an estimate off
a rounded proxy and reporting it as a measurement.** The share was correct; the
integer I derived from it was never measured. Withdrawn in full.

Survival differs sharply by class, which is why §4 reports the class breakdown:

| Δ | illicit | licit | unknown |
|---|---|---|---|
| 1 | 0.01900 | 0.05883 | 0.08483 |
| 3 | 0.01440 | 0.05258 | 0.06624 |
| 5 | 0.01126 | 0.04795 | 0.05360 |

### Two things that are construction, not behaviour

- **Structural zero at the window edge.** An address first seen at t0 = 49 can
  never satisfy Δ ≥ 1. **11,673 addresses (1.42% of the population) enter at
  t0 = 49** — exactly the Δ = 1 excluded count, which is not a coincidence but
  the definition. A further **73,075** enter at t0 ∈ [45, 48], so at Δ = 5 the
  label is a structural zero for all of them. Any sentence of the form
  "persistence falls with Δ" partly restates this window effect, which is why the
  within-t0 AUC is reported alongside the pooled one. §5 quantifies how much of
  the pooled AUC is exactly this.
- **The class-correlated gap.** Eligible survival differs strongly by class
  (illicit is by far the lowest, §4). **The model is class-blind** — class is
  never an input. So part of any well-fitting model's AUC *is* that gap,
  recovered from behaviour rather than supplied. This is stated up front because
  otherwise the first question a reader asks is whether the AUC is just
  illicit-vs-licit.

---

## 3. The arms

All three are CPU-only (`torch.set_num_threads(8)`; another job shares the box).
Split by **address**, never by row, 70/15/15, seed 20260924:
**train 576,059 / val 123,441 / test 123,442**, all three pairwise overlaps **0**;
39,765 of the test addresses are class 1 or 2.

| arm | features | graph |
|---|---|---|
| `mlp_feature_only` | own activity at `step ≤ t0` only | none |
| `graphsage` | own activity + graph structure (edges ≤ t0) + a 2-layer `SAGEConv` embedding on the cumulative snapshot | undirected, deduplicated, all 822,942 addresses as nodes |
| `tgn` | `TGNMemory` (canonical `IdentityMessage` + `LastAggregator` + `GRUCell`) state at t0 through a `SAGEConv` readout on the t0 snapshot, concatenated with the arm-2 tabular features | same snapshot graph |

All three are **multi-task**: one output head per Δ, sharing one trunk and one
training run. The alternative — one full run per Δ per arm — spends 3× the
compute to answer the same question, and the TGN memory pass does not depend on
the label at all. The heads are the only per-Δ parameters, and **every arm gets
the same treatment**, so the comparison between arms is unchanged.

### The TGN arm had to be de-risked before a two-hour run

`TGNMemory.update_state` writes `self.memory[n_id] = memory` **in place**.
Repeated in-place writes under autograd either raise a version-counter error on
step 3 or *silently deaden the graph on step 1* while the loss still falls (the
readout head alone can fit the training labels). So the check is a gradient
check, not a loss curve. `53d_tgn_wire.py` runs the arm's exact API surface at
20k nodes and asserts:

- gradients reach **`gru`, `time_enc`, `conv`, `trunk`, `heads`** on every step;
- `memory` actually moves (`|memory|₂ = 0` after `reset_state`, `> 0` after
  `update_state`) — a memory that never moves makes every readout identical and
  an "untrained" TGN indistinguishable from a trained one;
- `state_dict()` → `load_state_dict()` round-trips (this is how the best-val
  state is restored);
- the readout is deterministic on a fixed state.

Two implementation facts cost real time and are recorded so they are not
re-learned:

- **`t` must be `long`.** `TGNMemory` scatters it into its long `last_update`
  buffer; a float `t` raises *"Index put requires the source and destination
  dtypes match"*. The error names dtypes, not the argument.
- **`IdentityMessage` has no parameters.** It is a concat, so
  `msg_module.parameters()` is empty, and asking it for a gradient raises
  `max() arg is an empty sequence`. That is how the first smoke test of this
  arm failed. `53d` asserts the count is 0 rather than querying it for a
  gradient.

The TGN is kept permanently in **eval** mode. In eval mode `update_state` stores
the batch's messages and immediately applies them, so `tgn.memory` *is* the state
at `steps ≤ T` and can be fed straight to the readout. In train mode it applies
what the *previous* call stored and only then stores this call's, so the
committed memory lags one batch and reading it needs a per-call `forward()` over
the node set — at 822,942 nodes that is the whole cost of the arm. Gradients
still reach the GRU on the eval-mode path (measured: 53c; re-asserted: 53d).
Honestly stated: a **nonzero** gradient is measured; a **load-bearing** one is
not — step-1 `time_enc` gradients are ~2 orders of magnitude below `gru`'s.

---

## 4. Results

All figures are on the held-out **test** split (123,442 addresses, eligible
counts below), bootstrapped 95% CI, 1,000 resamples, seed 20260926.

| arm | Δ | n | **test AUC** | 95% CI | within-t0 AUC | acc | degenerate acc | class-1/2 subset AUC |
|---|---|---|---|---|---|---|---|---|
| `mlp_feature_only` | 1 | 121,716 | **0.8462** | [0.8418, 0.8503] | 0.7645 | 0.7732 | 0.9235 | 0.8247 |
| `mlp_feature_only` | 3 | 116,398 | **0.8647** | [0.8602, 0.8686] | 0.7626 | 0.7812 | 0.9376 | 0.8476 |
| `mlp_feature_only` | 5 | 110,841 | **0.8682** | [0.8637, 0.8727] | 0.7644 | 0.7687 | 0.9481 | 0.8570 |
| `graphsage` | 1 | 121,716 | **0.8037** | [0.7993, 0.8081] | 0.7285 | 0.7063 | 0.9235 | 0.7835 |
| `graphsage` | 3 | 116,398 | **0.8212** | [0.8161, 0.8259] | 0.7293 | 0.7219 | 0.9376 | 0.8044 |
| `graphsage` | 5 | 110,841 | **0.8397** | [0.8353, 0.8447] | 0.7342 | 0.7098 | 0.9481 | 0.8120 |
| `tgn` | 1 | 121,716 | **0.7963** | [0.7917, 0.8009] | 0.7143 | 0.7449 | 0.9235 | 0.7880 |
| `tgn` | 3 | 116,398 | **0.8140** | [0.8090, 0.8184] | 0.7164 | 0.7792 | 0.9376 | 0.8146 |
| `tgn` | 5 | 110,841 | **0.8328** | [0.8280, 0.8378] | 0.7110 | 0.7770 | 0.9481 | 0.8232 |
| *`shuffled_label_control`* | 1 | 121,716 | *0.8107* | — | — | — | — | — |
| *`shuffled_label_control`* | 3 | 116,398 | *0.8254* | — | — | — | — | — |
| *`shuffled_label_control`* | 5 | 110,841 | *0.8393* | — | — | — | — | — |

Wall times: `mlp_feature_only` 45.3 s (20 epochs), `graphsage` 998.6 s (6
epochs), `tgn` 1,003.0 s (6 epochs); the whole run 2,667.1 s.

### The three results that matter, in order of how much they cost

**1. The graph does not help — it hurts.** The feature-only MLP beats **both**
GNN arms at **every** Δ, by 0.029–0.043 AUC (far outside the CIs). The temporal
GNN arm is the *worst* arm at **every** Δ (0.7963/0.8140/0.8328, below GraphSAGE
throughout). On this dataset, at this budget,
with these features, the address→address graph contributes no usable signal
beyond what an address's own point-in-time activity already carries.

**2. The GNN arms are indistinguishable from a model trained on random labels.**
This is the finding that decides the run's admissibility, and it is not a
subtlety:

| Δ | `graphsage` | `tgn` | shuffled-label control | control − GraphSAGE | control − TGN |
|---|---|---|---|---|---|
| 1 | 0.8037 | 0.7963 | **0.8107** | **+0.0070** | **+0.0144** |
| 3 | 0.8212 | 0.8140 | **0.8254** | **+0.0042** | **+0.0114** |
| 5 | 0.8397 | 0.8328 | **0.8393** | −0.0004 | **+0.0065** |

**The shuffled-label control scores higher than the TGN arm at all three Δ, and
matches GraphSAGE to within 0.0004 at Δ = 5.** A model trained on permuted labels
is as good as, or better than, both graph arms. Whatever the graph arms are
measuring, it is not the training labels.

The MLP is the exception: it exceeds the control by +0.0355 / +0.0393 / +0.0289,
which is ~7× the CI half-width, so the MLP arm *does* carry label-driven signal.

**3. Accuracy is uninformative, as the plan warned.** Every arm's accuracy
(0.706–0.781) is **below** the degenerate "predict never recurs" baseline
(0.9235–0.9481) at every Δ. Predicting "never recurs" beats every trained model
on accuracy. This is why AUC is the headline and why the degenerate number is
printed beside every accuracy above.

### Class-stratified breakdown (illicit / licit / unknown)

The MLP's skill is concentrated in the **unknown** class and is worst on
**illicit** — which matters, since illicit is the class the study nominally cares
about:

| arm | Δ | illicit | licit | unknown |
|---|---|---|---|---|
| `mlp_feature_only` | 1 | 0.7594 | 0.8218 | 0.8602 |
| `mlp_feature_only` | 3 | 0.7923 | 0.8451 | 0.8782 |
| `mlp_feature_only` | 5 | 0.8399 | 0.8537 | 0.8800 |
| `graphsage` | 5 | 0.9082 | 0.8059 | 0.8614 |
| `tgn` | 5 | 0.8592 | 0.8184 | 0.8450 |

Note GraphSAGE's Δ = 5 illicit AUC (0.9082) is its best number anywhere — but it
comes with an n of 1,924 with 18 positives, and §6 gives it no weight. Illicit
positive rates are **0.94–1.38%**, an order of magnitude below unknown's
5.5–8.6%, so the illicit column is the noisiest in the table.

### The plan's MLP baseline, as the plan specifies it — and why it is not used

An MLP on **all 55** provided columns, same split, same labels, same
architecture as `mlp_feature_only`. Two readings exist, and they are **different
instruments** and are labelled as such:

**(i) Full population, `--quick` off** — the reading to quote, from
`53_E5p_result.oldwriter_55d7d8f8.json`, `naive_leaking_baseline.by_delta`:

| Δ | test AUC | 95% CI | pos_rate | n |
|---|---|---|---|---|
| 1 | **1.0** (exactly) | [1.0, 1.0] | 0.07650 | 121,716 |
| 3 | **0.9999999975** | [0.9999999885, 1.0] | 0.06236 | 116,398 |
| 5 | **0.9999997343** | [0.9999993366, 0.9999999622] | 0.05186 | 110,841 |

`admissible: false` — present and marked inadmissible, as the driver requires.
Note the trailing digits: they are **not** 1.0, and the run reports them rather
than rounding to 1.0000. The bootstrap CI's lower bound at Δ = 5 is
0.99999934 — still effectively the answer.

**(ii) Wiring-check reading, `--quick` on** (a 30,000-address subsample with at
least one step; the subsample is taken *by address*, so it is the whole
construction at smaller n, not a different construction):

| Δ | test AUC | val AUC trajectory |
|---|---|---|
| 1 | **1.0000** | 0.99740 → 0.99973 by epoch 8 |
| 3 | 0.9999 | — |
| 5 | 0.9996 | — |

**★ The mode is part of the number.** (ii) is a wiring-check reading: it was
taken to prove the harness runs end to end, on 3.6% of the population. The
**structural point survives the subsample** — a leaking feature set is leaking at
any n — but **the precise values do not**, and (i) is the reading to quote. The
causal-feature MLP in the same quick run reached val 0.79767 by epoch 3 (~0.79)
against the naive arm's 0.99964 in the same log, which is the comparison that
decided the feature design; the same contrast is visible at full scale in
§4**(i)** versus §4 (≈1.0 vs 0.846–0.868).

**INADMISSIBLE — this is not a baseline, it is a measurement of the leak.** It is
not merely that Δ = 1 is degenerate: the provided table contains
`last_block_appeared_in`, `first_block_appeared_in` and `lifetime_in_blocks`,
which *are* `t1 − t0` up to the block↔step mapping, so the leak is near-total at
**every** Δ, not just at the degenerate one. The plan's fallback condition
("the GNN improved little over the feature baseline") would therefore be
evaluated against a baseline scoring ≈1.0 at every Δ, and **would fire on an
artefact**. That is why `mlp_feature_only` above is rebuilt from the edge stream
truncated at t0 instead.

---

## 5. Specificity: is the AUC the model's, or the calendar's?

`room = 49 − t0` is knowable at t0 and is a strong predictor on its own — an
address entering at step 2 has more room to recur than one entering at step 46.
A pooled AUC therefore partly measures *when* an address entered, which is a
property of the dataset's growth, not of the address's behaviour. The within-t0
weighted AUC removes t0 exactly by pooling per-entry-step AUCs by bin size.

**The calendar component is large and consistent.** Taking the share of the
excess-over-chance AUC that survives entry-step conditioning:

| arm | Δ | pooled | within-t0 | calendar share of excess |
|---|---|---|---|---|
| `mlp_feature_only` | 1 | 0.8462 | 0.7645 | 23.6% |
| `mlp_feature_only` | 3 | 0.8647 | 0.7626 | 28.0% |
| `mlp_feature_only` | 5 | 0.8682 | 0.7644 | 28.2% |
| `graphsage` | 1 | 0.8037 | 0.7285 | 24.8% |
| `graphsage` | 3 | 0.8212 | 0.7293 | 28.6% |
| `graphsage` | 5 | 0.8397 | 0.7342 | 31.1% |
| `tgn` | 1 | 0.7963 | 0.7143 | 27.7% |
| `tgn` | 3 | 0.8140 | 0.7164 | 31.1% |
| `tgn` | 5 | 0.8328 | 0.7110 | 36.6% |

**Roughly a quarter to a third of every arm's apparent skill is entry timing.**
The share grows with Δ for all three arms, and is largest for the TGN — the arm
whose pooled AUC is most flattered by it.

**This table also locates the missing measurement.** Every arm's *within-t0* AUC
(0.711–0.765) sits **below** the shuffled-label control's *pooled* AUC
(0.811–0.839). Those two are not comparable as they stand — but the arms'
within-t0 numbers are the ones that have had the calendar removed, while the
control has no within-t0 reading at all. So the honest position is:

- the arms' pooled AUCs are **beaten by a control trained on random labels**;
- the arms' *calendar-free* AUCs cannot be compared to that control, because the
  control's calendar-free AUC **was not measured**.

That is precisely the gap §1's diagnosis names, and it is why the missing
measurement — the shuffled control's within-t0 AUC — is the one thing that would
move this from "not admissible" to a finding.

### The arm-vs-arm comparison, on the judged metric

The pooled column above (and its larger numbers) is **not** the metric the
control is judged on. Restating the plan's actual deliverable — "TGN vs baseline,
AUC" — on the within-t0 metric, which is where the null is 0.5 by construction
(`_tools/77_E5p_arm_table.py`, run by me against this artefact):

| comparison | Δ | TGN | baseline | **TGN − baseline** |
|---|---|---|---|---|
| TGN vs GraphSAGE | 1 | 0.7143 | 0.7285 | **−0.0142** |
| TGN vs GraphSAGE | 3 | 0.7164 | 0.7293 | **−0.0128** |
| TGN vs GraphSAGE | 5 | 0.7110 | 0.7342 | **−0.0232** |
| TGN vs MLP | 1 | 0.7143 | 0.7645 | **−0.0502** |
| TGN vs MLP | 3 | 0.7164 | 0.7626 | **−0.0462** |
| TGN vs MLP | 5 | 0.7110 | 0.7644 | **−0.0534** |

**TGN is below both baselines at every Δ, on the metric that is not contaminated
by entry timing.** The sign is consistent and the gap to the MLP is the larger of
the two. Since the plan's premise is that the temporal GNN should *lead*, this is
a negative result, and per this project's rules a negative result is the result —
it is reported as such rather than replaced by the pooled column, which is the
larger number for every arm.

Two caveats that keep the negative result from being over-read, both flagged by
the tools rather than by me:

- **The checkpoint was selected on the POOLED validation AUC (logged as G-72).**
  So the within-t0 cell is *not* the best-of-epochs for its own metric — it is
  the best-of-epochs for a different one. Arm-vs-arm on within-t0 is therefore
  mildly adversarial to whichever arm benefits most from the calendar, which §5
  shows is the TGN (36.6% at Δ = 5, the highest in the table). **The loss may be
  partly an artefact of mismatched selection.** Re-selecting on within-t0 val AUC
  would settle it; that has not been run.
- **The control's within-t0 band does not exist in this artefact**
  (`_tools/75_E5p_verify.py` reports it as "NOT IN THE RECORD" at all three Δ,
  and `76_E5p_null_band.py` exits with "NO within-t0 block on the control —
  nothing to derive from … a statement about the RECORD, not the science"). So
  **whether a 0.014–0.023 gap exceeds the control's own sampling spread is
  unknown**: the band that would answer it cannot be derived from what was
  written. The differences may or may not be real; the record does not say.

The minimal change that would unblock all of this is small and worth naming: the
control is scored by `test_auc_by_delta` only, while the arms go through
`eval_block` and get a full `within_t0_auc` with `per_bin`. **Running the control
through the same `eval_block` call it already has the scores for** would populate
the missing reading, and only then can `76_` derive the band.

---

## 6. Verdict and limitations

**Is the plan's E5 satisfied? No.** Plainly: the experiment the plan names has
now been *run to completion* — three arms, three Δ, held-out address split,
bootstrapped CIs — and **its results are not admissible**, because the run's own
pre-registered leakage criteria failed in two places, one of which (§1 failure b)
directly undermines the comparison. A completed run with a failed control is a
negative result, and it is reported as one. What has changed since
`05_E5fin_recurrence.md` is that this is no longer a *gap*: the code exists, the
run exists, the numbers exist, and the reason they cannot be used is measured
rather than unknown.

**Verdict per claim:**

| claim | verdict |
|---|---|
| The temporal GNN (TGN) outperforms GraphSAGE | **NOT ESTABLISHED — and the sign is against it.** GraphSAGE is higher at every Δ (0.8037/0.8212/0.8397 vs 0.7963/0.8140/0.8328). No Δ separates them by more than the CI widths, so the honest reading is "no difference measured", but there is no reading in which TGN wins. |
| A graph arm outperforms the feature-only MLP | **NOT ESTABLISHED — the sign is against it.** The MLP wins at every Δ by 0.029–0.043, outside the CIs. |
| The plan's fallback ("降级为 GraphSAGE + 手工时序特征") is licensed | **NO — and it would have fired on an artefact.** See §4: the fallback triggers when the GNN "improves little" over the feature baseline, and against the plan's *literal* baseline (AUC ≈ 1.0, §4(i)) it fires on a leak. |
| These AUCs measure persistence prediction | **NOT ESTABLISHED.** A model trained on **permuted labels** matches or beats both graph arms (§4). |
| The feature matrix is causal (`step ≤ t0` only) | **NOT ESTABLISHED.** 294/300 exact; the 6 exceptions are all `c_self_loops`, whose verifier channel reads 0 by construction (§1). Four of five compared feature families verified exactly, but that is not the same as the fifth being verified. |
| The provided table leaks (§4(i)) | **ESTABLISHED.** AUC = 1.0 / 0.9999999975 / 0.9999997343 on a full-population split. This is the one result here that is robust, because it is a *control* whose purpose is to succeed: the pipeline can see the answer when handed it. |
| Accuracy is uninformative here | **ESTABLISHED.** Every arm is below the degenerate "never recurs" baseline at every Δ. |

### Limitations, stated plainly

**The two that decide whether any number here may be quoted:**

1. **The two failed controls are the headline limitation**, and they are limits on
   *this report*, not on the dataset. Until the shuffled control is either fixed
   or shown to be mis-specified, **no arm's AUC in this report should be quoted as
   a persistence-prediction result** — including the MLP's, even though it is the
   one arm that beats the control. The MLP's margin is real; that the *task* is
   being measured is not.
2. **The run wrote its artefact only at the very end.** An earlier attempt
   trained all three arms for ~49 minutes and then died `rc=1` inside the final
   verification step, taking every trained result with it because nothing was
   persisted incrementally. The numbers are reproducible (the relaunched run
   reproduced the crashed run's GraphSAGE and TGN trajectories to the last
   displayed digit), but that is a **reproducibility** witness, not a
   correctness one: same code, same seeds, same data *should* agree. The
   engineering lesson is separate and real: **write the arms' results as each arm
   finishes.**

### Other limitations

1. **The epoch budget is a real constraint, and the cost figures that set it were
   measured under CPU contention.** `--epochs 6` came from `53c`'s
   "GraphSAGE 328 s/epoch" and "TGN 2.51 s/step", but the competing E9 OCR job
   was holding 6 of 14 vCPUs throughout `53c`. **The post-contention reality is
   ~5.6× cheaper**: uncontended MLP epochs fell from 15–40 s to **2.0 s**, and
   the full-scale GraphSAGE epoch ran at **132–190 s**, not 328 s. So the budget
   was chosen from an upper bound — which is why the run was affordable at all
   (2,667 s total, not the ~2 h extrapolated), and also why "were the GNN arms
   under-trained?" is **not** answerable by dismissing the budget: at Δ = 5
   GraphSAGE's val AUC was still rising (0.7878 → 0.8067 → 0.8171 at epochs
   2/4/6) when training stopped, so **the GNN arms had not converged**. That
   cuts against the GNN arms being *disadvantaged*, though: they are beaten by a
   control that had only 5 epochs (§1), so more training is not obviously the fix.
   Early stopping on val AUC with best-state restore means the reported model is
   the best validation epoch, not the last.
   *Cost rows in `53c` are labelled honestly: the `full_dedup_off` and
   `dedup_allnodes` rows are node-set matched; the `dedup_cohortnodes` row is
   **not comparable** to them and is not used.*
2. **Δ ∈ {1, 3, 5} only.** Beyond Δ = 5 censoring exceeds 10% and, at Δ = 20,
   42%. The table is reported to Δ = 20 so the reader can see why the
   pre-registered range stops where it does.
3. **The leakage verification is a 300-address sample** (see §1). It filters
   systematic error; it does not prove totality.
4. **`c_distinct_out`/`c_distinct_in` are sums of per-step distinct counts**, not
   true cumulative distinct counts. Stated because the two differ.
5. **Unknown-class addresses are in the population and in the graph** but carry
   no label of their own; they are included because the survival label is
   defined for them and because their presence is informative to their
   neighbours. The class-1/2 subset is reported separately for comparability
   with `05_`.
6. **The TGN/SAGE readout at t0 for an isolated address** falls back to the arm-2
   tabular features; such addresses are not dropped, and their count is in the
   JSON (`population_missing_cell`).

---

## 7. Corrections logged

Corrections to *records* — including one of my own, one the ledger carries, and
two pieces of advice I was given and did **not** adopt. Each is recorded rather
than quietly applied, because a ledger that is silently repaired is not a ledger.

**(a) `C-115④` records 53b's death as "死因未观测". That is wrong — I killed
it.** `53b_tgn_smoke.py` was started, produced no output for ~19 minutes, and I
terminated it with `pkill -f 53b_tgn_smoke.py`. The evidence that was read as
"died silently" is exactly the evidence for "was alive and busy": a 0-byte log,
793 s of user CPU, 5.4 GB RSS, and a print-at-the-end design that had not yet
been reached. The cause was my kill, not an unexplained death. **53b is cited as
evidence for nothing in this report** — it is excluded on the merits (it never
reached its first output line), not because it died. What replaced it is `53c`
(timed, per-variant, printing) and `53d` (assertions at tiny scale), both of
which produced readings.

**(b) The `--quick` run was reported dead while it was alive.** Its log was
inspected with `pgrep`, which returned nothing, and the conclusion drawn was that
the process had gone. `ps -eo pid,cmd` and a `/proc` scan both showed it alive at
3.15 GB RSS with cgroup `oom_kill` 0 and 59 GB free. **I then terminated it
deliberately** with SIGTERM, which is why the log's real ending is `Terminated` /
`RSC_EXIT=143` and not a crash. The kill was legitimate (the run had already
answered the question it was launched for); the *finding of death* was not. The
hypothesis built on top of that false finding has since been withdrawn.

**(c) Two instruments agreeing is not two witnesses — retracted claim.** The
`53c` cost-envelope variants were described as producing "bit-identical
gradients". They do not: at step 49 all three parameter groups diverge (gru
1.2111e-2 vs 1.2212e-2, time_enc 1.802e-4 vs 1.895e-4, head 3.4729e-2 vs
3.4536e-2). That claim is dropped from this report; §6/§8 report **measured
times** only. This is the project's standing rule about proxy measurements
arriving in a new costume: the two runs shared a blind spot (same seed, same
shape of computation), so their agreement carried no information about
equivalence.

**(d) Advised "use cohort scoping" — not adopted, and the advice is retracted.**
Restricting the graph to class-{1,2} nodes is *smaller*, not *faster
implementation*: events/step fall 57,612 → 22,535 and distinct nodes/step
18,790 → 5,517. It would have silently changed **what the model can see** — the
class-3 majority of counterparties would vanish from every neighbourhood — while
being reported as a performance optimisation. `53_E5p_temporal_gnn.py` does not
do this: full 822,942-node population, deduplicated `(src, dst, step)` edges,
5,602,818 undirected. **That is kept as is.** The cost table in this report
labels the rows honestly: the `full_dedup_off` and `dedup_allnodes` rows are
node-set matched; the `dedup_cohortnodes` row is **not comparable** to them and is
labelled so wherever it appears.

**(e) My own instrument had no positive control.** The first version of the
column-variance check excluded `Time step` *by name*, so
`columns_varying_within_address` was empty **by construction** and the instrument
could not have returned a nonzero value on any input. A 0-of-55 result from an
instrument that cannot return anything else is not evidence about the file.
Fixed by adding `Time step` as a positive control, where it returns 1.0000 on
multi-step addresses; the 0-of-55 reading is licensed by that and not by the
first version. The general form: **a check whose answer is fixed by its own
construction is not a check.**

**(f) WITHDRAWN — I reported a discrepancy that did not exist.** An earlier draft
of this section claimed Δ = 1's excluded count was "3 addresses off" the
independent reference. It is not: the measured count is **11,673**, exactly the
reference value, and all five Δ agree exactly. I had *inferred* an integer from a
**rounded share** (0.01418 → 11,670) and reported the difference between my
inference and the reference as a property of the data. **The inference was never
a measurement**, and reporting it as one is the same error the project keeps
re-finding: a derived estimate quoted with the confidence of an observation. The
share was right; the count I computed from it was not measured at all. Withdrawn
in full — see §2, which carries the real integers.

**(g) The completed run's artefacts were renamed out from under this report, and
that is recorded rather than normalised.** The run finished `RSC_EXIT=0` and
wrote `/root/cis/results/53_E5p_result.{json,txt}`. By the time I pulled them,
both had been renamed to `53_E5p_result.oldwriter_55d7d8f8.{json,txt}` — a
suffix **not chosen by me**, whose meaning I did not establish. I pulled the
`.txt` in the window before the rename and the `.json` after, which is why the
first pull of the `.json` failed with "No such file or directory" while the
`.txt` succeeded; the failure was a **race with a rename**, not a missing file,
and it briefly looked like data loss. Two things follow. First, the `55d7d8f8`
token is **not** the writer script's hash — the script is `1ebf15e85fe73026…`,
byte-identical on pod and local — so it is somebody else's identifier and this
report does not interpret it. Second, the deliverable path
`results/53_E5p_result.json` **does not exist**; what exists is the renamed file,
and the report says so rather than quietly pulling it under the expected name and
letting the filename imply an endorsement I cannot vouch for.

---

## 8. Instrument findings worth carrying forward

- **`pgrep -f` is not a liveness instrument in this container, and it fails in
  two different ways.** (i) A controlled test on a known-live `sleep 120`
  returned nothing at all, while `ps -eo pid,cmd` and a `/proc` scan both saw
  it — so it can miss a live process entirely (this produced the false "the job
  died" reading on the `--quick` run). (ii) It can also **succeed and identify
  the wrong process**: the `bg` launcher wraps the job as
  `bash -lc ': > log; cd /root && setsid nohup bash -c "( python ... )"'`, so
  three pids share the script's name in their cmdline — wrapper `bash -lc`
  (30821), inner `bash -c` (30822), worker `python` (30823). `pgrep -f
  '53_E5p_temporal_gnn.py' | head -1` returns **30821**, the outermost wrapper.
  `head -1` takes the lowest pid and the lowest pid is the least useful one.
  **Judge liveness with `ps -eo pid,args` and select the `python` line**, or read
  `/proc/<pid>/stat`. Two failure modes — silence and a confident wrong answer —
  from one instrument, and the second is the more dangerous because it looks
  like a reading.
- **`ps -eo etimes,pcpu` also returns 0 here, for every process.** `ps` in this
  container populates `cmd` and `rss` correctly but leaves `etimes`/`pcpu` at
  0 — including for PID 1. So `ps` is usable for *existence and command line*
  and **not** for elapsed time or CPU share; the `0` is the column being absent,
  not the process being idle. Elapsed time must come from the job's own
  progress prints, which is why every `53_*` script prints `[53 <elapsed>s]` on
  every line. A sentinel that reads `0.0` for both "no CPU used" and "column
  unavailable" is the same failure shape the ledger already records for
  `cuDeviceGetCount` returning `0`.
- **A long job's log is not evidence about the job unless it says so.** The
  `--quick` run's log went quiet for 330 s during GraphSAGE epoch 1 because a
  single epoch is one print. Progress lines are per-epoch for a reason; a quiet
  log is a quiet log, not a death.
- **Two instruments agreeing is not two witnesses.** The dedup/no-dedup variants
  in `53c` were first described as producing "bit-identical gradients"; they do
  not — step-49 values diverge in every group. That inference was retracted
  before it reached this report. What `53c` establishes is a **cost** ranking;
  it establishes nothing about equivalence.
- **`ps -eo etimes` / `%CPU` / `pgrep` and the `-c` backslash trap, in one
  session**: the same session produced four separate instruments that report a
  confident value unrelated to the question — `pgrep` (silence, or the wrapper's
  pid), `ps`'s elapsed/CPU columns (always `0`), and the local `-c` flag eating a
  layer of backslashes so that `r'D:\CIS\_tools\'` is a syntax error rather than
  a path. The common shape is that the *instrument's* failure mode and the
  *object's* state share a representation. For any probe that reports a scalar,
  ask what value it reports when it has not run at all.
- **A criterion can be on the wrong metric and still be "pre-registered".** The
  shuffled-label control was judged on the **pooled** AUC, where a strong
  calendar component (§5: 24–37% of the excess) sits above 0.5 for reasons that
  have nothing to do with labels. Judging it there makes the criterion fail for a
  reason that is itself a property of the design. `75_`/`76_` move the criterion
  to within-t0, where 0.5 is the null *by construction* — the right scale. **The
  lesson is not "the control was too strict" but "a null band must be derived on
  the metric the claim is made on."** Note the failed control and the missing
  band are two different problems: the pooled reading was the wrong scale *and*
  the within-t0 reading was never recorded.

---

## 9. Review note added after coordinator review (2026-09-24) — the header
## overstates, and two of this report's own decompositions disagree

Everything in the body stands. Two things should be read together with it.

**(a) The header's inference rests on the pooled column.** "Most of the arms'
apparent skill is not attributable to label-driven learning" is drawn from
control-pooled vs arm-pooled. §5 is explicit that those arms' pooled numbers
contain a large entry-timing component and that the control has **no** within-t0
reading. So the header's conclusion is licensed for the *pooled* metric and for
nothing else — and the pre-registered criterion it invokes
(`shuffled_control_at_chance`) is itself evaluated on `test_auc_by_delta`, the
pooled column, by the writer that produced this artefact.

The pooled column is the one that cannot separate the two hypotheses. Measured
here: across the 44 t0 bins at Δ=5 the positive rate spans 0.00152 → 0.18824, a
**124×** range. A scorer that reports only *which bin it is in* therefore clears
0.5 on the pooled metric with no label information whatever. Because a
whole-set label permutation preserves each bin's positive rate by the law of
large numbers, a model trained on permuted labels can learn exactly that and
score 0.81–0.84 pooled. On that reading the control's pooled 0.81 is the
**expected consequence of the t0 channel**, not evidence of leakage — which is
precisely why the fixed writer moves `shuffled_control_at_chance` onto the
within-t0 column. (Mechanism stated as a prediction; the run below tests it.)

**(b) §5 and the header decompose the same number two different ways and do not
reconcile.** §5 reports the calendar share of the excess as 23.6–36.6%, which
leaves 63–76% *label-driven*. The header reports that a no-label control matches
or beats the arms pooled, which leaves ~0%. Both cannot be read as stated. The
difference is that §5's share is computed against the arms' **within-t0** value,
while the control's 0.81 is on the **pooled** scale — the two decompositions use
different baselines. This report does not resolve which is the meaningful split,
and the missing measurement is again the thing that would.

**Neither reading changes the negative arm-vs-arm result of §5**, which is on the
within-t0 metric where all three arms share the same selection caveat.

**Remedy already running.** The coordinator relaunched E5p on 2026-09-24T03:34:54Z
(pid 36327) with the **fixed writer** (`1ebf15e85fe73026`, pod and local
byte-identical), which scores the control through `eval_block` and gives it a
`within_t0_auc` — the minimal change §5 names. If the control's within-t0 lands
near 0.5 while the arms sit at ~0.71–0.77, the header's conclusion is falsified;
if it lands near 0.7, it is confirmed. That is a decidable reading, not another
guess. Ledger: **C-160** in `pipeline_reports/progress.md`.

### §9(a) CORRECTED — the t0 channel does NOT explain the control. The residual is measurable.

§9(a) above concluded that the control's pooled 0.81–0.84 "is the **expected
consequence of the t0 channel**, not evidence of leakage". **That conclusion is
withdrawn.** The direction was right — most of the control's excess over 0.5 is
entry timing — but it was treated as the whole of it, and it is not.

The ceiling of the t0 channel is computable exactly. A scorer that is constant
within each t0 bin cannot beat one that returns the bin's own positive rate, and
that scorer's pooled AUC follows from `per_bin` alone. Computed two independent
ways (closed form over pairwise counts, and by constructing the implied
population and ranking it — they agree to 0.00e+00):

| Δ | channel ceiling | control pooled | residual | share of excess |
|---|---|---|---|---|
| 1 | 0.7195 | 0.810667 | **+0.0911** | 70.7% |
| 3 | 0.7539 | 0.825428 | **+0.0716** | 78.0% |
| 5 | 0.7723 | 0.839269 | **+0.0670** | 80.3% |

**The residual is positive at every Δ.** The channel explains 70–80% of the
control's excess over chance, but the control scores *above* the ceiling, so its
scores are **not** constant within bins — hence its within-t0 AUC must be
measurably above 0.5.

**This yields a consistency check the rerun can be held to.** Since
pooled ≤ ceiling for any within-bin-constant scorer, the pair
**[SUPERSEDED — REFUTED, see §9(e)]** (pooled ≈ 0.84, within-t0 ≈ 0.5) is **arithmetically impossible from one run**.
If the fixed writer reports that pair, it is a writer defect, not a finding. If
its control's within-t0 lands near 0.5, its pooled must come in at or below
~0.77 — the two readings have to move together.

Note also that §9(a)'s stated mechanism was unsupported on its own terms: a
global label permutation makes labels independent of t0, so a permuted-label
model cannot learn `rate(bin)` at all; it can learn only the global rate, which
scores 0.5 pooled. Whatever produces 0.81–0.84 is therefore not simply the
channel. Candidate explanations remain unmeasured — the writer's own comment at
lines 1036–1059 attributes the old control's monotone rise on *true* validation
AUC (0.79579 → 0.83927, training on pure noise) to checkpoint selection on true
validation labels, and blinds selection for that reason. That is a second
channel, distinct from the calendar, and the rerun changed exactly it — so the
rerun is **not** re-measuring the same quantity.

**How this error was caught.** The ceiling was first computed with a closed form
that summed the wrong element of a `(nneg, npos)` tuple, making the denominator
`sum(nneg) − sum(npos)` — 93,597 instead of 105,093 at Δ=5 — which inflated the
ceiling by +0.045, enough to reverse the sign of the residual. It was found only
because a second implementation was built from the population rather than from
the algebra and the two **disagreed**. The lesson is not "check your arithmetic":
it is that an independent instrument is only worth having if it is allowed to
disagree, and if its disagreement is treated as locating the error rather than
as noise to be reconciled away. Ledger: **C-162**.

**Boundary, carried from the peer who computed this:** the old artefact records
no `n` for the control, so the control's test population cannot be confirmed to
be the arms' (123,442 addresses; Δ=5 eligible 110,841). The three **arms** were
verified to share one population exactly (`n` and `n_pos` identical across arms
at every Δ), so the arm-vs-arm negative result of §5 is untouched by any of
this. If the control's population differed, the ceiling must be re-derived from
the rerun, which will carry `n`.

### §9(b) — three corrections to §9(a). All three verified at source, not transcribed.

§9(a) above carried a number and a mechanism that do not survive checking against
the files. Both are corrected here; the *direction* of §9(a) is unaffected.

**(i) The number is wrong. I read it out of a comment and recorded it as a
measurement.** §9(a) says the writer's comment "attributes the old control's
monotone rise on *true* validation AUC (0.79579 → 0.83927, training on pure
noise)". The comment is real — `_server/53_E5p_temporal_gnn.py:1044`, within the
cited range — and it does say `(0.79579 -> 0.83927)`. But **0.83927 is not a
validation-trajectory endpoint.** The delivered run's own log
(`_logs/53_full_rc1_20260924.log`) prints the shuffled control's per-epoch val AUC
as

    0.79579  0.80195  0.80686  0.80921  0.81379

and the *next* line of the same log is
`shufctl {'1': 0.8106673045844783, '3': 0.8254282453923566, '5': 0.8392686039334707}`.
0.83927 is the **Δ=5 test AUC**. A test reading was quoted as the endpoint of a
validation trajectory, in the writer's comment, and I carried it into the record
without opening the log. The endpoint is **0.81379**; the claim is wrong by
+0.0255. (The direction survives: the five points are strictly increasing. The
comment's range is 1038–1059, number at 1044; §9(a)'s "1036–1059" was approximate.)

**(ii) The mechanism does not cover the effect.** §9(a) repeated the comment's
attribution of the rise to checkpoint selection on true validation labels.
**Selection cannot move that trajectory.** `val_auc_mean` is computed and printed
every epoch regardless of which checkpoint is later retained (the log shows both
`leakctl ep1..ep10` and `shufctl ep1..ep5` as per-epoch series). Selection
determines which checkpoint is kept; it cannot make a noise-trained model's
progressive ranking of *true* val labels better epoch over epoch. The attribution
is not evidence and is withdrawn as an explanation.

**(iii) What is left, and it is the more interesting statement.** The control's
**epoch-1** val AUC is **0.79579** — already the mean over the 3 Δ heads — after
one epoch trained on nothing but permuted labels. The mean-over-heads calendar
ceiling is (0.7195 + 0.7539 + 0.7723)/3 = **0.7486**. The control sits **above
the ceiling at epoch 1**, before label content could plausibly act. So the channel
that lifts the control above the calendar is the 14 point-in-time features and the
model class — **not the calendar, and not selection.** The residual cause of
§9(a)'s +0.067 is therefore not established as selection either; the honest
position is the feature/model channel, which is legitimate for the arms and does
not rescue the control.

**Caveat, carried and not closed:** `per_bin` is test-only, so the ceiling cannot
be computed on the validation split. 0.7486 is a test figure compared against a
val reading. The splits are the same size order and drawn the same way (val
123,441 / test 123,442), but this is a cross-split comparison and is flagged as
one rather than presented as like-for-like.

**(iv) One boundary of §9(a) is retired.** §9(a) hedged that if the control's
population differed from the arms', the ceiling must be re-derived. **Retired.**
The writer lineage that produced the artefact
(`output/cis_sprint_20260924/code/_server/53_E5p_temporal_gnn.py`, sha
a45ef6880338, 1,470 lines — traceback lines 615 and 1470 match the crashed run
exactly) scores the control as
`auc(Y[te_m & OK[:, k], k], sh["scores"][te_m & OK[:, k], k])` — `te_m`, the
**test** split, true labels. The control and the arms share one population, so the
ceiling applies unconditionally. (The three **arms** were already verified to
share one population exactly.)

**(v) A filename I got wrong.** C-162 §⑤ names the tool `_tools/ceiling_check.py`.
The file is `_tools/_ceiling_check.py` — **leading underscore**; all four siblings
are underscore-prefixed (`_ceiling_check.py` 3,778 B, `_ceiling_both.py`,
`_ceiling_debug.py`, `_ceiling_rank_check.py`). This is G-62's shape again: an
existence claim recorded from an expected name. It was caught by the peer only
after a **name-based** search returned a false negative on both disk and pod, and
a **content** search (`*ceiling*`) found it. A name-based search produces false
negatives as readily as false positives.

**(vi) What this predicts for the rerun, stated before the reading exists.**
**[SUPERSEDED — REFUTED, see §9(e)]** Because pooled ≥ 0.80 with within-t0 = 0.5 is arithmetically impossible (no
within-bin-constant scorer can exceed 0.7723 at Δ=5), the fixed control's
within-t0 is expected to land **materially above 0.5, not near it**. Blinding
selection removes checkpoint-choice bias; it does not touch the epoch-1 floor. So:

  * within-t0 materially above 0.5 with pooled ~0.80–0.84 ⇒ the criterion
    `shuffled_control_at_chance` **fails again**, and the cause is the feature/model
    channel — not the calendar, not selection. §9(a)'s "the channel explains it"
    stays dead.
**[SUPERSEDED — REFUTED, see §9(e)]**   * (within-t0 ≈ 0.5, pooled ≈ 0.80–0.84) from one run ⇒ **writer defect, not a
    result.** Do not report it as a finding.

**How (i) was caught, and why it is the repeatable part.** Not by re-reading my own
text — the text was self-consistent. It was caught because someone opened the log
the numbers came from. §9(a) is a case of the library's 21st face: *I cited a
number I had read in a comment as though I had measured it.* A comment is a claim
about a measurement; it is not the measurement. The log is the measurement.

### §9(c) — the landing had two gaps, both closed before the artefact exists (C-169)

Recorded here because both are about **which object a name refers to**, which is
this report's recurring failure mode, and both were found and fixed while the
rerun was still training — before any landing could act on them.

**(i) A stale object sat under the live local name.** The writer writes the text
report at `:1588` and logs **no** `wrote` line for it, so the landing's
run-completion gate — which requires `wrote <path>` in the log — cannot reach the
text report at all. Meanwhile `results/53_E5p_result.txt` locally held the **old**
run's text, byte-identical to the pod's preserved copy (`1831495aff6b50c2…`). It
was renamed to `53_E5p_result.oldwriter_55d7d8f8.txt`, sha checked before and
after. The landing now archives and pulls the `.txt` as well, and binds it to the
JSON **by content**, not by transport: `runtime` must equal
`round(seconds_total, 1)`, and the text report's `summary: {...}` block must
**equal** the JSON's `leakage_check.summary` as a dict. Both relations were
measured on the old pair, the one pair written by a single process. A stale text
report fails the second relation.

**(ii) The archive and the driver's evidence check were two different names.**
`run_pipeline.py:66` gates E5 on `ev=["results/53_E5p_result.json"]` — the
canonical local name — while the landing pulled only to the writer-derived
archive name. Archiving alone would leave the driver reading a path that does not
exist. The landing now also places both objects at the canonical names, under the
same decide-before-touch rule: identical bytes are a no-op, different bytes
refuse. Both the archive guard (three branches, inode as the witness that no copy
happened — `cp -p` preserves mtime, so mtime cannot witness it) and the canonical
placement (three branches, including the refusal) were exercised, not merely
asserted.

**Unchanged predictions, restated so the landing is read against them.** On
landing, `81_e5p_landing_check.py --prediction fixedwriter` is expected to report
**zero GAP lines** and `feature_filter_verification_exact` is expected to be
**[SUPERSEDED — REFUTED, see §9(e)]** **True**; and (within-t0 ≈ 0.5 with pooled ≈ 0.80–0.84) remains arithmetically
impossible, so if it appears it is a writer defect and not a finding.

### §9(d) — §9(c)'s predictions, sharpened before the reading (C-170)

§9(c) closed with three predictions. Two of them are not the same kind of claim,
and the fix recorded in §9(c) is what makes the difference matter: with the
control's within-t0 column present, the six clearance readings stop being **absent
from the record** and start being **evaluated**. An evaluated check can fail on
its own merits, which is a different outcome from a missing reading.

Four outcomes, pre-registered (the ledger entry is C-170, written before the
artefact exists):

| # | GAP lines | FAIL lines | what it means |
|---|---|---|---|
| a | 0 | 0 | the hoped landing |
| b | 0 | a clearance check (`arm − ctl ≥ 0.05`) fails | **a finding about the experiment** — the arm does not clear its control by the margin. Not a landing defect, and not evidence the fix is broken |
| c | 0 | the chance check (`abs(ctl − 0.5) < 0.05`) fails | **a finding about the control channel** |
| d | ≥1 | — | the writer still is not emitting that reading (record incompleteness) |

So `81_`'s exit code 2 — "a genuine finding, GAP set matches" — is, in this
landing, most likely (b) or (c), **not** "the landing failed". That is the same
correction we made once already, in the other direction, when codes 4/5/2 were
being read as scientific failure.

**One scope note on §9(c)'s "arithmetically impossible" line.** It is about the
**control's own two columns**: pooled ≈ 0.80–0.84 while within-t0 ≈ 0.5. Its whole
load is the measured calendar ceiling (0.7195 / 0.7539 / 0.7723 at Δ=1/3/5), which
0.84 exceeds — so t0 alone cannot account for it. The predicate that licenses the
*arms*, however, is the **margin**, with the control near chance as the ideal
rather than the requirement: a control returning, say, 0.70 against arms at 0.76 is
not arithmetically contradictory, and the margin decides. That is a weaker but
real result, and it must not be reported as a writer defect — a defect is
established only when the two columns contradict **within one run**. The ceiling
comes from the **test**-split `per_bin` table, and the artefact carries no
validation bin table, so any cross-split use of it has to say so.

### §9(e) — ★★THE "ARITHMETICALLY IMPOSSIBLE" CLAIM IS REFUTED. The inference, not just the number. (C-172)

Four sites above now carry a `[SUPERSEDED — REFUTED]` marker: `:859`, `:964-966`,
`:973`, `:1015-1016`. The text is unchanged; the markers are inline so no line
number moved and a reader who lands mid-section sees the warning at the claim.
This section is what they point to.

**What was wrong was not the ceiling. It was the step after it.** The ceiling —
0.7195 / 0.7539 / 0.7723 — is the maximum pooled AUC attainable by a score that is
a **function of t0 alone**, i.e. constant within each bin with bins ordered by
positive rate. That much stands, and two independent implementations agree on it.

The invalid step is `:964-966`, which says the quiet part out loud: "no
within-bin-**constant** scorer can exceed 0.7723 at Δ=5", therefore the control's
within-t0 "is expected to land materially above 0.5". That equivocates between
**having variation within a bin** and **discriminating within a bin**. Variation
is necessary for within-bin discrimination; it is not sufficient, because the same
variation can instead order **cross-bin** pairs — and cross-bin pairs are the
large majority of all pairs. The ceiling bounds the t0-only family, not the family
with any given within-bin AUC.

**Refuted by exhaustive enumeration, not by argument** (`_tools/_refute_ceiling.py`;
integer scorings, ties allowed since `auc` is `roc_auc_score` and ties are exactly
how a within-bin-constant score reaches 0.5; restrict to assignments whose
within-bin AUC is **exactly 0.5 in every bin**, then maximise pooled):

| bins (p1,q1,p2,q2) | rates | ceiling | max pooled at within-AUC ≡ 0.5 **over the searched grid** (L=4; a LOWER bound — see below) |
|---|---|---|---|
| (2,2,1,3) | .50 / .25 | 0.633333 | **0.700000** |
| **(2,2,2,2)** | **.50 / .50** | **0.500000** | **0.625000** |
| (3,1,1,3) | .75 / .25 | 0.750000 | 0.750000 |
| (2,3,1,4) | .40 / .20 | 0.619048 | **0.666667** |
| (1,2,1,3) | .33 / .25 | 0.550000 | **0.650000** |

Four of five exceed the ceiling at **zero** within-bin skill. The cleanest case is
two bins with **equal** positive rates: the ceiling is 0.500 and a score with
within-bin AUC exactly 0.5 in both bins reaches pooled **0.625**.

**★AMENDMENT (C-177, same day): "max" above means max OVER THE SEARCHED GRID, and
the sup is not reached.** For (2,2,2,2) the value is 0.5625 / 0.625 / 0.65625 /
**0.6875** at L = 3 / 4 / 5 / 6 — still rising, so **0.625 is a witnessed lower
bound, not a maximum**, and the same caveat the (3,1,1,3) row earned ("not found
at this resolution") applies to every row including that one. The refutation is
unaffected — **one witness suffices, and 0.5625 at L=3 already exceeds the 0.500
ceiling** — but the label over-claimed, and a label is what a reader who does not
re-run the search carries away. The identity bounds it: for equal-rate bins
`pooled = (1 + P12 + P21)/4 <= 0.75`. **The peer's general form,
`pooled = [0.5(q1^2+q2^2) + q1*q2*(P12+P21)]/(q1+q2)^2` for `p_i = lam*q_i`, is
verified to 0.0e+00 over 6 configs / 131,622 witnesses at `lam != 1`** — at lam=1
it forces p=q, so the equal-size family is all it could ever have exercised.

**★★SECOND AMENDMENT (C-180): 上表里的数不是「下界」，是**已证的上确界**。**

**覆盖论证（同侪提出，我独立实现并验证）**：`auc` 只看成对的 `>`/`==`/`<`。
把每个取值换成**它在现存不同值中的排名**，三个 AUC 全不变，
`within-AUC ≡ 0.5` 的约束也不变 ⇒ **任何实数赋值都可投影进 (L=n) 格点**，故

> **(L=n) 格点上的最大值 =（全实数评分上的）上确界。**

**实现为 `_tools/_sup_weakorder.py`**（枚举**弱序**＝有序集划分），
**并自证枚举量**：叶数必须**逐位等于** `Σ_k k!·S(n,k) = Fubini(n)`
（n=4/6/8 实测 75 / 4683 / 545835 全对）。

| bins (p,q,p,q) | n | Fubini(n) | t0 上限 | **精确上确界** | 判定 |
|---|---|---|---|---|---|
| (2,2,1,3) | 8 | 545,835 | 0.633333 | **0.700000** | **超** |
| **(2,2,2,2)** | 8 | 545,835 | 0.500000 | **0.687500 = 11/16** | **超** |
| (3,1,1,3) | 8 | 545,835 | 0.750000 | **0.750000** | **不超（＝上限）** |
| (2,3,1,4) | 10 | 102,247,563 | 0.619048 | 未计算 | 见下 |
| (1,2,1,3) | 7 | 47,293 | 0.550000 | **0.650000** | **超** |
| (1,1,3,3) | 8 | 545,835 | 0.500000 | **0.562500 = 9/16** | **超** |

**三个结论：**

1. **五个可算配置上，精确上确界逐位等于格点最大值**
   ⇒ **C-177 里我改对了数值，缺的只是「叫它上确界」的资格**，而那资格**是证出来的，不是假定的**。
2. **★下界上升为上确界后，我 C-177 §② 那句话彻底倒了**：`(1,1,3,3)` 在**穷举枚举下仍为 0.5625**
   ⇒ 平台**是结构性的**，不是网格限制。同侪对此给了**证明**（`P12+P21 ≤ 4/3`）。
3. **★`(3,1,1,3)` 的精确上确界 = 0.750000 = 它自己的上限**
   ⇒ **在那一个配置上，「池化 > 上限」仍然能定罪**（同侪 item 4）。
   **⇒ 正确的边界是「上确界 = f(观测到的 within-AUC)」一个函数，不是一个阈值。**

**(2,3,1,4) 的上确界未计算**（Fubini(10)=102,247,563，超预算）——**不声称**。
**而它不需要**：同侪的见证给出 池化 = 2/3 > 0.619048，**一个见证就足以证伪**。

**★〔本段已作废 —— 见紧随其后的 C-182 更正〕一条关于本报告表格的同侪指控，已回源核实为误**：同侪 item 3 称我表中
`(2,3,1,4)` 在 L=4 列下印的是 `0.642857`。**实测我的该行：L=3 = 0.642857、**
**L=4 = 0.666667**，且同侪自己的见证（`pos1=[2,2], neg1=[3,2,0], pos2=[1], neg2=[1,1,1,1]`）
**在我的 `auc` 下逐位重现 14/21 = 0.666667**。⇒ **两人的数字全同，错的是列的归属**。
**此事已记入台账，不作平滑处理。**

---

**★★第三修正（C-182，2026-09-24）：上面那一段本身是错的 —— 同侪是对的。**

**我核的是我的 `工具`，而指控说的是上表。** 两句话都真，指的却是**两个不同的对象**：

| 对象 | L=3 | L=4 | 谁说的 |
|---|---|---|---|
| `_refute_ceiling.py` 打印的行 | 0.642857 | **0.666667** | 我的 §④ 引用的就是这个 |
| **上表（`:1079` 表头写的是「L=4」）的 `(2,3,1,4)` 格** | — | **印的是 `0.642857`** ← 即 **L=3 的值** | 同侪 item 3 指的就是这个，**他是对的** |

**⇒ 同侪指的不是「你的工具算出什么」，而是「你的表格印了什么」。我把工具读了一遍就宣布人家错，
等于用一件东西的读数去否证一句关于另一件东西的话。**

**独立重算**（`_tools/_settle_2314_cell.py`，**自己枚举，不引用任何一方的断言**）：

```
L=3: 59,049 assignments,    735 满足两箱 within-AUC 皆 = 0.5, max pooled = 0.642857
L=4: 1,048,576 assignments, 14,400 满足同约束,               max pooled = 0.666667
     我自己的 L=4 见证（与同侪的见证不同，同值）: [2,2,0,2,3,1,1,1,1,1]
```

**同侪见证逐位复现**：`[2,2,3,2,0,1,1,1,1,1]` ⇒ 箱内 AUC `0.500000 / 0.500000`，
**池化 `0.666667` = 14/21**，且**全部取值 ∈ {0,1,2,3} ⇒ 它落在任何 L ≥ 4 的格点内**。
**⇒ `0.642857` 不可能是该配置的 L=4 最大值，因为存在一个严格更大的、满足同一约束的格点。**

**处置**：上表该格**已就地改为 `0.666667`**（原值 `0.642857` 即 L=3 的值，此处留档）；
**错因与 [[artifact-existence-check-discipline]] ⑯／㉑ 同族** ——
**「核通过」要核它读的是哪个对象**；**我引用的是我对记录的转述，而转述不是证据**。
**这一段不删除，只标记作废**：一份把错误主张留着并标出「它错了」的记录，
比一份悄悄改干净的报告更有用。

**What this does to the landing, which is the point of writing it before the
artefact exists.** The pre-registered oracle — "(within-t0 ≈ 0.5, pooled ≈
0.80–0.84) from one run ⇒ writer defect, not a result" — is **withdrawn**. That
pair is not a contradiction. It is the **signature of a pooled AUC carried by t0
ordering**, which is precisely what the within-t0 fix exists to reveal, so if the
rerun produces it the reading is that *the fix works* — not that the writer is
broken. Reporting it as a defect would have been a false scientific claim
generated by my own tooling, and it was pre-registered in that direction.

**What survives, stated so it is not over-withdrawn.** The ceiling is still the
maximum for a t0-only score, so a positive residual still licenses exactly one
inference: **t0 alone cannot produce this pooled AUC.** What it does not license
is any bound on the within-bin AUC. `_ceiling_check.py`'s docstring and its
printed output said the stronger, invalid thing; both are now corrected, because
the runtime line was misleading in the same way the prose was.

**One consequence for the ruler's chance check.** `shuffled_control_at_chance` is
computed by the fixed writer from the **within-t0** column (`:1401-1404`), so a
`False` there is a reading about the control — the control retains within-bin
discrimination — and *not* a sign that two columns contradict each other. That is
why `81_`'s dismissal is now keyed by prediction (C-172 §4): the pooled-t0 reason
was true of the old writer's computation and is false of the new one.

**And the field that carries all of this is misnamed.** `within_t0_auc.weighted`
weights by **bin size** (`wts.append(int(m.sum()))`, `:471`); the weight that
actually closes `AUC_pooled = w·Ā + (1−w)·Ā_cross` is the **pair count**
`npi·nni`, which is reported nowhere. Recomputed independently from the old
artefact's `per_bin` (9/9 rows, not transcribed): the field equals the n-weighted
mean, `unweighted` equals the plain per-bin mean (max deviation 9.3e-07 —
`per_bin` stores `round(a,5)`, so that is rounding, not a mismatch), and the
pair-weighted mean differs from the field by **+0.0248 … +0.0414, same sign in
9/9**. The chance band is ±0.05. So the choice of weight can flip the verdict on a
reading being produced for the first time. Both weights should be emitted, both
named, and the paper should say which one §5 and the chance test use.

### §9(f) — 落地前预注册：`feature_filter_verification_exact`（C-173）

**为什么单开一节写它。** 这个量与 §9(a)–(e) 讨论的 within-t0 修法是**两回事**，
而 `run_pipeline.py` 的 `ev_require` **要求它为真**。若它仍为假，驱动器会把 E5p
判为 FAIL——**该 FAIL 与 within-t0 的六个 GAP 毫无关系**。不事先分开，
落地时会把一个**验证器缺陷**读成**泄漏证据**，或把「修法奏效」读成「整轮失败」。

**旧产物的读数（回源逐项，非转述）** —
`results/53_E5p_result.oldwriter_55d7d8f8.json`：

- `feature_filter_verification.n_mismatch = 6`（`n_compared = 300`，`n_exact_match = 294`）
- `first_mismatches` 6 条**全是同一列、同一方向**：`c_self_loops`
  stored `1.0` vs recomputed(`<= t0`) `0.0`
- `n_where_leq_differs_from_gt = 294`、`frac = 0.98` ⇒ **惰性对照不空**
- **★该 294 与 `n_exact_match` 的 294 数值相同**——见下面的③，这一点必须单独处理

**机制：★按「佐证」登记，不按「已测」登记。**
`_server/53_E5p_temporal_gnn.py:630-638` 的说明是**写入器自己的注释**，
即**一份自述**，不是测量：

> SELF-LOOPS ARE CAPTURED BEFORE THEY ARE FILTERED OUT. … on the filtered frame
> the conjunction is identically False, so `c_self_loops` recomputed as 0 for
> every address in the population — including the 8,707 that genuinely carry
> one (measured on the real join: 2,868,964 rows, 45,981 self-loop rows).
> The landed artefact's 6 non-exact rows were that defect and not a leak;
> for the five it recorded, the stored value equalled the count on this
> unfiltered join exactly.

**产出该产物的那一版写入器未被保存**，所以**注释里的机制无法由产物验证**。
产物能支持的是两件较弱的事：① 6 条失配**同列同向**（stored 1 / recomputed 0），
② 它们**集中在一列**。**⇒ 这与「重算侧在已过滤帧上做 `is_src & is_dst`、
该合取恒为假」一致，且排除泄漏；但不等于验证了该机制。**
**与 §9(a)、§9(i) 同一纪律：自述是待核断言，不是测量。**
（可核的是那条 join 的规模：本轮 rc4 日志自报
`n_join_rows 2868964, n_self_loop_rows 45981` —— 与注释中的两个数**逐位相同**。）

### ① 预言（在产物存在之前写下，可证伪、具体到四个读数）

| # | 量 | 预言 | 若不然，则 |
|---|---|---|---|
| P1 | `n_exact_match` | **294 → 300** | 修法未命中真因（真因在别处，须重查；**不得**改判为泄漏） |
| P2 | `n_mismatch` | **6 → 0** | 同上；且驱动器 `ev_require` 会硬判 E5p FAIL |
| P3 | `summary.feature_filter_verification_exact` | **False → True** | 同 P2 |
| **P4** | **`n_where_leq_differs_from_gt`** | **必须仍是 `294`，只准到 300 那一侧——见②** | 见② |

### ② ★P4 是 P1–P3 的守卫，且**旧值不可判**（同侪提出，我更正后采纳）

**先立一个否命题**：修法若让**重算侧不再工作**，两边都算 0 ⇒ `n_mismatch` 同样变 0。
**「相等」既可以是「修好了」，也可以是「都不算了」。** 所以 P2/P3 单独立不起来。

**但「≈0.98，不塌到 0」这个写法不够**：`n_where_leq_differs_from_gt = 294` 与
`n_exact_match = 294` **数值相同**，而**产物里没有存** `<= t0` 与 `> t0` 相异那一组的
**行身份**（只存了失配组的 `first_mismatches`）。**⇒ 从记录上无法区分**
「真值 294」与「该字段被接成了 `n_exact_match`」。`300` 也满足 `> 0`，
会被读成 `not_inert = True` 而**什么都没量**。

**⇒ 因此预注册的是「解耦」，不是一个区间：**

- `n_exact_match` **294 → 300**
- `n_mismatch` **6 → 0**
- **`n_where_leq_differs_from_gt` 必须仍为 294，不得变成 300**

**并附一条阳性对照要求**（写入器本轮的 checker 应能通过它）：
**喂给该检查一行「已知在 `<= t0` 与 `> t0` 两帧上相异」的样本，要求它被计数。**
没有这条，`not_inert` 这个正对照自己**从未被证明能返回非零**——
与本项目已登记的「排除 `Time step` 使 `n_varying == 0` 恒真」是同一缺陷形态
（写入器 `:581-585` 已就该形态自陈过一次）。

### ③ 分离记录（落地时须分开写，不得合并）

- **驱动器 FAIL**（若发生）＝ `ev_require` 未满足 ⇒ 与 within-t0 的六个 GAP **无关**；
- **六个 GAP 关闭**（预期）＝ 修法奏效 ⇒ 与驱动器是否 FAIL **无关**；
- 二者**可以同时成立**（GAP 全关而驱动器仍 FAIL）——那是**协调缺陷**，
  不是矛盾：**判据与它判的对象不同步**。**本轮不改 `run_pipeline.py`**（改门＝改判据）。

### ④ ★落地前修正（C-178，**写于 rc4 仍在训练时**）：
### **P4 的数值是我从「孤儿字段」转抄的，不是基线**；
### 并且 **P1（294→300）带一个我没写出来的前提**

**读的是当前写入器的源码**（`_server/53_E5p_temporal_gnn.py:616-715`），**不是产物**。

#### ① P4 作废为「值预言」，替换为两条更硬的

| # | 事实 |
|---|---|
| 1 | `:692-693` `n_exact` 由 **`np.allclose(stored[i], by_le[True])`** 计 |
| 2 | `:704-705` `n_leq_ne_gt` 由 **`np.array_equal(by_le[True], by_le[False])`** 计 |
| 3 | **两个操作数集、两个比较，互不相同** ⇒ **「该计数被接成 `n_exact_match`」的接线假设，由源码直接排除**，不必再由数值证 |
| 4 | `:699-703` 写入器自陈：**上一版把 `stored` 与 `gt` 重算比较的结果，用这个名字返回** ⇒ **旧字段是另一个量** |
| **5** | **回源旧产物本身**：旧产物**没有 `n_stored_equals_gt` 这个键**，而当前写入器在 `:713` **会输出它** ⇒ **旧 294 对新字段的值没有基线效力。** |

**⇒ 原 P4（「必须仍为 294」）作废，换为：**

- **新 P4a（结构）**：新产物**必须含 `n_stored_equals_gt`**（旧产物无此键）。
  **缺失 ⇒ 跑的不是我改过的那个写入器。**
- **新 P4b（方向）**：`n_stored_equals_gt` **必须小**。
  stored 携 `<= t0` 窗 ⇒ 它**不应**等于 `> t0` 重算。
  **若它接近 300，那是泄漏信号，须查，不得读成通过。**
- **原 P4 的意图**（计数不得与 `n_exact_match` 同源）**由第 3 条源码事实承担**，比数值更硬。

**★这正是预注册该有的用法**：读源码**在读数之前**
推翻了我自己的一条预言。**若等产物落地再改，那就成了事后调参。**

#### ② P1（294→300）的未声明前提：**被跳过的行会计进 `n_mismatch`**

```
:675-676   if len(r) == 0 and len(r_sl) == 0: continue     # 该行不计入 n_exact
:708       n = len(addrs)                                  # 但 n 恒为 300
:710       n_mismatch = n - n_exact                        # ⇒ 被跳行落在 mismatch 里
```

⇒ **若抽到任一「两帧都无边」的地址，`n_exact_match`
无论修得多好都到不了 300。**

**可判的鉴别器（先写下）**：
若落地后读到 **`n_exact_match == 299` 且 `n_mismatch == 1`**，
**则查 `first_mismatches` 是否为空**：
- **空 ⇒ 那一条是被跳过的行（不是缺陷）**，修法完全成功；
- **非空 ⇒ 是真失配，修法未命中真因。**

**★不得把 299 直接读成失败**，也**不得把 300 当成唯一的成功形式**。

---

### §9(g) — rc2 **崩溃**（C-174）：无产物；根因是**我自己的修复**；★教训：fixture 纪律只施于落地工具

**这一节写在产物存在之前，是因为它要说明「本轮重跑死过一次」本身。**
rc2（`1ebf15e8`）崩于 **2636.5s**，`53_E5p_result.json` **从未产生**
⇒ 六个 GAP 与 §9(f) 的四个预言**在 rc2 上全部未被检验**，正反都不得陈述。

**逐帧 traceback（pod 日志，非转述）**：`:1593 → :1345 → :1321 → :467 → :426`
⇒ `ValueError: multi_class must be in ('ovo', 'ovr')`。

**根因：我加的那一行没切列。** `wtauc` 收到的是**整块二维分数矩阵** `(n, 3)`；
`within_t0_auc` 用**箱掩码**索引它 ⇒ `s[m]` 形状 `(n_in_bin, 3)`；>2 列时
`roc_auc_score` 走 **multiclass 分支**，而 `multi_class` 默认 `"raise"` ⇒ 抛错。
**紧邻的下一行作了正确示范**（`lk["scores"][..., k]` 带了列索引），**新加的这行没有**。
**三个臂没崩**，因为臂走 `eval_block` 传**一维** ⇒ **旧写入器从不对 control 调 `wtauc`**，
该路径是本次修复**新引入**的 ⇒ **traceback 不是关于旧写入器的证据**。

**修复两处，不是一处**：调用方切列（`scores[m, k]`）＋ 被调方入口加**一维守卫**。
第二处把「44 分钟后、既不点名行也不给形状的隐晦报错」前移到入口，**并把那一行留在消息里**。

**控制表（对象 = 两个真实文件，各自独立解析）**：

| 例 | 对象/输入 | 结果 |
|---|---|---|
| A | **pre-fix** ＋ 二维 | `multi_class must be in ('ovo','ovr')` —— **复现崩溃** |
| B | post-fix ＋ 二维 | 守卫抛错，消息含 `y.shape=(300,) s.shape=(300, 3)` |
| C | post-fix ＋ 单列 | `weighted=0.51554` |
| D | post-fix ＋ 一维（臂） | `weighted=0.51554` |
| E | **pre-fix** ＋ 单列 | `weighted=0.51554` |

**C = D = E 逐位相同 ⇒ 修复在本就能工作处行为不变**，唯一改变的是**对坏输入的拒绝**。
**B 证明守卫不是字面量**：它被走到，并抛了。

**★本轮最值得留的教训。** `80_`／`81_` 的 `archive_once`／`place_canonical`／
`bind_text_report`／驳回域**各有成套 fixture（含阳性对照）**；
**而这次改写入器，一套都没有**——**崩掉的分支，恰好是没被控制的那一支。**
⇒ **规则：凡改写入器，先让新路径在本地以最小输入跑通（形状级 fixture 即可）再上 pod；
「只改了形状」不是免测理由，形状错误正是它引来的。**

**★顺带证伪一个我自己的量具写法**：第一版 fixture 让 pre/post **共用同一棵 parse tree**，
而 `ast.get_source_segment(text, node)` 按 `node` 的偏移去**当时**的 `text` 取片段
⇒ 改动点**之后**的函数**被静默截断**（丢 `return`，返回 `None`）。
**量具随被测物漂移的 fixture，对两者都不作数。**

---

### §9(h) — rc3 **启动器缺陷**（C-175）：注释声称了代码没实现的动作；假终止标记指向错的运行

rc3 起后 1 分钟查活日志：**98 行 ＝ 89（rc2 残留）＋ 4（rc3 头）＋ 5（rc3 已产出）**，
**逐项吻合** ⇒ 该文件**没被截断**。rc3 启动器的注释写着「refusing to truncate the live log」，
**而 `: > "$LOG"` 这条语句根本没有被写出来**。

**后果不只是不整洁**：终局判定是 `grep -c "RSC_EXIT="`，而 **rc2 残留自带 `RSC_EXIT=1`**
⇒ 计数从 1 起步 ⇒ **第一拍即报 TERMINAL，且那个标记属于上一个运行**。
**「两个运行共用一条文本通道」第三次在本项目复现。**

**处置＝断言而非声称**：rc4 启动器 `: > "$LOG"` → 写 4 行头 → `wc -l` **必须恰为 4**，
否则 `exit 4` **且不启动 python**；实测 `4 lines`，`head -1` = rc4 头，
**`grep -c "RSC_EXIT="` ＝ 0** ⇒ 守卫从**真零**起步。
**并把「哪个对象产生了本轮读数」写进日志自身的头部**（`writer sha256: 077cb379…` ＋ cmdline）。

**★一个声称了行为、而代码不实现的注释**，与写入器里写死的
`selection_was_blinded_to_true_labels=True` **同族**：两者都让**读注释的人**相信一个
**未被执行**的保证。


---

## §9(i) — ★★★ rc5 **落地**（2026-09-24）：判据码 **FAIL**，五个 VALUE 检查不成立、**零 GAP**；
## 在判分口径上 **TGN 对两个基线在每一个 delta 上都不占优**，而**打乱标签的对照本身不在机会线**

**本节所有数字由脚本从落地产物重算后写入**（㉑：转述不是证据）。
产物 sha256 `95f1416bf027f15186cb1366e3bccbbd2d1f5dd116596394630e561862d3e027`（`228980 B`），已归档为 `/root/cis/results/53_E5p_result.077cb37906477179.json`，
本地与 pod **同哈希**；`status='ok'`、`seconds_total=2632.5`。
（落地门：`RSC_EXIT=0` **且** 日志自带 `wrote` 一行 —— 两者都读到了。）

### ① C-159 的修复：**成立，而且是 300/300 这种最干净的形式**

| 读数 | 值 |
|---|---|
| `n_sampled` / `n_compared` | 300 / 300 |
| `n_exact_match` / `n_mismatch` | **300 / 0** |
| `first_mismatches` | **0 条**（空表） |
| `n_where_leq_differs_from_gt` | **294** |
| `n_stored_equals_gt` | **6** |
| `feature_filter_verification_exact` | **True** |

**⇒ 自环列在未过滤帧上重算后，300 个抽样地址全部逐值相符。**
旧写入器在这同一段给出 `n_exact_match=294 / n_mismatch=6`、且 5 条记录的失配**只差第 3 列（`c_self_loops`）** ⇒ 那 6 条就是自环缺陷，**修法把它们清零了**。

**★并给出 294 与 6 的算术**：`n_exact_match=300` ⇒ stored 与 `<= t0` 帧全等；
`n_stored_equals_gt=6` ⇒ 有 **6 行**的 `<= t0` 与 `> t0` 两帧取值**完全相同**，
⇒ 这 6 行**既不进** `n_where_leq_differs_from_gt`（**300 − 6 = 294**），**又进** `n_stored_equals_gt`。
**⇒ 一个数字解释另一个数字，无余项。**

### ② 判分口径上的结果：**TGN 不占优**

`75_` 的判分口径 = 加权 **within-t0** AUC，对照取其上同一口径的值
（`shuffled_label_control.test_within_t0_auc_by_delta`）。**由产物重算**：

| arm | Δ | arm | control | margin | |
|---|---|---|---|---|---|
| mlp_feature_only | 1 | 0.764463 | 0.713642 | **+0.050821** | clears |
| mlp_feature_only | 3 | 0.762612 | 0.711744 | **+0.050868** | clears |
| mlp_feature_only | 5 | 0.764449 | 0.715839 | **+0.048609** | **does NOT clear** |
| graphsage | 1 | 0.728509 | 0.713642 | **+0.014868** | **does NOT clear** |
| graphsage | 3 | 0.729253 | 0.711744 | **+0.017508** | **does NOT clear** |
| graphsage | 5 | 0.734203 | 0.715839 | **+0.018364** | **does NOT clear** |
| tgn | 1 | 0.714267 | 0.713642 | **+0.000625** | **does NOT clear** |
| tgn | 3 | 0.716434 | 0.711744 | **+0.004690** | **does NOT clear** |
| tgn | 5 | 0.711017 | 0.715839 | **-0.004823** | **does NOT clear** |

**⇒ TGN 对 GraphSAGE 三个 delta 全负（−0.014 ~ −0.023），对 MLP 全负（−0.046 ~ −0.053）。**
`77_E5p_arm_table.py` 的原文即此：**「If TGN does not exceed a baseline, THAT is the result and must be reported as the result」**
—— 不得省略，**也不得用 pooled 列替换**（pooled 列对每个 arm 都是更大的数：
TGN pooled 0.796/0.814/0.833 vs control pooled **0.799/0.815/0.832** —— **pooled 上对照还压过 TGN**）。

### ③ 打乱标签的对照**不在机会线上** —— 这是本轮最硬的一条负面结论

| Δ | within-t0 读数 | 由分箱结构导出的 99% 零带 | Monte-Carlo 99% 零带 | |
|---|---|---|---|---|
| 1 | **0.71364** | 0.4852..0.5148 | 0.4857..0.5141 | **OUTSIDE** |
| 3 | **0.71174** | 0.4858..0.5142 | 0.4855..0.5147 | **OUTSIDE** |
| 5 | **0.71584** | 0.4812..0.5188 | 0.4816..0.5185 | **OUTSIDE** |

`76_E5p_null_band.py` 自己的结论原文：**「This is NOT a band specification problem …
the control is genuinely off-chance. Report it as a finding; do not explain it away
by widening any band.」**

**⇒ 含义**：标签被打乱后模型仍能在 within-t0 内拿到 ≈0.71。**within-t0 这个口径本身仍容许一份可观的泄漏**
（相对机会线高出约 0.21）。**⇒ 各 arm 与对照之间那点差距，不能读成「模型学到了持续性」。**

★**（C-202，2026-09-24，rc6 落地后追加）**：未训练模型的地板**已按架构分别测出**（rc6 预注册项 `untrained_floor`）：mlp `0.4424/0.3927/0.5378`、graphsage `0.5321/0.5425/0.5163`、tgn `0.5329/0.3826/0.4333`（Δ=1/3/5）。**没有任何一个未训练读出达到 0.71**（最大 `0.5425`），mlp 与 tgn 在部分 Δ 上**低于 0.5** ⇒ **对照的 0.71 不是该口径的结构性地板**，本句的「仍容许一份可观的泄漏」**据此加强、不予撤回**。（★**本条读法已被 C-235 更正**：`0.21` **不是泄漏量**，见 C-234；此处**保留原文**不改写，以保证引用仍能对得上。）**但两点须并记**：①「约 0.21」是相对 **0.5** 量的，而 rc6 显示未训练地板**并非在每个架构上都恰好是 0.5** ⇒ 泄漏的**存在与方向**稳健（对照 `0.711–0.716` vs 未训练上界 `0.5425`），**量值 0.21 是近似的**；② **预注册的 P2（未训练 mlp 落在 `0.5±0.05`、至少 2/3 个 Δ）未成立（1/3）**，且**预注册 §4 的两条子句在本结果上互相矛盾**（条件「P2 或 P3 不成立」成立，而该分支的理由「某架构未训练到 ≳0.6」不成立）⇒ **该情形未被预注册预见，按差额登记、不择一子句**。 **（C-205 追加，2026-09-24）口径补注**：上面九个数与「最大 `0.5425`」都是 `within_t0_auc.**weighted**`（按**箱大小**加权；该字段名与实际权重不符，见本文 1199–1209）。**另一口径 `unweighted` 下**九个数为 mlp `0.4459/0.3957/0.5512`、graphsage `0.5311/0.5434/0.5277`、tgn `0.5365/0.3753/0.4318`，最大值 **`0.5512`**（mlp，Δ=5）；对照（打乱标签）两口径分别为 `0.71174–0.71584` 与 `0.71301–0.72462`。**★三个判决在两口径下完全相同**（P2 `1/3→0/3` 两口径均不成立；P3 `3/3`；P4 `2/3`）⇒ **只有最大值依赖口径，判决不依赖**；两口径的最大值都 ≪ 0.711，故「对照的 0.71 不是该口径的结构性地板」一句**不因口径而改**；上文已写的「量值 0.21 是近似的」正覆盖这一层口径依赖。

★**（C-235，2026-09-24，rc7 修复重跑落地后追加。本条更正上面两段的读法，**不删不改**它们。）**

**上面「该口径本身仍容许一份可观的泄漏」这句话里的「泄漏」指的是什么？** 三个数必须分开：

1. **对照（打乱标签、同一特征）的 within-t0**：`0.7136417188364709 / 0.7117442671095938 / 0.7158394519074591`（weighted，Δ=1/3/5） ⇒ 高出 0.5 约 **0.21**。**这 0.21 是在完全没有真标签信息的情况下达到的** ⇒ 它度量的是**特征侧的可预测性＋该口径的构造**，**不是**「可归因于真标签的泄漏量」。
2. **可归因于真标签的增量** ＝ 同特征下 `true − shuffled`。两个对象，均已**逐字节复算**：
   - **对象①「臂」**：`arms.mlp_feature_only.by_delta[D].within_t0_auc.weighted` − `leakage_check.shuffled_label_control.test_within_t0_auc_by_delta[D].weighted` ＝ **+0.050821305 / +0.050867940 / +0.048609102**（unweighted：+0.046765 / +0.046912 / +0.046159）；
   - **对象②「归因表基线行」**：`results/_e5p_landing/53_E5p_leak_attrib.json` → `rows["ALL10 as-built (baseline row)"].readings.{true_labels,shuffled}[D].weighted` ＝ **+0.052775475 / +0.054860133 / +0.057782667**（unweighted：+0.049095 / +0.051891 / +0.055382）。
   **★两个对象都 ≪ 0.21**（差一个量级）。
3. ⇒ **正确的读法**：该口径在特征侧自带约 0.21 的**无标签区分力**（这是**方法学**发现：这个指标不能当作「持续性」的干净证据），而**真标签带来的增量约 0.05**。★**本更正的出处**：台账 **C-234**（2026-09-24，第三次自纠，方向与 C-233 **相反**）；**C-235 是它的落地批次**（rc7 修复重跑 ＋ 验收器修 ＋ 正本传播）。★**两条限度必须与上面并记**（二者都已在台账 C-234 ⑥ 登记）：①「**成因是特征侧可预测性**」目前是**推断、不是实测** —— 已登记 `79_E5p_feature_attrib.py`（每一列**单独**对**真标签**取 within-t0，**未跑**），**若某列单独就 ~0.6，该归因才算测出来**；② `true − shuffled` 的约 0.05 是**两个单点**（臂、归因表基线行），**其零分布尚未建** ⇒ 只作**量级读数**，**不主张显著**。**不得**再把「读数 − 0.5 ≈ 0.21」写成泄漏量。

★**「一个数必须带它的对象」**：上面 ①② 是**两个不同的量**（臂 vs 归因表基线行），此前笔记只写「+0.0528/+0.0549/+0.0578」而**没写对象** ⇒ 复现时会被读成矛盾（同族 C-209「计数没带层」）。

★**（同批更正我自己的另一处过头话）** 我此前记「负对照 `NC room-only`／`NC t0-only` 在 untrained 与 shuffled 两态下**恰为** 0.5」。按 `53_E5p_leak_attrib.json` 复算：**`shuffled` 列**三个 Δ 都**精确** 0.5；但 **`true_labels` 列**在 Δ=5 上是 `0.4999954205943726`（room-only）与 `0.5000049026418846`（t0-only） ⇒ **不是「恰」**，应作「**~0.5，偏差 ≤ 5e-6**」。预注册只要求「~0.5」，故**仪器未被判坏**；但「恰」字是过头话。★这处偏差与「实测算分是否含并列（ties）**未验**」这项残余未闭合相邻，一并留作未闭合。
**⇒ 计划里 E5 的中心主张（时序 GNN 预测持续性）在这一轮里没有被支持。**

### ④ `75_` 的判决，照抄其自述

`FAIL -- 5 VALUE check(s) did not hold`，且 **0 GAP**。五个不成立的检查：
`summary.shuffled_control_at_chance is True`、`shuffled-label control at chance within-t0 (0.05)`、
以及三个 `arm … clears control by >=0.05`。
工具自己的话：**「Every required reading was present. The record is complete and the
predicate does not hold. Report neither 'done' nor 'absent'.」**

**⇒ 按本项目纪律：E5p 的产物存在、非空、可解析 ⇒ 管线判 `DONE`（build: DONE=12 / RUNNING=0 / FAILED=0）；
但 `DONE` 说的是「这一轮跑完并落了盘」，不是「主张成立」。两者必须分开写。**

### ⑤ 双向对照（`81_`）**有判别力**，两个方向都跑了

| 方向 | 对象 | GAP 集 | 结论 |
|---|---|---|---|
| `--prediction fixedwriter` | 新产物 | **空** | **与预言相符**（旧物那六条 GAP 全部关闭）；5 条 FAIL **全部是 FINDING**（固定写入器的 `shuffled_control_at_chance` 取自 within-t0 列，pooled 论证够不到它） |
| `--prediction oldwriter` | 旧产物 `55d7d8f8` | **六条全 PRESENT** | 与预言相符；其 `feature_filter_verification_exact` 判 FAIL 且是 **FINDING**（即 C-159 缺陷） |

**⇒ 同一个 `shuffled_control_at_chance=False` 在两个写入器上「够不够得着」不同**：
旧物可被 pooled 论证消解，**新物不可** —— **这正是预言里必须带上「哪条消解适用于哪一侧」的原因。**

### ⑥ 判据核实：`feature verify 300 / 300` 与我的预注册

`_e5p_prereg_check.py` 结论 **`RESULT: all as pre-registered`**（其 P1/P2/P3 与 P4a/P4b 见 §9(f)/C-178）。
**另**：`_check_rc5_prediction.py` 结论 **`STATE: CONFIRMED -- all 9 readings identical
digit-for-digit`**（sage ep4–6、tgn ep1–3 逐位相同）⇒ **一次修订在本机上的 run-to-run 数值确定性成立**。

### ⑦ ★并列发现的仪器缺陷：`76_E5p_null_band.py` 的 `--json` **被文档承诺、代码没实现**

`:53` 的 usage 写着 `[--json out.json]`；`:143` 把一切 `--` 开头的参数过滤掉、`:146` 只处理 `--draws`
⇒ **我传的输出路径被当成第二个位置参数静默吞掉，文件根本没写**（`results/_e5p_landing/76_E5p_null_band.json` 不存在）。
**⇒ 本节 ③ 的零带结论目前只在终端里，没有机器可读记录。**
**这与 81_ 自己的 docstring 里记的 76_ 那个缺陷是同族但**不同**的一条**（那条是「打印警告却返回成功」，
这条是「承诺一个输出却不写」）。**⇒ 在补上之前，③ 的数字要按「人读」标注，不得当可复算产物引用。**


---

## §9(j) — C-191b 的仪器缺陷**已修**：零带数字从「人读」升为可复算记录

`76_E5p_null_band.py` 已实现它文档承诺的 `--json`（`sha256 385cd92a45f58977c23e60218d4dbbd3c704153ebfb3ac5ddf43edaaee17f43f`），并**新增退出码 6**：
**`--option` 未知、`--draws` 缺值、给了两个 artefact 路径 ⇒ 6**，不再静默吞掉
（旧代码 `[a for a in sys.argv[1:] if not a.startswith("--")]` 正是 `--json` 路径被吃掉的机制）。
**每个出口都写记录**，含 `state`/`exit_code`/`target_sha256`/逐 delta 的带。
**★本次记录里 `exit_code` 的取值是 `2`，不是 6**：五值约定为
`0` 带内 · **`2` 已评估且落在带外** · `3` 缺席 · `4` 不完整 · `5` 两兼 · `6` 调用错。
**6 描述的是「调用错」这一类，不是这一次** ⇒ 本节原先只写 6，
而这次运行的判决码恰好**就是本节结论本身（`OUTSIDE`）**；
不写它，读者会把「本节在讲退出码」误当成「这次退出了 6」。

**重过对照 21/21**（`_c191c_76_controls.py`）——**因为本次改的是控制流，终端的字没变而退出码可能已动**，
原八项对照因此不再是对当前代码的证据。全部以子进程驱动。

零带现为 `results/_e5p_landing/76_E5p_null_band.json`（`sha256 b52bb516992eec70eab477c2b5dbff469b49811dc9a6791ce62d27dc38149572`，绑定
`target_sha256 = 95f1416bf027f15186cb1366e3bccbbd2d1f5dd116596394630e561862d3e027`）。**§9(i)③ 的三个带由它复现，逐位相同**：

| Δ | n_bins | n_skipped | SE | 解析 99% 带 | Monte-Carlo 99% 带 | 读数 | 判决 |
|---|---|---|---|---|---|---|---|
| 1 | 48 | 0 | 0.005736 | 0.4852..0.5148 | 0.4857..0.5141 | 0.71364 | **OUTSIDE** |
| 3 | 46 | 0 | 0.005524 | 0.4858..0.5142 | 0.4855..0.5147 | 0.71174 | **OUTSIDE** |
| 5 | 44 | 0 | 0.007291 | 0.4812..0.5188 | 0.4816..0.5185 | 0.71584 | **OUTSIDE** |

**★表头原先漏设两列，数字与 JSON 逐值相符、只是标签不齐**：数据行按 JSON 的字段
顺序印的是 `Δ · n_bins · n_skipped · SE · 解析带 · MC 带 · 读数 · 判决`，
**而旧表头只有 7 格、末格没有标题**（`读数` 之后还跟着一个未命名的空格）⇒ `SE` 那一格底下站的其实是 `n_skipped` 的 `0`，
**读者会把 `0` 读成「标准误为零」**——而这张表正是给 `OUTSIDE` 判决作证的那一张。
⇒ 已补 `n_skipped` 与 `判决` 两列标签，**数字一个未动**。
JSON 真值（Δ=1）：`n_bins 48 · skipped 0 · se 0.0057365 · 带 0.48522..0.51478 · MC 带 0.48572..0.51411 · 读数 0.7136417`。

**⇒ §9(i)③ 的结论不变（三个 delta 全部 OUTSIDE），但它现在不再是一条只能读终端的历史陈述。**


---

## 勘误 C-244（2026-09-24）—— E5p within-t0 缺口的措辞

**本节的措辞取代上文（含 C-202/C-235 追加块）中关于该缺口的因果表述**；**不改任何数字、不改任何对象**。

* **不得写**「≈0.21（或 ≈0.214）**泄漏**」——台账 C-234 ③ 明令禁止；C-244 已按 **v9 §〇 K2 自身规则**
  （「负对照修复落地前的任何读数不作证据」）裁决 v9 K1 与本台账的冲突。
* **测量可报**：控制组 within-t0 加权读数 **0.7139/0.7115/0.7117**；置换零（20,000 抽 ×3Δ）中心
  **0.499978/0.499996/0.500044**、SD 与解析式同、覆盖 0.990–0.992 ⇒ **带外，高出机会线 ≈0.214**。
* **因果不可报**：成因（真泄漏／特征侧可预测性／口径构造）**未归因**。`untrained`（epochs=0）读
  **0.4424/0.3927/0.5378**，是**向下**的一条固定方向，而控制组**向上**偏 0.214 ⇒ **不能互释**；
  两个负对照在 t0 箱内**恒定（必然 0.5）** ⇒ **无一项为零分布提供锚点**。
* **可立**：`true − shuffled` ＝ **+0.0528/+0.0549/+0.0578**（对象＝归因表基线行；对象「臂」＝
  +0.0508/+0.0509/+0.0486）。**两个单点之差、无零分布 ⇒ 不主张显著**。
* **分类因的时点**：**E5r（W2）**之后，即负对照被重建成「**箱内有变化**」之后。
