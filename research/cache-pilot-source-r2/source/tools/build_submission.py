"""Compile explicitly mapped project modules into a standalone flat ZIP."""
from pathlib import Path
import argparse,ast,hashlib,json,re,zipfile,sys
ROOT=Path(__file__).resolve().parents[1]
REQUIREMENTS_SHA='9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6'

class Flatten(ast.NodeTransformer):
    def __init__(self,mapping): self.mapping=mapping
    def visit_ImportFrom(self,node):
        if node.level: raise ValueError('Relative imports are not supported by the flat compiler')
        if node.module in self.mapping:
            node.module=self.mapping[node.module]
        elif node.module=='automl.execution.model_adapters':
            return [ast.copy_location(ast.Import(names=[ast.alias(self.mapping['automl.execution.model_adapters.'+item.name],item.asname or item.name)]),node) for item in node.names]
        elif node.module and node.module.startswith('automl'):
            raise ValueError('Unmapped project import: '+node.module)
        return node

def build_files():
    mapping=json.loads((ROOT/'tools/module_map.json').read_text())
    for path in (ROOT/'src/automl').rglob('*.py'):
        if path.name=='__init__.py': continue
        module='.'.join(path.relative_to(ROOT/'src').with_suffix('').parts)
        mapping.setdefault(module,module.replace('.','_'))
    if len(mapping.values())!=len(set(mapping.values())): raise ValueError('Flat module name collision')
    files={}
    for module,flat in mapping.items():
        path=ROOT/'src'/Path(*module.split('.')).with_suffix('.py')
        tree=Flatten(mapping).visit(ast.parse(path.read_text(encoding='utf-8')))
        text=ast.unparse(ast.fix_missing_locations(tree))+'\n'
        compile(text,flat+'.py','exec')
        if re.search(r'(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{12,}',text): raise ValueError('Possible secret in '+module)
        files[flat+'.py']=text.encode()
    for alias,target in {'agent_runner':'automl_runner','agent_policy':'automl_policy','agent_worker':'automl_worker','ensemble_cache':'automl_ensembles'}.items():
        files[alias+'.py']=f'import sys\nimport {target} as _module\nsys.modules[__name__]=_module\n'.encode()
    files['solution.py']=b'from automl_runner import THREADS,llm_plan,main,run_worker\nif __name__ == "__main__": main()\n'
    requirement=(ROOT/'requirements.txt').read_bytes()
    if hashlib.sha256(requirement).hexdigest()!=REQUIREMENTS_SHA: raise ValueError('Platform requirements changed')
    files['requirements.txt']=requirement
    return files

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,required=True); args=parser.parse_args()
    files=build_files(); args.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.output,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,data in sorted(files.items()):
            entry=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0)); entry.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(entry,data)
    if args.output.stat().st_size>100_000_000: raise ValueError('Archive too large')
    manifest={'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),'bytes':args.output.stat().st_size,'build_python':sys.version,
              'files':{n:hashlib.sha256(v).hexdigest() for n,v in files.items()}}
    args.output.with_suffix('.manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2))
if __name__=='__main__': main()
