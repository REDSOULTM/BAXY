"""Persist verified source, evidence pins, and the owner-controlled live app."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import psutil

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
out = base/'astra-acknowledgement266'
now = datetime.now(timezone.utc).isoformat()
process = psutil.Process(84328)
assert abs(process.create_time()-1788820609.3516054) < .01
assert process.name().casefold() == 'baxy.exe'
log = (out/'owner-suites-final.log').read_text(encoding='utf-8-sig')
assert '2597 passed in 54.36s' in log and 'failed' not in log
after = out/'after'
after.mkdir(exist_ok=False)
source_names = ['src/baxy_mind/effect_intent.py', 'tests/test_effect_intent.py']
for name in source_names:
    shutil.copy2(root/name, after/Path(name).name)
summary = '''# C03 — checkpoint266 — EN_CURSO

Goal-c03; main preservada. Último cambio266: la afirmación separada de una
petición explícita no cuenta como otro efecto. Normalización compartida y
resolución de identidad de apps coherentes; conserva condiciones, contenido
literal, prohibiciones y respuestas sociales. Fuente/test congelados en
astra-acknowledgement266/before y after. LECTURA_AFIRMACION265_266.md.

265 descartó _catalog_unavailable como causa de «Si, abre steam»: devuelve
None. La primera transformación errónea era unresolved_compound_contract,
que contaba «si» como efecto pendiente. REPLAY_FINAL compara mismo catálogo262
y tres literales antes/después: «Si, abre steam» ahora app.open/Steam, sin veto;
guardia de dominio real conserva operación. «abre steam» sigue igual. La frase
«Tengo en mente que abras steam» continúa sin resolver, no se atribuye mejora.

Validación266: pytest tests/test_effect_intent.py tests/test_compound_missions.py
tests/test_turn_policy.py -q --tb=short:2597 pass/0skip,54,36s. Ruff dos archivos
verde. Mismos41 tests con módulo anterior:21fail/20pass. Iteraciones previas y
errores de tooling preservados. No Full. Fast de266 y UI/modelo pendientes;
último Fast anterior262 verde, no equivale a validar fuente266.

Instancia264 ABIERTA POR PETICIÓN DEL DUEÑO: Baxy PID84328, createTime
1788820609.3516054, launcher100540, ventana397256. Sin watchdog/cierre automático,
sin hook y sin cambiar volumen. NO cerrar/reiniciar ni inyectar pruebas.
Usuario pide guardar sus mensajes nuevos para corregir DESPUÉS; no analizarlos
ahora. Traces privadas %LOCALAPPDATA%/BAXY/C03-owner264-private/; perfil real
dev-mente-v2. Modelo Qwen3.5 override no promovido. Proceso revalidado al cerrar
266; sesiones de tests71908 y68055 terminales, última exit0. No otras corridas.

Mantener evidencia263: PRUEBAS_UI263.md/TRAMO263_PINS.json; Steam simple y
recuperación verificados en UI, tres fallos restantes bien localizados. HTTP
privado C03-ui263-private/http-posts.jsonl. 267 seguir con esas trazas previas:
shortlist28 omite app.open en frase larga; fallback compositor convierte
facts.context en previousResponse (llm.py) y afirmó «Ya he abierto Steam.» sin
operación nueva. Falta reparar selección/composición y capacidades (length,
timeout, extra_claim, Response error). No añadir excepciones por Steam ni
repetir variantes de modelo sin causa nueva. Aún debe verificarse266 integrado.

Recursos260 con UI/LLM/captura/AEC/Piper:3516,66MiB GPU/4822,60MiB RAM; no ASR
humano.263:3504,71MiB GPU/5624,86MiB RAM, sin captura. Wake no certificado;
registro13b971… intacto. Cambio262 catálogo:292→293 apps, sólo añade Steam al
desambiguar destino local ausente;169operaciones sin cambios,39tests0skip.

Pendiente íntegro: ocho rutas útiles,100/100humanos frescos aún sin congelar
(742únicos/239revisados, tres ingleses admitidos), averías/recuperación,
UI/voz/ASR/recursos finales, perfil/runtime/instalación, continuidad C04–C09,
Full totalmente verde y publicación fuera main. C03 activo sin bloqueo externo.
'''
for name in ('CHECKPOINT.md', 'HANDOFF.md'):
    (base/name).write_text(summary, encoding='utf-8')
relevo = base/'RELEVO_ACTIVO.json'
data = json.loads(relevo.read_text(encoding='utf-8'))
data.update(confirmedAtUtc=now,
    checkpoint='266: shared affirmative-request boundary repaired; 2597 pass/0skip. Owner264 remains open and untouched.',
    continuation='267 prior HTTP263 retrieval/composition/capabilities. Defer new owner264 messages. Full scope remains active; no Full during repair.')
relevo.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
names = source_names + [
    'scratchpad/c03-boundaries265.py', 'scratchpad/c03-prepare266.py',
    'scratchpad/c03-baseline266.py', 'scratchpad/c03-verify266.py', 'scratchpad/c03-finish266.py',
    'artifacts/comprobaciones/C03/LECTURA_AFIRMACION265_266.md',
    'artifacts/comprobaciones/C03/astra-boundaries265/PREREG.json',
    'artifacts/comprobaciones/C03/astra-boundaries265/RESULT.json',
] + [str(path.relative_to(root)).replace('\\','/') for path in [
    out/'PREREG.json', out/'REPLAY.json', out/'REPLAY_FINAL.json',
    out/'baseline.log', out/'baseline-collected.log', out/'baseline-matched.log',
    out/'after-targeted.log', out/'after-bounded.log', out/'owner-suites.log',
    out/'owner-suites-final.log', after/'effect_intent.py', after/'test_effect_intent.py',
    out/'before/effect_intent.py', out/'before/test_effect_intent.py',
]]
pins = {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names}
(base/'TRAMO265_266_PINS.json').write_text(json.dumps({'utc':now,'publicFiles':pins,
    'ownerProcessRevalidated':84328, 'acceptance':'boundary only; no UI/model acceptance'},
    ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'pins':len(pins),'ownerPid':84328,'tests':'2597 pass / 0 skip',
    'status':'EN_CURSO','next':267}))
