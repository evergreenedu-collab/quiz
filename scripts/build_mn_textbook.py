# -*- coding: utf-8 -*-
"""몽골어 교재(textbook_mn.html) 조립기.

입력: translations/_tb/ko_pre.html(본문 앞부분, 한국어) + mn_ch1~10.html(번역 조각) + ko_tail.html(스크립트)
      + textbook.html 의 <head>
처리: head/pre/tail 의 UI 문구·링크를 몽골어/mn 경로로 치환(각 치환은 정확히 1회), 조각 결합,
      원본 textbook.html 과 태그·속성 시퀀스 동일성 검증, 괄호 밖 한글 0 검증.
사용법: py scripts/build_mn_textbook.py
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

PROJ = Path(__file__).parent.parent
TB = PROJ / "translations" / "_tb"


class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.seq = []

    @staticmethod
    def norm(t, a):
        out = []
        for k, v in a:
            if t == "a" and k == "href":
                continue  # 언어별 링크 차이 허용 (mn.html 등)
            if k in ("aria-label", "alt", "title"):
                continue  # 사람이 읽는 속성은 번역 허용
            if k == "class" and v:
                v = " ".join(x for x in v.split() if x != "on")  # 언어 스위처 활성 표시 차이 허용
            out.append((k, v))
        return tuple(sorted(out))

    def handle_starttag(self, t, a):
        self.seq.append(("S", t, self.norm(t, a)))

    def handle_startendtag(self, t, a):
        self.seq.append(("SE", t, tuple(sorted(a))))

    def handle_endtag(self, t):
        self.seq.append(("E", t))


def seq_of(html):
    p = P()
    p.feed(html)
    return p.seq


def rep(s, pairs, where):
    for old, new in pairs:
        c = s.count(old)
        if c != 1:
            raise SystemExit(f"[{where}] 치환 실패({c}회): {old[:70]!r}")
        s = s.replace(old, new)
    return s


HEAD_PAIRS = [
    ('<html lang="ko">', '<html lang="mn">'),
    ('<link rel="manifest" href="manifest.json">', '<link rel="manifest" href="manifest_mn.json">'),
    ('<meta name="apple-mobile-web-app-title" content="면허시험">', '<meta name="apple-mobile-web-app-title" content="Жолооны шалгалт">'),
    ('<title>외국인 운전면허 학과시험 교재</title>', '<title>Жолооны онолын шалгалтын сурах бичиг — Гадаад иргэдэд</title>'),
    ("--font-title: 'Noto Sans KR',", "--font-title: 'Noto Sans', 'Noto Sans KR',"),
    ("--font-body: 'Noto Sans KR',", "--font-body: 'Noto Sans', 'Noto Sans KR',"),
    (".lsw{display:flex;", ".lsw .lg{font-family:'Noto Sans KR',sans-serif}.lsw{display:flex;"),
    ('css2?family=Noto+Sans+KR:wght@400;500;600;700;800;900&display=swap',
     'css2?family=Noto+Sans:wght@400;500;600;700;800;900&family=Noto+Sans+KR:wght@400;500;600;700;800;900&display=swap'),
]

PRE_PAIRS = [
    ('<a href="textbook.html" class="lg on">🇰🇷 한국어</a>', '<a href="textbook.html" class="lg">🇰🇷 한국어</a>'),
    ('<a href="textbook_mn.html" class="lg">🇲🇳 Монгол</a>', '<a href="textbook_mn.html" class="lg on">🇲🇳 Монгол</a>'),
    ('<h1>🚗 외국인 운전면허 학과시험 교재</h1>', '<h1>🚗 Жолооны онолын шалгалтын сурах бичиг — Гадаад иргэдэд</h1>'),
    ('<p>한국도로교통공단(KoRoad) 교육본부</p>', '<p>Солонгосын Замын хөдөлгөөний газар (KoRoad) — Боловсролын газар</p>'),
    ('<a class="chip chip-sib" href="index.html">📝 학과시험 문제은행 1000문제 풀기</a>',
     '<a class="chip chip-sib" href="mn.html">📝 1000 асуултын сан бодох</a>'),
    ('aria-label="AI 튜터에게 질문하기, 새 창에서 열림">🤖 AI 튜터에게 질문하기</a>',
     'aria-label="AI багшаас асуух, шинэ цонхонд нээгдэнэ">🤖 AI багшаас асуух</a>'),
    ('<a class="diag-banner" href="diagnostic.html?lang=ko">📊 학습 효과 진단평가 <span>사전·사후 진단으로 향상도 확인</span></a>',
     '<a class="diag-banner" href="diagnostic.html?lang=mn">📊 Суралцахуйн үр дүнгийн үнэлгээ <span>Урьдчилсан·дараах оношилгоогоор ахицаа хэмжинэ</span></a>'),
]

TAIL_PAIRS = [
    ('aria-label="맨 위로"', 'aria-label="Дээш очих"'),
    ('<script src="gpt-guide.js?v=2"></script>', '<script src="gpt-guide.js?v=3"></script>'),
]


def main():
    ko_full = (PROJ / "textbook.html").read_text(encoding="utf-8")
    body_i = ko_full.find("<body")
    head = rep(ko_full[:body_i], HEAD_PAIRS, "head")
    first = ko_full.find('<div class="chapter-header" id="ch1">')
    scripts = [m.start() for m in re.finditer(r"<script", ko_full) if m.start() > body_i]
    pre = rep(ko_full[body_i:first], PRE_PAIRS, "pre")
    for k in range(1, 11):
        pre = pre.replace(f'<a href="#ch{k}"', f'<a href="#ch{k}"')  # 앵커 유지(명시)
    pre = re.sub(r">(\s*)(\d+)장<", lambda m: f">{m.group(1)}{m.group(2)}-р бүлэг<", pre)
    pre = re.sub(r"<!--([^>]*?)[가-힣][^>]*?-->", lambda m: "<!--" + re.sub(r"[가-힣·\s]+$", " ", m.group(1)).rstrip() + " -->", pre)  # 한글 주석 제거
    tail = ko_full[scripts[0]:]
    tail_pairs = [p for p in TAIL_PAIRS if p[0] in tail]
    tail = rep(tail, tail_pairs, "tail")
    tail = re.sub(r"//\s*[^\n]*[가-힣][^\n]*", "//", tail)  # 스크립트 한글 주석 제거

    chunks = []
    for k in range(1, 11):
        f = TB / f"mn_ch{k}.html"
        if not f.exists():
            raise SystemExit(f"번역 조각 없음: {f.name}")
        chunks.append(f.read_text(encoding="utf-8"))
    body_chunks = "".join(chunks)
    body_chunks = body_chunks.replace('href="https://evergreenedu-collab.github.io/quiz/textbook.html"', 'href="https://evergreenedu-collab.github.io/quiz/textbook_mn.html"')
    body_chunks = body_chunks.replace('href="https://evergreenedu-collab.github.io/quiz/"', 'href="https://evergreenedu-collab.github.io/quiz/mn.html"')
    html = head + pre + body_chunks + tail

    # 검증 1: 태그·속성 시퀀스 동일(본문 전체)
    ko_seq = seq_of(ko_full[body_i:])
    mn_seq = seq_of(html[html.find("<body"):])
    if ko_seq != mn_seq:
        for i, (a, b) in enumerate(zip(ko_seq, mn_seq)):
            if a != b:
                raise SystemExit(f"구조 불일치 #{i}: ko {a} / mn {b}")
        raise SystemExit(f"태그 개수 불일치 ko {len(ko_seq)} / mn {len(mn_seq)}")
    # 검증 2: 괄호 밖 한글 0 (lsw의 '한국어', CI alt 제외)
    body = html[html.find("<body"):]
    body_chk = body.replace("🇰🇷 한국어", "").replace('alt="한국도로교통공단 KOROAD"', "")
    body_chk = re.sub(r"<script.*?</script>", "", body_chk, flags=re.S)
    body_chk = re.sub(r"\([가-힣·,\s/~]+\)", "", body_chk)
    hang = re.findall(r".{0,25}[가-힣]+.{0,25}", body_chk)
    if hang:
        raise SystemExit(f"괄호 밖 한글 잔존 {len(hang)}건: {hang[:6]}")
    # 검증 3: 링크
    for must in ('href="mn.html"', 'href="diagnostic.html?lang=mn"', 'href="textbook_mn.html" class="lg on"', 'images/koroad-ci.png'):
        if must not in html:
            raise SystemExit(f"필수 링크 없음: {must}")
    body_nolsw = re.sub(r'<div class="lsw">.*?</div>', "", body, flags=re.S)
    bad = re.findall(r'href="(?:https://evergreenedu-collab.github.io/quiz/)?(?:index\.html|textbook\.html|vn\.html|en\.html|cn\.html|)"', body_nolsw)
    bad = [b for b in bad if b not in ('href=""',)]
    if bad:
        raise SystemExit(f"한국어/타언어 페이지 링크 잔존: {bad[:5]}")
    (PROJ / "textbook_mn.html").write_text(html, encoding="utf-8")
    print(f"textbook_mn.html 생성 ({len(html):,}자), 태그 {len(mn_seq)}개 구조 동일, 괄호 밖 한글 0")


if __name__ == "__main__":
    main()
