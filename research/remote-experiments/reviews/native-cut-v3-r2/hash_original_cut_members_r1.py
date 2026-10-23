"""Read five pristine split containers; publish only headers/hashes, never row indices."""
from pathlib import Path
import ast,hashlib,json,struct,time,zipfile
W=Path(__file__).resolve().parent;M=W/'alfa-hack-automl/research/remote-experiments/sources/fixed-cut-manifest-r2.json';meta=json.loads(M.read_text('utf-8'))
out=[]
for cut in meta['cuts']:
 p=W/'alfa-hack-automl/test-runs/2e'/('fe-'+cut['kind'])/'control_historical'/('seed-'+str(cut['cut']))/'split.npz'
 raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==cut['saved_npz_sha256'];members=[]
 with zipfile.ZipFile(p) as archive:
  assert archive.namelist()==['train.npy','validation.npy']
  for info in archive.infolist():
   b=archive.read(info);assert b[:6]==b'\x93NUMPY';version=tuple(b[6:8]);n=2 if version==(1,0) else 4;header_length=int.from_bytes(b[8:8+n],'little');start=8+n+header_length;header=ast.literal_eval(b[8+n:start].decode('latin1').strip());payload=b[start:]
   assert header['fortran_order'] is False and len(header['shape'])==1 and header['descr'] in ['<i4','<i8']
   width=int(header['descr'][-1]);assert len(payload)==header['shape'][0]*width
   canonical=hashlib.sha256();count=0
   for (value,) in struct.iter_unpack('<i' if width==4 else '<q',payload):
    assert value>=0;canonical.update(struct.pack('<q',value));count+=1
   assert count==header['shape'][0]
   members.append(dict(name=info.filename,npy_header=header,npy_bytes=len(b),npy_sha256=hashlib.sha256(b).hexdigest(),payload_sha256=hashlib.sha256(payload).hexdigest(),canonical_ordered_values_profile='nonnegative_index_le_i64_v1',canonical_ordered_values_sha256=canonical.hexdigest(),zip_creator_system=info.create_system,zip_compress_type=info.compress_type,zip_external_attr=info.external_attr))
 out.append(dict(kind=cut['kind'],cut=cut['cut'],original_npz_sha256=cut['saved_npz_sha256'],members=members))
report=dict(schema=1,status='read_only_original_split_header_hashes_no_fits',created_unix=time.time(),cuts=out,source_manifest_sha256=hashlib.sha256(M.read_bytes()).hexdigest(),canonicalization_scope='Diagnostic hashing of original nonnegative integer values only. Original files/rows/order/dtypes unchanged; no authority to replace earlier raw-byte gates.',source_data_or_indices_published=False,model_fits=0,API_calls=0)
P=W/'original-cut-member-fingerprints-r1.json';assert not P.exists();P.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'output_sha256':hashlib.sha256(P.read_bytes()).hexdigest(),'cuts':[dict(kind=x['kind'],cut=x['cut'],member_dtypes=[m['npy_header']['descr'] for m in x['members']]) for x in out],'model_fits':0}))
