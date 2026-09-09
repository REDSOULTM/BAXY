from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-os-provider416'
shutil.copyfile(Path(os.environ['TEMP']) / 'c03-os416-fast.log', out / 'fast.log')
assert 'source_quality_gate_passed: mode=Fast' in (out / 'fast.log').read_text(encoding='utf-8-sig')
report = '''# 416 — nombre de Windows observado y transportado; pruebas dueñas y Fast verdes

Sustituida la lectura OS RtlGetVersion por Win32_OperatingSystem local mediante
ExternalProcessRunner existente. Lee Caption, Version y ProductType, mantiene
arquitectura nativa. Cinco segundos máximos, cancelación propagada; el runner
oculta y termina el proceso en fallo. JSON inválido, error y timeout producen
fallo sanitizado del scope OS; otros scopes conservan sus mediciones. No caché,
tabla de versiones, respuesta fija, nueva operación ni dependencia añadida.
Se retiraron los constantes y el import nativo que quedaron sin consumidor.

Caption obligatorio viaja por OperatingSystemReading, OperatingSystemStatus y
SystemStatusOperatingSystemResult hasta el JSON verificado. Proveedor valida
longitud/control; Core exige texto normalizado y no vacío. Observación CIM local
en tres procesos: 0,415 / 0,354 / 0,355 segundos, siempre Windows 11 Home Single
Language / 10.0.26200 / workstation. Ver CIM_OBSERVATION.json.

`dotnet test tests/Baxy.Providers.Windows.Tests -c Release --nologo -v:minimal
--filter 'FullyQualifiedName~WindowsOperatingSystemProbeTests|FullyQualifiedName~WindowsSystemStatusProviderTests'`
→ 36 pass / 0 skips, 74 ms. Incluye captions Windows 10/11/Server/localizado,
NT 10.0 compartido, dato inválido, fallo/timeout parcial y cancelación en vuelo.

`dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal
--filter 'FullyQualifiedName~SystemStatus'` → 193 pass / 0 skips, 6 s.
Incluye contrato, handler, handshake y consumidores de recursos; captions
inválidos no pasan verificación y el resultado conserva el caption del servidor.

`.\\scripts\\test_source_quality.ps1` → Fast verde completo, build Release 18,76 s,
0 warnings / 0 errors. Fallos previos conservados: CA1826 en un test (corregido
acceso indexado) y saltos CRLF introducidos al editar tres tests (restaurados LF).
La corrección LF no altera su comportamiento; no se repitieron suites por ella.
No Full durante reparación. Fuente previa de audio EndpointName y todo WIP ajeno
se preservan. No modelo promovido ni voz/UI/aceptación certificadas.

Herencia, mecanismo Microsoft y comparación 1/4→4/4 están en
astra-os-caption415/RESULT.md. Siguiente: producto417 conserva los seis turnos411
y añade OS ES, RAM EN y CPU ES. No se da por resuelto antes de leer los finales.
'''
(out / 'RESULT.md').write_text(report, encoding='utf-8', newline='\n')
sources = ['src/Baxy.Providers.Windows/SystemStatus/WindowsSystemStatusProbe.cs', 'src/Baxy.Providers.Windows/SystemStatus/WindowsSystemStatusProvider.cs', 'src/Baxy.Providers.Windows/SystemStatus/SystemStatusContracts.cs', 'src/Baxy.Core/Operations/CoreOperationModels.cs', 'src/Baxy.Core/Operations/SystemStatusHandler.cs', 'tests/Baxy.Providers.Windows.Tests/SystemStatus/WindowsOperatingSystemProbeTests.cs', 'tests/Baxy.Providers.Windows.Tests/SystemStatus/WindowsSystemStatusProviderTests.cs', 'tests/Baxy.Integration.Tests/SystemStatusHandlerTests.cs', 'tests/Baxy.Integration.Tests/GpuSystemStatusHandlerTests.cs']
paths = [out / n for n in ['RESULT.md', 'provider.log', 'integration.log', 'compile-failure.log', 'fast-eol-failure.log', 'fast.log', 'CIM_OBSERVATION.json']]
paths += [root / n for n in sources]
(out / 'PINS.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2)+'\n', newline='\n')
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    p = base / name
    s = p.read_text(encoding='utf-8').replace('415 completado; implementación OS416 pendiente', '416 implementado y validado; producto417 preparado')
    start = s.index('Siguiente: sustituir')
    end = s.index('\n\nPendiente:', start)
    s = s[:start] + '''416 sustituye Rtl por CIM local con runner existente (5 s y cancelación);
Caption obligatorio hasta resultado verificado. 36 proveedor/193 integración,
0 skips; Fast verde/build18,76 s/0 warnings/errors. Pruebas de cancelación,
fallo parcial y dato inválido. CIM real 0,354–0,415 s; no modelo/voz medidos.
RESULT/PINS en astra-os-provider416. Producto417 preparado aún sin ejecutar:
py -X utf8 scratchpad/c03-os-product417.py. Misma secuencia411 más OS ES/RAM/CPU.
No editar fuente mientras corre; leer eventos privados, journal y composición.
''' + s[end:]
    p.write_text(s, encoding='utf-8', newline='\n')
p = base / 'RELEVO_ACTIVO.json'
relay = json.loads(p.read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint='Source416 OS caption implemented; 36 provider/193 integration zero skips and Fast green.', continuation='Run prepared product417 (same411 six plus OS ES/RAM/CPU), then inspect observed facts and final prose. Full C03 active.')
p.write_text(json.dumps(relay, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print('416 validated and recorded; 417 ready')
