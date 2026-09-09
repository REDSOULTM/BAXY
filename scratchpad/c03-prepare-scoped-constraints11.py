from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
old = 'astra-reference-context11'
name = 'astra-scoped-constraints11'
out = base / name
out.mkdir(exist_ok=False)
(out / 'CASES.json').write_bytes((base / old / 'CASES.json').read_bytes())
(base / f'{name}.turns.jsonl').write_bytes((base / f'{old}.turns.jsonl').read_bytes())
script = (root / 'scratchpad/c03-reference-context11.py').read_text(encoding='utf-8')
script = script.replace(old, name).replace('c03-reference-context11', 'c03-scoped-constraints11')
script = script.replace('Compound conservation and other gates remain.', 'The App shortcut for negative substrings is removed, so complete requests cross turn.decide. Compound conservation counts positive effects; a negative clause does not globally ban a separate positive clause. Standalone negatives, explicit no-tools, correction, device and missing-effect guards remain. Same eleven ordered inputs as reference-context11.')
(root / 'scratchpad/c03-scoped-constraints11.py').write_text(script, encoding='utf-8')
