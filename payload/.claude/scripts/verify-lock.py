#!/usr/bin/env python3
"""verify-lock.py — 검증 자산 변조(tamper) 감지 도구 (청사진 v2 N5).

플랜 시점에 확정된 검증 자산(DoD·verify-cmd·테스트 파일)의 해시를 잠그고,
실행 중 변경을 감지한다. 변경 감지 시 exit 1 → 게이트 무효·재승인 신호.

사용:
  verify-lock.py lock  <lockfile.json> <file...>   # 파일 해시 기록
  verify-lock.py check <lockfile.json>             # 전 파일 재해시 대조
"""
import sys, json, hashlib, os


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    cmd, lock = sys.argv[1], sys.argv[2]
    if cmd == 'lock':
        files = sys.argv[3:]
        if not files:
            print('lock: 대상 파일이 없다')
            return 2
        data = {os.path.abspath(f): sha256(f) for f in files}
        with open(lock, 'w') as fp:
            json.dump(data, fp, indent=1, ensure_ascii=False)
        print(f'locked: {len(data)} files -> {lock}')
        return 0
    if cmd == 'check':
        with open(lock) as fp:
            data = json.load(fp)
        bad = []
        for f, h in data.items():
            try:
                cur = sha256(f)
            except FileNotFoundError:
                bad.append((f, 'MISSING'))
                continue
            if cur != h:
                bad.append((f, 'MODIFIED'))
        if bad:
            for f, why in bad:
                print(f'TAMPER {why}: {f}')
            return 1
        print(f'check OK: {len(data)} files unchanged')
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main())
