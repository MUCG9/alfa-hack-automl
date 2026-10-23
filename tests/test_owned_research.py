"""Cross-process exclusion and PID identity for the development research queue."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import psutil
from overnight_research import identity_alive
from research_lock import ResearchLock


class OwnedResearchTests(unittest.TestCase):
    def test_process_identity_uses_creation_time_not_only_pid(self):
        process=psutil.Process()
        self.assertTrue(identity_alive({'pid':process.pid,'create_time':process.create_time()}))
        self.assertFalse(identity_alive({'pid':process.pid,'create_time':process.create_time()-1}))

    def test_second_queue_is_rejected_before_reading_tasks_or_starting_fits(self):
        (ROOT/'test-runs').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'test-runs') as temp:
            directory=Path(temp)
            fixture=directory/'fixture.lock'
            child=("import sys\nfrom unittest.mock import patch\n"
                   "sys.path.insert(0,sys.argv.pop(1))\nfixture=sys.argv.pop(1)\n"
                   "from research_lock import ResearchLock\nimport overnight_research\n"
                   "with patch.object(overnight_research,'ResearchLock',lambda _path: ResearchLock(fixture)):\n"
                   " overnight_research.main()\n")
            command=[sys.executable,'-c',child,str(ROOT/'tools'),str(fixture),'--output',str(directory/'refused')]
            for name in ['after-campaign','after-identity','regression-task','classification-task','dsl-candidates']:
                command += ['--'+name,str(directory/'intentionally-missing')]
            with ResearchLock(fixture):
                result=subprocess.run(command,capture_output=True,text=True,timeout=15)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Another owned research queue holds the training lock',result.stderr)
            self.assertFalse((directory/'refused/queue.json').exists())

    def test_busy_contender_does_not_truncate_locked_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'research.lock'
            path.write_text(json.dumps({'old':'x'*1000}),encoding='utf-8')
            identity={'pid':123,'create_time':456.}
            with ResearchLock(path) as lock:
                lock.write_identity(identity)
                command=[sys.executable,'-c',
                    "import sys; from research_lock import ResearchLock\n"
                    "try:\n with ResearchLock(sys.argv[1]): pass\n"
                    "except BlockingIOError:\n sys.exit(23)\n",str(path)]
                result=subprocess.run(command,cwd=ROOT/'tools',capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,23,result.stderr)
                lock.stream.seek(0)
                self.assertEqual(json.loads(lock.stream.read()),identity)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')),identity)

    def test_exception_releases_lock_and_keeps_reserved_byte(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'research.lock'
            with self.assertRaisesRegex(RuntimeError,'fixture'):
                with ResearchLock(path) as lock:
                    lock.write_identity({'fixture':'held'})
                    raise RuntimeError('fixture')
            self.assertGreaterEqual(path.stat().st_size,1)
            with ResearchLock(path) as lock:
                lock.write_identity({'fixture':'reacquired'})
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')),{'fixture':'reacquired'})


if __name__=='__main__': unittest.main(verbosity=2)
