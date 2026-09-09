from pathlib import Path
import datetime
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-ui109'
out.mkdir(exist_ok=False)
prior = json.loads((base / 'astra-ui107/PREREG.json').read_text(encoding='utf-8'))
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
registration = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
assert sha(registration) == prior['registrationSha256']
assert sha(prior['model']) == prior['modelSha256']
paths = [
    'src/baxy_mind/llm.py', 'src/baxy_mind/__main__.py',
    'src/Baxy.App/MainWindowViewModel.cs', 'src/Baxy.App/FieldProductChannel.cs',
    'src/Baxy.App/MindSidecarClient.cs',
    'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.dll',
    'src/Baxy.FieldUi/src/types.ts', 'src/Baxy.FieldUi/src/components/NeuralGraph.tsx',
    'src/Baxy.FieldUi/src/components/FieldCenter.tsx',
    'src/Baxy.FieldUi/src/components/LogoMark.tsx',
    'src/Baxy.FieldUi/src/App.tsx', 'src/Baxy.FieldUi/src/styles/prototype.css',
    'src/Baxy.FieldUi/src/hooks/useEventStream.ts', 'src/Baxy.FieldUi/ORIGIN.md',
    'src/Baxy.FieldUi/dist/index.html', 'src/Baxy.FieldUi/dist/assets/index-Dh8gdcnz.js',
    'src/Baxy.FieldUi/dist/assets/index-B7EBy9jN.css']
prereg = {
    'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'method': 'Source108 via py main.py, same source103 UI107 first three technical '
        'clock requests and same local Qwen3.5 override/wake0. Suspend only the '
        'verified owned llama-server descendant, observe pending and exhausted '
        'composition in the real desktop, resume that same process and ask the '
        'same clock again. Expect Thinking while pending, Error/Response error '
        'when exhausted with input available, no raw SYSTEM activity fallback, '
        'and useful recovery clearing the error without restarting App/server. '
        'No new model/prompt, injection, confirmation replay, human reserve or '
        'audio acceptance. Existing helper watchdog resumes within300s.',
    'cases': prior['cases'][:3], 'model': prior['model'],
    'modelSha256': prior['modelSha256'],
    'registrationSha256': prior['registrationSha256'], 'profile': prior['profile'],
    'files': {p: sha(root / p) for p in paths},
    'heritage': ['PRUEBAS_UI107.md', 'ASTRA-TRAMO-108.md'],
}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
for before, after in [('c03-ui107-resources.py','c03-ui109-resources.py'),
                      ('c03-suspend-ui107.py','c03-suspend-ui109.py')]:
    text = (root / 'scratchpad' / before).read_text(encoding='utf-8')
    assert text.count('astra-ui107') == 1
    (root / 'scratchpad' / after).write_text(text.replace('astra-ui107','astra-ui109'), encoding='utf-8', newline='\n')
print('UI109 preregistered; no processes launched or suspended.')
