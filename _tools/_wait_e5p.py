# -*- coding: utf-8 -*-
"""Poll the pod until E5p reports its terminal marker, then stop.

Monitoring only -- it makes no claims and archives nothing. The landing itself is
80_e5p_landing.py, which gates on the marker AND on the writer's own end-of-run
line before it will archive anything.

THREE STATES, NOT TWO (the peer's point, adopted)
-------------------------------------------------
The first version tested `any(line.isdigit() and int(line) > 0)` over the
combined output of a three-command probe. Signal and transport shared ONE text
channel, so an unreachable pod produced no digit line -- indistinguishable from
"the marker is not there yet" -- and it would report "still running" for the
full 29 minutes with the same final line it prints when the run genuinely is
still running. "I could not ask" and "I asked and the answer is no" must never
share a return value.

The pod prints its own UTC date, so that line is the heartbeat: if it is absent
the answer is not about the run. Three consecutive failures end the watch with
its own exit code rather than a status claim.

CALIBRATED SILENCE
------------------
Silence is not evidence of a stall by itself. The rc=1 reference run went
`ARM tgn done` -> 392 s of nothing -> `arms assembled`, because assembling the
arms is long, silent and CPU-bound. So this prints the log's age in seconds
every tick: a gap whose SIZE is visible can be compared against a known gap; a
gap that is only visible as "unchanged since last tick" cannot.
"""
import os
import re
import subprocess
import sys
import time

# The reference run took 2,667 s; 90 ticks covers 30 min and would end the watch
# before the marker on a run of that length. Overridable so the budget is a
# parameter rather than something edited mid-flight.
MAX_TICKS = int(os.environ.get("WAIT_MAX_TICKS", "90"))
SLEEP = int(os.environ.get("WAIT_SLEEP", "20"))
BLANK_LIMIT = 3
LOG = "/root/cis/logs/53_full.log"

# From the rc=1 reference run: the silence between "ARM <last> done" and
# "arms assembled". Exceeding this is worth saying out loud; being inside it
# is not an anomaly.
REFERENCE_ASSEMBLY_GAP_S = 392

HERE = os.path.dirname(os.path.abspath(__file__))
RSC = os.path.join(HERE, "rsc.py")

blank = 0
for i in range(1, MAX_TICKS + 1):
    probe = ('date -u +%%H:%%M:%%S; grep -c "RSC_EXIT=" %s; '
             'tail -n 2 %s; stat -c %%Y %s' % (LOG, LOG, LOG))
    pr = subprocess.run([sys.executable, RSC, "exec", probe],
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", cwd=HERE)
    if pr.returncode != 0:
        blank += 1
        print("[%3d] PROBE FAILED (rsc rc=%d) -- says NOTHING about the run"
              " (x%d)" % (i, pr.returncode, blank), flush=True)
        if blank >= BLANK_LIMIT:
            print("TRANSPORT LOST after %d consecutive failures. The run's"
                  " state is UNKNOWN, not 'still running'." % blank, flush=True)
            sys.exit(7)
        time.sleep(SLEEP)
        continue

    raw = (pr.stdout or "") + (pr.stderr or "")
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    clock = [l for l in lines if re.match(r"^\d{2}:\d{2}:\d{2}$", l)]
    # TWO all-digit lines now share this channel: the marker COUNT (small) and
    # the mtime EPOCH (10 digits). `l.isdigit()` alone matches both, so the
    # epoch would be read as a nonzero count and fire a FALSE terminal marker.
    # Length is what separates them; anything that counts a pure-digit line has
    # to say which digit line it means.
    counts = [l for l in lines if l.isdigit() and len(l) < 9]
    epochs = [l for l in lines if l.isdigit() and len(l) >= 9]
    tails = [l for l in lines if l.startswith("[53 ")]

    if not clock:
        blank += 1
        print("[%3d] PROBE ANSWERED WITHOUT POD CLOCK -- cannot tell a missing"
              " marker from an unanswered question (x%d)" % (i, blank),
              flush=True)
        if blank >= BLANK_LIMIT:
            print("TRANSPORT UNRELIABLE after %d ticks. State UNKNOWN."
                  % blank, flush=True)
            sys.exit(7)
        time.sleep(SLEEP)
        continue
    blank = 0

    age = "?"
    if epochs:
        try:
            age = "%ds" % (time.time() - float(epochs[-1]))
        except ValueError:
            pass

    # The label used to read "RSC_EXIT=%s" while %s was the OCCURRENCE COUNT.
    # It rendered as "RSC_EXIT=0", which reads as "the run exited with rc=0" and
    # sent me looking for a premature exit three minutes into a live run. A
    # count and a return code are different quantities; the label has to say
    # which one it is printing.
    print("[%3d] %s | RSC_EXIT occurrences=%s | log age %s | %s"
          % (i, clock[0], counts[0] if counts else "?", age,
             tails[-1][:110] if tails else "?"), flush=True)

    if counts and int(counts[0]) > 0:
        print("TERMINAL MARKER PRESENT -- the run has ended.", flush=True)
        subprocess.run([sys.executable, RSC, "exec",
                        'grep "RSC_EXIT=" %s; tail -n 6 %s; '
                        'ls -l /root/cis/results/53_E5p_result.json'
                        % (LOG, LOG)], cwd=HERE)
        sys.exit(0)

    if age != "?" and int(age.rstrip("s")) > REFERENCE_ASSEMBLY_GAP_S * 2:
        print("NOTE: log silent for %s, over 2x the %ds assembly gap seen in"
              " the reference run -- check CPU, do not assume a stall."
              % (age, REFERENCE_ASSEMBLY_GAP_S), flush=True)

    if i < MAX_TICKS:
        time.sleep(SLEEP)

print("still running after %d ticks (~%d min); no terminal marker. This is a"
      " statement about the MARKER, not about progress."
      % (MAX_TICKS, MAX_TICKS * SLEEP // 60))
sys.exit(1)
