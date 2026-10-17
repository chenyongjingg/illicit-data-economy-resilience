#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_lifelines.py -- why did KaplanMeierFitter raise TypeError?

`03_iden_infra.py` reported
        lifelines unavailable (TypeError); manual product-limit:
and fell back to a hand-rolled estimator. A fallback that runs silently is
indistinguishable from a package that is simply absent, so the failure is worth
pinning down before E0 depends on it: if the cause is a numpy/pandas API removal
it will hit *every* lifelines call (Cox, log-rank, PH test), not just this one,
and E0 would be quietly built on the substitute.

This runs the identical call on synthetic data so a data-shape problem and a
library problem are separated: if the synthetic fit also fails, the fault is in
the library stack, not in the cohort frame.
"""
from __future__ import annotations

import traceback

import numpy as np
import pandas as pd

print("numpy   %s" % np.__version__)
print("pandas  %s" % pd.__version__)
try:
    import lifelines
    print("lifelines %s" % lifelines.__version__)
except Exception:
    traceback.print_exc()
    raise SystemExit(1)

rng = np.random.default_rng(0)
dur = pd.Series(rng.exponential(5.0, 2000))
ev = pd.Series(rng.random(2000) < 0.8)

print("\n--- 1. KaplanMeierFitter on synthetic float64/bool ---")
from lifelines import KaplanMeierFitter

kmf = KaplanMeierFitter()
try:
    kmf.fit(dur, event_observed=ev)
    print("  fit   OK   n=%d" % len(kmf.durations))
    print("  predict(2.0) = %.4f" % kmf.predict(2.0))
    print("  median_survival_time_ = %s" % kmf.median_survival_time_)
except Exception:
    traceback.print_exc()

print("\n--- 2. duration as a *numpy array* (what np.where produces) ---")
kmf2 = KaplanMeierFitter()
try:
    kmf2.fit(np.asarray(dur, dtype=float), event_observed=np.asarray(ev, dtype=bool))
    print("  fit   OK")
except Exception:
    traceback.print_exc()

print("\n--- 3. duration with ints, event as a pandas nullable bool ---")
kmf3 = KaplanMeierFitter()
try:
    kmf3.fit(pd.Series(rng.integers(0, 20, 2000)),
             event_observed=pd.Series(rng.random(2000) < 0.8, dtype="boolean"))
    print("  fit   OK")
except Exception:
    traceback.print_exc()

print("\n--- 4. the exact call shape from 03_iden_infra.py ---")
n = 5000
added = pd.Series(pd.to_datetime("2026-06-25") +
                  pd.to_timedelta(rng.integers(0, 60, n), unit="D"))
lo = added + pd.to_timedelta(rng.exponential(3.0, n).round(3), unit="D")
online = rng.random(n) < 0.055
T_END = pd.Timestamp("2026-09-23")
t_event = (lo - added).dt.total_seconds() / 86400.0
t_cens = (T_END - added).dt.total_seconds() / 86400.0
duration = np.where(online, t_cens, t_event)
frame = pd.DataFrame({"duration": duration, "event": ~online})
print("  duration dtype=%s  event dtype=%s"
      % (frame["duration"].dtype, frame["event"].dtype))
kmf4 = KaplanMeierFitter()
try:
    kmf4.fit(frame["duration"], event_observed=frame["event"])
    print("  fit   OK   median=%s" % kmf4.median_survival_time_)
except Exception:
    traceback.print_exc()

print("\n--- 5. the downstream calls E0 needs ---")
try:
    from lifelines import CoxPHFitter
    from lifelines.statistics import logrank_test, proportional_hazard_test

    grp = rng.random(n) < 0.5
    lr = logrank_test(dur, dur, event_observed_A=ev, event_observed_B=ev[grp])
    print("  logrank_test      OK   p=%.4f" % lr.p_value)

    cf = frame.copy()
    cf["x"] = rng.normal(size=n)
    cph = CoxPHFitter()
    cph.fit(cf, duration_col="duration", event_col="event")
    print("  CoxPHFitter.fit   OK   coef=%.4f" % cph.params_["x"])
    ph = proportional_hazard_test(cph, cf, time_transform="rank")
    print("  proportional_hazard_test OK")
    print(ph.summary.to_string())
except Exception:
    traceback.print_exc()

print("\nPROBE_LIFELINES_DONE")
