# 03 — E4: AlphaBay listing survival

**Status:** complete. Code `_server/10_E4_ab_survival.py`; outputs
`results/10_E4_ab_survival.{txt,json}`, `results/figs/E4_ab_survival.{png,pdf}`.
Validation upstream: `_server/09_validate_ab_linkage.py`, `results/09_ab_linkage.txt`.

---

## 1. What the plan asked for, and what replaced it

The sprint plan specified **vendor-tenure survival**. Three things made that
impossible, and each was checked rather than assumed:

1. **AlphaBay has no vendor identifier (C-26).** Vendors are not recoverable from
   text either: only 8.9% of headings end in a parenthetical, and the commonest are
   `WARRANTY`, `FREE SHIPPING`, `ESCROW` — marketing phrases, not seller names.
2. **`ab_items.tenure_days` is not an outcome.** It carries `tenure_days` and
   `censored`, which look like a ready-made survival frame. `censored` is `True`
   for **all 114,231 rows** — zero events. `tenure_days` is only the age of a
   listing at the scrape date: a **backward recurrence time**, length-biased by
   construction. A Kaplan-Meier curve fitted to it estimates nothing.
3. The salvageable outcome is **time from listing to the item's first feedback
   event**, which `ab_feedback` timestamps.

## 2. The linkage was verified before it was used

`09_` tested the three things a join like this must not be assumed to satisfy:

| Check | Result |
|---|---|
| `n_feedback` counts the feedback rows actually present | exact match **52,494 / 52,494**; (no rows) XOR (`n_feedback==0`) = **0** |
| feedback events fall after their listing date | **0** negative durations |
| `item_number` identifies one entity | 114,231 distinct values in `ab_items` |

## 3. Exclusions, counted

| Excluded | n | Why |
|---|---|---|
| leaked header row | **1** | `rating == 'rating'`, `ts` NaT — a header row inside the data |
| feedback after the dump date | **57** | a file dated 2017-01-28 containing later timestamps is internally inconsistent, and the dump date is also the censoring date |

Retained: **1,217,329** feedback rows.

## 4. Headline

Unit = listing. Event = first recorded buyer feedback. All items censored at
**2017-01-28**. n = **114,231**; events **52,484 (45.9%)**; censored 61,747.
Listings span 2014-12-21 → 2017-01-28.

| t | S(t) |
|---|---|
| 1 d | 0.9485 |
| 3 d | 0.8739 |
| 7 d | 0.8059 |
| 14 d | 0.7422 |
| 30 d | 0.6668 |
| 60 d | 0.6030 |
| 90 d | 0.5679 |
| 180 d | 0.5137 |

**KM median: 222.9 days.** Among listings that ever received feedback, the median
is **10.8 days**.

> The gap between those two numbers is the censoring, not a contradiction. 222.9 d
> is the median over all listings counting the censored ones as "not yet"; 10.8 d
> is a naive median over the subset that has an event. Quoting either without
> saying which is which misstates the result.

## 5. ★ Correction C-40 — the outcome is not "first transaction"

This run originally labelled the outcome *time to first transaction*. That label
overstates it, and the data says so directly:

- listings with `sold > 0` (units demonstrably moved): **70,401**
- listings with ≥1 feedback: **52,484**
- ⇒ **17,917 listings (25.4% of those that moved) sold with no feedback at all**

So a listing that transacted may never enter the event set, and the "event rate"
of 45.9% understates the true transaction rate (≥61.6% by `sold>0`). The outcome
is **time to first recorded buyer feedback** — a proxy that misses at least a
quarter of movements, and misses them non-randomly (silent buyers are not a random
sample of buyers). Everything below is reported under the corrected label.

## 6. Group contrasts (log-rank; all p < 1e-90)

**Fastest to first feedback**

| Group | n | median d | S(30 d) |
|---|---|---|---|
| Drugs & Chemicals | 76,747 | 93.8 | 0.619 |
| Physical package | 84,486 | 107.8 | 0.628 |
| ships to United States | 16,441 | 22.1 | 0.460 |
| ships to United Kingdom | 3,201 | 23.6 | 0.474 |
| ships to Australia | 4,867 | 25.5 | 0.477 |
| origin Australia | 5,309 | 26.3 | 0.479 |
| origin United States | 22,796 | 34.8 | 0.516 |

**Slowest** — median not reached within the window (`inf`): Digital goods,
Digital Products, Fraud, Guides & Tutorials, Counterfeit Items, Services;
`ships to Worldwide` (n=68,614, S(30 d)=0.756) and `origin Worldwide` (n=46,114,
S(30 d)=0.772) never reach the median. Price is **non-monotone** (Q1 749.9 d, Q2
57.6 d, Q3 102.9 d, Q4 `inf`) — the quartiles do not order, so no monotone price
claim is made.

## 7. Cox models

**Pre-listing covariates only (safe).** n=114,231, events=52,484, concordance
**0.6657**. HR per SD:

| covariate | HR | 95% CI | p |
|---|---|---|---|
| price_log | **0.820** | 0.811–0.828 | <1e-4 |
| qty_log | **0.802** | 0.796–0.809 | <1e-4 |
| heading_len | 1.061 | 1.052–1.071 | <1e-4 |
| blurb_len | 1.047 | 1.037–1.056 | <1e-4 |
| n_tags | 1.011 | 1.001–1.020 | 0.024 |
| category1_Drugs & Chemicals | 1.144 | 1.112–1.177 | <1e-4 |
| category1_Fraud | 1.102 | 1.076–1.128 | <1e-4 |
| category1_Digital Products | 0.902 | 0.883–0.921 | <1e-4 |
| shipsto_United States | 1.126 | 1.085–1.169 | <1e-4 |
| shipsto_Worldwide | 0.871 | 0.829–0.915 | <1e-4 |
| origin_Worldwide | 0.769 | 0.733–0.807 | <1e-4 |

Direction: **higher price and larger quantity go with slower feedback**; longer
text goes with faster. These are associations on observational listing attributes,
not effects.

**★ The proportional-hazards assumption is violated in 19 of 24 covariates**
(rank test, p<0.05), and 25 of 26 in the extended model. All HRs above are
**time-averaged**, and the Kaplan-Meier medians in §6 — which assume nothing about
PH — are the assumption-free evidence. A Cox HR that violates PH should not be
read as "a 20% lower hazard" at any particular time.

**Flagged, not used causally.** `vendor_level` enters at HR **1.551**
(1.531–1.572). But it is plausibly a **scrape-time** attribute, i.e. measured
*after* the outcome, so it is reported in a separate clearly-marked model and no
causal reading is offered. `trust_level` is null (0.990, p=0.12).

## 8. What E4 does not establish

- **Vendor-level anything** — no vendor key (C-26).
- **Listing survival in the takedown sense** — every item is censored at one
  instant, so no listing *end* is ever observed.
- **Anything after 2017-01-28.**
- **Causal readings of `vendor_level` / `trust_level`** — may be post-outcome.
- **Correct standard errors.** The SEs assume independent listings. With no vendor
  key, clustering by seller is impossible, and the true SEs are **larger** than
  reported. Per C-34 this is the same failure mode that killed E0's headline, so
  it is stated rather than left implicit.
- **"First transaction."** See C-40 — the outcome is first *recorded feedback*.

## 9. Corrections logged

| id | correction |
|---|---|
| C-26 | AlphaBay carries no vendor identifier; E4's unit must be the listing |
| C-40 | the outcome is time to first **recorded feedback**, not first transaction; ≥25.4% of movements produce no feedback |
