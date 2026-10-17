#!/usr/bin/env bash
# lfs_start.sh -- ensure exactly one resumable Elliptic++ fetcher is running.
#
# This exists because a multi-line `rsc.py exec` command arrived at the pod with
# its newlines flattened to spaces, which turned `echo "pid $!"; sleep 5; ...`
# into a single echo whose arguments were the rest of the script. The visible
# symptom was empty output; the real damage was that each retry started another
# fetcher, and three of them were appending to the same cache files.
#
# Hence: orchestration lives in a file that is pushed and run. Patterns are
# bracketed ("fetch_data[.]py") so pkill cannot match the shell that is running
# the pkill -- the C-24 failure.
set -u
cd /root/cis

before=$(pgrep -cf 'fetch_elliptic_resume[.]py' || true)
pkill -f 'fetch_data[.]py' 2>/dev/null || true
pkill -f 'fetch_elliptic_resume[.]py' 2>/dev/null || true
sleep 2
killed=$before

setsid nohup python3 _server/fetch_elliptic_resume.py > logs/lfs_resume.log 2>&1 < /dev/null &
sleep 10

echo "killed_before=$killed  running_now=$(pgrep -cf 'fetch_elliptic_resume[.]py')"
echo "--- lfs_resume.log ---"
tail -12 logs/lfs_resume.log
