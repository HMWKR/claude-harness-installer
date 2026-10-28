#!/usr/bin/env python3
"""ThreeUI 카탈로그 생성기 — 네트워크 2회(sitemap.xml, GitHub raw shaders.tsx) → catalog/community.json + catalog/sitemap-index.md.

사용: python3 -I build-catalog.py [--out <catalog 폴더>]
  community.json : Community(무료·MIT) 항목 메타(id·category·label·tags·description·runtime·importName·variants·sourceFiles)
  sitemap-index.md: 사이트 전체(Community+Pro) 섹션 → 패밀리 → 변형 URL 색인
Pro 항목의 메타는 공개 저장소에 없다 — 색인의 slug만 있고, 상세는 사이트에서 본다.
"""
import argparse, collections, datetime, json, pathlib, re, sys, urllib.request

SITEMAP = "https://threeui.com/sitemap.xml"
SHADERS_TSX = "https://raw.githubusercontent.com/MengTo/threeui/main/src/data/shaders.tsx"
SECTIONS = ["landing-pages", "hero", "three-js", "backgrounds", "buttons", "text-animation",
            "ui-elements", "css", "motion-design", "3d-assets", "sections"]


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "threeui-reference-skill/1.0 (catalog refresh)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def extract_json_objects(ts: str):
    """shaders.tsx 안의 `{ ...{ <JSON> }` 블록을 중괄호 짝으로 잘라 json.loads 한다."""
    out, i, n = [], 0, len(ts)
    marker = "{ ...{"
    while True:
        i = ts.find(marker, i)
        if i < 0:
            break
        start = i + len(marker) - 1  # points at the inner '{'
        depth, j, in_str, esc = 0, start, False, False
        while j < n:
            c = ts[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        break
            j += 1
        block = ts[start:j + 1]
        try:
            out.append(json.loads(block))
        except json.JSONDecodeError as e:
            print(f"warn: JSON block at {start} skipped: {e}", file=sys.stderr)
        i = j + 1
    return out


def category_segment(category: str) -> str:
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", re.sub(r"\.js\b", "-js", category.lower())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(pathlib.Path(__file__).resolve().parent.parent / "catalog"))
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()

    # 1) sitemap index (Community + Pro)
    xml = fetch(SITEMAP)
    paths = [u.replace("https://threeui.com", "") for u in re.findall(r"<loc>(https://threeui\.com[^<]*)</loc>", xml)]
    sections = collections.OrderedDict()
    for p in paths:
        parts = p.strip("/").split("/")
        if len(parts) < 2 or parts[0] not in SECTIONS:
            continue
        fam = parts[1]
        var = parts[2] if len(parts) > 2 else None
        sections.setdefault(parts[0], collections.OrderedDict()).setdefault(fam, []).append(var)

    # 2) community metadata
    ts = fetch(SHADERS_TSX)
    objs = [o for o in extract_json_objects(ts) if isinstance(o, dict) and "id" in o and "category" in o]
    by_id = {o["id"]: o for o in objs}
    community = []
    for o in objs:
        if o.get("variantOf"):
            continue  # 변형 레코드는 부모 아래에 둔다
        cat_seg = category_segment(o["category"])
        item = {
            "id": o["id"],
            "category": o["category"],
            "url": f"https://threeui.com/{cat_seg}/{o['id']}",
            "bundle": f"https://threeui.com/source-code/{o['id']}.json",
            "label": o.get("label"),
            "importName": o.get("importName"),
            "runtime": o.get("runtime"),
            "tags": o.get("tags", []),
            "description": o.get("description"),
            "interaction": o.get("interaction"),
            "asset": o.get("asset"),
            "sourceCommit": o.get("sourceCommit"),
            "sourceFiles": o.get("sourceFiles", []),
            "variants": [
                {"id": v.get("id"), "label": v.get("label"), "description": v.get("description"),
                 "url": f"https://threeui.com/{cat_seg}/{o['id']}/{v.get('id')}"}
                for v in (o.get("variants") or [])
            ],
            "controls": [c.get("key") for c in (o.get("controls") or [])],
        }
        community.append(item)
    community_ids = {c["id"] for c in community}

    (out / "community.json").write_text(json.dumps({
        "generatedAt": today,
        "source": {"sitemap": SITEMAP, "shaders": SHADERS_TSX},
        "license": "Community code: MIT (github.com/MengTo/threeui) — item attribution/third-party notices stay required",
        "count": len(community),
        "items": community,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = [f"# ThreeUI 사이트 색인 (sitemap.xml 기준, {today} 생성)", "",
             "섹션 → 패밀리(slug) → 변형. URL = `https://threeui.com/<섹션>/<패밀리>[/<변형>]`.",
             "소스 번들 = `https://threeui.com/source-code/<패밀리>.json` — Community만 200, Pro는 404(미리보기만).",
             "`[C]` = community.json에 메타가 있는 Community 패밀리, 표시 없음 = Pro(또는 공개 저장소 미동기화) — 상세 페이지의 PRO 배지로 확정한다.", ""]
    total = 0
    for sec in SECTIONS:
        fams = sections.get(sec, {})
        n = sum(len(v) for v in fams.values())
        total += n
        lines.append(f"## /{sec} — 패밀리 {len(fams)} · URL {n}")
        for fam, vars_ in fams.items():
            vs = [v for v in vars_ if v]
            tag = " [C]" if fam in community_ids else ""
            lines.append(f"- `{fam}`{tag}" + (f" — 변형 {len(vs)}: " + ", ".join(vs) if vs else ""))
        lines.append("")
    (out / "sitemap-index.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"community.json: {len(community)} families ({sum(len(c['variants']) or 1 for c in community)} browse results)")
    print(f"sitemap-index.md: {sum(len(v) for v in sections.values())} families, {total} item URLs")
    missing = [c["id"] for c in community if not any(c["id"] in fams for fams in sections.values())]
    if missing:
        print(f"note: {len(missing)} community ids not in sitemap: {missing[:10]}")


if __name__ == "__main__":
    main()
