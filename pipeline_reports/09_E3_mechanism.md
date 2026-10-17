# 09 — E3 mechanism attribution: PSM + DiD, H1/H4, 500 placebos

**Status:** complete. One pre-registration defect measured, one of my own
readings reversed by a better-controlled null, and a **parallel-trends violation
in E1 v3's headline design**.
Code `_server/38_E3_mechanism.py`, `39_E3_robust.py`. Outputs `results/38_*`,
`results/39_*` → `pipeline_reports/_ref/`.

E3 is pre-registered as **"PSM + DiD（H1–H4）+ 500 次安慰剂检验"**:

> H1 去中心化 ↑ → 恢复时间 ↓　H2 跨层桥接 ↑ → 恢复时间 ↓
> H3 功能冗余 ↑ → 功能恢复 ↑　H4 单纯高中心性与韧性无显著正相关

Report 08 settled by measurement which hypotheses have a substrate. **H2 and H3
are not run here** and are recorded as such in §6 of the output rather than
quietly dropped. H1 and H4 are run.

The estimator is E1 v3's, copied verbatim (`demean` + `fe_did`, SE clustered on
seller) — changing it would make matched-vs-unmatched incomparable.

---

## 1. ★ The pre-registered PSM specification is infeasible, measurably

The first attempt matched **zero** pairs. The cause is substantive, not
numerical: treatment is *defined* as "active in the target **and** in a dead
market", which forces `n_markets ≥ 2` for every treated seller. `n_markets` has
**SMD +3.31**, so putting it in the propensity model makes treatment perfectly
predictable and destroys overlap:

| covariate set | n | max\|b\| | overlap | pairs | worst \|SMD\| |
|---|---|---|---|---|---|
| A full (as pre-registered) | 9 | **20.61** | **0.000** | **0** | 3.313 |
| B minus definitional `n_markets` | 8 | 2.14 | 0.696 | 77 | 1.596 |
| C Apollon activity + quality | 6 | 2.17 | 0.886 | 74 | 1.596 |
| D baseline size + quality | 4 | 2.71 | 0.949 | **121** | 0.519 |

**The specification the plan asked for is the one that fails.** Three reduced
specifications match; the DiD is reported under all three, not only the best.

## 2. The event effect survives matching — but its magnitude does not

| design | pairs | β (seller+week) | p | β (+stratum×week) | p |
|---|---|---|---|---|---|
| unmatched | 489 | **+3.8819** | 0.0048 | +3.6365 | 0.0118 |
| B minus `n_markets` | 77 | +1.4199 | 0.4798 | +3.6376 | 0.1192 |
| C activity + quality | 74 | +2.4426 | 0.2432 | +4.4911 | 0.0602 |
| D size + quality | 121 | +1.0424 | 0.3619 | +1.3435 | 0.2281 |

The point estimate ranges **+1.04 to +4.49** across defensible matched designs.
The *existence* of an effect is stable; the *magnitude* is not, and no matched
design reproduces E1 v3's +3.88 with a cluster-robust p below 0.05.

## 3. ★ The decisive finding: E1 v3's design has a pre-trend

500 placebo event dates were drawn inside the pre-period, the panel re-cut at
each, and the same estimator re-run. Each real β is placed in **its own**
design's null:

| design | null mean | null sd | real β | percentile | p_placebo |
|---|---|---|---|---|---|
| **unmatched** | **+1.2929** | 0.36 | +3.8819 | 100.0% | 0.0000 |
| B minus `n_markets` | +0.2748 | 0.68 | +1.4199 | 96.8% | 0.0320 |
| C activity + quality | +0.0111 | 0.93 | +2.4426 | 100.0% | 0.0000 |
| D size + quality | −0.0694 | 0.64 | +1.0424 | 97.8% | 0.0220 |

**The unmatched null's mean is +1.29 with sd 0.36.** With no event at all, the
treated arm already grows ~1.3 reviews/week faster than the control arm. That is
a **parallel-trends violation in E1 v3's headline design** — a genuine defect in
the specification that produced this project's social-layer result, found by
turning the placebo into a pre-trend test rather than a formality.

**Matching repairs it**: the matched nulls sit at +0.27, +0.01 and −0.07, i.e.
≈ 0. That is the strongest argument *for* the matched designs and explains why
the matched point estimates are smaller — the unmatched figure was carrying the
pre-existing differential trend.

**And the effect survives the repaired nulls**: every matched design places its
real β in the **97th–100th percentile** of its own null (p_placebo 0.000–0.032).

### The two uncertainties disagree, and both are reported

For design D the cluster-robust *t* gives **p = 0.36** while the placebo rank
test gives **p = 0.022**. The placebo null's sd (0.64) is **narrower** than the
cluster-robust SE (1.14) on the same design, and that gap is the entire
disagreement. They answer different questions — sampling variability across
sellers vs. extremeness relative to the design's own pre-period behaviour — and
neither is privileged here. **Reported as a divergence, not resolved by choosing
the smaller number.**

## 4. H1 and H4

| sample | term | β | se | p |
|---|---|---|---|---|
| unmatched | did × decentralization | +1.4686 | 2.13 | 0.4903 |
| PSM-matched | did × decentralization | +2.4823 | 2.11 | 0.2416 |
| unmatched | did × centrality | −4.1798 | 2.87 | 0.1454 |
| PSM-matched | did × centrality | −0.5804 | 2.35 | 0.8047 |

- **H1 (decentralization → faster recovery): NOT SUPPORTED.** Positive in both
  specifications but not significant (matched p = 0.24). Directionally as
  predicted, evidentially absent.
- **H4 (raw centrality → no significant positive relation): SUPPORTED.** The
  centrality interaction is negative under both specifications and never
  significantly positive. The pre-registered hypothesis is an absence, and the
  absence is what is found.

Moderators are pre-event constants, so seller FE absorbs their main effects;
only the interaction with `did` is identified, and they are centred so `did`
reads at the average moderator value. Decentralization counts markets **other
than** the target and the dead ones — counting the dead markets would build the
treatment into the moderator.

## 5. Corrections to my own work in this stage

| id | content |
|---|---|
| **C-68** | **我的缺陷（把匹配失败当结果）**：38_ 首轮 PSM 得 0 对，我在报告口径里几乎要写成「效应被匹配消掉」。**真实原因是分离性**（预注册协变量集含 `n_markets`，而它是处理定义的推论）⇒ **是规格不可行，不是效应消失**。且空样本让我打印出 `worst SMD after = 0.0000`——**一个在空数组上算出来的「完美平衡」**。 |
| **C-69** | **我的缺陷（对照不对齐）**：38_ 用**未匹配**设计造 500 个安慰剂（null 均值 +1.29），却拿**匹配样本**的 β 去比 ⇒ **不是同一个设计的检验**。39_ 为每个设计各造一套 null 后才可读。**这条是本次结论反转的直接原因**：匹配设计的 null 在 0 附近且实测 β 落在 97–100 百分位。 |
| **C-70** | **我的缺陷（择优）**：38_ 按「配对数最多」挑协变量集 D，等于**在结果上做了选择**。39_ 把 B/C/D 三个可匹配集**全部**报出（+1.42 / +2.44 / +1.04），并明说量级不可复现、存在性可复现。 |
| **C-71** | **真实性质（E1 v3 的规格缺陷）**：未匹配设计的安慰剂 null 均值 **+1.29（sd 0.36）** ⇒ **处理组在任何事件之前就已比控制组每周快约 1.3 条评价** = **平行趋势不成立**。E1 v3 的 +3.88 因此被高估；匹配把 null 均值压回 ≈0。**把安慰剂当预趋势检验用，才让它现形。** |
| **C-72** | **真实性质（两种不确定性冲突）**：同一设计 D 上，聚类稳健 t 给 p=0.36、安慰剂秩检验给 p=0.022；原因是**安慰剂 null 的 sd（0.64）比聚类稳健 SE（1.14）窄**。**两者回答不同问题，此处并列报告、不择小取用。** |

## 6. Verdict

**ESTABLISHED**

1. **The pre-registered PSM covariate set is infeasible**: separation
   (max\|b\| = 20.6), overlap **0.000**, zero matched pairs — because it contains
   `n_markets`, which treatment defines. Three reduced specifications match
   (74–121 pairs).
2. **E1 v3's unmatched design violates parallel trends**: its own placebo null
   has mean **+1.29 (sd 0.36)**, so the treated arm was already growing faster
   before any event. Matching reduces the null mean to ≈ 0.
3. **An event effect survives the repaired design** (97th–100th percentile of
   each matched null, p_placebo 0.000–0.032) but its **magnitude is not stable**
   (+1.04 to +4.49) and no matched design reaches cluster-robust p < 0.05.
4. **H4 supported** (centrality: no significant positive relation);
   **H1 not supported** (positive but n.s.).

**NOT ESTABLISHED**

- **A precise effect size for substitution.** The designs disagree by a factor
  of four and the two uncertainty measures disagree on significance.
- **H2, H3** — not testable on this data (report 08 §1, C-45 carried forward).
- **That the mechanism is decentralization or centrality.** Neither moderator is
  significant; H4's "support" is the confirmation of an *absence*, which is
  weaker evidence than a positive finding.
- **Any interpretation beyond seller-level reallocation.** Treated sellers lose
  their dead-market outlet, so part of any Apollon increase is mechanical
  reallocation by that seller rather than market-level recovery.
