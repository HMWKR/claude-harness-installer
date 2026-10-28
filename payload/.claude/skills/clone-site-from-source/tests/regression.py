#!/usr/bin/env python3
import json, shutil, struct, subprocess, sys, zlib, os
from datetime import datetime, timezone
from pathlib import Path
SK = Path.home()/".claude/skills/clone-site-from-source/scripts"
sys.path.insert(0, str(SK))
from generate_site_docs import DOCUMENT_NAMES, DEEP_UX_DOCUMENT_NAMES, DEEP_UX_REQUIRED_HEADINGS, EVIDENCE_LABELS
# 실행마다 새 임시 폴더 — 예전 값은 다른 세션의 scratchpad로 하드코딩돼 실행할 때 그 경로를 지우고 다시 만들었다(2026-09-30 감사)
import tempfile
BASE = Path(tempfile.mkdtemp(prefix="clone-site-rg-"))

def chunk(t,d):
    c=t+d; return struct.pack(">I",len(d))+c+struct.pack(">I",zlib.crc32(c))
def png(w,h,real=True,declared=None):
    dw,dh = declared or (w,h)
    out = b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",dw,dh,8,2,0,0,0))
    if real:
        raw=b"".join(b"\x00"+b"\xcc\xdd\xee"*w for _ in range(h))
        out += chunk(b"IDAT",zlib.compress(raw))
    return out+chunk(b"IEND",b"")

VOCAB = ("""
정보구조 라우트 캡처 뷰포트 타이포그래피 간격 토큰 반응형 접근성 인터랙션 상태 증거
네비게이션 푸터 히어로 카드 버튼 폼 모달 드로어 탭 필터 검색 스크롤 포커스 키보드 모션
대비 명도 자산 폰트 이미지 아이콘 색상 그리드 여백 정렬 계층 콘텐츠 문구 링크 라벨
오류 로딩 빈상태 성공 경계 권한 범위 제외 대표 라우트패밀리 측정 오버플로 콘솔 빌드
테스트 회귀 문서 근거 출처 검증 추론 확인 불가 필요 사용자 운영자 여정 퍼널 전환 유지
획득 활성화 재방문 추천 수익 구독 결제 온보딩 첫가치 완료 이탈 복구 재시도 알림 배지
브레드크럼 페이지네이션 무한스크롤 정렬옵션 토스트 스낵바 툴팁 팝오버 시트 바텀시트
헤더 사이드바 레이아웃 컨테이너 브레이크포인트 모바일 태블릿 데스크톱 와이드 다크모드
라이트모드 시스템설정 애니메이션 트랜지션 이징 지속시간 지연 감속 스프링 패럴랙스
호버 액티브 비활성 선택됨 체크됨 확장됨 축소됨 필수 선택 유효성 제약 마스킹 자동완성
플레이스홀더 헬퍼텍스트 카운터 제출 초기화 취소 삭제 편집 저장 미리보기 공유 복사
다운로드 업로드 드래그 드롭 정렬 그룹화 확대 축소 회전 자르기 원본 사본 버전 이력
스키마 메타데이터 구조화데이터 사이트맵 로봇 캐노니컬 오픈그래프 트위터카드 파비콘
성능 지표 로딩순서 지연로딩 프리로드 프리페치 번들 청크 압축 캐시 전송량 레이아웃시프트
보안 헤더 정책 프레이밍 참조자 쿠키 개인정보 약관 저작권 상표 라이선스 출처표기
""").split()
def body(deep, extra=""):
    words = VOCAB*4 if deep else VOCAB*2
    return " ".join(words) + " " + extra

def build(name, **o):
    root = BASE/"크롤링"/name
    if root.exists(): shutil.rmtree(root)
    for d in ("qa/source","qa/implementation","qa/comparisons","qa/metrics","문서","src"):
        (root/d).mkdir(parents=True, exist_ok=True)
    # 증거 이미지
    for d in ("source","implementation","comparisons"):
        for fn, data in o.get("images", {"shot.png": png(1280,720)}).items():
            (root/"qa"/d/fn).write_bytes(data) if isinstance(data,bytes) else (root/"qa"/d/fn).write_text(data)
    (root/"qa/metrics/routes.json").write_text(json.dumps(o.get("metrics",
        [{"route":"/","title":"Example","width":1280,"height":720}])), encoding="utf-8")
    if o.get("robots_copy", True): (root/"qa/robots.txt").write_text("User-agent: *\nAllow: /\n")
    (root/"package.json").write_text(o.get("pkg", '{"name":"t","scripts":{"build":"vite build"}}'))
    (root/"src/App.tsx").write_text(o.get("src", 'export const App = () => <div>hi</div>;\n'))
    auth = o.get("auth", {"basis":"public-documentation-site","confirmed_by":"IANA example domain",
                          "robots_txt_checked":"allowed","robots_txt_url":"https://example.com/robots.txt"})
    m = {"schema_version":1,"source_url":"https://example.com/","source_origin":"https://example.com",
         "crawl_container":"크롤링","site_name":name,
         "captured_at":o.get("captured", datetime.now(timezone.utc).isoformat()),
         "auth_boundary":"public-only","external_writes":False,"routes":["/"],
         "scope":{"mode":"public-comprehensive","reduction_reason":None,"inventory_basis":["global-navigation"],
                  "included_routes":["/"],"excluded_routes":[],"dynamic_route_families":[]},
         "viewports":{"desktop":{"width":1280,"height":720},"mobile":{"width":390,"height":844}},
         "evidence":{"source":"qa/source","implementation":"qa/implementation","comparisons":"qa/comparisons"}}
    if auth is not None: m["authorization"]=auth
    (root/"clone-source.json").write_text(json.dumps(m,ensure_ascii=False), encoding="utf-8")
    (root/"design-qa.md").write_text(o.get("qa",
        "# QA\nTypography Spacing Colors Image Copy Interactions Console Build Sites\n"
        "- source: qa/source/shot.png\n- impl: qa/implementation/shot.png\nfinal result: passed\n"), encoding="utf-8")
    for dn in DOCUMENT_NAMES:
        if dn in DEEP_UX_DOCUMENT_NAMES:
            txt = "".join(f"## {h}\n{body(True)}\n" for h in DEEP_UX_REQUIRED_HEADINGS[dn])
            txt += " ".join(EVIDENCE_LABELS)*3
            if dn.startswith("17"): txt += "\n```mermaid\ngraph TD;A-->B;\n```\n"
            if dn.startswith("20"): txt += o.get("doc20_extra","")
        else:
            txt = body(False) + o.get(f"doc_extra_{dn[:2]}", "")
        (root/"문서"/dn).write_text(txt, encoding="utf-8")
    return root

def run(root,*x):
    r=subprocess.run([sys.executable,str(SK/"validate_clone_artifacts.py"),"--project-root",str(root),*x],
                     capture_output=True,text=True)
    return r.returncode, r.stdout.strip()

FORGE = [
 ("0바이트 png만", dict(images={"a.png":b""})),
 ("텍스트를 .png로", dict(images={"a.png":b"this is not an image"})),
 ("1x1 + 0바이트 동거(원래 우회)", dict(images={"shot.png":png(1,1),"junk.jpg":b""})),
 ("IHDR만(IDAT 없음)", dict(images={"a.png":png(1280,720,real=False)})),
 ("1x1 진짜 PNG", dict(images={"a.png":png(1,1)})),
 ("metrics null/0", dict(metrics={"url":None,"title":None,"width":0,"height":0})),
 ("합성키 urltitlewidthheight", dict(metrics={"urltitlewidthheight":0})),
 ("metrics 빈 dict 값", dict(metrics={"path":{},"label":{},"width":{},"height":{}})),
 ("design-qa가 metrics만 인용", dict(qa="# QA\nTypography Spacing Colors Image Copy Interactions Console Build Sites\nqa/metrics/routes.json qa/metrics/routes.json\nfinal result: passed\n")),
 ("confirmed_by='x'", dict(auth={"basis":"other","confirmed_by":"x","robots_txt_checked":"allowed","robots_txt_url":"https://example.com/robots.txt"})),
 ("robots_url 호스트 불일치", dict(auth={"basis":"user-owned","confirmed_by":"me myself","robots_txt_checked":"allowed","robots_txt_url":"https://evil.net/robots.txt"})),
 ("allowed인데 사본 없음", dict(robots_copy=False)),
 ("package.json 스칼라", dict(pkg="0")),
 ("build 스크립트 없음", dict(pkg='{"name":"t"}')),
 ("src 비어있음", dict(src=None)),
 ("문서 filler(ㅋ 반복)", dict()),
]
HONEST = [
 ("KST naive 타임스탬프", dict(captured=datetime.now().isoformat())),
 ("대문자/공백/@2x 파일명", dict(images={"홈 화면 데스크톱@2x.PNG":png(1280,720)},
     qa="# QA\nTypography Spacing Colors Image Copy Interactions Console Build Sites\n"
        "- `홈 화면 데스크톱@2x.PNG` (source, implementation 동일 파일명)\nfinal result: passed\n")),
 ("metrics viewport{w,h}·pathname", dict(metrics=[{"pathname":"/","name":"Example","viewport":{"w":1280,"h":720}}])),
 ("iframe 원격 임베드", dict(src='export const A = () => <iframe src="https://www.youtube.com/embed/x" />;\n')),
 ("주석에 원본 URL 대조", dict(src='// 원본: https://example.com/logo.png\nexport const A = () => <img src="/assets/logo.png" />;\n')),
 ("문서에 원본 문구 \"Pending\" 인용", dict(doc_extra_07=' 상태 배지는 "Pending" / "Shipped"로 표기된다.')),
 ("robots 404 자기소유", dict(auth={"basis":"user-owned","confirmed_by":"site owner (본인)","robots_txt_checked":"not-applicable-owned","robots_txt_url":"https://example.com/robots.txt"}, robots_copy=False)),
]

print(f"{'':4}{'케이스':<40} {'기대':<5} {'실제':<5} 판정")
print("── 위조 (전부 exit 1이어야 함) " + "─"*40)
ok=0
for i,(label,o) in enumerate(FORGE):
    if label=="문서 filler(ㅋ 반복)":
        root=build(f"F{i}",**o)
        for dn in DOCUMENT_NAMES: (root/"문서"/dn).write_text("ㅋ"*1400, encoding="utf-8")
    elif label=="src 비어있음":
        root=build(f"F{i}"); (root/"src/App.tsx").unlink()
    else:
        root=build(f"F{i}",**o)
    rc,out=run(root); good = rc==1; ok+=good
    print(f"    {label:<40} {1:<5} {rc:<5} {'OK' if good else '✘ 통과됨!'}")
    if not good: print("      "+out[:200])
print("── 정직 (전부 exit 0이어야 함) " + "─"*40)
for i,(label,o) in enumerate(HONEST):
    root=build(f"H{i}",**o)
    rc,out=run(root); good = rc==0; ok+=good
    print(f"    {label:<40} {0:<5} {rc:<5} {'OK' if good else '✘ 오탐!'}")
    if not good:
        print("      "+ "\n      ".join(l for l in out.splitlines() if l.startswith("-"))[:500])
print(f"\n{ok}/{len(FORGE)+len(HONEST)} 통과")

# [2026-07-27 추가] 실사용에서 JPEG SOF 오프셋 버그가 잡혔다 — 위 픽스처가 PNG만 써서
# JPEG 치수 경로를 한 번도 검증하지 않았기 때문이다. 포맷별 치수 판독을 직접 고정한다.
def test_image_parsers():
    import importlib, tempfile
    v = importlib.import_module("validate_clone_artifacts")
    importlib.reload(v)
    results = []
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # PNG
        pp = td/"a.png"; pp.write_bytes(png(640, 360))
        results.append(("PNG 640x360", v.read_image_size(pp), (640, 360)))
        # JPEG (PIL로 실제 인코딩) + 큰 COM 세그먼트를 앞에 끼운 변형
        try:
            from PIL import Image
            jp = td/"b.jpg"
            Image.new("RGB", (1200, 875), (238, 238, 238)).save(jp, "JPEG", quality=85)
            results.append(("JPEG 1200x875", v.read_image_size(jp), (1200, 875)))
            raw = jp.read_bytes()
            # COM 세그먼트 길이 필드는 2바이트(최대 65535)라 60KB짜리 2개로 나눠
            # SOF를 옛 65536 고정 창 밖으로 밀어낸다.
            seg = b"\xff\xfe" + (60000 + 2).to_bytes(2, "big") + b"P" * 60000
            padded = td/"c.jpg"; padded.write_bytes(raw[:2] + seg + seg + raw[2:])
            results.append(("JPEG + 70KB COM 패딩", v.read_image_size(padded), (1200, 875)))
        except ImportError:
            results.append(("JPEG (PIL 없음 — 건너뜀)", None, None))
    print("\n── 포맷별 치수 판독 " + "─"*44)
    ok = 0
    for label, got, want in results:
        if want is None:
            print(f"    {label:<40} 건너뜀"); ok += 1; continue
        good = got == want; ok += good
        print(f"    {label:<40} {str(want):<14} {str(got):<14} {'OK' if good else '✘'}")
    return ok, len([r for r in results])

_pok, _ptotal = test_image_parsers()
print(f"\n포맷 판독 {_pok}/{_ptotal} 통과")
