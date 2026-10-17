# Artifacts that are not redistributed here

`manuscript/supplementary/Additional file 2.txt` is the SHA-256 census of the
**study tree** -- the 302 result artifacts the project produced. This repository
is a *distribution subset* of that tree, and the census is not edited to match
it: a census that is rewritten to agree with whatever is being shipped measures
the shipment, not the study.

The arithmetic, verified by `manifest_bind.py` at each build:

| | count |
|---|---|
| manifest entries | 302 |
| **present here and byte-identical** | **163** |
| withheld, third-party reproductions | 46 |
| withheld, other | 93 |
| hash disagreements | **0** |

For every artifact that *is* here, the file's SHA-256 equals the census entry
for it, so the manifest doubles as a receipt for this subset: 163 of 302 entries
can be checked against a file in this repository.

## 1. Third-party reproductions (46 files)

These are pages, page text and full-document OCR of the nine monthly
breach-posture reports (Digital World Consulting) that the manuscript's
Supplementary Note S5.2 describes as *qualitative motivation only*, explicitly
not used as evidence. Reproducing a third party's report in full, in a public
repository, is redistribution rather than reproducibility, and nothing in the
manuscript needs it. The report numbers themselves are carried by the audited
artifacts that remain:

    results/57_E9_ocr_p6.json       per-issue headline counts, with controls
    results/59_E9_ocr_full.json     OCR provenance: pages, character counts
    results/71_E9_query_windows.json  the declared window per issue

    results/57_ocr_2025-01_p06.png
    results/57_ocr_2025-01_p06.txt
    results/57_ocr_2025-02_p06.png
    results/57_ocr_2025-02_p06.txt
    results/57_ocr_2025-03_p06.png
    results/57_ocr_2025-03_p06.txt
    results/57_ocr_2025-04_p06.png
    results/57_ocr_2025-04_p06.txt
    results/57_ocr_2025-06_p06.png
    results/57_ocr_2025-06_p06.txt
    results/57_ocr_2025-07_p06.png
    results/57_ocr_2025-07_p06.txt
    results/57_ocr_2025-08_p06.png
    results/57_ocr_2025-08_p06.txt
    results/57_ocr_2025-10_p06.png
    results/57_ocr_2025-10_p06.txt
    results/57_ocr_2025-11_p06.png
    results/57_ocr_2025-11_p06.txt
    results/57_p06/2025-01.txt
    results/57_p06/2025-02.txt
    results/57_p06/2025-03.txt
    results/57_p06/2025-04.txt
    results/57_p06/2025-06.txt
    results/57_p06/2025-07.txt
    results/57_p06/2025-08.txt
    results/57_p06/2025-10.txt
    results/57_p06/2025-11.txt
    results/59_ocr_full_text/59_ocr_full_2025-06.txt
    results/59_ocr_full_text/59_ocr_full_2025-07.txt
    results/59_ocr_full_text/59_ocr_full_2025-08.txt
    results/59_ocr_full_text/59_ocr_full_2025-10.txt
    results/59_ocr_full_text/59_ocr_full_2025-11.txt
    results/_e9_pages/2025-01_p04.png
    results/_e9_pages/2025-01_p05.png
    results/_e9_pages/2025-01_p06.png
    results/_e9_pages/2025-01_p07.png
    results/_e9_pages/2025-06_p06.png
    results/_e9_pages/2025-06_p06_box.png
    results/_e9_pages/2025-07_p04.png
    results/_e9_pages/2025-07_p05.png
    results/_e9_pages/2025-07_p06.png
    results/_e9_pages/2025-07_p07.png
    results/_e9_pages/2025-08_p06.png
    results/_e9_pages/2025-10_p06.png
    results/_e9_pages/2025-10_p06_box.png
    results/_e9_pages/2025-11_p06.png

## 2. Other unsatisfied census entries (93 files)

These were produced by the project but are not part of the released subset:
intermediate re-runs, superseded revisions of a result, and per-cell receipts
kept in the working tree rather than promoted into the distribution. Their
digests stay in the census because the census is the study tree's record.

    results/47b_E8_rc2.json
    results/47b_E8_rc2.txt
    results/53_E5p_l4_L2_off.json
    results/53_E5p_l4_L2_off.txt
    results/53_E5p_l4_L2_on.json
    results/53_E5p_l4_L2_on.txt
    results/53_E5p_l4_L3_off.json
    results/53_E5p_l4_L3_off.txt
    results/53_E5p_l4_L3_on.json
    results/53_E5p_l4_L3_on.txt
    results/53_E5p_result.077cb37906477179.json
    results/53_E5p_result.077cb37906477179.txt
    results/53_E5p_result.json
    results/53_E5p_result.txt
    results/53_E5p_result_oldwriter_55d7d8f8.json
    results/53_E5p_result_rc6.json
    results/53_E5p_result_rc6.txt
    results/53_E5p_result_rc6b_lean3.json
    results/53_E5p_result_rc7_lean4.json
    results/53_E5p_result_rc7_lean4.txt
    results/53_E5r_deleak_L1.json
    results/53_E5r_deleak_L1.txt
    results/53_E5r_deleak_L2.json
    results/53_E5r_deleak_L2.txt
    results/53_E5r_deleak_L3.json
    results/53_E5r_deleak_L3.txt
    results/53e2_lean3_receipt.json
    results/53e3_lean4_receipt.json
    results/53e4_lean4_receipt.json
    results/72_e9_availability.json
    results/77_tab_band.png
    results/_e5p_landing/53_E5p_leak_attrib.json
    results/_e5p_landing/53_E5p_leak_attrib.reading.md
    results/_e5p_landing/53_E5p_leak_attrib_rc8.json
    results/_e5p_landing/53_E5p_rc6b_lean.log
    results/_e5p_landing/53_E5p_rc6b_lean2.log
    results/_e5p_landing/53_E5p_rc6b_local.log
    results/_e5p_landing/53_E5p_result.077cb37906477179.json
    results/_e5p_landing/53_E5p_result.077cb37906477179.txt
    results/_e5p_landing/53_E5p_result_rc6.25b53705d7b8319f.json
    results/_e5p_landing/53_E5p_result_rc6.25b53705d7b8319f.json.PROVENANCE.md
    results/_e5p_landing/53_E5p_result_rc8_lean.json
    results/_e5p_landing/53_E5p_result_rc8_lean.txt
    results/_e5p_landing/53_E5r_equiv.json
    results/_e5p_landing/53_E5r_equiv2.json
    results/_e5p_landing/53_E5r_floor.json
    results/_e5p_landing/53_E5r_nc_band.DERIVED.txt
    results/_e5p_landing/53_E5r_nc_band.json
    results/_e5p_landing/62_E13_validity.json
    results/_e5p_landing/62_E13_validity.txt
    results/_e5p_landing/63_E14_coverage_audit.txt
    results/_e5p_landing/64_E14_changepoint.json
    results/_e5p_landing/64_E14_changepoint.txt
    results/_e5p_landing/64_E14_changepoint_rc2.json
    results/_e5p_landing/64_E14_changepoint_rc2.txt
    results/_e5p_landing/64_E14_changepoint_rc3.json
    results/_e5p_landing/64_E14_changepoint_rc3.txt
    results/_e5p_landing/64_E14_changepoint_rc4.json
    results/_e5p_landing/64_E14_changepoint_rc4.txt
    results/_e5p_landing/64_E14_changepoint_rc5.json
    results/_e5p_landing/64_E14_changepoint_rc5.txt
    results/_e5p_landing/64_E14_changepoint_rc6.json
    results/_e5p_landing/64_E14_changepoint_rc6.txt
    results/_e5p_landing/76_E5p_null_band.json
    results/_e5p_landing/76_E5p_null_band.json.README.md
    results/_e5p_landing/77_E5p_arm_table.md
    results/_e5p_landing/77_tab_band.pod.png
    results/_e5p_landing/_16_E5p_temporal_gnn.preedit_5a174960.md
    results/_e5p_landing/ellipticpp_input_manifest.sha256
    results/_e5p_landing/rc6_added_leaves.txt
    results/_e5r_landing/53_E5r_ablation.json
    results/_e5r_landing/53_E5r_ablation.txt
    results/_e5r_landing/53_E5r_ablation_mainrc.json
    results/_e5r_landing/53_E5r_ablation_mainrc.txt
    results/_e5r_landing/53_E5r_rc10_ablation.log
    results/_e8rc2_local/47b_E8_rc2.json
    results/_e8rc2_local/47b_E8_rc2.txt
    results/_e8rc2_pod/47b_E8_rc2.json
    results/_e8rc2_pod/47b_E8_rc2.txt
    results/_e8rc2_pod/47b_e8_rc2.log
    results/_op1_landing/OP1_gpu_witness.log
    results/_op1_landing/op1_gpu_witness.json
    results/_op1_landing/op1_preflight_handrun.20260924T1400Z.log
    results/_superseded_51_E9_series.json.podcopy
    results/_superseded_51_E9_series.json.podcopy.README.md
    results/elliptic_address_level.parquet
    results/ellipticpp_input_manifest.sha256
    results/figs/02_analyses_overview.md
    results/figs/02_protocol_flow.pdf
    results/figs/02_protocol_flow.png
    results/figs/06_shuffled_trajectory.pdf
    results/figs/06_shuffled_trajectory.png
    results/op1_gpu_witness.json

### 2.1 Of those, 1 whose bytes are here after all

The census records a path; a path is what is absent. For the 1 entry
below the *content* is in this repository under a different name, so
counting it as withheld would be a claim one `sha256sum` refutes. The
duplicate is listed with the file that carries it:

    results/53_E5p_result_oldwriter_55d7d8f8.json
        same bytes as  results/53_E5p_result.oldwriter_55d7d8f8.json
        same bytes as  results/_e5p_landing/53_E5p_result_oldwriter_55d7d8f8.json

## 3. Corpora

No source corpus is redistributed either. Every input is pinned by URL and
SHA-256 in [`data/README.md`](data/README.md).
