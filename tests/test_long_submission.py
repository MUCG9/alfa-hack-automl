"""Release-only launcher defaults; no new fitting or canonical policy changes."""
import hashlib
from pathlib import Path
import runpy
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_submission import build_files,LONG01_ENTRY,LONG01_SHA,REQUIREMENTS_SHA


class LongSubmissionTests(unittest.TestCase):
    def test_exact_frozen_core(self):
        files=build_files('long01-submit')
        frozen=ROOT/'release/solution-long01-anytime1.zip'
        self.assertEqual(hashlib.sha256(frozen.read_bytes()).hexdigest(),LONG01_SHA)
        with zipfile.ZipFile(frozen) as archive:
            self.assertEqual(set(files),set(archive.namelist()))
            changed=[name for name in files if files[name]!=archive.read(name)]
        self.assertEqual(changed,['solution.py'])
        self.assertEqual(len(files),55)

    def test_original_requirements(self):
        self.assertEqual(hashlib.sha256(build_files('long01-submit')['requirements.txt']).hexdigest(),REQUIREMENTS_SHA)

    def test_canonical_default_unchanged(self):
        self.assertNotEqual(build_files()['solution.py'],LONG01_ENTRY)
        self.assertIn(b'main()',build_files()['solution.py'])

    def test_task_only_invocation(self):
        captured=[]
        module=types.ModuleType('automl_runner')
        module.THREADS=2
        module.llm_plan=module.run_worker=lambda:None
        module.main=lambda:captured.append(sys.argv[:])
        with tempfile.TemporaryDirectory() as tmp:
            entry=Path(tmp)/'solution.py'
            entry.write_bytes(LONG01_ENTRY)
            with patch.dict(sys.modules,{'automl_runner':module}),patch.object(sys,'argv',['solution.py','task.md']):
                runpy.run_path(str(entry),run_name='__main__')
        self.assertEqual(captured[0][1:],['--offline','--time-budget','10800','--search-until-deadline','--finalization-reserve','1200','--max-extended-experiments','1000','task.md'])
        for budget_args in (['--time-budget','300'],['--time-budget=300']):
            with self.subTest(arguments=budget_args),tempfile.TemporaryDirectory() as tmp:
                entry=Path(tmp)/'solution.py'
                entry.write_bytes(LONG01_ENTRY)
                explicit=['solution.py','task.md','--offline',*budget_args]
                with patch.dict(sys.modules,{'automl_runner':module}),patch.object(sys,'argv',explicit[:]):
                    runpy.run_path(str(entry),run_name='__main__')
                self.assertEqual(captured[-1][1:],explicit[1:])

    def test_unknown_profile_rejected(self):
        with self.assertRaises(ValueError): build_files('unknown')


if __name__=='__main__': unittest.main()
