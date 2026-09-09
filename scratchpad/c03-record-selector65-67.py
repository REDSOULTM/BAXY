from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
report = base / 'PRUEBAS_CONTEXTO_SELECTOR65_67.md'
assert not report.exists()
lines = ['# C03 — aislamiento del historial en selección65–67', '',
         'Se reutilizan cuatro paquetes AUTO exactos de files64-wire/wire-29264.jsonl. '
         'La hora tomó la ruta determinista y no produjo un quinto paquete. '
         'No hay efectos, validadores de decisión ni reintentos. Conservan las instrucciones y herramientas de BAXY; '
         'no son pruebas del modelo sin wrapper. Sin reserva humana ni UI/audio.', '',
         'Expectativa en los cuatro pedidos: proponer filesystem.read.text como efecto de lectura. '
         'El plan añade búsqueda e identidad y el proveedor conserva su límite. Elegir search sólo no cumple leer.', '',
         '65: capturado1/4; sin contexto4/4; instrucción sobre alcance del fallo2/4. '
         '66: capturado1/4; roles nativos2/4; sólo mensajes anteriores del usuario4/4. '
         '67: capturado1/4; descripción de lectura más explícita2/4. '
         'Ninguna variante se ha incorporado al producto.', '']
paths = []
for name in ('selector-history65', 'selector-history66', 'selector-catalog67'):
    directory = base / ('astra-' + name)
    lines += [f'## {name}', '', (directory / 'RESULT.json').read_text(encoding='utf-8'), '']
    for raw in (directory / 'posts.jsonl').read_text(encoding='utf-8').splitlines():
        row = json.loads(raw)
        choice = row['response']['choices'][0]
        message = choice['message']
        operations = [call['function']['name'] for call in message.get('tool_calls', [])]
        lines += [f"### {row['turn']} / {row['variant']}", '', f"Entrada: {row['text']}", '',
                  f"Selección: {json.dumps(operations)}; finish_reason={choice['finish_reason']}.", '',
                  f"Texto bruto: {message.get('content', '')}", '']
    paths += [f'artifacts/comprobaciones/C03/astra-{name}/{f}' for f in ('PREREG.json', 'RESULT.json', 'posts.jsonl')]
lines += ['## Decisión y siguiente comparación', '',
          'La retirada del historial o únicamente de las respuestas anteriores restablece la selección en4/4: '
          'hay evidencia causal de contaminación por prosa previa. Eso NO autoriza borrar el historial de todos los pedidos: '
          'faltan controles de referencias cuyo efecto se encuentre sólo en una oferta o explicación del asistente. '
          'El contexto de conversación y grounding debe conservarse. Los intentos de añadir instrucciones, cambiar roles o '
          'retocar la descripción no resuelven; no repetir esas variantes. La siguiente hipótesis debe separar intención '
          'actual y referencias necesarias, con contrastes antes de editar fuente.', '',
          'Reutilización: ASTRA47 e INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md ya fijan diferencias entre contexto '
          'de conversación y protocolo nativo. El caso actual es selección, no respuesta de conocimiento; no extender '
          'starts_new_definition_topic a acciones. is_elliptical_followup exige interrogativo y NO sirve para close that/hazlo. '
          'No añadir un detector de referencias parcial sin demostrar esos contrastes.', '',
          'Instrumentación:65 primero se detuvo antes de PREREG/inferencia por esperar5 AUTO; corregido a4 y ejecutado una sola vez. '
          '66 deriva del script65: su PREREG conserva el method anterior y añade comparison66 que describe la comparación efectiva; '
          'posts.jsonl demuestra que no_context/scoped_history NO se ejecutaron en66. Esa duplicación de metadatos se conserva '
          'y queda aclarada aquí, sin alterar la preregistración. El añadido extra del script no se usa en66/67.', '',
          'Producción actual: sólo guard del proveedor63 añadido desde fuente58; descripción pública, historial y selector intactos. '
          'PRUEBAS_ARCHIVOS63_64.md conserva2/5 y las negativas posteriores. No cierre de C03. '
          'El script de progreso64 está preparado, no ejecutado.', '']
report.write_text('\n'.join(lines), encoding='utf-8')
paths.append(str(report.relative_to(root)).replace('\\', '/'))
(base / 'TRAMO65_67_PINS.json').write_text(json.dumps({'scope': 'Native diagnostic comparisons, no source promotion',
    'files': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}}, indent=2), encoding='utf-8')
print('Recorded65–67')
