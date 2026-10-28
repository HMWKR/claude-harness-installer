# 실동작 검증 게이트 (Live Feature Verify) — feature 완료 정의

> 프론트/백엔드 **기능 구현**의 "완료"는 코드 작성·요소 존재가 아니라 **브라우저로 실제 동작이 검증된 상태**다. 표면 PASS·임의 PASS 금지. (근거: live-verify-loop 메타학습 R54 code≠live, R77 surface≠functional, R55 테스트러너가 아니라 브라우저를 직접 몰아서.)

## 발동 트리거
- UI 컴포넌트·버튼·폼·모달·라우팅·상태변경 구현/수정
- API·엔드포인트·서버 핸들러·DB 연동 기능 구현/수정
- "완료"·"다음 작업으로" 선언 **직전** (항상)

## 기본 도구 (이 영역의 정본)
- **`aside repl`이 기본 도구다** (전역 기본과 동일 — uncompromising-rigor §1이 2026-09-05부터 Aside 우선). 검증은 **결정적 레인(`repl`)으로만** 한다 — `aside "<작업>"` 에이전트 위임은 탐색용이고, 그 자연어 요약을 PASS 증거로 삼지 않는다.
- Playwright MCP·Chrome MCP는 deny로 차단되어 **툴이 존재하지 않는다**. Aside로 못 하는 검증은 §1-c대로 보고한다 — 대체 브라우저를 찾지 않는다.
- 검증 실행 절차는 `live-verify-loop` 또는 `webapp-testing` 스킬에 위임한다(중복 신설 금지) — 이 규약은 게이트 기준만 강제. **단 그 스킬들이 Playwright·Chrome MCP 호출이나 자체 브라우저 스크립트(webapp-testing의 native Python Playwright 등) 작성을 지시하면 무시하고 `aside repl`로 치환한다**(MCP 툴은 deny로 없고, 자체 브라우저를 띄우는 스크립트는 rigor §1 진입 절차가 금지한다 — 모듈 설치 여부와 무관). 절차 순서는 스킬을 그대로 따른다.

## 검증 3계층 — 전부 통과해야 PASS (임의 판단 금지)
1. **상호작용**: 요소가 "있다"가 아니라 실제 클릭/입력/제출이 **실행**됨 — `snapshot(page)`로 ref를 얻고 `page.locator('e12').click()`으로 직접 조작(CSS 셀렉터 아님).
2. **기능 결과**: 의도한 상태변화 확인 — UI 반영 + 네트워크 2xx·응답 본문 + 데이터/DB 반영 + 라우팅. 증거는 `snapshot(page).diff`(UI 변화) + 인페이지 계측(네트워크·콘솔) + `performance.getEntriesByType('navigation')[0].responseStatus`(HTTP 상태)로 확보한다.
3. **케이스 전수**: 정상 경로 + 실패·엣지·경계(빈 입력·잘못된 값·권한 거부·에러 응답).

## 증거 캡처 — 고정 절차 (2026-09-05 실측)

**네트워크·콘솔**: Aside는 CDP 도메인을 전부 차단하므로(`Network.enable` → `wasn't found`) 브라우저 도구가 자동으로 모아주지 않는다. **네비게이션 직후 `page.evaluate()`로 계측을 직접 주입해야 하고, 주입을 빼먹으면 증거가 0건이 된다**:

```js
await page.evaluate(() => {
  window.__ev = { console: [], net: [], errors: [] };
  ['log','warn','error','info'].forEach(k => { const o = console[k];
    console[k] = function(){ window.__ev.console.push(k+': '+Array.from(arguments).join(' ')); return o.apply(console, arguments); }; });
  addEventListener('error', e => window.__ev.errors.push('error: ' + (e.message || (e.target && e.target.src) || e.type)), true);
  addEventListener('unhandledrejection', e => window.__ev.errors.push('unhandledrejection: ' + String(e.reason)));
  const of = window.fetch;
  window.fetch = function(){ const a = arguments;
    return of.apply(this, a).then(r => { const rec = {url:String(a[0]), status:r.status, ok:r.ok}; window.__ev.net.push(rec);
      r.clone().text().then(t => { rec.body = t.slice(0, 500); }).catch(() => {}); return r; }); };
  const xo = XMLHttpRequest.prototype.open, xs = XMLHttpRequest.prototype.send;   // axios 기본값은 XHR이다
  XMLHttpRequest.prototype.open = function(m, u){ this.__u = u; return xo.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function(){ this.addEventListener('loadend', () => window.__ev.net.push({url:String(this.__u), status:this.status, xhr:true,
    body:String(this.responseText || '').slice(0, 500)})); return xs.apply(this, arguments); };
  new PerformanceObserver(l => l.getEntries().forEach(e => window.__ev.net.push({res:e.name, type:e.initiatorType})))
    .observe({ type:'resource', buffered:true });
});
// 상호작용 후
const ev = await page.evaluate(() => window.__ev);
```

계측은 페이지 네비게이션마다 날아간다 — **이동할 때마다 다시 주입한다.** 주입 전(로드 중)에 난 오류는 잡히지 않으므로, 로드 오류가 의심되면 주입 뒤 같은 동작을 다시 일으켜 확인한다.

**시각 증거**: `await page.screenshot({type:'png'})`는 Buffer를 돌려준다. `path` 인자는 Aside 세션
디렉토리로 샌드박스되어 **작업 디렉토리로 파일이 나오지 않는다** — 로컬 증거파일은 base64를
stdout에 찍고 셸에서 되돌려 저장한다:

```bash
aside repl "... console.log('B64_START'); console.log(Buffer.from(await page.screenshot({type:'png'})).toString('base64')); console.log('B64_END')" > raw.txt
sed -n '/^B64_START$/,/^B64_END$/p' raw.txt | sed '1d;$d' | tr -d '\n' | base64 -d > evidence.png
file evidence.png   # PNG image data 확인 — 0바이트/비PNG면 증거 아님
```

저장 후 `file`로 실제 PNG인지 확인하고, 시각 판정 항목이면 이미지를 **직접 읽어 눈으로 대조**한다.
저장했다는 사실만으로 시각 항목을 PASS 처리하지 않는다.

## 완료 규칙 (엄격)
- 각 항목 PASS/FAIL을 step-by-step 기록한다. **FAIL이 1개라도 있으면 미완료** → 고치고 재검증한다.
- "완료" 선언에는 **`aside repl` 실행 증거(스냅샷 diff/네트워크/콘솔/응답/스크린샷) ≥1개를 첨부**한다. 증거 없는 완료는 완료가 아니다. Aside 에이전트 레인의 자연어 답변은 증거로 치지 않는다.
- 발견된 미동작은 결함으로 등재한다 — 강등 불가(`uncompromising-rigor §2` 정합).
- 서버 미기동·환경 미비로 실검증이 불가능하면: 먼저 **스스로 해소를 시도**한다(dev 서버 기동, `run` 스킬 등 가역 범위 — 2026-07-02 Fable 정합). 그래도 불가하면 **추측 PASS 금지** → 차단 사유를 보고한다.
