from pathlib import Path
import json

BASE = Path(__file__).resolve().parents[1] / 'artifacts/comprobaciones/C03'
probe = BASE / 'astra-qwen-documented-profile'
rows = [json.loads(line) for line in (probe / 'posts.jsonl').read_text(encoding='utf-8').splitlines()]
live = [json.loads(line) for line in (BASE / 'astra-knowledge-owner-live/replies.jsonl').read_text(encoding='utf-8').splitlines()]
previous = {row['id']: row for line in (BASE / 'astra-real-dialogue-system-layers/replies.jsonl').read_text(encoding='utf-8').splitlines() if (row := json.loads(line))['variant'] == 'baseline'}
header = '''# C03 — Qwen documentado, capas y respuestas literales

2026-09-06. Casos de desarrollo ya consumidos, procedentes de los logs reales.
No son reserva, ni una sesión histórica consecutiva, ni aceptación de C03.
La clasificación utiliza el contexto reconstruido registrado en PREREG; el chat
se mide sin historial. Ninguna de estas llamadas ejecuta operaciones del PC.

## Qué se comparó

69 llamadas directas al servidor local: 54 de texto y 15 de clasificación.
Capas: mensaje de usuario solo con máximo 512 tokens; mensajes preparados por
BAXY con 512; mismos mensajes con su presupuesto original (128, Steam 64).
Muestreo actual greedy con seed 0 frente a recomendaciones de Qwen con seeds
0 y 17 previamente fijadas: temperatura 0,7, top-p 0,8, top-k 20, min-p 0,
penalización de presencia 0. Mismos pesos, cuantización y backend.

El servidor no usa wrapper, validadores ni reintentos de BAXY para estas salidas;
LlmRuntime sólo administra su arranque y cierre. La etapa de mensajes BAXY hereda
sus prompts preparados, por lo que sí incluye el efecto de su clasificación de
presentación. 84,89 s; pico 3497,56 MiB GPU y 3612,91 MiB RAM; registro intacto.

Fuentes y configuración: [investigación](INVESTIGACION_MODELO_C03.md).
Reproducción, payloads completos, respuestas, props y template:
[carpeta de evidencia](astra-qwen-documented-profile/PREREG.json).

## Hallazgos leídos

- La primaria interpreta la fecha correctamente; el veto posterior ya estaba
  localizado. El muestreo nuevo no corrige el volumen absoluto contextual.
- El modelo solo también pide aclarar «no silencies el audio». Con los mensajes
  BAXY aparece «SIEMPRE» o una pregunta innecesaria. Ningún perfil la resuelve.
- En «no subas el volumen», el perfil documentado más los mensajes BAXY afirma
  que ya está bajado sin observación. No se promueve ese perfil por reputación.
- Steam genera una explicación extensa sin BAXY, truncada incluso a 512; el
  perfil greedy añade «millones de juegos». El perfil nuevo no acredita exactitud
  general. Con BAXY, antes del cambio, una regla confunde el prefijo «ahora» con
  una observación y obliga a atribuirle al usuario la explicación solicitada.
- La pregunta del aire muestra que una respuesta generalmente correcta puede
  añadir afirmaciones incorrectas: hay una comparación con fuego en el Sol y
  negaciones excesivas sobre el agua del aire. No se cuenta todo como aprobado.
- El template del GGUF difiere del oficial en tratamiento del historial de
  pensamiento. Los dos renders de conversación simple comparados son idénticos;
  esa diferencia no explica por sí sola los fallos aquí. No se cambió el template.

Estas observaciones no son una puntuación exhaustiva de todas las afirmaciones de
las 69 salidas. Se publican completas para revisión; no hay árbitro automático que
las declare correctas por haberse generado. Ninguna cuenta entre los cien finales.

## Cambio comprobado en la ruta normal de chat

Una pregunta clasificada como conocimiento conserva ese propósito y ya no se
convierte en observation_ack por empezar con adverbio o sustantivo. No se añadió
un filtro para Steam ni una respuesta fija. El seguimiento conserva su contrato.
El sampler sigue igual. Pruebas dueñas: 1033 pass, 0 skip, 5,84 s.
Seis llamadas normales de chat con wrapper/guardas/reintentos, 7,44 s,
3495,56 MiB GPU, 2819,95 MiB RAM. Registro intacto. No acredita UI.

'''
verdicts = {
    't3': 'APROBADO: responde París.',
    't4': 'APROBADO: identifica H₂O y la composición molecular.',
    't5': 'NO CERRADO: la distinción aire/agua es correcta; la afirmación final sobre ausencia/cantidad de H₂O necesita corregirse o justificarse, y no se acepta como prueba de exactitud completa.',
    't6': 'APROBADO para la petición sencilla del dueño: explica la función de Steam. «Aplicaciones como Steam Workshop» es una imprecisión terminológica registrada, no una atribución de acciones al PC.',
    't11': 'APROBADO: acepta no subir el volumen; pregunta final redundante, sin afirmar un cambio.',
    't20': 'NO APROBADO: SIEMPRE y la pregunta no reconocen adecuadamente la restricción.',
}
parts = [header]
for row in live:
    old = previous[row['id']]
    parts += [f"### {row['id']} — prueba normal tras el cambio\n\nEntrada literal:\n\n```text\n{row['text']}\n```\n\n",
              f"Antes, respuesta literal o error registrado:\n\n```text\n{old.get('answer') or old.get('error')}\n```\n\n",
              f"Después, respuesta literal:\n\n```text\n{row.get('answer') or row.get('error')}\n```\n\n{verdicts[row['id']]}\n\n"]
parts.append('## Anexo — las 69 llamadas directas, sin recortes\n\nEl payload completo y el contexto de cada llamada están en posts.jsonl.\n\n')
for number, row in enumerate(rows, 1):
    choices = (row.get('response') or {}).get('choices') or [{}]
    choice = choices[0]
    current = row['payload']['messages'][-1]['content']
    # The structured call includes the catalog in this last message. Its literal
    # request is separately preserved in the immutable preregistration.
    if row['layer'] == 'primary_structured':
        prereg = json.loads((probe / 'PREREG.json').read_text(encoding='utf-8'))
        current = next(case['text'] for case in prereg['contextCases'] if case['id'] == row['id'])
    answer = (choice.get('message') or {}).get('content') or row.get('error') or ''
    parts.append(f"### Llamada {number}: {row['layer']} / {row['id']} / {row['profile']} / seed {row['seed']}\n\nEntrada literal: \n\n```text\n{current}\n```\n\nRespuesta literal:\n\n```text\n{answer}\n```\n\nfinish_reason: `{choice.get('finish_reason')}`; {row['seconds']} s.\n\n")
(BASE / 'PRUEBAS_MODELO_DOCUMENTADO_C03.md').write_text(''.join(parts), encoding='utf-8')
(BASE / 'astra-knowledge-owner-live/adjudication.json').write_text(json.dumps({'purpose':'consumed development, not final acceptance','verdicts':verdicts},ensure_ascii=False,indent=2),encoding='utf-8')
print('69 direct calls and 6 normal chat replies preserved in Markdown.')
