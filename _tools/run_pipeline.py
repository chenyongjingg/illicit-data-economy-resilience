#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_pipeline.py -- advance the D:\\CIS sprint as far as it can actually go.

WHAT THIS IS FOR
    One command that (1) asks the pod for a GPU verdict, (2) computes the state of
    every stage from artefacts on disk, (3) runs whatever is runnable, and
    (4) writes a state file. Run it on a schedule and the sprint advances by itself.

WHAT IT REFUSES TO DO
    It will not report a stage as complete because a report says so, because a
    ledger line claims it, or because the stage is "supposed to be" done. A stage
    is DONE only if its evidence artefact exists on disk, is non-empty, and parses.
    Everything else is PENDING, BLOCKED, or NOT_IMPLEMENTED -- three different
    words, because "blocked on the author" and "nobody has written it yet" call for
    different actions and must never be collapsed into one status.

    In particular this driver does NOT make E8 runnable: it has no training
    corpus (E3 produced no annotations) -- and that clause is the one that
    binds, so it survives the GPU's recovery. The GPU was down on 2026-09-24
    (C-27) and the scheduled-path verdict is now `COMPUTE_OK`
    (`_logs/pipeline_state.json`, 2026-09-25T18:54:12); the CLOSED
    validation arm -- renamed EV-legacy in plan v10 §六-4 -- consumes E8.
    EV-legacy is NOT E9b: E9b is the simulation-vs-observed comparison and is a
    live row in STAGES below. E10 is absent by DECISION: the author struck it
    (with E12) from the plan's skeleton and contribution list on 2026-09-25
    (ledger C-372 裁决 2), so its absence says nothing about feasibility. What
    its row used to record -- that ten reconnaissance scripts 44-62 exist and
    were never the obstacle -- is kept as a comment where the row was. A driver
    around stages that do not exist is not automation, and calling it that
    would be the false claim this project forbids.

USAGE
    python _tools/run_pipeline.py            # report state only
    python _tools/run_pipeline.py --advance  # also run stages that are READY
    python _tools/run_pipeline.py --json     # machine-readable only
"""
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "_tools"))
RESULTS = os.path.join(ROOT, "results")
LOGS = os.path.join(ROOT, "pipeline_reports")
STATE = os.path.join(ROOT, "_logs", "pipeline_state.json")

# gate ids used below
G_GPU = "C-27 (GPU unusable in-container; console restart required)"
G_C13 = "C-13 (external inputs; author decision, see report 11)"

# ---- evidence predicates, named so that an experiment-level list reads -------
# ★ 2026-09-25 (C-411 意向 / C-412 落地). `ev_require` may be a LIST parallel to
# `ev`, so each artefact is judged by the predicate that speaks ITS schema (see
# compute()). These two are named because BOTH E5r and E16 need the de-leak one,
# and neither should be judged by the ablation predicate.
ABLATION_OK = lambda d: (                                    # noqa: E731
    d.get("n_trainings", 0) >= 10
    and (d.get("F2_drop_F_pos") or {}).get("any_not_read") is False
    and isinstance((d.get("equivalence") or {}).get("abs_delta_max"),
                   (int, float)))


def DELEAK_OK(d):
    """Did this stage-3 de-leak retrain land?

    Written against the DE-LEAK schema (results/53_E5r_deleak_L*.json, produced
    by `_server/_run_53_rc9_deleak.sh` with `E5R_DELEAK=<declared set name>`),
    NOT the ablation schema. It is held to what such a file can answer: it ran
    to `status: ok`, skipped no arm, and records which feature set it applied to.
    Applying the ablation predicate here instead returns False on every field --
    which reads a landed stage as an unlanded one.
    """
    return (d.get("status") == "ok"
            and (d.get("skipped_arms") or {}).get("skipped") == []
            and bool((d.get("deleak") or {}).get("applied_to"))
            and bool((d.get("deleak") or {}).get("set_name")))

# state constants -- deliberately three, not two
DONE, READY, RUNNING, BLOCKED, NOT_IMPL, FAILED = (
    "DONE", "READY", "RUNNING", "BLOCKED", "NOT_IMPLEMENTED", "FAILED")

# Each stage: id, what it is, evidence artefact(s) that would prove it ran,
# the runner command (None => nothing to run), and its hard gate.
STAGES = [
    dict(id="E0",  title="infrastructure takedown",
         ev=["results/04_E0_infra_takedown.json"], gate=None, run=None),
    dict(id="E4",  title="social survival",
         ev=["results/10_E4_ab_survival.json"], gate=None, run=None),
    dict(id="E1",  title="social substitution",
         ev=["results/41_E1_pretrend_headline.json"], gate=None, run=None),
    dict(id="E5m", title="recurrence measurement (E5-fin)",
         ev=["results/24_E5fin_recurrence.json"], gate=None, run=None),
    # The plan's E5 is a PREDICTIVE model. The measurement above is not it, and
    # the plan's fallback is conditional on a temporal GNN that has never been
    # trained -- so the fallback is not licensed and this is a gap, not a
    # reframe. CPU-runnable (torch 2.5.1 + PyG 2.8.0 on the pod). See C-104.
    dict(id="E5p", title="temporal GNN primary arm (the plan's E5)",
         ev=["results/53_E5p_result.json"],
         # Not "the file exists". The plan's E5 IS a three-arm AUC comparison at
         # a horizon, so the predicate reads the AUCs themselves: three named
         # arms, each carrying a NUMERIC auc_test at every recorded Delta, at
         # least two Deltas (the plan does not fix Delta, so the script
         # pre-registers a set and this requires the set to be a set), a
         # non-empty test split, the two leakage checks whose failure would
         # invalidate the AUCs, and the provided-column baseline present AND
         # marked inadmissible. A run that wrote its file after one arm crashed,
         # or after a leak, must not read as DONE.
         #
         # The Deltas live at meta.deltas, NOT at the top level -- this predicate
         # was first written against a synthetic artefact built from memory and
         # read d["deltas"], which is None on the real schema, so it would have
         # returned False forever on a perfect artefact. The mutation test did
         # not catch it because the fixture was written from the same wrong
         # model as the predicate. It is now exercised against the real file.
         ev_require=lambda d: (
             isinstance((d.get("meta") or {}).get("deltas"), list)
             and len(d["meta"]["deltas"]) >= 2
             and all(
                 isinstance(
                     ((((d.get("arms") or {}).get(a) or {}).get("by_delta") or {})
                      .get(str(D), {})).get("auc_test"), (int, float))
                 for a in ("mlp_feature_only", "graphsage", "tgn")
                 for D in d["meta"]["deltas"])
             and isinstance((d.get("split") or {}).get("test"), int)
             and (d["split"]["test"] or 0) > 0
             and bool(((d.get("leakage_check") or {}).get("summary") or {})
                      .get("feature_filter_verification_exact"))
             and bool(((d.get("leakage_check") or {}).get("summary") or {})
                      .get("no_lifetime_column_in_model_matrices"))
             and ((d.get("naive_leaking_baseline") or {})
                  .get("admissible") is False)
         ),
         gate=None,
         # ★A RUNNER IS DECLARED HERE SO THAT `RUNNING` CAN BE MEASURED (2026-09-24).
         # With `run=None` this stage could not be probed for a live job: the probe
         # below only visits stages that have a `run`, so a live E5p read as
         # `NOT_IMPLEMENTED` and `RUNNING=0` -- a false status about an executing
         # job, in a file this project hands to readers.
         #
         # `manual=True` KEEPS LAUNCH AUTHORITY WHERE IT WAS. The generic launcher
         # at the bottom of this file pushes the script and runs it; it cannot
         # assert the WRITER's sha256, which `_run_53_full_rc5.sh` does before it
         # starts. A run of the wrong revision is a reading about a different
         # object, so this stage must not be auto-launched by a tool that cannot
         # check which revision it is launching.
         run=dict(script="53_E5p_temporal_gnn.py", log="logs/53_full.log",
                  manual=True,
                  manual_reason="the launcher must assert the writer's sha256 "
                                "first (_run_53_full_rc5.sh does; the generic "
                                "launcher cannot)"),
         # Status strings go stale the moment the ground moves (R26): this one
         # said "not attempted" until 53_E5p_temporal_gnn.py existed, and the
         # gate note below said "no model for E5p" until it was written. Point at
         # the artefact, not at a state.
         note="53_E5p_temporal_gnn.py + results/53_E5p_result.json; CPU-only, "
              "no GPU needed; three arms at Deltas 1/3/5 on a point-in-time "
              "footing -- 16_E5p_temporal_gnn.md §0"),
    dict(id="E6",  title="resilience (E6-fin)",
         ev=["results/26_E6fin_resilience_v2.json"], gate=None, run=None),
    dict(id="E7",  title="takedown latency (E7-inf)",
         ev=["results/34_E7inf_dark.json"], gate=None, run=None),
    dict(id="E3",  title="mechanism",
         ev=["results/39_E3_robust.json"], gate=None, run=None),
    dict(id="E2",  title="substitution event study -- REPORTED INFEASIBLE",
         ev=["results/40_E2_feasibility.json"], gate=None, run=None),
    # ★ NAMING ISOLATION (plan v10 §六-4, 2026-09-25). The closed validation arm
    # was renamed EV-legacy. E9a / E9a2 / E9a3 are a DIFFERENT family: DWC
    # monthly anchors, retained under their own names, carrying no validation
    # duty (plan: Intro-level qualitative motivation only). Any future sweep
    # that means to delete "the closed E9" must NOT touch these three rows --
    # they are the only copy of a 9-period series that cost an OCR positive
    # control to obtain. The rename is a comment plus a docstring edit rather
    # than a textual substitution for a reason no regex can see: the arm and the
    # live family share the prefix `E9`, and the family is what occurs
    # everywhere in this file.
    #   Measured on this file 2026-09-25 with the predicate STATED, because the
    #   bare counts this comment used to carry ("occurs 11x; 9 of those are this
    #   family") were withdrawn for being unstated and self-contradictory -- a
    #   count without its predicate is not a fact. Over the CODE lines only
    #   (comments excluded, so that this comment cannot count itself),
    #   `re.findall(r"E9(?![A-Za-z0-9_])", code)` matches exactly 3: the
    #   `title="E9 series ..."` of E9a2 and E9a3, and the `* E9: TWO series`
    #   print. All three are the FAMILY. No line of code names the closed arm as
    #   a bare `E9` at all -- the docstring names it EV-legacy, and the only
    #   place it appears as a bare token is prose here. That is the whole reason
    #   a substitution would be wrong, and it is checkable.
    dict(id="E9a", title="external anchor acquisition (DWC monthly series)",
         ev=["results/43_E9_anchor_fetch.json"],
         # The fetcher writes its result file even when it found nothing, so the
         # file existing is not the claim. The claim is that months were verified
         # and a series came out.
         ev_require=lambda d: d.get("n_verified", 0) >= 9,
         gate=None,
         run=dict(script="43_E9_anchor_fetch.py", args=["8"], log="logs/43_e9_fetch.log")),
    # Split out of E9a. `n_series_extracted` was a COUNT whose values were
    # persisted nowhere -- a gate reading a proxy (C-104). The fetch claim is
    # "issues verified, bytes match"; the curve is a separate deliverable and
    # must not ride on the fetch's evidence file.
    dict(id="E9a2", title="E9 series extraction (text-layer route)",
         ev=["results/51_E9_series.json"],
         # Pinned to the VALUES, not to a count of them: every entry of every
         # sub-series must be a positive int. A count can be satisfied by a
         # structure that holds nothing -- which is exactly what C-104 caught.
         ev_require=lambda d: (
             d.get("n_periods_with_values", 0) >= 3
             and all(isinstance(v, int) and v > 0
                     for s in (d.get("series") or {}).values()
                     for v in s.values())),
         gate=None, run=None,
         note="4/9 issues yielded values as text; other 5 have no text layer"),
    # The other five issues DO state the metrics -- the text layer just cannot
    # see them (the body is not text objects on those pages). Rendering p.6 and
    # reading it shows 深网和暗网有效情报 1,140,767 份 plainly. So "silent" was a
    # property of one extraction route, not of the reports. This stage is the
    # second route, and it is only allowed to count if its own positive control
    # passed: the four issues whose values are known from the text layer must be
    # reproduced by OCR first.
    dict(id="E9a3", title="E9 series via OCR (the other 5 issues)",
         ev=["results/57_E9_ocr_p6.json"],
         # Not "the file exists": not "some number came out". The control must
         # have passed (4/4 known values reproduced) AND the series must actually
         # cover more periods than the text-layer route did.
         ev_require=lambda d: (
             bool((d.get("validation") or {}).get("validated"))
             and (d.get("validation") or {}).get("n_agree") == 4
             and d.get("n_periods", 0) >= 9
             and all(isinstance(v, int) and v > 0
                     for s in (d.get("series") or {}).values()
                     for v in s.values())),
         gate=None, run=None,
         note="validated 4/4 against the text-layer values; 9 periods recovered"),
    dict(id="E8",  title="LLM-agent simulation",
         ev=["results/47b_E8_rc2.json"],
         # NOT "the file exists". rc2's own criterion for being allowed to
         # produce a number, in order: it first reproduced E3's estimator
         # exactly (|d|=0.00e+00 on all three published quantities); then theta
         # is interior (rc1's failure was a fit pinned to a grid bound); then at
         # least one scenario yielded a usable bootstrap half-life (rc1 yielded
         # none -- every half-life None, all six draws failed). So the predicate
         # is rc1's defect list inverted, and it was run on BOTH files: rc2
         # True, rc1 False. A predicate with no discriminating power would have
         # been no predicate.
         # ★ `theta_clipped` is min(theta, 1.0) -- a VALUE, not a flag (read
         # from rc2:355). The first version of this predicate tested
         # `not theta_clipped`, which is silently always False because 0.2511
         # is truthy: it would have reported a landed result as FAILED. The
         # flag is `theta_gt_1` (rc2:361). Field names are not what they look
         # like -- measured, not assumed.
         ev_require=lambda d: (
             bool((d.get("replication_gate") or {}).get("passed"))
             and 0.0 < float(((d.get("transfer_estimate") or {}).get("theta"))
                             or 0.0) < 1.0
             and not (d.get("transfer_estimate") or {}).get("theta_gt_1")
             and any((v or {}).get("halflife_boot_usable", 0) > 0
                     for k, v in ((d.get("scenarios")
                                   if isinstance(d.get("scenarios"), dict)
                                   else {})).items()
                     if k != "_rank1_counts")),
         gate=G_GPU, run=None,
         # TWO independent blockers, and the first one is upstream of the GPU:
         # (1) the plan trains QLoRA on "E3-annotated channel/post behaviour
         #     data" -- E3 ran H1/H4 only and produced DiD coefficients, not
         #     annotations; no annotation artefact exists anywhere in the tree.
         # (2) then the GPU. Reporting only (2) would tell the author to open a
         #     gate that opens onto an empty training set.
         # ★ 2026-09-24: neither blocker stopped E8. The plan's OWN risk table
         #   pre-registers the degradation path ("QLoRA 行为模型失真 -> 退化为
         #   prompt 驱动 agent"), so the CPU arm is an AUTHORISED arm, not a
         #   substitution -- 47_E8_simulation.py says exactly this in its header.
         #   rc2 has since delivered the ranking. So the GPU line above is about
         #   the QLoRA ARM ONLY, and "whether a script exists on disk" is a fact
         #   about the world that this table had wrong: two do (47_, 47b_), with
         #   nine artefacts (C-221, C-224). No runner is declared here, so this
         #   driver will not launch it.
         note="QLoRA arm unrun: no training corpus (E3 produced no annotations) "
              "AND that arm needs the GPU (C-101). The CPU arm has run and "
              "delivered the ranking (C-221/C-224); see ev for what it must "
              "satisfy."),
    dict(id="E9b", title="simulation vs observed curve",
         ev=[], gate=G_GPU, run=None,
         # NOT E9a2 alone: that route is the text layer and stops at 4 periods
         # by its own title. The complete 9-period series exists only once the
         # OCR route (E9a3) is joined to it. Written against E9a2 alone, E9b
         # would compare the simulation to 4 months and silently drop 5.
         # ★ 2026-09-24: of the three stages in this neighbourhood, E9b is the
         #   one whose "no script" is TRUE -- searched by NAME and by CONTENT
         #   ("E9b"/"E9_b") across _server/, scripts/ and _tools/, and the
         #   string occurs only in this driver and in ledger/memory writers.
         #   One of its two stated obstacles has meanwhile lifted: E8's output
         #   is now on disk (C-221), so what is missing is the comparison
         #   runner itself. Its series input is NOT asserted here -- read the
         #   E9a2/E9a3 rows above rather than inferring it from this note.
         note="no runner for the comparison itself; its inputs are E8's output "
              "(now on disk, C-221) and the full 9-period series "
              "(E9a2 text layer for 4 periods + E9a3 OCR for the other 5)"),
    # ★ E10 WAS HERE AND WAS REMOVED ON THE AUTHOR'S RULING (2026-09-25,
    # ledger C-372 裁决 2). This is a DECISION, not an infeasibility: the
    # author struck E10 (and E12) from the paper's skeleton and contribution
    # list outright, so a stage row for it would keep a dropped item alive in
    # the one table the watchdog reads. W4 no longer holds a "decision point";
    # a single lightweight re-review remains, defaulting to deleted.
    #
    # WHAT IS KEPT HERE IS THE KNOWLEDGE, NOT THE STAGE. The row's own record
    # was that "no script exists" was FALSE: TEN reconnaissance scripts
    # (44-62: ScienceDB search, endpoint discovery, three harvest routes, a
    # download probe, a corpus file census, an API-context map) exist, with
    # three probe artefacts in the frozen package. They are ALL
    # reconnaissance -- they exist BECAUSE C-108 enumerated the whole ScienceDB
    # OAI holdings (27,500 records) and found no role-annotation corpus in
    # them. There is no kappa/consistency runner, and the blocker was always
    # the missing labelled source, not the GPU and not the absence of code.
    # Anyone who wants E10 back needs that corpus first; the scripts are not
    # the obstacle.

    # ==================================================================
    # ★ PLAN v10 ADDITIONS (2026-09-25), appended as ONE BLOCK at the end.
    # Every row above is byte-identical to what it was before this change, so
    # the edit can be audited line by line (ledger C-370/C-371). v10 §三's
    # matrix and §五's three new GPU experiments name eight stages this table
    # did not carry; a table that does not carry a stage has nothing to say
    # about it -- which is the tool-side form of v10's iron law ②.
    #
    # ALL EIGHT DECLARE run=None. Nothing here can be launched by --advance,
    # which is what keeps this edit safe while 53_E5p_temporal_gnn_rc9.py is
    # in flight on the pod.
    # ==================================================================
    dict(id="E5r", title="feature-family ablation (stage-2 landed; stage-3 landed 2026-09-25)",
         ev=["results/_e5r_landing/53_E5r_ablation.json",
             "results/53_E5r_deleak_L1.json",
             "results/53_E5r_deleak_L2.json",
             "results/53_E5r_deleak_L3.json"],
         # FOUR EVIDENCE FILES: the stage-2 ablation, plus the three stage-3
         # de-leak retrains (L1/L2/L3), which landed on 2026-09-25.
         #
         # ★ CORRECTION 2026-09-25 (C-411 意向 / C-412 落地). The 2026-09-24 note
         # written here read:
         #   "compute() will read this as `FAILED: partial: ...=missing` ... and
         #    the only honest encoding of it ... it would erase the fact that the
         #    de-leaked retrain has not landed."
         # Both halves are now stale, and the second one is why the row was wrong:
         #   * the de-leak files ARE on disk and each self-reports `status: ok` on
         #     device cuda (L3: 4906.8 s, no skipped arm), so "has not landed" is
         #     false -- and a row that says so is as wrong as one that erases it;
         #   * the row never read `missing`: it read `present but did not succeed`,
         #     because ONE ablation predicate was applied to de-leak files, where
         #     all three of its keys (`n_trainings`, `F2_drop_F_pos`,
         #     `equivalence`) are absent.
         # So the FAILED was the predicate's own domain error, not a statement
         # about the experiment. Each file now carries the predicate that speaks
         # its schema, and the stage-3 fact is carried by the de-leak files' own
         # `status` field -- not by the row's colour.
         #
         # The ablation predicate asks "did the ablation read every cell", NOT
         # "did the leakage band come out usable". v10 §一-1 suspends the headline
         # leak number precisely because 53_E5r_nc_band.json self-reports
         # INSTRUMENT FAILED; a predicate requiring a usable band would read a
         # correctly self-reported instrument failure as a failed stage.
         ev_require=[ABLATION_OK] + [DELEAK_OK] * 3,
         gate=None, run=None,
         note="stage-2 ablation is the authority for family-level attribution "
              "(v10 §一-3): n_trainings 23, F2_drop_F_pos.any_not_read False. "
              "Its spec declares device cuda and equivalence.abs_delta_max "
              "0.006794 > 1e-3, so v10 §一-5 forbids pooling it with the "
              "rc6-rc9 CPU readings. Stage-3 is E16's subject and is on the pod "
              "only -- no deleak artefact exists under results/ locally."),
    dict(id="E13", title="validity benchmark for the measurement suite",
         ev=["results/_e5p_landing/62_E13_validity.json"],
         # The predicate asks whether ALL SIX indicators were evaluated, NOT
         # whether all six passed. v10 §三 reports E13 as partly passed: 4/6
         # clear the 0.8 rank-recovery bar (centrality_redistribution,
         # functional_redundancy, recovery_time, structural_entropy;
         # connectivity_resilience 0.7855192674986701 and migration_efficiency
         # 0.7792087646107846 fall short). Written as "all six pass", this
         # predicate would read a run that HONESTLY reports 4/6 as FAILED --
         # it would fail the stage for being honest. The three blocks must also
         # agree on which indicators exist: a run that evaluated six and
         # calibrated four did not finish.
         ev_require=lambda d: (
             isinstance(d.get("F1_rank_recovery"), dict)
             and len(d["F1_rank_recovery"]) == 6
             and all(isinstance(v.get("rank_recovered_0.8"), bool)
                     and isinstance(v.get("n_used"), int)
                     for v in d["F1_rank_recovery"].values())
             and set((d.get("F2_calibration") or {})) == set(d["F1_rank_recovery"])
             and set((d.get("F3_permutation_control") or {}))
             == set(d["F1_rank_recovery"])),
         gate=None, run=None,
         note="v10 §三: report as-is, no extrapolation to E1. E15 extends this "
              "with per-indicator repeats and confidence intervals, to decide "
              "whether the two short-fall indicators are marginal."),
    dict(id="E14", title="change-point detection on the anchor series",
         ev=["results/_e5p_landing/64_E14_changepoint_rc6.json"],
         # NOT "a change point was found". v10 §三 reports E14 as an all-miss
         # exploratory negative result, and the negative result IS the finding:
         # a predicate that required a detection would read a working stage as
         # a broken one. What must hold is that BOTH sources ran to the end --
         # the segment arrays exist and are non-empty, and the pre-registered
         # firing-rate criterion was evaluated (main_source only; the second
         # source is a report-only baseline and carries no such flag).
         ev_require=lambda d: (
             all(isinstance((d.get(s) or {}).get("detected_months"), list)
                 and len((d.get(s) or {}).get("distances") or []) > 0
                 for s in ("main_source", "second_source"))
             and isinstance((d.get("main_source") or {})
                            .get("firing_rate_ok_0.20"), bool)),
         gate=None, run=None,
         note="v10 §三: the pre-registered events (AlphaBay/Hansa) are outside "
              "the data range, so the run substituted Agora 2015-08 / Evolution "
              "2015-03 -- v10 requires that substitution to appear in the "
              "paper. rc6 self-reports 1069.8 s/round on cuda, which is E17's "
              "input machinery."),
    dict(id="E16", title="de-leaked retrain + clean-feature upper bound",
         ev=[], gate=G_GPU, run=None,
         note="plan v10 §五. ★ CORRECTION 2026-09-25 (C-411): this note read "
              "\"no runner: a filename search for E16 across _tools/, scripts/ "
              "and _server/ returns nothing\". That search was on FILE NAMES, and "
              "the runner is not named after the experiment -- so the zero hit "
              "was a property of the SEARCH KEY, not of the object. The runner is "
              "`_server/_run_53_rc9_deleak.sh` (sets L2_value_aggs -> L1_no_room "
              "-> L3_t0_only, pre-registered ## C-307, exec body "
              "_server/53_E5p_temporal_gnn_rc9.py), and it has landed: "
              "results/53_E5r_deleak_L{1,2,3}.json each self-report status: ok on "
              "device cuda. ★ That covers the FIRST HALF of this row's title "
              "(the de-leaked retrain). The SECOND HALF (clean-feature upper "
              "bound: F_pos-only / drop adr+deg+txm) still has NO artefact, so "
              "`ev` is deliberately left empty: filling it would make this row "
              "read DONE and erase the half that is not done -- the same error "
              "E5r's stale note made in the other direction. Splitting this row "
              "in two is an author decision. "
              "Input is "
              "stage-2's feature-family lists (F_pos-only / drop adr+deg+txm); "
              "output is a GPU reading in its OWN table, since v10 §一-5 "
              "forbids pooling with rc6-rc9. Contribution 2's narrative does "
              "not depend on this succeeding -- an AUC back at ~0.5 is itself "
              "the finding (v10 §八 risk table)."),
    dict(id="E17", title="change-point power analysis (minimum detectable effect)",
         ev=[], gate=G_GPU, run=None,
         note="plan v10 §五, no runner: filename search for E17 returns "
              "nothing. Input is E14's pipeline (cuda already verified at "
              "1069.8 s/round) plus synthetic shocks on the real graph. It "
              "answers whether E14's all-miss is a power problem or a method "
              "problem, and v10 §八 states both outcomes are writable."),
    dict(id="E15", title="validity benchmark extended (repeats + CIs)",
         ev=[], gate=G_GPU, run=None,
         note="plan v10 §五, no runner: filename search for E15 returns "
              "nothing. Extends E13 to 100 repeats per indicator with "
              "confidence intervals, to decide whether the two short-fall "
              "indicators are marginal or genuinely below the bar."),
    dict(id="E11", title="annotation sensitivity (E4 KM/Cox + E8 rc2 ranking)",
         ev=[], gate=G_GPU, run=None,
         note="plan v10 §三 schedules E11 for W5 and no runner exists. Its "
              "objects are E4's KM/Cox estimates and E8 rc2's ranking, with S3 "
              "as the primary scenario."),
    # ★ E12 was added here on 2026-09-25 for plan v10 §三 and REMOVED THE SAME
    # DAY on the author's ruling (ledger C-372 裁决 2: E10/E12 go to the delete
    # branch immediately; W4 keeps no decision point). E11 stays: it was not
    # part of that ruling and v10 §三 still schedules it for W5.

]


def pod_state():
    """(reachable, gpu_verdict, detail). Never guesses: an unreachable pod is
    reported as unreachable, not as a GPU failure."""
    try:
        import rsc
    except ImportError as exc:
        return False, "NO_RSC", str(exc)
    try:
        rc, out, _ = rsc.run("echo POD_OK; hostname", quiet=True)
    except Exception as exc:                                    # noqa: BLE001
        return False, "UNREACHABLE", "%s: %s" % (type(exc).__name__, exc)
    if "POD_OK" not in (out or ""):
        return False, "UNREACHABLE", "no POD_OK in output"

    # Push the preflight and run it; its exit code is the verdict, so we must
    # read the code, not just the text.
    local = os.path.join(ROOT, "_tools", "gpu_preflight.py")
    try:
        rsc.push(local, "/root/cis/_tools/gpu_preflight.py")
        rc, out, _ = rsc.run("/usr/local/miniconda3/envs/cis/bin/python "
                             "/root/cis/_tools/gpu_preflight.py", quiet=True)
        verdict = "UNKNOWN"
        for line in (out or "").splitlines():
            if line.startswith("GPU_PREFLIGHT:"):
                verdict = line.split(":", 1)[1].strip()
                break
        return True, verdict, "exit=%s" % rc
    except Exception as exc:                                    # noqa: BLE001
        return True, "PREFLIGHT_ERROR", "%s: %s" % (type(exc).__name__, exc)


def already_running(rsc, script_name):
    """(suppress_launch, alive, why) -- is this script alive, and what did we measure?

    Without this, "READY" (evidence absent) cannot be told apart from "already
    launched and still working", so a periodic watchdog re-launches the same job
    every tick: duplicate process, two writers on one log and one output file.
    A missing artefact means "no result yet", NOT "nothing is running".

    Three return values because the fail-safe and the finding are different
    things, and there are THREE outcomes, not two:

        alive=True    the probe ran and found the process
        alive=False   the probe ran and did NOT find it
        alive=None    the probe did not run / did not answer -- nothing measured

    A failed probe must still suppress the launch (a skipped tick is cheap, a
    duplicated long download is not) -- but it must NOT then be reported as
    "job alive on pod", which is a fact the probe did not establish. Both of
    those paths suppress; only one asserts. Collapsing None into True made a
    broken instrument's silence read as a live job.

    NOTE on the instrument itself. Two instruments have been used here and both
    read LOW, which is the dangerous direction: the caller treats `n == 0` as
    "nothing running" and therefore does NOT suppress, so an undercount starts a
    SECOND copy of a live 50-minute experiment -- two writers on one output file.

      1. `pgrep -fa <name> | grep -v pgrep | wc -l` MATCHED ITS OWN PROBE: with
         53_E5p live it returned two pids, the job and the probe's own shell,
         because that shell's command line contains the script name. It read 1
         only because the probe text happened to contain the literal "pgrep".
         Its reading depended on how the probe was phrased. And `pgrep` has
         already failed a controlled test on this pod (a known-live `sleep 120`
         printed nothing while `ps -eo pid,cmd` and a /proc scan saw it).
      2. `_tools/_probe_alive.py` -- the replacement. Reads /proc/<pid>/cmdline
         directly and requires argv[0] to be a python interpreter AND some argv
         element to contain `/cis/scripts/<name>`. The interpreter requirement
         makes self-matching structurally impossible (this probe's own argv[0] is
         an interpreter running `_probe_alive.py`, never the searched name).
         Passed a positive control (found the live 53_E5p, and did NOT count its
         own shell) and a negative control (a name that is not running -> 0).
         Its FIRST version returned 0 for the live job because it tested
         `needle in argv` -- list membership, i.e. equality -- against an element
         that merely contains the needle. The control caught it; reading the code
         back did not. That is why the control is run every time.

    So alive=False is "this probe did not see it", which is still weaker than
    "it is gone". Liveness here is a suppression hint, never evidence that a job
    finished.
    """
    try:
        rc, out, _ = rsc.run(
            "python3 /root/cis/_tools/_probe_alive.py %s" % script_name,
            quiet=True)
        tail = (out or "").strip().splitlines()
        if not tail or "PROBE_ERROR" in (out or ""):
            # The probe ran and could not look. Suppress, and do NOT assert
            # liveness: "my instrument failed" must not share a value with
            # "the object is absent".
            return True, None, ("probe could not look; launch suppressed, "
                                "liveness UNVERIFIED")
        n = int(tail[-1])
        if n < 0:
            return True, None, ("probe returned the error sentinel; launch "
                                "suppressed, liveness UNVERIFIED")
        return (n > 0), (n > 0), ("job alive on pod (%d proc)" % n if n
                                  else "no process found")
    except Exception as exc:                                    # noqa: BLE001
        return True, None, ("probe FAILED (%s); launch suppressed, liveness "
                            "UNVERIFIED" % type(exc).__name__)


def evidence_ok(rel, require=None):
    """A stage is done only if its artefact is present, non-empty, parses, AND
    satisfies the stage's own success predicate.

    Existence alone is not success. A run that found nothing still writes its
    result file -- so "the file is there" would report a failed acquisition as a
    completed one. That is the same error this project keeps meeting in other
    clothing: reading a proxy (a file exists) as the thing itself (it worked).
    """
    p = os.path.join(ROOT, rel.replace("/", os.sep))
    if not os.path.isfile(p):
        return False, "missing"
    if os.path.getsize(p) == 0:
        return False, "empty"
    if p.lower().endswith(".json"):
        try:
            with open(p, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:                                # noqa: BLE001
            return False, "unparseable: %s" % type(exc).__name__
        if require is not None:
            try:
                if not require(data):
                    return False, "present but did not succeed"
            except Exception as exc:                            # noqa: BLE001
                return False, "success check raised: %s" % type(exc).__name__
    return True, "ok"


def compute(stages, gpu_ok):
    """Two INDEPENDENT facts per stage, never merged into one word:
         build  -- has anyone written it?  DONE / READY / FAILED / NOT_IMPLEMENTED
         gate   -- may it run today?        open / CLOSED (by whom)
    E8 is both NOT_IMPLEMENTED and gated on the GPU. Reporting only "BLOCKED"
    would tell the author to open a gate that would still open onto nothing, and
    would hide that somebody has to write the experiment.
    """
    out = []
    for st in stages:
        if st["ev"]:
            req = st.get("ev_require")
            # ★ 2026-09-25 (C-411 意向 / C-412 落地) -- THE EXPERIMENT-LEVEL RULE.
            # `ev_require` may be a LIST parallel to `ev`: each artefact is then
            # judged by the predicate that speaks ITS schema. A single callable
            # keeps the old meaning (one predicate, applied to every file).
            #
            # Why: E5r's `ev` holds the stage-2 ablation AND the stage-3 de-leak
            # retrain, whose schemas are different objects. One predicate written
            # for the ablation was applied to the de-leak file, where all three of
            # its keys are absent -- so the row read `FAILED: partial` while the
            # de-leak artefacts were on disk and self-reporting `status: ok`.
            # A predicate and its domain must speak the same language; when they
            # do not, the failure is the predicate's, not the artefact's.
            if isinstance(req, (list, tuple)):
                oks = [evidence_ok(e, req[i] if i < len(req) else None)
                       for i, e in enumerate(st["ev"])]
            else:
                oks = [evidence_ok(e, req) for e in st["ev"]]
            if all(o[0] for o in oks):
                build, why = DONE, "evidence present"
            elif any(o[0] for o in oks):
                build, why = FAILED, "partial: %s" % ", ".join(
                    "%s=%s" % (e, o[1]) for e, o in zip(st["ev"], oks))
            elif any(o[1] != "missing" for o in oks):
                # A file IS there and did not support the claim: "empty",
                # "unparseable", or "present but did not succeed". That is
                # FAILED -- work was written and did not come out right.
                #
                # This branch was missing, and a single-artefact stage fell
                # through to NOT_IMPLEMENTED: evidence_ok drew the distinction
                # and compute threw it away. Measured on E5p, whose artefact ran
                # to completion and failed two of its own leakage checks:
                # evidence_ok said "present but did not succeed" and the report
                # read "nobody has written it yet". Those call for opposite
                # actions. NOT_IMPLEMENTED now means exactly one thing -- there
                # is nothing on disk at all.
                build, why = FAILED, "artefact present but did not succeed: %s" % (
                    ", ".join("%s=%s" % (e, o[1]) for e, o in zip(st["ev"], oks)))
            elif st["run"]:
                build, why = READY, "no evidence yet; runner available"
                if st["run"].get("manual"):
                    build, why = READY, ("no evidence yet; runner exists but is "
                                         "MANUAL -- see run.manual_reason")
            else:
                # ★THIS LABEL IS ABOUT THE TABLE, NOT ABOUT THE WORLD (2026-09-24).
                # It used to say "no runnable script exists", which is a claim
                # about the filesystem made by a tool that did not look at the
                # filesystem. E5p is the measured case: it sat at
                # NOT_IMPLEMENTED with RUNNING=0 counting 0 while its writer ran
                # on the pod, because its stage dict declared `run=None` -- the
                # script existed, was on disk, and was executing.
                # The same conflation is what the standing rule forbids in prose
                # ("never call E8/E10 blocked alone -- also state that no script
                # exists"); here it was happening in the status string.
                build, why = NOT_IMPL, ("no runner declared in this table for this "
                                        "stage; whether a script exists on disk is "
                                        "a separate question -- " +
                                        st.get("note", ""))
        else:
            build, why = NOT_IMPL, ("no runner declared in this table for this "
                                    "stage; whether a script exists on disk is a "
                                    "separate question -- " + st.get("note", ""))

        if st["gate"] is None:
            gate = "open"
        elif st["gate"].startswith("C-27") and gpu_ok:
            gate = "open (GPU now passes)"
        else:
            gate = "CLOSED: %s" % st["gate"].split(" (")[0]
        out.append(dict(st, build=build, gate=gate, why=why))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--advance", action="store_true",
                    help="run stages that are READY (default: report only)")
    ap.add_argument("--json", action="store_true", help="print state JSON only")
    args = ap.parse_args()

    t0 = time.time()
    reachable, verdict, detail = pod_state()
    gpu_ok = (verdict == "COMPUTE_OK")
    states = compute(STAGES, gpu_ok)

    ran = []
    held_tick = set()   # launches suppressed by THIS tick's probe (see below)
    # Ask the pod about RUNNING regardless of --advance. A stage whose job is
    # in flight must never be reported READY: READY means "nothing is happening
    # and it could be started", which is the opposite of the truth. Only checking
    # this while launching made the plain report lie.
    rsc = None
    if reachable:
        try:
            rsc = __import__("rsc")
        except ImportError:
            rsc = None
    if rsc is not None:
        for st in states:
            # ★THE LABEL MUST NOT GATE THE MEASUREMENT (2026-09-24). This read
            # `st["build"] == READY`, so a stage labelled NOT_IMPLEMENTED was
            # never probed -- and E5p sat at NOT_IMPLEMENTED with RUNNING=0 while
            # its job ran, because the label said there was nothing to look for.
            # A status inferred from a label is not a probe. Every stage that is
            # not DONE and declares a runner is now asked.
            if st["build"] != DONE and st["run"]:
                suppress, alive, why = already_running(rsc, st["run"]["script"])
                if not suppress:
                    continue
                held_tick.add(st["id"])
                if alive:
                    st["build"] = RUNNING
                # else: the probe measured nothing (alive is None) or the job is
                # genuinely gone. Either way `build` must stay READY -- READY is
                # the only state we can assert without having measured. Asserting
                # RUNNING here is what let a failed probe read as a live job.
                st["why"] = why

    if args.advance and rsc is not None:
        for st in states:
            if st["build"] != READY or not st["run"]:
                continue
            if st["id"] in held_tick:
                # Suppression is the same suppression as before; only the state
                # label changed. A probe that did not answer still holds the
                # launch for this tick (a skipped tick is cheap, a duplicate long
                # download is not) -- but it no longer claims RUNNING while doing
                # it. Held is reported, not silent.
                ran.append((st["id"], "HELD: %s" % st["why"]))
                continue
            r = st["run"]
            # ★MANUAL RUNNERS ARE NOT AUTO-LAUNCHED (2026-09-24). Declaring a
            # runner so that `RUNNING` can be MEASURED must not also hand this
            # tool launch authority it cannot exercise safely: the generic path
            # below pushes and runs the script without asserting which WRITER
            # revision it is, and E5p's launcher does assert that. Splitting the
            # two: declaring a runner grants observability, not consent.
            if r.get("manual"):
                ran.append((st["id"], "MANUAL: declared for detection only -- %s"
                            % r.get("manual_reason", "not auto-launched")))
                continue
            script = os.path.join(ROOT, "_server", r["script"])
            if not os.path.isfile(script):
                ran.append((st["id"], "SKIPPED: %s not found" % r["script"]))
                continue
            rsc.push(script, "/root/cis/scripts/%s" % r["script"])
            logp = "/root/cis/%s" % r["log"]
            # Rotate the previous log BEFORE launching. The log of a CRASHED run
            # is the evidence of why it crashed -- the 2026-09-24 E5p failure was
            # diagnosed entirely from one. Without this, every relaunch truncates
            # (`>` below) and a crash loop leaves only its last attempt behind.
            # `.prev` matches the convention already used for results
            # (63_E9_query_labels.prev.json).
            #
            # This must be a SEPARATE call, not part of the launched command:
            # rsc.bg() truncates its log synchronously before the job starts, so
            # a rotation inside the command would faithfully copy an empty file.
            try:
                rsc.run("[ -f %s ] && cp -p %s %s.prev || true"
                        % (logp, logp, logp), quiet=True)
            except Exception:                                   # noqa: BLE001
                # A failed rotation must not abort a launch; it is a
                # bookkeeping step, and the log is still written either way.
                pass
            cmd = ("/usr/local/miniconda3/envs/cis/bin/python -u /root/cis/scripts/%s %s"
                   % (r["script"], " ".join(r.get("args", []))))
            rsc.bg(cmd + " > /root/cis/%s 2>&1" % logp, logp)
            ran.append((st["id"], "LAUNCHED %s -> %s" % (r["script"], r["log"])))
    elif args.advance:
        ran.append(("-", "pod unreachable; nothing launched"))

    payload = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pod_reachable": reachable,
        "gpu_verdict": verdict,
        "gpu_detail": detail,
        "gpu_ok": gpu_ok,
        "counts": {s: sum(1 for x in states if x["build"] == s)
                   for s in (DONE, RUNNING, READY, FAILED, NOT_IMPL)},
        "gates_closed": sum(1 for x in states if x["gate"].startswith("CLOSED")),
        "stages": [dict(id=x["id"], title=x["title"], build=x["build"],
                        gate=x["gate"], why=x["why"]) for x in states],
        "advance_actions": ran,
    }
    # ★ 2026-09-25 (C-411 意向 / C-412 落地) -- THE EXPERIMENT-LEVEL RULE, IN THE
    # ARTEFACT. A reader of this JSON never sees the comments above the stage
    # list, so the rule that decided every `build` value is stated here as well.
    payload["ev_require_rule"] = (
        "build=DONE requires the stage's artefacts to be present, non-empty, "
        "parse, AND satisfy ev_require. ev_require may be a single predicate "
        "(applied to every artefact of the stage) or a LIST parallel to `ev`, in "
        "which case each artefact is judged ONLY by the predicate that speaks its "
        "own schema. A stage must not read FAILED because a predicate written for "
        "one schema was applied to a file of another: on 2026-09-25 that made E5r "
        "read `FAILED: partial` while its three stage-3 de-leak artefacts were on "
        "disk and each self-reported status: ok.")
    # Completion is asserted by the process that had to survive to write it.
    # The watchdog wrapper's trailing `exit=` line is lost exactly on the runs
    # that abort, so the machine-readable verdict must not depend on cmd.exe
    # reaching its last line. Written last, so a crash mid-run leaves no
    # report_completed=True behind.
    #
    # The field was called plain `completed` and a reader took it to mean "the
    # experiments completed" -- it says nothing of the kind. This whole file is
    # a snapshot of the gate taken by a reporter, and nothing in it completes
    # anything: the stages above may be RUNNING while this says True, which is
    # exactly what happened at 10:46 on 2026-09-24 with E5p live on the pod.
    # Renamed, and the meaning is now carried by the artefact itself rather than
    # only by this comment (a reader of the JSON never sees the comment).
    # No consumer read the old key, so the rename breaks nothing.
    payload["report_completed"] = True
    payload["report_completed_means"] = (
        "this gate REPORT reached its last line; it does NOT mean any experiment "
        "finished, and stages may be RUNNING while this is true")
    # `generated` can legitimately be NEWER than the last _logs/watchdog.log
    # entry: the watchdog is only one of the callers. A human running this file
    # to look at the gate rewrites the state file and appends nothing to the
    # watchdog log, so a state file newer than any logged run is expected, not
    # evidence of a rogue writer. Record the caller so that is checkable instead
    # of inferable.
    payload["invoked_via"] = "watchdog(--advance)" if args.advance else "manual(report-only)"
    payload["pid"] = os.getpid()
    payload["pid_means"] = (
        "PID of this gate-report process on the machine that ran it (often the "
        "local machine), NOT of any experiment; pod pids are unrelated")
    payload["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("CIS pipeline state -- %s" % payload["generated"])
    print("pod: %s   gpu: %s (%s)"
          % ("reachable" if reachable else "UNREACHABLE", verdict, detail))
    print()
    print("%-5s %-42s %-16s %s" % ("id", "stage", "build", "gate"))
    for x in states:
        print("%-5s %-42s %-16s %s"
              % (x["id"], x["title"][:42], x["build"], x["gate"][:34]))
    print()
    c = payload["counts"]
    print("build: DONE=%d RUNNING=%d READY=%d FAILED=%d NOT_IMPLEMENTED=%d "
          "| gates closed=%d"
          % (c[DONE], c[RUNNING], c[READY], c[FAILED], c[NOT_IMPL],
             payload["gates_closed"]))
    for sid, msg in ran:
        print("  advance: %s %s" % (sid, msg))
    if c[NOT_IMPL]:
        print()
        print("NOT_IMPLEMENTED is not a gate an author can open. Seeing it is the")
        print("per-stage reason above -- opening a gate onto an experiment that is")
        print("not runnable changes nothing.")
    if not gpu_ok:
        print()
        print("GPU gate closed (%s). The GPU is necessary but not sufficient:" % verdict)
        print("every stage behind it is ALSO missing something else (no training")
        print("corpus for E8), so a console restart today buys nothing, and that")
        print("is now measured rather than assumed. E5p is NOT behind this gate:")
        print("it is CPU-only, so no restart is needed for it. Whether its run has")
        print("LANDED is a separate question, and this line deliberately does not")
        print("answer it -- read its artefact row above (R26: a status string goes")
        print("stale the moment the ground moves; point at the artefact). What")
        print("remains is:")
        print("  * E10: the plan's corpus EXISTS and is open access (C-103), but it")
        print("    is a case corpus, and the full OAI enumeration of the holdings")
        print("    (27,500 records) found NO telecom-fraud role-annotation corpus")
        print("    (C-108). The archive's existence is settled; its SUITABILITY is")
        print("    not. E10 still has no ground truth.")
        print("  * E9: TWO series, not one (C-107/C-111). Each report prints both,")
        print("    and the distinction decides whether E9b is writable:")
        print("      - 高价值买卖情报: 9 periods, stable to 1.7x (3,999-6,889).")
        print("        Usable as the comparison series.")
        print("      - 深网和暗网有效情报: 9 periods, unstable across 16.6x")
        print("        (68,904-1,140,767), with a value repeated in consecutive")
        print("        months and a 16x collapse that partially reverses.")
        print("        UNATTRIBUTED -- report it as its own descriptive series.")
        print("    An unattributed change in what was counted would otherwise enter")
        print("    the paper looking like a collapse in illicit activity.")
    print("\nwrote %s (%.1fs)" % (STATE, time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
