#!/usr/bin/env bash
# 전체 번역 검수 러너 — queue의 배치를 Codex로 순차 판정, out/에 결과 저장.
# 중단돼도 재실행하면 완료된 배치(out에 결과 존재)는 건너뜀.
# 사용법: bash scripts/audit_run.sh [최대 배치 수]
set -u
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
QUEUE="$PROJ/translations/audit/queue"
OUT="$PROJ/translations/audit/out"
LIMIT="${1:-10000}"
mkdir -p "$OUT"
count=0
for f in $(ls "$QUEUE" | sort); do
  base="${f%.json}"
  [ -s "$OUT/$base.txt" ] && continue
  [ "$count" -ge "$LIMIT" ] && break
  count=$((count+1))
  echo "[$(date +%H:%M:%S)] ($count) $base 검수 중..."
  PROMPT="너는 한국 운전면허 학과시험의 번역 품질 감사자다. 파일 translations/audit/queue/$f 를 읽어라. 각 항목의 한국어 원문(ko_*)과 번역(tr_*)을 대조해 **학습자를 오도하는 실질 오류만** 보고하라: 의미 반전·방향(좌/우) 오류·숫자/단위 오류·부정어 소실·정답 판단을 바꾸는 오역·심각한 비문. 단순 직역투·사소한 어색함은 제외. check/detail 필드가 있으면 그 자동 지적이 '실제 오류인지 오탐인지'를 판정하라. 출력은 반드시 순수 JSON 배열만: [{\"n\": 번호, \"field\": \"b|c[k]|e\", \"severity\": \"critical|major|minor|false_positive\", \"issue\": \"한국어 한 줄\", \"suggestion\": \"수정 번역문 (해당 언어)\"}] — 오류가 없으면 []."
  codex exec --sandbox read-only -m gpt-5.6-sol -c model_reasoning_effort="low" -C "$PROJ" "$PROMPT" < /dev/null > "$OUT/$base.txt" 2>&1
  if grep -q "hit your usage limit" "$OUT/$base.txt"; then
    rm -f "$OUT/$base.txt"
    echo "⛔ Codex 사용량 한도 도달 — 중단 (리셋 후 재실행하면 이어서 진행)"
    exit 2
  fi
  echo "  -> $(wc -c < "$OUT/$base.txt") bytes"
done
echo "완료: 이번 실행 $count개 배치 처리"
