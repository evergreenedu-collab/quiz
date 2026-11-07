# -*- coding: utf-8 -*-
"""몽골어 학습 페이지(mn.html) 생성기.

흐름: 몽골어 PDF 추출 → ①~⑤ 보기 분리 → 한국어(index.html)의 imgs·t 결합
      → 무결성 검사 → translations/risky_mn.json 기록
      → vn.html 템플릿의 UI 문구를 몽골어로 치환해 mn.html 생성 + manifest_mn.json
      → translations/expl_mn.json 이 있으면 해설(e) 주입 (RISKY·무해설은 폴백)

사용법: py scripts/build_mn_page.py [--dry-run]
"""
import sys
import json
import re
import argparse
from json import JSONDecoder
from pathlib import Path

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / "scripts"))
from html_to_txt import extract_Q
from refresh_pdf import find_pdfs, extract_pdf
from pdfq import parse_body, parse_answer

T = PROJ / "translations"


def parse_choices(rec):
    """PDF record → b, c(4~5개), a (공통 추출기 pdfq 사용)."""
    b, c, err = parse_body(rec["body"], "mn")
    if err:
        return None, err
    a, err = parse_answer(rec["a"], len(c))
    if err:
        return None, err
    return {"b": b, "c": c, "a": a}, None


def digit_set(a):
    return tuple(sorted(c for c in str(a) if c.isdigit()))


def digit_seq(q):
    return re.findall(r"\d+", q["b"] + " " + " ".join(q["c"]))


def build_records(pdf_path, ko):
    extracted = extract_pdf(pdf_path, "mn")
    extra = sorted(set(extracted) - set(range(1, 1001)))
    if extra:
        print(f"   ⚠️ 1~1000 밖 번호 추출됨(무시): {extra}")
    problems = {}
    Q = []
    for n in range(1, 1001):
        reasons = []
        rec = extracted.get(n)
        if not rec:
            problems[n] = ["PDF에 문항 없음"]
            continue
        parsed, err = parse_choices(rec)
        if err:
            problems[n] = [err]
            continue
        kq = ko[n]
        if not parsed["b"]:
            reasons.append("본문 빈값")
        if any(not c for c in parsed["c"]):
            reasons.append("보기 빈값")
        ans_nums = [int(x) for x in parsed["a"].split(", ")]
        if any(x < 1 or x > len(parsed["c"]) for x in ans_nums):
            reasons.append(f"정답 범위 밖 {parsed['a']} / 보기 {len(parsed['c'])}")
        if digit_set(parsed["a"]) != digit_set(kq["a"]):
            reasons.append(f"정답불일치 mn={parsed['a']} ko={kq['a']}")
        if len(parsed["c"]) != len(kq["c"]):
            reasons.append(f"보기수({len(parsed['c'])}≠{len(kq['c'])})")
        if re.search(r"[가-힣]", parsed["b"] + "".join(parsed["c"])):
            reasons.append("한글 잔존")
        q = {"n": n, "b": parsed["b"], "c": parsed["c"], "a": parsed["a"],
             "imgs": list(kq.get("imgs") or []), "t": kq["t"]}
        Q.append(q)
        if reasons:
            problems[n] = reasons
    return Q, problems


REPLACEMENTS = [
    ('<html lang="vi">', '<html lang="mn">'),
    ('href="manifest_vn.json"', 'href="manifest_mn.json"'),
    ('content="Ôn thi GPLX"', 'content="Жолооны шалгалт"'),
    ('<title>🚗 AI Luyện thi lý thuyết lái xe</title>', '<title>🚗 Жолооны онолын шалгалтын AI багш</title>'),
    ('css2?family=Noto+Sans+KR:wght@400;500;600;700;800;900&display=swap',
     'css2?family=Noto+Sans:wght@400;500;600;700;800;900&family=Noto+Sans+KR:wght@400;500;600;700;800;900&display=swap'),
    ("body{font-family:'Noto Sans KR',sans-serif;", "body{font-family:'Noto Sans','Noto Sans KR',sans-serif;"),
    ('aria-label="AI Luyện thi lý thuyết lái xe, đang tải"', 'aria-label="Жолооны онолын шалгалтын AI багш, ачааллаж байна"'),
    ('<a href="vn.html" class="lg on">🇻🇳 Tiếng Việt</a><a href="mn.html" class="lg">🇲🇳 Монгол</a></div>',
     '<a href="vn.html" class="lg">🇻🇳 Tiếng Việt</a><a href="mn.html" class="lg on">🇲🇳 Монгол</a></div>'),
    ('<span class="badge">Có hiệu lực 2026.3.9</span>', '<span class="badge">2026.3.9-өөс хүчинтэй</span>'),
    ('placeholder="Tìm theo số hoặc từ khóa"><button onclick="go()">Tìm</button>',
     'placeholder="Дугаар эсвэл түлхүүр үгээр хайх"><button onclick="go()">Хайх</button>'),
    ('<a class="chip chip-sib" href="textbook_vn.html">📘 Xem giáo trình</a>', '<a class="chip chip-sib" href="textbook_mn.html">📘 Сурах бичиг үзэх</a>'),
    ('aria-label="Hỏi gia sư AI, mở trong cửa sổ mới">🤖 Hỏi gia sư AI</a>',
     'aria-label="AI багшаас асуух, шинэ цонхонд нээгдэнэ">🤖 AI багшаас асуух</a>'),
    ('<a class="diag-banner" href="diagnostic.html?lang=vn">📊 Đánh giá hiệu quả học tập <span>Đo tiến bộ qua chẩn đoán trước/sau</span></a>', '<a class="diag-banner" href="diagnostic.html?lang=mn">📊 Суралцахуйн үр дүнгийн үнэлгээ <span>Урьдчилсан·дараах оношилгоогоор ахицаа хэмжинэ</span></a>'),
    ('Tất cả<span class="num">1000</span>', 'Бүгд<span class="num">1000</span>'),
    ('Văn bản<span class="num">', 'Текст<span class="num">'),
    ('Ảnh<span class="num">', 'Зураг<span class="num">'),
    ('Biển báo<span class="num">', 'Тэмдэг<span class="num">'),
    ('Video<span class="num">', 'Видео<span class="num">'),
    ('data-r="all">Tất cả</button>', 'data-r="all">Бүгд</button>'),
    ('© KoRoad Ban Giáo dục', '© KoRoad Боловсролын газар'),
    ('const TN={"문장형": "📝 Văn bản", "사진형": "📷 Ảnh", "표지판형": "🚸 Biển báo", "동영상형": "🎬 Video"};',
     'const TN={"문장형": "📝 Текст", "사진형": "📷 Зураг", "표지판형": "🚸 Тэмдэг", "동영상형": "🎬 Видео"};'),
    ('const BTN_SHOW="Xem đáp án",BTN_HIDE="Ẩn đáp án";', 'const BTN_SHOW="Хариулт харах",BTN_HIDE="Хариулт нуух";'),
    ('const VID_MSG="🎬 Câu hỏi này cần xem video.",NOT_FOUND=" không tìm thấy.",LABEL_ANS="Đáp án";',
     'const VID_MSG="🎬 Энэ асуултад видео үзэх шаардлагатай.",NOT_FOUND=" дугаартай асуулт олдсонгүй.",LABEL_ANS="Хариулт";'),
    ('const LABEL_EXPL="Giải thích",LABEL_ASK_AI="🤖 Hỏi gia sư AI",PREP_MSG="Giải thích đang được chuẩn bị. ",'
     'AI_NOTE="※ Câu trả lời của AI chỉ mang tính tham khảo, có thể không phải là giải thích chính thức.",'
     'LABEL_QHDR="Câu hỏi thi bằng lái số ",ASK_PROMPT="Vui lòng giải thích đáp án của câu hỏi này.",LABEL_COPIED="Đã sao chép! Đang mở gia sư AI";',
     'const LABEL_EXPL="Тайлбар",LABEL_ASK_AI="🤖 AI багшаас асуух",PREP_MSG="Тайлбар бэлтгэгдэж байна. ",'
     'AI_NOTE="※ AI-ийн хариулт зөвхөн лавлагааны зориулалттай бөгөөд албан ёсны тайлбар биш байж болно.",'
     'LABEL_QHDR="Жолооны шалгалтын асуулт №",ASK_PROMPT="Энэ асуултын хариултыг тайлбарлаж өгнө үү.",LABEL_COPIED="Хуулагдлаа! AI багш нээгдэж байна",'
     'EXPL_NOTE="※ Энэ тайлбар нь солонгос эх бичвэрийн AI орчуулга бөгөөд зөвхөн лавлагааны зориулалттай.";'),
    ("'</b> câu, hiển thị <b>'+R+'</b>'", "'</b> асуулт, <b>'+R+'</b> харуулж байна'"),
    ('<div class="ev">${escHtml(q.e)}</div></div>`;', '<div class="ev">${escHtml(q.e)}</div><div class="ai-note">${EXPL_NOTE}</div></div>`;'),
    ("var LANG='vn';", "var LANG='mn';"),
    ("inapp:'Vui lòng mở trang này bằng Safari hoặc Chrome từ menu rồi thử lại.'}\n};",
     "inapp:'Vui lòng mở trang này bằng Safari hoặc Chrome từ menu rồi thử lại.'},\n"
     "mn:{txt:'Хурдан нээхийн тулд Нүүр дэлгэцэд нэмнэ үү',btn:'Нэмэх',st:'Нүүр дэлгэцэд нэмэх арга',"
     "s1:'Доорх Хуваалцах товчийг дарна уу',s2:'“Нүүр дэлгэцэд нэмэх”-ийг сонгоно уу',close:'Хаах',"
     "inapp:'Цэснээс Safari эсвэл Chrome-оор энэ хуудсыг нээгээд дахин оролдоно уу.'}\n};"),
    ("'Không tìm thấy kết quả cho <b>\"'+v+'\"</b>'", "'Хайлтын үр дүн олдсонгүй: <b>\"'+v+'\"</b>'"),
]


def render_html(template_html, Q):
    i = template_html.find("const Q=")
    s = template_html.find("[", i)
    _, end = JSONDecoder().raw_decode(template_html[s:])
    head, tail = template_html[:s], template_html[s + end:]
    shell = head + "__Q_ARRAY__" + tail
    for must in ('Tiếng Việt · Монгол</div>', 'gpt-guide.js?v=3'):
        if must not in shell:
            raise SystemExit(f'템플릿(vn.html)에 기대 문자열 없음: {must}')
    for old, new in REPLACEMENTS:
        cnt = shell.count(old)
        if cnt != 1:
            raise SystemExit(f"템플릿 치환 실패 (발견 {cnt}회): {old[:60]!r}")
        shell = shell.replace(old, new)
    ui_part = shell.split("var I18N=")[0].replace("Tiếng Việt", "")
    leftovers = sorted(set(re.findall(r"[ăâđêôơưĂÂĐÊÔƠƯạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]", ui_part)))
    if leftovers:
        raise SystemExit(f"베트남어 잔존 의심 문자: {leftovers}")
    arr = json.dumps(Q, ensure_ascii=False, separators=(",", ":"))
    return shell.replace("__Q_ARRAY__", arr, 1) if shell.count("const Q=__Q_ARRAY__") == 1 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pdfs = find_pdfs(PROJ / "원본_PDF")
    if "mn" not in pdfs:
        raise SystemExit("원본_PDF/ 에 Mongolian PDF 없음")
    ko = {q["n"]: q for q in extract_Q(str(PROJ / "index.html"))}
    Q, problems = build_records(pdfs["mn"], ko)
    print(f"[1] 추출 {len(Q)}문항, 문제 {len(problems)}건")
    for n in sorted(problems):
        print(f"   Q{n}: {', '.join(problems[n])}")

    base = json.load(open(T / "risky_questions.json", encoding="utf-8"))["risky"]
    risky = {str(n): list(r) for n, r in base.items()}
    for n, r in problems.items():
        risky[str(n)] = risky.get(str(n), []) + [f"mn:{x}" for x in r]

    shifted = [q["n"] for q in Q if digit_seq(q) != digit_seq(ko[q["n"]])]
    print(f"[2] 숫자 시퀀스 ko≠mn 문항(검토용, 차단 아님): {len(shifted)}개 {shifted[:60]}")
    five = sum(1 for q in Q if len(q["c"]) == 5)
    multi = sum(1 for q in Q if "," in q["a"])
    print(f"[3] 5지선다 {five}, 복수정답 {multi}, 이미지문항 {sum(1 for q in Q if q['imgs'])}, "
          f"이미지참조 {sum(len(q['imgs']) for q in Q)}, 동영상형 {sum(1 for q in Q if q['t']=='동영상형')}")
    print(f"[4] RISKY {len(risky)} = 기존 {len(base)} + mn 추가 {len(set(risky)-set(base))}")

    MANUAL_FALLBACK = {}
    for n, why in MANUAL_FALLBACK.items():
        risky[n] = risky.get(n, []) + [f"mn:{why}"]
    risky = dict(sorted(risky.items(), key=lambda kv: int(kv[0])))
    payload = {"safe_count": 1000 - len(risky), "risky_count": len(risky), "risky": risky}
    mn_fallback = {n for n, r in risky.items() if any(x.startswith("mn:") for x in r)}
    payload["mn_fallback"] = sorted(mn_fallback, key=int)
    print(f"    몽골어 해설 폴백 대상(mn 사유 있음): {sorted(mn_fallback, key=int)}")

    expl_path = T / "expl_mn.json"
    injected = 0
    if expl_path.exists():
        trans = json.load(open(expl_path, encoding="utf-8"))
        for q in Q:
            n = str(q["n"])
            if n in mn_fallback:
                continue
            if n in trans and trans[n].strip():
                q["e"] = trans[n].strip()
                injected += 1
        print(f"[5] 해설 주입 {injected}개 (폴백 {len(Q)-injected})")
    else:
        print("[5] translations/expl_mn.json 없음 → 전 문항 해설 폴백")

    fatal = {n: r for n, r in problems.items() if any(("문항 없음" in x) or ("마커" in x) or ("정답 형식" in x) or ("정답 중복" in x) or ("빈값" in x) or ("정답불일치" in x) or ("한글 잔존" in x) or ("정답 범위" in x) for x in r)}
    if len(Q) != 1000 or fatal:
        raise SystemExit(f"중단: 추출 {len(Q)}문항, 치명 문제 {fatal} — mn.html 을 생성하지 않음")
    if args.dry_run:
        print("dry-run: 파일 쓰지 않음")
        return
    (T / "risky_mn.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    html = render_html((PROJ / "vn.html").read_text(encoding="utf-8"), Q)
    if html is None:
        raise SystemExit("템플릿의 const Q 자리 표시자 확인 실패")
    (PROJ / "mn.html").write_text(html, encoding="utf-8")
    m = json.load(open(PROJ / "manifest_vn.json", encoding="utf-8"))
    m.update({"name": "Жолооны онолын шалгалтын AI багш", "short_name": "Жолооны шалгалт",
              "lang": "mn", "start_url": "./mn.html"})
    (PROJ / "manifest_mn.json").write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[6] mn.html ({len(html):,}자), manifest_mn.json, translations/risky_mn.json 기록")


if __name__ == "__main__":
    main()
