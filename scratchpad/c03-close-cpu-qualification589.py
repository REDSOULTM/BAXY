"""Seal CPU adapter qualification and actual-product limits; no promotion yet."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
commit = 'e2215905b7177dd4000ace66b15b9919e6063bf8'


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def rows(p):
    return [json.loads(s) for s in p.read_text(encoding='utf-8-sig').splitlines()]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


notes = {
    'scoped-lora586': '''# Nativo586 — adaptador sólo para prosa CPU

45EOS: doce entradasCPU por base greedy, base con muestreo oficialQwen2507 y ese mismo muestreo con LoRA piloto4; tres controles de confirmación/nombre mantienen la base con escala0 en los tres perfiles. CPU: base registrada7/12, base documentada8/12, adaptador12/12. La mejora no se atribuye sólo al sampler. Cuatro fixtures explícitamente sintéticos cambian pregunta, uso, conteos y modelo. Algunas cifras se redondean a enteros;25,5→25 cae exactamente en el límite de media unidad admitido por la precisión publicada, sin relajar la guarda. No afirmar preservación de todos los decimales.

Los tres controles fueraCPU dan el mismo texto byte por byte después de peticiones con adaptador. Dos nombres son correctos; la confirmación conserva el ambiguo I remember your name anterior a habilitar memoria. Se acredita aislamiento, no calidad resuelta de confirmación ni memoria. GET inicial muestra escala1 pese al flag; POST/GET verifica0 antes de inferencia y cada petición fija0/1. No nuevo entrenamiento ni promoción. Piloto4e28d7728, Qwen3605803b, b9980/38a9d28e.

GPU3693,563MiB/RAM1030,723MiB,20,296s. LoRA pesa11.806.848bytes y el backend informa11,25MiB de tensoresGPU: el aumento del pico no equivale sólo al peso del archivo. Convertir aFP16 ahorraría pocosMiB de pesos; no se inició esa conversión sin demostrar que compense. Sin UI/voz ni consumo conjunto.
''',
    'usage-product587': '''# Producto587 — guarda584 efectiva, gramática pendiente

Fuente584 publicadae2215905b7177dd4000ace66b15b9919e6063bf8.17finales sin cortes. La variante Tengo un uso pasa ahora por corrección y publica Tiene un uso del20% en CPU: ya no atribuye el uso al asistente, pero conserva sujeto omitido. H0350 sigue abierto hasta una formulación inequívoca en el candidato integrado. H0065 sigue fallando en gramática: Esto computadora está usando el28,125% de la CPU. No sumar crédito por la guarda ni por otros usos correctos. Topología, los demás usos y controles de nombre/identidad/hora-audio/red conservados.

GPU3497,559MiB/RAM2441,012MiB,44,641s. Sin UI/voz ni consumo conjunto final. Encuesta13/729/0 intacta; original742/rev1248 intacto. Sin cambio de manifiesto.
''',
    'scoped-lora-seeds588': '''# Nativo588 — otras semillas y misiones de CPU

38EOS: diecinueve casos por semillas17/42, con el mismo adaptador sóloCPU y muestreo documentado. Dieciséis casosCPU por semilla (los doce586 más cuatro capturas de modelo/conteo, incluidas misiones con lecturas ordenadas) conservan hechos y sujeto. Los tres controles fueraCPU mantienen escala0 y el texto base; no se da por resuelta su confirmación. Se verificaron porcentajes exactos o redondeados a la precisión mostrada, físicos/lógicos, modelos, español e inglés. La base no se repitió: está en586. No se escogió sólo seed0 favorable.

GPU3547,559MiB/RAM864,629MiB,18,500s. La variación del pico frente a586 es de una corrida/perfil de solicitudes distinto, no una reducción causal demostrada. No promoción, UI/voz ni cobertura nueva.
''',
    'scoped-lora-product589': '''# Producto589 — candidato CPU con adaptador:17 finales correctos

Fuente584 publicadae2215905b7177dd4000ace66b15b9919e6063bf8, más un override experimental del adaptador piloto4 en la prosa que sólo informaCPU. El hook no altera petición, hechos ni respuestas: selecciona escala1/muestreo documentado dentro del compose CPU y escala0 explícita en todas las otras peticiones. El estado global se verifica0 por GET/POST/GET antes de publicar readiness. La activación usa contexto por hilo y lo restaura al salir. No se ha incorporado ni registrado todavía este mecanismo en el producto.

17finales correctos/sin cortes: seis topologías, siete preguntas de uso y cuatro controles de nombre/identidad/hora-audio/red. Los usos reales incluyen22,875816993→22,9%,13,75%,13,29113924→13,3%,24,375%,35% y46,89655172→46,9%. Desaparecen tanto Estoy/Tengo como Esto computadora. Las doce llamadas de composiciónCPU reciben escala1 y los demás POST escala0; una pregunta inglesa de uso se contesta desde el contexto conversacional previo13,3%, sin fingir una lectura nueva. Las misiones de topología conservan sus lecturas completas. No hubo reintentos CPU de reparación del sujeto en esta corrida.

GPU3575,559MiB/RAM2589,078MiB,41,922s. Son3,49GiB de VRAM y2,53GiB de RAM en conductor sin ventana/voz; no consumo conjunto final. Manifiesto13b971b3 sin cambios. Es la primera verificación integrada de esta selección por rol, no una promoción ni un cierre deC03. H0065/H0350 quedan abiertos en el registro vigente hasta incorporación y verificación sin hook; evidencia candidata enlazada. Encuesta13 cubiertos/729 abiertos/0NA,742/rev1248 intacto. BAXY manual cerrado, ninguna decisión del dueño pendiente.
''',
}

for name, note in notes.items():
    private = local / ('C03-' + name + '-private')
    out = base / ('astra-' + name)
    result = {'adopted': False, 'registered_manifest_changed': False, 'source_commit': commit, 'survey_counts': {'covered': 13, 'open': 729, 'not_applicable': 0}}
    report = [note]
    adjudication = []
    if name in ('scoped-lora586', 'scoped-lora-seeds588'):
        responses = rows(private / 'responses.jsonl')
        cases = {c['case']: c for c in read(private / 'cases.json')}
        assert len(responses) == (45 if name.endswith('586') else 38)
        assert all(r['response']['choices'][0]['finish_reason'] == 'stop' for r in responses)
        failures = {'registered-base': {'582:10', '582:12', '582:20', '582:21', 'synthetic-0'}, 'documented-base': {'582:10', '582:20', '582:21', 'synthetic-0'}}
        for r in responses:
            c = cases[r['case']]
            verdict = 'wrong_machine_actor' if r['case'] in failures.get(r['profile'], set()) else 'correct_cpu_with_display_rounding' if c['cpu_scope'] else 'base_control_preserved_not_new_coverage'
            adjudication.append({'case': r['case'], 'profile': r['profile'], 'verdict': verdict, 'response': r})
            report += ['\n## ' + r['case'] + ' · ' + r['profile'], '\n```json', json.dumps(c['payload'], ensure_ascii=False, indent=2), '```', r['response']['choices'][0]['message']['content'], verdict]
        result.update(resources=read(out / 'RESOURCES.json'), native_responses=len(responses))
    else:
        panel = read(private / 'panel.json')
        finals = [r for r in rows(private / 'capture/events.jsonl') if r.get('type') == 'terminal']
        assert len(panel) == len(finals) == 17 and read(out / 'EXIT.json')['exitCode'] == 0
        for i, (c, final) in enumerate(zip(panel, finals)):
            verdict = 'grammar_failure' if name.endswith('587') and i == 6 else 'subject_omitted_requirement_open' if name.endswith('587') and i == 10 else 'correct'
            adjudication.append({**c, 'ordinal': i + 1, 'terminal': final, 'verdict': verdict})
            report += [f'\n## {i + 1} · {c["case_id"]}', c['text'], final['final'], verdict]
        posts = rows(private / 'http-posts.jsonl')
        report += ['\n## Captura nativa completa', '\n```json', json.dumps(posts, ensure_ascii=False, indent=2), '```']
        result.update(resources=read(out / 'resources.json'), finals=17, correct=17 if name.endswith('589') else 15)
        if name.endswith('589'):
            requests = [r for r in posts if r['stage'] == 'request']
            active = [r for r in requests if r['payload'].get('lora') == [{'id': 0, 'scale': 1.0}]]
            inactive = [r for r in requests if r['payload'].get('lora') == [{'id': 0, 'scale': 0.0}]]
            assert len(active) == 12 and len(active) + len(inactive) == len(requests)
            assert read(private / 'adapter-state.json')['verified'][0]['scale'] == 0
            result.update(active_cpu_posts=len(active), explicit_inactive_posts=len(inactive), no_cpu_actor_repairs=all(len(r['payload']['messages']) == 2 for r in active))
    write(private / 'adjudication.json', adjudication)
    (private / 'RESULT.md').write_text('\n\n'.join(report), encoding='utf-8', newline='\n')
    (out / 'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
    result.update(private_report_sha256=sha(private / 'RESULT.md'), adjudication_sha256=sha(private / 'adjudication.json'))
    write(out / 'RESULT.json', result)
    write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
    with (root / '.gitattributes').open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(f'/artifacts/comprobaciones/C03/astra-{name}/** -text\n')
    with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
        stream.write('\n\n' + note)

registry = local / 'C03-survey-requirements336-private/requirements.jsonl'
private = local / 'C03-scoped-lora-product589-private'
backup = private / 'requirements-before-adjudication.jsonl'
assert not backup.exists()
backup.write_bytes(registry.read_bytes())
requirements = rows(backup)
for case_id, ordinals in [('H0065', list(range(7, 11))), ('H0350', list(range(11, 14)))]:
    row = next(r for r in requirements if r['case_id'] == case_id)
    assert row['verification_status'] == 'open'
    row.update(verification_updated_at=datetime.now(timezone.utc).isoformat(), verification_reason='589 verifica variantes reales con adaptador experimental sóloCPU; sujeto/gramática/cifras correctos.586/588 generalizan valores, modelos y semillas. Pendiente incorporar y verificar el candidato sin hook y registrar el perfil; no se acredita todavía al runtime vigente.')
    row['verification_evidence'].append({'campaign': 'astra-scoped-lora-product589', 'source_commit': commit, 'experimental_adapter_override': True, 'private_adjudication': str(private / 'adjudication.json'), 'ordinals': ordinals, 'ui_or_voice_credit': False})
registry.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in requirements), encoding='utf-8', newline='\n')
summary = read(base / 'SURVEY_REQUIREMENTS336.json')
summary.update(requirements_sha256=sha(registry), updated_at=datetime.now(timezone.utc).isoformat())
write(base / 'SURVEY_REQUIREMENTS336.json', summary)
handoff = notes['scoped-lora-product589'] + '''
Siguiente: incorporar selecciónCPU cualificada en el ownerLLM y registro reproducible del adaptador, con base/modelo/hash y default0 verificado, selección explícita por petición que no afecte clasificación/conversación/progreso/otras métricas. Evitar copiar el hook con contexto por hilo si basta decidir en el constructor del payload de composición. MindRuntimeDiscovery.cs y scripts/baxy_runtime_config.py son los dos lectores del manifiesto; ambos cierran propiedades y deben admitir juntos el perfil opcional. PythonLLM no tiene soporteLoRA hoy. Si se tocaC#+Python, Full obligatorio al adoptar. Después validar sin hook, UI/voz y consumo conjunto antes de promoción definitiva.

Fuente584 publicadae2215905:2165pass+121subtests/0skip; CPU55+STT12pass/1skip ambiental; Fast verde19,81s/0warnings/errors. Árbol Python6ca99187a3a2f97e5ba3736c5b61e2bae9710f97ed44441f8a4819f7bbeadb7d/403, históricos intactos. No procesos de583–589 pendientes. Main5f572ee intacto. Resto de encuesta/ocho rutas, unidadesGPU/memoria/progreso/curiosidades, UI real, loopback íntegro/AEC separado, aceptación y Full final siguen abiertos; C08 humano sólo evidencia/reanudación. No nuevo entrenamiento.583 limitado9B y585roletool descartados para adopción por fallos medidos.
'''
(base / 'HANDOFF.md').write_text(handoff, encoding='utf-8', newline='\n')
state = read(base / 'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), publishedSourceCommit=commit, checkpoint='589:17 correct shared-product finals with experimental CPU-only pilot4;586/588 seeds and changed facts qualified. No adapter source or registration yet. Survey13/729/0.', continuation='Implement and validate reproducible scoped adapter, then actual product without hook and joint resources. C#/Python adoption requires Full. Remaining C03 criteria stay open.')
write(base / 'RELEVO_ACTIVO.json', state)
matrix = root / 'documentacion/sprints/Sprints comprobación/03_MATRIZ_DE_CRITERIOS.md'
content = matrix.read_text(encoding='utf-8')
old = 'Última fuente publicada1dc8b33dcd60cc1dcc99586d51ac108f7e127ba5 (581), comprobada582:17 finales,15 correctos; topología H0007 cubierta, dos fallos de uso CPU aún abiertos. Dueñas2156 pass+121 subtests/0 skips; Fast verde, Release1,76s sin advertencias/errores. Encuesta13/729/0. Main intacto5f572ee. Full final y aceptación C03 pendientes.'
new = 'Última fuente publicadae2215905b7177dd4000ace66b15b9919e6063bf8 (584);2165 pass+121 subtests/0 skips; Fast verde, Release19,81s sin advertencias/errores. Producto587 verifica la guarda pero conserva gramática/sujeto omitido. Candidato experimental589 da17 finales correctos con adaptador sóloCPU, todavía sin incorporar ni registrar. Encuesta13/729/0. Main intacto5f572ee. Full final y aceptación C03 pendientes.'
assert content.count(old) == 2
matrix.write_text(content.replace(old, new), encoding='utf-8', newline='\n')
print('586–589 sealed; candidate successful, not registered; survey13/729/0.')
