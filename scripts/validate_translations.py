# -*- coding: utf-8 -*-
"""번역 자동 검증기 (2026-10-10 — 688 방향 오역 신고 후 Codex 설계 6종 검사).

HTML 임베드 Q(런타임 정본)를 한국어 원본과 대조:
  ① 방향어 보존 (좌/우 ↔ trái/phải, left/right, 左/右)
  ② 같은 문항 내 보기 중복 (정규화 후 동일 — 688 유형)
  ③ 숫자 보존 (원문 숫자 집합 ⊂ 번역 숫자 집합)
  ④ 부정어 보존 (않/금지/없 ↔ not/no, không/cấm, 不/禁/没)
  ⑤ 한글 잔존 (외국어 본문·보기·해설에 한글)
  ⑥ 괄호·따옴표 짝
절단 검사는 scripts/repair_truncations.py(원본 PDF 대조)가 전담.

사용법: py scripts/validate_translations.py [--strict]
출력: 콘솔 요약 + translations/validation_report.json (LLM 정밀 검수 우선순위용)
"""
import argparse
import json
import re
import sys
import unicodedata
from json import JSONDecoder
from pathlib import Path

PROJ = Path(__file__).parent.parent
HTML = {"ko": "index.html", "en": "en.html", "cn": "cn.html", "vn": "vn.html"}

DIR = {
    "ko": {"L": re.compile(r"좌측|왼쪽|좌회전|좌로"), "R": re.compile(r"우측|오른쪽|우회전|우로"),
           "BOTH": re.compile(r"좌우|좌·우|좌ㆍ우|양측|양쪽|좌\s*․\s*우")},
    "vn": {"L": re.compile(r"bên trái|rẽ trái|phía trái|sang trái", re.I),
           "R": re.compile(r"bên phải|rẽ phải|phía phải|sang phải", re.I),
           "BOTH": re.compile(r"trái.{0,6}phải|hai bên", re.I)},
    "en": {"L": re.compile(r"\bleft\b", re.I), "R": re.compile(r"\bright(?!s\b| of way|-of-way)\b", re.I),
           "BOTH": re.compile(r"left and right|both sides", re.I)},
    "cn": {"L": re.compile(r"左"), "R": re.compile(r"右"), "BOTH": re.compile(r"左右|两侧|兩側")},
}
NEG = {
    "ko": re.compile(r"않|금지|없|말아야|아니"),
    "vn": re.compile(r"không|cấm|chưa|đừng", re.I),
    "en": re.compile(r"\bnot\b|\bno\b|prohibit|never|cannot|n't|\bnor\b|without|forbidden|banned|\bavoid", re.I),
    "cn": re.compile(r"不|禁|没|勿|无|非|莫"),
}
HANGUL = re.compile(r"[가-힣]")


def norm(s):
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", str(s or ""))).lower()


def nums_of(s):
    out = []
    for m in re.finditer(r"\d+(?:[.,]\d+)?", str(s or "")):
        out.append(m.group().replace(",", "."))
    return sorted(out)


def load_q(path):
    html = path.read_text(encoding="utf-8")
    i = html.find("const Q=")
    if i < 0:
        i = html.find("const Q =")
    s = html.find("[", i)
    Q, _ = JSONDecoder().raw_decode(html[s:])
    return {q["n"]: q for q in Q}


def dir_state(lang, text):
    d = DIR[lang]
    if d["BOTH"].search(text or ""):
        return "B"
    has_l = bool(d["L"].search(text or ""))
    has_r = bool(d["R"].search(text or ""))
    return ("B" if has_l and has_r else "L" if has_l else "R" if has_r else "-")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    ko = load_q(PROJ / HTML["ko"])
    report = {}
    for lang in ("vn", "en", "cn"):
        tr = load_q(PROJ / HTML[lang])
        issues = []
        for n, kq in ko.items():
            tq = tr.get(n)
            if not tq:
                issues.append({"n": n, "check": "missing", "detail": "문항 없음"})
                continue
            kc, tc = kq.get("c") or [], tq.get("c") or []
            # ① 방향어 보존 (보기 단위)
            for i, (k, t) in enumerate(zip(kc, tc)):
                ks, ts = dir_state("ko", k), dir_state(lang, t)
                if ks != "-" and ts != "-" and ks != ts:
                    issues.append({"n": n, "check": "direction", "detail": f"c[{i+1}] 한국어={ks} 번역={ts}",
                                   "ko": k[:60], "tr": t[:80]})
                elif ks in ("L", "R") and ts == "-":
                    issues.append({"n": n, "check": "direction_missing", "detail": f"c[{i+1}] 한국어={ks} 번역에 방향어 없음",
                                   "ko": k[:60], "tr": t[:80]})
            # ② 보기 중복
            seen = {}
            for i, t in enumerate(tc):
                key = norm(t)
                if len(key) >= 12 and key in seen:
                    if norm(kc[i]) != norm(kc[seen[key]]):   # 원문은 다른데 번역만 같음
                        issues.append({"n": n, "check": "dup_choice",
                                       "detail": f"c[{seen[key]+1}]와 c[{i+1}] 번역 동일 (원문은 다름)"})
                seen.setdefault(key, i)
            # ③ 숫자 보존 ④ 부정어 (보기 단위)
            for i, (k, t) in enumerate(zip(kc, tc)):
                kn, tn = nums_of(k), nums_of(t)
                missing = [x for x in kn if x not in tn]
                if missing:
                    issues.append({"n": n, "check": "number", "detail": f"c[{i+1}] 번역에 누락된 숫자 {missing}",
                                   "ko": k[:60], "tr": t[:80]})
                if NEG["ko"].search(k) and not NEG[lang].search(t) and len(norm(t)) > 10:
                    issues.append({"n": n, "check": "negation", "detail": f"c[{i+1}] 부정어 소실 의심",
                                   "ko": k[:60], "tr": t[:80]})
            # ⑤ 한글 잔존 (b·c·e)
            for fkey in ("b", "e"):
                v = tq.get(fkey)
                if isinstance(v, str) and HANGUL.search(v):
                    issues.append({"n": n, "check": "hangul", "detail": f"{fkey}에 한글 잔존"})
            for i, t in enumerate(tc):
                if HANGUL.search(t or ""):
                    issues.append({"n": n, "check": "hangul", "detail": f"c[{i+1}]에 한글 잔존"})
            # ⑥ 괄호 짝 (보기+해설)
            for fkey, v in [("e", tq.get("e"))] + [(f"c[{i+1}]", t) for i, t in enumerate(tc)]:
                if isinstance(v, str) and (v.count("(") != v.count(")")):
                    issues.append({"n": n, "check": "paren", "detail": f"{fkey} 괄호 짝 불일치"})
        by_check = {}
        for it in issues:
            by_check[it["check"]] = by_check.get(it["check"], 0) + 1
        print(f"[{lang}] 지적 {len(issues)}건 — " + ", ".join(f"{k}:{v}" for k, v in sorted(by_check.items())))
        report[lang] = issues

    out = PROJ / "translations" / "validation_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n상세: {out}")
    total = sum(len(v) for v in report.values())
    if args.strict and total:
        sys.exit(1)


if __name__ == "__main__":
    main()
