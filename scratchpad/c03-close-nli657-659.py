"""Seal bilingual NLI rejection with independently verified backend parity."""
from pathlib import Path
import statistics

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")],__file__,'exec'))
out = base / 'astra-nli-fact-probe658'
private = home / 'C03-nli-fact-probe658-private'
assert not (out / 'RESULT.json').exists()
panel = read(private / 'panel.json')
stats = {}
adjudication = []
for threads in [2,4]:
    results = rows(private / f'results-{threads}.jsonl')
    assert len(results) == len(panel) == 31
    selected = []
    for case, actual in zip(panel,results):
        assert case['case_id'] == actual['case_id']
        expected_accept = case['expected_label'] == 'supported'
        actual_accept = actual['label'] == 'supported'
        selected.append({**case,**actual,'threads':threads,'exact_correct':case['expected_label'] == actual['label'],
                         'binary_correct':expected_accept == actual_accept,
                         'false_accept':actual_accept and not expected_accept,
                         'false_reject':expected_accept and not actual_accept})
    stats[str(threads)] = {k:sum(r[k] for r in selected) for k in ['exact_correct','binary_correct','false_accept','false_reject']}
    stats[str(threads)].update(total=31,median_inference_seconds=statistics.median(r['inference_seconds'] for r in selected),
                              median_pair_seconds=statistics.median(r['pair_total_seconds'] for r in selected),
                              max_tokens=max(r['tokens'] for r in selected),
                              false_accept_cases=[r['case_id'] for r in selected if r['false_accept']],
                              false_reject_cases=[r['case_id'] for r in selected if r['false_reject']])
    assert stats[str(threads)]['binary_correct'] == 21
    assert stats[str(threads)]['false_accept'] == 1 and stats[str(threads)]['false_reject'] == 9
    adjudication += selected
assert [r['label'] for r in adjudication[:31]] == [r['label'] for r in adjudication[31:]]
write(private / 'adjudication.json',adjudication)
report = ['# NLI658 — no adoptado']
for r in adjudication:
    report += ['## '+r['case_id']+f' / CPU {r["threads"]}',r['premise'],r['reply'],
               f'Expected {r["expected_label"]}; actual {r["label"]}; binary correct {r["binary_correct"]}.',
               json.dumps(r['probabilities'],ensure_ascii=False)]
(private / 'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8',newline='\n')
note = '''# 658 — NLI multilingüe pequeño no cualifica para el contrato factual

El modelo oficial multilingual-MiniLMv2-L6-mnli-xnli, revisión0a71e92a, recibe pares premisa/hipótesis nativos en CPU FP32. Misma población31 de656; los hechos pasan a premisas naturales bilingües con límites explícitos. Cambian modelo y representación: no es una comparación causal de un único factor.

Perfiles2/4 hilos producen las mismas etiquetas:21/31 decisiones binarias, una falsa aceptación y nueve falsos rechazos por perfil. Acepta que Brújula está instalada frente a instalado=false; rechaza descripciones verdaderas, abstenciones y una conversión correcta de RAM. Se conservan las probabilidades y los textos. No se cambia umbral ni se excluyen ejemplos para aprobar.

CPUExecutionProvider confirmado, máscara y pares nativos, sin cortes (todos≤512tokens). Picos RSS816,418MiB con2hilos y771,473MiB con4;4,344s/3,812s incluyendo proceso y carga. Sin infracciones. No son mínimos ni incrementos medidos en BAXY conjunto. El backend se contrasta con pesos originales en659 antes de atribuir el resultado al candidato. Modelo no incorporado al runtime; encuesta26/716/0.
'''
seal(out,private,{'adopted':False,'stats':stats,'thread_profiles_same_labels':True,
    'resources':read(out / 'RESOURCES.json'),'runtime_modified':False,'product_or_ui_or_voice_credit':False,
    'model_only_causal_comparison_to656':False},note,
    ['panel.json','results-2.jsonl','results-4.jsonl','backend-2.json','backend-4.json','worker-2.log','worker-4.log','adjudication.json','RESULT.md'])
out = base / 'astra-nli-native-parity659'
private = home / 'C03-nli-native-parity659-private'
assert not (out / 'RESULT.json').exists()
results = read(private / 'results.json')
assert len(results) == 31 and all(r['label_parity'] and r['tokens_equal'] for r in results)
maximum = max(r['max_probability_abs_difference'] for r in results)
assert maximum <= .001
resources = read(out / 'RESOURCES.json')
assert resources['exit_code'] == 0 and not resources['violations']
note = '''# 659 — ONNX y pesos nativos coinciden

Se descargaron los pesos safetensors originales de la misma revisión y se verificó su SHA. PyTorch2.13.0+cpu/Transformers5.14.1, FP32/eval/inference_mode, atención eager y2/1hilos reproducen las31 etiquetas ONNX. Token IDs y máscara del tokenizer nativo coinciden exactamente; diferencia máxima de probabilidad0,000001848, por debajo de0,001 predefinido. La mala clasificación de658 no se explica por esos caminos de backend ni por truncamiento.

Pico RSS1006,707MiB y21,781s de proceso nativo, sin infracciones. No se presenta como perfil óptimo ni consumo conjunto del producto. Esta comprobación valida la comparación, no la calidad: el candidato sigue sin cualificar para este contrato. No se cambia el modelo de BAXY ni se introduce un juez adicional. Fuente654 y encuesta26/716/0 intactas.
'''
seal(out,private,{'label_parity':31,'total':31,'native_tokenizer_parity':True,
    'max_probability_abs_difference':maximum,'tolerance':.001,'backend_equivalent_for_panel':True,
    'candidate_qualified':False,'runtime_modified':False,'resources':resources,
    'backend':read(private / 'backend.json')},note,['results.json','backend.json','worker.log'])
out = base / 'astra-nli-assets657'
(out / 'RESULT.md').write_text('# 657 — activos NLI oficiales verificados\n\nRevisión0a71e92a: ONNX FP32, tokenizer y configuración verificados por SHA/LFS o blob Git y guardados fuera del repositorio. La descarga no cambia el runtime. Evaluación en658 y paridad nativa en659; el candidato no se incorpora. Sólo URLs públicas salieron de la máquina.\n',encoding='utf-8',newline='\n')
write(out / 'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
# Keep the pre-close progress note chronological, not above the checkpoint title.
checkpoint = base / 'CHECKPOINT.md'
content = checkpoint.read_text(encoding='utf-8')
prefix = '# 657–659 — verificador NLI CPU, aún sin adopción\n'
if content.startswith(prefix):
    boundary = content.index('\n\n', content.index('\n\n')+2)+2
    progress = content[:boundary]
    content = content[boundary:]+'\n\n## Nota de progreso657–659 conservada\n\n'+progress
    checkpoint.write_text(content,encoding='utf-8',newline='\n')
with checkpoint.open('a',encoding='utf-8',newline='\n') as f:
    f.write('\n\n## Estado al terminar659\n\n657/658/659 terminados y sellados, sesiones77561/51876 recogidas;658 terminal directo exit0. Ningún proceso activo. NLI pequeño21/31binarias con9rechazos falsos; paridad nativa31/31. No incorporado. Fuente654 publicada, encuesta26/716/0. Publicar evidencia657–659; siguiente: reparar límites factuales en el contrato existente y aislar fuga de metadatos en prosa655. No tercera colección de clasificadores ni barrido de seeds sobre estos errores.\n')
state_path = base / 'RELEVO_ACTIVO.json'
state = read(state_path)
state.update(checkpoint='654 publicada.656 juezQwen no cualifica;658 NLI21/31binarias,659 paridad nativa31/31. Encuesta26/716/0.',
             continuation='Publicar657–659; reparar límites factuales del contrato existente y aislar metadato foreground en prosa655. No procesos activos ni decisión pendiente.',activeValidation=None,
             publishedEvidenceCommit='1654c492552b53c5c6edb706f5c24b63dd3bf6c9')
write(state_path,state)
with (base / 'HANDOFF.md').open('a',encoding='utf-8',newline='\n') as f:
    f.write('\n\n## Actualización659 — vigente sobre la estrategia anterior\n\n656 está publicado en1654c492552b53c5c6edb706f5c24b63dd3bf6c9.657–659 terminados,sellados,sin procesos activos. MiniLM NLI revisión0a71e92a,activos D:/BAXYRuntime/experiments/models/minilm-nli-0a71e92a.658 CPU2/4hilos ambos21/31binarias,1aceptación falsa/9rechazos falsos.659 pesosPyTorchFP32 y tokenizer nativo reproducen31/31etiquetas, diferencia máxima1,848e-6; no es un problema de esos backends. Nada promovido. No repetir estos jueces con seeds o probar colección de modelos. Próximo: contrato factual existente y aislamiento de fuga del metadato foreground en el primer borrador655/t24. Heredar648–653 y payload real; no vetar sólo la palabra ni fabricar prosa fija. Encuesta26/716/0, fuente654 intacta. Scripts657/658/659 y close-nli657-659 YAejecutados,no repetir. Auditar y publicar este tramo antes de nueva fuente.\n')
print({'nli_stats':stats,'native_label_parity':31,'runtime_modified':False})
