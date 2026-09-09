from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
out = base / 'astra-read-recovery413'
private = local / 'C03-read-recovery413-private'
reference_path = local / 'C03-read-recovery413-cases-private/reference411.json'
reference = json.loads(reference_path.read_text(encoding='utf-8'))
first_by_pid = {}
for line in (private / 'http-posts.jsonl').open(encoding='utf-8-sig'):
    row = json.loads(line)
    if (row.get('stage') == 'request' and len(row['payload'].get('tools', [])) == 28
        and row['payload']['messages'][-1].get('content') == reference['messages'][-1]['content']):
        first_by_pid.setdefault(row['pid'], row['payload'])
assert len(first_by_pid) == 2
matches = {str(pid): payload == reference for pid, payload in first_by_pid.items()}
assert all(matches.values())
(out / 'payload-match-per-native-pid.json').write_text(json.dumps(matches, indent=2) + '\n', encoding='utf-8')
rows = [json.loads(s) for s in (out / 'replies.jsonl').open(encoding='utf-8')]
assert len(rows) == 30
cases = json.loads((local / 'C03-read-recovery413-cases-private/cases.json').read_text(encoding='utf-8'))['cases']
case_by_id = {c['id']: c for c in cases}
report = ['# 413 — reproducción exacta; recuperación temprana mejora sólo el caso frío', '',
    'Quince consultas por brazo (target frío y14calientes):13/15→14/15 útiles bajo el criterio de lectura solicitada. Target frío baseline reproduce411: Want me to check which Windows account is running me?; variante propone system.identity antes de las guardas normales y éstas la conservan.4,875s→3,109s. Los13controles generales siguen útiles. El mismo target caliente recita la cuenta del historial sin lectura nueva en ambos brazos:3,156s/4,765s. No atribuir a este resultado solución total de observación ni del producto.', '',
    'Ambas primarias frías igualan el payload411, con bienvenida, tools/system/sampler/budgets idénticos. La aserción dentro del runner para el segundo brazo consultaba el primer match del archivo acumulado; la verificación posterior independiente por los dos PID nativos confirma igualdad en ambos. payload-match-per-native-pid.json y referencia privada permiten auditarlo. No se modifica el PREREG ni se oculta esta limitación del gate en tiempo de ejecución.', '',
    'La variante sólo es un hook diagnóstico y añade un pase temprano manteniendo el fallback tardío original. NO ADOPTADA aún. Una implementación tendría que mover la reparación existente, conservar las propuestas read_only antes de todas las guardas y retirar llamadas duplicadas, sin autorizar efectos por texto fijo o saltar kernel/grounding. El caso caliente aún falla y exige examinar por qué la segunda AUTO también recita; no añadir más pases idénticos. Source410 permanece la última adoptada/validada.', '',
    'Procesos cerrados, manifiesto intacto. No ejecución de efectos, GUI/audio físico, recursos conjuntos ni aceptación humana fresca. Cuenta real sustituida sólo en el reporte público; originales privados preservados.', '']
for row in rows:
    reply = row['reply']
    failed = row['id'] == 'actual411-t3' and (row['variant'] == 'baseline' or row['phase'] == 'warm')
    prose = reply.get('reply') or reply.get('question') or '(propuesta estructurada)'
    prose = prose.replace(os.environ['USERNAME'], '[WINDOWS_IDENTITY]')
    report += [f"## {row['variant']} / {row['phase']} / {row['id']} — {'fallo' if failed else 'útil'}", '',
               case_by_id[row['id']]['request'], '', f"{reply['kind']}; operación {reply.get('operation')}; {row['seconds']}s.", '',
               '> ' + prose.replace('\n', '\n> '), '']
(out / 'RESULT.md').write_text('\n'.join(report), encoding='utf-8')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
paths = [out / n for n in ['PREREG.json', 'replies.jsonl', 'RESULT.md', 'EXIT.json', 'payload-match-baseline.json', 'payload-match-early-read.json', 'payload-match-per-native-pid.json']]
paths += [private / n for n in ['http-posts.jsonl', 'turn-audit.jsonl', 'hook/sitecustomize.py', 'startup-baseline.jsonl', 'startup-early-read.jsonl']]
paths += [reference_path, reference_path.with_name('cases.json')]
(out / 'PINS.json').write_text(json.dumps({str(p): sha(p) for p in paths}, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'native_payloads_match411': matches, 'rows': len(rows), 'baseline_useful': 13, 'variant_useful': 14}))

state = '''# C03 — fuente410 validada; 413 cerrado y parcial — EN_CURSO

Goal completo activo; Goal-c03/HEAD2bf3d4c. Preservar WIP/main/evidencia. Sinagentes,
commit/push niFull durante reparación. BAXYmanual cerrado; encuesta742/rev1248 y16
mensajesdirectos consolidados, automáticos excluidos. Original/servidor101140 intactos.
Todos los modelos/productos/tests cerrados (últimos45865,63904,32053). Sólo encuesta
yMSBuild /nodeReuse:true inactivo permanecen. No414preparado ni fuente411–413.

Última fuente410(Python/.NET): recursos abstienen antecuenta/usuario; catálogo
descriptor Windows exacto387, sin identidadgenérica para preservarGPU.12focal,
2260Python+121subtests0skip42,27s; Kernel140pass0reportedskips1s con benchmark
explícito omitido(no cuenta como pass); Fastverde/build10,88s0warn/error. RESULT/PINS.

411producto4/6útiles: T1usernameENfrío síleeidentity(lexical/closed_refusal_withdrawn),
T2/T4cuentaES yT6concepto bien. T3pregunta innecesaria; T5diceWindows10 porNT10.0.
6finales/admissions200,3identity+1status verificadas,sin timeout/silencio,exit0.
CIMconfirmaWindows11HomeSingleLanguage/10.0.26200. Provider status sólo númerosNT,
sin caption comercial; resolveresteotrofalloC03, nohardcodearWindows11. RESULT/PINS411,
OS_OBSERVATION;cuentasrealesprivadas. No nuevaafirmación sobre frío basadaen408.

T3causa: primeraAUTOrecita cuenta desdeprosa anterior; identityera1/28 ysegundaAUTO
sílaelige, pero __main__6288–6318 observation_not_recital siemprepregunta permiso.
412intentó retenersegundaAUTOread_only antesdeguardas normales, manteniendofallback
tardío sóloendiagnóstico.15/15→15/15 porquehistorialactivityomitíabienvenida inicial;
NO reprodujo411, noadoptar. payload-diff411 pruebaúnicadiferencia bienvenida. Igual
riesgo404b: reconstruirsiempre desdepayloadHTTPnativo, noactivityaislada.

413síreproduce: casoactualhistoriaHTTP411conbienvenida +13controles409, targetfrío
y14warm,15consultas/brazo. Ambasprimariasfrías iguales411 (verificaciónpor2PID),
baseline13/15→variante14/15. Fríoaclara4,875s→identity3,109s;13controlesconservados.
Calienteambosrecitancuenta pasada sinlectura(3,156/4,765s): SIGUEFALLANDO. Noeditar
productoañadiendopasesduplicados. Hook noadoptado; si se usa, mover reparación
existenteantesdeinformation/domain/compound/actionguards, conservarread_onlyyretirar
duplicación. Antes,examinarsegundaAUTOcaliente/nativos: repetirigualnoconstituyefix.
Runneraserciónsegundobrazo consultóprimerregistroacumulado; postcheck2PIDindependiente
confirmaigualdadreal. RESULT/PINS412/413completos; datosrealesenprivado413-cases.

Archivosclave: scratchpad/c03-read-recovery413.py,c03-early-read413-hook.py,
astra-read-recovery413/RESULT.md; privadaC03-read-recovery413-private/http-posts,
turn-audit y C03-read-recovery413-cases-private/reference411.json. Helperactual
__main__2016_catalog_answers_the_request devuelvesóloprimeraop ydescartaproposal;
_post_native_tool_selection llm5857 normalizaen_decide_turn7150. Dueños tests/
test_turn_policy.py11800 parahelper. No quitarbienvenida delproductoparaocultarfallo.

409warm11/13→13/13descriptor,408retrieval2/4→4/4.407promociónfunciona24,438s, no
agotamiento185s.405audit lexical. No repetirtimeouts/sampler399/400,prompt391,
resolvedor392,catálogo376,wrappers346/347,origen349,9B390 sinnuevodato.
404nombreactualconversacióny402literallecturaconservados. MemoriaES/redactada,
falsapersistenciaalpresentarse yprecedenciaaclaraciónMainWindow671 abiertos.

RestaC03:ocho rutas/encuesta/fallos264;0requisitosfinales/0de100frescoscertificados;
averías,UIreal/vozfísica/ASR/wake/≤4GBconjunto,runtime/instalación/contratosC04–C09,
Fullverde/publicación. Sinbloqueoexterno, sinporcentaje/ETA inventado. Goalactivo.
'''
(base / 'CHECKPOINT.md').write_text(state, encoding='utf-8')
(base / 'HANDOFF.md').write_text(state.replace('# C03', '# Handoff C03', 1), encoding='utf-8')
(base / 'CHECKPOINT_413_ANTES_414.md').write_text(state, encoding='utf-8')
relevo = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
relevo.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint='Source410 validated;411 product4/6;412 failed reproduction;413 exact13/15→14/15 partial, not adopted. Models closed.', continuation='No414prepared. Inspect warm413 native secondary reciting historical account; do not duplicate passes. OS marketing-name error411 also open. Full C03 active.')
(base / 'RELEVO_ACTIVO.json').write_text(json.dumps(relevo, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
