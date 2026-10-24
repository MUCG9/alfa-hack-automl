"""Aggregate-only reports and bounded coordinator summaries."""
import hashlib
import json
from pathlib import Path
from automl_contracts_error_analysis import AnalysisArtifactRef, ErrorProfile, ERROR_ANALYSIS_SCHEMA_VERSION

def write_json(path, value):
    path = Path(path)
    content = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
    with path.open('xb') as stream:
        stream.write(content)
    return AnalysisArtifactRef(str(path.resolve()), hashlib.sha256(path.read_bytes()).hexdigest())

def read_section(profile, name):
    section = next((s for s in profile.sections if s.name == name))
    if section.status != 'complete':
        return None
    root = Path(profile.request.output_dir).resolve()
    path = Path(section.result.path).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Section artifact is outside the report directory')
    if path.stat().st_size > 32 * 2 ** 20:
        raise ValueError('Section artifact exceeds summary byte bound')
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != section.result.sha256:
        raise ValueError('Report section SHA256 mismatch')
    result = json.loads(content)
    if result.get('schema_version') != ERROR_ANALYSIS_SCHEMA_VERSION or result.get('section') != name or result.get('request_sha256') != profile.request_sha256:
        raise ValueError('Report section schema/request identity mismatch')
    return result

def summary(profile):
    """Bounded scalar evidence for a future planner; no rows, probabilities or paths."""
    profile = ErrorProfile.from_dict(profile.to_dict())
    models = read_section(profile, 'models')
    comparisons = read_section(profile, 'comparisons')
    uncertainty = read_section(profile, 'uncertainty')
    metric = profile.request.task.metric
    result = {'schema_version': '1.0', 'request_sha256': profile.request_sha256, 'status': profile.status, 'diagnostic_only': True, 'prediction_scope': profile.request.prediction_scope, 'metric': metric[:100], 'control': profile.request.control_model_id[:100], 'models': [], 'comparisons': [], 'intervals': [], 'sections': {s.name: s.status for s in profile.sections}, 'limitations': [v[:500] for v in profile.limitations[:5]]}
    if models:
        for name, value in sorted(models['models'].items())[:8]:
            result['models'].append({'model': name[:100], 'fold_mean': value['fold_mean'][metric], 'pooled_oof': value.get('pooled_oof', {}).get('metrics', {}).get(metric)})
    if comparisons:
        for pair in comparisons['pairs'][:8]:
            result['comparisons'].append({'models': [m[:100] for m in pair['models']], 'fold_mean_delta': pair['fold_mean_delta']})
    if uncertainty:
        for item in uncertainty['comparisons'][:8]:
            result['intervals'].append({'candidate': item['candidate'][:100], 'fold': item['fold'][:100], 'status': item['status'], 'paired_percentile_95': item.get('paired_percentile_95')})
    while len(json.dumps(result, ensure_ascii=False).encode()) > 8192:
        collection = next((result[k] for k in ('limitations', 'comparisons', 'intervals', 'models') if result[k]), None)
        if collection is None:
            raise ValueError('Diagnostic summary exceeds byte budget')
        collection.pop()
    return result

def write_reports(profile):
    root = Path(profile.request.output_dir)
    write_json(root / 'error_profile.json', profile.to_dict())
    overview = summary(profile)
    write_json(root / 'planner_summary.json', overview)
    label = lambda value: json.dumps(value, ensure_ascii=False)
    lines = ['# Error passport', '', 'Status: ' + profile.status, 'Scope: ' + profile.request.prediction_scope, '', 'Diagnostic evidence only; no training, selection, thresholds or weights fitted.', '', '| Model | Fold mean | Pooled OOF |', '|---|---:|---:|']
    for model in overview['models']:
        lines.append('| ' + label(model['model']).replace('|', '\\|') + ' | ' + str(model['fold_mean']) + ' | ' + str(model['pooled_oof']) + ' |')
    lines.extend(['', '## Paired comparisons', '', 'Delta means second model minus first; lower is better for RMSE.', '', '| First / second model | Fold-mean delta |', '|---|---:|'])
    for pair in overview['comparisons']:
        lines.append('| ' + label(pair['models']).replace('|', '\\|') + ' | ' + str(pair['fold_mean_delta']) + ' |')
    lines.extend(['', '## Conditional uncertainty', ''])
    for item in overview['intervals']:
        lines.append('- ' + label(item['candidate']) + ', fold ' + label(item['fold']) + ': ' + item['status'] + ', paired 95% interval ' + str(item['paired_percentile_95']))
    lines.extend(['', '## Sections', ''])
    for section in profile.sections:
        lines.append('- ' + section.name + ': ' + section.status + (': ' + label(section.reason) if section.reason else ''))
    lines.extend(['', '## Findings', ''])
    for finding in profile.findings:
        lines.append('- ' + label(finding.summary))
    lines.extend(['', '## Limits', ''])
    lines.extend(('- ' + label(value) for value in profile.limitations))
    with (root / 'error_profile.md').open('xb') as stream:
        stream.write(('\n'.join(lines) + '\n').encode('utf-8'))
