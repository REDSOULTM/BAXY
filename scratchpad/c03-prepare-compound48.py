from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-compound-shell48'
out.mkdir(exist_ok=False)
texts = [
    'Dime la hora, revisa el estado del audio y dime el uso de CPU.',
    'Dime la hora y el estado del audio.',
    'Tell me the time and the volume.',
    'What time is it y cómo está el audio?',
    'Dime la hora y no silencies el audio.',
    'Dime la hora y revisa la CPU',
    '¿Cómo está el audio?',
]
out.with_suffix('.turns.jsonl').write_text('\n'.join(json.dumps({'cmd': 'turn', 'text': t}, ensure_ascii=False) for t in texts) + '\n', encoding='utf-8')
(out / 'CASES.json').write_text(json.dumps({'kind': 'consumed and synthetic technical regression', 'texts': texts,
    'expectedOperations': [['system.time', 'audio.status', 'system.status'], ['system.time', 'audio.status'],
                           ['system.time', 'audio.status'], ['system.time', 'audio.status'], ['system.time'],
                           ['system.time', 'system.status'], ['audio.status']],
    'scope': 'Read-only PC observations; no effects, no acceptance reserve, no UI/voice claim.'}, ensure_ascii=False, indent=2), encoding='utf-8')
driver = (root / 'scratchpad/c03-scoped-reader11.py').read_text(encoding='utf-8').replace('scoped-reader11', 'compound-shell48')
method = ('Source47 plus removal of C# clock/audio substring shortcut and fixed two-step plan. '
          'Same triple request that droppedCPU in wire-context47; known ES/EN/mixed pair controls and independent prohibition. '
          'Registered runtime, no hook/PythonPath/model/sampler overrides. Read-only conductor, not UI or voice acceptance. '
          'Candidate uses existing literal reader and generic mission path, with current progress composition. '
          'No new classifier/regex. Prior context differs from baseline13, so compare requested operations, verified facts '
          'and completeness, not prose identity or latency as a controlled improvement.')
driver = driver.replace('manifest_hash = sha(manifest_path)', "files += ['src/baxy_mind/voice_output.py', 'src/Baxy.App/NaturalSystemStatusRequestParser.cs', 'artifacts/comprobaciones/C03/TRAMO47_PINS.json']\nmanifest_hash = sha(manifest_path)")
driver = driver.replace("(out/'PREREG.json').write_text", f"prereg['method'] = {method!r}\n(out/'PREREG.json').write_text", 1)
(root / 'scratchpad/c03-compound-shell48.py').write_text(driver, encoding='utf-8')
print('Prepared7 read-only compound controls.')
