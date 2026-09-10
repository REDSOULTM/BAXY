"""Adopt766 after owners/integrity/Fast, preserving the failed765 binary seal."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import subprocess

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
out = base/'TRUNCATION766'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
now = datetime.now(timezone.utc).isoformat()


def write(path, value):
    path.write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))


assert not subprocess.check_output(['git','diff','--cached','--name-only']).strip()
assert subprocess.check_output(['git','branch','--show-current'],text=True).strip() == 'Goal-c03'
pins = read(out/'SOURCE_PINS.json')
assert all(sha(root/p)==h for p,h in pins.items())
assert all(sha(root/p)==h for p,h in read(base/'DENSE_INVENTORY764/SOURCE_PINS.json').items())
for name, marker in [('owners-final',b'457 passed'),('integrity',b'343 passed, 1 skipped'),('fast',b'source_quality_gate_passed: mode=Fast')]:
    data=(Path(os.environ['TEMP'])/f'c03-truncation766-{name}.log').read_bytes().replace(b'\r\n',b'\n')
    assert marker in data
    (out/f'{name}.log').write_bytes(data)
write(out/'VALIDATION.json', {
    'utc':now,'owner_command':'Registered Python -X utf8 -m pytest tests/test_compose_contract.py tests/test_c03_request_preservation.py tests/test_c03_inventory_semantic_projection.py -q',
    'owners':{'passed':457,'failed':0,'skipped':0,'seconds':2.87,'new_cases':30},
    'integrity_command':'Registered Python -X utf8 -m pytest tests/test_price_v8_veto_damage_by_cause.py tests/test_stt_quality_evaluators.py tests/test_validate_physical_wake_v17_program.py tests/test_c03_window_inventory.py tests/test_c03_window_facts.py tests/test_c03_observed_window_vocabulary.py -q',
    'integrity':{'passed':343,'failed':0,'environmental_skips':1,'seconds':3.85,'skip':'Blind STT campaign inputs absent; not a pass or voice acceptance'},
    'fast_command':'scripts/test_source_quality.ps1 -Mode Fast','fast_exit_code':0,'release_seconds':11.04,'warnings':0,'errors':0,
    'source_and_declaration_pins_unchanged_after_fast':True,
    'test_line_endings':'Test file only converted CRLF to LF after Fast, then owners rerun; no source/declaration changes. TEST_LINE_ENDINGS.json records both hashes.',
    'replay':'RECONSTRUCTED_REPLAY.json: same projected facts and draft accepted in one stub call, no real inference. Initial attempt used audit situation truncated at2048characters and is preserved as an input error.',
    'full_new':False,'full_reason':'Python-only source adoption; no shared C#+Python change. Final Full remains required.',
    'coverage_added':0,'real_product_pending':'Prepared767 registered73 cases with postbuild DLL seal',
})
write(out/'ADOPTION.json',{'utc':now,'status':'adopted_after_owners_integrity_and_fast','source_pins':'SOURCE_PINS.json',
    'commit':'Containing commit','model_prompt_budget_changed':False,'coverage_added':0,'survey_counts':{'covered':26,'open':716,'not_applicable':0}})
(out/'REPORT.md').write_bytes('''# Palabra observada completa, sin excepción por aplicación

El detector de palabras cortadas compara ahora valores de hechos y palabras de respuesta con el mismo mínimo de cinco letras. Antes, un nombre completo como Atlas quedaba fuera de las palabras válidas y podía confundirse con un recorte de AtlasHelper, aunque ambos aparecieran en la observación. El cambio es general: no añade nombres permitidos ni altera el modelo, su prompt o la respuesta.

30 controles nuevos incluyen seis nombres, español/inglés, valores anidados, una coincidencia que sólo aparece como clave y prefijos realmente incompletos. Las457 pruebas dueñas pasan; integridad343pass/1skip ambiental por entradas STT privadas ausentes. Fast pasó, Release11,04s, cero advertencias/errores. El archivo de tests se normalizó a LF y sus dueñas se repitieron; la fuente y sus declaraciones no cambiaron después de Fast.

Con el borrador correcto de H0023 capturado en765, una reproducción controlada devuelve el texto exacto en una sola llamada simulada. El primer intento usó el campo situation del audit, truncado a2048caracteres: fue un error de entrada y está conservado. La reproducción corregida reconstruye el envoltorio verificado y demuestra igualdad del payload proyectado; no se presenta como una repetición del input bruto completo ni una inferencia nueva. H0103 conserva omisiones adicionales, y el resto de bloqueos sigue abierto.

765 se publica como diagnóstico por el cambio de DLL durante la preparación automática del launcher. El driver767 usa primero la compilación de main.py y sella después el ejecutable, antes de ejecutar los73casos completos con el mismo perfil y criterios. Se exigirá que el DLL y la fuente permanezcan intactos.

Programa407 y declaraciones vigentes STT/V8 actualizados; sellos históricos intactos. Encuesta26cubiertos/716abiertos/0NA. Sin crédito de reserva, UI/voz, consumo conjunto o cierre C03. Full final pendiente.
'''.encode('utf-8'))
checkpoint=('766adoptado: comparación de palabras completas usa mínimo5 en fuente yrespuesta; sin excepciones deapps/modelos. '
    '457owners pass/0skips/2,87s,343integridad pass/1skip ambiental/3,85s,Fast exit0/Release11,04s/0warnings/errors. '
    'Reproducción controlada deH0023 devuelveborrador exacto en1stub, no modelo real; primera entradaaudittruncada conservada. '
    '765=diagnóstico52/73 por DLL reconstruidoantesdelconductor. Publicar yseguir767 conprebuild antesdesello.26/716/0.\n\n')
cp=base/'CHECKPOINT.md';pending=cp.with_suffix('.pending.md');pending.write_bytes(checkpoint.encode()+cp.read_bytes());pending.replace(cp)
(base/'HANDOFF.md').write_bytes('''# Handoff C03 — fuente766 — 2026-09-10

Goal íntegro activo en Goal-c03; main intacto5f572ee1. Encuesta742/rev1248:26cubiertos/716abiertos/0NA; SHAregistro680a4e1de73b6ab9d9d0b7122c74084f978ab514b688cb8c45f6621f362d26a0. Sin pregunta pendiente. BAXY manual cerrado. No inferencia/gate activo;79148 y51130 terminaron/recogidos. Preservar WIP ajeno.

Fuentes760(proyección/página/recencia) y764(dense inventarios) publicadas;764commit295be2b7d813683bcf8042302ae08a9573038852.766igualó mínimo de palabras5/5 en _truncated_fact_word;30controles nuevos,457owners/0skips,343integridad/1skipSTT,Fast0/Release11,04s. TRUNCATION766/VALIDATION.json contiene comandos. SóloPython; noFull nuevo. Programa407=b779c55710ff6efbf1d179d460d7ad6c093bd71e96ad8b290db56d0efa455ad3,raíces experiments/voice_latency+scripts+src/baxy_mind. Cinco pins actuales766; dos764. No tocar SOURCE_PINS históricos751/760 ni wakev17.

Siguiente: publicar766 y ejecutar scratchpad/c03-status-batch767.py con Python registrado. Ya preparado, no repetir preparador766. Mismos73casos689/729 y criterios; el driver prepara compile_if_needed(force=False) desde main.py antes de sellar DLL y luego lanza py main.py --conductor. Registrar sesión/PID; no editar fuente durante la corrida. Exigir todos los EXIT guards, incluido app_dll_unchanged.

765 terminó exit0/382,609s,3499,56MiBGPU/2386,90MiBRSS. Todas las fuentes/manifiesto/runner intactos, pero DLL cambió: launcher lo recompiló antes del conductor tras el sello previo. Sólo diagnóstico52acreditables/21fallos, no aceptación sellada. H0650 ahora ordena valores distintos correctamente, no ganancia causal. STATUS_BATCH765/RESULT.json y BINARY_SEAL_FAILURE.json; respuestas/payloads privados en C03-status-batch765-private/review.json y ADJUDICACION.md. No normalizar ese fallo a pass.

H0023 primera respuesta765 es fiel20/24; guardián de truncación rechaza Steam como prefijo de steamwebhelper porque sólo admitía hechos6+letras. 766repara eso. Replay inicial falló porque audit.situation está cortado a2048caracteres; RECONSTRUCTED_REPLAY usa sobre verificado reconstruido, proyecta payload idéntico y admite borrador exacto en1stub. No inferencia ni inputbrutoidéntico. H0103 primera lista omite identidades/agrupa sin cuentas: no aprobar al retirar el veto.

Otros bloqueos de ventanas: H0209/H0663/EN vetados por dominio; foco fiel «Ahora tiene focus el ventanal de ChatGPT» y relativa «El que tiene foco ahora es ChatGPT» rechazados. Lectura realizada: window_prose_facts.py:162–205 window_subject limita prefijo;:241–286 enlace no consume relativa/cópula, pero ya hay identidad observada única, negación y guardias condicionales. Dueños focus_apposition/identity_answers/focus_subject_order. Root repara después de767, sin excepción literal ni por modelo.

Resto: lecturas ausentes/frescura, RAMusable llamada instalada/disponible, interfazUp confundida con Internet, WLAN ampliado, CPU acumulada presentada como actual. 699probó50tareas completas×6perfiles sinBAXY;73757paresK2,14sóloBAXY/3sólo directo. No promover K2 ni atribuir defectos de integración al modelo. Full7histórico4574.NETpass/1skip+16omisiones;11399Pythonpass/3skips+466subtests. Faltan cobertura completa742,reserva,UI/loopback/AEC,recursos conjuntos≤4GiB,matriz/continuidad yFullfinal. C03 no terminado.
'''.encode('utf-8'))
rp=base/'RELEVO_ACTIVO.json';r=read(rp);r.update(checkpoint=checkpoint.strip(),confirmedAtUtc=now,activeValidation=None,
    workStatus='truncation766_adopted_pending_publication',continuation='Publish766 then run prepared767 complete73; verify postbuild DLL seal and all exits before acceptance.')
write(rp,r)
paths=[out/name for name in ['SOURCE_PINS.json','PROGRAM.json','PLAN.json','owners.log','owners-final.log','integrity.log','fast.log',
    'CAPTURED_REPLAY.json','RECONSTRUCTED_REPLAY.json','TEST_LINE_ENDINGS.json','VALIDATION.json','ADOPTION.json','REPORT.md']]
paths.extend(base/'STATUS_BATCH765'/name for name in ['PREREG.json','PROCESS.json','RESOURCES.json','EXIT.json','RESULT.json','BINARY_SEAL_FAILURE.json','REPORT.md'])
paths.extend(root/'scratchpad'/name for name in ['c03-review-status765.py','c03-prepare-truncation766.py','c03-status-batch767.py','c03-adopt-truncation766.py'])
paths.append(base/'DENSE_INVENTORY764/PUBLICATION.json')
assert all(p.is_file() and b'\r\n' not in p.read_bytes() for p in paths)
artifact_pins={p.relative_to(root).as_posix():sha(p) for p in paths};write(out/'PINS.json',artifact_pins)
paths.extend([out/'PINS.json',*[root/p for p in pins],*[base/name for name in ['CHECKPOINT.md','HANDOFF.md','RELEVO_ACTIVO.json']]])
relative=[p.relative_to(root).as_posix() for p in paths];subprocess.run(['git','add','--',*relative],check=True)
assert set(subprocess.check_output(['git','diff','--cached','--name-only'],text=True).splitlines())==set(relative)
for p,h in {**artifact_pins,**pins}.items():
    assert hashlib.sha256(subprocess.check_output(['git','show',':'+p])).hexdigest()==h,p
subprocess.run(['git','diff','--cached','--check'],check=True)
print(json.dumps({'source_pins':len(pins),'artifact_pins':len(artifact_pins),'staged':len(paths)}))
