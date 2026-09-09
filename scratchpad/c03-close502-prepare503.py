"""Record integrated proposal/binding evidence and the next bounded defect."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-audio-mind502'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
def rows(path):
    return [json.loads(s) for s in path.open(encoding='utf-8-sig')]
replies = rows(out / 'replies.jsonl')
bindings = {r['id']: r for r in rows(out / 'bindings.jsonl')}
cases = {c['id']: c for c in json.loads((out / 'PREREG.json').read_text(encoding='utf-8-sig'))['cases']}
resources = json.loads((out / 'RESOURCES.json').read_text(encoding='utf-8-sig'))
assert len(replies) == 14 and len(bindings) == 10
adjudications = []
for row in replies:
    case = cases[row['id']]
    reply = row['reply']
    expected = case.get('expected', [])
    failure = row['id'] in {'owner46', 'word-meaning'}
    if not failure:
        assert reply.get('effectOperations') == expected
        assert not reply.get('failure_code')
    bound = bindings.get(row['id'])
    if bound:
        result = bound['reply']
        if bound['type'] == 'plan':
            assert result['kind'] == 'plan'
            assert [s['operation'] for s in result['steps']] == expected
            values = {key: value for step in result['steps'] for key, value in step['arguments'].items()}
        else:
            assert result['ok'] is True
            values = result['arguments']
        assert all(values.get(k) == v for k, v in case.get('arguments', {}).items())
    adjudications.append({'id': row['id'], 'request': case['request'],
                          'proposal_or_clarification_correct': not failure,
                          'binding_correct': True if bound else None,
                          'reply': reply, 'binding': bound['reply'] if bound else None,
                          'assessment': ('Runtime failure on dessilencies; misleading clarification' if row['id'] == 'owner46' else
                                         'Internal prose and unverified offer to control microphone' if row['id'] == 'word-meaning' else
                                         'Correct proposal/clarification, and exact arguments where requested; no effects executed')})
write(out / 'ADJUDICATION.json', adjudications)
write(out / 'RESULT.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'session': 48855, 'exit': 0,
    'correct_proposals_or_clarifications': 12, 'cases': 14, 'correct_bindings': 10,
    'binding_calls': 10, 'open_cases': ['owner46', 'word-meaning'], 'resources': resources,
    'owner51': {'turn_seconds': .484, 'plan_seconds_rounded': .000,
                'operations': ['audio.volume', 'audio.mute'], 'arguments': [{'level': 100}, {'state': False}]},
    'comparison': 'Owner51 failed in499 after6.188s;502 preserves antecedent, effects and arguments. Original resumed string also gives both correct arguments. No model/runtime/profile change.',
    'limits': 'Actual mind protocol and shell-shaped binding requests, not execution of C# UI, kernel/provider effects or voice. No fresh acceptance reserve.'
})
lines = ['# Audio contextual: protocolo real 502', '',
         'Fuente 501 con runtime registrado. Doce de catorce propuestas/aclaraciones correctas; diez de diez solicitudes de argumentos o plan correctas. Los casos siguen siendo desarrollo, no aceptación fresca.', '',
         '«Al 100, pero desmutealo», con el pedido anterior auténtico, produce audio.volume(level=100) y audio.mute(state=false), en ese orden. Turno: 0,484 s; plan por debajo de la resolución de 1 ms del registro. En 499 tardaba 6,188 s y terminaba en error. La cadena explícita de reanudación también produce ambos argumentos correctos. No se ejecutó audio.', '',
         '| Entrada | Salida literal del turno | Plan o argumentos | Evaluación |', '|---|---|---|---|']
for a in adjudications:
    reply = a['reply']
    visible = reply.get('question') or reply.get('reply') or json.dumps(reply['effectOperations'], ensure_ascii=False)
    binding = a['binding']
    literal_binding = json.dumps(binding.get('steps', binding.get('arguments')), ensure_ascii=False) if binding else 'No solicitado'
    lines.append('| ' + ' | '.join(str(x).replace('|', '/').replace('\n', ' / ') for x in
                                  [a['request'], visible, literal_binding, a['assessment']]) + ' |')
lines += ['', f"RAM {resources['ram_peak_mib']:.3f} MiB; VRAM {resources['gpu_peak_mib']:.3f} MiB; tiempo total {resources['seconds']} s. Son la mente, sus recursos semánticos y el conductor, no todo BAXY con UI/voz. Manifiesto intacto.", '',
          'Pendientes: owner46 con dessilencies y la definición con prosa interna/oferta de micrófono no acreditada. El shell y el audio físico siguen pendientes de demostración.', '']
(out / 'RESULT.md').write_text('\n'.join(lines), encoding='utf-8')
for name in ['CHECKPOINT.md', 'HANDOFF.md', 'ESTADO_PARA_DUENO_2026-09-08.md']:
    shutil.copy2(base / name, out / (Path(name).stem + '-before.md'))
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
new = base / 'astra-unmute-request503'
private = local / 'C03-unmute-request503-private'
new.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
for relative in ['src/baxy_mind/effect_intent.py', 'src/baxy_mind/__main__.py', 'tests/test_effect_intent.py', 'tests/test_turn_policy.py']:
    shutil.copy2(root / relative, private / (Path(relative).stem + '-before.py'))
write(new / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'cause': 'Pure inspection: owner46 retains perfecto as the request head even if dessilencies is replaced by desmutealo. Bare desilencia/dessilencia are also absent from the shared unmute family. Correcting only the spelling cannot fix the actual request.',
    'hypothesis': 'Recognize the unmute verb family and preserve an explicit request through an acknowledgement and a need/desire frame. Frames are transparent only when an actual catalog-effect head follows; retain quoted content, negation, conditionals and non-global audio scope.',
    'validation': 'Preregister new focal baseline before source edits, with grammar layers separated and cross-domain controls. Whole-mind actual literal and argument state=false must follow any source repair; no claim from unit selection alone.',
    'heritage': '485 and500 shared morphology,498 quoted clause boundaries; native490 fails owner46 at the documented Qwen profile while497 original Gemma understands it in typed isolated calls. Current actual request-reader loss is independently reproducible. No new prompt or sampler sweep.',
    'limits': 'No changes yet. No reserve, provider effects or model promotion.'
})
state = '''# C03: fuente 501 validada, protocolo 502 cerrado, 503 preregistrado

Goal íntegro activo. Goal-c03 / HEAD 2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. Autoridad C03_ASTRA_AUTORIDAD.md, identidad y AGENTS.md. Conservar WIP/main/evidencia. Sin agentes, commits, publicación ni Full durante reparación. BAXY manual cerrado. Encuesta completa:742 respuestas/rev1248; preservar PID101140 y29800.

No hay runtime, build ni prueba activos. Últimas sesiones recogidas con exit0: owners98547, Fast51448 y mente502/48855. Buildservers cerrados. Fuente vigente effect_intent.py y __main__.py501; llm.py466. Registro SHA13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed intacto.

501: respuesta numérica sólo hereda un pedido anterior del usuario que prueba el contrato audio.volume/level incompleto. Conserva literalmente los dos pedidos y vuelve a aplicar todas las guardas. El plan comparte referente; binding prueba valor único y usa la misma familia unmute que la selección. 26 pruebas de lectura y11 de turno/argumentos. Siete suites:3377 pass y121 subtests pass, cero skips,48,89s. Fast verde; Release3,31s,0warnings/errors. Artefacto astra-context-level501 con PINS y SOURCE.patch; fallos intermedios preservados.

502:14 turnos de desarrollo y10 bindings usando el protocolo real;12 propuestas/aclaraciones correctas y10/10 bindings correctos. Owner51 «Al100,pero desmutealo» conserva audio.volume(level100) +audio.mute(statefalse),0,484s de turno yplan<1ms de resolución. Antes499 fallaba en6,188s. Resumed string también correcto. Owner49 pregunta el nivel; negación contextual, cambio a hora e inglés conservados. Fallan owner46 y definición con prosa interna/oferta de micrófono no acreditada. RAM1773,180/GPU3497,559MiB,45,297s: mente/conductor, no UI/voz ni efectos. RESULT/ADJ/PINS completos en astra-audio-mind502.

Siguiente:503, scratchpad y artifact astra-unmute-request503 ya PREREG, sin tests ni fuente nuevos aún. Diagnóstico puro: owner46 conserva perfecto como cabeza incluso sustituyendo dessilencies por desmutealo; desilencia/dessilencia tampoco figuran en familia. Revisar conjuntamente marco de asentimiento/petición y familia verbal; sólo transparentes ante una acción explícita. No eliminar negaciones, citas, condicionales ni objetos ajenos. Leer _strip_request_envelope4181, _request_head4250 y _UNMUTE_VERB; las líneas se desplazan. Hacer baseline antes de tocar fuente. No otro barrido de prompt/sampler.

Cambios previos conservados:485 clíticos;487 prohibiciones independientes;498 pero/but positivos y protección de citas (3174pass/Fast);500 ponle, delimitador compartido y nivel faltante con PC/computer (3188pass/Fast). 499 documenta fallo del texto reanudado antes de500/501. La interfaz C# intenta una decisión independiente antes de reanudar, pero502 ya responde correctamente al fragmento sin caer en RecoveryFailureCode; aún falta probar el shell real.

Modelos: Qwen2507Q4/b9980 registrado es candidato, no aceptación. Versiones y perfiles específicos documentados en INVESTIGACION_MODELO_C03. 489 recuperación de contexto sola no basta;490 sampler oficial tampoco.491/492 contratos/polaridad intercambian fallos.493 publicadoGemma repite;494 raw=parsed;495 HTTP400 antes de generar;496 quitar gramática elimina extras pero admite operación ajena y prosa de éxito.497 Gemma original evita extras en14nativas y3prompts idénticos, pero invierte silencio en3casos y viola interfaz sin argumentos en4; no promoción. RAM1030,965/GPU1681,988MiB sólo nativo. No reabrir variantes472–476,481Q8,4829B,484JSON ni barridos de gramática sin causa nueva.

Ahorros:425 producto RAM5,18→3,03→2,75GiB con cacheRAM0/no-mmapGPU.462 Gemma lazy-on conserva respuestas y reduce RAM del compositor.464 Gemma producto por conductor7/8útiles, RAM2653,13/GPU1694,18MiB; confirmación de activación pendiente.437 Qwen3.5 7/8,RAM2,75GiB/GPU3,10GiB, confusión de sujeto/nombre. Ninguna cifra demuestra todo BAXY sólo en VRAM ni un mínimo universal.

Reserva:204 potenciales/192 canónicos/12gruposduplicados;475 semántica,477 fuente/contexto,483 exposición.176/204 completos contrastados;7fuentes originales ausentes,6textos cortados a100caracteres.0certificados, no congelada, no ejecutada. Faltan contexto/entrenamiento/splits y refrescar exposiciones posteriores a483. Autoría ya confirmada; no preguntar otra vez. Sesión264 es desarrollo expuesto, no reserva. Privado TRANSCRIPT282 SHA9658a77505564ec1384e58aba91ed75d03b078f865182f94b6ecc3b0ee839ef6.

Cierre completo pendiente: ocho rutas/generalizar742; confirmaciones útiles y veraces; incidentes264/apps/París/Steam/YouTube/Spotify/capacidades/cierre;100humanosfrescos con procedencia/contexto, congelados y100/100 ES/EN/mezcla natural; averías/recuperación; UIreal/voz/audiofísico/ASR/wake;≤4GiBVRAMconjunta; runtime/instalación/continuidadC04–C09; Full final íntegramente verde y publicación fuera de main. No porcentaje/ETA ni cierre parcial.

Python-Xutf8; archivos utf-8-sig. exec_command se recoge con write_stdin. Privados %LOCALAPPDATA%/BAXY. No editar fuente durante pruebas/runtimes/builds. Estados anteriores preservados en astra-audio-mind502/*-before.md y498/*-before.md.
'''
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    (base / name).write_text(state, encoding='utf-8')
record = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
record.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
              checkpoint='501 validada;502 cerrado:12/14 propuestas,10/10 bindings; owner51 correcto. Sin runtime activo.',
              continuation='503 preregistrado:marco de petición y familia desilenciar. Baseline antes de editar. C03 íntegro activo.')
write(base / 'RELEVO_ACTIVO.json', record)
print('502 closed and pinned;503 preregistered. Current checkpoint rewritten.')
