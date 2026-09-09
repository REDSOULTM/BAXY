from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
report = base / 'PRUEBAS_REFERENCIAS_Y_MODELO68_71.md'
assert not report.exists()
lines = ['# C03 — referencias, contexto y modelo68–71', '',
         'Controles técnicos consumidos/sintéticos; ninguna reserva humana ni UI/audio. '
         'No hay ejecución de funciones en estos replays. Fuente de producto intacta desde63.', '',
         '68 demuestra que retirar globalmente las respuestas del asistente rompe referencias y puede añadir una acción a una '
         'pregunta sobre un fallo. Diálogo completo5/6; sólo usuarios1/6; sin contexto1/6. '
         'El modelo registrado ya falla con diálogo completo al leer el segundo archivo: selecciona búsqueda. '
         'No se oculta ese fallo con una etiqueta de referencia correcta.', '',
         '69 prueba decisión previa de necesidad de diálogo, sin reescribir la petición:5/10 clasificaciones correctas y5/10 '
         'selecciones correctas.70 retira sólo response_format, conserva prompt y presupuesto: idéntico resultado. '
         'Se descarta esta estrategia; no se añade otro clasificador al producto ni más variantes de etiqueta.', '',
         '71 conserva todos los paquetes y el diálogo, cambia sólo al Qwen3.5-4B Q4_K_M heredado.9/10 selecciones correctas '
         'frente a6/10 de Qwen3-2507: recupera los cuatro archivos y leer el segundo, pero propone lectura ante ¿Por qué no pudiste?. '
         'No promoción. La mejora nativa exige recorrer producto y todos los roles, especialmente conocimiento y errores.', '']
paths = []
for name in ('selector-references68', 'selector-context69', 'selector-context70', 'selector-qwen35-71'):
    directory = base / ('astra-' + name)
    lines += [f'## {name}', '', (directory / 'RESULT.json').read_text(encoding='utf-8'), '']
    for raw in (directory / 'posts.jsonl').read_text(encoding='utf-8').splitlines():
        row = json.loads(raw)
        choice = row['response']['choices'][0]
        message = choice['message']
        operations = [c['function']['name'] for c in message.get('tool_calls', [])]
        lines += [f"### {row.get('id', row.get('turn'))} / {row.get('variant', 'candidate')}", '',
                  f"Entrada: {row['text']}", '', f"Selección: {json.dumps(operations)}; fin={choice['finish_reason']}.", '',
                  f"Texto bruto: {message.get('content', '')}", '']
        if 'dependencyResponse' in row:
            lines += [f"Decisión previa: {row['dependencyResponse']['choices'][0]['message']['content']}", '']
    paths += [f'artifacts/comprobaciones/C03/astra-{name}/{f}' for f in ('PREREG.json', 'RESULT.json', 'posts.jsonl')]
lines += ['## Herencia, contraste actual y límites', '',
          'Se reutilizan _bounded_history, los paquetes64 y la separación de contexto47. '
          'is_elliptical_followup excluye órdenes deícticas y no se fuerza a otro dominio. '
          '[Context engineering, fuente primaria consultada2026-09-07](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) '
          'motiva seleccionar información relevante; no certifica un clasificador para Qwen.69/70 lo refutan localmente.', '',
          'El activo Qwen3.5 ya existía. scratchpad/c03-native-qwen35.log y su variante thinking registran pruebas antiguas '
          'de conversación con fallos factuales y perfiles diferentes. No se borran ni se extrapola éxito de selección a conocimiento. '
          'Las rutas astra-native-qwen35/gpu.json y astra-native-qwen35-thinking/gpu.json no existían al consultarlas; '
          'no se atribuyen recursos antiguos sin evidencia.71 mide los actuales y guarda llama-command.json.', '',
          '[Ficha oficial Qwen3.5-4B consultada2026-09-07](https://huggingface.co/Qwen/Qwen3.5-4B) admite no-thinking mediante '
          'enable_thinking=false y publica perfil general0.7/top_p0.8/top_k20/min_p0/presence1.5. '
          '71 usa selección determinista0,seed0,256 tokens para aislar cambio de modelo. No adapta aún toda la inferencia. '
          '3slots de4096,KVq8,ngl99,b9980CUDA; GPU3175,56MiB,RAM4529,92MiB,12,89s,registro intacto.', '',
          'Prueba72: mismo prefijo de5 archivos y5 transferencias con override de modelo sólo en perfil aislado. '
          'Sin registro/promoción, sin cambios de código, sin detector69. Mide por la entrada real de producto y conserva '
          'payloads/causas/rechazos. El conductor no acredita UI/audio físico.', '']
report.write_text('\n'.join(lines), encoding='utf-8')
paths.append(str(report.relative_to(root)).replace('\\', '/'))
paths.append('artifacts/comprobaciones/C03/astra-selector-qwen35-71/llama-command.json')
(base / 'TRAMO68_71_PINS.json').write_text(json.dumps({'scope': 'Read-only native comparisons; no source/model promotion',
    'files': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}}, indent=2), encoding='utf-8')
print('Recorded68–71')
