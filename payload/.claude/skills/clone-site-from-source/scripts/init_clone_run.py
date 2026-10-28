#!/usr/bin/env python3
"""Initialize the evidence contract for an authorized URL-to-code clone run."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from generate_site_docs import generate_docs


VIEWPORT_PATTERN = re.compile(r"^(?P<width>[1-9]\d*)x(?P<height>[1-9]\d*)$")


def parse_viewport(value: str) -> dict[str, int]:
    match = VIEWPORT_PATTERN.fullmatch(value.strip().lower())
    if not match:
        raise argparse.ArgumentTypeError("viewport must use WIDTHxHEIGHT, for example 1280x720")
    return {"width": int(match.group("width")), "height": int(match.group("height"))}


def normalize_routes(values: list[str] | None) -> list[str]:
    routes: list[str] = []
    for value in values or ["/"]:
        route = value.strip()
        # [하네스 적응 2026-07-25] `//host/path`(프로토콜 상대) 차단 추가. 원문 검사는
        # `://` 부재만 봐서 `//evil.example.net/x`가 "same-origin absolute pathname"으로
        # 통과했고(실증), 그 값을 브라우저에 넘기면 타 오리진을 크롤한다.
        if (
            not route.startswith("/")
            or route.startswith("//")
            or ".." in route
            or "://" in route
        ):
            raise ValueError(f"route must be a same-origin absolute pathname: {value}")
        route = "/" if route == "/" else route.rstrip("/")
        if route not in routes:
            routes.append(route)
    return routes


def manifest_path_exists(project_root: Path) -> bool:
    return (project_root / "clone-source.json").is_file()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--route", action="append", dest="routes")
    parser.add_argument(
        "--scope-mode",
        choices=("public-comprehensive", "user-limited"),
        default="public-comprehensive",
    )
    parser.add_argument(
        "--scope-note",
        help="required reason when --scope-mode is user-limited",
    )
    parser.add_argument("--desktop", default="1280x720", type=parse_viewport)
    parser.add_argument("--mobile", default="390x844", type=parse_viewport)
    parser.add_argument(
        "--authorization-basis",
        choices=['user-owned', 'user-confirmed-permission', 'public-documentation-site', 'other'],
        required=True,
        help="크롤 권한의 근거. capture-contract \u00a71 기계화 — 없으면 검증기가 완료를 거부한다.",
    )
    parser.add_argument(
        "--authorization-confirmed-by",
        required=True,
        help="권한을 확인해 준 주체(예: 'user', 'site owner <이름>', 'IANA example domain').",
    )
    parser.add_argument(
        "--robots-txt-status",
        choices=("allowed", "absent-404", "not-applicable-owned"),
        help="robots.txt 확인 **결과**. allowed=크롤 허용 확인(qa/robots.txt 사본 필요) / "
             "absent-404=robots.txt 없음 / not-applicable-owned=자기 소유 사이트. "
             "확인하지 않았으면 붙이지 마라 — 검증기가 완료를 거부한다.",
    )
    parser.add_argument(
        "--update-authorization",
        action="store_true",
        help="기존 프로젝트의 authorization 블록만 갱신한다. qa/·design-qa.md·문서/는 "
             "건드리지 않는다(2026-07-27 이전 프로젝트 마이그레이션 경로 — --force를 쓰면 "
             "완성된 문서 22개가 플레이스홀더로 되돌아간다).",
    )
    parser.add_argument("--force", action="store_true", help="replace existing manifest and QA scaffold")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.project_root.expanduser().resolve()
    if not project_root.is_dir():
        raise SystemExit(f"project root does not exist: {project_root}")
    if project_root.parent.name != "크롤링":
        raise SystemExit("project root must be nested under an exact '크롤링' directory")

    parsed = urlparse(args.source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit("source URL must be an absolute http(s) URL")

    try:
        routes = normalize_routes(args.routes)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    scope_note = args.scope_note.strip() if args.scope_note else None
    if args.scope_mode == "user-limited" and not scope_note:
        raise SystemExit("--scope-note is required when --scope-mode is user-limited")

    # [2026-07-27] 기존 프로젝트 마이그레이션: authorization 블록만 갱신하고 종료한다.
    if args.update_authorization:
        if not manifest_path_exists(project_root):
            raise SystemExit("--update-authorization requires an existing clone-source.json")
        existing = json.loads((project_root / "clone-source.json").read_text(encoding="utf-8"))
        existing["authorization"] = {
            "basis": args.authorization_basis,
            "confirmed_by": args.authorization_confirmed_by.strip(),
            "robots_txt_checked": args.robots_txt_status or False,
            "robots_txt_url": f"{parsed.scheme}://{parsed.netloc}/robots.txt",
        }
        (project_root / "clone-source.json").write_text(
            json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Updated authorization block in {project_root / 'clone-source.json'}")
        return 0

    qa_root = project_root / "qa"
    for name in ("source", "implementation", "comparisons", "metrics"):
        (qa_root / name).mkdir(parents=True, exist_ok=True)

    manifest_path = project_root / "clone-source.json"
    qa_path = project_root / "design-qa.md"

    # [하네스 적응 2026-07-25] 원자성·파괴 방어 두 건.
    # (F4) 원문은 manifest/qa 2개만 사전 검사하고 문서 충돌은 generate_docs() 안에서
    #      터졌다 — 실패했는데 manifest·design-qa는 이미 써진 반쪽 상태가 남고, 벗어나는
    #      길이 --force뿐이라 아래 F3를 발동시켰다. 문서 충돌을 여기서 먼저 본다.
    # (F3) --force가 사람이 수 시간 쓴 문서 22개를 무음으로 덮어썼다. 백업을 남긴다.
    docs_root = project_root / "문서"
    existing_docs = sorted(p for p in docs_root.glob("*.md")) if docs_root.is_dir() else []
    if not args.force:
        existing = [str(path) for path in (manifest_path, qa_path) if path.exists()]
        existing += [str(p) for p in existing_docs]
        if existing:
            raise SystemExit("refusing to overwrite existing files; pass --force if intentional: " + ", ".join(existing))
    else:
        doomed = [p for p in (manifest_path, qa_path) if p.exists()] + existing_docs
        if doomed:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_root = project_root / f".clone-backup-{stamp}"
            for path in doomed:
                target = backup_root / path.relative_to(project_root)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
            print(f"--force: backed up {len(doomed)} existing file(s) to {backup_root.name}/")

    canonical_url = parsed._replace(fragment="").geturl()
    manifest = {
        "schema_version": 1,
        "source_url": canonical_url,
        "source_origin": f"{parsed.scheme}://{parsed.netloc}",
        "crawl_container": "크롤링",
        "site_name": project_root.name,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "auth_boundary": "public-only",
        "authorization": {
            "basis": args.authorization_basis,
            "confirmed_by": args.authorization_confirmed_by.strip(),
            "robots_txt_checked": args.robots_txt_status or False,
            "robots_txt_url": f"{parsed.scheme}://{parsed.netloc}/robots.txt",
        },
        "external_writes": False,
        "routes": routes,
        "scope": {
            "mode": args.scope_mode,
            "reduction_reason": scope_note if args.scope_mode == "user-limited" else None,
            "inventory_basis": [
                "global-navigation",
                "footer-navigation",
                "primary-same-origin-links",
            ],
            "included_routes": routes,
            "excluded_routes": [],
            "dynamic_route_families": [],
        },
        "viewports": {"desktop": args.desktop, "mobile": args.mobile},
        "evidence": {
            "source": "qa/source",
            "implementation": "qa/implementation",
            "comparisons": "qa/comparisons",
            "metrics": "qa/metrics",
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    qa_scaffold = f"""# Design QA — Source Site Clone

## Scope

- Source: `{canonical_url}`
- Routes: {', '.join(f'`{route}`' for route in routes)}
- Desktop: `{args.desktop['width']} × {args.desktop['height']}`
- Mobile: `{args.mobile['width']} × {args.mobile['height']}`

## Evidence

- Source: `qa/source/`
- Implementation: `qa/implementation/`
- Combined comparisons: `qa/comparisons/`
- Metrics: `qa/metrics/`

## Findings

- [P1] Source and implementation comparison has not been completed.

## Required fidelity surfaces

- Typography: pending
- Spacing/layout: pending
- Colors/tokens: pending
- Image/asset quality: pending
- Copy/content: pending
- Icons: pending
- Responsiveness: pending
- Interactions/accessibility: pending

## Verification

- Primary interactions: pending
- Console errors/warnings: pending
- Build: pending
- Sites tests: pending

final result: blocked
"""
    qa_path.write_text(qa_scaffold, encoding="utf-8")
    generated_docs = generate_docs(project_root, force=args.force)
    print(f"Initialized clone evidence contract at {project_root}")
    print(f"Generated {len(generated_docs)} documentation scaffolds in {project_root / '문서'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
