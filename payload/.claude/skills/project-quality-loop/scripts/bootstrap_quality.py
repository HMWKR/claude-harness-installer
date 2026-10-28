#!/usr/bin/env python3
"""Create a non-destructive .claude/quality workspace and project detection report."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATE_DIR = SKILL_DIR / "templates"
sys.path.insert(0, str(SCRIPT_DIR))

from detect_project import detect_project  # noqa: E402

TEMPLATE_MAP = {
    "PROJECT_QUALITY_MANIFEST.md": "manifest.md",
    "TEST_MATRIX.md": "test-matrix.md",
    "DECISION_LOG.md": "decision-log.md",
    "FINAL_VERIFICATION_REPORT.md": "final-report.md",
}


def replace_tokens(text: str, *, run_id: str, root: Path, mode: str) -> str:
    now = datetime.now(timezone.utc).astimezone()
    replacements = {
        "{{RUN_ID}}": run_id,
        "{{DATE}}": now.date().isoformat(),
        "{{MODE}}": mode,
        "{{ROOT}}": str(root),
        "{{BASELINE}}": "확인 필요",
        "{{SCOPE}}": "현재 프로젝트 전체",
        "{{TITLE}}": "의사결정 제목",
    }
    for token, value in replacements.items():
        text = text.replace(token, value)
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root")
    parser.add_argument("--mode", default="full", choices=["full", "plan", "audit", "fix", "release"])
    parser.add_argument("--run-id", help="Optional run identifier")
    parser.add_argument("--force", action="store_true", help="Overwrite generated markdown templates")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    quality_dir = root / ".claude" / "quality"
    evidence_dir = quality_dir / "evidence" / run_id
    evidence_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    preserved: list[str] = []
    for source_name, target_name in TEMPLATE_MAP.items():
        source = TEMPLATE_DIR / source_name
        target = quality_dir / target_name
        if target.exists() and not args.force:
            preserved.append(str(target))
            continue
        text = replace_tokens(source.read_text(encoding="utf-8"), run_id=run_id, root=root, mode=args.mode)
        target.write_text(text, encoding="utf-8")
        created.append(str(target))

    findings = quality_dir / "findings.jsonl"
    if not findings.exists():
        findings.touch()
        created.append(str(findings))
    else:
        preserved.append(str(findings))

    detection = detect_project(root)
    detection.update({"run_id": run_id, "mode": args.mode})
    detection_path = quality_dir / "project-detection.json"
    detection_path.write_text(json.dumps(detection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    environment = {
        "run_id": run_id,
        "root": str(root),
        "mode": args.mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (evidence_dir / "environment.json").write_text(
        json.dumps(environment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    summary = {
        "quality_dir": str(quality_dir),
        "evidence_dir": str(evidence_dir),
        "run_id": run_id,
        "created": created,
        "preserved": preserved,
        "project_detection": str(detection_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
