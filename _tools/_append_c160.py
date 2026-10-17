# -*- coding: utf-8 -*-
"""Append C-160 to the ledger. Append-only: no historical line is touched."""
import io
import os

LEDGER = r"D:\CIS\pipeline_reports\progress.md"

ENTRY = u"""
---

## C-160 — 2026-09-24 — ★E5p 落地产物的两条 FAIL：**一条是「关于记录」的主张，
## 一条是「关于泄漏」的候选**，两者都**不能**支撑「图臂技能不来自标签驱动学习」；
## ★同侪的池化比较**算术逐位全对、但立在 t0 混杂列上**；**决定性测量不在记录里** ⇒ 重跑已启动；
## ★同侪拟编号 **C-120 与既有条目撞号**（`progress.md:2799`），本条改用 **C-160**

### ① 同侪给的两条 FAIL，我在**主源**上逐条复核，**读数全部成立**

落地产物（已被改名为 `results/53_E5p_result.oldwriter_55d7d8f8.json`，195,651 B）：

    leakage_check.summary.shuffled_control_at_chance            = False
    leakage_check.summary.feature_filter_verification_exact     = False
    leakage_check.shuffled_label_control.test_auc_by_delta
         = {'1': 0.8106673045844783, '3': 0.8254282453923566, '5': 0.8392686039334707}
    leakage_check.feature_filter_verification.n_exact_match     = 294   (mismatch 6)

六处 mismatch 的 `features_compared[2] = 'c_self_loops'`，方向单一
（`stored[2] ∈ {1,2}` 而 `recomputed[2] = 0`）—— **与 C-159 §⑦ 独立所得逐条一致**：
**存量值对，校验器错。**

**路径更正（须写准，否则「核通过」核的对象就不对）**：
真产物**没有顶层 `summary`，也没有顶层 `deltas`**；旗标在 **`leakage_check.summary.*`**，
Δ 集合在 **`meta.deltas = [1, 3, 5]`**。同侪行文写的 `summary.X` 是简写。

### ② 同侪的池化比较：**算术全对**（我逐位复算）

| Δ | 对照池化 | mlp | graphsage | tgn | 对照−mlp | 对照−graph | 对照−tgn |
|---|---|---|---|---|---|---|---|
| 1 | 0.810667 | 0.8462 | 0.8037 | 0.7963 | **−0.0355** | +0.0069 | +0.0143 |
| 3 | 0.825428 | 0.8647 | 0.8212 | 0.8140 | **−0.0392** | +0.0042 | +0.0115 |
| 5 | 0.839269 | 0.8682 | 0.8397 | 0.8328 | **−0.0289** | −0.0004 | +0.0065 |

⇒ 「随机标签训练的对照 **≥ 两个图臂**、与 GraphSAGE 在 Δ=5 差 0.0004」**数字无误**。

### ③ ★但该比较**立在 t0 混杂列上**，故**不能**支撑同侪的头条结论

C-156 §④（**先于本次运行**、据修复版源码立的判据）已写明：池化列被 t0 混杂，
**模型只要认出这条边属于哪个 t0 就能拿到高 AUC，与标签无关**；0.81–0.84 正是该混杂的
**预期后果**；**这正是判据被移到 within-t0 的原因**。

**本次把它量出来了**：Δ=5 共 44 个 t0 分箱，**箱内正例率跨 124 倍**
（0.00152 → 0.18824）。⇒ 一个**只会说「我在哪个箱」**的打分器，在池化指标上
**本来就高于 0.5**。且洗牌若是在全训练集上做的，**每个箱仍近似保留其真实正例率**
（大数定律），模型学到的正是这个 —— 于是**对照池化 0.81 与臂池化 0.83 被同一个通道抬高**，
**两者之差不可解释**。
（**此为机制预测，不是本轮测到的读数**；判别它的是 running 的重跑。）

### ④ ★决定性测量**不在记录里**（逐键核过，非推测）

    shuffled_label_control 的键 == ['purpose', 'test_auc_by_delta']   ← 只有这两把

臂有 `within_t0_auc`（unweighted，Δ=1/3/5）：

| | Δ=1 | Δ=3 | Δ=5 |
|---|---|---|---|
| mlp_feature_only | 0.7598 | 0.7621 | 0.7708 |
| graphsage | 0.7306 | 0.7358 | 0.7450 |
| tgn | 0.7170 | 0.7241 | 0.7242 |
| **naive 基线** | **1.0000** | **1.0000** | **1.0000** |
| **对照** | **不存在** | **不存在** | **不存在** |

- 臂的 within-t0 **全在 0.5 之上**；
- naive 基线 within-t0 = **1.0000** ⇒ **该仪器活着**（能到 1.0），故 0.72 **不是退化零**；
- **对照的 within-t0 不存在** ⇒ 「对照是否落在 0.5 附近」**本记录无法回答**。

**⇒ 同侪的结论既未被证成，也未被证伪。** 它自己把这个边界写清楚了
（「band 不可导」「成因未查明，两候选未测」）——**这与本库「无记录 ≠ 未发生」一致**；
**超出边界的只是它的头条那一句。**

### ⑤ 同侪修掉的两处驱动缺陷：**源码上复核，成立**

- `ev_require` 原读**顶层** `d["deltas"]`（真产物为 `None`）⇒ **对完美产物也永远返回 False**。
  现读 `meta.deltas`，且读 `leakage_check.summary.feature_filter_verification_exact`、
  `.no_lifetime_column_in_model_matrices`、`naive_leaking_baseline.admissible is False`。
- `compute` 把 `evidence_ok` 的「present but did not succeed」**折叠成 NOT_IMPLEMENTED**，
  即把「写了但没过判据」读成「还没人写」；已分列为 **FAILED**。

**★这是本库第 16 面的近亲**：判据读错对象时，**它对任何输入都返回同一个答案** ——
**一致没有信息量**。（夹具与判据出自同一个错误模型，所以 8 变异测试漏掉了它。）

### ⑥ ★同侪拟编号 **C-120 与既有条目撞号** ⇒ 改用 C-160

`progress.md:2799` **已经是 C-120**（标题含「两处撤回…E5p 真实状态」）。
若照抄，同一台账会出现**两个不同的 C-120**。
**同侪文本中的事实我逐条核过并采纳；编号不采信。**（现最大编号 = C-159。）
**⇒ 一般形式：编号是「我派的席位」最容易出错而我又最不该照抄的一类转述。**

### ⑦ 重跑已启动（写入器已换为修复版）

| 项 | 值 |
|---|---|
| 写入器 | `53_E5p_temporal_gnn.py` sha256 `1ebf15e85fe73026…`，79,168 B，1,594 行，**pod 与本地逐字节相同** |
| launcher | `/root/cis/scripts/_run_e5p.sh`（先 `sed -i 's/\\r$//'`，CR 计数实测 **0**） |
| 日志 | `/root/cis/logs/53_full.log`；**旧日志先保全再启动，未覆盖** |
| 启动 | 2026-09-24T03:34:54Z，pid **36327** |
| 存活判据 | `ps -eo pid,lstart,cmd` **与** `/proc` 扫描**双仪器一致**（**不用 `pgrep`**，见 C-120 §③） |
| 命令 | `--epochs 6 --mlp-epochs 20 --eval-every 2`（与落地那次相同） |

**本轮要补的正是 ④ 缺的那一列**：修复版把 `shuffled_control_at_chance` 移到 within-t0，
并给对照补上 `within_t0_auc`。**若对照 within-t0 ≈ 0.5 而臂 ≈ 0.72，则同侪的头条被证伪；
若对照 within-t0 也 ≈ 0.7，则被证成。这是一个可判别的读数，不是又一次猜测。**

### ⑧ 未做／未主张

- **未把 `ev` 重指向 `oldwriter_*` 文件** —— 同意同侪：那会让驱动为一个**未过自身判据**的产物背书。
- **未宣告 E5 完成、未宣告有泄漏、未宣告无泄漏。**
- 同侪撤回的「Δ=1 排除数差 3 个」（从**舍入后的 share** 反推整数当成了测量）：
  **记录其撤回**。产物内 `delta1_equals_recurrence = {n_delta1_pos: 61487,
  n_nsteps_ge_2: 61487, identical: true}`，与该处一致。
- 产物**改名**（`.json` 拉取报 `No such file or directory` 而 `.txt` 成功）是**与我的改名竞态**，
  **不是数据丢失** —— 两个文件都在盘上。
"""

raw = io.open(LEDGER, "rb").read()
assert raw.count(b"\r\n") == 0, "ledger is CRLF; refusing to append and change its endings"
before = len(raw)
with io.open(LEDGER, "a", encoding="utf-8", newline="\n") as fh:
    fh.write(ENTRY)
after = os.path.getsize(LEDGER)
head = io.open(LEDGER, "rb").read()[:before]
assert head == raw, "append modified existing bytes -- that is not append-only"
print("ledger %d -> %d bytes (+%d), existing bytes untouched" % (before, after, after - before))
