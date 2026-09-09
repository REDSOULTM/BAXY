from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
name = 'astra-integrated-real22'
out = base / name
out.mkdir(exist_ok=False)
source = 'astra-real-users-constraints22'
(out / 'CASES.json').write_bytes((base / source / 'CASES.json').read_bytes())
(base / f'{name}.turns.jsonl').write_bytes((base / f'{source}.turns.jsonl').read_bytes())
script = (root / 'scratchpad/c03-public-host3.py').read_text(encoding='utf-8')
script = script.replace('astra-public-host3', name).replace('c03-public-host3', 'c03-integrated-real22')
start = script.index(" 'method':")
end = script.index("\n 'registrationSha256'", start)
script = script[:start] + " 'method':'Replay the twenty consumed literal corpus requests and two explicit volume cleanup/readback commands from astra-real-users-constraints22, unchanged order/text. Current integrated source after native reference-data selection, contextual catalog recovery, scoped compound conservation, removal of the App negative shortcut and native dead-branch cleanup. Intended effects are local reads and volume35 then100; final cleanup explicitly sets100 and reads back. No external messaging, no app launching, no UI/fault injections or fresh acceptance. Registered runtime without model/KV/PythonPath/sampling overrides. Preserve all failures; this is regression/development, not the hundred-turn reserve.'," + script[end:]
(root / 'scratchpad/c03-integrated-real22.py').write_text(script, encoding='utf-8')
