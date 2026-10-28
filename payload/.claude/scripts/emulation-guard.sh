#!/bin/bash
# emulation-guard.sh — Stop 훅 (청사진 v2 N3, 비차단 관찰 모드)
# 한국어 약속-미이행("이제 ~하겠습니다"로 끝나고 실행 없음)을 감지해 사용자에게 systemMessage로만 알린다(대화를 이어가게 하지 않는다 — fablize 게이트 보존, 2026-10-02).
# 거버넌스: Stop "차단"(decision:block) 권위는 fablize gate_stop 1곳 — 이 훅은 block을 절대 쓰지 않는다.
# stop_hook_active(또는 이 훅의 자체 1회 가드) 시 침묵. 모든 오류 fail-open(exit 0).
set +e
input=$(cat)
EG_STDIN="$input" python3 - <<'PY'
import sys, json, os, re, hashlib

try:
    data = json.loads(os.environ.get('EG_STDIN', '') or '{}')
except Exception:
    sys.exit(0)

# 다른 Stop 훅이 이미 재관여시킨 턴이면 침묵 (루프 방지)
if data.get('stop_hook_active'):
    sys.exit(0)

tpath = data.get('transcript_path', '') or ''

def _tail_lines(path, tail_bytes=1000000):
    # 성능(H3, 2026-07-06): 전체 transcript 대신 끝부분만. 마지막 assistant 메시지는 파일 끝에 있다.
    with open(path, 'rb') as f:
        f.seek(0, 2)
        size = f.tell()
        start = size - tail_bytes if size > tail_bytes else 0
        f.seek(start)
        blob = f.read()
    if start > 0:
        nl = blob.find(b'\n')
        blob = blob[nl + 1:] if nl >= 0 else b''
    return blob.decode('utf-8', 'replace').splitlines()

last_text, last_had_tool = '', False
try:
    for line in _tail_lines(tpath):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = obj.get('message', obj) if isinstance(obj, dict) else {}
        if obj.get('type') == 'assistant' or (isinstance(msg, dict) and msg.get('role') == 'assistant'):
            content = msg.get('content', []) if isinstance(msg, dict) else []
            if isinstance(content, list):
                texts = [b.get('text', '') for b in content if isinstance(b, dict) and b.get('type') == 'text']
                tools = [b for b in content if isinstance(b, dict) and b.get('type') == 'tool_use']
                if texts or tools:
                    last_text = '\n'.join(texts).strip()
                    last_had_tool = bool(tools)
except Exception:
    sys.exit(0)

# 도구 호출로 끝났거나 텍스트가 없으면 정상
if last_had_tool or not last_text:
    sys.exit(0)

tail = last_text[-400:]

# 한국어 약속-미이행: 미래 의사 표명으로 끝남 (finish-the-work.sh의 한국어판)
promise = re.search(
    r'(이제|지금부터|다음으로|곧|바로)?\s*[가-힣A-Za-z0-9 ,·()\[\]/]*'
    r'(하겠습니다|진행하겠습니다|시작하겠습니다|작성하겠습니다|실행하겠습니다|만들겠습니다|해보겠습니다|진행합니다)\s*[.!]?\s*$',
    tail)

# 사용자에게 묻고 끝나는 정상 종료는 통과
asks = re.search(r'(\?|주세요|할까요|괜찮으시|선택해|여쭙|기다립니다|대기합니다|주시면)', tail)

if promise and not asks:
    # Stop의 additionalContext는 대화를 이어가게 하고, 이어진 턴의 다음 Stop에는 stop_hook_active=true가 들어와
    # fablize gate_stop(유일한 Stop 권위)이 검사를 건너뛴다 — 그래서 사용자 표시(systemMessage)만 낸다(2026-10-02 최종 검토)
    print(json.dumps({"systemMessage": "[emulation-guard 관찰] 직전 응답이 실행 없이 작업 의사 표명으로 끝났습니다 — 이어서 진행하라고 지시하거나 차단 사유를 확인하세요."}, ensure_ascii=False))
sys.exit(0)
PY
exit 0
