"""Replay the captured account observation through adopted source, no guard patch."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import json
import runpy

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-account284'
# Reuse only imports and the transport adapter from the frozen comparison.
# Do not execute its experiment or its guard replacement.
tree = ast.parse((root / 'scratchpad/c03-identity283.py').read_text(encoding='utf-8'))
imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
imports = [node for node in imports if not (isinstance(node, ast.ImportFrom) and node.module == 'baxy_mind')]
scope = {}
exec(compile(ast.Module(body=imports, type_ignores=[]), '<imports283>', 'exec'), scope)
scope['sys'].path.insert(0, str(root / 'src'))
from baxy_mind import llm
scope['llm'] = llm
adapter = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Runtime')
exec(compile(ast.Module(body=[adapter], type_ignores=[]), '<transport283>', 'exec'), scope)
prereg = json.loads((root / 'artifacts/comprobaciones/C03/astra-identity283/PREREG.json').read_text(encoding='utf-8'))
record = {
    'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Actual source284, same request, observed facts and transport adapter as283. No monkeypatch. Native backend only; no UI or operation effects.',
    'sourceSha256': hashlib.sha256((root / 'src/baxy_mind/llm.py').read_bytes()).hexdigest(),
    'request': prereg['request'], 'facts': prereg['facts'],
}
(out / 'NATIVE_PREREG.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
runtime = scope['Runtime']()
try:
    record['answer'] = runtime.compose_user_message(prereg['request'], 'status', prereg['facts'])
except Exception as error:
    record['error'] = repr(error)
record['posts'] = runtime.posts
previous = json.loads((root / 'artifacts/comprobaciones/C03/astra-identity283/RESULT.json').read_text(encoding='utf-8'))
record['initialPayloadEquals283'] = runtime.posts[0]['payload'] == previous[0]['posts'][0]['payload']
(out / 'NATIVE_RESULT.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({key: value for key,value in record.items() if key not in ('posts','facts')}, ensure_ascii=False))
assert record['initialPayloadEquals283']
assert 'answer' in record
assert 'usuario' in record['answer'].casefold()
