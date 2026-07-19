# -*- coding: utf-8 -*-
"""한국어 해설을 영·중·베로 이식하기 전 안전성 검증 게이트.

배경: 정답 번호는 4개 언어가 같지만, 일부 문항은 보기 순서·개수·이미지가
언어별로 달라 한국어 해설을 그대로 붙이면 엉뚱한 보기를 설명하게 된다.
ko 대비 en/cn/vn을 4종 대조 → SAFE(이식 허용) / RISKY(번역 제외·폴백) 분류.

사용법:
    py scripts/verify_explanations.py
출력: SAFE/RISKY 개수와 목록. translations/risky_questions.json 기록.
"""
import sys
import json
import re
from pathlib import Path

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ))
from html_to_txt import extract_Q  # 기존 파서 재사용

# 사용자·조사로 확인된 기대 위험 문항 (회귀 감지용)
EXPECTED_RISKY = {39, 456, 466, 509, 737, 789, 841, 842, 863, 865, 889, 919}


def digit_set(a):
    """정답에서 숫자만 뽑아 정렬 튜플 (표기 차이 무시)"""
    return tuple(sorted(c for c in str(a) if c.isdigit()))


def marker_polluted(e):
    """해설에 보기 마커/라벨이 누출된 파싱 오염 흔적 검사.
    정상 '②번은~' 참조는 제외하고, 해설 말미의 보기 블록(②③④⑤로 끝남)만 오염으로 본다.
    (■ 라벨 누출은 현재 데이터에 흔치 않아 말미 마커만 신호로 사용)"""
    if not e:
        return False
    return bool(re.search(r"[②③④⑤]\s*$", e.strip()))


def load_all():
    files = {"ko": "index.html", "en": "en.html", "cn": "cn.html", "vn": "vn.html"}
    return {lang: {q["n"]: q for q in extract_Q(str(PROJ / f))} for lang, f in files.items()}


def classify(Qs):
    ko = Qs["ko"]
    risky = {}
    for n, kq in ko.items():
        reasons = []
        for lang in ("en", "cn", "vn"):
            q = Qs[lang].get(n)
            if not q:
                reasons.append(f"{lang}:문항없음")
                continue
            if digit_set(q.get("a", "")) != digit_set(kq.get("a", "")):
                reasons.append(f"{lang}:정답불일치")
            if len(q.get("c", [])) != len(kq.get("c", [])):
                reasons.append(f'{lang}:보기수({len(q.get("c", []))}≠{len(kq.get("c", []))})')
            if list(q.get("imgs", [])) != list(kq.get("imgs", [])):
                reasons.append(f"{lang}:imgs")
        if marker_polluted(kq.get("e", "")):
            reasons.append("ko:마커오염")
        if reasons:
            risky[n] = reasons
    safe = [n for n in ko if n not in risky]
    return safe, risky


def main():
    Qs = load_all()
    for lang, m in Qs.items():
        print(f"  {lang}: {len(m)}문항 로드")
    safe, risky = classify(Qs)
    print(f"\n총 {len(Qs['ko'])}문항 → SAFE {len(safe)} / RISKY {len(risky)}")
    print(f"RISKY: {sorted(risky)}")
    for n in sorted(risky):
        print(f"  Q{n}: {', '.join(risky[n])}")

    out_dir = PROJ / "translations"
    out_dir.mkdir(exist_ok=True)
    payload = {
        "safe_count": len(safe),
        "risky_count": len(risky),
        "risky": {str(n): risky[n] for n in sorted(risky)},
    }
    (out_dir / "risky_questions.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n기록: translations/risky_questions.json")

    if set(risky) == EXPECTED_RISKY:
        print("✅ 기대 RISKY 12문항과 정확히 일치")
        return 0
    print(f"⚠️ 기대와 차이 — 추가:{sorted(set(risky) - EXPECTED_RISKY)}, 누락:{sorted(EXPECTED_RISKY - set(risky))}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
