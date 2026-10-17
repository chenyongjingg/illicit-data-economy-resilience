# CHANGELOG.md — what was deleted, where it went, and why

**Input.** `D:\CIS\submission_jksucis_anon\manuscript.tex` (85,053 B; the most
recent anonymised submission). There is no `./original/` directory and no
`main.tex` at the task's assumed path; the identification judgment is recorded in
`MISSING_INPUTS.md`. The deliverable lives at `D:\CIS\sr_version\` because the
task's input tree does not exist.

**Governing constraint.** Only deletion, restructuring and rewriting were
performed. **No number, claim, citation or figure was invented.** The real author
block and funding line were carried in verbatim from the non-anonymised
submissions, because *Scientific Reports* is single-anonymous and the task
forbids altering author/funding information. Every `.bib` entry in
`manuscript.bib` is present in `refs.bib`; **no citation entry was deleted.**

---

## 1. Front matter

| Item | Action | Reason |
|------|--------|--------|
| Title | Replaced with candidate **T1**: *Validation-first measurement of resilience in illicit data economies: a controlled study with a negative-result ledger on public data* | Must contain "validation-first"/"measurement validity" **and** "resilience"; darknet/Bitcoin appear only as scenario words in the body, never in the title. Candidate **T2** (*Measuring resilience under measurement validity: a validation-first protocol and negative-result ledger for illicit data-trading ecosystems*) is recorded in a preamble comment in `main.tex` for the author to choose at submission. |
| Abstract | Rewritten as a structured **Background / Methods / Results / Conclusions** abstract, **175 words** (PDF text layer, including the four labels) | Task cap is ≤180 words; Results is exactly three sentences, one per surviving finding. |
| Abstract, last sentence | **Deleted**: "The protocol, not any single number, is the contribution." | Declarative/manifesto sentence of exactly the kind the task names as an example to remove. Its content is not lost: it is expressed operationally by the title and by §3. |
| Abstract, `-0.49 pp` etc. | Retained verbatim; no number re-computed | Number-fidelity rule. |
| Author block / affiliation / funding / Declarations | **Preserved verbatim**; only the "Additional file" descriptions were reworded to point at the Supplementary Notes | Task prohibition on altering author/funding info; task instruction on the additional-file descriptions. |

## 2. §1 Introduction (`sections/01_intro.tex`, 589 words)

| Item | Action | Destination / reason |
|------|--------|----------------------|
| Whole section | Rewritten to the mandated **four-paragraph formula**: (1) universal problem — falsifiable measurement with no ground truth, censored data, rare events; (2) the illicit data economy as the instance; (3) what existing work lacks (no controlled validation); (4) C1/C2/C3 in one sentence each + one structure sentence | Structural requirement. |
| Original §2 **Related Work** | **Folded into Introduction paragraph 3** (one 3-sentence paragraph with `\citep{}` groups) | The four-paragraph formula has no room for a separate Related Work section; the citations are all retained, none deleted. |
| Original Introduction's declarative/manifesto framing and internal process meta-discussion | Deleted | Task prohibition (example given: the "protocol, not any single number" sentence). Standard academic hedging (e.g. "we report the null rather than the estimate") was kept. |
| `-0.49 pp` | Retained as a bold anchor | Number fidelity + bold-at-first-appearance rule. |

## 3. §2 Data (`sections/02_data.tex`, 137 words) + Table 1

| Item | Action | Destination / reason |
|------|--------|----------------------|
| Original §3 Data prose | Compressed to **three sentences**: the three layers share no time axis; all sources are public; one licence sentence | Length allocation (~0.7 page). |
| Table 1 | **Condensed from the original 9-row table to four columns Layer / Source / Size / Licence**, 9 rows retained | Task specifies the four-column form. |
| Per-source time coverage (AlphaBay right-censoring, Agora window, no-date panels, the Elliptic++ block→date anchor) | **Moved out of the body** | → **S5.1**. One clause survives in the body ("49 ordinal steps anchor from outside the data to approximately 2016-01-01 to 2017-11-03"). |
| Hansa and Valhalla dumps (51,553 reviews / 16,511 listings) | **Moved** to the Table 1 caption (as a pointer) and detailed in **S5.2** | They contribute no reported number; keeping them in the body would cost space for nothing. |

## 4. §3 Protocol (`sections/03_protocol.tex`, 1013 words) + Fig. 1

| Item | Action | Destination / reason |
|------|--------|----------------------|
| Original §4.1 **Design rule** | Kept; restated as **G1 / G2 / G3, one paragraph each** | Length allocation (C1 ≈ 1.5 pages). |
| **Two-list rule** (original §4.1) | Kept as **one paragraph** in the body; the worked reasoning | Detail → **S1.1**. It is a distinctive move and must stay visible. |
| G1 metric-validity **matrix detail** (six metrics × three criteria) | Summary kept in the body (each criterion passes two of six, no metric passes all three; `0.9859`; `0.8407`); **full matrix moved** | → **S2.4**. |
| **Feature-side separability trap** (original §4.2) | **Fully retained in the body**, including the `0.71364` vs `[0.4852, 0.5148]` comparison and the "what anchors 0.5" and "how far the repair goes" paragraphs | Task explicitly requires this core paragraph and the 0.71364-vs-0.5 comparison to survive. |
| Original §4.3 **Protocol summary** (the falsifiability list) | **Moved out of the body** | → **S1.2**. |
| Original §4.4 **Engineering discipline** (302-artifact census, 61,487) | Kept compactly in G3 (61,487) with the census boundary and the `302`, `283` accounting | Detail → **S1.3**; reproduction discipline → **S1.4**. |
| Fig. 1 (protocol flow) | **Retained as the first figure**, `figures/02_protocol_flow.pdf`, width reduced to 0.78 `\textwidth` | The task requires Fig. 1 to be kept; the width reduction is the mandated first lever for page control. |

## 5. §4 Controlled Analyses (`sections/04_analyses.tex`, 2747 words) + Table 2 + Figs. 2–3

| Item | Action | Destination / reason |
|------|--------|----------------------|
| **NEW Table 2** | Placed as the **first thing in the section**: the seven analyses × (Analysis / Layer / Headline quantity / The control that bites / What it rejected). **Every cell copied verbatim from Appendix Table A1**; no new column and no new value | Task requirement. Deliberately *not* a "seven analyses × surviving conclusion" column that does not exist in the source — inventing that column would have created new content. The A1 columns already carry what survived and what the control rejected. |
| Seven analyses | Rewritten in a **uniform four-part Q/D/C/F structure** (Question / Design / Control / Finding), 1–3 sentences per part | Readability norm; ~5 pages. |
| E7-inf, E6-fin, E1-v3 | Each additionally keeps **one "Bound" sentence** | Task requirement. |
| Original §5.4 **specification-curve coefficient listing** | **Moved out of the body**; the body keeps the demotion and the corrected magnitudes | → **S2.2**. |
| Original §5.2 E0 clustered-SE detail | Body keeps the two clustered p-values; the `14.44×` IID-vs-block comparison and the 14-day cohort trend detail are in the body/annex appropriately | Extra detail → **S2.1**. |
| Original §5.5 E5-fin withheld p-values | Body keeps the withholding; the `-27.4` pp…`+13.1` pp span rationale | → **S2.1**. |
| Original §5.9 **WP4 exploratory cross-layer association** | **Moved out of the body** | → **S2.3**. It is exploratory and is not one of the seven controlled analyses. |
| Figs. 2–3 | Fig. 2 = `E7inf_v2.pdf`; Fig. 3 = `E6fin_resilience_v2.pdf`; both at 0.58 `\textwidth`, moved to the end of the section | They support E7-inf and E6-fin, two of the three surviving findings. |
| **`E0_infra_takedown.pdf`** | **Moved to the supplementary** (not printed in the body) | Rationale: it is a full-page-tall figure (372×496.8 pt), and its finding (E0, median lifetime 1.36 days) is already carried by Fig. 2's infrastructure story and by the number in Table 2; keeping four *and* a tall fifth figure would break the ≤12-page budget. **This is a figure-placement decision, not a deletion of the finding.** |
| Original §5.8 **synthesis prose** | Compressed into the section's closing paragraph; the three `results/figs/...` source paths **scrubbed** | Zero-internal-path rule. |

## 6. §5 Negative Results (`sections/05_negative.tex`, 1105 words) + Fig. 4

| Item | Action | Destination / reason |
|------|--------|----------------------|
| Whole section | Kept and **compressed but not emasculated** — it is the paper's differentiator | Task prohibition on deleting the negative-result narrative. |
| Four independent failures (E5p/E5r) | Presented as a **four-item numbered `enumerate`** (baseline loss; negative-control band INSTRUMENT FAILED with the three cells and their rates; ablation gate failure max |d| = 0.0068; the +0.05 increment not licensable) | Nominal window `[0.005, 0.055]`, 400 draws and the three failing cells retained verbatim. |
| Trap / "how far the repair goes" / untrained floor / voided graph-side round | Kept in the body with the `0.71364→0.6561` trajectory and the vacuous-`0.5` explanation | Task requires the trap measurement and the vacuous-control explanation in the body. |
| **L1/L2/L3 anatomy** (per-configuration accounting) | **Moved out of the body** | → **S3.1**. |
| **E14 changepoint detail** | Body keeps `0/25 = 0.000` and the volume-only control; the shifted-date baselines and the substitutions | Detail → **S3.2**. |
| **E2 / E10 / EV-legacy** "three dead ends" | Kept as one short paragraph | Full anatomy → **S3.3**. |
| Fig. 4 (shuffled-control trajectory) | **Retained**, `06_shuffled_trajectory.pdf`, 0.50 `\textwidth` | It is the ledger's central exhibit and visually carries the "repair stops short" message. |

## 7. §6 Governance & Limitations (`sections/06_governance.tex`, 528 words)

| Item | Action | Destination / reason |
|------|--------|----------------------|
| Original §7 Governance | **8 numbered items → 5**, each **one sentence plus a one-sentence condition** | Length allocation (~1 page together with Limitations and Conclusion). Merge points: the two dismantling items (60%/2.5% and peripheral removal 98.88%) were kept as separate items because they answer different questions; the ethics and disclosure items were **moved into the Declarations block** (where *Scientific Reports* expects them) rather than deleted. |
| Original §8 Limitations (i)–(vii) | Kept **(i)(ii)(iii)(vi)**, each 1–2 sentences | Task specifies exactly these four. |
| Dropped Limitations (iv)(v)(vii) — metric-validity detail, external validation, novelty exhaustiveness | **Moved** | → **S2.4**, **S2.3/S5.2**, and the metric-validity note in **S2.4** respectively. A closing pointer sentence in the body names the notes. |
| Original §9 Ethics Statement | **Folded into the Declarations block** and expanded in **S5.3** | *Scientific Reports* conventions; the statement text is preserved, not dropped. |

## 8. §7 Conclusion (`sections/07_conclusion.tex`, 141 words) + back matter

| Item | Action | Destination / reason |
|------|--------|----------------------|
| Conclusion | Rewritten to **four sentences**; manifesto-type closing lines deleted | Length allocation; task prohibition on declarative/manifesto sentences. |
| Footnotes | **All footnotes deleted** (the one footnote in the source was E6-fin's right-censored marginal-cost note); its content is **inlined** into the E5-fin Bound sentence | Task requires zero footnotes. Verified: `\footnote` count = 0 in the whole tree. |
| Internal paths | **All `results/...` and `results/NN_....json` references deleted** from the body and replaced with "full audit trail in Supplementary Notes / from the corresponding authors" | Task requirement. Verified: `grep -r "results/"` over the whole deliverable returns **0** hits. The census tree names in **S1.3** are given as counts and generic tree descriptions rather than literal paths, so the zero-path rule holds there too. |
| Bibliography | `refs.bib` = the full original `.bib`, **23 entries, all preserved** | Task prohibition on deleting citation entries. |
| Back matter | Declarations block preserved verbatim at the end of `main.tex`, with the two "Additional file" entries reworded to point at Supplementary Note S1 (the census-boundary rule and the SHA-256 census itself) | Task requirement. |
| `\documentclass` | `article` (10 pt, 2.1 cm margins) instead of `wlscirep.cls` | The official class was not available offline; the content is class-agnostic and the class can be swapped at submission (documented in a `main.tex` preamble comment). |

## 9. What the supplementary now holds (S1–S5)

- **S1** — two-list rule (S1.1), falsifiability list (S1.2), the audit census
  (S1.3), reproduction discipline (S1.4).
- **S2** — full controls and every rejected estimator (S2.1), the E1-v3
  specification curve (S2.2), the WP4 exploratory association (S2.3), the
  metric-validity matrix (S2.4).
- **S3** — per-configuration de-leakage anatomy (S3.1), changepoint detail
  (S3.2), the three dead ends (S3.3).
- **S4** — family-level profile WP8 (S4.1), scenario robustness E8 (S4.2).
- **S5** — per-source time coverage (S5.1), additional and context sources
  (S5.2), licence and ethics detail (S5.3).

## 10. Build-state summary

| File | Pages | Notes |
|------|-------|-------|
| `main.tex` | **14 total** — **body = pages 1–12**, page 13 = bibliography, page 14 = Declarations | ≤12-page body goal met; the reference list and the Declarations block are back matter and are typeset after the body. |
| `supplementary.tex` | 5 | Standalone, compiles clean. |
| `cover_letter.tex` | 1 | Three paragraphs. |
| Body word count | **7481** (prose + floats); 6441 prose-only | Within the 7000–8000 target. See `wordcount.txt`. |
| Abstract | **175 words** | ≤180-word cap met. |
| Compile | `pdflatex` + `bibtex`, **0 errors** | `!`-line count = 0. |

---

## 11. Reference audit and the census-file gap (post-delivery round)

### 11.1 Every reference verified against the record of record

All **23** entries in `refs.bib` were verified by resolving the DOI or arXiv id
**parsed from the bib file itself** against Crossref / the arXiv API and
comparing the returned title, first author and year with what the entry claims:
**20 resolved clean on the first pass.**

The three that the verifier flagged are **checker artifacts, not defects**, and
each was closed against an independent source:

| Entry | Why the verifier flagged it | Resolution |
|-------|-----------------------------|------------|
| `decaryhetu2017police` | The verifier compared its year against Crossref `issued` (2016-10-29, the online-first date) | Crossref `published-print` is 2017-02, vol. 67(1), pp. 55–75 — **exactly** what the bib claims. The bib was right; the ruler read the wrong field. |
| `soska2015measuring` | No DOI registered, so the Crossref *bibliographic* fallback returned an unrelated paper | Confirmed on the USENIX Security '15 programme page: Soska & Christin, pp. 33–48. |
| `vanwegberg2018lost` | Same — no DOI registered | Confirmed as van Wegberg & Verburgh, WebSci '18 darknet workshop, pp. 1–5, Amsterdam 2018. |

### 11.2 Two real defects found by the same audit — both mine, both fixed

| Defect | How it was found | Fix |
|--------|------------------|-----|
| **Three citations dropped.** `hamilton2017inductive`, `rossi2020temporal`, `xu2020inductive` are cited in the source at "Temporal-graph models, TGN … and the temporal-attention variant of the same family … The baselines are MLP and GraphSAGE …" but were absent from the rewritten sections, leaving them as orphan bibliography entries. | Orphan scan of `main.aux` `\citation{}` against `refs.bib` | Restored verbatim in `sections/05_negative.tex`. Now **orphans 0, ghosts 0.** |
| **Reference numbering was alphabetical, not by order of first appearance.** With `plainnat`, `albert2000error` was `[1]` — non-compliant with *Scientific Reports*. | Reading the assigned numbers out of `main.aux` | `\bibliographystyle{plainnat}` → `{unsrtnat}`. Verified from `main.bbl`: the order is now exactly citation order, `soska2015measuring` = `[1]`. |

### 11.3 The Declarations promised two census files that were not in the package

The Declarations promised (a) the rule that draws the census boundary and (b)
the SHA-256 census of the 302 result artifacts. Both **existed** in the source
package and on disk, but neither was **packaged**, so the promise was unfulfilled
as delivered. Both are now shipped in `supplementary/`.

The census was not merely copied — it was **independently regenerated from the
bytes on disk** and then compared with the shipped artifact:

| Check | Result |
|-------|--------|
| Per-tree counts recomputed from the live tree | 196 / 25 / 40 / 14 / 9 / 5 / 5 / 3 / 3 / 2 → **302**, matching the declaration tree by tree |
| Regenerated census vs shipped `Appendix B` | **302 identical lines**, byte-for-byte on digest *and* path (the earlier `cmp` mismatch was line *order*: the shipped file is globally sorted, the fresh walk is per-tree) |
| Regenerated census vs the older 294-entry manifest in the working tree | 294 pairs identical, **0 lost**, the 8 extra being exactly the eight L4 outputs (4 cells × json + txt) the manuscript narrates |

`Additional file 2.txt` is shipped **byte-identical** to the source artifact.
`Additional file 1.txt` is the source rule text with an **enumerated** set of
replacements only — the header block (which still named the previous journal and
the double-anonymous placeholders) and the cross-references to the previous
manuscript's section numbering. Each replacement declares how many times it must
fire; a mismatch fails the run. Result: 127 lines in, 127 lines out; the only
digit-runs that disappeared are the four old section numbers (`4.4`, `4.3`,
`6.1`, `5.8`) and the only ones that appeared are the declared ones (`S1.3` ×6,
`Additional file 2` numbering ×5, the postcode and the e-mail, both carried
verbatim from `main.tex`). **No datum in the rule was touched.**

**Lesson recorded.** The first run of the packaging script failed on its own
count assertion: the source file is **CRLF** while its companion is LF. The
assertion caught it *before* any output was written — which is the whole point of
declaring the expected number of changes instead of measuring after the fact.
Line-ending normalization is now declared as change 0, with its own count.

### 11.4 Declarations wording corrected

Because Supplementary Note S1 only *described* the census, the sentence
"Included in Supplementary Note S1" was an over-claim. It now names the two
files, and the supplementary list in `main.tex` carries an entry for them.
Rebuilt: **14 pages, body 1–12, 0 errors**, 19/19 mandated numbers hit, 0 internal
paths, 0 `\footnote{`.

---

## 12. Upload round: figure citations, the E0 figure, and the bundle

Three things surfaced only when the package was assembled for the portal.

### 12.1 No figure was cited in the text

The four body figures carried `\label`s but **no `\ref` anywhere in the text** —
a *Scientific Reports* technical-check failure waiting to happen. Repaired with
four **bare parenthetical pointers** at sentences that are already about the
figure in question; nothing descriptive was added, so no claim is new:

| Figure | Cited at |
|--------|----------|
| Fig. 1 (protocol flow) | §3 opening, the sentence stating that the gates are general |
| Fig. 2 (E7-inf reconstitution) | §4, end of the E7-inf Finding |
| Fig. 3 (E6-fin giant component) | §4, opening sentence of the E6-fin Finding |
| Fig. 4 (shuffled trajectory) | §5, the "how far the repair goes" trajectory sentence |

Verified from the rendered text layer: the first mentions appear in the order
**Fig. 1, 2, 3, 4**, so the numbering is stable.

### 12.2 The E0 figure was in neither document — and §5 of this file said it was

`CHANGELOG.md` §5 has claimed since the first delivery that
`E0_infra_takedown.pdf` was "moved to the supplementary". It was **in neither
document**: not in the body, not in `supplementary.tex`. **A log that describes
a move does not perform it**, and no check compared the log against the tree, so
the claim stood unchallenged.

It is now actually where the log said it was: `supplementary.tex` **§S4.3**, as
**Supplementary Fig. S1**, with the source caption reproduced verbatim except
that the trailing `results/04_E0_infra_takedown.json` path is replaced by
"audited result artifact available from the corresponding author" (zero-internal-
path rule). `\renewcommand{\thefigure}{S\arabic{figure}}` makes the label print
as **Figure S1** in the supplementary only. `main.tex`'s supplementary list
names it. E0 is not one of the three surviving findings, which is exactly why it
is the one that moved.

### 12.3 The bundle

`manuscript_latex.zip` (193,576 B) — `main.tex`, `refs.bib`, `main.bbl`,
`sections/` (7), and the **four** figures the body uses. `main.bbl` is carried so
that a pipeline which does not run `bibtex` still gets its bibliography.

Verified by **clean-room compile**: the zip is extracted into an empty directory
with no `.aux` and no `.bbl` of ours, and built with `pdflatex` → `bibtex` →
`pdflatex` ×2. Result: **0 errors, 14 pages, 23 bibliography entries, 16 pages of
figures present**, `Fig. 4` and `98.88` both found in the rendered text. The zip
timestamp is pinned to 1980-01-01 so that rebuilding the same content yields the
same bytes.

### 12.4 Gate re-run after all of the above

Body 1–12 (references p13, Declarations p14); **19/19** mandated numbers (the
comma forms `61,487` and `14,266` included — a bare-digit grep misses them, and
`-0.49` needs `grep --` or the leading dash is read as a flag: both were my
rulers being wrong, not the text); 0 `results/`; 0 `\footnote{`; orphans 0,
ghosts 0; supplementary 6 pages.
