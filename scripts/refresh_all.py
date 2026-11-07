# -*- coding: utf-8 -*-
"""학과시험 문제은행 원커맨드 갱신 오케스트레이터.

트리거: 사용자가 원본_PDF/ 에 공단 PDF 5개(한국어/English/Chinese/Vietnamese/Mongolian)를 넣고 "갱신 시작".
원칙: 추출 → 스테이징(translations/_refresh/) → 검증 → 원자적 반영. 추출이 1000/1000 통과하기 전엔 HTML을 건드리지 않는다.
비교 기준은 현재 HTML이 아니라 "이전 PDF 스냅샷"(translations/pdf_snapshot/{lang}.json) — 검수로 HTML에 직접 넣은 정정이
재추출로 되돌아가지 않게 하기 위함. 스냅샷이 없으면(최초) HTML과 비교한다.

phase 순서: preflight → extract → diff → apply → patches → integrity → translate → inject → outputs → check → snapshot → report → pr
  - translate: ko 해설이 바뀐/신규 문항의 번역 델타(translations/_refresh/delta_{lang}.json)를 만들고,
    번역본(delta_{lang}_done.json)이 없으면 종료코드 3으로 멈춘다 → Claude 서브에이전트가 번역 → `--resume` 로 재개.
  - 신규 문항(1~1000 밖)·삭제는 자동 반영하지 않고 리포트만 남긴다 (문항 수 체계가 바뀌면 사람이 판단).

사용: py scripts/refresh_all.py [--dry-run] [--resume] [--phase NAME] [--fields b,c,a,e] [--compare-html] [--no-browser]
종료코드: 0 성공 / 2 추출·검증 실패(HTML 미변경) / 3 번역 대기
"""
import argparse
import json
import re
import subprocess
import sys
import time
from datetime import date
from json import JSONDecoder
from pathlib import Path

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / "scripts"))
from html_to_txt import extract_Q  # noqa: E402
from refresh_pdf import find_pdfs  # noqa: E402
from pdfq import extract_lang, normalize, qhash, file_sha256, EXTRACTOR_VERSION  # noqa: E402

LANGS = ["ko", "en", "cn", "vn", "mn"]
HTML = {"ko": "index.html", "en": "en.html", "cn": "cn.html", "vn": "vn.html", "mn": "mn.html"}
STAGE = PROJ / "translations" / "_refresh"
SNAP = PROJ / "translations" / "pdf_snapshot"
PHASES = ["preflight", "extract", "diff", "apply", "patches", "integrity", "translate", "inject", "outputs", "check", "snapshot", "report", "pr"]
LOG = []


def log(msg):
    print(msg)
    LOG.append(msg)


def run(cmd, check=True):
    r = subprocess.run(cmd, cwd=str(PROJ), capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    if check and r.returncode != 0:
        raise SystemExit(f"명령 실패 {cmd}: {out[-800:]}")
    return r.returncode, out


def load_q(lang):
    return {q["n"]: q for q in extract_Q(str(PROJ / HTML[lang]))}


def save_q(lang, by_n):
    path = PROJ / HTML[lang]
    html = path.read_text(encoding="utf-8")
    i = html.find("const Q=")
    s = html.find("[", i)
    _, end = JSONDecoder().raw_decode(html[s:])
    arr = json.dumps([by_n[n] for n in sorted(by_n)], ensure_ascii=False, separators=(",", ":"))
    path.write_text(html[:s] + arr + html[s + end:], encoding="utf-8")


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def jsave(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- phases
def preflight(args, M):
    pdfs = find_pdfs(PROJ / "원본_PDF")
    missing = [l for l in LANGS if l not in pdfs]
    if missing:
        raise SystemExit(f"[preflight] PDF 없음: {missing} — 파일명에 한국어/English/Chinese/Vietnamese/Mongolian 포함 필요")
    M["pdfs"] = {l: {"path": pdfs[l], "name": Path(pdfs[l]).name, "sha256": file_sha256(pdfs[l])} for l in LANGS}
    _, st = run(["git", "status", "--porcelain"], check=False)
    tracked_mod = [x for x in st.splitlines() if x and not x.startswith("??")]
    if tracked_mod and not args.resume and not args.dry_run:
        raise SystemExit("[preflight] 추적 파일에 미커밋 변경이 있습니다. 먼저 커밋/정리하세요:\n" + "\n".join(tracked_mod[:10]))
    _, br = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    _, sha = run(["git", "rev-parse", "--short", "HEAD"])
    M["git"] = {"branch": br.strip(), "base": sha.strip()}
    rc, _ = run(["node", "--version"], check=False)
    if rc != 0:
        raise SystemExit("[preflight] node 없음 (스크립트 문법 검사에 필요)")
    if not args.no_browser:
        rc, _ = run([sys.executable, "-c", "import playwright"], check=False)
        if rc != 0:
            raise SystemExit("[preflight] Playwright 없음: pip install playwright && python -m playwright install chromium (또는 --no-browser)")
    M["extractor"] = EXTRACTOR_VERSION
    log(f"[preflight] PDF 5개 확인, git {M['git']['branch']}@{M['git']['base']}, 추출기 {EXTRACTOR_VERSION}")


def extract(args, M):
    ok = True
    M["extract"] = {}
    for l in LANGS:
        items, problems, extra = extract_lang(M["pdfs"][l]["path"], l)
        jsave(STAGE / f"extract_{l}.json", {str(n): q for n, q in items.items()})
        M["extract"][l] = {"count": len(items), "problems": {str(n): r for n, r in problems.items()}, "extra_numbers": extra}
        log(f"[extract] {l}: {len(items)}문항, 문제 {len(problems)}건{(' ' + str(dict(list(problems.items())[:5]))) if problems else ''}, 범위 밖 번호 {extra[:5]}")
        if len(items) != 1000 or problems or extra:
            ok = False
    if not ok:
        raise SystemExit("[extract] 추출 게이트 실패 — HTML은 변경하지 않았습니다. 위 문제를 해결한 뒤 다시 실행하세요.")


def _baseline(l, args):
    snap = SNAP / f"{l}.json"
    if snap.exists() and not args.compare_html:
        return {int(k): v for k, v in jload(snap)["items"].items()}, "snapshot"
    return load_q(l), "html"


def diff(args, M):
    M["diff"] = {}
    fields = ["b", "c", "a", "e"]
    for l in LANGS:
        new = {int(k): v for k, v in jload(STAGE / f"extract_{l}.json").items()}
        base, src = _baseline(l, args)
        changes = {}
        for n, q in new.items():
            b = base.get(n)
            if not b:
                changes[n] = {"new": True}
                continue
            ch = {}
            for f in fields:
                if f == "e" and l != "ko":
                    continue
                nv = q.get(f, "")
                bv = b.get(f, "")
                if f == "c":
                    same = [normalize(x) for x in nv] == [normalize(x) for x in bv]
                else:
                    same = normalize(nv) == normalize(bv)
                if not same:
                    ch[f] = {"old": bv, "new": nv}
            if ch:
                changes[n] = ch
        removed = sorted(set(base) - set(new))
        M["diff"][l] = {"baseline": src, "changed": {str(n): sorted(k for k in v if k != "new") for n, v in changes.items() if not v.get("new")},
                        "new": sorted(n for n, v in changes.items() if v.get("new")), "candidate_delete": removed}
        jsave(STAGE / f"diff_{l}.json", {str(n): v for n, v in changes.items()})
        byf = {}
        for v in changes.values():
            for k in v:
                if k != "new":
                    byf[k] = byf.get(k, 0) + 1
        log(f"[diff] {l} (기준={src}): 변경 {len([1 for v in changes.values() if not v.get('new')])}문항 {byf}, 신규 {len(M['diff'][l]['new'])}, 삭제후보 {len(removed)}")


def apply(args, M):
    fields = set(args.fields.split(","))
    M["apply"] = {}
    for l in ("ko", "en", "cn", "vn"):  # mn 은 build_mn_page 가 PDF에서 직접 생성
        d = {int(k): v for k, v in jload(STAGE / f"diff_{l}.json").items()}
        Q = load_q(l)
        if l == "ko":
            M["pre_ko_e"] = {str(n): normalize(q.get("e", "")) for n, q in Q.items()}
        applied = {}
        for n, ch in d.items():
            if ch.get("new"):
                continue  # 신규 문항은 자동 반영 안 함(리포트)
            for f, ov in ch.items():
                if f not in fields:
                    continue
                if f == "e" and not str(ov["new"]).strip() and str(ov["old"]).strip():
                    M.setdefault("apply_skipped", []).append(f"{l} Q{n}: PDF 해설 빈값 — 기존 해설 유지")
                    continue
                Q[n][f] = ov["new"]
                applied.setdefault(n, []).append(f)
        M["apply"][l] = {"applied": {str(n): v for n, v in applied.items()}, "skipped_new": M["diff"][l]["new"]}
        if applied and not args.dry_run:
            save_q(l, Q)
        log(f"[apply] {l}: {len(applied)}문항 반영{' (dry-run: 미저장)' if args.dry_run else ''}, 신규 미반영 {len(M['diff'][l]['new'])}")


def patches(args, M):
    if args.dry_run:
        log("[patches] dry-run: 생략")
        return
    _, out = run([sys.executable, "-X", "utf8", "scripts/apply_manual_patches.py"])
    M["patches"] = out.strip().splitlines()
    log("[patches] " + " / ".join(M["patches"]))


def integrity(args, M):
    if args.dry_run:
        log("[integrity] dry-run: 생략")
        return
    rc, out = run([sys.executable, "-X", "utf8", "scripts/verify_explanations.py"], check=False)
    M["integrity"] = out.strip().splitlines()[-6:]
    if rc != 0:
        raise SystemExit("[integrity] 위험문항 판정이 기대와 다릅니다 — ALLOWED/EXPECTED_RISKY 를 검토하세요:\n" + out[-600:])
    log("[integrity] 5개 언어 정답·보기수·이미지 일치 (RISKY 0)")


def translate(args, M):
    ko = load_q("ko")
    pre = M.get("pre_ko_e") or {}
    delta = sorted(n for n, q in ko.items() if (q.get("e") or "").strip() and normalize(q.get("e", "")) != pre.get(str(n), normalize(q.get("e", ""))))
    caches = {l: jload(PROJ / "translations" / f"expl_{l}.json") for l in ("en", "cn", "vn", "mn")}
    need = {}
    for l, c in caches.items():
        H = load_q(l)
        ns = [n for n in delta] + [n for n, q in ko.items() if (q.get("e") or "").strip() and str(n) not in c]
        ns = sorted(set(ns))
        need[l] = ns
        if ns:
            jsave(STAGE / f"delta_{l}.json", {str(n): {"ko": ko[n]["e"], "question": H[n]["b"], "choices": H[n]["c"], "answer": H[n]["a"]} for n in ns})
    M["translate"] = {l: {"count": len(ns), "numbers": ns[:50]} for l, ns in need.items()}
    pending = {l: ns for l, ns in need.items() if ns and not (STAGE / f"delta_{l}_done.json").exists()}
    if pending:
        log("[translate] 번역 필요: " + ", ".join(f"{l} {len(ns)}건" for l, ns in pending.items()))
        log("  → translations/_refresh/delta_{lang}.json 을 서브에이전트로 번역해 delta_{lang}_done.json({n: 번역문}) 생성 후 --resume")
        if args.dry_run:
            return
        raise SystemExit(3)
    for l, ns in need.items():
        if not ns:
            continue
        done = jload(STAGE / f"delta_{l}_done.json")
        miss = [n for n in ns if str(n) not in done or not done[str(n)].strip() or re.search(r"[가-힣]", done[str(n)])]
        if miss:
            raise SystemExit(f"[translate] {l} 번역본 누락/한글잔존: {miss[:10]}")
        caches[l].update({str(n): done[str(n)].strip() for n in ns})
        jsave(PROJ / "translations" / f"expl_{l}.json", dict(sorted(caches[l].items(), key=lambda kv: int(kv[0]))))
        log(f"[translate] {l}: 번역 {len(ns)}건 캐시 반영")
    if not delta and not any(need.values()):
        log("[translate] 번역 델타 없음")


def inject(args, M):
    if args.dry_run:
        log("[inject] dry-run: 생략")
        return
    run([sys.executable, "-X", "utf8", "scripts/inject_translations.py"])
    _, out = run([sys.executable, "-X", "utf8", "scripts/build_mn_page.py"])
    M["inject_mn"] = [x for x in out.splitlines() if x.startswith("[")]
    if (PROJ / "scripts" / "build_mn_textbook.py").exists() and (PROJ / "translations" / "_tb" / "mn_ch1.html").exists():
        run([sys.executable, "-X", "utf8", "scripts/build_mn_textbook.py"])
    log("[inject] en/cn/vn 해설 주입, mn.html·textbook_mn.html 재생성")


def outputs(args, M):
    if args.dry_run:
        log("[outputs] dry-run: 생략")
        return
    run([sys.executable, "-X", "utf8", "html_to_txt.py"])
    log("[outputs] gpt_files/quiz_bank_*.txt, quiz_data_*.json 5개 재생성")


def check(args, M):
    cmd = [sys.executable, "-X", "utf8", "scripts/final_check.py"] + (["--no-browser"] if args.no_browser else [])
    rc, out = run(cmd, check=False)
    M["check"] = out.strip().splitlines()[-12:]
    log("[check] " + (out.strip().splitlines()[-1] if out.strip() else "출력 없음"))
    if rc != 0:
        raise SystemExit("[check] final_check 실패:\n" + out[-1500:])


def snapshot(args, M):
    if args.dry_run:
        log("[snapshot] dry-run: 생략")
        return
    SNAP.mkdir(parents=True, exist_ok=True)
    for l in LANGS:
        items = jload(STAGE / f"extract_{l}.json")
        jsave(SNAP / f"{l}.json", {"pdf": M["pdfs"][l]["name"], "sha256": M["pdfs"][l]["sha256"], "extractor": EXTRACTOR_VERSION,
                                   "date": str(date.today()), "items": items})
    log("[snapshot] translations/pdf_snapshot/{ko,en,cn,vn,mn}.json 갱신 (다음 갱신의 비교 기준)")


def report(args, M):
    lines = [f"# 문제은행 갱신 리포트 ({date.today()})", "", "## 입력",
             *[f"- {l}: {M['pdfs'][l]['name']} (sha256 {M['pdfs'][l]['sha256'][:12]}…)" for l in LANGS],
             f"- git: {M['git']['branch']}@{M['git']['base']}, 추출기 {M['extractor']}", "", "## 추출",
             *[f"- {l}: {M['extract'][l]['count']}문항, 문제 {len(M['extract'][l]['problems'])}건" for l in LANGS], "", "## 변경(기준: 이전 PDF 스냅샷 또는 HTML)"]
    for l in LANGS:
        d = M.get("diff", {}).get(l, {})
        lines.append(f"- {l} (기준={d.get('baseline')}): 변경 {len(d.get('changed', {}))}문항, 신규 {d.get('new')}, 삭제후보 {d.get('candidate_delete')}")
        for n, fs in list(d.get("changed", {}).items())[:60]:
            lines.append(f"  - Q{n}: {', '.join(fs)}")
    lines += ["", "## 반영", *[f"- {l}: {len(M.get('apply', {}).get(l, {}).get('applied', {}))}문항" for l in ("ko", "en", "cn", "vn")],
              "", "## 수동 패치", *[f"- {x}" for x in M.get("patches", [])],
              "", "## 번역 델타", *[f"- {l}: {v['count']}건 {v['numbers'][:20]}" for l, v in M.get("translate", {}).items()],
              "", "## 검사", *[f"- {x}" for x in M.get("check", [])], "", "## 로그", *[f"- {x}" for x in LOG]]
    (STAGE / "report.md").write_text("\n".join(lines), encoding="utf-8")
    log(f"[report] translations/_refresh/report.md")


def pr(args, M):
    if args.dry_run:
        log("[pr] dry-run: 생략")
        return
    branch = f"feat/quiz-refresh-{date.today()}"
    if M["git"]["branch"] in ("main", "master"):
        run(["git", "checkout", "-b", branch])
    run(["git", "add", "-u"])
    run(["git", "add", "translations/pdf_snapshot", "mn.html", "textbook_mn.html", "gpt_files", "원본_PDF"], check=False)
    msg = f"chore: 학과시험 문제은행 갱신 {date.today()} (PDF 5개, 자동 파이프라인)\n\n" + "\n".join(LOG[-20:]) + "\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\n"
    (STAGE / "commit_msg.txt").write_text(msg, encoding="utf-8")
    run(["git", "commit", "-q", "-F", str(STAGE / "commit_msg.txt")])
    run(["git", "push", "-q", "-u", "origin", "HEAD"])
    body = (STAGE / "report.md").read_text(encoding="utf-8") + "\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n"
    (STAGE / "pr_body.md").write_text(body, encoding="utf-8")
    _, out = run(["gh", "pr", "create", "--base", "main", "--head", "HEAD", "--title", f"chore: 학과시험 문제은행 갱신 {date.today()}", "--body-file", str(STAGE / "pr_body.md")], check=False)
    log("[pr] " + out.strip().splitlines()[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="추출·비교·리포트만 (HTML/파일 미변경)")
    ap.add_argument("--resume", action="store_true", help="번역 완료 후 translate 단계부터 재개")
    ap.add_argument("--phase", default=None, help="특정 단계만 실행")
    ap.add_argument("--fields", default="b,c,a,e", help="apply 단계에서 반영할 필드")
    ap.add_argument("--compare-html", action="store_true", help="스냅샷 대신 현재 HTML과 비교")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--no-pr", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    STAGE.mkdir(parents=True, exist_ok=True)
    mpath = STAGE / "manifest.json"
    M = jload(mpath) if (args.resume or args.phase) and mpath.exists() else {}
    phases = PHASES if not args.phase else [args.phase]
    if args.resume and not args.phase:
        phases = PHASES[PHASES.index("translate"):]
    if args.no_pr and "pr" in phases:
        phases.remove("pr")
    try:
        for ph in phases:
            globals()[ph](args, M)
            jsave(mpath, M)
    except SystemExit as e:
        jsave(mpath, M)
        if e.code == 3:
            report(args, M)
            print("\n⏸ 번역 대기 — 번역 후 `py scripts/refresh_all.py --resume` 로 재개")
            sys.exit(3)
        print(f"\n⛔ {e}")
        sys.exit(2)
    print("\n✅ 완료")


if __name__ == "__main__":
    main()
