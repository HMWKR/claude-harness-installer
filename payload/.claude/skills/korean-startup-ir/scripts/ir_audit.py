#!/usr/bin/env python3
"""Audit IR planning records. This checks consistency, never the truth of evidence."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import zipfile


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def audit(plan, plan_path, pptx_path=None, review_path=None, release=False):
    findings = []

    def add(code, message, severity='error'):
        findings.append({'severity': severity, 'code': code, 'message': message})

    def records(key):
        value = plan.get(key, [])
        if not isinstance(value, list):
            add('schema', f'{key} must be an array')
            return {}
        result = {}
        for row in value:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'].strip():
                add('schema', f'{key} entries need a nonempty string id')
                continue
            if row['id'] in result:
                add('duplicate_id', f'{key}: duplicate {row["id"]}')
            result[row['id']] = row
        return result

    def ids(row, key, location):
        value = row.get(key, [])
        if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
            add('schema', f'{location}.{key} must be an array of ids')
            return []
        return value

    if not isinstance(plan, dict):
        return {'mechanical_only': True, 'status': 'fail', 'findings': [
            {'severity': 'error', 'code': 'schema', 'message': 'Plan must be a JSON object'}]}
    if type(plan.get('schema_version')) is not int or plan['schema_version'] != 1:
        add('schema_version', 'schema_version must be 1')
    brief = plan.get('brief', {})
    if not isinstance(brief, dict):
        add('schema', 'brief must be an object')
        brief = {}
    for key in ('project', 'stage', 'language', 'as_of'):
        if not isinstance(brief.get(key), str) or not brief[key].strip():
            add('brief_missing', f'brief.{key} is required')
    if brief.get('purpose') not in ('fundraising', 'demo-day', 'program', 'partnership'):
        add('purpose', 'Unsupported or missing purpose')
    if brief.get('consumption') not in ('live', 'read'):
        add('consumption', 'consumption must be live or read')
    sources, claims = records('sources'), records('claims')
    requirements, slides = records('requirements'), records('slides')
    if not slides:
        add('empty_deck', 'No slides in the plan')
    used_claims, covered = set(), set()
    seconds = 0
    for sid, slide in slides.items():
        for key in ('title', 'takeaway', 'visual'):
            if not isinstance(slide.get(key), str) or not slide[key].strip():
                add('slide_missing', f'{sid}.{key} is required')
        for cid in ids(slide, 'claim_ids', sid):
            used_claims.add(cid)
            if cid not in claims:
                add('claim_not_found', f'{sid} references missing claim {cid}')
        for rid in ids(slide, 'requirement_ids', sid):
            covered.add(rid)
            if rid not in requirements:
                add('requirement_not_found', f'{sid} references missing requirement {rid}')
        if brief.get('consumption') == 'live':
            value = slide.get('seconds')
            if not number(value) or value < 0:
                add('timing', f'{sid}.seconds must be a nonnegative finite number')
            else:
                seconds += value
    maximum = brief.get('max_slides')
    if maximum is not None:
        if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum <= 0:
            add('slide_limit', 'max_slides must be a positive integer or null')
        elif len(slides) > maximum:
            add('slide_limit', f'{len(slides)} slides exceeds limit {maximum}')
    if brief.get('consumption') == 'live':
        duration, reserve = brief.get('duration_seconds'), brief.get('reserve_seconds', 0)
        if not number(duration) or duration <= 0 or not number(reserve) or reserve < 0:
            add('timing', 'Live deck needs positive duration_seconds and nonnegative reserve_seconds')
        elif seconds + reserve > duration + 0.01:
            add('time_overrun', f'Slides {seconds:g}s + reserve {reserve:g}s exceeds {duration:g}s')
    for eid, source in sources.items():
        for key in ('reference', 'locator', 'accessed_on'):
            if not isinstance(source.get(key), str) or not source[key].strip():
                add('source_missing', f'{eid}.{key} is required')
        if source.get('status') not in ('inspected', 'unread'):
            add('source_status', f'{eid} needs inspected or unread status')
    for rid, req in requirements.items():
        if not isinstance(req.get('text'), str) or not req['text'].strip():
            add('requirement_missing', f'{rid} has no requirement text')
        if not isinstance(req.get('required'), bool):
            add('schema', f'{rid}.required must be boolean')
        if req.get('required') and rid not in covered:
            add('uncovered_requirement', f'No slide addresses required item {rid}')
        eid = req.get('source_id')
        if not isinstance(eid, str) or eid not in sources:
            add('requirement_source', f'{rid} needs its actual source_id')
        elif sources[eid].get('status') != 'inspected':
            add('requirement_source', f'{rid} source has not been inspected')
        weight = req.get('weight')
        if weight is not None and (not number(weight) or weight < 0):
            add('weight', f'{rid}.weight must be nonnegative or null')
    known_kinds = {'fact', 'reported', 'derived', 'forecast', 'hypothesis', 'missing'}
    dependencies = {}
    for cid, claim in claims.items():
        kind = claim.get('kind')
        if not isinstance(kind, str) or kind not in known_kinds:
            add('claim_kind', f'{cid}: unsupported claim kind')
        if not isinstance(claim.get('statement'), str) or not claim['statement'].strip():
            add('claim_statement', f'{cid} needs a statement')
        source_ids = ids(claim, 'source_ids', cid)
        for eid in source_ids:
            if eid not in sources:
                add('source_not_found', f'{cid} references missing source {eid}')
            elif sources[eid].get('status') != 'inspected':
                add('source_unread', f'{cid} uses unread source {eid}')
        if kind in ('fact', 'reported') and not source_ids:
            add('unsupported_claim', f'{cid}: {kind} needs an inspected source')
        if kind in ('reported', 'forecast', 'hypothesis', 'missing') and not nonempty_string(claim.get('qualification')):
            add('qualification', f'{cid}: label its evidence/forecast limitation')
        if kind == 'missing' and cid in used_claims:
            add('missing_claim', f'{cid}: a slide still needs this fact', 'error' if release else 'warning')
        if 'value' in claim and claim['value'] is not None:
            if not number(claim['value']):
                add('numeric_value', f'{cid}.value must be finite numeric data')
            for key in ('unit', 'period', 'scope'):
                if not isinstance(claim.get(key), str) or not claim[key].strip():
                    add('metric_context', f'{cid}.{key} is required for numeric claims')
        if kind == 'derived':
            calc = claim.get('calculation')
            if not isinstance(calc, dict):
                add('calculation', f'{cid}: derived claim needs calculation')
                continue
            op = calc.get('op')
            if op == 'external':
                if not nonempty_string(calc.get('reference')) or calc.get('checked') is not True:
                    add('external_calculation', f'{cid}: external model needs location and actual check')
                else:
                    add('external_unverified', f'{cid}: external calculation is recorded, not recomputed by this tool', 'warning')
                continue
            inputs = ids(calc, 'inputs', cid + '.calculation')
            dependencies[cid] = inputs
            if op not in ('sum', 'difference', 'product', 'ratio', 'percent_change'):
                add('calculation', f'{cid}: unsupported arithmetic operation')
                continue
            if not inputs or (op in ('difference', 'ratio', 'percent_change') and len(inputs) != 2):
                add('calculation', f'{cid}: invalid operand count')
                continue
            if any(i not in claims or not number(claims[i].get('value')) for i in inputs):
                add('calculation_input', f'{cid}: input claims need finite numeric values')
                continue
            values = [claims[i]['value'] for i in inputs]
            try:
                if op == 'sum': result = sum(values)
                elif op == 'product': result = math.prod(values)
                elif op == 'difference': result = values[0] - values[1]
                elif op == 'ratio': result = values[0] / values[1]
                else: result = (values[1] - values[0]) / values[0] * 100
                if not number(result) or not number(claim.get('value')) or not math.isclose(result, claim['value'], rel_tol=1e-8, abs_tol=1e-8):
                    add('calculation_mismatch', f'{cid}: stored value does not match recomputed {result}')
            except (ZeroDivisionError, OverflowError):
                add('calculation_undefined', f'{cid}: zero denominator or arithmetic overflow')
    # Validate dependency graph, including indirect missing/assumption inputs.
    def walk(cid, trail, root):
        if cid in trail:
            add('calculation_cycle', ' -> '.join(trail + [cid]))
            return
        for dep in dependencies.get(cid, []):
            row = claims.get(dep, {})
            if row.get('kind') == 'missing' and root in used_claims:
                add('missing_input', f'{root} depends on unresolved {dep}', 'error' if release else 'warning')
            if row.get('kind') in ('forecast', 'hypothesis', 'reported') and not nonempty_string(claims[root].get('qualification')):
                add('derived_qualification', f'{root} uses uncertain input {dep}; label the limitation')
            walk(dep, trail + [cid], root)
    for cid in dependencies:
        walk(cid, [], cid)
    reachable_claims = set(used_claims)
    pending = list(used_claims)
    while pending:
        for dep in dependencies.get(pending.pop(), []):
            if dep not in reachable_claims:
                reachable_claims.add(dep)
                pending.append(dep)
    numeric_review_required = any(
        claims.get(cid, {}).get('value') is not None for cid in reachable_claims)
    requirement_review_required = any(row.get('required') is True for row in requirements.values())
    if pptx_path:
        try:
            with zipfile.ZipFile(pptx_path) as z:
                tree = ET.fromstring(z.read('ppt/presentation.xml'))
                count = len(tree.findall('{http://schemas.openxmlformats.org/presentationml/2006/main}sldIdLst/{http://schemas.openxmlformats.org/presentationml/2006/main}sldId'))
            if count != len(slides):
                add('slide_count_mismatch', f'PPTX has {count} slides; plan has {len(slides)}')
        except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as e:
            add('pptx_unreadable', f'PPTX cannot be checked: {type(e).__name__}')
    if release and not pptx_path:
        add('pptx_required', 'Release record check needs the final PPTX')
    if release and not review_path:
        add('review_required', 'Release record check needs review.json')
    if review_path:
        try:
            review = json.loads(Path(review_path).read_text(encoding='utf-8'))
            if not isinstance(review, dict):
                raise ValueError('review must be an object')
            if review.get('plan_sha256') != digest(plan_path):
                add('stale_plan_review', 'Review does not match the current plan file')
            if pptx_path and review.get('pptx_sha256') != digest(pptx_path):
                add('stale_pptx_review', 'Review does not match the current PPTX')
            checks = review.get('checks', {})
            if not isinstance(checks, dict):
                raise ValueError('checks must be an object')
            for key in ('evidence', 'numbers', 'requirements', 'story', 'structure', 'visual', 'timing'):
                check = checks.get(key, {})
                if not isinstance(check, dict):
                    check = {}
                status = check.get('status')
                allowed = {'pass'} if key in ('evidence', 'story', 'structure', 'visual') else {'pass', 'not_applicable'}
                if key == 'numbers' and numeric_review_required:
                    allowed = {'pass'}
                if key == 'requirements' and requirement_review_required:
                    allowed = {'pass'}
                if key == 'timing' and brief.get('consumption') == 'live':
                    allowed = {'pass'}
                if not isinstance(status, str) or status not in allowed or not nonempty_string(check.get('note')):
                    add('review_incomplete', f'{key}: missing, failed, or unexplained check', 'error' if release else 'warning')
            renders = review.get('renders', [])
            if not isinstance(renders, list):
                raise ValueError('renders must be an array')
            seen = set()
            for render in renders:
                if not isinstance(render, dict):
                    add('render_record', 'Invalid render record')
                    continue
                sid = render.get('slide_id')
                if not isinstance(sid, str) or sid not in slides or sid in seen:
                    add('render_record', 'Render slide id is duplicate or unknown')
                    continue
                seen.add(sid)
                value = render.get('path')
                if not isinstance(value, str) or not value:
                    add('render_record', f'{sid}: render path is missing')
                    continue
                path = Path(value)
                if not path.is_absolute():
                    path = Path(review_path).resolve().parent / path
                if render.get('reviewed') is not True:
                    add('render_not_reviewed', f'{sid}: actual visual review is not recorded')
                if not path.is_file() or render.get('sha256') != digest(path):
                    add('stale_render_review', f'{sid}: render file missing or hash changed')
            if release and seen != set(slides):
                add('render_coverage', 'Visual review records do not cover every current slide')
        except (OSError, ValueError, json.JSONDecodeError) as e:
            add('review_unreadable', f'Review cannot be checked: {e}')
    errors = sum(x['severity'] == 'error' for x in findings)
    return {'mechanical_only': True, 'status': 'fail' if errors else 'pass',
            'release_record_requested': release, 'requires_human_judgment': True,
            'summary': {'slides': len(slides), 'claims': len(claims), 'sources': len(sources),
                        'allocated_slide_seconds': seconds, 'errors': errors,
                        'warnings': sum(x['severity'] == 'warning' for x in findings)},
            'limitations': ['Does not verify source truth, semantic coverage, actual speech timing, visual quality, or who reviewed images.'],
            'findings': findings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--pptx', type=Path)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--release', action='store_true')
    args = parser.parse_args()
    output_allowed = True
    try:
        if args.out:
            output = args.out.resolve()
            for source in (args.plan, args.pptx, args.review):
                if source and (output == source.resolve() or
                               (args.out.exists() and source.exists() and args.out.samefile(source))):
                    output_allowed = False
                    raise ValueError('--out must not overwrite the plan, PPTX, or review input')
        plan = json.loads(args.plan.read_text(encoding='utf-8'))
        result = audit(plan, args.plan, args.pptx, args.review, args.release)
        code = 1 if result['status'] == 'fail' else 0
    except (OSError, ValueError, TypeError, OverflowError, RecursionError) as e:
        result = {'mechanical_only': True, 'status': 'fail', 'findings': [
            {'severity': 'error', 'code': 'execution_error', 'message': str(e)}]}
        code = 2
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out and output_allowed:
        try:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text + '\n', encoding='utf-8')
        except OSError as e:
            result['status'] = 'fail'
            result['findings'].append({'severity': 'error', 'code': 'output_error', 'message': str(e)})
            text = json.dumps(result, ensure_ascii=False, indent=2)
            code = 2
    print(text)
    return code


if __name__ == '__main__':
    sys.exit(main())
