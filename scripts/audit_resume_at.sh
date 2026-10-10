#!/usr/bin/env bash
# 쿼터 리셋(01:25) 이후 검수 재개 — 01:35까지 대기 후 러너 실행.
set -u
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
target="2026-10-11 01:35:00"
while [ "$(date +%s)" -lt "$(date -d "$target" +%s)" ]; do sleep 120; done
echo "[$(date)] 쿼터 리셋 — 검수 재개"
bash "$PROJ/scripts/audit_run.sh"
