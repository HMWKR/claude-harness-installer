#!/usr/bin/env python3
"""capture.js·measure.js의 자리표시자를 한 번에 치환해 aside repl에 넘길 JS를 출력한다.

run-qa.sh와 clone-site capture-contract §8이 함께 쓰는 단일 정본이다 — 두 곳에 치환 코드를 복제했다가
measure.js에 `__COMBO__`가 추가됐을 때 한쪽만 고쳐져 측정이 조용히 실패했다(2026-09-30 감사 통합 회귀).

사용: render.py <capture.js|measure.js> <URL> <조합 JSON>
  - URL은 JSON 문자열 리터럴로, `/*__FORCE_THEME__*/`는 같은 폴더 theme.js 원문으로, `__COMBO__`는 그대로 넣는다.
  - 정규식 한 번으로 치환해 넣은 값을 다시 훑지 않는다 — URL 안의 자리표시자 문자열이 코드로 바뀌지 않는다(감사 #9·#28).
  - measure.js 조합: '{"vitals":true}' 또는 '{"theme":"dark","width":375}'(width null = 창 크기)
  - capture.js 조합: '["dark",375,812]'
"""
import json
import os
import re
import sys

if len(sys.argv) != 4:
    sys.exit(__doc__)
src = open(sys.argv[1], encoding="utf-8").read()
theme = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "theme.js"), encoding="utf-8").read()
json.loads(sys.argv[3])  # 조합이 JSON이 아니면 여기서 실패한다(코드 주입 방지)
val = {"__URL__": json.dumps(sys.argv[2]), "/*__FORCE_THEME__*/": theme, "__COMBO__": sys.argv[3]}
print(re.sub(r"__URL__|/\*__FORCE_THEME__\*/|__COMBO__", lambda m: val[m.group(0)], src))
