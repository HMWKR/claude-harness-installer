#!/usr/bin/env python3
"""ThreeUI 로컬 검색 — Community 메타(community.json) + 사이트 전체 slug 색인(sitemap-index.md).

사용: python3 -I threeui-search.py <검색어...> [--category <카테고리>] [--free|--pro] [--probe] [--limit N] [--json]
  검색어는 모두 포함(AND), 대소문자 무시. id·label·tags·description·runtime·variant 라벨/설명을 본다.
  색인에만 있는 패밀리(Pro 또는 공개 저장소 미동기화)는 slug·변형 id 일치로만 찾는다.
  --probe: 그 패밀리들의 소스 번들 URL을 GET(1바이트)로 확인해 200이면 "Community(최신)"으로 표시한다(요청은 결과 수만큼).
카테고리: Landing Pages, Hero, Three.js, Backgrounds, Buttons, Text Animation, UI Elements, CSS, Motion Design, Sections, 3D Assets
"""
import argparse, json, pathlib, re, sys, urllib.error, urllib.request

HERE = pathlib.Path(__file__).resolve().parent.parent / "catalog"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def probe(url: str) -> int:
    """번들 존재 확인 — GET(Range 1바이트) + JSON content-type. HEAD는 SPA 폴백이 200을 돌려줘 쓰지 않는다(2026-10-16 실측)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "threeui-reference-skill/1.0", "Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            ctype = r.headers.get("Content-Type", "")
            return r.status if "json" in ctype else 404
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("terms", nargs="+")
    ap.add_argument("--category")
    ap.add_argument("--free", action="store_true", help="Community(메타 있음)만")
    ap.add_argument("--pro", action="store_true", help="색인 전용(Pro/미동기화)만")
    ap.add_argument("--probe", action="store_true", help="색인 전용 결과의 번들 URL을 GET으로 확인")
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    terms = [t.lower() for t in a.terms]
    data = json.loads((HERE / "community.json").read_text(encoding="utf-8"))
    hits = []
    if not a.pro:
        for it in data["items"]:
            if a.category and it["category"].lower() != a.category.lower():
                continue
            hay = " ".join([it["id"], it["category"], it.get("label") or "", it.get("description") or "", it.get("runtime") or "",
                            it.get("interaction") or "", " ".join(it.get("tags", [])),
                            " ".join(f"{v['id']} {v['label']} {v.get('description') or ''}" for v in it.get("variants", []))]).lower()
            hayn = norm(hay)
            if all(t in hay or norm(t) in hayn for t in terms):
                score = (sum(3 for t in terms if t in (it.get("label") or "").lower()) + sum(2 for t in terms if t in it["id"])
                         + sum(1 for t in terms if t in " ".join(it.get("tags", [])).lower()))
                hits.append((score, it))
    hits.sort(key=lambda x: -x[0])
    index_hits = []
    if not a.free:
        idx = (HERE / "sitemap-index.md").read_text(encoding="utf-8")
        section = None
        community_ids = {it["id"] for it in data["items"]}
        for line in idx.splitlines():
            m = re.match(r"^## /([a-z0-9-]+)", line)
            if m:
                section = m.group(1)
                continue
            m = re.match(r"^- `([a-z0-9-]+)`(\s*\[C\])?(?: — 변형 \d+: (.*))?$", line)
            if not m or not section:
                continue
            fam, is_c, variants = m.group(1), bool(m.group(2)), (m.group(3) or "")
            if is_c or fam in community_ids:
                continue
            if a.category and norm(a.category) not in (norm(section), norm(section.replace("-js", ".js"))):
                continue
            hay = f"{fam} {variants}".lower()
            if all(norm(t) in norm(hay) for t in terms):
                index_hits.append({"id": fam, "section": section, "url": f"https://threeui.com/{section}/{fam}",
                                   "bundle": f"https://threeui.com/source-code/{fam}.json",
                                   "variants": [v.strip() for v in variants.split(",") if v.strip()]})
        if a.probe:
            for h in index_hits[:a.limit]:
                h["bundle_status"] = probe(h["bundle"])
    if a.json:
        print(json.dumps({"community": [h for _, h in hits[:a.limit]], "index_only": index_hits[:a.limit]}, ensure_ascii=False, indent=1))
        return
    print(f"# Community (무료·MIT·소스 번들 공개) — {len(hits)}건" + (f", 상위 {a.limit}" if len(hits) > a.limit else ""))
    for _, it in hits[:a.limit]:
        vs = [v["id"] for v in it.get("variants", [])]
        print(f"- {it['label']}  [{it['category']}]  {it['url']}")
        print(f"    runtime: {it.get('runtime')} · tags: {', '.join(it.get('tags', [])[:8])}" + (f" · variants: {', '.join(vs)}" if vs else ""))
        print(f"    {(it.get('description') or '')[:160]}")
        print(f"    fetch: threeui-fetch.sh {it['id']}" + (f" --variant <{vs[0]}|...>" if vs else ""))
    print(f"\n# 색인 전용 — Pro 또는 공개 저장소 미동기화(slug 일치만) — {len(index_hits)}건" + (f", 상위 {a.limit}" if len(index_hits) > a.limit else "")
          + ("" if a.probe else " · `--probe`로 번들 200 여부 확인"))
    for h in index_hits[:a.limit]:
        st = h.get("bundle_status")
        mark = "" if st is None else ("  → 번들 200: Community(최신, 미동기화) — threeui-fetch.sh 가능" if st in (200, 206) else f"  → 번들 {st}: Pro(미리보기만)")
        print(f"- {h['id']}  [/{h['section']}]  {h['url']}" + (f"  variants: {', '.join(h['variants'])}" if h['variants'] else "") + mark)


if __name__ == "__main__":
    main()
