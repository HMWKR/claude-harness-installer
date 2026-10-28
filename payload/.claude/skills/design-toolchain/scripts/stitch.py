#!/usr/bin/env python3
"""capture.js 출력(구간 캡처 base64)을 실제 스크롤 위치 기준으로 겹침을 잘라 이어 붙인다.

사용: stitch.py <raw.txt> <outdir> <tag>
종료코드: 0 = 네 조합(다크·라이트 × 375·1280) 모두 완전
          1 = 하나라도 누락·건너뜀·중단·검산 실패(불완전)
          3 = 완전하지만 자동 판정 불가 — 테마 전환 미확인·미처리 테마 조건·미정착 구간(수동 확인 필요)
배율은 구간마다 PNG 실제 높이 ÷ CSS 높이로 구해 겹침을 자르고, 최종 높이는 fullH × 배율과 구간 수 이내
반올림 오차까지 허용한다(codex 2차 검수 #9). 구간 PNG의 가로·세로 배율이 서로 다르거나 구간끼리 배율이 다르면
clip이 창 밖으로 나간 것이므로 불완전으로 본다(2026-09-30 감사 #2). 중간 파일은 실행별 임시 폴더에만 둔다.
조합마다 repl을 따로 부르므로 META 줄이 여러 개이고, 전부 합친다(감사 #7).
"""
import base64
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

VIEWPORT_H = {"375": 812, "1280": 800}
EXPECTED = {f"{t}_{w}" for t in ("dark", "light") for w in VIEWPORT_H}
SAME_IMAGE_RATIO = 0.001      # 다크·라이트 결과에서 달라진 픽셀 비율이 이 미만이면 같은 화면으로 본다
CUT_REASON = {"BUDGET": "시간 예산 초과", "SEGMENT_CAP": "구간 상한 도달", "NO_SCROLL_PROGRESS": "스크롤이 진행되지 않음",
              "SHRANK": "문서가 이미 찍은 구간보다 짧아짐"}


def identify(path: Path) -> tuple[int, int]:
    out = subprocess.run(["magick", "identify", "-format", "%w %h", str(path)],
                         capture_output=True, text=True, check=True).stdout.split()
    return int(out[0]), int(out[1])


def same_image(a: Path, b: Path) -> bool:
    """두 결과 이미지가 사실상 같은가(크기가 다르면 다른 화면). magick compare는 달라진 픽셀 수를 stderr로 낸다."""
    if identify(a) != identify(b):
        return False
    r = subprocess.run(["magick", "compare", "-metric", "AE", "-fuzz", "2%", str(a), str(b), "null:"],
                       capture_output=True, text=True)
    if r.returncode not in (0, 1):
        return False
    w, h = identify(a)
    return float(r.stderr.split()[0]) / (w * h) < SAME_IMAGE_RATIO


def main() -> int:
    raw_path, outdir, tag = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    outdir.mkdir(parents=True, exist_ok=True)
    # 이전 실행의 같은 이름 결과를 먼저 지운다 — 이번에 건너뛴 조합의 옛 PNG가 현재 결과로 보이지 않게(감사 #16)
    for key in EXPECTED:
        (outdir / f"full-{key}-{tag}.png").unlink(missing_ok=True)
    raw = open(raw_path, encoding="utf-8").read()
    meta = {}
    for line in re.findall(r"^META (.*)$", raw, re.M):
        try:
            meta.update(json.loads(line))
        except json.JSONDecodeError:
            pass
    if not meta:
        print("불완전: META 줄 없음(캡처 스크립트 중단)"); return 1
    incomplete = manual = False
    for key in sorted(EXPECTED):
        m = meta.get(key)
        if not m:
            print(f"{key}: 불완전 — 캡처 없음"); incomplete = True
        elif m.get("error") == "VIEWPORT_TOO_SMALL":
            print(f"{key}: 불완전 — 탭 창 {m.get('iw')}x{m.get('ih')}가 조합 크기보다 작다(Aside 창을 키운 뒤 다시 실행)")
            incomplete = True
        elif m.get("error"):
            print(f"{key}: 불완전 — 건너뜀 {m['error']}"); incomplete = True
        elif not m.get("ys"):                                  # 촬영 도중 중단(codex 3차 #1)
            cut = f" {m['cut']}({CUT_REASON.get(m['cut'], '')})" if m.get("cut") else ""
            print(f"{key}: 불완전 — 구간 기록 없음(캡처 중단{cut})"); incomplete = True
        else:
            if m.get("cut"):                                   # 예산·상한·스크롤 막힘(감사 #7)
                print(f"{key}: 불완전 — 캡처 중단 {m['cut']}({CUT_REASON.get(m['cut'], '')})"); incomplete = True
            if m.get("stable") is False:                       # 하단 지연 로딩 미안정(3차 #2)
                print(f"{key}: 불완전 — 하단 지연 로딩이 안정화되지 않음"); incomplete = True
            if m.get("innerScroll"):                           # 앱 셸 내부 스크롤(감사 #6)
                s = m["innerScroll"]
                print(f"{key}: 불완전 — 내부 스크롤 컨테이너 {s['el']}에 숨은 내용 {s['hidden']}px(문서 스크롤만 캡처함)")
                incomplete = True

    with tempfile.TemporaryDirectory(dir=outdir, prefix=".stitch-") as tmp:
        for key in sorted(EXPECTED):
            m = meta.get(key) or {}
            if m.get("error") or not m.get("ys"):
                continue
            w = int(key.split("_")[1])
            h = VIEWPORT_H[str(w)]
            parts, scales = [], []
            for i, y in enumerate(m["ys"]):
                b = re.search(rf"^SEG_{key}_{i}_START\n(.*?)\nSEG_{key}_{i}_END$", raw, re.S | re.M)
                if not b:
                    print(f"{key}: 불완전 — 구간 {i} 없음"); incomplete = True; parts = []; break
                seg = Path(tmp) / f"{key}_{i}.png"
                seg.write_bytes(base64.b64decode(b.group(1).replace("\n", "")))
                pw, ph = identify(seg)
                scale = ph / h                                   # 이 구간의 실제 배율
                # 가로·세로 배율이 다르거나(창 밖 clip) 앞 구간과 배율이 다르면 이어 붙일 수 없다(감사 #2)
                if abs(pw - w * scale) > 1 or (scales and abs(ph - h * scales[0]) > 1):
                    print(f"{key}: 불완전 — 구간 {i} 크기 {pw}x{ph}가 {w}x{h}×{scales[0] if scales else scale:g}와 맞지 않음")
                    incomplete = True
                scales.append(scale)
                if i > 0:
                    overlap = (m["ys"][i - 1] + h) - y         # 스크롤이 끝에서 멈춰 앞 구간과 겹친 CSS px
                    if overlap > 0:
                        subprocess.run(["magick", str(seg), "-gravity", "north", "-chop",
                                        f"0x{round(overlap * scale)}", "+repage", str(seg)], check=True)
                parts.append(str(seg))
            if not parts:
                continue
            out = outdir / f"full-{key}-{tag}.png"
            subprocess.run(["magick", *parts, "-append", str(out)], check=True)
            ow, oh = identify(out)
            scale = sum(scales) / len(scales)
            expect = round(m["fullH"] * scale)
            ok = abs(oh - expect) <= len(parts)                  # 구간별 반올림 오차 허용
            incomplete |= not ok
            notes = []
            if m.get("unsupported"):
                notes.append(f"not·or 테마 조건 {m['unsupported']}개 미처리(수동 확인)"); manual = True
            if m.get("blockedSheets"):
                notes.append(f"읽지 못한 교차 출처 시트 {m['blockedSheets']}개(시트 media 조건만 강제)")
            if m.get("unsettled"):
                notes.append(f"시간 안에 못 끝난 애니메이션·이미지 {m['unsettled']}개(수동 확인)"); manual = True
            if m.get("innerScrollNote"):                        # 문서는 스크롤되는 페이지의 큰 내부 스크롤 상자 — 메모만
                s = m["innerScrollNote"]
                notes.append(f"내부 스크롤 상자 {s['el']}의 숨은 내용 {s['hidden']}px는 캡처 밖(사용자 화면과 같음)")
            print(f"{key}: {out.name} {ow}x{oh} (기대 {expect}±{len(parts)}, {'OK' if ok else '불일치'}) "
                  f"배율={scale:g} overflowX={m['overflowX']} bg={m['bg']} 시스템={m.get('system')} 테마강제={m.get('themeRules')}"
                  + (" | " + "; ".join(notes) if notes else ""))

        # 테마 전환 확인(감사 #3): 강제 지점이 0이거나 다크·라이트 결과가 같은 화면이면 다크 검사가 됐는지 알 수 없다
        for w in VIEWPORT_H:
            d, l = meta.get(f"dark_{w}") or {}, meta.get(f"light_{w}") or {}
            fd, fl = outdir / f"full-dark_{w}-{tag}.png", outdir / f"full-light_{w}-{tag}.png"
            if not (fd.exists() and fl.exists()):
                continue
            # 배경색 비교를 더한다 — 클래스 방식 테마에 부수 media 규칙이 섞이면 로고 하나만 바뀌어도 '다른 화면'으로
            # 통과했다(검토 반박 #3). 다크·라이트의 body 배경색이 같으면 테마가 실제로 바뀌었는지 알 수 없다.
            why = ("테마 강제 지점 0" if not d.get("themeRules") and not l.get("themeRules")
                   else "다크·라이트 배경색이 같다" if d.get("bg") and d.get("bg") == l.get("bg")
                   else "다크·라이트 결과 이미지가 같다" if same_image(fd, fl) else None)
            if why:
                print(f"테마 전환 미확인({w}): {why} — 단일 테마 사이트면 정상, 클래스·data-theme 방식이면 다크 미검사(수동 확인)")
                manual = True
    return 1 if incomplete else (3 if manual else 0)


if __name__ == "__main__":
    sys.exit(main())
