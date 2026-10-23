"""Read-only diagnostics backend. It never invokes Execution or Search."""
import hashlib
from pathlib import Path

from threadpoolctl import threadpool_limits

from automl.contracts.error_analysis import ErrorAnalysisRequest, ErrorProfile, ErrorProfileSection, ErrorFinding, PROFILE_SECTIONS, ERROR_ANALYSIS_SCHEMA_VERSION
from automl.contracts.messages import canonical_hash
from automl.infrastructure.runtime import source_files, project_root
from automl.error_analysis.artifacts import Guard, load, finite
from automl.error_analysis.comparisons import model_profiles, comparison_profiles
from automl.error_analysis.slices import profiles as slice_profiles
from automl.error_analysis.uncertainty import profiles as uncertainty_profiles
from automl.error_analysis.reporting import write_json, write_reports


LIMITATIONS = (
    'Reused held-out data: exploratory diagnostics, not independent/private score or validation certification.',
    'All statistics are conditional on saved predictions; no model refits, weight fitting or selection performed.',
    'Fold mean and pooled OOF are distinct; overlapping holdouts and forward backtests are never pooled.',
    'Slice and bootstrap comparisons are exploratory, unadjusted for multiple comparisons; low support is labelled.',
    'Source/recipe provenance records declarations from frozen runs; it does not reconstruct historical model binaries.',
    'Limits are cooperative with bounded reads/NPZ expansion; use the CLI subprocess watchdog for whole-process limits.',
)


def analysis_source_sha256():
    root = project_root()
    return canonical_hash({str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files()})


def _inputs(request):
    paths = [request.dataset.path, request.protocol.path]
    for ref in request.predictions:
        paths.extend([ref.predictions.path, ref.split.path])
        paths.extend(r.path for r in (ref.probabilities, ref.recorded_result) if r is not None)
    paths.extend(r.path for r in (request.groups, request.observation_time) if r is not None)
    return [Path(p).resolve() for p in paths]


def analyze(request):
    if not isinstance(request, ErrorAnalysisRequest):
        raise ValueError('Expected ErrorAnalysisRequest')
    request = ErrorAnalysisRequest.from_dict(request.to_dict())
    output = Path(request.output_dir).resolve()
    if output.exists():
        raise FileExistsError('Refusing an existing report directory')
    if any(path.is_relative_to(output) for path in _inputs(request)):
        raise ValueError('Report directory cannot contain input artifacts')
    guard = Guard(request.budget)
    source_sha = analysis_source_sha256()
    sections = []
    findings = []
    with threadpool_limits(limits=request.budget.threads):
        try:
            data = load(request, guard)
            if any(p.is_relative_to(output) for p in guard.verified):
                raise ValueError('Report directory cannot contain protocol evidence')
        except Exception as exc:
            output.mkdir(parents=True, exist_ok=False)
            for name in PROFILE_SECTIONS:
                sections.append(ErrorProfileSection(name, 'failed' if name == 'alignment' else 'unavailable',
                    reason=type(exc).__name__ + ': ' + str(exc)[:500] if name == 'alignment' else 'Alignment not verified'))
            profile = ErrorProfile(request, request.sha256, source_sha, 'failed', tuple(sections), LIMITATIONS)
            write_reports(profile)
            return profile
        output.mkdir(parents=True, exist_ok=False)
        envelope = {'schema_version': ERROR_ANALYSIS_SCHEMA_VERSION, 'request_sha256': request.sha256}
        alignment_ref = write_json(output / 'alignment.json', dict(envelope, section='alignment', **data.alignment))
        sections.append(ErrorProfileSection('alignment', 'complete', alignment_ref))
        computations = [('models', model_profiles), ('comparisons', comparison_profiles), ('slices', slice_profiles), ('uncertainty', uncertainty_profiles)]
        for name, compute in computations:
            try:
                guard.check()
                result = compute(data, guard)
                reason = None
                if name == 'uncertainty':
                    result, reason = result
                if result is None:
                    sections.append(ErrorProfileSection(name, 'unavailable', reason=reason))
                else:
                    artifact = write_json(output / (name + '.json'), dict(envelope, section=name, **finite(result)))
                    sections.append(ErrorProfileSection(name, 'complete', artifact))
                    if name == 'models':
                        control = result['models'][request.control_model_id]
                        findings.append(ErrorFinding('control_metric',
                            'Control fold-mean ' + request.task.metric + '=' + str(control['fold_mean'][request.task.metric]), ('models',)))
                        for fold, record in list(control['folds'].items())[:3]:
                            if request.task.kind == 'regression':
                                text = 'Control fold ' + fold + ': largest 1% of residuals account for ' + str(record['largest_error_concentration']['0.01']['squared_error_share']) + ' of squared error.'
                            else:
                                label, f1 = min(record['metrics']['per_class_f1'].items(), key=lambda item: item[1])
                                text = 'Control fold ' + fold + ': lowest class F1=' + str(f1) + ' for ' + label + '; inspect class support before acting.'
                            findings.append(ErrorFinding('control_error_' + fold, text, ('models',)))
            except Exception as exc:
                sections.append(ErrorProfileSection(name, 'failed', reason=type(exc).__name__ + ': ' + str(exc)[:500]))
        try:
            guard.verify_unchanged()
            if analysis_source_sha256() != source_sha:
                raise ValueError('Analyzer source changed during analysis')
        except (ValueError, OSError, RuntimeError) as exc:
            # Invalidate the manifest; never let completed downstream sections certify mutated inputs.
            sections = [ErrorProfileSection(name, 'failed' if name == 'alignment' else 'unavailable',
                reason=str(exc)[:500] if name == 'alignment' else 'Input/source integrity invalidated') for name in PROFILE_SECTIONS]
            findings = []
        status = 'failed' if sections[0].status != 'complete' else 'complete' if all(s.status == 'complete' for s in sections) else 'partial'
        profile = ErrorProfile(request, request.sha256, source_sha, status, tuple(sections), LIMITATIONS, tuple(findings))
        write_reports(profile)
        return profile


class LocalErrorAnalyzer:
    def analyze(self, request):
        return analyze(request)
