# 07 — E7-inf: takedown latency and host reconstitution in URLhaus

**Status:** complete, after **three corrections of my own** and one measurement
that refuted my own hypothesis twice.
Code `_server/28_E7inf_takedown.py` (superseded), `29_urlhaus_status_probe.py`
(diagnostic), `30_E7inf_v2.py`, `31_E7inf_robust.py`, `32_E7inf_strat_placebo.py`,
`33_E7inf_size_ip.py`, `34_E7inf_dark.py` (reported).
Outputs in `results/` and `pipeline_reports/_ref/`.

---

## 0. What the plan asked for, and what replaced it

The plan's E7 asks for **HGT + attribution** (SHAP / GNNExplainer) over
**bridging versus centrality**. What is delivered is a takedown-latency and
host-reconstitution analysis in URLhaus.

The substitution is forced by the explanatory variable, not by convenience: the
plan's E7 asks whether bridging nodes matter more than central ones, and a
bridging node has **no substrate** in the assembled data — market-level
betweenness is 0 (the projection is near-complete) and the cross-layer
intersection is 3 addresses out of 822,942 (`results/37_E3_bridge_probe.json`).
Rather than fit an attribution model over a variable that does not exist, the
E7 question is asked on a layer where the outcome is directly observed: whether
a removal sticks, and whether hosts that get reused stick longer.

## 1. The object, and the two days that decide everything

URLhaus full dump: **58,310 URL rows, 17,400 hosts**. Columns include
`dateadded`, `url_status` (online/offline), `last_online`, `threat`, `reporter`.

The first thing that had to be established is what `last_online` *means*, and
the answer is that **it means two different things in the same column**:

| row is | `last_online` holds |
|---|---|
| `online` | the **crawl stamp** (~the snapshot) |
| `offline` | when it was last seen **alive** (the removal time) |

Evidence: all 16,038 `online` rows carry a `last_online` within **0.4 days** of
the snapshot (median 0.18 d = 4.3 h — one crawl cycle), while `offline` rows
carry lifetimes with median 0.73 d. And the added-year × `last_online`-year
crosstab has **no non-null `last_online` outside 2026 at all**.

From that follows the second fact, which decides the cohort. Removals are
recorded on a **razor-sharp** boundary:

```
2026-06-24   n=1       off=0       0.0%
2026-06-25   n=120     off=118    98.3%
2026-06-26   n=584     off=584   100.0%
```

Every month before 2026-06 has **0.0%** offline — including 3,691 rows added
2025-10 and 29 added 2019-01. A URL added in 2019 is not still online. The
discontinuity is one day wide, so it is a property of **the dump's bookkeeping,
not of the URLs**: URLhaus prunes entries that stop resolving, so an old row
survives only *by* still resolving. That is selection on the outcome, and it is
why an earlier draft's cohort (everything from 2025-03) was wrong.

**Cohort: 44,750 rows added 2026-06-25 onward** (76.7% of the file), 94.46%
offline, 2,478 censored, 90 days of follow-up.

## 2. ★ Result 1 — takedown latency is fast, and is bracketed, not point-estimated

`last_online` is missing for **19.85%** of offline rows — URLs never observed
alive. That missingness is not random, and dropping it truncates the *shortest*
lifetimes. Three treatments are reported side by side and they bracket the
answer:

| treatment | n | events | median (d) | q25 | q75 | censored |
|---|---|---|---|---|---|---|
| `zero` (missing → event at day 0) | 44,750 | 42,272 | **0.472** | 0.000 | 2.317 | 5.5% |
| `drop` (missing rows removed) | 36,359 | 33,881 | **0.859** | 0.171 | 3.559 | 6.8% |
| `censor` (missing → still alive) | 44,750 | 33,881 | **1.517** | 0.273 | 21.308 | 24.3% |

KM under `zero`: 50% offline by day **0.47**, 75% by **2.32**, 90% by **9.98**.

**Median takedown latency is 0.5–1.5 days and 90% of URLs are gone within ten
days.** No point estimate is claimed; the truth lies between the bounds.

## 3. ★ Result 2 — reused hosts are NOT stickier (a sign reversal)

The naive comparison across hosts said the opposite, and it was an artifact:

| comparison | first URL on host | repeat URL | verdict |
|---|---|---|---|
| across hosts (superseded) | median 0.539 d | median 2.005 d | *looks* 3.7× stickier |
| **within host (reported)** | 85.24% die ≤7 d | 84.75% die ≤7 d | **−0.49 pp** |

A host can only produce a repeat URL if it **survived** to be reused, so the
across-host contrast is contaminated by immortal time / selection on survival.
The within-host paired design makes the host its own control:

- 8,552 hosts, sign test **p = 8.05e-07**, mean within-host difference **−0.0049**
- hosts where later < first: 475; later > first: 334; **tied: 7,743 (90.5%)**
- the small negative effect **strengthens** as bulk hosts are dropped
  (−0.0049 → −0.0076 → −0.0095), so it is not an outlier artifact

**The direction reverses under the clean design.** Reuse confers no persistence
advantage; if anything later URLs die marginally sooner. The magnitude is
trivial (0.49 pp) against an 85% base rate, so the honest statement is *no
evidence of a reuse advantage*, not *evidence of a reuse penalty*.

## 4. ★ Result 3 — hosts that go fully dark do come back, and domains more than IPs

"Removal followed by an addition" is the **default** for a busy host, not a
response to a takedown — a host with 100 URLs collects a hit within 7 days of
*any* removal time by construction. The measure was rebuilt to ask the question
only of hosts that were **fully dark** at the moment of removal (every URL added
before *t* already offline by *t*). A continuously-active host contributes no
such event at all, so the confound is removed by construction.

**49.40% of removals (16,738 events, 12,795 hosts) are darkening events.**

| W | n | returns | real | chance floor | excess | p |
|---|---|---|---|---|---|---|
| 1 d | 16,416 | 2,279 | **13.88%** | 2.24% | **+11.64** | 0.000 |
| 3 d | 15,861 | 2,785 | **17.56%** | 5.92% | +11.64 | 0.000 |
| 7 d | 15,065 | 3,159 | **20.97%** | 12.28% | +8.69 | 0.000 |
| 30 d | 10,548 | 2,704 | 25.64% | 42.56% | −16.92 | — **not interpretable** |

After a host goes fully dark it returns with a new URL within **one day 13.88%
of the time — 6.2× its 2.24% chance floor** — and within a week ~21%. The
chance floor is a stratum-matched placebo: the same hosts, the same additions,
the same number of removals, with only the pairing shuffled.

By host size × naming (W = 7 d):

| size | kind | n | real | floor | excess | p |
|---|---|---|---|---|---|---|
| 1 | named | 425 | **0.00%** | 7.98% | −7.98 | 1.000 |
| 1 | IP | 3,244 | **0.00%** | 8.16% | −8.16 | 1.000 |
| 2–5 | named | 249 | 33.33% | 11.85% | +21.48 | 0.000 |
| 2–5 | IP | 8,394 | 16.29% | 9.30% | **+6.99** | 0.000 |
| 6–20 | named | 369 | 67.48% | 19.00% | +48.48 | 0.000 |
| 6–20 | IP | 1,724 | 57.66% | 30.17% | +27.49 | 0.000 |
| >20 | named | 312 | **80.77%** | 27.72% | +53.05 | 0.000 |
| >20 | IP | 348 | 61.49% | 36.51% | +24.98 | 0.000 |

**Two findings.**

1. **The size-1 rows are an exact negative control.** A host with one URL
   *cannot* have a later addition, and both read **0.00%** against ~8% floors.
   The shuffle machinery provably cannot manufacture signal from nothing, which
   is what licenses reading the other rows.
2. **Domain-based infrastructure is substantially more resilient than raw-IP
   infrastructure**, and this **survives the size control**: at every size ≥2
   the named-host excess is roughly double the IP excess, and at >20 URLs named
   hosts return **80.77%** of the time versus 61.49%. Compare §3 of report 06:
   in the financial layer, removing the **entire** labelled illicit subgraph
   left the giant component at 98.88%. Here, removing a host produces a
   replacement URL a fifth of the time within a week, and four fifths of the
   time on large domain-hosted hosts. **The two layers differ sharply in how
   much a single removal accomplishes.**

Composition, for the record: **82.79% of URLs sit on bare IP literals**, and the
top providers are /24 blocks (94.154.43.0/24 alone carries 2,335 URLs) plus
free-subdomain services — `r2.dev`, `oast.pro` (interactsh), `workers.dev`,
`vercel.app`. The `oast.pro` presence is a reminder that a feed like this
carries scanner/researcher traffic alongside criminal traffic.

## 5. Corrections and defects

**★ C-52 (my defect, cohort).** 28_ chose its cohort as "everything from the
first dense addition month" (2025-03, 56,708 rows). Those rows are pruned-from-
the-dump survivors whose `offline=False` is not an observation, giving ~8,700
perpetually-censored seven-year observations in the KM curve — which is why the
90th percentile came back `nan`.

**★ C-53 (my defect, denominator).** 28_ reported "19.0% came after the removal"
computed **among removals that already had a later addition** — selecting on the
event. The correct denominator is all removals, with the window right-censored
so a removal near the snapshot cannot be scored as a non-reconstitution.

**★ C-54 (my defect, immortal time).** 28_'s first-vs-repeat comparison across
hosts was contaminated by selection on survival (a host must survive to be
reused). The within-host paired design reverses the sign of the effect (§3).

**★ C-55 (my defect, duplicate arm).** A third treatment labelled `separate` was
built with the same filter as `drop` — a duplicate presented as an independent
arm. Replaced by `censor`, which is genuinely different and brackets from above.

**★ C-56 (a real property; measure not interpretable).** The W = 30 d row of §4
has its chance floor (42.56%) *above* its real rate (25.64%). At large W the
follow-up restriction selects early events and the shuffled baseline saturates,
so the pairing statistic is meaningless there. It is reported and labelled
rather than dropped.

**★ C-57 (my defect; a diagnostic check that lied).** A `grep -c buckets` used to
confirm I had deleted an unused variable returned 1 and I read it as "still
present". The single match was the word "buckets" inside a log string. A
substring test against a file that contains prose gives false positives.

## 6. Verdict

**ESTABLISHED**

1. `last_online` is dual-meaning (crawl stamp for `online`, removal time for
   `offline`), and removals exist only from **2026-06-25** onward — a one-day
   discontinuity that is a property of the dump.
2. **Takedown latency is fast**: median **0.47–1.52 days** bracketed across
   treatments; 90% offline within ~10 days.
3. **Reuse confers no persistence advantage.** Under a within-host paired design
   the effect is **−0.49 pp** (p = 8e-07) and it strengthens as bulk hosts are
   removed; the naive across-host 3.7× stickiness was selection on survival.
4. **Hosts that go fully dark return**: **13.88%** within one day (6.2× a
   stratum-matched chance floor of 2.24%) and ~21% within a week.
5. **Domain-hosted infrastructure is about twice as resilient as IP-literal
   infrastructure at equal size** (80.77% vs 61.49% return at >20 URLs), with a
   validated negative control at size 1 reading exactly 0.00%.

**NOT ESTABLISHED**

- **That this describes illicit infrastructure as a whole.** The cohort is one
  feed's recent window, dominated by IP literals (82.8%), with an unknown
  admixture of scanner traffic.
- **That the 82.8% IP-literal composition is a property of crime** rather than
  of what URLhaus tracks.
- **Any provider-level displacement.** Measured and **null**: real 19.33% vs a
  shuffled placebo of 22.38% (sd 0.19), excess **−3.05 pp**, p = 1.0000. Once
  the pairing is broken the rate does not fall, so the provider-level measure
  carries no information beyond provider size.
- **The W = 30 d reconstitution rate** (C-56).
