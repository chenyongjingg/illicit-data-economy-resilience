#!/usr/bin/env bash
# probe_net.sh -- is the pod's egress genuinely ~0.5 MB/s, or is the running
# Elliptic++ LFS fetch eating a shared cap?
#
# Non-destructive: it does not stop the fetch. Instead it samples the on-disk
# growth of the LFS cache to obtain the fetch's own throughput, and simultaneously
# measures a known-good mirror download. If the two rates sum to a constant, the
# link is shared and the fix is to serialise; if the fetch alone is slow while
# the mirror is fast, the bottleneck is per-connection and the fix is parallelism.
set -u
CACHE=/root/cis/data/lfs_cache
MIRROR=https://mirrors.aliyun.com/pypi/simple/
PIP=/usr/local/miniconda3/envs/cis/bin/pip

b_now () { du -sb "$CACHE" 2>/dev/null | cut -f1; }

echo "=== LFS cache contents ==="
ls -la "$CACHE" 2>/dev/null | tail -12
echo "objects present: $(ls -1 "$CACHE" 2>/dev/null | wc -l)"

B0=$(b_now); T0=$(date +%s)

echo "=== concurrent mirror download (background) ==="
rm -rf /tmp/net_dl; mkdir -p /tmp/net_dl
( /usr/bin/time -f "%e" $PIP download --no-cache-dir --no-deps -q -d /tmp/net_dl \
    --index-url "$MIRROR" --trusted-host mirrors.aliyun.com scipy ) >/tmp/net_pip.log 2>&1 &
PIP_PID=$!

sleep 30
B1=$(b_now); T1=$(date +%s)

wait $PIP_PID 2>/dev/null
PIP_T=$(tail -1 /tmp/net_pip.log | tr -dc '0-9.')
PIP_SZ=$(du -sb /tmp/net_dl 2>/dev/null | cut -f1)

awk -v b0="$B0" -v b1="$B1" -v t0="$T0" -v t1="$T1" 'BEGIN{
  d=b1-b0; s=t1-t0;
  printf "LFS fetch growth : %d bytes in %ds = %.3f MB/s\n", d, s, (s>0? d/s/1048576 : 0)}'
awk -v s="${PIP_SZ:-0}" -v t="${PIP_T:-30}" 'BEGIN{
  printf "mirror concurrent: %d bytes in %.1fs = %.3f MB/s\n", s, t, (t>0? s/t/1048576 : 0)}'

echo "=== HuggingFace reachability (would give a faster route to Elliptic++ if mirrored) ==="
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
curl -s -o /dev/null -w "hf direct : http=%{http_code} t=%{time_total}s\n" -m 20 https://huggingface.co/api/models
export http_proxy=http://mihomo.kube-system.svc.cluster.local:7890
export https_proxy="$http_proxy"
curl -s -o /dev/null -w "hf proxy  : http=%{http_code} t=%{time_total}s\n" -m 20 https://huggingface.co/api/models

echo "=== raw LFS host (objects are served from a storage host, not github.com) ==="
curl -sI -m 20 -x "$http_proxy" https://github-cloud.s3.amazonaws.com 2>&1 | head -2

rm -rf /tmp/net_dl /tmp/net_pip.log
echo "PROBE_NET_DONE"
