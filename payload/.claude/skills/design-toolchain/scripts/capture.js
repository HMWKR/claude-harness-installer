// 한 조합(테마 × 폭) 전체 페이지 구간 캡처 (aside repl 전용, run-qa.sh가 URL·조합·테마 함수 자리표시자를 치환)
// - 조합마다 repl을 따로 부른다 — repl 1회 120초 제한을 네 조합이 나눠 쓰지 않게(2026-09-30 감사 #7).
// - 폭: 같은 출처 iframe + clip (Aside는 setViewportSize·CDP 없음). fullPage:true는 가짜 이미지라 금지.
//   탭 창이 조합 크기보다 작으면 clip이 창 밖으로 나가므로 VIEWPORT_TOO_SMALL로 건너뛴다(감사 #2).
// - 테마: theme.js forceTheme — 시스템 설정과 무관, 다른 미디어 조건 보존, @import·그룹 규칙 재귀.
// - 부드러운 스크롤 끔·정착 대기(구간마다 보이는 이미지·유한 애니메이션 완료, 감사 #5), 직전 구간에 완전히 찍힌
//   fixed·sticky만 이후 구간에서 숨김(아직 안 찍힌 sticky·화면 전체를 덮는 배경 레이어는 보존, 감사 #4),
//   하단 도달 후 높이·이미지 안정화 대기(지연 로딩), 내부 스크롤 컨테이너 검출(감사 #6), 전체 시간 예산, 탭 정리는 finally.
const T = __URL__;
const [THEME, W, H] = __COMBO__;
const KEY = THEME + '_' + W;
const BUDGET_MS = 95000;      // repl 제한(120초) 안에서 META를 반드시 출력하도록 남기는 여유
const MAX_SEGS = 60;          // 구간 상한(1280 기준 약 48,000px)
const MAX_REGROW = 10;        // 무한 스크롤 대비 재측정 상한
const t0 = Date.now(), meta = {};
let vp = null;
try {
  vp = await openTab(T);
  meta[KEY] = await vp.evaluate(async ([src, w, h, theme]) => {
    /*__FORCE_THEME__*/
    const within = (p, ms, tag) => Promise.race([p, new Promise((_, bad) => setTimeout(() => bad(new Error(tag)), ms))]);
    if (innerWidth < w || innerHeight < h) return { error: 'VIEWPORT_TOO_SMALL', iw: innerWidth, ih: innerHeight };
    document.head.innerHTML = ''; document.body.style.cssText = 'margin:0'; document.body.innerHTML = '';
    const f = Object.assign(document.createElement('iframe'), { width: w, height: h, id: 'cap' });
    f.style.cssText = 'border:0;display:block';
    const ok = new Promise(r => f.onload = r); f.src = src; document.body.appendChild(f);
    try { await within(ok, 15000, 'TIMEOUT_IFRAME_LOAD'); } catch (e) { return { error: e.message }; }
    await new Promise(r => setTimeout(r, 600));
    let doc;
    try { doc = f.contentDocument; } catch (e) { doc = null; }
    if (!doc || !doc.body || doc.location.href === 'about:blank') return { error: 'FRAME_BLOCKED' };  // X-Frame-Options·frame-ancestors
    try { await within(doc.fonts.ready, 3000, 'FONTS'); } catch (e) { /* 웹폰트가 늦으면 3초 뒤 그대로 진행 */ }
    const th = forceTheme(doc, theme);
    doc.documentElement.style.scrollBehavior = 'auto';
    doc.documentElement.style.scrollbarWidth = 'none';   // 구간마다 다른 위치로 찍히는 스크롤바 잡음 제거
    await new Promise(r => setTimeout(r, 200));
    const d = doc.documentElement, cw = f.contentWindow;
    // 앱 셸: 문서 대신 화면 절반 이상 크기의 내부 요소가 스크롤하면 그 안의 숨은 내용은 찍히지 않는다(감사 #6).
    // body의 overflow는 html이 두 축 모두 visible일 때 뷰포트로 넘어가므로(CSS 명세) 그때 body는 제외한다.
    const hs = cw.getComputedStyle(d), bodyToViewport = hs.overflowX === 'visible' && hs.overflowY === 'visible';
    // 문서 자체가 스크롤되는 페이지의 큰 내부 스크롤 상자(코드 블록·약관·채팅 로그)는 사용자에게도 그렇게 보이므로
    // 메모(innerScrollNote)만 남기고, 문서가 스크롤되지 않는 앱 셸일 때만 불완전으로 본다(검토 회귀: 영구 rc=1).
    let innerScroll = null, innerScrollNote = null;
    const docScrolls = d.scrollHeight > cw.innerHeight + 8;
    for (const el of [doc.body, ...doc.body.querySelectorAll('*')]) {
      if (el === doc.body && bodyToViewport) continue;
      if (!/^(auto|scroll|overlay)$/.test(cw.getComputedStyle(el).overflowY)) continue;
      const hidden = el.scrollHeight - el.clientHeight;
      if (el.clientHeight >= h / 2 && el.clientWidth >= w / 2 && hidden > 8) {
        const found = { el: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.classList.length ? '.' + [...el.classList].slice(0, 3).join('.') : ''), hidden };
        if (docScrolls) innerScrollNote = innerScrollNote || found; else { innerScroll = found; break; }
      }
    }
    return { ...th, innerScroll, innerScrollNote, iw: cw.innerWidth, sw: d.scrollWidth, overflowX: d.scrollWidth > cw.innerWidth,
             fullH: d.scrollHeight, bg: getComputedStyle(doc.body).backgroundColor,
             system: matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light' };
  }, [T, W, H, THEME]);
  if (meta[KEY].error) console.log('SKIP ' + KEY + ' ' + meta[KEY].error);
  else {
    const m = meta[KEY], ys = []; let regrow = 0, capped = false;
    m.unsettled = 0;
    for (let i = 0; ; i++) {
      if (i >= MAX_SEGS) { m.cut = 'SEGMENT_CAP'; break; }
      if (Date.now() - t0 > BUDGET_MS) { m.cut = 'BUDGET'; break; }
      const st = await vp.evaluate(async ([target, first]) => {
        const cw = document.getElementById('cap').contentWindow, d = cw.document;
        const sleep = (ms) => new Promise(r => setTimeout(r, Math.max(0, ms)));
        if (!first) for (const el of d.querySelectorAll('[data-cap-seen]')) el.style.visibility = 'hidden';
        cw.scrollTo(0, target);
        let last = -1;
        for (let k = 0; k < 20 && cw.scrollY !== last; k++) { last = cw.scrollY; await sleep(50); }
        await sleep(150);
        // 이 구간에 보이는 이미지 로드·디코드(최대 2초)와 유한 애니메이션·전환 완료(최대 1.5초)를 기다린다(감사 #5).
        // 무한 반복 애니메이션은 끝나지 않으므로 기다리지 않는다. 시간 안에 못 끝난 개수는 pend로 돌려준다.
        const onScreen = (el) => { if (!el || !el.getBoundingClientRect) return true; const r = el.getBoundingClientRect(); return r.bottom > 0 && r.top < cw.innerHeight && r.right > 0 && r.left < cw.innerWidth; };   // 가로 경계 포함(codex 최종 게이트)
        const imgs = [...d.images].filter(im => !im.complete && onScreen(im));
        if (imgs.length) await Promise.race([Promise.all(imgs.map(im => im.decode().catch(() => {}))), sleep(2000)]);
        const running = () => d.getAnimations().filter(a => a.playState === 'running' && a.effect
          && Number.isFinite(a.effect.getComputedTiming().endTime) && onScreen(a.effect.target));
        const end = Date.now() + 1500;
        for (let run = running(); run.length && Date.now() < end; run = running())
          await Promise.race([Promise.all(run.map(a => a.finished.catch(() => {}))), sleep(end - Date.now())]);
        const pend = running().length + [...d.images].filter(im => !im.complete && onScreen(im)).length;
        return { y: cw.scrollY, fullH: d.documentElement.scrollHeight, pend };
      }, [ys.length ? ys[ys.length - 1] + H : 0, i === 0]);   // 직전 구간이 실제로 찍힌 위치 바로 다음 — 끝에서 당겨진 뒤 문서가 늘어도 빈 띠가 없다
      if (i > 0 && st.y <= ys[ys.length - 1] && st.y + H < st.fullH) { m.cut = 'NO_SCROLL_PROGRESS'; break; }   // 스크롤이 막힌 페이지
      let y = st.y;
      ys.push(y);
      if (y + H >= st.fullH) {
        // 하단: 높이가 750ms 동안 그대로이고 보이는 이미지가 다 로드될 때까지(최대 4초) 기다린다
        const settle = await vp.evaluate(async () => {
          const cw = document.getElementById('cap').contentWindow, d = cw.document;
          let hgt = d.documentElement.scrollHeight, still = 0;
          for (let k = 0; k < 16; k++) {
            await new Promise(r => setTimeout(r, 250));
            const n = d.documentElement.scrollHeight;
            // 보이는 이미지만 센다 — display:none·가로 밖 lazy 이미지는 끝내 오지 않아 영구 미안정이 됐다(2026-10-02 최종 검토)
            const pending = [...d.images].some(im => { if (im.complete) return false; const r = im.getBoundingClientRect();
              return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < cw.innerHeight && r.right > 0 && r.left < cw.innerWidth; });
            if (n === hgt && !pending) { if (++still >= 3) break; } else { still = 0; hgt = n; }
          }
          // 미정착 개수는 정착 대기 뒤에 다시 센다 — 대기 중 다 로드된 이미지를 '못 끝남'으로 세지 않게(검토 회귀)
          const onScreen = (el) => { if (!el || !el.getBoundingClientRect) return true; const r = el.getBoundingClientRect(); return r.bottom > 0 && r.top < cw.innerHeight && r.right > 0 && r.left < cw.innerWidth; };   // 가로 경계 포함(codex 최종 게이트)
          const pend = d.getAnimations().filter(a => a.playState === 'running' && a.effect
            && Number.isFinite(a.effect.getComputedTiming().endTime) && onScreen(a.effect.target)).length
            + [...d.images].filter(im => !im.complete && onScreen(im)).length;
          return { fullH: d.documentElement.scrollHeight, stable: still >= 3, y: cw.scrollY, pend };
        });
        st.pend = settle.pend;
        m.stable = settle.stable;
        if (settle.fullH > st.fullH) {                         // 지연 로딩으로 늘어났다 → 이 구간은 버리고 이어서 찍는다
          if (regrow < MAX_REGROW) { regrow++; ys.pop(); i--; m.fullH = settle.fullH; continue; }
          capped = true;                                       // 상한을 넘어 또 늘어남 = 끝없이 늘어나는 페이지(감사 #10)
        }
        m.fullH = settle.fullH;
        // 문서가 줄면 브라우저가 스크롤을 당긴다 — 실제로 찍힐 위치로 기록을 고친다(감사 #11)
        y = settle.y; ys[ys.length - 1] = y;
        // 직전 구간보다 위로 당겨졌다 = 이미 찍은 구간에 지금은 없는 내용이 들어 있다 → 이어 붙일 수 없다
        if (ys.length > 1 && y < ys[ys.length - 2]) { ys.pop(); m.cut = 'SHRANK'; break; }
        if (capped) m.stable = false;
      } else m.fullH = st.fullH;
      m.unsettled += st.pend;
      const b = await vp.screenshot({ type: 'png', clip: { x: 0, y: 0, width: W, height: H } });
      console.log(`SEG_${KEY}_${i}_START`); console.log(Buffer.from(b).toString('base64')); console.log(`SEG_${KEY}_${i}_END`);
      // 스크린샷이 성공한 뒤에만 '찍힘' 표시 — 버린 구간의 sticky가 숨겨져 사라지는 경로 차단(codex 3차 #3).
      // 화면 전체(가로·세로 90% 이상)를 덮는 fixed 레이어(grain·그라디언트 배경 등)는 모든 구간에 보여야 하므로 표시하지 않는다(감사 #4).
      await vp.evaluate(() => {
        const cw = document.getElementById('cap').contentWindow, d = cw.document;
        for (const el of d.querySelectorAll('body *')) {
          const p = cw.getComputedStyle(el).position, r = el.getBoundingClientRect();
          const cover = r.width >= cw.innerWidth * 0.9 && r.height >= cw.innerHeight * 0.9;
          if ((p === 'fixed' || p === 'sticky') && !cover && r.top >= 0 && r.bottom <= cw.innerHeight && r.left >= 0 && r.right <= cw.innerWidth && r.width > 0 && r.height > 0
              && (!el.checkVisibility || el.checkVisibility({ opacityProperty: true, visibilityProperty: true }))) el.setAttribute('data-cap-seen', '');   // 투명·숨김이면 아직 안 찍힌 것(codex 3차)   // 촬영 영역(가로·세로)에 완전히 든 것만(codex 2차 게이트)
        }
      });
      if (capped || y + H >= m.fullH) break;
    }
    m.ys = ys;
  }
} catch (e) {                                                  // REPL 수준 예외(탭 열기·CDP 시간 초과 등)도 결과로 남긴다
  meta[KEY] = { ...(meta[KEY] || {}), error: 'REPL_ERROR ' + String(e && e.message || e).slice(0, 120) };
} finally {
  console.log('META ' + JSON.stringify(meta));
  if (vp) await closeTab(vp);
}
