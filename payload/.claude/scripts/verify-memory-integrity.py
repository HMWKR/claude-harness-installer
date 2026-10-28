#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify-memory-integrity.py — SessionStart 가드 로직.
메모리 파일을 스캔해 손상 한글 토큰을 발견하면 경고를 출력한다 (차단하지 않음).

경고 임계값 (WARN — 경고 전용이라 블로킹 가드보다 민감하게):
  - '영'(U+C601) 3회+ 연속  (정상어 "영영" 오탐 회피 위해 2가 아닌 3)
  - U+FFFD('�') 1회+  (치환 문자는 정상 텍스트에 없으므로 단일 출현도 손상)
  - '□'(U+25A1) 3회+ 연속
  - UTF-8 디코드 실패(바이트 손상) 그 자체

스캔 대상: ~/.claude/projects/*/memory/ 하위 모든 *.md
출력: 손상 발견 시 경고 텍스트(SessionStart context). 없으면 무출력. 항상 exit 0.
설계 원칙: FAIL-OPEN — 경고를 못 내도 세션을 막지 않는다.
정책: ~/.claude/rules/safety.md
"""
import os
import re
import glob

YOUNG_MIN = 3
FFFD_MIN = 1
SQUARE_MIN = 3

RE_YOUNG = re.compile("영{%d,}" % YOUNG_MIN)
RE_FFFD = re.compile("�{%d,}" % FFFD_MIN)
RE_SQUARE = re.compile("□{%d,}" % SQUARE_MIN)


def scan(path):
    """파일에서 손상 신호 목록을 반환. 정상이면 None."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except Exception:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ["UTF-8 디코드 실패(바이트 손상)"]
    hits = []
    if RE_YOUNG.search(text):
        hits.append("'영' %d회+ 연속" % YOUNG_MIN)
    if RE_FFFD.search(text):
        hits.append("U+FFFD('�') 출현")
    if RE_SQUARE.search(text):
        hits.append("'□' %d회+ 연속" % SQUARE_MIN)
    return hits or None


def main():
    try:
        import sys
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    home = os.path.expanduser("~")
    pattern = os.path.join(home, ".claude", "projects", "*", "memory", "**", "*.md")
    found = {}
    for p in glob.glob(pattern, recursive=True):
        hits = scan(p)
        if hits:
            found[p] = hits

    if found:
        print(
            "[verify-memory-integrity] ⚠ 손상 의심 메모리 발견 — 인용 시 "
            "'[손상 메모리 인용]'을 명시하고 복구 필요를 사용자에게 보고하세요 "
            "(정책: ~/.claude/rules/safety.md):"
        )
        for p in sorted(found.keys()):
            rel = p.replace(home, "~")
            print("  - %s : %s" % (rel, ", ".join(found[p])))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # FAIL-OPEN
