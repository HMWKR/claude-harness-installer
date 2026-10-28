// page-audit.js — 디자인 기준을 숫자로 재는 페이지 안 측정 함수.
// 브라우저 도구의 evaluate에 이 파일 내용을 그대로 넘긴다(식 하나 = Promise<결과>). 이 하네스에서는 `dloop.py measure --kind audit`이 대신 돌린다.
// 폭은 측정하는 창(또는 같은 출처 iframe)의 innerWidth다. 판정 비교용 값은 반올림하지 않는다.
(async () => {
  if (document.fonts && document.fonts.ready) await document.fonts.ready;   // 늦게 붙는 글꼴은 줄 수·폭을 바꾼다
  const W = innerWidth;
  const all = [...document.querySelectorAll('body *')];
  const visible = el => {
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return false;
    const s = getComputedStyle(el);
    return s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0;
  };

  // 어떤 색 표기든 sRGB로 바꾼다(oklch·color() 포함) — 1×1 캔버스에 칠해 읽는다
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', { willReadFrequently: true });
  const rgba = c => {
    cx.clearRect(0, 0, 1, 1); cx.fillStyle = 'rgba(0,0,0,0)'; cx.fillStyle = c; cx.fillRect(0, 0, 1, 1);
    const d = cx.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2], d[3] / 255];
  };
  const over = (top, under) => { const a = top[3]; return [0, 1, 2].map(i => top[i] * a + under[i] * (1 - a)).concat(1); };
  const lum = c => {
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  // 불투명해질 때까지 조상 배경을 쌓는다. 그림·그라디언트·투명도·필터·혼합을 만나면 판정 불가(null)
  const background = el => {
    const layers = [];
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const s = getComputedStyle(n);
      if (parseFloat(s.opacity) < 1 || (s.filter && s.filter !== 'none') || (s.mixBlendMode && s.mixBlendMode !== 'normal')
          || (s.backdropFilter && s.backdropFilter !== 'none')) return null;
      if (s.backgroundImage && s.backgroundImage !== 'none') return null;
      const c = rgba(s.backgroundColor);
      if (c[3] > 0) { layers.push(c); if (c[3] >= 1) break; }
    }
    let base = [255, 255, 255, 1];
    for (let i = layers.length - 1; i >= 0; i--) base = over(layers[i], base);
    return base;
  };
  const ownText = el => [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
  const LARGE_BOLD = 14 * 96 / 72;   // 14pt = 18.666…px (WCAG 큰 글자: 18pt 또는 굵은 14pt)

  // ---- 글자·대비(직접 글자를 가진 요소마다)
  const texts = all.filter(el => ownText(el).length > 0 && visible(el));
  const sizes = new Set(), families = new Set();
  let normalMin = Infinity, largeMin = Infinity, failNormal = 0, failLarge = 0, unknownBg = 0;
  const worst = [];
  for (const el of texts) {
    const s = getComputedStyle(el);
    const px = parseFloat(s.fontSize);
    sizes.add(Math.round(px * 2) / 2);
    families.add((s.fontFamily.split(',')[0] || '').replace(/["']/g, '').trim().toLowerCase());
    const bg = background(el);
    if (!bg) { unknownBg++; continue; }
    const large = px >= 24 || (px >= LARGE_BOLD && parseInt(s.fontWeight, 10) >= 700);
    const r = ratio(over(rgba(s.color), bg), bg);
    if (large) { largeMin = Math.min(largeMin, r); if (r < 3) failLarge++; }
    else { normalMin = Math.min(normalMin, r); if (r < 4.5) failNormal++; }
    if (r < 4.5 && worst.length < 8) worst.push({ text: ownText(el).slice(0, 40), ratio: r, px });
  }

  // ---- 본문(문단 전체 글자 — 안쪽 span에 글자가 있어도 센다)
  let bodyMin = Infinity, lhMin = Infinity, measureLatin = 0, measureCjk = 0;
  // 문단 태그가 아니어도(div·span·td 등) 직접 글자가 40자 이상이면 본문으로 본다 — 마크업만 바꿔 '해당 없음'이 되지 않게. 제목은 뺀다
  const bodyEls = new Set(document.querySelectorAll('p, li, dd, blockquote, figcaption'));
  for (const el of all) if (ownText(el).replace(/\s+/g, ' ').length >= 40) bodyEls.add(el);
  for (const el of bodyEls) {
    if (!visible(el) || el.closest('h1, h2, h3, h4, h5, h6, [role=heading]')) continue;
    const t = el.textContent.replace(/\s+/g, ' ').trim();
    if (t.length < 40) continue;                         // 40자 이상 = 본문(짧은 캡션·메타 제외)
    const s = getComputedStyle(el);
    const px = parseFloat(s.fontSize);
    bodyMin = Math.min(bodyMin, px);
    const lh = s.lineHeight === 'normal' ? px * 1.2 : parseFloat(s.lineHeight);
    lhMin = Math.min(lhMin, lh / px);
    // 줄 수 = 글자 상자 top을 줄 간격 절반 이내로 묶은 무리 수(위첨자·인라인 요소가 줄을 늘리지 않게)
    const rg = document.createRange(); rg.selectNodeContents(el);
    const tops = [...rg.getClientRects()].filter(r => r.height > 0).map(r => r.top).sort((a, b) => a - b);
    let lines = 0, last = -Infinity;
    for (const tp of tops) { if (tp - last > lh * 0.5) { lines++; last = tp; } }
    if (lines >= 2) {
      const cjk = (t.match(/[ㄱ-ㆎ가-힣぀-ヿ一-鿿]/g) || []).length / t.length > 0.3;
      const em = (el.clientWidth - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight)) / px;
      if (cjk) measureCjk = Math.max(measureCjk, em); else measureLatin = Math.max(measureLatin, em);
    }
  }

  // ---- 누를 수 있는 것의 크기. 예외는 문장 속 링크만(보수적 자체 규칙 — WCAG의 간격 예외는 적용하지 않는다)
  const interactive = [...document.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, [role=button], [role=link], [tabindex]:not([tabindex="-1"])')].filter(visible);
  const inSentence = el => {
    if (el.tagName !== 'A') return false;
    const block = el.closest('p, li, dd, td');
    if (!block) return false;
    if (block.tagName === 'P') return true;
    const linkText = [...block.querySelectorAll('a')].reduce((n, a) => n + a.textContent.trim().length, 0);
    return block.textContent.trim().length - linkText >= 20;   // 링크 말고도 20자 이상 문장이 있을 때만
  };
  let small24 = 0, button44 = 0; const smallSamples = [];
  for (const el of interactive) {
    if (inSentence(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 24 || r.height < 24) { small24++; if (smallSamples.length < 8) smallSamples.push({ tag: el.tagName, text: (el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 30), w: Math.round(r.width), h: Math.round(r.height) }); }
    if ((el.tagName === 'BUTTON' || el.getAttribute('role') === 'button') && (r.width < 44 || r.height < 44)) button44++;
  }

  // ---- 그림
  const imgs = [...document.images];
  const raster = imgs.filter(i => i.currentSrc && !/\.svg(\?|#|$)/i.test(i.currentSrc) && i.naturalWidth > 100);
  const imgStats = {
    count: imgs.length,
    broken: imgs.filter(i => i.complete && i.naturalWidth === 0 && i.currentSrc).length,
    alt_missing: imgs.filter(i => !i.hasAttribute('alt')).length,
    no_dimensions: imgs.filter(i => !(i.hasAttribute('width') && i.hasAttribute('height'))).length,
    legacy_format: raster.filter(i => /\.(png|jpe?g|gif)(\?|#|$)/i.test(i.currentSrc)).length,
  };

  // ---- 스타일시트 규칙(다른 출처 시트는 읽을 수 없어 따로 센다)
  // 감속 규칙은 안에 실제 선언이 있어야, 초점 규칙은 보이는 표시(outline·box-shadow·테두리·배경·글자색·밑줄)를 줘야 센다 — 빈 규칙·outline:none은 세지 않는다
  let reducedRule = false, focusRule = false, unreadableSheets = 0;
  const keyframes = {};                                   // 키프레임 이름 → 그 안에서 바뀌는 속성
  const hasDecl = r => !!(r.style && r.style.length) || [...(r.cssRules || [])].some(hasDecl);
  const showsFocus = st => {
    const os = st.getPropertyValue('outline-style').trim(), ow = st.getPropertyValue('outline-width').trim();
    if (os && os !== 'none' && !/^0(px)?$/.test(ow)) return true;
    const bs = st.getPropertyValue('box-shadow').trim();
    if (bs && bs !== 'none') return true;
    return [...st].some(p => /^(border|background|color$|text-decoration|text-underline)/.test(p));
  };
  const walk = rules => { for (const r of rules) {
    if (r.conditionText && /prefers-reduced-motion/.test(r.conditionText) && hasDecl(r)) reducedRule = true;
    if (r.selectorText && /:focus(-visible|-within)?/.test(r.selectorText) && r.style && showsFocus(r.style)) focusRule = true;
    if (r.type === 7 && r.name) { keyframes[r.name] = new Set([...r.cssRules].flatMap(k => [...k.style])); continue; }
    if (r.cssRules) walk(r.cssRules);
  } };
  for (const sh of document.styleSheets) { try { walk(sh.cssRules); } catch (e) { unreadableSheets++; } }
  // 다른 출처 시트를 못 읽었는데 규칙을 못 찾았다면 '없음'이 아니라 '모름'이다(거짓 FAIL 방지 — 같은 출처 빌드에서 다시 잰다)
  const reducedOut = reducedRule || (unreadableSheets ? null : false), focusOut = focusRule || (unreadableSheets ? null : false);
  const animated = all.filter(el => { const s = getComputedStyle(el); return s.animationName !== 'none' || s.transitionDuration.split(',').some(d => parseFloat(d) > 0); });
  // 레이아웃 속성을 움직이는 요소: 키프레임이 그 속성을 바꾸거나, 시간이 0보다 긴 전이가 그 속성(또는 all)에 걸린 것
  const LAYOUT = /^(width|height|min-width|min-height|max-width|max-height|top|left|right|bottom|inset|margin|padding)/;
  const layoutAnim = animated.filter(el => {
    const s = getComputedStyle(el);
    const kf = s.animationName.split(',').map(x => x.trim()).some(n => n !== 'none' && [...(keyframes[n] || [])].some(p => LAYOUT.test(p)));
    const props = s.transitionProperty.split(',').map(x => x.trim()), durs = s.transitionDuration.split(',');
    return kf || props.some((p, i) => parseFloat(durs[i % durs.length]) > 0 && (p === 'all' || LAYOUT.test(p)));
  }).length;

  // ---- 구조·문구
  const heads = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(visible).map(h => +h.tagName[1]);
  let skips = 0; for (let i = 1; i < heads.length; i++) if (heads[i] - heads[i - 1] > 1) skips++;
  const bodyText = document.body.innerText;
  const GENERIC = /^(자세히( 보기)?|더 ?보기|바로 ?가기|클릭|여기|learn more|read more|more|click here|here|details|see more)$/i;
  const genericLinks = interactive.filter(el => GENERIC.test(((el.getAttribute('aria-label') || el.textContent) || '').replace(/\s+/g, ' ').trim())).length;
  const placeholder = (bodyText.match(/lorem ipsum|\bplaceholder\b|\bTODO\b|\bTBD\b|\{\{|\}\}|\bundefined\b|\bNaN\b|\[object Object\]/gi) || []).length;

  // ---- 전송량: 압축 본문 크기 기준(캐시와 무관). 크기를 알 수 없는 자원(다른 출처, Timing-Allow-Origin 없음)이 있으면 값 없음
  const res = performance.getEntriesByType('resource');
  const size = e => e.encodedBodySize || e.transferSize || 0;
  const unknown = e => !size(e) && !e.decodedBodySize && !/^data:/.test(e.name);
  const isJs = e => e.initiatorType === 'script' || /\.m?js(\?|#|$)/i.test(e.name);
  const js = res.filter(isJs);
  const nav = performance.getEntriesByType('navigation')[0];
  const jsKb = js.some(unknown) ? null : js.reduce((a, e) => a + size(e), 0) / 1024;
  const totalKb = res.some(unknown) ? null : (res.reduce((a, e) => a + size(e), 0) + (nav ? size(nav) : 0)) / 1024;

  // ---- LCP·CLS: 지원 여부를 확인하고, 새 항목이 1초 멈출 때까지(최대 4초) 모은다
  const supported = (window.PerformanceObserver && PerformanceObserver.supportedEntryTypes) || [];
  const collect = type => new Promise(done => {
    if (!supported.includes(type)) return done(null);
    const got = []; let quiet;
    const po = new PerformanceObserver(l => { got.push(...l.getEntries()); clearTimeout(quiet); quiet = setTimeout(end, 1000); });
    const end = () => { po.disconnect(); clearTimeout(cap); done(got); };
    const cap = setTimeout(end, 4000);
    po.observe({ type, buffered: true });
    quiet = setTimeout(end, 1000);
  });
  const [lcpE, clsE] = await Promise.all([collect('largest-contentful-paint'), collect('layout-shift')]);
  const lcp = lcpE && lcpE.length ? (lcpE[lcpE.length - 1].renderTime || lcpE[lcpE.length - 1].startTime) : null;
  const lcpLast = lcpE && lcpE.length ? lcpE[lcpE.length - 1] : null;   // 무엇이 LCP인지 남긴다 — 원인을 추측으로 고치지 않게
  const lcpEl = lcpLast && lcpLast.element ? { tag: lcpLast.element.tagName, id: lcpLast.element.id || null, cls: String(lcpLast.element.className || '').slice(0, 60), text: (lcpLast.element.textContent || '').trim().slice(0, 40), url: lcpLast.url || null, size: lcpLast.size } : null;
  let cls = null;
  if (clsE) {                           // 세션 창: 앞 항목과 1초 넘게 떨어지거나 창이 5초를 넘으면 새 창
    cls = 0; let win = 0, start = null, prev = null;
    for (const e of clsE.sort((a, b) => a.startTime - b.startTime)) {
      if (e.hadRecentInput) continue;
      if (start === null || e.startTime - prev > 1000 || e.startTime - start > 5000) { win = 0; start = e.startTime; }
      win += e.value; prev = e.startTime; cls = Math.max(cls, win);
    }
  }

  // ---- 넘침: 문서 폭 넘침 + 루트(html·body)가 잘라 숨긴 내용(글자·그림, 또는 화면보다 넓은 요소).
  // 화면 밖에 통째로 둔 것(숨김 패턴)·fixed·aria-hidden·안쪽 스크롤 상자 안의 것은 세지 않는다
  const clipsX = s => /hidden|clip|auto|scroll/.test(s.overflowX);
  const rootClipped = el => { for (let n = el.parentElement; n && n !== document.body && n !== document.documentElement; n = n.parentElement) if (clipsX(getComputedStyle(n))) return false; return true; };
  let cut = 0; const cutSamples = [];
  for (const el of all) {
    if (!visible(el) || getComputedStyle(el).position === 'fixed' || el.closest('[aria-hidden="true"], [inert]')) continue;
    const r = el.getBoundingClientRect();
    if (r.right <= 0 || r.left >= W) continue;
    if (!(ownText(el).length || /^(IMG|SVG|VIDEO|CANVAS|TABLE|PICTURE|IFRAME)$/i.test(el.tagName) || r.width > W + 1)) continue;
    const amt = Math.max(r.right - W, -r.left);
    if (amt > 1 && rootClipped(el)) {
      cut = Math.max(cut, amt);
      if (cutSamples.length < 5) cutSamples.push({ tag: el.tagName, text: ownText(el).slice(0, 30), left: Math.round(r.left), right: Math.round(r.right) });
    }
  }

  const num = v => (Number.isFinite(v) ? v : null);
  return {
    url: location.href, width: W, at: new Date().toISOString(),
    metrics: {
      'overflow.px': Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth, cut),
      'contrast.normal_min': num(normalMin), 'contrast.large_min': num(largeMin),
      'contrast.fail_normal': failNormal, 'contrast.fail_large': failLarge, 'contrast.unknown_bg': unknownBg,
      'type.body_px_min': num(bodyMin), 'type.size_steps': sizes.size, 'type.families': families.size,
      'type.line_height_min': num(lhMin), 'type.measure_em_latin': measureLatin || null, 'type.measure_em_cjk': measureCjk || null,
      'target.small24': small24, 'target.button_lt44': button44,
      'img.count': imgStats.count, 'img.broken': imgStats.broken, 'img.alt_missing': imgStats.alt_missing,
      'img.no_dimensions': imgStats.no_dimensions, 'img.legacy_format': imgStats.legacy_format,
      'motion.reduced_rule': reducedOut, 'motion.animated': animated.length, 'motion.layout_anim': layoutAnim,
      'focus.rule': focusOut, 'css.unreadable_sheets': unreadableSheets,
      'struct.h1': heads.filter(h => h === 1).length, 'struct.heading_skips': skips,
      'struct.main': document.querySelectorAll('main, [role=main]').length, 'struct.lang': !!document.documentElement.lang,
      'text.placeholder': placeholder, 'text.generic_links': genericLinks, 'dom.nodes': document.getElementsByTagName('*').length,
      'perf.js_kb': jsKb, 'perf.transfer_kb': totalKb, 'perf.lcp_ms': lcp, 'perf.cls': cls,
    },
    samples: { low_contrast: worst, small_targets: smallSamples, overflow_cut: cutSamples, sizes: [...sizes].sort((a, b) => a - b), families: [...families], lcp_element: lcpEl,
               ttfb_ms: nav ? nav.responseStart : null },
  };
})()
