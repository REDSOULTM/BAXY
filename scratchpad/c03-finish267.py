"""Persist source evidence without interacting with the manual test session."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import psutil

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
out = base/'astra-compose-provenance267'
now = datetime.now(timezone.utc).isoformat()
log = (out/'owner-suites.log').read_text(encoding='utf-8-sig')
assert '999 passed in 6.00s' in log and 'failed' not in log
owner_running = False
try:
    process = psutil.Process(84328)
    owner_running = process.name().casefold() == 'baxy.exe' and abs(process.create_time()-1788820609.3516054) < .01
except psutil.NoSuchProcess:
    pass
after = out/'after'
after.mkdir(exist_ok=False)
source_names = ['src/baxy_mind/llm.py', 'tests/test_compose_contract.py']
for name in source_names:
    shutil.copy2(root/name, after/Path(name).name)
runtime = Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
runtime_sha = hashlib.sha256(runtime.read_bytes()).hexdigest()
assert runtime_sha == '13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
summary = f'''# C03 — checkpoint267 — EN_CURSO

Goal-c03; main preservada. Último cambio267: llm.compose_user_message deja de
promover facts.context a situation.previousResponse. La misma prosa anterior
viaja como JSON previous_dialogue_for_references_only fuera de situation,
incluidos los tres intentos; sin nuevo system, sampler ni validador de frases.
PROCEDENCIA_COMPOSITOR267.md; astra-compose-provenance267/before y after.

HTTP9 de UI263 decía «Ya he abierto Steam.» sin operación nueva. Su system
presentaba situation como evidencia, pero ésta contenía la respuesta anterior.
PAYLOAD_COMPARISON.json: petición, system, roles y parámetros idénticos;
sólo se separa el contexto de los hechos. Es captura antes de HTTP, NO inferencia.
La frase falsa aún pasa compose_visible_defect. C# ClaimsUnverifiedSuccess
también la dejó pasar. No afirmar resuelto el fallo público ni ocultarlo con
una frase especial; pendiente comparación nativa y frontera de publicación.

267: pytest test_compose_contract/test_llm_transport/test_turn_policy:999pass,
0skip,6,00s; cinco controles nuevos/actualizados fallaban antes. Ruff verde.
266: lector separa afirmación seguida de petición usando cabezas existentes
y morfología negativa; resolver app usa normalización compartida. «Si, abre
steam» pasa de falso compuesto2 a app.open/Steam; catálogo-unavailable eraNone.
2597pass/0skip,54,36s y ruff. Ninguno de266/267 tiene aún prueba modelo/UI/Fast.
Último Fast anterior262 verde; no se repite Full durante reparación.

Instancia264 pertenece al dueño: PID84328/createTime1788820609.3516054,
launcher100540, ventana397256; proceso revalidado al cerrar267: {owner_running}.
NO cerrar/reiniciar ni inyectar pruebas; sin watchdog ni cierre automático.
NO leer ahora sus mensajes nuevos: el dueño pidió guardarlos para corregir
DESPUÉS. Traces privadas C03-owner264-private; perfil real dev-mente-v2.
No se usó su servidor de inferencia ni cambió volumen. Tests267 terminaron
exit0; no medición propia en curso. Registro13b971… intacto, overrideQwen3.5.

Siguiente268: seguir con HTTP263 y diagnósticos de causa anteriores, sin tocar
264. La frase «Tengo en mente que abras steam» pierde app.open en shortlist28;
dos selecciones nativas sin tools. Resolver recuperación de operación/identidad
y admisión de afirmaciones. Capacidades263: lista incompleta/length, timeout,
extra_claim, UI Response error; también sigue pendiente. Paquetes267 listos
para comparación nativa cuando no interfiera con las pruebas del dueño.
Reutilizar investigación formato/modelo y catalog67, no otro barrido genérico.

Conservar PRUEBAS_UI263/TRAMO263 y LECTURA_AFIRMACION265_266/TRAMO265_266.
UI263 Steam simple y recuperación verificados con Core. Recursos260 conjuntos
UI/LLM/captura/AEC/Piper:3516,66MiBGPU/4822,60MiBRAM, sin ASR humano;
263:3504,71MiBGPU/5624,86MiBRAM, sin captura. Wake no certificado.

Alcance íntegro pendiente: ocho rutas útiles,100/100humanos frescos aún sin
congelar (742únicos/239revisados, tres ingleses admitidos), averías/recuperación,
UI/voz/ASR/recursos finales, perfil/runtime/instalación, continuidad C04–C09,
Full verde y publicación fuera main. C03 activo, sin bloqueo externo.
'''
for name in ('CHECKPOINT.md','HANDOFF.md'):
    (base/name).write_text(summary, encoding='utf-8')
relevo_path = base/'RELEVO_ACTIVO.json'
relevo = json.loads(relevo_path.read_text(encoding='utf-8'))
relevo.update(confirmedAtUtc=now,
    checkpoint='267: dialogue removed from verified situation; 999pass/0skip. Native/public acceptance pending.',
    continuation='268 prior HTTP263 retrieval and public truthfulness; defer new owner264 messages and keep its instance untouched.')
relevo['userOwnedInstance']['processRevalidated'] = owner_running
relevo_path.write_text(json.dumps(relevo, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
names = source_names + ['scratchpad/c03-inspect267.py','scratchpad/c03-prepare267.py',
    'scratchpad/c03-payload267.py','scratchpad/c03-finish267.py',
    'artifacts/comprobaciones/C03/PROCEDENCIA_COMPOSITOR267.md']
names += [str(path.relative_to(root)).replace('\\','/') for path in [
    out/'PREREG.json', out/'PAYLOAD_COMPARISON.json', out/'baseline.log',
    out/'compose-suite.log', out/'owner-suites.log',
    out/'before/llm.py', out/'before/test_compose_contract.py',
    after/'llm.py', after/'test_compose_contract.py']]
pins = {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names}
(base/'TRAMO267_PINS.json').write_text(json.dumps({'utc':now,'publicFiles':pins,
    'runtimeSha256':runtime_sha, 'nativeInference':False,'ownerProcessRunning':owner_running},
    ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'pins':len(pins),'ownerRunning':owner_running,'tests':'999pass/0skip','status':'EN_CURSO'}))
