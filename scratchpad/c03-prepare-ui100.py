from pathlib import Path
import datetime
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-ui100'
out.mkdir(exist_ok=False)
profile = Path(os.environ['LOCALAPPDATA']) / 'BAXY/dev-mente-v2'
sandbox = profile / 'filesystem-sandbox'
sandbox.mkdir(parents=True, exist_ok=True)
fixtures = {'c03-ui100-lectura.txt': 'Lectura técnica C03: el color de control es turquesa.\n'.encode('utf-8'),
    'c03-ui100-invalid-utf8.txt': b'\xff\xfe\x00C03 invalid UTF8\n'}
for name in fixtures:
    assert not (sandbox / name).exists(), name
assert not (sandbox / 'c03-ui100-ausente.txt').exists()
for name, data in fixtures.items():
    (sandbox / name).write_bytes(data)
cases = ['Dime la hora.',
    'Lee el archivo "c03-ui100-ausente.txt" del sandbox.',
    "Why couldn't you read that file?",
    'Lee el contenido del archivo "c03-ui100-lectura.txt" del sandbox.',
    'Read the file "c03-ui100-invalid-utf8.txt" in the sandbox.',
    "Why couldn't you read that file?",
    'Dime la hora, el audio y el uso de CPU.', 'Pon el volumen.']
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
model = Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')
with model.open('rb') as stream:
    model_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
prereg = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'method': 'Real desktop UI via py main.py and Windows Computer Use @oai/sky. '
    'No browser automation or --ui-probe. run_baxy.ps1 uses persistent dev-mente-v2; '
    'only two uniquely named new fixtures added, all previous data preserved. '
    'Eight predefined technical readonly/clarification requests; no volume value/effect supplied. '
    'Observe window readiness, progress and final language/facts. App trace is timing evidence; '
    'window screenshots/accessibility establish what is actually visible. --ui-capture alone '
    'does not activate FieldUiProbe, so it will not be used or claimed as passive capture. '
    'Qwen3.5 isolated override, wake disabled for this visual phase; voice/audio acceptance separate. '
    'No human reserve or promotion. No simultaneous models/builds after startup.',
    'profile': str(profile), 'model': str(model), 'modelSha256': model_sha,
    'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest(),
    'cases': cases, 'fixtures': {str(sandbox / k): hashlib.sha256(v).hexdigest() for k, v in fixtures.items()},
    'files': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in (
        'main.py', 'scripts/run_baxy.ps1', 'src/baxy_mind/llm.py', 'src/Baxy.App/MainWindowViewModel.cs')}}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
for name in ('CHECKPOINT.md', 'HANDOFF.md'):
    path = base / name
    content = path.read_text(encoding='utf-8')
    content = content.replace('--ui-capture permite registrar ventana sin --ui-probe.',
        '--ui-capture solo NO activa FieldUiProbe; no usarlo como captura pasiva.')
    content += ('\nUI100 preparado, no lanzado: astra-ui100/PREREG.json fija8turnos técnicos y2fixtures\n'
        'únicos en dev-mente-v2. Se usará py main.py con override Qwen3.5 y wake0,\n'
        'Computer Use sky ya inicializado. --ui-capture sin --ui-probe no captura nada.\n'
        'No modelos/procesos propios activos. Comprobar ventana/captura, luego voz aparte.\n')
    path.write_text(content, encoding='utf-8')
print('UI100 prepared; not launched.')
