(function () {
  var T = {
    ko: {
      title: 'AI 튜터 이용 안내',
      sub: 'ChatGPT로 이동하기 전에 확인해 주세요',
      s1t: '빠른 답변 받기',
      s1b: '입력창 오른쪽의 모델 이름을 눌러 <b>GPT-5.6</b>을 선택하면 더 빠르게 답변을 받을 수 있습니다.',
      s2t: '‘이제 플러그인입니다’ 안내가 보이면',
      s2b: 'OpenAI의 정책 변경 안내입니다. <b>[GPT 계속 사용하기]</b>를 누르거나 안내를 닫고 바로 질문하세요.',
      note: 'ℹ️ 이 안내는 OpenAI가 GPT 서비스를 플러그인으로 전환하면서 생긴 것으로, <b>2026년 12월 11일</b>까지는 불가피하게 표시됩니다. 이후 새 방식으로 전환할 예정입니다.',
      go: 'AI 튜터 열기',
      close: '닫기'
    },
    en: {
      title: 'Before you start',
      sub: 'Please check this before opening ChatGPT',
      s1t: 'Get faster answers',
      s1b: 'Tap the model name next to the message box and choose <b>GPT-5.6</b> to get faster answers.',
      s2t: 'If you see “…is now a plugin”',
      s2b: 'This is an OpenAI policy notice. Tap <b>[Keep using GPT]</b> or close it, then ask your question.',
      note: 'ℹ️ This notice appears because OpenAI is moving GPTs to plugins. It cannot be avoided until <b>December 11, 2026</b>; a new setup will follow.',
      go: 'Open AI Tutor',
      close: 'Close'
    },
    zh: {
      title: 'AI 导师使用说明',
      sub: '打开 ChatGPT 之前请先确认',
      s1t: '更快获得回答',
      s1b: '点击输入框右侧的模型名称，选择 <b>GPT-5.6</b>，可以更快获得回答。',
      s2t: '如果看到“现已成为插件”的提示',
      s2b: '这是 OpenAI 的政策变更通知。请点击 <b>[继续使用 GPT]</b> 或关闭提示，然后直接提问。',
      note: 'ℹ️ 由于 OpenAI 正将 GPT 转为插件，此提示在 <b>2026 年 12 月 11 日</b>前无法避免，之后将切换为新方式。',
      go: '打开 AI 导师',
      close: '关闭'
    },
    vi: {
      title: 'Hướng dẫn sử dụng gia sư AI',
      sub: 'Vui lòng xem trước khi mở ChatGPT',
      s1t: 'Nhận câu trả lời nhanh hơn',
      s1b: 'Nhấn vào tên mô hình bên cạnh ô nhập và chọn <b>GPT-5.6</b> để nhận câu trả lời nhanh hơn.',
      s2t: 'Nếu thấy thông báo “…hiện là plugin”',
      s2b: 'Đây là thông báo thay đổi chính sách của OpenAI. Nhấn <b>[Tiếp tục dùng GPT]</b> hoặc đóng thông báo rồi đặt câu hỏi.',
      note: 'ℹ️ Thông báo này xuất hiện do OpenAI chuyển GPT sang plugin và không thể tránh cho đến <b>ngày 11/12/2026</b>; sau đó sẽ chuyển sang cách mới.',
      go: 'Mở gia sư AI',
      close: 'Đóng'
    }
  };
  var lang = (document.documentElement.lang || 'ko').slice(0, 2);
  var t = T[lang] || T.en;

  var css =
    '.gg-ov{position:fixed;inset:0;z-index:9999;background:rgba(0,20,50,.55);display:flex;align-items:center;justify-content:center;padding:16px;opacity:0;transition:opacity .18s}' +
    '.gg-ov.on{opacity:1}' +
    '.gg-box{width:100%;max-width:420px;background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 18px 48px rgba(0,20,60,.3);transform:translateY(16px);transition:transform .22s;font-family:inherit;color:#1A1D2E}' +
    '.gg-ov.on .gg-box{transform:none}' +
    '.gg-hd{background:linear-gradient(135deg,#003FA2,#00923F);color:#fff;padding:20px 22px 18px}' +
    '.gg-hd h2{margin:0;font-size:19px;font-weight:800;line-height:1.3}' +
    '.gg-hd p{margin:5px 0 0;font-size:13px;opacity:.9}' +
    '.gg-bd{padding:18px 20px 6px}' +
    '.gg-st{display:flex;gap:12px;margin-bottom:16px}' +
    '.gg-n{flex:none;width:28px;height:28px;border-radius:50%;background:#EBF0FA;color:#003FA2;font-weight:800;font-size:14px;display:flex;align-items:center;justify-content:center}' +
    '.gg-st h3{margin:3px 0 4px;font-size:15px;font-weight:800;line-height:1.35}' +
    '.gg-st p{margin:0;font-size:14px;line-height:1.55;color:#4A4F6A}' +
    '.gg-st b{color:#003FA2}' +
    '.gg-pill{display:inline-flex;align-items:center;gap:6px;margin-top:8px;padding:5px 12px;border-radius:999px;background:#F3F4F8;border:1px solid #E2E5EF;font-size:13px;font-weight:700;color:#6E7191}' +
    '.gg-pill i{font-style:normal;color:#00923F}' +
    '.gg-note{margin:-4px 0 12px;padding:10px 12px;border-radius:10px;background:#F3F4F8;font-size:12.5px;line-height:1.5;color:#6E7191}' +
    '.gg-note b{color:#4A4F6A}' +
    '.gg-ft{display:flex;gap:10px;padding:8px 20px 20px}' +
    '.gg-ft button{min-height:48px;border-radius:14px;font-size:15px;font-weight:800;font-family:inherit;cursor:pointer;border:0}' +
    '.gg-close{flex:0 0 auto;padding:0 18px;background:#F3F4F8;color:#4A4F6A}' +
    '.gg-go{flex:1;background:linear-gradient(135deg,#003FA2,#2563EB);color:#fff;box-shadow:0 4px 12px rgba(0,63,162,.3)}' +
    '@media (max-width:560px){.gg-ov{align-items:flex-end;padding:0}.gg-box{max-width:none;border-radius:22px 22px 0 0;transform:translateY(100%)}.gg-ft{padding-bottom:calc(20px + env(safe-area-inset-bottom))}}';

  var style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  var nativeOpen = window.open.bind(window);
  var pendingUrl = null;
  var ov = null;

  function build() {
    ov = document.createElement('div');
    ov.className = 'gg-ov';
    ov.setAttribute('role', 'dialog');
    ov.setAttribute('aria-modal', 'true');
    ov.setAttribute('aria-labelledby', 'gg-title');
    ov.innerHTML =
      '<div class="gg-box">' +
      '<div class="gg-hd"><h2 id="gg-title">🤖 ' + t.title + '</h2><p>' + t.sub + '</p></div>' +
      '<div class="gg-bd">' +
      '<div class="gg-st"><div class="gg-n">1</div><div><h3>⚡ ' + t.s1t + '</h3><p>' + t.s1b + '</p>' +
      '<span class="gg-pill">GPT-6 ⌄ <i>→</i> GPT-5.6 ✓</span></div></div>' +
      '<div class="gg-st"><div class="gg-n">2</div><div><h3>💬 ' + t.s2t + '</h3><p>' + t.s2b + '</p></div></div>' +
      '<p class="gg-note">' + t.note + '</p>' +
      '</div>' +
      '<div class="gg-ft"><button type="button" class="gg-close">' + t.close + '</button>' +
      '<button type="button" class="gg-go">' + t.go + ' →</button></div>' +
      '</div>';
    document.body.appendChild(ov);
    ov.addEventListener('click', function (e) { if (e.target === ov) hide(); });
    ov.querySelector('.gg-close').addEventListener('click', hide);
    ov.querySelector('.gg-go').addEventListener('click', function () {
      var url = pendingUrl;
      hide();
      if (url) nativeOpen(url, '_blank', 'noopener');
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && ov.style.display !== 'none') hide();
    });
  }

  function show(url) {
    pendingUrl = url;
    if (!ov) build();
    ov.style.display = 'flex';
    requestAnimationFrame(function () { ov.classList.add('on'); });
    ov.querySelector('.gg-go').focus();
  }

  function hide() {
    ov.classList.remove('on');
    setTimeout(function () { ov.style.display = 'none'; }, 200);
  }

  function isGpt(url) { return /chatgpt\.com\/g\//.test(String(url || '')); }

  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]');
    if (a && isGpt(a.href)) {
      e.preventDefault();
      e.stopImmediatePropagation();
      show(a.href);
    }
  }, true);

  window.open = function (url) {
    if (isGpt(url)) { show(url); return null; }
    return nativeOpen.apply(null, arguments);
  };
})();
