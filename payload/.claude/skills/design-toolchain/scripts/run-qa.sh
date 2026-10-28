#!/bin/bash
# 디자인 QA 한 번에 실행 (aside-browser 전용, 2026-09-28 실측 레시피 + codex 교차검수 1·2차 + 2026-09-30 감사 반영)
# 사용: run-qa.sh <URL> <출력폴더> [태그=before]
#   1) 375·1280 × 다크·라이트(강제) 전체 페이지 구간 캡처 → 겹침 제거 후 이어 붙이기(높이 검산)
#   2) 페이지 안 Web Vitals(LCP·CLS 세션 윈도우) + axe-core WCAG 2.2 AA(창 폭·375 × 다크·라이트)
#   조합·모드마다 aside repl을 따로 부른다(repl 1회 120초 제한 — 감사 #7).
# 종료코드: 0 = 모든 조합 완전 검사 + axe 위반 0 + 수동 확인 항목 0
#           1 = 하나라도 누락·건너뜀·시간 초과·검산 실패(불완전 — 통과로 보지 않는다)
#           2 = 완전 검사에서 axe 위반 발견
#           3 = 완전 검사·위반 0이지만 자동 판정 불가 항목 있음(axe 보류·테마 전환 미확인·미처리 테마 조건·
#               미정착 구간) — 출력된 목록을 사람이 PNG·페이지로 확인한 뒤에만 통과로 본다
# 전제: Aside 앱 실행 중, ImageMagick(magick), 대상 URL 응답 200. 결과 PNG는 반드시 직접 열어 눈으로 확인한다.
set -uo pipefail
URL="${1:?URL 필요}"; OUT="${2:?출력 폴더 필요}"; TAG="${3:-before}"
DIR="$(cd "$(dirname "$0")" && pwd)"
[[ "$URL" =~ ^https?://[^[:space:]\'\"\\]+$ ]] || { echo "URL 형식 거부(http/https, 공백·따옴표·역슬래시 불가): $URL"; exit 1; }
[[ "$TAG" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "태그는 영숫자·-·_ 만: $TAG"; exit 1; }
command -v magick >/dev/null || { echo "ImageMagick(magick)이 없다 — stitch.py 이어 붙이기에 필요(설치는 사용자 판단)"; exit 1; }
mkdir -p "$OUT" || exit 1
pgrep -f Aside.app >/dev/null || { echo "Aside 앱이 실행 중이 아니다 — 사용자에게 실행 요청"; exit 1; }
# -g: URL의 []{}를 글로빙하지 않는다(요청 1건만 — 감사 #26), --proto: http/https 외 프로토콜 금지
code=$(curl -g -L --max-redirs 5 --proto =http,https --proto-redir =http,https -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 15 "$URL") || true
[ "$code" = "200" ] || { echo "대상 응답이 200이 아니다: $code"; exit 1; }

# 자리표시자(URL·조합·테마 함수) 치환은 render.py 단일 정본 — clone-site capture-contract §8도 같은 파일을 쓴다.
render() { python3 "$DIR/render.py" "$1" "$URL" "$2"; }

RAW="$OUT/capture-$TAG.raw.txt"; : > "$RAW"
for combo in '["dark",375,812]' '["dark",1280,800]' '["light",375,812]' '["light",1280,800]'; do
  aside repl "$(render "$DIR/capture.js" "$combo")" >> "$RAW" 2>&1
done
python3 "$DIR/stitch.py" "$RAW" "$OUT" "$TAG"; cap_rc=$?
if [ "$cap_rc" -eq 0 ] || [ "$cap_rc" -eq 3 ]; then rm -f "$RAW"
else
  echo "캡처 불완전 — 원본 로그 보존: $RAW"
  # 구간 base64 본문을 빼고 오류 줄만, 줄 길이 제한(감사 #8)
  awk '/^SEG_.*_START$/{s=1;next} /^SEG_.*_END$/{s=0;next} !s' "$RAW" | grep -iE "error|^SKIP" | cut -c1-300 | head -5
fi

MRAW="$OUT/measure-$TAG.txt"; : > "$MRAW"
for mode in '{"vitals":true}' '{"theme":"dark","width":null}' '{"theme":"dark","width":375}' '{"theme":"light","width":null}' '{"theme":"light","width":375}'; do
  aside repl "$(render "$DIR/measure.js" "$mode")" >> "$MRAW" 2>&1
done
python3 - "$MRAW" <<'PY'
import json, re, sys
raw = open(sys.argv[1], encoding="utf-8").read()

def lines(tag):
    out = []
    for s in re.findall(rf"^{tag} (.*)$", raw, re.M):
        try:
            out.append(json.loads(s))
        except json.JSONDecodeError:
            pass
    return out

vs = lines("VITALS"); vit = vs[0] if vs else None
axe = {}
for part in lines("AXE"):
    if isinstance(part, dict):
        axe.update(part)
incomplete = manual = False
need = ("lcp", "cls", "status", "route", "title", "width", "height")
if not isinstance(vit, dict) or any(vit.get(k) is None for k in need) or vit.get("status") != 200:
    print("VITALS 불완전:", vit, *[l[:300] for l in raw.splitlines() if "rror" in l][:2]); incomplete = True
else:
    print("VITALS", json.dumps(vit, ensure_ascii=False) + ("  (provisional: 관찰 한계 도달)" if vit.get("provisional") else ""))
bad = 0
for k in ("dark_window", "dark_375", "light_window", "light_375"):
    r = axe.get(k)
    if not r or "error" in r:
        print(f"AXE {k}: 불완전 — {(r or {}).get('error', '결과 없음')}"); incomplete = True; continue
    bad += len(r["violations"])
    held = r["incomplete"]                               # axe가 판정하지 못한 항목 — 손으로 확인(gap #11)
    extra = ""
    if r.get("unsupported"):
        extra += f" | not·or 테마 조건 {r['unsupported']}개 미처리(수동 확인)"; manual = True
    if r.get("blockedSheets"):
        extra += f" | 읽지 못한 교차 출처 시트 {r['blockedSheets']}개(시트 media 조건만 강제)"
    if held:
        manual = True
    print(f"AXE {k}: 위반 {len(r['violations'])} 통과 {r['passes']} 보류 {len(held)}종·노드 {sum(x['nodes'] for x in held)}개"
          f" 테마강제 {r['themeRules']} bg {r['bg']}{extra}"
          + "".join(f"\n   - {x['id']} ({x['impact']}) ×{x['nodes']} {x['target']}" for x in r["violations"])
          + "".join(f"\n   ? 보류 {x['id']} ×{x['nodes']}" for x in held))
sys.exit(1 if incomplete else (2 if bad else (3 if manual else 0)))
PY
meas_rc=$?
# 측정 파서가 0·2·3 밖의 코드(시그널 종료 등)로 끝나도 불완전으로 본다(2026-10-02 최종 검토)
if { [ "$cap_rc" -ne 0 ] && [ "$cap_rc" -ne 3 ]; } || { [ "$meas_rc" -ne 0 ] && [ "$meas_rc" -ne 2 ] && [ "$meas_rc" -ne 3 ]; }; then echo "결과: 불완전(rc=1) — 통과로 보지 않는다"; exit 1; fi
[ "$meas_rc" -eq 2 ] && { echo "결과: axe 위반 있음(rc=2)"; exit 2; }
if [ "$cap_rc" -eq 3 ] || [ "$meas_rc" -eq 3 ]; then echo "결과: 자동 검사 위반 0 · 수동 확인 필요(rc=3) — 위 목록을 확인한 뒤에만 통과"; exit 3; fi
echo "결과: 완전 검사·위반 0(rc=0)"; exit 0
