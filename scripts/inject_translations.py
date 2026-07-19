# -*- coding: utf-8 -*-
"""번역 캐시(translations/expl_{en,cn,vn}.json)를 en/cn/vn HTML의 e 필드에 주입.
- RISKY 문항(risky_questions.json)은 e 제거 → 화면에서 폴백(준비 중+AI튜터).
- 해설 없는 문항(번역 대상 아님)은 e 없음 유지 → 폴백.
사용법: py scripts/inject_translations.py
"""
import sys
import json
import re
from json import JSONDecoder
from pathlib import Path

PROJ = Path(__file__).parent.parent
T = PROJ / "translations"

risky = set(json.load(open(T / "risky_questions.json", encoding="utf-8"))["risky"])

for lang in ["en", "cn", "vn"]:
    trans = json.load(open(T / f"expl_{lang}.json", encoding="utf-8"))
    path = PROJ / f"{lang}.html"
    html = path.read_text(encoding="utf-8")
    i = html.find("const Q=")
    if i < 0:
        i = html.find("const Q =")
    s = html.find("[", i)
    Q, end = JSONDecoder().raw_decode(html[s:])

    injected = 0
    fallback = 0
    for q in Q:
        n = str(q["n"])
        if n in risky:
            q.pop("e", None)  # RISKY → 폴백
            fallback += 1
        elif n in trans:
            q["e"] = trans[n]
            injected += 1
        else:
            q.pop("e", None)  # 해설 없는 문항 → 폴백

    new_arr = json.dumps(Q, ensure_ascii=False, separators=(",", ":"))
    html = html[:s] + new_arr + html[s + end:]
    path.write_text(html, encoding="utf-8")
    print(f"{lang}.html: 번역 주입 {injected}개, 폴백(RISKY+무해설) {fallback + (len(Q)-injected-fallback)}개")

print("\n주입 완료. serve.py로 확인하세요.")
