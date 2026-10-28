#!/usr/bin/env python3
"""understand-anything 훅의 `$TOOL_INPUT` → stdin JSON 재적용 스크립트 (멱등).

배경은 `patches/README.md` §3. 훅 입력은 stdin JSON인데 업스트림은 존재하지 않는
`$TOOL_INPUT` 환경변수를 읽어, git 커밋 후 지식그래프 자동갱신이 한 번도 발화한 적이
없었다. 캐시는 휘발성이라 플러그인 업데이트 후 이 스크립트를 다시 돌려야 한다
(`harness-sweep.py` 가 `$TOOL_INPUT` 참조를 다시 신고해 알려 준다).

사용법:
    python3 ~/.claude/patches/fix-understand-anything.py            # 적용(멱등)
    python3 ~/.claude/patches/fix-understand-anything.py --verify   # 격리 실동작 대조
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

OLD = """printf '%s' "$TOOL_INPUT\""""
NEW = ('python3 -c "import json,sys;d=json.load(sys.stdin);'
       "print((d.get('tool_input') or {}).get('command',''))\" 2>/dev/null")


def plugin_root() -> Path:
    inst = json.load(open(Path.home() / ".claude/plugins/installed_plugins.json"))["plugins"]
    arr = inst.get("understand-anything@understand-anything")
    if not arr:
        sys.exit("understand-anything 미설치")
    return Path(arr[0]["installPath"])


def apply() -> int:
    hj = plugin_root() / "hooks/hooks.json"
    d = json.load(open(hj))
    n = 0
    for _ev, groups in (d.get("hooks") or {}).items():
        for g in groups:
            for h in g.get("hooks", []):
                cmd = h.get("command", "")
                if OLD in cmd:
                    h["command"] = cmd.replace(OLD, NEW)
                    n += 1
    if n:
        json.dump(d, open(hj, "w"), ensure_ascii=False, indent=2)
        open(hj, "a").write("\n")
    print(f"patched: {n} (0이면 이미 적용됨 — 멱등)")
    return n


def verify() -> int:
    """격리 임시 프로젝트에서 실제 훅 커맨드를 돌려 양방향을 대조한다."""
    root = plugin_root()
    d = json.load(open(root / "hooks/hooks.json"))
    cmds = [h["command"] for g in (d.get("hooks") or {}).get("PostToolUse", [])
            for h in g.get("hooks", [])]
    if not cmds:
        sys.exit("PostToolUse 훅이 없다")
    cmd = cmds[0]
    ok = True
    with tempfile.TemporaryDirectory() as t:
        ua = Path(t) / ".understand-anything"
        ua.mkdir()
        (ua / "config.json").write_text('{"autoUpdate": true}')
        (ua / "knowledge-graph.json").write_text("{}")
        for payload, should_fire, label in (
                ('{"tool_input":{"command":"git commit -m x"}}', True, "git commit"),
                ('{"tool_input":{"command":"ls -la"}}', False, "무관한 명령")):
            p = subprocess.run(["sh", "-c", cmd], input=payload, capture_output=True,
                               text=True, cwd=t, timeout=30,
                               env={"PATH": "/usr/bin:/bin:/usr/local/bin",
                                    "CLAUDE_PLUGIN_ROOT": str(root)})
            fired = bool(p.stdout.strip())
            good = fired == should_fire
            ok &= good
            print(f"  {'PASS' if good else 'FAIL'}  {label}: "
                  f"발화={fired} 기대={should_fire}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else (apply() and 0))
