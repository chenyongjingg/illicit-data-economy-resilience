# -*- coding: utf-8 -*-
"""Append the E5p/C-160 block to the CIS topic memory, and refresh its index hook."""
import io
import os

MEM = r"C:\Users\33378\.claude\projects\C--Windows-System32\memory"
TOPIC = os.path.join(MEM, "cis-blackmarket-resilience-sprint.md")
INDEX = os.path.join(MEM, "MEMORY.md")

BLOCK = u"""

## ★E5p 落地与其自身两条判据（C-160，2026-09-24）

**E5p 全量跑完（RSC_EXIT=0，2,667 s），但产物自身两条泄漏判据 FAIL**
⇒ 该产物**未过驱动判据**，已改名 `results\\53_E5p_result.oldwriter_55d7d8f8.json`
（**`results\\53_E5p_result.json` 不存在这个名字**；改名是**与我的拉取竞态，不是数据丢失**）。

- `leakage_check.summary.feature_filter_verification_exact = False`（294/300，6 处**全且仅在
  `c_self_loops`**，方向单一 stored∈{1,2}、recomputed=0）——**存量对、校验器错**（= C-159 §⑦）。
- `leakage_check.summary.shuffled_control_at_chance = False`，读的是**池化列**
  `test_auc_by_delta = 0.81067/0.82543/0.83927`。
  **★臂的池化被无标签对照压住或追平**（对照−TGN = +0.0143/+0.0115/+0.0065；
  对照−GraphSAGE = +0.0069/+0.0042/−0.0004）——**算术逐位核过，全对**。

**★★但该比较立在 t0 混杂列上，故不能支撑「图臂技能不来自标签驱动学习」：**
Δ=5 的 44 个 t0 分箱，**箱内正例率跨 124×**（0.00152 → 0.18824）。
**全训练集洗牌按大数定律保住各箱正例率** ⇒ 一个**只会说「我在哪个箱」**的打分器池化**本来就 >0.5**，
而它**不需要任何标签信息** ⇒ **对照池化 0.81 是该通道的预期后果，不是泄漏证据**
（这正是修复版把该旗标移到 within-t0 的原因；C-156 §④ 先于本次运行已立此判据）。
**臂的 within-t0（unweighted）0.7170/0.7241/0.7242（TGN）· 0.7306/…（GraphSAGE）· 0.7598/…（MLP）
全在 0.5 以上；naive 基线 within-t0 = 1.0000 ⇒ 该仪器活着（能到 1.0），0.72 不是退化零。**
**⇒ 对照的 within-t0 —— 唯一能裁决的读数 —— 不在记录里**（`shuffled_label_control` 的键**只有**
`['purpose','test_auc_by_delta']`）⇒ **同侪的结论既未证成也未证伪。**

**重跑已启动**（补这一列）：写入器修复版 `1ebf15e85fe73026`（pod 与本地逐字节同，79,168 B，1,594 行）；
launcher `/root/cis/scripts/_run_e5p.sh`；日志 `/root/cis/logs/53_full.log`（**旧日志先保全再启动**）；
**2026-09-24T03:34:54Z，pid 36327**，存活以 `ps -eo pid,lstart,cmd` **与** `/proc` 双仪器确认。

**★纪律增量**：
- **席位最容易错、而我最不该照抄的就是「编号」**——同侪拟登记的 **C-120 与 `progress.md:2799`
  既有条目撞号**，照抄会让同一台账出现两个 C-120 ⇒ 本条实为 **C-160**（现最大编号）。
  **其文本中的事实逐条核过并采纳，编号不采信。**
- **判据读错对象 ⇒ 对任何输入返回同一答案**：驱动 `ev_require` 原读**顶层** `d["deltas"]`
  （真产物 `meta.deltas`），**对完美产物也永远 False**；夹具与判据出自同一个错误模型，
  故 8 变异测试漏掉它 ⇒ **一致没有信息量**（本库第 16 面近亲）。
  另 `compute` 曾把 `evidence_ok` 的「present but did not succeed」折叠成 `NOT_IMPLEMENTED`
  （=把「写了没过判据」读成「还没人写」），两态须分开。
- **`pgrep` 在本 pod 不可用作存活判据**（C-120 §③）；本次改用 `ps` + `/proc` 双仪器。
"""

raw = io.open(TOPIC, "rb").read()
assert raw.count(b"\r\n") == 0, "topic memory is CRLF"
before = len(raw)
with io.open(TOPIC, "a", encoding="utf-8", newline="\n") as fh:
    fh.write(BLOCK)
assert io.open(TOPIC, "rb").read()[:before] == raw, "not append-only"
print("topic %d -> %d (+%d)" % (before, os.path.getsize(TOPIC), os.path.getsize(TOPIC) - before))

# index hook: append a compact line rather than rewriting the existing hook
idx = io.open(INDEX, encoding="utf-8").read()
HOOK = (u"- **★E5p 落地（C-160，09-24）**：跑完但自身两条判据 FAIL；"
        u"**池化列被 t0 混杂（44 箱正例率跨 124×）⇒ 无标签对照的 0.81 不是泄漏证据**；"
        u"**决定性读数（对照 within-t0）不在记录里 ⇒ 重跑中（pid 36327）**。"
        u"详见 [cis-blackmarket-resilience-sprint](cis-blackmarket-resilience-sprint.md) 末节。\n")
if "★E5p 落地（C-160" not in idx:
    with io.open(INDEX, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(HOOK)
    print("index hook appended")
else:
    print("index hook already present")
