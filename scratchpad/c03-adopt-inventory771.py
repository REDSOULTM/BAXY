"""Seal validated771 and the next complete registered regression."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import subprocess

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/comprobaciones/C03';OUT=BASE/'INVENTORY_SCOPE771'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def write(path,data):
    path.write_bytes((json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))


assert not subprocess.check_output(['git','diff','--cached','--name-only']).strip()
assert not (OUT/'ADOPTION.json').exists()
pins=read(OUT/'SOURCE_PINS.json')
assert all(sha(ROOT/p)==h for p,h in pins.items())
assert all(sha(ROOT/p)==h for p,h in read(BASE/'DENSE_INVENTORY764/SOURCE_PINS.json').items())
assert b'986 passed in 6.20s' in (OUT/'owners.log').read_bytes()
for name,marker in [('integrity',b'1011 passed, 1 skipped in 7.61s'),('fast',b'source_quality_gate_passed: mode=Fast')]:
    raw=(Path(os.environ['TEMP'])/('c03-inventory-scope771-'+name+'.log')).read_bytes().replace(b'\r\n',b'\n')
    assert marker in raw;(OUT/(name+'.log')).write_bytes(raw)
now=datetime.now(timezone.utc).isoformat()
write(OUT/'VALIDATION.json',{'utc':now,
    'python':'C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe',
    'owners_arguments':'-X utf8 -m pytest tests/test_c03_inventory_scope_polarity.py tests/test_c03_inventory_semantic_projection.py tests/test_c03_window_inventory.py tests/test_c03_window_state_facts.py tests/test_c03_window_focus_coverage.py tests/test_compose_contract.py tests/test_c03_request_preservation.py -q',
    'owners':{'passed':986,'failed':0,'skipped':0,'seconds':6.20,'new_cases':68},
    'integrity_arguments':'-X utf8 -m pytest <integrity_files> -q',
    'integrity_files':subprocess.check_output(['git','ls-files','tests/test_c03_window*.py'],text=True).splitlines()+[
        'tests/test_c03_observed_window_vocabulary.py','tests/test_price_v8_veto_damage_by_cause.py',
        'tests/test_stt_quality_evaluators.py','tests/test_validate_physical_wake_v17_program.py'],
    'integrity':{'passed':1011,'failed':0,'environmental_skips':1,'seconds':7.61,'skip':'Private blind STT campaign inputs absent; not a pass/voice credit'},
    'fast_command':'scripts/test_source_quality.ps1 -Mode Fast','fast_exit_code':0,'fast_session':87564,'terminal_collected':True,
    'release_seconds':25.94,'warnings':0,'errors':0,'all_source_pins_unchanged_after_validation':True,
    'replay':'CAPTURED_REPLAY: measured770C retry payload equals candidate exactly; exactC/D replies pass complete compositor in1stub, false chronology remains rejected. No new inference.',
    'full_new':False,'full_reason':'Python-only adoption; no C#+Python shared source change. Final Full remains required.',
    'coverage_added':0,'product_pending':'Prepared772 full73 frozen panel/criteria and postbuild DLL seal.'})
write(OUT/'ADOPTION.json',{'utc':now,'status':'adopted_after_owners_integrity_fast','source_pins':'SOURCE_PINS.json',
    'commit':'Containing commit','new_model_or_profile':False,'first_attempt_sampler_budget_unchanged':True,
    'retry_and_inventory_fact_interpretation_changed':True,'coverage_added':0})
(OUT/'REPORT.md').write_bytes('''# Cantidades y negación ligadas a su observación

El verificador de inventarios distingue ahora la cantidad de una lista/página del total seleccionado y la afirmación de exhaustividad de su negación. Reutiliza el mismo dato derivado de página completa que recibe el modelo; no inventa un total cuando la enumeración es incompleta. Tener una página como sujeto no autoriza afirmar que contiene todas las ventanas del inventario, mientras que «todas las ventanas mostradas en esta página» limita el cuantificador a esa página.

La corrección de cronología incorpora exactamente la explicación explícita medida en770C. Se conserva el borrador, que aquella variante utilizó para mantener las20identidades, y un único constructor reemplaza la duplicación entre segundo y tercer intento. La explicación se añade sólo cuando la validación detecta cronología no observada; no se cambia primer intento, modelo, sampler ni presupuesto.

68 controles nuevos cubren español/inglés, cantidades y totales distintos, páginas completas/parciales y alcance desconocido, afirmaciones/negaciones, nombres observados opacos y ambas rutas de modelo.986 pruebas dueñas pasan; integridad de ventanas y pins1011pass/1skip ambiental por datos STT privados ausentes. Las suites se solapan. Fast pasó con Release25,94s, cero advertencias y errores. Fuente y declaraciones permanecen selladas.

Una reproducción controlada acepta literalmente C/D capturadas en770, en una llamada simulada cada una, y comprueba que el nuevo segundo request es idéntico al que generó C con inferencia real. El borrador que inventa recencia sigue rechazado. Se conserva la limitación de entrada: el sobre se reconstruyó con payload proyectado idéntico porque audit.situation está truncado. No es una nueva sesión real de BAXY ni una certificación del tiempo total de reintento.

El fallo770B sigue abierto: omitía una ventana repetida aunque el verificador aceptaba. Ninguna cobertura se acredita con esa variante. También quedan interpretación del inventario, foco, lecturas ausentes y otros bloqueos del panel.772 ejecutará los73casos completos con el runtime registrado tras publicar esta fuente. Encuesta26cubiertos/716abiertos/0NA; sin crédito UI/voz/reserva ni cierre C03. Full final pendiente.
'''.encode('utf-8'))
note=('771 adoptado: alcance de cantidad/polaridad de exhaustividad y causa explícita770C.986owners/0skip/6,20s, '
    '1011integridad/1skipSTT/7,61s;Fast0/87564 recogida/Release25,94s.6pinsintactos. C/Dexactasaceptadas1stub;retryigual770C. '
    'Publicar yejecutar772 completo73, no procesoactivo. Omisiónrepetida770B sigueabierta.26/716/0.\n\n')
cp=BASE/'CHECKPOINT.md';pending=cp.with_suffix('.pending.md');pending.write_bytes(note.encode()+cp.read_bytes());pending.replace(cp)
r=read(BASE/'RELEVO_ACTIVO.json');r.update(checkpoint=note.strip(),confirmedAtUtc=now,activeValidation=None,
    workStatus='inventory_scope771_adopted_pending_publication',continuation='Publish771 then run prepared772 complete73 with registered Python. Require all EXIT guards, adjudicate actual replies/observations before credit.')
write(BASE/'RELEVO_ACTIVO.json',r)
handoff='''# Handoff C03 —771 —2026-09-10

Goal activo en Goal-c03, main intacto5f572ee1. Encuesta742/rev1248:26cubiertos/716abiertos/0NA; registroSHA85f9ef743313dd906eaece95204dc46f3c644d3f8ba9db307b1bcc8c208899f6. Sin pregunta pendiente. BAXY manual cerrado.87564 terminó0/recogida; no inferencia/gate activo. Preservar WIP ajeno.

771adoptado, publicar. INVENTORY_SCOPE771/VALIDATION:986owners/0skip/6,20s,68nuevos;1011integridad/1skipSTT/7,61s;Fast0/Release25,94s.6pins actuales, programa407=cadb63073d8ea75694fa1a477aada8c336a76a72db4ac9f5c899e7a9d0c183f8, mismas3raíces. Fuente sóloPython, sinFull nuevo. No tocar pins históricos ni wakev17.

Reparación: window_prose_facts liga count a lista/list, comparte alcance completo/parcial/desconocido con proyección y distingue negación de exhaustividad; página como sujeto no autoriza allglobal. llm.py reutiliza constructor retry/third y añade exactamente causa explícita770C para cronología no observada. Modelo/sampler/primerintento/presupuesto intactos. CAPTURED_REPLAY acepta C/D exactas1stub y demuestra que requestretry==770C; no inferencia nueva ni inputbrutoidéntico.

Siguiente: publicar771 y ejecutar scratchpad/c03-status-batch772.py con C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe -X utf8. Mismos73casos689/729, sin hooks; prepara main.compile_if_needed antes del sello DLL. Reviewer772 preparado. No editar fuente durante corrida. Todas las guardas EXIT true y adjudicación manual contra cada observación.

769publicada en803f211d:52/73,21fallos;3499,56MiB/2510,80MiB/344,859s, todasguardastrue. Dosinventariosfallaron, ventanalfiel vetado;H0655/CPUEN cambian por datos/redacción,sin causalidad. Registro50evidencias añadidas sin estados nuevos.770publicada mismo commit:factorial4 sobre20/25, A20conrecenciafalsa,B19omisiónaceptadaporchecker,C/D20fielesvetadosporalcance/negación.771reparaesosvetos yusaC;noequivale a entrega real.

770B continúa abierto: verificador no comprueba cobertura/multiplicidad de lista. No hay extractor multiset de inventario existente. observed_response_literals.py:8–50 usa set sólo para vocabulario; el mapa de foco subjects[name]→set(indices) SÍ conserva cuántas ventanas comparten alias pero sólo enlazaidentidadúnica, no inventarios. No atribuirle pérdida de conteo. Pruebasdueñas inventory.py:107–164/189–222; conservar traduccioneslegítimas/nombres opacos sinwhitelistdeapps.

Otrosbloqueos: lector window_inventory_arguments effect_intent.py:5257–5312 excluye observación+interrogativa,ortografía y adverbiopresenteinterno;grounding reusaelmismolector. Foco ventanal/relativa ya localizado. RAMetiquetas,Internetvsinterfaz,WLAN,CPUacumulada,lecturasfaltantes. Full7histórico4574.NETpass/1skip+16omisiones;11399Pythonpass/3skips+466subtests. Faltan742,reserva,UI/loopback/AEC,recursosconjuntos≤4GiB,matriz/continuidad,Fullfinal.69950tareas×6perfiles sinBAXY;no promover modelo desde fallos de capas. C03 activo.
'''
(BASE/'HANDOFF.md').write_bytes(handoff.encode('utf-8'))
names=['CAPTURED_REPLAY.json','SOURCE_PINS.json','PROGRAM.json','PLAN.json','owners-collection-error.log',
    'owners-scope.log','owners.log','integrity.log','fast.log','VALIDATION.json','ADOPTION.json','REPORT.md']
paths=[OUT/name for name in names]+[ROOT/'scratchpad'/name for name in ['c03-replay-inventory771.py',
    'c03-prepare-inventory771.py','c03-adopt-inventory771.py','c03-status-batch772.py','c03-review-status772.py']]
assert all(b'\r\n' not in p.read_bytes() for p in paths)
artifact_pins={p.relative_to(ROOT).as_posix():sha(p) for p in paths};write(OUT/'PINS.json',artifact_pins)
paths += [OUT/'PINS.json']+[ROOT/p for p in pins]+[BASE/name for name in ['CHECKPOINT.md','HANDOFF.md','RELEVO_ACTIVO.json']]
relative=[p.relative_to(ROOT).as_posix() for p in paths]
subprocess.run(['git','add','--',*relative],check=True)
assert set(subprocess.check_output(['git','diff','--cached','--name-only'],text=True).splitlines())==set(relative)
for p,h in {**pins,**artifact_pins}.items():
    assert hashlib.sha256(subprocess.check_output(['git','show',':'+p])).hexdigest()==h,p
subprocess.run(['git','diff','--cached','--check'],check=True)
print(json.dumps({'source_pins':len(pins),'artifact_pins':len(artifact_pins),'staged_files':len(relative)}))
