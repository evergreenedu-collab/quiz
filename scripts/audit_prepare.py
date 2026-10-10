# -*- coding: utf-8 -*-
"""전체 번역 검수 배치 준비기 (2026-10-10 — 사용자 지시 '전체 검수').

translations/audit/queue/ 에 Codex 검수용 배치 파일 생성:
  1xx_flags_{lang}: 자동검증(validation_report.json) 지적 판정 — 최우선
  2xx_choices_{lang}_{i}: 문제+보기 전수 (배치 40문항)
  3xx_expl_{lang}_{i}: 해설 전수 (배치 20건)
scripts/audit_run.sh 가 큐를 순서대로 소비 → translations/audit/out/ 에 결과 저장.
"""
import json
import sys
import unicodedata
from json import JSONDecoder
from pathlib import Path

PROJ = Path(__file__).parent.parent
HTML = {"ko": "index.html", "en": "en.html", "cn": "cn.html", "vn": "vn.html"}
QUEUE = PROJ / "translations" / "audit" / "queue"
OUT = PROJ / "translations" / "audit" / "out"


def load_q(path):
    html = path.read_text(encoding="utf-8")
    i = html.find("const Q=")
    if i < 0:
        i = html.find("const Q =")
    s = html.find("[", i)
    Q, _ = JSONDecoder().raw_decode(html[s:])
    return {q["n"]: q for q in Q}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    QUEUE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    ko = load_q(PROJ / HTML["ko"])
    report = json.loads((PROJ / "translations" / "validation_report.json").read_text(encoding="utf-8"))
    ko_expl = json.loads((PROJ / "translations" / "_ko_source.json").read_text(encoding="utf-8"))
    made = 0

    for lang in ("vn", "en", "cn"):
        tr = load_q(PROJ / HTML[lang])
        expl = json.loads((PROJ / "translations" / f"expl_{lang}.json").read_text(encoding="utf-8"))

        # 1) 자동검증 지적 판정 배치 (지적 100건씩)
        flags = report.get(lang, [])
        for bi in range(0, len(flags), 100):
            chunk = []
            for f in flags[bi:bi + 100]:
                n = f["n"]
                kq, tq = ko.get(n) or {}, tr.get(n) or {}
                chunk.append({"n": n, "check": f["check"], "detail": f["detail"],
                              "ko_c": kq.get("c"), "tr_c": tq.get("c"),
                              "ko_b": kq.get("b"), "tr_b": tq.get("b")})
            name = f"1{bi // 100:02d}_flags_{lang}.json"
            (QUEUE / name).write_text(json.dumps(chunk, ensure_ascii=False, indent=1), encoding="utf-8")
            made += 1

        # 2) 문제+보기 전수 (40문항씩)
        ns = sorted(ko)
        for bi in range(0, len(ns), 40):
            chunk = []
            for n in ns[bi:bi + 40]:
                kq, tq = ko[n], tr.get(n) or {}
                chunk.append({"n": n, "ko_b": kq.get("b"), "ko_c": kq.get("c"), "a": kq.get("a"),
                              "tr_b": tq.get("b"), "tr_c": tq.get("c")})
            name = f"2{bi // 40:02d}_choices_{lang}.json"
            (QUEUE / name).write_text(json.dumps(chunk, ensure_ascii=False, indent=1), encoding="utf-8")
            made += 1

        # 3) 해설 전수 (20건씩)
        ens = sorted(expl, key=lambda x: int(x))
        for bi in range(0, len(ens), 20):
            chunk = []
            for n in ens[bi:bi + 20]:
                chunk.append({"n": int(n), "ko_e": ko_expl.get(n, ""), "tr_e": expl[n]})
            name = f"3{bi // 20:02d}_expl_{lang}.json"
            (QUEUE / name).write_text(json.dumps(chunk, ensure_ascii=False, indent=1), encoding="utf-8")
            made += 1

    print(f"배치 파일 {made}개 생성 → {QUEUE}")


if __name__ == "__main__":
    main()
