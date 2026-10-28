#!/bin/bash
# uiux-skill-router.sh — UserPromptSubmit 훅 (스킬 신호 라우터)
# 프롬프트에서 ① UI/UX ② 영상 ③ 검증·QA·보안·검수 신호를 감지하면 해당 스킬 라우팅
# 컨텍스트를 주입한다. C계층(신호 라우터)으로, disable-model-invocation·참조 0곳이라
# 모델이 스스로 못 부르는 고가치 자산(project-quality-loop 등)의 가시성을 회복시킨다
# (2026-08-09 발동성 감사 반영). stdout이 additionalContext로 전달, 미감지 시 무출력.
# 2026-09-30: 신호 판정을 python(단어 경계·공백 제거본·배제 구문)으로 옮겨 오탐·미탐을 줄이고
# (감사 #37·#84·#85·#86), 영상 블록(Remotion 권유)을 추가했다. 회귀 코퍼스: 같은 폴더 router-corpus.tsv

prompt=$(jq -r '.prompt // empty' 2>/dev/null)
[ -z "$prompt" ] && exit 0

flags=$(ROUTER_PROMPT="$prompt" python3 - <<'PY' 2>/dev/null
import os, re

p = os.environ.get("ROUTER_PROMPT", "")
low = p.lower()

# UI가 아닌 뜻으로 자주 쓰이는 구문은 먼저 지운다(오탐 방지)
UI_VETO = [
    r"시스템\s*디자인", r"(db|데이터베이스|스키마|api|아키텍처|백엔드|소프트웨어)\s*디자인",
    r"\bsystem design\b", r"\b(database|schema|api|architecture|backend|data|software|db) design\b",
    r"\bdesign (the |a |an )?(database|schema|api|architecture|backend|data model|algorithm|system)\b",
    r"\bdesign (pattern|doc|document|decision)s?\b",
]
text = low
for v in UI_VETO:
    text = re.sub(v, " ", text)
if re.search(r"투자|주식|자산|펀드|리밸런싱|채권|수익률|\b(invest|stock|asset|fund|rebalanc|etf|bond)", text):
    text = re.sub(r"포트폴리오|\bportfolio\b", " ", text)
nsp = re.sub(r"\s+", "", text)  # 한국어 복합어는 띄어쓰기 변형까지 잡는다

# 웹·화면 문맥 — 단독으로 UI 블록을 켠다
UI_WEB_KO = [
    "디자인", "레이아웃", "반응형", "다크모드", "라이트모드", "여백", "버튼", "컴포넌트", "색상", "글꼴", "폰트",
    "세련", "대시보드", "히어로", "목업", "와이어프레임", "스타일가이드", "타이포", "랜딩", "웹사이트", "홈페이지",
    "웹페이지", "프론트엔드", "포트폴리오", "피그마", "모달", "바텀시트", "팝오버", "툴팁", "드로어", "호버",
    "마이크로인터랙션", "폴리싱", "로고", "아이콘", "시각화", "소개사이트",
    "쓰리디", "셰이더", "쉐이더", "웹지엘",  # 3D·WebGL UI 소재(threeui-reference, 2026-10-16)
]
UI_WEB_KO_RE = [r"3d(인터랙티브|버튼|배경|효과|장면|씬|에셋|요소|히어로|ui)", r"사이트(를|의|가)?(만들|제작|리뉴얼|개편|구축|개선|수정)", r"소개페이지", r"페이지(를|의)?(만들|제작|리뉴얼|개편|구축|디자인)", r"화면(을|이|의)?(설계|구성|다듬|개선|만들|정리|수정)",
                r"토스트(알림|메시지|ui)"]
UI_WEB_EN = [
    r"\bui\b", r"\bux\b", r"\bdesign\b", r"\bweb ?sites?\b", r"\bhome ?pages?\b", r"\bweb ?pages?\b",
    r"\blanding ?pages?\b", r"\bfront-?end\b", r"\blayouts?\b", r"\bresponsive\b", r"\b(dark|light) ?mode\b",
    r"\bcss\b", r"\btailwind\b", r"\bmockups?\b", r"\bwireframes?\b", r"\bdashboards?\b", r"\bhero (section|image|banner)\b",
    r"\btypograph", r"\bfigma\b", r"\bmodals?\b", r"\bpopovers?\b", r"\btooltips?\b", r"\bhover\b",
    r"\bbottom ?sheet\b", r"\btoast (notification|message|component)s?\b", r"\bsonner\b", r"\bmicro-?interactions?\b",
    r"\b(ui|react|vue|svelte|card|button|form) components?\b", r"\bbuttons?\b", r"\bstyl(e|ing) guide\b",
    r"\bpolish (the )?(ui|design|page|screen|layout|landing|site|animations?)\b", r"\bvisual (design|polish|hierarchy)\b",
    r"\bportfolio\b", r"\bdata ?viz\b", r"\b(bar|line|pie) charts?\b", r"\bimpeccable\b",
    r"\bwebgl2?\b", r"\bthree\.?js\b", r"\bthreeui\b", r"\bglsl\b", r"\bshaders?\b", r"\b3d (interactive|button|background|scene|asset|ui|effect|hero)s?\b",
]
# 모션 계열 — 영상 신호가 없을 때만 UI로 본다(영상 작업이면 영상 블록이 담당)
UI_MOTION_KO = ["애니메이션", "모션", "인터랙션", "트랜지션", "이징", "제스처", "스와이프", "드래그", "화면전환", "페이지전환"]
UI_MOTION_KO_RE = [r"스프링(애니메이션|모션|물리)"]
UI_MOTION_EN = [
    r"\banimations?\b", r"\bmotion\b", r"\binteractions?\b", r"\beasing\b", r"\bswipe\b", r"\bdrag(-| and |&)drop\b",
    r"\bdraggable\b", r"\bspring (animation|physics)\b", r"\busespring\b",
    r"\b(page|screen|view|route|layout|css|shared element) transitions?\b", r"\btransitions? (animation|effect|duration|timing)\b",
]

VIDEO_VETO = [r"영상\s*(처리|인식|통화|회의|분석)", r"<video", r"\bvideo (call|conferenc|tag|element)"]
vtext = low
for v in VIDEO_VETO:
    vtext = re.sub(v, " ", vtext)
vnsp = re.sub(r"\s+", "", vtext)
VIDEO_KO = ["영상", "동영상", "비디오", "모션그래픽", "쇼츠", "릴스", "유튜브", "틱톡", "자막", "리모션"]
VIDEO_EN = [
    r"\bvideos?\b", r"\bmp4\b", r"\bmotion graphics?\b", r"\bremotion\b", r"\bsubtitles?\b", r"\bexplainer\b",
    r"\bpromo (video|clip)s?\b", r"\byoutube shorts\b", r"\binstagram reels\b", r"\btiktok\b",
]

QA_KO_RE = [r"검수", r"검증", r"점검", r"품질", r"고도화", r"반복\s*개선", r"끝까지", r"완성도", r"테스트", r"취약",
            r"보안", r"감사(?!합|드|해|하|했|의|히)", r"리뷰", r"2차\s*의견", r"성능", r"출시", r"배포\s*전"]
QA_EN = [r"\bqa\b", r"\btests?\b", r"\btesting\b", r"\bpytest\b", r"\bjest\b", r"\bvitest\b", r"\be2e\b", r"\bsecurity\b",
         r"\bvulnerab", r"\baudit", r"\breview", r"\bsecond opinion\b", r"\bperformance\b"]

def hit(words, s):
    return any(w in s for w in words)

def rx(pats, s):
    return any(re.search(x, s, re.A) for x in pats)   # re.A: 한글 조사를 단어 문자로 보지 않는다("UI를"·"CSS가")

video = hit(VIDEO_KO, vnsp) or rx(VIDEO_EN, vtext)
# 영상에도 흔한 모호어(로고·아이콘·시각화·대시보드·차트)는 모션 계열처럼 영상 신호가 없을 때만 UI로 본다
AMBIG_KO = {"로고", "아이콘", "시각화", "대시보드"}
AMBIG_EN = {r"\bdashboards?\b", r"\b(bar|line|pie) charts?\b", r"\bdata ?viz\b"}
ui_web = (hit([w for w in UI_WEB_KO if w not in AMBIG_KO], nsp) or rx(UI_WEB_KO_RE, nsp)
          or rx([x for x in UI_WEB_EN if x not in AMBIG_EN], text))
ui_motion = (hit(UI_MOTION_KO, nsp) or rx(UI_MOTION_KO_RE, nsp) or rx(UI_MOTION_EN, text)
             or hit(AMBIG_KO, nsp) or rx(AMBIG_EN, text))
# 2026-10-16: 디자인 하네스 세부 신호 — 레퍼런스·모션 성능·엣지 데이터·녹화→웹 모션(design-toolchain references/remotion-vs-motiscope.md)
REF_KO = [r"레퍼런스", r"참고\s*(사이트|디자인|화면)", r"벤치마크", r"벤치마킹", r"무드\s*보드", r"경쟁사\s*(디자인|사이트|화면)", r"refero", r"레페로"]
REF_EN = [r"\breferences? (site|design|screen)s?\b", r"\bmood ?boards?\b", r"\bdesign inspiration\b", r"\bbenchmark (the )?(design|ui|site)s?\b", r"\brefero\b"]
PERF_KO = [r"버벅", r"끊(김|겨|기|긴)", r"프레임\s*(드롭|저하|떨어)", r"렉(이|걸|있)", r"뚝뚝", r"부드럽지\s*않"]
PERF_EN = [r"\bjank", r"\bjanky\b", r"\bstutter", r"\bchoppy\b", r"\bdropp?(ed|ing)? frames?\b", r"\bframe ?drops?\b", r"\blaggy (animation|scroll)"]
EDGE_KO = [r"깨지는지", r"(데이터|이름|텍스트|글자)\S{0,4}\s*(들어가면|넣으면)\s*깨", r"긴\s*(텍스트|이름|글자|제목|문구)", r"엣지\s*케이스", r"최악(의)?\s*(데이터|경우)", r"넘치(는지|면)"]
EDGE_EN = [r"\bedge cases?\b", r"\bworst[- ]case\b", r"\bstress[- ]test\b", r"\blong (names?|text|labels?)\b", r"\bbreak (the|this) (ui|component|layout)\b"]
REC_IN = [r"(화면\s*)?녹화(본|한|된|해서)?", r"이\s*(영상|gif|움짤)\s*(처럼|같이|대로|의\s*(모션|애니메이션|움직임))", r"\.(mp4|mov|webm|gif|m4v)\b", r"\bscreen ?recording\b", r"\b(this|the) (video|gif|clip)('s)? (motion|animation)\b", r"\bmotiscope\b"]
WEB_OUT = [r"사이트", r"페이지", r"웹", r"히어로", r"버튼", r"컴포넌트", r"css", r"gsap", r"framer", r"코드로", r"\bweb\b", r"\bsite\b", r"\bpage\b", r"\bcomponent\b", r"\bhero\b"]
VIDEO_OUT = [r"영상(을|으로)?\s*(만들|제작|렌더|뽑)", r"mp4(로|를)\s*(만들|뽑|렌더)", r"렌더(링)?(해|하)", r"쇼츠", r"릴스", r"(데모|소개|홍보)\s*영상", r"\brender (a|the|an)? ?video\b", r"\bmake (a|the) video\b", r"\bremotion\b"]
ref = rx(REF_KO, low) or rx(REF_EN, low)
perf = rx(PERF_KO, low) or rx(PERF_EN, low)
edge = rx(EDGE_KO, low) or rx(EDGE_EN, low)
rec2web = rx(REC_IN, low) and rx(WEB_OUT, low) and not rx(VIDEO_OUT, low)
if rec2web:
    video = False   # 녹화는 입력일 뿐 — 영상 산출 블록(Remotion) 대신 녹화→웹 모션 블록
out = []
if ui_web or (ui_motion and not video) or ref or perf or edge or rec2web:
    out.append("ui")
if video:
    out.append("video")
for name, on in (("ref", ref), ("perf", perf), ("edge", edge), ("rec2web", rec2web)):
    if on:
        out.append(name)
if rx(QA_KO_RE, low) or rx(QA_EN, low):
    out.append("qa")
print(" ".join(out))
PY
)

case " $flags " in *" ui "*)
  cat <<'EOF'
[uiux-skill-router] UI/UX 신호 감지 — 단계별로 맞는 스킬만 Skill 도구로 부른다(역할이 겹치는 스킬 동시 호출 금지). 규범: rules/ui-ux-craft.md · 도구 정본: design-toolchain 스킬
⓪ 기준까지 반복하는 고도화(고도화·리디자인·경쟁사 수준·완성도 기준·끝까지·until it meets the bar) = design-elevation-loop 먼저 — 완성도 기준을 질문으로 정해 잠그고 goal을 건 뒤, 아래 ①~④를 회차 안에서 단계별로 부른다(리서치가 없으면 리서치부터)
① 방향(새 화면·리디자인, 코드 전 design-brief.md — 대상·느낌·참고 사이트 1~2곳 필수, 상세는 rules/ui-ux-craft.md "브리프 우선"): **리서치 근거는 Refero 먼저**(사용자 결제 완료·유일한 허용 유료 — MCP `refero_search_styles/get_style`→`search_screens/get_screen`→`search_flows/get_flow`, 절차는 `refero-design` 스킬의 reference lock·decision ledger; 단 권위는 이 라우터, 변형 선택은 벤치마크·판정단으로 메인이 결정, 이미지는 codex, 참조 파일은 필요한 것만 로드) → 랜딩·소개(마케팅) 사이트·포트폴리오·리디자인 = design-taste-frontend("Design Read" 1줄 + draw.mjs 방향; v2가 메인 절차(inspect·assets 포함), 생성 그림은 codex — ui-ux-craft) / 그 밖의 새 UI = frontend-design:frontend-design
② 크래프트: emil-design-eng(UI 구축·수정 기본 — 빠른 반복 UI는 CSS transition) · animate(새 모션을 결정 순서대로 구현·레시피) · apple-design(제스처 추적·스프링·시트 — 제스처엔 transition 대신 물리) · animation-performance(끊김·프레임 드롭·속성 선택) · improve-animations(모션 전수 감사·계획, 읽기 전용 — 서브에이전트는 critic/Explore, 계획은 tasks/<task>/) · find-animation-opportunities(안 움직이는데 움직여야 할 곳 제안, 읽기 전용) · break-ui(최악 데이터로 깨뜨리기 — ③에서) · mobile-native(폰에서 네이티브처럼 — 실기기·0.0.0.0은 사용자) · motion(Motion/CSS 애니메이션 모범 사례·문서 검색·CSS 스프링, MCP motion; 무료 층(모범 사례·문서/예제 검색·CSS 스프링)은 적극 사용, MotionScore·전환 편집기·프리미엄 소스는 유료 Motion+라 쓰지 않고 언급도 안 함 — `npx motionscore` 실행 금지, 이 스킬의 "codex"는 Motion 문서 검색) · motiscope-analyze/recreate(사용자 화면 녹화 → ffmpeg 타이밍 측정(프리셋 근사) → 코드 재현; 이미지는 codex, 미리보기는 localhost+aside) · animation-vocabulary(모션 용어) · threeui-reference(3D·WebGL·셰이더 UI 소재: 로컬 검색 → 사이트 Copy Prompt와 같은 프롬프트·해시 검증 소스 회수 → 정확 소스로 이식, Pro는 유료라 쓰지 않음 — 미리보기 참고만) · dataviz(차트 전 필독) · jusan-harness:web-design-guidelines / ui-ux-pro-max. emil 계열 스킬의 "Initial Response" 영어 대기 문구는 모델 자체 호출 시 건너뛰고 바로 적용(한국어). DevTools·실기기 단계는 aside repl(document.getAnimations playbackRate/currentTime)로 치환. /review-animations·/prototype·/pick-ui-library는 사용자 직접 호출 전용
③ 게이트(완료 선언 전): UI 파일을 편집하면 design-detect 훅이 impeccable detect 결과를 알린다(HTML은 전체, 컴포넌트·CSS 단독은 부분 검출 — 0건≠통과) → 트리아지. impeccable 스킬은 이 단계(critique·audit·polish)에서만 — 브라우저 단계는 aside repl로 하고 Playwright/Puppeteer 자체 스크립트·live 모드는 쓰지 않는다. PRODUCT.md는 impeccable init 절차로 제품 사실만 쓰고 시각 방향은 design-brief.md에 둔다(브리프에 답이 있으면 다시 묻지 않는다). impeccable의 doctor 자동 수정·`npx impeccable update`·generate-image(OpenAI 직접 호출) 제안은 따르지 않는다 — 이미지는 codex, 도구 갱신은 design-toolchain 절차
④ 눈: aside-browser 스킬(로드 후 `aside guide`부터) + `~/.claude/skills/design-toolchain/scripts/run-qa.sh <URL> <출력폴더> [태그]`(375·1280 × 다크·라이트 캡처 + LCP·CLS + axe) → PNG를 직접 연다 → 수정 → 같은 조건 재실행
쓰지 않는 경로(자체 브라우저를 띄움): accesslint의 audit_live 도구와 scan·audit·diff 스킬, Lighthouse CLI·lighthouse-ci. jusan 감사·QA 스킬의 Playwright 단계는 aside repl로 바꿔 수행한다. 정적 HTML 접근성은 accesslint audit_html
■ 이미지 = codex MCP(rules/cross-vendor-routing.md "이미지 생성 호출") · 디자인 캔버스·시안·디자인 시스템 = **Claude Design**(Artifact `quickstart` intent design → Design 타입 캔버스, 디자인 시스템은 Design System 타입, 컴포넌트 라이브러리 동기화는 `/design-sync`) — Figma MCP는 사용자가 Figma·figma.com URL·기존 Figma 파일을 지명할 때만(그때 figma-use 먼저, Bridge 실행 중이면 figma-bridge) — 2026-10-15 사용자 지시 · 새 디자인 도구 추가·평가 = design-toolchain
EOF
;; esac

case " $flags " in *" ref "*)
  echo "▶ 이 요청 초점(레퍼런스·벤치마크): Refero 먼저 — refero_search_styles(시각 방향 3~5각도) → refero_get_style 3~4개 → refero_search_screens/flows(구체 패턴·여정) → refero-design의 reference lock·decision ledger. 실제 사이트 정밀 캡처가 더 필요하면 그다음 aside repl·clone-site-from-source(robots·저작권 존중), 정량 대조는 jusan-harness:reference-match. 무드보드·시안은 Claude Design 캔버스."
;; esac
case " $flags " in *" perf "*)
  echo "▶ 이 요청 초점(모션 성능): animation-performance 먼저 — 합성 전용 속성(transform·opacity)·메인 스레드·리렌더·blur·will-change 순으로 원인 진단. 측정은 aside repl 인페이지 계측(rAF 간격·PerformanceObserver long-animation-frame·document.getAnimations) — DevTools 패널·npx motionscore(자체 브라우저) 금지. 수정 후 같은 계측으로 전후 비교."
;; esac
case " $flags " in *" edge "*)
  echo "▶ 이 요청 초점(엣지 데이터): break-ui — 긴 이름·끊김 없는 이메일·0/1/1000건·비라틴·이모지·극단 숫자를 넣은 최악 데이터 픽스처 + Demo/Worst 토글(공개 site/src/pages 밖, dev 전용) → 깨진 곳과 수정안. 폭별 확인은 run-qa.sh(375·1280), 200% 줌은 반폭 iframe으로 흉내."
;; esac
case " $flags " in *" rec2web "*)
  echo "▶ 이 요청 초점(녹화 → 웹 모션): motiscope 위주, Remotion은 결과가 '영상 파일'일 때만(정본: design-toolchain references/remotion-vs-motiscope.md — 2026-10-16 실측: motiscope는 구간·홀드·대표 프레임은 쓸 만하나 이징 종류·cubic-bezier·시차 숫자는 3/3 틀림). 순서: motiscope analyze <영상> → report의 구간·홀드만 채택 → 골라 준 프레임을 직접 열어 이징·시차·순서 판정 → (정교함이 필요하면) Remotion 매개변수 컴포지션으로 후보를 렌더해 원본 녹화와 프레임 단위 대조·후보 탐색(같은 실험에서 상자 오차 188px→107px→10px) → animate·emil-design-eng·무료 motion 문서로 CSS/JS 구현(토큰 우선, CDN GSAP·인라인 스크립트 산출물은 CSP 때문에 그대로 쓰지 않음) → aside repl로 getAnimations() duration·easing·delay를 측정 구간과 대조. 결과 수치는 '프리셋 근사'로 표기. 녹화는 사용자가 만든다(Aside 녹화 불가)."
;; esac

case " $flags " in *" video "*)
  cat <<'EOF'
[uiux-skill-router] 영상 신호 감지 — 만들 영상의 종류로 도구를 고른다(근거·한계: design-toolchain 스킬 §5):
■ Remotion을 권한다 — 코드로 짜는 영상: 모션그래픽·타이틀·로고 애니메이션, 제품·기능 소개와 UI 데모, 데이터·차트·지도 애니메이션, 자막이 핵심인 쇼츠·릴스, 여러 소재(이미지·클립·음성·음악)를 한 편으로 조립, 해상도·언어·데이터만 바꾼 대량 변형, 수정이 반복될 영상
  - 진입은 `remotion-best-practices` 스킬 하나(세부 스킬로 안내한다). 처음 도입할 때 라이선스를 1줄 고지: 무료는 개인·직원 3명 이하 영리 조직·비영리·평가, 그 밖의 영리 조직은 Company License(remotion.pro)
■ Remotion이 아닌 경우
  - 참고 녹화를 보고 '웹 페이지 안' 모션으로 옮기는 일 → motiscope 위주(영상 분석·측정은 Remotion이 못 한다). 참고 영상을 보고 '영상으로' 다시 만들 때는 motiscope로 구간·홀드를 먼저 재고 Remotion으로 제작(정본: design-toolchain references/remotion-vs-motiscope.md)
  - 실사·시네마틱처럼 촬영한 듯한 생성형 클립 → fal.ai image-to-video(Kling 등). 브랜드 통제가 필요하면 Blender(Blender MCP·`blender -b --python`)로 시작·끝 기준 프레임을 렌더해 넣는다. 영상화 전 Blender 장면을 사용자에게 검사받고, 호출 전 단가 확인·사용자 비용 상한 안에서만(2026-10-22 사용자 지시)
  - 웹페이지 안에서 도는 UI 모션(hover·모달·페이지 전환) → 영상 파일이 아니다. UI 쪽 스킬(emil-design-eng 등)
  - 렌더가 끝난 영상·사용자 촬영본의 후처리(probe·검사·압축·루프·비율 변형·라우드니스·자르기·이어붙이기·웹 내보내기) → `ffmpeg-skill`(probe → --dry-run → 실행 → check/verify). 시스템 ffmpeg는 Homebrew 9.0.2로 정상 실행되지만 drawtext·subtitles(libass)·vidstab 필터가 없다(2026-10-15 doctor) — 영상 속 글자·자막·제목은 Remotion으로 만들고 ffmpeg로 굽지 않는다. 새 장면 합성도 Remotion
  - 생성형 영상 호출은 fal.ai 직접 호출(키는 프로젝트 `.env`의 `FAL_KEY`, 출력·커밋 금지)로 한다 — 생성형 영상을 감싼 서드파티 스킬·CLI(자체 브라우저·자격 증명 읽기)는 설치하지 않는다
■ 하네스 운용 규칙(스킬 기본값과 다름)
  - 사용자 미리보기: `npx remotion studio --no-open`(옵션 없이 실행하면 시스템 브라우저가 열린다) → `open -b at.studio.AsideBrowser "http://localhost:<port>/<컴포지션ID>"`. Studio는 LAN(*:port)에도 열리므로 확인이 끝나면 종료
  - 모델이 직접 확인: `npx remotion render <ID> out/frames --frames=0,<중간>,<끝> --image-format=png` 또는 `npx remotion still` → PNG를 직접 연다(렌더 엔진인 Chrome Headless Shell은 브라우저 작업 예외)
  - 최종 렌더는 사용자가 요청할 때만. 새 프로젝트는 remotion.config.ts에 `Config.setVideoImageFormat("png")`·`Config.setPixelFormat("yuv420p")`를 넣는다(기본 jpeg 프레임은 yuvj420p 풀레인지) → 렌더 후 `npx remotion ffprobe`로 길이·해상도·fps·pix_fmt 검산
  - 소재: 이미지는 codex로 만들고 촬영본은 사용자에게서 받아 `public/`에 두고 `staticFile()`로 불러온다
  - 웹 첫 화면 무음 루프: Remotion `--muted` → 첫·끝 프레임 이음을 `still` 두 장으로 대조 → H.264 MP4(yuv420p, +faststart) + VP9/AV1 WebM 두 벌 + 포스터(PNG → AVIF/WebP), 용량 예산 명시. 사이트는 `autoplay muted loop playsinline` + prefers-reduced-motion이면 포스터 정지. 화면 글자가 있으면 ko/en을 언어별 props로 따로 렌더
  - 음성: 로컬 한국어 TTS 미확보 → 기본은 무음 + 화면 글자. 외부 유료 TTS(ElevenLabs 등)는 승인 대상. 효과음은 원격 URL을 렌더에서 직접 부르지 않고 라이선스 확인한 파일을 `public/`에
EOF
;; esac

case " $flags " in *" qa "*)
  cat <<'EOF'
[uiux-skill-router] 검증·QA·보안·검수 신호 감지 — 작업 성격에 맞는 스킬/벤더를 발동하라:
■ 반복 검수·완성도 루프
- design-elevation-loop: 대상이 디자인·UI면 이쪽 — 완성도 기준 질문 → 잠금·goal → 측정·블라인드 판정단으로 충족까지 반복(모델 호출 가능)
- project-quality-loop: 프로젝트 전 차원(코드·보안·성능·QA 포함) 검수·출시 판정 루프 (슬래시 전용 — 이 신호에서 제안). 디자인 루프와 동시에 바깥 루프로 돌리지 않는다
■ 검증·감사
- jusan-harness:security-review / security-audit: 보안 검토(OWASP·시크릿·인증)
- jusan-harness:live-verify-loop / webapp-testing: 실동작 검증 절차 (브라우저 조작은 aside-browser 스킬의 `aside repl` — Playwright 지시는 치환)
- jusan-harness:project-ultra-audit / web-audit-pipeline: 전체 페이지·기능 감사 — 브라우저 단계는 aside repl로 치환하고, Lighthouse·lighthouse-ci 단계는 design-toolchain run-qa.sh 측정으로 대체
- 접근성(WCAG): aside 안 axe 주입 스캔(design-toolchain run-qa.sh) · 정적 HTML은 accesslint `audit_html`
■ 교차벤더 2차 의견 (cross-vendor 스킬)
- 코드 리뷰·아키텍처 결정·2회 수정 실패·보안·엣지케이스 → codex read-only 2차 의견
- 시각/실사 판정·고위험 → codex + Claude critic 판정단. (규범: rules/cross-vendor-routing.md)
EOF
;; esac
exit 0
