"""Close the model investigation checkpoint without granting C03 acceptance."""
from pathlib import Path
from datetime import datetime, timezone
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base/'K2_HORIZON_LATENCY697'
summary = json.loads((out/'SUMMARY698.json').read_text(encoding='utf-8'))
p = base/'RELEVO_ACTIVO.json'
state = json.loads(p.read_text(encoding='utf-8-sig'))
note = ('Investigación K2 finalizada:19 corridas/860 resultados evaluables sobre50 entradas(49 fixtures), '
    'seis benchmarks fijos y backend Windows Unicode/NFC+parser697/698 corregido. '
    'Decisión autónoma: conservar Qwen; mejor K2 BF16 high33/50 vsQwen30/50,10ganancias/7regresiones, '
    'mediana1.3285s vs.649s y máximo37.797s vs2.235s. Q4low32/50;Q8low20/50;Q8medium32/50 con2errores parser. '
    'Autoparser121tests4539assertions yPEG39tests210assertions verdes,cero skips. '
    'Cola63450 final exit0; no inferencia activa. Informe REPORTE_FINAL.md generado. '
    'Runtime productivo intacto. Reanudar sólo bloqueantes compartidos693/694; C03 activo26/716/0, ninguna decisión pendiente del dueño.')
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint=note,
    continuation='Leer/adjudicar producto694 contra payload completo y cerrar/adoptar fuente693 sólo si cumple. No repetir K2 sin dato nuevo; elegir Qwen ya está resuelto.',
    activeValidation=None, activeReadOnlyAgent=None, pendingOwnerClarification=None,
    workStatus='resume_shared_blockers_after_completed_k2_investigation',
    ownerPriority='K2 comparison and latency investigation completed; resume only C03 blockers with registered Qwen.',
    k2Report='artifacts/comprobaciones/C03/K2_HORIZON_LATENCY697/REPORTE_FINAL.md')
k2 = state['k2Comparison']
k2.update(panelTag=None, investigationCompleted=True,
    queuedControls={'sessionId':63450,'exitCode':0,'status':'completed_and_manually_adjudicated'},
    backendReceipt='artifacts/comprobaciones/C03/K2_HORIZON_LATENCY697/BACKEND_BUILD698.json',
    decision='retain_registered_qwen_runtime', promotion=False, ownerDecisionPending=False)
k2['completedNativePanels'] = {tag: {
    'pass':r['adjudication']['pass'], 'fail':r['adjudication']['fail'],
    'selector_pass':r['adjudication']['selector_pass'],
    'prose_and_conversation_pass':r['adjudication']['prose_and_conversation_pass'],
    'cases':r['measurements']['responses'],
    'gpu_mib':r['measurements']['resources']['gpu_peak_mib'],
    'ram_mib':r['measurements']['resources']['ram_peak_mib'],
    'median_seconds':r['measurements']['seconds']['median'],
    'max_seconds':r['measurements']['seconds']['max']
} for tag,r in summary['records'].items()}
p.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with (base/'CHECKPOINT.md').open('a',encoding='utf-8') as f:
    f.write('\n\n## Cierre investigación K2 698 — '+state['confirmedAtUtc']+'\n\n'+note+'\n')
handoff = '''# Handoff — C03 — investigación K2 cerrada, goal activo

## Objetivo y autoridad
Completar C03 de respuesta veraz. Objetivo vigente: adjunto goal-objective.md SHA621020a31266e98d043b07f214e8a8c6c3cb48f1287d27e411bf805402dadb86, ruta en RELEVO_ACTIVO.json. Rama Goal-c03; main intacto. Encuesta742/rev1248:26 cubiertos/716 abiertos/0NA. Ninguna decisión pendiente del dueño.

## Estado
Hecho: comparación K2 y diagnóstico de lentitud, reporte en K2_HORIZON_LATENCY697/REPORTE_FINAL.md.19corridas,860resultados evaluables del panel50(49fixtures). Seis benchmarks fijos. No inferencia, compilación ni agentes activos; cola63450 exit0.

Decisión: conservar runtime Qwen registrado. Mejor K2 BF16 high33/50 frente30/50;10ganancias/7regresiones con un fixture duplicado. Mediana1.33s/máx37.80s frente.65s/2.24s. K2 Q4low32/50 yQ8low20/50. Q8medium32/50 conserva2errores de parsing y acción de conexión no solicitada. No reabrir otra cuadrícula K2 sin hipótesis/dato nuevo.

## Evidencia y cambios
- K2_HORIZON_LATENCY697/SUMMARY698.json, MODEL_DECISION698.json: todas las adjudicaciones, recursos y límites. Textos completos privados; evidencia pública de IDs/causas/hashes.
- Fork externo D:/BAXYRuntime/build/llama-k2-horizon-35999d1: Windows Unicode/NFC, kwargs efectivos, delimitador de esfuerzo y transición implícita a herramientas. BACKEND_BUILD698.json fija parche y15EXE/DLL. No promoción a BAXY. Cierres de esfuerzo incompatibles permanecen internos, como en parser oficial.
- Corrección698: reproducción previa36fallos. `test-chat-auto-parser.exe`→121tests/4539assertions; `test-chat-peg-parser.exe`→39/210;0fallos/excepciones/skips. BuildReleaseCUDA13/SM86 exit0. Tokenizer285/285antes de cada K2; prefijos50/50en cada control698.
- Bench697:Q8pequeño171–173t/s,BF16~112,Q4grande~72. GRAPH_OPT no mejora material. Picos sólo árbol del servidor/benchmark, NO conjuntoBAXY. Q8grande28capas excedió4096MiB y fue rechazado;24capas sólo20selectores, parada adaptativa documentada.

## Trabajo C03 pendiente, ya preparado
Fuente693 NO ADOPTADA: projection decimalRAM/disco/GPU, RAM instalada medida, wifi.status ReadOnly. Full693 exit0:11051Python pass/3skips/466subtests;4480NET pass/1skip agregado (opt-ins aparte). ÁrbolPython79701619cda32892fe5cadc14a5ea36efd05412250abe6de108b2da1fa014140/406ficheros. No extender ese Full al forkK2 ni llamarlo cierre deC03.

Producto694:73terminales,exit0,manifestintacto; revisión generada/leída, falta adjudicar contra payload completo y sellar/adoptar. Ver astra-status-batch694, scratchpad/c03-review-status-batch694.py y c03-read-native-status694.py. Native690/691 sellados; tablero692 sólo planificación. Prototype695 NO aplicar:50variantes dieron3falsas lecturas por propietario/drive/conocimiento.

Runtime productivo Qwen4B2507Q4_K_M/b9980, manifest13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed. Última fuente adoptada686 d7ddd926; evidencia689 HEADprevio8400bfd7. Publicación K2 investigativa separada; las modificaciones693 ySTT previas siguen sin adoptar. Ver git status antes de stagear.

## Siguiente acción
Adjudicar todos los resultados694 con scratchpad/c03-read-native-status694.py y causa compartida de frescura/alcance; adoptar693 sólo con evidencia completa. Después siguen las742exigencias,8rutas,cienrespuestas,avería/restauración,UI/voz/loopback/AEC yrecursos conjuntos/Full final que exige C03. Esta investigación no concede cobertura ni cierra el goal.
'''
(base/'HANDOFF.md').write_text(handoff,encoding='utf-8')
print(json.dumps({'panels':len(summary['records']),'goal':'active','coverage':state['surveyVerificationCounts']}))
