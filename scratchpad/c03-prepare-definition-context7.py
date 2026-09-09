from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
old = 'astra-native-budget13'
name = 'astra-definition-context7'
out = base / name
out.mkdir(exist_ok=False)
cases = json.loads((base / old / 'CASES.json').read_text(encoding='utf-8'))['development']
cases = [cases[i] for i in (0, 1, 2, 4)]
cases += [{'text_literal': text, 'source_references': [], 'kind': 'synthetic-context-regression-control'}
          for text in ('¿y para qué sirve?', 'define DNS', 'explain what DNS does')]
(out / 'CASES.json').write_text(json.dumps({'development': cases}, ensure_ascii=False, indent=2), encoding='utf-8')
(base / f'{name}.turns.jsonl').write_text(''.join(json.dumps({'cmd': 'turn', 'text': row['text_literal']}, ensure_ascii=False) + '\n' for row in cases), encoding='utf-8')
script = (root / 'scratchpad/c03-native-budget13.py').read_text(encoding='utf-8')
script = script.replace(old, name).replace('c03-native-budget13', 'c03-definition-context7')
start = script.index(" 'method':")
end = script.index("\n 'registrationSha256'", start)
script = script[:start] + " 'method':'Seven ordered development controls: inherited water/air/Steam/SSID sequence plus explicitly labeled synthetic reference and repeated-topic controls. Source scopes only the generation context for a new single-word definition topic; stored history remains intact. Native AUTO/budget256 and current published Core retained. Registered runtime without model/KV/PythonPath/sampling overrides. No effects or fault injections intended, no fresh acceptance or UI proof.'," + script[end:]
(root / 'scratchpad/c03-definition-context7.py').write_text(script, encoding='utf-8')
