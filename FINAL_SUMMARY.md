# CIS sprint — FINAL SUMMARY

**Date:** 2026-09-24
**Input:** `数据黑产韧性研究-冲刺计划书v10.md` — the live plan, shipped in this package
as `plan/`. The sprint was launched 2026-09-24 against v5 of that plan (11 experiments:
E0–E9 plus a few-shot annotation appendix E10); v5–v9 are void per v10's own footer.
**Conventions:** those of `D:\KBS-final` — ledger in `pipeline_reports/`, numbered
stage reports, dated `output/` packages, per-artefact SHA-256, explicit
identifiability and limitation disclosure.
**Delegation:** the author was away and delegated all decisions, with the standing
constraints *保持科学性*, *严禁虚假声明、数据伪造损坏*, and *降低对本地网络的依赖*.

This document is the index. Every claim below points at a stage report and a
result file; nothing here is asserted on the strength of this summary alone.

---

## 0. Coverage against the plan

| plan item | status | report | result files |
|---|---|---|---|
| **E0** infrastructure-layer survival + revival | **RUN** | `02_E0_infrastructure_takedown.md` | `04_*`, `05_*` |
| **E1** multi-layer resilience profile | **RUN** (headline revised) | `04_E1_social_substitution.md` + **§10** | `14_*`–`17_*`, `41_*` |
| **E2** cross-event / cross-layer comparison | **INFEASIBLE — reported, not substituted** | `10_E2_feasibility.md` | `40_*` |
| **E3** causal attribution (PSM + DiD + placebo) | **RUN in part** (H1, H4) | `08_E3_feasibility.md`, `09_E3_mechanism.md` | `36_*`–`39_*` |
| **E4** role-stratified social survival | **RUN** | `03_E4_social_survival.md` | `09_*`, `10_*` |
| **E5** temporal GNN persistence prediction | **RUN — the artefact has LANDED and the plan's claim is NOT SUPPORTED by it** (rc5 landed 2026-09-24 05:42Z; `results/53_E5p_result.json`, sha256 `95f1416bf027f151…`, `status='ok'`, `seconds_total=2632.5`, CPU-only, three arms at Δ∈{1,3,5}; the earlier text — "the prediction arm is IN FLIGHT … exists **neither locally nor on the pod** (C-120)" — was a **timestamped reading taken at 01:53 UTC and is superseded**). The C-159 feature-filter repair is **confirmed** (`feature verify 300/300`, `n_exact_match=300`, `n_mismatch=0`). But on the judged within-t0 metric **TGN does not beat either baseline at any Δ** (vs MLP −0.046…−0.053; vs GraphSAGE −0.014…−0.023), and the label-shuffled control sits at **0.714/0.712/0.716**, **outside the null band derived from the bin structure at every Δ** ⇒ the within-t0 metric itself still admits ≈0.21 of leak, and the arms' margin over that control is not evidence of learned persistence. ★**（C-202，2026-09-24，rc6 落地后追加）**：未训练模型的地板**已按架构分别测出**（rc6 预注册项 `untrained_floor`）：mlp `0.4424/0.3927/0.5378`、graphsage `0.5321/0.5425/0.5163`、tgn `0.5329/0.3826/0.4333`（Δ=1/3/5）。**没有任何一个未训练读出达到 0.71**（最大 `0.5425`），mlp 与 tgn 在部分 Δ 上**低于 0.5** ⇒ **对照的 0.71 不是该口径的结构性地板**，本句的「仍容许一份可观的泄漏」**据此加强、不予撤回**。（★**本条读法已被 C-235 更正**：`0.21` **不是泄漏量**，见 C-234；此处**保留原文**不改写，以保证引用仍能对得上。）**但两点须并记**：①「约 0.21」是相对 **0.5** 量的，而 rc6 显示未训练地板**并非在每个架构上都恰好是 0.5** ⇒ 泄漏的**存在与方向**稳健（对照 `0.711–0.716` vs 未训练上界 `0.5425`），**量值 0.21 是近似的**；② **预注册的 P2（未训练 mlp 落在 `0.5±0.05`、至少 2/3 个 Δ）未成立（1/3）**，且**预注册 §4 的两条子句在本结果上互相矛盾**（条件「P2 或 P3 不成立」成立，而该分支的理由「某架构未训练到 ≳0.6」不成立）⇒ **该情形未被预注册预见，按差额登记、不择一子句**。 `75_E5p_verify.py`: **FAIL — 5 value checks did not hold, 0 GAPs** ("neither 'done' nor 'absent'"). Not a reframe | `05_E5fin_recurrence.md` + **`16_E5p_temporal_gnn.md` §9(i)** | `19_*`–`24_*`, `53*`, `75_*`, `77_*` |
| ↳ **C-235** (2026-09-24, rc7 修复重跑落地后追加) | ★**上格那句读法更正。** 「对照高出 0.5 约 0.21」**不是**「≈0.21 的泄漏」：那 0.21 是**无标签信息**时（打乱标签、**同一**特征矩阵）就能达到的读数 ⇒ 它属于**特征侧可预测性＋该口径的构造**，**不是**可归因于真标签的泄漏量。可归因于**真标签**的量是**同特征下 `true − shuffled`**，**两个对象**、均已逐字节复算：**① 臂** `arms.mlp_feature_only.by_delta[D].within_t0_auc.weighted` − `leakage_check.shuffled_label_control.test_within_t0_auc_by_delta[D].weighted` ＝ **+0.050821305 / +0.050867940 / +0.048609102**（Δ=1/3/5）；**② 归因表基线行** `results/_e5p_landing/53_E5p_leak_attrib.json` → `rows["ALL10 as-built (baseline row)"].readings.{true_labels,shuffled}[D].weighted` ＝ **+0.052775475 / +0.054860133 / +0.057782667**。**两者都 ≪ 0.21**（差一个量级） ⇒ 正确读法：**该口径在特征侧自带约 **0.21** 的无标签区分力（这是**方法学**发现，不是泄漏的量）；**真标签的增量约 0.05**。★**本更正的出处**：台账 **C-234**（2026-09-24，第三次自纠，方向与 C-233 **相反**）；**C-235 是它的落地批次**（rc7 修复重跑 ＋ 验收器修 ＋ 正本传播）。★**两条限度必须与上面并记**（二者都已在台账 C-234 ⑥ 登记）：①「**成因是特征侧可预测性**」目前是**推断、不是实测** —— 已登记 `79_E5p_feature_attrib.py`（每一列**单独**对**真标签**取 within-t0，**未跑**），**若某列单独就 ~0.6，该归因才算测出来**；② `true − shuffled` 的约 0.05 是**两个单点**（臂、归因表基线行），**其零分布尚未建** ⇒ 只作**量级读数**，**不主张显著**。**不得**再把「读数 − 0.5 ≈ 0.21」写成泄漏量。本格**不撤回**「该口径的绝对高度不能单独支撑持续性主张」。 | —— | `results/53_E5p_result_rc7_lean4.json` / `.txt`（**修复重跑**，`sha256 83b12e0b…`）、`results/53e4_lean4_receipt.json`（**验收**：收据 13 条全 PASS，其中 1 条自标 `discriminative: false` ⇒ **会响的是 12 条**；两组均 PASS，exit 0） |
| **E6** cross-layer alignment by graph embedding | **REFRAMED → structural resilience** | `06_E6fin_resilience.md` | `25_*`, `26_*` |
| **E7** HGT + attribution over bridging vs centrality | **REFRAMED → URLhaus takedown** | `07_E7inf_takedown.md` | `28_*`–`34_*` |
| **E8** causal-calibrated LLM-agent simulation | **NOT RUN** — no training corpus (upstream of the GPU) | `_server/47_*` (invalid environment, C-101) | — |
| **E9** external validation | **ANCHOR ACQUIRED, series consolidated (9 periods, up to 4 channels each, 0 disagreements)** — 9 issues byte-verified (C-102/C-104); series recovered by text layer (4 periods) and by OCR (9 periods, control 4/4, C-107); **consolidated into `67_` with the asserting channels named per period** (C-119); **(C-122) all five text-layer-less issues are now OCR'd in FULL — 0 zero-char pages, per-page errors none, exit marker `RSC_EXIT=0`**; **(C-121) the per-category tab row was recovered and is a THIRD quantity, not the bullet — it equals `effective` in 01–02, `high_value` in 03/06/07/08/11, and NEITHER in 04 and 10, so the equality is coincidence rather than identity; that is the mechanism of the C-112 disagreement (2025-04's bullet reads `3，999` while `6663` sits in the tab row)** — the channel set is `text_layer` (01–04), `ocr_p6_250` (9), `ocr_p6_200` (9) and a **human pixel read** of a 400-dpi render at band 0.02–0.32 (9); ⚠ three of the four are programs reading a render, so their agreement is **not** independent corroboration (C-112) — the pixel read is the channel that is; ⚠ the reports' own screenshots are **not** a second witness for the series and the report states **several** section-level aggregates, so taking section 一's pair is itself a selection needing disclosure (C-112/C-113) — **(C-125) and that selection is now MEASURED rather than asserted: the documents' own second monthly series (匿名社交社群情报总数量) moves OPPOSITE to the anchor in both months where the anchor moves sharply — 2025-08 the anchor falls 94% while the series rises 48%, 2025-11 the anchor rises 30% while the series falls 85% — so C-109's "rise / repeat / collapse" is a property of the selected aggregate, not of the documents; and the United States row is stated twice on one page in two element forms that disagree in 2025-06 (892 prose vs 932 table) and 2025-10 (1265 vs 1267), making "same page, same quantity, two different values" a stable feature of these files rather than one accident**; ★**(C-124) the p.6 figures are the HIT COUNTS of a query whose window is printed on the same page — 2025-08 reads `为您找到6826条匹配结果`, which is exactly its second headline figure; the convention is `[month-01, next-month-01)` and 2025-06/07/08 comply, but 2025-10's window is `[2025-09-01, 2025-10-01)`, witnessed three independent ways (lower bound, upper bound, and a 30-day span where October has 31) ⇒ the point labelled 2025-10 is a September observation and October is covered by no issue in the set; 2025-06 and 2025-07 additionally report a byte-identical `effective` (1,140,767) under two blind-spot-independent channels; and "the second headline figure reappears elsewhere in the document" holds 4/5, failing only on 2025-10. ⚠ **the query window's UPPER bound is readable on all nine issues, and on 8 of them it is the first day of the month AFTER the issue's own month — 2025-10 is the unique exception, printed `[2025-09-01, 2025-10-01)`; the LOWER bound is not recoverable from the OCR on exactly 2025-03, 2025-04 and 2025-11 (the `r` of `release_time` and the `小` of `小于等于：` were dropped)** (measured at object level, C-190; that entry's §③/§④ were withdrawn as already-registered in C-190c, and the `+310 s` clock offset in C-190e was withdrawn in C-190f) — **the earlier reading that the window was UNREAD for 2025-01/02/03/04/11 was taken at 01:53Z and is superseded for 01 and 02, whose windows are readable in full**; unread ≠ absent, and no claim is made about the unread lower bounds**; comparison still needs E8 | — | `43_*`, `51_*`, `57_*`, `59_*`, `63_*`, `64_*`, `65_*`, `66_*`, `67_*`, `69_*`, `71_*` |
| **E10** few-shot role annotation (κ ≥ 0.75) | **CORPUS LOCATED, annotation not run** — `10.57760/sciencedb.j00133.00466` (571 条电信诈骗案例, open access, C-103); the full OAI enumeration (27,500 records, C-108) found **no** telecom-fraud role-annotation corpus, so ground truth must be produced; κ labelling needs an LLM | — | `50_*` |
| **Data layer** (cross-cutting) | **RUN** | `01_data_layer.md` | `01_data_qc.txt`, `00_*` |

**E6 and E7** were reframed rather than dropped, and the reframing is stated in
each report's own §0. **E5 was not reframed**: its delivery is a measurement with
no model fitted, its plan fallback is conditional on a temporal GNN that has
never been trained, and it is carried here as an **open gap**. E2 is reported as
infeasible and **no substitute event pair was entered under its heading**.

*(Corrected 2026-09-24. This paragraph previously read "E5/E6/E7" and claimed the
reframing was stated in "each report's own §1". Both were false: 05/06/07
contained no such section, and E5 is not a reframe. The §0 sections were written
rather than the sentence deleted, so the promise could be tested. See C-104.)*

## 1. What is established

**E0 — infrastructure takedown (URLhaus).** Median time online after listing
**1.36 days** (n = 36,262; 93.2% events); S(1d) 0.606, S(7d) 0.158, S(30d) 0.050,
with a ~5% tail past 30 days. Removal speed differs **strongly by malware family
tag** (Mozi ≈2× faster than the rest). No trend across the 89-day window.
★ **The hypothesis the plan expected E0 to support — that infrastructure
concentration affects survival — is NOT established**: the descriptive gradient
does not survive block-clustered SEs (p = 0.17). Every duration is a **lower
bound** (`last_online` is the last sighting, not the takedown instant).

**E4 — social survival (AlphaBay).** n = 114,231 listings, 45.9% events, all
censored 2017-01-28. KM median **222.9 days**; median **10.8 days** among
listings that ever received feedback. The gap between those two numbers is
**censoring, not contradiction** — quoting either without saying which is which
misstates the result. SEs are **understated** (no vendor key ⇒ clustering
impossible), the same failure mode that killed E0's headline.

**E1 — substitution (kilos 5-market panel).** Composition turnover with
**preserved aggregate volume**: two markets stop within a day, Apollon goes 6.2%
→ 68.4% of volume, total weekly volume within 2% of pre-shock. **Entry is
directed**: exposed sellers enter the growing market at **+10.5 pp** and the
shrinking market at **+0.0 pp**, which excludes general mobility. The response
depends on **which** market died (Cryptonia 21.0% vs 7.4%, OR 3.34, p=3.5e-6;
Cannazon 7.1% vs 7.4% on 10 events).
★ **Magnitude corrected in §10**: the intensive-margin effect is **+1.0 to +2.4
reviews/week** (treated base 1.15), **not +3.64**. The +3.64 came from a design
carrying a **+1.1/week pre-trend** whose placebo evidence was only three draws.

**E3 — attribution.** **H4 supported** (centrality: no significant positive
relation). **H1 not supported** (positive but n.s.). **H2's substrate is absent**
— 124 checksum-valid BTC addresses in the social layer, 3 intersect Elliptic,
**all three adjudicated non-transactional**, none class-illicit, with a positive
control confirming the machinery. **H3 not testable** (no category column).
★ The **pre-registered PSM covariate set is infeasible** (separation,
max|b| = 20.6, overlap 0.000, zero pairs) because it contains `n_markets`, which
the treatment defines.

**E5-fin — recurrence (Elliptic).** Recurrence in the labelled subgraph is
**7.47%**; 91.6–98.2% of addresses appear in exactly one time step. Recurrence is
**monotone in class**: illicit 1.82% < licit 5.80% < unknown 8.37%, and the
ordering holds within entry steps, i.e. **after the ceiling is removed without a
model**. Higher entry-step intensity predicts **lower** recurrence.

**E6-fin — structural resilience (Elliptic).** **Robust-yet-fragile**: random
failure needs **60%** of nodes removed to halve the giant component,
degree-targeting needs **2.5%**. The labelled **illicit subgraph is structurally
peripheral** (mean degree 3.645 vs 10.803) — removing **all** of it (1.734% of
nodes) leaves **98.88%** of the giant component, indistinguishable from random
removal. **Targeted suppression of illicit addresses has no network-level effect
here.** Connectivity is saturated across all 49 steps, so it cannot measure
resilience in this object.

**E7-inf — takedown latency and reconstitution (URLhaus).** Median takedown
latency **0.47–1.52 days** (bracketed across treatments); 90% offline within ~10
days. **Reuse confers no persistence advantage** — under a within-host paired
design the effect is **−0.49 pp** (p = 8e-07); the naive across-host 3.7×
stickiness was **selection on survival**. **Hosts that go fully dark return**:
**13.88%** within one day (6.2× a stratum-matched chance floor of 2.24%), ~21%
within a week. **Domain-hosted infrastructure is ~2× as resilient as IP-literal**
at equal size (80.77% vs 61.49% return at >20 URLs).

**Data layer.** Seven built tables; three of nine social tables carry **no date at
all**; `hansa_reviews` carries **two date columns with different meanings** (444
content days vs a 1-day crawl stamp). Elliptic's time axis is **ordinal** (49
steps), so the financial layer **cannot be anchored to any calendar event**.

## 2. What is NOT established

- **E8, E9b, E10 were not run.** E8 has **no training corpus** — its own row (§0)
  puts that *upstream of the GPU* — and E10 has **no role-labelling ground truth**
  (C-13). The GPU was a further blocker on 2026-09-24 and has since recovered
  (§3). E9's anchor was
  collected and its curve extracted (C-103/C-107), so what remains of E9 is the
  comparison (E9b), which consumes E8's simulation output.
  ⚠ The curve's middle values come from OCR, because on those issues the body is
  not text objects — see C-107 for the validation and its boundary (p.6 only).
- **E2 was not run**, and no substitute was entered in its place.
- **Any precise effect size for social substitution** — designs disagree by a
  factor of four and the two uncertainty measures disagree on significance.
- **That the substitution mechanism is decentralization or centrality** — H4's
  "support" is the confirmation of an *absence*, which is weaker than a positive
  finding.
- **Any cross-layer address bridge** (3 intersections, none usable), and
  therefore **any calendar-anchored use of Elliptic**.
- **Anything long-run in E0/E7** — the retention windows forbid it (C-29).
- **The H3 mechanism (functional redundancy)** — no category column exists in the
  panel that carries the outcome.

## 3. Blockers requiring the author

**GPU unavailable (C-27) — fourth independent confirmation, 2026-09-24.**
`nvidia-smi` sees `NVIDIA GeForce RTX 4090, 24564 MiB, driver 610.57.04`, but:

```
cuInit(0)            -> 100        (CUDA_ERROR_NO_DEVICE)
cuDeviceGetCount     -> rc=3       (CUDA_ERROR_NOT_INITIALIZED; the out-param is
                                    never written, so any value read from it is
                                    the caller's own sentinel, not a measurement)
torch.cuda.is_available() -> False
torch.cuda.init()    -> raises "No CUDA GPUs are available"
```

The device is visible to the driver but `libcuda` cannot initialise it — a
pod/container-level fault, not a library one. The card self-reports
`GPU requires reset` with `Channel Repair Pending` and `TPC Repair Pending`
(recorded in C-27). **That needed a pod restart, a console action — and as read on
2026-09-24 it blocked E8 and E10 outright and the GPU portions of E5/E7 as planned.**
⚠ Read that as a **dated** statement of what the fault held up, **not as E8's
attribution**: E8's blocker was never the GPU (see its §0 row — *no training
corpus, upstream of the GPU*), and the E5/E7 GPU portions have since been run on
their own terms — their own rows, not this one, say where they stand.

**Two answers to "how many GPUs", depending on who is asked**, on the same machine:
`cuDeviceGetCount` cannot say (the driver never initialised) while
`torch.cuda.device_count() == 1` (NVML sees the card). Neither number is wrong; they
answer different questions. **NVML success is not evidence CUDA works** — which is
exactly why the verdict below comes from a real kernel and not from `nvidia-smi`.

Re-run of the delivered preflight on this pod (`code/_tools/gpu_preflight.py -v`),
checked against the C-27 record rather than trusted on its own:

```
nvml           listed         1 card(s)  RTX 4090, uuid GPU-f28bd3c6-…, 00000000:61:00.0
nvml_health    repair_pending GPU requires reset, Channel Repair Pending, TPC Repair Pending
cuda_driver    fail           cuInit rc=100
torch          present        2.5.1+cu124
torch_cuda     unavailable    torch.cuda.is_available() == False
GPU_PREFLIGHT: NVML_ONLY_NO_CUDA        exit 2
```

The instrument reproduces the already-recorded signature on an object whose answer
was known in advance. **That is the only reason to believe its verdict on a pod
whose answer is not known yet.**

**Update, 2026-09-25 — C-27 no longer holds on the scheduled path.** Everything
above is the 2026-09-24 reading and is left as written. As of
`_logs/pipeline_state.json` (`generated` `2026-09-25T18:54:12`, `invoked_via`
`watchdog(--advance)`), `gpu_verdict` is **`COMPUTE_OK`**, `gpu_ok` is `true` and
`pod_reachable` is `true` — i.e. **a real kernel ran**, from the same instrument
whose 09-24 signature is recorded above. So "It blocks E8 and E10 outright"
describes that day, not today: **the restart recorded as a console action has
either been taken or the GPU has recovered.**

⚠ **Do not carry the recovery over to attribution.** E8's blocker was never the
GPU: its own row (§0) gives **no training corpus (upstream of the GPU)**, and that
clause is untouched by the recovery — nor is C-13, which E10 and E9b still wait on.

⚠ **Nor does it transfer to this machine.** Locally `nvidia-smi` is absent,
`torch.cuda.is_available()` is `False` and `torch.cuda.device_count()` is `0`
(`torch 2.12.0+cpu`). C-27 is a **pod** finding — its definition reads *on a pod* —
and it is the pod that has recovered, not the laptop.

**Authored decisions still open:** **C-05** (whether to procure a Bayonet-window
dataset) and **C-13** (substitutes for C-08's role-labelling ground truth and
E9's external anchor).

**★ The GPU is necessary but not sufficient — and C-13 outranks it.** Even with the
GPU fixed, E10 has no role-labelling ground truth, E9 has no external anchor, and E8
consumes E10's output. **Deciding C-13 comes before treating the GPU as the
blocker**; otherwise a restart is bought for a precondition that is still unmet.
This is recorded because it is the kind of ordering that is easy to get backwards
when a red blocker is the visible one — and, as of 2026-09-25, **the GPU is no
longer the visible blocker while C-13 still is.**

## 3b. C-13 reconnaissance (2026-09-24) — report 11

> ⚠️ **Corrected by C-99.** The byte count and sha256 quoted below describe **the first
> 28.7% of the file**, not the report — see the correction immediately after the block.
> As of 2026-09-24 the full 2025 series is **being acquired**, so "no full series
> downloaded" was true when written and is no longer the current state.

Reconnaissance only: **no substitute dataset was adopted, no full series downloaded,
no E9/E10 result produced.** What it establishes is what C-13 costs.

**E9's anchor is an uncollected item, not an unfindable one.** The plan asks for
"simulation extrapolation vs the 2025 report's **measured curves**" — curves need a
*time series*, which a single annual report cannot give. The plan's own wording names
**《全球数据泄露态势月度报告》** (数世咨询 × 零零信安, monthly, built on the 0.zone OSINT
system). C-08 recorded it as **not acquired**, not as non-existent. I downloaded one
issue directly rather than trusting a search summary — as recorded at the time:

```
HTTP 200, 9,158,656 B, application/pdf, magic = %PDF-1.7      <-- superseded, see C-99
sha256 cc92f9fae16349cf9709ed73f0254ffddec8c71d5c64595f9db83c420bc9e51c
data/external/c13_recon/dwcon_leak_posture_2025-03.pdf
```

**Correction (C-99).** The report is **31,921,548 B**; `9,158,656` was the prefix my own
`--max-time` cut the transfer at, and `size_download` — *how much had arrived when I
killed it* — was read as the file's size. The saved file has **`startxref` and `%%EOF`
zero times in the whole file**: it is not a damaged PDF, it is a prefix of one. PyMuPDF
opened and silently repaired it, which is why nothing downstream complained; pypdf
refused. **The sha256 is withdrawn as an identifier** (it identifies a fragment). The
claim *"this PDF is publicly obtainable"* survives on better evidence: two independent
HEADs agree on `Content-Length: 31,921,548` with `Accept-Ranges: bytes`. Recorded as
**C-99** in the ledger; discipline face ㉔.

**So the E9 half of C-13 is not a substitution decision — it is a collection task with
zero cost** — and as of this writing it is **running**, server-side, with 9 of 12 months
of 2025 already located. One cross-check came free: the 2025.12 figures (942,968 / 6,446)
were returned independently by two unrelated retrieval paths. That agreement carries
weight **because the paths are independent** — the opposite of the MIR case, where two
instruments sharing one blind spot agreed and proved nothing. What matters is
independence, not the number of sources.

**★ E9 needs no GPU.** The plan lists it twice as a CPU experiment (GPU usage column
`—`; the GPU table puts "statistical experiments (E0–E4, E3, E9)" in the `<4GB` row).
E9 does consume E8's simulation output, and E8 does need the GPU — so E9's **periphery**
(collecting the report, extracting curves) can start now, while the **comparison** waits
on E8. This is document evidence, not something I measured.

**E10 is the half that is genuinely blocked.** Its role-labelling ground truth —
ScienceDB "571 telecom-fraud cases" — **could not be confirmed to exist**; the only hit
for "571" was a Korean voice-phishing corpus, unrelated and differently shaped.
**"I did not find it" is not "it does not exist"** — that search was a general engine
with Chinese keywords, and a ScienceDB on-site search has not been done. Candidate
alternatives are listed in report 11 and **none adopted**: swapping the dataset changes
what E10 measures, which is an author decision (the E2 precedent: report infeasible,
do not substitute). The plan's hard constraint "public datasets only" also meets the
Cambridge collections, which require an application and a data-use agreement —
**whether those still count as "public" is for the author to rule on, not me.**

## 3a. Where the data actually is (C-94)

Before this session, `D:\CIS\data` was **0 bytes**; all 23 GB existed only on the
pod, which is transient. Backed up and verified:

| pod path | size | status |
|---|---|---|
| `data/raw/` | **148 MB** | **irreplaceable** — 5 source archives; pulled, 5/5 hashes match |
| `data/extracted/` | 20 GB | the same archives, decompressed ⇒ regenerable, not pulled |
| `data/EllipticPlusPlus-main/` | 2.1 GB | public GitHub repo ⇒ regenerable, not pulled |
| `data/_recon/` | 45 MB | abuse.ch snapshot + gwern index (provenance for E0/E7); pulled as one tar |
| `work/` | — | 7 derived tables; pulled, 7/7 hashes match |

**The backup size was set by irreplaceability, not by total volume.** Deciding by
directory size would have moved 20 GB of decompressed copies while the actual
single point of failure was 148 MB. Every pulled file was checked against a hash
list **computed on the pod before the transfer** — a locally recomputed hash could
only prove local-consistency-with-local.

The pod does have its own egress (cluster proxy), so model weights for E8/E10 can be
pulled server-side rather than over the author's hotspot.

## 4. Integrity record

```
results/ : 89 files
old manifest (83 entries) -> UNCHANGED 83, ADDED 6, CHANGED 0, REMOVED 0
RE-VERIFY: 89 entries checked, 0 bad        VERIFY_OK
transfer sha256 (pod = local): 9a67eb654c1cb24d…   (29.02 MB)

package cis_sprint_20260924 : 233 entries
sha256sum -c _MANIFEST.sha256  ->  OK 233, FAILED 0, exit 0, stderr empty
sha256sum -c _logs/results_manifest.sha256 -> OK 89, FAILED 0
```

The count is a time stamp, not a property of the deliverable. An earlier build carried
**230**; it is preserved with its own manifest at
`output/_superseded_cis_sprint_20260924_build1_230entries/` — still verifiable
against itself, exactly as it was recorded. It is not the deliverable, and the
canonical path always names the current one. **230 → 233 = `gpu_preflight.py` +
report 11 + `_docx_text.py`**, all added after that build.
When counting the manifest's own lines, remember the two `#` header lines are not
entries — and **do not accept a match count that equals the file's line count until
you have checked that the pattern is not degenerate** (`grep -c ''` matches every
line; `grep -vc ': OK$'` returning 0 is what makes the count a measurement).

**83 previously-recorded files came back byte-identical** through
SFTP + tar extraction, so `results/` is write-once in practice. The transfer hash
was computed on both sides and matches, which is an independent check on a
different path than the manifest.

The last two lines are the **acceptance standard for an integrity record**: a
tool this project did not write (coreutils), running the exact command the README
tells the reader to run, against the delivered object. Until C-93 it did not
pass — see below.

The full ledger, including every falsified hypothesis and every one of my own
defects, is `pipeline_reports/progress.md`. **78 distinct correction ids**
(C-01 … C-93; ids C-02, C-08, C-10–C-12, C-14–C-19 and C-77–C-80 were never
issued, and C-4180 in the ledger is a grep artifact of the string *RFC-4180* —
which is why a raw `grep -o 'C-[0-9]*' | sort -u` returns 79, not 78).

**Corrections of my own work are recorded alongside results, not quietly
repaired.** The four that changed a published conclusion in this sprint:

| id | what it changed |
|---|---|
| C-71 / **C-82** | E1's design violates parallel trends; **stratum×week FE removes only 14% of the drift** it was introduced to remove |
| **C-84** | "largest of three placebos" is a selection minimum — it understated the null by ~30% and voided report 04's discriminating-power argument |
| **C-85** | report 09's 500 placebos covered model (i) only, while report 04 reports model (ii) — **I had been backing one design's conclusion with another design's null** |
| **C-90** | the integrity manifest was being computed **on the machine it was supposed to check**; split into pod-side packing and local-side hashing |
| **C-93** | **the delivered manifests were CRLF, so `sha256sum -c` — the first command the README gives — failed on all 229 entries.** Python's own reader hides it (universal newlines strip `\r`), so the record was verifiable only by the tool that wrote it; the packaging step reported `0 bad` throughout, correctly, by its own reading |
| **C-96** | `cuDeviceGetCount -> rc=3, n=0` was reported as a count of zero cards. `rc=3` is `CUDA_ERROR_NOT_INITIALIZED`: **the call never wrote its output parameter**, so the `0` was the sentinel I had initialised it with. Re-run with a `-1` sentinel reads `-1` on the same machine. **Downgrades one number from a measurement to an artefact**; changes no conclusion |

## 5. Deliverables

| path | contents |
|---|---|
| `pipeline_reports/progress.md` | the ledger — every stage, every correction |
| `pipeline_reports/00_…`–`10_….md` | eleven stage reports |
| `pipeline_reports/11_C13_external_data_recon.md` | what C-13 costs: E9's anchor is obtainable and free; E10's ground truth unconfirmed |
| `pipeline_reports/_ref/` | referenced instrument outputs |
| `results/` | 89 artefacts, SHA-256 in `_logs/results_manifest.sha256` |
| `_logs/results_manifest.diff.txt` | the UNCHANGED/ADDED/CHANGED/REMOVED record |
| `_server/` | every stage script, as run |
| `_tools/rsc.py`, `_tools/verify_results.py` | pod transport; local verification |
| `_tools/gpu_preflight.py` | one-line GPU verdict; **the acceptance test for any new pod** (exit 0 iff a real kernel ran) |


---

## Erratum C-244 (2026-09-24) — wording of the E5p within-t0 gap

**Supersedes the wording of the C-235 row above and of the E5p/`16_E5p` block.** It does not
change any measured number or any object.

**Do not write "~0.21 (or ~0.214) of leak".** The ledger's C-234 (3) forbids that sentence, and
C-244 adjudicates the conflict with the v9 errata table (K1) under **v9's own K2 rule** --
"no reading before the negative control is fixed counts as evidence".

| layer | may be written | content |
|---|---|---|
| measurement | **yes** | control within-t0 weighted readout **0.7139 / 0.7115 / 0.7117**; permutation null (20,000 draws x 3 deltas) centred **0.499978 / 0.499996 / 0.500044**, SD equal to the closed form, coverage 0.990-0.992 -> **outside the band, ~0.214 above the chance line** |
| cause | **no** | the cause (true leakage / feature-side predictability / construction of the readout) is **NOT attributed**. The `untrained` arm (epochs=0) reads 0.4424 / 0.3927 / 0.5378 -- a single fixed direction **below** 0.5 -- while the control is **above** by 0.214, so it cannot explain it; and the negative controls are constant inside a t0 bin (necessarily 0.5), so **no arm supplies an anchor for a null distribution**. |
| what does stand | **yes** | `true - shuffled` = **+0.0528 / +0.0549 / +0.0578** (object: the attribution table's baseline row; the "arms" object gives +0.0508 / +0.0509 / +0.0486). These are **two single points, no null distribution => no significance is claimed**. |
| when the cause can be named | -- | after **E5r (W2)**, i.e. after the negative control is rebuilt so that it varies inside a t0 bin. |

So: **measurement reportable; cause deferred to E5r.** This is v9's K2 applied to v9's K1.
