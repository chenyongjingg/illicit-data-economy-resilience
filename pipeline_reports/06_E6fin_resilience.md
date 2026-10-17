# 06 — E6-fin: structural resilience of the labelled Bitcoin transaction graph

**Status:** complete, after **v1 was corrected on two counts**, one my bug and one
a real property of the data.
Code `_server/25_E6fin_resilience.py` (v1, superseded), `26_E6fin_resilience_v2.py`
(reported). Outputs `results/25_…` (v1, retained), `results/26_E6fin_resilience_v2.{txt,json}`,
`results/figs/E6fin_resilience_v2.{png,pdf}`.

---

## 0. What the plan asked for, and what replaced it

The plan's E6 asks for **cross-layer alignment by graph embedding** (Node2Vec /
HGT) with an ablation. **The two layers it names do not meet.** The social↔chain
linkage recovers **3 addresses**, against 124 social addresses and 822,942
on-chain ones (`results/37_E3_bridge_probe.json`, with a recovery control) — that
is not a substrate on which an embedding alignment can be fitted.

What is delivered instead is a **structural resilience analysis of the labelled
Bitcoin transaction graph** (§2–§3): what happens to the network when its most
central nodes are removed, and whether the illicit subgraph is where the damage
lands. The plan's underlying question — how do these layers hold together under
disruption — is answered inside the one layer that has both a graph and a
recorded event, rather than across two layers that do not meet.

## 1. The object

Address–address edges rebuilt from real input→output pairs on the transaction
side (not from the pre-built `AddrAddr_edgelist`, which carries no time):
**2,868,964 pairs → 2,822,983 after dropping self-loops** (change addresses),
over **822,942 nodes**, plotted against 49 time steps.

**The clock comes from outside the data.** Steps span blocks 391,200–487,975 at
2,016 blocks/step. Anchoring on the well-known **block 400,000 = 2016-02-25** and
144 blocks/day maps the window to **≈2016-01-01 → 2017-11-03**, and places the
**July 2017 enforcement wave** (AlphaBay and Hansa both taken down 2017-07-20,
BTC-e on 2017-07-25) at **steps 41–43**. The block→date map is approximate, ±1
step. Because that window is fixed by an external fact about the world and not by
this dataset, testing it is a test rather than a description.

## 2. ★ Result 1 — the network is fragile to targeting, and the illicit subgraph is not the target

Every curve below removes nodes in a stated order and tracks the giant component
as a fraction of *surviving* nodes. All curves share an explicit random tail, so
the head order is the only thing that differs between them (see §5, defect 1).

| removed | random | degree-targeted | illicit (by degree) | illicit (random) |
|---|---|---|---|---|
| 0.5% | 99.61% | 79.16% | 99.91% | 99.91% |
| 10% | 93.08% | 20.48% | 93.16% | 93.16% |
| 30% | 76.60% | 1.80% | 76.61% | 76.61% |
| 50% | 56.90% | 0.00% | 57.42% | 57.42% |

| curve | removed to halve the giant component | AUC |
|---|---|---|
| random failure | **60.0%** | 54.23 |
| **degree-targeted** | **2.5%** | **5.49** |
| illicit-targeted (by degree) | 60.0% | 54.50 |
| illicit-targeted (random) | 60.0% | 54.51 |

**Two findings.**

1. **A ~24× asymmetry between random failure and targeted removal** (60% vs 2.5%
   of nodes to halve the giant component). The graph has the scale-free
   signature: robust to random loss, fragile to hub removal.
2. **★ Targeting illicit addresses is indistinguishable from chance.** At the
   point where *every* illicit node has been removed — 14,266 nodes, **1.734%** of
   the graph — the giant component stands at:

   | curve | giant component left |
   |---|---|
   | random | **98.88%** |
   | illicit, targeted by degree | **98.87%** |
   | illicit, targeted at random | **98.88%** |

   Removing the entire labelled illicit population does not measurably fragment
   this network, and targeting its best-connected members does no better than
   picking illicit nodes at random.

The mechanism is visible in the degree table rather than inferred:

| class | n | mean degree | median degree |
|---|---|---|---|
| illicit | 14,266 | **3.645** | 2 |
| licit | 251,088 | **10.803** | 2 |
| unknown | 557,588 | 5.168 | 2 |

**The labelled illicit subgraph is structurally peripheral.** It attaches to the
transaction graph but is not its backbone; the hubs — and therefore the
fragility — sit in the licit and unknown populations (exchanges and services).
This is directly RQ3-relevant: *address-level suppression of illicit activity has
no network-level effect, because the network's resilience does not depend on the
illicit addresses.*

## 3. ★ Result 2 — connectivity is saturated, so it is not a usable instrument

`gc_frac` is **1.0000 in 47 of 49 steps** (0.9999 at step 22, 0.9997 at step 43);
sd = 0.0002. The 2-week address graph is **one connected component at essentially
every step**, and the whole graph is 822,935 / 822,942 nodes in one component
(99.9991%).

This is a **measurement** finding, and it is negative: giant-component
connectivity has no range in this object and **cannot serve as a resilience
instrument at this resolution**. A measure that reads 1.0000 every period cannot
register a shock.

## 4. ★ Result 3 — the pre-specified enforcement test does not reject

The test was fixed before it was run: window steps 41–43, direction "lower",
null = 20,000 random 3-step windows drawn from the same series.

| observable | series mean (sd) | steps 41–43 mean | permutation p(≤) |
|---|---|---|---|
| illicit share | 0.0174 (0.0140) | 0.0084 | **0.0954** |
| illicit address count | 300.4 (241.8) | 232.7 | **0.3458** |
| active address count | 18,790 (7,658) | 26,461 | 0.9577 (**higher**) |

**Nothing rejects at 0.05.** Two of the three observables show no movement at all,
and the third moves the *wrong* way (more addresses active during the window, not
fewer). A 5-step window (41–45) gives p = 0.0353 on illicit share, but that window
was chosen after seeing the series and is **exploratory, not evidence**.

**This is a low-power test and the null does not establish absence.** The series
is extremely noisy — the illicit address count has CV 0.80 — so a real 20–30%
suppression lasting 3 steps would often not be detected. And a further limitation
cannot be checked from inside the data: **it is not verifiable that AlphaBay's or
Hansa's addresses are in Elliptic's labelled illicit set at all.** If they are
not, absence is expected and the test is uninformative rather than negative.

Contrast with the social layer, where the same kind of event (Cryptonia/Cannazon,
2019-11) produced an unmistakable break. The difference in detectability across
layers is itself a cross-layer observation.

## 5. Corrections and defects

**★ C-50 (my defect, in v1).** In `25_`, the `illicit-first (degree)` and
`illicit-first (random)` curves were **identical at every grid point**
(88.76 / 73.11 / 49.76 / 25.30). Cause: `np.setdiff1d` returns a **sorted** array,
so both orders shared the same tail; and since the illicit head is only 1.7% of
nodes, by the first grid point (10%) both curves were already deep inside the
identical tail. **The printed curves looked entirely plausible**, which is what
made it dangerous — the defect did not announce itself as an error. Fixed in v2 by
giving every curve an explicit shared random tail and **asserting** in code that
the illicit curves share a tail and differ in their head.

**★ C-51 (a real property, not a bug).** `gc_frac` saturated at 1.0000 in 47/49
steps. v1's §4 z-score shock test divided by an sd of ~0 and printed values like
`z = −6.39` and `z = +0.19` that are meaningless. **Those z-scores are
withdrawn.** The shock test was moved to observables that vary.

| id | correction |
|---|---|
| C-50 | 25_'s illicit removal curves were identical by construction (`setdiff1d` sorts); the contrast was destroyed, and the output looked plausible |
| C-51 | giant-component connectivity is **saturated** at 1.0000 in 47/49 steps; v1's connectivity z-scores are withdrawn; connectivity is not a usable resilience instrument here |

## 6. Verdict

**ESTABLISHED**

1. **Robust-yet-fragile**: random failure needs **60%** of nodes removed to halve
   the giant component; degree-targeting needs **2.5%**.
2. **The labelled illicit subgraph is structurally peripheral** (mean degree 3.645
   vs 10.803 for licit) and removing **all** of it (1.734% of nodes) leaves
   **98.88%** of the giant component — indistinguishable from removing the same
   number at random. **Targeted suppression of illicit addresses has no
   network-level effect here.**
3. **Connectivity is saturated** across all 49 steps, so it cannot measure
   resilience in this object.

**NOT ESTABLISHED**

- **Any effect of the July 2017 enforcement wave** on the labelled subgraph
  (p = 0.095 / 0.346 / 0.96). Low power, and it is not verifiable that those
  actors are in the labelled set at all.
- **That these results describe Bitcoin.** This is the **labelled subgraph**, whose
  composition is a collection artefact (**C-49**). The licit and unknown
  populations are the graph's hubs here partly because that is what was collected.
- **That "suppressing illicit addresses has no effect" generalises** beyond the
  labelled set — the conclusion is about this graph.
