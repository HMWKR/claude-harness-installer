#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sanitize-korean.py — PreToolUse 가드 로직.
손상 한국어 토큰이 포함된 Write/Edit/MultiEdit/git commit 을 차단한다.

손상 시그니처 (2026-05-27 인코딩 사고 기반, 정책: ~/.claude/rules/safety.md):
  - '영'(U+C601) 4회+ 연속  ← BLOCK 임계값.
      safety.md 원문은 '2회+'지만 "영영/영영히"는 정상 한국어 단어라
      블로킹 가드에서 2회는 오탐(정상 작업 차단)을 유발한다.
      사고 시 '영'은 긴 런으로 붕괴되므로 4회+ 로 상향해도 탐지에 충분하다.
  - U+FFFD('�') 1회+  ← 치환 문자는 정상 텍스트에 절대 없으므로 단일 출현도 손상.
      (적대적 검증: 정상 글자 사이 흩어진 단일 '�'는 'run 2회+'로는 미탐 → 임계값 1)
  - '□'(U+25A1) 3회+ 연속

설계 원칙: FAIL-OPEN. 입력 파싱 실패·예외·인코딩 문제 시 항상 허용({})하여
정상 작업을 절대 막지 않는다. (놓친 손상은 SessionStart 경고 가드가 2차로 잡는다.)

CC PreToolUse 훅 프로토콜:
  stdin  = JSON {"tool_name": "...", "tool_input": {...}}
  stdout = 차단 시 {"decision":"block","reason":"..."} / 허용 시 {}
  exit   = 항상 0
"""
import sys
import json
import re

ALLOW = "{}"

# 손상 시그니처 (임계값은 위 docstring 근거)
YOUNG_MIN = 4    # '영' 연속 차단 임계값
FFFD_MIN = 1     # '�' 차단 임계값 (단일 출현도 손상 — 정상 텍스트에 없음)
SQUARE_MIN = 3   # '□' 연속 차단 임계값

RE_YOUNG = re.compile("영{%d,}" % YOUNG_MIN)
RE_FFFD = re.compile("�{%d,}" % FFFD_MIN)
RE_SQUARE = re.compile("□{%d,}" % SQUARE_MIN)


def detect(text):
    """손상 시그니처 발견 시 사유 문자열, 없으면 None."""
    if not text:
        return None
    if RE_YOUNG.search(text):
        return "한글 손상 토큰('영' %d회+ 연속)" % YOUNG_MIN
    if RE_FFFD.search(text):
        return "치환 문자(U+FFFD '�')"
    if RE_SQUARE.search(text):
        return "깨진 문자('□') %d회+ 연속" % SQUARE_MIN
    return None


def extract_text(tool_name, tool_input):
    """도구별로 '실제 기록될 텍스트'만 추출한다."""
    if tool_name == "Write":
        return tool_input.get("content", "") or ""
    if tool_name == "Edit":
        return tool_input.get("new_string", "") or ""
    if tool_name == "MultiEdit":
        parts = []
        for e in tool_input.get("edits", []) or []:
            if isinstance(e, dict):
                parts.append(e.get("new_string", "") or "")
        return "\n".join(parts)
    if tool_name == "Bash":
        cmd = tool_input.get("command", "") or ""
        # git commit 에 한정 — 비-git Bash 명령은 즉시 허용해 잠금 위험을 최소화한다.
        return cmd if "git commit" in cmd else ""
    return ""


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    raw = sys.stdin.read()
    if not raw or not raw.strip():
        print(ALLOW)
        return

    data = json.loads(raw)
    tool_name = data.get("tool_name", "") or ""
    tool_input = data.get("tool_input", {}) or {}
    if not isinstance(tool_input, dict):
        print(ALLOW)
        return

    text = extract_text(tool_name, tool_input)
    reason = detect(text)
    if reason:
        out = {
            "decision": "block",
            "reason": (
                "[sanitize-korean] %s 감지 — 손상 텍스트의 Write/Edit/commit을 차단했습니다. "
                "정상 한국어로 복구한 뒤 다시 시도하세요. "
                "(정책: ~/.claude/rules/safety.md / 임계값 조정: ~/.claude/scripts/sanitize-korean.py)"
                % reason
            ),
        }
        print(json.dumps(out, ensure_ascii=False))
    else:
        print(ALLOW)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # FAIL-OPEN: 어떤 예외에서도 작업을 막지 않는다.
        print(ALLOW)
