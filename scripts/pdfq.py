# -*- coding: utf-8 -*-
"""공단 학과시험 PDF 공통 추출기 (5개 언어).

refresh_pdf.extract_pdf(정답 라벨 앵커) 위에 보기 파서를 얹어 HTML Q 형식의 문항을 만든다.
- 보기 마커 ①~⑤ (오타 기호 ⓛ→①, ➀➁➂➃→①②③④ 보정), 마커는 문항 안에서 정확히 1회씩·순서대로
- 사진 설명줄(■ …, 몽골어 n …)은 보기에서 제거 (en/cn/vn 기존 데이터와 동일한 관례)
- 정답 'N' 또는 'N, N' 정규화 (중복·오름차순)
- ko 해설: 다음 문항 번호 줄에서 절단 (혼입 방지)
- normalize()/qhash(): 변경 판정용 정규형 (NFC·공백·NBSP·따옴표 변형만 동등 처리)

사용: from pdfq import extract_lang, normalize, qhash, EXTRACTOR_VERSION
"""
import hashlib
import re
import unicodedata
from pathlib import Path

from refresh_pdf import extract_pdf

EXTRACTOR_VERSION = "2026-11-07.1"
MARKERS = "①②③④⑤"
MARKER_FIX = {"ⓛ": "①", "➀": "①", "➁": "②", "➂": "③", "➃": "④", "➄": "⑤"}
CAPTION_RE = re.compile(r"(?m)^\s*■")
CAPTION_RE_MN = re.compile(r"(?m)(?:^\s*■|^n |\sn (?=[А-ЯЁӨҮA-Z0-9«\"“+]))")


def normalize(s):
    s = unicodedata.normalize("NFC", str(s or ""))
    s = s.replace(" ", " ").replace("　", " ")
    s = s.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"\s+", " ", s).strip()
    return s


def clean(s):
    """저장용 정리: NFC·NBSP·연속 공백만 정리 (따옴표 등 내용 문자는 보존)"""
    s = unicodedata.normalize("NFC", str(s or ""))
    s = s.replace(" ", " ").replace("　", " ")
    return re.sub(r"\s+", " ", s).strip()


def qhash(q, with_e=False):
    parts = [str(q["n"]), normalize(q["b"]), "|".join(normalize(c) for c in q["c"]), normalize(q["a"])]
    if with_e:
        parts.append(normalize(q.get("e", "")))
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _fix_markers(body):
    for k, v in MARKER_FIX.items():
        body = body.replace(k, v)
    return body


def parse_body(body, lang="ko"):
    """추출 body → (b, c, err). 마커는 ①부터 연속·각 1회."""
    body = _fix_markers(body)
    cap = (CAPTION_RE_MN if lang == "mn" else CAPTION_RE).search(body)
    counts = {m: body.count(m) for m in MARKERS}
    if cap:
        # 사진 설명줄은 마지막 마커 뒤에만 허용 — 그 앞에서 나오면 본문 일부이므로 유지
        last = max((body.rfind(m) for m in MARKERS if counts[m]), default=-1)
        if cap.start() > last:
            body = body[:cap.start()]
            counts = {m: body.count(m) for m in MARKERS}
    dup = [m for m, c in counts.items() if c > 1]
    if dup:
        return None, None, f"마커 중복 {dup}"
    present = [(body.find(m), i) for i, m in enumerate(MARKERS) if counts[m]]
    if not present:
        return None, None, "보기 마커 없음"
    present.sort()
    if [i for _, i in present] != list(range(len(present))):
        return None, None, f"마커 순서 이상 {[MARKERS[i] for _, i in present]}"
    first = present[0][0]
    head = body[:first].strip()
    m = re.match(r"^\s*(\d+)\.?\s*(.*)", head, re.DOTALL)
    b = clean(m.group(2) if m else head)
    c = []
    for k, (p, _) in enumerate(present):
        end = present[k + 1][0] if k + 1 < len(present) else len(body)
        c.append(clean(body[p + 1:end]))
    if not b or any(not x for x in c):
        return None, None, "본문/보기 빈값"
    return b, c, None


def parse_answer(raw, n_choices):
    a = re.sub(r"^\s*(?:đúng\s*)?[:：]\s*", "", str(raw or "").strip())
    nums = re.findall(r"\d+", a)
    if not nums or not re.fullmatch(r"[\d\s,.，、]+", a):
        return None, f"정답 형식 이상 {a!r}"
    if len(set(nums)) != len(nums):
        return None, f"정답 중복 {a!r}"
    vals = sorted(int(x) for x in nums)
    if any(v < 1 or v > n_choices for v in vals):
        return None, f"정답 범위 밖 {vals} / 보기 {n_choices}"
    return ", ".join(str(v) for v in vals), None


def cut_explanation(e, n):
    """ko 해설: 다음 문항('N+1. ' 또는 아무 'NNN. ') 줄에서 절단, 공백 정규화."""
    if not e:
        return ""
    m = re.search(r"(?:^|\n)\s*%d\.\s" % (n + 1), e) or re.search(r"\n\s*\d{1,4}\.\s", e)
    if m:
        e = e[:m.start()]
    return clean(e)


def extract_lang(pdf_path, lang):
    """→ (items: {n: {n,b,c,a[,e]}}, problems: {n: reason}, found_numbers: set)"""
    raw = extract_pdf(str(pdf_path), lang)
    items, problems = {}, {}
    for n in range(1, 1001):
        rec = raw.get(n)
        if not rec:
            problems[n] = "PDF에서 문항 없음(정답 라벨 미검출)"
            continue
        b, c, err = parse_body(rec["body"], lang)
        if err:
            problems[n] = err
            continue
        a, err = parse_answer(rec["a"], len(c))
        if err:
            problems[n] = err
            continue
        q = {"n": n, "b": b, "c": c, "a": a}
        if lang == "ko":
            q["e"] = cut_explanation(rec.get("e", ""), n)
        items[n] = q
    extra = sorted(k for k in raw if k < 1 or k > 1000)
    return items, problems, extra


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
