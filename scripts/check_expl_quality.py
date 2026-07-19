# -*- coding: utf-8 -*-
"""한국어 해설 품질 검사: 절단·다음문항 혼입·괄호 미완 등 손상 문항 식별.
번역 전 선행 검사 — 손상된 해설을 번역하면 3개 언어로 전파되므로.
"""
import sys
import json
import re
from pathlib import Path

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ))
from html_to_txt import extract_Q

Q = extract_Q(str(PROJ / "index.html"))
issues = {}
for q in Q:
    e = (q.get("e") or "").strip()
    if not e:
        continue
    probs = []
    # 1) 다음 문항(n+1) 지문 혼입만 — 법조항 나열 '1.2.3.'은 오탐이라 제외
    nxt = str(q["n"] + 1)
    if re.search(r"(?<!제)(?<!별표)(?<!표)\s" + re.escape(nxt) + r"\.\s*[가-힣]", " " + e):
        probs.append(f"다음문항({nxt})혼입")
    # 2) 괄호·낫표 짝 안 맞음(끊김 신호)
    if e.count("(") != e.count(")") or e.count("（") != e.count("）"):
        probs.append("괄호미완")
    if e.count("「") != e.count("」"):
        probs.append("낫표미완")
    # 3) 영문 단어 중간에서 끝남(끊김)
    if re.search(r"[A-Za-z]{3,}$", e):
        probs.append(f"영문끊김[...{e[-15:]}]")
    # 4) 라벨 잔존(추출 오염)
    if "■" in e or e[:6].startswith("해설"):
        probs.append("라벨잔존")
    if probs:
        issues[q["n"]] = probs

print(f"검사 대상(해설 있음): {sum(1 for q in Q if (q.get('e') or '').strip())}문항")
print(f"손상 의심 문항: {len(issues)}개\n")
for n in sorted(issues):
    print(f"  Q{n}: {', '.join(issues[n])}")

out = PROJ / "translations" / "_ko_damaged.json"
out.write_text(json.dumps({str(n): issues[n] for n in sorted(issues)}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n기록: translations/_ko_damaged.json ({len(issues)}개)")
