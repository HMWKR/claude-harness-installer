#!/usr/bin/env python3
"""dloop.py 시험 — python3 test_dloop.py (표준 라이브러리 unittest, 임시 폴더만 쓴다)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

DLOOP = Path(__file__).resolve().parent / "dloop.py"
URL = "http://127.0.0.1:9999/"
AXES = ["hierarchy", "typography_color", "imagery", "copy", "trust", "mobile", "distinctiveness"]
TOOLS = ("aside", "node", "codex", "runqa", "inspect", "impeccable", "goals", "verify_lock")


TOOL_ENV = {}   # 실행 도구 경로는 state.json이 아니라 환경 변수로만 덮어쓴다(dloop._tool, 2026-10-16 보안 수정)


def run(*args, check=None):
    p = subprocess.run([sys.executable, str(DLOOP), *map(str, args)], capture_output=True, text=True,
                       env={**os.environ, **TOOL_ENV})
    if check is not None and p.returncode != check:
        raise AssertionError(f"exit {p.returncode} != {check}\nstdout:{p.stdout}\nstderr:{p.stderr}")
    return p


def write(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def stamp(raw_dir, n):
    """dloop measure가 남기는 실행 기록을 흉내 낸다(이 시험은 도구를 실제로 돌리지 않는다)."""
    write(Path(raw_dir) / "runner.json", {"runner": "dloop", "kind": "test", "round": n})


def flat(scores_by_label):
    """{"A": 4, "B": [..7]} → 모든 축 점수 사전."""
    return {lab: dict(zip(AXES, v if isinstance(v, list) else [v] * 7)) for lab, v in scores_by_label.items()}


AUDIT_BASE = {"overflow.px": 0, "contrast.normal_min": 7.1, "contrast.large_min": 8.0, "contrast.fail_normal": 0,
              "contrast.fail_large": 0, "contrast.unknown_bg": 0, "type.body_px_min": 16, "type.size_steps": 6,
              "type.families": 1, "type.line_height_min": 1.6, "type.measure_em_latin": None, "type.measure_em_cjk": 30,
              "target.small24": 0, "target.button_lt44": 0, "img.broken": 0, "img.alt_missing": 0, "img.no_dimensions": 0,
              "img.legacy_format": 0, "motion.reduced_rule": True, "motion.layout_anim": 0, "focus.rule": True,
              "css.unreadable_sheets": 0, "struct.h1": 1, "struct.heading_skips": 0, "struct.main": 1, "struct.lang": True,
              "text.placeholder": 0, "text.generic_links": 0, "dom.nodes": 400, "perf.js_kb": 40, "perf.transfer_kb": 300,
              "perf.lcp_ms": 900, "perf.cls": 0.01}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.keydir = Path(tempfile.mkdtemp())          # 저장소 밖(판정자가 못 읽는 곳)
        self.w = self.root / "W"
        self.init()

    def init(self, *extra):
        run("init", "--dir", self.w, "--root", self.root, "--url", URL, "--force", *extra, check=0)
        self.set_tools()

    def set_tools(self, **over):
        st = json.loads((self.w / "state.json").read_text())
        st["tools"] = {**{k: "/x" for k in TOOLS}, **over}
        write(self.w / "state.json", st)
        TOOL_ENV.clear()
        TOOL_ENV.update({f"DLOOP_TOOL_{k.upper()}": (v or "") for k, v in st["tools"].items()})

    def tearDown(self):
        self.tmp.cleanup()
        shutil.rmtree(self.keydir, ignore_errors=True)

    def answers(self, extra=None, **kw):
        a = {"answers": {"대상 범위": "대표 페이지 1개", "변경 깊이": "다듬기", "리서치": "새로 5곳",
                         "기준 설정": "묶음으로 한 번에", "기준 묶음": "기본(출시 최소)", "경쟁 우위": "근접",
                         "판정 엄격도": "가볍게", "반복 한도": "3회", "goal 방식": "goal 없이"},
             "targets": {"urls": [URL]}}
        a["answers"].update(extra or {})
        a.update(kw)
        write(self.w / "answers.json", a)
        return self.w / "answers.json"

    def lock(self, extra=None, compset=True, **kw):
        run("compile", "--dir", self.w, "--answers", self.answers(extra, **kw), check=0)
        if compset:                                   # 경쟁 기준은 늘 있다(최소 L1) — 판정 전에 비교 대상이 잠겨 있어야 한다
            self.compset()
        return json.loads((self.w / "criteria.lock.json").read_text())

    def relock(self, extra=None, reason="사용자 승인: 시험", *flags, **kw):
        return run("compile", "--dir", self.w, "--answers", self.answers(extra, **kw), "--relock", "--reason", reason, *flags)

    def metrics(self, n=0):
        p = self.w / f"rounds/r{n}/metrics.json"
        return {k: v["value"] for k, v in json.loads(p.read_text())["metrics"].items()} if p.exists() else {}

    def audit_round(self, n, widths=(375, 1280), runner=True, **over):
        adir = self.w / f"rounds/r{n}/audit"
        for w in widths:
            write(adir / f"home@{w}.json", {"url": URL + f"?r={n}", "width": w, "metrics": {**AUDIT_BASE, **over}})
        if runner:
            stamp(adir, n)
        return run("ingest", "--dir", self.w, "--round", n, "--kind", "audit")

    def axe_round(self, n, impact=None, drop=None, route="/", runner=True):
        lines = ["VITALS " + json.dumps({"route": route, "title": "t", "width": 1280, "height": 800, "status": 200, "lcp": 900, "cls": 0})]
        for k in ("dark_window", "dark_375", "light_window", "light_375"):
            if k == drop:
                continue
            v = [{"id": "color-contrast", "impact": impact, "nodes": 2, "target": "p"}] if impact and k == "dark_375" else []
            lines.append("AXE " + json.dumps({k: {"violations": v, "incomplete": [{"id": "x", "nodes": 1}], "passes": 30}}))
        f = self.w / f"rounds/r{n}/qa/home/measure-r{n}.txt"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("noise\n" + "\n".join(lines) + "\n")
        if runner:
            stamp(self.w / f"rounds/r{n}/qa", n)
        return run("ingest", "--dir", self.w, "--round", n, "--kind", "axe")

    def evidence(self, name="ev.md", text="증거 기록"):
        p = self.w / name
        p.write_text(text)
        return p

    def manual_all(self, n):
        ev = self.evidence()
        lk = json.loads((self.w / "criteria.lock.json").read_text())
        for c in lk["criteria"]:
            if c["source"] == "manual":
                run("set", "--dir", self.w, "--round", n, "--metric", c["metric"], "--value", "true", "--evidence", ev, check=0)

    def compset(self, names=("acme",)):
        write(self.w / "research/comparison-set.json", {"competitors": [{"name": x} for x in names]})
        run("lockset", "--dir", self.w, check=0)

    def seal(self, n, key, check=0, name=None):
        kp = self.keydir / (name or f"key-r{n}.json")
        write(kp, key)
        p = run("seal", "--dir", self.w, "--round", n, "--key", kp, check=check)
        return kp if check == 0 else p

    def unseal(self, n, kp):
        shutil.copy(kp, self.w / f"rounds/r{n}/panel/key.json")

    def judge(self, n, jid, vendor, scores, rationale=True, blind=None):
        j = {"judge": jid, "vendor": vendor, "scores": scores, "blind_check": blind or {"recognized": [], "guessed_owner": "unknown"}}
        if rationale:
            j["rationale"] = {lab: {ax: "근거" for ax in sc} for lab, sc in scores.items()}
        write(self.w / f"rounds/r{n}/panel/judge-{jid}.json", j)

    def all_pass_round(self, n=0):
        self.audit_round(n)
        self.axe_round(n)
        self.manual_all(n)
        kp = self.seal(n, {"A": "ours", "B": "comp:acme"})
        self.judge(n, "c1", "anthropic", flat({"A": 4, "B": 4}))
        self.unseal(n, kp)
        run("panel", "--dir", self.w, "--round", n, check=0)


class Questions(Base):
    def test_every_set_respects_tool_limits(self):
        for s in ("scope", "preset", "quality1", "quality2", "process"):
            qs = json.loads(run("questions", "--dir", self.w, "--set", s, check=0).stdout)["questions"]
            self.assertTrue(1 <= len(qs) <= 4, s)
            self.assertEqual(len({q["question"] for q in qs}), len(qs))
            for q in qs:
                self.assertLessEqual(len(q["header"]), 12, q["header"])
                self.assertTrue(2 <= len(q["options"]) <= 4, q["header"])
                labels = [o["label"] for o in q["options"]]
                self.assertEqual(len(labels), len(set(labels)))
                self.assertTrue(labels[0].endswith(" (권장)"), q["header"])
                self.assertEqual(sum(l.endswith(" (권장)") for l in labels), 1)

    def test_quality_options_preview_their_checks(self):
        qs = json.loads(run("questions", "--dir", self.w, "--set", "quality1", check=0).stdout)["questions"]
        self.assertEqual([q["header"] for q in qs], ["시각 완성도", "타이포·색", "이미지", "모션·효과"])
        self.assertTrue(all("누적 검사" in o["preview"] for q in qs for o in q["options"]))

    def test_research_note_and_recommendation_follow_detection(self):
        rq = next(x for x in json.loads(run("questions", "--dir", self.w, "--set", "scope", check=0).stdout)["questions"] if x["header"] == "리서치")
        self.assertIn("리서치 없음", rq["question"])
        self.assertTrue(rq["options"][0]["label"].startswith("새로 10~15곳"))
        for i in range(6):
            (self.root / "web-crawling" / f"site{i}").mkdir(parents=True)
        self.init()
        rq = next(x for x in json.loads(run("questions", "--dir", self.w, "--set", "scope", check=0).stdout)["questions"] if x["header"] == "리서치")
        self.assertIn("web-crawling 6곳", rq["question"])
        self.assertTrue(rq["options"][0]["label"].startswith("기존 리서치 사용"))

    def test_answered_questions_are_skipped(self):
        write(self.w / "answers.json", {"answers": {"리서치": "기존 리서치 사용+보강", "기준 설정": "묶음으로 한 번에"}})
        out = json.loads(run("questions", "--dir", self.w, "--set", "scope", "--answers", self.w / "answers.json", check=0).stdout)
        self.assertEqual([q["header"] for q in out["questions"]], ["대상 범위", "변경 깊이"])
        self.assertEqual(out["skipped_already_answered"], ["리서치", "기준 설정"])

    def test_rigor_and_goal_options_follow_tools(self):
        self.set_tools(codex=None, goals=None)
        qs = {q["header"]: q for q in json.loads(run("questions", "--dir", self.w, "--set", "process", check=0).stdout)["questions"]}
        self.assertTrue(qs["판정 엄격도"]["options"][0]["label"].startswith("표준(동종)"))
        std = next(o for o in qs["판정 엄격도"]["options"] if o["label"].startswith("표준 ") or o["label"] == "표준")
        self.assertIn("다른 벤더 판정 도구를 찾지 못했다", std["description"])
        goal = [o["label"] for o in qs["goal 방식"]["options"]]
        self.assertTrue(goal[0].startswith("네이티브 /goal만"))
        self.assertFalse(any(x.startswith(("기록+멈춤", "goals.py")) for x in goal))

    def test_questions_mark_missing_tools(self):
        self.set_tools(runqa=None)
        qs = json.loads(run("questions", "--dir", self.w, "--set", "quality2", check=0).stdout)["questions"]
        a11y = next(q for q in qs if q["header"] == "접근성")
        self.assertTrue(any("이 환경에 없는 도구: runqa" in o["description"] for o in a11y["options"]))


class Compile(Base):
    def test_preset_lock_hash_chain_and_runner_policy(self):
        lk = self.lock()
        self.assertTrue(all(v == 1 for v in lk["levels"].values()))
        self.assertEqual(lk["targets"]["widths"], [375, 1280])
        sha = (self.w / "criteria.lock.sha256").read_text().strip()
        chain = [json.loads(x) for x in (self.w / "locks/chain.jsonl").read_text().splitlines()]
        self.assertEqual([r["kind"] for r in chain], ["compile", "lockset"])
        self.assertEqual(chain[0]["sha"], sha)
        self.assertEqual(lk["process"]["require_runner"].get("audit"), True)
        self.assertEqual(lk["process"]["quorum"], 1)

    def test_detail_answer_overrides_preset_and_widths_follow_responsive(self):
        lk = self.lock({"반응형": "6폭 무결"})
        self.assertEqual(lk["levels"]["responsive"], 2)
        self.assertEqual(lk["targets"]["widths"], [320, 375, 768, 1024, 1280, 1440])

    def test_higher_level_overrides_same_check_threshold(self):
        lcp = [c for c in self.lock({"성능": "빠름"})["criteria"] if c["id"] == "perf.lcp"]
        self.assertEqual((len(lcp), lcp[0]["value"]), (1, 1500))

    def test_unknown_label_and_missing_dims_fail(self):
        self.assertIn("선택지에 없음", run("compile", "--dir", self.w, "--answers", self.answers({"성능": "엄청 빠름"})).stderr)
        write(self.w / "a2.json", {"answers": {"기준 설정": "항목별 세부 선택", "성능": "Good 기준"}, "targets": {"urls": [URL]}})
        self.assertIn("수준이 정해지지 않은 차원", run("compile", "--dir", self.w, "--answers", self.w / "a2.json").stderr)

    def test_recommended_mode_fills_from_default_preset(self):
        write(self.w / "a3.json", {"answers": {"기준 설정": "권장값으로 진행"}, "targets": {"urls": [URL]}})
        run("compile", "--dir", self.w, "--answers", self.w / "a3.json", check=0)
        self.assertEqual(json.loads((self.w / "criteria.lock.json").read_text())["levels"]["visual"], 2)

    def test_targets_required_and_normalized_duplicates(self):
        self.assertIn("대상 URL이 없다", run("compile", "--dir", self.w, "--answers", self.answers(targets={"urls": []})).stderr)
        for pair in ([URL, URL + "?r=3"], [URL, URL + "index.html"], ["http://Example.com:80/a/", "http://example.com/a"]):
            self.assertIn("중복", run("compile", "--dir", self.w, "--answers", self.answers(targets={"urls": pair})).stderr, pair)

    def test_missing_tools_drop_detectors_and_reroute_measures(self):
        self.set_tools(runqa=None, inspect=None)
        p = run("compile", "--dir", self.w, "--answers", self.answers({"시각 완성도": "체계 갖춤"}), check=0)
        lk = json.loads((self.w / "criteria.lock.json").read_text())
        ids = {c["id"] for c in lk["criteria"]}
        self.assertNotIn("vis.inspect", ids)                   # 검출기가 없으면 그 검사는 빠진다(메모 남김)
        self.assertIn("vis.detect", ids)
        self.assertIn("a11y.axe_serious", ids)                  # 측정 도구가 없으면 ingest 경로로 잰다
        self.assertEqual(lk["ingest_only"], ["axe"])
        self.assertFalse(lk["process"]["require_runner"]["axe"])
        self.assertIn("inspect 검출기가 없어 뺐다", p.stdout)
        self.assertIn("ingest로 잰다", p.stdout)

    def test_cross_vendor_missing_is_noted_and_same_vendor_rigor_exists(self):
        self.set_tools(codex=None)
        p = run("compile", "--dir", self.w, "--answers", self.answers({"판정 엄격도": "표준"}), check=0)
        self.assertIn("다른 벤더 판정 도구", p.stdout)
        p = self.relock({"판정 엄격도": "표준(동종)"})
        self.assertEqual(p.returncode, 0, p.stderr)
        lk = json.loads((self.w / "criteria.lock.json").read_text())
        self.assertNotIn("rg.vendor", {c["id"] for c in lk["criteria"]})
        self.assertEqual(lk["process"]["quorum"], 3)

    def test_relock_needs_reason_and_failed_relock_keeps_old_lock(self):
        self.lock()
        self.assertIn("--reason", run("compile", "--dir", self.w, "--answers", self.w / "answers.json", "--relock").stderr)
        before = (self.w / "criteria.lock.json").read_text()
        p = self.relock({"성능": "없는 선택지"})
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual((self.w / "criteria.lock.json").read_text(), before)   # 실패해도 옛 잠금이 그대로
        for _ in range(3):                                                      # 같은 초에 여러 번 다시 잠가도 이력이 덮이지 않는다
            self.assertEqual(self.relock(reason="사용자: 기준 유지").returncode, 0)
        self.assertEqual(len(list((self.w / "locks").glob("criteria.*.json"))), 3)

    def test_history_blocks_compile_without_relock(self):
        self.lock()
        (self.w / "criteria.lock.json").unlink()
        (self.w / "criteria.lock.sha256").unlink()
        self.assertIn("잠금 이력", run("compile", "--dir", self.w, "--answers", self.answers()).stderr)
        self.assertEqual(self.relock(reason="사용자 승인: 잠금 파일 복구").returncode, 0)
        chain = [json.loads(x) for x in (self.w / "locks/chain.jsonl").read_text().splitlines() if '"compile"' in x]
        self.assertEqual((len(chain), chain[-1]["prev"], chain[-1]["relock"]), (2, None, True))

    def test_scope_note_when_multi_page_scope_has_one_url(self):
        out = run("compile", "--dir", self.w, "--answers", self.answers({"대상 범위": "핵심 여정"}), check=0).stdout
        self.assertIn("URL이 1개", out)


class Measure(Base):
    def test_set_rules(self):
        ev = self.evidence()
        self.assertIn("compile", run("set", "--dir", self.w, "--round", 0, "--metric", "motion.pause_ok", "--value", "true", "--evidence", ev).stderr)
        self.lock()
        self.assertIn("measure·ingest", run("set", "--dir", self.w, "--round", 0, "--metric", "perf.lcp_ms", "--value", 1, "--evidence", ev).stderr)
        self.assertIn("잠긴 기준에 없는", run("set", "--dir", self.w, "--round", 0, "--metric", "foo.bar", "--value", 9, "--evidence", ev).stderr)
        self.assertIn("measure·ingest·panel·personas", run("set", "--dir", self.w, "--round", 0, "--metric", "panel.judges", "--value", 9, "--evidence", ev).stderr)
        self.assertIn("비어 있지 않은 파일", run("set", "--dir", self.w, "--round", 0, "--metric", "contrast.unknown_ok", "--value", "true", "--evidence", self.w).stderr)
        self.assertIn("비어 있지 않은 파일", run("set", "--dir", self.w, "--round", 0, "--metric", "contrast.unknown_ok", "--value", "true", "--evidence", self.evidence("empty.md", "")).stderr)
        outside = self.keydir / "x.md"
        outside.write_text("x")
        self.assertIn("비어 있지 않은 파일", run("set", "--dir", self.w, "--round", 0, "--metric", "contrast.unknown_ok", "--value", "true", "--evidence", outside).stderr)
        old = self.evidence("old.md", "예전 확인")
        past = time.time() - 3600
        os.utime(old, (past, past))
        self.assertIn("회차 시작", run("set", "--dir", self.w, "--round", 0, "--metric", "contrast.unknown_ok", "--value", "true", "--evidence", old).stderr)
        run("set", "--dir", self.w, "--round", 0, "--metric", "contrast.unknown_ok", "--value", "true", "--evidence", ev, check=0)

    def test_nan_and_infinity_are_rejected(self):
        self.lock()
        ev = self.evidence()
        for bad in ("nan", "inf", "-inf", "1e999"):
            p = run("set", "--dir", self.w, "--round", 0, "--metric", "contrast.unknown_ok", f"--value={bad}", "--evidence", ev)
            self.assertNotEqual(p.returncode, 0, bad)
            self.assertIn("유한한", p.stderr, bad)

    def test_parallel_sets_are_all_kept(self):
        custom = [{"id": f"cu.m{i}", "desc": "x", "metric": f"custom.m{i}_ok", "op": "true", "value": True, "source": "manual"} for i in range(12)]
        self.lock(custom=custom)
        ev = self.evidence()
        procs = [subprocess.Popen([sys.executable, str(DLOOP), "set", "--dir", str(self.w), "--round", "0", "--metric", c["metric"],
                                   "--value", "true", "--evidence", str(ev)], stdout=subprocess.PIPE, stderr=subprocess.PIPE) for c in custom]
        for p in procs:
            p.wait()
        self.assertTrue(all(p.returncode == 0 for p in procs))
        m = self.metrics()
        self.assertEqual(sorted(k for k in m if k.startswith("custom.")), sorted(c["metric"] for c in custom))

    def test_ingest_needs_exact_width_coverage(self):
        self.lock()
        self.audit_round(0, widths=(375, 1290))      # 1280 대신 1290 → 정확히 일치하지 않음
        m = self.metrics()
        self.assertEqual(m["audit.coverage"], 0.5)
        self.assertNotIn("overflow.px", m)

    def test_failed_reingest_drops_old_values(self):
        self.lock()
        self.audit_round(0)
        self.assertIn("overflow.px", self.metrics())
        (self.w / "rounds/r0/audit/home@1280.json").unlink()
        run("ingest", "--dir", self.w, "--round", 0, "--kind", "audit", check=0)
        m = self.metrics()
        self.assertNotIn("overflow.px", m)          # 옛 통과값이 남지 않는다
        self.assertEqual(m["audit.coverage"], 0.5)

    def test_missing_or_null_required_metric_is_unmeasured(self):
        self.lock()
        self.audit_round(0, **{"overflow.px": None, "type.measure_em_latin": None})
        m = self.metrics()
        self.assertNotIn("overflow.px", m)          # 넘침 None = 측정 실패
        self.assertIsNone(m["type.measure_em_latin"])   # 라틴 문단 없음 = 해당 없음

    def test_aggregates_worst_case(self):
        self.lock()
        adir = self.w / "rounds/r0/audit"
        write(adir / "home@375.json", {"url": URL, "width": 375, "metrics": {**AUDIT_BASE, "overflow.px": 12, "type.body_px_min": 14}})
        write(adir / "home@1280.json", {"url": URL, "width": 1280, "metrics": {**AUDIT_BASE, "struct.lang": False}})
        stamp(adir, 0)
        run("ingest", "--dir", self.w, "--round", 0, "--kind", "audit", check=0)
        m = self.metrics()
        self.assertEqual((m["overflow.px"], m["type.body_px_min"], m["struct.lang"], m["struct.h1_bad"]), (12, 14, False, 0))

    def test_round_order_is_enforced(self):
        self.lock()
        self.assertIn("r0(기준선)", self.audit_round(1).stderr)
        self.audit_round(0)
        self.assertIn("판정(check)한 뒤", self.audit_round(1).stderr)
        out = run("check", "--dir", self.w).stdout          # 잘못 놓인 r1 폴더가 있어도 차례인 r0을 판정한다
        self.assertTrue(out.startswith("r0:"), out)
        self.assertIn("판정 차례 밖의 폴더", out)
        self.assertIn("건너뛸 수 없다", self.audit_round(2).stderr)
        self.assertIn("새 회차", self.audit_round(0).stderr)   # 판정한 회차에 다시 넣으려면 --fix-reason
        self.audit_round(1)
        run("check", "--dir", self.w)
        self.assertIn("지난 회차", run("ingest", "--dir", self.w, "--round", 0, "--kind", "audit").stderr)
        self.assertNotEqual(run("ingest", "--dir", self.w, "--round", -1, "--kind", "audit").returncode, 0)


class Ingest(Base):
    def setUp(self):
        super().setUp()
        self.lock()

    def test_axe_counts_serious_and_needs_all_combos(self):
        self.axe_round(0, impact="serious")
        m = self.metrics()
        self.assertEqual((m["axe.serious_critical"], m["axe.violations"], m["axe.incomplete"], m["axe.coverage"]), (1, 1, 4, 1.0))
        self.axe_round(0, drop="light_375")
        self.assertEqual(self.metrics()["axe.coverage"], 0.0)
        self.assertNotIn("axe.serious_critical", self.metrics())

    def test_axe_moderate_is_not_serious(self):
        self.axe_round(0, impact="moderate")
        m = self.metrics()
        self.assertEqual((m["axe.serious_critical"], m["axe.violations"]), (0, 1))

    def test_audit_from_another_round_is_rejected(self):
        self.audit_round(0)
        run("check", "--dir", self.w)
        shutil.copytree(self.w / "rounds/r0/audit", self.w / "rounds/r1/audit")
        self.assertIn("다른 회차", run("ingest", "--dir", self.w, "--round", 1, "--kind", "audit").stderr)

    def inspect_report(self, **over):
        rep = {"url": URL, "at": "2999-01-01T00:00:00Z", "allow": [], "viewports": [{"width": 1280, "load": "load"}, {"width": 375, "load": "load"}],
               "findings": [{"level": "FAIL", "id": "eyebrow"}, {"level": "WARN", "id": "measure"}]}
        rep.update(over)
        write(self.w / "rounds/r0/inspect/home.json", rep)
        stamp(self.w / "rounds/r0/inspect", 0)
        return run("ingest", "--dir", self.w, "--round", 0, "--kind", "inspect")

    def test_inspect_validation_and_approved_exceptions(self):
        self.assertIn("회차 시작", self.inspect_report(at="2000-01-01T00:00:00Z").stderr)
        self.assertIn("회차 시작", self.inspect_report().stderr)                 # 미래 시각도 거부
        nowiso = datetime.now(timezone.utc).isoformat()
        self.assertIn("측정한 폭이 없거나", self.inspect_report(at=nowiso, viewports=[]).stderr)
        self.assertIn("모두 재야", self.inspect_report(at=nowiso, viewports=[{"width": 1280, "load": "load"}]).stderr)
        self.assertIn("대상이 아닌 URL", self.inspect_report(at=nowiso, url="http://127.0.0.1:9999/other").stderr)
        self.assertIn("사유·증거 없는 허용", self.inspect_report(at=nowiso, allow=["still-page"]).stderr)
        ev = str(self.evidence())
        both = [{"level": "FAIL", "id": "still-page"}, {"level": "FAIL", "id": "eyebrow"}]
        write(self.w / "exceptions.json", [{"kind": "allow", "rule": "still-page", "reason": "정지 시안 단계", "evidence": ev}])
        p = self.inspect_report(at=nowiso, findings=both)                        # 승인 원문이 없으면 규칙 전체 예외는 무시
        self.assertIn("예외 무시", p.stdout)
        self.assertEqual(self.metrics()["inspect.fail"], 2)
        write(self.w / "exceptions.json", [{"kind": "allow", "rule": "still-page", "reason": "정지 시안 단계", "evidence": ev,
                                             "approval": "사용자: 시안 단계는 모션 규칙 빼도 돼"}])
        self.inspect_report(at=nowiso, findings=both)
        m = self.metrics()
        self.assertEqual((m["inspect.fail"], m["inspect.excepted"]), (1, 1))

    def test_detect_needs_scope_raw_run_and_counts_exceptions(self):
        ddir = self.w / "rounds/r0/detect"
        write(ddir / "detect.json", [{"antipattern": "low-contrast", "file": "/b/dist/index.html", "line": 3}, {"antipattern": "b", "file": "/b/dist/a.html"}])
        self.assertIn("scope.json", run("ingest", "--dir", self.w, "--round", 0, "--kind", "detect").stderr)
        write(ddir / "scope.json", {"html_files": 0, "rc": 2, "flags": ["--json", "--no-inline-ignores"]})
        stamp(ddir, 0)
        run("ingest", "--dir", self.w, "--round", 0, "--kind", "detect", check=0)
        self.assertNotIn("detect.count", self.metrics())      # 검사한 HTML 0개 = 미측정
        write(ddir / "scope.json", {"html_files": 3, "rc": 2, "flags": ["--json"]})
        self.assertIn("예외 표식", run("ingest", "--dir", self.w, "--round", 0, "--kind", "detect", check=0).stdout)
        self.assertNotIn("detect.count", self.metrics())      # 소스 안 예외 표식을 따른 실행 = 미측정
        write(ddir / "scope.json", {"html_files": 3, "rc": 2, "flags": ["--json", "--no-inline-ignores"]})
        run("ingest", "--dir", self.w, "--round", 0, "--kind", "detect", check=0)
        self.assertEqual(self.metrics()["detect.count"], 2)
        write(self.w / "exceptions.json", [{"kind": "detect", "antipattern": "low-contrast", "file": "dist/index.html", "line": 3,
                                             "reason": "그라디언트 위 글자 — 실측 7.1:1", "evidence": str(self.evidence())}])
        run("ingest", "--dir", self.w, "--round", 0, "--kind", "detect", check=0)
        m = self.metrics()
        self.assertEqual((m["detect.count"], m["detect.excepted"]), (1, 1))


class Panel(Base):
    KEY = {"A": "comp:acme", "B": "ours", "C": "comp:beta"}

    def setUp(self):
        super().setUp()
        self.lock()
        self.compset(("acme", "beta"))
        self.pdir = self.w / "rounds/r0/panel"
        self.kp = self.seal(0, self.KEY)

    def scores(self, ours, acme, beta):
        return flat({"B": ours, "A": acme, "C": beta})

    def panel(self, check=0):
        self.unseal(0, self.kp)
        return run("panel", "--dir", self.w, "--round", 0, check=check)

    def panel_metrics(self):
        self.panel()
        return self.metrics()

    def test_medians_wins_losses_gap(self):
        self.judge(0, "c1", "anthropic", self.scores([5, 4, 4, 4, 4, 4, 4], 3, [4, 4, 3, 3, 3, 3, 3]))
        self.judge(0, "c2", "Anthropic", self.scores(4, 3, [4, 4, 3, 3, 3, 3, 3]))
        self.judge(0, "x1", "openai", self.scores([4, 4, 4, 4, 4, 4, 5], 3, [4, 4, 3, 3, 3, 3, 3]))
        m = self.panel_metrics()
        self.assertEqual((m["panel.judges"], m["panel.cross_vendor"], m["panel.axis.hierarchy.ours"]), (3, 1, 4))
        self.assertEqual((m["panel.vs.acme.wins"], m["panel.vs.beta.wins"], m["panel.vs.beta.losses"]), (7, 5, 0))
        self.assertAlmostEqual(m["panel.vs.min_wins_ratio"], 5 / 7)
        self.assertEqual(m["panel.vs_median.min_diff"], 0.5)

    def test_small_or_split_differences_are_ties(self):
        for jid, ours in (("c1", 4), ("c2", 4), ("c3", 5), ("c4", 5)):
            self.judge(0, jid, "anthropic", self.scores(ours, 4, 2))
        m = self.panel_metrics()
        self.assertEqual(m["panel.vs.acme.wins"], 0)            # 중앙값 4.5 대 4 — 판정자 절반만 우세 → 무승부
        self.assertEqual(m["panel.vs.beta.wins"], 7)
        self.assertEqual(m["panel.vs.acme.losses"], 0)

    def test_order_variants_average_within_judge_first(self):
        self.judge(0, "c1@a", "anthropic", self.scores(4, 3, 3))
        self.judge(0, "c1@b", "anthropic", self.scores(5, 3, 3), blind={"recognized": [], "guessed_owner": "B"})
        self.judge(0, "c2", "anthropic", self.scores(3, 3, 3))
        self.judge(0, "c3", "anthropic", self.scores(4, 3, 3))
        m = self.panel_metrics()
        self.assertEqual((m["panel.judges"], m["panel.blind_breaches"]), (3, 1))
        self.assertEqual(m["panel.axis.copy.ours"], 4)          # c1 평균 4.5, c2 3, c3 4의 중앙값 — 변형을 늘려도 한 표

    def test_blind_majority_breach_produces_no_scores(self):
        self.judge(0, "c1", "anthropic", self.scores(5, 3, 3), blind={"recognized": ["acme"], "guessed_owner": "unknown"})
        self.judge(0, "c2", "anthropic", self.scores(5, 3, 3), blind={"recognized": [], "guessed_owner": "B"})
        self.judge(0, "c3", "anthropic", self.scores(5, 3, 3))
        out = self.panel().stdout
        self.assertIn("블라인드가 깨진", out)
        m = self.metrics()
        self.assertEqual(m["panel.blind_breaches"], 2)
        self.assertNotIn("panel.vs.min_wins_ratio", m)
        self.assertNotIn("panel.ours_min", m)

    def test_every_cell_needs_a_score_and_a_reason(self):
        self.judge(0, "c1@c", "anthropic", self.scores(4, 3, 3))
        self.assertIn("@a·@b", self.panel(check=None).stderr)
        (self.pdir / "judge-c1@c.json").unlink()
        self.judge(0, "c1", "anthropic", self.scores(6, 3, 3))
        self.assertIn("1~5", self.panel(check=None).stderr)
        self.judge(0, "c1", "anthropic", self.scores(4, 3, 3), rationale=False)
        self.assertIn("rationale", self.panel(check=None).stderr)
        sc = self.scores(4, 3, 3)
        del sc["C"]["trust"]
        self.judge(0, "c1", "anthropic", sc)
        self.assertIn("모든 자극·축", self.panel(check=None).stderr)
        self.judge(0, "c1", "anthropic", self.scores(4, 3, 3))
        j = json.loads((self.pdir / "judge-c1.json").read_text())
        j["rationale"]["B"]["copy"] = " "
        write(self.pdir / "judge-c1.json", j)
        self.assertIn("근거가 없다", self.panel(check=None).stderr)

    def test_vendor_names_are_grouped_by_family(self):
        self.judge(0, "c1", "Claude Opus 5.5", self.scores(4, 3, 3))
        self.judge(0, "x1", "OpenAI codex (gpt)", self.scores(4, 3, 3))
        self.judge(0, "x2", "some-model", self.scores(4, 3, 3))
        m = self.panel_metrics()
        self.assertEqual((m["panel.judges"], m["panel.cross_vendor"]), (3, 1))

    def test_seal_rules(self):
        inside = self.root / "key.json"
        write(inside, self.KEY)
        self.assertIn("저장소 밖", run("seal", "--dir", self.w, "--round", 0, "--key", inside).stderr)
        self.assertGreaterEqual(len(json.loads(self.kp.read_text())["nonce"]), 16)      # 봉인 때 무작위 값을 넣는다
        self.judge(0, "c1", "anthropic", self.scores(4, 3, 3))
        self.assertIn("이미 있다", self.seal(0, self.KEY, check=None, name="again.json").stderr)
        past = time.time() - 600
        os.utime(self.pdir / "judge-c1.json", (past, past))
        p = self.panel(check=None)
        self.assertEqual(p.returncode, 3)
        self.assertIn("봉인보다 먼저", p.stderr)
        self.judge(0, "c1", "anthropic", self.scores(4, 3, 3))
        swapped = {**json.loads(self.kp.read_text()), "A": "ours", "B": "comp:acme"}   # 판정 뒤에 우리 라벨 바꿔 끼우기
        write(self.pdir / "key.json", swapped)
        p = run("panel", "--dir", self.w, "--round", 0)
        self.assertEqual(p.returncode, 3)
        self.assertIn("봉인", p.stderr)

    def test_seal_needs_the_exact_locked_competitors(self):
        shutil.rmtree(self.pdir)
        self.assertIn("잠긴 목록", self.seal(0, {"A": "comp:acme", "B": "ours"}, check=None).stderr)
        self.assertIn("잠긴 목록", self.seal(0, {"A": "comp:acme", "B": "ours", "C": "comp:acme"}, check=None).stderr)

    def test_reference_anchor_is_not_a_competitor(self):
        shutil.rmtree(self.pdir)
        self.kp = self.seal(0, {**self.KEY, "D": "ref:studio"})
        sc = self.scores(4, 3, 3)
        sc["D"] = dict(zip(AXES, [5] * 7))
        self.judge(0, "c1", "anthropic", sc)
        self.assertEqual(self.panel_metrics()["panel.vs.min_wins_ratio"], 1)

    def test_comparison_set_change_after_lock_is_tamper(self):
        self.judge(0, "c1", "anthropic", self.scores(4, 3, 3))
        write(self.w / "research/comparison-set.json", {"competitors": [{"name": "acme"}]})
        (self.w / "comparison-set.sha256").write_text(__import__("hashlib").sha256((self.w / "research/comparison-set.json").read_bytes()).hexdigest() + "\n")
        self.assertEqual(self.panel(check=None).returncode, 3)       # 해시 파일을 다시 써도 잠금 이력과 다르다

    def pairs(self, jid, results, why="근거"):
        rows = []
        for (comp, ax), (w1, w2) in results.items():
            rows.append({"left": "B", "right": comp, "axis": ax, "winner": w1, "why": why})
            rows.append({"left": comp, "right": "B", "axis": ax, "winner": w2, "why": why})
        write(self.pdir / f"pairs-{jid}.json", {"judge": jid, "pairs": rows})

    def test_pairwise_needs_both_orders_and_keeps_lower_grade(self):
        self.judge(0, "c1", "anthropic", self.scores(4, 3, 3))
        full = {(c, ax): ("B", "B") for c in ("A", "C") for ax in AXES}
        mixed = dict(full); mixed[("A", "hierarchy")] = ("B", "A")
        loss = dict(full); loss[("C", "copy")] = ("C", "C")
        self.pairs("c1", mixed)
        self.pairs("c2", loss)
        self.pairs("c3", full)
        m = self.panel_metrics()
        self.assertEqual((m["panel.pair.acme.wins"], m["panel.pair.beta.wins"], m["panel.pair.beta.losses"], m["panel.pair.max_losses"]), (7, 6, 0, 0))

    def test_pairwise_split_vote_counts_as_loss(self):
        self.judge(0, "c1", "anthropic", self.scores(4, 3, 3))
        full = {(c, ax): ("B", "B") for c in ("A", "C") for ax in AXES}
        loss = dict(full); loss[("C", "copy")] = ("C", "C")
        self.pairs("c1", full)
        self.pairs("c2", loss)
        m = self.panel_metrics()
        self.assertEqual((m["panel.pair.beta.losses"], m["panel.pair.max_losses"]), (1, 1))

    def test_pairwise_rejects_bad_winner_missing_reason_duplicates_and_one_direction(self):
        self.judge(0, "c1", "anthropic", self.scores(4, 3, 3))
        self.pairs("c1", {("A", "hierarchy"): ("Bee", "B")})
        self.assertIn("winner", self.panel(check=None).stderr)
        self.pairs("c1", {("A", "hierarchy"): ("B", "B")}, why="")
        self.assertIn("근거(why)", self.panel(check=None).stderr)
        full = {(c, ax): ("B", "B") for c in ("A", "C") for ax in AXES}
        self.pairs("c1", full)
        shutil.copy(self.pdir / "pairs-c1.json", self.pdir / "pairs-c1-copy.json")
        self.assertIn("중복", self.panel(check=None).stderr)
        (self.pdir / "pairs-c1-copy.json").unlink()
        rows = [{"left": "B", "right": c, "axis": ax, "winner": "B", "why": "w"} for c in ("A", "C") for ax in AXES]
        write(self.pdir / "pairs-c1.json", {"judge": "c1", "pairs": rows})
        self.assertIn("맞비교 미완", self.panel().stdout)
        self.assertNotIn("panel.pair.max_losses", self.metrics())


class Personas(Base):
    def test_receipts_and_severity_mapping(self):
        self.lock()
        pdir = self.w / "rounds/r0/personas"
        pdir.mkdir(parents=True)
        f = pdir / "findings.jsonl"
        f.write_text(json.dumps({"persona": "designer", "severity": "high"}) + "\n")
        self.assertIn("실행 기록", run("personas", "--dir", self.w, "--round", 0).stderr)
        (pdir / "designer.md").write_text("페르소나 답 원문")
        rows = [{"persona": "designer", "severity": s, "status": st} for s, st in
                (("high", "open"), ("Critical", "open"), ("4", "fixed"), ("2", "open"), ("minor", "open"), ("0", "open"), ("Low", "open"))]
        f.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        run("personas", "--dir", self.w, "--round", 0, check=0)
        m = self.metrics()
        self.assertEqual((m["persona.count"], m["persona.open_high"], m["persona.open_medium"]), (1, 3, 2))   # status는 보지 않는다
        f.write_text(json.dumps({"persona": "designer", "severity": "urgent"}) + "\n")
        self.assertIn("severity", run("personas", "--dir", self.w, "--round", 0).stderr)


class Check(Base):
    def test_exit_codes_tamper_and_rounding(self):
        lk = self.lock()
        self.assertEqual(run("check", "--dir", self.w).returncode, 2)
        self.audit_round(0)
        p = run("check", "--dir", self.w)
        self.assertEqual(p.returncode, 2, p.stdout)
        self.audit_round(1, **{"perf.cls": 0.1004})              # 0.1로 반올림해 통과시키지 않는다
        p = run("check", "--dir", self.w)
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn("perf.cls", p.stdout)
        lk["criteria"][0]["value"] = 99
        write(self.w / "criteria.lock.json", lk)
        self.assertEqual(run("check", "--dir", self.w).returncode, 3)
        import hashlib
        (self.w / "criteria.lock.sha256").write_text(hashlib.sha256((self.w / "criteria.lock.json").read_bytes()).hexdigest() + "\n")
        p = run("check", "--dir", self.w)
        self.assertEqual(p.returncode, 3)                         # 해시 파일을 다시 써도 잠금 이력과 다르다
        self.assertIn("잠금 이력", p.stdout)

    def test_all_pass_returns_zero_with_gate_word(self):
        self.lock()
        self.all_pass_round(0)
        p = run("check", "--dir", self.w)
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn("all locked criteria passed", p.stdout)
        self.assertIn("다시 잠금 0회", p.stdout)

    def test_provenance_runner_round_and_raw_digest(self):
        self.lock()
        self.all_pass_round(0)
        self.assertEqual(run("check", "--dir", self.w).returncode, 0)
        audit_file = self.w / "rounds/r0/audit/home@375.json"
        audit_file.write_text(audit_file.read_text().replace('"overflow.px": 0', '"overflow.px": 5'))
        p = run("check", "--dir", self.w)
        self.assertEqual(p.returncode, 2)
        self.assertIn("집계 뒤 바뀜", p.stdout)
        (self.w / "rounds/r0/audit/runner.json").unlink()        # 직접 측정 기록이 없는 원 출력(측정 오류 수정으로 같은 회차 재집계)
        run("ingest", "--dir", self.w, "--round", 0, "--kind", "audit", "--fix-reason", "시험", check=0)
        self.assertIn("dloop measure", run("check", "--dir", self.w).stdout)
        stamp(self.w / "rounds/r0/audit", 7)                       # 다른 회차의 실행 기록
        run("ingest", "--dir", self.w, "--round", 0, "--kind", "audit", "--fix-reason", "시험", check=0)
        self.assertIn("이 회차에 dloop measure", run("check", "--dir", self.w).stdout)
        mp = self.w / "rounds/r0/metrics.json"
        data = json.loads(mp.read_text())
        data["metrics"]["axe.serious_critical"]["source"] = "set"   # 출처를 바꿔 끼우기
        mp.write_text(json.dumps(data))
        self.assertIn("출처 set", run("check", "--dir", self.w).stdout)

    def test_manual_evidence_change_is_detected(self):
        self.lock()
        self.all_pass_round(0)
        self.evidence(text="바뀐 증거")
        p = run("check", "--dir", self.w)
        self.assertEqual(p.returncode, 2)
        self.assertIn("수동 증거", p.stdout)

    def test_competitive_criteria_need_locked_set(self):
        self.lock()
        self.all_pass_round(0)
        (self.w / "comparison-set.sha256").unlink()
        self.assertEqual(run("check", "--dir", self.w).returncode, 3)

    def test_relock_with_new_target_unmeasures_old_metrics(self):
        self.lock()
        self.all_pass_round(0)
        self.assertEqual(run("check", "--dir", self.w).returncode, 0)
        self.assertEqual(self.relock(targets={"urls": [URL, URL + "signup"]}).returncode, 0)
        p = run("check", "--dir", self.w)
        self.assertEqual(p.returncode, 2, p.stdout)
        self.assertIn("대상·폭이 바뀐 뒤", p.stdout)
        self.assertIn("다시 잠금 1회", p.stdout)

    def test_not_latest_and_unknown_round(self):
        self.lock()
        self.all_pass_round(0)
        run("check", "--dir", self.w, check=0)
        before = (self.w / "rounds/r0/verdict.json").read_text()
        self.audit_round(1, **{"perf.lcp_ms": 9000})
        p = run("check", "--dir", self.w, "--round", 0)
        self.assertEqual(p.returncode, 3)
        self.assertIn("NOT_LATEST", p.stdout)
        self.assertNotIn("all locked criteria passed", p.stdout)
        self.assertEqual((self.w / "rounds/r0/verdict.json").read_text(), before)
        self.assertEqual(run("check", "--dir", self.w, "--round", 9).returncode, 3)
        self.assertFalse((self.w / "rounds/r9").exists())

    def test_work_folder_can_be_moved(self):
        self.lock()
        self.all_pass_round(0)
        self.assertEqual(run("check", "--dir", self.w).returncode, 0)
        moved = self.root / "moved-project"
        shutil.copytree(self.root, moved, ignore=shutil.ignore_patterns("moved-project"))
        p = run("check", "--dir", moved / "W")
        self.assertEqual(p.returncode, 0, p.stdout)            # 복사·이동해도 원 출력·증거를 작업 폴더 기준으로 찾는다

    def test_relative_work_dir_works(self):
        rel = os.path.relpath(self.w, Path.cwd())
        run("compile", "--dir", rel, "--answers", self.answers(), check=0)
        self.compset()
        self.all_pass_round(0)
        self.assertEqual(run("check", "--dir", rel).returncode, 0)

    def test_round_cap_flag_and_exceed(self):
        self.lock()
        for n in range(3):
            self.audit_round(n)
            run("check", "--dir", self.w, "--round", n)
        self.assertIn("ROUND_CAP", " ".join(json.loads((self.w / "rounds/r2/verdict.json").read_text())["flags"]))
        p = self.audit_round(3)
        self.assertEqual(p.returncode, 3)
        self.assertIn("반복 한도", p.stderr)

    def stall(self, values):
        self.lock({"반복 한도": "6회"})
        for n, v in enumerate(values):
            self.audit_round(n, **{"perf.lcp_ms": v})
            run("check", "--dir", self.w, "--round", n)
        return " ".join(json.loads((self.w / f"rounds/r{len(values) - 1}/verdict.json").read_text())["flags"])

    def test_stall_needs_k_consecutive_non_improvements(self):
        self.assertIn("STALLED: perf.lcp", self.stall((4000, 4100, 4200)))

    def test_deleting_a_middle_verdict_makes_check_rejudge_it(self):
        self.stall((4000, 4100, 4200))
        (self.w / "rounds/r1/verdict.json").unlink()            # 판정 기록을 지워 정체 신호를 숨기려 해도
        self.assertTrue(run("check", "--dir", self.w).stdout.startswith("r1:"))   # 차례인 r1부터 다시 판정한다
        self.assertIn("STALLED: perf.lcp", run("check", "--dir", self.w).stdout)

    def test_improvement_inside_window_is_not_stall(self):
        self.assertNotIn("STALLED: perf.lcp", self.stall((4000, 3900, 3950)))

    def test_steady_improvement_is_not_stall(self):
        self.assertNotIn("STALLED: perf.lcp", self.stall((4000, 3500, 3000)))

    def test_equality_criteria_use_distance(self):
        self.lock({"반복 한도": "6회"})
        for n, v in enumerate((3, 2, 1)):
            self.audit_round(n, **{"overflow.px": v})
            run("check", "--dir", self.w, "--round", n)
        flags = " ".join(json.loads((self.w / "rounds/r2/verdict.json").read_text())["flags"])
        self.assertNotIn("STALLED: rs.overflow", flags)


class Lifecycle(Base):
    def test_resume_finds_the_active_folder_and_init_refuses_a_second(self):
        w1 = self.root / "tasks" / "design-loop-2026-10-15"
        run("init", "--dir", w1, "--root", self.root, "--url", URL, check=0)
        out = run("resume", "--root", self.root, check=0).stdout
        self.assertIn("design-loop-2026-10-15", out)
        p = run("init", "--dir", self.root / "tasks" / "design-loop-2026-10-16", "--root", self.root, "--url", URL)
        self.assertIn("resume", p.stderr)
        run("init", "--dir", self.root / "tasks" / "design-loop-2026-10-16", "--root", self.root, "--url", URL, "--new", check=0)

    def test_judged_round_needs_fix_reason_and_keeps_old_verdict(self):
        self.lock()
        self.audit_round(0)
        run("check", "--dir", self.w, "--round", 0)
        p = self.audit_round(0)
        self.assertIn("새 회차", p.stderr)
        run("ingest", "--dir", self.w, "--round", 0, "--kind", "audit", "--fix-reason", "측정 폭 오류", check=0)
        self.assertEqual(len(list((self.w / "rounds/r0").glob("verdict.*.json"))), 1)

    def test_relock_keeps_detector_config_baseline(self):
        self.lock()
        cfg = self.root / ".impeccable" / "config.json"
        cfg.parent.mkdir()
        cfg.write_text('{"detector": {"ignoreRules": ["low-contrast"]}}')
        self.assertEqual(self.relock(reason="사용자 승인: 한도 변경").returncode, 0)
        self.audit_round(0)
        self.assertIn("guard..impeccable/config.json", run("check", "--dir", self.w).stdout)   # relock으로 설정 변경이 묻히지 않는다
        self.assertEqual(self.relock(None, "사용자 승인: 설정 기준선 다시 찍기", "--reset-guards").returncode, 0)
        self.assertNotIn("guard.", run("check", "--dir", self.w).stdout)

    def test_round_cap_override_and_persona_rigor_conflict(self):
        run("compile", "--dir", self.w, "--answers", self.answers(), "--round-cap", "8", check=0)
        self.assertEqual(json.loads((self.w / "criteria.lock.json").read_text())["process"]["round_cap"], 8)
        p = self.relock({"시각 완성도": "완성도 높음"})
        self.assertEqual(p.returncode, 4)
        self.assertIn("페르소나", p.stderr)

    def test_goal_ab_prints_both_and_cd_for_every_goals_call(self):
        out = run("compile", "--dir", self.w, "--answers", self.answers({"goal 방식": "기록+멈춤 차단"}), check=0).stdout
        self.assertIn("/goal design-elevation-loop", out)
        cmds = [l for l in out.splitlines() if "python3 /x " in l]          # 시험에서 goals.py 경로는 /x
        self.assertGreaterEqual(len(cmds), 4)
        self.assertTrue(all(f"cd {self.w.resolve()} && python3 /x " in l for l in cmds), cmds)
        self.assertIn(" gate --dir ", out)
        self.assertIn("--status blocked", out)

    def test_state_json_tool_paths_are_never_executed(self):
        # 저장소에 들어 있는 조작된 state.json이 실행 파일을 가리켜도 실행하지 않는다(2026-10-16 보안 검토)
        evil = self.root / "evil_goals.py"
        evil.write_text("import os\nopen(os.path.join(os.getcwd(), 'evil-ran'), 'w').write('x')\n")
        st = json.loads((self.w / "state.json").read_text())
        st["tools"]["goals"] = str(evil)
        write(self.w / "state.json", st)
        TOOL_ENV.pop("DLOOP_TOOL_GOALS", None)   # 실행하는 사람이 덮어쓰지 않은 상태
        self.lock()
        self.all_pass_round(0)
        run("gate", "--dir", self.w, "--id", "G004")
        self.assertFalse((self.w / "evil-ran").exists())

    def test_gate_closes_the_goal_only_after_check_passes(self):
        fake = self.root / "fake_goals.py"
        fake.write_text("import json, os, sys\nopen(os.path.join(os.getcwd(), 'goals-called.json'), 'w').write(json.dumps(sys.argv[1:]))\nprint('checkpoint recorded')\n")
        self.set_tools(goals=str(fake))
        self.lock()
        p = run("gate", "--dir", self.w, "--id", "G004")
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse((self.w / "goals-called.json").exists())
        self.all_pass_round(0)
        p = run("gate", "--dir", self.w, "--id", "G004", check=0)
        args = json.loads((self.w / "goals-called.json").read_text())
        self.assertEqual(args[:5], ["checkpoint", "--id", "G004", "--status", "complete"])
        self.assertIn("all locked criteria passed", args[args.index("--verify-evidence") + 1])
        self.assertIn(" check --dir ", args[args.index("--verify-cmd") + 1])

    def test_answer_key_with_detection_suffix_resolves(self):
        q = next(x for x in json.loads(run("questions", "--dir", self.w, "--set", "scope", check=0).stdout)["questions"] if x["header"] == "리서치")
        a = {"answers": {"대상 범위": "대표 페이지 1개", "변경 깊이": "다듬기", q["question"]: "새로 5곳", "기준 설정": "묶음으로 한 번에",
                         "기준 묶음": "기본(출시 최소)", "경쟁 우위": "근접", "판정 엄격도": "가볍게", "반복 한도": "3회", "goal 방식": "goal 없이"},
             "targets": {"urls": [URL]}}
        write(self.w / "a.json", a)
        run("compile", "--dir", self.w, "--answers", self.w / "a.json", check=0)


class Guard(Base):
    def test_detector_config_change_needs_approved_exception(self):
        self.lock()
        self.audit_round(0)
        self.assertNotIn("guard.", run("check", "--dir", self.w).stdout)
        for name in ("config.json", "design.json"):
            cfg = self.root / ".impeccable" / name
            cfg.parent.mkdir(exist_ok=True)
            cfg.write_text('{"x": 1}')
        out = run("check", "--dir", self.w).stdout
        self.assertIn("guard..impeccable/config.json", out)
        self.assertIn("guard..impeccable/design.json", out)
        ev = str(self.evidence())
        write(self.w / "exceptions.json", [{"kind": "config", "file": ".impeccable/config.json", "reason": "오탐 규칙 끔", "evidence": ev},
                                            {"kind": "config", "file": ".impeccable/design.json", "reason": "브랜드 글꼴 선언", "evidence": ev,
                                             "approval": "사용자: 브랜드 글꼴은 Pretendard"}])
        out = run("check", "--dir", self.w).stdout
        self.assertIn("guard..impeccable/config.json", out)        # 승인 원문이 없으면 예외로 치지 않는다
        self.assertNotIn("guard..impeccable/design.json", out)
        self.assertIn("예외 1개 적용: 설정:.impeccable/design.json", out)

    def test_inline_markers_do_not_matter_because_measures_ignore_them(self):
        self.lock()
        self.audit_round(0)
        src = self.root / "src"
        src.mkdir()
        (src / "a.css").write_text("/* impeccable-disable low-contrast */\n")
        self.assertNotIn("guard.", run("check", "--dir", self.w).stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
