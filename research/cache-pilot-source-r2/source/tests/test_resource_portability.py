"""Peak memory units on supported platforms; no model fits or API calls."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from automl.infrastructure import resources


class PeakMemoryPortabilityTests(unittest.TestCase):
    def test_linux_keeps_kib_to_mib_scaling(self):
        usage=Mock(return_value=SimpleNamespace(ru_maxrss=131072))
        posix=SimpleNamespace(RUSAGE_SELF=0,getrusage=usage)
        with (patch.object(resources.sys,'platform','linux'),
              patch.object(resources,'resource',posix),
              patch.object(resources.psutil,'Process',side_effect=AssertionError('POSIX uses getrusage'))):
            self.assertEqual(resources.peak_rss_mb(),128.)
        usage.assert_called_once_with(posix.RUSAGE_SELF)

    def test_windows_uses_peak_working_set_bytes_not_current_rss(self):
        process=Mock()
        process.memory_info.return_value=SimpleNamespace(peak_wset=256*2**20,rss=4*2**20)
        with (patch.object(resources.sys,'platform','win32'),
              patch.object(resources,'resource',None),
              patch.object(resources.os,'getpid',return_value=12345),
              patch.object(resources.psutil,'Process',return_value=process) as factory):
            self.assertEqual(resources.peak_rss_mb(),256.)
        factory.assert_called_once_with(12345)
        process.memory_info.assert_called_once_with()

    def test_macos_scales_resource_bytes_to_mib(self):
        posix=SimpleNamespace(RUSAGE_SELF=0,getrusage=Mock(return_value=SimpleNamespace(ru_maxrss=384*2**20)))
        with patch.object(resources.sys,'platform','darwin'),patch.object(resources,'resource',posix):
            self.assertEqual(resources.peak_rss_mb(),384.)


if __name__=='__main__':
    unittest.main()
