#!/usr/bin/env python3
"""Detect project types, stacks, risk signals, and likely quality commands.

Uses only Python's standard library and never executes project commands.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

IGNORED_DIRS = {
    ".git", ".hg", ".svn", ".idea", ".vscode", ".next", ".nuxt",
    "node_modules", "vendor", "dist", "build", "target", "coverage",
    ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".terraform", ".gradle", ".cache", "Pods", "DerivedData",
}
MAX_DEPTH = 5
MAX_TEXT_BYTES = 512_000


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _walk(root: Path, max_depth: int = MAX_DEPTH) -> Iterable[Path]:
    root_parts = len(root.parts)
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        depth = len(current_path.parts) - root_parts
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".tox")]
        if depth >= max_depth:
            dirs[:] = []
        for filename in files:
            yield current_path / filename


def _read_text(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_TEXT_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _add_command(commands: list[dict[str, str]], kind: str, command: str, source: str) -> None:
    if not command:
        return
    if any(item["command"] == command for item in commands):
        return
    commands.append({"kind": kind, "command": command, "source": source})


def detect_project(root: Path) -> dict[str, Any]:
    root = root.resolve()
    files = list(_walk(root))
    by_name: dict[str, list[Path]] = {}
    for path in files:
        by_name.setdefault(path.name.lower(), []).append(path)

    types: set[str] = set()
    frameworks: set[str] = set()
    test_tools: set[str] = set()
    quality_tools: set[str] = set()
    risk_signals: set[str] = set()
    manifests: set[str] = set()
    commands: list[dict[str, str]] = []
    notes: list[str] = []

    package_jsons = [p for p in files if p.name == "package.json"]
    js_deps: set[str] = set()
    for package_path in package_jsons:
        package = _read_json(package_path)
        if not package:
            notes.append(f"Could not parse {_relative(package_path, root)}")
            continue
        manifests.add(_relative(package_path, root))
        deps: dict[str, Any] = {}
        for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            section = package.get(key, {})
            if isinstance(section, dict):
                deps.update(section)
        js_deps.update(str(name).lower() for name in deps)
        scripts = package.get("scripts", {})
        if isinstance(scripts, dict):
            prefix = "" if package_path.parent == root else f"--prefix {package_path.parent.relative_to(root).as_posix()} "
            preferred = {
                "test": "test", "test:unit": "test", "test:integration": "integration",
                "test:e2e": "e2e", "e2e": "e2e", "lint": "lint",
                "typecheck": "typecheck", "type-check": "typecheck", "check": "check",
                "build": "build", "dev": "run", "start": "run", "format:check": "format",
            }
            for script_name, kind in preferred.items():
                if script_name in scripts:
                    _add_command(commands, kind, f"npm {prefix}run {script_name}".strip(), _relative(package_path, root))

    js_framework_map = {
        "react": ("web-ui", "React"), "next": ("web-ui", "Next.js"),
        "vue": ("web-ui", "Vue"), "nuxt": ("web-ui", "Nuxt"),
        "svelte": ("web-ui", "Svelte"), "@sveltejs/kit": ("web-ui", "SvelteKit"),
        "@angular/core": ("web-ui", "Angular"), "astro": ("web-ui", "Astro"),
        "vite": ("web-ui", "Vite"), "express": ("backend-api", "Express"),
        "fastify": ("backend-api", "Fastify"), "@nestjs/core": ("backend-api", "NestJS"),
        "koa": ("backend-api", "Koa"), "hono": ("backend-api", "Hono"),
        "electron": ("desktop", "Electron"), "@tauri-apps/api": ("desktop", "Tauri"),
        "react-native": ("mobile", "React Native"), "expo": ("mobile", "Expo"),
        "commander": ("cli-tui", "Commander"), "yargs": ("cli-tui", "Yargs"),
        "oclif": ("cli-tui", "oclif"), "@modelcontextprotocol/sdk": ("agent-automation-mcp", "MCP"),
        "langchain": ("agent-automation-mcp", "LangChain"), "@langchain/core": ("agent-automation-mcp", "LangChain"),
        "openai": ("agent-automation-mcp", "OpenAI SDK"), "@anthropic-ai/sdk": ("agent-automation-mcp", "Anthropic SDK"),
    }
    for dep, (project_type, framework) in js_framework_map.items():
        if dep in js_deps:
            types.add(project_type)
            frameworks.add(framework)

    js_test_map = {
        "@playwright/test": "Playwright", "playwright": "Playwright", "cypress": "Cypress",
        "jest": "Jest", "vitest": "Vitest", "mocha": "Mocha", "ava": "AVA",
        "@testing-library/react": "Testing Library", "axe-core": "axe-core",
        "@axe-core/playwright": "axe-core",
    }
    for dep, tool in js_test_map.items():
        if dep in js_deps:
            test_tools.add(tool)
    for dep, tool in {
        "eslint": "ESLint", "prettier": "Prettier", "typescript": "TypeScript",
        "lighthouse": "Lighthouse", "lhci": "Lighthouse CI",
    }.items():
        if dep in js_deps:
            quality_tools.add(tool)

    python_manifests = []
    for name in ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "pipfile", "poetry.lock"):
        python_manifests.extend(by_name.get(name, []))
    python_text = "\n".join(_read_text(p).lower() for p in python_manifests)
    for path in python_manifests:
        manifests.add(_relative(path, root))
    if python_manifests:
        frameworks.add("Python")
        if any(token in python_text for token in ("fastapi", "flask", "django", "starlette", "litestar")):
            types.add("backend-api")
        if any(token in python_text for token in ("typer", "click", "argparse", "textual", "rich")):
            types.add("cli-tui")
        if any(token in python_text for token in ("pandas", "polars", "pyspark", "apache-airflow", "dbt", "sqlalchemy")):
            types.add("data-etl")
        if any(token in python_text for token in ("torch", "tensorflow", "scikit-learn", "transformers", "xgboost", "mlflow")):
            types.add("ml-ai-model")
        if any(token in python_text for token in ("langchain", "llama-index", "anthropic", "openai", "mcp")):
            types.add("agent-automation-mcp")
        if "pytest" in python_text or (root / "tests").exists():
            test_tools.add("pytest")
            _add_command(commands, "test", "pytest", "Python project signals")
        if "ruff" in python_text or by_name.get("ruff.toml"):
            quality_tools.add("Ruff")
            _add_command(commands, "lint", "ruff check .", "Python project signals")
        if "mypy" in python_text or by_name.get("mypy.ini"):
            quality_tools.add("mypy")
            _add_command(commands, "typecheck", "mypy .", "Python project signals")

    if by_name.get("cargo.toml"):
        types.add("cli-tui" if any("src/main.rs" in _relative(p, root) for p in files) else "library-sdk")
        frameworks.add("Rust")
        for p in by_name["cargo.toml"]:
            manifests.add(_relative(p, root))
        _add_command(commands, "build", "cargo build", "Cargo.toml")
        _add_command(commands, "test", "cargo test", "Cargo.toml")
        _add_command(commands, "lint", "cargo clippy --all-targets --all-features -- -D warnings", "Cargo.toml")

    if by_name.get("go.mod"):
        types.add("backend-api" if any(re.search(r"/(cmd|api|server)/", f"/{_relative(p, root)}/") for p in files) else "library-sdk")
        frameworks.add("Go")
        for p in by_name["go.mod"]:
            manifests.add(_relative(p, root))
        _add_command(commands, "test", "go test ./...", "go.mod")
        _add_command(commands, "lint", "go vet ./...", "go.mod")

    java_manifests = by_name.get("pom.xml", []) + by_name.get("build.gradle", []) + by_name.get("build.gradle.kts", [])
    if java_manifests:
        types.add("backend-api")
        frameworks.add("JVM")
        for p in java_manifests:
            manifests.add(_relative(p, root))
        if by_name.get("pom.xml"):
            _add_command(commands, "test", "mvn test", "pom.xml")
        elif (root / "gradlew").exists():
            _add_command(commands, "test", "./gradlew test", "Gradle wrapper")
        else:
            _add_command(commands, "test", "gradle test", "Gradle project")

    if by_name.get("pubspec.yaml"):
        types.add("mobile")
        frameworks.add("Flutter")
        manifests.update(_relative(p, root) for p in by_name["pubspec.yaml"])
        _add_command(commands, "test", "flutter test", "pubspec.yaml")
        _add_command(commands, "lint", "flutter analyze", "pubspec.yaml")

    if (root / "android").is_dir() or (root / "ios").is_dir():
        if "web-ui" not in types or any(x in js_deps for x in ("react-native", "expo")):
            types.add("mobile")

    if by_name.get("tauri.conf.json") or by_name.get("tauri.conf.json5"):
        types.add("desktop")
        frameworks.add("Tauri")

    infra_extensions = {".tf", ".tfvars"}
    if any(p.suffix.lower() in infra_extensions for p in files) or by_name.get("dockerfile") or by_name.get("docker-compose.yml") or by_name.get("compose.yaml"):
        types.add("infrastructure-devops")
    if any("k8s" in p.parts or "kubernetes" in p.parts or p.name.lower() in {"helmfile.yaml", "chart.yaml"} for p in files):
        types.add("infrastructure-devops")
        frameworks.add("Kubernetes/Helm")
    if any(p.suffix.lower() == ".tf" for p in files):
        frameworks.add("Terraform")
        _add_command(commands, "validate", "terraform validate", "Terraform files")

    db_signals = ("migrations", "prisma", "schema.sql", "flyway", "liquibase", "alembic")
    if any(any(signal in part.lower() for signal in db_signals) for p in files for part in p.parts):
        types.add("database")

    notebook_count = sum(1 for p in files if p.suffix.lower() == ".ipynb")
    data_count = sum(1 for p in files if p.suffix.lower() in {".csv", ".parquet", ".avro", ".feather"})
    if notebook_count or data_count:
        types.add("data-etl")

    doc_exts = {".md", ".rst", ".adoc", ".docx", ".pdf", ".pptx", ".txt"}
    media_exts = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".mp4", ".mov", ".wav", ".mp3"}
    code_exts = {".js", ".jsx", ".ts", ".tsx", ".py", ".go", ".rs", ".java", ".kt", ".swift", ".cs", ".cpp", ".c", ".rb", ".php"}
    doc_count = sum(1 for p in files if p.suffix.lower() in doc_exts)
    media_count = sum(1 for p in files if p.suffix.lower() in media_exts)
    code_count = sum(1 for p in files if p.suffix.lower() in code_exts)
    if doc_count and code_count == 0:
        types.add("document-content")
    if media_count and code_count == 0:
        types.add("design-media")

    if any(p.name.lower() in {"openapi.yaml", "openapi.yml", "openapi.json", "swagger.yaml", "schema.graphql"} for p in files):
        types.add("backend-api")
        frameworks.add("API schema")

    ci_files = [p for p in files if ".github/workflows" in _relative(p, root) or p.name.lower() in {"gitlab-ci.yml", "jenkinsfile", "circle.yml"}]
    if ci_files:
        quality_tools.add("CI")

    searchable = " ".join(
        [" ".join(js_deps), python_text]
        + [_relative(p, root).lower() for p in files[:5000]]
    )
    for pattern, label in {
        r"stripe|payment|billing|checkout|toss": "payment-or-billing",
        r"oauth|openid|jwt|auth|session|rbac": "authentication-or-authorization",
        r"pii|personal|privacy|gdpr|hipaa|resident|patient": "personal-or-sensitive-data",
        r"mail|email|slack|discord|sms|webhook": "external-message-or-webhook",
        r"migration|alembic|prisma|flyway|liquibase": "data-migration",
        r"terraform|kubernetes|helm|docker|deploy": "operational-infrastructure",
        r"anthropic|openai|llm|agent|mcp|langchain": "ai-or-agent-execution",
    }.items():
        if re.search(pattern, searchable, flags=re.IGNORECASE):
            risk_signals.add(label)

    if not types:
        types.add("unknown")
        notes.append("No strong project-type signal found; manual classification is required.")

    primary_priority = [
        "mixed-product", "web-ui", "mobile", "desktop", "backend-api",
        "agent-automation-mcp", "data-etl", "ml-ai-model", "infrastructure-devops",
        "database", "cli-tui", "library-sdk", "document-content", "design-media", "unknown",
    ]
    substantive = {t for t in types if t not in {"database", "infrastructure-devops"}}
    if len(substantive) >= 2 and any(t in substantive for t in {"web-ui", "mobile", "desktop"}) and "backend-api" in substantive:
        types.add("mixed-product")
    sorted_types = sorted(types, key=lambda t: primary_priority.index(t) if t in primary_priority else 999)

    result = {
        "root": str(root),
        "project_types": sorted_types,
        "primary_type": sorted_types[0],
        "frameworks": sorted(frameworks),
        "manifests": sorted(manifests),
        "test_tools": sorted(test_tools),
        "quality_tools": sorted(quality_tools),
        "suggested_commands": commands,
        "risk_signals": sorted(risk_signals),
        "inventory": {
            "files_scanned": len(files),
            "code_files": code_count,
            "document_files": doc_count,
            "media_files": media_count,
            "notebooks": notebook_count,
            "data_files": data_count,
            "ci_files": len(ci_files),
        },
        "notes": notes,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root to inspect")
    parser.add_argument("--output", help="Optional JSON output path")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args()

    result = detect_project(Path(args.root))
    text = json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
