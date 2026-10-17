# 04 — E1: does activity move to a surviving market when others die?

> ### ★ §6c and §8 claim 3 are SUPERSEDED — see §10 (added 2026-09-24).
> §6c's placebo evidence for model (ii) was **three draws**. Re-measured with
> 500, the null's mean is **+1.1156**, not the ≈0 a "largest placebo +0.76"
> implied, and **stratum × week FE removes only 14% of the pre-trend** it was
> introduced to remove. The effect is real but its size is **+1.0 to +2.4**
> reviews/week, not +3.64. The text below is left exactly as written.

**Status:** complete, after **three designs**, two of which were declined by their
own falsification tests.
Code `_server/11_…`, `12_…`, `13_…` (probes), `14_E1…` (v1, declined),
`15_E1…v2` (declined), `16_E1_v3.py` (reported), `17_E1_products.py` (follow-up).
Outputs `results/14_…`, `results/15_…`, `results/16_E1_v3.{txt,json}`,
`results/17_E1_products.{txt,json}`, `results/figs/E1_social_substitution_v3.{png,pdf}`.

---

## 1. What the data is

Five dated markets inside `kilos_reviews.parquet`. Two things had to be fixed
before any time-series claim could be made, and both are recorded as corrections.

**★ C-38 — the timestamp resolution differs by market, and it is not noise.**

| market | distinct seconds-of-day | clock |
|---|---|---|
| Empire | 1,440 | real (minute resolution) |
| Apollon | 780 | real (minute resolution) |
| Cannazon | **2** | **date only** |
| Cryptonia | **2** | **date only** |
| CannaHome | **2** | **date only** |

The two values are `22:00:00` and `23:00:00` UTC, in proportions that track the
season (Cannazon 84%/16%, CannaHome 18%/82%) — i.e. **local midnight converted
from CET/CEST**. Three of five markets carry dates, not times. Any sub-daily
analysis across markets would compare a real clock against a rounded one. For that
reason **everything in E1 is at weekly resolution**, which makes the rounding
irrelevant.

**★ C-39 — Samsara has no time axis at all.** All 10,216 Samsara rows have
`f2 == 0`, which parses to 1970-01-01. It is a null marker, not a date. Samsara is
excluded from every time-based analysis; including it would have inserted 10,216
events into 1970.

**★ C-41 — Cryptonia's rows come from a different pipeline.** Its `f3` is `1` in
**100.0%** of rows (Empire 85.7%, all others 98.2–98.4%), and it is one of the
three date-only markets. Two independent schema-level differences point at a
different collection route into the same dataset.

## 2. Correction C-42 — the overlap statistic is not migration

`11_` found 387 of 1,660 handles (23.3%) present in more than one market, carrying
51.0% of reviews. The tempting reading is vendor mobility. Two checks say not to
take it that way:

- **No identity key exists.** The table is
  `market`, `vendor`, `f2`, `f3`, `price`, `text_len` and nothing else — no PGP
  key, no account id, no contact handle. A matching handle is not a person, and
  the error runs **both ways** (two people may share a handle; one person may use
  two). It is neither an upper nor a lower bound on mobility.
- **The overlap is concentrated, not spread.** The largest pair is
  Apollon/Cryptonia at 0.410 containment against a median of 0.183 across all ten
  pairs — one pair dominating is what shared provenance looks like.

The decisive test: are the **rows** duplicated? Across all five markets,
**0 of 224,593** distinct `(vendor, price, timestamp, text_len)` tuples appear in
more than one market, and **0 of 76,382** for Apollon+Cryptonia specifically. So
there is no shared feed. The overlap is real but unidentified.

## 3. The aggregate (descriptive only)

| market | pre (wk mean) | post (wk mean) | change | share pre → post |
|---|---|---|---|---|
| Empire | 2,769 | 1,050 | −62% | 41.4% → 18.4% |
| Cannazon | 1,909 | 5 | −100% | 28.5% → 0.1% |
| Cryptonia | 1,430 | 0 | −100% | 21.4% → 0.0% |
| **Apollon** | 418 | 3,915 | **+836%** | 6.2% → **68.4%** |
| CannaHome | 164 | 752 | +358% | 2.5% → 13.1% |
| **TOTAL** | **6,691** | **5,722** | **−14%** | |

Cryptonia runs at ~500 reviews/day to its last day and **stops dead on
2019-11-17**; Cannazon collapses the next day. Total ecosystem volume is
**roughly preserved** — the week of 2019-12-16 (11,434) is within 2% of the week
before the shock (11,625) — while the composition turns over almost completely.

**This table cannot distinguish substitution from a collector re-weighting its
coverage.** A scraper that shifted which markets it harvested would produce it
exactly, with nobody moving. It is reported as a description, never as an effect.

## 4. v1 — declined

Seller-level DiD on Apollon: beta = **−1.3364**, p = 0.0118. Its own placebos:

| event | beta | p |
|---|---|---|
| 2019-08-05 (placebo) | −1.148 | 0.083 |
| 2019-09-02 (placebo) | **−1.691** | **0.0028** |
| 2019-10-07 (placebo) | **−1.656** | **0.0020** |
| **2019-11-18 (real)** | **−1.336** | 0.0118 |

**The placebos are larger, and more significant, than the event.** The design was
measuring a pre-existing trend. Cause, visible in v1's own trend table: the control
group was defined as "active in Apollon before the event", so 331/331 of them are
Apollon-active by construction against 158/697 of the treated. Their means run
0.178 → 2.816 across the pre-period against the treated's 0.099 → 0.937. Two groups
selected to differ in **level** differ in **trend**, because count variance scales
with the mean. v1 is declined in full.

## 5. v2 — declined, and why

v2 rebuilt the test three ways. Two worked, one did not.

- **A. Aggregate** — as §3.
- **B. Symmetric entry test** — exposed 96/539 (17.8%) vs control 16/204 (7.8%),
  OR 2.55, p = 5.2e-4. **But its placebo was 0/237 and 0/436** — no entry in either
  arm, because Apollon barely existed in 2019-07/09. *A test whose placebo has no
  room to move is not a test.*
- **C. Intensive DiD** — candidate set was `apollon_active & (dead | empire)`,
  which silently excluded Apollon-only sellers and left **16 controls against 158
  treated**. The crosstab printed 3/11, 1/31, 4/40, 8/76 and the imbalance was
  visible in it; the significance test was not the thing that was wrong.

## 6. v3 — reported

### 6a. Is entry *directed*, or just general mobility? (the falsification B needs)

Same definition for every target: among sellers naive to the target before the
event, who appears there after.

| target | exposed n | exposed % | control n | control % | OR | p |
|---|---|---|---|---|---|---|
| **Apollon** (grew +836%) | 539 | **17.8%** | 231 | **7.4%** | **2.728** | **1.4e-4** |
| CannaHome (grew +358%) | 684 | 0.1% | 533 | 0.2% | 0.78 | 1.0 |
| **Empire** (shrank −62%) | 638 | **0.0%** | 342 | **0.0%** | — | 1.0 |

**Entry-rate gap: Apollon +10.5 pp; Empire +0.0 pp.** Sellers exposed to the dead
markets did **not** enter the shrinking market at any elevated rate. This is what
kills the "exposed sellers are simply more mobile people" explanation: the effect
is directed at the market that absorbed the volume. CannaHome is uninformative
(floor effect — 0.1%).

### 6b. The source market decides

| source | entered Apollon | rate | control rate | OR | p |
|---|---|---|---|---|---|
| **Cryptonia**-only | **87/415** | **21.0%** | 7.4% | **3.339** | **3.5e-6** |
| Cannazon-only | 10/140 | 7.1% | 7.4% | 0.968 | 1.0 |

Two markets die on the same day. One population substitutes; the other does not
move at all. **The Cannazon null rests on 10 events, so it is underpowered rather
than confident.**

### 6c. Intensive margin, with the scale artefact removed

Candidate set corrected to **all** Apollon-active sellers (489). Baseline
intensity stratum × treatment is now balanced: s1 56/11, s2 50/31, s3 88/40,
s4 137/76.

| model | beta | se | p | 95% CI |
|---|---|---|---|---|
| (i) seller + week FE | +3.882 | 1.370 | 0.0048 | [+1.19, +6.57] |
| **(ii) + stratum × week FE** | **+3.637** | 1.440 | **0.0119** | **[+0.81, +6.47]** |

Treated pre-period mean = **1.153** reviews/week, so the estimate is **3.2× the
pre-period level**. Model (ii) gives every baseline-intensity group its own weekly
path, absorbing any differential trend that is a function of baseline size — the
exact defect that produced v1's spurious effect.

Placebos on (ii), pre-period data only:

| placebo event | beta | p |
|---|---|---|
| 2019-08-05 | +0.465 | 0.042 |
| 2019-09-02 | +0.508 | 0.087 |
| 2019-10-07 | +0.761 | 0.128 |

**The largest placebo (+0.76) is 4.8× smaller than the event estimate (+3.64), and
its CI [+0.02, +0.91] excludes the event estimate.** Unlike v1, this design has
discriminating power, and the effect survives it.

## 7. What the mechanism is *not* — a refuted hypothesis

The natural explanation for §6b is product-market overlap: Cryptonia was a general
market and so was Apollon, so its sellers could redeploy; Cannazon was a cannabis
specialist with nowhere comparable to go. **The price data refutes the version of
this that price can proxy:**

| market | share of reviews inside Apollon's 5–95% price band |
|---|---|
| Cannazon | **93.4%** |
| Cryptonia | **80.7%** |

The market that *failed* to move had **more** price overlap, not less. Price is a
weak stand-in for product type and this does not disprove the overlap story — but
it removes the only evidence the available columns could have offered for it.
**The product-overlap explanation is untested**, because `kilos_reviews` has no
category column. It is recorded as an open hypothesis, not a finding.

Entrants and non-entrants are otherwise alike: Cryptonia entrants median 25
pre-period reviews vs non-entrants 20; median price 0.0112 vs 0.0136.
So non-entry is not a size or quality effect.

`f3` is **not usable as a rating**: it is `1` in 100% of Cryptonia rows and 85.7%
of Empire's. Reported, not relied on.

## 8. Verdict

**ESTABLISHED**

1. **Composition turnover with preserved aggregate volume.** Two markets stop
   within a day; total ecosystem volume is roughly preserved; Apollon goes from
   6.2% to 68.4% of it. Descriptive, and confounded with collection policy.
2. **Entry is directed.** Exposed sellers enter the growing market at +10.5 pp and
   the shrinking market at +0.0 pp. General mobility is excluded.
3. **Seller-level substitution at the intensive margin is real and survives
   stratum×week FE and a placebo 4.8× smaller** (+3.64 reviews/week vs a treated
   base of 1.15; CI excludes zero and excludes every placebo).
4. **The response depends on which market died**: Cryptonia 21.0% vs control 7.4%
   (OR 3.34, p=3.5e-6); Cannazon 7.1% vs 7.4% (10 events).

**NOT ESTABLISHED**

- **Any mechanism.** Product-overlap is untested and its price proxy is refuted.
- **That the shock caused the turnover.** A collector re-weighting coverage
  remains observationally equivalent at the aggregate level. §6 tests survive it
  — a scraper changing Apollon's coverage moves all Apollon sellers together and is
  absorbed by week FE — but "survives this confound" is not "the confound is
  ruled out".
- **Vendor identity.** Treatment is a handle match and no key exists. Sellers who
  changed handle are misfiled as controls, which **attenuates**. A positive result
  survives that; the Cannazon null does not distinguish "did not move" from "moved
  under another name".
- **Where the non-movers went.** §3 of `17_` compares non-entrants' post-activity,
  but "did not enter Apollon" is defined by the absence of Apollon activity, so
  that comparison is largely **tautological** and is not relied on.

## 9. Corrections logged

| id | correction |
|---|---|
| C-38 | timestamp resolution differs by market; Cannazon/Cryptonia/CannaHome are **date-only** (22:00/23:00 UTC = local CET/CEST midnight) |
| C-39 | Samsara's `f2 == 0` for all 10,216 rows — a null marker, not 1970 |
| C-41 | Cryptonia is 100% `f3 == 1` — a different collection pipeline |
| C-42 | handle overlap ≠ vendor mobility; no identity key exists; 0 duplicate rows across markets |
| C-43 | E1 v1's DiD was **declined** — placebos larger and more significant than the event |
| C-44 | E1 v2's section C candidate set excluded Apollon-only sellers, leaving 16 controls; v2's B placebo had no room to move |
| C-45 | the product-overlap mechanism is **untested**; its price proxy points the wrong way |

---

## 10. Addendum (2026-09-24) — the headline design's placebo evidence, re-measured

Report 09 ran 500 placebos under each design, and **every one of them used
`fes=("seller","week")` — model (i)**. Model (ii), the design §6c actually
reports, was left standing on the **three** placebos printed there. That gap is
closed by `_server/41_E1_pretrend_headline.py`, which runs the same 500 fake
event dates under **both** specifications for every design. Nothing else moves:
the matched seller list is computed once from the real pre-period and reused, so
only the fake event date varies.

**Control, run first.** The three placebos recorded in §6c were re-run:
**+0.4648 / +0.5076 / +0.7610** against recorded **+0.465 / +0.508 / +0.761** →
**CONTROL RECOVERED**. The instrument measures what the instrument that wrote
§6c measured, so the new numbers are comparable to it. Real betas reproduce §6c
exactly: model (i) **+3.8819**, model (ii) **+3.6365**.

### 10a. The 500-draw nulls, both models

| design | model | null mean | null sd | real β | percentile | p_placebo |
|---|---|---|---|---|---|---|
| unmatched | i seller+week | +1.2929 | 0.3617 | +3.8819 | 100.0% | 0.0000 |
| unmatched | **ii +stratum×week** | **+1.1156** | 0.3205 | +3.6365 | 100.0% | 0.0000 |
| B minus `n_markets` | i | +0.2748 | 0.6794 | +1.4199 | 96.8% | 0.0320 |
| B minus `n_markets` | **ii** | +0.6672 | 0.8803 | +3.6376 | 100.0% | 0.0000 |
| C activity + quality | i | +0.0111 | 0.9340 | +2.4426 | 100.0% | 0.0000 |
| C activity + quality | **ii** | +0.6606 | 1.2322 | +4.4911 | 100.0% | 0.0000 |
| D size + quality | i | −0.0694 | 0.6404 | +1.0424 | 97.8% | 0.0220 |
| D size + quality | **ii** | +0.1326 | 0.5419 | +1.3435 | 97.8% | 0.0220 |

### 10b. Three findings

**(a) §6c's justification for model (ii) fails.** §6c introduced stratum × week
FE to "absorb the differential trend that is a function of baseline size — the
exact defect that produced v1's spurious effect". Measured on the unmatched
sample, the drift goes from **+1.2929 to +1.1156**: **14% removed.** The
pre-trend is *not* a function of baseline size stratum.

**(b) On matched samples, adding stratum × week FE makes the null worse.**
B +0.27 → +0.67, C +0.01 → +0.66, D −0.07 → +0.13. Model (ii) is the
**worse-behaved** specification in every matched design — its 175 stratum × week
cells sit close to collinear with treatment inside 74–121 matched pairs.

**(c) §6c's "the largest placebo (+0.76) is 4.8× smaller than the event estimate
(+3.64)" is void.** A null with mean +1.1156 and sd 0.3205 places **all three
recorded draws below its own mean**: +0.465 (−2.03 sd), +0.508 (−1.90),
+0.761 (−1.11). The largest of three draws is a selection *minimum*; here it
understated the null by ~30%. The same objection voids "its CI [+0.02, +0.91]
excludes the event estimate" — one draw's CI is not the design's null.

### 10c. What survives, and what the number is

The event contrast is far outside the design's own pre-period behaviour:
**+3.6365 against a null of +1.1156 (sd 0.3205) is +7.9 null-sd**, p_placebo
0.0000. The event does add something.

But a null mean of +1.1156 **is** the parallel-trends violation, and under a
violated trend the DiD estimand is β_event + bias, with bias ≈ the drift. So the
event-attributable component is at most **+2.52 (= 3.6365 − 1.1156)** — and that
subtraction assumes the drift would have continued unchanged, which this design
cannot check. For scale: the treated pre-period mean is **1.153** reviews/week,
so the drift (+1.116) is **97% of the treated arm's entire pre-period level**.
§6c's contrast is dominated by pre-existing drift.

The designs whose nulls *are* well-behaved are the matched ones under model
(i): **C (+0.0111)** and **D (−0.0694)**. Their real betas are **+2.4426**
(p_placebo 0.0000) and **+1.0424** (p_placebo 0.0220).

**Revised §8 claim 3.** Was: *"Seller-level substitution at the intensive margin
is real and survives stratum×week FE and a placebo 4.8× smaller (+3.64
reviews/week vs a treated base of 1.15; CI excludes zero and excludes every
placebo)."* Now: **the effect is real and survives a 500-draw falsification on
the designs whose null sits near zero, at +1.0 to +2.4 reviews/week against a
treated base of 1.15. The +3.64 figure comes from a design carrying a
+1.1/week pre-trend and is not the effect size.**

### 10d. Corrections logged in this addendum

| id | correction |
|---|---|
| **C-82** | §6c 的规格理由**不成立**：stratum×week FE 只移除 **14%** 的漂移（+1.2929 → +1.1156），预趋势**不是**基线规模分层的函数 |
| **C-83** | **匹配样本上 model (ii) 的零假设更差**（B +0.27→+0.67、C +0.01→+0.66、D −0.07→+0.13）⇒ 该规格在匹配设计里是**更差**的规格，与 §6c 的取舍方向相反 |
| **C-84** | **「三个安慰剂里最大的那个」是选择最小值，不是零假设的刻画**：三次抽样全部落在 500 次零分布均值**以下**（−2.03/−1.90/−1.11 sd），把零假设低估约 30% ⇒ §6c「4.8× smaller」与其 CI 论证**作废** |
| **C-85** | **我的缺陷（覆盖缺口）**：报告 09 的 500 次安慰剂**只跑在 model (i) 上**，而报告 04 报告的是 model (ii)，其安慰剂证据只有 3 次 ⇒ 我一度用 model (i) 的 500 次零分布去给 model (ii) 的结论背书。已由 41_ 补齐（两种规格各 500 次） |
