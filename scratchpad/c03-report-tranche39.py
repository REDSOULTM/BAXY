import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
lines = ['# C03 — presupuesto de conocimiento y alcance de negación', '',
         'Tramo 39, 2026-09-06. Veintitrés entradas/respuestas literales: diez sondas y trece turnos de producto. '
         'Son desarrollo consumido y controles sintéticos declarados; ninguno pertenece a la reserva de cien.', '',
         '## Cambio integrado', '',
         'El presupuesto de conocimiento pasa de 128 a 256 tokens. Se adopta la política ya medida en el tramo38: '
         'una frase por defecto, con excepción explícita cuando se pide profundizar, detalle o un formato. '
         'No cambia el modelo, sampler, identidad, catálogo ni otros roles. No garantiza que cualquier respuesta detallada quepa en256.', '',
         'Se hereda INVESTIGACION_MODELO_C03.md: ficha específica Qwen3-4B-Instruct-2507, documentación del servidor b9980, '
         'papers y reportes reproducibles. La evidencia anterior de Steam ya diferenciaba truncamiento de desconocimiento. '
         'Aquí se cambia sólo el presupuesto respecto de cada política retenida y se miden tokens, recursos y producto.', '',
         '## Sonda controlada del presupuesto', '',
         '[Prerregistro](astra-knowledge-budget/PREREG.json), [payloads](astra-knowledge-budget/posts.jsonl), '
         '[respuestas](astra-knowledge-budget/replies.jsonl), [recursos](astra-knowledge-budget/RESULT.json). '
         'Wrapper BAXY con historial vacío, temperatura0 y max_tokens256; no es modelo aislado. '
         'Comparadores128 están en las sondas del tramo38. 11,94s; GPU3497,56MiB; RAM2857,54MiB; registro intacto; proceso terminó0.', '']
rows = [json.loads(x) for x in (base/'astra-knowledge-budget/replies.jsonl').read_text(encoding='utf-8').splitlines()]
for i, row in enumerate(rows, 1):
    verdict = ('NO APROBADO: analogía falsa entre SSID y contraseña.' if row['id']=='synthetic-en-definition' and row['stage']=='current_256'
               else 'NO ACREDITA mejora de precisión: el aumento de presupuesto conserva ampliaciones problemáticas de la política actual.' if row['stage']=='current_256' and (row['id']=='synthetic-detail-control' or row['text']=='El aire es h20?')
               else 'ÚTIL en esta sonda; no prueba conducta integrada con historial.')
    lines += [f"### Sonda {i} — {row['stage']}", '', '**Entrada literal**', '```text', row['text'], '```', '', '**Respuesta literal**', '```text', row['answer'] or '', '```', '', verdict, '']
verdicts = {
    'astra-knowledge-budget-integrated8': [
        'APROBADO: identifica correctamente H₂O.',
        'NO APROBADO: pide aclaración innecesaria. La primaria ya devuelve mode=clarify; no es el compositor recortando una respuesta correcta.',
        'APROBADO: explicación sencilla de Steam.',
        'APROBADO: completa composición del aire y papel de humedad, sin corte visible.',
        'NO APROBADO: añade analogía falsa con contraseña.',
        'APROBADO: nombre observado del endpoint, volumen y silencio conservados.',
        'NO APROBADO: pierde la lectura de hora solicitada después de la negación social.',
        'APROBADO: publica la lectura real de hora.'
    ],
    'astra-clause-scope5': [
        'NO APROBADO: persiste pérdida de lectura solicitada.',
        'NO APROBADO: persiste pérdida de lectura solicitada en inglés.',
        'NO APROBADO: publica una hora no verificada; no contar como recuperación ni éxito.',
        'APROBADO: reconoce la prohibición sin decir la hora.',
        'APROBADO: lectura real de hora tras el fallo.'
    ]
}
for folder, decisions in verdicts.items():
    lines += [f'## Producto — {folder}', '', f'[Prerregistro]({folder}/PREREG.json), [casos]({folder}/CASES.json), '
              f'[eventos y respuestas]({folder}/paired.json), [traza de interpretación]({folder}/turn-audit.jsonl), '
              f'[resultado]({folder}/RESULT.json). Runtime registrado, perfil propio, sin overrides de modelo/sampling. '
              'La segunda corrida prueba una variante de resolución por cláusulas que se retiró al no mejorar el producto.', '']
    for i, (row, decision) in enumerate(zip(json.loads((base/folder/'paired.json').read_text(encoding='utf-8')), decisions, strict=True), 1):
        lines += [f'### Turno {i}', '', '**Entrada literal**', '```text', row['request'], '```', '', '**Respuesta literal**', '```text', row['final'], '```', '', decision, '']
lines += ['## Variante retirada y causa siguiente', '',
          'En resolve_explicit_effects se probó permitir una orden directa en cualquier cláusula ya separada, '
          'añadiendo `and not any(_is_direct_request(clause) for clause in clauses)` a la comprobación de entrada. '
          'La lectura española aislada empezó a resolverse, pero unresolved_compound_contract siguió devolviendo veto '
          'por negación global; la cláusula inglesa `I don\'t mind` siguió contándose como acción desconocida. '
          'La primaria aún eligió conversación sin observación y se publicó una hora inventada en un control. '
          'Este ajuste fue retirado; no queda como reparación parcial.', '',
          'Los tests existentes pasaron2454/2454 durante esa variante. Los seis controles nuevos dieron5pass/1fail '
          '(el reconocimiento inglés), y el producto sólo2/5útiles. Se conservaron los resultados; '
          'no se promovió la variante ni se declara resuelto el requisito inglés. Los controles técnicos retirados '
          'exigían resolver las dos frases sociales anteriores, y rechazar `no me digas la hora`, '
          '`don\'t tell me the time`, `no uses herramientas, dime la hora`, `traduce: no me molesta, dime la hora`.', '',
          'Pendiente: conservar alcance de negación en el contrato semántico completo, no sólo en el reconocimiento léxico. '
          'No repetir el mismo parche ni añadir una excepción para «no me molesta». La aclaración del aire nace en la primaria; '
          'SSID falla en la prosa incluso con política breve. El cambio de presupuesto no se presenta como solución de esos fallos.', '',
          '## Preparación del corpus', '',
          'La auditoría acotada cuenta560textos únicos en traces (la copia histórica y la viva se solapan), '
          '115en Carter_v1 y16ficheros de sesiones .gemma4. El detalle permanece privado en '
          'LOCALAPPDATA/BAXY/C03-real-user-pool-20260906/session_source_candidates.json. '
          'Una sesión contiene transcripciones compatibles con audio de fondo; observed_user y request_start no certifican '
          'por sí solos autor humano ni intención dirigida a BAXY. Revisar origen/contexto antes de reservar100.', '']
(base/'PRUEBAS_PRESUPUESTO_Y_NEGACION_C03.md').write_text('\n'.join(lines), encoding='utf-8')

checkpoint = base/'CHECKPOINT.md'
old = checkpoint.read_text(encoding='utf-8')
rest = old[old.index('### Registro conservado38'):]
now = '''# C03 — CHECKPOINT — 2026-09-06, tramo 39

## Estado vigente39: presupuesto reparado; negación compuesta pendiente

C03 EN_CURSO/ACTIVE, sin bloqueo externo. Tramo39 fue progreso: fuente, medición
integrada y diagnóstico de un ajuste fallido. PRUEBAS_PRESUPUESTO_Y_NEGACION_C03.md
conserva23literales (10sondas+13producto), dictámenes y variante retirada.

Integrado en llm.py: knowledge256tokens y política ya medida de una frase salvo
detalle/formato solicitado. Mismo modelo/sampler/registro/otros roles.
astra-knowledge-budget:10llamadas,11,94s,GPU3497,56MiB,registro intacto,57483terminal0.
astra-knowledge-budget-integrated8:5/8útiles;76,11s,GPU3499,56MiB,RAM5089,43MiB,
29739terminal0. Detalle termina bien, agua/Steam/audio/hora útiles. Aire pasa a
aclaración innecesaria en la PRIMARIA; SSID añade analogía falsa con contraseña;
negación social+hora sigue fallando. No afirmar desarrollo completo ni reserva.

Se probó resolver la orden directa en cualquiera de las cláusulas ya separadas.
El español aislado se reconoce; el inglés no. unresolved_compound_contract aún
veta globalmente. astra-clause-scope5:2/5útiles;65,05s,GPU3497,56MiB,RAM4682,09MiB;
17092terminal0. «no abras Steam, dime la hora» publica14horas sin lectura verificada:
fallo. AJUSTE RETIRADO, junto con sus tests experimentales; evidencia preservada.
No se relajó el veto para promoverlo. No añadir excepción textual ni repetirlo.

Validación de conocimiento:2609pass,0skip,45,70s; Ruff/Fast verdes. Variante de
cláusulas:2454pass existentes pero1fail/5pass controles nuevos; retirada por fallo
de producto. Tras retirar, validación final activa8528 y Fast14130: recogerlos.
Logs scratchpad/c03-knowledge-final-{owner,fast}.log. No Full final ni UI actual.
Sin procesos LLM propios vivos; main intacto, cambios sin commit/push.

Auditoría de pool:560únicos traces,115Carter_v1,16archivos sesiones.gemma4.
Copias histórica/viva no son fuentes independientes. Detalle privado:
LOCALAPPDATA/BAXY/C03-real-user-pool-20260906/session_source_candidates.json.
No certificar humano por observed_user; hay posibles pruebas automáticas/audio
de fondo. No existe aún reserva100conautoría/contexto/exposición comprobados.

Siguiente: contrato de alcance de negación completo (unresolved_compound_contract
y lectura semántica); la tentativa sólo en resolve_explicit_effects no basta.
Para aire, inspeccionar clasificación anterior al catálogo: mode=clarify nace ahí,
no en chat. Mantener pendientes SSID, corpus100, ocho rutas, averías/recuperación,
UI/recursos, contratos posteriores afectados, Full y publicación propia.

'''
checkpoint.write_text(now+rest, encoding='utf-8')
(base/'ASTRA-TRAMO-39.md').write_text('''# C03 — tramo 39, 2026-09-06

Conocimiento permite256tokens, con respuesta breve por defecto y excepción para
detalle/formato. El control detallado ya termina en producto, sin ampliar VRAM.
No se cambia modelo, backend, sampler ni los demás roles.

PRUEBAS_PRESUPUESTO_Y_NEGACION_C03.md conserva23literales y dictámenes. Producto:
5/8útiles en la secuencia de conocimiento. Aire: aclaración innecesaria de la
primaria; SSID: analogía incorrecta; negación social+hora: pierde la lectura.

Se retiró una tentativa de reconocer la orden posterior en el resolver léxico:
no corrige el contrato global de negación;2/5útiles en producto, una hora inventada.
Tests existentes2454pass no acreditaban esa conducta; nuevos controles5pass/1fail.
No promover reparaciones parciales ni contar errores honestos como utilidad normal.

La auditoría del corpus distingue560traces,115Carter_v1 y16archivos.gemma4;
request_start no prueba humano. Continúa en CHECKPOINT.md; sin reserva100, Full,
UI final ni publicación. C03 EN_CURSO, sin bloqueo externo.
''', encoding='utf-8')
print('Tramo39: 23 literales y decisiones registradas; validación final pendiente de recoger.')
