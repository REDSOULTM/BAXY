import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
name = 'astra-clause-scope5'
out = base / name
out.mkdir(exist_ok=False)
texts = ['no me molesta, dime la hora', "I don't mind, tell me the time", 'no abras Steam, dime la hora', 'no me digas la hora', 'dime la hora']
(out / 'CASES.json').write_text(json.dumps({'development': [{'text_literal': t, 'kind': 'synthetic-regression-control', 'source_references': []} for t in texts]}, ensure_ascii=False, indent=2), encoding='utf-8')
(base / f'{name}.turns.jsonl').write_text(''.join(json.dumps({'cmd': 'turn', 'text': t}, ensure_ascii=False)+'\n' for t in texts), encoding='utf-8')
script = (root/'scratchpad/c03-audio-endpoint-name3.py').read_text(encoding='utf-8')
script = script.replace('astra-audio-endpoint-name3', name).replace('c03-audio-endpoint-name3', 'c03-clause-scope5')
script = script.replace('Three previously consumed literal audio requests: identify output, read level, read mute.', 'Five synthetic regression controls: positive clock read after social negation ES/EN, distinct app prohibition plus clock read, pure prohibition, clock recovery. No app launch is authorized or expected. The existing clause resolver now recognizes a direct request in a later clause. No change to negative-authority guards.')
(root/'scratchpad/c03-clause-scope5.py').write_text(script, encoding='utf-8')
