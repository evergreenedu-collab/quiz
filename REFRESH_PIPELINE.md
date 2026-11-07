# 학과시험 문제은행 갱신 절차 (원커맨드 자동화, 2026-11-07)

> **사용자분이 하실 일은 4가지뿐입니다.** 나머지는 Claude가 `scripts/refresh_all.py` 로 자동 실행합니다.

## 사용자분이 하실 일
1. 공단에서 받은 PDF **5개**(한국어·English·Chinese·Vietnamese·Mongolian)를 `원본_PDF/` 에 넣기
   - 파일명에 언어 키워드(`한국어` / `English` / `Chinese` / `Vietnamese` / `Mongolian`)가 들어 있어야 자동 식별됩니다.
   - 옛 PDF는 지워도 되고 두어도 됩니다(같은 언어가 2개면 나중 것을 씁니다 — 헷갈리지 않게 지우는 걸 권장).
2. Claude에게 **"갱신 시작"**
3. Claude가 올린 PR의 검증 리포트를 보고 **Merge**
4. 플러그인 Knowledge 갱신: Claude가 만들어 주는 문장을 ChatGPT Plugin Creator에 붙여 넣고 바탕화면의 `quiz_bank_*.txt` 5개 첨부 (약 2분, `gpt_files/PLUGIN_UPDATE_MESSAGE.md` 참조)

## Claude가 자동으로 하는 일 (`py scripts/refresh_all.py`)
| 단계 | 내용 | 실패 시 |
|---|---|---|
| preflight | PDF 5개 식별·SHA 기록, git 추적 파일 깨끗한지, node·Playwright 확인 | 즉시 중단(아무것도 안 바꿈) |
| extract | 5개 PDF → 1000문항 (①~⑤, ⓛ·➀ 보정, 사진 설명줄 제거, 정답 정규화, ko 해설 혼입 절단) | 1000/1000·문제 0건 아니면 중단 |
| diff | **이전 PDF 스냅샷**(`translations/pdf_snapshot/`)과 정규화 비교 → 변경/신규/삭제후보 | — |
| apply | 변경 필드만 HTML Q에 반영. 신규 문항·삭제는 자동 반영하지 않고 리포트 | PDF 해설이 빈값이면 기존 유지 |
| patches | `translations/manual_patches.json` 재적용(멱등) | — |
| integrity | 5개 언어 정답·보기수·이미지 일치(`verify_explanations.py`, ALLOWED 예외만) | 중단 |
| translate | 바뀐 ko 해설만 `translations/_refresh/delta_{lang}.json` 으로 → **Claude 서브에이전트가 번역**(용어집) → `--resume` | 번역 대기(종료코드 3) |
| inject | en/cn/vn 해설 주입, `mn.html`·`textbook_mn.html` 재생성 | — |
| outputs | `gpt_files/quiz_bank_*.txt`, `quiz_data_*.json` 5개 | — |
| check | `scripts/final_check.py` 전수 검사(11개 페이지 CI·글꼴·스위처·스크립트, 데이터 일치, GPTs 산출물, 브라우저 렌더링) | 중단 |
| snapshot | 이번 PDF 추출본을 다음 비교 기준으로 저장 | — |
| report / pr | `translations/_refresh/report.md` → 브랜치 push·PR 생성(머지는 사용자) | — |

```powershell
py scripts/refresh_all.py               # 전체 (번역 필요하면 멈춤)
py scripts/refresh_all.py --resume      # 번역 완료 후 재개
py scripts/refresh_all.py --dry-run     # 추출·비교·리포트만 (아무것도 안 바꿈)
py scripts/final_check.py               # 언제든 전수 검사
```

## 왜 "이전 PDF 스냅샷"과 비교하나
10월 검수에서 보기·해설 수백 건을 HTML에 직접 정정했습니다. 새 PDF를 "현재 HTML"과 비교하면 그 정정이 PDF 원문으로 되돌아갑니다.
그래서 **PDF끼리** 비교해 공단이 실제로 바꾼 문항만 반영합니다. 공단 원문 자체의 오류 정정은 `manual_patches.json` 에 근거와 함께 기록해 두면 재추출 후에도 자동 재적용됩니다.

## 사람이 판단해야 하는 경우 (파이프라인이 멈추고 리포트에 남김)
- 문항 수 체계가 바뀜(1~1000 밖 번호, 결번) → 추출 게이트 실패. 공단 PDF 형식 변화이므로 `scripts/pdfq.py` 조정 필요.
- 신규 문항 → 이미지(`images/`)·유형(t) 확정 후 반영. `scripts/match_images.py` 로 이미지 추출.
- 교재(`textbook*.html`)는 PDF와 무관(공단 교재 개정 시 별도 작업).
- 영·중 PDF가 한국어와 보기 수가 다른 456번 같은 공식 차이는 `verify_explanations.py` 의 `ALLOWED` 에 근거와 함께 등록.

## 기록
- 2026-11-07 베이스라인: 현재 PDF 5개로 실행 → 기존 결함 발견·정정(한국어 해설 25건 목록 절단 복원, 982·983 해설 밀림, 정답 표기 6건, 몽골어 사진 설명줄 누출) → 번역 델타 27건×4언어 → 스냅샷 생성.
