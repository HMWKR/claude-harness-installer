#!/usr/bin/env python3
"""~/.claude 하네스를 이 레포의 payload/로 내보낸다 (개인 정보 제거 포함).

사용: python3 tools/export.py [--src ~/.claude] [--out <repo 루트>]

- 화이트리스트에 있는 것만 복사한다. 세션 기록·메모리·캐시·자격 증명은 대상이 아니다.
- 홈 경로는 __HOME__ 자리표시자로 바꾸고, install.sh가 설치할 때 $HOME으로 되돌린다.
- 원본 레포가 있는 외부 스킬(~/.agents/.skill-lock.json에 기록된 것)은 복사하지 않고
  manifest/skills.json에 출처만 남긴다. 설치 때 원본에서 받는다.
- 끝에 개인 정보 의심 패턴을 스캔해 남은 것이 있으면 exit 1.
"""
import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

HOME = str(Path.home())
INCLUDE = [
    "CLAUDE.md", "rules", "scripts", "skills", "agents", "commands", "workflows",
    "adapters", "verification-templates", "patches", "bkit.config.json",
]
INCLUDE_GLOBS = ["hookify.*.local.md"]
SKIP_NAMES = {"__pycache__", ".DS_Store", "node_modules", "state", ".claude", ".omc",
              "anti-loop-state.json", "anti-loop-state.json.bak", ".env", ".credentials.json"}
SKIP_SUFFIXES = (".pyc", ".log", ".pem", ".key", ".zip")  # .zip: 받은 원본 아카이브는 재배포하지 않는다
SKIP_SKILLS = {"synced"}  # claude.ai 계정 동기화 스킬 — 계정마다 다르다
# 소유자 머신 전용 권한(홈 경로 기반 Read, 개인 열람 사이트)은 설치자에게 맞지 않는다
PERSONAL_PERM = re.compile(r"^Read\(//" + re.escape(HOME.lstrip("/")) + r"|^WebFetch\(domain:")
ORCA_MARK = ".orca/agent-hooks"  # Orca 앱이 주입한 훅 — 하네스가 아니다
# 새 환경에서 clone이 실패하고 하네스에 필수가 아니어서 배포판에서 뺀다(insane-search 1개뿐)
DROP_MARKETPLACES = {"gptaku-plugins"}
# 내장이라 settings에 없지만 새 환경에는 등록돼 있지 않은 공식 마켓플레이스
OFFICIAL = {"claude-plugins-official": {"source": "github", "repo": "anthropics/claude-plugins-official"}}


def is_text(p: Path) -> bool:
    try:
        chunk = p.read_bytes()[:8192]
    except OSError:
        return False
    if b"\0" in chunk:
        return False
    try:
        chunk.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


# 개인·회사 고유 문자열 치환표({"원문": "치환"}). 금칙어 자체가 공개 레포에 실리지 않도록
# 레포 밖(기본 ~/.config/harness-export/redact.json, HARNESS_REDACT로 변경)에서 읽는다.
_REDACT_FILE = Path(os.environ.get("HARNESS_REDACT", Path(HOME, ".config/harness-export/redact.json")))
REDACT = json.loads(_REDACT_FILE.read_text()) if _REDACT_FILE.exists() else {}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@(?!anthropic\.com|users\.noreply)[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.(?!json|png|jpe?g|webp|svg|html?|md|js|ts|css|txt|yml|yaml)[a-z]{2,}\b")


def scrub_text(s: str) -> str:
    s = s.replace(HOME, "__HOME__")
    for k, v in REDACT.items():
        s = s.replace(k, v)
    return EMAIL.sub("<redacted-email>", s)


def copy_tree(src: Path, dst: Path, skip_top=()):
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        dirs[:] = [d for d in dirs if d not in SKIP_NAMES
                   and not (rel == Path(".") and d in skip_top)
                   and not (Path(root, d).is_symlink())]
        for f in files:
            sp = Path(root, f)
            if f in SKIP_NAMES or f.endswith(SKIP_SUFFIXES) or sp.is_symlink():
                continue
            if "state" in f and f.endswith(".json") and "scripts" in sp.parts:
                continue
            dp = dst / rel / f
            dp.parent.mkdir(parents=True, exist_ok=True)
            if is_text(sp):
                dp.write_text(scrub_text(sp.read_text(encoding="utf-8")), encoding="utf-8")
            else:
                shutil.copy2(sp, dp)
            os.chmod(dp, sp.stat().st_mode & 0o777)


def strip_orca(hooks: dict) -> dict:
    out = {}
    for ev, matchers in hooks.items():
        kept = []
        for m in matchers:
            hs = [h for h in m.get("hooks", []) if ORCA_MARK not in h.get("command", "")]
            if hs:
                kept.append({**m, "hooks": hs})
        if kept:
            out[ev] = kept
    return out


def export_settings(src: Path, out: Path):
    s = json.loads((src / "settings.json").read_text())
    s["hooks"] = strip_orca(s.get("hooks", {}))
    if ORCA_MARK in json.dumps(s.get("statusLine", "")):
        s.pop("statusLine")
    # autoMode.environment는 특정 회사·저장소 설명이다 — 설치자 환경에 맞지 않는다
    if "autoMode" in s:
        s["autoMode"].pop("environment", None)
        if not s["autoMode"]:
            s.pop("autoMode")
    for name in DROP_MARKETPLACES:
        s.get("extraKnownMarketplaces", {}).pop(name, None)
        for pid in [k for k in s.get("enabledPlugins", {}) if k.endswith("@" + name)]:
            s["enabledPlugins"].pop(pid)
    perms = s.get("permissions", {})
    perms["additionalDirectories"] = [d for d in perms.get("additionalDirectories", [])
                                      if not d.startswith(HOME)]
    for k in ("allow", "ask"):
        perms[k] = [r for r in perms.get(k, []) if not PERSONAL_PERM.search(r)]

    # settings.local.json은 cwd가 홈일 때만 읽힌다. 훅(anti-loop·checkpoint)만 전역 settings로
    # 합치고, 그 파일의 넓은 Bash 자동 허용(curl·python3·rm 등)은 공개본에 싣지 않는다.
    loc = json.loads((src / "settings.local.json").read_text())
    for ev, matchers in strip_orca(loc.get("hooks", {})).items():
        s["hooks"].setdefault(ev, []).extend(matchers)
    (out / "settings.json").write_text(
        scrub_text(json.dumps(s, ensure_ascii=False, indent=2)) + "\n", encoding="utf-8")
    return s


def export_skills(src: Path, out: Path, manifest: Path):
    lock_path = Path(HOME, ".agents/.skill-lock.json")
    lock = json.loads(lock_path.read_text())["skills"] if lock_path.exists() else {}
    external, vendored, dropped = [], [], []
    for d in sorted((src / "skills").iterdir()):
        name = d.name
        if name in SKIP_SKILLS or name.startswith("."):
            continue
        if name in lock:
            e = lock[name]
            external.append({"name": name, "source": e["source"], "skillPath": e.get("skillPath", "")})
        elif d.is_symlink():
            dropped.append(name)  # 출처 없는 로컬 링크 스킬(~/.agents) — 포함 범위 밖
        elif d.is_dir():
            copy_tree(d, out / "skills" / name)
            vendored.append(name)
    (manifest / "skills.json").write_text(json.dumps(
        {"external": external, "vendored": vendored, "excluded_local_links": dropped},
        ensure_ascii=False, indent=2) + "\n")
    return external, vendored, dropped


SCAN = [
    (re.compile(re.escape(HOME)), "home path"),
    (re.compile(re.escape(Path(HOME).name), re.I), "username"),
    (re.compile(r"claude\.ai/(code/)?artifact/[A-Za-z0-9-]+"), "claude.ai artifact"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"), "uuid"),
    (EMAIL, "email"),
    (re.compile(r"(gh[opsu]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|xox[bpa]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,})"), "token"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}"), "bearer"),
]


def scan(root: Path, extra):
    hits = []
    pats = SCAN + [(re.compile(re.escape(x), re.I), "custom:" + x) for x in [*extra, *REDACT]]
    for p in root.rglob("*"):
        if p.is_file() and ".git" not in p.parts and p != _REDACT_FILE and is_text(p):
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                for rx, label in pats:
                    if label == "uuid" and "threeui-reference/catalog/" in str(p):
                        continue  # 공개 카탈로그(threeui.com)의 항목 ID
                    if rx.search(line):
                        hits.append(f"{p.relative_to(root)}:{i}: [{label}] {line.strip()[:160]}")
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(Path(HOME, ".claude")))
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--extra-scan", default="", help="쉼표로 구분한 추가 금칙어")
    a = ap.parse_args()
    src, root = Path(a.src), Path(a.out)
    out, manifest = root / "payload" / ".claude", root / "manifest"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    manifest.mkdir(exist_ok=True)

    for item in INCLUDE:
        p = src / item
        if p.is_dir() and item != "skills":
            copy_tree(p, out / item)
        elif p.is_file():
            (out / item).write_text(scrub_text(p.read_text(encoding="utf-8")), encoding="utf-8")
    for g in INCLUDE_GLOBS:
        for p in src.glob(g):
            (out / p.name).write_text(scrub_text(p.read_text(encoding="utf-8")), encoding="utf-8")

    s = export_settings(src, out)
    ext, ven, drop = export_skills(src, out, manifest)
    (manifest / "plugins.json").write_text(json.dumps({
        "marketplaces": {**OFFICIAL, **{k: v["source"] for k, v in s.get("extraKnownMarketplaces", {}).items()}},
        "plugins": [k for k, v in s.get("enabledPlugins", {}).items() if v],
    }, ensure_ascii=False, indent=2) + "\n")

    print(f"payload: {sum(1 for _ in out.rglob('*') if _.is_file())} files")
    print(f"skills: vendored {len(ven)}, external {len(ext)}, excluded {drop}")
    extra = [x for x in a.extra_scan.split(",") if x]
    hits = scan(root, extra)
    if hits:
        print(f"\n개인 정보 의심 {len(hits)}건:")
        print("\n".join(hits[:200]))
        sys.exit(1)
    print("scan: clean")


if __name__ == "__main__":
    main()
