---
name: warn-dangerous-rm
enabled: true
event: bash
pattern: rm\s+(-rf|-fr|--recursive\s+--force)
---

# ⚠️ 위험한 rm 명령어 감지

**주의**: `rm -rf` 또는 유사한 파괴적 명령어가 감지되었습니다.

## 확인 사항

1. **대상 경로가 정확한가요?**
   - 실수로 상위 디렉토리를 삭제하지 않는지 확인
   - 와일드카드(`*`)가 의도한 범위인지 확인

2. **백업이 있나요?**
   - Git에 커밋되지 않은 변경사항이 있는지 확인
   - 중요한 데이터가 포함되어 있지 않은지 확인

3. **대안을 고려했나요?**
   - `rm -i` (대화형 삭제)로 먼저 테스트
   - 휴지통으로 이동하는 방법 고려

## 안전한 대안

```bash
# 대화형 삭제 (각 파일 확인)
rm -ri directory/

# 먼저 내용 확인
ls -la directory/

# Git tracked 파일만 삭제
git clean -fd
```

> **Deep Analysis Mode 원칙**: 파괴적 변경은 반드시 사용자 승인 후 진행
