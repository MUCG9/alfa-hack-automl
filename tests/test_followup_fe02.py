"""Follow-up refuses fitting while another coordinator owns the lock."""
from pathlib import Path
import fcntl
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import psutil
import followup_fe02 as followup


class FollowupTests(unittest.TestCase):
    def test_busy_lock_is_preserved_and_prevents_task_discovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'tools').mkdir()
            for name in ['protected_selection_worker.py', 'benchmark_candidates.py']:
                (root/'tools'/name).write_text('# no execution in this fixture\n')
            (root/'test-runs').mkdir()
            process = psutil.Process()
            identity = root/'predecessor.json'
            identity.write_text(json.dumps({'pid': process.pid, 'create_time': process.create_time()-1}))
            queue = root/'queue.json'
            queue.write_text(json.dumps({'status': 'completed', 'source_unchanged': True, 'source_sha256': {}}))
            output = root/'test-runs/followup'
            arguments = ['followup', '--after-identity', str(identity), '--after-queue', str(queue),
                         '--task', str(root/'must-not-read-task'), '--output', str(output)]
            with (root/'test-runs/.owned-research.lock').open('a+') as owner:
                fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch.object(followup, 'ROOT', root), patch.object(followup, 'source_hashes', return_value={}), \
                     patch.object(followup, 'discover') as discover, patch.object(sys, 'argv', arguments):
                    followup.main()
                discover.assert_not_called()
                self.assertEqual(json.loads((output/'followup.json').read_text())['status'], 'training_lock_busy')
                with (root/'test-runs/.owned-research.lock').open('a+') as probe:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(probe.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


if __name__ == '__main__':
    unittest.main(verbosity=2)
