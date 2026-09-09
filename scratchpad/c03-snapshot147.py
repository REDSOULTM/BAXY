from pathlib import Path
import hashlib
import json
import shutil

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-source147-snapshot'
out.mkdir(exist_ok=False)
prereg=json.loads((base/'astra-voice148/PREREG.json').read_text(encoding='utf-8'))
paths=[*prereg['sources'],'tests/test_voice_capture_clock.py','tests/test_mind_voice_runtime.py','docs/AI_CONTEXT_MAP.md']
rows=[]
for name in paths:
    data=(root/name).read_bytes()
    digest=hashlib.sha256(data).hexdigest()
    if name in prereg['sources']:
        assert digest==prereg['sources'][name]
    target=out/name
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(data)
    rows.append({'source':name,'snapshot':str(target.relative_to(root)),'sha256':digest,'bytes':len(data)})
for name in ['c03-source143-owner-final.log','c03-source143-fast.log','c03-source147-owner.log','c03-source147-fast.log']:
    import tempfile
    source=Path(tempfile.gettempdir())/name
    target=out/name
    shutil.copyfile(source,target)
    rows.append({'source':str(source),'snapshot':str(target.relative_to(root)),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'bytes':target.stat().st_size})
(out/'INDEX.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
print(f'{len(rows)} immutable source/log snapshots')
