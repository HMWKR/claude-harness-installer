#!/usr/bin/env python3
"""py-percent 형식(.py) → Jupyter 노트북(.ipynb) 변환기.

셀 구분 규칙:
  # %% [markdown]   → 마크다운 셀 시작 (이후 줄들의 선행 '# ' 제거)
  # %%              → 코드 셀 시작
파일 시작부터 첫 마커 전까지 내용이 있으면 코드 셀로 취급.
"""
import json
import sys
from pathlib import Path


def convert(src_path: str, dst_path: str) -> int:
    lines = Path(src_path).read_text(encoding="utf-8").splitlines()
    cells = []
    cur_type = None  # 'markdown' | 'code' | None
    cur_lines = []

    def flush():
        nonlocal cur_lines, cur_type
        if cur_type is None:
            cur_lines = []
            return
        # 앞뒤 빈 줄 제거
        while cur_lines and not cur_lines[0].strip():
            cur_lines.pop(0)
        while cur_lines and not cur_lines[-1].strip():
            cur_lines.pop()
        if not cur_lines:
            cur_lines = []
            return
        source = [l + "\n" for l in cur_lines[:-1]] + [cur_lines[-1]]
        if cur_type == "markdown":
            cells.append({"cell_type": "markdown", "metadata": {}, "source": source})
        else:
            cells.append({
                "cell_type": "code", "metadata": {}, "source": source,
                "outputs": [], "execution_count": None,
            })
        cur_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# %%") or stripped.startswith("#%%"):
            flush()
            cur_type = "markdown" if "[markdown]" in stripped else "code"
            continue
        if cur_type == "markdown":
            # 마크다운 줄은 '# ' 접두를 벗긴다 ('#' 단독 줄은 빈 줄)
            if line.startswith("# "):
                cur_lines.append(line[2:])
            elif stripped == "#":
                cur_lines.append("")
            else:
                cur_lines.append(line)
        else:
            if cur_type is None:
                if not stripped:
                    continue
                cur_type = "code"
            cur_lines.append(line)
    flush()

    nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "language_info": {"name": "python"},
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        },
        "cells": cells,
    }
    Path(dst_path).write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(cells)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: py2ipynb.py <src.py> <dst.ipynb>")
        sys.exit(1)
    n = convert(sys.argv[1], sys.argv[2])
    print(f"{sys.argv[2]}: {n} cells")
