#!/usr/bin/env bash
# probe_speed2.sh -- measure the *real* pip download path (not curl on an error
# page). The first probe returned a 404 body, so its "speed" was latency on a
# 2 KB error page and proves nothing about throughput.
#
# This one downloads an actual ~45 MB wheel from mirrors.aliyun.com twice: once
# with the pod's global proxy in the environment, once with aliyun excluded via
# no_proxy. It also confirms GitHub still works with that no_proxy in place, so
# the fix cannot silently break the LFS / tarball fetches.
set -u
PROXY="http://mihomo.kube-system.svc.cluster.local:7890"
MIRROR="https://mirrors.aliyun.com/pypi/simple/"
PKG="scipy"
PIP=/usr/local/miniconda3/envs/cis/bin/pip

run_case () {
  local label="$1"; shift
  rm -rf /tmp/spd_dl; mkdir -p /tmp/spd_dl
  local t0 t1 sz
  t0=$(date +%s.%N)
  "$@" >/tmp/spd_pip.log 2>&1
  local rc=$?
  t1=$(date +%s.%N)
  sz=$(du -sb /tmp/spd_dl 2>/dev/null | cut -f1)
  awk -v l="$label" -v a="$t0" -v b="$t1" -v s="${sz:-0}" -v r="$rc" \
    'BEGIN{d=b-a; printf "%-28s rc=%d bytes=%d time=%.1fs rate=%.2f MB/s\n", l, r, s, d, (d>0? s/d/1048576 : 0)}'
  grep -iE "downloading|saved|error|warning" /tmp/spd_pip.log | head -3
}

echo "=== A: proxy in env (what the pod does by default) ==="
export http_proxy="$PROXY" https_proxy="$PROXY"
unset no_proxy NO_PROXY
run_case "aliyun via proxy" $PIP download --no-deps -q -d /tmp/spd_dl \
  --index-url "$MIRROR" --trusted-host mirrors.aliyun.com "$PKG"

echo "=== B: aliyun excluded from the proxy (proposed fix) ==="
export no_proxy="mirrors.aliyun.com,localhost,127.0.0.1"
export NO_PROXY="$no_proxy"
run_case "aliyun excluded from proxy" $PIP download --no-deps -q -d /tmp/spd_dl \
  --index-url "$MIRROR" --trusted-host mirrors.aliyun.com "$PKG"

echo "=== C: with that same no_proxy, does GitHub still work? ==="
code=$(curl -s -o /dev/null -w '%{http_code}' -m 30 \
  https://codeload.github.com/git-disl/EllipticPlusPlus/tar.gz/refs/heads/main)
echo "github tarball through proxy with no_proxy set -> http=$code"

rm -rf /tmp/spd_dl /tmp/spd_pip.log /tmp/spd.bin /tmp/spd2.bin
echo "PROBE_SPEED2_DONE"
