"""Cross-process exclusion and PID identity for the development research queue."""
from pathlib import Path
import fcntl
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import psutil
from overnight_research import identity_alive


class OwnedResearchTests(unittest.TestCase):
    def test_process_identity_uses_creation_time_not_only_pid(self):
        process=psutil.Process()
        self.assertTrue(identity_alive({'pid':process.pid,'create_time':process.create_time()}))
        self.assertFalse(identity_alive({'pid':process.pid,'create_time':process.create_time()-1}))

    def test_second_queue_is_rejected_before_reading_tasks_or_starting_fits(self):
        (ROOT/'test-runs').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'test-runs') as temp, (ROOT/'test-runs/.owned-research.lock').open('a+') as lock:
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            directory=Path(temp)
            command=[sys.executable,str(ROOT/'tools/overnight_research.py'),'--output',str(directory/'refused')]
            for name in ['after-campaign','after-identity','regression-task','classification-task','dsl-candidates']:
                command += ['--'+name,str(directory/'intentionally-missing')]
            result=subprocess.run(command,capture_output=True,text=True,timeout=15)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Another owned research queue holds the training lock',result.stderr)
            self.assertFalse((directory/'refused/queue.json').exists())
            fcntl.flock(lock.fileno(),fcntl.LOCK_UN)


if __name__=='__main__': unittest.main(verbosity=2)
