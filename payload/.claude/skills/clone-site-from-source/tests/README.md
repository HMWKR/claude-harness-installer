# 게이트 회귀 스위트

`python3 tests/regression.py` — 23케이스 양방향 회귀. **검증기를 고칠 때마다 돌려라.**

- **위조 16종** (전부 `exit 1`이어야 함): 0바이트/텍스트 이미지, 1×1+0바이트 동거,
  IHDR 껍데기, 1×1 진짜 PNG, metrics `null`/`0`/합성키/빈dict, design-qa가 metrics만 인용,
  `confirmed_by="x"`, robots URL 호스트 불일치, allowed인데 사본 없음, package.json 스칼라,
  build 스크립트 없음, src 비어있음, 문서 filler.
- **정직 7종** (전부 `exit 0`이어야 함): KST naive 타임스탬프, 대문자·공백·`@2x` 파일명,
  `viewport:{w,h}`·`pathname` metrics, YouTube iframe 임베드, 주석의 원본 URL 대조,
  문서 안 원본 문구 `"Pending"` 인용, robots 404인 자기 소유 사이트.

이 스위트의 존재 이유: 2026-07-27 적대 검증에서 게이트가 **위조에 관대하고 정직한 변형에
가혹한**, 방향이 반대로 걸린 상태로 드러났다. 한쪽만 고치면 반대쪽이 무너진다 —
반드시 양방향으로 확인한다.
