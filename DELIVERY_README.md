# CIS sprint deliverable — @@DATE_ISO@@

Produced against `数据黑产韧性研究-冲刺计划书v10.md` — the live plan, carried in
`plan/`. The sprint was launched 2026-09-24 against v5 of that plan (11 experiments,
E0–E9 plus a few-shot annotation appendix E10); v5–v9 are void per v10's own footer,
so the plan shipped here is v10. The `.docx` form is not shipped: nothing in this
tree can write it.

## Verify before reading

Run this from inside the package directory, and **read the exit status, not just
the scroll**. Expected, and measured on this package:

```
$ sha256sum -c _MANIFEST.sha256        # @@N_ENTRIES@@ entries, one line per artefact
... @@N_ENTRIES@@ lines of "...: OK"
$ echo $?
0                                      # @@N_ENTRIES@@ OK, 0 FAILED, no stderr
```

The manifest's own header repeats the count. **If the two ever disagree, the
header is right** — it is written from the tree, this sentence is written by
hand. **The two numbers above are now substituted by the packager** (`@@N_ENTRIES@@`
and `@@N_RESULTS@@` are replaced with measured values at build time), because a
hand-written count is exactly the thing that goes stale on every rebuild — this
paragraph used to say so instead of fixing it.

Every artefact in this package is hashed in `_MANIFEST.sha256`, written after
copying and then re-read from disk to check. **`_logs/results_manifest.sha256`
is the record for `results/` alone** (verify from `D:\CIS\` with `python
code/_tools/verify_results.py --check`), along with
`_logs/results_manifest.diff.txt`, which records the transition as
**215 UNCHANGED, 68 ADDED, 0 CHANGED, 0 REMOVED** — every previously-recorded
result file is byte-identical, and 68 arrived since. (This sentence read
**89 / 114** until 2026-09-25. Read the numbers off the shipped
`_logs/results_manifest.diff.txt` rather than from here: they are its output.)

⚠ **Read that diff with its coverage in mind, because the coverage changed.**
The manifest it diffs against held 215 of the 283 files; the 68 it did not cover
are exactly the `ADDED` lines in the diff, listed one per file. So **its silence
about a file was never evidence about that file** unless the file appears there,
and `CHANGED 0` is a statement about a 215-file subset rather than about the
tree. The record now covers **all 283** files, and `verify_results.py`
re-verifies against the manifest it just wrote.

Two earlier versions of this paragraph, kept because each was true of the record
it described: when this package's first build wrote it, the baseline held **89
entries, covering files numbered `41_` and below**, so everything from `42_`
onward — the whole E9 anchor chain (`42_`, `43_`, `51_`, `55_`, `57_`, `59_`,
`63_`–`71_`), E5p's probe and bench artefacts (`52_`, `53a_`, `53c_`, `53d_`),
E8's simulation (`47_`) and E10's discovery (`54_`) — sat **outside** that
record; and until 2026-09-25 the paragraph said the record covered 203 files,
which was the count at that time. This paragraph also once called the old record
"the equivalent record for `results/` alone", which was true of its *form* and
false of its *extent*.

**A note the command above earns.** The first build of this package shipped both
manifests in CRLF, because Python on Windows writes text mode by default. Every
entry then failed with `FAILED open or read`: `sha256sum` read the `\r` as the
last character of the filename. The packaging script's own re-verification
reported `0 bad` anyway, and was not wrong — Python normalises `\r\n` to `\n` on
reading, so the record could be checked by the tool that wrote it and by nothing
else. Fixed at the writer (`newline="\n"`), and the two existing records
normalised in place with no change to their content. Recorded as **C-93** in
`pipeline_reports/progress.md`. If you re-verify and it fails, believe the
command, not this paragraph.

## Layout

```
FINAL_SUMMARY.md          index of every claim, with pointers to its evidence
pipeline_reports/         ledger (progress.md) + 12 stage reports + _ref/
results/                  @@N_RESULTS@@ artefacts: per-stage .txt/.json, figures, logs
code/_server/             every stage script, as run
code/_tools/              pod transport (rsc.py), local verification,
                          gpu_preflight.py
_logs/                    the results/ integrity record
plan/                     the source plan, for provenance
```

## Headline results

- **E0** infrastructure takedown: median **1.36 d** online (n = 36,262).
- **E4** social survival: KM median **222.9 d**; **10.8 d** among listings that
  received feedback (the gap is censoring).
- **E1** substitution: volume preserved, **entry directed** (+10.5 pp vs +0.0 pp),
  intensive-margin effect **+1.0 to +2.4** reviews/week.
- **E3** attribution: **H4 supported, H1 not**, H2's substrate absent, H3 untestable.
- **E5-fin** recurrence **7.47%**, monotone in class (illicit < licit < unknown).
- **E6-fin** robust-yet-fragile; removing the **entire** illicit subgraph leaves
  98.88% of the giant component.
- **E7-inf** takedown latency **0.47–1.52 d**; reuse confers **no** persistence
  advantage; hosts that go dark **return** (13.88% within a day).

## Reported as infeasible, not substituted

- **E2** — no acquired dataset brackets either pre-registered event (Onymous is
  45 d too early for the earliest data; Bayonet 173 d too late for the latest).
  Reported as infeasible; **no alternative event pair was entered under its
  heading.**
- **E8, E10** — not run; need a GPU.
- **E9** — **the anchor IS met; this paragraph previously said it was not, and
  that statement was false when it was written.** All nine issues of the report
  the plan named were fetched and byte-verified (C-102/C-104); the series was
  recovered and consolidated with the channels asserting each value named
  (C-119); the five text-layer-less issues were OCR'd in full (C-122); and the
  anchor's own instrument was then audited against the documents (C-124/C-125/C-126).
  **What remains unmet is E9's *comparison*, which consumes E8's output** — E8 is
  not implemented, so E9's analysis cannot run. **The anchor is also not the clean
  monthly series it looks like**: the p.6 figures are query hit counts, the
  2025-10 issue's window covers September rather than October, and the documents'
  own second monthly series moves opposite to the anchor in both months the
  anchor moves sharply. Those limits are stated in
  `pipeline_reports/00_recon_and_design.md` and are part of E9's result, not a
  footnote to it.

## Blocked — and on what, in what order

There are **two** gates, not one, and the ordering matters:

1. **GPU (C-27).** `nvidia-smi` sees the RTX 4090, but `cuInit -> 100`
   (`CUDA_ERROR_NO_DEVICE`), while the card self-reports `GPU requires reset` with
   Channel/TPC Repair Pending. Every in-container remedy was tested and refused;
   **a pod restart from the console is the only one.** Confirmed four times
   independently, and reproducible with `code/_tools/gpu_preflight.py`.
2. **Missing inputs (C-13, from C-08).** **E9's half of this gate is CLOSED** — the
   anchor was fetched and verified, so "E9 has no external anchor" is no longer
   true. E10 still has no role-labelling ground truth, and E8 consumes E10's
   output, so the gate is now an E10 gate.

**The GPU is necessary but not sufficient.** Fixing it would not start E8 or E10,
because E10's half of gate 2 would still be shut. (**E9 does not enter this
argument at all** — it needs no GPU, and its anchor no longer waits on gate 2;
only its comparison waits on E8.) **So deciding C-13 should come before paying
for a restart** — otherwise the restart is bought for a precondition that is still
unmet.

**And gate 2 was cheaper than it looked** (report 11, reconnaissance only). E9's anchor
was not a substitute to be chosen — it was the report the plan already named, publicly
downloadable, verified by direct fetch — **and it has since been fetched,
byte-verified and consolidated** (C-102/C-104/C-119/C-122), so that half of the gate
is closed. E10 is the half that is genuinely blocked: its ground truth
**could not be confirmed to exist**, and no alternative was adopted — that is an author
decision, not a substitution to be made quietly.

**Data for report 11's verification** — the plan's text extraction and one verified
issue of the monthly report — is at `D:\CIS\data\external\c13_recon\`. Like all raw
data, it is **not** in this package.

## Data

**This package contains no raw data.** The corpora are 23 GB and live in `D:\CIS\data`,
backed up in the 2026-09-24 session from a pod that no longer needs to hold the only
copy; every file was checked against a hash list computed **on the pod, before the
transfer**. Only the **148 MB** of source archives in `data/raw/` are irreplaceable —
the 20 GB of `extracted/` is their decompression and the 2.1 GB Elliptic++ tree is a
public repository. See `FINAL_SUMMARY.md` §3a.

## Corrections

`pipeline_reports/progress.md` carries **@@N_LEDGER@@ entries** — counted at
build time over the ledger in this package, `## C-…` section headings, so the
number in this sentence can be checked against the bytes in front of you. They
record corrections, the intent written before each change, and the measurement
that followed it. **Four** of my
own defects changed a published conclusion in this sprint and are recorded in
place rather than quietly repaired — including one where a design's placebo
evidence was **three draws** reported as if it characterised a null, and one where
the integrity manifest was being computed **on the machine it was supposed to
check**. A fifth, **C-93**, made this package's own verification step fail as
shipped; it is described under *Verify before reading* above. A sixth, **C-96**,
downgraded a recorded GPU figure from a measurement to an artefact — on the same
machine, with the same call, the only thing that changed was the value I had
initialised it with. Details in `FINAL_SUMMARY.md` §4.

(This paragraph read "**78 distinct correction ids**" until 2026-09-25. That
number could not be reproduced from the tree under any predicate I tried —
`## C-…` headings numbered 295, distinct ids 284, and the heading words
"correction"/"defect"/"fix" give 37/15/6 — so it was replaced by a count whose
predicate is stated and whose value the packager measures. A count without its
predicate is not a fact, which is the same rule this sprint applied to its
results; the delivery face was not exempt from it.)
