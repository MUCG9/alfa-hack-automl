"""Verify the release harness records failures and owns timed-out descendants."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,time,unittest,zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import psutil
import verify_release


class ReleaseVerifierTests(unittest.TestCase):
    def test_real_nonzero_script_preserves_both_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            result=verify_release.run_check([sys.executable,'-c',
                'import sys;print("progress");print("failure",file=sys.stderr);sys.exit(7)'],
                directory,os.environ.copy(),10,2**30)
            self.assertEqual(result['exit_code'],7)
            self.assertIn('progress',result['stdout']);self.assertIn('failure',result['stderr'])

    def test_timeout_records_partial_output_and_cleans_detached_child(self):
        with tempfile.TemporaryDirectory() as directory:
            code='import subprocess,sys,time; p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"],start_new_session=True);print(p.pid,flush=True);time.sleep(30)'
            result=verify_release.run_check([sys.executable,'-u','-c',code],directory,os.environ.copy(),.8,2**30)
            self.assertEqual(result['exit_code'],'timeout')
            pid=int(result['stdout'].strip())
            try:alive=psutil.Process(pid).is_running() and psutil.Process(pid).status()!=psutil.STATUS_ZOMBIE
            except psutil.NoSuchProcess:alive=False
            self.assertFalse(alive)

    def test_failed_unpacked_run_writes_false_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'tests').mkdir();archive=root/'fixture.zip'
            files={'solution.py':b'pass\n','requirements.txt':b''}
            with zipfile.ZipFile(archive,'w') as packed:
                for name,data in files.items():packed.writestr(name,data)
            for name in ['test_v2.py','test_resilience.py','smoke.py']:
                (root/'tests'/name).write_text('import sys;print("failed fixture");sys.exit(3)')
            output=root/'receipt.json'
            with patch.object(verify_release,'ROOT',root),patch.object(verify_release,'build_files',return_value=files):
                with self.assertRaises(SystemExit):verify_release.main(['--archive',str(archive),'--output',str(output)])
            result=json.loads(output.read_text())
            self.assertFalse(result['passed']);self.assertTrue(result['matches_current_source'])
            self.assertEqual(len(result['checks']),1);self.assertEqual(result['checks'][0]['exit_code'],3)


if __name__=='__main__':unittest.main(verbosity=2)
