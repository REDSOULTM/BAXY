from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03'
names = ['astra-constraint-purpose', 'astra-constraint-scope', 'astra-constraint-sampling', 'astra-constraint-scope-data']
failures = {
    ('astra-constraint-purpose', 3): 'Añade una consecuencia no sustentada sobre la conexión con playlists y devuelve una instrucción al usuario.',
    ('astra-constraint-purpose', 4): 'Afirma que Spotify está en uso sin haberlo observado.',
    ('astra-constraint-purpose', 6): 'Afirma un modo de ahorro previo sin evidencia.',
    ('astra-constraint-purpose', 7): 'Devuelve al usuario una tarea de comprobar el sonido en vez de reconocer su restricción.',
    ('astra-constraint-purpose', 14): 'Garantiza que el brillo nunca bajará, aunque BAXY sólo puede comprometer su propia actuación.',
    ('astra-constraint-sampling', 23): 'Añade una promesa de atender cada sonido que esta prueba no establece.',
}
lines = ['# Pruebas de restricciones — C03, tramo 36', '',
    '2026-09-06. Diagnóstico de desarrollo: 56 respuestas a ocho entradas literales consumidas del corpus; no son 56 casos independientes ni la reserva de cien. No se certifica autoría humana o ausencia de exposición al entrenamiento.', '',
    'Se comparó el compositor existente con una representación de restricción sin operaciones ni observaciones, luego una instrucción de alcance temporal, el muestreo documentado con tres semillas y el alcance como dato. Los prompts completos y respuestas brutas están en los enlaces de cada corrida. No se cambió el producto ni el runtime registrado.', '',
    'Criterio aplicado a mano conforme a las aclaraciones del dueño: aceptar reconocimientos sencillos, variaciones de estilo y compromisos de primera persona de no actuar. La palabra «nunca» por sí sola no convierte un reconocimiento en una afirmación falsa del estado del PC. No aceptar observaciones inventadas, garantías sobre cambios ajenos a BAXY ni capacidades de vigilancia añadidas. Esta adjudicación se realiza después de las sondas y no altera sus preregistros ni demuestra aceptación final.', '',
    'Corrección de la interpretación inicial del experimento: la insistencia en primera persona exacta y en rechazar todo «nunca» sobrecalificaba el estilo. No usarla para justificar más filtros, más prompts o un cambio de modelo.', '',
    'Los dictámenes siguientes son del contenido emitido por estas sondas. Las variantes directas conocen de antemano que la entrada es una restricción; todavía no demuestran que BAXY la identifique y la presente bien en una conversación real.', '']
total = accepted = 0
for name in names:
    rows = [json.loads(x) for x in (out / name / 'replies.jsonl').read_text(encoding='utf-8').splitlines()]
    result = json.loads((out / name / 'RESULT.json').read_text(encoding='utf-8'))
    passed = sum((name, i) not in failures and not row.get('error') for i, row in enumerate(rows, 1))
    total += len(rows)
    accepted += passed
    lines += [f'## {name}', '',
        f'{passed}/{len(rows)} respuestas útiles según el criterio anterior. {result["elapsedSeconds"]} s; pico GPU {result["gpuPeakMiB"]:.2f} MiB; pico RAM {result["ramPeakMiB"]:.2f} MiB. Registro intacto: {result["registrationUnchanged"]}.', '',
        f'[Preregistro y procedencia]({name}/PREREG.json) · [Mensajes completos enviados y devueltos]({name}/posts.jsonl) · [Respuestas]({name}/replies.jsonl) · [Recursos]({name}/RESULT.json)', '']
    for i, row in enumerate(rows, 1):
        answer = row['answer']
        if isinstance(answer, dict):
            answer = answer.get('content')
        reason = failures.get((name, i))
        if row.get('error'):
            reason = str(row['error'])
        lines += [f'### {i}. {row["stage"]}', '', '**Entrada literal**', '```text', row['text'], '```', '', '**Respuesta literal**', '```text', answer or '', '```', '',
            ('**NO APROBADO:** ' + reason) if reason else '**APROBADO:** Reconoce la restricción sin afirmar una observación o un cambio ya ejecutado.', '']
lines += ['## Límites y decisión', '',
    f'{accepted}/{total} respuestas aprobadas en conjunto, con entradas y variantes repetidas: esta suma no es una tasa independiente de calidad de BAXY ni un porcentaje del goal. El compositor existente obtiene 4/8; la representación específica inicial 7/8; la variante de alcance 8/8; muestreo 23/24; alcance como dato 8/8.', '',
    'No se promueve el muestreo: añade una promesa de vigilancia en una semilla y no ofrece una ventaja demostrada frente a la variante determinista. La representación específica sí ofrece una hipótesis útil de integración, pendiente de verificar la detección de restricciones frente a negaciones conversacionales y acciones positivas posteriores.', '',
    'Errata de descripción conservada: algunos scripts derivados mantienen en PREREG.method la descripción de dos etapas del primer experimento, aunque sus listas stages y los posts muestran una etapa o tres semillas. No se reescribieron los preregistros congelados. Las 56 filas anteriores proceden de replies.jsonl, no de esa descripción heredada.', '',
    'Herencia y estado del arte: se reutilizó INVESTIGACION_MODELO_C03.md (ficha oficial Qwen3-4B-Instruct-2507, configuración de generación y llama.cpp b9980). La búsqueda exploratoria de otros modelos no produjo una comparación local nueva; no se adopta ni se descarta otro modelo a partir de ella.', '']
(out / 'PRUEBAS_RESTRICCIONES_C03.md').write_text('\n'.join(lines), encoding='utf-8')
print(json.dumps({'responses': total, 'accepted_development_responses': accepted, 'report': str(out / 'PRUEBAS_RESTRICCIONES_C03.md')}, ensure_ascii=False))
