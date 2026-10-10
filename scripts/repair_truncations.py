# -*- coding: utf-8 -*-
"""PDF 추출 절단 복원기 (2026-10-10 — 베트남어 688번 신고로 발견된 전수 문제).

HTML 임베드 Q의 문제(b)·보기(c)가 원본 PDF 대비 중간에 잘렸는지 검사하고,
원본 PDF 전문에서 해당 문자열을 찾아 문장 끝(다음 보기 마커·섹션 기호)까지 복원한다.
quiz_data_{lang}.json도 함께 동기화.

사용법:
  py scripts/repair_truncations.py            # 검사만 (보고)
  py scripts/repair_truncations.py --apply    # 복원 적용 (HTML + quiz_data)
"""
import argparse
import json
import re
import sys
import unicodedata
from json import JSONDecoder
from pathlib import Path

import pypdf

PROJ = Path(__file__).parent.parent
PDF_DIR = PROJ / "원본_PDF"

LANGS = {
    "ko": {"html": "index.html", "pdf_kw": "한국어"},
    "en": {"html": "en.html", "pdf_kw": "English"},
    "cn": {"html": "cn.html", "pdf_kw": "Chinese"},
    "vn": {"html": "vn.html", "pdf_kw": "Vietnamese"},
}

# 보기/섹션 경계 — PDF에서 복원 구간의 끝 (다음 보기·캡션·정답/해설 라벨·다음 문항)
BOUNDARY = re.compile(
    r'[①②③④⑤➀➁➂➃➄■◆□<]|\n\s*\d{1,4}\s*\.'
    r'|정답|해설|Answer|Explanation|答案|解说|解說|Đáp án|Giải thích')


def load_q(html_path):
    html = html_path.read_text(encoding="utf-8")
    i = html.find("const Q=")
    if i < 0:
        i = html.find("const Q =")
    s = html.find("[", i)
    Q, end = JSONDecoder().raw_decode(html[s:])
    return html, s, end, Q


def pdf_fulltext(lang):
    kw = LANGS[lang]["pdf_kw"]
    pdfs = [p for p in PDF_DIR.glob("*.pdf") if kw in p.name]
    if not pdfs:
        return None
    r = pypdf.PdfReader(str(pdfs[0]))
    return "\n".join((p.extract_text() or "") for p in r.pages)


def _norm(s):
    """비교용 정규화 — NFC(베트남어 성조 합성형 통일) + 공백 제거."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", s or ""))


def build_anchors(pdf_text, questions):
    """문항 본문(b) 앞부분을 앵커로 PDF 윈도우 산출 — 번호 앵커는 해설 속
    열거 번호('1.', '2.')에 오매칭되므로 본문 텍스트 매칭이 확실하다."""
    norm_chars, norm_map = [], []
    for idx, ch in enumerate(pdf_text):
        if not ch.isspace():
            norm_chars.append(ch)
            norm_map.append(idx)
    pdf_norm = "".join(norm_chars)

    starts = {}
    search_from = 0
    for q in sorted(questions, key=lambda x: x["n"]):
        key = _norm(q.get("b", ""))[:30]
        if len(key) < 10:
            continue
        pos = pdf_norm.find(key, search_from)
        if pos < 0:
            pos = pdf_norm.find(key)   # 순서 어긋남 대비 전역 재시도
        if pos >= 0:
            starts[q["n"]] = norm_map[pos]
            search_from = pos + 1
    windows = {}
    ordered = sorted(starts.items(), key=lambda kv: kv[1])
    for i, (n, p) in enumerate(ordered):
        nxt = ordered[i + 1][1] if i + 1 < len(ordered) else len(pdf_text)
        windows[n] = (max(0, p - 20), nxt)
    return windows


def check_in_window(window_text, frag):
    """문항 윈도우 안에서 frag 완결/절단 판정.
    반환: ('ok'|'truncated'|'notfound', 복원문 또는 None)"""
    nf = _norm(frag)
    if len(nf) < 10:
        return ("ok", None)          # 짧은 보기(단답·수치)는 판정 생략
    norm_chars, norm_map = [], []
    for idx, ch in enumerate(window_text):
        if not ch.isspace():
            norm_chars.append(ch)
            norm_map.append(idx)
    wnorm = "".join(norm_chars)
    pos = wnorm.find(nf)
    if pos < 0:
        return ("notfound", None)
    start = norm_map[pos]
    after_idx = pos + len(nf)
    tail_start = norm_map[after_idx] if after_idx < len(norm_map) else len(window_text)
    m = BOUNDARY.search(window_text, tail_start)
    end = m.start() if m else min(tail_start + 400, len(window_text))
    extension = re.sub(r"\s+", "", window_text[tail_start:end])
    if not extension:
        return ("ok", None)
    full = re.sub(r"\s+", " ", window_text[start:end]).strip()
    return ("truncated", full)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--langs", default="vn,en,cn,ko")
    args = ap.parse_args()

    total_fix, total_manual = 0, 0
    for lang in [x.strip() for x in args.langs.split(",") if x.strip()]:
        html_path = PROJ / LANGS[lang]["html"]
        html, s, end, Q = load_q(html_path)
        pdf_text = pdf_fulltext(lang)
        if not pdf_text:
            print(f"[{lang}] 원본 PDF 없음 — 건너뜀")
            continue
        pdf_text = unicodedata.normalize("NFC", pdf_text)
        windows = build_anchors(pdf_text, Q)

        fixed, manual = [], []
        for q in Q:
            win = windows.get(q["n"])
            if not win:
                manual.append((f'{q["n"]}', "(PDF에서 문항 앵커 못 찾음)"))
                continue
            wtext = pdf_text[win[0]:win[1]]
            fields = [("b", None, q.get("b"))]
            for ci, c in enumerate(q.get("c") or []):
                fields.append(("c", ci, c))
            for fkey, ci, val in fields:
                if not isinstance(val, str):
                    continue
                status, full = check_in_window(wtext, val)
                loc = f'{q["n"]}.{fkey}' + (f"[{ci + 1}]" if ci is not None else "")
                if status == "truncated":
                    fixed.append((loc, val[-25:], full[-40:]))
                    if args.apply:
                        if fkey == "b":
                            q["b"] = full
                        else:
                            q["c"][ci] = full
                elif status == "notfound":
                    manual.append((loc, val[-30:]))

        print(f"\n[{lang}] 절단 복원 가능 {len(fixed)}건 / 수동 확인 {len(manual)}건")
        for loc, old, new in fixed[:30]:
            print(f"  ✅ {loc}: …{old!r} → …{new!r}")
        for loc, old in manual[:15]:
            print(f"  ⚠️ {loc}: …{old!r} (PDF 매칭 실패)")
        total_fix += len(fixed)
        total_manual += len(manual)

        if args.apply and fixed:
            new_arr = json.dumps(Q, ensure_ascii=False, separators=(",", ":"))
            html_path.write_text(html[:s] + new_arr + html[s + end:], encoding="utf-8")
            jd_path = PROJ / f"quiz_data_{lang}.json"
            if jd_path.exists():
                jd = json.loads(jd_path.read_text(encoding="utf-8"))
                by_n = {x["n"]: x for x in jd.get("questions", [])}
                for q in Q:
                    t = by_n.get(q["n"])
                    if t:
                        t["b"], t["c"] = q.get("b"), q.get("c")
                jd_path.write_text(json.dumps(jd, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
            print(f"  💾 {LANGS[lang]['html']} + quiz_data_{lang}.json 반영")

    print(f"\n합계: 복원 {total_fix}건, 수동 확인 {total_manual}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
