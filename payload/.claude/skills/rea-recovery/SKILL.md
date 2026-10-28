---
name: rea-recovery
description: REA MCP(mcp__rea__*) 분석이 resource·reported_limits·provider_timeout·클라이언트 시간 초과·출력 절단으로 실패하거나 부분 Evidence만 남았을 때, 그리고 큰 JS 번들·Electron·HAR을 REA로 분석하기 전에 범위·예산을 잡을 때 읽는 복구 순서. Use when REA 분석 실패, 힙 부족, max_heap_mb, analysis_timeout_ms, partial_observation, "REA 다시 돌려", 번들 분석 범위 설정. NOT for 일반 소스 저장소 구조 분석(REA 불필요), 웹 탐색·크롤·UI 검증(aside 전용).
---

# REA 분석·자원 제한 복구

착수 전 `~/.claude/skills/reverse-engineer-anything/SKILL.md`를 읽고, `references/`는 아래 단계가 가리키는 파일만 그때 읽는다(JS·Electron은 `javascript-applications.md`, 연결 문제는 `connection-and-recovery.md`, Evidence 이동은 `evidence-workflows.md`). 설치 버전의 도움말과 현재 세션 MCP 스키마가 이 문서보다 우선한다 — 아래 필드는 스키마가 지원할 때만 쓴다.

대상(URL/경로·버전/해시)과 질문을 먼저 정하고 같은 대상의 기존 Evidence를 재사용한다. 도구 부재·실패 시에만 `connection-and-recovery.md`를 읽는다. JS/HAR 때문에 네이티브 엔진을 일괄 설치하지 않는다.

브라우저·Electron 런타임 관찰은 REA 스킬의 `references/runtime-observation.md` 절차를 그대로 따른다(rigor §1 예외 ③). REA 도구로 안 될 때만 Aside로 넘어가되 분석 대상 웹사이트 한 곳에 한정한다(rules/uncompromising-rigor.md §1-b 레시피). 일반 웹 탐색·UI 검증은 여전히 Aside다.

## 복구 순서

1. `resource`·`reported_limits`·`limitations`·`unknowns`·부분 Evidence로 원인을 구분한다: 분석기 힙 / 부모 누적 결과 / 의미 분석량 / REA 시간 초과 / 클라이언트 시간 초과 / 출력 절단.
2. 프레임워크 식별만 필요하면 manifest·소스 맵·HTML 등 이미 확보한 근거부터 쓴다. 내부 동작 추적에 필요한 번들만 추가 분석한다.
3. `source_paths`에 inventory의 정확한 파일과 관련 manifest·소스 맵을 명시한다(의존성은 자동 포함되지 않는다). 기존 chunk 단위로 나누고 제외 관계는 미확인으로 남긴다. 빈 배열을 전체 선택으로 쓰거나 JS를 임의 바이트로 자르지 않는다.
4. 분석기 힙 부족일 때만 `max_heap_mb`를 검토한다. 기본값(CLI 6.7.0 `--help` 기준 1024 MiB)은 격리 분석기의 V8 old-space이며 총 RSS나 MCP 본체 한도가 아니다. Bun 호스트 REA는 이 값을 강제하지 않는다(Windows만 커밋 메모리를 값+512 MiB로 제한). 현재 버전과 호스트 여유를 확인하고 좁힌 범위에서 단계적으로 올린다 — 전역 무제한·동시 대형 분석은 피한다.
5. 부모 결과·의미 분석량 제한은 범위 분할 또는 `max_semantic_nodes` 등 예산 축소(CLI 도움말·서버 스키마에만 있고 스킬 문서엔 없음)로 대응하고 줄어든 coverage를 기록한다. 힙 증설만으로 부모 제한이 해결된다고 주장하지 않는다.
6. `provider_timeout`은 범위와 `analysis_timeout_ms`를 검토한다. 기본값(CLI 6.7.0 기준 300000 ms)은 파일별 예산이며 전체 작업 시간이 아니다. 클라이언트 제한은 설치 버전의 지원 설정을 따로 확인한다 — Codex의 `tool_timeout_sec`를 복사하지 않는다.
7. 클라이언트 시간 초과만으로 서버 종료를 가정하지 않는다. 기존 작업·Evidence·정리 상태를 확인한 뒤 재시도한다(rules/loop-prevention.md: 변경점 없는 재실행 금지).
8. `detail: "summary"`는 전달량을 줄일 뿐 분석 메모리 부족의 해결책이 아니다. 출력 절단이면 실제 `parent_evidence_id`·`node_id`로 작은 view/페이지를 읽거나 export한다. `error.details.partial_observation`은 같은 연결의 `inspect_analysis_view`로 조회한다. ID를 지어내지 않는다.
9. 세션 이동 전 export하고 import 또는 완전한 inline Evidence를 쓴다. 연결에 종속된 retained ID만 넘기지 않는다.
10. Wakaru 복원은 Linux x64·지정 엔진 요구를 확인한다 — macOS ARM64의 기본 복구 수단이 아니다. 원인·범위·예산 변화 없이 반복하지 않으며 해결되지 않은 부분은 partial/unresolved로 보고한다.

## 결과 보고

관측·추론·미확인을 분리하고 대상, 도구 버전, Evidence 저장 위치, 분석 범위, 제외 파일, 실패 원인·다음 대안을 적는다. 부분 결과에서 찾지 못한 것을 부재로 단정하지 않는다. 작은 fixture 성공을 대형 번들 메모리 문제 해결로 일반화하지 않는다. 구현이 따르면 rules/live-feature-verify.md를 따른다.
