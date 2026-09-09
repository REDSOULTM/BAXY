from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-wire-context47'
out.mkdir(exist_ok=False)
missing = Path('C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt')
assert not missing.exists()
commands = (base / 'astra-routes-volume46.turns.jsonl').read_text(encoding='utf-8').splitlines()[:10]
extras = [
    'Dime la hora, revisa el estado del audio y dime el uso de CPU.',
    f'Lee el archivo "{missing.as_posix()}".',
    '¿Qué hora es?',
]
commands.extend(json.dumps({'cmd': 'turn', 'text': text}, ensure_ascii=False) for text in extras)
out.with_suffix('.turns.jsonl').write_text('\n'.join(commands) + '\n', encoding='utf-8')
cases = {'kind': 'consumed technical prefix10 plus3 synthetic diagnostics', 'missingFileVerifiedAbsent': str(missing),
         'extras': extras, 'effectScope': 'Read-only local clock/audio/CPU and a missing file; no audio adjustment or user file mutation.'}
(out / 'CASES.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding='utf-8')
driver = (root / 'scratchpad/c03-scoped-reader11.py').read_text(encoding='utf-8').replace('scoped-reader11', 'wire-context47')
driver = driver.replace('manifest_hash = sha(manifest_path)', "files += ['src/baxy_mind/voice_output.py', 'scratchpad/c03-wire-hook47/sitecustomize.py', 'artifacts/comprobaciones/C03/TRAMO46_PINS.json']\nmanifest_hash = sha(manifest_path)")
method = ('Capture exact product payloads and replies through an opt-in read-only sitecustomize wrapper of LlmRuntime._post. '
          'Same registered model/backend/template/sampler and product source46, PythonPath adds only diagnostic hook. '
          'First10 consumed technical turns reproduce the history leading to gravity; not a repeat33 to seek a pass. '
          'Then3 separate read-only diagnostics for compound progress, missing-file error and a normal clock recovery. '
          'No fresh acceptance or UI/audio claim. Hook adds I/O overhead, so not a performance benchmark. '
          'No captured packet is modified. Existing16-call context comparison did not reproduce the Moon phrase; '
          'C# last12messages includes current input, leaving an older orphan assistant that the five-pair reconstruction omitted.')
driver = driver.replace("(out/'PREREG.json').write_text", f"prereg['method'] = {method!r}\n(out/'PREREG.json').write_text", 1)
driver = driver.replace("app=ROOT/", "env.update(BAXY_MIND_PYTHONPATH=str(ROOT/'scratchpad/c03-wire-hook47')+os.pathsep+str(ROOT/'src'), C03_WIRE_TRACE_DIR=str(out))\napp=ROOT/")
driver = driver.replace('no readiness instrumentation or runtime overrides.', 'payload logging hook enabled; model/backend/sampler unchanged.')
(root / 'scratchpad/c03-wire-context47.py').write_text(driver, encoding='utf-8')
print('Prepared13 read-only technical inputs and exact-wire diagnostic driver.')
