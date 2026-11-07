# -*- coding: utf-8 -*-
"""상설 전수 검사기 — 배포 전 반드시 통과해야 하는 게이트.

검사 항목
  A. 데이터: 5개 언어 Q=1000(1~1000 결번·중복 0), 정답·보기수·이미지·유형이 한국어와 일치(ALLOWED 예외만 허용),
     본문/보기 빈값 0, 보기에 사진 설명줄(■) 누출 0, 비한국어 페이지 한글 잔존은 허용목록(translations/hangul_allow.json)만
  B. 페이지 일관성(11개): CI 바, 글꼴(Noto Sans 계열), 언어 스위처 5개, gpt-guide 캐시 버전 동일, manifest 연결
  C. 인라인 스크립트 node --check
  D. GPTs 산출물: quiz_bank_*.txt 문제 1000·해설 수, quiz_data_*.json count 1000 (HTML과 동일 해설 수)
  E. (옵션) Playwright 11개 페이지 렌더링 오류 0  (--no-browser 로 생략)

사용: py scripts/final_check.py [--no-browser]
종료코드 0=ALL OK, 1=실패
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ))
from html_to_txt import extract_Q  # noqa: E402

QUIZ = {"ko": "index.html", "en": "en.html", "cn": "cn.html", "vn": "vn.html", "mn": "mn.html"}
TEXTBOOK = {"ko": "textbook.html", "en": "textbook_en.html", "cn": "textbook_cn.html", "vn": "textbook_vn.html", "mn": "textbook_mn.html"}
ALL_PAGES = list(QUIZ.values()) + list(TEXTBOOK.values()) + ["diagnostic.html"]
ALLOWED_MISMATCH = {456: {"en", "cn"}}  # 영·중 공식 PDF 보기 5개(ko 4개) — verify_explanations.ALLOWED 와 동일
HANGUL_ALLOW = PROJ / "translations" / "hangul_allow.json"


def ds(a):
    return sorted(c for c in str(a) if c.isdigit())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    fails = []

    def fail(msg):
        fails.append(msg)
        print("  ❌", msg)

    # A. 데이터
    RAW = {l: extract_Q(str(PROJ / f)) for l, f in QUIZ.items()}
    L = {l: {q["n"]: q for q in arr} for l, arr in RAW.items()}
    for l, arr in RAW.items():
        if len(arr) != len(L[l]):
            fail(f"{l}: 중복 문항 번호 {len(arr) - len(L[l])}건")
    ko = L["ko"]
    allow = json.loads(HANGUL_ALLOW.read_text(encoding="utf-8")) if HANGUL_ALLOW.exists() else {}
    for l, Q in L.items():
        print(f"[{l}] Q={len(Q)} 해설={sum(1 for q in Q.values() if (q.get('e') or '').strip())}")
        if sorted(Q) != list(range(1, 1001)):
            fail(f"{l}: 문항 번호 1~1000 아님")
        for n, q in Q.items():
            k = ko.get(n)
            if not k:
                continue
            if ds(q["a"]) != ds(k["a"]):
                fail(f"{l} Q{n}: 정답 불일치 {q['a']} vs ko {k['a']}")
            if len(q["c"]) != len(k["c"]) and l not in ALLOWED_MISMATCH.get(n, set()):
                fail(f"{l} Q{n}: 보기수 {len(q['c'])} vs ko {len(k['c'])}")
            if q.get("imgs") != k.get("imgs"):
                fail(f"{l} Q{n}: 이미지 불일치")
            if q.get("t") != k.get("t"):
                fail(f"{l} Q{n}: 유형 불일치")
            if not q["b"].strip() or any(not c.strip() for c in q["c"]):
                fail(f"{l} Q{n}: 본문/보기 빈값")
            if any("■" in c for c in q["c"]) or "■" in q["b"]:
                fail(f"{l} Q{n}: 사진 설명줄(■) 누출")
            if l != "ko":
                txt = q["b"] + " ".join(q["c"]) + (q.get("e") or "")
                if re.search(r"[가-힣]", txt) and str(n) not in set(map(str, allow.get(l, []))):
                    fail(f"{l} Q{n}: 한글 잔존(허용목록 외)")
    for n, k in ko.items():
        if re.search(r"(?<![\d.])%d\.\s" % (n + 1), k.get("e") or ""):
            fail(f"ko Q{n}: 해설에 다음 문항 번호 패턴 '{n+1}.' — 혼입 의심")
        if k["t"] in ("사진형", "표지판형") and not k.get("imgs"):
            fail(f"ko Q{n}: {k['t']}인데 imgs 없음")
        for im in k.get("imgs") or []:
            if not (PROJ / "images" / im).exists():
                fail(f"ko Q{n}: 이미지 파일 없음 {im}")

    # B. 페이지 일관성
    versions = set()
    for f in ALL_PAGES:
        p = PROJ / f
        if not p.exists():
            fail(f"{f}: 파일 없음")
            continue
        h = p.read_text(encoding="utf-8")
        if 'class="ci-bar"' not in h:
            fail(f"{f}: CI 바 없음")
        if not re.search(r"Noto\+Sans", h):
            fail(f"{f}: Noto Sans 글꼴 링크 없음")
        if f == "diagnostic.html":
            if h.count('data-l="') != 5:
                fail(f"{f}: 언어 버튼 {h.count('data-l=')}개")
        else:
            n_lsw = len(re.findall(r'<a href="(?:index|en|cn|vn|mn|textbook|textbook_en|textbook_cn|textbook_vn|textbook_mn)\.html" class="lg', h))
            if n_lsw != 5:
                fail(f"{f}: 언어 스위처 {n_lsw}개")
        m = re.search(r'gpt-guide\.js\?v=(\d+)', h)
        if m:
            versions.add(m.group(1))
        if f in QUIZ.values() and 'rel="manifest"' not in h:
            fail(f"{f}: manifest 없음")
        # C. 스크립트 문법
        tmp = PROJ / "_final_check_tmp.js"
        tmp.write_text("\n;\n".join(re.findall(r"<script>(.*?)</script>", h, re.S)), encoding="utf-8")
        r = subprocess.run(["node", "--check", str(tmp)], capture_output=True, text=True)
        tmp.unlink(missing_ok=True)
        if r.returncode != 0:
            fail(f"{f}: 스크립트 문법 오류 {r.stderr[:120]}")
    if len(versions) > 1:
        fail(f"gpt-guide 캐시 버전 혼재 {versions}")
    print(f"[pages] {len(ALL_PAGES)}개 검사, gpt-guide v={versions}")

    # D. GPTs 산출물
    for l in QUIZ:
        t = (PROJ / "gpt_files" / f"quiz_bank_{l}.txt").read_text(encoding="utf-8")
        j = json.loads((PROJ / f"quiz_data_{l}.json").read_text(encoding="utf-8"))
        nq, ne = t.count("===== 문제 "), t.count("\n해설: ")
        if nq != 1000 or j.get("count") != 1000:
            fail(f"gpt {l}: 문제 {nq} json {j.get('count')}")
        jq = {x["n"]: x for x in j.get("questions", [])}
        stale = [n for n, q in L[l].items() if n not in jq or any(jq[n].get(k) != q.get(k) for k in ("b", "c", "a"))]
        if stale:
            fail(f"gpt {l}: quiz_data 가 HTML과 불일치 {stale[:5]} — html_to_txt.py 재실행 필요")
        if any(f"===== 문제 {n} =====" not in t for n in L[l]):
            fail(f"gpt {l}: txt 에 누락된 문제 있음")
        print(f"[gpt {l}] 문제 {nq} 해설 {ne}")

    # E. 브라우저
    if not args.no_browser:
        try:
            from playwright.sync_api import sync_playwright
            import time
            srv = subprocess.Popen([sys.executable, "-m", "http.server", "8766", "--bind", "127.0.0.1"], cwd=str(PROJ),
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.5)
            try:
                with sync_playwright() as p:
                    b = p.chromium.launch()
                    for f in ALL_PAGES:
                        errs = []
                        pg = b.new_page(viewport={"width": 390, "height": 800})
                        pg.on("pageerror", lambda e: errs.append(str(e)))
                        url = f"http://127.0.0.1:8766/{f}" + ("?lang=mn" if f == "diagnostic.html" else "")
                        pg.goto(url)
                        pg.wait_for_timeout(1500)
                        if errs:
                            fail(f"{f}: 브라우저 오류 {errs[0][:100]}")
                        pg.close()
                    b.close()
            finally:
                srv.terminate()
            print("[browser] 11개 페이지 렌더링 검사 완료")
        except ImportError:
            fail("Playwright 미설치 (pip install playwright && python -m playwright install chromium) — 또는 --no-browser")

    print("\nRESULT:", "ALL OK" if not fails else f"FAIL ({len(fails)}건)")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
