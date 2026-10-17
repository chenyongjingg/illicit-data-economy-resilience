# number_check.md — key number → original section → new section

Source manuscript: `D:\CIS\submission_jksucis_anon\manuscript.tex`
(85,053 B, 572 lines, the most recent anonymised submission). Section names below
are the original manuscript's; new-file names are relative to `D:\CIS\sr_version\`.

**Rule applied throughout.** Every number retained in the new version is copied
character-for-character from the original. Nothing was rounded, merged,
recomputed, rescaled or re-expressed. Where the original printed a number in a
comma form (`61,487`, `14,266`), the comma form is preserved — the checklist's
comma-less forms (`61487`, `14266`) match the same tokens and are noted in the
table. Where the original printed a value inside `\textbf{}` (a bold anchor), the
bold is kept; **bold is used for at-first-appearance anchors in each section**,
per the fast-read norm, and never changes the digits.

## A. The mandated 19-number checklist

| # | Number | Original section (§ / subsection) | New location | Verbatim? |
|---|--------|-----------------------------------|--------------|-----------|
| 1 | `98.88` | §5.6 Structural position of the illicit subgraph (E6-fin v2); also Introduction, Governance | `main.tex` abstract; `sections/04_analyses.tex` (E6-fin); `sections/06_governance.tex` item 2 | yes (`98.88\%`) |
| 2 | `13.88` | §5.1 Host reconstitution after infrastructure takedown (E7-inf); Governance; Conclusion | `main.tex` abstract; `sections/04_analyses.tex` (E7-inf ×2); `sections/06_governance.tex` item 3 | yes (`13.88\%`) |
| 3 | `1.36` | §5.2 Infrastructure survival after listing (E0); also E4, synthesis, Governance, Conclusion | `main.tex` abstract; `sections/04_analyses.tex` (E0); `sections/06_governance.tex` item 3 | yes |
| 4 | `222.9` | §5.3 Product survival in the social layer (E4); synthesis; Conclusion | `sections/04_analyses.tex` (E4) | yes |
| 5 | `10.5` | §5.4 Directional displacement after a market seizure (E1-v3); Governance; Conclusion | `main.tex` abstract; `sections/04_analyses.tex` (E1-v3); `sections/06_governance.tex` item 5 | yes (`+10.5`) |
| 6 | `0.71364` | §4.2 The feature-side separability trap; §6.1 E5p/E5r | `sections/03_protocol.tex` (×3); `sections/05_negative.tex`; `supplementary.tex` S3.1 | yes |
| 7 | `0.6561` | §4.2 trap; §6.1 E5p/E5r | `sections/03_protocol.tex`; `sections/05_negative.tex` (×2); `supplementary.tex` S3.1 | yes |
| 8 | `0.5000` | §6.1 Temporal prediction of recurrence (E5p/E5r) | `sections/05_negative.tex` (×2); `supplementary.tex` S3.1 | yes |
| 9 | `61487` | §4.4 Engineering discipline; §5.5 E5-fin; Conclusion | `sections/03_protocol.tex` (G3, as `61,487`); `sections/04_analyses.tex` ×2 (as `61,487`); `supplementary.tex` S1.4 | yes — **printed as `61,487` in both original and new; the checklist's comma-less `61487` matches this token** |
| 10 | `14266` | Introduction; §5.6 E6-fin | `main.tex` abstract; `sections/04_analyses.tex` (E6-fin) | yes — **printed as `14,266`** |
| 11 | `1.734%` | Introduction; §5.6 E6-fin | `main.tex` abstract; `sections/04_analyses.tex` (E6-fin as `1.734\%`) | yes |
| 12 | `3.645` | §5.6 E6-fin | `sections/04_analyses.tex` (E6-fin) | yes |
| 13 | `10.803` | §5.6 E6-fin | `sections/04_analyses.tex` (E6-fin) | yes |
| 14 | `2.24` | §5.1 E7-inf; Conclusion | `main.tex` abstract; `sections/04_analyses.tex` (E7-inf ×2) | yes (`2.24\%`) |
| 15 | `6.2` | §5.1 E7-inf; §5.4 E1-v3; synthesis; Governance; Limitations; Conclusion | `main.tex` abstract (`6.2\times`); `sections/04_analyses.tex` ×4; `sections/06_governance.tex`; `sections/07_conclusion.tex` | yes |
| 16 | `1.4031` | §5.6 E6-fin; Governance | `sections/04_analyses.tex` (E6-fin) | yes |
| 17 | `34.2723` | §5.6 E6-fin; Governance | `sections/04_analyses.tex` (E6-fin) | yes |
| 18 | `-0.49` | Introduction; §5.1 E7-inf; Conclusion | `sections/01_intro.tex` (`-0.49\,pp`); `sections/04_analyses.tex` ×2 | yes |
| 19 | `0.8047` | §5.7 Causal attribution of resilience (E3); Conclusion | `sections/04_analyses.tex` (E3 ×2) | yes |

**Verification method.** After the final build, `pdftotext -layout main.pdf` was
run and each of the 19 strings was counted in the extracted text layer (with the
comma form counted for entries 9 and 10). Result: **all 19 hit; none missing.**
The same 19 strings were also located in the LaTeX sources of both the original
and the new tree, and each new occurrence was read in context and confirmed to
carry the same meaning, the same unit and the same comparison as in the original.
Two independent counting passes (source-tree grep and PDF text layer) were used
deliberately, because a number that survives in one representation and not the
other is exactly the failure this check exists to catch.

## B. Other numbers retained (spot-checked, context-verified)

| Number | Original section | New location |
|--------|------------------|--------------|
| `0.71174`, `0.71584` | §4.2 trap (per-horizon shuffle readings) | `sections/03_protocol.tex` |
| `[0.4852, 0.5148]`, `[0.4858, 0.5142]`, `[0.4812, 0.5188]` | §4.2 trap (permutation bands) | `sections/03_protocol.tex`, `sections/05_negative.tex` |
| `0.4897–0.5141`, `0.01406` | §4.2 "what anchors 0.5" | `sections/03_protocol.tex` |
| `0.71556`, `0.71758`, `0.69372`, `0.56115` | §4.2 arm readings | `sections/03_protocol.tex` |
| `0.7155632`, `0.7136417`, `0.6560979` | §6.1 L1/L2/as-built | `sections/05_negative.tex`, `supplementary.tex` S3.1 |
| `0.6378`, `0.3672–0.6378` | §6.1 untrained floor | `sections/05_negative.tex`, `supplementary.tex` S3.1 |
| `0/25 = 0.000`, `0.040` | §6.2 changepoint E14 | `sections/05_negative.tex` |
| `1.0` (test AUC, trap) | §6.1 | `sections/05_negative.tex` |
| `0.0700`, `0.0650`, `[0.005, 0.055]`, `400 draws` | §6.1 negative-control band | `sections/05_negative.tex` |
| `0.0068`, `1e-3` | §4.4 / §5.8 / §6.1 ablation gate | `sections/03_protocol.tex`, `sections/05_negative.tex` |
| `302`, `283`, `196`, `25`, `40`, `14`, `9`, `5`, `5`, `3`, `3`, `2` | §4.4 census | `supplementary.tex` S1.3 |
| `80.77\%`, `61.49\%`, `1.31\times` | §5.6 / Governance item 4 | `sections/06_governance.tex` |
| `60\%`, `2.5\%` | §5.6 / Governance item 1 | `sections/06_governance.tex` |
| `-0.7206`, `0.6867`, `[0.5365, 0.7206]`, `0.5038`, `50.4\%`, `4 distinct values` | §5.9 WP4 | `supplementary.tex` S2.3 |
| `3.2892–4.1176`, `3.7755`, `0.00e+00`, `0.0360`, `3.6005`, `3.6365`, `489`, `158`, `2.2926–4.2076`, `0.1468`, `0.2723`, `+1.0424`, `+2.4426` | §5.4 E1-v3 spec curve | `supplementary.tex` S2.2 |
| `0.1736`, `0.5978`, `14.44\times`, `-27.4` pp, `+13.1` pp | §5.2 E0 / §5.5 E5-fin | `supplementary.tex` S2.1 |
| `51,553`, `16,511` | §3 Data | `supplementary.tex` S5.2 |
| `66.582` pp, `8` families, `200` rows | §Appendix WP8 | `supplementary.tex` S4.1 |
| `-1583.33`, `2.4426`, `648\times`, `0.73–0.77` | §Appendix E8 | `supplementary.tex` S4.2 |
| `1.0016`, `[0.9999, 1.0034]`, `p = 0.070` | §5.2 E0 trend | `sections/04_analyses.tex` |

## C. Numbers deliberately not carried into the main text

All are retained in `supplementary.tex`; none is deleted from the submission.
They were moved out of the ≤12-page body under the length allocation, not
dropped:

- Per-configuration de-leakage accounting (L1/L2/L3 detail) → **S3.1**.
- Specification-curve coefficient listing → **S2.2**.
- Metric-validity matrix detail (the six metrics, per-criterion) → **S2.4**
  (summary sentence retained in `sections/03_protocol.tex` G1, including
  `0.9859` and `0.8407`).
- Exploratory cross-layer association (WP4) → **S2.3**.
- Family-level profile (WP8) → **S4.1**.
- Scenario robustness (E8) → **S4.2**.
- Per-source time coverage and the Elliptic++ block→date anchor → **S5.1**.

## D. Note on the two comma-form entries

The mandated checklist writes `61487` and `14266`. Both numbers are printed in
the original manuscript **with thousands separators** (`61,487`, `14,266`) — in
the abstract, in the census and in the E6-fin subsection. The new version
preserves the original's comma form exactly, because altering the separator would
be a change to the surface form of a number the task requires to be verbatim. A
comma-less grep of the PDF text layer therefore returns 0 raw hits for these two
strings while the comma-form grep returns 3 and 2 hits respectively; both counts
are reported in REFLECT_LOG.md rather than silently reconciled.
