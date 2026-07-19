# -*- coding: utf-8 -*-
"""번역 대상 추출: SAFE 문항 중 한국어 해설이 있는 것 → translations/_ko_source.json
(RISKY 12문항과 해설 없는 문항은 제외)
"""
import sys
import json
from pathlib import Path

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ))
from html_to_txt import extract_Q

risky = set(int(n) for n in json.load(
    open(PROJ / "translations" / "risky_questions.json", encoding="utf-8"))["risky"])

Q = extract_Q(str(PROJ / "index.html"))
src = {q["n"]: q["e"] for q in Q
       if q["n"] not in risky and (q.get("e") or "").strip()}

out = PROJ / "translations" / "_ko_source.json"
out.write_text(json.dumps(src, ensure_ascii=False, indent=1), encoding="utf-8")

tot = sum(len(e) for e in src.values())
print(f"번역 대상(SAFE + 해설 있음): {len(src)}문항")
print(f"총 해설 글자수: {tot:,} (평균 {tot // len(src)}자, 최대 {max(len(e) for e in src.values())}자)")
print(f"기록: translations/_ko_source.json")
print(f"\n샘플(첫 3개):")
for n in list(src)[:3]:
    print(f"  Q{n}: {src[n][:70]}...")
