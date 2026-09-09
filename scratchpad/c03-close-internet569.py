"""Close native diagnostics, adjudicate product568, and checkpoint validated source569."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib
import json
import os
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

diagnostics = {
    'progress-addressee565': 'No adoptado. Cambiar sólo el destinatario de la fase elimina la tercera persona española, pero la respuesta inglesa afirma que no ha habido progreso. Los seis controles de otras fases son idénticos entre brazos y no prueban tratamientos independientes.16 EOS; no barrer más redacciones de esta fase.',
    'scoped-configuration566': 'No adoptado. Limitar la instrucción540 a memory.status conserva los otros17 paquetes, pero el nuevo caso español de continuidad sigue negando memoria entre sesiones, incluso con una lectura real del estado. Los resultados ingleses mejoran algunas contradicciones; no basta para generalizar.52 EOS. No se cambia prompt ni se añaden vetos.',
    'qwen9b-thinking567': 'Calificación detenida. Primera confirmación agotó180 segundos sin final. El servidor fue detenido deliberadamente durante el segundo caso; el reinicio de conexión y los diez errores de conexión posteriores son consecuencias del corte, no diez fallos semánticos del modelo. Cero finales evaluables. El campo completed de RESOURCES describe sólo la terminación del bucle de colección. Perfil con19 capas GPU y un slot8192: GPU3426,148MiB/RAM3037,359MiB; no promoción ni demostración de incapacidad semántica. No reutilizar el timeout como respuesta equivocada.',
}
for name, conclusion in diagnostics.items():
    out = base / ('astra-' + name); private = local / ('C03-' + name + '-private')
    rows = [json.loads(s) for s in (private / 'responses.jsonl').read_text(encoding='utf-8-sig').splitlines()]
    eos = sum(r.get('response', {}).get('choices', [{}])[0].get('finish_reason') == 'stop' for r in rows)
    if name == 'scoped-configuration566':
        requests = [json.loads(s) for s in (private / 'requests.jsonl').read_text(encoding='utf-8-sig').splitlines()]
        grouped = {}
        for row in requests:
            grouped.setdefault(row['case'], []).append(row['payload'])
        unchanged = sum(pair[0] == pair[1] for pair in grouped.values())
        assert unchanged == 17
    lines = ['# ' + name, '', conclusion, '']
    for row in rows:
        lines += [f'## {row["case"]} · {row["profile"]}', '', json.dumps(row, ensure_ascii=False, indent=2), '']
    lines += ['## Entradas nativas', '', (private / 'requests.jsonl').read_text(encoding='utf-8-sig')]
    (private / 'RESULT.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    (out / 'RESULT.md').write_text('# ' + name + '\n\n' + conclusion + '\n\nDesarrollo local, sin UI/voz, promoción ni cobertura adicional.\n', encoding='utf-8', newline='\n')
    write(out / 'RESULT.json', {'adopted': False, 'evaluable_finals': eos, 'collected_rows': len(rows), 'conclusion': conclusion, 'private_report_sha256': sha(private / 'RESULT.md'), 'resources': read(out / 'RESOURCES.json')})

private = local / 'C03-survey-readonly568-private'; out = base / 'astra-survey-readonly568'
panel = read(private / 'panel.json')
events = [json.loads(s) for s in (private / 'capture/events.jsonl').read_text(encoding='utf-8-sig').splitlines()]
finals = [r for r in events if r.get('type') == 'terminal']
assert len(finals) == len(panel) == 15 and read(out / 'EXIT.json')['exitCode'] == 0
assert not read(out / 'resources.json')['violations']
posts = [json.loads(s) for s in (private / 'http-posts.jsonl').read_text(encoding='utf-8-sig').splitlines()]
notes = {
    'H0037': 'Abierto: carga inactiva y alimentación externa se observan, pero el tercer final afirma reposo y ausencia de descarga sin un indicador observado de descarga. No convertir isCharging:false en prueba de isDischarging:false.',
    'H0063': 'Cubierto: literal y variantes ES/EN de porcentaje conservan95% y, cuando los mencionan, presencia/carga inactiva/alimentación externa. Contraste con nativos8–10. No equivale a calibración física de batería.',
    'H0073': 'Cubierto: literal y variantes ES/EN/reordenadas conservan volumen100 y ausencia de silencio, frente a nativos11–13. En13 hay una instrucción contradictoria sobre ausencia de muted pese a estar en seen; el final mantiene la verdad. Defecto del compositor identificado para reparación separada, no se oculta.',
    'H0080': 'Abierto: dos finales españoles observan online:true; variante inglesa se convierte en web.search y falla por resultados irrelevantes. Nativos18/19 proponen network.status y wifi.status, pero el resultado20 conserva la búsqueda incorrecta. Fuente569 repara reconocimiento; falta producto570.',
    'H0057': 'Cubierto: negativas Chrome/Firefox/Opera, ES/EN y objeto antepuesto, reciben compromiso coherente y no producen misión/operación. Los eventos de esos tres turnos sólo son admisión, actividad, disponibilidad y estado; llamadas nativas sin tool_calls para ejecutar aperturas.',
}
adjudication = [{**case, 'ordinal': i + 1, 'terminal': finals[i], 'adjudication': notes[case['case_id']]} for i, case in enumerate(panel)]
write(private / 'adjudication.json', adjudication)
lines = ['# Producto568 — encuesta', '']
for row in adjudication:
    lines += [f'## {row["ordinal"]} · {row["case_id"]}', '', row['text'], '', row['terminal']['final'], '', row['adjudication'], '']
(private / 'RESULT.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
registry = local / 'C03-survey-requirements336-private/requirements.jsonl'
backup = private / 'requirements-before-adjudication.jsonl'
assert not backup.exists()
backup.write_bytes(registry.read_bytes())
requirements = [json.loads(s) for s in backup.read_text(encoding='utf-8-sig').splitlines()]
commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
assert commit.startswith('e00db70e')
for case_id in ('H0063', 'H0073', 'H0057'):
    row = next(r for r in requirements if r['case_id'] == case_id)
    assert row['verification_status'] == 'open'
    row.update(verification_status='covered', generalization_status='verified_product_variants', verification_reason=notes[case_id], verification_updated_at=datetime.now(timezone.utc).isoformat())
    row['verification_evidence'].append({'campaign': 'astra-survey-readonly568', 'source_commit': commit, 'private_adjudication': str(private / 'adjudication.json'), 'ordinals': [r['ordinal'] for r in adjudication if r['case_id'] == case_id], 'ui_or_voice_credit': False})
assert Counter(r['verification_status'] for r in requirements) == {'covered': 11, 'open': 731}
registry.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in requirements), encoding='utf-8', newline='\n')
counts = {'covered': 11, 'open': 731, 'not_applicable': 0}
summary = read(base / 'SURVEY_REQUIREMENTS336.json')
summary.update(requirements_sha256=sha(registry), validated_current=11, verification_counts=counts, updated_at=datetime.now(timezone.utc).isoformat())
write(base / 'SURVEY_REQUIREMENTS336.json', summary)
write(out / 'RESULT.json', {'published': 15, 'newly_covered': ['H0063', 'H0073', 'H0057'], 'survey_counts': counts, 'resources': read(out / 'resources.json'), 'private_report_sha256': sha(private / 'RESULT.md'), 'adjudication_sha256': sha(private / 'adjudication.json'), 'limits': 'No UI/voz. H0037/H0080 abiertos. Fuente555; reparación posterior569 no se atribuye a568.'})
(out / 'RESULT.md').write_text('# Producto568\n\n15 finales, sin cortes. Cubiertos H0063, H0073 y H0057 con variantes ES/EN y orden/objetos. H0037 mantiene una inferencia no probada de ausencia de descarga; H0080 falla en inglés por enrutamiento web.\n\nEncuesta11 cubiertos/731 abiertos/0 no aplicables. GPU3497,559MiB/RAM2420,844MiB,42,016s. Sin UI/voz. Informes privados conservan entradas, finales, adjudicación y nativos.\n', encoding='utf-8', newline='\n')

out = base / 'astra-internet-query569'
for suffix in ('owners', 'fast', 'stt'):
    source = Path(os.environ['TEMP']) / f'c03-internet569-{suffix}.log'
    (out / (suffix + '.log')).write_bytes(source.read_bytes())
assert '2604 passed, 121 subtests passed' in (out / 'owners.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out / 'fast.log').read_text(encoding='utf-8-sig')
assert '12 passed, 1 skipped' in (out / 'stt.log').read_text(encoding='utf-8-sig')
note = '''# C03 — 569: consulta de conexión local

Producto568 separó un fallo de interpretación: la pregunta inglesa sobre este PC adquiría web.search por la palabra internet. El nuevo reconocimiento de la cláusula completa preserva network.status, el catálogo ausente no sustituye operación, y otra petición no desaparece. Misma arquitectura y modelo, sin respuestas fijas. Baseline final22 casos:13 fallos/9pass,0,80s; focal22pass,0,57s. Dueñas2604pass+121subtests,0skips,58,07s. STT12pass/1skip ambiental,1,21s. Fast verde, Release20,32s,0advertencias/errores. Sólo Python; Full final pendiente.

Durante la reproducción de baseline Windows devolvió OSError22 al restaurar el archivo candidato. Baseline quedó íntegro y el patch se reaplicó antes de las dueñas/Fast; no quedó fuente antigua ni vacío. Árbol actual90b2fedd464bb3a639860d4d91a2912c84915a2b35132cc5907fe440185fdb8a/403archivos. Sellos históricos intactos.

Encuesta11cubiertos/731abiertos/0NA tras568: nuevosH0063,H0073,H0057. Producto56815finales, GPU3497,559MiB/RAM2420,844MiB,42,016s, sinUI/voz. H0037 no demuestra ausencia de descarga; H0080 inglés falla antes de esta reparación. Falta producto570 con fuente569. Otro defecto localizado: llm.py9410 declara muted ausente al mirar sólo observed superior, aunque los resultados de misión lo contienen y _merged_observed ya lo conserva; reparar en tramo posterior.

565 cambia destinatario de progreso y produce ausencia de progreso inglesa no demostrada; no adoptado.566 restringe la distinción configuración/capacidad a su operación, pero no generaliza continuidad entre sesiones; no adoptado.567 Qwen9Bthinking: primer caso180s sin final, corte deliberado durante el segundo. GPU3426,148MiB/RAM3037,359MiB. Cero finales semánticamente evaluables; los errores de conexión posteriores pertenecen al corte, no al modelo. No fuentes ni perfiles de estas campañas promovidos.

Siguiente: publicar569 con dueñas verdes y comprobar red local en producto570; reparar contradicción de observaciones de audio por su owner. Después continúan CPU/VRAM/capacidad/otros casos, ocho rutas, encuesta, UI real, loopback completo/AEC supresión, recursos conjuntos y Full final. No decisión del dueño pendiente; BAXY manual cerrado; goal activo y main intacto.
'''
(out / 'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
write(out / 'RESULT.json', {'adopted': True, 'owners': {'passed': 2604, 'subtests': 121, 'skips': 0, 'seconds': 58.07}, 'fast': 'passed', 'release_seconds': 20.32, 'stt': {'passed': 12, 'environmental_skips': 1, 'seconds': 1.21}, 'product': 'pending570', 'survey_counts': counts})
candidate = out / 'effect_intent.py.candidate'
assert sha(candidate) == sha(root / 'src/baxy_mind/effect_intent.py')
candidate.unlink()  # Temporary own restoration copy; validated source is published in this commit.
folders = ['astra-' + name for name in diagnostics] + ['astra-survey-readonly568', 'astra-internet-query569']
attributes = root / '.gitattributes'; text = attributes.read_text(encoding='utf-8')
for folder in folders:
    directory = base / folder
    write(directory / 'PINS.json', {p.name: sha(p) for p in directory.iterdir() if p.is_file() and p.name != 'PINS.json'})
    rule = f'/artifacts/comprobaciones/C03/{folder}/** -text'
    if rule not in text:
        text += rule + '\n'
attributes.write_text(text, encoding='utf-8', newline='\n')
(base / 'HANDOFF.md').write_text(note, encoding='utf-8', newline='\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n' + note)
state = read(base / 'RELEVO_ACTIVO.json')
state.update(checkpoint='569: local internet query repaired;2604pass+121subtests/Fast green. Survey11/731/0. Product570 pending.', surveyVerificationCounts=counts, continuation='Publish569, verify shared network product570, then repair audio merged-observation contradiction; C03 remains active.')
write(base / 'RELEVO_ACTIVO.json', state)
print(json.dumps(counts))
