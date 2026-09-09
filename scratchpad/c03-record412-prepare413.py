from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
out = base / 'astra-read-recovery412'
private = local / 'C03-read-recovery412-private'
rows = [json.loads(s) for s in (out / 'replies.jsonl').open(encoding='utf-8')]
assert len(rows) == 30
case_file = local / 'C03-read-recovery412-cases-private/cases.json'
cases = json.loads(case_file.read_text(encoding='utf-8'))['cases']
case_by_id = {c['id']: c for c in cases}
report = ['# 412 —15/15→15/15; no reproduce411, no adoptar recuperación temprana', '',
    'Quince consultas por brazo: target frío más14casos calientes,30respuestas. Ambas versiones seleccionan identity en el target y conservan todos los controles. La variante añade llamadas y demora sin mejora útil aquí. No fuente nueva, efectos, promoción o aceptación fresca; procesos cerrados, manifiesto intacto.', '',
    'La hipótesis no quedó probada: el historial reconstruido de activity omitió la bienvenida que sí recibió el modelo en411. payload-diff411.json demuestra que tools/system/sampler/budgets/campos restantes son iguales; sólo falta el primer assistant «¡Hola! Bienvenido. ¿En qué puedo ayudarte hoy?». El observador de activity se conectó después de publicarla. No llamar a412 reproducción exacta ni atribuir su éxito al hook. Mismo riesgo observado404b: para reproducir se toma el historial del payload HTTP nativo, no sólo activity.', '',
    '413 corrige la procedencia del historial y exige igualdad del primer payload frío con411 antes de seguir. Reutiliza el mismo hook/control; ningún cambio del producto ni otro prompt. Conservar412 y su comparación, no ocultar la reproducción incompleta.', '']
for row in rows:
    reply = row['reply']
    report += [f"## {row['variant']} / {row['phase']} / {row['id']}", '', case_by_id[row['id']]['request'], '',
               f"{reply['kind']}; operación {reply.get('operation')}; {row['seconds']}s.", '',
               '> ' + (reply.get('reply') or reply.get('question') or '(propuesta estructurada)').replace('\n', '\n> '), '']
(out / 'RESULT.md').write_text('\n'.join(report), encoding='utf-8')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
paths = [out / n for n in ['PREREG.json', 'replies.jsonl', 'RESULT.md', 'EXIT.json']]
paths += [private / n for n in ['http-posts.jsonl', 'turn-audit.jsonl', 'payload-diff411.json', 'startup-baseline.jsonl', 'startup-early-read.jsonl', 'hook/sitecustomize.py']]
paths += [case_file]
(out / 'PINS.json').write_text(json.dumps({str(p): sha(p) for p in paths}, indent=2) + '\n', encoding='utf-8')

reference = next(row['payload'] for line in (local / 'C03-account-product411-private/http-posts.jsonl').open(encoding='utf-8-sig')
                 if (row := json.loads(line)).get('stage') == 'request'
                 and len(row['payload'].get('tools', [])) == 28
                 and row['payload']['messages'][-1].get('content') == cases[0]['request'])
cases[0]['history'] = [m for m in reference['messages'][:-1] if m['role'] in {'user', 'assistant'}]
case_dir = local / 'C03-read-recovery413-cases-private'
case_dir.mkdir(exist_ok=False)
case413 = case_dir / 'cases.json'
reference413 = case_dir / 'reference411.json'
case413.write_text(json.dumps({'cases': cases}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
reference413.write_text(json.dumps(reference, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
source = (root / 'scratchpad/c03-read-recovery412.py').read_text(encoding='utf-8')
for a, b in [('astra-read-recovery412', 'astra-read-recovery413'), ('C03-read-recovery412-private', 'C03-read-recovery413-private'), ('C03-read-recovery412-cases-private', 'C03-read-recovery413-cases-private'), ('catalog412', 'catalog413'), ('close412', 'close413'), ('c03-early-read412-hook.py', 'c03-early-read413-hook.py')]:
    source = source.replace(a, b)
source = source.replace("prereg = {'utc':", "reference_path = cases_path.with_name('reference411.json')\nreference = json.loads(reference_path.read_text(encoding='utf-8'))\nprereg = {'reference411_sha256': sha(reference_path), 'utc':")
source = source.replace('actual411T3 with exact last12role history', 'actual411T3 with exact native411 history including its initial welcome')
source = source.replace('before attributing its comparison to the real411 boundary.', 'before attributing its comparison to the real411 boundary. Unlike412, assert byte-value equality of the first cold primary payload with411 for both arms before continuing.')
needle = "        evidence_status = client.request({'id': 'evidence407-initial'"
position = source.index(needle)
assertion = '''        cold_primary = next(row['payload'] for line in (private / 'http-posts.jsonl').open(encoding='utf-8-sig')
                            if (row := json.loads(line)).get('stage') == 'request'
                            and len(row['payload'].get('tools', [])) == 28
                            and row['payload']['messages'][-1].get('content') == cold_case['request'])
        exact = cold_primary == reference
        (out / f'payload-match-{variant}.json').write_text(json.dumps({'equal_to411': exact, 'reference_sha256': sha(reference_path)}, indent=2) + '\\n', encoding='utf-8')
        assert exact, 'cold primary does not reproduce411 payload; stop before claiming a repair'
'''
source = source[:position] + assertion + source[position:]
target = root / 'scratchpad/c03-read-recovery413.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')
hook = root / 'scratchpad/c03-early-read413-hook.py'
hook.write_text((root / 'scratchpad/c03-early-read412-hook.py').read_text(encoding='utf-8').replace('C03-read-recovery412-private', 'C03-read-recovery413-private'), encoding='utf-8')
print(json.dumps({'412_rows': len(rows), '413_prepared': True, 'actual_history_messages': len(cases[0]['history'])}))
