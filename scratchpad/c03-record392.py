"""Close the records of completed diagnostics; never rewrite captured responses."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'

def read(path):
    assert path.stat().st_size < 1_000_000, path
    return json.loads(path.read_text(encoding='utf-8-sig'))

def rows(path):
    assert path.stat().st_size < 1_000_000, path
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]

def quoted(text):
    return '\n'.join('> ' + line for line in text.splitlines())

def record(folder, title, verdict, notes, responses=True):
    out = base / folder
    prereg = read(out / 'PREREG.json')
    result = [f'# {title}', '', verdict, '', notes, '', 'Sin edición de fuente ni promoción de runtime. Diagnóstico de desarrollo; no acredita aceptación humana fresca, producto completo, UI ni voz física.', '']
    if responses:
        for row in rows(out / 'replies.jsonl'):
            case = next(c for c in prereg['cases'] if c['id'] == row['id'])
            request = case.get('request', case.get('text'))
            history = case.get('history', [])
            reference = case.get('reference', prereg.get('reference'))
            if reference:
                request = request or reference['messages'][-1]['content']
                history = reference['messages'][1:-1]
            result += [f"## {row['id']}" + (f" — {row['variant']}" if 'variant' in row else ''), '', 'Contexto literal:', '']
            for message in history:
                result += [f"**{message['role']}**", quoted(message['content']), '']
            result += ['Entrada:', quoted(request), '', 'Respuesta literal:', '']
            if 'choice' in row:
                message = row['choice']['message']
                result += [quoted(message.get('content') or '(sin prosa)')]
                if message.get('tool_calls'):
                    result += ['', 'Llamada propuesta (no ejecutada):', '```json', json.dumps(message['tool_calls'], ensure_ascii=False, indent=2), '```']
                result += ['', f"finish_reason: {row['choice'].get('finish_reason')}; {row['seconds']} s.", '']
            else:
                result += [quoted(row.get('answer', row.get('detail', ''))), '', f"{row['seconds']} s. Guardia de estado no leído: {row.get('unread_machine_claim')}; idioma opuesto: {row.get('opposite_language')}. Estas guardias no certifican verdad semántica.", '']
    result_path = out / 'RESULT.md'
    assert not result_path.exists(), result_path
    result_path.write_text('\n'.join(result) + '\n', encoding='utf-8')
    pin_paths = [out / 'PREREG.json', result_path]
    for name in ['replies.jsonl', 'RESOURCES.json', 'command.json']:
        if (out / name).exists():
            pin_paths.append(out / name)
    private = Path(prereg['private'])
    for name in ['posts.jsonl', 'server.log']:
        if (private / name).exists():
            pin_paths.append(private / name)
    pins = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in pin_paths}
    (out / 'PINS.json').write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')

record('astra-qwen9b-native389', '389 — 9B con mmap: detenido por RAM disponible',
       'No hay resultado de calidad: el watchdog cerró el modelo antes de la primera respuesta.',
       'RESOURCES.json: GPU 2905,574 MiB; RAM del árbol 5770,914 MiB; 13,797 s. Se activó el límite de RAM libre del sistema (<768 MiB), no el de GPU. completed=false, manifest_unchanged=true. La cota no se relajó. No atribuir ausencia de respuesta a comprensión del modelo.', False)
record('astra-qwen9b-native390', '390 — 9B sin mmap: cabe aislado, no mejora identidad',
       '2/4 útiles: ambas preguntas sobre la cuenta de Windows proponen system.identity correctamente; ambas preguntas sobre la persona repiten la frase previa del asistente y no recuperan Eva. No adoptar el modelo.',
       'Mismos cuatro casos, prompt, historial, herramientas y sampler de 387/389; --no-mmap cambia la carga. RESOURCES.json: GPU 2918,316 MiB (2,85 GiB), RAM del árbol 3987,754 MiB (3,89 GiB), 30,11 s, sin violaciones. Usa RAM adicional. No mide convivencia con voz ni mínimo de VRAM del producto. Ninguna operación ejecutada; manifest_unchanged=true.')
record('astra-native-answer-contract391', '391 — responsabilidad de la respuesta nativa',
       'Rechazado: 5/8 útiles con instrucción original, 4/8 con la última frase modificada. No cambia fuente.',
       'T10, identidad de BAXY, Lucía y París conservan contenido útil; el aire pasa de correcto a una respuesta contradictoria ("Sí, el aire no es H2O"). Persistencia explícita, persona Álvaro tras cancelación y persona Eva siguen fallando. La mayor longitud de algunas respuestas tampoco demuestra mejora de voz. No repetir variantes comparables del selector sin una causa nueva.')
record('astra-context-owner392', '392 — resolvedor contextual existente',
       'Rechazado como dueño general de preguntas con historial: 5/10 útiles. Esquema válido y guardias aprobadas no bastan.',
       'Útiles: t5 (Jordan), t10 (Álvaro), assistant-conflict (Jordan), human-identity-es (Eva), corrected-self-name (Casey). Fallos: third-party atribuye Morgan al usuario; family-identity atribuye Noah al usuario aunque es su hermano; explicit-persistence inventa que Jordan fue guardado; product380-t9 niega el dato de Álvaro por memoria deshabilitada; assistant-identity responde como asistente genérico en español a una pregunta inglesa. Las guardias sólo detectan el último idioma, no los errores de atribución ni el guardado inventado. No enrutar todas las preguntas aquí ni interpretar direct_answer no vacío como evidencia.')

old = base / 'CHECKPOINT.md'
archive = base / 'CHECKPOINT_386_ANTES_392.md'
assert not archive.exists()
archive.write_bytes(old.read_bytes())
checkpoint = '''# C03 — checkpoint392 — EN_CURSO

Goal completo activo en Goal-c03, HEAD 2bf3d4c. Preservar WIP, main y evidencia.
Sin agentes, commit/push ni Full durante reparación. BAXY está cerrado para uso manual.
16 mensajes directos y 742 registros de encuesta rev1248 consolidados; automáticos excluidos.
Encuesta original y servidor 101140 intactos. No hay modelos ni producto de diagnóstico activos
al verificar procesos tras 392. Registros 389–392 completados en sus RESULT.md y PINS.json.

## Fuente y validación vigentes

Última .NET: 379, cancelación conserva operación y target seguros tras retirar la invocación.
Seis suites dueñas: 1977 pass, 0 skips, 2m18s. Fast 17,86s de build, cero warnings/errors.
Última Python: 383, conserva borrador nativo sin llamadas/finish_reason=stop como initial_reply
local al turno de conversación; lo somete a las guardias y reintentos de chat. No caché nueva.
Focal 9 pass, 0 skips, 957 deselected, 1,32s; dueñas 1342 pass, 0 skips, 6,01s;
Fast 1,52s de build, cero warnings/errors. Sin edición fuente posterior a 383, sin Full.
Pins V8 actuales actualizados en 383; evidencia histórica intacta.

## Qué está demostrado y qué falla

Producto 380 anterior a 383: 6/10 útiles + 1 parcial + 1 silencio (antes 370: 4/10).
Cancelaciones ya nombran bien la operación y respetan idioma. T5 silencio, T7 eco,
T9 identidad del asistente en vez de persona, T10 confusión entre contexto y persistencia.
No se habilitó ni guardó memoria: journal status completed y dos save/recall fallidos.
381/382 diagnóstico y 384 fuente real: 4/5 frente a 3/5 previo. 385→386 panel fijo de 17:
13/17→14/17 útiles en contenido. Falla persistencia explícita (catálogo público excluye memory),
persona Álvaro tras cancelación y persona Eva interpretada como cuenta Windows. No aceptación fresca.

387 descripción más precisa de system.identity: 2/4→2/4, rechazada.
388 descarga 9B experimental con SHA verificado; registro del producto intacto.
389 9B/ngl14 con mmap detenido antes de respuestas por RAM libre <768 MiB; sin juicio de calidad.
390 mismo 9B/ngl14 sin mmap: 2/4, no mejora identidad. GPU 2918,316 MiB, RAM 3987,754 MiB,
sin violaciones; usa RAM adicional y no acredita voz simultánea. No adoptar 9B.
391 última frase del selector pide contestar directamente: 5/8→4/8; identidad no mejora
y el aire se vuelve contradictorio. Rechazado; no más variantes comparables de redacción.
392 resolvedor contextual existente: 5/10. Confunde nombre de tercero/hermano con usuario,
inventa guardado y sigue negando Álvaro por memoria deshabilitada. Rechazado como dueño general.

## Siguiente acción y límites del diseño

Corregir separación contexto conversacional / memoria persistida / cuenta Windows, midiendo
primero el dueño adecuado. No volver a ampliar el prompt del selector ni instalar un nombre
en caché global. No usar respuestas anteriores del asistente como prueba del nombre.
Inspeccionados: llm._compose_literal_recall_answer (5965) conserva un literal mediante [[R1]],
pero presupone referencia ya resuelta; no demuestra a quién pertenece. _resolve_contextual_answer
no comprueba la verdad; 392 demuestra el riesgo. NaturalMemoryRequestParser.TryBindSaveInput
extrae una declaración sólo para un guardado previamente solicitado; AskToSave NO trae operación.
No hay diseño nuevo adoptado ni script393 preparado al escribir este checkpoint.
Herencia revisada: biblioteca/gemma4-agent/documentacion/08_memoria_jarvis/research/2_memoria.md
1–75: separación de hechos y procedencia útil como hipótesis; sus porcentajes/propuestas no son
mediciones de BAXY actual. No añadir capas de memoria, embeddings o resúmenes sin necesidad medida.

## Pendiente del goal completo

Ocho rutas con voz propia e idioma correcto; fallos de sesión 264 y base de 742 (cero aceptados
individualmente en el candidato final); 100 humanos frescos, literales y con procedencia/contexto
congelados (cero certificados/congelados); averías aparte; UI real; voz física/ASR/wake y recursos
conjuntos <=4 GB; runtime/instalación y contratos C04–C09 sin ejecutar otros goals; Full final verde
y publicación fuera de main. Sin bloqueo externo ni cierre. No porcentaje o plazo inventado.
Historial detallado: CHECKPOINT_386_ANTES_392.md y RESULT/PINS de cada tramo.
'''
old.write_text(checkpoint, encoding='utf-8')
(base / 'HANDOFF.md').write_text(checkpoint, encoding='utf-8')
active_path = base / 'RELEVO_ACTIVO.json'
active = read(active_path)
active.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='392 complete. Source383 unchanged/validated.389 resource stop;390 2/4 isolated no-mmap, no promotion;391 5/8->4/8 rejected;392 5/10 contextual resolver rejected. All diagnostic models closed.',
    continuation='Separate conversation facts, persisted memory and Windows identity at the correct existing owner. No new prompt variants or global name cache. Full C03 active, manual BAXY closed.')
active_path.write_text(json.dumps(active, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Reports and pins389–392 written; checkpoint392 current; no source edited.')
