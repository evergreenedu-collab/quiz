# 문제 개편 자동화 파이프라인 (Claude 주도 반자동)

> **트리거**: 사용자가 새 PDF 4개(한·영·중·베)를 `원본_PDF/`에 넣고 "학과시험 문제 갱신하자"라고 하면, Claude가 아래 순서를 단계별로 실행한다. 데이터 처리는 스크립트, 번역·판단·검증은 Claude/서브에이전트/Codex가 담당한다.
>
> **핵심 원칙**: 해설 정정·번역은 자동화하면 **오매칭 위험**(유사 본문·번호 매핑 어긋남)이 크다. 반드시 **정답 대조 + Codex 교차검증**으로 잡는다.

## 사전 준비
- 새 PDF 4개를 `원본_PDF/`에 배치(파일명에 한국어/English/Chinese/Vietnamese 포함).
- Python: `py`(3.14). `pip install pymupdf` 필요.

## 단계

### 0. 백업·브랜치
```
git checkout -b feat/quiz-refresh-YYYY-MM-DD
```
en/cn/vn/index `.bak` 사본 + 백업 브랜치(CLAUDE.md 안전절차).

### 1. PDF 추출 + HTML 문제 교체
```
py scripts/refresh_pdf.py                 # PDF→추출 + HTML과 번호 비교(리포트)
py scripts/apply_pdf_to_html.py [--dry-run]  # 추출본→const Q 갱신(실질변경만, 4개 언어)
py scripts/match_images.py                # 이미지(imgs) 매칭
```
- `apply_pdf_to_html.py`(✅구현·검증): **실질 변경만 갱신**(공백·유사문장부호 정규화로 무시), **정답 100% 정확**, **추출 실패·부재 문항은 삭제 없이 원본 보존**(데이터 손실 방지), 보기 개수 변경 문항은 c 미갱신+경고, 신규 문항 자동 추가.
  - ⚠️ 같은 회차 재적용해도 en~87·vn~55문항 본문이 미세 갱신됨(PDF 추출 특수문자차, **정답·의미 무관**). 실제 개편 문항은 내용이 완전히 달라 명확히 구분됨.
  - ⚠️ 실행 직후 `git diff`로 실제 변경 문항을 사용자와 검토 후 진행. 자동 폐기(문항 삭제)는 하지 않음(보존 리포트만) → 진짜 폐기는 수동 확인.
- 카운터 라인(1000/문장/사진/표지판/동영상) 재계산.

### 2. 한국어 해설 정정
```
py scripts/repair_ko.py [--dry-run]
```
- 300자 절단·다음문항 혼입 문항을 **본문+보기+정답 앵커**로 원본 PDF에서 재추출.
- **정답 자동 대조**로 오매칭 격리 → 실패 문항은 리포트(수동/Codex 확인).
- 통과분을 index.html의 e 필드에 반영. 원본 PDF에 해설 없는 문항은 폴백.

### 3. SAFE/RISKY 분류
```
py scripts/verify_explanations.py
```
- ko 대비 en/cn/vn 4종 대조(정답·보기수·imgs·마커) → SAFE/RISKY.
- RISKY(보기 순서 언어별 상이)는 번역 제외·폴백. `translations/risky_questions.json`.

### 4. 번역 (Claude 서브에이전트)
```
py scripts/extract_ko_source.py           # SAFE+해설 있는 문항 → translations/_ko_source.json
```
- Claude가 언어별 5배치 병렬 서브에이전트로 en/cn/vn 번역 → `translations/expl_{lang}.json`.
- **용어규칙 프롬프트 주입**(아래 용어집). 중국어=간체.
- 배치 인덱스: 정렬 후 0-196,197-393,394-590,591-787,788-끝.

### 5. 번역 검증·후처리
- 언어별 Codex 샘플(또는 전수 배치) 검증 → 용어·조문번호·의미 지적.
- 공통 용어 일괄 후처리 + 개별 서브에이전트 반영.
- 한글 잔존 검사(판례번호·순서기호·고유명사는 허용).

### 6. HTML 주입 + GPTs txt
```
py scripts/inject_translations.py         # expl_*.json → en/cn/vn HTML e 주입, RISKY 폴백
py html_to_txt.py                         # 【조정 필요】 GPTs txt에 번역 반영(convert의 ko주입→번역캐시 우선+RISKY차단)
```

### 7. 검증·커밋·배포
- JS 문법 검증(en/cn/vn 메인 스크립트 파싱), 4파일 Q=1000·해설 수 일관.
- serve.py 육안 확인 → 커밋 → PR → 사용자 머지 → Pages 배포.
- 머지 후 바탕화면에 새 gpt_files 복사 + GPTs Knowledge 재업로드 안내.

## 언어별 용어집 (번역 프롬프트에 주입)
- **공통**: 도로교통법=Road Traffic Act/道路交通法/Luật Giao thông đường bộ. 시행령=Enforcement Decree/施行令/Nghị định. 시행규칙=Enforcement Rule/施行规则/Thông tư. 조문번호(제○조/항/호, 별표) 원형 유지.
- **en**: 차로변경=lane change, 보도=sidewalk, 경음기=horn, 방향지시등=turn signal, 안전띠=seat belt, 안전표지=traffic sign, 서행=slow down, 일시정지=come to a complete stop, 앞지르기=overtaking, 횡단보도=crosswalk, 회전교차로=roundabout, 개인형 이동장치=personal mobility device, 고속도로=expressway, 연습운전면허=learner's license, 범칙금=traffic fine, 차폭등=clearance lamps, 운행기록계=tachograph.
- **cn(간체)**: 变更车道·人行道·喇叭·转向灯·安全带·交通标志·减速慢行·停车(일시정지)·超车·人行横道·环形交叉路口·个人移动装置·有轨电车(노면전차)·紧急车辆·儿童校车·客车(승합차)·无保护左转·禁令标志(규제표지)·电动滑板车·罚款(과태료/범칙금)·婴幼儿(영유아)·车行道(차도)·发动机制动(기관제동)·羁押(구속).
- **vn**: chuyển làn đường·vỉa hè·còi·đèn xi nhan·dây an toàn·biển báo giao thông·đi chậm·dừng lại hẳn·vượt xe·vòng xuyến·thiết bị di chuyển cá nhân·nhường đường(양보)·Thông tư(부령)·Nghị định của Tổng thống(대통령령)·hiện tượng trượt nước(수막현상). 조문 제○호=điểm/mục.

## 미구현·주의 (다음 구축)
- ✅ `apply_pdf_to_html.py`(1단계) 구현·검증 완료 — 정답 100%·데이터 손실 0·실질 변경만 감지.
- **`html_to_txt.py` convert() 조정**(남은 갭): ko 해설 무조건 주입 → 번역 캐시(expl_*.json) 우선 + RISKY 차단.
- 위험 문항 언어별 보기 정렬 후 SAFE 편입은 별도.
