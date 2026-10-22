"""Resolve documented table roles locally; ambiguity is never guessed away."""
from pathlib import Path
import re

ALIASES={
    'train':('train','training','fitting','learn','обучение'),
    'test':('test','evaluation','eval','holdout','тест'),
    'sample_submission':('sample_submission','submission_sample','sample_predictions','submission_format','sample','example','пример'),
    'data_dictionary':('data_dictionary','dictionary','schema','metadata','словарь'),
}
IGNORED={'automl_runs','test-runs','dist','release','__pycache__'}
SUFFIXES={'.csv','.tsv','.tab'}


def _safe(root,path):
    resolved=path.resolve()
    if not resolved.is_relative_to(root): raise ValueError('Input path leaves task directory')
    return resolved


def _catalog(root):
    tables=[]
    for path in root.rglob('*'):
        relative=path.relative_to(root)
        if any(part.startswith('.') or part in IGNORED for part in relative.parts): continue
        if path.suffix.lower() not in SUFFIXES or not path.is_file(): continue
        tables.append(_safe(root,path))
        if len(tables)>128: raise ValueError('Too many input tables; explicit file roles are required')
    return sorted(set(tables))


def find_input(root:Path,name:str,text:str)->Path:
    root=root.resolve()
    # Retain exact public paths before introducing broader filename aliases.
    mentions=re.findall(r'`([^`\n]*'+re.escape(name)+r')`',text)
    for match in mentions:
        candidate=_safe(root,root/match)
        if candidate.is_file(): return candidate
    direct=_safe(root,root/name)
    if direct.is_file(): return direct
    candidates=[p for p in _catalog(root) if p.name==name]
    if len(candidates)!=1: raise ValueError(f'Expected one {name}, found {len(candidates)}')
    return candidates[0]


def _resolve_inputs_deterministic(root,text):
    root=Path(root).resolve(); tables=None; paths={}
    for role,aliases in ALIASES.items():
        try:
            path=find_input(root,role+'.csv',text)
        except ValueError as exc:
            if 'Input path leaves' in str(exc): raise
            if tables is None: tables=_catalog(root)
            candidates=[p for p in tables if any(re.search(r'(?:^|[_\-.])'+re.escape(alias)+r'(?:$|[_\-.])',p.stem.lower()) for alias in aliases)]
            mentioned=[p for p in candidates if str(p.relative_to(root)) in text or p.name in text]
            if len(mentioned)==1: candidates=mentioned
            if not candidates and role=='data_dictionary': continue
            if len(candidates)!=1: raise ValueError(f'Ambiguous or missing {role} table ({len(candidates)} candidates)') from exc
            path=candidates[0]
        if path in paths.values(): raise ValueError('One input table cannot serve two roles')
        paths[role]=path
    return paths


def resolve_inputs(root,text,allow_llm=False,resolution=None,validate=None):
    try: return _resolve_inputs_deterministic(root,text)
    except ValueError as exc:
        if not allow_llm or 'leaves task directory' in str(exc): raise
        from automl.task_understanding.semantic_inputs import infer_file_roles
        return infer_file_roles(Path(root).resolve(),text,str(exc),resolution,validate=validate)
