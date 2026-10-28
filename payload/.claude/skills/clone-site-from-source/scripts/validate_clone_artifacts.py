#!/usr/bin/env python3
"""Validate required evidence and build artifacts for a source-site clone."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from generate_site_docs import (
    DEEP_UX_DOCUMENT_NAMES,
    DEEP_UX_REQUIRED_HEADINGS,
    DOCUMENT_NAMES,
    EVIDENCE_LABELS,
    PLACEHOLDER,
)


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif"}
SOURCE_SUFFIXES = {".css", ".html", ".js", ".jsx", ".mjs", ".ts", ".tsx"}
# [하네스 적응 2026-07-25] `href`를 자산 핫링크 검사에서 분리했다. 비협상 게이트 3은
# "핫링크된 **자산**" 금지인데 원문 정규식이 href까지 잡아, 보존해야 하는 푸터 법적 링크·
# 외부 소셜 앵커(SKILL.md "법적 카피 보존")를 반려하고 원문 링크를 지우도록 유도했다.
REMOTE_ATTRIBUTE = re.compile(r"(?:src|srcset|poster)\s*=\s*[\"']https?://", re.IGNORECASE)
REMOTE_CSS_URL = re.compile(r"url\(\s*[\"']?https?://", re.IGNORECASE)
MIN_DOCUMENT_CHARACTERS = 300
MIN_DEEP_UX_DOCUMENT_CHARACTERS = 1200
MIN_DEEP_UX_EVIDENCE_LABELS = 6
AUTHORIZATION_BASES = ('user-owned', 'user-confirmed-permission', 'public-documentation-site', 'other')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument(
        "--max-evidence-age-days",
        type=int,
        default=None,
        help="captured_at이 이 일수보다 오래되면 실패시킨다(기본 off).",
    )
    parser.add_argument(
        "--require-openai-hosting",
        action="store_true",
        help="Codex Sites 호스팅 산출물(.openai/hosting.json, dist/server/index.js)을 필수로 검사한다. "
             "이 하네스 기본값은 off — 해당 배포 표면이 없다.",
    )
    return parser.parse_args()


def image_count(path: Path) -> int:
    return sum(1 for item in path.rglob("*") if item.is_file() and item.suffix.lower() in IMAGE_SUFFIXES)


# [하네스 적응 2026-07-27] 내용 검사 5종 추가. 배경: 적대 감사가 1×1 투명 PNG·`{}` metrics·
# "asdf"×400 문서로 이 게이트를 통과시켰다. 게이트가 파일 존재·문자열 포함·글자 수만 보기
# 때문이었다. 아래 검사는 전부 "정상 작업에서는 절대 걸리지 않고, 위조에서는 반드시 걸리는"
# 기준만 채택했다 — 오탐이 이 하네스의 1순위 안티골이다.

def read_image_size(path: Path) -> tuple[int, int] | None:
    """PNG/JPEG/WebP의 픽셀 크기를 헤더에서 읽는다. 외부 패키지 없이 stdlib만 쓴다.

    판별 불가(손상·미지 포맷)면 None — 그 경우는 통과시킨다(오탐 방지).
    """
    try:
        fh = path.open("rb")
    except OSError:
        return None
    with fh:
        blob = fh.read(4096)
        # PNG: IHDR의 선언 크기를 믿기 전에 IDAT(실제 픽셀 데이터) 존재를 확인한다.
        # 헤더만 든 24바이트 껍데기가 1280×720을 '선언'하고 통과하던 구멍(적대 검증 실증).
        if blob[:8] == b"\x89PNG\r\n\x1a\n" and blob[12:16] == b"IHDR":
            fh.seek(0)
            if b"IDAT" not in fh.read(1 << 20):
                return None
            return (int.from_bytes(blob[16:20], "big"), int.from_bytes(blob[20:24], "big"))
        # GIF87a/89a: LE 2바이트 × 2
        if blob[:4] == b"GIF8" and len(blob) >= 10:
            return (int.from_bytes(blob[6:8], "little"), int.from_bytes(blob[8:10], "little"))
        # WebP: 'RIFF' .... 'WEBP'
        if blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
            fourcc = blob[12:16]
            if fourcc == b"VP8X" and len(blob) >= 30:
                return (int.from_bytes(blob[24:27], "little") + 1,
                        int.from_bytes(blob[27:30], "little") + 1)
            if fourcc == b"VP8 " and len(blob) >= 30:
                return (int.from_bytes(blob[26:28], "little") & 0x3FFF,
                        int.from_bytes(blob[28:30], "little") & 0x3FFF)
            if fourcc == b"VP8L" and len(blob) >= 25:
                bits = int.from_bytes(blob[21:25], "little")
                return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
            return None
        # JPEG: SOF를 파일 끝까지 스트리밍 탐색한다. 고정 창(65536)을 쓰면 앞에 큰
        # COM/APP 세그먼트를 끼워 SOF를 창 밖으로 밀어내는 위조가 통한다(실증).
        if blob[:2] == b"\xff\xd8":
            fh.seek(2)
            while True:
                b1 = fh.read(1)
                if not b1:
                    return None
                if b1 != b"\xff":
                    continue
                mk = fh.read(1)
                if not mk:
                    return None
                m = mk[0]
                if m in (0xD8, 0x01, 0xFF) or 0xD0 <= m <= 0xD7:
                    continue
                raw = fh.read(2)
                if len(raw) < 2:
                    return None
                ln = int.from_bytes(raw, "big")
                if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                         0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    # SOF 세그먼트: [precision(1)][height(2)][width(2)]...
                    # 길이 2바이트를 이미 읽었으므로 여기서부터 precision이다.
                    seg = fh.read(5)
                    if len(seg) < 5:
                        return None
                    return (int.from_bytes(seg[3:5], "big"),   # width
                            int.from_bytes(seg[1:3], "big"))   # height
                if ln < 2:
                    return None
                fh.seek(ln - 2, 1)
        return None


# 전체 화면 캡처로 인정할 최소 변. output-contract가 "one full-view desktop/mobile
# screenshot"을 요구하므로, 각 증거 디렉토리에 이 크기 이상이 최소 1장은 반드시 있다.
# 부분 확대 비교(작은 크롭)는 이 기준과 무관하게 함께 둘 수 있다.
MIN_FULL_VIEW_EDGE = 320


def has_full_view_image(path: Path) -> tuple[bool, int, int]:
    """(전체뷰 1장 이상 존재, 판별된 수, 판별 불가 수).

    [2026-07-27 정정] 초판은 판별 불가를 만나면 즉시 통과시켰다(오탐 방지 의도).
    그 결과 0바이트 .png 한 장이 디렉토리 검사 전체를 끄는 스위치가 됐다(적대 검증 실증).
    이제 판별 불가는 '합격'이 아니라 '증거 불충분'으로 센다.
    """
    decided = unreadable = 0
    ok = False
    for item in path.rglob("*"):
        if not (item.is_file() and item.suffix.lower() in IMAGE_SUFFIXES):
            continue
        size = read_image_size(item)
        if size is None:
            unreadable += 1
            continue
        decided += 1
        if size[0] >= MIN_FULL_VIEW_EDGE and size[1] >= MIN_FULL_VIEW_EDGE:
            ok = True
    return (ok, decided, unreadable)


# [2026-07-27] 값 검증이 생겼으므로 키 이름은 넓혀도 안전하다 — 오탐(viewportW, page,
# px:{w,h} 등 정당한 명명)을 함께 없앤다. 위조 차단은 값 쪽이 담당한다.
METRIC_KEY_CONCEPTS = {
    "route": re.compile(r"url|route|path|href|page|slug", re.IGNORECASE),
    "title": re.compile(r"title|heading|h1|label|name", re.IGNORECASE),
    "width": re.compile(r"width|viewport|(?:^|[^a-z])w(?:$|[^a-z])", re.IGNORECASE),
    "height": re.compile(r"height|viewport|(?:^|[^a-z])h(?:$|[^a-z])", re.IGNORECASE),
}
DIMENSION_TEXT = re.compile(r"^\s*(\d{2,5})\s*[x×,]\s*(\d{2,5})\s*$")


MARKER_LINE = re.compile(r"(?m)^\s*(?:[-*>]\s*)?(?:TODO|FIXME|pending)\b\s*[:\-]", re.IGNORECASE)


def strip_quoted(text: str) -> str:
    """코드펜스·인라인 코드·따옴표 인용을 제거한다(원본 문구 인용 오탐 방지)."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", "", text)
    return re.sub(r"[\"\u201c\u2018][^\"\u201d\u2019\n]{0,80}[\"\u201d\u2019]", "", text)


def iter_records(node: object):
    """중첩 구조에서 dict 레코드를 전부 훑는다."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from iter_records(value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_records(value)


def _dimension_ok(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value > 0
    return bool(isinstance(value, str) and DIMENSION_TEXT.match(value))


def is_measurement(record: dict) -> bool:
    """[2026-07-27] 키 '이름'만 보던 것을 (키, 값) 쌍 검증으로 바꿨다.

    null/0/빈 dict로 채운 위조와 `{"urltitlewidthheight": 0}` 같은 합성 키가 통과하던 구멍.
    """
    hit: set[str] = set()
    for key, value in record.items():
        # 치수는 한 겹 중첩까지 본다 — {"viewport": {"w": 1280, "h": 720}} 같은 정당한
        # 스키마가 레코드 경계로 갈라져 오탐이 나던 것을 흡수한다.
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                for concept in ("width", "height"):
                    if METRIC_KEY_CONCEPTS[concept].search(str(sub_key)) and _dimension_ok(sub_value):
                        hit.add(concept)
            continue
        for concept, pattern in METRIC_KEY_CONCEPTS.items():
            if not pattern.search(str(key)):
                continue
            if concept in ("width", "height"):
                if _dimension_ok(value):
                    hit.add(concept)
            elif isinstance(value, str) and value.strip():
                hit.add(concept)
    return len(hit) >= 3


def find_remote_hotlinks(project_root: Path) -> list[str]:
    findings: list[str] = []
    for base_name in ("src", "public"):
        base = project_root / base_name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            # [2026-07-27] 파일 단위 판정은 자체 호스팅이 **불가능한** 서드파티 임베드
            # (YouTube/지도 iframe)와 원본 URL 대조 주석까지 반려해, 통과시키려면 원본
            # 기능을 삭제하게 만들었다. 라인 단위 + 예외로 바꾼다.
            for line in text.splitlines():
                if not (REMOTE_ATTRIBUTE.search(line) or REMOTE_CSS_URL.search(line)):
                    continue
                stripped = line.lstrip()
                if "<iframe" in line or "<embed" in line:
                    continue
                if "clone-allow-remote" in line:
                    continue
                if stripped.startswith(("//", "*", "/*", "#", "<!--")):
                    continue
                findings.append(f"{path.relative_to(project_root)}: {stripped[:80]}")
                break
    return findings


def main() -> int:
    args = parse_args()
    root = args.project_root.expanduser().resolve()
    errors: list[str] = []

    if not root.is_dir():
        raise SystemExit(f"project root does not exist: {root}")
    if unicodedata.normalize("NFC", root.parent.name) != "크롤링":
        errors.append("project root must be <execution-root>/크롤링/<SiteName>")

    manifest_path = root / "clone-source.json"
    manifest: dict = {}
    if not manifest_path.is_file():
        errors.append("missing clone-source.json")
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as error:
            errors.append(f"invalid clone-source.json: {error}")
        if manifest:
            if manifest.get("schema_version") != 1:
                errors.append("clone-source.json schema_version must be 1")
            if unicodedata.normalize("NFC", str(manifest.get("crawl_container") or "")) != "크롤링":
                errors.append("clone-source.json crawl_container must be '크롤링'")
            if manifest.get("site_name") != root.name:
                errors.append("clone-source.json site_name must match the project directory name")
            if not re.match(r"^https?://", str(manifest.get("source_url", ""))):
                errors.append("clone-source.json source_url must be absolute http(s)")
            if not manifest.get("routes") or not isinstance(manifest.get("routes"), list):
                errors.append("clone-source.json routes must be a non-empty list")
            if manifest.get("external_writes") is not False:
                errors.append("clone-source.json external_writes must be false")

            # [내용 검사 2026-07-27] captured_at은 형식만 있고 아무도 안 봤다.
            # 파싱 가능해야 하고 미래일 수 없다(위조 타임스탬프 차단).
            captured_at = manifest.get("captured_at")
            try:
                captured = datetime.fromisoformat(str(captured_at))
                # [2026-07-27] naive를 UTC로 간주하던 것은 UTC보다 앞선 타임존(KST 등)에서
                # 정상 타임스탬프를 '미래'로 반려하는 상시 오탐이었다. 시스템 로컬로 해석한다.
                if captured.tzinfo is None:
                    captured = captured.astimezone()
                if captured > datetime.now(timezone.utc) + timedelta(hours=1):
                    errors.append(
                        f"clone-source.json captured_at is in the future: {captured_at} "
                        "(타임존 표기 +09:00 또는 Z 를 붙여라)"
                    )
                # 나이는 manifest 생성 시각이 아니라 **증거 파일**에서 잰다 — 오래 걸린
                # 프로젝트가 오늘 전량 재캡처해도 반려되던 오탐 제거.
                qa_dir = root / "qa"
                newest = max(
                    (p.stat().st_mtime for p in qa_dir.rglob("*") if p.is_file()),
                    default=None,
                ) if qa_dir.is_dir() else None
                if newest is not None:
                    newest_dt = datetime.fromtimestamp(newest, timezone.utc)
                    if newest_dt < captured - timedelta(hours=1):
                        errors.append("qa evidence files predate captured_at — 재캡처되지 않았다")
                    if args.max_evidence_age_days is not None:
                        age = (datetime.now(timezone.utc) - newest_dt).days
                        if age > args.max_evidence_age_days:
                            errors.append(
                                f"qa evidence is {age} days old "
                                f"(limit {args.max_evidence_age_days}) — recapture the source"
                            )
            except (TypeError, ValueError):
                errors.append(f"clone-source.json captured_at must be ISO-8601: {captured_at!r}")

            # [내용 검사 2026-07-27] 이 스킬은 타사 사이트 전량 복제 파이프라인인데
            # 권한 확인이 산문 경고뿐이었고 게이트는 한 항목도 보지 않았다.
            # capture-contract §1("소유했거나 재현 허가를 받은 사이트로 한정")을 기계화한다.
            authorization = manifest.get("authorization")
            if not isinstance(authorization, dict):
                errors.append(
                    "clone-source.json must include an authorization block "
                    "(basis, confirmed_by, robots_txt_checked) — capture-contract \u00a71"
                )
            else:
                basis = str(authorization.get("basis") or "").strip()
                if basis not in AUTHORIZATION_BASES:
                    errors.append(
                        "clone-source.json authorization.basis must be one of: "
                        + ", ".join(AUTHORIZATION_BASES)
                    )
                confirmed = authorization.get("confirmed_by")
                if not isinstance(confirmed, str) or len(confirmed.strip()) < 3:
                    errors.append("clone-source.json authorization.confirmed_by must be a non-trivial string")
                if basis == "other" and len(str(authorization.get("basis_note") or "").strip()) < 20:
                    errors.append(
                        "authorization.basis 'other' requires basis_note (≥20자) explaining the legal basis"
                    )
                # [2026-07-27] boolean이던 것을 확인 '결과' 열거형으로 바꿨다. robots.txt가
                # 404인 자기 소유 사이트에서 정직한 값이 없어 거짓 신고를 학습시키던 구조.
                status = authorization.get("robots_txt_checked")
                if status not in (True, "allowed", "absent-404", "not-applicable-owned"):
                    errors.append(
                        "authorization.robots_txt_checked must be one of: "
                        "true, 'allowed', 'absent-404', 'not-applicable-owned'"
                    )
                if status == "not-applicable-owned" and basis != "user-owned":
                    errors.append("'not-applicable-owned' is only valid with basis=user-owned")
                # 로컬 대조: robots_txt_url 호스트가 source_url 호스트와 같아야 한다
                if urlparse(str(authorization.get("robots_txt_url") or "")).netloc.lower() != \
                   urlparse(str(manifest.get("source_url", ""))).netloc.lower():
                    errors.append("authorization.robots_txt_url must be the source_url host's /robots.txt")
                # 가져왔다고 주장하면 사본이 있어야 한다
                if status in (True, "allowed"):
                    robots_copy = root / "qa" / "robots.txt"
                    if not (robots_copy.is_file() and robots_copy.stat().st_size > 0):
                        errors.append(
                            "robots_txt_checked 주장은 qa/robots.txt 사본을 요구한다 "
                            "(curl -sS <robots_txt_url> -o qa/robots.txt)"
                        )
            # 아무도 읽지 않던 경계 필드
            if manifest.get("auth_boundary") != "public-only":
                errors.append("clone-source.json auth_boundary must be 'public-only' (capture-contract §1)")
            scope = manifest.get("scope")
            if not isinstance(scope, dict):
                errors.append("clone-source.json scope must be an object")
            else:
                scope_mode = scope.get("mode")
                if scope_mode not in {"public-comprehensive", "user-limited"}:
                    errors.append("clone-source.json scope.mode must be public-comprehensive or user-limited")
                if scope_mode == "user-limited" and not str(scope.get("reduction_reason") or "").strip():
                    errors.append("user-limited scope requires a reduction_reason")
                inventory_basis = scope.get("inventory_basis")
                if not isinstance(inventory_basis, list) or not inventory_basis:
                    errors.append("clone-source.json scope.inventory_basis must be a non-empty list")
                included_routes = scope.get("included_routes")
                if not isinstance(included_routes, list) or included_routes != manifest.get("routes"):
                    errors.append("clone-source.json scope.included_routes must exactly match routes")
                excluded_routes = scope.get("excluded_routes")
                if not isinstance(excluded_routes, list):
                    errors.append("clone-source.json scope.excluded_routes must be a list")
                else:
                    for index, exclusion in enumerate(excluded_routes):
                        if not isinstance(exclusion, dict) or not str(exclusion.get("url") or "").strip() or not str(exclusion.get("reason") or "").strip():
                            errors.append(f"scope.excluded_routes[{index}] must include url and reason")
                route_families = scope.get("dynamic_route_families")
                if not isinstance(route_families, list):
                    errors.append("clone-source.json scope.dynamic_route_families must be a list")
                else:
                    for index, family in enumerate(route_families):
                        if (
                            not isinstance(family, dict)
                            or not str(family.get("name") or "").strip()
                            or not isinstance(family.get("representative_routes"), list)
                            or not family.get("representative_routes")
                            or not str(family.get("capture_rule") or "").strip()
                        ):
                            errors.append(
                                f"scope.dynamic_route_families[{index}] must include name, representative_routes, and capture_rule"
                            )

    qa_path = root / "design-qa.md"
    qa_text = ""
    if not qa_path.is_file():
        errors.append("missing design-qa.md")
    else:
        qa_text = qa_path.read_text(encoding="utf-8")
        if qa_text.rstrip().splitlines()[-1:] != ["final result: passed"]:
            errors.append(
                "design-qa.md must end with exactly 'final result: passed' as the last line "
                "(서명·메모는 그 위로 옮겨라)"
            )
        required_terms = (
            "Typography",
            "Spacing",
            "Colors",
            "Image",
            "Copy",
            "Interactions",
            "Console",
            "Build",
            "Sites",
        )
        missing_terms = [term for term in required_terms if term.lower() not in qa_text.lower()]
        if missing_terms:
            errors.append("design-qa.md is missing required QA surfaces: " + ", ".join(missing_terms))
        # [내용 검사] `final result: passed` 한 줄이 QA 통과 전권을 갖는 구조를 완화한다.
        # design-qa.md는 실존하는 증거 파일을 최소 2개 지목해야 한다 — output-contract가
        # "source visual truth paths"와 "implementation screenshot paths"를 요구하므로
        # 정상 작업은 자연히 충족하고, 위조는 증거를 실제로 만들어야만 통과한다.
        # [2026-07-27] 정규식으로 본문에서 경로를 뽑던 방식은 양방향으로 틀렸다:
        # `qa/./source/x.png` 표기 변형이 중복 계수를 뚫었고, 대문자 확장자·공백·괄호·@2x가
        # 든 정당한 파일명은 잡히지 않아 정직한 작업을 반려했다. 실파일에서 본문으로
        # 역방향 매칭하면 둘 다 사라진다.
        qa_root = root / "qa"
        qa_files = [
            p.relative_to(root).as_posix()
            for p in qa_root.rglob("*")
            if p.is_file() and (p.suffix.lower() in IMAGE_SUFFIXES or p.suffix.lower() == ".json")
        ] if qa_root.is_dir() else []
        cited = [rel for rel in qa_files if rel in qa_text or Path(rel).name in qa_text]
        shots = [r for r in cited if Path(r).suffix.lower() in IMAGE_SUFFIXES]
        if not any(r.startswith("qa/source") for r in shots) or \
           not any(r.startswith("qa/implementation") for r in shots):
            errors.append(
                "design-qa.md must cite at least one existing screenshot under qa/source "
                "and one under qa/implementation"
            )

    for evidence_name in ("source", "implementation", "comparisons"):
        evidence_dir = root / "qa" / evidence_name
        if not evidence_dir.is_dir() or image_count(evidence_dir) == 0:
            errors.append(f"qa/{evidence_name} must contain at least one image")
            continue
        # [내용 검사] 1×1 투명 PNG로 통과하던 구멍. 전체뷰 캡처 최소 1장을 요구한다.
        full_view, decided, unreadable = has_full_view_image(evidence_dir)
        if not full_view:
            if decided == 0:
                errors.append(
                    f"qa/{evidence_name}: 판별 가능한 캡처가 0장 (판별 불가 {unreadable}장) — "
                    "PNG/JPEG/WebP/GIF로 최소 1장 제출"
                )
            else:
                errors.append(
                    f"qa/{evidence_name} has no full-view capture "
                    f"(need at least one image ≥ {MIN_FULL_VIEW_EDGE}×{MIN_FULL_VIEW_EDGE}; "
                    f"{decided} checked, {unreadable} unreadable)"
                )

    metrics_dir = root / "qa" / "metrics"
    metrics_files = [p for p in metrics_dir.rglob("*") if p.suffix.lower() == ".json"] if metrics_dir.is_dir() else []
    if not metrics_files:
        errors.append("qa/metrics must contain at least one JSON metrics file")
    else:
        # [내용 검사] `{}` 로 통과하던 구멍. §6 "Measure route fidelity"가 요구하는
        # 라우트·제목·치수 개념이 키에 실제로 있어야 한다. 어떤 실제 측정 파일도 충족한다.
        unparsable: list[str] = []
        measured = False
        for path in metrics_files:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError, OSError):
                unparsable.append(str(path.relative_to(root)))
                continue
            if any(is_measurement(record) for record in iter_records(payload)):
                measured = True
        if unparsable:
            errors.append("qa/metrics contains unreadable JSON: " + ", ".join(unparsable))
        if not measured:
            errors.append(
                "qa/metrics must contain at least one record with non-empty route/title "
                "and positive width/height (§6 Measure route fidelity)"
            )

    docs_root = root / "문서"
    deep_ux_texts: dict[str, str] = {}
    for document_name in DOCUMENT_NAMES:
        document_path = docs_root / document_name
        if not document_path.is_file():
            errors.append(f"missing 문서/{document_name}")
            continue
        document_text = document_path.read_text(encoding="utf-8")
        # [하네스 적응 2026-07-25] "pending"을 부분문자열로 검사하면 정상 문서의
        # "depending on viewport"·"Appending"이 미완성으로 오검출된다(실증). 단어 경계로 좁혔다.
        # [2026-07-27] 원본 사이트 문구 인용("Pending" 상태 배지, "TODO" 네비 라벨,
        # 원본 번들 주석)이 미완성으로 반려되던 오탐. 인용·코드펜스를 걷어내고
        # **줄머리 마커 형태**만 잡는다. PLACEHOLDER는 원문 그대로 검사한다.
        scan_text = strip_quoted(document_text)
        if PLACEHOLDER in document_text or MARKER_LINE.search(scan_text):
            errors.append(f"incomplete documentation markers remain in 문서/{document_name}")
        # SERIOUS-6: 글자 수만 보면 'ㅋ'×1300으로 통과한다. 고유 어휘로 filler를 거른다.
        tokens = re.findall(r"[\w가-힣]+", document_text)
        unique_tokens = len(set(tokens))
        min_unique = 120 if document_name in DEEP_UX_DOCUMENT_NAMES else 40
        if unique_tokens < min_unique:
            errors.append(
                f"문서/{document_name}: 고유 어휘 {unique_tokens} < {min_unique} — filler text"
            )
        minimum_characters = (
            MIN_DEEP_UX_DOCUMENT_CHARACTERS
            if document_name in DEEP_UX_DOCUMENT_NAMES
            else MIN_DOCUMENT_CHARACTERS
        )
        if len(document_text.strip()) < minimum_characters:
            errors.append(f"문서/{document_name} is too short to be a complete site analysis")
        if document_name in DEEP_UX_DOCUMENT_NAMES:
            deep_ux_texts[document_name] = document_text
            missing_headings = [
                heading
                for heading in DEEP_UX_REQUIRED_HEADINGS[document_name]
                if f"## {heading}" not in document_text
            ]
            if missing_headings:
                errors.append(
                    f"문서/{document_name} is missing required headings: "
                    + ", ".join(missing_headings)
                )
            evidence_label_count = sum(document_text.count(label) for label in EVIDENCE_LABELS)
            if evidence_label_count < MIN_DEEP_UX_EVIDENCE_LABELS:
                errors.append(
                    f"문서/{document_name} must apply evidence labels to material claims "
                    f"(found {evidence_label_count}, require at least {MIN_DEEP_UX_EVIDENCE_LABELS})"
                )

    if deep_ux_texts:
        deep_ux_corpus = "\n".join(deep_ux_texts.values())
        missing_evidence_labels = [label for label in EVIDENCE_LABELS if label not in deep_ux_corpus]
        if missing_evidence_labels:
            errors.append(
                "deep UX documentation does not represent every evidence level: "
                + ", ".join(missing_evidence_labels)
            )
        flow_text = deep_ux_texts.get("17-상세-유저플로우-상태-복구.md", "")
        if "```mermaid" not in flow_text:
            errors.append("문서/17-상세-유저플로우-상태-복구.md must include a Mermaid flow or state diagram")
        test_matrix_text = deep_ux_texts.get("20-기능-상태-테스트-매트릭스.md", "")
        # 원본 UI의 체크박스 재현("- [ ] 약관 동의")까지 잡던 오탐 → 출시 체크리스트 절로 한정
        release_section = next(
            (s for s in re.split(r"^## ", test_matrix_text, flags=re.M) if s.startswith("출시")),
            "",
        )
        if "- [ ]" in strip_quoted(release_section):
            errors.append("문서/20-기능-상태-테스트-매트릭스.md contains unchecked release items")

    # [하네스 적응 2026-07-25] Codex Sites 호스팅 산출물(.openai/hosting.json ×2,
    # dist/server/index.js)은 이 환경에 존재하지 않는 배포 표면의 것이므로 기본 필수에서
    # 제외하고 --require-openai-hosting 옵트인으로 내렸다. references/output-contract.md의
    # "필수 아님" 서술과 이 게이트가 정면 모순이었고, 그 탈출로가 '빈 파일 위조'였다.
    required_files = [root / "package.json"]
    if args.require_openai_hosting:
        required_files += [
            root / ".openai" / "hosting.json",
            root / "dist" / "server" / "index.js",
            root / "dist" / ".openai" / "hosting.json",
        ]
    for required_file in required_files:
        if not required_file.is_file():
            errors.append(f"missing {required_file.relative_to(root)}")
        elif required_file.name == "package.json":
            # 0바이트 위조 방어 — 존재 검사만으로는 게이트가 내용을 보지 않는다.
            try:
                pkg = json.loads(required_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                errors.append(f"{required_file.relative_to(root)} is not valid JSON: {exc}")
            else:
                # json.loads만 통과하면 `0`·`null`도 지나가던 구멍
                if not isinstance(pkg, dict) or not str(pkg.get("name") or "").strip():
                    errors.append("package.json must be an object with a name")
                elif not isinstance(pkg.get("scripts"), dict) or "build" not in pkg["scripts"]:
                    errors.append("package.json must define a build script (acceptance gate 11)")

    # [2026-07-27] 클론 구현물이 0파일이어도 완료 선언이 가능하던 구멍
    if not any(
        p.suffix.lower() in SOURCE_SUFFIXES
        for name in ("src", "app")
        if (root / name).is_dir()
        for p in (root / name).rglob("*")
        if p.is_file()
    ):
        errors.append("src/ 또는 app/ 아래 소스 파일이 없다 — 클론 구현물이 존재하지 않는다")

    hotlinks = find_remote_hotlinks(root)
    if hotlinks:
        errors.append("remote asset hotlinks detected in: " + ", ".join(hotlinks))

    if errors:
        print("Clone artifact validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Clone artifact validation passed: {root}")
    print(f"Routes: {len(manifest.get('routes', []))}")
    print("Evidence: source, implementation, comparisons, metrics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
