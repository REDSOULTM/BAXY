"""Literal review of unchanged and patched native decoder, all controls retained."""
from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
def read(path):
    return json.loads(path.read_text(encoding='utf-8'))
baseline = read(base/'astra-native205-baseline/RESULTS.json')
patched = read(base/'astra-native205-patched/RESULTS.json')
assert len(baseline) == len(patched) == 47
assert all(row['text'] == row['installedBeamText'] for row in baseline if row['installedBeamText'] is not None)
assert baseline[-1]['silenceControl'] and patched[-1]['silenceControl']
lines = ['# C03 — comparación nativa de sherpa-onnx 1.13.4 y PR3657', '',
    'La compilación sin parche reproduce literalmente las 46 lecturas previas comparables. Sobre silencio produce «Thank you.»; la propuesta lo deja vacío. Mismos 47 controles, CPU6/beam8, sin hotwords, cambios de audio ni dispositivos. La propuesta upstream está abierta; estos resultados no constituyen promoción ni aceptación del producto. El primer intento de este informe falló porque suponía incorrectamente silencio vacío en baseline; las transcripciones originales se conservan intactas.', '',
    '| Caso | Contenido de entrada | Sin parche | Con PR3657 |',
    '|---|---|---|---|']
changed = []
def cell(text):
    return text.replace('|', '\\|').replace('\n', ' ') if text else '(vacío)'
for index, (old, new) in enumerate(zip(baseline, patched, strict=True)):
    keys = ['case','human','condition','engine','segment','humanOverlapSamples','original','silenceControl']
    assert all(old.get(key) == new.get(key) for key in keys)
    if 'case' in old:
        label = f"{old['case']}/{old['segment']}"
        content = f"humano {old['human']}, {old['condition']}, {old['engine']}, solape humano {old['humanOverlapSamples']} muestras"
    elif old.get('original'):
        label = f"original {old['human']}"
        content = 'WAV humano original con padding197'
    else:
        label, content = 'silencio', 'dos segundos de ceros'
    lines.append(f"| {label} | {content} | {cell(old['text'])} | {cell(new['text'])} |")
    if old['text'] != new['text']:
        changed.append({'index': index, 'case': label, 'content': content,
            'before': old['text'], 'after': new['text']})
out = base/'astra-sherpa205'
(out/'COMPARISON.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
(out/'DIFFERENCES.json').write_text(json.dumps(changed, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'total': len(patched), 'changed': len(changed), 'differences': changed}, ensure_ascii=True))
