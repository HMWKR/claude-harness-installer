// 테마 강제(페이지 문맥에서 실행) — run-qa.sh가 capture.js·measure.js의 테마 함수 자리표시자에 이 함수를 인라인한다.
// prefers-color-scheme 조건만 참/거짓으로 평가하고 다른 조건(min-width 등)은 보존한다(codex 2차 #5).
// @import 시트(그 import 자체의 media 조건 포함 — 3차 #4)와 @supports·@layer·@media 그룹 규칙 안쪽까지 재귀한다(2차 #4).
// 한 조건에 테마 조건이 여러 번 나와도 전부 평가한다(3차 #5). not·or 조건은 unsupported로 센다.
// 시트 자체 media·<picture> source·color-scheme(light dark)도 강제한다(2026-09-30 감사 #1). themeRules = 강제한 지점 수.
function forceTheme(doc, want) {
  const RXG = /\(\s*prefers-color-scheme\s*:\s*(dark|light)\s*\)/gi;
  const out = { themeRules: 0, unsupported: 0, blockedSheets: 0 };
  // 미디어 조건 하나 → { keep, text, touched, bad }
  const rewriteMedium = (m) => {
    const hits = [...m.matchAll(RXG)];
    if (!hits.length) return { keep: true, text: m, touched: false };
    if (/\bnot\b|\bor\b/i.test(m)) return { keep: true, text: m, touched: false, bad: true };
    if (hits.some(h => h[1].toLowerCase() !== want)) return { keep: false, touched: true };   // 반대 테마 분기
    const rest = m.replace(RXG, '').split(/\band\b/i).map(s => s.trim()).filter(Boolean).join(' and ');
    return { keep: true, text: rest || 'all', touched: true };
  };
  // MediaList 전체 → { changed, text(null = 전부 반대 테마라 비활성), bad }
  const rewriteList = (media) => {
    const kept = []; let changed = false, bad = false;
    for (const m of Array.from(media)) {
      const r = rewriteMedium(m);
      bad = bad || !!r.bad; changed = changed || r.touched;
      if (r.keep) kept.push(r.text);
    }
    return { changed, bad, text: kept.length ? kept.join(', ') : null };
  };
  const walk = (list, owner) => {
    for (let i = list.length - 1; i >= 0; i--) {
      const r = list[i];
      if (r.styleSheet) {                                   // @import: 자체 media 조건부터 변환
        if (r.media && r.media.length) {
          const w = rewriteList(r.media);
          if (w.bad) out.unsupported++;
          else if (w.changed) { r.media.mediaText = w.text === null ? 'not all' : w.text; out.themeRules++; }
        }
        let rr; try { rr = r.styleSheet.cssRules; } catch (e) { out.blockedSheets++; continue; }
        walk(rr, r.styleSheet); continue;
      }
      if (r.media && r.cssRules) {
        const w = rewriteList(r.media);
        if (w.bad) out.unsupported++;
        else if (w.changed) {
          const inner = Array.from(r.cssRules).map(x => x.cssText).join('\n');
          owner.deleteRule(i);
          if (w.text !== null) {
            owner.insertRule('@media ' + w.text + ' {\n' + inner + '\n}', i);
            walk(owner.cssRules[i].cssRules, owner.cssRules[i]);   // 안쪽에 중첩된 테마 조건
          }
          out.themeRules++;
          continue;
        }
      }
      if (r.cssRules) walk(r.cssRules, r);                  // @supports·@layer·일반 @media 재귀
    }
  };
  for (const s of doc.styleSheets) {
    // 시트 자체의 media(<link media>·<style media>) — 교차 출처 시트도 media는 읽고 바꿀 수 있다(감사 #1)
    if (s.media && s.media.length) {
      const w = rewriteList(s.media);
      if (w.bad) out.unsupported++;
      else if (w.changed) {
        s.media.mediaText = w.text === null ? 'not all' : w.text; out.themeRules++;
        if (w.text === null) continue;                     // 반대 테마 시트는 통째로 꺼졌다
      }
    }
    let rules; try { rules = s.cssRules; } catch (e) { out.blockedSheets++; continue; }   // 교차 출처 시트
    walk(rules, s);
  }
  // <picture><source media="(prefers-color-scheme: …)"> — 속성 문자열을 MediaList로 파싱해 같은 규칙으로 바꾼다
  for (const src of doc.querySelectorAll('picture > source[media]')) {
    const w = rewriteList(new CSSStyleSheet({ media: src.media }).media);
    if (w.bad) out.unsupported++;
    else if (w.changed) { src.media = w.text === null ? 'not all' : w.text; out.themeRules++; }
  }
  // color-scheme가 light·dark 둘 다 허용하는 요소(light-dark()·폼 컨트롤·캔버스 색이 시스템을 따른다)는
  // 원하는 테마 하나로 고정한다. 한쪽만 허용하는 요소·normal은 실제 브라우저처럼 그대로 둔다.
  const win = doc.defaultView, root = doc.documentElement;
  const both = (v) => /\blight\b/.test(v) && /\bdark\b/.test(v);
  const meta = doc.querySelector('meta[name="color-scheme"]');
  if (win.getComputedStyle(root).colorScheme === 'normal' && meta && both(meta.content)) {
    root.style.colorScheme = want; out.themeRules++;
  }
  for (const el of [root, ...doc.querySelectorAll('body, body *')]) {
    if (both(win.getComputedStyle(el).colorScheme)) { el.style.colorScheme = want; out.themeRules++; }
  }
  return out;
}
