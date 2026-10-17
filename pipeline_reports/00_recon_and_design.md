# CIS 00 — Workspace reconnaissance, data audit, and revised experimental design

**Date:** 2026-09-23/24
**Author of record:** autonomous agent session (author away; full delegation granted)
**Inputs read:** `D:\CIS\数据黑产韧性研究-冲刺计划书v5.docx` (the only file in the
workspace — converted to text and read line by line, 262 lines).
**Reference engineering conventions:** `D:\KBS-final` (ledger in `pipeline_reports\`,
staged reports `00_`…`05_`, `FINAL_SUMMARY.md`, `output\<dated packages>`,
per-artefact SHA-256, explicit identifiability/limitation disclosures).

---

## 1. What was asked

Complete **all** experiment pipelines of the sprint plan on the provided 4090 pod,
sync artefacts and results back to `D:\CIS`, hold the engineering standard of
`D:\KBS-final`, keep the science clean (no fabricated or silently repaired data),
monitor continuously, and work autonomously. Local link is a phone hotspot, so
prefer the pod's own bandwidth.

## 2. Target, in the plan's own words

*Complex & Intelligent Systems* (Springer, Q1). Three research questions —
RQ1 how to **measure** resilience, RQ1.5 whether persistence is **predictable**,
RQ2 which structural features **generate** resilience, RQ3 which interventions
**suppress** it — over 11 experiments E0–E9 plus a few-shot annotation appendix.

---

## 3. Environment: verified facts (not assumed)

Probed directly on the pod; carried by `_server/setup_env.sh` and the `rsc.py`
remote client.

| Property | Plan assumed | **Measured** |
|---|---|---|
| GPU | RTX 4090 24 GB | RTX 4090, 24564 MiB, driver 610.57.04 ✅ |
| CPU | — | AMD EPYC 7542, 14 vCPU |
| RAM | **100 GB** | **64 GB** ⚠️ |
| Disk | — | 100 GB overlay, 76 GB free after reclaiming the raw HTML crawl |
| OS / Python | — | Ubuntu 22.04.5; miniconda at `/usr/local/miniconda3`, env `py312` is Python **3.13** with no scientific stack → built a fresh `cis` env on Python 3.11 |
| Outbound net | — | direct **and** internal mihomo proxy (`:7890`). pypi/github/gwern/abuse.ch reachable; **archive.org unreachable on both routes**; mirror speeds measured: aliyun 8.2 MB/s ≫ pytorch.org 1.2 MB/s > tuna 0.5 MB/s |
| Tooling gaps | — | no `git`, no `unzip` in the image → used `codeload` tarballs and Python `zipfile` |

**C-01 (capacity).** The plan's 100 GB RAM figure is wrong; the pod has 64 GB.
This matters only for E8 (QLoRA + a 32B quantised model concurrently) and is
recorded now so that any later OOM is attributed correctly rather than blamed on
the code.

---

## 4. Data audit: what is actually reachable, and what it actually contains

Executed by `_server/fetch_data.py` + `_server/audit_dates.py`; raw output at
`results/00_date_audit.txt`. Coverage figures below come from re-parsing the
staged bytes, not from dataset documentation.

### 4.1 Social layer (marketplaces)

| Dataset | Rows | Columns of note | **Real date coverage** |
|---|---|---|---|
| AlphaBay `all_feedback.csv` | **1,217,387** | date, time, comment, rating, item | **2015-01-03 → 2017-01-28 (25 months)** |
| AlphaBay `active listings.csv` | 114,231 | 18 cols incl. `listed`, `vendor level`, `trust level`, `category1` | per-listing `listed` dates (range to be fixed in the data stage) |
| Agora 2014–2015 | 109,689 | Vendor, Category, Item, Price, Origin, Rating | **none — no date column** |
| Hansa listings 2016-12 | 14,773 | item, vendor, price, category, ships-from | scrape window 2016-12-11…13 |
| Hansa reviews 2016-12 | 51,553 | status, vendor, price, **+ a review-date column** | scrape ts 2016-12-13; true review dates to be extracted |
| Valhalla listings 2016-10 | 16,510 | item, vendor, price, origin | **none** |
| Kilos multi-market reviews | 235,904 | market, vendor, …, text | **none** |
| Kaggle drug listings | 194,433 | seller, price, ship_from, **source (market)** | **none** |

Kilos market mix: Empire 83,008 · Cannazon 55,740 · Apollon 41,456 · Cryptonia
35,223 · Samsara 10,237 · CannaHome 9,987.
Kaggle market mix: agora 124,842 · silkroad2 24,062 · nucleus 18,364 ·
evolution 15,772 · outlaw_market 5,756 · abraxas 4,087 · themarketplace 1,378 ·
1776 172.

### 4.2 Financial layer

Elliptic++ (9 Git-LFS objects, **2,206.1 MB**; the GitHub tarball ships only LFS
pointer stubs — a trap worth recording, **C-02**). Objects are fetched through
the public LFS batch API and each is verified against its LFS OID. Composition
once materialised: transactions (`txs_classes/features/edgelist`) and actors
(`wallets_*`, `AddrAddr/AddrTx/TxAddr` edgelists), 49 time steps spanning
2014–2019, with illicit/licit labels.

### 4.3 Infrastructure layer

| Feed | Rows | Fields | Real coverage |
|---|---|---|---|
| ThreatFox full dump | **105,999** IOCs | first_seen, ioc_value/type, threat_type, malware, last_seen, confidence, reporter | first_seen **2020-12-14 → 2026-09-23**; last_seen (37,366 non-null) **2026-03-23 → 2026-09-23** |
| URLhaus full dump | **58,310** URLs | date_added, url, **url_status**, **last_online**, threat, tags, reporter | date_added **2018-06-05 → 2026-09-23**; last_online 2026-06-25 → 2026-09-23; status **offline 42,272 / online 16,038** |

Both feeds are materially **recency-weighted** (ThreatFox: 26,832 of 105,999 IOCs
were first seen in 2026-09 alone) and ThreatFox's non-null `last_seen` values all
fall in the last six months. This is consistent with a rolling-retention feed
rather than a complete historical register, and it imposes **right-truncation /
length-biased sampling** on any survival estimate. It must be handled explicitly
(§6), not ignored.

---

## 5. Premise corrections against the sprint plan

These change the design, so they are stated plainly and early.

**C-03 — the Gwern archive does not cover 2016–2018.** Gwern's DNM archive is a
2013–2015 scraping programme ("from between 2013–2015 … I scraped/mirrored on a
weekly or daily basis"; coverage stated as *"Mirrors of ~89 Tor-Bitcoin darknet
markets & forums **2011–2015**"*). The plan's social-layer row reads
"Gwern DNM Archives 2016–2018 → Bayonet (2017.07) main natural experiment". The
archive cannot supply a Bayonet window.

**C-04 — the canonical 50 GB archive is unreachable from this pod.** It is
distributed primarily as an Internet Archive torrent; `archive.org` and its file
hosts return connection failure on both the direct and the proxied route. Only
Gwern's own HTTP tree (`gwern.net/doc/darknet-market/…`) is fetchable.

**C-05 — no reachable source gives a pre/post window around either headline
event.** Checked directly: Agora carries no date column at all; AlphaBay listings
carry `listed` dates but the scrape is a single 2017-01-28 snapshot; Valhalla and
Kilos carry no dates. So *neither Onymous (2014-11) nor Bayonet (2017-07) is
currently identifiable as a difference-in-differences natural experiment on the
social layer.* The one genuine longitudinal signal available is AlphaBay's
**feedback event stream, 1.22 M dated rows over 25 months**.

**C-06 — the AlphaBay feedback stream is survivorship-biased.** The scrape
records "every single listing … that Alphabay served up a valid page for" in
January 2017; feedback is attached only to listings that still existed then.
Monthly counts run 1, 2, 1,102, 4,897, 7,447 … 120,618 across 2015-01 → 2016-12,
and the early floor is far more plausibly explained by attrition of the host
listings than by a market that had ~1 transaction in its first month. **Any
trend or shock estimate from this series must be reported as an estimate on
surviving listings, not as market activity.**

**C-07 — infrastructure-layer survival is right-truncated (see §4.3).** Reported
persistence times measure "has not yet been pruned and has not been re-observed",
which is weaker than "remained online".

**C-08 — the plan's two supporting datasets are not yet located.** The ScienceDB
"电信诈骗案件集（571 起）" role-labelling ground truth and the "2025 年数据泄露态势
报告" external-validation curve have not been found on a reachable host. E4's
annotation target and E9's external anchor are therefore **provisional** and are
flagged for authored decision if no public substitute is found (see C-13).

**C-09 — plan arithmetic.** The matrix lists E0,E1,E2,E4,E5,E6,E7,E3,E8,E9 = 10
experiments, described as 11; the eleventh is the W5 few-shot annotation study.
Treated as 10 + 1 and reported as such rather than silently rounded.

---

## 6. Revised design

The plan's *questions* survive intact; its *identification strategy* does not.
The revision keeps every one of RQ1 / RQ1.5 / RQ2 / RQ3 and re-anchors each on
data that exists, with the strength of each identification stated up front.

**Organising claim (unchanged in spirit):** resilience is measured as a
multi-dimensional property of an ecosystem, and the three layers of a data
black-market stack are observed at three different levels of temporal
resolution. The paper's methodological contribution becomes a **resilience
measurement suite plus an explicit per-layer identifiability analysis** — which
is a stronger and more honest contribution than a single natural experiment
asserted on data that cannot support it.

### Layer roles

| Layer | Data | Temporal resolution | What it can identify |
|---|---|---|---|
| Social | AlphaBay 1.22 M feedback events; Agora/AlphaBay/Hansa/Valhalla/Kilos/druglisting cross-sections | 25-month event stream on survivors (C-06) + many cross-sections | structure ↔ redundancy ↔ centrality; vendor tenure survival |
| Financial | Elliptic++ (2014–2019, 49 steps, labelled) | true discrete time series, complete within window | node/cluster persistence **and its prediction**; recovery after disruption |
| Infrastructure | ThreatFox + URLhaus | continuous, 2018–2026, with online/offline status | post-takedown persistence and **revival**; right-truncated (C-07) |

### Experiment mapping

* **E0** — Infrastructure-layer resilience (survival + revival). **Strongest
  identification.** The two feeds are the only sources here that record the
  *same* entity transitioning between live and dead over years.
* **E1** — Multi-layer resilience profile: the six planned metrics
  (recovery time, functional redundancy, structural entropy, centrality
  redistribution rate, migration efficiency, connectivity resilience) computed
  per layer with layer-appropriate definitions.
* **E2** — Cross-event / cross-layer comparison, reframed from "Onymous vs
  Bayonet" (not identifiable, C-05) to **metric consistency across layers and
  across the disruption events that each layer does contain**.
* **E3** — Causal attribution (PSM + DiD + placebo). Re-anchored from the
  unavailable social-layer event window onto **disruptions observable inside
  Elliptic's 2014–2019 window and inside the IOC feeds**, with H1–H4 tested where
  the design is identifiable and reported as *not identifiable* otherwise.
* **E4** — Role-stratified survival (Kaplan–Meier + Cox) on vendor tenure and on
  IOC persistence; complementary log-log where the baseline hazard is steep.
* **E5** — Temporal GNN (TGN/TGAT) persistence prediction on Elliptic++, against
  GraphSAGE and a feature-only MLP baseline. The plan's target is a **horizon**
  label — verbatim `预测节点在 t+Δ 是否存续` — and the recurrence delivered in
  `05_` is that label at **Δ = 1** (`t1 - t0 >= 1` and `n_steps >= 2` select the
  same 61,487 rows, zero mismatches in either direction), i.e. the degenerate end
  of the axis, not a different quantity.
  ⚠ The plan **does not specify Δ**, so Δ is a free parameter: it must be
  pre-registered and **more than one value reported**, each with its censoring
  share (Δ=3 censors 6.83% of the cohort, Δ=5 11.81%, Δ=10 25.71%).
  ⚠ Whether censored rows are dropped moves the reported survival rate — at Δ=3
  illicit survival is 1.440% with censoring dropped and 1.318% without — so the
  treatment must be stated, not left implicit.
  ⚠ **The MLP baseline as naturally built would leak, and the leak would fire the
  plan's own fallback.** At Δ=1 the label *is* `num_timesteps_appeared_in >= 2` —
  a column of the provided table — so a table-feature MLP would score near-
  perfectly beside an honest GNN, and the plan's trigger ("GNN improves little
  over the feature baseline") would fire on an artefact rather than on the GNN.
  Both arms must be built point-in-time from the edge stream truncated at t0.
  ⚠ The plan's 串联逻辑 assigns "predictive validity for E3" jointly to **E5 and
  E7**; revised E7 is a measurement, so **E5 is the sole remaining leg** of that
  reviewer-facing triangulation — load-bearing, not one-of-eleven.
  The primary arm is CPU-runnable (C-104) and the script now exists; it had
  **not been attempted** when this document was first written.
* **E6** — Reframed from cross-layer alignment by graph embedding (Node2Vec /
  HGT) + ablation — **the two layers do not meet**: the social↔chain linkage
  recovers 3 addresses out of 124 social / 822,942 on-chain
  (`results/37_E3_bridge_probe.json`), which is not a substrate for alignment.
  Now: structural resilience of the labelled Bitcoin transaction graph (`06_`).
* **E7** — Reframed from HGT + attribution (SHAP / GNNExplainer) over bridging vs
  centrality — **the explanatory variable has no substrate** (market-level
  betweenness 0; cross-layer intersection 3). Now: takedown latency and host
  reconstitution in URLhaus (`07_`).
* **E8** — Causal-calibrated LLM-agent simulation with ranking bootstrap; the
  plan's own degradation path (prompt-driven agent + rejection sampling) is
  pre-registered as the fallback if QLoRA fit is not defensible.
* **E9** — External validation. **Anchor retrieved and byte-verified**, 9 issues
  (`results/43_E9_anchor_fetch.json`, C-102/C-104), **and the curve is now
  extracted — 9 periods, by two routes** (C-107):
  the text layer yields Jan–Apr (`results/51_E9_series.json`); the remaining five
  issues state the same two sentences but their bodies are **not text objects**,
  so they were recovered by rendering p.6 and OCRing it
  (`results/57_E9_ocr_p6.json`). The OCR route was admitted only after
  reproducing the four known values **4/4** — and that control caught a
  full-width-comma defect in the extractor that would otherwise have been
  recorded as "the report states no such number".
  ⇒ **The consolidated series is `results/67_E9_series_consolidated.json`**
  (`67_`, C-119). It supersedes `51_E9_series.json` for *reading the series*:
  that file still says `n_periods_with_values = 4` because it was written before
  the OCR route existed, and shipping it beside a nine-period claim would leave
  the reader to adjudicate two artefacts.
  **Every period carries the list of channels that assert its value**, and all
  four channels agree on all nine periods: `text_layer` (01–04 only),
  `ocr_p6_250` (9), `ocr_p6_200` (9), and a **human pixel read** of a 400-dpi
  render of p.6 at band y 0.02–0.32 (9), where the two headline sentences sit.
  ⚠ **Three of those four are programs reading a render.** Agreement among OCR
  passes is not independent corroboration (C-112); the pixel read is the channel
  that shares no blind spot with them. It was taken for **all nine** periods, not
  only where the others disagreed.
  ⚠ **The pixel channel was uniformised after the fact.** 2025-01/02 were first
  rendered at band 0.30–0.80 — a band that shows the publisher's *screenshot and
  its red box* but **not** the headline sentences; the 03/04 renders of C-112 are
  in the same position. Those readings are correct for what they measured (the
  screenshot value, which equals bullet 1 in 01/02 and bullet 2 from March on,
  C-112) but they measured **a different element**. Only the 0.02–0.32 renders
  feed the consolidated channel; the two sets must not be merged.
  ⚠ From 2025-11 the reports retitle themselves `全球数据泄露态势月度报告`
  (all earlier issues: `数据泄露态势月度报告`). Cosmetic, but it is a
  document-identity change in the series and is recorded rather than smoothed.
  ⚠ **Boundary, revised 2026-09-24 (C-122).** This entry previously read "OCR
  covers **p.6 only**, the data page under a templated layout confirmed on the
  four text-layer issues. Other pages of those five are **not** claimed either
  way." That is no longer the state: `59_E9_ocr_full.py` has now OCR'd **all
  pages** of all five text-layer-less issues (06/07/08/10/11), with **0
  zero-char pages**, no per-page error, and an observed exit marker
  (`RSC_EXIT=0`) — text in `results/59_ocr_full_text/`. So the *capability* now
  covers the whole document. What the series still rests on is narrower, and the
  revision does **not** widen any claim: the anchor is read from **p.6**, and the
  full text is not yet used for any claim. The five issues' remaining pages are
  now *available* rather than *unclaimed* — using them is a new decision, not an
  implication of this one.
  ⚠ **The per-category tab row is a third quantity, not the bullet** (C-121).
  `results/63_E9_query_labels.json` now reports it: the tab row's single non-zero
  value equals `effective` in 01–02, `high_value` in 03/06/07/08/11, and
  **neither** in 04 and 10 — the two exceptions are what show the equality is
  coincidence, not identity. In particular **2025-04's bullet reads `3，999`
  while `6663` sits in the tab row**, which is the mechanism of the C-112
  disagreement: `6663` is another element, not a second reading of the bullet.
  The version before C-121 could not report any of this — its adjacency regex
  bound a number to a category name only when the two were adjacent, and these
  tables render the labels and the counts as **separate runs**, so the field
  returned `[]` for all nine months while never having read a single category
  count.
  ⚠ **Boundary, revised 2026-09-24 (C-124/C-125) — the anchor is a QUERY, and
  the reports' own second series contradicts it.** Two things that this entry
  previously carried only as caveats are now measured.
  **(a) The p.6 figures are hit counts, and the query's window is on the page.**
  Each issue's p.6 carries a screenshot of the publisher's search UI: 2025-08
  reads `为您找到6826条匹配结果`, where **6,826** is exactly that issue's second
  headline figure. The convention is `[month-01, next-month-01)`, and
  2025-06/07/08 comply — each with three independent witnesses (lower bound,
  upper bound, and a span equal to that month's length). **2025-10 does not**:
  its window is `[2025-09-01, 2025-10-01)`, witnessed the same three ways,
  including a **30-day** span where October has 31. So the point labelled
  **2025-10 is a September observation**, and October is covered by no issue in
  the set. Independently, 2025-06 and 2025-07 report a **byte-identical**
  `effective` (1,140,767) under two blind-spot-independent channels, which a
  per-month count should not do. Artefact: `results/71_E9_query_windows.json`.
  ⚠ The window is **unread** for 01–04 (the string is absent from their text
  layer) and for 11 (only an OCR fragment survives, whose sign is not
  recoverable; it is kept in a separate `UNCLASSIFIED` bucket rather than
  guessed). **No claim is made about those windows** — unread is not absent.
  **(b) A second in-document monthly series moves OPPOSITE to the anchor.** The
  documents state `匿名社交社群情报总数量`, and in **both** months where the
  anchor moves sharply the two go opposite ways: 2025-08 the anchor falls 94%
  while the series rises 48%; 2025-11 the anchor rises 30% while the series falls
  85%. So C-109's "rise / repeat / collapse" is a property of the **selected**
  aggregate, not of the documents. This is C-113's caveat converted from an
  assertion into a measurement. Artefact: `results/69_E9_second_series.json`.
  ⚠ Neither series is claimed to be the true one and they are not comparable in
  unit or magnitude (份 vs 条, two orders of magnitude apart). The claim is
  narrower and it is the whole claim: **two in-document aggregates that a reader
  could call "the dark-web activity level" do not move together.**
  ⚠ Also measured: the United States row is stated **twice on one page in two
  element forms**, and the two **disagree** — 2025-06 reads 892 in prose against
  932 in the table, 2025-10 reads 1265 against 1267. This is the third instance
  of the C-112 family (2025-04's `3，999` vs `6663`), so "same page, same
  quantity, two different values" is a **stable feature of these files**, not one
  accident.
  ⚠ **Each report prints TWO series, and they behave differently (C-111).**
  `泄露数据的高价值买卖情报` covers all 9 periods and spans only **1.72×**
  (3,999–6,889) — usable as the comparison series.
  `深网和暗网有效情报` also covers 9 periods but spans **16.56×**
  (68,904–1,140,767), including a value **repeated in consecutive months**
  (06/07 both 1,140,767, confirmed source-level by an independent read) and a
  **16× collapse that partially reverses** (Jul–Aug). Those three moves are
  **unattributed** (C-109/C-111).
  ⇒ **E9b's comparison uses the second series; the first is reported separately
  as its own descriptive, unattributed series** — not dropped, since discarding
  it for being unstable would itself be selecting by result. An unattributed
  change in what was counted would otherwise enter the paper looking like a
  collapse in illicit activity. ⚠ The reports' own screenshots are **not
  evidence about either series** (C-112): they show a query-result count under a
  query whose shape changes in March, and the tab vocabulary (`数据泄露情报`,
  `暗网情报`) shares no term with the headline vocabulary (`深网和暗网有效情报`,
  `泄露数据的高价值买卖情报`), so a tab label cannot bear on which bullet a box
  shows. The boxed value coincides with a headline bullet in 8 of 9 issues and
  matches neither in 2025-10. ⚠ The report states **at least four section-level
  aggregates** (section 一's pair, a national subtotal on the same page, section
  二's per-incident counts, section 四's own monthly totals); E9 takes section
  一's pair, and **that choice is itself a selection that must be stated**.
  What remains of E9 is the comparison, which consumes E8's simulation side.
* **E10 (the plan's 11th)** — Few-shot role annotation with κ ≥ 0.75. The plan's
  named corpus **exists**: `10.57760/sciencedb.j00133.00466`, "571 条电信诈骗案例",
  open access, zh, 7 files (C-103). It is a case corpus, **not** role
  annotations. **The full OAI-PMH enumeration is now done** — 27,500 records /
  550 pages, 1,065 term hits — and of 21 fraud-term datasets only 2 also carry
  annotation terms, **neither of them telecom-fraud role annotation** (C-108).
  So there is no reusable labelled source in the holdings, and the κ ≥ 0.75
  labelling has to be produced, which needs an LLM (GPU blocked, C-27).
  ⚠ Scope: **metadata level only** — a dataset can label roles without saying so.

### Pre-registered hypotheses (unchanged)

H1 decentralisation ↑ → recovery time ↓ · H2 cross-layer bridging ↑ → recovery
time ↓ · H3 functional redundancy ↑ → functional recovery ↑ · H4 raw centrality
alone is **not** significantly related to resilience.

---

## 7. Open items for the author (raise, do not silently choose)

* **C-13** — substitutions for C-08's role-labelling ground truth and E9's
  external anchor.
* **C-05** — whether to *procure* a Bayonet-window dataset (a Kaggle DNM scrape or
  an author-supplied archive would restore the plan's headline experiment); absent
  that, E2/E3 report the reframed comparison.

## 8. Engineering conventions adopted

* Remote client `_tools/rsc.py`: base64 transport with **SHA-256 verified on both
  ends**; every non-trivial step is a **file pushed and run**, never a quoted
  one-liner (two shell hops mangle one-liners indistinguishably from real
  negatives).
* All raw data stays on the pod; only code, metrics, figures, reports and
  manifests sync to `D:\CIS`.
* Every acquisition records URL + bytes + SHA-256 in
  `data/_recon/acquisition_manifest.json`.
* Findings from this document are numbered `C-NN` and are never rewritten, only
  superseded by a new numbered entry — the same discipline the KBS ledger uses.

## 9. Immediate plan

1. Finish `cis` env; materialise Elliptic++ LFS; fix the three unresolved schemas
   (AlphaBay vendor column, Hansa review dates, Kilos columns).
2. Build the data layer → tidy tables in `work/` with a QC report.
3. Run E0 (strongest identification) end to end.
4. Then E1→E4, then the GPU layer E5–E7, then E8/E9 with declared fallbacks.
5. Sync results + write the stage reports as each stage closes.
