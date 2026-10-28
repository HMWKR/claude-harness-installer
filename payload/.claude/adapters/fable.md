# [L0 어댑터] 모델 프로파일: Fable (저처방)

> adapter-inject 자동 주입 — 현재 세션 모델이 claude-fable-*/mythos-* 로 감지됨.

- **처방 수준: 저** — 목표·제약·완료 기준만 제시하고 방법 선택은 모델에 위임한다. 단계별 미세 지시를 추가하지 않는다(과처방은 품질 저하).
- **thinking**: 상시 on(모델 기본) — 추가 상향 요청 불필요. 서브에이전트는 effort로 태스크 난이도에 맞춰 지정.
- **L1 증폭 N (실질 pass-through)**: 설계 판정단 1–2 / 구현 best-of-1 / 리뷰 렌즈 3×반박자 2 / 디버그 경쟁 가설 3 / 모호성 해석 2.
- **분해 입도**: coarse — 긴 자율 턴 허용(maxTurnSpan: long). 불필요한 태스크 분절 금지.
- **검증 주권(원칙 4)**: DoD·verify-cmd는 verification-templates/ 템플릿 우선. 템플릿 밖 자기 저작 시 이종 검증자 1 이상 통과 후 verify-lock으로 해시 고정.
