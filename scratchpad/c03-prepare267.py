"""Freeze compose evidence provenance before changing its serialization."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil

root = Path(__file__).resolve().parents[1]
out = root/'artifacts/comprobaciones/C03/astra-compose-provenance267'
out.mkdir(exist_ok=False)
(out/'before').mkdir()
sources = ['src/baxy_mind/llm.py', 'tests/test_compose_contract.py']
for name in sources:
    shutil.copy2(root/name, out/'before'/Path(name).name)
wire = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui263-private/http-posts.jsonl'
data = {'utc':datetime.now(timezone.utc).isoformat(),
    'hypothesis':'A previous assistant utterance is dialogue context, not a verified observation. UI263 HTTP9 put Steam ya está abierto inside situation while the existing system message designates situation as evidence. Separate the same literal context outside situation without changing the system instructions, sampler, or verified facts.',
    'method':'Inspect exact saved UI263 packets and generation/audit. Test actual compose serialization on first/retry/third attempts, keeping historical reference context and typed current results distinct. No inference against the owner264 process, no UI inputs, no reading its new messages.',
    'criteria':'Previous prose cannot enter visible situation; current verified observations remain identical with/without previous prose. Context remains available as escaped JSON data on the appropriate conversation path in every attempt. No replayed assistant role, fixed response, new validator phrase, or new system prompt.',
    'limits':'Packet/unit evidence does not prove native generation or public acceptance; remaining retrieval and publication guard failures stay open. Native before/after and final UI must follow when they can run without disturbing owner testing.',
    'sourceBefore':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sources},
    'wireSha256':hashlib.sha256(wire.read_bytes()).hexdigest(),
    'primarySource':'https://qwen.readthedocs.io/en/latest/framework/function_call.html',
    'inheritance':['INVESTIGACION_MODELO_C03.md','INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md','PRUEBAS_UI263.md']}
(out/'PREREG.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(out)
