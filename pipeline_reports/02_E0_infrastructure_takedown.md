# Stage 2 — E0: infrastructure takedown latency (URLhaus)

**Target question.** RQ1 at the infrastructure layer: once a malicious URL is
publicly listed, how long does it stay online, and what predicts a longer life?

**Artefacts.** Code `_server/04_E0_infra_takedown.py`, `_server/05_E0_robust.py`
(validity checks), `_server/06_E0_figure.py`. Output
`results/04_E0_infra_takedown.{txt,json}`, `results/05_E0_robustness.{txt,json}`,
`results/figs/E0_infra_takedown.{png,pdf}`. Input `work/ioc_urlhaus.parquet`
(58,310 rows), built by `_server/01_build_tables.py`.

---

## 1. What E0 measures, and why it is restricted

URLhaus is a rolling-retention feed. Cross-tabulating `date_added` year against
`url_status` shows **100% of every 2018–2025 cohort is `online` and none is
`offline`**; offline rows exist only in 2026, and `last_online` is confined to an
89-day window. The feed keeps an old URL only while it is still up.

Consequence: `last_online − date_added` computed over the whole feed measures
**URLhaus's retention policy**, not takedown speed. The analysis is therefore
restricted to URLs added inside the window (2026-06-25 → 2026-09-23), where a
takedown occurring after listing would have been recorded.

| | |
|---|---|
| feed rows | 58,310 |
| added inside the window | 44,630 (76.5%) |
| … of which offline with **no** `last_online` (takedown known, time unobserved) | 8,368 (18.7%) |
| … offline with `last_online` **before** `date_added` | 0 |
| **timing-analysable cohort** | **36,262** |
| events (taken down) | 33,786 |
| censored (still online at feed end) | 2,476 |
| event rate | **93.2%** |

The 8,368 untimed rows are **events**, so dropping them biases survival upward.
They are bracketed rather than dropped silently (§4).

## 2. Headline result

Kaplan–Meier on the 36,262-URL cohort:

| t | 0.5 d | 1 d | 2 d | 7 d | 14 d | 30 d |
|---|---|---|---|---|---|---|
| S(t) = still online | 0.861 | 0.606 | 0.387 | **0.158** | 0.100 | 0.050 |

**Median time online after listing: 1.36 days (32.7 h).**

So takedown is fast for most listed URLs — half are gone within a day and a half —
and there is a long tail: ~5% remain online after a month.

## 3. Two features of the feed that constrain the design

Both were found by inspection and are reported as findings, not worked around:

- **`threat` is degenerate.** The cohort holds exactly **one** value,
  `malware_download` (36,262/36,262). A threat-type stratum does not exist here.
- **87% of URLs are bare IP literals** (31,527/36,262), not domain names. So
  "hosting concentration" is properly an **IP-block** question, which is also the
  unit a takedown acts on. The infra block is the `/24` for IP literals and the
  registrable host otherwise: 9,303 distinct blocks.

The tag vocabulary substitutes for the missing threat column, but it **is not one
partition**. Tags mix six kinds of statement:

| role | examples (count in cohort) |
|---|---|
| payload | `elf` 19,797 · `exe` 731 · `sh` 524 |
| arch | `32-bit` 10,683 · `mips` 8,248 · `arm` 3,197 |
| **family** | `mozi` 15,830 · `mirai` 15,022 · `gafgyt` 332 · `connectwise` 416 |
| url_character | `botnetdomain` 1,981 · `opendir` 1,376 |
| **provenance** (who found it) | `censys` 893 |
| submitter tooling | `ua-wget` 8,257 |
| placeholder | `none` 3,696 |

E0's first pass built a "malware family" variable from this vocabulary and got
levels including `censys`, `botnetdomain`, `opendir` and `ua-wget`. Three of those
are not malware families. The corrected analysis below treats each tag as its own
binary stratum, which asserts no partition.

## 4. Group contrasts (log-rank, each tag binary)

| tag | role | n with | median with | median without | S(7d) with | S(7d) without | χ² |
|---|---|---|---|---|---|---|---|
| `mozi` | family | 15,830 | **1.13** | 1.81 | **0.051** | 0.242 | 2786.6 |
| `mirai` | family | 15,022 | **1.66** | 1.26 | **0.215** | 0.117 | 481.7 |
| `32-bit` | arch | 10,683 | 1.24 | 1.46 | 0.056 | 0.202 | 1135.6 |
| `mips` | arch | 8,248 | 1.13 | 1.49 | 0.051 | 0.190 | 1056.4 |
| `arm` | arch | 3,197 | 1.59 | 1.35 | 0.124 | 0.161 | 11.2 |
| `botnetdomain` | url_character | 1,981 | **0.68** | 1.39 | 0.087 | 0.162 | 152.6 |
| `opendir` | url_character | 1,376 | 1.80 | 1.35 | 0.298 | 0.152 | 77.7 |
| `censys` | **provenance** | 893 | **3.84** | 1.35 | **0.452** | 0.150 | 371.0 |
| `ua-wget` | submitter | 8,257 | **2.35** | 1.30 | **0.324** | 0.107 | 1427.4 |
| `exe` | payload | 731 | 1.01 | 1.37 | 0.282 | 0.155 | 31.5 |
| `elf` | payload | 19,797 | 1.35 | 1.38 | 0.166 | 0.146 | **1.4 (p=0.24)** |

Two readings matter here.

**The family contrasts are the substantive ones.** Mozi-tagged URLs are taken down
roughly twice as fast as the rest (median 1.13 vs 1.81 d; only 5% survive a week
against 24%). Mirai-tagged URLs go the other way (1.66 vs 1.26 d). `elf` — the
most common payload tag — carries **no** signal at all.

**But the largest contrasts are measurement artefacts, not malware properties.**
`censys` (3.84 vs 1.35 d) and `ua-wget` (2.35 vs 1.30 d) describe *how the URL
entered the dataset* — a scanner found it, or a tool submitted it. A URL that a
scanner discovered is one that stayed up long enough to be scanned. Reading
"censys URLs are more resilient" as a property of the infrastructure would be
reading the selection rule as the phenomenon. §5 tests this directly.

## 5. Robustness: the concentration result does not survive

**5a. Dependence.** 8,755 hosts carry ≥2 URLs, covering 31,548 URLs (87.0% of the
cohort). Within such a host:

| shared value within host | share |
|---|---|
| `date_added` | **72.0%** |
| `duration` | 3.5% |
| `last_online` | **0.9%** |

So co-hosted URLs are **registered in bulk at the same instant** but are probed
individually — the event times are genuinely distinct, and the non-independence is
in the entry time, not the takedown time. This was the thing most likely to make
the whole analysis an artefact, and it is not.

**5b. The block-size gradient is descriptive only.** By URLs sharing a block:

| URLs in block | 1 | 2 | 3–5 | 6–20 | 21–100 | 100+ |
|---|---|---|---|---|---|---|
| n | 2,583 | 7,886 | 6,513 | 8,795 | 4,472 | 6,013 |
| median (d) | 1.06 | 1.58 | 1.23 | 1.31 | 1.54 | 1.60 |
| S(7d) | 0.158 | 0.095 | 0.082 | 0.132 | 0.281 | 0.270 |

Omnibus log-rank χ² = 856.3 (5 df, p ≈ 7.6e-183). The gradient is **non-monotone**
and the extremes move opposite ways, which is already a warning.

**5c. Cluster-robust standard errors destroy it.** `log1p(URLs in block)` is
constant within a block, so clustering by block is the correct variance model for
it. Doing so inflates its standard error **14.4×**:

| covariate | IID se | block-clustered se | ratio |
|---|---|---|---|
| `log_block` | 0.00730 | **0.10539** | **14.44×** |
| `has_botnetdomain` | 0.00574 | 0.05040 | 8.79× |
| `has_opendir` | 0.00581 | 0.03921 | 6.75× |
| `has_censys` | 0.00598 | 0.03340 | 5.58× |
| `has_elf` | 0.01115 | 0.05400 | 4.84× |
| `n_tags` | 0.01148 | 0.05409 | 4.71× |
| `log_reporter_volume` | 0.00709 | 0.02745 | 3.87× |
| `has_mirai` | 0.00687 | 0.02350 | 3.42× |
| `has_mozi` | 0.00837 | 0.02558 | 3.06× |

With block-clustered errors the concentration coefficient is **not significant**
(HR 1.0572 per SD, se 0.0409, **p = 0.17**), against p ≈ 0 under IID errors.

**5d. The provenance contrast is absorbed by the submitter.** 114 reporters filed
the cohort and the top five filed 72.6%; `geenensp` alone filed 29.6%. Re-fitting
with reporter as a stratum (which compares only within submitter, absorbing the
submission pathway entirely):

| covariate | IID HR (p) | reporter-stratified HR (p) |
|---|---|---|
| `has_mozi` | 1.451 (<1e-4) | **1.407 (<1e-4)** |
| `has_botnetdomain` | 1.167 (<1e-4) | **1.140 (<1e-4)** |
| `has_censys` | 0.949 (<1e-4) | **0.996 (p = 0.71)** |
| `has_mirai` | 0.990 (p = 0.15) | 0.969 (<1e-4) |
| `has_elf` | 1.012 (p = 0.30) | 1.018 (p = 0.16) |
| `log_block` | 1.057 (<1e-4) | 1.067 (<1e-4) |

The `censys` "effect" **vanishes** (0.949 → 0.996, p = 0.71): the apparent
resilience of scanner-discovered URLs was the submitter, not the URL. The family
contrasts survive unchanged.

**5e. Proportional hazards is violated.** In E0's first multivariable Cox, 12 of 17
covariates fail the Schoenfeld (rank) test at p < 0.05. At n = 36,262 that test is
over-powered and small violations become significant, but the count is too high to
ignore. Every HR above is therefore a **time-averaged** hazard ratio; the
assumption-free evidence in this report is the KM medians and S(7d) columns, and
those are what §4's conclusions rest on.

**5f. No temporal trend.** Using a fixed 14-day horizon restricted to cohorts with
a full 14 days of follow-up (n = 30,015), the takedown-within-14-days rate runs
84.0–93.7% across 11 weeks with no direction: **OR = 1.0016 per day
[0.9999, 1.0034], p = 0.070**.

## 6. Verdict

**Established.**
- Median time online after listing is **1.36 days** (n = 36,262; 93.2% events);
  S(1d) = 0.606, S(7d) = 0.158, S(30d) = 0.050. Fast for the bulk, with a ~5% tail
  surviving beyond a month.
- Survival differs **strongly and robustly by malware family tag**: Mozi URLs are
  removed about twice as fast as the rest (HR ≈ 1.41 within submitter), Mirai URLs
  more slowly.
- URL shape matters: `botnetdomain` URLs are removed fastest (median 0.68 d).
- Payload tag `elf` — the commonest — carries no signal.
- **No trend** in takedown speed across the 89-day window.

**Explicitly not established.**
- **Any effect of infrastructure concentration on survival.** The descriptive
  gradient is real but non-monotone, and it does not survive block-clustered
  standard errors (p = 0.17). E0 declines this claim. This is the hypothesis the
  sprint plan expected E0 to support; it does not.
- **Any resilience advantage of scanner-discovered URLs.** Absorbed by submitter.
- **Absolute survival times.** `last_online` is the last *sighting*, not the
  takedown instant, so every duration is a **lower bound**; the detection cadence
  is unpublished.
- **Anything long-run.** The retention window forbids multi-year persistence
  claims (C-29).
- **Causality.** These are associations among co-observed URL features.

## 7. Sensitivity: the 8,368 untimed events

Placing them at both ends of their feasible interval [0, `t_cens`]:

| placement | n | median | S(7d) |
|---|---|---|---|
| all at t = 0 (fastest) | 44,630 | 0.96 d | 0.128 |
| **primary (excluded)** | **36,262** | **1.36 d** | **0.158** |
| all at t_cens (slowest) | 44,630 | 1.94 d | 0.310 |

The primary estimate lies inside the bracket, and the bracket is wide (0.96–1.94 d,
±0.4 d). The **ordering** conclusions in §4–§5 are unaffected because the untimed
rows are spread across all groups, but the headline median should be quoted with
this interval.

---

## Corrections recorded during E0

- **C-32.** The tag vocabulary is **not one partition**: it mixes payload, arch,
  malware family, URL character, detection provenance and submitter tooling. E0's
  first pass built a "malware family" variable whose levels included `censys`,
  `botnetdomain`, `opendir` and `ua-wget`. Caught by listing the vocabulary instead
  of trusting the construct.
- **C-33.** `none` is a **placeholder** meaning "no tags", not submitter tooling.
  Mislabelled on the first pass; it inflated the tool-submitted group from 8,257 to
  11,117. Label only — the median contrast (2.12 vs 1.33 d) is unaffected.
- **C-34.** `log1p(URLs in block)` is a **block-level** covariate; IID standard
  errors understate its SE by **14.4×**. The concentration result is not
  significant under the correct variance model. **Any cluster-constant covariate in
  this project must be reported with cluster-robust SEs.**
- **C-35.** 18.7% of the window cohort is **offline with no `last_online`** — these
  are events with unobserved times. An earlier check reported "negative observed
  durations: 0" while never testing for missingness, so the gap was invisible.
  Now counted and bracketed.
- **C-36.** `pod_status.sh` reported `BAD : lifelines (ModuleNotFoundError)` for
  two runs while lifelines worked. It was printing the **last line of
  `setup_env.log`**, written before those packages were installed — a record of the
  past read as present state. The snapshot now imports the packages live.
