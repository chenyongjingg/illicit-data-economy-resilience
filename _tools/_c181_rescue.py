# -*- coding: utf-8 -*-
"""C-181: the pod restart -- what it cost, what it did NOT fix, and the rescue.

Two rules are load-bearing in this file and are asserted, not trusted:

  1. APPEND-ONLY. The ledger's existing bytes are compared before and after; a
     single changed byte fails the write. (Historical lines are never edited.)
  2. THE CREDENTIAL IS NOT WRITTEN HERE. The ledger is itself a delivered and now
     published artefact, so quoting the password while reporting that the password
     leaked would repeat the defect one level out. It is referred to by location
     (`_tools/rsc.py`, the `CIS_PASS` fallback at :39), which is precise and
     checkable without reproducing it.
"""
import io
import os
import re
import sys

LEDGER = r"D:\CIS\pipeline_reports\progress.md"

# ★ C-206. This used to be the literal assembled from two 8-character pieces, on the
# theory that a split literal cannot be grepped out of this file either. It can: the
# two halves sit on one line with a `+` between them, so any reader -- and any search
# for either half -- recovers the credential at once. What the split DID stop is the
# project's own gate (`_build_repo_stage.py:scan()`), which searched only the
# contiguous form and therefore reported CLEAN. The net effect was zero protection and
# a blinded audit. Recovered at runtime instead, and the failure is loud.


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _needle import NEEDLE as _LITERAL  # noqa: E402  C-206: recovered positionally, never written

ENTRY = """

---

## C-181 — 2026-09-24 — ★★**平台重启**：它**没有修好 GPU**，却**杀掉了 rc4**；
## 并记本轮的两项**交付层**缺陷（包内携带服务器口令／清单与包由两个选择式生成）＋一次极限抢救

### ① 重启的读数：**同一张降级卡被挂回来了**

重启后（pod `up 0 min`、04:56Z）实跑 `_tools/gpu_preflight.py -v`（**我自己的副本，sha256 `e30c102a…`，与 pod 上逐字节相同**）：

```
nvml           listed          1 card(s)  RTX 4090 uuid=GPU-f28bd3c6-f5e5-78c6-2d72-617b0e7e5b71
nvml_health    repair_pending  GPU requires reset, Channel Repair Pending, TPC Repair Pending
cuda_driver    fail            cuInit rc=100, cuDeviceGetCount rc=3 n=-1
torch          2.5.1+cu124
torch_cuda     unavailable     torch.cuda.is_available() == False
GPU_PREFLIGHT: NVML_ONLY_NO_CUDA      EXIT=2
```

**三个 repair 标记逐字回来、uuid 同一张、`cuInit` 仍是 100（`CUDA_ERROR_NO_DEVICE`）**
⇒ **C-27 的判据（本 pod 上跑 preflight，NVML 看见卡不算通过）明确未过**。
**⇒ 重启的处置方向是错的：平台把同一张卡挂回来，而请求原文已经写明「重挂同一张坏卡无用」。**
**下一步的口径必须改成：换一张物理卡（或对该卡做硬件复位），并报出 uuid 与三行健康读数。**
★同侪 session 独立测得同一 uuid、同样三行、同样 verdict ⇒ **两方独立**（且我这份是**自己的仪器、自己的副本**跑的）。

### ② 重启杀掉了 rc4：死因是**外部**，与 rc2/rc3 并列登记

| 运行 | 死因 | 体例 |
|---|---|---|
| rc2 | 我提议的一次改动 | 已记 |
| rc3 | 一次**未被记录**的截断 | 已记 |
| **rc4** | **平台重启（外部）** | **本行** |

**证据链**：header `_rc4_launch.out` = `2026-09-24T04:23:37Z`；日志末行 `[53 1653.5s] tgn ep3 loss 2.9986 val None (113s)`；
`04:23:37Z + 1653.5s = 04:51:10Z`；pod `up 0 min`（04:56Z）；无 `53_E5p` 进程存活；`results/` 下**无** `53_E5p_result.json`。
⇒ **rc4 覆盖 27.6 分钟，SAGE 臂跑完（best val 0.817130344131379 @ep6），死于 TGN ep3，约 70% 处。**
★**「无产物」不等于「无事发生」**——一个只看到空 `53_E5p_result.json` 的后来者会重新起诉一次**被外部杀掉**的运行，
所以死因按与 rc2/rc3 相同的体例写进运行表。

### ③ ★rc4 的**设备**：rc4 与「已落地」那次跑在**同一设备**上，而**记录里一个字都没有**

`grep -ic 'cuda\\|cpu\\|thread'` 在 **`53_full.landed_55d7d8f8.log` 上返回 0** —— **这两份记录里不存在设备词汇**
⇒ **一次 CPU 运行和一次 GPU 运行在那份记录中不可区分**，且**落地那次的设备事后无法从记录恢复**。

**但可以独立推定，用的是值不是时间**：落地日志与 rc4 日志在**9 个重叠读数上逐位相同**——

```
sage ep2 0.7878481324856293 / ep4 0.8066557132006477 / ep6 0.817130344131379
tgn  ep2 0.7763413239077487                      （仅墙钟秒数不同）
```

⇒ **同设备、同代码路径、数值层可复现**。（**这是从值相等推出的，不是说出来的**；
**墙钟不可用作判据**，它每次都不同。）
**⇒ rc5 的设备 = CPU**（与 rc4 同机同卡不可用），**而这一次它被写进运行头**。

**★纪律**：**「设备未记录」必须照实写成「未记录」，不能用「大概是 CPU」代替**——
一个设备未知的数**不是完全指定的数**（cuDNN/cuBLAS 与 scatter-atomic 归约非位确定，而本项目许可带是 ±0.05）。
同侪指出这一点是对的，故本轮把设备行**加在运行之前**（`_tools/_device_block.py`），
并遵我自己登记过的**哨兵规则**：`is_available()` 为 False 时 `device_count` **不打印 0**（0 正是「真的没有卡」也会打印的值，
两个来源的 0 相撞会遮住坏通道），打印 `-1` 并在同一行注明 **UNMEASURED**。

### ④ rc5：同一写入器、CPU、新 run id

`_run_53_full_rc5.sh`：**先断言写入器 sha = `077cb379…`（与 rc4 同）**，
再断言要保留的确实是 rc4 的日志（header 含该 sha、且**不含** `RSC_EXIT=`，即「未终结」才允许重跑），
然后截断，**并断言截断生效**——判据取 `^\\[53 ` **不存在**（rc3 的教训：注释描述了截断而代码没写这句；
且**行数不能再作判据**，因为头里现在有长度可变的设备块）。
**`rsc.py bg` 自身以 `: > {log}` 开场** ⇒ 若把 `53_full.log` 交给 `bg`，rc4 的日志会在我的保留步骤之前就被清掉；
故 `bg` 的日志目标是 `_rc5_launch.out`，两个文件各恰一个 `RSC_EXIT=`。

### ⑤ ★交付层缺陷一：**读者那份交付包里带着服务器口令**

```
./_tools/rsc.py:39                                             <- CIS_PASS 的默认值
./output/cis_sprint_20260924/code/_tools/rsc.py:39             <- 同一行，**在交付物内**
./output/_superseded_cis_sprint_20260924_build1..6/code/_tools/rsc.py:39
```

**共 8 份**（现役包 + 全部 7 个 `_superseded_*`）。同目录 `.rsc_cache.json` 另带 pod 的 IP。
⇒ **本项目的交付物携带运行环境的凭据**。修法：**去掉默认值，只读环境变量**（包里只剩变量名）。
★**顺序不可颠倒：秘密不能先提交再删除——`git log -S` 是公开面**（与 09-19 三仓重建同一条轴）。
★**报告「口令泄漏」时不得把口令抄进台账**：台账自身是交付物，抄一遍就是**把同一缺陷向外复制一层**。

### ⑥ ★交付层缺陷二：**清单与包由两个选择式各自生成，于是必然不一致**

抢救时我先用一条 `find` 生成 `_rescue_manifest.sha256`（343 行），再用**另一条**（不同的 `-name` 表）打 `tar`。
两条式子的 `-name` 列表**差一个 `*.sha256`** ⇒ 清单里列了 `results_manifest.sha256`，**而包里没有它**。
校验立刻报出来：`sha256sum -c` 得 **341/343 OK**，两处失配——
① 清单**包含了它自己**（自指，无法自洽）；② `results_manifest.sha256` **列而未装**。
⇒ **凡「A 描述 B」的成对产物，A 与 B 必须由同一个选择式生成**，否则 A 变成对「包里没有的集合」的断言。
（与第 06 轮冻结记录「清单能错、哈希不会对错文件」同族：**清单是可错的那一半**。）

### ⑦ 抢救结果（内容级核对，非按名核对）

pod 上的量：`data/` **23 G / 169,604 件**（其中 `extracted/` 20 G / 169,541 件）。

**判据 = 内容**：`data/raw` **5/5 与本地逐字节相同**（`C-94` 的口径在删机前复核通过）；
`data/external` + `data/_recon` 共 25 件按 sha256 逐件比对 ⇒ **0 处失配**；
打包 65,865,393 B，落地后 `sha256sum -c` **341/343 OK**（两处已解释如上）。
**补齐 5 件本地缺失的 E10 件**（均在 `data/external/c13_recon/`）：
`44_E10_groundtruth_search.json`、`45_E10_endpoint_discovery.json`、`46_E10_oai_harvest.json`、
`46_E10_oai_titles.txt`、**`50_E10_records_full.jsonl`（96,648,992 B）**。
★**这 5 件与 C-13 直接相关**（E10 的真值搜索与端点发现），**此前从未落地** ——
**「按名找过没有」不等于「不存在」**：它们是**放在 `data/` 下而不是 `results/` 下**的数据，按结果目录找永远找不到。

**未取的两棵大树，理由是「可导出」而非「不重要」，并记下可核指纹**（不取 23 G 是把热点带宽用在刀刃上）：

| 树 | 件数 | 字节 | **文件列表 sha256（前 32）** |
|---|---|---|---|
| `data/extracted` | 169,541 | 21,257,014,304 | `0e583ff41e0556539e4dc3979f475af6` |
| `data/EllipticPlusPlus-main` | 32 | 2,221,824,034 | `93470ed6d36a5ec8aebd71fe81857ee7` |

导出输入在包内（`data/raw/` 5 件 ＋ `EllipticPlusPlus.tar.gz`）⇒ **列表哈希使它们可核而不必传输**。

### ⑧ 我在本轮自己身上抓到的同一个错（第三次，形态最轻）

```
du -sh raw data _tools output 2>/dev/null && echo "=== secrets ===" && grep -rn "<password>" .
```
`raw/` 不存在 ⇒ `du` 非零退出 ⇒ **`&&` 短路，口令扫描根本没跑**。
**若我照当时的屏幕回话，就会报出「未发现秘密」——而那个判断来自一次未执行的扫描。**
**同族**：守卫的谓词不是它守卫的量（C-179）、注释声称了代码没做的事（rc3）。
**处置**：判据链上的分隔符一律用 `;` 而非 `&&`；**并在报告里给出产生该读数的命令**。
"""
raw = io.open(LEDGER, "rb").read()
led = io.open(LEDGER, encoding="utf-8").read()
assert "## C-181" not in led, "C-181 already appended"
assert _LITERAL not in ENTRY, "the credential must not be written into the ledger"
io.open(LEDGER, "w", encoding="utf-8", newline="").write(led + ENTRY)
after = io.open(LEDGER, "rb").read()
assert after.startswith(raw), "LEDGER PREFIX CHANGED -- append-only violated"
assert after.count(b"\r\n") == 0, "CRLF introduced -- the ledger is LF-only"
print("ledger: C-181 appended (%d -> %d B, %d lines)"
      % (len(raw), len(after), after.count(b"\n")))
assert _LITERAL not in after.decode("utf-8", "replace"), "credential present in ledger"
print("assertion: the credential does NOT occur anywhere in the ledger")
