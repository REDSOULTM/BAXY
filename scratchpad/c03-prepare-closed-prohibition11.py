from pathlib import Path
import json
root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
name = 'astra-closed-prohibition11'
out = base / name
out.mkdir(exist_ok=False)
texts = [
    'decime cuánto volumen hay', 'Ponlo a 100 ahora', 'Hola, quien sos?',
    'Dime qué dispositivo de audio está activo', 'no silencies el audio',
    "Don't mute the audio", 'no subas el volumen', '¿No está silenciado el audio?',
    'dime la hora, no abras Steam', 'dime la hora y no abras Steam', 'dime la hora',
]
cases = {'development': [{'text_literal': text, 'origin': 'consumed integrated-real22' if i < 5 or i == 6 else 'synthetic or consumed scope control',
                          'note': 'diagnostic only; no fresh acceptance'} for i, text in enumerate(texts)],
         'source': 'astra-integrated-real22/CASES.json for inherited corpus provenance',
         'method': 'Five literal corpus inputs in their former local order, then negative-question and clause-order controls. Only intended mutation is setting audio100, followed by verified state reads. No app launching or external messaging.'}
(out / 'CASES.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding='utf-8')
(base / f'{name}.turns.jsonl').write_text(''.join(json.dumps({'cmd': 'turn', 'text': text}, ensure_ascii=False) + '\n' for text in texts), encoding='utf-8')
script = (root / 'scratchpad/c03-integrated-real22.py').read_text(encoding='utf-8')
script = script.replace('astra-integrated-real22', name).replace('c03-integrated-real22', 'c03-closed-prohibition11')
start = script.index(" 'method':")
end = script.index("\n 'registrationSha256'", start)
script = script[:start] + " 'method':" + repr(cases['method'] + ' Current Python source preserves inherited closed prohibitions before catalog reclassification. Registered runtime; no overrides. Product conductor, not UI acceptance.') + ',' + script[end:]
(root / 'scratchpad/c03-closed-prohibition11.py').write_text(script, encoding='utf-8')
