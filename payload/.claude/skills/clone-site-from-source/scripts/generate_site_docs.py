#!/usr/bin/env python3
"""Generate evidence-grounded Markdown documentation scaffolds for a clone run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DOCUMENT_NAMES = (
    "00-문서-목록.md",
    "01-사이트-개요.md",
    "02-정보구조.md",
    "03-유저-플로우.md",
    "04-화면-상태-목록.md",
    "05-디자인-디테일.md",
    "06-반응형-규칙.md",
    "07-콘텐츠-에셋.md",
    "08-인터랙션-접근성.md",
    "09-기술-구현-메모.md",
    "10-누락-가정-리스크.md",
    "11-크롤링-보고서.md",
    "12-원본-대비-차이.md",
    "13-SEO-성능-보안-준수.md",
    "14-UX-전략-인기-성공요인.md",
    "15-역할-JTBD-사용자-여정.md",
    "16-서비스-퍼널-성장-루프.md",
    "17-상세-유저플로우-상태-복구.md",
    "18-디자인-UX-원리-평가.md",
    "19-서비스-경험-감사-리스크-개선.md",
    "20-기능-상태-테스트-매트릭스.md",
    "21-UX-근거-출처-레지스터.md",
)

PLACEHOLDER = "<!-- 작성 필요: 원본 캡처와 DOM 증거를 근거로 이 절을 완성하세요. -->"
DEEP_UX_DOCUMENT_NAMES = DOCUMENT_NAMES[14:]
EVIDENCE_LABELS = ("[확인]", "[강한 추론]", "[검증 필요]", "[확인 불가]")
DEEP_UX_REQUIRED_HEADINGS = {
    "14-UX-전략-인기-성공요인.md": (
        "근거 표기",
        "결론",
        "실제 인기와 성장 신호",
        "무엇을 특히 잘했는가",
        "인기의 실제 구조",
        "반대 근거와 설명 한계",
        "성공 요인과 부작용",
        "최종 평가",
    ),
    "15-역할-JTBD-사용자-여정.md": (
        "서비스가 해결하는 상위 문제",
        "역할 인벤토리",
        "JTBD",
        "전체 사용자 여정",
        "역할별 상세 여정",
        "감정 여정",
        "서비스 블루프린트",
        "핵심 성공 지표",
        "확인하지 못한 핵심 질문",
    ),
    "16-서비스-퍼널-성장-루프.md": (
        "북극성 가치",
        "AARRR 퍼널",
        "핵심 성장 루프",
        "전환 설계 지도",
        "루프가 끊기는 지점",
        "측정 이벤트 설계",
        "추천 메트릭 트리",
        "가드레일 지표",
        "최종 평가",
    ),
    "17-상세-유저플로우-상태-복구.md": (
        "증거 규칙",
        "상위 서비스 구조",
        "핵심 플로우 인벤토리",
        "플로우별 상세 명세",
        "작업 상태 머신",
        "핵심 상태와 실패 범위",
        "관리자와 운영자 흐름",
        "복구 UX 원칙",
        "추가 검증 우선순위",
    ),
    "18-디자인-UX-원리-평가.md": (
        "디자인 전략 요약",
        "핵심 디자인 원리",
        "정보구조 평가",
        "화면별 UX 역할",
        "인지 부하 평가",
        "콘텐츠 디자인 평가",
        "행동과 설득 디자인",
        "다크 패턴 위험 감사",
        "접근성 관점",
        "휴리스틱 평가",
        "모방할 가치가 있는 원칙",
        "그대로 모방하면 안 되는 부분",
        "최종 평가",
    ),
    "19-서비스-경험-감사-리스크-개선.md": (
        "감사 상태와 한계",
        "프로젝트 분류",
        "역할 범위",
        "인터페이스와 서비스 접점",
        "상세 발견",
        "마찰 지점",
        "관리자와 운영자 경험",
        "빠진 가능성이 높은 기능",
        "교차 위험",
        "우선순위 로드맵",
        "역할별 인계 요구",
        "최종 판정",
    ),
    "20-기능-상태-테스트-매트릭스.md": (
        "판정 기준",
        "핵심 기능 테스트",
        "상태와 실패 커버리지",
        "접근성 검증표",
        "반응형 검증표",
        "성능 검증",
        "출시 전 체크리스트",
        "최소 회귀 스위트",
        "현재 결론",
    ),
    "21-UX-근거-출처-레지스터.md": (
        "증거 계층",
        "직접 관찰한 현재 공개 화면",
        "로컬 근거",
        "외부 핵심 출처",
        "수치 불일치와 해석",
        "확정할 수 있는 것",
        "확정할 수 없는 것",
        "사용자 게시물의 취급",
        "분석 방법",
        "추가로 필요한 근거",
        "문서별 근거 연결",
        "최종 근거 판정",
    ),
}


def load_manifest(project_root: Path) -> dict:
    manifest_path = project_root / "clone-source.json"
    if not manifest_path.is_file():
        raise SystemExit(f"missing clone-source.json: {manifest_path}")
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"invalid clone-source.json: {error}") from error


def templates(manifest: dict) -> dict[str, str]:
    site_name = str(manifest.get("site_name", "Site"))
    source_url = str(manifest.get("source_url", ""))
    routes = manifest.get("routes", [])
    route_list = "\n".join(f"- `{route}`" for route in routes) or "- `/`"
    common = f"- 사이트: **{site_name}**\n- 원본: `{source_url}`\n- 근거 루트: `qa/source/`\n"
    evidence_guide = """- `[확인]`: 현재 공개 화면·DOM·자산·로컬 산출물 또는 날짜가 있는 권위 자료로 직접 확인
- `[강한 추론]`: 복수의 관찰이 지지하지만 직접 선언되지는 않은 해석
- `[검증 필요]`: 분석·인증 접근·사용자 조사·추가 출처가 필요한 가설
- `[확인 불가]`: 인증·백엔드·운영·상업·과거 데이터가 없어 확인할 수 없는 범위"""

    return {
        "00-문서-목록.md": f"""# {site_name} 크롤링 문서 목록

{common}
## 목적

이 디렉터리는 원본 사이트의 구조, 사용자 흐름, 디자인 규칙, 상호작용, 구현 판단, 확인하지 못한 영역을 재현 가능한 형태로 기록한다.

## 문서 상태

| 문서 | 다루는 내용 | 상태 |
| --- | --- | --- |
| 01-사이트-개요 | 목적, 대상 사용자, 가치 제안, 범위 | {PLACEHOLDER} |
| 02-정보구조 | 내비게이션, 페이지 계층, 콘텐츠 구조 | {PLACEHOLDER} |
| 03-유저-플로우 | 주요 목표별 진입·분기·완료 흐름 | {PLACEHOLDER} |
| 04-화면-상태-목록 | 화면, 컴포넌트, 상태, 증거 경로 | {PLACEHOLDER} |
| 05-디자인-디테일 | 타이포, 색상, 간격, 표면, 이미지, 모션 | {PLACEHOLDER} |
| 06-반응형-규칙 | 데스크톱·태블릿·모바일 변화 | {PLACEHOLDER} |
| 07-콘텐츠-에셋 | 카피, 이미지, SVG, 폰트, 영상 | {PLACEHOLDER} |
| 08-인터랙션-접근성 | 조작 방식, 키보드, 포커스, 의미 구조 | {PLACEHOLDER} |
| 09-기술-구현-메모 | 로컬 구현 구조와 백엔드 경계 | {PLACEHOLDER} |
| 10-누락-가정-리스크 | 미확인 영역, 추정, 검증 방법 | {PLACEHOLDER} |
| 11-크롤링-보고서 | URL, 상태, 캡처, 자산, 측정 결과 | {PLACEHOLDER} |
| 12-원본-대비-차이 | 원본과 로컬 구현의 시각·동작·기술 차이 | {PLACEHOLDER} |
| 13-SEO-성능-보안-준수 | 메타데이터, 성능, 개인정보, 보안, 법적 경계 | {PLACEHOLDER} |
| 14-UX-전략-인기-성공요인 | UX 전략, 인기·성장 근거, 성공 요인과 반대 근거 | {PLACEHOLDER} |
| 15-역할-JTBD-사용자-여정 | 역할, JTBD, 전체 여정, 감정과 서비스 블루프린트 | {PLACEHOLDER} |
| 16-서비스-퍼널-성장-루프 | AARRR, 전환, 성장 루프, 이벤트와 가드레일 | {PLACEHOLDER} |
| 17-상세-유저플로우-상태-복구 | 단계·분기·상태·실패·복구·운영자 흐름 | {PLACEHOLDER} |
| 18-디자인-UX-원리-평가 | 디자인 원리, 인지 부하, 설득·접근성·휴리스틱 | {PLACEHOLDER} |
| 19-서비스-경험-감사-리스크-개선 | 전체 접점 감사, 마찰, 위험, 개선 로드맵 | {PLACEHOLDER} |
| 20-기능-상태-테스트-매트릭스 | 기능·상태·접근성·반응형·성능 회귀 검증 | {PLACEHOLDER} |
| 21-UX-근거-출처-레지스터 | 관찰 근거, 외부 출처, 충돌과 주장 한계 | {PLACEHOLDER} |
""",
        "01-사이트-개요.md": f"""# {site_name} 사이트 개요

{common}
## 한 문장 정의

{PLACEHOLDER}

## 핵심 가치 제안

{PLACEHOLDER}

## 주요 사용자와 사용 맥락

{PLACEHOLDER}

## 사용자가 달성하려는 목표

{PLACEHOLDER}

## 공개 범위와 인증 경계

{PLACEHOLDER}

## 수집된 경로

{route_list}

## 관찰 근거

{PLACEHOLDER}
""",
        "02-정보구조.md": f"""# {site_name} 정보구조

{common}
## 사이트맵

{route_list}

## 전역 내비게이션

{PLACEHOLDER}

## 페이지별 콘텐츠 계층

{PLACEHOLDER}

## 공통 헤더·푸터·지속 UI

{PLACEHOLDER}

## URL·쿼리·해시가 표현하는 상태

{PLACEHOLDER}

## 정보구조 근거

{PLACEHOLDER}
""",
        "03-유저-플로우.md": f"""# {site_name} 유저 플로우

{common}
## 플로우 작성 원칙

관찰된 화면과 안전하게 실행한 상호작용만 확정 사실로 기록한다. 로그인 뒤나 외부 쓰기가 필요한 단계는 경계로 표시한다.

## 핵심 플로우 목록

{PLACEHOLDER}

## 플로우 1 — 주요 사용자 목표

- 사용자/상황: {PLACEHOLDER}
- 진입점: {PLACEHOLDER}
- 완료 조건: {PLACEHOLDER}
- 단계별 경로: {PLACEHOLDER}
- 분기·되돌아가기: {PLACEHOLDER}
- 로딩·빈값·오류 상태: {PLACEHOLDER}
- 인증·외부 서비스 경계: {PLACEHOLDER}
- 캡처 근거: {PLACEHOLDER}

```mermaid
flowchart TD
    A[진입] --> B[관찰된 첫 단계]
    B --> C{{분기}}
    C --> D[완료]
    C --> E[오류 또는 경계]
```

## 보조 플로우와 이탈 경로

{PLACEHOLDER}

## 확인하지 못한 플로우

{PLACEHOLDER}
""",
        "04-화면-상태-목록.md": f"""# {site_name} 화면·상태 목록

{common}
## 화면 인벤토리

| 경로/화면 | 목적 | 주요 영역 | 데스크톱 증거 | 모바일 증거 |
| --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |

## 컴포넌트와 상태

| 컴포넌트 | 기본 | Hover/Focus | 선택/열림 | 빈값/오류/성공 | 근거 |
| --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |

## 지속 UI와 스크롤 변화

{PLACEHOLDER}

## 로컬 재현 범위

{PLACEHOLDER}
""",
        "05-디자인-디테일.md": f"""# {site_name} 디자인 디테일

{common}
## 디자인 언어 요약

{PLACEHOLDER}

## 타이포그래피

- 폰트 패밀리·fallback: {PLACEHOLDER}
- 크기·굵기·행간·자간 계층: {PLACEHOLDER}
- 줄바꿈·말줄임 규칙: {PLACEHOLDER}

## 색상과 토큰

| 역할 | 값 | 사용 위치 | 근거 |
| --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |

## 간격·그리드·레이아웃 리듬

{PLACEHOLDER}

## 표면·테두리·반경·그림자

{PLACEHOLDER}

## 로고·아이콘·이미지·영상

{PLACEHOLDER}

## 모션·전환·커서

{PLACEHOLDER}

## 디자인 예외와 특수 상태

{PLACEHOLDER}
""",
        "06-반응형-규칙.md": f"""# {site_name} 반응형 규칙

{common}
## 관찰한 뷰포트

{PLACEHOLDER}

## 브레이크포인트별 변화

| 영역 | 데스크톱 | 태블릿/중간 | 모바일 | 근거 |
| --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |

## 내비게이션 변화

{PLACEHOLDER}

## 그리드·정렬·순서 변화

{PLACEHOLDER}

## 타이포·간격·이미지 변화

{PLACEHOLDER}

## 고정 요소와 오버플로

{PLACEHOLDER}
""",
        "07-콘텐츠-에셋.md": f"""# {site_name} 콘텐츠·에셋

{common}
## 핵심 메시지와 보조 카피

{PLACEHOLDER}

## CTA·레이블·상태 문구

{PLACEHOLDER}

## 에셋 인벤토리

| 유형 | 원본 URL/위치 | 로컬 경로 | 크기/형식 | 복사/대체 | 근거 |
| --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |

## 폰트와 아이콘 출처

{PLACEHOLDER}

## 영상·썸네일·지연 로딩

{PLACEHOLDER}

## 로컬화하지 못한 에셋

{PLACEHOLDER}
""",
        "08-인터랙션-접근성.md": f"""# {site_name} 인터랙션·접근성

{common}
## 주요 조작 목록

{PLACEHOLDER}

## 키보드·포커스·Escape

{PLACEHOLDER}

## 의미 구조와 레이블

{PLACEHOLDER}

## 대비·텍스트 확대·탭 영역

{PLACEHOLDER}

## 모션 감소와 상태 알림

{PLACEHOLDER}

## 접근성 차이와 로컬 보완

{PLACEHOLDER}
""",
        "09-기술-구현-메모.md": f"""# {site_name} 기술·구현 메모

{common}
## 원본 기술 단서

{PLACEHOLDER}

## DOM·CSS·자산 이식 전략

{PLACEHOLDER}

## 로컬 라우팅과 상태 관리

{PLACEHOLDER}

## 백엔드·인증·외부 쓰기 대체

{PLACEHOLDER}

## 제거한 스크립트·추적·네트워크 연결

{PLACEHOLDER}

## 빌드·Sites·테스트 구조

{PLACEHOLDER}
""",
        "10-누락-가정-리스크.md": f"""# {site_name} 누락·가정·리스크

{common}
## 확인하지 못한 화면과 상태

{PLACEHOLDER}

## 명시적 가정

| 가정 | 이유 | 영향 | 확인 방법 | 상태 |
| --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |

## 로그인·결제·생성·외부 서비스 경계

{PLACEHOLDER}

## 디자인·콘텐츠·기술 리스크

{PLACEHOLDER}

## 후속 검증 우선순위

{PLACEHOLDER}
""",
        "11-크롤링-보고서.md": f"""# {site_name} 크롤링 보고서

{common}
## 실행 요약

{PLACEHOLDER}

## URL 결과

| 요청 URL | 최종 URL | 상태 | 제목 | H1 | 비고 |
| --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |

## 캡처·DOM·스타일 수집량

{PLACEHOLDER}

## 자산 복사 결과

{PLACEHOLDER}

## 데스크톱·모바일 측정 결과

{PLACEHOLDER}

## 상호작용 검증 결과

{PLACEHOLDER}

## 콘솔·빌드·QA 결과

{PLACEHOLDER}
""",
        "12-원본-대비-차이.md": f"""# {site_name} 원본 대비 차이

{common}
## 비교 기준

원본 캡처, 로컬 구현 캡처, 오버레이 또는 정량 지표를 같은 뷰포트와 상태에서 비교한다. 관찰할 수 없는 서버 동작은 시각적 차이와 분리한다.

## 차이 목록

| ID | 경로·상태 | 영역 | 원본 | 로컬 | 영향 | 근거 | 처리 상태 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |  |  |

## 시각적 차이

{PLACEHOLDER}

## 상호작용·상태 차이

{PLACEHOLDER}

## 콘텐츠·에셋 차이

{PLACEHOLDER}

## 기술·백엔드 경계로 인한 차이

{PLACEHOLDER}

## 허용된 차이와 남은 수정 우선순위

{PLACEHOLDER}
""",
        "13-SEO-성능-보안-준수.md": f"""# {site_name} SEO·성능·보안·준수

{common}
## SEO·메타데이터·공유 카드

문서 제목, description, canonical, robots, sitemap, Open Graph, Twitter 카드, 구조화 데이터, 언어·지역 메타를 기록한다.

{PLACEHOLDER}

## 성능·네트워크·로딩 전략

핵심 자산 크기, 요청 수, 폰트·이미지·영상 로딩, 캐시, 지연 로딩, 레이아웃 이동과 관찰한 성능 지표를 기록한다.

{PLACEHOLDER}

## 보안·개인정보·추적

공개 페이지에서 관찰된 쿠키, 분석·광고·추적 스크립트, 입력 지점, 외부 전송, CSP·보안 헤더 단서를 기록한다. 민감 정보나 인증을 우회하지 않는다.

{PLACEHOLDER}

## 법적 고지·저작권·라이선스

약관, 개인정보처리방침, 쿠키 고지, 상표·저작권·에셋 라이선스와 클론에서 재사용할 수 없는 항목을 기록한다.

{PLACEHOLDER}

## 브라우저·기기 호환성과 운영 관찰성

브라우저 차이, 폴백, 오류 로깅, 분석 이벤트, 모니터링 단서와 로컬 구현의 운영 범위를 기록한다.

{PLACEHOLDER}
""",
        "14-UX-전략-인기-성공요인.md": f"""# {site_name} UX 전략·인기·성공 요인

{common}
## 근거 표기

{evidence_guide}

모든 주요 판단에 위 표기를 붙이고, 인기·성장·성과 수치는 출처 날짜와 접근 날짜를 함께 기록한다.

## 결론

제품이 누구의 어떤 문제를 어떤 경험 구조로 해결하는지, 핵심 강점과 가장 큰 제약을 한 문단으로 요약한다.

{PLACEHOLDER}

## 실제 인기와 성장 신호

| 주장/수치 | 값·기간 | 출처·발행일 | 접근일 | 신뢰 수준 | 한계 |
| --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |

## 무엇을 특히 잘했는가

| UX 선택 | 사용자에게 주는 효과 | 작동 메커니즘 | 근거 | 반대 효과 |
| --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |

## 인기의 실제 구조

획득, 첫 가치, 반복 사용, 공유, 수익화, 생태계 요인이 어떻게 연결되는지 설명하고 인과와 상관을 구분한다.

{PLACEHOLDER}

## 반대 근거와 설명 한계

UX만으로 설명할 수 없는 모델 성능, 가격, 유통, 브랜드, 시기, 파트너십과 시장 환경을 분리한다.

{PLACEHOLDER}

## 성공 요인과 부작용

| 성공 요인 | 긍정 효과 | 비용·위험 | 영향을 받는 사용자 | 검증 방법 |
| --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |

## 최종 평가

{PLACEHOLDER}
""",
        "15-역할-JTBD-사용자-여정.md": f"""# {site_name} 역할·JTBD·사용자 여정

{common}
## 근거 표기

{evidence_guide}

## 서비스가 해결하는 상위 문제

{PLACEHOLDER}

## 역할 인벤토리

| 역할 | 상황·숙련도 | 목표 | 핵심 과업 | 불안·제약 | 관찰 근거 |
| --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |

방문자, 신규 사용자, 반복 사용자, 파워 유저, 팀/구매자, 개발자/통합자, 운영자/지원/모더레이터를 적용 가능성에 따라 포함한다.

## JTBD

| 역할 | 상황(When) | 동기(I want to) | 기대 결과(So I can) | 기능적·감정적·사회적 결과 | 성공 신호 |
| --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |

## 전체 사용자 여정

발견 → 가치 이해 → 온보딩 → 첫 가치 → 반복/완성 → 내보내기/공유 → 재방문 → 업그레이드/해지/복구를 연결한다.

{PLACEHOLDER}

## 역할별 상세 여정

| 단계 | 행동 | 화면·접점 | 기대 | 마찰 | 상태·분기 | 근거 | 개선 기회 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |  |  |

## 감정 여정

| 단계 | 예상 감정 | 감정의 원인 | 위험 신호 | 지원 장치 | 측정 방법 |
| --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |

## 서비스 블루프린트

| 사용자 행동 | 전면 UI | 후면 시스템 | 운영자·지원 | 정책·데이터 | 실패·복구 |
| --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |

## 핵심 성공 지표

{PLACEHOLDER}

## 확인하지 못한 핵심 질문

{PLACEHOLDER}
""",
        "16-서비스-퍼널-성장-루프.md": f"""# {site_name} 서비스 퍼널·성장 루프

{common}
## 근거 표기

{evidence_guide}

현재 수치가 아니라 관찰 가능한 전환 설계와 검증해야 할 이벤트를 기록한다.

## 북극성 가치

사용자 가치 단위, 선행 지표, 결과 지표, 품질 가드레일을 구분한다.

{PLACEHOLDER}

## AARRR 퍼널

| 단계 | 사용자 의도 | 진입·화면 | 핵심 행동 | 완료 이벤트 | 이탈 위험 | 복구/실험 |
| --- | --- | --- | --- | --- | --- | --- |
| 획득 | {PLACEHOLDER} |  |  |  |  |  |
| 활성화 |  |  |  |  |  |  |
| 유지 |  |  |  |  |  |  |
| 추천 |  |  |  |  |  |  |
| 수익 |  |  |  |  |  |  |

## 핵심 성장 루프

콘텐츠, 공유/추천, 템플릿·리믹스, 커뮤니티, 통합/생태계 루프를 적용 가능성에 따라 설명한다.

{PLACEHOLDER}

## 전환 설계 지도

| 전환 | 촉발 신호 | 가치 약속 | 마찰 | 신뢰 장치 | 성공·가드레일 지표 |
| --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |

## 루프가 끊기는 지점

{PLACEHOLDER}

## 측정 이벤트 설계

| 이벤트 | 트리거 | 필수 속성 | 사용자 가치 가설 | 개인정보 주의 | QA 방법 |
| --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |

## 추천 메트릭 트리

{PLACEHOLDER}

## 가드레일 지표

품질, 실패율, 시간·비용, 취소/환불, 불만, 접근성, 안전, 저작권, 운영 부담을 포함한다.

{PLACEHOLDER}

## 최종 평가

{PLACEHOLDER}
""",
        "17-상세-유저플로우-상태-복구.md": f"""# {site_name} 상세 유저 플로우·상태·복구

{common}
## 증거 규칙

{evidence_guide}

## 상위 서비스 구조

```mermaid
flowchart TD
    A[발견과 진입] --> B[가치 이해와 선택]
    B --> C[핵심 작업]
    C --> D{{결과 판정}}
    D -->|성공| E[완성·저장·공유]
    D -->|실패| F[오류 이해·수정·재시도]
    E --> G[재방문·확장·업그레이드]
```

{PLACEHOLDER}

## 핵심 플로우 인벤토리

| ID | 역할·목표 | 진입점 | 주요 경로 | 완료 조건 | 경계 | 근거 |
| --- | --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |  |

## 플로우별 상세 명세

각 플로우마다 배우·상황·전제, 단계·화면·컨트롤, 결정·분기·되돌아가기, 시스템 피드백, 완료·이탈, 로딩·빈값·오류·권한·할당량, 복구·지원, 모바일·키보드 차이, 증거와 검증 방법을 기록한다.

{PLACEHOLDER}

## 작업 상태 머신

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Editing
    Editing --> Validating
    Validating --> Running
    Validating --> Invalid
    Invalid --> Editing
    Running --> Success
    Running --> Failed
    Failed --> Editing
    Failed --> Running: retry
    Success --> Refining
    Refining --> Running
```

{PLACEHOLDER}

## 핵심 상태와 실패 범위

| 기능/화면 | 기본 | 로딩 | 빈값 | 성공 | 오류 | 권한/할당량 | 복구 | 증거 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |  |  |  |

## 관리자와 운영자 흐름

모더레이션, 지원, 환불/청구, 장애 대응, 콘텐츠·정책 관리, 감사 로그에서 관찰 가능한 것과 확인 불가한 것을 분리한다.

{PLACEHOLDER}

## 복구 UX 원칙

{PLACEHOLDER}

## 추가 검증 우선순위

{PLACEHOLDER}
""",
        "18-디자인-UX-원리-평가.md": f"""# {site_name} 디자인·UX 원리 평가

{common}
## 근거 표기

{evidence_guide}

## 디자인 전략 요약

{PLACEHOLDER}

## 핵심 디자인 원리

| 원리 | 구현 방식 | 사용자 효과 | 근거 | 예외·비용 |
| --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |

## 정보구조 평가

경로 구조, 전역·지역 내비게이션, 라벨, 탐색성, 깊이, 중복, 목적 기반 묶음을 평가한다.

{PLACEHOLDER}

## 화면별 UX 역할

| 화면/영역 | 사용자 질문 | 주 행동 | 시각적 우선순위 | 다음 단계 | 근거 |
| --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |

## 인지 부하 평가

{PLACEHOLDER}

## 콘텐츠 디자인 평가

용어, 라벨, 도움말, 오류·빈값·성공 문구, 가격·제약 설명, 지역화 가능성을 평가한다.

{PLACEHOLDER}

## 행동과 설득 디자인

{PLACEHOLDER}

## 다크 패턴 위험 감사

강제 지속, 숨은 비용, 오도된 긴급성, 기본 선택, 해지 마찰, 개인정보·동의, 사회적 압박을 확인한다.

{PLACEHOLDER}

## 접근성 관점

{PLACEHOLDER}

## 휴리스틱 평가

| 원칙 | 판정 | 발견 | 사용자 영향 | 근거 | 개선 |
| --- | --- | --- | --- | --- | --- |
| 시스템 상태 가시성 | {PLACEHOLDER} |  |  |  |  |

## 모방할 가치가 있는 원칙

{PLACEHOLDER}

## 그대로 모방하면 안 되는 부분

{PLACEHOLDER}

## 최종 평가

{PLACEHOLDER}
""",
        "19-서비스-경험-감사-리스크-개선.md": f"""# {site_name} 서비스 경험 감사·리스크·개선

{common}
## 근거 표기

{evidence_guide}

## 감사 상태와 한계

감사한 경로·역할·뷰포트·상태·기간, 인증 및 백엔드 경계, 확인할 수 없는 영역을 선언한다.

{PLACEHOLDER}

## 프로젝트 분류

{PLACEHOLDER}

## 역할 범위

{PLACEHOLDER}

## 인터페이스와 서비스 접점

| 접점 | 사용자 역할 | 목적 | 연결 시스템/운영 | 관찰 상태 | 근거 |
| --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |

## 상세 발견

| ID | 우선순위 | 경로·상태 | 발견 | 사용자 영향 | 근거 | 권고 |
| --- | --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |  |

## 마찰 지점

{PLACEHOLDER}

## 관리자와 운영자 경험

{PLACEHOLDER}

## 빠진 가능성이 높은 기능

관찰되지 않았다는 이유만으로 부재를 확정하지 말고 필요성, 추론 근거, 검증 방법을 기록한다.

{PLACEHOLDER}

## 교차 위험

신뢰·가격·개인정보·안전·모더레이션·저작권·지원·접근성·성능·운영 위험을 연결한다.

{PLACEHOLDER}

## 우선순위 로드맵

| 우선순위 | 문제 | 제안 | 사용자 영향 | 소유 역할 | 의존성 | 성공 지표 | 검증 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P0/P1/P2/P3 | {PLACEHOLDER} |  |  |  |  |  |  |

## 역할별 인계 요구

{PLACEHOLDER}

## 최종 판정

{PLACEHOLDER}
""",
        "20-기능-상태-테스트-매트릭스.md": f"""# {site_name} 기능·상태·테스트 매트릭스

{common}
## 근거 표기

{evidence_guide}

## 판정 기준

통과, 실패, 차단, 미관찰을 정의하고 원본 관찰과 로컬 클론 검증을 분리한다.

{PLACEHOLDER}

## 핵심 기능 테스트

| ID | 경로·기능 | 전제 | 절차 | 기대 결과 | 데스크톱 | 모바일 | 근거 | 상태 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |  |  |  |

## 상태와 실패 커버리지

| 기능 | 기본 | 로딩 | 빈값 | 검증 오류 | 네트워크 오류 | 권한/할당량 | 재시도·복구 | 상태 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |  |  |  |

## 접근성 검증표

{PLACEHOLDER}

## 반응형 검증표

{PLACEHOLDER}

## 성능 검증

{PLACEHOLDER}

## 출시 전 체크리스트

- [ ] 경로 직접 접근과 뒤로/앞으로 이동
- [ ] 핵심 상호작용과 오류·복구
- [ ] 키보드·포커스·Escape·감소된 모션
- [ ] 모바일 오버플로와 탭 영역
- [ ] 콘솔 오류·경고
- [ ] 빌드·Sites 테스트·아티팩트 검증

{PLACEHOLDER}

## 최소 회귀 스위트

{PLACEHOLDER}

## 현재 결론

{PLACEHOLDER}
""",
        "21-UX-근거-출처-레지스터.md": f"""# {site_name} UX 근거·출처 레지스터

{common}
## 증거 계층

{evidence_guide}

직접 관찰, 로컬 산출물, 공식 자료, 권위 있는 2차 자료, 사용자 게시물을 구분하며 낮은 등급의 근거로 높은 등급의 주장을 대체하지 않는다.

## 직접 관찰한 현재 공개 화면

| ID | 경로·상태 | 뷰포트 | 관찰 내용 | 스크린샷/DOM/메트릭 | 접근일 | 신뢰 |
| --- | --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |  |

## 로컬 근거

| ID | 산출물 경로 | 뒷받침하는 주장 | 생성·검증 방법 | 한계 |
| --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |

## 외부 핵심 출처

| ID | 제목·발행자 | URL | 발행일 | 접근일 | 뒷받침하는 주장 | 신뢰·한계 |
| --- | --- | --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |  |  |

## 수치 불일치와 해석

{PLACEHOLDER}

## 확정할 수 있는 것

{PLACEHOLDER}

## 확정할 수 없는 것

{PLACEHOLDER}

## 사용자 게시물의 취급

개별 경험과 시장 전체 사실을 구분하고 대표성, 시점, 이해관계, 재현 가능성을 기록한다.

{PLACEHOLDER}

## 분석 방법

{PLACEHOLDER}

## 추가로 필요한 근거

{PLACEHOLDER}

## 문서별 근거 연결

| 문서 | 핵심 주장 | 근거 ID | 반대 근거 | 확인 수준 |
| --- | --- | --- | --- | --- |
| {PLACEHOLDER} |  |  |  |  |

## 최종 근거 판정

{PLACEHOLDER}
""",
    }


def generate_docs(project_root: Path, force: bool = False) -> list[Path]:
    project_root = project_root.expanduser().resolve()
    if project_root.parent.name != "크롤링":
        raise SystemExit("project root must be <execution-root>/크롤링/<SiteName>")
    manifest = load_manifest(project_root)
    docs_root = project_root / "문서"
    docs_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, content in templates(manifest).items():
        path = docs_root / name
        if path.exists() and not force:
            raise SystemExit(f"refusing to overwrite existing document: {path}")
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    written = generate_docs(args.project_root, force=args.force)
    print(f"Generated {len(written)} site documents in {written[0].parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
