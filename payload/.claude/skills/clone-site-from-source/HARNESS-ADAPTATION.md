# 하네스 적응 기록 (2026-07-25)

## 출처

`~/Desktop/clone-site-from-source-skill-2026-07-25.zip` (33KB, 13항목)로 받았다.
원본 zip과 해시를 `.provenance/`에 보존했다 — 내 수정과 원문을 언제든 대조할 수 있다.

```
sha256  6b7a4744cf1c651ff80a16fdccae039ade480ce85011820a585e24c30711663c
```

**이 스킬은 OpenAI/Codex 환경에서 왔다.** 근거: `agents/openai.yaml`(Codex 에이전트 인터페이스
정의), `Codex Desktop` 프리뷰 참조, `.openai/hosting.json` 산출물, `@Sites` 공유 타깃,
`npm run test:sites` 테스트 타깃. 이 하네스에는 업스트림이 없으므로 `~/.claude/skills/`가
정본 위치이고, git 추적 대상이라 설치 즉시 백업된다(원격 `HMWKR/claude-harness`).

## 왜 그대로 넣지 않았는가

원문 SKILL.md는 동반 워크플로 4종을 **필수 선행**으로 요구하고, 20행이 "요구 워크플로나
브라우저 표면이 없으면 **중단하고 블로커 보고**"라고 규정한다. 실측 결과 4종 전부 부재다:

| 원문 요구 | 이 하네스 |
|---|---|
| `product-design:url-to-code` | **부재** |
| `browser:control-in-app-browser` | **부재** |
| `local-prototype-preflight` | **부재** |
| `design-qa` | **부재** |

그대로 설치하면 첫 줄에서 멈추는 스킬이 된다 — "선언은 있는데 실제로는 작동하지 않는 자산",
즉 이 하네스가 2026-07-25에 대대적으로 청산한 실패 클래스와 정확히 같다
(`disabled/README.md`의 채택 기준: ① 배선돼 발화하는가 ② **전제가 실존하는가**).

## 무엇을 바꿨는가 — 환경 결속 + 검증기 결함 수정

7개 비협상 게이트, 캡처/출력/경험문서 계약 3종, 00–21 문서 세트, 증거 라벨 체계는 전부
원문 그대로다. **단 검증기는 손댔다** — 초판에서 "검증기 통과 조건은 전부 원문 그대로"라고
썼는데 그게 틀렸다. 적대 감사가 그 서술이 만든 모순을 잡아냈고(아래 §검증기 수정), 계약서와
게이트를 한쪽으로 통일하는 쪽을 택했다.

| 위치 | 원문 | 변경 | 이유 |
|---|---|---|---|
| `SKILL.md` 동반 워크플로 | 4종 필수 선행 | Playwright MCP / `run` / `playwright-design-audit`+`accesslint:audit` / §Pipeline 자체 — **2026-09-28 폐기**: 브라우저는 aside, 접근성은 run-qa.sh axe(아래 2026-09-28~30 절) | 부재 의존을 실재 등가로 재결속 |
| `SKILL.md` 스크린샷 | 언급 없음 | `type`·`scale` **필수 인자** 명시 — **2026-09-28 폐기**(Playwright MCP 인자, 현행은 아래 절) | 2026-07-25 실측: 생략 시 호출 실패로 증거 0장. 이 스킬은 스크린샷이 핵심이라 치명적이었을 지점 |
| `SKILL.md` 핸드오프 | Codex Desktop 프리뷰 / `@Sites` 공유 제안 | 로컬 프리뷰 URL / 명시 요청 시에만 공유 | 해당 표면 부재 |
| `SKILL.md` §7 테스트 | `npm run test:sites` 무조건 | `package.json`에 실재할 때만, 없으면 대체 후 기록, 대체 대상 없으면 "부재" 명시 | 없는 명령의 통과를 주장하지 않기 위해 |
| `output-contract.md` 게이트 12 | `test:sites` 통과 필수 | 위와 동일하게 조건부 | 같은 이유 |
| `output-contract.md` 트리 | `.openai/hosting.json` 필수 | 필수 아님, 프레임워크 배포 설정으로 대체·미존재 시 기록 | Codex Sites 전용 산출물 |

추가한 것: 증거 라벨 매핑(`[확인]`↔`[검증됨]` 등), 인접 스킬 경계(`reference-match`는 정합
검사, 이 스킬은 전체 크롤+클론+문서화 — 겹치면 이 스킬이 상위).

`agents/openai.yaml`은 **삭제하지 않고 남겼다** — 출신 환경의 증거이고, 삭제는 이 하네스의
보존 원칙에 어긋난다.

## 이 하네스와 잘 맞는 지점

우연이 아니라 같은 규율을 공유한다:

- **증거 라벨 4종**이 `[검증됨]`/`[추정]`/`[미확인]` 규약과 거의 1:1이다.
- "추론을 반복으로 확정 사실로 바꾸지 말라", "비즈니스 성공과 인터페이스 품질을 분리하고
  근거 없는 인과를 주장하지 말라", "출처가 어긋나면 평균내지 말고 둘 다 보존하라" —
  `rules/uncompromising-rigor.md`·`rules/anti-hallucination.md`와 동일한 태도.
- "빌드 성공만으로는 시각 검증이 아니다"(§7) — `rules/live-feature-verify.md`의 code≠live 명제.
- **기계 검증기**(`validate_clone_artifacts.py`)가 완료 게이트라는 **구조**는 자기채점 금지
  원칙과 정합한다. 단 초판에서 이걸 "정합 확인"으로 쓴 것은 **과장이었다** — 아래 §남은
  구조적 한계 참조. 게이트는 파일 존재·문자열 포함·글자 수만 본다.
- 캡처 계약 §1이 쿠키·자격증명·개인 API 읽기와 접근통제 우회, 외부 쓰기를 금지한다 —
  `rules/safety.md` 정합.

## 검증기 수정 5건 (적대 감사 결과, 전부 실증 후 적용)

설치 후 `critic` 에이전트로 스크립트 4개(1,608줄)를 적대 감사했다. 보안 축은 깨끗했다 —
네트워크·서브프로세스·`eval`/`exec`·파일 삭제 API **0건**, 경로 탈출은 상대·절대·NFKC 전각
3종 공격 전부 `크롤링` 컨테이너 안으로 접혔다(sanitize + `resolve()` + `relative_to()` 삼중).
문제는 **게이트 신뢰성**이었다.

| # | 결함 | 수정 | 실증 |
|---|---|---|---|
| F2 | **내가 만든 모순(fatal)** — `output-contract.md`는 "`.openai/hosting.json` 생략 가능"인데 검증기 `:210`은 하드 요구. 탈출로가 "0바이트 빈 파일 위조"였고 그게 실제로 통과했다 | Codex Sites 산출물 3개를 `--require-openai-hosting` **옵트인**으로 내림. `package.json`은 JSON 파싱 검사 추가 | 기본 0건 / 옵트인 2건 위반 · 0바이트 `package.json` 반려 확인 |
| F5 | `"pending" in text.lower()`가 정상 문서의 `depending on viewport`·`Appending`을 미완성으로 오검출 | 단어 경계 `\bpending\b` | 8/8 케이스 통과(오탐 3종 미검출, 진짜 3종 탐지) |
| F6 | 핫링크 정규식이 `href`를 잡아 **보존해야 하는 푸터 법적 링크**를 반려. 통과시키려면 원문 링크를 지우는 역방향 수정을 유도 | `href` 분리, 자산은 `src`/`srcset`/`poster`/`url()`만 | 법적 앵커 0건 위반 · `<img src="https://cdn...">`는 탐지 |
| F3 | `--force`가 사람이 쓴 문서 22개를 **무음으로** 덮어썼다(백업·확인 전무). 이 스킬의 실작업량 대부분이 그 문서다 | 덮어쓰기 전 `.clone-backup-<UTC>/`로 전량 백업 + 건수 출력 | 24파일 백업 · 수기 내용 백업에 보존 확인 |
| F4 | 비원자적 — 문서 충돌이 `generate_docs()` 안에서 터져 `clone-source.json`·`design-qa.md`는 이미 써진 반쪽 상태가 남고, 벗어나는 길이 `--force`뿐이라 F3를 발동시켰다 | 문서 충돌 검사를 manifest 쓰기 **전으로** 이동 | 충돌 시 아무것도 쓰지 않고 반려 확인 |
| F7 | `//evil.example.net/x`가 "same-origin absolute pathname" 검사를 통과(원문은 `://` 부재만 확인) → 타 오리진 크롤 위험 | `route.startswith("//")` 차단 | 차단 확인, 정상 라우트 통과 |

## 남은 구조적 한계 — 사용자 결정 필요

**게이트는 형식 검사다.** 감사가 실증했다: 각 증거 디렉토리에 **1×1 투명 PNG 1장**, metrics는
`{}`, 문서 22개는 `"asdf "×400`에 필수 `##` 제목과 라벨만 나열, `design-qa.md`는 9개 단어 한 줄
+ `final result: passed` — 이 **순수 쓰레기 프로젝트가 검증기를 통과했다**
(`Clone artifact validation passed`).

게이트가 보지 않는 것: 이미지가 실제 스크린샷인지, `qa/metrics/*.json`에 측정값이 있는지,
문서가 관찰에 근거하는지, `dist/`가 실제 빌드 산출인지. 그리고 `design-qa.md` 마지막 줄에
`final result: passed`를 append하는 한 번이 QA 통과 선언 전권을 갖는다.

### 2026-07-27 — 내용 검사 5종 추가 (사용자 승인 후 적용)

위 한계를 실제로 메웠다. 설계 기준은 하나 — **정상 작업에서는 절대 걸리지 않고 위조에서는
반드시 걸리는 것만** 채택한다(오탐이 이 하네스의 1순위 안티골).

| 검사 | 막는 것 | 오탐 방지 설계 |
|---|---|---|
| 전체뷰 캡처 ≥320×320 (헤더 직접 파싱, PNG/JPEG/WebP) | 1×1 투명 PNG 위조 | 판별 불가 포맷은 **통과**시킨다. 부분 확대 크롭은 함께 있어도 무방(1장만 충족하면 됨) |
| metrics 키 개념 ≥3 (route/title/width/height) | `{}` 위조 | 키 **이름 패턴**만 보므로 명명 자유도 유지(`pathname`·`documentWidth` 등 매칭) |
| design-qa가 실존 증거 2개 이상 인용 | `final result: passed` 한 줄 단독 권한 | output-contract가 이미 "source/implementation 경로 기재"를 요구 — 정상 작업은 자연 충족 |
| `captured_at` ISO 파싱 + 미래 아님 | 위조 타임스탬프 | 신선도 상한은 **옵트인**(`--max-evidence-age-days`) |
| `authorization {basis, confirmed_by, robots_txt_checked}` | 권한 확인 없는 크롤 | `init_clone_run.py`가 CLI로 받아 생성 |

양방향 검증 7/7 통과 — 어제 게이트를 통과했던 쓰레기 프로젝트는 이제 반려되고, 정상 형태는
위반 0으로 통과한다. 각 검사를 하나씩만 위조한 케이스도 개별 반려를 확인했다.

### 2026-07-27 2차 — 적대 검증이 1차 하드닝을 뚫었다

3방향 적대 검증(critic 3 + 종합 1)의 판정은 **"신뢰 불가"**였다. 게이트가 *위조에 관대하고
정직한 변형에 가혹한*, 방향이 반대로 걸린 상태였다. 1차에서 넣은 5종 중 4종이 각각 단독으로
무너졌다. **가장 큰 구멍은 내가 "오탐 방지"라고 넣은 조기 반환이었다** —
`has_full_view_image()`가 판별 불가 이미지를 만나면 즉시 통과시켜서, **0바이트 `.png` 한 장이
그 디렉토리 검사 전체를 끄는 스위치**가 됐다(3개 각도가 독립 발견).

수정 방향을 하나로 통일했다: **값·구조는 조이고 표기·명명·경로 자유도는 넓힌다.**

| 수정 | 막은 위조 | 함께 없앤 오탐 |
|---|---|---|
| 판별 불가 → '증거 불충분'으로 반전 | 0바이트·텍스트·GIF개명·RIFF미지·IHDR껍데기 8종 | — |
| JPEG SOF 스트리밍 탐색(65536 창 폐기) | 70KB COM 패딩으로 SOF를 창 밖으로 밀기 | — |
| PNG IDAT 존재 확인 | 24바이트 헤더 껍데기 | — |
| metrics를 (키,값) 레코드 단위 검증 | `null`/`0`/빈dict/`{"urltitlewidthheight":0}` | 키 패턴 확대(`pathname`·`viewportW`·`page`) + 중첩 `viewport:{w,h}` |
| design-qa 인용을 실파일 역방향 매칭 | `qa/./source/x.png` 중복, metrics만 인용 | 대문자 `.PNG`·공백·`@2x`·괄호 파일명 |
| `captured_at` naive를 **로컬 타임존**으로 | — | **KST 상시 오탐**(9시간 미래로 반려) |
| 나이를 manifest가 아닌 `qa/` mtime에서 측정 | — | 오래 걸린 프로젝트가 오늘 재캡처해도 반려 |
| 문서 고유 어휘 하한(120/40) | `'ㅋ'×1400`·`'asdf'×400` | — |
| package.json 객체+name+build 스크립트 | `0`·`null` 스칼라 | — |
| `src/`·`app/`에 소스 파일 존재 | **사이트 없이 완료 선언** | — |
| 핫링크 라인 단위 + iframe·주석·프라그마 예외 | — | YouTube/지도 임베드, 원본 URL 대조 주석 |
| 마커를 줄머리 형태로 한정 + 인용·코드펜스 제외 | — | 원본 UI의 `"Pending"` 배지·`TODO` 라벨 인용 |
| `- [ ]`를 출시 체크리스트 절로 한정 | — | 원본 폼의 체크박스 재현 |
| `robots_txt_checked`를 **결과 열거형**으로 | — | robots 404인 자기 소유 사이트에서 거짓 신고를 학습시키던 구조 |
| robots_txt_url ↔ source_url 호스트 대조 / `qa/robots.txt` 사본 요구 / `auth_boundary` 검사 / `basis='other'`는 `basis_note` ≥20자 | 권한 블록 10/10 위조 통과 | — |
| NFC 정규화 | — | macOS NFD 한글 경로 |

**양방향 회귀 23/23** — 위조 16종 전부 반려, 정직 7종 전부 통과. 픽스처는
`tests/regression.py`에 고정했다. **검증기를 고칠 때마다 반드시 양방향으로 돌린다** — 한쪽만
보면 반대쪽이 무너진다는 것이 이번 교훈이다.

**채택하지 않은 제안 11종**도 기록한다(오탐을 늘리는 수정): `MIN_FULL_VIEW_EDGE` 상향·뷰포트
연동, 선언 픽셀 대비 바이트 비율 휴리스틱, 단색·엔트로피 판정, metrics 다중개념 키 무효화,
문서별 사이트명 언급 강제, `confirmed_by` 금지어 블랙리스트, 신선도 기본 활성화, robots.txt
실 fetch 기본 필수화, 마커 검사 제거, 마지막 줄 요건 완화, `--force` 동작 변경.

### 남은 잔여 위험 (정직하게)

- **PNG 선언 크기와 실제 픽셀을 대조하지 않는다.** IHDR가 4000×4000이라 주장하고 IDAT가
  1픽셀이어도 통과한다. 바이트 비율 휴리스틱은 단색 랜딩·PNG8 팔레트 최적화를 무는 오탐이라
  거부했다. 이건 **의도적 트레이드오프**다.
- **`captured_at`에 하한이 없다.** `0001-01-01`도 기본값에서 통과한다. 신선도 상한은
  `--max-evidence-age-days` 옵트인이다(기본 활성화는 오래 걸린 정직한 프로젝트를 문다).
- **권한은 여전히 자기 신고다.** 호스트 대조와 `qa/robots.txt` 사본 요구로 위조 비용은
  올렸지만 사본 자체를 위조할 수 있고, `basis`가 실제 `source_url`과 맞는지는 대조하지 않는다.
  실제 fetch(`--verify-robots`)는 미구현 — 검증기가 네트워크에 의존하면 오프라인·사내망·
  localhost 클론이 전부 반려되는 flaky 게이트가 되기 때문이다.
- **문서는 어휘 다양성만 본다.** 관찰에 근거했는지, 실제 라우트를 서술하는지는 보지 않는다.
- 이 목록을 "완전한 방어"로 부르지 않는다 — 목표는 **증명이 아니라 위조 비용 상승과 거짓
  진술의 명시화**다.

## 2026-09-28~30 — 브라우저 Aside 재결속 (현행 결속)

위 표의 Playwright MCP·`accesslint:audit` 결속은 폐기됐다. 현행은 SKILL.md "Required companion workflows"가 정본이다.

- **브라우저**: Playwright·Chrome MCP는 `permissions.deny`로 툴 자체가 없다 → `aside-browser` 전용(`rules/uncompromising-rigor.md` §1). 스크린샷은 `page.screenshot` Buffer를 base64로 회수한다(`path`는 Aside 세션 폴더로 샌드박스).
- **뷰포트 캡처**: design-toolchain `run-qa.sh`(375×812·1280×800 고정). 2026-09-30부터 manifest를 `init_clone_run.py --mobile 375x812 --desktop 1280x800`으로 맞추고 러너 출력 파일명을 계약 파일명으로 옮긴다.
- **성능**: Lighthouse(자체 Chrome) → aside 페이지 안 측정 `measure.js`(capture-contract §8). 2026-09-30에 sed 치환(SyntaxError)을 JSON 치환으로 고쳤고, 같은 날 measure.js에 `__COMBO__`가 추가되며 레시피가 다시 깨져 2026-10-01 치환을 `design-toolchain/scripts/render.py` 단일 정본으로 합쳤다(로컬 페이지 실행·`is_measurement` 통과 재확인).
- **접근성**: `accesslint:audit`(자체 Chrome) → run-qa.sh의 axe-core 주입 스캔.
- **본문 Codex 전용 지시**(Product Design 부트스트랩·`design-qa`·ImageGen·"Sites tests"): 2026-09-30에 각 줄에 적응 주석을 달았다(`run`·playwright-design-audit·codex 이미지 생성·실재 테스트만).

## 미확인 / 다음에 확인할 것

- 실제 사이트로 파이프라인을 **끝까지 돌려본 적 없다.** 첫 실사용 때 `resolve_clone_destination`
  → `init_clone_run` → 문서 생성 → `validate_clone_artifacts` 순서가 이 환경에서 실제로
  통과하는지 관측해야 한다. [미확인]
- `문서/`·`크롤링` 등 한국어 디렉토리명이 검증기·생성기 양쪽에서 일관되게 처리되는지
  실사용 전 미검증. [미확인]
