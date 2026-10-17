# illicit-data-economy-resilience

Code, derived results and the research log behind the manuscript

> **Validation-first measurement of resilience in illicit data economies: a
> controlled study with a negative-result ledger on public data**

submitted to *Scientific Reports*.

The study asks whether an illicit data economy absorbs a disruption and resumes
function, and it reports the answer under controls able to reject it. Several of
the answers are negative and are kept, with their reasons, rather than dropped.

## Status

**Private, while the manuscript is under review.** It becomes public on
acceptance.

This file does not carry a status report of its own: the authoritative record of
what ran, what was measured, and what was later refuted is
[`pipeline_reports/progress.md`](pipeline_reports/progress.md), an append-only
ledger of numbered entries (`C-01` …). A summary here would be a second account
of the same thing, and the two would drift — an earlier revision of this file
listed open items that had since closed.

## Layout

| path | what it is | files |
|---|---|---|
| `manuscript/` | the submission: LaTeX source, compiled PDFs, figures, supplementary material | 25 |
| `_server/` | the experiment pipeline, one script per stage | 97 |
| `_tools/` | the harness: remote execution, verification and audit tools | 99 |
| `results/` | derived results and figures | 163 |
| `pipeline_reports/` | the append-only ledger, per-experiment reports, reference tables | 65 |
| `data/` | **hashes only** — no corpus bytes | 1 |
| `数据黑产韧性研究-冲刺计划书v10.md` | the governing sprint plan, v10 | 1 |

## The manuscript

`manuscript/main.tex` is the body; it `\input`s `manuscript/sections/`.
`manuscript/supplementary.tex` is standalone. Both are plain `article` class and
build with pdflatex:

```bash
cd manuscript
pdflatex -interaction=nonstopmode main.tex
bibtex   main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

`manuscript/manuscript_latex.zip` is the bundle that was uploaded to the journal
(figures packed in, compiled by the journal's own service). The two plain-text
files under `manuscript/supplementary/` are the additional files the manuscript
cites: the rule that draws the census boundary, and the census itself.

## What is not here

**No corpus.** Every source dataset is third-party and governed by its own terms.
[`data/README.md`](data/README.md) pins each one by URL and SHA-256 instead, so
the inputs can be fetched and checked rather than trusted.

**Not all of the census.** `manuscript/supplementary/Additional file 2.txt` is a
302-entry SHA-256 census of the study tree's result artifacts. 163 of those are
here and byte-identical to their census entry; 139 are not, 46 of them because
they are reproductions of a third party's report. The census is *not* edited to
match what ships — a census rewritten to agree with the shipment measures the
shipment, not the study. [`NOT_REDISTRIBUTED.md`](NOT_REDISTRIBUTED.md) lists
every withheld entry and why.

## The audit trail

Three logs, and they do different jobs:

* `pipeline_reports/progress.md` — the ledger. **Append-only.** A wrong claim is
  corrected by a new dated entry, never by editing the entry that made it, so
  several entries exist only to record that an earlier entry was wrong.
* `ERRATA.md` — defects found after a package had already been built, and what
  was done about each.
* `manuscript/CHANGELOG.md` — what the manuscript's condensation changed, by
  section, with the check that verified each change.

`manuscript/number_check.md` and `manuscript/wordcount.txt` trace the numbers and
the length budget that the submission is required to meet.

## One incident, recorded rather than removed

An early revision of `_tools/rsc.py` carried a live host and password as literal
defaults, which put a working credential into every delivery package built from
it. The defaults are gone — the runner now reads `CIS_HOST`, `CIS_PORT` and
`CIS_PASS` from the environment and fails loudly when any is absent — and the
incident is kept in the ledger (`C-181`), in `ERRATA.md` and in
`OPERATIONS.md` rather than quietly deleted. The manuscript discloses it too.
No credential value appears in this repository or in its history.

## Line endings

`.gitattributes` sets `* -text`: **line endings are never normalised.** Some
artifacts here are checksum manifests consumed by POSIX tools over data produced
on another machine, and a manifest's line endings are part of the manifest — a
CRLF manifest makes `sha256sum -c` read a carriage return into every filename and
fail on all of them, while a checker written in Python, which reads in
universal-newline mode, reports success. The checker and the thing it checks
sharing a blind spot is not a passing test.

## Running the pipeline

The pipeline was driven against a remote execution host through `_tools/rsc.py`,
a small paramiko client. It takes its connection details from the environment and
has no defaults:

```bash
export CIS_HOST=...
export CIS_PORT=...
export CIS_PASS=...
python _tools/rsc.py stat
```

`CIS_USER` alone keeps a default, because an account name points at nobody's
host. See [`OPERATIONS.md`](OPERATIONS.md) for how the runner resolves its
environment.
