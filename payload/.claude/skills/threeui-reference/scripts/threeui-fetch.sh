#!/usr/bin/env bash
# ThreeUI Community 소스 번들 회수 — 사이트의 "Copy Prompt"와 같은 결과를 파일로 만든다.
#   threeui-fetch.sh <family-slug> [out-dir=web-crawling/threeui] [--variant <id>]
# 결과: <out-dir>/<family>/{bundle.json, prompt.md, SOURCE.md, src/...}
# 종료코드: 0 성공 · 2 번들 없음(Pro 또는 slug 오류 — 스크래핑하지 말고 보고) · 1 해시 불일치/오류
set -euo pipefail
fam="${1:-}"; shift || true
[[ -n "$fam" && "$fam" =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo "usage: threeui-fetch.sh <family-slug> [out-dir] [--variant <id>]" >&2; exit 1; }
out="web-crawling/threeui"; variant=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --variant) variant="${2:-}"; shift 2;;
    *) out="$1"; shift;;
  esac
done
dest="$out/$fam"; mkdir -p "$dest"
url="https://threeui.com/source-code/$fam.json"
code=$(curl -sSL --max-time 60 --proto '=https' -o "$dest/bundle.json" -w '%{http_code}' "$url" || echo 000)
if [[ "$code" != "200" ]]; then
  rm -f "$dest/bundle.json"; rmdir "$dest" 2>/dev/null || true
  echo "NO_BUNDLE ($code) $url — Pro 항목이거나 slug 오류. Pro 소스는 구매 후 'npx @designcodeio/threeui-cli add $fam' 또는 Pro MCP로만. 스크래핑 금지(약관)." >&2
  exit 2
fi
export THREEUI_FAM="$fam" THREEUI_DEST="$dest" THREEUI_VARIANT="$variant" THREEUI_URL="$url"
export THREEUI_CATALOG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/catalog/community.json"
python3 -I - <<'PY'
import hashlib, json, os, pathlib, datetime
fam, dest, variant, url, cat = (os.environ[k] for k in ("THREEUI_FAM", "THREEUI_DEST", "THREEUI_VARIANT", "THREEUI_URL", "THREEUI_CATALOG"))
dest = pathlib.Path(dest)
b = json.loads((dest / "bundle.json").read_text(encoding="utf-8"))
files, assets = b.get("files", []), b.get("assets", [])
bad = []
for f in files:
    code = f.get("code", "")
    h = hashlib.sha256(code.encode("utf-8")).hexdigest()
    if h != f.get("sha256"):
        bad.append((f["path"], f.get("sha256"), h))
    p = dest / f["path"].lstrip("/")
    if ".." in p.parts:
        raise SystemExit(f"refused path: {f['path']}")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(code, encoding="utf-8")
if bad:
    for path, want, got in bad:
        print(f"HASH_MISMATCH {path} declared={want} computed={got}")
    raise SystemExit(1)
meta = {}
catp = pathlib.Path(cat)
if catp.exists():
    for it in json.loads(catp.read_text(encoding="utf-8"))["items"]:
        if it["id"] == fam:
            meta = it
            break
import_name = meta.get("importName") or "".join(w.capitalize() for w in fam.split("-"))
label = meta.get("label") or fam
runtime = meta.get("runtime") or "(see page)"
page_url = meta.get("url") or f"https://threeui.com/browse?q={fam}"
vmeta = next((v for v in meta.get("variants", []) if v["id"] == variant), None) if variant else None
brief = (vmeta or {}).get("description") or meta.get("description") or ""
canonical = next((f for f in files if f.get("role") in ("canonical-source", "scene-source") and f["path"].endswith(".html")), None)
usage_props = f'\n        variant="{variant}"\n      ' if variant else " "
usage = (f'import {{ {import_name} }} from "@designcodeio/threeui";\nimport "@designcodeio/threeui/style.css";\n\n'
         f'export function Scene() {{\n  return (\n    <div className="shader-frame">\n      <{import_name}{usage_props}/>\n    </div>\n  );\n}}')
lines = [f"# Integrate <{import_name} /> from ThreeUI using its exact source", "",
         "You are working in an existing application. Implement this component from the exact source linked or included below. Do not recreate it from the preview, screenshot, description, or filename.", "",
         f"Component: `{import_name}`"]
if vmeta:
    lines.append(f"Variant: **{vmeta['label']}** (`{variant}`)")
lines += [f"Runtime: {runtime}", f"Source revision: `{meta.get('sourceCommit') or 'see bundle'}`", "",
          "Reference brief:", brief, "", "## Current configured usage", "", "```tsx", usage, "```", "",
          "## Exact implementation source", "", f"Complete registered source bundle: [{url}]({url})", f"Component page: {page_url}", ""]
if canonical:
    lines += [f"Direct canonical HTML source: `{canonical['path']}` (self-contained document, {canonical.get('lines')} lines)", ""]
lines += ["Required registered files (saved next to this prompt at the same relative paths, hashes verified):", ""]
for f in files:
    lines.append(f"- `{f['path']}` — {f.get('role')} · {f.get('lines')} lines · SHA-256 `{f.get('sha256')}`")
if assets:
    lines += ["", "Binary assets (copy byte-for-byte from the ThreeUI package or CDN; verify hash):", "",
              "| Path | MIME | Bytes | SHA-256 |", "| --- | --- | ---: | --- |"]
    for a in assets:
        lines.append(f"| `{a.get('path')}` | {a.get('mimeType')} | {a.get('bytes')} | `{a.get('sha256')}` |")
lines += ["", "## Implementation requirements", "",
          "- Preserve the authored structure, styling, shaders, motion, interactions, responsive behavior, dependencies, and asset paths described by the source.",
          f"- Use the configured `<{import_name} />` usage above, including the selected variant and props.",
          "- Build directly in the destination project. Do not embed the ThreeUI documentation page and do not approximate the result from its rendered appearance.",
          "- Fetch and read the complete source before editing. If the source cannot be retrieved, stop and report that instead of recreating it.",
          "- After implementation, verify the rendered result and its interactions in the browser (this harness: `aside repl`).", ""]
(dest / "prompt.md").write_text("\n".join(lines), encoding="utf-8")
src_md = [f"# {label} — 출처 기록", "", f"- 페이지: {page_url}" + (f" (변형 `{variant}`)" if variant else ""),
          f"- 번들: {url} (schemaVersion {b.get('schemaVersion')}, id `{b.get('id')}`)",
          f"- 회수일: {datetime.date.today().isoformat()}",
          "- 라이선스: ThreeUI Community — MIT (github.com/MengTo/threeui). 항목별 attribution·제3자 고지 유지. 글꼴은 SIL OFL 1.1, Three.js 런타임 MIT.",
          "- 파일 해시(SHA-256, 검증 완료):"]
src_md += [f"  - `{f['path']}` {f.get('sha256')}" for f in files]
(dest / "SOURCE.md").write_text("\n".join(src_md) + "\n", encoding="utf-8")
total = sum(f.get("bytes", 0) for f in files)
print(f"OK {fam}: files={len(files)} ({total} bytes) assets={len(assets)} -> {dest}/ (prompt.md, SOURCE.md, source files)")
for f in files:
    print(f"  {f.get('role'):17} {f['path']}")
PY
