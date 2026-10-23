"""Read-only in-memory serialization diagnostic; no split regeneration or model fit."""
from pathlib import Path
import ast,copy,hashlib,io,json,struct,time,zipfile
W=Path(__file__).resolve().parent;original=json.loads((W/'original-cut-member-fingerprints-r1.json').read_text('utf-8'));remote=json.loads((W/'remote-incoming/remote-port-01/7f4cdec88fc2b82e80779e3b0ab27709f6f75101/artifacts/pure-checks.json').read_text('utf-8'));reported={(x['kind'],x['cut']):x for x in remote['partition_gate']['cuts']};cuts=[]
for entry in original['cuts']:
 kind,cut=entry['kind'],entry['cut'];p=W/'alfa-hack-automl/test-runs/2e'/('fe-'+kind)/'control_historical'/('seed-'+str(cut))/'split.npz';assert hashlib.sha256(p.read_bytes()).hexdigest()==entry['original_npz_sha256'];buffer=io.BytesIO()
 with zipfile.ZipFile(p) as source,zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as target:
  for info in source.infolist():
   b=source.read(info);n=2 if tuple(b[6:8])==(1,0) else 4;length=int.from_bytes(b[8:8+n],'little');end=8+n+length;header=ast.literal_eval(b[8+n:end].decode('latin1').strip());width=int(header['descr'][-1]);payload=b[end:]
   canonical=b''.join(struct.pack('<q',v) for (v,) in struct.iter_unpack('<i' if width==4 else '<q',payload));head=b[8+n:end].replace(b"'<i4'",b"'<i8'") if width==4 else b[8+n:end];assert len(head)==length
   zi=copy.copy(info);zi.create_system=3
   with target.open(zi,'w',force_zip64=True) as stream:stream.write(b[:8+n]+head+canonical)
 digest=hashlib.sha256(buffer.getvalue()).hexdigest();r=reported[kind,cut]
 cuts.append(dict(kind=kind,cut=cut,original_Windows_npz_sha256=entry['original_npz_sha256'],derived_Linux_i64_npz_sha256=digest,remote_reported_Linux_npz_sha256=r['npz_sha256'],exact_native_container_match=digest==r['npz_sha256']))
report=dict(schema=1,status='read_only_native_serialization_derivation',created_unix=time.time(),profile='numpy_savez_forcezip64_stored_member_order_train_validation_creator3_little_endian_i64',cuts=cuts,all5_derived_native_npz_match=all(x['exact_native_container_match'] for x in cuts),
 authority='Independent deterministic in-memory encoding of the original pinned ordered values. All original split files/rows/dtypes unchanged. Earlier strict rawbyte gates remain blocked; future versioned profile only after review. No fitting artifacts or indices published.',model_fits=0,API_calls=0)
out=W/'derived-linux-npz-fingerprints-r1.json';assert not out.exists();out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'all5_derived_native_npz_match':report['all5_derived_native_npz_match']}))
