---
name: warn-unattended-delete
enabled: true
event: bash
pattern: find\s+[^|;]*-delete|find\s+[^|;]*-exec\s+rm
---

# ⚠️ 시간·조건 기준 일괄 삭제 감지

`find ... -delete` 또는 `find ... -exec rm` 이 감지되었습니다. **이 패턴이 실제로
사고를 냈습니다** — `claude-gc.sh`가 `plugins/cache`를 "MCP 캐시"로 오인해 활성
플러그인 페이로드 3,427파일을 9일간 지웠고, 그 사실은 11일 뒤에야 발견됐습니다.

## 확인 사항

1. **대상 경로가 정말 캐시·임시물인가?**
   먼저 `-delete` 를 빼고 돌려 목록을 눈으로 본다. 삭제 대상 개수를 센다.
2. **`-mtime` 기준이 "미사용"을 뜻하는가?**
   설치 시점이 오래된 활성 자산은 mtime이 낡았어도 살아 있는 자산이다.
   접근 시간(`-atime`)도 신뢰할 수 없다(noatime 마운트).
3. **되돌릴 수 있는가?**
   git 추적 밖이거나 재설치 경로가 없으면 삭제하지 않는다.

## 안전한 대안

```bash
# 1) 항상 먼저: 목록만 본다
find <path> -mtime +9 -print | tee /tmp/to-delete.txt | wc -l

# 2) 되돌릴 수 있게: 지우지 말고 옮긴다
mkdir -p /tmp/quarantine && \
  find <path> -mtime +9 -exec mv {} /tmp/quarantine/ \;

# 3) 자동화라면: 기본값을 dry-run 으로, --force 를 명시 인자로 분리
```

> `rules/safety.md` **무인 삭제 자동화 금지** 조항의 발화 지점.
> 훅에서 도는 스크립트에 시간 기준 일괄 삭제를 넣지 않는다.
