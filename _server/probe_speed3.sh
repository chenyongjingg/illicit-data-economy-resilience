#!/usr/bin/env bash
# probe_speed3.sh -- clean re-measurement.
#
# probe_speed2 was contaminated: case A populated pip's HTTP cache, so case B
# was served from disk (0.6 s for 35 MB, 52 MB/s) and measured nothing about the
# network. Both cases re-run here with --no-cache-dir, direct first so the
# ordering cannot favour the second case either.
#
# probe_speed2's GitHub check also returned 000. That is re-tested here, because
# the Elliptic++ LFS fetch is running concurrently and shares the same proxy --
# a saturated proxy and a blocked proxy look identical from a single 000.
set -u
PROXY="http://mihomo.kube-system.svc.cluster.local:7890"
MIRROR="https://mirrors.aliyun.com/pypi/simple/"
PKG="scipy"
PIP=/usr/local/miniconda3/envs/cis/bin/pip

echo "=== competing traffic on the proxy right now ==="
pgrep -af "python|curl|wget" | grep -viE "pgrep|grep|probe_speed3" | head -8
echo

run_case () {
  local label="$1"; shift
  rm -rf /tmp/spd_dl; mkdir -p /tmp/spd_dl
  local t0 t1 sz rc
  t0=$(date +%s.%N)
  "$@" >/tmp/spd_pip.log 2>&1; rc=$?
  t1=$(date +%s.%N)
  sz=$(du -sb /tmp/spd_dl 2>/dev/null | cut -f1)
  awk -v l="$label" -v a="$t0" -v b="$t1" -v s="${sz:-0}" -v r="$rc" \
    'BEGIN{d=b-a; printf "%-30s rc=%d bytes=%d time=%.1fs rate=%.2f MB/s\n", l, r, s, d, (d>0? s/d/1048576 : 0)}'
}

echo "=== B first (direct), both with --no-cache-dir ==="
export no_proxy="mirrors.aliyun.com,localhost,127.0.0.1"
export NO_PROXY="$no_proxy"
export http_proxy="$PROXY" https_proxy="$PROXY"
run_case "aliyun EXCLUDED from proxy" $PIP download --no-cache-dir --no-deps -q -d /tmp/spd_dl \
  --index-url "$MIRROR" --trusted-host mirrors.aliyun.com "$PKG"

echo "=== A (through the proxy) ==="
unset no_proxy NO_PROXY
export http_proxy="$PROXY" https_proxy="$PROXY"
run_case "aliyun VIA proxy" $PIP download --no-cache-dir --no-deps -q -d /tmp/spd_dl \
  --index-url "$MIRROR" --trusted-host mirrors.aliyun.com "$PKG"

echo "=== C: GitHub, 3 attempts, with no_proxy excluding only aliyun ==="
export no_proxy="mirrors.aliyun.com,localhost,127.0.0.1"; export NO_PROXY="$no_proxy"
export http_proxy="$PROXY" https_proxy="$PROXY"
for i in 1 2 3; do
  printf '  attempt %d: ' "$i"
  curl -s -o /dev/null -w 'http=%{http_code} %{speed_download} B/s t=%{time_total}s\n' \
    -m 40 https://codeload.github.com/git-disl/EllipticPlusPlus/tar.gz/refs/heads/main || echo "curl rc=$?"
done

rm -rf /tmp/spd_dl /tmp/spd_pip.log
echo "PROBE_SPEED3_DONE"
