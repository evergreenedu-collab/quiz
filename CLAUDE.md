# 외국인 학과시험 AI튜터 — Claude 작업 가이드

이 파일은 이 프로젝트에서 Claude가 작업할 때 자동으로 참조하는 안내서입니다. 사용자분과 Claude가 매끄럽게 협업해서 면허시험 문제은행 갱신·정정 작업을 빠르고 안전하게 진행하도록 만든 매뉴얼입니다.

## 프로젝트 개요

- **목적**: 외국인 운전면허 학과시험 학습용 4개 언어(한·영·중·베) 웹 사이트
- **배포**: GitHub Pages (https://evergreenedu-collab.github.io/quiz/)
- **데이터 규모**: 4개 언어 × 1000문항 (1~1000번, 결번 없음)
- **운영**: 한국도로교통공단 부산광역시지부 교육본부

## 핵심 파일 구조

```
외국인-학과시험-AI튜터/
├── index.html          # 한국어 학습 페이지 (980KB, 데이터 1000개 포함)
├── en.html             # 영어
├── cn.html             # 중국어
├── vn.html             # 베트남어
├── textbook.html       # 한국어 교재 (동영상 무관)
├── textbook_en/cn/vn.html
├── images/             # 사진형·표지판형 문항 이미지 (291개)
├── 원본_PDF/           # 4개 언어 PDF 원본 (.gitignore 처리, 영구 보존)
├── movie/              # 동영상 35개 (.gitignore 처리, GitHub Releases에 업로드)
├── scripts/            # 자동화 스크립트 (이 가이드의 핵심)
│   ├── refresh_pdf.py   # PDF → HTML 데이터 자동 갱신
│   └── match_images.py  # 이미지 위치 매칭·추출
├── html_to_txt.py      # HTML → gpt_files/quiz_bank_*.txt 변환 (GPTs 동기화)
├── gpt_files/         # ChatGPT GPTs 학습 텍스트 (4개 언어, HTML 정본 추출본)
│   └── quiz_bank_{ko,en,cn,vn}.txt
└── UPDATE_GUIDE.md     # 사용자분용 한국어 갱신 가이드 (꼭 함께 읽으세요)
```

## 데이터 형식 (HTML 안의 JS 객체)

각 HTML은 `const Q=[{...},...]` 형태의 1000개 문항 배열을 가집니다.

```json
{
  "n": 842,                          // 문항 번호 (1~1000)
  "b": "다음 상황에서 가장 안전한 운전방법 2가지는?",   // 본문
  "c": ["선택지1", "선택지2", "선택지3", "선택지4"],   // 4개 선택지
  "a": "1, 4",                       // 정답 (단일 또는 복수)
  "e": "도로교통법 시행규칙...",      // 해설 (한국어 PDF만 보유)
  "imgs": ["q842.jpg"],              // 이미지 파일명 (사진형·표지판형만)
  "t": "사진형"                      // 유형: 문장형/사진형/표지판형/동영상형
}
```

**카운터 라인** (4개 언어 동일): 1000 / 문장 680 / 사진 185 / 표지판 100 / 동영상 35

## 주요 동영상·이미지 호스팅

- **동영상 35개 (Q966~Q1000)**: GitHub Releases `videos-v1` 에 업로드
  - URL: `https://github.com/evergreenedu-collab/quiz/releases/download/videos-v1/{문항번호}.mp4`
  - HTML 코드에서 `card()` 함수 안 `<video>` 태그로 동적 생성
- **사진·표지판 이미지 285개**: 프로젝트 폴더의 `images/` 안에 (img_NNNN.jpg, sign_NNNN.png, qNNN.png/jpg)

## PDF 추출 알고리즘 핵심 (refresh_pdf.py 안에 구현)

각 언어 PDF의 정답 라벨이 다릅니다 — 이게 추출의 anchor:

| 언어 | 정답 라벨 |
|---|---|
| 한국어 | `■ 정답：N` |
| 영어 | `■ Answer：N` |
| 중국어 | `■ 正确答案 : N` |
| 베트남어 | `■ Đáp án đúng : N` ← `đúng :` 까지 포함되니 추출 시 제거 필요 |

### 알고리즘 단계
1. PDF 전체 텍스트 추출 (PyMuPDF `fitz`)
2. 정답 라벨 위치 모두 식별 → 각 정답 직전 region에서 첫 번째 `(\d+)\.` 매치 → 그 N이 문항 번호
3. 본문 = N. ~ ■ 정답 직전, 선택지 = `①②③④` 또는 `➀➁➂➃` 분리
4. 정답 = 라벨 다음 텍스트, 해설 = ■ 해설 ~ 다음 문항 직전

### 극단 케이스 (스크립트가 처리)
- 점 다음 따옴표 (한국어 `15.‘`, `109.‘`)
- 점 없음 (중국어 PDF의 Q455 — `455 下列…`)
- 다양한 선택지 마커 (`①②③④` 또는 `➀➁➂➃`)
- 베트남어 정답 라벨 `Đáp án đúng :` (đúng 접두사 제거 처리)

## 이미지 위치 매칭 알고리즘 (match_images.py 안에 구현)

PDF 페이지에서 어떤 이미지가 어느 문항인지 자동 매칭:
1. 페이지의 텍스트 블록 분석 → 각 문항 시작 y좌표 식별
2. 페이지의 모든 이미지 + 위치(y좌표) 추출
3. 이미지 y좌표가 어느 문항 범위에 들어가는지로 자동 판별
4. 작은 이미지(99×123 등)는 표지판, 큰 이미지(2484×1406 등)는 사진형으로 추정

**향후 갱신 시**: 이 알고리즘이 정확히 작동하므로, 새 PDF에 대해서도 동일하게 자동 매칭 가능.

## GPTs 텍스트 동기화 (html_to_txt.py 안에 구현)

ChatGPT GPTs 학습용 4개 언어 텍스트 (`gpt_files/quiz_bank_{ko,en,cn,vn}.txt`) 를 HTML 정본에서 자동 생성:

1. 4개 HTML 의 `const Q=[...]` 추출 → 1000문항씩 sort
2. **한국어 해설(`e`)·이미지(`imgs`) 매핑**을 만들어 비한국어 HTML 의 빈 필드에 자동 주입
   - en/cn/vn 의 `e` 는 전부 빈 문자열 → 한국어 해설 그대로 복사 (GPTs 가 사용자 질문 언어로 번역 응답)
   - en HTML 5개(Q737/Q789/Q841/Q863/Q865), cn HTML 2개(Q889/Q919) 의 `imgs` 누락 → 한국어 imgs 복사
3. 사용자 양식 (`===== 문제 N =====` / `유형` / `질문` / `이미지` / `①~④` / `정답` / `해설`) 으로 출력, UTF-8/LF

**향후 갱신 시**: HTML 갱신이 완료되면 **반드시 `py html_to_txt.py` 를 실행** 해서 4개 txt 를 동시 갱신할 것. 같은 PR 에 묶어 머지.

## 안전 절차 (모든 작업의 표준)

1. **작업 시작 전 백업**:
   - 로컬: `Copy-Item -LiteralPath` 로 폴더 통째 복사 (OneDrive 환경 주의: `-LiteralPath` 필수)
   - 4개 HTML `.bak` 사본
   - GitHub 백업 브랜치 생성 (`backup-before-XXX-YYYY-MM-DD`)
2. **작업은 별도 브랜치에서**: main 직접 푸시 금지
3. **사용자가 PR 검토 후 머지**: Claude가 자동 머지하지 않음 (사용자가 명시 동의 시 도와드림)
4. **PR 머지 후 사이트 검증**: GitHub Pages 빌드 2~3분, 사용자가 https://evergreenedu-collab.github.io/quiz/ 에서 확인
5. **백업 자료 보존**: 작업 후 1주일 이상

## 사용자 협업 원칙

- **단계별 보고**: 큰 작업도 검증 게이트별로 진행 결과 보고
- **위치 기반 설명**: 이미지 매칭 같이 시각적 매칭이 필요한 경우 "위/중간/아래" 같이 명확히 표현 (사이즈만 말하면 모호함)
- **본문 단서 제공**: PDF 검증 시 사용자분이 빠르게 확인할 수 있도록 본문 키워드 힌트
- **자동 진행 vs 확인**: 작은 자동 작업은 진행 + 보고, 큰 결정·삭제·force push는 명시 동의

## 미해결·향후 작업

- (현재 없음) 모든 미해결 작업 PR #1~#9 로 완료 (PR #9: GPTs txt 동기화 자동화)
- 새 PDF 갱신 시: `UPDATE_GUIDE.md` 절차 참조

### 다음 갱신 시 Claude 가 자동으로 수행할 순서

1. 백업 + 작업 브랜치
2. `python scripts/refresh_pdf.py` → PDF 1000문항 추출·비교, 사용자 승인
3. HTML 4개 갱신 + 카운터 재계산 + (필요 시) `python scripts/match_images.py`
4. **`py html_to_txt.py` 자동 실행 → `gpt_files/quiz_bank_*.txt` 4개 동기화** (절대 빠뜨리지 말 것)
5. 검증 (4파일 Q=1000, V=35, E≈996, I=285 일관) → PR 생성 (HTML + gpt_files 같은 PR)
6. 사용자분 PR 검토·머지
7. 머지 후 바탕화면(`C:\Users\user\OneDrive\바탕 화면\`) 에 새 4 파일 자동 복사
8. 사용자분에게 ChatGPT GPTs Knowledge 재업로드 절차 안내 (기존 4파일 삭제 → 새 4파일 업로드 → Save)

## 관련 GitHub 저장소

- 본 저장소: `evergreenedu-collab/quiz`
- 동영상 자산: `evergreenedu-collab/quiz` Releases `videos-v1`

## 사용자분 배경 (협업 톤)

- 한국도로교통공단 부산지부 교육본부 교수
- 한국어 응답·코드 영어 식별자
- vibe coding 초보 — 단계별 설명, "왜?" 함께 설명, 위험 작업 사전 경고

자세한 갱신 절차는 `UPDATE_GUIDE.md` 를 보세요.
