"""Render manual adjudication of existing evidence; never rerun the product."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'astra-real-users-development20'
rows = json.loads((OUT / 'paired.json').read_text(encoding='utf-8'))
cases = json.loads((OUT / 'CASES.json').read_text(encoding='utf-8'))
failures = {
    8: 'Después de pedir la hora, pide aclarar de qué fecha se habla. Pierde el contexto cotidiano.',
    10: 'El resultado de system.status contiene el nombre del CPU, no un inventario de GPU. Presenta Radeon Graphics como respuesta verificada y omite la GPU dedicada; los datos recibidos no sustentan esa identificación.',
    11: 'No publica una respuesta útil a una restricción negativa. Termina en composition_failed (missing_literal_fact;recovery:missing_literal_fact;retry_exhausted), con controles disponibles. Los borradores internos no son respuestas visibles.',
    17: 'Tras consultar el volumen, rechaza ponerlo a 100 como fuera de sus funciones. No ejecuta la restauración: pierde el referente.',
    18: 'Saluda pero omite responder quién es. El problema es la pregunta ignorada, no el estilo del saludo.',
    20: 'Repite la aclaración sobre dispositivos del turno anterior; no reconoce la nueva restricción de no silenciar el audio.',
}
observations = {
    15: 'Aceptada con observación: solicita una cantidad que no se especificó. Preguntar además la dirección es redundante, porque up ya la indica; no se convierte esa torpeza aislada en un bloqueo.',
    19: 'Aclaración aceptable: dispositivo de audio puede referirse a salida o micrófono. No se penaliza una ambigüedad razonable.',
}
lines = [
    '# C03 — primeras 20 entradas literales de los logs', '',
    'Evaluación manual: **14 respuestas aceptadas (dos con observaciones), 6 fallos**. '
    'Son casos de desarrollo, no los cien de aceptación ni un porcentaje de completitud del goal.', '',
    'Las entradas se copiaron del conjunto heredado del Goal 10 y los logs locales, sin '
    'traducir, corregir erratas ni añadir «en spanglish». La secuencia de esta corrida fue '
    'organizada para el diagnóstico: no se afirma que estos veinte turnos fueran consecutivos '
    'en una sesión histórica. Que una entrada figure en un log no prueba por sí solo autoría '
    'humana ni independencia del entrenamiento. CASES.json conserva todas las referencias.', '',
    'Se aprueban explicaciones sencillas, español ante mezcla natural y aclaraciones razonables. '
    'No se exige alternar idiomas. Se rechazan omisiones de lo pedido, pérdida de contexto, '
    'silencio ante una petición normal y afirmaciones sin datos suficientes.', '',
    'Runtime registrado: Qwen3-4B-Instruct-2507 Q4_K_M base, sin LoRA ni overrides de modelo. '
    'Conductor del producto, sin ventana y con wake desactivado por diseño. '
    '117,09 s; pico atribuido de GPU 3499,56 MiB; proceso terminado con código 0. '
    'El código 0 acredita ejecución de la medición, no calidad de las respuestas. Full pendiente.', '',
]
adjudication = []
for index, (row, case) in enumerate(zip(rows, cases, strict=True), 1):
    assert row['request'] == case['text_literal']
    verdict = 'NO APROBADO' if index in failures else 'APROBADO'
    reason = failures.get(index, observations.get(index, 'Responde de manera útil y fiel a lo pedido.'))
    source = case['source_references'][0]
    entry = {'turnId': row['turnId'], 'caseId': case['id'], 'verdict': verdict,
             'reason': reason, 'freshAcceptance': False, 'review': 'manual-practical-owner-rubric'}
    adjudication.append(entry)
    lines += [f'## {index}. {verdict}', '', '**Entrada literal**', '```text', row['request'], '```', '']
    if row['terminal'] == 'composition_failed':
        lines += ['**Respuesta visible:** no hubo respuesta final en lenguaje natural. '
                  'El estado técnico fue `composition_failed`.', '']
    else:
        lines += ['**Respuesta literal**', '```text', row['final'], '```', '']
    lines += [reason, '', f"Procedencia: `{source['source']}` · `{source['source_location']}` · ID `{case['id']}`.", '']
lines += ['## Evidencia y límites', '',
          '- `astra-real-users-development20/CASES.json`: expectativas y referencias anteriores a la corrida.',
          '- `PREREG.json` y `RESULT.json`: candidato, huellas y recursos.',
          '- `paired.json`, `events.jsonl` y `compose-audit.jsonl`: entradas, respuestas, estados y hechos recibidos.',
          '- `adjudication.json`: dictamen individual; no se obtiene del estado published_final.',
          '- El turno 12 verificó el cambio real de 100 a 35. El turno 17 falló al restaurarlo. '
          'La restauración posterior se registra aparte en `astra-real-users-volume-restore/` y no corrige retrospectivamente ese fallo.', '',
          'Pendiente: revisar idiomas y autoría del conjunto provisional, completar cobertura histórica, '
          'recuperar contexto original de las secuencias seleccionadas y reservar entradas no consumidas '
          'para aceptación. No ejecutar efectos de un log sin revisar la situación actual.', '']
(OUT / 'adjudication.json').write_text(json.dumps(adjudication, ensure_ascii=False, indent=2), encoding='utf-8')
(BASE / 'PRUEBAS_CORPUS_REAL_C03.md').write_text('\n'.join(lines), encoding='utf-8')
print(json.dumps({'accepted': 14, 'failed': 6, 'report': str(BASE / 'PRUEBAS_CORPUS_REAL_C03.md'),
                  'pairedSha256': hashlib.sha256((OUT / 'paired.json').read_bytes()).hexdigest()}))
