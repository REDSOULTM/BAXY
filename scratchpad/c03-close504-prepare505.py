"""Close the audio protocol observation and preregister a private chat-boundary pair."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-audio-mind504'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines()]

cases = json.loads((out / 'PREREG.json').read_text(encoding='utf-8-sig'))['cases']
replies = {r['id']: r for r in rows(out / 'replies.jsonl')}
bindings = {r['id']: r for r in rows(out / 'bindings.jsonl')}
adjudication = []
for case in cases:
    row = replies[case['id']]
    reply = row['reply']
    selected = reply.get('effectOperations', [])
    assert selected == case['expected'], case['id']
    binding = bindings.get(case['id'])
    if binding:
        value = binding['reply']
        if binding['type'] == 'plan':
            assert [s['operation'] for s in value['steps']] == selected
            actual = {k: v for step in value['steps'] for k, v in step['arguments'].items()}
        else:
            assert value['ok'] is True
            actual = value['arguments']
        assert actual == case['arguments'], (case['id'], actual)
    useful = case['id'] != 'word-meaning'
    if case['id'] == 'owner49':
        assert reply['kind'] == 'clarify' and reply['question']
    adjudication.append({**row, 'proposal_or_clarification_correct': useful,
                         'binding_correct': True if binding else None,
                         'reason': 'Expected operations/order and grounded arguments preserved; no provider execution.' if useful else 'Definition includes internal selector prose and an offer of microphone control not evidenced by this response.'})
resources = json.loads((out / 'RESOURCES.json').read_text(encoding='utf-8-sig'))
assert len(replies) == 14 and len(bindings) == 11
assert resources['completed'] and not resources['violations'] and resources['manifest_unchanged']
write(out / 'ADJUDICATION.json', adjudication)
write(out / 'RESULT.json', {'utc': datetime.now(timezone.utc).isoformat(),
    'process_session': 98221, 'exit': 0, 'proposals_correct': 13, 'turns': 14,
    'bindings_correct': 11, 'bindings': 11, 'resources': resources,
    'source': 'effect_intent503, __main__501, llm466',
    'limits': 'Development mind/plan/arguments only. No provider effect, shell, physical audio, voice or C03 acceptance.'})
(out / 'RESULT.md').write_text('''# Audio: protocolo con fuente 503

13 de 14 propuestas/aclaraciones correctas y 11 de 11 bindings correctos. La petición literal owner46 ahora selecciona audio.mute en 0,016 s y liga state=false. Owner51 conserva volumen100 y silencio desactivado: 0,437 s de turno y 0,016 s de plan. Se mantienen los demás controles, el orden y los argumentos.

La definición de desmutear aún publica la prosa interna del selector. En 502 la respuesta visible coincide literalmente con su contenido HTTP20, posteriormente pasado a chat como initial_reply. No se atribuye a un modelo sin aislar esa reutilización. El siguiente diagnóstico 505 compara esa frontera con la generación bajo el rol real de conversación y controles de memoria ya consumidos.

Sesión98221 recogida exit0. RAM1778,219MiB y VRAM3497,559MiB;38,813s; sin violaciones y manifiesto intacto. Son mente y conductor, sin UI, voz ni efectos físicos. No promoción ni aceptación C03.
''', encoding='utf-8')
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})

for name in ['CHECKPOINT.md', 'HANDOFF.md', 'ESTADO_PARA_DUENO_2026-09-08.md']:
    path = base / name
    (out / (name.removesuffix('.md') + '-before.md')).write_bytes(path.read_bytes())
checkpoint = (base / 'CHECKPOINT.md').read_text(encoding='utf-8-sig')
tail = checkpoint[checkpoint.index('Cambios previos conservados:'):checkpoint.index('\n503: baseline')]
current = '''# C03: fuente 503 validada y protocolo 504 cerrado

Goal íntegro activo. Goal-c03/HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. Autoridad C03_ASTRA_AUTORIDAD.md, identidad y AGENTS.md. Preservar WIP/main/evidencia. Sin agentes, commits, publicación ni Full durante reparación. BAXY manual cerrado; encuesta742/rev1248 y procesos101140/29800 conservados.

Sin runtime, prueba ni build activo. Último504/sesión98221 recogido exit0. Fuente effect_intent503, __main__501, llm466. Siete suites3404pass+121subtests/0skips52,86s y Fast verde/Release3,25s0warnings/errors; sesiones7688 y60961 cerradas. Buildservers cerrados. Manifiesto13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed intacto.

503 comparte la familia unmute/desilenciar/dessilenciar y marcos de petición tras asentimiento. Normaliza deseo explícito sólo en lectores de efectos; preserva conversaciones/aclaraciones y la cabeza heredada para escribir notas. Seis regresiones de la primera normalización global corregidas y sus fallos preservados. 501 conserva contexto numérico sólo ante el anterior pedido humano cuyo contrato de volumen está incompleto, con guardas y binding compartidos.

504:14turnos,13propuestas/aclaraciones correctas,11/11bindings correctos. Owner46 ahora audio.mute(statefalse),0,016s; owner51 volumen100+mutefalse,0,437s+plan0,016s. RAM1778,219/GPU3497,559MiB;38,813s. Ningún efecto/UI/voz. RESULT/ADJ/PINS completos. Sólo falla la definición: publica prosa interna del selector.

Siguiente505: par privado sin edición de fuente, chat con/sin initial_reply. El borrador procede del selector, no del rol de conversación. Herencia tests/test_turn_policy.py418–481 conserva nombres y verifica guardas; comprobar esos controles antes de quitar la reutilización. llm.py6611 reutiliza el texto; __main__.py6492 lo transmite; llm.py7212 lo propaga. Mismo modelo/perfil/catalogo/payloads; cambia únicamente reutilización de borrador en la ruta chat. No barrido de sampler, no reserva y no efectos.

'''
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    (base / name).write_text(current + tail, encoding='utf-8')
status_path = base / 'ESTADO_PARA_DUENO_2026-09-08.md'
status = status_path.read_text(encoding='utf-8-sig')
start = status.index('El caso «perfecto')
end = status.index('## Recursos medidos')
status = status[:start] + '''La corrección503 ya pasó siete suites:3404 pruebas y121 subpruebas aprobadas, cero skips,52,86s. Fast y Release también pasaron, sin advertencias ni errores. La compuerta Full final sigue pendiente.

La prueba real504 comprobó además «perfecto, necesito lo dessilencies pls»: silencio desactivado, interpretación en0,016s. Quedó en13 propuestas/aclaraciones correctas de14 y11 planes o argumentos correctos de11. La definición todavía muestra prosa interna del selector; se está comprobando la reutilización de ese texto con controles de conversación y memoria. No se ha probado aún el audio físico ni la interfaz con estas correcciones.

''' + status[end:]
status = status.replace('Mente y planes actuales, 502 | 1,73 GiB', 'Mente y planes actuales, 504 | 1,74 GiB')
status_path.write_text(status, encoding='utf-8')
record = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
record.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint='504 cerrado:13/14 propuestas,11/11bindings; fuente503 validada; ningún proceso de prueba activo.', continuation='505 aislar reutilización del borrador nativo en conversación, sin editar fuente; C03 íntegro activo.')
write(base / 'RELEVO_ACTIVO.json', record)

panel = [
    {'id': 'definition-es', 'request': '¿Qué significa desmutear?', 'history': [], 'expected': []},
    {'id': 'definition-en', 'request': 'What does unmute mean?', 'history': [], 'expected': []},
    {'id': 'ram-new-topic', 'request': 'Explain what RAM is.', 'history': [{'role': 'user', 'content': 'My name is Jordan.'}, {'role': 'assistant', 'content': 'Hello Jordan.'}], 'expected': []},
    {'id': 'name-es', 'request': 'Me llamo Álvaro. ¿Cuál es mi nombre?', 'history': [], 'expected': []},
    {'id': 'name-en', 'request': 'My name is Jordan. What is my name?', 'history': [], 'expected': []},
    {'id': 'recall-es', 'request': '¿Cómo me llamo?', 'history': [{'role': 'user', 'content': 'Me llamo Álvaro.'}], 'expected': []},
    {'id': 'recall-en', 'request': 'What is my name?', 'history': [{'role': 'user', 'content': 'My name is Jordan.'}, {'role': 'assistant', 'content': 'Your name is Morgan.'}], 'expected': []},
]
campaign = base / 'astra-chat-draft505'
campaign.mkdir(exist_ok=False)
write(campaign / 'PREREG.json', {'utc': datetime.now(timezone.utc).isoformat(), 'source': '503', 'cases': panel,
    'method': 'Two fresh mind sidecars, identical panel/catalogue/model/profile. Private instrumentation logs initial_reply; treatment only drops that keyword before original LlmRuntime.chat. No source changes. Check actual posted conversation role and every memory control, not just visible word-meaning. Reject treatment if it only hides failure, hallucinates effects or regresses names. Development, not fresh human acceptance or model ranking.',
    'heritage': ['tests/test_turn_policy.py:418-481', 'biblioteca/gemma4-agent/documentacion/02_router/research/1_toolcalling.md:5,113-161', 'astra-audio-mind502 private HTTP20/21/22'],
    'primary_checked': ['https://qwen.readthedocs.io/en/stable/framework/function_call.html', 'https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507'],
    'mechanism': 'Official Qwen documents tool selection as a protocol with supplied function instructions. It does not establish that internal selector content is a final BAXY conversation. Local initial_reply skips the correct role payload; inspect that difference causally.'})
original = (root / 'scratchpad/c03-audio-mind504.py').read_text(encoding='utf-8-sig')
for mode in ['baseline', 'generation']:
    script = original.replace('504', '505-' + mode)
    start = script.index('cases=[')
    end = script.index('\nmanifest=', start)
    script = script[:start] + 'cases=' + repr(panel) + script[end:]
    script = script.replace("write(out/'PREREG.json',", "write(out/'PREREG.json',")
    # Replace inherited narrative; parameters/hashes and concrete cases stay captured.
    start = script.index("'method':")
    end = script.index("'profile_reason':", start)
    script = script[:start] + "'method':" + repr('505 ' + mode + ': identical seven consumed development conversations, fresh sidecar; private chat-boundary observer. See parent astra-chat-draft505/PREREG.json.') + ',' + script[end:]
    hook = '''\nfrom baxy_mind.llm import LlmRuntime as _DraftRuntime
_draft_original_chat = _DraftRuntime.chat
def _draft_observed_chat(self, *args, **kwargs):
    import json as _j
    from pathlib import Path as _P
    _draft = kwargs.get('initial_reply')
    with (_P(os.environ['LOCALAPPDATA']) / 'BAXY/C03-audio-mind505-MODE-private/chat-boundary.jsonl').open('a', encoding='utf-8') as _f:
        _f.write(_j.dumps({'request': args[0] if args else kwargs.get('text'), 'mode': 'MODE', 'initial_reply': _draft, 'kind': kwargs.get('conversation_kind')}, ensure_ascii=False) + '\\n')
    if 'MODE' == 'generation':
        kwargs.pop('initial_reply', None)
    return _draft_original_chat(self, *args, **kwargs)
_DraftRuntime.chat = _draft_observed_chat
'''.replace('MODE', mode)
    marker = "(hook/'sitecustomize.py').write_text(hook_source,encoding='utf-8')"
    assert marker in script
    script = script.replace(marker, 'hook_source += ' + repr(hook) + '\n' + marker)
    (root / ('scratchpad/c03-chat-draft505-' + mode + '.py')).write_text(script, encoding='utf-8')
write(campaign / 'PINS.json', {p.name: sha(p) for p in campaign.iterdir() if p.is_file() and p.name != 'PINS.json'})
print('504 adjudicated13/14 and11/11;505 two fresh-process scripts prepared, no source mutation.')
