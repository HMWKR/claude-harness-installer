# 교차벤더 라우팅 — codex MCP

> 구 image-codex-routing.md의 승계·확장 (2026-08-09). 이미지 = codex(2026-09-28 grok에서 전환), 영상 = Remotion(2026-09-30) + 생성형은 fal.ai·Blender(2026-10-22), grok은 2026-10-02 퇴역(구독 해지 — `disabled/README.md`). 검증·심판 좌석도 규정한다.

## 라우팅 표

| 작업 유형 | 벤더·경로 | 비고 |
|---|---|---|
| 벡터/코드형 이미지 (로고·아이콘·SVG·다이어그램) | codex — `mcp__codex__codex` | codex는 벡터·코드 자산에 강함 |
| 래스터/사진형 이미지 (히어로·일러스트·목업 사진) | codex — `mcp__codex__codex`(내장 `image_gen__imagegen`) | **2026-09-28 사용자 지시로 grok에서 전환.** 실측: 1254×1254 PNG(~2MB), 원본은 `~/.codex/generated_images/<threadId>/`에 남고 지시하면 cwd로 복사. 호출 규약·후처리는 아래 "이미지 생성 호출" |
| 코드형 영상 (모션그래픽·타이틀·제품 데모·데이터/지도 애니메이션·자막·여러 소재 조립·대량 변형) | 로컬 — Remotion(`remotion-best-practices` 스킬) | **2026-09-30 사용자 지시.** 벤더 호출이 아니라 로컬 렌더. 권유 기준·운용 규칙은 영상 신호 때 라우터가 주입하고, 근거·한계는 design-toolchain 스킬 §5 |
| 참고 녹화(mp4·mov·gif) → 웹 페이지 안 모션 | 로컬 — motiscope(`motiscope-analyze`) 위주, 정교함이 필요하면 Remotion 매개변수 렌더로 원본과 프레임 대조 | **2026-10-16 사용자 지시·실측**: 단독 188px → 프레임 판독 107px → Remotion 루프 10px. 결과물은 CSS·JS 코드(영상으로 박지 않음). 정본 design-toolchain `references/remotion-vs-motiscope.md` |
| 생성형 영상 클립(AI 영상) | fal.ai(image-to-video, 예: `fal-ai/kling-video/v3/pro/image-to-video`) + Blender 기준 프레임 | **2026-10-22 사용자 지시.** Blender로 시작·끝 프레임을 렌더해 넣으면 색·구도를 통제한다. 영상화 전 Blender 장면을 사용자에게 검사받고, 비용 상한은 사용자가 정한다. 키는 출력·커밋 금지. 후처리는 Remotion·ffmpeg |
| 코드 검증·적대 검수·판정단 이종석 | codex — `mcp__codex__codex` + **`sandbox: "read-only"` 명시 필수** | sandbox 무명시 호출은 **훅이 차단**(codex-sandbox-guard, 2026-08-09 집행 승격). 2026-09-30부터 `danger-full-access`·`config`의 sandbox 키, `workspace-write`의 넓은 cwd(없음·상대·홈과 그 상위·홈 바로 아래·홈의 숨김 폴더·`~/Library`·소스 루트, 대소문자 무관)도 차단. 2026-10-02부터 Bash의 `codex exec`도 같은 규칙(workspace-write는 `--cd` 필수, `--add-dir`도 검사) — **실수 방지 장치이지 보안 경계가 아니다**(스크립트 파일 경유 등 의도적 우회는 못 막음) |
| **코드 리뷰 2차 의견**(아키텍처 결정·2회 수정 실패 후 근본원인·보안·알고리즘 엣지케이스·적대적 계획 검토) | codex — `mcp__codex__codex`(sandbox:"read-only") | 트리거는 `cross-vendor` 스킬. `/codex:review`는 disable-model-invocation이라 모델 자동발동 불가 → 스킬이 MCP 직접 호출로 우회 |

## 동원 매트릭스 — 작업유형 × 실행경로 (2026-08-09)

"소형 단발"의 정의: 프롬프트 수 KB 이하·단일 라운드·수십 초 내 반환(read-only 검증/핑 수준). 아래 ✅는 실측한 셀만이며, `[미검증]`은 능력 부재가 아니라 이 세션에서 카나리를 돌리지 않았다는 뜻(일반화 금지 — 필요 시 개별 카나리 후 승격).

| 실행 경로 | codex MCP | 실측 근거 |
|---|:---:|---|
| main 직접 | ✅ | 다회 실호출(codexGate·이미지 회수). MCP 서버 토큰이 낡으면 `codex exec -s read-only` CLI가 등가 경로(2026-10-02 실측) |
| 서브에이전트(Agent) | [미검증] | codex 셀은 미시험 |
| 워크플로 에이전트 | ✅ 소형 | wf-codex-probe: read-only 26초 stall無 [검증됨] |
| 팀메이트(Agent teams) | 리드에 요청 | 공식: 팀메이트는 백그라운드 서브에이전트 스폰·중첩 팀 불가 → 게이트는 리드가 수행 |

## 호출 규율

- **결정적 교차벤더 게이트는 main 직접**(규범 유지): CLAUDE.md·agent-teams-boundaries·conductor-verify 전반의 "main 직접" 원칙을 그대로 둔다. 위 매트릭스의 소형 단발 성공은 **능력 확인**이지 규범 완화가 아니다 — 서브에이전트/워크플로 내부의 소형 검증 호출은 실측상 동작하나, 장시간·다중 라운드·대형 diff·최종 판정은 반드시 main이 수행한다(구 2026-07-07 stall 사례가 그 유형). 미검증 셀을 운영에서 쓰려면 먼저 개별 카나리로 승격한다.
- **팀메이트 경로**: 팀메이트는 교차벤더를 직접 부르지 말고 **리드(main)에 게이트를 요청**한다(공식 구조 제약 — 팀메이트는 백그라운드 서브에이전트 스폰 불가). 브리프에 이 프로토콜을 명시한다.
- **회수**: 워커/벤더는 외부에 직접 쓰지 않는다 — 산출물(SVG 코드·이미지 파일·검토 텍스트)은 오케스트레이터가 회수해 반영한다([[agent-teams-boundaries]] 정합).
- **승인**: 디자인 작업에 필요한 이미지 생성은 codex로 바로 진행한다(2026-09-28 사용자 지시) — 생성 전 장수·용도를 1줄 고지한다. 한 작업에서 5장을 넘는 이미지 생성은 별도 승인 대상(텍스트 위임·검증은 상시 허용). 이 조항이 agent-teams-boundaries §5.0 "외부·유료 모델 호출은 별도 승인"의 예외 목록이다 — 여기 적힌 상시 허용만 승인 없이 진행하고, 그 밖의 외부·유료 호출은 §5.0대로 승인받는다.

## 이미지 생성 호출 (codex, 2026-09-28 실측)

1. **호출**: `mcp__codex__codex` + `sandbox: "workspace-write"` + `cwd`는 **산출 전용 폴더**(예: `<프로젝트>/assets/generated/`) — workspace-write는 cwd 하위 전체에 쓰기 권한을 주므로 소스 루트를 cwd로 주지 않는다(가드가 넓은 cwd를 차단 — 저장소 루트에 구현을 맡기는 workspace-write 호출도 막히니 하위 폴더를 cwd로 준다). `approval-policy: "never"`.
2. **프롬프트**: "내장 이미지 생성 도구로 생성(코드·SVG로 그리기 금지) → `./<이름>.png`로 복사 → `file`/`sips`로 크기 보고, 불가하면 대체 생성 없이 불가라고 답하라"를 명시한다. 원하는 비율·장면·조명·팔레트를 design-brief.md에서 가져온다.
3. **회수 검증**: codex 보고를 믿지 않고 main이 `file`·`sips -g pixelWidth -g pixelHeight`로 확인하고 이미지를 직접 열어 본다.
4. **후처리·배치**: 규칙은 rules/ui-ux-craft.md "이미지 자산" — 표시 크기로 줄여 WebP/AVIF 변환, `width`/`height` 명시, AI 사진 티 점검.
5. **출처 기록**: 이미지 옆 `<이름>.prompt.md`에 프롬프트·codex threadId·생성일을 남긴다(재생성·교체·고지용). `~/.codex/generated_images/`의 원본은 자동 삭제하지 않는다(safety.md 무인 삭제 금지).
