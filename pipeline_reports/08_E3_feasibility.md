# 08 — E3 feasibility: does the pre-registered design have data under it?

**Status:** complete. One decisive negative result, two instrument corrections,
and one substrate relocation.
Code `_server/36_E3_h_feasibility.py`, `37_E3_bridge_probe.py`.
Outputs `results/36_*`, `results/37_*`, copied to `pipeline_reports/_ref/`.

E3 is pre-registered as **"PSM + DiD（H1–H4）+ 500 次安慰剂检验"** with

> H1 去中心化 ↑ → 恢复时间 ↓　H2 跨层桥接 ↑ → 恢复时间 ↓
> H3 功能冗余 ↑ → 功能恢复 ↑　H4 单纯高中心性与韧性无显著正相关

This stage asked, for each hypothesis, whether its measurement substrate
**exists** — before running any of the analysis. That is the discipline the last
stage forced (report 07 §1: `last_online` had to be understood before a cohort
could be drawn from it, and the answer changed the design).

---

## 1. ★ H2 (cross-layer bridging) — substrate measured ABSENT

The plan's bridging key is **"PGP/收款地址 ↔ Elliptic 链上地址（先用规则匹配）"**,
promising "桥接节点清单" as a deliverable.

**No PGP or payment-address column exists in any social-layer file.** Headers are
`Vendor,Category,Item,Item Description,…` and `date,time,comment,rating,item`.
But an absent *column* does not prove an absent *key* — an address can sit inside
free text. So the scan searched all text and asked whether each candidate
**decodes as base58check**:

| file | regex candidates | ★checksum-valid (distinct) |
|---|---|---|
| agora | 13 | 3 |
| alphabay_items | 172 | **159** |
| alphabay_feedback | 3 | 2 |
| hansa_listings | 0 | 0 |
| hansa_reviews | 0 | 0 |
| valhalla_listings | 0 | 0 |
| kilos_reviews | 2 | 2 |
| druglisting | 355 | 5 |
| **total (distinct)** | | **124** |

The checksum is load-bearing. `druglisting` proposes 355 candidates and only
**5** validate (1.4%); `alphabay_items` proposes 172 and **159** validate (92%).
A regex-only count would have reported 545 addresses; the true figure is 124.
**base58check's false-positive rate is 2⁻³², so every one of the 124 is a real
base58 address** — the rejected candidates were the noise.

Intersecting 124 social addresses against Elliptic++'s **822,942**
(`Actors Dataset/wallets_classes.csv`) yields **3**:

| address | found in | Elliptic class | adjudication |
|---|---|---|---|
| `12c6DSiU4Rq3P4ZxziKxzrL5LmMBrzjrJX` | alphabay `blurb` | 3 unknown | **artifact** — sits in a listing *selling a leaked blockchain dump* ("Very Rare to find to Block 401419 7.8M Addresses… Beginning: `1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa`;6617981597"). Those are the **genesis address and the first-ever transaction recipient** — the dump's opening rows, not payment addresses. |
| `38ccq12hPFoiSksxUdr6SQ5VosyjY7s9AU` | alphabay `blurb` | **2 licit** | **artifact** — a **charity donation list** ("Sean's Outpost… MAPS"). Elliptic classes it **licit**. |
| `12o7NkLkivenB2v1aej9tSSzkB3SJ7vPXD` | agora `Destination` | 3 unknown | **data-entry error** — `Destination` holds shipping countries (USA 14,666 / Worldwide 12,200 / …); only **2 of 109,689** rows hold an address-shaped value. Vendor `sexyhomer`, a counterfeit-watch listing. |

**Controls.** A known Elliptic address injected into the social pool was
recovered (intersection 3 → 4) — the machinery works, so the small number is a
property of the data, not of broken code.

**Why the 3 hits are not evidence of bridging.** Elliptic++ covers 822,942 of
roughly a billion Bitcoin addresses (~0.07%). A 3/124 hit rate (2.4%) is far
above chance — but the explanation is **selection by activity**: Elliptic
contains addresses that *have transactions*, and the three hits are a charity, a
genesis address and a first-transaction recipient, i.e. exactly the high-traffic
addresses that any activity-sampled graph contains. Vendors' fresh payment
addresses have few transactions and are absent. The intersection therefore
selects for **famous addresses, not for market links**.

**And even a mechanical link would not land on the target.** Only
**14,266 / 822,942 (1.73%)** of Elliptic is labelled illicit. Of the three hits,
none is class 1: two are unknown and one is **licit**.

> **H2 is NOT TESTABLE in the acquired data.** There is no bridging-node list to
> produce. This is a measured absence, not an assumption, and the plan's E6
> ("跨层对齐增强") inherits it.

## 2. ★ druglisting is not a market — it is an aggregated corpus

`druglistingdataset` carries a `source` column over **8 markets**:

```
agora 124842 · silkroad2 24062 · nucleus 18364 · evolution 15772
outlaw_market 5756 · abraxas 4087 · themarketplace 1378 · 1776 172
```

So the naive cross-file comparison — "agora × druglisting share 2,929 handles,
therefore sellers operate in two markets" — is **one market counted twice**:
druglisting's `agora` subset shares **91.0%** of agora's vendor set (2,906 of
3,192) at a different crawl completeness (109,689 vs 124,842 rows).

Multi-homing must instead be read off the corpus's **own market label**:

| corpus | sellers | in >1 market | dated? |
|---|---|---|---|
| druglisting | 6,192 | **1,353 (21.85%)** | **no** |
| kilos panel (5 markets) | 1,565 | **344 (22.0%)** | **yes** |

## 3. Substrate relocated: H1 and H4 belong on the kilos panel

E1 v3 does not read the CSVs directly — it reads `/root/cis/work/kilos_reviews.parquet`
(`market`, `vendor`, `f2` unix seconds, `f3` rating ∈ {−1,0,1}). That table is a
**dated multi-market panel**:

```
Empire 82892 · Cannazon 55675 · Apollon 41424 · Cryptonia 35160
Samsara 10216 (all f2=0, C-39) · CannaHome 9958     1661 vendors, 99 weeks
```

★ **`f3` gives a quality outcome** (positive 211,332 / negative 7,175 /
neutral 6,602) and **`market` gives the multi-homing moderator**, both with
time. So H1 and H4 are computable as *time-varying* quantities on a panel that
already carries E1 v3's event (2019-11-18 Cryptonia/Cannazon), whereas
druglisting is **cross-sectional** and can only support a static H1 check.

**Consequence for the design:** E3 belongs on the kilos panel, reusing E1 v3's
window (`PRE0 2019-06-03 → EVENT 2019-11-18 → POST1 2020-01-12`) and its
corrected candidate set, with PSM and the H1/H3/H4 moderators added on top.

## 4. H3 has no proxy, and its natural one is already refuted

The only category-like fields anywhere are agora's `Category` (109 distinct),
alphabay's `category1/2/3` (12/48/92) and `product_class` (2) — and **both are
undated/cross-sectional**, while H3 ("功能冗余 ↑ → 功能恢复 ↑") is a dynamic
claim. The kilos panel has **no category column** (C-45), and C-45 records that
the one available proxy **refutes** the hypothesis. Any H3 proxy in E3 must be
declared a weak proxy with C-45 carried forward, not silently upgraded.

## 5. Corrections to my own work in this stage

| id | content |
|---|---|
| **C-60** | **我的缺陷（标签）**：36_ 把 kilos 的 `c0` 当 vendor 列，报「94 distinct handles」。**`c0` 是 market 列**（builder `01_build_tables.py:307` 明写 `market=r[0]`，vendor 是 `r[1]`）。一个 94 个市场的读数被贴上了 vendor 标签。**教训：列的位置语义要回源 builder，不能从首行猜。** |
| **C-61** | **我的缺陷（假阴性读成缺席）**：36_ 报 hansa_listings「无时间列」，**错**——`c0` 就是时间戳（`2016-12-11 20:13:54.654635 -0500 EST`），只是 pandas 对 `-0500 EST` 这种带时区名的格式解析失败。**仪器的解析失败被读成了对象的属性缺失**（C-57 同族）。凡报「列不存在」必须先排除解析器不会读。 |
| **C-62** | **我的缺陷（对照无判别力）**：37_ 的「负对照」用 2 个伪造地址并入社会层再求交，返回 3——**它按构造就等于实测交集**，因为伪造地址本就不在 Elliptic 里。该对照**没有区分力**；真正有用的是那个**阳性对照**（注入已知 Elliptic 地址、被回收，3→4）。**要证明「交集不为空」，需要的是注入；要证明「交集的数不是错的」，需要的是同一台仪器上的已知配对。** |
| **C-63** | **仪器缺陷（静默解析）**：`agora_2014_2015.csv` 的**表头带前导空格**（`' Category'`、`' Item'`），`df['Item']` 抛 KeyError 而 `df[' Item']` 正常。凡跨表按列名 join 都有单向失配风险。 |
| **C-64** | **真实性质**：agora 的 `Remarks` 列 109,689/109,689 行都是**字面字符串 `'nan'`**（不是缺失），该列不携带信息。 |

## 6. Verdict

**ESTABLISHED**

1. **H2's substrate is absent.** 124 distinct checksum-valid BTC addresses exist
   in the social layer, 3 intersect Elliptic, and **all three are adjudicated as
   non-transactional** (leaked-dump preview, charity donation, one mis-filed
   cell); **none** is class-illicit. A positive control confirms the machinery.
2. **druglisting is an 8-market aggregated corpus**, and cross-file handle
   overlap between it and agora is **91.0% market duplication**, not multi-homing.
3. **The kilos panel is a dated 5-market panel** (1,565 vendors, 344
   multi-market, `f3` rating outcome) and is the correct substrate for H1/H4 —
   druglisting is cross-sectional and supports only a static check.

**NOT ESTABLISHED**

- **H2 in any form.** Not a weak signal — the pre-registered bridging-node list
  cannot be produced from the acquired data. E6 inherits this.
- **H3 via any natural proxy** (C-45 carried forward, unchanged).
- **E2 as pre-registered.** Onymous (2014-11) predates the acquired coverage;
  alphabay ends **2017-01-28**, ~6 months *before* Bayonet (2017-07-20). To be
  reported as a feasibility finding, **not silently substituted**.
- **That the 3 Elliptic hits are a "small" bridge effect.** They are 3, and each
  has a specific non-bridging explanation; the excess over chance is explained
  by activity-based sampling of Elliptic.
