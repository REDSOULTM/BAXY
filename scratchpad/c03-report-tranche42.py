from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
lines = ['# C03 — contexto, negaciones y regresión integrada', '',
         'Desarrollo consumido y controles sintéticos identificados: no es la reserva de cien turnos. '
         'Las entradas del corpus se conservan literales; su presencia en el corpus no certifica por sí sola autoría humana ni independencia. '
         'Las respuestas se leen de capturas y los fallos permanecen visibles.', '']
call_count = 0
for name in ('astra-observation-selection', 'astra-native-reference-packet'):
    lines += [f'## {name}', '', f'[Prerregistro, candidatos e historial]({name}/PREREG.json) · [Payloads completos]({name}/posts.jsonl)', '',
              'Esta sonda interpreta peticiones; las funciones seleccionadas no se ejecutan.', '']
    with (base / name / 'posts.jsonl').open(encoding='utf-8') as stream:
        for entry in stream:
            row = json.loads(entry)
            call_count += 1
            choice = row['response']['choices'][0]
            lines += [f"### Llamada {call_count} · {row['stage']}", '', '**Entrada literal de la persona**',
                      '```text', row['case'], '```', '', '**Respuesta del modelo: campos capturados**',
                      '```json', json.dumps(choice['message'], ensure_ascii=False, indent=2), '```', '',
                      f"Finalización: `{choice.get('finish_reason')}`. El candidato y el contexto exactos figuran en el payload enlazado.", '']
    lines += [f'[Comparación con los conjuntos esperados]({name}/replies.jsonl)', '']
lines += ['La compatibilidad débil acepta hora, audio y web para el seguimiento de SSID. '
          'AUTO con historial en roles elimina ese falso positivo, pero falla tres controles. '
          'Al representar el mismo historial como datos de referencia separados del texto actual, AUTO conserva los ocho conjuntos esperados. '
          'Es evidencia local para esta revisión/backend, no una garantía general del modelo.', '']
judgments = {
    'astra-reference-context11': {
        6: 'NO APROBADO: una petición válida termina en fallo de interpretación.',
        7: 'NO APROBADO: no hay respuesta final visible.',
        8: 'NO APROBADO: inventa14horas. La App salta turn.decide al encontrar «no abras» y llama al redactor sin observación.',
    },
    'astra-scoped-constraints11': {},
}
if (base / 'astra-integrated-real22/paired.json').exists():
    judgments['astra-integrated-real22'] = {
        5: 'APROBADO: distingue aire y agua y explica la mezcla de gases. No se exige una explicación exhaustiva; «en forma pura» se entiende referido a que el aire no es agua pura.',
        10: 'APROBADO: identifica la RTX 3060 Laptop observada. La primera persona es una elección de redacción, no un dato de hardware inventado.',
        15: 'APROBADO: pide la cantidad que falta para subir el volumen; no ejecuta una cantidad supuesta.',
        18: 'APROBADO: se identifica como BAXY. usuario y REDNOTE proceden de system.identity verificado, no son datos inventados. El encaminamiento a esa lectura queda como observación interna.',
        20: 'NO APROBADO: «no silencies el audio» termina en fallo de interpretación tras dos fallos de contrato. La prohibición no se convierte en efecto, pero falta una respuesta útil.',
        21: 'APROBADO como limpieza, fuera de los veinte casos: audio.volume confirma que ya está en 100; no se atribuye un cambio inexistente.',
        22: 'APROBADO como lectura posterior, fuera de los veinte casos: audio.status verifica volumen 100 y muted:false.',
    }
product_count = 0
for name, notes in judgments.items():
    folder = base / name
    rows = json.loads((folder / 'paired.json').read_text(encoding='utf-8'))
    result = json.loads((folder / 'RESULT.json').read_text(encoding='utf-8'))
    lines += [f'## {name}', '', f'[Casos y procedencia]({name}/CASES.json) · [Captura completa]({name}/paired.json) · [Prerregistro]({name}/PREREG.json)', '',
              f"Exit {result['exitCode']}; {result['elapsedSeconds']}s; GPU{result['gpuPeakMiB']:.2f}MiB; registro intacto:{result['registrationUnchanged']}.", '']
    for index, row in enumerate(rows, 1):
        product_count += 1
        lines += [f'### Turno {index}', '', '**Entrada literal**', '```text', row['request'], '```', '',
                  '**Respuesta literal**', '```text', row['final'] if row['terminal'] == 'published_final' else '[No hubo respuesta final visible]', '```', '',
                  f"Terminal: `{row['terminal']}`.", '', notes.get(index, 'APROBADO en este control: respuesta útil y coherente con la petición y sus restricciones.'), '']
    if name == 'astra-scoped-constraints11':
        with (folder / 'compose-audit.jsonl').open(encoding='utf-8') as stream:
            observations = [json.loads(entry) for entry in stream]
        for turn in ('t6', 't7', 't8', 't11'):
            evidence = next(row for row in observations if row['trace'] == turn)
            situation = json.loads(evidence['situation'])
            assert situation['operation'] == 'system.time' and situation['verified'] is True
            assert evidence['payload']['clock'] == '21:32'
        lines += ['Las cuatro horas (t6,t7,t8,t11) tienen hechos `system.time`, `verified:true`, UTC y offset local−180; '
                  'los payloads derivados indican21:32. La traza Core no contiene apertura de Steam. '
                  'Las prohibiciones t9/t10 no invocan Core.', '',
                  f'[Hechos observados]({name}/compose-audit.jsonl) · [Llamadas Core]({name}/shell-trace.jsonl)', '']
    if name == 'astra-integrated-real22':
        with (folder / 'compose-audit.jsonl').open(encoding='utf-8') as stream:
            published = {row.get('trace'): row for entry in stream
                         if (row := json.loads(entry)).get('published')}
        for turn in ('t7', 't8', 't9', 't10', 't12', 't13', 't14', 't16', 't17', 't18', 't19', 't21', 't22'):
            assert json.loads(published[turn]['situation'])['verified'] is True
        assert published['t7']['payload']['clock'] == published['t9']['payload']['clock'] == '21:45'
        assert published['t8']['payload']['date'] == '2026-09-06'
        assert json.loads(published['t22']['situation'])['observed']['state'] == {'volumePercent': 100, 'muted': False}
        lines += ['Dictamen: 19/20 casos de desarrollo útiles; t20 falla. Las dos comprobaciones de limpieza pasan aparte. '
                  'No son cien turnos frescos ni un porcentaje del goal. Hora, fecha, GPU, identidad y audio tienen observaciones verificadas. '
                  'El audio pasa de 100 a 35 y de nuevo a 100, sin silencio, según las capturas de esta corrida.', '',
                  f'[Hechos observados y borradores rechazados]({name}/compose-audit.jsonl) · [Decisiones y recuperación]({name}/turn-audit.jsonl)', '']
lines.insert(4, f'Este informe conserva {call_count} llamadas del modelo y {product_count} respuestas de producto. Las repeticiones entre variantes no se cuentan como turnos nuevos.')
(base / 'PRUEBAS_CONTEXTO_Y_NEGACION_C03.md').write_text('\n'.join(lines), encoding='utf-8')
