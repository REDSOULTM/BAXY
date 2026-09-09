from pathlib import Path
import datetime
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-audio121'
out.mkdir(exist_ok=False)
for source, destination in (('c03-capture-audio110.py', 'c03-capture-audio121.py'),
                            ('c03-launch-audio110.py', 'c03-launch-audio121.py')):
    text = (root / 'scratchpad' / source).read_text(encoding='utf-8').replace('audio110', 'audio121')
    if source.startswith('c03-capture'):
        text = text.replace('180', '300')
    with (root / 'scratchpad' / destination).open('x', encoding='utf-8', newline='\n') as f:
        f.write(text)
prior = json.loads((base / 'astra-audio110/PREREG.json').read_text(encoding='utf-8'))
native = json.loads((base / 'astra-native-voice120/PREREG.json').read_text(encoding='utf-8'))
def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
assert sha(manifest) == native['registrationSha256'] == prior['registrationSha256']
paths = set(prior['sourceFiles']) - {'scratchpad/c03-capture-audio110.py'}
paths.update(native['sources'])
paths.update({'scratchpad/c03-capture-audio121.py', 'scratchpad/c03-launch-audio121.py'})
prereg = {**prior, 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'method': 'Source119 actual py main.py desktop, same Qwen3.5 override/full registered voice '
                    'wake1 as110. New Piper runtime and English voice are staged candidate assets, '
                    'manifest not promoted. Three inherited clocks ES/EN/mixed, not human reserve. '
                    'Record real default microphone and WASAPI loopback privately for up to300s '
                    '(110 final window was truncated at180s). Stop only after final audio window. '
                    'Temporarily set actual endpoint0.30/unmuted, restore its exact initial state. '
                    'No PythonPath hooks, device sink, draft injection or concurrent model/build. '
                    'Sampler owns new App tree before readiness, tracks Piper children too. '
                    'No voice-input acceptance in this run; acoustic content must be analyzed.',
          'sourceFiles': {p: sha(root / p) for p in sorted(paths)},
          'ttsModels': native['models'], 'piperRuntime': native['runtime'],
          'piperRuntimeSha256': native['runtimeSha256'],
          'heritage': ['PRUEBAS_AUDIO110_NATIVE111.md', 'PRUEBAS_TTS114_118.md', 'ASTRA-TRAMO-119.md']}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
print('Audio121 preregistered; no launch, capture or volume change yet.')
