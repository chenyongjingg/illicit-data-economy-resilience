# 10 — E2 feasibility: the two-event comparison cannot be run, and that is the finding

**Status:** complete. **E2 is reported as INFEASIBLE AS PRE-REGISTERED.** No
substitute event study was run in its place.
Code `_server/40_E2_feasibility.py` (four versions; §5 records why).
Outputs `results/40_E2_feasibility.{txt,json}`.

E2 is pre-registered as:

> **Onymous vs Bayonet 指标一致性（E1 管线复用）** — run E1's pipeline on two
> events, Onymous (2014-11-06) and Bayonet (2017-07-20), and show the indicators
> agree.

"**E1 管线复用**" is the load-bearing phrase, because it fixes *which data* the
test can use. E1's pipeline runs on the kilos panel. So the first question is not
whether the two events are interesting — it is whether anything that was
acquired covers them.

**The claim is measured, not assumed.** Every dataset was scanned in full for
date-bearing columns; nothing was inferred from a failed parse.

---

## 1. Measured coverage of every acquired dataset

| dataset | date column | format | span | distinct dates |
|---|---|---|---|---|
| `alphabay_items` | `listed` | `Jun 13, 2016` | 2014-12-21 .. 2017-01-28 | 738 |
| `alphabay_feedback` | `date` | inferred | 2015-01-03 .. 2017-01-28 | 687 |
| `hansa_listings` | `c0` | inferred | 2016-12-11 .. 2016-12-13 | **2** |
| `hansa_reviews` | **`c6`** | inferred | **2015-09-12 .. 2016-12-13** | **444** |
| `hansa_reviews` | `c0` | inferred | 2016-12-13 .. 2016-12-13 | 1 |
| `kilos_reviews` | `c2` | **unix seconds** | **2018-02-19 .. 2020-01-12** | 654 |
| `agora` | — | — | **no date column** | — |
| `valhalla_listings` | — | — | **no date column** | — |
| `druglisting` | — | — | **no date column** | — |

Three of nine tables carry no date at all. **`hansa_reviews` carries two
different date columns and they mean different things**: `c6` is the content
date (444 distinct days) and `c0` is a **crawl stamp constant across the dump**
(1 distinct day). Reading `c0` would have made the entire Hansa review corpus
look like a single day's snapshot. This is the same dual-semantics structure
found in `ioc_urlhaus.last_online` (report 07 §1): **one column, two meanings,
and whichever one you assume determines your answer.**

`hansa_listings` is a genuine 3-day snapshot (2 distinct dates) with no content
date — so it cannot support any before/after design regardless of events.

## 2. ★ The event coverage matrix — every cell is NO

| dataset | Onymous 2014-11-06 | Bayonet 2017-07-20 |
|---|---|---|
| `alphabay_items` | **45 d too early** | **173 d too late** |
| `alphabay_feedback` | **58 d too early** | **173 d too late** |
| `hansa_listings` | 767 d too early | 219 d too late |
| `hansa_reviews` | 311 d too early | 219 d too late |
| `kilos_reviews` | 1202 d too early | 215 d too early |
| `agora`, `valhalla_listings`, `druglisting` | no dates | no dates |

**Pairs with the event inside the span at all — any margin: NONE.**
**Pairs with ≥90 d on both flanks: NONE.**

The two pre-registered events fall in the **gaps on either side of the acquired
AlphaBay/Hansa era**, not inside it:

- **Onymous** (2014-11-06) is **45 days before** the earliest acquired record
  (`alphabay_items`, 2014-12-21) and 58 days before the earliest feedback row.
- **Bayonet** (2017-07-20) is **173 days after** the acquired era ends
  (2017-01-28) and 219 days after Hansa's last review (2016-12-13), and still
  **215 days before** the kilos panel begins (2018-02-19).

There is a **13-month hole** between the AlphaBay/Hansa era and the kilos era,
and both events fall in or beside it. This is not a marginal shortfall that a
looser margin would rescue: **not one dataset-event pair has the event inside
its span at all.**

## 3. E1's own pipeline covers neither event

```
E1 v3 reads /root/cis/work/kilos_reviews.parquet
its span: 2018-02-19 .. 2020-01-12  (225109 dated rows, 654 distinct dates)
  covers Onymous (2014-11-06): NO
  covers Bayonet (2017-07-20): NO
```

So "E1 管线复用" is not available. Reuse of E1's pipeline would require the
pipeline's own panel to cover the event, and it covers neither. **E2 cannot be
run by reuse**, and building a second pipeline on the AlphaBay/Hansa era would
not be E2 as pre-registered — it would be a different study wearing E2's name.

## 4. The financial layer cannot be anchored to a calendar at all

`txs_features.csv` time column: `Time step`, **n = 203,769 rows, 49 distinct
values, min 1, max 49.**

Elliptic's time axis is **ordinal** — integer steps, not dates. It carries no
anchor to any real-world event. **E2 and E6 both need a date on the financial
layer, and neither can have one from this source.** This is independent of the
address-intersection result in report 08 §1: even a perfect cross-layer address
link could not be placed on a common timeline.

## 5. The instrument: four versions, three failures, each one plausible

Recorded because each failure returned a *confident* wrong answer rather than an
error, and the same failure modes are available to any future reader of these
files.

| v | approach | how it failed | what it returned |
|---|---|---|---|
| 1 | `pandas.read_csv` | fell back to the python engine on the 1.2M-row table; still running at 15 min | (killed) |
| 2 | streaming `csv.reader`, **pick one date column per file** | ties resolved to file order → two hansa files both resolved to `c0` | hansa as a **1-day** span |
| 3 | report **every** qualifying column | (i) regex **anchored** with `$`, so hansa's `... -0500 EST` suffix failed every value; (ii) sample was the **first 20k rows** | **"no date column"** for files that have one |
| 4 | unanchored, format-aware, **full-population** scan | — | all spans reproduce the recorded QC instrument |

**v3 is the instructive one.** It fixed v2's column-selection bug and introduced
two new ones: the `$` anchor broke exactly the hansa case that v2 (which had no
anchor) handled, and the head-of-file sample inherited the file's **block
order** — `kilos_reviews` is ordered by market and its entire Samsara block, the
first 20k rows, has `f2 == 0`, the null marker, so no epoch-shaped value was ever
sampled. **A fix for one defect introduced another, and both produced "no date
column" — a wrong answer that looks like a fact about the data.**

## 6. Verdict

**ESTABLISHED**

1. **No acquired dataset brackets either pre-registered event.** Not with a
   90-day margin, not with any margin. Onymous is 45 d too early for the
   earliest data; Bayonet is 173 d too late for the latest.
2. **E2's stated method — reuse of E1's pipeline — is unavailable**, because
   that pipeline's panel (2018-02-19 .. 2020-01-12) covers neither event.
3. **The financial layer has no calendar anchor** (49 ordinal steps), so E2 and
   E6 are foreclosed on that side independently of §1–§2.
4. **Three of nine social tables carry no date at all**, and one
   (`hansa_reviews`) carries two date columns with different meanings.

**NOT ESTABLISHED / NOT ATTEMPTED**

- **E2 was not run.** It is reported as infeasible rather than replaced. No
  alternative event pair was selected, because selecting one after seeing which
  events the data covers is exactly the substitution that pre-registration
  exists to prevent. If a substitute is wanted it must be pre-registered as a
  new test with its own events, not entered under E2's heading.
- **Nothing about Onymous or Bayonet themselves.** This report measures data
  coverage, not takedown efficacy.

## 7. Corrections logged

| id | correction |
|---|---|
| **C-87** | **修一个缺陷引入另一个**：v3 的日期正则加了 `$` 锚，hansa 的 `2016-12-13 02:37:18.202573553 -0500 EST` 尾缀使每个值都不匹配 ⇒ **修 v2 的「挑错列」反而弄坏了 v2 本来能处理的时区名**。判据：**改检测器后必须在已知能通过的样例上复测**，不能只测新目标 |
| **C-88** | **文件头采样继承分块顺序**：kilos 按市场排序，前 20k 行全是 Samsara 块（`f2 == 0` 空标记）⇒ **epoch 列在样本里 0 次出现，被读成「无日期列」**。**样本的偏倚来自文件的拼接方式，不是列的属性** |
| **C-89** | **退化估计器给出假读数**：v4 首轮日志打印 `[stride=1 over ~2001 rows]`，而该文件有 1,217,388 行——`est` 退化成「已读行数」，stride 恒为 1。**读数是错的，但行为（全量扫描）比宣称的更好** ⇒ 已改成显式全量扫描并打印真实行数。**凡读数是算出来的，就要问它在哪个输入上退化成常数** |
| **C-90** | **我的缺陷（把完整性记录算在被检查的那台机器上）**：42_ 首版在 **pod 上**重建 manifest，`FileNotFoundError: /root/cis/_logs/results_manifest.sha256` ⇒ **manifest 是本地产物**。在 pod 上算、随包带走，等于**拿记录检查记录自己**。已拆为 pod 侧只打包、本地侧才计算与比对 |
| **C-91** | **kilos `c2` 95.6% epoch / 4.4% 非 epoch**，非 epoch 部分 = Samsara 的 `0`（10,216 / 235,905 = **4.33%**）⇒ **独立复现 C-39**（Samsara 无时间轴） |
| **C-92** | **「ragged」是相对最宽行，不是损坏**：`kilos_reviews` 235,904/235,905、`hansa_listings` 5,518/14,773 看似极高，但 kilos 无表头且自由文本内含未转义逗号 ⇒ 该计数度量的是**行宽容度变异**。**并列计数必须注明口径**（本库既有条目），否则会被读成数据损坏 |

## 8. ★ 交付核对（本地侧，2026-09-24）

```
old manifest: 83 entries ; files on disk: 89
UNCHANGED 83   ADDED 6   CHANGED 0   REMOVED 0
RE-VERIFY: 89 entries checked, 0 bad      VERIFY_OK
```

传输入口的 sha256 在两端一致（`9a67eb654c1cb24d…`，29.02 MB），是在
**另一条路径**上（SFTP + tar 解包）对同一批字节的独立核对。**83 件已记录文件
逐字节未变** ⇒ results/ 在实践中是 write-once；6 件新增 = `40_*`×3 + `41_*`×3。
