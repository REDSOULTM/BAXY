from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
lines = ['# C03 — restricciones y aclaración de volumen: pruebas del tramo 37', '',
         '2026-09-06. C03 EN_CURSO. Se conservan 37 respuestas del producto y 33 respuestas de sondas: 70 en total, con casos repetidos. Ninguna cifra representa cien casos frescos ni un porcentaje de completitud.', '',
         'Los casos procedentes del pool conservan texto y referencias, pero no certifican autoría humana o frescura. Los controles sintéticos están identificados. Los enlaces contienen prompts completos, hechos, respuestas brutas y resultados, no sólo ejemplos favorables.', '']
count = 0

def section(name):
    result = json.loads((base / name / 'RESULT.json').read_text(encoding='utf-8-sig'))
    lines.extend([f'## {name}', '',
        f'Tiempo {result["elapsedSeconds"]} s; pico GPU {result["gpuPeakMiB"]:.2f} MiB; pico RAM {result["ramPeakMiB"]:.2f} MiB; registro intacto: {result["registrationUnchanged"]}.', '',
        f'[Preregistro]({name}/PREREG.json) · [Recursos]({name}/RESULT.json)', ''])

def literal(text, answer, verdict, heading):
    global count
    count += 1
    lines.extend([f'### {heading}', '', '**Entrada del caso, literal**', '```text', text, '```', '',
                  '**Respuesta literal**', '```text', answer, '```', '', verdict, ''])

products = ['astra-real-constraints12', 'astra-real-users-constraints22', 'astra-air-device-followup3']
for name in products:
    section(name)
    lines.extend([f'[Procedencia y controles]({name}/CASES.json) · [Respuestas y hechos]({name}/paired.json) · [Traza del shell]({name}/shell-trace.jsonl) · [Composición]({name}/compose-audit.jsonl)', ''])
    rows = json.loads((base / name / 'paired.json').read_text(encoding='utf-8-sig'))
    for i, row in enumerate(rows, 1):
        verdict = '**APROBADO:** Respuesta útil y fiel al pedido y a los hechos disponibles en este caso de desarrollo.'
        if name == 'astra-real-constraints12':
            if 2 <= i <= 9:
                verdict = '**APROBADO:** Reconoce la prohibición sin afirmar cambios ejecutados; la traza no registra una invocación Core en este turno. «Nunca» en el reconocimiento no se penaliza por sí solo.'
            elif i == 10:
                verdict = '**NO APROBADO — control sintético:** La negación social no justifica perder la petición de consultar la hora. El producto publica un fallo de interpretación.'
            elif i >= 11:
                verdict = '**RESTAURACIÓN/LECTURA APROBADA:** Audio a 100 y lectura posterior sin silencio. No cuenta como caso normal de aceptación.'
        elif name == 'astra-real-users-constraints22':
            if i == 10:
                verdict = '**APROBADO:** La observación system.status incluye NVIDIA GeForce RTX 3060 Laptop GPU. La primera persona es una variación de estilo, no una GPU inventada.'
            elif i == 15:
                verdict = '**APROBADO:** Sólo pregunta la cantidad. La traza muestra decisión clarify, sin llamada arguments ni ejecución de ajuste con una cantidad inventada.'
            elif i == 19:
                verdict = '**PENDIENTE DE CONTINUIDAD:** Aclaración de alcance plausible, sin inventar identidad. No demuestra que pueda identificar después el dispositivo. No contar como identificación resuelta ni dar por verde todo el panel.'
            elif i >= 21:
                verdict = '**RESTAURACIÓN/LECTURA APROBADA:** 100 y muted:false confirmados; fuera del grupo de veinte casos normales.'
        else:
            verdict = {
                1: '**NO APROBADO EN PRECISIÓN:** La conclusión principal —aire distinto de agua, mayormente nitrógeno y oxígeno— es correcta. La explicación añadida presenta H₂O como vapor y generaliza sobre ausencia de agua sin tratar la humedad; no es una descripción general adecuada del agua o del aire. No es un rechazo por idioma o brevedad.',
                2: '**NO APROBADO:** Informa volumen y silencio, pero no identifica el dispositivo pedido. AudioStatusReceipt sólo transporta hash/objetivo/volumen/silencio, sin nombre visible: falta ese hecho en la fuente, no sólo una frase mejor.',
                3: '**CONTROL CON PRECONDICIÓN NO OBSERVADA:** Era una respuesta sintética prevista para una pregunta de alcance, pero en esta corrida el turno anterior no formuló esa pregunta. Conservar la salida; no usarla como prueba de continuidad de la aclaración de la otra corrida.',
            }[i]
        literal(row['request'], row.get('final') or '', verdict, row['turnId'])

probes = ['astra-negative-conversation-purpose', 'astra-clarification-operation-ids',
          'astra-direct-missing-fields', 'astra-direct-missing-language']
for name in probes:
    section(name)
    lines.extend([f'[Todos los mensajes reales enviados y devueltos]({name}/posts.jsonl) · [Resultado de la API de BAXY]({name}/replies.jsonl)', '',
        'La entrada de caso se inserta en el payload del enlace; la respuesta de abajo es el content literal del servidor, antes de la evaluación del producto. No se ejecutaron sus argumentos.', ''])
    posts = [json.loads(line) for line in (base / name / 'posts.jsonl').read_text(encoding='utf-8').splitlines()]
    rows = [json.loads(line) for line in (base / name / 'replies.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(posts) == len(rows), (name, len(posts), len(rows))
    for i, (post, row) in enumerate(zip(posts, rows, strict=True), 1):
        assert post['case'] == row['id'] and post['stage'] == row['stage']
        answer = post['response']['choices'][0]['message'].get('content') or ''
        if name == 'astra-negative-conversation-purpose':
            verdict = {
                6: '**NO APROBADO:** Invierte bajar por subir.',
                10: '**NO APROBADO:** Confunde la falta de conocimiento del usuario con la del asistente y no explica Steam.',
                11: '**NO APROBADO:** Promete una revisión no iniciada y devuelve al usuario comprobaciones sin diagnosticar. Esta sonda no tiene observaciones ni ejecución.',
            }.get(i, '**APROBADO EN ESTA SONDA:** Responde al sentido del caso sin inventar un estado observado.')
        elif name == 'astra-clarification-operation-ids':
            verdict = '**APROBADO EN ESTA SONDA:** Pide sólo cantidad. La ruta existente ya acierta; retirar identificadores no demuestra reparar el fallo de la otra ruta. Variante no promovida.'
        elif not row['id'].startswith('synthetic-'):
            verdict = '**NO APROBADO COMO EXTRACCIÓN:** El pedido no da cantidad, pero la salida inventa amount=1. La guarda independiente del producto rechazó ese valor en el caso integrado anterior. La pregunta se estudia aparte; ninguna de estas variantes se promovió.'
        else:
            verdict = '**CONTROL SINTÉTICO — ARGUMENTOS CORRECTOS:** Conserva cantidad y dirección explícitas. fallback_question no es una respuesta normal visible cuando esos argumentos se aceptan; no contarla como una aclaración necesaria.'
        literal(row['text'], answer, verdict, f'{i}. {row["stage"]}')

lines.extend(['## Qué cambió y qué sigue pendiente', '',
    'Se integró la presentación de prohibiciones con el prompt de alcance medido en el tramo36. Se heredó el vocabulario de acciones para reconocer la flexión negativa sin convertir toda negación en una orden. No se añadieron llamadas al modelo ni un nuevo verificador por frases.', '',
    'Para volumen se reutilizó la ruta de aclaración explícita: se amplió su reconocimiento a los verbos compuestos ingleses sin cantidad. Esta ruta sustituye en esos casos la extracción especulativa y pide sólo amount. Los cambios de prompt de extracción fallidos se conservaron como evidencia y no se adoptaron.', '',
    'La pregunta por dispositivo requiere investigar la lectura del nombre del endpoint; el contrato actual sólo tiene objetivo/hash/volumen/silencio. La precisión del aire en sesión limpia y la negación social seguida de una petición positiva siguen pendientes. Cien frescos, UI y Full final no se han completado.', '',
    'Validación final de esta fuente: 2804 pruebas Python pass, 0 skips, 44,64 s; Fast terminal0 con build Release sin errores/avisos; git diff --check. Ver ASTRA-TRAMO-37.md para comandos, hashes y límites.'])
(base / 'PRUEBAS_RESTRICCIONES_INTEGRADAS_C03.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
assert count == 70, count
print(f'{count} entradas/respuestas literales guardadas')
