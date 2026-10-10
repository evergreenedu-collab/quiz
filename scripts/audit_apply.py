# -*- coding: utf-8 -*-
"""검수 발견(findings.json) 적용기 — critical/major의 suggestion을 HTML Q + quiz_data에 반영.

안전장치:
- 보기 인덱스: 모델 출력이 0/1-기준 혼용 → 선언 인덱스(1-기준 우선)와 기존 번역문-제안문
  유사도(difflib)로 교차 확인, 애매하면 전 보기 중 최유사(여유 마진)로, 그래도 애매하면 보류.
- 언어 순도(en/vn에 한글·한자 금지, cn에 한글 금지), 길이 비율 0.35~3.0.
- minor/false_positive/제안 없음 → 적용 안 함(검토 목록).
사용법: py scripts/audit_apply.py [--apply]  (기본 드라이런)
출력: translations/audit/apply_report.json
"""
import argparse
import difflib
import json
import re
import sys
import unicodedata
from json import JSONDecoder
from pathlib import Path

PROJ = Path(__file__).parent.parent
HTML = {"en": "en.html", "cn": "cn.html", "vn": "vn.html"}
HANGUL = re.compile(r"[가-힣]")
HANJA = re.compile(r"[一-鿿]")


def norm(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(s or ""))).strip()


def sim(a, b):
    return difflib.SequenceMatcher(None, norm(a).lower(), norm(b).lower()).ratio()


def lang_ok(lang, s):
    if HANGUL.search(s):
        return False
    if lang in ("en", "vn") and HANJA.search(s):
        return False
    return True


def load_q(path):
    html = path.read_text(encoding="utf-8")
    i = html.find("const Q=")
    if i < 0:
        i = html.find("const Q =")
    s = html.find("[", i)
    Q, end = JSONDecoder().raw_decode(html[s:])
    return html, s, end, Q


def resolve_choice_idx(field, choices, sugg):
    """'c[k]' + 제안문 유사도로 실제 인덱스 확정. 실패 시 None."""
    m = re.match(r"c\[(\d+)\]", str(field))
    scores = [sim(c, sugg) for c in choices]
    cand = []
    if m:
        k = int(m.group(1))
        for idx in (k - 1, k):              # 1-기준 우선, 0-기준 보조
            if 0 <= idx < len(choices):
                cand.append(idx)
    for idx in cand:
        if scores[idx] >= 0.35:
            return idx
    best = max(range(len(choices)), key=lambda i: scores[i]) if choices else None
    if best is not None and scores[best] >= 0.45:
        others = sorted(scores, reverse=True)
        if len(others) < 2 or others[0] - others[1] >= 0.1:
            return best
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    findings = json.loads((PROJ / "translations" / "audit" / "findings.json").read_text(encoding="utf-8"))
    applied, review = [], []
    docs = {}
    for lang in HTML:
        docs[lang] = load_q(PROJ / HTML[lang])

    # 대상별 최우선 1건만 (critical > major, 그다음 issue 긴 것)
    rank = {"critical": 0, "major": 1}
    pick = {}
    for it in findings:
        if it.get("severity") not in rank or not str(it.get("suggestion", "")).strip():
            if it.get("severity") in ("critical", "major"):
                review.append({**it, "skip_reason": "suggestion 없음"})
            continue
        key = (it["lang"], it["n"], str(it.get("field")))
        cur = pick.get(key)
        if cur is None or (rank[it["severity"]], -len(str(it.get("issue", "")))) < \
                          (rank[cur["severity"]], -len(str(cur.get("issue", "")))):
            pick[key] = it

    for it in pick.values():
        lang, n, field = it["lang"], it["n"], str(it.get("field"))
        sugg = norm(it["suggestion"])
        html, s, end, Q = docs[lang]
        q = next((x for x in Q if x["n"] == n), None)
        if not q:
            review.append({**it, "skip_reason": "문항 없음"})
            continue
        if not lang_ok(lang, sugg):
            review.append({**it, "skip_reason": "언어 순도 실패"})
            continue
        if field == "b":
            old = q.get("b", "")
            if not (0.35 <= len(sugg) / max(len(norm(old)), 1) <= 3.0) or sim(old, sugg) < 0.25:
                review.append({**it, "skip_reason": "b 유사도/길이 가드"})
                continue
            if args.apply:
                q["b"] = sugg
            applied.append({**it, "target": "b", "old": old})
        elif field.startswith("c["):
            choices = q.get("c") or []
            idx = resolve_choice_idx(field, choices, sugg)
            if idx is None:
                review.append({**it, "skip_reason": "보기 인덱스 미확정"})
                continue
            old = choices[idx]
            if not (0.35 <= len(sugg) / max(len(norm(old)), 1) <= 3.0):
                review.append({**it, "skip_reason": "길이 가드"})
                continue
            if args.apply:
                q["c"][idx] = sugg
            applied.append({**it, "target": f"c[{idx + 1}](1-base)", "old": old})
        else:
            review.append({**it, "skip_reason": f"미지원 field {field}"})

    if args.apply:
        for lang, (html, s, end, Q) in docs.items():
            path = PROJ / HTML[lang]
            path.write_text(html[:s] + json.dumps(Q, ensure_ascii=False, separators=(",", ":"))
                            + html[s + end:], encoding="utf-8")
            jd_path = PROJ / f"quiz_data_{lang}.json"
            jd = json.loads(jd_path.read_text(encoding="utf-8"))
            by = {x["n"]: x for x in jd.get("questions", [])}
            for q in Q:
                t = by.get(q["n"])
                if t:
                    t["b"], t["c"] = q.get("b"), q.get("c")
            jd_path.write_text(json.dumps(jd, ensure_ascii=False, indent=1), encoding="utf-8")

    rep = {"applied": applied, "review": review}
    out = PROJ / "translations" / "audit" / "apply_report.json"
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    import collections
    print(f"적용{'(드라이런)' if not args.apply else ''}: {len(applied)}건 | 보류(검토): {len(review)}건")
    print("적용 분포:", dict(collections.Counter(f"{x['lang']}/{x['severity']}" for x in applied)))
    print("보류 사유:", dict(collections.Counter(x['skip_reason'] for x in review)))
    print(f"→ {out}")


if __name__ == "__main__":
    main()
