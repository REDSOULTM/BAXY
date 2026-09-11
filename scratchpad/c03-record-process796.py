"""Record the completed baseline and the current blocking repairs, without coverage credit."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-process-batch795-private'
rows = json.loads((PRIVATE / 'review.json').read_text(encoding='utf-8'))
passed = {'H0169', 'H0669', 'process795-memory_rank-01', 'process795-memory_rank-06'}
causes = {
    'list': 'Missing fresh read, or bounded list narrated without its observed count and scope.',
    'count': 'Missing fresh read, or ten returned rows confused with the observed count (205 in fresh count turns).',
    'memory_rank': 'Missing fresh read, duplicated names without preserved PID identity, or rank order changed.',
    'cpu_rank': 'Missing fresh read, composition failure, or lifetime CPU time represented as current usage.',
    'app_memory': 'No fresh app membership/aggregation observation; one process cannot establish the app total.',
    'unspecified_rank': 'No fresh read and no declared metric or clarification.',
}
adjudication = []
for row in rows:
    good = row['case_id'] in passed
    adjudication.append({'case_id': row['case_id'], 'turn_id': row['turn_id'], 'group': row['group'],
        'pass': good, 'reason': 'Fresh, explicit memory metric and faithful top ranks; no extra numeric/PID detail required for distinct names.' if good
        else causes[row['group']], 'final_sha256': hashlib.sha256(row['terminal']['final'].encode()).hexdigest()})
result = {'utc': datetime.now(timezone.utc).isoformat(), 'cases': 50, 'passed': 4, 'failed': 46,
          'groups': {g: dict(Counter('pass' if r['pass'] else 'fail' for r in adjudication if r['group'] == g))
                     for g in sorted(causes)}, 'adjudication': adjudication,
          'scope': 'Registered product conductor, no UI/voice/reserve acceptance or survey credit.',
          'criteria': 'PROCESS_CATEGORY795_PLAN.json frozen before execution. PID identity required where same-name instances recur; values not mandatory unless requested.',
          'private_transcript': str(PRIVATE / 'RESPUESTAS.md')}
(BASE / 'PROCESS_BATCH795/ADJUDICATION.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
resources = json.loads((BASE / 'PROCESS_BATCH795/RESOURCES.json').read_text())
report = f'''# Procesos795: baseline de producto

50 respuestas completas, 4 correctas y 46 fallidas según el criterio congelado; no acredita cobertura de encuesta. Las cuatro válidas son H0169, H0669, memory_rank-01 y memory_rank-06. Nombres distintos en un top no exigen añadir PIDs ni cifras que el usuario no pidió. Para instancias homónimas se conserva el criterio congelado de identidad.

Los fallos se concentran en lectura fresca, conteo/alcance, identidad y CPU actual. El modelo registrado sigue siendo Qwen; esta prueba no reabre su elección ni representa modelo nativo. El bruto, las transformaciones, los hechos y los finales están en el informe privado RESPUESTAS.md; ADJUDICATION.json registra cada turno sin publicar sus datos del PC.

Recursos del árbol conductor: {resources.get('gpu_peak_mib')} MiB VRAM, {resources.get('ram_peak_mib')} MiB RAM; {resources.get('seconds')} s; violaciones: {resources.get('violations')}. No incluye certificación de UI o voz.

Reparación796 en curso: lectura CPU por intervalo con identidad estable y normalización por procesadores lógicos de la máquina; proyección de conteo separado de filas; conservación de PID en la operación de inventario; reconocimiento de preguntas y límites hablados. Sin promoción ni nueva cobertura hasta validar y repetir la categoría.

Herencia: WindowsSystemStatusProvider usa muestreo150ms y WindowsSystemStatusProbe obtiene GetActiveProcessorCount de todos los grupos. La biblioteca ya consultada no aportó otra implementación vigente. Referencias primarias revisadas2026-09-10: [Process.TotalProcessorTime](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.totalprocessortime?view=net-10.0) documenta tiempo CPU acumulado; [Environment.ProcessorCount](https://learn.microsoft.com/en-us/dotnet/api/system.environment.processorcount?view=net-10.0) puede reflejar afinidad/cuota del proceso y no sirve como denominador físico global. Se reutiliza la sonda Windows existente.
'''
(BASE / 'PROCESS_BATCH795/REPORT.md').write_text(report, encoding='utf-8')
checkpoint = '795 completa50/50,4correctas/46fallos;48385terminal0 recogida, fuentes793 intactas durante corrida.796 candidato CPU intervalar/conteo/PID/routing en reparación, no adoptado. Provider6pass0skip; integración33pass0skip. DueñasPython activas80153. Modelo Qwen elegido; sin más comparaciones.28/714/0.'
path = BASE / 'CHECKPOINT.md'
path.write_text(checkpoint + '\n\n' + path.read_text(encoding='utf-8-sig'), encoding='utf-8')
path = BASE / 'RELEVO_ACTIVO.json'
state = json.loads(path.read_text(encoding='utf-8-sig'))
state.update(checkpoint=checkpoint, workStatus='process796_repair', continuation='Finish shared process blockers, owners and Full (C# plus Python), then rerun frozen50 category through main conductor. Preserve main/WIP and no model comparisons.',
             activeValidation={'name': 'process796_python_owners', 'session': 80153},
             previousGoalTurnClassification='progress',
             previousGoalTurnClassificationReason='Collected all50 process turns and implemented shared provider/projection/routing repairs; testing in progress.')
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
path = BASE / 'HANDOFF.md'
history = path.read_text(encoding='utf-8-sig')
(BASE / 'HANDOFF_BEFORE796.md').write_text(history, encoding='utf-8')
path.write_text('''# Handoff C03 — reparación796

Goal activo en Goal-c03; main intacto5f572ee1, HEAD publicado65761a14. Qwen3-4B-Instruct2507Q4_K_M elegido por orden del dueño; no más comparaciones. BAXY manual cerrado. Encuesta742/rev1248 y WIP ajeno preservados;28cubiertos/714abiertos/0NA.

795 terminó50casos,4pass/46fail;48385terminal0 recogida. REPORT/ADJUDICATION en PROCESS_BATCH795. Literales y hechos privados en LOCALAPPDATA/BAXY/C03-process-batch795-private/RESPUESTAS.md y review.json. Fuente793 intacta durante795. Nuevas causas: selección/gate omite consultas de procesos; conteo toma10filas por205observados; sanitizadorKernel eliminaPID; CPU usa acumulado desdearranque. Dos agentesRO identificaron fronteras, root implementa.

796 CANDIDATO sin adoptar: cambios C# en provider/contracts/handler/visiblefacts y Python effect_intent/__main__/measurement_prose_projection/llm. Tests nuevos test_c03_process_inventory.py y ampliaciones ProcessListHandlerTests/WindowsProcessStatusProviderTests. Provider6pass/0skip; integración33pass/0skip. Primer compilado de tests falló por colecciónDictionary y se corrigió; Python primer fallo fue regla system.status inaplicable y schema del test incompleto, ya corregidos. DueñasPython80153activas; revisar resultado antes de más tests. No hay inferencia activa.

Pendiente inmediato: resolver fronteras restantes de routing (agente k2_parser737 RO) y límite de facts C# (k2_role_recipe737 RO); finalizar dueñas y Full obligatorio por C#+Python. Sellar candidato y repetir los mismos50casos como797 sinpromover modelo, con lectura real. Reusar runner795 adaptando sólopins/candidato y directoriosnuevos. Preservarbaseline795.

No dar crédito automático por tests ni terminales. Continúan bloqueantes app-memory (membresía/agrupación de app), prosa y alcance según nueva categoría. Cierre global requiere742generalizados, reserva100,UIreal,loopback/AEC,recursosconjuntos≤4GiB,matriz/continuidadC04–C09,Fullfinalverde. Publicar fuente adoptada con dueñas/Full y checkpoint; paths explícitos, main intacto.
''', encoding='utf-8')
print(json.dumps({'recorded': 50, 'passed': 4, 'resources': resources, 'coverage': '28/714/0'}))
