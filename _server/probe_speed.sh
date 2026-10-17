#!/usr/bin/env bash
# probe_speed.sh -- is a domestic PyPI mirror faster direct or through the pod's
# global proxy?
#
# Why this exists: the pod's login shell exports
#   http_proxy=http://mihomo.kube-system.svc.cluster.local:7890
# globally, so every `pip install` against mirrors.aliyun.com was silently being
# routed through an overseas proxy. That is the actual cause of the repeated
# "WARNING: Connection interrupted while downloading" and the hang on
# nvidia_cudnn_cu12 (664.8 MB) -- not a slow mirror, and not a flaky pod disk.
# The measurement below decides the fix rather than assuming it.
set -u

URL="https://mirrors.aliyun.com/pypi/web/packages/source/n/numpy/numpy-2.1.3.tar.gz"
PROXY="http://mihomo.kube-system.svc.cluster.local:7890"

for mode in direct proxy; do
  if [ "$mode" = direct ]; then
    unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
  else
    export http_proxy="$PROXY" https_proxy="$PROXY"
  fi
  rm -f /tmp/spd.bin
  R=$(curl -s -o /tmp/spd.bin -w "%{http_code} %{size_download} %{speed_download} %{time_total}" \
        --max-time 45 "$URL" 2>&1)
  SZ=$(stat -c %s /tmp/spd.bin 2>/dev/null || echo 0)
  printf 'aliyun %-6s -> http=%s bytes=%s speed=%.0f B/s total=%ss (file=%s)\n' \
    "$mode" "$(echo "$R" | cut -d' ' -f1)" "$(echo "$R" | cut -d' ' -f2)" \
    "$(echo "$R" | cut -d' ' -f3)" "$(echo "$R" | cut -d' ' -f4)" "$SZ"
done
rm -f /tmp/spd.bin

echo "--- github: direct vs proxy (the proxy is needed for this one) ---"
GH="https://codeload.github.com/git-disl/EllipticPlusPlus/tar.gz/refs/heads/main"
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
curl -s -o /dev/null -w "github direct -> %{http_code} %{speed_download} B/s\n" --max-time 30 "$GH"
export http_proxy="$PROXY" https_proxy="$PROXY"
curl -s -o /dev/null -w "github proxy  -> %{http_code} %{speed_download} B/s\n" --max-time 30 "$GH"

echo "--- does aliyun resolve/route at all with no_proxy set? ---"
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
export no_proxy="mirrors.aliyun.com"
export http_proxy="$PROXY" https_proxy="$PROXY"
rm -f /tmp/spd2.bin
R=$(curl -s -o /tmp/spd2.bin -w "%{http_code} %{speed_download}" --max-time 45 "$URL" 2>&1)
echo "aliyun with http_proxy set + no_proxy=mirrors.aliyun.com -> $R (bytes=$(stat -c %s /tmp/spd2.bin 2>/dev/null || echo 0))"
rm -f /tmp/spd2.bin
echo "PROBE_SPEED_DONE"
