# -*- coding: utf-8 -*-
"""PDF 추출본 → HTML const Q 문제 교체 (파이프라인 1단계 핵심).

각 언어 PDF에서 추출한 문항(본문 b·보기 c·정답 a·해설 e)을 HTML의 const Q 배열에 반영한다.
- 기존 문항: b/c/a 갱신(ko는 e도). **t·imgs는 유지**(match_images가 별도 담당).
- 신규 문항(PDF에만 있음): 추가(t=문장형/동영상형 기본, imgs=[]).
- HTML에만 있고 PDF에 없는 문항: **원본 보존**(추출 실패와 구분 불가 → 자동 삭제 안 함, 리포트만).
- **보기 개수가 바뀐 문항은 경고**만 하고 b/a만 갱신(c는 수동 확인 — parse_record는 ①~④ 4선택지 기준이라 5선택지 문항 주의).

사용법: py scripts/apply_pdf_to_html.py [--dry-run]
⚠️ 실행 순서: 이 스크립트 → repair_ko.py(해설 정정) → match_images.py(이미지). (REFRESH_PIPELINE.md 참조)
"""
import sys
import json
import argparse
from json import JSONDecoder
from pathlib import Path

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ / "scripts"))
sys.path.insert(0, str(PROJ))
from refresh_pdf import extract_pdf, parse_record, find_pdfs
from html_to_txt import extract_Q  # noqa (일관성/향후용)

HTML = {"ko": "index.html", "en": "en.html", "cn": "cn.html", "vn": "vn.html"}


_PUNCT = [("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'),
          ("–", "-"), ("—", "-"), ("\xa0", " ")]


def same(a, b):
    """공백·유사 문장부호 정규화 후 동일하면 True — 미세차는 변경으로 보지 않음(불필요 갱신 방지)."""
    def _n(s):
        s = s or ""
        for x, y in _PUNCT:
            s = s.replace(x, y)
        return "".join(s.split())
    return _n(a) == _n(b)


def apply(dry_run=False):
    pdfs = find_pdfs(PROJ / "원본_PDF")
    for lang in ["ko", "en", "cn", "vn"]:
        if lang not in pdfs:
            print(f"{lang}: PDF 없음 — skip")
            continue
        extracted = extract_pdf(pdfs[lang], lang)
        path = PROJ / HTML[lang]
        html = path.read_text(encoding="utf-8")
        i = html.find("const Q=")
        if i < 0:
            i = html.find("const Q =")
        s = html.find("[", i)
        Q, end = JSONDecoder().raw_decode(html[s:])
        by_n = {q["n"]: q for q in Q}
        pdf_nums = set(extracted)

        upd = 0
        add = 0
        warn = []   # 보기 개수 변경(c 미갱신, 수동 확인)
        kept = []   # PDF 추출 실패/부재 → 원본 보존(데이터 손실 방지)
        new_Q = []
        for n in sorted(set(by_n) | pdf_nums):
            pr = parse_record(extracted[n]) if n in extracted else None
            if pr and n in by_n:
                q = by_n[n]
                ch = False
                if not same(pr["b"], q.get("b")):
                    q["b"] = pr["b"]; ch = True
                if len(pr["c"]) == len(q.get("c", [])):
                    if not all(same(x, y) for x, y in zip(pr["c"], q.get("c", []))):
                        q["c"] = pr["c"]; ch = True
                else:
                    warn.append(n)  # 보기 개수 변경 → c는 수동 확인(자동 갱신 안 함)
                if str(pr["a"]) != str(q.get("a", "")):
                    q["a"] = pr["a"]; ch = True
                if lang == "ko" and pr.get("e") and not same(pr["e"], q.get("e")):
                    q["e"] = pr["e"]; ch = True
                new_Q.append(q)
                if ch:
                    upd += 1
            elif pr:  # 신규(PDF에만 있고 파싱 성공)
                nq = {"n": n, "b": pr["b"], "c": pr["c"], "a": pr["a"],
                      "imgs": [], "t": "동영상형" if n >= 966 else "문장형"}
                if lang == "ko":
                    nq["e"] = pr["e"]
                new_Q.append(nq)
                add += 1
            elif n in by_n:  # PDF 추출 실패/부재 → 원본 그대로 보존(삭제 안 함)
                new_Q.append(by_n[n])
                kept.append(n)
            # else: PDF에 있으나 파싱 실패 + 기존에도 없음 → 건너뜀

        new_Q.sort(key=lambda q: q["n"])
        print(f"{lang}: 갱신 {upd}, 신규 {add}, 보존(추출실패/부재) {len(kept)}{' '+str(kept) if kept else ''}, "
              f"보기수변경 {len(warn)}")

        if not dry_run:
            new_arr = json.dumps(new_Q, ensure_ascii=False, separators=(",", ":"))
            html = html[:s] + new_arr + html[s + end:]
            path.write_text(html, encoding="utf-8")

    if dry_run:
        print("(dry-run — 파일 미수정)")
    else:
        print("반영 완료. 다음: py scripts/repair_ko.py, py scripts/match_images.py")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="파일 수정 없이 결과만")
    args = ap.parse_args()
    apply(args.dry_run)
