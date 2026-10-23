"""Diagnostic only: compare original ordered-value hashes with sealed remote metadata."""
from pathlib import Path
import ast,hashlib,json,struct,time,zipfile
W=Path(__file__).resolve().parent;P=W/'original-cut-member-fingerprints-r1.json';original=json.loads(P.read_text('utf-8'));B=W/'remote-incoming/remote-port-01/7f4cdec88fc2b82e80779e3b0ab27709f6f75101';remote=json.loads((B/'artifacts/pure-checks.json').read_text('utf-8'))
reported={(x['kind'],x['cut']):x for x in remote['partition_gate']['cuts']};out=[]
for entry in original['cuts']:
 kind,cut=entry['kind'],entry['cut'];r=reported[kind,cut]
 p=W/'alfa-hack-automl/test-runs/2e'/('fe-'+kind)/'control_historical'/('seed-'+str(cut))/'split.npz';assert hashlib.sha256(p.read_bytes()).hexdigest()==entry['original_npz_sha256']
 combined=hashlib.sha256();members=[]
 with zipfile.ZipFile(p) as archive:
  for info in archive.infolist():
   b=archive.read(info);n=2 if tuple(b[6:8])==(1,0) else 4;length=int.from_bytes(b[8:8+n],'little');end=8+n+length;h=ast.literal_eval(b[8+n:end].decode('latin1').strip());width=int(h['descr'][-1]);payload=b[end:]
   normalized=b''.join(struct.pack('<q',v) for (v,) in struct.iter_unpack('<i' if width==4 else '<q',payload));combined.update(normalized)
   head=b[8+n:end];newhead=head.replace(b"'<i4'",b"'<i8'") if width==4 else head;assert len(newhead)==len(head)
   npy64=b[:8+n]+newhead+normalized
   expected_hash=hashlib.sha256(npy64).hexdigest();rm=next(x for x in r['diagnostic']['members'] if x['name']==info.filename)
   members.append(dict(name=info.filename,original_dtype=h['descr'],original_shape=h['shape'],expected_little_endian_i64_npy_sha256=expected_hash,remote_reported_npy_sha256=rm['uncompressed_member_sha256'],matches=expected_hash==rm['uncompressed_member_sha256']))
 out.append(dict(kind=kind,cut=cut,original_npz_sha256=entry['original_npz_sha256'],remote_npz_sha256=r['npz_sha256'],raw_container_matches=entry['original_npz_sha256']==r['npz_sha256'],
  original_canonical_concat_sha256=combined.hexdigest(),remote_reported_ordered_i64_concat_sha256=r['ordered_indices_sha256'],ordered_values_match=combined.hexdigest()==r['ordered_indices_sha256'],members=members))
report=dict(schema=1,status='original_vs_sealed_remote_metadata_diagnostic',created_unix=time.time(),remote_result_sha='7f4cdec88fc2b82e80779e3b0ab27709f6f75101',original_members_manifest_sha256=hashlib.sha256(P.read_bytes()).hexdigest(),cuts=out,
 all5_ordered_values_match=all(x['ordered_values_match'] for x in out),all10_expected_i64_npy_members_match=all(m['matches'] for x in out for m in x['members']),
 observations='Original Windows regression arrays are int64, classification arrays int32. Remote harness requires int64. A diagnostic little-endian int64 encoding of original ordered values is compared with sealed remote hashes; no files/rows/order or earlier gate result are changed.',
 limitations='Remote hashes remain reported evidence, not possession of remote private arrays. Old raw-byte gate remains blocked. A separate versioned cross-platform serialization contract must be reviewed before later fits.',model_fits=0,API_calls=0)
target=W/'remote-original-cut-identity-diagnostic-r1.json';assert not target.exists();target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'diagnostic_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'all5_ordered_values_match':report['all5_ordered_values_match'],'all10_i64_npy_members_match':report['all10_expected_i64_npy_members_match'],'old_raw_gate_unchanged':True}))
