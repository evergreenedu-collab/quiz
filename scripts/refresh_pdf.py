"""
외국인 학과시험 AI튜터 — PDF → HTML 자동 갱신 스크립트

사용법 (PowerShell):
    cd "c:\\Users\\user\\projects\\외국인-학과시험-AI튜터"
    python scripts/refresh_pdf.py [--dry-run] [--lang ko,en,cn,vn]

옵션:
    --dry-run           실제 HTML을 수정하지 않고 추출 결과만 보고
    --lang              특정 언어만 처리 (기본: 모두)

요구사항:
    pip install pymupdf

작동 흐름:
    1. 원본_PDF/ 의 4개 PDF 자동 식별
    2. 각 PDF에서 1000개 문항 자동 파싱
    3. 현재 HTML 데이터와 비교 (누락·차이 식별)
    4. 결과 리포트 출력 (사용자 검증 후 다음 단계 결정)

스크립트가 직접 HTML을 덮어쓰지 않습니다. 추출본을
임시 JSON 으로 저장하고, Claude(또는 사용자)가 검토 후
별도 단계로 HTML 갱신을 진행합니다.
"""

import fitz  # PyMuPDF
import re
import json
import os
import argparse
import sys
from pathlib import Path


# ----- PDF 식별 -----

def find_pdfs(pdf_dir):
    """원본_PDF/ 폴더에서 4개 언어 PDF 자동 식별 (파일명 패턴 매칭)"""
    candidates = list(Path(pdf_dir).glob("*.pdf"))
    found = {}
    for p in candidates:
        name = p.name
        if "한국어" in name or "Korean" in name:
            found["ko"] = str(p)
        elif "English" in name or "영어" in name:
            found["en"] = str(p)
        elif "Chinese" in name or "中文" in name or "중국어" in name:
            found["cn"] = str(p)
        elif "Vietnamese" in name or "베트남" in name or "Tieng" in name.lower():
            found["vn"] = str(p)
    return found


# ----- 언어별 라벨 -----

ANSWER_LABELS = {
    "ko": r"■\s*정답",
    "en": r"■\s*Answer",
    "cn": r"■\s*正确答案",
    "vn": r"■\s*Đáp\s*án",
}
EXPLANATION_LABELS = {
    "ko": r"■\s*해설",
    "en": r"■\s*Explanation|■\s*Description",
    "cn": r"■\s*解析|■\s*解释",
    "vn": r"■\s*Giải\s*thích|■\s*Giải\s*đáp",
}


# ----- 추출 알고리즘 (PR #4·#6 작업의 정제 버전) -----

PRIMARY_Q_PATTERN = re.compile(r"(?:\n|\A)\s*(\d+)\.(?!\d)")
CN_FALLBACK_Q_PATTERN = re.compile(r"(?:\n|\A)\s*(\d+)\s+(?=[一-鿿])")


def extract_pdf(pdf_path, lang):
    """PDF에서 문항 1000개 추출 → {n: {body, a, e}}"""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    doc.close()

    ans_label = ANSWER_LABELS[lang]
    exp_label = EXPLANATION_LABELS[lang]
    ans_positions = [m.start() for m in re.finditer(ans_label, text)]

    extracted = {}
    for i, ap in enumerate(ans_positions):
        prev_ap = ans_positions[i - 1] if i > 0 else 0
        region = text[prev_ap:ap]

        # 1순위: 점 패턴
        last_qm = None
        for qm in PRIMARY_Q_PATTERN.finditer(region):
            last_qm = qm

        # 2순위 (cn 한정): 점 없는 fallback
        if not last_qm and lang == "cn":
            for qm in CN_FALLBACK_Q_PATTERN.finditer(region):
                last_qm = qm

        if not last_qm:
            continue

        num = int(last_qm.group(1))
        body_text = text[prev_ap + last_qm.start() : ap].strip()

        next_ap = ans_positions[i + 1] if i + 1 < len(ans_positions) else len(text)
        after = text[ap:next_ap]

        am = re.search(ans_label + r"[\s:：]*([^\n■]+)", after)
        answer = am.group(1).strip() if am else ""
        # 베트남어는 'đúng :' 접두사 제거
        if lang == "vn":
            answer = re.sub(r"^\s*đúng\s*[:：]\s*", "", answer)

        em = re.search(exp_label + r"[\s:：]*(.+?)(?=$|\Z)", after, re.DOTALL)
        expl = em.group(1).strip() if em else ""

        record = {"body": body_text, "a": answer, "e": expl}
        if num in extracted:
            if len(body_text) > len(extracted[num]["body"]):
                extracted[num] = record
        else:
            extracted[num] = record

    return extracted


# ----- HTML 데이터 비교 -----

def get_html_question_nums(html_path):
    """HTML 파일에서 문항 번호 집합 추출"""
    with open(html_path, encoding="utf-8") as f:
        html = f.read()
    return set(int(m.group(1)) for m in re.finditer(r'"n":(\d+),', html))


# ----- 본문·선택지·t 파싱 (HTML 객체 변환용) -----

def parse_record(rec):
    """PDF record → HTML 객체 형식 (b, c, a, e)"""
    body = rec["body"]
    # 선택지 마커 자동 감지
    pos1 = next((body.find(c) for c in "①②③④" if body.find(c) >= 0), -1)
    pos2 = next((body.find(c) for c in "➀➁➂➃" if body.find(c) >= 0), -1)
    valid = [p for p in (pos1, pos2) if p >= 0]
    if not valid:
        return None
    first = min(valid)
    set_used = "①②③④" if first == pos1 else "➀➁➂➃"

    head = body[:first].strip()
    choices_text = body[first:]

    qm = re.match(r"^\s*\d+\.?\s*(.*)", head, re.DOTALL)
    question = (qm.group(1) if qm else head).strip()
    question = re.sub(r"\s+", " ", question)

    parts = re.split("[" + set_used + "]", choices_text)
    if len(parts) < 5:
        return None
    choices = [re.sub(r"\s+", " ", p.strip()) for p in parts[1:5]]

    answer = re.sub(r"^\s*[:：]\s*", "", rec["a"].strip())
    answer = re.sub(r"\s+", " ", answer).strip()

    expl = rec["e"]
    next_q = re.search(r"\n\s*\d+\.\s", expl)
    if next_q:
        expl = expl[: next_q.start()]
    expl = re.sub(r"\s+", " ", expl).strip()

    return {"b": question, "c": choices, "a": answer, "e": expl}


# ----- 메인 흐름 -----

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="추출만 하고 저장 안 함")
    parser.add_argument("--lang", default="ko,en,cn,vn", help="처리 언어 (콤마)")
    parser.add_argument("--out-dir", default=None, help="추출 JSON 저장 폴더 (기본: %TEMP%/quiz_extract)")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent.resolve()
    pdf_dir = project_root / "원본_PDF"
    html_files = {
        "ko": project_root / "index.html",
        "en": project_root / "en.html",
        "cn": project_root / "cn.html",
        "vn": project_root / "vn.html",
    }

    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        out_dir = Path(os.environ.get("TEMP", "/tmp")) / "quiz_extract"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("외국인 학과시험 AI튜터 — PDF → HTML 갱신 스크립트")
    print("=" * 70)

    # 1. PDF 식별
    pdfs = find_pdfs(pdf_dir)
    print(f"\n[1/3] 원본_PDF/ 에서 PDF 자동 식별:")
    for lang in ("ko", "en", "cn", "vn"):
        if lang in pdfs:
            print(f"  ✅ {lang}: {Path(pdfs[lang]).name}")
        else:
            print(f"  ❌ {lang}: 못 찾음 (파일명에 '한국어'/'English'/'Chinese'/'Vietnamese' 포함되어야 함)")

    target_langs = [l for l in args.lang.split(",") if l in pdfs]
    if not target_langs:
        print("\n처리할 언어가 없어 종료합니다.")
        sys.exit(1)

    # 2. PDF 추출
    print(f"\n[2/3] PDF 1000개 추출 (언어: {', '.join(target_langs)}):")
    all_extracted = {}
    for lang in target_langs:
        extracted = extract_pdf(pdfs[lang], lang)
        all_extracted[lang] = extracted
        nums = set(extracted.keys())
        missing = sorted(set(range(1, 1001)) - nums)
        status = "✅" if len(missing) == 0 else "⚠️"
        print(f"  {status} {lang}: {len(nums)}개 / 누락 {len(missing)}개 {missing if missing else ''}")

        if not args.dry_run:
            out_path = out_dir / f"{lang}_extracted.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(extracted, f, ensure_ascii=False)

    # 3. HTML 비교
    print(f"\n[3/3] PDF vs 현재 HTML 비교:")
    summary = {}
    for lang in target_langs:
        if not html_files[lang].exists():
            print(f"  {lang}: HTML 파일 없음 - skip")
            continue
        html_nums = get_html_question_nums(html_files[lang])
        pdf_nums = set(all_extracted[lang].keys())

        pdf_only = sorted(pdf_nums - html_nums)
        html_only = sorted(html_nums - pdf_nums)

        summary[lang] = {
            "html_count": len(html_nums),
            "pdf_count": len(pdf_nums),
            "add_to_html": pdf_only,
            "html_orphan": html_only,
        }
        print(f"  --- {lang} ---")
        print(f"    HTML: {len(html_nums)}개 / PDF: {len(pdf_nums)}개")
        if pdf_only:
            print(f"    ⚠️ PDF에만 있음 (HTML에 추가 필요): {pdf_only}")
        if html_only:
            print(f"    ⚠️ HTML에만 있음 (의심 - PDF 갱신 검토): {html_only}")
        if not pdf_only and not html_only:
            print(f"    ✅ 일치 (변경 불필요)")

    if not args.dry_run:
        with open(out_dir / "compare_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\n결과 저장: {out_dir}")

    print("\n" + "=" * 70)
    print("다음 단계:")
    print("  1. 위 결과를 사용자분과 검토")
    print("  2. PDF에만 있는 번호 = HTML에 추가할 객체 (parse_record 활용)")
    print("  3. HTML에만 있는 번호 = 의심 (PDF 갱신·새 폐기 번호 가능성)")
    print("  4. 이미지 매칭은 scripts/match_images.py 별도 실행")
    print("  5. UPDATE_GUIDE.md 의 후속 절차 따라 작업")
    print("=" * 70)


if __name__ == "__main__":
    main()
