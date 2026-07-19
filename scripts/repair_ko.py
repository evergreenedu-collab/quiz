# -*- coding: utf-8 -*-
"""한국어 해설 정정 (파이프라인 2단계).

300자 절단·다음 문항 혼입 문항을 **본문+보기+정답 앵커**로 원본 PDF에서 재추출한다.
정답 자동 대조로 오매칭을 격리(유사 본문에서 엉뚱한 문항 잡히는 것 방지)하고,
후속 문항 지문 잔존을 제거한 뒤 index.html의 e 필드에 반영한다.

사용법:
    py scripts/repair_ko.py [--dry-run]

배경(2026-07-19): 배포본 해설 116개가 300자에서 잘려 다음 문항이 섞여 있었음.
자동 재추출도 "다음 상황에서..." 같은 유사 본문에서 오매칭 위험 → 정답 대조 필수.
오매칭·매칭 실패 문항은 리포트만 하고 손대지 않음(수동/Codex 확인).
"""
import sys
import re
import json
import argparse
from pathlib import Path
import fitz

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ))
from html_to_txt import extract_Q
from refresh_pdf import find_pdfs


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def dset(a):
    return tuple(sorted(c for c in str(a) if c.isdigit()))


def strip_next_question(n, e):
    """현재 문항번호 n보다 큰 후속 문항번호 'NN. 한글' 잔존을 잘라냄."""
    for m in re.finditer(r"(?<!제)(?<!별표)(?<!\d)\s(\d{1,4})\.\s+[가-힣]", " " + e):
        if int(m.group(1)) > int(n):
            return e[: m.start() - 1]
    return e


def repair(dry_run=False):
    ko_pdf = find_pdfs(PROJ / "원본_PDF").get("ko")
    if not ko_pdf:
        print("한국어 PDF를 찾지 못함(원본_PDF/)")
        return {}, []
    doc = fitz.open(ko_pdf)
    full = norm("\n".join(p.get_text() for p in doc))
    doc.close()

    Q = extract_Q(str(PROJ / "index.html"))
    idx = {q["n"]: q for q in Q}
    # 300자에서 잘린(절단 의심) 문항
    targets = [q["n"] for q in Q if len(q.get("e") or "") == 300]

    fixed = {}
    unmatched = []
    for n in targets:
        q = idx[n]
        b = norm(q["b"])[:22]
        c0 = norm(q["c"][0])[:12] if q.get("c") else ""
        cands = [m.start() for m in re.finditer(re.escape(b), full)]
        pos = None
        # 1순위: 본문+보기1+정답 모두 일치
        for p in cands:
            seg = full[p:p + 2600]
            am = re.search(r"정답\s*[:：]\s*([0-9,\.\s]+?)\s*(?:■|해설)", seg)
            ok_ans = am and dset(am.group(1)) == dset(q["a"])
            ok_c0 = (not c0) or (c0 in seg)
            if ok_ans and ok_c0:
                pos = p
                break
        # 2순위: 정답만 일치(보기1 실패 시)
        if pos is None:
            for p in cands:
                seg = full[p:p + 2600]
                am = re.search(r"정답\s*[:：]\s*([0-9,\.\s]+?)\s*(?:■|해설)", seg)
                if am and dset(am.group(1)) == dset(q["a"]):
                    pos = p
                    break
        if pos is None:
            unmatched.append(n)
            continue
        seg = full[pos:pos + 3000]
        h = re.search(r"해설\s*[:：]?\s*(.+?)(?=■\s*정답|\Z)", seg)
        e = h.group(1) if h else ""
        e = strip_next_question(n, e)
        e = norm(re.sub(r"^\s*해설\s*[:：]?\s*", "", e.replace("■", "")))
        if e:
            fixed[n] = e
        else:
            unmatched.append(n)

    print(f"절단(300자) {len(targets)}개 → 정정 {len(fixed)} / 매칭실패·오매칭 {len(unmatched)}")
    if unmatched:
        print(f"  ⚠️ 자동 매칭 실패(수동/Codex 확인 필요): {sorted(unmatched)}")

    if not dry_run and fixed:
        html = (PROJ / "index.html").read_text(encoding="utf-8")
        for n, e in fixed.items():
            pat = re.compile(r'("n":' + str(n) + r',(?:(?!"n":)[\s\S])*?"e":)"(?:[^"\\]|\\.)*"')
            html, c = pat.subn(lambda m: m.group(1) + json.dumps(e, ensure_ascii=False), html, count=1)
        (PROJ / "index.html").write_text(html, encoding="utf-8")
        print(f"index.html 반영 완료: {len(fixed)}개")
    elif dry_run:
        print("(dry-run — 파일 미수정)")
    return fixed, unmatched


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="파일 수정 없이 결과만 출력")
    args = ap.parse_args()
    repair(args.dry_run)
