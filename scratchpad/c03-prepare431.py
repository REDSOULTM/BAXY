from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

out = base / 'astra-native-identity430'
assert not (out / 'RESULT.md').exists()
rows = [json.loads(line) for line in (out / 'replies.jsonl').open(encoding='utf-8')]
assert len(rows) == 8
wire = local / 'C03-os-product417-private/http-posts.jsonl'
with wire.open(encoding='utf-8-sig') as stream:
    request = next(json.loads(line)['payload'] for line in stream
                   if (r := json.loads(line)).get('stage') == 'request'
                   and r['payload'].get('tools')
                   and r['payload'].get('tool_choice') == 'auto'
                   and r['payload']['messages'][-1].get('content') == 'What is my Windows username?')
names = [tool['function']['name'] for tool in request['tools']]
assert 'baxy_system__identity' not in names
(out / 'HARNESS_FAILURE.json').write_text(json.dumps({
    'exit_code': 1, 'error': 'AssertionError: identity function absent in first417 account payload',
    'completed_pairs': 4, 'planned_pairs': 11, 'unexecuted_pairs': 7,
    'first_unexecuted_case': 'actual417-account1', 'offered_function_names': names,
}, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(Path(os.environ['TEMP']) / 'c03-native-identity430-launch.log', out / 'launch.log')
(out / 'RESULT.md').write_text('''# 430 — alias descartado; corrida parcial por fallo del harness

Se completaron cuatro de los once pares previstos. El harness se detuvo antes
del primer control de cuenta de Windows: el primer payload AUTO417 seleccionado
no ofrecía la función que la prueba pretendía renombrar. Son ocho respuestas,
no veintidós; los siete pares restantes no se ejecutaron. Exit 1.

La evidencia disponible ya rechaza la adopción: Álvaro y Nina cambian la lectura
de Windows por afirmaciones falsas sobre memoria deshabilitada o imposibilidad
de recordar; Ana María sigue seleccionando la cuenta. La declaración sobre Omar
pasa de afirmar un guardado a decir que ha tomado nota, sin demostrar qué significa.
No se modifica el identificador nativo ni se repite la corrida buscando un éxito.

Recursos: 18,797 s; GPU 3175,5625 MiB, RAM 1204,92578125 MiB; sin violaciones de
los límites; manifiesto intacto. El finally cerró el cliente; comprobación posterior
sin llama-server, Baxy.App ni dotnet activos. Sin fuente adoptada.

429 sí demuestra 4/4 composiciones útiles con el evento de conversación existente,
pero todavía no resuelve cómo reconocer el turno de presentación completo.
El siguiente cambio aborda el fallo independiente de aclaración de aplicación.
''', encoding='utf-8', newline='\n')
paths = [out / name for name in ['PREREG.json', 'RESULT.md', 'HARNESS_FAILURE.json',
    'resources.json', 'replies.jsonl', 'command.json', 'launch.log']]
paths += [local / 'C03-native-identity430-private/posts.jsonl']
(out / 'PINS.json').write_text(json.dumps({str(p): sha(p) for p in paths}, indent=2) + '\n', newline='\n')

next_out = base / 'astra-application-clarification431'
next_out.mkdir(exist_ok=False)
prereg = {
    'utc': datetime.now(timezone.utc).isoformat(),
    'hypothesis': 'The existing explicit incomplete-request contract lacks a generic application object. Extend its app.open branch with a whole-request grammar using the existing opener/envelope and generic app nouns. Reuse ClarificationIntent(application), the existing model-authored question, and pending clarification. Do not widen the appId domain guard, approve guessed targets, introduce another classifier or fixed prose.',
    'baseline': 'Product426 T3 permission question and T6 false unsupported; both begin with native app.open then lose it at domain_grounding because appId is absent.',
    'inheritance': 'Current effect_intent.resolve_explicit_clarification_intent already handles missing volume/calendar/message fields and app.open window/default-browser ambiguity. __main__._prepare_turn_result already asks before retrieval/effect dispatch. Historical gemma4-agent slot_filling.md describes model questions plus platform-specific continuation: preserve asking for missing information, do not restore brand/TTL heuristics.',
    'primary_sources': [
        {'url': 'https://legacy-docs-oss.rasa.com/docs/rasa/forms/', 'scope': 'Legacy OSS reference for requesting unfilled required slots; not a proposal to add Rasa or fixed utterances.'},
        {'url': 'https://json-schema.org/understanding-json-schema/reference/object#required', 'scope': 'Required-field validity is distinct from capability availability. No schema changes.'},
    ],
    'criteria': 'ES/EN/natural mix and polite wrappers with only generic app object ask which app with no effect. Named installed/uninstalled targets, questions, negation, hypothetical, external device and appended commands must not be consumed by this grammar. Preserve pending private precedence. Product replay426 after owner/Fast validation, same eight turns individually judged. Synthetic development only.',
    'validation': 'Failing owner regressions before source; focused then effect_intent/turn_policy/current_catalog_review/catalog_operation_aliases owners and Fast. No Full during repair.',
    'sources_before': {name: sha(root / name) for name in ['src/baxy_mind/effect_intent.py', 'src/baxy_mind/__main__.py', 'src/baxy_mind/llm.py', 'tests/test_effect_intent.py', 'tests/test_turn_policy.py']},
}
(next_out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    shutil.copyfile(base / name, base / name.replace('.md', '_430_ANTES_431.md'))
checkpoint = '''# C03 — EN_CURSO — 431 preparado, fuente vigente 425

Goal completo, Goal-c03 / HEAD 2bf3d4c. Preservar WIP/main/evidencia. Sin agentes,
commit/push ni Full durante reparación. BAXY manual cerrado. Encuesta terminada:
742 respuestas, revisión1248; servidor101140/padre29800 intacto.17 mensajes directos
consolidados; automáticos excluidos. No modelos/builds activos.

## Mejora medida
425: cache-ram0 y no-mmap sólo con GPU; CPU conserva mmap. Mismos pesos, contexto,
precisión, slots y sampler.6 focales/293 owners +121subtests,0skips; Fast verde
build4,11s.426 producto: RAM3106,70MiB/GPU3177,56MiB,55,422s, sin corte.
8 terminales,4 útiles, contenidos iguales423/424. Comparación424 mmap+cache0:
RAM5207,20MiB. RSS del árbol; no mínimo global ni certificación de voz física.
Detalle legible en RECURSOS_2026-09-08.md; pruebas y hashes en astra-host-memory425.

## Reparación actual
426 T3/T6 «Abre una aplicación»: native app.open correcto; domain_grounding lo
retira por falta de appId. T3 pide permiso;T6 dice falsamente que no puede.
431 reutilizará resolve_explicit_clarification_intent: rama de app.open existente,
gramática de petición completa con objeto genérico, pregunta del modelo por la
aplicación. No ampliar autoridad de appId ni añadir otra capa. PREREG431 escrito.
Primero regresiones negativas y positivas, baseline, luego fuente y owners/Fast.

Presentación personal:426/427 AUTO confunde nombre humano con cuentaWindows.
427 guardia genérica9/13: descartar (rompe requests de memoria y app incompleta).
428 status session_context_only2/4;429 evento conversation4/4 composición, todavía
sin clasificación segura.430 alias identity→windows_account descartado:4/11pares,
fallo de harness antes de cuentas y tres presentaciones aún incorrectas. RESULT430.
No atajo C# con DeclaredNameInputPattern: puede tragarse órdenes sin puntuación.

## Fuente anterior y pendientes
418 precedencia privada sobre aclaración pública:6 focales/2007owners/Fast;
runtime explícito omitido, no pass. EN verificado en426; ES T7 dice «Mi nombre»
en vez del nombre humano.416 OS Caption CIM:36provider/193integration/Fast;
4178/9 útiles, cuentaT3 pide permiso innecesario.410/402/404/395/397 conservados.
413/414 early-read intercambian fallos;349 source=user no arregla sujeto.

Quedan ocho rutas y expectativas742/fallos manuales264;0 requisitos certificados
finales y0/100 humanos frescos (204potenciales335 reservados). Averías/recuperación,
UI real,voz física/ASR/wake y ≤4GB conjunto,runtime/instalación/contratosC04–C09,
Full final verde entero y publicación fuera de main. Sin ETA ni cierre parcial.
'''
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    (base / name).write_text(checkpoint, encoding='utf-8', newline='\n')
relay_path = base / 'RELEVO_ACTIVO.json'
relay = json.loads(relay_path.read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='430 discarded after four pairs; harness assertion recorded. Source425 current; no model/build active.',
    continuation='431: existing explicit application clarification grammar; failing regressions before source, then owners/Fast and same product426 replay. Full C03 remains active.')
relay_path.write_text(json.dumps(relay, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print('430 recorded; 431 preregistered; checkpoint rewritten')
