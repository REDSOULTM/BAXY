"""Adjudicate observations572/573 without changing survey credit or native payloads."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def rows(p):
    return [json.loads(s) for s in p.read_text(encoding='utf-8-sig').splitlines()]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


private = local / 'C03-audio-product572-private'
out = base / 'astra-audio-product572'
panel = read(private / 'panel.json')
finals = [r for r in rows(private / 'capture/events.jsonl') if r.get('type') == 'terminal']
posts = rows(private / 'http-posts.jsonl')
assert len(panel) == len(finals) == 6 and read(out / 'EXIT.json')['exitCode'] == 0
warnings = [r for r in posts if 'Do not mention mute' in str(r.get('payload', {}))]
assert [r['id'] for r in warnings] == [16, 17]
assert all('request interpretation failed' in str(r['payload']) for r in warnings)
assert all('"muted"' not in str(r['payload']) for r in warnings)
notes = [
    'Correcto: sonido no silenciado y volumen100, coinciden con la observación real; sin instrucción contradictoria de ausencia.',
    'Correcto en inglés: conserva silencio y volumen observados; sin instrucción contradictoria de ausencia.',
    'Abierto: la petición compuesta fracasa durante interpretación. Las dos instrucciones de ausencia pertenecen a ese fallo sin observaciones de audio; no desmienten la reparación571.',
    'Abierto: sólo llega audio.status a la prosa; falta la lectura de hora. La respuesta declara desconocimiento en vez de inventar la hora, pero no cumple el pedido.',
    'Control correcto de volumen100 y sonido no silenciado.',
    'Control correcto de conectividad online.',
]
adjudication = [{**case, 'ordinal': i + 1, 'terminal': finals[i], 'adjudication': notes[i]} for i, case in enumerate(panel)]
write(private / 'adjudication.json', adjudication)
lines = ['# Producto572 — audio observado y coordinación', '']
for row in adjudication:
    lines += [f'## {row["ordinal"]}', '', row['text'], '', row['terminal']['final'], '', row['adjudication'], '']
lines += ['## Capturas nativas completas', '', '```json', json.dumps(posts, ensure_ascii=False, indent=2), '```']
(private / 'RESULT.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
audio_note = '''# Producto572 — reparación de observaciones de audio verificada

Seis finales sin cortes: las dos preguntas de volumen/silencio ES/EN y los dos controles previos coinciden con los hechos. Dos variantes nuevas de hora+silencio no cumplen: ES falla interpretación; EN entrega sólo audio.status y declara desconocer la hora. No se contabilizan como éxitos. Las dos advertencias de ausencia de muted están en native16/17, con fallo de interpretación y sin observaciones de audio; las respuestas que sí reciben muted ya no reciben la advertencia contradictoria.

GPU3497,559 MiB; RAM2386,109 MiB;32,687s. Conductor compartido sin ventana, no UI/voz ni consumo conjunto final. Encuesta12 cubiertos/730 abiertos/0NA, sin crédito nuevo.
'''
(out / 'RESULT.md').write_text(audio_note, encoding='utf-8', newline='\n')
write(out / 'RESULT.json', {'finals': 6, 'correct': [1, 2, 5, 6], 'open': [3, 4], 'known_mute_false_absence_instructions': 0, 'legitimate_absence_instructions_in_failure': [16, 17], 'source571_verified': True, 'private_report_sha256': sha(private / 'RESULT.md'), 'adjudication_sha256': sha(private / 'adjudication.json'), 'resources': read(out / 'RESOURCES.json'), 'survey': {'covered': 12, 'open': 730, 'not_applicable': 0}})

private = local / 'C03-cpu-topology573-private'
out = base / 'astra-cpu-topology573'
responses = rows(private / 'responses.jsonl')
requests = rows(private / 'requests.jsonl')
assert len(responses) == len(requests) == 12
assert all(r['response']['choices'][0]['finish_reason'] == 'stop' for r in responses)
lines = ['# Nativo573 — observación de núcleos físicos', '']
for request, response in zip(requests, responses, strict=True):
    assert request['case'] == response['case'] and request['profile'] == response['profile']
    lines += [f'## {response["case"]} / {response["profile"]}', '', response['response']['choices'][0]['message']['content'], '', '```json', json.dumps(request['payload'], ensure_ascii=False, indent=2), '```', '']
cpu_note = '''# Nativo573 — medir el dato de núcleos físicos sí mejora la respuesta

Doce EOS, dos brazos. Agregar únicamente physicalCoreCount medido permite distinguir8 físicos/16 lógicos en las peticiones de CPU ES/EN. Dos controles sintéticos con otro modelo de procesador y6 físicos/8 lógicos conservan la distinción. El control de uso ES sigue atribuyendo23,75% total a BAXY: defecto independiente abierto; EN conserva26,875%. No se adopta por ello un arreglo del sujeto.

Windows confirmó8 físicos/16 lógicos mediante GetLogicalProcessorInformationEx(RelationProcessorCore) y GetActiveProcessorCount; dos lecturas nativas iguales. Los datos actuales añadidos a capturas históricas no son una instantánea simultánea de producto. Los controles6/8 son explícitamente sintéticos.

GPU3497,559 MiB; RAM720,555 MiB;8,016s, sólo modelo nativo. Sin cambio de runtime, fuente o encuesta en573. Justifica implementar el dato verificado en el proveedor574 y comprobar transporte/validación/producto antes de acreditar conducta. Fuente oficial: https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getlogicalprocessorinformationex
'''
lines += [cpu_note]
(private / 'RESULT.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
(out / 'RESULT.md').write_text(cpu_note, encoding='utf-8', newline='\n')
write(out / 'RESULT.json', {'native_finals': 12, 'physical_observation_promising': True, 'production_adoption': False, 'cpu_actor_fixed': False, 'private_report_sha256': sha(private / 'RESULT.md'), 'resources': read(out / 'RESOURCES.json'), 'survey': {'covered': 12, 'open': 730, 'not_applicable': 0}})
for folder in ('astra-audio-product572', 'astra-cpu-topology573'):
    out = base / folder
    write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
    with (root / '.gitattributes').open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(f'/artifacts/comprobaciones/C03/{folder}/** -text\n')
note = '# Handoff C03 — 573; fuente574 en validación\n\n' + audio_note.split('\n', 1)[1] + '\n' + cpu_note.split('\n', 1)[1] + '''
Fuente571 publicada3c368a55. Fuente574 en WIP: lectura nativa acotada de topología, physicalCoreCount opcional en contrato para conservar desconocido en observaciones anteriores, transporte Core y validación sin inferir SMT. Dueñas iniciales proveedor31pass/0skip, integración79pass/0skip; añadido control de dato desconocido, nueva validación en curso. Falta Fast y producto575 antes de acreditar CPU. No cambios Python ni runtime.

Goal activo, ninguna decisión pendiente del dueño; BAXY manual cerrado. Survey12/730/0 y742/rev1248 intactos. Main5f572ee1b48cb5e2543ee5e06510e51057c9c845 intacto. Quedan otros fallos de prosa/encuesta, ocho rutas, UI real, loopback completo/AEC como supresión, recursos conjuntos, aceptación y Full final. Full526 rojo original reparado por dueñas528–531, no presentar como Full verde. C08 humano sólo evidencia.
'''
(base / 'HANDOFF.md').write_text(note, encoding='utf-8', newline='\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n' + note)
state = read(base / 'RELEVO_ACTIVO.json')
state.update(checkpoint='573: audio572 four correct/two compound failures; verified physical count improves native573. Source574 in owner validation.', continuation='Finish574 owners/Fast, publish validated source and verify product575 CPU. Resolve compound clock/mute first incorrect transform; other C03 obligations remain.', publishedSourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(), confirmedAtUtc=datetime.now(timezone.utc).isoformat())
write(base / 'RELEVO_ACTIVO.json', state)
print('572/573 adjudicated; survey unchanged12/730/0, source574 in progress.')
