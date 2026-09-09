from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
name = 'astra-reference-context11'
out = base / name
out.mkdir(exist_ok=False)
cases = json.loads((base / 'astra-definition-context7/CASES.json').read_text(encoding='utf-8'))['development']
cases = cases[:5]
cases += [{'text_literal': text, 'source_references': [], 'kind': 'synthetic-scope-and-recovery-control'}
          for text in ('no me molesta, dime la hora', "I don't mind, tell me the time",
                       'no abras Steam, dime la hora', 'no uses herramientas, dime la hora',
                       'no me digas la hora', 'dime la hora')]
(out / 'CASES.json').write_text(json.dumps({'development': cases}, ensure_ascii=False, indent=2), encoding='utf-8')
(base / f'{name}.turns.jsonl').write_text(''.join(json.dumps({'cmd': 'turn', 'text': row['text_literal']}, ensure_ascii=False) + '\n' for row in cases), encoding='utf-8')
script = (root / 'scratchpad/c03-public-host3.py').read_text(encoding='utf-8')
script = script.replace('astra-public-host3', name).replace('c03-public-host3', 'c03-reference-context11')
start = script.index(" 'method':")
end = script.index("\n 'registrationSha256'", start)
script = script[:start] + " 'method':'Eleven consumed definition/follow-up and labeled synthetic scope/recovery controls. Native AUTO receives the same literal current request and bounded history as reference data. Catalog recovery uses contextual AUTO rather than the old weak per-operation identity classifier. Compound conservation and other gates remain. Registered runtime, no model/sampling/KV/PYTHONPATH overrides; no intended mutations, fault injection, UI or fresh acceptance.'," + script[end:]
(root / 'scratchpad/c03-reference-context11.py').write_text(script, encoding='utf-8')
