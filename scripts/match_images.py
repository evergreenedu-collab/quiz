"""
외국인 학과시험 AI튜터 — 이미지 위치 매칭·추출 스크립트

PDF 페이지 안에서 어떤 이미지가 어느 문항에 속하는지 자동 판별 + 저장.

사용법 (PowerShell):
    cd "c:\\Users\\user\\projects\\외국인-학과시험-AI튜터"
    python scripts/match_images.py --pdf ko --num 842 --num 955 [--out images/]

옵션:
    --pdf      추출할 PDF 언어 (기본: ko - 한국어 PDF가 가장 풍부)
    --num      문항 번호 (반복 가능, 다수 처리)
    --out      저장 폴더 (기본: images/)
    --dry-run  매칭 결과만 보고, 저장 안 함

알고리즘:
    1. 페이지의 텍스트 블록을 분석해 각 문항 시작 y좌표 식별
    2. 페이지의 모든 이미지 + y좌표 추출
    3. 이미지 y중심값이 어느 문항 y범위에 들어가는지로 자동 매칭
    4. 매칭된 이미지를 적절한 파일명(qNNN.jpg/png)으로 저장

사용자 검증:
    이미지 사이즈 정보(예: 사진형은 보통 큼, 표지판은 100x100 가까움)와
    위치(위/중간/아래)를 출력해 사용자분이 PDF로 검증할 수 있게 함.

요구사항:
    pip install pymupdf
"""

import fitz
import re
import os
import argparse
from pathlib import Path


PDF_NAMES = {
    "ko": "한국어",
    "en": "English",
    "cn": "Chinese",
    "vn": "Vietnamese",
}


def find_pdf(pdf_dir, lang):
    keyword = PDF_NAMES.get(lang, lang)
    for p in Path(pdf_dir).glob("*.pdf"):
        if keyword in p.name:
            return p
    return None


def find_question_page(doc, target_num):
    """문항 번호가 있는 페이지 찾기"""
    for page_num in range(doc.page_count):
        text = doc[page_num].get_text()
        if re.search(r"(?:\n|\A)\s*" + str(target_num) + r"\.", text):
            return page_num
        # cn 같이 점 없는 케이스
        if re.search(r"(?:\n|\A)\s*" + str(target_num) + r"\s+(?=[一-鿿])", text):
            return page_num
    return None


def match_images_in_page(page, target_num):
    """페이지 안 이미지를 문항에 매칭. 대상 문항의 이미지 정보 반환."""
    blocks = page.get_text("blocks")
    q_pos = {}
    for b in blocks:
        if len(b) < 5:
            continue
        text = b[4]
        m = re.match(r"^\s*(\d+)\.\s", text)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 1000:
                q_pos[n] = (b[1], b[3])  # y_top, y_bottom

    sorted_qs = sorted(q_pos.items())
    images = page.get_images(full=True)

    matched = []
    for idx, img in enumerate(images):
        xref = img[0]
        rects = page.get_image_rects(xref)
        if not rects:
            continue
        rect = rects[0]
        img_yc = (rect.y0 + rect.y1) / 2

        owner = None
        position_label = "?"
        for i, (n, _) in enumerate(sorted_qs):
            this_y = sorted_qs[i][1][0]
            next_y = sorted_qs[i + 1][1][0] if i + 1 < len(sorted_qs) else 1e9
            if this_y <= img_yc < next_y:
                owner = n
                # 페이지 내 위치 분류 (위/중/아래)
                if i == 0:
                    position_label = "위"
                elif i == len(sorted_qs) - 1:
                    position_label = "아래"
                else:
                    position_label = "중간"
                break
        if owner is None and sorted_qs and img_yc < sorted_qs[0][1][0]:
            owner = sorted_qs[0][0]
            position_label = "맨위"

        if owner == target_num:
            matched.append({
                "idx": idx,
                "xref": xref,
                "width": img[2],
                "height": img[3],
                "y0": rect.y0,
                "y1": rect.y1,
                "position": position_label,
            })

    return matched, sorted_qs


def save_image(doc, xref, out_path, force_rgb=True):
    pix = fitz.Pixmap(doc, xref)
    if force_rgb and pix.colorspace and pix.colorspace.n >= 4:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    pix.save(str(out_path))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", default="ko", help="언어 (ko/en/cn/vn, 기본: ko)")
    parser.add_argument("--num", type=int, action="append", required=True, help="문항 번호 (반복 가능)")
    parser.add_argument("--out", default=None, help="저장 폴더 (기본: 프로젝트의 images/)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent.resolve()
    pdf_dir = project_root / "원본_PDF"
    out_dir = Path(args.out) if args.out else project_root / "images"
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = find_pdf(pdf_dir, args.pdf)
    if not pdf_path:
        print(f"❌ {args.pdf} 언어 PDF 못 찾음 (원본_PDF/ 안)")
        return

    print(f"PDF: {pdf_path.name}")
    doc = fitz.open(pdf_path)

    for target_num in args.num:
        print(f"\n=== Q{target_num} 매칭 ===")
        page_num = find_question_page(doc, target_num)
        if page_num is None:
            print(f"  ❌ Q{target_num} 페이지 못 찾음")
            continue
        print(f"  페이지: {page_num + 1}")

        page = doc[page_num]
        matched, sorted_qs = match_images_in_page(page, target_num)
        print(f"  페이지 내 문항: {[n for n, _ in sorted_qs]}")

        if not matched:
            print(f"  ⚠️ Q{target_num}에 매칭된 이미지 없음")
            continue

        for m in matched:
            ext = "jpg" if m["width"] > 500 else "png"
            print(f"    이미지 {m['idx']}: {m['width']}x{m['height']}, "
                  f"위치 {m['position']}(y={m['y0']:.0f}~{m['y1']:.0f}) → 저장 후보 q{target_num}.{ext}")

            if not args.dry_run:
                # 한 문항에 이미지 여러개면 첫 번째만 (대표). 필요시 인덱스 추가.
                if matched.index(m) == 0:
                    out_path = out_dir / f"q{target_num}.{ext}"
                else:
                    out_path = out_dir / f"q{target_num}_{m['idx']}.{ext}"
                save_image(doc, m["xref"], out_path)
                size_kb = os.path.getsize(out_path) / 1024
                print(f"      ✅ 저장: {out_path} ({size_kb:.1f}KB)")

    doc.close()
    print("\n완료.")


if __name__ == "__main__":
    main()
