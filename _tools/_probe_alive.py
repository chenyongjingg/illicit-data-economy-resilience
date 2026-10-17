#!/usr/bin/env python3
"""Count live jobs running a named pipeline script -- without pgrep.

Why this exists
---------------
`run_pipeline.already_running()` used `pgrep -fa <name> | grep -v pgrep | wc -l`.
Two defects, both observed on this pod:

1. **It matches its own probe.** `pgrep -fa 53_E5p_temporal_gnn.py` returned TWO
   pids: the real job (33171) and the shell that was running the probe, because
   that shell's own command line contains the script name. It happened to be
   filtered here only because the probe text contained the literal string
   "pgrep". Change the probe's wording and the count changes -- an instrument
   whose reading depends on how it is phrased.

2. **`pgrep` itself has already failed a controlled test on this pod**: with a
   known-live `sleep 120` it printed nothing while `ps -eo pid,cmd` and a /proc
   scan both saw the pid. An undercount here is not harmless: the caller treats
   `n == 0` as "nothing running" and therefore does NOT suppress the launch, so
   a blind pgrep makes the watchdog start a SECOND copy of a live 50-minute
   experiment -- two writers on one output file.

How this one is different
-------------------------
It reads `/proc/<pid>/cmdline` directly and requires the command to BE a python
process executing `/cis/scripts/<name>`:

    * argv[0] must name a python interpreter  -> excludes every shell, including
      the probe's own, since the probe's argv[0] is `bash`
    * argv must contain `/cis/scripts/<name>` -> excludes other python jobs

So it cannot match its own invocation: this script's own argv contains
`_probe_alive.py`, never the name being searched for... unless the name is
passed as an argument, which is why the search term is matched against the
*interpreter plus script path* and not against the whole command line.

Usage:  _probe_alive.py <script-name> [--verbose]
Prints a single integer (the count) on the last line. Exit 0 either way --
"counted zero" and "could not look" must not share a return value.
"""
import os
import sys


def scan(name):
    """Return (pids, unreadable) for python processes running /cis/scripts/<name>."""
    needle = "/cis/scripts/" + name
    pids, unreadable = [], 0
    me = os.getpid()
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid == me:
            continue
        try:
            with open("/proc/%d/cmdline" % pid, "rb") as fh:
                raw = fh.read()
        except (IOError, OSError):
            unreadable += 1
            continue
        if not raw:
            continue
        argv = [a.decode("utf-8", "replace") for a in raw.split(b"\0") if a]
        if not argv:
            continue
        # argv[0] must be a python interpreter (excludes bash/sh/probe shells)
        if "python" not in os.path.basename(argv[0]):
            continue
        # SUBSTRING over the argv elements, not list membership. `needle in argv`
        # is equality against each element, and the real job's element is
        # `/root/cis/scripts/<name>` -- it CONTAINS the needle but does not equal
        # it, so the first version returned 0 for a process that was running.
        # Caught by the positive control, not by reading it back: an instrument
        # that reads low is exactly the defect this file exists to remove.
        if any(needle in a for a in argv):
            pids.append(pid)
    return pids, unreadable


def main():
    if len(sys.argv) < 2:
        sys.stderr.write(__doc__)
        return 2
    name = sys.argv[1]
    verbose = "--verbose" in sys.argv[2:]
    try:
        pids, unreadable = scan(name)
    except Exception as exc:                                    # noqa: BLE001
        # Distinguishable from a real zero: say so loudly, and use a sentinel
        # the caller can refuse to read as a count.
        sys.stdout.write("PROBE_ERROR %s\n-1\n" % type(exc).__name__)
        return 0
    if verbose:
        sys.stdout.write("name=%s  pids=%s  unreadable_proc_entries=%d\n"
                         % (name, pids, unreadable))
    sys.stdout.write("%d\n" % len(pids))
    return 0


if __name__ == "__main__":
    sys.exit(main())
