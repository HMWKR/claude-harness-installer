#!/bin/bash
# adapter-inject.sh — UserPromptSubmit 훅 (L0 모델 어댑터, 청사진 v2 N1)
# transcript JSONL의 마지막 assistant 메시지 model 필드로 현재 모델을 감지해
# ~/.claude/adapters/<profile>.md 를 additionalContext로 주입한다.
# 직전 주입과 같은 프로파일이면 침묵(중복 주입 방지). 모든 오류는 fail-open(exit 0).
# stdin: JSON { transcript_path, ... }
set +e
input=$(cat)
ADAPTER_STDIN="$input" python3 - "$HOME/.claude/adapters" <<'PY'
import sys, json, os, hashlib

adapters_dir = sys.argv[1]
try:
    data = json.loads(os.environ.get('ADAPTER_STDIN', '') or '{}')
except Exception:
    sys.exit(0)

tpath = data.get('transcript_path', '') or ''
mfile = os.path.join(os.path.expanduser('~/.claude/state'),
                     'session-model-' + hashlib.sha256(tpath.encode()).hexdigest()[:16])

# SessionStart: 세션 모델을 기록만 한다(주입은 UserPromptSubmit 한 곳). model 필드는 SessionStart 입력에만
# 온다(공식 문서, 생략될 수 있음). 첫 프롬프트에는 transcript에 assistant 메시지가 없으므로 이 기록이 1차
# 폴백이다 — 2026-09-30 settings.json에서 model 키가 사라져 settings 폴백이 _default로 떨어졌다(감사 누락 #3).
if data.get('hook_event_name') == 'SessionStart':
    m = str(data.get('model') or '')
    if m:
        try:
            os.makedirs(os.path.dirname(mfile), exist_ok=True)
            with open(mfile, 'w') as f:
                f.write(m)
        except Exception:
            pass
    if data.get('source') in ('compact', 'clear'):
        # 요약·초기화로 프로파일이 컨텍스트에서 사라졌다 — 중복 방지 기록을 지워 다음 프롬프트에 다시 주입한다(2026-10-02)
        try:
            os.remove(os.path.join(os.path.expanduser('~/.claude/state'),
                                   'adapter-' + hashlib.sha256(tpath.encode()).hexdigest()[:16]))
        except OSError:
            pass
    sys.exit(0)

def _detect(lines):
    found = ''
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = obj.get('message', obj) if isinstance(obj, dict) else {}
        if obj.get('type') == 'assistant' or (isinstance(msg, dict) and msg.get('role') == 'assistant'):
            m = (msg.get('model') if isinstance(msg, dict) else '') or obj.get('model') or ''
            # API 오류 가짜 항목(<synthetic>)은 실모델이 아니므로 건너뜀 (2026-07-03 실동작 감사 발견)
            if m and 'synthetic' not in m.lower():
                found = m
    return found

def _tail_lines(path, tail_bytes=1000000):
    # 성능(H3, 2026-07-06): 매 프롬프트마다 전체 transcript를 읽지 않고 끝부분만 읽는다.
    # 마지막 assistant 메시지는 파일 끝에 있으므로 tail로 충분. 잘린 첫 줄은 버린다.
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

model = ''
try:
    model = _detect(_tail_lines(tpath))
    if not model:  # tail 미검출(초대형 마지막 메시지 등) → 전체 스캔 폴백(동작 동일성 보장)
        with open(tpath) as f:
            model = _detect(f)
except Exception:
    pass

if not model:  # 1차 폴백: SessionStart가 기록한 이 세션의 모델
    try:
        with open(mfile) as f:
            model = f.read().strip()
    except Exception:
        pass

if not model:
    # 2차 폴백(2026-08-09): 세션 첫 프롬프트에는 transcript에 assistant 메시지가
    # 없어 미검출 → _default(고처방)로 떨어졌다(실측 state 31%가 이 경로).
    # 세션 기본 모델은 settings의 model 필드가 알므로 그것을 쓴다. 런타임
    # 오버라이드 세션은 두 번째 프롬프트부터 transcript 검출이 우선한다.
    try:
        with open(os.path.expanduser('~/.claude/settings.json')) as f:
            model = str(json.load(f).get('model', '') or '')
    except Exception:
        pass

ml = model.lower()
if 'fable' in ml or 'mythos' in ml:
    prof = 'fable'
elif 'opus' in ml:
    prof = 'opus'
elif 'sonnet' in ml:
    prof = 'sonnet'
else:
    prof = '_default'  # 미검출·haiku·미지 모델 → 안전 기본값(고처방)

# transcript 단위 중복 주입 방지
state_dir = os.path.expanduser('~/.claude/state')
try:
    os.makedirs(state_dir, exist_ok=True)
except Exception:
    sys.exit(0)
key = hashlib.sha256(tpath.encode()).hexdigest()[:16]
sfile = os.path.join(state_dir, 'adapter-' + key)
prev = ''
try:
    with open(sfile) as f:
        prev = f.read().strip()
except Exception:
    pass
if prev == prof:
    sys.exit(0)

ppath = os.path.join(adapters_dir, prof + '.md')
try:
    with open(ppath) as f:
        content = f.read()
except Exception:
    sys.exit(0)
try:
    with open(sfile, 'w') as f:
        f.write(prof)
except Exception:
    pass

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": content
    }
}, ensure_ascii=False))
PY
exit 0
