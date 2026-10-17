# 05 — E5-fin: recurrence of participation in the labelled Bitcoin subgraph

**Status:** complete, **and its headline does not survive its own specificity
check.** Reported as a negative specificity result, which is what the check was
for.
Code `_server/18_…`–`23_…` (probes), `24_E5fin_recurrence.py` (reported).
Outputs `results/19_…`–`23_…` (validation), `results/24_E5fin_recurrence.{txt,json}`,
`results/figs/E5fin_recurrence.{png,pdf}`.

---

## 0. What the plan asked for, and what is delivered instead

The plan's E5 asks for a **predictive model**: a temporal GNN (TGN/TGAT)
predicting recurrence of participation in Elliptic++, against a GraphSAGE
baseline and a feature-only MLP, with a pre-registered fallback to
"GraphSAGE + hand-built temporal features" if the temporal GNN fails to converge
or shows limited gain.

**Neither is delivered here.** What this report delivers is a **measurement** of
recurrence — the quantity a predictive model would take as its label — and **no
model is fitted** (§4). That is not a reframing of the plan's experiment; it is a
missing experiment, recorded as such.

The distinction matters because the plan's fallback is *conditional*: it fires
when the temporal GNN "did not converge or improved little". **The temporal GNN
has never been trained**, so the trigger has not fired, and running the fallback
now would assume an outcome instead of measuring one. The primary arm is
CPU-runnable on the pod (`torch 2.5.1`, `torch_geometric 2.8.0`, Elliptic++
present) and has not been attempted.

## 1. The measurement had to be established before anything was measured

Four probes, three of which overturned the previous one. This is the part of the
work that carries the weight.

**The schema guess was wrong.** `18_` predicted `wallets_features.csv` would carry
per-time-step columns named `<quantity>_Time Step`. It carries **zero** such
columns — it has a `Time step` column and 1,268,260 rows.

**C-46 — a row is one (address, transaction) participation, not one (address,
step).** `19_` tested the obvious reading (one row per active step) and it failed:
`num_timesteps_appeared_in` equalled the row count for only **71.52%** of
addresses, and one address carried **1,471 rows in a 49-step window**. `20_` then
found the structure and the arithmetic closes exactly:

| quantity | value |
|---|---|
| rows | 1,268,260 |
| byte-identical duplicate rows (all 57 columns) | 347,569 |
| duplicated `(address, Time step)` pairs | **347,569** ← the same number |
| distinct `(address, Time step)` pairs | 920,691 |
| 1,268,260 − 347,569 | **920,691** ✓ |

and `347,569 / 822,942 = 0.422`, exactly the mean `rows − stated` from `19_`. So
`num_timesteps_appeared_in` was right and the row count was the inflated thing.
`total_txs`, `num_txs_as_sender`, `num_txs_as receiver` are **constant within
address** (0 / 822,942 vary) — address-level lifetime totals repeated on every row.

The reading that fits: a row is one (address, *transaction*) participation, every
non-key column is an address-level aggregate, and two transactions of one address
inside one time step are byte-identical because **the schema has no transaction id
column**. 1,268,260 rows ÷ 203,769 transactions = **6.22 addresses per transaction**.

**That reading was confirmed against a different object, not by plausibility.**
`21_` used the role-split edge lists on the transaction side (`AddrTx_edgelist` =
senders, `TxAddr_edgelist` = receivers), built independently of
`wallets_features`:

> **`num_txs_as_sender + num_txs_as receiver == row count` for 822,939 /
> 822,942 addresses (100.00%), maximum difference 0.**

`22_` then verified the cell-level quantity a panel would actually consume —
`row_n == sender_edges + receiver_edges` per (address, step) cell — and got
**98.90% exact agreement** over the same 920,691 cells (zero cells present in one
file and not the other). The residual is one-sided (`edge_n ≥ row_n` always, max
difference 0), touches 1.10% of cells, and holds 4.91% of participation volume.

So the per-step participation count is a **verified** measurement, with a
disclosed residual. Everything below stands on it.

## 2. ★ The duration design was killed before it was written

`23_` asked whether a survival design sits on this measurement. It does not:

| class | n | appear in exactly 1 time step | ≥2 steps |
|---|---|---|---|
| illicit | 14,266 | **98.18%** | 1.82% |
| licit | 251,088 | 94.20% | 5.80% |
| unknown | 557,588 | 91.63% | 8.37% |

Median duration is **0 steps for every class**. On a 49-step window with 92%+
one-shot addresses, a Kaplan–Meier curve is a step function that falls to the
floor immediately and the thing being modelled is the one-shot majority, not a
process. No survival model was fitted. The outcome is binary: **does the address
appear in ≥ 2 distinct time steps.**

`23_` also produced a hypothesis that the probe itself refuted, which is worth
recording because it is the ordinary case: `19_` had reported illicit
first-step median = last-step median = 28 against 22/23 for licit, and "both
medians landing on the same non-central value" looked like a spike in one class's
entry distribution. It is not a spike. When 98% of a class has `t0 == t1`, the
median of `t0` and the median of `t1` are the median of the same variable and must
agree. The anomaly dissolves under the one-shot structure.

## 3. ★ The ceiling is not optional

An address entering at step `t0` has at most `49 − t0` steps of room, and the
classes do not enter at the same time. From `23_`:

| entry step | n | mean room (49−t0) | observed mean duration |
|---|---|---|---|
| 1–10 | 220,639 | 43.7 | 1.57 |
| 11–20 | 124,885 | 33.5 | 1.01 |
| 21–30 | 137,209 | 24.6 | 0.80 |
| 31–40 | 163,496 | 13.1 | 0.21 |
| 41–49 | 176,713 | 4.5 | 0.10 |

Observed duration tracks available room almost exactly. And 7.75% of licit
addresses enter at step 1 against **0.51%** of illicit ones, with mean `t0` of
23.58 (licit) vs **28.74** (illicit). An unconditional comparison of recurrence
would measure the calendar. Every estimate below is computed **within an entry
step**, which removes the ceiling exactly and needs no model.

## 4. Result: recurrence is low, and it is ordered by class

Overall recurrence **7.47%** (61,487 / 822,942). Within-entry-step rates:

| class | n | recurrence | mean t0 | mean room |
|---|---|---|---|---|
| illicit | 14,266 | **1.816%** | 28.74 | 20.26 |
| licit | 251,088 | **5.796%** | 23.58 | 25.42 |
| unknown | 557,588 | **8.371%** | 24.83 | 24.17 |

Within-step differences (illicit − licit) across the 48 usable entry steps:
**mean −2.586 pp, median −1.689 pp, illicit lower in 35 / 48 steps.**

Logistic with entry-step fixed effects (n = 811,269, unknown = base):
`illicit` **−1.4235** (se 0.0636), `licit` **−0.6563** (se 0.0101),
`log(entry intensity)` **−1.0147** (se 0.0131). Higher entry-step intensity goes
with *lower* recurrence — burst addresses are one-shot.

Recurrence by entry-intensity quartile is monotone in class in **every** quartile
(illicit < licit < unknown), with the gap widest at Q4 (illicit 0.73% vs licit
8.12%).

## 5. ★ The specificity check, and why the headline is withheld

The falsification that matters is not the placebo. A random split of the unknown
class gives a within-step mean difference of **+0.021 pp** — 130× smaller than the
observed −2.735 pp — but that only shows the estimator is not manufacturing
differences *at random*. It says nothing about the design.

The check that bites compares two classes that enforcement does **not**
distinguish:

| comparison | within-step mean difference |
|---|---|
| illicit − licit | **−2.735 pp** |
| **licit − unknown** | **−2.470 pp** |

**Comparable.** By the criterion stated before the run, class is therefore **not**
doing illicit-specific work. The pattern is a **monotone gradient across all three
labelling categories** — unknown > licit > illicit — and a gradient across the
whole labelling scheme is equally consistent with *how addresses entered the
labelled subgraph* as with anything about illicit behaviour. This is the same
family of confound as E1's collector re-weighting: the class label and the
observation process are not separable here.

**Also withheld: every p-value.** The pooled estimate carries a nominal se of
0.091 pp, but the between-step differences span **−27.4 pp to +13.1 pp**. The
observed heterogeneity is roughly 100× the nominal se, so the fixed-effect se
assumes a homogeneity the data plainly violates and the pooled p-value is not
interpretable. Only the effect *size* and the *heterogeneity* are reported.

## 6. Verdict

**ESTABLISHED**

1. **A verified per-(address, time step) participation count** for Elliptic++,
   checked against independently constructed edge lists (100.00% address-level,
   98.90% cell-level).
2. **Recurrence in the labelled subgraph is low: 7.47%**, and 91.6–98.2% of
   addresses appear in exactly one time step.
3. **Recurrence is monotone in class — illicit 1.82% < licit 5.80% < unknown
   8.37%** — and this ordering holds within entry steps, i.e. after the ceiling is
   removed exactly and without a model.
4. **Higher entry-step intensity predicts *lower* recurrence.**

**NOT ESTABLISHED**

- **That illicitness causes low recurrence.** The licit−unknown gap (−2.470 pp) is
  as large as the illicit−licit gap (−2.735 pp). A monotone gradient over a
  three-way label does not identify a binary illicit effect (**C-48**).
- **Any p-value.** Between-step heterogeneity is ~100× the nominal se.
- **That this measures resilience of illicit finance.** The outcome is recurrence
  of participation in the **labelled subgraph**, not all on-chain activity
  (**C-49**). An address "dies" here when it stops touching the labelled
  subgraph.
- **Vendor/actor behaviour.** Class is an **actor-level** determination ("was ever
  involved in illicit activity"), not a per-time-step state, so nothing here says
  what an address was doing at a given step.

## 7. Corrections logged

| id | correction |
|---|---|
| C-46 | a `wallets_features` row is one (address, **transaction**) participation; 347,569 byte-identical rows are distinct transactions the schema cannot separate (no tx id column); `total_txs` etc. are address-level totals repeated per row |
| C-47 | `rsc.py bg` sanitises its log path but not the command string — a leading-slash argument is MSYS-mangled; call sites need `MSYS_NO_PATHCONV=1` |
| C-48 | E5-fin's class effect is **not specific to illicit**: licit − unknown (−2.470 pp) ≈ illicit − licit (−2.735 pp); monotone over the labelling scheme, so not attributable to illicitness |
| C-49 | the outcome is recurrence in the **labelled subgraph**, not in Bitcoin; "death" here means ceasing to touch the labelled subgraph |
