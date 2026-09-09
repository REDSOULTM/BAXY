from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
lines = ['# C03 — pruebas literales del selector nativo y del contexto', '',
         'Desarrollo y regresión consumidos; no son los cien turnos de aceptación. '
         'Las entradas históricas y los controles sintéticos se identifican en cada CASES.json. '
         'Se preservan todos los fallos. Las transcripciones siguientes se leen de las capturas, sin reescribir respuestas.', '']
notes = {
    'astra-native-primary13': {
        3: 'NO APROBADO: fallo de composición, sin respuesta útil.',
        4: 'NO APROBADO: explicación cortada a mitad de palabra.',
        5: 'NO APROBADO: confunde el identificador SSID con una contraseña.',
        7: 'NO APROBADO: no interpreta una petición válida de hora.',
        9: 'NO APROBADO: fallo de composición, sin respuesta útil.',
        10: 'NO APROBADO: afirma las 14 horas sin lectura; las lecturas contiguas verifican 20:41.',
    },
    'astra-native-budget13': {
        3: 'NO APROBADO: atribuye Steam a Microsoft y lo describe como nube de computación.',
        4: 'No aceptado como prueba de exactitud: termina, pero añade generalizaciones sobre humedad y procesos biológicos que la corrida no verifica.',
        5: 'NO APROBADO: conserva la analogía falsa con una contraseña.',
        7: 'NO APROBADO: no interpreta una petición válida de hora.',
        9: 'NO APROBADO: fallo de composición, sin respuesta útil.',
        10: 'NO APROBADO: afirma las 14 horas sin lectura; las lecturas contiguas verifican 20:54.',
    },
    'astra-definition-context7': {
        5: 'NO APROBADO: pierde el referente SSID y pregunta por un tema que ya está en el historial. turn-audit localiza la conversión de knowledge a clarify en observation_not_recital, antes del chat.',
        7: 'NO APROBADO: la primera respuesta explica DNS correctamente, pero App y compose rechazan el hostname como internal_code; la tercera composición introduce metadiscurso. No es un fallo de conocimiento en la primera respuesta.',
    },
    'astra-public-host3': {},
}
for name, judgments in notes.items():
    folder = base / name
    rows = json.loads((folder / 'paired.json').read_text(encoding='utf-8'))
    result = json.loads((folder / 'RESULT.json').read_text(encoding='utf-8'))
    lines += [f'## {name}', '', f'[Prerregistro]({name}/PREREG.json) · [Captura]({name}/paired.json) · [Recursos]({name}/RESULT.json)', '',
              f"Proceso: exit {result['exitCode']}; {result['elapsedSeconds']} s; pico GPU {result['gpuPeakMiB']:.2f} MiB. Registro sin cambios: {result['registrationUnchanged']}.", '']
    for index, row in enumerate(rows, 1):
        lines += [f'### Turno {index}', '', '**Entrada literal**', '```text', row['request'], '```', '', '**Respuesta literal**',
                  '```text', row['final'] if row['terminal'] == 'published_final' else '[No hubo respuesta final visible]', '```', '',
                  f"Terminal registrado: `{row['terminal']}`.", '',
                  judgments.get(index, 'APROBADO en este control: conserva la petición y los hechos, o reconoce honestamente la restricción. No acredita otras rutas.'), '']
name = 'astra-knowledge-history-factorial'
lines += ['## Ablación de políticas e historial', '',
          'Doce llamadas directas. Mismo modelo, temperatura, presupuesto y template; se comparan presencia de las políticas y presencia del historial publicado. '
          'Se captura la primera respuesta, antes de validadores/reintentos. El historial previo exacto está en cada payload.', '',
          f'[Método e historial]({name}/PREREG.json) · [Todos los payloads y respuestas]({name}/posts.jsonl)', '',
          'Hallazgo: con políticas y sin historial ajeno al tema, Steam se atribuye a Valve y SSID se define como nombre de red. '
          'Con historial aparecen hechos falsos; sin políticas varias respuestas agotan el presupuesto. '
          'Esto localiza una contribución del contexto, sin demostrar que el modelo aislado siempre acierte ni justificar borrar el historial general.', '']
with (base / name / 'posts.jsonl').open(encoding='utf-8') as stream:
    for index, line in enumerate(stream, 1):
        row = json.loads(line)
        choice = row['response']['choices'][0]
        lines += [f"### Llamada {index}: {row['stage']}", '', '**Entrada literal**', '```text', row['text'], '```', '',
                  '**Respuesta literal**', '```text', choice['message'].get('content') or '', '```', '',
                  f"Finalización del modelo: `{choice.get('finish_reason')}`. Las respuestas `length` están incompletas y no se aprueban.", '']
(base / 'PRUEBAS_SELECTOR_Y_CONTEXTO_C03.md').write_text('\n'.join(lines), encoding='utf-8')
