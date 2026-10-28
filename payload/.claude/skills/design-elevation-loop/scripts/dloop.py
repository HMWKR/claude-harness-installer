#!/usr/bin/env python3
"""dloop.py — design-elevation-loop 보조 도구 (표준 라이브러리만).

  init      --dir D --root R --url U [--url …] [--new]       작업 폴더·state.json·도구·기존 리서치 탐지
  resume    --root R                                         진행 중인 작업 폴더(W)를 찾아 상태를 보인다(재개는 늘 여기부터)
  questions --dir D --set scope|preset|quality1|quality2|process [--answers A]   AskUserQuestion 입력 JSON
  compile   --dir D --answers A [--relock --reason R] [--round-cap N]   답 → criteria.lock.json·DoD.md·goal 명령(판마다 locks/chain.jsonl)
  lockset   --dir D                                          research/comparison-set.json 잠금(기준선 전)
  measure   --dir D --round N --kind audit|axe|inspect|detect [--target DIR] [--fix-reason R]   도구를 직접 돌려 원 출력·지표를 만든다
  ingest    --dir D --round N --kind audit|axe|inspect|detect   이미 있는 원 출력에서 지표를 만든다(다른 환경용)
  set       --dir D --round N --metric ID --value V --evidence FILE   수동 기준 1개 기록
  seal      --dir D --round N --key FILE                     판정 전에 라벨 대응표(저장소 밖 파일)를 봉인한다
  panel     --dir D --round N                                봉인한 대응표·블라인드 판정 파일 → panel.* 지표
  personas  --dir D --round N                                페르소나 실행 기록·지적 → persona.* 지표
  check     --dir D [--round N]                              잠긴 기준 대비 판정
  status    --dir D                                          회차별 추이·정체·한도
  gate      --dir D --id ID [--evidence E]                   check를 직접 돌려 0일 때만 goals.py 마지막 단계를 닫는다(goal A)

check 종료 코드: 0 전부 충족 / 1 미달 있음 / 2 미달 없이 미측정 있음 / 3 잠금 변조·잠금 없음·한도 초과·최신 회차 아님.
측정·기록은 회차 차례를 지킨다(r0부터, 판정한 회차의 다음 회차로만). 다른 명령의 오류는 0이 아닌 코드와 'dloop:' 문장으로 알린다.
변경 감지(해시·출처·원 출력 지문)는 실수와 지름길을 막는 장치다. 의도적 위조까지 막는 보장은 최종 독립 검증이 한다.
"""
import argparse
import hashlib
import json
import math
import os
import re
import secrets
import shlex
import shutil
import statistics
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

try:
    import fcntl
except ImportError:          # Windows — 동시 기록 잠금 없이 동작한다
    fcntl = None

HERE = Path(__file__).resolve().parent
CATALOG = HERE / "catalog.json"
AUDIT_JS = HERE / "page-audit.js"
HOME = Path.home()
OPS = {"==": lambda a, b: a == b, "<=": lambda a, b: a <= b, ">=": lambda a, b: a >= b,
       "<": lambda a, b: a < b, ">": lambda a, b: a > b}
RECOMMENDED = " (권장)"
LIMITS = {"questions": (1, 4), "options": (2, 4), "header": 12}
SOURCE_OF = {"audit": "audit", "axe": "axe", "inspect": "inspect", "detect": "detect",
             "panel": "panel", "persona": "persona", "manual": "set"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")       # 다 쓴 뒤 바꿔 끼운다(중간에 끊겨도 반쪽 파일이 남지 않게)
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, p)


@contextmanager
def wlock(d):
    """같은 작업 폴더의 지표 기록은 한 번에 하나씩 — set을 동시에 돌려도 기록이 사라지지 않게."""
    with open(Path(d) / ".dloop.lock", "a") as f:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl:
                fcntl.flock(f, fcntl.LOCK_UN)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dir_digest(p):
    """폴더 안 파일 경로·내용의 지문. 집계 뒤 원 출력이 바뀌었는지 본다."""
    p = Path(p)
    h = hashlib.sha256()
    if p.is_file():
        h.update(sha(p).encode())
        return h.hexdigest()
    for f in sorted(x for x in p.rglob("*") if x.is_file()):
        h.update(str(f.relative_to(p)).encode() + b"\0" + sha(f).encode() + b"\n")
    return h.hexdigest()


def die(msg, code=2):
    print(f"dloop: {msg}", file=sys.stderr)
    sys.exit(code)


def catalog():
    return load(CATALOG)


def state(d):
    p = Path(d) / "state.json"
    if not p.exists():
        die(f"{p} 없음 — 먼저 init")
    return load(p)


def lock_of(d):
    p = Path(d) / "criteria.lock.json"
    if not p.exists():
        die("criteria.lock.json 없음 — 먼저 compile(기준을 잠근 뒤에만 측정값을 기록한다)")
    return load(p)


def log(d, event, **kw):
    with open(Path(d) / "log.md", "a", encoding="utf-8") as f:
        f.write(f"- {now()} {event} " + json.dumps(kw, ensure_ascii=False) + "\n")


def finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


# ---------------------------------------------------------------- init
def _exists(p):
    return str(p) if Path(p).exists() else None


def _newest_engine():
    hits = sorted((HOME / ".impeccable" / "bin").glob("*/impeccable"))
    return str(hits[-1]) if hits else None


TOOLS = {
    "aside": lambda: shutil.which("aside"),
    "node": lambda: shutil.which("node"),
    "codex": lambda: shutil.which("codex"),
    "runqa": lambda: _exists(HOME / ".claude/skills/design-toolchain/scripts/run-qa.sh"),
    "inspect": lambda: _exists(HOME / ".claude/skills/design-taste-frontend/scripts/inspect.mjs"),
    "gemini": lambda: shutil.which("gemini"),
    # 스킬의 실행기가 먼저다. PATH의 impeccable은 옛 3.x CLI일 수 있어 마지막에 본다
    "impeccable": lambda: _exists(HOME / ".claude/skills/impeccable/scripts/impeccable") or _newest_engine() or shutil.which("impeccable"),
    "goals": lambda: _exists(HOME / ".claude/plugins/marketplaces/fablize/scripts/goals.py"),
    "verify_lock": lambda: _exists(HOME / ".claude/scripts/verify-lock.py"),
}
def _tool(name):
    """실행할 도구 경로는 매번 고정 TOOLS 표에서 다시 찾는다 — 작업 폴더 state.json의 tools 값은 기록·표시용이고
    실행에 쓰지 않는다(저장소에 들어 있는 조작된 state.json이 임의 실행 파일을 가리키는 것을 막는다, 2026-10-16 보안 검토)."""
    env = os.environ.get(f"DLOOP_TOOL_{name.upper()}")
    if env is not None:   # 실행하는 사람이 정하는 환경 변수만 덮어쓸 수 있다(시험·비표준 설치용). 빈 값 = 없음
        return env or None
    f = TOOLS.get(name)
    return f() if f else None


RESEARCH_DIRS = ("web-crawling", "research", "competitors", "benchmark", "경쟁사", "레퍼런스")
SKIP = {"node_modules", ".git", "dist", "build", ".astro", ".next", ".cache", "archive"}


def detect_research(root, max_depth=4):
    found = []
    root = Path(root)

    def walk(p, depth):
        if depth > max_depth:
            return
        try:
            entries = list(p.iterdir())
        except OSError:
            return
        for e in entries:
            if e.name in SKIP or e.name.startswith("."):
                continue
            low = e.name.lower()
            if e.is_dir():
                if any(low.startswith(k) for k in RESEARCH_DIRS):
                    sites = [c for c in e.iterdir() if c.is_dir() and not c.name.startswith(".")]
                    dated = sorted(m.group(0) for f in e.rglob("*") if f.is_dir()
                                   for m in [re.search(r"\d{4}-\d{2}-\d{2}", f.name)] if m)
                    # 수집일은 폴더 이름의 날짜를 쓴다(복사하면 수정 시각이 바뀐다). 날짜 폴더가 없으면 수정 시각
                    found.append({"path": str(e.relative_to(root)), "kind": "dir", "entries": len(sites),
                                  "newest": dated[-1] if dated else _newest(e),
                                  "date_from": "folder-name" if dated else "mtime",
                                  "empty_files": sum(1 for f in e.rglob("*") if f.is_file() and f.stat().st_size == 0)})
                walk(e, depth + 1)
            elif low.endswith(".md") and ("benchmark" in low or "competitor" in low or "경쟁" in low):
                found.append({"path": str(e.relative_to(root)), "kind": "file",
                              "newest": date.fromtimestamp(e.stat().st_mtime).isoformat()})

    walk(root, 0)
    return found


def _newest(p):
    newest = 0.0
    for f in Path(p).rglob("*"):
        try:
            newest = max(newest, f.stat().st_mtime)
        except OSError:
            pass
    return date.fromtimestamp(newest).isoformat() if newest else None


def active_dirs(root):
    root = Path(root).resolve()
    cands = list(root.glob("tasks/design-loop-*/state.json")) + list(root.glob(".design-loop/*/state.json"))
    return sorted((p.parent for p in cands), key=lambda p: max((x.stat().st_mtime for x in p.rglob("*") if x.is_file()), default=0))


def cmd_resume(a):
    ws = active_dirs(a.root)
    if not ws:
        print("진행 중인 작업 폴더가 없다 — 새 루프면 init")
        return
    w = ws[-1]
    print(f"W = {w}" + (f"  (다른 작업 폴더 {len(ws) - 1}개: {', '.join(str(x) for x in ws[:-1])})" if len(ws) > 1 else ""))
    cmd_status(argparse.Namespace(dir=str(w)))


def cmd_init(a):
    d = Path(a.dir)
    if (d / "state.json").exists() and not a.force:
        die(f"{d}/state.json 이미 있음 — 이어서 하려면 status, 새로 시작하려면 --force")
    others = [w for w in active_dirs(a.root) if w.resolve() != d.resolve()]
    if others and not a.new:
        die("진행 중인 작업 폴더가 있다: " + ", ".join(str(w) for w in others)
            + " — 이어서 하려면 resume(날짜가 바뀌어도 그 폴더가 W다), 사용자가 새 루프를 원할 때만 --new")
    d.mkdir(parents=True, exist_ok=True)
    (d / "rounds").mkdir(exist_ok=True)
    root = Path(a.root).resolve()
    st = {
        "created": now(),
        "root": str(root),
        "targets": {"urls": a.url, "widths": [int(w) for w in a.widths.split(",") if w.strip()]},
        "tools": {k: f() for k, f in TOOLS.items()},
        "research": detect_research(root),
    }
    dump(d / "state.json", st)
    log(d, "init", targets=st["targets"])
    print(json.dumps({"tools": st["tools"], "research": st["research"]}, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- 검출기 설정 감시·예외
# 측정은 소스 안 예외 표식을 따르지 않는다(detect는 --no-inline-ignores, inspect는 중립 폴더에서 실행).
# 결함을 빼는 길은 exceptions.json 하나다. 검출기 설정 파일은 잠글 때의 해시와 비교한다.
GUARD_CONFIGS = (".impeccable/config.json", ".impeccable/config.local.json", ".impeccable/design.json")
EXCEPTION_FIELDS = {"allow": ("rule", "approval"), "config": ("file", "approval"), "detect": ("antipattern", "file")}


def scope_paths(d, scope):
    """잠금에는 작업 폴더 기준 상대 경로로 둔다 — 폴더를 옮기거나 복사해도 판정이 유지된다."""
    return (Path(d) / scope["root"]).resolve()


def guard_scan(d, scope):
    root = scope_paths(d, scope)
    return {"scope": scope, "configs": {c: (sha(root / c) if (root / c).exists() else None) for c in GUARD_CONFIGS}}


def _evidence_file(d, root, ev):
    """비어 있지 않은 일반 파일이고 작업 폴더나 저장소 안에 있어야 증거로 친다. 상대 경로는 작업 폴더, 그다음 저장소 기준."""
    if not ev:
        return None
    cands = [Path(ev)] if Path(ev).is_absolute() else [Path(d) / ev] + ([Path(root) / ev] if root else [])
    for p in cands:
        try:
            rp = p.resolve()
        except OSError:
            continue
        inside = any(str(rp).startswith(str(Path(x).resolve()) + os.sep) for x in (d, root) if x)
        if rp.is_file() and rp.stat().st_size > 0 and inside:
            return rp
    return None


def _rel(d, p):
    try:
        return os.path.relpath(Path(p).resolve(), Path(d).resolve())
    except ValueError:
        return str(Path(p).resolve())


def exceptions(d, lock, quiet=False):
    """exceptions.json의 유효한 항목만. 규칙 전체를 끄는 예외(allow·config)는 사용자 승인 원문(approval)이 있어야 한다."""
    p = Path(d) / "exceptions.json"
    if not p.exists():
        return []
    rows = load(p)
    if not isinstance(rows, list):
        die("exceptions.json은 배열이어야 한다", 3)
    root = scope_paths(d, lock["guards"]["scope"])
    ok = []
    for e in rows:
        need = EXCEPTION_FIELDS.get(e.get("kind")) if isinstance(e, dict) else None
        if need is None:
            if not quiet:
                print(f"  예외 무시: 종류는 {'·'.join(EXCEPTION_FIELDS)}만 — {json.dumps(e, ensure_ascii=False)[:100]}")
            continue
        if not str(e.get("reason", "")).strip() or not _evidence_file(d, root, e.get("evidence")) \
                or any(not str(e.get(k, "")).strip() for k in need):
            if not quiet:
                print(f"  예외 무시: reason·evidence·{'·'.join(need)} 중 빠진 것이 있다 — {json.dumps(e, ensure_ascii=False)[:100]}")
            continue
        ok.append(e)
    return ok


def exception_label(e):
    if e["kind"] == "allow":
        return f"inspect:{e['rule']}"
    if e["kind"] == "config":
        return f"설정:{e['file']}"
    return f"detect:{e['antipattern']}@{e['file']}" + (f":{e['line']}" if e.get("line") else "")


def guard_rows(d, lock):
    base = lock.get("guards")
    if not base:
        return []
    cur = guard_scan(d, base["scope"])
    ex = exceptions(d, lock, quiet=True)
    rows = []
    for c, h in cur["configs"].items():
        if h != base["configs"].get(c) and not any(e["kind"] == "config" and e["file"] == c for e in ex):
            rows.append({"id": f"guard.{c}", "status": "FAIL", "metric": "guard", "value": "changed",
                         "target": "exceptions.json에 사유·증거·사용자 승인", "gap": None})
    return rows


def allowed_rules(d, lock):
    return {e["rule"] for e in exceptions(d, lock) if e["kind"] == "allow"}


# ---------------------------------------------------------------- questions
def option_list(q, recommended_value):
    opts = []
    for o in q["options"]:
        label = o["label"] + (RECOMMENDED if o["value"] == recommended_value else "")
        item = {"label": label, "description": o["description"]}
        if o.get("preview") and not q.get("multiSelect"):
            item["preview"] = o["preview"]
        opts.append(item)
    opts.sort(key=lambda x: 0 if x["label"].endswith(RECOMMENDED) else 1)   # 권장안을 맨 앞에(AskUserQuestion 관례)
    return opts


def cumulative_checks(dim, level):
    merged = {}
    for lv in dim["levels"]:
        if lv["level"] > level:
            break
        for c in lv["checks"]:
            merged[c["id"]] = {**c, "level": lv["level"]}
    return list(merged.values())


def dimension_question(dim, tools=None):
    opts = []
    for lv in dim["levels"]:
        checks = cumulative_checks(dim, lv["level"])
        preview = "\n".join(f"- {c['desc']}" for c in checks)
        lacking = sorted({t for c in checks for t in c.get("requires", []) if tools is not None and not tools.get(t)})
        desc = lv["summary"] + (f" (이 환경에 없는 도구: {', '.join(lacking)} — 대체 경로는 measurement.md)" if lacking else "")
        opts.append({"label": lv["label"], "value": lv["level"],
                     "description": desc, "preview": f"{lv['label']} — 누적 검사\n{preview}"})
    return {"question": dim["question"], "header": dim["header"], "multiSelect": False, "options": opts}


def validate_payload(payload):
    qs = payload["questions"]
    if not qs:
        return payload
    lo, hi = LIMITS["questions"]
    if not lo <= len(qs) <= hi:
        die(f"질문 수 {len(qs)} — {lo}~{hi}개여야 한다")
    texts = [q["question"] for q in qs]
    if len(set(texts)) != len(texts):
        die("질문 문구 중복")
    for q in qs:
        if len(q["header"]) > LIMITS["header"]:
            die(f"머리 '{q['header']}' {len(q['header'])}자 — {LIMITS['header']}자 이하")
        lo, hi = LIMITS["options"]
        if not lo <= len(q["options"]) <= hi:
            die(f"'{q['header']}' 선택지 {len(q['options'])}개 — {lo}~{hi}개")
        labels = [o["label"] for o in q["options"]]
        if len(set(labels)) != len(labels):
            die(f"'{q['header']}' 선택지 이름 중복")
    return payload


def research_strength(st):
    return max((r.get("entries", 0) for r in st.get("research", []) if r["kind"] == "dir"), default=0)


def research_note(st):
    found = st.get("research", [])
    if not found:
        return "(탐지 결과: 기존 경쟁사·레퍼런스 리서치 없음)"
    top = sorted(found, key=lambda r: r.get("entries", 0), reverse=True)[:3]
    parts = [f"{r['path']}" + (f" {r['entries']}곳" if r["kind"] == "dir" else "") + f" ({r.get('newest')})"
             for r in top]
    return "(탐지 결과: " + ", ".join(parts) + ")"


def preset_preview(cat, key):
    lv = cat["presets"][key]["levels"]
    names = {x["id"]: x["header"] for x in cat["dimensions"]}
    return "\n".join(f"- {names[k]}: L{v}" for k, v in lv.items())


def cmd_questions(a):
    st = state(a.dir)
    tools = st.get("tools", {})
    cat = catalog()
    preset = cat["presets"][cat["default_preset"]]["levels"]
    if a.set in ("quality1", "quality2"):
        dims = {x["id"]: x for x in cat["dimensions"]}
        qs = []
        for i in cat["question_sets"][a.set]:
            q = dimension_question(dims[i], st.get("tools", {}))
            q["options"] = option_list(q, preset[i])
            qs.append(q)
    elif a.set == "preset":
        q = {"question": "완성도 기준을 어느 묶음으로 정할까요?", "header": "기준 묶음", "multiSelect": False,
             "options": [{"label": p["label"], "value": k, "description": p["summary"],
                          "preview": preset_preview(cat, k)} for k, p in cat["presets"].items()]}
        q["options"] = option_list(q, cat["default_preset"])
        qs = [q]
    else:
        qs = []
        for q in cat["fixed_questions"][a.set]:
            q = json.loads(json.dumps(q))
            rec = q.get("recommended")
            if q.get("dimension"):
                dim = next(x for x in cat["dimensions"] if x["id"] == q["dimension"])
                q = {**dimension_question(dim, st.get("tools", {})), "question": q.get("question", dim["question"])}
                rec = preset[dim["id"]]
            if q["header"] == "판정 엄격도" and not (tools.get("codex") or tools.get("gemini")):
                for o in q["options"]:
                    if o["value"] in ("standard", "strict"):
                        o["description"] += " — 다른 벤더 판정 도구를 찾지 못했다(MCP 등 다른 수단이 없으면 충족할 수 없다)"
                rec = "standard_same"
            if q["header"] == "goal 방식" and not tools.get("goals"):
                q["options"] = [o for o in q["options"] if o["value"] not in ("A", "AB")]   # goals.py가 없으면 기록 장부를 못 쓴다
                rec = "B"
            if q["header"] == "리서치":
                q["question"] += " " + research_note(st)
                rec = "reuse" if research_strength(st) >= 5 else "new_wide"
                if not st.get("research"):        # 탐지된 리서치가 없으면 '재사용' 선택지를 내지 않는다
                    q["options"] = [o for o in q["options"] if o["value"] != "reuse"]
            q["options"] = option_list(q, rec)
            qs.append({k: v for k, v in q.items() if k in ("question", "header", "multiSelect", "options")})
    answered = set()
    if a.answers and Path(a.answers).exists():
        raw = load(a.answers)
        answered = set((raw.get("answers", raw)).keys())
    skipped = [q["header"] for q in qs if q["header"] in answered or q["question"] in answered]
    qs = [q for q in qs if q["header"] not in answered and q["question"] not in answered]
    out = validate_payload({"questions": qs})
    if skipped:
        out["skipped_already_answered"] = skipped   # AskUserQuestion에는 questions만 넘긴다
    print(json.dumps(out, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- compile
def strip(label):
    return label[: -len(RECOMMENDED)] if label.endswith(RECOMMENDED) else label


def resolve(cat, answers):
    qdefs = [("dim", d["id"], dimension_question(d)) for d in cat["dimensions"]]
    for qs in cat["fixed_questions"].values():
        for q in qs:
            if not q.get("dimension"):
                qdefs.append(("choice", q["key"], q))
    qdefs.append(("preset", "preset", {"header": "기준 묶음", "question": "완성도 기준을 어느 묶음으로 정할까요?",
                                        "options": [{"label": p["label"], "value": k} for k, p in cat["presets"].items()]}))
    dims, choices = {}, {}
    for key, label in answers.items():
        bare = key.split(" (탐지 결과", 1)[0]          # 리서치 질문 문장 뒤 탐지 덧말은 떼고 맞춘다
        hit = next((x for x in qdefs if key in (x[2]["header"], x[2].get("question")) or bare == x[2].get("question")), None)
        if not hit:
            die(f"알 수 없는 질문 키 '{key}'")
        kind, ident, q = hit
        opt = next((o for o in q["options"] if o["label"] == strip(label)), None)
        if not opt:
            allowed = ", ".join(o["label"] for o in q["options"])
            die(f"'{key}'의 답 '{label}'이 선택지에 없음 — 기타 응답이면 가장 가까운 수준을 사용자와 확인하거나 custom 기준으로 넣는다. 선택지: {allowed}")
        if kind == "dim":
            dims[ident] = opt["value"]
        elif kind == "preset":
            for k, v in cat["presets"][opt["value"]]["levels"].items():
                dims.setdefault(k, v)
            choices["preset"] = opt["value"]
        else:
            choices[ident] = opt["value"]
    return dims, choices


SOURCE_TOOLS = {"audit": ("aside",), "axe": ("runqa",), "inspect": ("node", "inspect"), "detect": ("impeccable",)}


def chain_path(d):
    return Path(d) / "locks" / "chain.jsonl"


def chain_append(d, entry):
    """잠금·비교 대상의 판마다 한 줄 — check가 지금 파일이 마지막 판과 같은지 대조한다."""
    p = chain_path(d)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now(), **entry}, ensure_ascii=False) + "\n")


def chain_rows(d):
    p = chain_path(d)
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


def chain_last(d, kind):
    return next((r for r in reversed(chain_rows(d)) if r.get("kind") == kind), None)


def scope_sig(lock):
    """지표를 어느 대상·폭으로 쟀는지 — 다시 잠가 대상이 바뀌면 옛 지표는 미측정이 된다."""
    t = lock["targets"]
    blob = json.dumps({"urls": sorted(norm_url(u) for u in t["urls"]), "widths": sorted(t["widths"])})
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def cmd_compile(a):
    d = Path(a.dir)
    st = state(d)
    cat = catalog()
    lock = d / "criteria.lock.json"
    if not a.relock and (lock.exists() or chain_path(d).exists() or _round_dirs(d)):
        die("잠금 이력이 있다 — 기준 변경은 사용자 승인 후 --relock --reason \"<승인 원문>\"")
    if a.relock and not a.reason.strip():
        die("--relock에는 --reason(사용자 승인 원문)이 필요하다")
    raw = load(a.answers)
    answers = raw.get("answers", raw)
    dims, choices = resolve(cat, {k: v for k, v in answers.items() if isinstance(v, str)})
    base = cat["presets"][choices.get("preset", cat["default_preset"])]["levels"]
    if choices.get("mode", "detail") == "recommended":
        dims = {**base, **dims}
    missing = [x["id"] for x in cat["dimensions"] if x["id"] not in dims]
    if missing:
        die(f"수준이 정해지지 않은 차원: {', '.join(missing)} — 질문을 마저 하거나 기준 묶음을 고른다")
    criteria, notes, ingest_only = [], [], set()
    tools = st.get("tools", {})
    app_screens = choices.get("target") == "all"
    for dim in cat["dimensions"]:
        for c in cumulative_checks(dim, dims[dim["id"]]):
            src = c["source"]
            if app_screens and src == "inspect":
                notes.append(f"{c['id']}: inspect는 마케팅 페이지 규칙이라 앱 화면이 섞인 범위에서 뺐다 — 마케팅 페이지만 재려면 custom 기준으로")
                continue
            if src in ("inspect", "detect") and not all(tools.get(x) for x in SOURCE_TOOLS[src]):
                notes.append(f"{c['id']}: 이 환경에 {src} 검출기가 없어 뺐다 — 같은 역할의 검출기가 있으면 custom 기준으로 넣는다")
                continue
            if src in ("audit", "axe") and not all(tools.get(x) for x in SOURCE_TOOLS[src]):
                ingest_only.add(src)
            criteria.append({"id": c["id"], "dimension": dim["id"], "level": c["level"], "desc": c["desc"],
                             "metric": c["metric"], "op": c["op"], "value": c["value"], "source": src,
                             "na_ok": bool(c.get("na_ok"))})
    rigor_key = choices.get("rigor", "standard")
    rigor = cat["rigor"][rigor_key]
    for c in rigor["criteria"]:
        criteria.append({**c, "dimension": "rigor", "level": 0, "na_ok": False})
    if rigor["cross_vendor"] and not (tools.get("codex") or tools.get("gemini")):
        notes.append("rg.vendor: 다른 벤더 판정 도구(codex·gemini CLI)를 찾지 못했다 — MCP처럼 CLI 밖 수단이 있으면 그대로 쓰고, "
                     "없으면 사용자에게 알리고 '표준(동종)'으로 다시 잠근다")
    for c in raw.get("custom", []):
        for k in ("id", "desc", "metric", "op", "value", "source"):
            if k not in c:
                die(f"custom 기준에 {k} 없음: {c}")
        if c["op"] not in OPS and c["op"] != "true":
            die(f"custom 기준 연산자 {c['op']} — {list(OPS)} 또는 true")
        if c["source"] not in SOURCE_OF:
            die(f"custom 기준 출처 {c['source']} — {list(SOURCE_OF)}")
        criteria.append({**c, "dimension": c.get("dimension", "custom"), "level": c.get("level", 0),
                         "na_ok": bool(c.get("na_ok"))})
    for s in sorted(ingest_only):
        notes.append(f"{s}: 이 환경에 {'·'.join(SOURCE_TOOLS[s])}가 없어 다른 도구로 원 출력을 만들어 ingest로 잰다 — 형식은 references/measurement.md")
    if rigor["personas"] == 0 and any(c["source"] == "persona" for c in criteria):
        die("페르소나 기준(L3 이상)이 잠기는데 판정 엄격도 '가볍게'는 페르소나가 0명이다 — 엄격도를 표준 이상으로 하거나 수준을 사용자와 다시 정한다", 4)
    ids = [c["id"] for c in criteria]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        die(f"기준 id 중복: {dup}")
    targets = dict(raw.get("targets") or st.get("targets") or {})
    resp = next(x for x in cat["dimensions"] if x["id"] == "responsive")
    level_widths = [w for lv in resp["levels"] if lv["level"] <= dims["responsive"] for w in lv.get("widths", [])]
    targets["widths"] = sorted(set(targets.get("widths", [])) | set(level_widths))
    targets["urls"] = [u for u in targets.get("urls", []) if u]
    if not targets["urls"]:
        die("대상 URL이 없다 — 답 파일의 targets.urls에 범위에 맞는 실제 주소를 넣는다")
    if len({norm_url(u) for u in targets["urls"]}) != len(targets["urls"]):
        die("대상 URL이 정규화 뒤 중복된다")
    if choices.get("target") in ("journey", "public", "all") and len(targets["urls"]) == 1:
        notes.append("대상 범위가 여러 페이지인데 URL이 1개다 — 라우트·사이트맵에서 범위에 드는 페이지를 모두 넣었는지 확인한다")
    used_sources = {c["source"] for c in criteria}
    scope = {"root": _rel(d, st["root"])}
    cap = int(a.round_cap or choices.get("round_cap", cat["default_round_cap"]))
    if cap < 1:
        die("반복 한도는 1 이상")
    out = {
        "skill": "design-elevation-loop", "locked_at": now(),
        "targets": targets, "levels": dims, "choices": choices,
        "process": {"round_cap": cap,
                    "stall_k": int(cat["stall_k"]), "rigor": rigor_key,
                    "panel_axes": cat["panel_axes"], "judges": rigor["judges"], "quorum": rigor["quorum"],
                    "pair_quorum": rigor.get("pair_quorum", 0), "cross_vendor": rigor["cross_vendor"],
                    "personas": rigor["personas"], "goal": choices.get("goal", "A"),
                    # 이 환경에 도구가 있으면 그 출처의 지표는 dloop measure로 직접 잰 것만 인정한다
                    "require_runner": {k: all(tools.get(x) for x in v) for k, v in SOURCE_TOOLS.items() if k in used_sources}},
        "criteria": criteria,
        "notes": raw.get("notes", ""),
        "compile_notes": notes,
        "ingest_only": sorted(ingest_only),
        "guards": guard_scan(d, scope),
    }
    if lock.exists() and not a.reset_guards:      # 다시 잠가도 검출기 설정 기준선은 넘겨받는다(그 사이 바뀐 설정이 묻히지 않게)
        out["guards"] = load(lock)["guards"]
    prev = sha(lock) if lock.exists() else None
    if lock.exists():                       # 새 잠금을 다 만든 뒤에야 옛 잠금을 옮긴다(실패해도 옛 잠금이 남게)
        hist = d / "locks"
        hist.mkdir(exist_ok=True)
        shutil.move(str(lock), hist / f"criteria.{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.json")
    dump(lock, out)
    new = sha(lock)
    (d / "criteria.lock.sha256").write_text(new + "\n", encoding="utf-8")
    chain_append(d, {"kind": "compile", "sha": new, "prev": prev, "relock": bool(a.relock), "reason": a.reason})
    write_dod(d, out, cat)
    log(d, "compile", relock=bool(a.relock), reason=a.reason, levels=dims, choices=choices)
    print(f"locked: {len(criteria)} criteria → {lock} (잠금 {new[:12]})")
    for x in notes:
        print(f"  참고: {x}")
    print_goal(d, out, st)


def write_dod(d, lock, cat):
    names = {x["id"]: x["header"] for x in cat["dimensions"]}
    names["rigor"] = "평가 엄격도"
    lines = ["# 잠긴 완성도 기준(DoD)", "",
             f"- 잠금: {lock['locked_at']} · 반복 한도 {lock['process']['round_cap']}회(r0 포함) · 정체 판정 {lock['process']['stall_k']}회",
             "- 수준: " + ", ".join(f"{names.get(k, k)} L{v}" for k, v in lock["levels"].items()),
             f"- 대상: {', '.join(lock['targets']['urls'])} × 폭 {lock['targets']['widths']}", "",
             "| id | 차원 | 기준 | 지표 | 조건 | 출처 |", "|---|---|---|---|---|---|"]
    for c in lock["criteria"]:
        cond = "참" if c["op"] == "true" else f"{c['op']} {c['value']}"
        lines.append(f"| {c['id']} | {names.get(c['dimension'], c['dimension'])} | {c['desc']} | `{c['metric']}` | {cond} | {c['source']} |")
    lines += ["", "기준 변경은 사용자 승인 후 `dloop.py compile --relock --reason \"<승인 원문>\"`로만 한다."]
    (Path(d) / "DoD.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_goal(d, lock, st):
    mode = lock["process"]["goal"]
    W = Path(d).resolve()
    me = Path(__file__).resolve()
    q = shlex.quote
    check = f"python3 {q(str(me))} check --dir {q(str(W))}"
    lock_sha = sha(W / "criteria.lock.json")[:12]
    if mode in ("A", "AB"):
        goals = _tool("goals")
        if not goals:
            print("\n[goal A] goals.py를 찾지 못했다 — 사용자에게 알리고 B(네이티브 /goal)나 C로 다시 고른다")
        else:
            brief = (f"디자인 고도화 루프 — 잠금 {lock_sha}, 기준 {len(lock['criteria'])}개, "
                     f"반복 한도 {lock['process']['round_cap']}회(r0 포함). DoD {W / 'DoD.md'}")
            stories = [
                "리서치::경쟁사·레퍼런스 리서치가 기준 수준을 채우고 비교 대상이 잠겼다(dloop lockset)",
                "기준선::라운드 0 측정과 판정(rounds/r0/verdict.json)이 있다",
                f"개선 루프::{check} 가 0으로 끝난다 — 한도·정체 시 사용자 결정을 기록한다",
                "최종 검증::독립 검증(실행 모델 밖)이 증거를 재확인하고 잠금이 무결하다",
            ]
            cd = f"cd {q(str(W))} && python3 {q(goals)}"
            print("\n[goal A] 기록·재개용 장부 — 멈춤을 막지 않는다. goals.py는 매번 작업 폴더에서 부른다:")
            print(f"{cd} create --brief {q(brief)} " + " ".join(f"--goal {q(s)}" for s in stories))
            print(f"{cd} next")
            print(f"{cd} status")
            print(f"마지막 단계는 손으로 닫지 않는다 — check를 직접 돌려 0일 때만 닫는다: python3 {q(str(me))} gate --dir {q(str(W))} --id <마지막 id>")
            print(f"미달로 마무리(사용자 결정): {cd} checkpoint --id <id> --status blocked --evidence \"<사용자 결정 원문> + <check 출력>\"")
    if mode in ("B", "AB"):
        print("\n[goal B] 멈춤 차단 — 사용자가 직접 입력할 문구(모델은 /goal을 설정할 수 없고, 판정은 대화만 보는 작은 모델이 한다). 문구를 준 뒤 이번 턴을 끝낸다:")
        print(f"/goal design-elevation-loop 회차를 반복한다. 끝나는 조건: 마지막 응답에 `{check}` 출력이 그대로 붙어 있고 "
              "그 출력에 'all locked criteria passed'가 있으며 최종 독립 검증 결과가 보고됐다. 또는 반복 한도"
              f"({lock['process']['round_cap']}회, r0 포함)에 닿았거나 같은 기준이 접근을 바꾼 뒤에도 다시 정체돼 사용자에게 결정을 물었다.")
    if mode == "C":
        print("\n[goal C] goal 없이 진행 — 완료 판정은 여전히 check 종료 코드 0이다.")


# ---------------------------------------------------------------- lockset
def cmd_lockset(a):
    d = Path(a.dir)
    lock_of(d)
    p = d / "research" / "comparison-set.json"
    if not p.exists():
        die(f"{p} 없음 — 리서치 단계에서 비교 대상 목록을 먼저 쓴다")
    comps = load(p).get("competitors", [])
    if not comps or any(not c.get("name") for c in comps):
        die("competitors가 비었거나 name 없는 항목이 있다")
    names = [c["name"] for c in comps]
    if len(set(names)) != len(names):
        die("비교 대상 이름 중복")
    if any(Path(d, "rounds", r, "panel").exists() for r in _round_dirs(d)):
        die("이미 봉인·판정한 회차가 있다 — 비교 대상은 기준선 판정 전에 잠근다")
    s = sha(p)
    (d / "comparison-set.sha256").write_text(s + "\n", encoding="utf-8")
    chain_append(d, {"kind": "lockset", "sha": s, "competitors": names})
    log(d, "lockset", competitors=names)
    print(f"comparison set locked: {', '.join(names)}")
    if len(names) < 2:
        print("  참고: 직접 경쟁 1곳 — 경쟁 우위 판정이 한 곳에 좌우된다. 리서치로 더 찾을 수 있으면 보탠다")


def locked_competitors(d):
    p, s = Path(d) / "research" / "comparison-set.json", Path(d) / "comparison-set.sha256"
    if not (p.exists() and s.exists()):
        die("비교 대상이 잠기지 않았다 — lockset 먼저", 3)
    last = chain_last(d, "lockset")
    if s.read_text().strip() != sha(p) or not last or last.get("sha") != sha(p):
        die("comparison-set.json이 잠근 판과 다르다", 3)
    return [c["name"] for c in load(p)["competitors"]]


# ---------------------------------------------------------------- metrics store
def _round_dirs(d):
    r = Path(d) / "rounds"
    return sorted((x.name for x in r.iterdir() if x.is_dir() and re.fullmatch(r"r\d+", x.name)),
                  key=lambda n: int(n[1:])) if r.exists() else []


def metrics_path(d, n):
    return Path(d) / "rounds" / f"r{n}" / "metrics.json"


FIX_REASON = {"value": None}


def round_gate(d, n, lock):
    """측정·기록은 차례로: r0부터, 판정(check)한 마지막 회차의 다음 회차로만, 반복 한도 안에서.
    폴더가 있는지가 아니라 판정 기록으로 따진다(원 출력을 먼저 놓으면 폴더가 생기기 때문이다)."""
    if n < 0:
        die("회차는 0 이상")
    cap = lock["process"]["round_cap"]
    if n > cap - 1:
        die(f"r{n}은 반복 한도({cap}회, r0 포함)를 넘는다 — 사용자 승인 후 relock으로 한도를 바꾼다", 3)
    k = judged_upto(d)
    if n > k + 1:
        die("첫 측정은 r0(기준선)이다 — r0을 판정(check)한 뒤 다음 회차로 넘어간다" if k < 0
            else f"회차를 건너뛸 수 없다 — 다음은 r{k + 1}(판정한 뒤에 그다음 회차)")
    if n < k:
        die(f"r{n}은 지난 회차다 — 마지막으로 판정한 회차는 r{k}")


def judged_upto(d):
    """r0부터 판정 기록이 끊기지 않고 이어지는 마지막 회차(-1 = 아직 없음)."""
    k = -1
    while (Path(d) / "rounds" / f"r{k + 1}" / "verdict.json").exists():
        k += 1
    return k


def current_round(d):
    """판정 차례인 회차 — 판정이 이어진 다음 회차의 폴더가 있으면 그 회차, 없으면 마지막으로 판정한 회차(None = 측정 전)."""
    k = judged_upto(d)
    if (Path(d) / "rounds" / f"r{k + 1}").is_dir():
        return k + 1
    return k if k >= 0 else None


def guard_round(d, n):
    """이미 판정한 회차에는 새 측정을 넣지 않는다. 측정 오류를 고칠 때만 --fix-reason을 주고, 옛 판정은 보존한다."""
    v = Path(d) / "rounds" / f"r{n}" / "verdict.json"
    if not v.exists():
        return
    if not FIX_REASON["value"]:
        die(f"r{n}은 이미 판정했다 — 개선 뒤 측정은 새 회차(r{n + 1})에 한다. 측정 오류를 고치는 재측정이면 --fix-reason \"<사유>\"")
    keep = v.with_name(f"verdict.{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.json")
    shutil.move(str(v), keep)
    log(d, "remeasure", round=n, reason=FIX_REASON["value"], kept=keep.name)


def begin(d, n, lock):
    round_gate(d, n, lock)
    guard_round(d, n)


def replace_source(d, n, lock, source, values, evidence):
    """한 출처의 지표를 통째로 바꾼다 — 다시 집계에 실패하면 옛 통과값이 남지 않는다."""
    guard_round(d, n)
    runner, rround = runner_of(evidence)
    digest = dir_digest(evidence) if Path(evidence).exists() else None
    with wlock(d):
        p = metrics_path(d, n)
        data = load(p) if p.exists() else {"round": n, "metrics": {}}
        data["metrics"] = {k: v for k, v in data["metrics"].items() if v.get("source") != source}
        for m, v in values.items():
            data["metrics"][m] = {"value": v, "evidence": _rel(d, evidence), "source": source, "round": n,
                                  "scope": scope_sig(lock), "raw_sha": digest, "runner": runner,
                                  "runner_round": rround, "at": now()}
        dump(p, data)


def runner_of(raw_dir):
    r = Path(raw_dir) / "runner.json"
    if not r.exists():
        return None, None
    j = load(r)
    return j.get("runner"), j.get("round")


def parse_value(v):
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        x = int(v)
    except ValueError:
        try:
            x = float(v)
        except ValueError:
            die(f"값 '{v}' — 숫자 또는 true/false만")
    if not finite(x):
        die(f"값 '{v}' — 유한한 숫자만")
    return x


# ---------------------------------------------------------------- URL·폭
def norm_url(u):
    """출처(scheme·host·port)와 경로로 비교한다. 기본 포트·끝의 index.html·끝 빗금·쿼리 r(캐시 피하기)은 지우고, 해시는 '#/' 라우트만 남긴다."""
    p = urlparse(u)
    host = (p.hostname or "").lower()
    try:
        port = p.port
    except ValueError:
        port = None
    if port and not ((p.scheme == "http" and port == 80) or (p.scheme == "https" and port == 443)):
        host += f":{port}"
    path = re.sub(r"/index\.html?$", "/", p.path).rstrip("/") or "/"
    q = urlencode([(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k != "r"])
    frag = p.fragment if p.fragment.startswith("/") else ""
    return urlunparse((p.scheme, host, path, "", q, frag))


AUDIT_MAX = ("overflow.px", "contrast.fail_normal", "contrast.fail_large", "contrast.unknown_bg", "type.size_steps",
             "type.families", "type.measure_em_latin", "type.measure_em_cjk", "target.small24", "target.button_lt44",
             "img.broken", "img.alt_missing", "img.no_dimensions", "img.legacy_format", "motion.layout_anim",
             "struct.heading_skips", "text.placeholder", "text.generic_links", "dom.nodes", "perf.lcp_ms", "perf.cls",
             "perf.js_kb", "perf.transfer_kb", "css.unreadable_sheets")
AUDIT_MIN = ("contrast.normal_min", "contrast.large_min", "type.body_px_min", "type.line_height_min", "struct.main")
AUDIT_ALL = ("motion.reduced_rule", "focus.rule", "struct.lang")
NA_ALLOWED = {"contrast.normal_min", "contrast.large_min", "type.body_px_min", "type.line_height_min",
              "type.measure_em_latin", "type.measure_em_cjk"}   # 그 페이지에 해당 글자가 없을 수 있다


# ---------------------------------------------------------------- ingest
def ingest_audit(d, n, lock):
    adir = Path(d) / "rounds" / f"r{n}" / "audit"
    files = [f for f in sorted(adir.glob("*.json")) if f.name != "runner.json"]
    if not files:
        die(f"{adir}/*.json 없음 — page-audit.js 결과를 먼저 저장한다(measure --kind audit)")
    runs = [load(f) for f in files]
    want = [(norm_url(u), w) for u in lock["targets"]["urls"] for w in lock["targets"]["widths"]]
    have = {}
    for f, r in zip(files, runs):
        if not isinstance(r, dict) or "metrics" not in r or not finite(r.get("width")):
            die(f"{f.name}: page-audit 결과 형식이 아니다")
        k = (norm_url(str(r.get("url", ""))), int(r["width"]))
        rq = dict(parse_qsl(urlparse(str(r.get("url", ""))).query)).get("r")
        if rq is not None and rq != str(n):
            die(f"{f.name}: 다른 회차(r={rq})에서 잰 결과다 — 이 회차에서 다시 잰다")
        if k in have:
            die(f"같은 대상·폭 결과가 둘이다: {k}")
        have[k] = r
    missing = [k for k in want if k not in have]       # 폭은 정확히 일치해야 한다(±허용 없음)
    values = {"audit.coverage": round(1 - len(missing) / len(want), 6)}
    if missing:
        replace_source(d, n, lock, "audit", values, adir)
        print("측정 안 된 대상(지표를 만들지 않는다): " + ", ".join(f"{u}@{w}" for u, w in missing))
        return
    use = [have[k] for k in want]
    for m in AUDIT_MAX + AUDIT_MIN:
        raw = [r["metrics"].get(m, "MISSING") for r in use]
        if "MISSING" in raw or any(v is None for v in raw) and m not in NA_ALLOWED:
            print(f"측정 실패(값 없음): {m} — 미측정으로 남긴다")
            continue
        vals = [v for v in raw if finite(v)]
        if len(vals) + sum(1 for v in raw if v is None) != len(raw):
            print(f"숫자가 아닌 값: {m} — 미측정으로 남긴다")
            continue
        values[m] = (max(vals) if m in AUDIT_MAX else min(vals)) if vals else None
    for m in AUDIT_ALL:
        raw = [r["metrics"].get(m) for r in use]
        if all(isinstance(v, bool) for v in raw):
            values[m] = all(raw)
    values["struct.h1_bad"] = sum(1 for r in use if r["metrics"].get("struct.h1") != 1)
    replace_source(d, n, lock, "audit", values, adir)
    print(f"r{n} audit: {len(use)}개 측정 → 지표 {len(values)}개")


def _json_lines(text, tag):
    out = []
    for s in re.findall(rf"^{tag} (.*)$", text, re.M):
        try:
            out.append(json.loads(s))
        except json.JSONDecodeError:
            pass
    return out


def ingest_axe(d, n, lock):
    """run-qa.sh의 measure-*.txt(VITALS·AXE 줄). VITALS의 route는 경로만 있어 경로로 맞춘다(출처 비교 불가 — 한계)."""
    qdir = Path(d) / "rounds" / f"r{n}" / "qa"
    files = sorted(qdir.rglob("measure-*.txt"))
    if not files:
        die(f"{qdir}/**/measure-*.txt 없음 — measure --kind axe 또는 run-qa.sh 출력을 rounds/r{n}/qa/<페이지>/에 둔다")
    want = {urlparse(u).path.rstrip("/") or "/" for u in lock["targets"]["urls"]}
    seen, serious, total, held = {}, 0, 0, 0
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        vit = next(iter(_json_lines(text, "VITALS")), None)
        axe = {}
        for part in _json_lines(text, "AXE"):
            if isinstance(part, dict):
                axe.update(part)
        combos = [axe.get(k) for k in ("dark_window", "dark_375", "light_window", "light_375")]
        if not isinstance(vit, dict) or vit.get("route") is None or vit.get("status") != 200 \
                or any(not isinstance(r, dict) or "error" in r or not isinstance(r.get("violations"), list) for r in combos):
            print(f"불완전: {f}")
            continue
        route = vit["route"].rstrip("/") or "/"
        if route in seen:
            die(f"같은 페이지의 axe 결과가 둘이다: {route} ({seen[route]}, {f})")
        seen[route] = f
        for r in combos:
            total += len(r["violations"])
            serious += sum(1 for v in r["violations"] if str(v.get("impact")).lower() in ("serious", "critical"))
            held += len(r.get("incomplete", []))
    missing = sorted(want - set(seen))
    values = {"axe.coverage": round(1 - len(missing) / len(want), 6)}
    if not missing:
        values.update({"axe.serious_critical": serious, "axe.violations": total, "axe.incomplete": held})
    replace_source(d, n, lock, "axe", values, qdir)
    if missing:
        print("axe가 완전히 측정되지 않은 페이지(지표를 만들지 않는다): " + ", ".join(missing))
    else:
        print(f"r{n} axe: 페이지 {len(seen)}개 — 위반 {total}(심각·치명 {serious}), 보류 {held}")


def _round_start(d, lock, n):
    prev = Path(d) / "rounds" / f"r{n - 1}" / "verdict.json"
    return load(prev)["at"] if n > 0 and prev.exists() else lock["locked_at"]


def _iso(s):
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def ingest_inspect(d, n, lock):
    """inspect.mjs report.json. 회차 시작 전·미래 시각·빈 결과·대상 불일치는 받지 않는다."""
    idir = Path(d) / "rounds" / f"r{n}" / "inspect"
    files = [f for f in sorted(idir.glob("*.json")) if f.name != "runner.json"]
    since, limit = _iso(_round_start(d, lock, n)), datetime.now(timezone.utc) + timedelta(minutes=5)
    allowed = allowed_rules(d, lock)
    want = {norm_url(u) for u in lock["targets"]["urls"]}
    seen, fails, excepted = set(), 0, 0
    for f in files:
        r = load(f)
        at = _iso(r.get("at"))
        if not at or at < since or at > limit:
            die(f"{f.name}: report.at {r.get('at')} — 회차 시작({since:%Y-%m-%d %H:%M}) 뒤·지금 앞이어야 한다(크래시하면 옛 보고서가 남는다)")
        vps = r.get("viewports") or []
        if not vps or any(v.get("load") == "timeout" for v in vps):
            die(f"{f.name}: 측정한 폭이 없거나 로드 시간 초과 — 미측정")
        widths = [v.get("width", 0) for v in vps]
        if not (any(w >= 1100 for w in widths) and any(w <= 480 for w in widths)):
            die(f"{f.name}: 데스크톱(≥1100)과 모바일(≤480) 폭을 모두 재야 한다 — {widths}")
        u = norm_url(str(r.get("url", "")))
        if u not in want:
            die(f"{f.name}: 대상이 아닌 URL {r.get('url')}")
        if u in seen:
            die(f"{f.name}: 같은 URL 보고서가 둘이다")
        seen.add(u)
        extra = set(r.get("allow") or []) - allowed
        if extra:
            die(f"{f.name}: exceptions.json에 사유·증거 없는 허용 규칙 {sorted(extra)}")
        for x in r.get("findings", []):
            if x.get("level") == "FAIL":
                if x.get("id") in allowed:
                    excepted += 1
                else:
                    fails += 1
    values = {}
    if want - seen:
        print("inspect 보고서가 없는 대상: " + ", ".join(sorted(want - seen)))
    else:
        values.update({"inspect.fail": fails, "inspect.excepted": excepted})
    replace_source(d, n, lock, "inspect", values, idir)
    if values:
        print(f"r{n} inspect: 보고서 {len(seen)}개 — FAIL {fails}" + (f" (예외로 뺀 FAIL {excepted})" if excepted else ""))


def ingest_detect(d, n, lock):
    """impeccable detect --json 출력(배열)과 실행 기록(scope.json: 종료 코드·HTML 수·플래그). 소스 안 예외 표식을 따른 실행은 받지 않는다."""
    ddir = Path(d) / "rounds" / f"r{n}" / "detect"
    out, scope = ddir / "detect.json", ddir / "scope.json"
    if not out.exists() or not scope.exists():
        die(f"{ddir}에 detect.json·scope.json이 없다 — measure --kind detect --target <빌드 폴더>")
    try:
        arr = load(out)
    except json.JSONDecodeError:
        die("detect.json이 JSON이 아니다 — detect가 대상을 읽지 못했다")
    sc = load(scope)
    values = {}
    if not isinstance(arr, list) or sc.get("rc") not in (0, 2) or int(sc.get("html_files", 0)) < len(lock["targets"]["urls"]):
        print(f"detect 미측정: 배열 아님 또는 rc={sc.get('rc')} 또는 HTML {sc.get('html_files')}개 < 대상 {len(lock['targets']['urls'])}개")
    elif not ({"--no-inline-ignores", "--no-config"} & set(sc.get("flags") or [])):
        print("detect 미측정: 소스 안 예외 표식(impeccable-disable)을 따른 실행이다 — --no-inline-ignores로 다시 돌린다")
    else:
        ex = [e for e in exceptions(d, lock) if e["kind"] == "detect"]

        def excepted(x):
            return any(e["antipattern"] == x.get("antipattern") and e["file"] in str(x.get("file", ""))
                       and (not e.get("line") or e.get("line") == x.get("line")) for e in ex)
        kept = [x for x in arr if not excepted(x)]
        values.update({"detect.count": len(kept), "detect.excepted": len(arr) - len(kept)})
    replace_source(d, n, lock, "detect", values, ddir)
    if values:
        print(f"r{n} detect: 결함 {values['detect.count']}건 (HTML {sc['html_files']}개"
              + (f", 예외로 뺀 {values['detect.excepted']}건" if values["detect.excepted"] else "") + ")")


INGEST = {"audit": ingest_audit, "axe": ingest_axe, "inspect": ingest_inspect, "detect": ingest_detect}


def cmd_ingest(a):
    d = Path(a.dir)
    lock = lock_of(d)
    begin(d, a.round, lock)
    INGEST[a.kind](d, a.round, lock)
    log(d, "ingest", round=a.round, kind=a.kind)


# ---------------------------------------------------------------- measure (도구를 직접 돌린다)
def _stamp(raw_dir, kind, cmd, n):
    dump(Path(raw_dir) / "runner.json", {"runner": "dloop", "kind": kind, "round": n, "at": now(), "cmd": cmd,
                                          "nonce": secrets.token_hex(8)})


def _http_ok(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def _slug(u):
    p = urlparse(u)
    return re.sub(r"[^A-Za-z0-9]+", "-", (p.path.strip("/") or "home") + ("-" + p.query if p.query else "")).strip("-")[:60] or "home"


def _with_r(u, n):
    p = urlparse(u)
    q = parse_qsl(p.query, keep_blank_values=True) + [("r", str(n))]
    return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(q), p.fragment))


def measure_audit(d, n, lock, st, a):
    aside = _tool("aside")
    if not aside:
        die("aside가 없다 — 이 환경의 브라우저 도구로 page-audit.js를 돌려 rounds/rN/audit/에 두고 ingest --kind audit")
    adir = Path(d) / "rounds" / f"r{n}" / "audit"
    adir.mkdir(parents=True, exist_ok=True)
    src = json.dumps(AUDIT_JS.read_text(encoding="utf-8"))
    for u in lock["targets"]["urls"]:
        if not _http_ok(_with_r(u, n)):
            die(f"{u} 이 200을 돌려주지 않는다 — 서버를 띄우거나 주소를 확인한다")
        ur = _with_r(u, n)
        for w in lock["targets"]["widths"]:
            js = (f"const SRC={src};const U={json.dumps(ur)};const W={w};"
                  "const t=await openTab(U);await sleep(800);"
                  "await page.evaluate(([u,w])=>{document.body.innerHTML='';const f=document.createElement('iframe');"
                  "f.src=u;f.style.cssText='width:'+w+'px;height:900px;border:0';document.body.appendChild(f);},[U,W]);"
                  "await sleep(2500);const fr=page.frames().find(f=>f.parentFrame&&f.parentFrame());"
                  "const out=fr?await fr.evaluate(SRC):{error:'NO_FRAME'};"
                  "console.log('JSON_START');console.log(JSON.stringify(out));console.log('JSON_END');await closeTab(t);")
            try:
                p = subprocess.run([aside, "repl", js], capture_output=True, text=True, timeout=170)
            except subprocess.TimeoutExpired:
                die(f"aside repl 시간 초과: {u} @{w}")
            m = re.search(r"^JSON_START\n(.*?)\nJSON_END$", p.stdout, re.S | re.M)
            if not m:
                die(f"aside 출력에서 결과를 찾지 못했다: {u} @{w}\n{p.stdout[-400:]}{p.stderr[-400:]}")
            res = json.loads(m.group(1))
            if "error" in res or not str(res.get("url", "")).startswith(urlparse(u).scheme):
                die(f"측정 실패 {u} @{w}: {res.get('error') or res.get('url')} — iframe 차단(X-Frame-Options 등)이면 막지 않는 로컬 빌드로")
            if int(res.get("width", 0)) != w:
                die(f"틀 폭이 {res.get('width')}로 측정됐다(요청 {w}) — 창이 너무 작은지 확인한다")
            dump(adir / f"{_slug(u)}@{w}.json", res)
            print(f"audit {u} @{w} 완료")
    _stamp(adir, "audit", f"aside repl page-audit × {len(lock['targets']['urls'])}페이지 × {lock['targets']['widths']}", n)
    ingest_audit(d, n, lock)


def measure_inspect(d, n, lock, st, a):
    node, script = _tool("node"), _tool("inspect")
    if not (node and script):
        die("node 또는 inspect.mjs가 없다")
    idir = Path(d) / "rounds" / f"r{n}" / "inspect"
    idir.mkdir(parents=True, exist_ok=True)
    for u in lock["targets"]["urls"]:
        host = urlparse(u).hostname or ""
        if host not in ("localhost", "127.0.0.1", "::1"):
            die(f"inspect는 로컬 주소에만 쓴다: {u}")
        if not _http_ok(u):
            die(f"{u} 이 200을 돌려주지 않는다(inspect는 404도 그대로 검사한다)")
        # 중립 폴더에서 돌린다 — 저장소의 .taste-skill/direction.json 허용 목록을 따르지 않게(예외는 exceptions.json으로만)
        p = subprocess.run([node, script, u, "--widths", "1280,375", "--out", str(idir / f"{_slug(u)}-out"), "--json"],
                           capture_output=True, text=True, timeout=600, cwd=idir)
        if p.returncode not in (0, 1):
            die(f"inspect 실패(rc {p.returncode}): {u}\n{p.stderr[-400:]}")
        try:
            rep = json.loads(p.stdout)
        except json.JSONDecodeError:
            die(f"inspect가 보고서를 내지 못했다(크래시): {u}")
        dump(idir / f"{_slug(u)}.json", rep)
        print(f"inspect {u} 완료")
    _stamp(idir, "inspect", "node inspect.mjs <url> --widths 1280,375 --json", n)
    ingest_inspect(d, n, lock)


def measure_detect(d, n, lock, st, a):
    engine = _tool("impeccable")
    if not engine:
        die("impeccable 엔진이 없다")
    if not a.target or not Path(a.target).is_dir():
        die("--target <빌드된 HTML 폴더>가 필요하다(CSS·JSX만 넣으면 대부분 놓친다)")
    ddir = Path(d) / "rounds" / f"r{n}" / "detect"
    ddir.mkdir(parents=True, exist_ok=True)
    html = sum(1 for _ in Path(a.target).rglob("*.html"))
    flags = ["--json", "--no-advisory", "--no-inline-ignores"]      # 소스 안 예외 표식은 따르지 않는다(예외는 exceptions.json으로만)
    p = subprocess.run([engine, "detect", *flags, str(Path(a.target).resolve())],
                       capture_output=True, text=True, timeout=600, cwd=scope_paths(d, lock["guards"]["scope"]))
    (ddir / "detect.json").write_text(p.stdout or "", encoding="utf-8")
    dump(ddir / "scope.json", {"target": str(Path(a.target).resolve()), "html_files": html, "rc": p.returncode,
                               "flags": flags, "at": now()})
    _stamp(ddir, "detect", f"{engine} detect {' '.join(flags)} {a.target}", n)
    ingest_detect(d, n, lock)


def measure_axe(d, n, lock, st, a):
    runqa = _tool("runqa")
    if not runqa:
        die("run-qa.sh가 없다 — axe-core 결과를 같은 형식(VITALS·AXE 줄)으로 rounds/rN/qa/<페이지>/에 두고 ingest --kind axe")
    qdir = Path(d) / "rounds" / f"r{n}" / "qa"
    for u in lock["targets"]["urls"]:
        out = qdir / _slug(u)
        out.mkdir(parents=True, exist_ok=True)
        p = subprocess.run(["bash", runqa, u, str(out), f"r{n}"], capture_output=True, text=True, timeout=900)
        (out / "stdout.txt").write_text(p.stdout + "\n" + p.stderr, encoding="utf-8")
        print(f"axe {u} rc={p.returncode}" + (" (불완전 — 통과 아님)" if p.returncode == 1 else ""))
    _stamp(qdir, "axe", "run-qa.sh <url> <out> r<N>", n)
    ingest_axe(d, n, lock)


def cmd_measure(a):
    d = Path(a.dir)
    lock = lock_of(d)
    begin(d, a.round, lock)
    {"audit": measure_audit, "inspect": measure_inspect, "detect": measure_detect, "axe": measure_axe}[a.kind](d, a.round, lock, state(d), a)
    log(d, "measure", round=a.round, kind=a.kind)


# ---------------------------------------------------------------- set (수동 기준)
def cmd_set(a):
    d = Path(a.dir)
    lock = lock_of(d)
    crit = [c for c in lock["criteria"] if c["metric"] == a.metric]
    if not crit:
        die(f"{a.metric}: 잠긴 기준에 없는 지표 — 수동 기록은 잠긴 수동 기준에만")
    if any(c["source"] != "manual" for c in crit):
        die(f"{a.metric}: 출처가 {sorted({c['source'] for c in crit})}인 지표는 measure·ingest·panel·personas로만 만든다")
    ev = _evidence_file(d, None, a.evidence)
    if not ev:
        die(f"증거 {a.evidence} — 작업 폴더 안의 비어 있지 않은 파일이어야 한다(작업 폴더를 옮겨도 판정이 유지되게)")
    start = _iso(_round_start(d, lock, a.round))
    if datetime.fromtimestamp(ev.stat().st_mtime, timezone.utc) < start - timedelta(seconds=1):
        die(f"증거 {ev.name}은 이 회차 시작({start:%Y-%m-%d %H:%M:%S}) 전에 만든 파일이다 — 이번 회차에서 다시 확인하고 기록을 갱신한다")
    value = parse_value(a.value)
    begin(d, a.round, lock)
    with wlock(d):
        p = metrics_path(d, a.round)
        data = load(p) if p.exists() else {"round": a.round, "metrics": {}}
        data["metrics"][a.metric] = {"value": value, "evidence": _rel(d, ev), "source": "set", "round": a.round,
                                     "scope": scope_sig(lock), "evidence_sha": sha(ev), "at": now()}
        dump(p, data)
    log(d, "set", round=a.round, metric=a.metric, value=a.value, evidence=str(ev))
    print(f"r{a.round} {a.metric} = {a.value}")


# ---------------------------------------------------------------- panel
VENDOR_FAMILY = (("anthropic", ("anthropic", "claude", "opus", "sonnet", "haiku", "fable")),
                 ("openai", ("openai", "codex", "gpt")), ("google", ("google", "gemini")), ("xai", ("xai", "grok")),
                 ("mistral", ("mistral",)), ("meta", ("meta", "llama")), ("deepseek", ("deepseek",)), ("alibaba", ("qwen", "alibaba")))


def vendor_family(v):
    """판정자가 적은 벤더 이름을 계열로 묶는다 — 'Claude Opus'를 다른 벤더로 세지 않게. 모르는 이름은 다른 벤더로 치지 않는다."""
    s = str(v or "").strip().lower()
    return next((fam for fam, keys in VENDOR_FAMILY if any(k in s for k in keys)), "unknown")


def _judge_base(jid):
    base, _, var = jid.partition("@")
    if var and var not in ("a", "b"):
        die(f"판정자 id '{jid}' — 순서 변형은 @a·@b 두 개까지만")
    return base


def read_key(p):
    """{"A": "ours", "B": "comp:이름", "C": "ref:이름", "nonce": "…"} → (원본, 라벨 대응, 우리 라벨, 경쟁사 라벨→이름)."""
    key = load(p)
    if not isinstance(key, dict):
        die("key 파일은 객체여야 한다")
    labels = {k: v for k, v in key.items() if k != "nonce"}
    ours = [k for k, v in labels.items() if v == "ours"]
    if len(ours) != 1:
        die("key에 ours가 정확히 하나 있어야 한다")
    bad = [v for v in labels.values() if v != "ours" and not str(v).startswith(("comp:", "ref:"))]
    if bad:
        die(f"key 값은 ours·comp:이름·ref:이름만: {bad}")
    return key, labels, ours[0], {k: v.split(":", 1)[1] for k, v in labels.items() if v.startswith("comp:")}


def check_comps(d, comps):
    if comps:
        locked = locked_competitors(d)
        if sorted(comps.values()) != sorted(locked):         # 잠긴 목록과 정확히 같아야 한다(빼기·중복 금지)
            die(f"판정 대상 경쟁사 {sorted(comps.values())}가 잠긴 목록 {sorted(locked)}과 다르다")


def cmd_seal(a):
    """판정자를 띄우기 전에 라벨 대응표를 봉인한다 — 점수를 본 뒤 어느 자극이 우리인지 바꾸지 못하게.
    대응표는 저장소 밖에 둔다(판정자가 저장소를 읽을 수 있다). 무작위 nonce가 봉인 해시를 라벨 조합으로 거꾸로 맞히지 못하게 한다."""
    d = Path(a.dir)
    begin(d, a.round, lock_of(d))
    kp = Path(a.key).resolve()
    if str(kp).startswith(str(Path(state(d)["root"]).resolve()) + os.sep):
        die("key 파일은 저장소 밖에 둔다 — 판정이 끝난 뒤에 rounds/rN/panel/key.json으로 복사한다")
    key, labels, _, comps = read_key(kp)
    check_comps(d, comps)
    if len(str(key.get("nonce", ""))) < 16:
        key["nonce"] = secrets.token_hex(16)
        dump(kp, key)
    pdir = d / "rounds" / f"r{a.round}" / "panel"
    if list(pdir.glob("judge-*.json")) + list(pdir.glob("pairs-*.json")):
        die("이 회차에 판정 파일이 이미 있다 — 봉인은 판정자를 띄우기 전에 한다")
    dump(pdir / "seal.json", {"key_sha": sha(kp), "labels": sorted(labels), "at": now(), "at_epoch": time.time()})
    log(d, "seal", round=a.round, labels=sorted(labels))
    print(f"r{a.round} 봉인: 라벨 {', '.join(sorted(labels))} — 판정이 끝나면 {kp} 를 {pdir / 'key.json'} 로 복사한 뒤 panel")


def panel_scores(judged, o, comps, axes, quorum):
    """판정자 사이 중앙값으로 축마다 비교한다. 승은 중앙값 차이 0.5 이상 + 판정자 과반이 같은 방향일 때만, 패는 중앙값이 0.5 이상 낮을 때(낮은 등급 보존)."""
    if len(judged) < quorum:
        print(f"판정자 {len(judged)}명 — 정족수 {quorum}명 미만이라 점수 지표를 만들지 않는다")
        return {}

    def med(label, ax):
        return statistics.median(s[(label, ax)] for s in judged.values())

    def result(label, ax):
        om, cm = med(o, ax), med(label, ax)
        up = sum(1 for s in judged.values() if s[(o, ax)] > s[(label, ax)])
        if om - cm >= 0.5 and up * 2 > len(judged):
            return "win"
        return "loss" if cm - om >= 0.5 else "tie"

    ours_m = {ax: med(o, ax) for ax in axes}
    values = {f"panel.axis.{ax}.ours": v for ax, v in ours_m.items()}
    values["panel.ours_min"] = min(ours_m.values())
    if not comps:
        return values
    wins_r, losses, gaps, by_axis = [], [], [], {ax: [] for ax in axes}
    for label, name in comps.items():
        res = [result(label, ax) for ax in axes]
        g = sum(ours_m[ax] - med(label, ax) for ax in axes) / len(axes)
        w, l = res.count("win"), res.count("loss")
        values.update({f"panel.vs.{name}.wins": w, f"panel.vs.{name}.losses": l, f"panel.vs.{name}.mean_gap": g})
        wins_r.append(w / len(axes))
        losses.append(l)
        gaps.append(g)
        for ax in axes:
            by_axis[ax].append(med(label, ax))
    values.update({"panel.vs.min_wins_ratio": min(wins_r), "panel.vs.max_losses": max(losses),
                   "panel.vs.min_mean_gap": min(gaps),
                   "panel.vs_median.min_diff": min(ours_m[ax] - statistics.median(by_axis[ax]) for ax in axes)})
    return values


def cmd_panel(a):
    d = Path(a.dir)
    lock = lock_of(d)
    begin(d, a.round, lock)
    axes = lock["process"]["panel_axes"]
    quorum = lock["process"]["quorum"]
    pdir = d / "rounds" / f"r{a.round}" / "panel"
    seal_p, kp = pdir / "seal.json", pdir / "key.json"
    if not seal_p.exists():
        die("seal.json 없음 — 판정자를 띄우기 전에 dloop seal로 라벨 대응표를 봉인한다")
    if not kp.exists():
        die(f"{kp} 없음 — 판정이 끝나면 봉인한 대응표를 이 자리로 복사한다")
    seal = load(seal_p)
    if sha(kp) != seal.get("key_sha"):
        die("key.json이 봉인한 대응표와 다르다 — 판정 뒤에 라벨을 바꿀 수 없다", 3)
    _, key, o, comps = read_key(kp)
    check_comps(d, comps)
    labels = sorted(key)
    files, pair_files = sorted(pdir.glob("judge-*.json")), sorted(pdir.glob("pairs-*.json"))
    if not files:
        die(f"{pdir}/judge-*.json 없음")
    early = [f.name for f in files + pair_files if f.stat().st_mtime < seal.get("at_epoch", 0)]
    if early:
        die(f"봉인보다 먼저 만든 판정 파일: {early} — 봉인 뒤에 새로 판정한다", 3)
    per_judge, vendors, breaches, seen_ids = {}, {}, set(), set()
    for f in files:
        j = load(f)
        jid = str(j.get("judge") or "")
        if not jid:
            die(f"{f.name}: judge id가 없다")
        if jid in seen_ids:
            die(f"판정자 id 중복: {jid}")
        seen_ids.add(jid)
        base = _judge_base(jid)
        scores, why = j.get("scores") or {}, j.get("rationale")
        if not isinstance(why, dict):
            die(f"{f.name}: rationale(축마다 근거)이 없다 — 판정 규약 위반")
        extra = sorted(set(scores) - set(labels))
        if extra:
            die(f"{f.name}: 봉인에 없는 자극 {extra}")
        for label in labels:
            for ax in axes:
                v = (scores.get(label) or {}).get(ax)
                if not (finite(v) and 1 <= v <= 5):
                    die(f"{f.name}: {label}.{ax} = {v!r} — 모든 자극·축을 1~5로 채점해야 한다(빠진 칸이 있으면 판정을 다시 받는다)")
                if not str((why.get(label) or {}).get(ax, "")).strip():
                    die(f"{f.name}: {label}.{ax} 근거가 없다 — 근거 없는 점수는 받지 않는다(판정을 다시 받는다)")
                per_judge.setdefault(base, {}).setdefault((label, ax), []).append(v)
        fam = vendor_family(j.get("vendor"))
        if base in vendors and vendors[base] != fam:
            die(f"판정자 {base}의 벤더가 파일마다 다르다")
        vendors[base] = fam
        bc = j.get("blind_check") or {}
        if bc.get("recognized") or bc.get("guessed_owner") == o:     # 회사를 알아봤거나 의뢰한 쪽을 맞혔다
            breaches.add(base)
    # 판정자 단위로 먼저 묶는다(순서 변형은 평균) → 판정자 사이 중앙값
    judged = {b: {k: statistics.fmean(v) for k, v in s.items()} for b, s in per_judge.items()}
    values = {"panel.judges": len(judged),
              "panel.cross_vendor": sum(1 for b in judged if vendors[b] not in ("anthropic", "unknown")),
              "panel.blind_breaches": len(breaches)}
    if breaches and len(breaches) * 2 >= len(judged):
        print(f"블라인드가 깨진 판정자 {len(breaches)}/{len(judged)}명 — 점수 지표를 만들지 않는다. 자극을 다시 가리고 새 판정자로 다시 판정한다")
    else:
        values.update(panel_scores(judged, o, comps, axes, quorum))
        if comps and pair_files:
            values.update(pairwise(pair_files, key, o, comps, axes, lock["process"]["pair_quorum"] or quorum))
    replace_source(d, a.round, lock, "panel", values, pdir)
    log(d, "panel", round=a.round, judges=sorted(judged), vendors=vendors, blind_breaches=sorted(breaches))
    print(json.dumps(values, ensure_ascii=False, indent=1))


def pairwise(files, key, ours, comps, axes, quorum):
    """좌우를 바꿔 두 번 물어 두 번 다 이긴 경우만 그 판정자의 승(엇갈리면 무승부).
    판정자 사이: 진 표가 없고 과반이 승이면 승, 진 표가 이긴 표 이상이면 패, 나머지는 무승부(낮은 등급 보존)."""
    per, values, seen = {}, {}, set()
    for f in files:
        j = load(f)
        jid = str(j.get("judge") or "")
        if not jid:
            die(f"{f.name}: judge id가 없다")
        if jid in seen:
            die(f"맞비교 판정자 id 중복: {jid}")
        seen.add(jid)
        base = _judge_base(jid)
        sides = {}
        for p in j.get("pairs", []):
            L, R, ax, win = p.get("left"), p.get("right"), p.get("axis"), p.get("winner")
            if ax not in axes or L not in key or R not in key or ours not in (L, R):
                continue
            other = R if L == ours else L
            if other not in comps:
                continue
            if win not in (L, R, "tie"):
                die(f"{f.name}: winner '{win}' — left·right 라벨 또는 tie만")
            if not str(p.get("why", "")).strip():
                die(f"{f.name}: {other}/{ax} 근거(why)가 없다 — 근거 없는 판정은 받지 않는다")
            side = "ours_left" if L == ours else "ours_right"
            res = "win" if win == ours else "loss" if win == other else "tie"
            if (other, ax, side) in sides and sides[(other, ax, side)] != res:
                die(f"{f.name}: 같은 쌍·방향에 서로 다른 판정")
            sides[(other, ax, side)] = res
        for (other, ax, side) in list(sides):
            if side != "ours_left" or (other, ax, "ours_right") not in sides:
                continue
            slot = per.setdefault((other, ax), {})
            if base in slot:
                die(f"판정자 {base}의 맞비교가 여러 파일에 있다 — 판정자 하나의 두 방향은 한 파일로 합친다")
            a_, b_ = sides[(other, ax, "ours_left")], sides[(other, ax, "ours_right")]
            slot[base] = "win" if a_ == b_ == "win" else "loss" if a_ == b_ == "loss" else "tie"
    ratios, losses_all = [], []
    for label, name in comps.items():
        outcomes = []
        for ax in axes:
            votes = list(per.get((label, ax), {}).values())
            if len(votes) < quorum:
                break
            w, l = votes.count("win"), votes.count("loss")
            outcomes.append("win" if l == 0 and w * 2 > len(votes) else "loss" if l and l >= w else "tie")
        if len(outcomes) != len(axes):
            print(f"맞비교 미완: {name}(축마다 두 방향 판정 {quorum}명 이상 필요)")
            continue
        values[f"panel.pair.{name}.wins"] = outcomes.count("win")
        values[f"panel.pair.{name}.losses"] = outcomes.count("loss")
        ratios.append(outcomes.count("win") / len(axes))
        losses_all.append(outcomes.count("loss"))
    if comps and len(ratios) == len(comps):
        values["panel.pair.min_wins_ratio"] = min(ratios)
        values["panel.pair.max_losses"] = max(losses_all)
    return values


# ---------------------------------------------------------------- personas
# NN/g 심각도 0~4와 흔한 표기를 세 단계로 옮긴다(0 = 사용성 문제 아님 → 세지 않는다)
SEVERITY = {"high": "High", "critical": "High", "blocker": "High", "major": "High", "catastrophe": "High",
            "catastrophic": "High", "4": "High", "3": "High", "medium": "Medium", "minor": "Medium", "2": "Medium",
            "low": "Low", "cosmetic": "Low", "1": "Low"}


def cmd_personas(a):
    d = Path(a.dir)
    lock = lock_of(d)
    begin(d, a.round, lock)
    pdir = d / "rounds" / f"r{a.round}" / "personas"
    receipts = {f.stem for f in pdir.glob("*.md") if f.stat().st_size > 0}   # 페르소나별 실행 기록(답 원문)
    f = pdir / "findings.jsonl"
    if not f.exists():
        die(f"{f} 없음 — 지적이 없으면 빈 파일로 둔다")
    rows = []
    for i, x in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        if not x.strip():
            continue
        try:
            r = json.loads(x)
        except json.JSONDecodeError:
            die(f"findings.jsonl {i}행: JSON이 아니다")
        s = str(r.get("severity", "")).strip().lower()
        if s == "0":
            continue
        sev = SEVERITY.get(s)
        if not sev:
            die(f"findings.jsonl {i}행: severity '{r.get('severity')}' — High·Medium·Low 또는 NN/g 0~4(critical·major·minor·cosmetic도 받는다)")
        if r.get("persona") not in receipts:
            die(f"findings.jsonl {i}행: 페르소나 '{r.get('persona')}'의 실행 기록({pdir}/<이름>.md)이 없다")
        rows.append({**r, "severity": sev})
    # status는 보지 않는다 — 이 회차 실행에서 나온 지적은 모두 열린 것으로 센다(고쳤는지는 다음 회차의 새 실행이 확인한다)
    values = {"persona.count": len(receipts),
              "persona.open_high": sum(1 for r in rows if r["severity"] == "High"),
              "persona.open_medium": sum(1 for r in rows if r["severity"] == "Medium")}
    replace_source(d, a.round, lock, "persona", values, pdir)
    log(d, "personas", round=a.round, personas=sorted(receipts), rows=len(rows))
    print(f"r{a.round} personas={len(receipts)} High={values['persona.open_high']} Medium={values['persona.open_medium']}")


# ---------------------------------------------------------------- check
def evaluate(c, v):
    if c["op"] == "true":
        return v is True
    return finite(v) and OPS[c["op"]](v, c["value"])


def gap(c, v):
    """기준까지 남은 거리. 수치 == 는 절댓값, 참·거짓은 0·1."""
    if c["op"] == "true":
        return 0.0 if v is True else 1.0
    if not finite(v):
        return None
    if c["op"] == "==":
        return abs(v - c["value"])
    return max(0.0, c["value"] - v) if c["op"] in (">=", ">") else max(0.0, v - c["value"])


def provenance(d, lock, c, m, n):
    """출처·회차·대상·원 출력 지문·직접 측정 여부가 맞는지. 문제가 있으면 사유 문자열."""
    want = SOURCE_OF[c["source"]]
    if m.get("source") != want:
        return f"출처 {m.get('source')} ≠ {want}"
    if m.get("round") != n:
        return f"회차 {m.get('round')} ≠ r{n}"
    if m.get("scope") != scope_sig(lock):
        return "대상·폭이 바뀐 뒤 다시 재지 않은 값"

    def at(p):
        p = Path(p or "")
        return p if p.is_absolute() else Path(d) / p
    if want == "set":
        ev = at(m.get("evidence"))
        if not ev.is_file() or sha(ev) != m.get("evidence_sha"):
            return "수동 증거 파일이 없거나 기록 뒤 바뀜"
        return None
    raw = at(m.get("evidence"))
    rdir = (Path(d) / "rounds" / f"r{n}").resolve()
    if not raw.exists() or not str(raw.resolve()).startswith(str(rdir) + os.sep):
        return "원 출력이 이 회차 폴더 밖이거나 없음"
    if dir_digest(raw) != m.get("raw_sha"):
        return "원 출력이 집계 뒤 바뀜 — 다시 measure·ingest"
    need = lock["process"].get("require_runner", {}).get(want)
    if need and (m.get("runner") != "dloop" or m.get("runner_round") != n):
        return "이 환경에서는 이 회차에 dloop measure로 직접 잰 값만 인정"
    return None


def verdict_for(d, lock, n):
    p = metrics_path(d, n)
    try:
        metrics = load(p)["metrics"] if p.exists() else {}
    except (json.JSONDecodeError, KeyError):
        die(f"{p}가 손상됐다", 3)
    rows = []
    for c in lock["criteria"]:
        m = metrics.get(c["metric"])
        row = {"id": c["id"], "metric": c["metric"]}
        why = provenance(d, lock, c, m, n) if m else "측정값 없음"
        if why:
            rows.append({**row, "status": "UNMEASURED", "reason": why})
            continue
        v = m["value"]
        if v is None:
            rows.append({**row, "status": "N/A" if c.get("na_ok") else "UNMEASURED", "reason": "해당 없음" if c.get("na_ok") else "값 없음"})
            continue
        if c["op"] != "true" and not finite(v):
            rows.append({**row, "status": "UNMEASURED", "reason": f"숫자가 아닌 값 {v!r}"})
            continue
        rows.append({**row, "status": "PASS" if evaluate(c, v) else "FAIL", "value": v,
                     "target": f"{c['op']} {c['value']}" if c["op"] != "true" else "true", "gap": gap(c, v)})
    return rows


def _fmt(v):
    return f"{v:.4g}" if isinstance(v, float) else str(v)


def cmd_check(a):
    d = Path(a.dir)
    try:
        lock_p, sha_p = d / "criteria.lock.json", d / "criteria.lock.sha256"
        if not lock_p.exists() or not sha_p.exists():
            print("TAMPER/NO-LOCK: criteria.lock.json 또는 해시가 없다")
            sys.exit(3)
        cur = sha(lock_p)
        last = chain_last(d, "compile")
        if cur != sha_p.read_text().strip() or not last or last.get("sha") != cur:
            print("TAMPER: criteria.lock.json이 잠금 이력(locks/chain.jsonl)의 마지막 판과 다르다 — 게이트 무효, 사용자 재승인 필요")
            sys.exit(3)
        lock = load(lock_p)
        if any(c["metric"].startswith(("panel.vs", "panel.pair")) for c in lock["criteria"]):
            cf, cs, lastset = d / "research" / "comparison-set.json", d / "comparison-set.sha256", chain_last(d, "lockset")
            if not (cs.exists() and cf.exists() and lastset) or not (cs.read_text().strip() == sha(cf) == lastset.get("sha")):
                print("TAMPER: 경쟁 기준이 있는데 comparison-set이 잠기지 않았거나 잠근 판과 다르다")
                sys.exit(3)
        rounds = _round_dirs(d)
        latest = current_round(d)
        if latest is None:
            die("측정한 회차가 없다 — rounds/r0부터")
        n = latest if a.round is None else a.round
        if f"r{n}" not in rounds:
            die(f"r{n} 없음 — 있는 회차: {', '.join(rounds)}", 3)
        stray = [r for r in rounds if int(r[1:]) > latest]
        cap = lock["process"]["round_cap"]
        if n > cap - 1:
            print(f"ROUND_CAP_EXCEEDED: r{n}은 한도 {cap}회(r0~r{cap - 1})를 넘는다 — 사용자 승인 후 relock으로 한도를 바꾼다")
            sys.exit(3)
        rows = verdict_for(d, lock, n) + guard_rows(d, lock)
    except (OSError, json.JSONDecodeError, KeyError) as e:
        print(f"TAMPER/BROKEN: 판정에 필요한 파일을 읽지 못했다 — {e}")
        sys.exit(3)
    count = {s: sum(1 for r in rows if r["status"] == s) for s in ("PASS", "N/A", "FAIL", "UNMEASURED")}
    code = 1 if count["FAIL"] else 2 if count["UNMEASURED"] else 0
    print(f"r{n}: PASS {count['PASS']} · 해당없음 {count['N/A']} · FAIL {count['FAIL']} · 미측정 {count['UNMEASURED']} (기준 {len(rows)}개) · exit {code}")
    for r in rows:
        if r["status"] not in ("PASS", "N/A"):
            extra = f" 값 {_fmt(r['value'])} / 기준 {r['target']}" if "value" in r else f" ({r.get('reason', '')})"
            print(f"  {r['status']:<10} {r['id']} `{r['metric']}`{extra}")
    if n != latest:
        print(f"NOT_LATEST: r{n}은 판정 차례(r{latest})가 아니다 — 다른 회차는 보기만 하고, 완료 판정은 차례인 회차로만 한다")
        sys.exit(3)
    if stray:
        print(f"  ! 판정 차례 밖의 폴더(판정하지 않음): {', '.join(stray)} — 회차는 차례로 잰다")
    flags = stall_flags(d, n, rows, lock["process"]["stall_k"])
    if n == cap - 1:
        flags.append(f"ROUND_CAP: r{n}이 한도 {cap}회의 마지막 회차 — 미달이면 멈추고 사용자에게 묻는다")
    relocks = [r for r in chain_rows(d) if r.get("kind") == "compile" and r.get("relock")]
    ex = exceptions(d, lock)
    dump(d / "rounds" / f"r{n}" / "verdict.json",
         {"round": n, "at": now(), "lock_sha": cur, "relocks": len(relocks), "exceptions": [exception_label(e) for e in ex],
          "counts": count, "exit": code, "flags": flags, "rows": rows})
    for f in flags:
        print(f"  ! {f}")
    print(f"  잠금 {cur[:12]} · 다시 잠금 {len(relocks)}회"
          + ("" if not relocks else " — " + " / ".join(f"{r['at'][:16]} {str(r.get('reason', ''))[:50]}" for r in relocks[-3:])))
    if ex:
        print(f"  예외 {len(ex)}개 적용: " + ", ".join(exception_label(e) for e in ex))
    if code == 0:
        print(f"dloop check: all locked criteria passed (r{n})")   # fablize 게이트가 성공으로 읽는 낱말
    sys.exit(code)


def stall_flags(d, n, rows, k):
    """마지막 회차까지 '개선 없는 전이'가 k번 연속이면 정체. 중간에 한 번이라도 줄었으면 정체가 아니다."""
    hist = {}
    for i in range(n):          # check는 판정 차례(앞 회차가 모두 판정된 회차)만 판정하므로 앞 회차 기록이 늘 있다
        hist[i] = {r["id"]: r for r in load(Path(d) / "rounds" / f"r{i}" / "verdict.json")["rows"]}
    hist[n] = {r["id"]: r for r in rows}
    flags = []
    for r in rows:
        if r["status"] != "FAIL":
            continue
        streak = 0
        for i in range(n, 0, -1):
            cur, prev = hist.get(i, {}).get(r["id"]), hist.get(i - 1, {}).get(r["id"])
            if not cur or not prev or cur["status"] != "FAIL" or prev["status"] != "FAIL":
                break
            cg, pg = cur.get("gap"), prev.get("gap")
            if cg is not None and pg is not None and cg < pg - 1e-9:
                break
            streak += 1
        if streak >= k:
            flags.append(f"STALLED: {r['id']} — {streak}회 연속 개선 없음 → 접근 방식을 바꾼다")
    return flags


def cmd_status(a):
    d = Path(a.dir)
    lock = load(d / "criteria.lock.json") if (d / "criteria.lock.json").exists() else None
    print(f"작업 폴더 {d} · 기준 {'%d개' % len(lock['criteria']) if lock else '미잠금'}"
          + (f" · 반복 한도 {lock['process']['round_cap']}(r0 포함)" if lock else ""))
    for r in _round_dirs(d):
        p = d / "rounds" / r / "verdict.json"
        if p.exists():
            v = load(p)
            c = v["counts"]
            print(f"  {r}: PASS {c['PASS']} FAIL {c['FAIL']} 미측정 {c['UNMEASURED']} exit {v['exit']}"
                  + "".join(f"\n    ! {f}" for f in v.get("flags", [])))
        else:
            print(f"  {r}: 판정 전")


def cmd_gate(a):
    """goal A의 마지막 단계를 닫는 길 — check를 직접 돌려 0일 때만 goals.py checkpoint를 대신 부른다."""
    d = Path(a.dir).resolve()
    goals = _tool("goals")
    if not goals:
        die("goals.py가 없다 — goal A를 쓰지 않는 환경이다")
    me = str(Path(__file__).resolve())
    p = subprocess.run([sys.executable, me, "check", "--dir", str(d)], capture_output=True, text=True)
    sys.stdout.write(p.stdout)
    sys.stderr.write(p.stderr)
    if p.returncode != 0:
        die(f"check 종료 코드 {p.returncode} — goal 단계를 닫지 않는다", p.returncode)
    cmd = " ".join(shlex.quote(x) for x in ("python3", me, "check", "--dir", str(d)))
    q = subprocess.run([sys.executable, goals, "checkpoint", "--id", a.id, "--status", "complete",
                        "--evidence", a.evidence or "dloop gate: check exit 0", "--verify-cmd", cmd,
                        "--verify-evidence", p.stdout.strip()], cwd=d, capture_output=True, text=True)
    sys.stdout.write(q.stdout)
    sys.stderr.write(q.stderr)
    sys.exit(q.returncode)


def nonneg(v):
    n = int(v)
    if n < 0:
        raise argparse.ArgumentTypeError("회차는 0 이상")
    return n


def main():
    p = argparse.ArgumentParser(prog="dloop.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("init"); x.add_argument("--dir", required=True); x.add_argument("--root", default=".")
    x.add_argument("--url", action="append", default=[]); x.add_argument("--widths", default="375,1280")
    x.add_argument("--force", action="store_true"); x.add_argument("--new", action="store_true", help="다른 진행 중 작업 폴더가 있어도 새 루프를 연다(사용자가 원할 때만)")
    x = s.add_parser("resume"); x.add_argument("--root", default=".")
    x = s.add_parser("questions"); x.add_argument("--dir", required=True)
    x.add_argument("--set", required=True, choices=["scope", "preset", "quality1", "quality2", "process"])
    x.add_argument("--answers", help="이미 받은 답(answers.json) — 답이 있는 질문은 빼고 낸다")
    x = s.add_parser("compile"); x.add_argument("--dir", required=True); x.add_argument("--answers", required=True)
    x.add_argument("--relock", action="store_true"); x.add_argument("--reason", default="")
    x.add_argument("--round-cap", type=int, help="반복 한도를 선택지 밖 값으로(사용자 승인 원문을 --reason에)")
    x.add_argument("--reset-guards", action="store_true", help="relock 때 검출기 설정 기준선을 새로 찍는다(사용자 승인 시에만)")
    x = s.add_parser("lockset"); x.add_argument("--dir", required=True)
    x = s.add_parser("measure"); x.add_argument("--dir", required=True); x.add_argument("--round", type=nonneg, required=True)
    x.add_argument("--kind", required=True, choices=["audit", "axe", "inspect", "detect"]); x.add_argument("--target")
    x.add_argument("--fix-reason")
    x = s.add_parser("ingest"); x.add_argument("--dir", required=True); x.add_argument("--round", type=nonneg, required=True)
    x.add_argument("--kind", required=True, choices=["audit", "axe", "inspect", "detect"]); x.add_argument("--fix-reason")
    x = s.add_parser("set"); x.add_argument("--dir", required=True); x.add_argument("--round", type=nonneg, required=True)
    x.add_argument("--metric", required=True); x.add_argument("--value", required=True); x.add_argument("--evidence", required=True)
    x.add_argument("--fix-reason")
    for name in ("panel", "personas"):
        x = s.add_parser(name); x.add_argument("--dir", required=True); x.add_argument("--round", type=nonneg, required=True)
        x.add_argument("--fix-reason")
    x = s.add_parser("seal"); x.add_argument("--dir", required=True); x.add_argument("--round", type=nonneg, required=True)
    x.add_argument("--key", required=True, help="저장소 밖에 둔 라벨 대응표 JSON")
    x = s.add_parser("check"); x.add_argument("--dir", required=True); x.add_argument("--round", type=nonneg)
    x = s.add_parser("status"); x.add_argument("--dir", required=True)
    x = s.add_parser("gate"); x.add_argument("--dir", required=True); x.add_argument("--id", required=True)
    x.add_argument("--evidence", default="")
    a = p.parse_args()
    FIX_REASON["value"] = getattr(a, "fix_reason", None)
    {"init": cmd_init, "resume": cmd_resume, "questions": cmd_questions, "compile": cmd_compile, "lockset": cmd_lockset,
     "measure": cmd_measure, "ingest": cmd_ingest, "set": cmd_set, "seal": cmd_seal, "panel": cmd_panel,
     "personas": cmd_personas, "check": cmd_check, "status": cmd_status, "gate": cmd_gate}[a.cmd](a)


if __name__ == "__main__":
    main()
