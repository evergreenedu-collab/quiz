# -*- coding: utf-8 -*-
"""검수 결과 파서 — translations/audit/out/*.txt(Codex 출력)에서 최종 JSON 배열을
추출·집계해 translations/audit/findings.json 생성.

Codex 출력은 로그+최종답(동일 JSON이 2회 찍히는 경우 있음) 형태 → 파일에서
'파싱 가능한 마지막 JSON 배열'을 채택하고, (lang,n,field,issue)로 중복 제거.
"""
import json
import re
import sys
from json import JSONDecoder
from pathlib import Path

PROJ = Path(__file__).parent.parent
OUT = PROJ / "translations" / "audit" / "out"
DEC = JSONDecoder()


def last_json_array(text):
    best = None
    for m in re.finditer(r"\[", text):
        i = m.start()
        # 빠른 필터: '[{' 또는 '[]' 꼴만 시도
        nxt = text[i:i + 2]
        if nxt not in ("[{", "[]"):
            continue
        try:
            val, _ = DEC.raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        if not isinstance(val, list):
            continue
        if val and isinstance(val[0], dict):
            if "n" not in val[0]:
                continue
            if any(k in val[0] for k in ("ko_b", "ko_c", "ko_e", "tr_b", "tr_c", "tr_e", "check")):
                continue   # 입력 배치 echo — 검수 결과 아님
        best = val
    return best


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    findings = []
    seen = set()
    parse_fail = []
    for f in sorted(OUT.glob("*.txt")):
        lang = f.stem.split("_")[-1]
        kind = f.stem.split("_")[1]
        arr = last_json_array(f.read_text(encoding="utf-8", errors="replace"))
        if arr is None:
            parse_fail.append(f.name)
            continue
        for it in arr:
            if not isinstance(it, dict):
                continue
            key = (lang, it.get("n"), str(it.get("field")), str(it.get("issue"))[:60])
            if key in seen:
                continue
            seen.add(key)
            it["lang"] = lang
            it["kind"] = kind
            it["src"] = f.stem
            findings.append(it)

    sev = {}
    by_lang = {}
    for it in findings:
        s = it.get("severity", "?")
        sev[s] = sev.get(s, 0) + 1
        by_lang.setdefault(it["lang"], {}).setdefault(s, 0)
        by_lang[it["lang"]][s] += 1

    out = PROJ / "translations" / "audit" / "findings.json"
    out.write_text(json.dumps(findings, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"총 발견 {len(findings)}건 (중복 제거 후) | 심각도: {sev}")
    for lg, d in sorted(by_lang.items()):
        print(f"  [{lg}] {d}")
    if parse_fail:
        print(f"⚠️ JSON 추출 실패 배치 {len(parse_fail)}개: {parse_fail[:10]}")
    print(f"→ {out}")


if __name__ == "__main__":
    main()
