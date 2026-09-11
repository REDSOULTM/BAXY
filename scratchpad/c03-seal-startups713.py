"""Seal the completed startup diagnostic and verify the Full prerequisites."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import statistics

import psutil

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-fixture-startup-probe713'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-fixture-startup713-private'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not (out/'RESULT.json').exists()
exit_record=json.loads((out/'EXIT.json').read_text())
assert exit_record['fixture_restored'] and exit_record['temporary_helper_removed']
log=(out/'TEST.log').read_text(encoding='utf-8')
assert 'Correctas FiftyColdStartsUsingTheActualContractFixture' in log
assert 'Pruebas totales: 1' in log and 'Correcto: 1' in log
assert exit_record['test_passed_from_log'] and exit_record['cleanup_completed_afterward']
assert not any(p.info['name'] and p.info['name'].lower() in {'testhost.exe','baxy-core.exe','llama-server.exe'} for p in psutil.process_iter(['name']))
rows=[]
for p in sorted(private.glob('startup-*/result.json')):
    r=json.loads(p.read_text())
    r['id']=p.parent.name;r['result_sha256']=sha(p)
    rows.append(r)
assert len(rows)==50 and all(r['IsReady'] and not r['HasStartupError'] and not r['captured'] and not r['diagnosticErrors'] for r in rows)
candidate=json.loads((base/'astra-catalog-source712/CANDIDATE.json').read_text())
assert all(sha(root/name)==value for name,value in candidate['sources'].items())
assert sha(root/'tests/Baxy.Integration.Tests/MindShellEndToEndTests.cs')=='628ab599ecae26227707d479220bbab41a06f17e9a3980c828c8dd6c45119ae3'
assert not (root/'tests/Baxy.Integration.Tests/TemporaryStartupProbe713.cs').exists()
owners=json.loads((base/'astra-catalog-source712/PROVIDER_OWNERS_EXIT.json').read_text(encoding='utf-8-sig'))
assert owners['exit_code']==0
times=[r['seconds'] for r in rows]
result={'utc':datetime.now(timezone.utc).isoformat(),'wrapper_exit_code':exit_record['exit_code'],'test_exit_code':exit_record['test_exit_code'],'dotnet_diagnostic_tests':{'passed':1,'failed':0,'skipped':0},
    'startup_attempts':rows,'ready':50,'failed_startups':0,'initialize_seconds':{'minimum':min(times),'median':statistics.median(times),'maximum':max(times)},
    'candidate_sources_unchanged':True,'fixture_restored':True,'temporary_helper_removed':True,
    'baseline709':{'ready':5,'failed_startups':1,'stopped_on_first_failure':True},
    'scope':'Same real fixture and observation as709;50independent Core/data-root starts in one NUnit test, no model/user turn. Original10s deadline applies to Core handshake, not all InitializeAsync. No retries after failure. This run does not prove absence of rare failure or meet all C03 acceptance.',
    'full_next':'Run integrated source-quality Full, which rebuilds the restored source and removes the diagnostic from test binaries. Do not run product706 on the previous Full4.',
    'adopted':False,'coverage_added':0,'goal_complete':False}
write(out/'RESULT.json',result)
(out/'REPORT.md').write_text(f'''# Arranque tras una sola enumeración del catálogo

Los50 arranques del fixture real terminaron listos, sin timeout del Core, error de inicio ni captura diagnóstica. La sonda anterior había terminado en su sexto arranque con5listos/1fallido. Se conservó el mismo montaje, observador y límite de10s del saludo del Core, con nuevos datos privados por arranque.

NUnit: **1pass,0fail,0skips**. Las50inicializaciones están dentro de esa prueba; no se presentan como50pruebas NUnit ni50requisitos de encuesta. InitializeAsync completo midió mínimo{min(times):.3f}s, mediana{statistics.median(times):.3f}s y máximo{max(times):.3f}s. Ese reloj también incluye trabajo posterior al saludo y no comparte su límite10s.

El fixture quedó restaurado byteporbyte y el helper temporal retirado. Todas las fuentes del candidato712 permanecen idénticas a su sello. El siguiente Full debe recompilar los tests porque el binario utilizado todavía contenía la instrumentación.

El ejecutor terminó con exit1 por OSError22 al restaurar el fixture después de terminar las pruebas. El código de salida del proceso de tests no llegó a guardarse; su log conserva NUnit1pass. Se comprobó que el archivo instrumentado no estaba truncado, se retiró el bloque temporal con apply_patch y su hash volvió a coincidir exactamente con el respaldo. EXIT.json preserva el fallo operativo; no se transforma en un exit0 del comando original.

Este resultado apoya la reparación del arranque en este host; no garantiza ausencia de fallos raros ni cierraC03. Las respuestas del modelo, UI, voz y recursos conjuntos no se midieron. La encuesta sigue26cubiertos/716abiertos/0noaplicables. Fuente705+712 sin adoptar hasta completar Full y regresión de producto.
''',encoding='utf-8')
print(json.dumps({k:result[k] for k in ['ready','failed_startups','initialize_seconds','candidate_sources_unchanged','fixture_restored','temporary_helper_removed']}))
