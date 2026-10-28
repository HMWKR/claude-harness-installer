---
name: warn-console-log
enabled: true
event: file
pattern: console\.(log|debug|info)\s*\(
---

# 💡 console.log 사용 감지

**참고**: 디버깅용 `console.log`가 감지되었습니다.

## 확인 사항

1. **의도적인 로깅인가요?**
   - 임시 디버깅용이라면 커밋 전 제거 필요
   - 영구 로깅이라면 적절한 로깅 라이브러리 고려

2. **프로덕션 코드인가요?**
   - 프로덕션에서는 `console.log` 대신 구조화된 로깅 권장
   - 민감한 정보가 출력되지 않는지 확인

## 권장 대안

```javascript
// 개발용 - 조건부 로깅
if (process.env.NODE_ENV === 'development') {
  console.log('Debug:', data);
}

// 프로덕션용 - 구조화된 로깅
logger.info('User action', { userId, action });
```

> **Deep Analysis Mode**: 코드 품질을 위해 디버깅 코드 정리를 권장합니다.
