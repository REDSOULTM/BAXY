from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
old = 'astra-definition-context7'
name = 'astra-public-host3'
out = base / name
out.mkdir(exist_ok=False)
cases = json.loads((base / old / 'CASES.json').read_text(encoding='utf-8'))['development']
cases = [cases[index] for index in (3, 5, 6)]
(out / 'CASES.json').write_text(json.dumps({'development': cases}, ensure_ascii=False, indent=2), encoding='utf-8')
(base / f'{name}.turns.jsonl').write_text(''.join(json.dumps({'cmd': 'turn', 'text': row['text_literal']}, ensure_ascii=False) + '\n' for row in cases), encoding='utf-8')
script = (root / 'scratchpad/c03-definition-context7.py').read_text(encoding='utf-8')
script = script.replace(old, name).replace('c03-definition-context7', 'c03-public-host3')
start = script.index(" 'method':")
end = script.index("\n 'registrationSha256'", start)
script = script[:start] + " 'method':'Three consumed definition/DNS controls retained from definition-context7. Python and App now distinguish syntactically explicit public web hosts (http(s) or www) from internal dotted operation codes. Other internal-code checks retained with positive and negative owner tests. Verify that a correct knowledge answer containing a hostname reaches the user without unnecessary recomposition. Existing context/native candidate retained; no effects, UI, overrides or fresh acceptance.'," + script[end:]
script = script.replace("files.append('src/Baxy.App/bin", "files.append('src/Baxy.App/UserMessagePolicy.cs')\nfiles.append('src/Baxy.App/bin")
(root / 'scratchpad/c03-public-host3.py').write_text(script, encoding='utf-8')
