#!/usr/bin/env python3
"""Read-only, limited PPTX inspection. No rendering or claims of full validity.

python pptx_audit.py deck.pptx --out report.json
python pptx_audit.py --preflight
Exit 0: no detected errors; exit 1: errors or inspection failure.
"""

import argparse
import json
import os
from pathlib import Path
import posixpath
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile


def local(tag):
    return tag.rsplit("}", 1)[-1]


def child(element, name):
    return next((item for item in element if local(item.tag) == name), None)


def text_of(element):
    return "\n".join(item.text or "" for item in element.iter() if local(item.tag) == "t")


def add(report, severity, code, message, **context):
    report["findings"].append(dict(severity=severity, code=code, message=message, **context))


def new_report(mode):
    return {
        "schema_version": 1, "mode": mode, "mechanical_only": True,
        "status": "pass", "checks": {}, "findings": [],
        "limitations": [
            "No rendering, visual review, text-fit test, or factual verification.",
            "No guarantee of full OOXML validity, font availability, or complete editability.",
        ],
    }


def probe(command, env=None):
    try:
        run = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=15, env=env)
        return {"status": "available" if run.returncode == 0 else "unavailable",
                "detail": (run.stdout if run.returncode == 0 else run.stderr).strip()[:300]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "unknown", "detail": str(exc)[:300]}


def preflight():
    node = shutil.which("node")
    node_env = os.environ.copy()
    modules = {}
    for name in ("pptx", "fitz"):
        modules[name] = probe([sys.executable, "-c", "import " + name + "; print('import succeeded')"])
    node_check = probe([node, "--version"]) if node else {"status": "missing"}
    pptxgenjs = (probe([node, "-e", "console.log(require.resolve('pptxgenjs'))"], node_env)
                if node else {"status": "missing"})
    commands = {name: shutil.which(name) for name in ("soffice", "libreoffice", "pdftoppm", "fc-list")}
    return {
        "python": {"executable": sys.executable, "version": sys.version.split()[0]},
        "python_modules": modules, "node": node_check, "pptxgenjs": pptxgenjs,
        "commands_on_path": commands,
        "font_availability": "not_checked",
        "platform_skills_and_connected_tools": "not_detectable_by_this_script",
        "note": "Tool presence/import is not proof that a deck can render correctly; no installation performed.",
    }


def relationship_owner(path):
    if path == "_rels/.rels":
        return ""
    directory, filename = posixpath.split(path)
    if posixpath.basename(directory) != "_rels" or not filename.endswith(".rels"):
        return None
    return posixpath.join(posixpath.dirname(directory), filename[:-5])


def resolve_target(owner, target):
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        raise ValueError("Internal relationship has an absolute URI without TargetMode=External")
    target_path = unquote(parsed.path)
    resolved = posixpath.normpath(target_path.lstrip("/") if target_path.startswith("/")
                                 else posixpath.join(posixpath.dirname(owner), target_path))
    if resolved in ("", ".", "..") or resolved.startswith("../"):
        raise ValueError("Relationship target is empty or escapes the package")
    return resolved


def relationships(roots, names, report):
    maps = {}
    for path, root in roots.items():
        if not path.endswith(".rels"):
            continue
        owner = relationship_owner(path)
        if owner is None:
            add(report, "error", "relationship_path", "Unexpected relationship part path", part=path)
            continue
        entries = maps.setdefault(owner, {})
        for item in root:
            if local(item.tag) != "Relationship":
                continue
            rid, target = item.get("Id"), item.get("Target")
            if not rid or target is None or rid in entries:
                add(report, "error", "relationship_entry", "Missing or duplicate relationship ID/target", part=path)
                continue
            entry = {"type": item.get("Type", ""), "external": item.get("TargetMode") == "External"}
            if entry["external"]:
                entry["target"] = target
            else:
                try:
                    entry["target"] = resolve_target(owner, target)
                    if entry["target"] not in names:
                        add(report, "error", "missing_relationship_target", "Internal target is missing",
                            part=path, relationship=rid, target=entry["target"])
                except ValueError as exc:
                    add(report, "error", "relationship_target", str(exc), part=path, relationship=rid)
                    continue
            entries[rid] = entry
    for owner, root in roots.items():
        for item in root.iter():
            for attribute, rid in item.attrib.items():
                if "}" not in attribute:
                    continue
                namespace, name = attribute[1:].split("}", 1)
                if namespace.endswith("/relationships") and name in ("id", "embed", "link") and rid not in maps.get(owner, {}):
                    add(report, "error", "unknown_relationship_reference", "XML references an undefined relationship",
                        part=owner, relationship=rid)
    return maps


def inspect_geometry(root, size, report, number):
    tree = next((item for item in root.iter() if local(item.tag) == "spTree"), None)
    if tree is None:
        add(report, "error", "missing_shape_tree", "Slide has no shape tree", slide=number)
        return
    width, height = size
    has_timing = any(local(item.tag) == "timing" for item in root.iter())
    for shape in tree:
        kind = local(shape.tag)
        if kind not in ("sp", "pic", "graphicFrame", "cxnSp", "grpSp"):
            continue
        meta = next((item for item in shape.iter() if local(item.tag) == "cNvPr"), None)
        name = meta.get("name", kind) if meta is not None else kind
        if kind == "grpSp":
            add(report, "warning", "group_geometry_not_checked", "Grouped coordinates need visual review",
                slide=number, shape=name)
            continue
        container = child(shape, "spPr")
        transform = child(container, "xfrm") if container is not None else child(shape, "xfrm")
        if transform is None:
            add(report, "warning", "inherited_geometry_not_checked", "Layout/master coordinates are not resolved",
                slide=number, shape=name)
            continue
        if transform.get("rot", "0") != "0" or any(transform.get(k) in ("1", "true") for k in ("flipH", "flipV")):
            add(report, "warning", "transformed_geometry_not_checked", "Rotation/flip needs visual review",
                slide=number, shape=name)
            continue
        offset, extent = child(transform, "off"), child(transform, "ext")
        try:
            x, y = int(offset.attrib["x"]), int(offset.attrib["y"])
            w, h = int(extent.attrib["cx"]), int(extent.attrib["cy"])
        except (AttributeError, KeyError, TypeError, ValueError):
            add(report, "error", "invalid_geometry", "Missing or invalid shape coordinates", slide=number, shape=name)
            continue
        if w < 0 or h < 0:
            add(report, "error", "negative_extent", "Negative shape extent", slide=number, shape=name)
            continue
        has_text = bool(text_of(shape).strip())
        has_data = any(local(item.tag) in ("chart", "tbl") for item in shape.iter())
        outside = x + w <= 0 or y + h <= 0 or x >= width or y >= height
        bleed = not has_text and not has_data and x <= 0 and y <= 0 and x + w >= width and y + h >= height
        if outside:
            add(report, "error" if (has_text or has_data) and not has_timing else "warning", "shape_outside_canvas",
                "Shape is wholly outside the slide; inspect any intended hidden/animated content",
                slide=number, shape=name)
        elif not bleed and (x < 0 or y < 0 or x + w > width or y + h > height):
            add(report, "warning", "partial_canvas_overflow", "Partial overflow may be intentional bleed; review visually",
                slide=number, shape=name)


def audit(path):
    report = new_report("pptx")
    report["file"] = str(path.resolve())
    report["slides"] = []
    report["checks"] = {"package_xml": "not_run", "internal_relationships": "not_run",
                        "slide_order": "not_run", "basic_geometry": "not_run",
                        "font_availability": "not_checked", "visual_review": "not_checked",
                        "factual_accuracy": "not_checked", "complete_editability": "not_guaranteed"}
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if len(names) != len(archive.namelist()):
                add(report, "error", "duplicate_zip_entries", "Archive contains duplicate part names")
            if "[Content_Types].xml" not in names:
                add(report, "error", "missing_content_types", "Required content types part is missing")
            roots = {}
            for info in archive.infolist():
                if info.filename.endswith((".xml", ".rels")):
                    if info.file_size > 16 * 1024 * 1024:
                        raise ValueError("XML part exceeds the 16 MiB inspection limit: " + info.filename)
                    raw = archive.read(info)
                    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                        raise ValueError("DTD/entity declarations are not supported: " + info.filename)
                    try:
                        roots[info.filename] = ET.fromstring(raw)
                    except ET.ParseError as exc:
                        add(report, "error", "malformed_xml", str(exc), part=info.filename)
            report["checks"]["package_xml"] = "fail" if any(f["code"] in ("malformed_xml", "missing_content_types", "duplicate_zip_entries") for f in report["findings"]) else "pass"
            maps = relationships(roots, names, report)
            report["checks"]["internal_relationships"] = "fail" if any("relationship" in f["code"] for f in report["findings"]) else "pass"
            main = next((e["target"] for e in maps.get("", {}).values()
                         if e["type"].endswith("/officeDocument") and not e["external"]), None)
            if main not in roots or local(roots[main].tag) != "presentation":
                raise ValueError("Root officeDocument relationship does not identify a readable presentation")
            presentation = roots[main]
            size = child(presentation, "sldSz")
            width, height = int(size.attrib["cx"]), int(size.attrib["cy"])
            if width <= 0 or height <= 0:
                raise ValueError("Slide dimensions must be positive")
            report["slide_size_emu"] = {"width": width, "height": height}
            slide_ids = child(presentation, "sldIdLst")
            slide_ids = [] if slide_ids is None else list(slide_ids)
            seen = set()
            for number, slide_id in enumerate(slide_ids, 1):
                rid = next((v for k, v in slide_id.attrib.items() if k.endswith("}id")), None)
                entry = maps.get(main, {}).get(rid, {})
                target = entry.get("target")
                if entry.get("external") or not entry.get("type", "").endswith("/slide") or target not in roots:
                    add(report, "error", "invalid_slide_reference", "Slide ID does not resolve to a slide part", slide=number, relationship=rid)
                    continue
                if target in seen:
                    add(report, "error", "duplicate_slide_reference", "A slide part appears more than once in the slide list", slide=number)
                seen.add(target)
                root = roots[target]
                if local(root.tag) != "sld":
                    add(report, "error", "invalid_slide_root", "Referenced part is not a slide", slide=number, part=target)
                    continue
                content = text_of(root)
                counts = {label: sum(local(item.tag) == tag for item in root.iter())
                          for label, tag in (("text_runs", "t"), ("pictures", "pic"), ("native_charts", "chart"), ("native_tables", "tbl"))}
                notes = []
                for rel in maps.get(target, {}).values():
                    if rel["type"].endswith("/notesSlide") and rel.get("target") in roots:
                        notes.append(text_of(roots[rel["target"]]))
                report["slides"].append({"number": number, "part": target, "text": content,
                                         "notes_text": "\n".join(notes), "counts": counts})
                if not content.strip():
                    add(report, "warning", "text_free_slide", "No slide-local text; image/master-only slides may be intentional", slide=number)
                inspect_geometry(root, (width, height), report, number)
            report["slide_count"] = len(slide_ids)
            if not slide_ids:
                add(report, "warning", "no_slides", "Presentation has no slides; this may be a template")
            report["checks"]["slide_order"] = "fail" if any(f["code"] in ("invalid_slide_reference", "duplicate_slide_reference", "invalid_slide_root") for f in report["findings"]) else "pass"
            report["checks"]["basic_geometry"] = "limited; axis-aligned slide-local shapes only; overlaps not checked"
            report["declared_font_references"] = sorted({item.get("typeface") for root in roots.values()
                for item in root.iter() if local(item.tag) in ("latin", "ea", "cs", "font") and item.get("typeface")})
    except (OSError, zipfile.BadZipFile, RuntimeError, ValueError, AttributeError, KeyError, TypeError, OverflowError, NotImplementedError) as exc:
        add(report, "error", "inspection_failed", str(exc))
    report["status"] = "fail" if any(item["severity"] == "error" for item in report["findings"]) else "pass"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", nargs="?", type=Path)
    parser.add_argument("--out", type=Path, help="Write the JSON report here as well as stdout")
    parser.add_argument("--preflight", action="store_true", help="Report local tools; may be combined with a deck")
    args = parser.parse_args()
    if args.deck is None and not args.preflight:
        parser.error("Provide a PPTX file or --preflight")
    report = audit(args.deck) if args.deck else new_report("preflight")
    if args.preflight:
        report["environment"] = preflight()
        report["checks"]["local_tool_probes"] = "completed; missing tools are reported, not installed"
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        try:
            if args.deck and args.out.resolve() == args.deck.resolve():
                raise ValueError("Report path must not overwrite the input deck")
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(output + "\n", encoding="utf-8")
        except (OSError, ValueError) as exc:
            add(report, "error", "report_write_failed", str(exc))
            report["status"] = "fail"
            output = json.dumps(report, ensure_ascii=False, indent=2)
    print(output)
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
