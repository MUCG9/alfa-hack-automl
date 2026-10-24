"""Independent journal mock fixtures; no model, data, process, provider or clock."""
from pathlib import Path
import hashlib,importlib.util,json,tempfile,unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('_rq4_artifact_reader',Path(__file__).with_name('artifact_audit.py'))
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)

def frame(value):
    raw=json.dumps(value,separators=(',',':'),allow_nan=False).encode('utf-8')
    return b'OBS1 '+format(len(raw),'06x').encode()+b' '+hashlib.sha256(raw).hexdigest().encode()+b' '+raw+b'\n'

class FramedObservationContracts(unittest.TestCase):
    def test_exact_large_record_boundaries_and_partial_tail_preserve_only_original_latest(self):
        short={'sequence':2,'nonce':'synthetic-original'}
        empty={'padding':''};large={'padding':'x'*(262144-len(json.dumps(empty,separators=(',',':')).encode()))}
        encoded=frame(large);self.assertEqual(len(encoded),262144+78)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'observation.json'
            for raw in (encoded+encoded,frame({'sequence':1})+encoded+frame(short),encoded+frame(short)+frame({'sequence':3})[:40]):
                with self.subTest(size=len(raw)):
                    path.write_bytes(raw);checks=[]
                    value=A.framed_observation(path,lambda:checks.append(True))
                    self.assertEqual(value,large if raw==encoded+encoded else short)
                    self.assertEqual(path.read_bytes(),raw);self.assertGreater(len(checks),4)

    def test_complete_corruption_denials_nonobjects_and_missing_record_stop(self):
        good=frame({'sequence':1});bad_digest=bytearray(frame({'sequence':2}));bad_digest[12]=ord('0') if bad_digest[12]!=ord('0') else ord('1')
        raw_nonfinite=b'{"x":NaN}'
        nonfinite=b'OBS1 '+format(len(raw_nonfinite),'06x').encode()+b' '+hashlib.sha256(raw_nonfinite).hexdigest().encode()+b' '+raw_nonfinite+b'\n'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'observation.json'
            for raw in (bytes(bad_digest)+good,good+bytes(bad_digest),b'WRONG'+good[5:],frame([]),nonfinite,good[:20],b'x'*262225):
                with self.subTest(size=len(raw)):
                    path.write_bytes(raw)
                    with self.assertRaises((RuntimeError,ValueError,UnicodeError)):A.framed_observation(path)
            path.write_bytes(good)
            with patch.object(Path,'open',side_effect=PermissionError('synthetic denied')):
                with self.assertRaises(PermissionError):A.framed_observation(path)

if __name__=='__main__':unittest.main(verbosity=2)
