from pathlib import Path
import json

base = Path(__file__).resolve().parents[1] / 'artifacts/comprobaciones/C03'
lines = ['# C03 — prohibiciones: selección, contexto y producto', '',
         'Desarrollo consumido y controles sintéticos identificados. No es la reserva de cien turnos. '
         'Las funciones de las sondas no se ejecutan. Las respuestas literales y los fallos se conservan.', '']
count = 0
for name in ('astra-negative-current-selection', 'astra-negative-no-history'):
    lines += [f'## {name}', '', f'[Prerregistro y procedencia]({name}/PREREG.json) · [Payloads completos]({name}/posts.jsonl)', '']
    judgments = {(row['stage'], row['text']): row for entry in (base / name / 'replies.jsonl').open(encoding='utf-8') if (row := json.loads(entry))}
    for entry in (base / name / 'posts.jsonl').open(encoding='utf-8'):
        row = json.loads(entry)
        count += 1
        choice = row['response']['choices'][0]
        verdict = judgments[row['stage'], row['case']]
        lines += [f"### Llamada {count} · {row['stage']}", '', '**Entrada literal**', '```text', row['case'], '```', '',
                  '**Respuesta literal del modelo (campos capturados)**', '```json', json.dumps(choice['message'], ensure_ascii=False, indent=2), '```', '',
                  f"Conjunto esperado: `{verdict['expected']}`. Coincide: `{verdict['pass']}`. Finalización: `{choice.get('finish_reason')}`.", '']
lines += ['La política original obtiene 10/12; aclararla obtiene 11/12 y retirar historial obtiene 11/12. '
          'Las tres variantes siguen proponiendo audio.status ante «no silencies el audio». No se adoptan las dos variantes. '
          'El acierto de «Ponlo» sin historial no prueba resolución del referente: es un control de pérdida de contexto.', '']
notes = {
    'astra-closed-prohibition11': {
        5: 'APROBADO para la petición: reconoce la prohibición. Añade estado coherente con la lectura inmediatamente anterior; no demuestra reproducción física. Se elimina ese arrastre de contexto en la variante posterior, sin convertir esta preferencia de concisión en un fallo semántico.',
        8: 'NO APROBADO: pide confirmar la lectura que la persona ya solicitó mediante una pregunta negativa.',
        9: 'NO APROBADO: no hubo respuesta final visible.',
        10: 'NO APROBADO: una petición de hora con prohibición independiente termina en error de interpretación.',
    },
    'astra-closed-prohibition7': {
        5: 'NO APROBADO: reconoce la prohibición pero añade una promesa universal de presencia sin interrupciones que BAXY no puede garantizar.',
        6: 'NO APROBADO: cambia no silenciar por garantizar audio fuerte y claro. La persona no pidió elevar el volumen ni se midió claridad física.',
    },
}
product_count = 0
for name, verdicts in notes.items():
    folder = base / name
    rows = json.loads((folder / 'paired.json').read_text(encoding='utf-8'))
    result = json.loads((folder / 'RESULT.json').read_text(encoding='utf-8'))
    lines += [f'## {name}', '', f'[Casos]({name}/CASES.json) · [Captura]({name}/paired.json) · [Fuente y runtime]({name}/PREREG.json)', '',
              f"Exit {result['exitCode']}; {result['elapsedSeconds']} s; GPU {result['gpuPeakMiB']:.2f} MiB; registro intacto: {result['registrationUnchanged']}.", '']
    for i, row in enumerate(rows, 1):
        product_count += 1
        lines += [f'### Turno {i}', '', '**Entrada literal**', '```text', row['request'], '```', '',
                  '**Respuesta literal**', '```text', row['final'] if row['terminal'] == 'published_final' else '[No hubo respuesta final visible]', '```', '',
                  f"Terminal: `{row['terminal']}`.", '', verdicts.get(i, 'APROBADO: respuesta útil y coherente con la petición y el contexto observado.'), '']
    lines += [f'[Observaciones y composición]({name}/compose-audit.jsonl) · [Decisiones y rechazos]({name}/turn-audit.jsonl) · [Ejecución Core]({name}/shell-trace.jsonl)', '']
lines += [f'Conserva {count} llamadas del modelo y {product_count} respuestas de producto. Las repeticiones no son casos frescos. '
          'closed-prohibition11: 8/11 útiles; quedan pregunta negativa y orden de cláusulas. '
          'La variante de siete turnos obtiene 5/7: retirar historial empeora dos reconocimientos. Se revierte únicamente ese cambio; '
          'se conserva el cierre de prohibiciones en la decisión. Tampoco resuelve aquellos tres controles.', '']
(base / 'PRUEBAS_PROHIBICIONES_Y_ALCANCE_C03.md').write_text('\n'.join(lines), encoding='utf-8')
