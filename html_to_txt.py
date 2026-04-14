"""HTML 문제은행 → GPTs용 txt 변환 스크립트."""
import json
import os
import re
from collections import Counter

REPO = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(REPO, "gpt_files")
os.makedirs(OUT_DIR, exist_ok=True)

TARGETS = [
    ("index.html", "quiz_bank_ko.txt"),
    ("en.html",    "quiz_bank_en.txt"),
    ("cn.html",    "quiz_bank_cn.txt"),
    ("vn.html",    "quiz_bank_vn.txt"),
]

CIRCLED = ["①", "②", "③", "④", "⑤"]
IMG_URL_BASE = "https://raw.githubusercontent.com/evergreenedu-collab/quiz/main/images/"


def extract_Q(html_path: str):
    with open(html_path, "r", encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"const\s+Q\s*=\s*\[", text)
    if not m:
        raise ValueError(f"const Q 배열을 찾지 못함: {html_path}")
    start = m.end() - 1
    depth = 0; in_str = False; esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
        else:
            if ch == '"': in_str = True
            elif ch == "[": depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start:i + 1])
    raise ValueError("배열 종료를 찾지 못함")


def format_question(q):
    lines = [f"===== 문제 {q['n']} =====",
             f"유형: {q['t']}",
             f"질문: {q['b'].strip()}"]
    imgs = q.get("imgs") or []
    if imgs:
        urls = [IMG_URL_BASE + im for im in imgs]
        lines.append(f"이미지: {' '.join(urls)}")
    for idx, ch in enumerate(q.get("c", [])):
        mark = CIRCLED[idx] if idx < len(CIRCLED) else f"({idx+1})"
        lines.append(f"{mark} {ch.strip()}")
    lines.append(f"정답: {q.get('a', '').strip()}")
    expl = (q.get("e") or "").strip()
    if expl:
        lines.append(f"해설: {expl}")
    return "\n".join(lines)


def convert(html_path, out_path):
    Q = extract_Q(html_path)
    Q.sort(key=lambda x: x["n"])
    body = "\n\n".join(format_question(q) for q in Q) + "\n"
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    types = Counter(q["t"] for q in Q)
    print(f"{os.path.basename(html_path)}: {len(Q)} {dict(types)}")


def main():
    for html_name, txt_name in TARGETS:
        convert(os.path.join(REPO, html_name), os.path.join(OUT_DIR, txt_name))


if __name__ == "__main__":
    main()
