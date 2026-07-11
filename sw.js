// PWA 설치 조건 충족용 최소 service worker.
// 캐싱하지 않는다 — 모든 요청은 네트워크로 통과시켜 항상 최신 콘텐츠를 보여준다.
// (문제 데이터가 자주 갱신되는 앱이라 캐시로 인한 "옛 화면" 문제를 원천 차단)
self.addEventListener('fetch', function () {});
