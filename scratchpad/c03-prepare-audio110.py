from pathlib import Path
import datetime
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-audio110'
out.mkdir(exist_ok=False)
prior = json.loads((base / 'astra-ui109/PREREG.json').read_text(encoding='utf-8'))
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()
registration = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
assert sha(registration) == prior['registrationSha256']
assert sha(prior['model']) == prior['modelSha256']
paths = list(prior['files']) + ['src/baxy_mind/voice_output.py', 'src/baxy_mind/voice.py',
    'src/baxy_mind/voice_aec.py','scratchpad/c03-capture-audio110.py']
data = {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'method':'Same source108, Qwen3.5 override, full registered voice stack with wake on. '
      'Real desktop via py main.py, Computer Use inputs, no diagnostic PythonPath/hook. '
      'Three inherited technical clock requests ES/EN/mixed, not human reserve. '
      'Record microphone(default MME Realtek input1,16kmono) and separate WASAPI '
      'loopback(default Realtek endpoint13,48kstereo) outside repository for up to180s. '
      'Original audio is level0/muted true; temporarily use0.30/unmuted and restore '
      'both in recorder finally. Capture greeting and responses; inspect acoustic '
      'energy/transcription locally after stopping product, never count loopback '
      'as room/microphone evidence. Resource sampler attaches only to newly launched '
      'App before readiness; no other models/builds. No voice-input acceptance yet.',
    'cases':['Dime la hora.','What time is it?','Dime la hora, please.'],
    'model':prior['model'], 'modelSha256':prior['modelSha256'],
    'registrationSha256':prior['registrationSha256'], 'profile':prior['profile'],
    'sourceFiles':{p:sha(root / p) for p in paths},
    'heritage':['ASTRA-TRAMO-45.md','PRUEBAS_VOZ_UI_C03.md','PRUEBAS_UI109.md'],
    'primarySource':'https://python-sounddevice.readthedocs.io/en/0.5.5/api/streams.html',
    'primarySourceConsulted':'2026-09-07; same installed0.5.5; InputStream.read with owned stream, no callback',
    'notAcceptance':['fresh human100','physical speech input','registered model promotion','full gate']}
(out / 'PREREG.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
print('Audio110 preregistered; no recording, volume change or launch yet.')
