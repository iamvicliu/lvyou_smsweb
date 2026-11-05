#!/usr/bin/env bash
# 从 Mac 一条命令跑全套自检：优先局域网直连 n1，连不上再走 n1-frp。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ -n "${SELFCHECK_HOST:-}" ]]; then
  HOST="$SELFCHECK_HOST"
elif ssh -o ConnectTimeout=3 -o BatchMode=yes n1 true >/dev/null 2>&1; then
  HOST=n1
else
  HOST=n1-frp
fi

scp -q "$ROOT/scripts/selfcheck.py" "$HOST:/tmp/selfcheck.py"
ssh "$HOST" 'docker cp /tmp/selfcheck.py lvyou-smsweb:/tmp/selfcheck.py >/dev/null
rc=0
docker exec lvyou-smsweb python /tmp/selfcheck.py || rc=$?
docker exec lvyou-smsweb sh -c "rm -f /tmp/selfcheck.py" || true
rm -f /tmp/selfcheck.py
exit $rc'
