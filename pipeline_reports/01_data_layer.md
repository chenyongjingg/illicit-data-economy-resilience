# 01 — Data layer: what was acquired, and what it can and cannot answer

**Status:** complete. Consolidates the recorded QC instrument
(`results/01_data_qc.txt`, run 2026-09-23T16:48) with the later measurements in
reports 07–09. Builder: `_server/01_build_tables.py`.

Every number below is a reading from a recorded instrument run, not a summary
from memory. Where a builder annotation contradicts a later measurement, both
are shown and the contradiction is registered.

---

## 1. The built tables

`01_build_tables.py` writes seven parquet tables to `/root/cis/work/`:

| table | rows in → out | dropped | size |
|---|---|---|---|
| `ab_items` | 114,231 → 114,231 | — | 2.76 MB |
| `ab_feedback` | 1,217,387 → 1,217,387 | bad_date 1, bad_time 1 | 12.29 MB |
| `hansa_reviews` | 51,553 → 51,553 | — | 0.58 MB |
| `kilos_reviews` | 235,905 → 235,326 | not_6_columns 579 | 2.32 MB |
| `valhalla_listings` | 16,511 → 16,511 | — | 0.52 MB |
| `ioc_threatfox` | 105,999 → 105,999 | — | 5.05 MB |
| `ioc_urlhaus` | 58,310 → 58,310 | — | 2.84 MB |

Plus `EllipticPlusPlus-main/` (not built into a table): `Transactions Dataset/`
(`txs_features.csv` 695 MB, `txs_classes.csv`, `txs_edgelist.csv`) and
`Actors Dataset/` (`wallets_classes.csv` 822,942 addresses, three edgelists).

Column counts in the built tables exceed the source headers because the builder
adds derived columns (e.g. `ab_items` 18 source columns → 22 built; `ab_feedback`
5 → 6 with a parsed `ts`). **That is not a parser disagreement** — checked, not
assumed.

## 2. Time coverage — the constraint that shapes the whole design

| table | date column | span | usable? |
|---|---|---|---|
| `ab_items` | `listed` | 2014-12-21 .. 2017-01-28 | 769 d |
| `ab_feedback` | `ts` | 2015-01-03 .. 2017-01-28 | 756 d |
| `hansa_reviews` | `review_ts` | 2015-09-12 .. 2016-12-13 | 458 d |
| `kilos_reviews` | **`f2` (unix s)** | 2018-02-19 .. 2020-01-12 | 692 d |
| `valhalla_listings` | — | none | cross-sectional |
| `agora` | — | none | cross-sectional |
| `druglisting` | — | none | cross-sectional |
| `ioc_threatfox` | `first_seen_utc` | 2020-12-14 .. 2026-09-23 | see §5 |
| `ioc_urlhaus` | `dateadded` | 2026-06-25 .. 2026-09-23 | see §5 |

**The social-layer tables do not overlap in a way that supports a single
multi-market panel across eras.** AlphaBay ends 2017-01-28; the kilos panel
starts 2018-02-19. There is a 13-month gap, and the two events the plan names
fall in or beside it (report 10).

## 3. ★ Registered defects in the data layer

**C-76 — the builder's own annotation contradicts the data, and the annotation
was believed for a stage.** `01_build_tables.py:316` logs
`NOTE: no date column exists in this file -> cross-sectional only.` for
`kilos_reviews`. **`f2` is a unix timestamp spanning 2018-02-19 .. 2020-01-12.**
The note is wrong, and it is the kind of wrong that propagates: report 03 (E4)
and the first two E1 attempts treat kilos as cross-sectional. E1 v3 later used
`f2` correctly, so the *result* is sound — but the recorded annotation still
says otherwise and would mislead the next reader. **A recorded instrument output
is not self-validating** (G-39 family).

**C-77 — `hansa_reviews` vendor handles are masked 100%.** The QC instrument
records `vendor masked: 51553 / 51553 = 100.0%`. Values look like `F***e`. This
is *why* 36_ found `agora × hansa_reviews = 0` shared handles: it is not an
absence of common sellers, it is a **masked field**, and no handle-based joining
is possible against this table. Joining on it would have produced a false
negative silently.

**C-78 — a header row leaked into data.** `ab_feedback` rating values include
`{'rating': 1}` alongside `good/bad/neutral` — one row where the header itself
became a record. Volume 1 of 1,217,387. Registered, not repaired: editing a
built table would invalidate the QA-run hashes.

**C-79 — one row's review text became a market label.** `kilos_reviews` markets
carry a seventh value that is an entire review paragraph
(`'\nStealth is spot on. Order was so overweight…'`, n=1) — a parse failure on a
ragged line. It is excluded by every analysis that filters to the five named
markets, which is why it never affected a result, but it is present in the table.

**C-80 — `ab_items.listed_raw` is null in all 114,231 rows.** Every row. The
derived `listed` is fully populated, so the raw field is dead weight; an
analysis that reached for `listed_raw` would find nothing and might read that as
missing data rather than as an unused column.

**C-81 — script directory sprawl.** Stage scripts live in three places on the
pod: `/root/cis/scripts/` (through `35_`), `/root/cis/_server/` (`36_` onward,
38 files), `/root/cis/code/`, plus one stray at `/root/cis/18_probe_elliptic.py`.
`35_gpu_diag.py` was looked for in `_server/` and was in `scripts/`. **The same
name can resolve to different paths depending on the directory assumed** —
the "同名不同物" family. Consolidated recommendation, not yet executed.

## 4. Elliptic: labels and an anonymised time axis

| class | meaning | n |
|---|---|---|
| 1 | illicit | **14,266** (1.73%) |
| 2 | licit | 251,088 (30.5%) |
| 3 | unknown | 557,588 (67.8%) |
| | total | 822,942 |

**★ Elliptic's time axis is ordinal, not calendar.** `txs_features.csv` carries
integer time steps, so the financial layer **cannot be anchored to a real-world
event at all**. This is independent of the address-intersection result: even a
perfect cross-layer address link (which does not exist — report 08 §1) could not
be placed on a common timeline. **E2 and E6 both require a calendar anchor and
neither can have one from this source.**

## 5. Infrastructure layer: dual semantics and a pruning boundary

`ioc_urlhaus` (58,310 rows): `url_status` offline 42,272 / online 16,038
(27.5% censored); `last_online` null in 8,391 rows = **19.85% of offline rows**.

Report 07 §1 established that `last_online` means **two different things in one
column** — crawl stamp for `online` rows, removal time for `offline` rows — and
that removals exist only from a **one-day-wide boundary**
(2026-06-24 → 2026-06-25). The QC instrument independently corroborates the
boundary: its recorded `last_online` window begins **2026-06-25 16:46:29**.
Two instruments, different code, same boundary.

`ioc_threatfox` (105,999 rows): `ioc_type` domain 44,545 / ip:port 25,049 /
sha256 16,558 / url 11,773 / md5 4,552 / sha1 3,522; `first_seen_utc`
2020-12-14 .. 2026-09-23; `last_seen_utc` populated in only 44,533 rows and
**null in 61,466 (58%)**. The 58% null on the second timestamp is the
informative-missingness problem report 07 §2 bracketed rather than dropped.

## 6. What the data layer can and cannot support

**Can support:** takedown/reconstitution survival analysis on URLhaus (report
07); seller-level panel DiD on the kilos five-market panel with `f3` rating as
an outcome and market labels as a moderator (reports 09); AlphaBay item↔feedback
linkage (46.0% of items join); Elliptic graph structure (reports 06).

**Cannot support:** any cross-layer address bridge (report 08 §1 — 124 candidate
addresses, 3 intersections, all adjudicated non-transactional, none illicit);
any calendar-anchored use of Elliptic (§4); E2's two-event comparison (report
10); H3's functional redundancy, for which no category column exists in the
panel that carries the outcome (C-45).
