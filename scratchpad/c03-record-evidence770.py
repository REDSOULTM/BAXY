"""Record completed769 and controlled770, preserving literals privately."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import copy
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
sys.path.insert(0, str(ROOT / 'src'))
from baxy_mind.llm import _payload_fact_defect


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


now = datetime.now(timezone.utc).isoformat()
source = 'e6937520569170eaa03dfde335ac5f41fcb6cb33'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == source
assert not (BASE / 'STATUS_BATCH769/RESULT.json').exists()
out = BASE / 'STATUS_BATCH769'
run = PRIVATE / 'C03-status-batch769-private'
exit769 = read(out / 'EXIT.json')
assert exit769['exit_code'] == 0 and all(exit769[k] for k in ['manifest_unchanged', 'sources_unchanged',
    'source768_unchanged', 'source764_unchanged', 'runner_unchanged', 'app_dll_unchanged'])
result = copy.deepcopy(read(BASE / 'STATUS_BATCH767/RESULT.json'))
result.update(utc=now, source_commit=source, correct=52, not_accredited=21, substantive_failures=21,
    resources=read(out / 'RESOURCES.json'), interpretation_sensitive=3,
    method='All73 reviewed against own fresh observations and frozen criteria: root t1-7/t32-40; bounded read-only reviews t8-31 and t41-73. No terminal-only scoring.',
    interpretation_sensitivity='H0655 distinguishes usable/free/used/installed in the complete reply and passes consistently with765, unlike767 bare available claim. H0383/audio-status-en retain prior acceptance of measured default endpoint without unrequested name/percent-symbol requirements.',
    comparison_limit='Same panel and configuration, but live observations and wording differ. No causal quality/latency gain from score52 versus51. Both inventory failures remain; detailed matched-factor analysis in770.')
changes = {
    'H0023': (False, 'inventory_draft_rejected', 'First and retry preserve20 entries/25total but repeat unobserved recency. No final list. Trace57.468s; registered full run cannot alone attribute latency change.'),
    'H0103': (False, 'inventory_draft_rejected', 'First/retry omit identities and multiplicity from20/24; retry also adds unsupported hidden/partially visible claim. Truncated-word veto also appears. No final list.'),
    'windows-focus-mixed': (False, 'faithful_focus_draft_rejected', 'Observed focused ChatGPT is correctly named in ventanal/focus wording, repeatedly rejected as missing_fact. This previously diagnosed form remains unrepaired.'),
    'H0539': (False, 'memory_total_labelled_available', 'Usable16.5395GB is labelled16.5GB available; measured available1.956GB and installed17.1799GB.'),
    'H0508': (False, 'memory_total_labelled_available', 'Windows observation correct, but usable16.5395GB is labelled16.54GB available; available1.944GB, installed17.1799GB.'),
    'H0655': (True, 'verified_answer', 'Complete reply distinguishes usable16.5395, free1.941, used14.5985 and installed17.1799GB. Meaning differs from767; no causal improvement credited.'),
    'cpu-usage-en': (True, 'verified_answer', '21.25% matches this turn\'s usagePercent. Different from7670.662% draft scaled to66.2%; no causal repair credited.'),
    'H0650': (True, 'verified_answer', 'Fresh RAM ranking is descending: ChatGPT1.17GB, python874MB, llama769MB, msedge465MB, ChatGPT377MB; distinct observed processes retained.'),
    'H0675': (False, 'no_fresh_read', 'ChatGPT1.17GB asserted without a fresh system.process.list observation.'),
}
for verdict in result['verdicts']:
    if verdict['case_id'] in changes:
        verdict['correct'], verdict['category'], verdict['reason'] = changes[verdict['case_id']]
    if verdict['case_id'] in {'H0104', 'windows-focus-reference-es'}:
        verdict['reason'] = 'Fresh foreground observation supports named ChatGPT window and any stated maximized state.'
assert sum(v['correct'] for v in result['verdicts']) == 52
result['failure_categories'] = dict(Counter(v['category'] for v in result['verdicts'] if not v['correct']))
result['evidence_sha256'] = {name:sha(run/name) for name in result['evidence_sha256']}
assert not result['resources']['violations']
write(out / 'RESULT.json', result)
write(run / 'adjudication.json', result)
review = read(run / 'review.json')
md = ['# Adjudicación769', '52 acreditadas/21fallos. Payloads y borradores completos en review.json; sin crédito automático de cobertura.']
for row,verdict in zip(review, result['verdicts']):
    assert row['case_id'] == verdict['case_id']
    md += [f"## {row['turn_id']} · {row['case_id']}", '**Entrada:** '+row['text'],
        '**Respuesta:** '+row['terminal']['final'], '**Criterio:** '+row['criterion'],
        '**Adjudicación:** '+('PASS. ' if verdict['correct'] else 'FAIL. ')+verdict['reason']]
(run/'ADJUDICACION.md').write_bytes(('\n\n'.join(md)+'\n').encode('utf-8'))

registry = PRIVATE/'C03-survey-requirements336-private/requirements.jsonl'
before_sha = sha(registry)
assert before_sha == 'dd88ee5458ef8cb0637993ba33429ae42fc4bc67974b656ce0e046eadacc40f4'
backup = run/'requirements-before769.jsonl'
assert not backup.exists()
backup.write_bytes(registry.read_bytes())
before = [json.loads(line) for line in backup.open(encoding='utf-8-sig')]
after = copy.deepcopy(before)
verdicts = {v['case_id']:v for v in result['verdicts'] if v['case_id'].startswith('H')}
assert len(verdicts) == 50
for row in after:
    verdict = verdicts.get(row['case_id'])
    if verdict is None:
        continue
    row.setdefault('verification_evidence', []).append({'campaign':'STATUS_BATCH769',
        'source_commit':source,'case_id':row['case_id'],'turn_id':verdict['turn_id'],
        'literal_diagnostic_correct':verdict['correct'],'category':verdict['category'],
        'private_adjudication':str(run/'adjudication.json'),'registered_runtime':True,'no_hooks':True,
        'coverage_credit':False,'ui_or_voice_credit':False,
        'development_variants_in_same_family':[v['case_id'] for v in result['verdicts']
            if v['group']==verdict['group'] and not v['case_id'].startswith('H')]})
    row['verification_reason']='769: literal '+('acreditado' if verdict['correct'] else 'sin acreditar')+'; '+verdict['category']+'. Generalización completa pendiente, sin crédito de UI/voz/consumo conjunto.'
    row['verification_updated_at']=now
allowed={'verification_evidence','verification_reason','verification_updated_at'}
assert len(after)==742 and Counter(r['verification_status'] for r in after)=={'open':716,'covered':26}
assert all({k:v for k,v in a.items() if k not in allowed}=={k:v for k,v in b.items() if k not in allowed} for a,b in zip(before,after))
assert sum(a!=b for a,b in zip(before,after))==50
registry.write_bytes((''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in after)).encode('utf-8'))
write(out/'REGISTRY_UPDATE.json',{'utc':now,'before_sha256':before_sha,'after_sha256':sha(registry),
    'snapshot_private':str(backup),'changed_rows':50,'fields_changed':sorted(allowed),'coverage_added':0,
    'counts':result['survey'],'authorship_expectations_literals_source_references_and_statuses_unchanged':True})
(out/'REPORT.md').write_bytes('''# Tanda769: la corrección todavía no entrega inventarios

73casos completos:52respuestas acreditadas y21fallos, todas las guardas intactas. Pico3499,56MiB VRAM y2510,80MiB RAM residente sumada;344,859s, sin violaciones. El52frente al51de767 no acredita una mejora: H0655 y CPUEN pasan con otros valores/redacción y el foco mixto vuelve a usar una forma fiel que BAXY rechaza. No hay crédito de UI/voz ni del consumo conjunto final.

Los dos inventarios siguen fallando. H0023 conserva las20identidades pero repite recencia no observada, incluso con la causa estructurada; H0103 omite identidades/multiplicidad y añade otra afirmación no observada. Ambos consumen unos57s de traza con recuperación. No se atribuye todo el aumento a768 sin control de las entradas;770 congela una observación y compara dos factores de corrección.

Se revisaron todas las respuestas contra sus hechos frescos y rúbricas originales.50filas reciben referencias de evidencia sin cambiar estados, procedencia o expectativas:26cubiertos/716abiertos/0NA. Literales, hechos y adjudicación permanecen privados en C03-status-batch769-private. C03 sigue activo.
'''.encode('utf-8'))

out770=BASE/'CORRECTION_ISOLATION770';private770=PRIVATE/'C03-correction-isolation770-private'
raw=read(out770/'RESULT.json');planned=read(private770/'planned.json');rows=read(private770/'results.json')
facts=read(private770/'reconstructed.json')
assert raw['calls_completed']==raw['calls_planned']==len(rows)==4
assert raw['sources_unchanged'] and raw['driver_unchanged'] and not raw['violations']
expected=Counter(w['title'] or w['processName'] for w in facts['captured_payload']['seen']['windows'])
verdicts770=[];md=['# Diagnóstico770 — cuatro respuestas completas', '**Petición:** '+facts['user_text'],
    'Hechos completos: reconstructed.json. Un solo inventario, sin crédito de producto/reserva/encuesta.']
for row in rows:
    response=row['response']['choices'][0];text=response['message']['content']
    entries=[line.strip()[2:].strip() for line in text.splitlines() if line.strip().startswith('- ')]
    # Explicit manual-review localization equivalence, never product logic.
    actual=Counter('explorer' if e=='Explorador de archivos' else 'Correo - Explorador de archivos'
        if e=='Explorador de archivos (Correo - Explorador de archivos)' else e for e in entries)
    defect=_payload_fact_defect(text,facts['captured_payload'],facts['user_text'])
    correct=row['arm'] in {'C_explicit_cause','D_no_draft_explicit_cause'}
    reasons={'A_current':'All20 identities but unobserved recency repeated; legitimate extra_claim rejection.',
        'B_no_rejected_draft':'19entries: one explorer instance omitted despite claiming20. Window validator accepts; manual completeness fails.',
        'C_explicit_cause':'All20 identities, correct20/25 partial scope, opening order explicitly unknown. False reversed_result: lista is absent from page-context vocabulary,20 treated as total25.',
        'D_no_draft_explicit_cause':'All20 identities, correct20/25 page, denies list completeness and unknown opening order. False extra_claim: negated includes-all statement treated as affirmative.'}
    if correct:
        assert actual==expected
    verdict={'arm':row['arm'],'semantic_correct':correct,'entries':len(entries),'missing':dict(expected-actual),
        'extra':dict(actual-expected),'validator_defect':defect,'reason':reasons[row['arm']],
        'seconds':row['seconds'],'finish_reason':response['finish_reason'],'usage':row['response']['usage'],
        'timings':row['response']['timings']}
    verdicts770.append(verdict)
    md += ['## '+row['arm'],'**Respuesta:** '+text,'**Adjudicación:** '+reasons[row['arm']]]
write(out770/'ADJUDICATION.json',{'utc':now,'semantically_correct':2,'semantically_failed':2,
    'verdicts':verdicts770,'inference_calls':4,'source_unchanged':True,
    'input_scope':'Reconstructed verified envelope with identical projected payload, not raw full input replay; audit is truncated.',
    'limits':'Single frozen observation/fixed order, no model ranking or total product retry-budget acceptance; source unchanged.',
    'next':'Repair page-subject and quantified-statement polarity in existing window fact checker; preserve rejection of actual global completeness/recency. Explicit-cause factor has two faithful outputs; do not adopt solely on synthetic tests.',
    'evidence_sha256':{name:sha(private770/name) for name in ['results.json','planned.json','reconstructed.json','server.log']}})
(private770/'ADJUDICACION.md').write_bytes(('\n\n'.join(md)+'\n').encode('utf-8'))
(out770/'REPORT.md').write_bytes('''# Separar respuesta del modelo y rechazo de BAXY

Cuatro llamadas con la misma observación20/25, modelo, backend y sampler comparan dos factores: mantener o quitar el borrador rechazado, y añadir o no una explicación explícita de la ausencia de tiempos de apertura. Las otras entradas permanecen iguales. Se reconstruye el envoltorio verificado con payload proyectado idéntico; audit.situation está truncado y no se presenta como input bruto idéntico.

| Variante | Contenido | Validador actual | Tiempo |
|---|---|---|---:|
| A: corrección768 |20entradas, recencia inventada |Rechazo correcto |4,219s|
| B: quitar borrador |19entradas, falta una instancia |Aceptación incorrecta |3,859s|
| D: quitar borrador y explicar causa |20entradas fieles, página20/25 |Rechazo incorrecto |4,391s|
| C: conservar borrador y explicar causa |20entradas fieles, página20/25 |Rechazo incorrecto |4,375s|

C falla porque «esta lista incluye20ventanas» se interpreta como total25: el vocabulario de página no reconoce lista/list. D falla porque «la lista no incluye todaslasventanas» se interpreta como afirmar exhaustividad. En ambos, decir que el orden de apertura no se conoce es correcto y el guard de cronología no es el disparador. B demuestra además que la presencia de cada nombre no prueba la multiplicidad de las entradas: la adjudicación manual lo rechaza aunque el verificador lo admita.

La explicación explícita produce dos respuestas fieles en esta observación. No prueba estabilidad, generalización ni que los reintentos quepan en el presupuesto total. Prefill/generación y tokens están en ADJUDICATION; todos reportan cache_n0. Pico de servidor3497,56MiB VRAM/718,58MiB RSS;20,469s incluyendo arranque, sin violaciones. Cuatro llamadas terminaron stop, fuentes y driver intactos; no hay crédito de UI/voz/encuesta/reserva ni promoción de modelo.

La siguiente reparación queda localizada en la vinculación de cantidades al sujeto lista/página y la polaridad de la afirmación exhaustiva, conservando los controles negativos. El cambio de instrucciones sólo podrá adoptarse junto con evidencia real de entrega, sin convertir un verificador verde en verdad por definición. C03 activo.
'''.encode('utf-8'))
note=('769 y770 terminados/adjudicados,63153 y9883 recogidos, no proceso activo.769=52/73,21fallos;3499,56MiB/2510,80MiB/344,859s. '
    '770factorial: A20recencia falsa; B19omite1explorer aunquevalidador acepta; C/D20fieles vetados. C:lista no cuenta como página,20tratado25; D:negación de exhaustividad leída positiva. '
    'Causa explícita corrige contenido en2respuestas, sinproductopass. Siguiente reparar subject/polarity del verificador y medir entrega; no nueva fuente771 aún. '
    'RegistroSHA='+sha(registry)+';26/716/0.\n\n')
cp=BASE/'CHECKPOINT.md';pending=cp.with_suffix('.pending.md');pending.write_bytes(note.encode()+cp.read_bytes());pending.replace(cp)
r=read(BASE/'RELEVO_ACTIVO.json');r.update(checkpoint=note.strip(),confirmedAtUtc=now,activeValidation=None,
    workStatus='status769_and_factorial770_adjudicated_validator_repair_pending',
    continuation='Repair inventory count subject and negative all-windows claim; keep actual false claims rejected. Explicit cause improved two matched outputs770, but real registered delivery remains pending.')
write(BASE/'RELEVO_ACTIVO.json',r)
(BASE/'HANDOFF.md').write_bytes(('''# Handoff C03 —769/770 —2026-09-10

Goal activo en Goal-c03, main intacto5f572ee1. Fuente768 publicadae6937520569170eaa03dfde335ac5f41fcb6cb33;7fuentes/18evidencias verificadas HEAD=origin=remoto. Encuesta742/rev1248:26cubiertos/716abiertos/0NA, SHAregistro '''+sha(registry)+'''. Sin pregunta pendiente. BAXY manual cerrado.63153 y9883 terminal0/recogidos; no inferencia/gate activo. Preservar WIP ajeno.

769:52/73,21fallos, todosguards true.3499,56MiBGPU/2510,80MiBRSS/344,859s. H0023 inventa recencia aun con768;H0103 omite identidades/multiplicidad. Foco ventanal vuelve a ser vetado fielmente. H0655/CPUEN pasan conotrosvalores/redacción, sinatribucióncausal.50referencias añadidas conservando estados. STATUS_BATCH769/RESULT/REPORT y privado review.json/ADJUDICACION.md.

770factorial4llamadas unaobservación20/25: A768 conserva20pero recencia falsa;B sinborrador conserva19(omiteexplorer) y verificadoracepta;C/D concausa explícita conservan20ypágina fieles pero verificadorrechaza. C=reversed_result porque _PAGE_CONTEXT noincluyelista/list,cuenta20seleede25total. D=extra_claim porque «La lista no incluye todaslasventanas» seleeafirmativa. Cronología no dispara C/D: desconocimiento correcto. Rutas window_prose_facts.py:381–382,484–514. Paresindependientes CvsA yDvsB aíslan explicación explícita. Sinmodelo/receta/promoción ni crédito producto.770ADJUDICATION conserva tiempos/tokens; todoscache_n0. Servidor3497,56MiB/718,58MiB,20,469s, fuentesintactas.

Siguiente: reparar cantidad ligada al sujeto lista/página y polaridad de exhaustividad en verificador existente; controles positivos/negativos ES/EN, totales conocidos/desconocidos, páginascompletas/parciales, nombres observados opacos. No relajar afirmaciones realmente falsas ni adoptar respuesta prefabricada. La explicación explícita de770produce2respuestasfieles, pero no está en producto: scratchpad/c03-correction-isolation770.py conserva el único texto/factor medido. No nueva fuente771 iniciada. Publicar769/770 evidencia antes de adoptar otra fuente.

768validación:775dueñas/0skip,1011window-integridad/1skipSTT,Fast0/Release22,36s. Programa407=ba7851452608e5e8fb1d6bb5601764fe0cfe02069379cd8369654a6f8936e3de, mismas3raíces; no tocar pins históricos ni wakev17. SóloPython, sin nuevoFull. READONLY agente además localizó H0209/H0663/EN: window_inventory_arguments effect_intent.py:5257–5312 excluye cabezaobservación+interrogativa,varianteortográfica,adverbiopresenteinterno;groundingreusaelmismollector (__main__.py:4243). Pruebas test_c03_window_inventory.py:22–96. Repara familias, no literales.

Full7histórico4574.NETpass/1skip+16omisiones;11399Pythonpass/3skips+466subtests. Faltan cobertura742,reserva,UI/loopback/AEC,recursosconjuntos≤4GiB,matriz/continuidad yFullfinal.699 probó50tareas×6perfiles sinBAXY;73757paresK2. No atribuir fallos de capas al modelo. C03 no terminado.
''').encode('utf-8'))
print(json.dumps({'status769':{'correct':52,'failed':21},'factorial770':{'correct':2,'failed':2},'registry_sha256':sha(registry)}))
