# -*- coding: utf-8 -*-
"""translations/manual_patches.json을 HTML 임베드 Q + quiz_data_{lang}.json에 적용.
공단 원본 PDF 자체의 오류 정정 — PDF 재추출 후 반드시 재실행 (UPDATE_GUIDE 참조).
사용법: py scripts/apply_manual_patches.py
"""
import json
import sys
from json import JSONDecoder
from pathlib import Path

PROJ = Path(__file__).parent.parent
HTML = {"ko": "index.html", "en": "en.html", "cn": "cn.html", "vn": "vn.html"}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    patches = json.loads((PROJ / "translations" / "manual_patches.json").read_text(encoding="utf-8"))
    for lang, items in patches.items():
        if lang.startswith("_"):
            continue
        html_path = PROJ / HTML[lang]
        html = html_path.read_text(encoding="utf-8")
        i = html.find("const Q=")
        if i < 0:
            i = html.find("const Q =")
        s = html.find("[", i)
        Q, end = JSONDecoder().raw_decode(html[s:])
        by_n = {q["n"]: q for q in Q}
        applied = 0
        for n_str, patch in items.items():
            q = by_n.get(int(n_str))
            if not q:
                print(f"  ⚠️ {lang} {n_str}: 문항 없음")
                continue
            for idx_str, text in (patch.get("c") or {}).items():
                ci = int(idx_str) - 1
                if 0 <= ci < len(q.get("c", [])):
                    if q["c"][ci] != text:
                        q["c"][ci] = text
                        applied += 1
            if patch.get("b"):
                q["b"] = patch["b"]
                applied += 1
        html_path.write_text(html[:s] + json.dumps(Q, ensure_ascii=False, separators=(",", ":"))
                             + html[s + end:], encoding="utf-8")
        jd_path = PROJ / f"quiz_data_{lang}.json"
        if jd_path.exists():
            jd = json.loads(jd_path.read_text(encoding="utf-8"))
            jby = {x["n"]: x for x in jd.get("questions", [])}
            for q in Q:
                t = jby.get(q["n"])
                if t:
                    t["b"], t["c"] = q.get("b"), q.get("c")
            jd_path.write_text(json.dumps(jd, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{lang}] 수동 패치 {applied}건 적용")


if __name__ == "__main__":
    main()
