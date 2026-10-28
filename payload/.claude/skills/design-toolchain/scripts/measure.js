// 페이지 안 Web Vitals + axe-core WCAG 2.2 AA (aside repl 전용, run-qa.sh가 URL·모드·테마 함수 자리표시자를 치환)
// - 모드마다 repl을 따로 부른다(Vitals 1회 + axe 4조합 각 1회) — repl 1회 120초 제한을 나눠 쓰지 않게(2026-09-30 감사 #7).
//   출력 줄(VITALS·AXE)은 finally에서 찍어 예외가 나도 결과가 남는다.
// - Vitals: 사용자 창 크기 탭에서 측정(Aside는 뷰포트 변경 불가). CLS = 세션 윈도우 최댓값(web.dev 정의:
//   이동 간격 < 1초, 윈도우 ≤ 5초). 새 항목이 1.5초 멈출 때까지 관찰, 6초 한계 도달 시 provisional=true.
// - axe: 창 크기 또는 375 폭(같은 출처 iframe) × 다크·라이트. 테마 강제는 capture.js와 같은 방식.
//   axe는 사용자 실세션 탭에 주입되므로 SRI 해시로 고정한다(감사 #15·#25) — 버전을 올리면 해시도 함께 바꾼다.
const TGT = __URL__;
const MODE = __COMBO__;                                  // { vitals: true } 또는 { theme, width(null = 창 크기) }
const AXE = 'https://cdn.jsdelivr.net/npm/axe-core@4.13.0/axe.min.js';
const AXE_SRI = 'sha384-jzJDdyy7z7+/I7TeoAg0Gc8k9hD8b1xRN0W18hMptWJ0cdoiebywhPpCyP9eBOgn';   // npm 레지스트리 무결성 검증본과 동일(2026-09-30)
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

if (MODE.vitals) {
let vitals = null, pg = null;
try {
pg = await openTab(TGT);
vitals = await pg.evaluate(() => new Promise(res => {
  const out = { lcp: null, lcpEl: null, shifts: [] }; let lastEntry = performance.now(); const t0 = performance.now();
  new PerformanceObserver(l => { const e = l.getEntries().at(-1); out.lcp = Math.round(e.startTime); lastEntry = performance.now();
    out.lcpEl = e.element ? e.element.tagName + (e.element.currentSrc ? ' ' + e.element.currentSrc.split('/').pop() : '') : null;
  }).observe({ type: 'largest-contentful-paint', buffered: true });
  new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) out.shifts.push([e.startTime, e.value]); lastEntry = performance.now();
  }).observe({ type: 'layout-shift', buffered: true });
  const finish = (provisional) => {
    let cls = 0, win = 0, start = 0, prev = -Infinity;
    for (const [t, v] of out.shifts.sort((a, b) => a[0] - b[0])) {
      if (t - prev < 1000 && t - start < 5000) win += v; else { win = v; start = t; }
      prev = t; cls = Math.max(cls, win);
    }
    const nav = performance.getEntriesByType('navigation')[0], fcp = performance.getEntriesByName('first-contentful-paint')[0];
    res({ route: location.pathname, title: document.title, width: innerWidth, height: innerHeight,
          status: nav.responseStatus, ttfb: Math.round(nav.responseStart), fcp: fcp ? Math.round(fcp.startTime) : null,
          lcp: out.lcp, lcpEl: out.lcpEl, cls: Number(cls.toFixed(4)), shiftCount: out.shifts.length, provisional });
  };
  const tick = () => {
    const now = performance.now();
    if (now - lastEntry >= 1500) return finish(false);
    if (now - t0 >= 6000) return finish(true);
    setTimeout(tick, 250);
  };
  setTimeout(tick, 250);
}));
} catch (e) {
  vitals = { error: 'REPL_ERROR ' + String(e && e.message || e).slice(0, 120) };
} finally {
  console.log('VITALS ' + JSON.stringify(vitals));
  if (pg) await closeTab(pg);
}
} else {

// axe 실행기: 대상 문서(doc)에 axe를 주입하고 테마를 강제한 뒤 스캔한다
const runAxe = async (tab, theme, width) => tab.evaluate(async ([AXE, AXE_SRI, TAGS, theme, width, src]) => {
  /*__FORCE_THEME__*/
  // 모든 대기에 시간 제한 — 한 조합이 멈춰도 측정 전체가 죽지 않게(2026-09-28 간헐 대기 실측)
  const within = (p, ms, tag) => Promise.race([p, new Promise((_, bad) => setTimeout(() => bad(new Error(tag)), ms))]);
  let doc = document, win = window;
  try {
  if (width) {                                          // 375 폭: 같은 출처 iframe
    document.head.innerHTML = ''; document.body.style.cssText = 'margin:0'; document.body.innerHTML = '';
    const f = Object.assign(document.createElement('iframe'), { width, height: 812 });
    const ok = new Promise(r => f.onload = r); f.src = src; document.body.appendChild(f); await within(ok, 15000, 'TIMEOUT_IFRAME_LOAD');
    await new Promise(r => setTimeout(r, 600));
    try { doc = f.contentDocument; win = f.contentWindow; } catch (e) { return { error: 'FRAME_BLOCKED' }; }
    if (!doc || !doc.body) return { error: 'FRAME_BLOCKED' };
  }
  if (/^chrome-error:/.test(doc.location.href)) return { error: 'PAGE_LOAD_ERROR' };   // 탭이 브라우저 오류 페이지면 그 페이지를 검사하지 않는다
  const th = forceTheme(doc, theme);                  // theme.js 공용 로직(조건 보존·재귀)
  // 페이지에 이미 있는 window.axe는 믿지 않는다 — 가짜 axe.run()이 위반 0을 돌려줄 수 있다(2026-10-02 codex 최종 게이트).
  // 접근자·쓰기 불가로 심어 둔 axe는 덮어쓸 수 없으니 거부하고, 아니면 비운 뒤 고정 엔진을 항상 주입해 버전을 확인한다.
  const pre = Object.getOwnPropertyDescriptor(win, 'axe');
  if (pre && (pre.get || pre.set || pre.writable === false || !pre.configurable)) return { error: 'AXE_SHADOWED_BY_PAGE' };
  if (pre) delete win.axe;
  // 엔진 스크립트가 window.axe에 처음 대입하는 값을 재정의 불가 덫으로 잡는다 — 로드 직후 페이지가 window.axe를 같은 버전의
  // 가짜로 바꿔도 덫이 잡은 진짜 객체와 그 run을 쓴다(2026-10-02 codex 2차 게이트). 적대적 페이지가 엔진 내부를 고치는 것까지는
  // 막지 못한다 — 검사 대상은 사용자 자신의 페이지라는 전제(위협 모델: 실수·우연한 전역 충돌 방지).
  let real = null;
  Object.defineProperty(win, 'axe', { configurable: false, get: () => real, set: (v) => { if (!real) real = v; } });
  await within(new Promise((ok, bad) => { const sc = doc.createElement('script'); sc.integrity = AXE_SRI; sc.crossOrigin = 'anonymous'; sc.src = AXE; sc.onload = ok; sc.onerror = () => bad(new Error('AXE_LOAD_ERROR')); doc.head.appendChild(sc); }), 15000, 'TIMEOUT_AXE_LOAD');
  const want = (AXE.match(/axe-core@([\d.]+)/) || [])[1];
  if (!real || real.version !== want || typeof real.run !== 'function') return { error: 'AXE_VERIFY_FAILED' };
  const realRun = real.run;
  const r = await within(realRun.call(real, doc, { runOnly: { type: 'tag', values: TAGS } }), 30000, 'TIMEOUT_AXE_RUN');
  return { width: win.innerWidth, themeRules: th.themeRules, unsupported: th.unsupported, blockedSheets: th.blockedSheets, bg: win.getComputedStyle(doc.body).backgroundColor, passes: r.passes.length,
           incomplete: r.incomplete.map(v => ({ id: v.id, nodes: v.nodes.length })),
           violations: r.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, target: v.nodes[0] && v.nodes[0].target.join(' ') })) };
  } catch (e) { return { error: String(e && e.message || e) }; }
}, [AXE, AXE_SRI, TAGS, theme, width, TGT]);

// 조합마다 새 탭(같은 URL goto는 해시만 다를 때 로드가 일어나지 않아 대기 시간 초과 — 2026-09-28 실측)
const axe = {}, akey = MODE.theme + (MODE.width ? '_' + MODE.width : '_window');
let tab = null;
try {
  tab = await openTab(TGT);
  axe[akey] = await runAxe(tab, MODE.theme, MODE.width);
} catch (e) {                                          // REPL 수준 예외(CDP 시간 초과 등)도 결과로 남긴다
  axe[akey] = { error: 'REPL_ERROR ' + String(e && e.message || e).slice(0, 80) };
} finally {
  console.log('AXE ' + JSON.stringify(axe));
  if (tab) await closeTab(tab);
}
}
