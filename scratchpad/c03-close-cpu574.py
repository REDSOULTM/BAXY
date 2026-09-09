"""Checkpoint validated native CPU topology and its exact owner evidence."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-cpu-physical574'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


for part in ('provider', 'integration', 'fast'):
    (out / (part + '.log')).write_bytes((Path(os.environ['TEMP']) / f'c03-cpu574-{part}.log').read_bytes())
assert 'Superado:    31' in (out / 'provider.log').read_text(encoding='utf-8-sig')
assert 'Superado:    80' in (out / 'integration.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out / 'fast.log').read_text(encoding='utf-8-sig')
note = '''# Handoff C03 — fuente574 validada

Se adopta physicalCoreCount leído por GetLogicalProcessorInformationEx(RelationProcessorCore), independiente del conteo lógico de GetActiveProcessorCount. Búfer acotado y liberado en finally; registros variables validados por tipo, tamaño y grupos. No proceso CIM nuevo, división por SMT ni dato inferido del nombre. Un fallo real de topología produce measurement_failed para CPU y conserva otras métricas; conteo imposible produce invalid_measurement. El contrato admite null para observaciones anteriores sin ese dato; Core conserva desconocido, nunca fabrica núcleos.

Pruebas proveedor/topología:31pass/0skip,80ms, incluida lectura real8 físicos/16 lógicos, mezcla SMT/grupos, datos truncados y fallos aislados. Integración SystemStatusHandler/GPU:80pass/0skip,172ms, transporte de12 físicos/24 lógicos, null y rechazos de conteos imposibles. Fast verde completo, Release6,15s,0advertencias/errores. Sin cambio Python ni runtime; árbol STT564e880c9d37bf3c26965006e34c98288a8793d7c37313c59e34271cd595d0b6/403 intacto. Full final pendiente; la regla actual pide Full por adopción que cambie C# y Python juntos o por cierre final, no por cada fuente.

Heredado573:12 EOS; agregar sólo el dato medido corrige la distinción física/lógica en ES/EN y en controles sintéticos6/8 con otro modelo de CPU. El uso total sigue mal atribuido a BAXY en español, sin regresión nueva. Producto575 pendiente, seis variantes CPU más uso/red/audio; sin acreditar H0007 todavía.

Fuente571 publicada3c368a55 y verificada572: cuatro respuestas correctas (audio ES/EN y controles), dos nuevas compuestas hora/silencio no resueltas. ES falla interpretación; EN sólo lleva audio.status al escritor. Advertencias de ausencia16/17 corresponden al fallo sin observaciones, no al caso reparado. GPU5723497,559MiB/RAM2386,109MiB;573 nativoGPU3497,559MiB/RAM720,555MiB. No son recursos conjuntos finales ni UI/voz.

Goal activo, nada pendiente del dueño. Encuesta12 cubiertos/730 abiertos/0NA, original742/rev1248 intacto. BAXY manual cerrado; main5f572ee1b48cb5e2543ee5e06510e51057c9c845 intacto. Publicar574 con dueñas verdes, cerrar build servers propios y ejecutar575. Luego localizar primera transformación de hora+silencio; quedan sujeto CPU, GPU/unidades, capacidad/recibos de memoria, progreso, curiosidades, encuesta/ocho rutas, UI real, loopback completo, AEC como supresión, recursos conjuntos, aceptación y Full final. Full526 rojo original reparado por dueñas528–531, no presentar como Full verde. C08 humano sólo evidencia y reanudación.
'''
(out / 'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
write(out / 'RESULT.json', {'adopted': True, 'provider_tests': {'passed': 31, 'skipped': 0, 'milliseconds': 80}, 'integration_tests': {'passed': 80, 'skipped': 0, 'milliseconds': 172}, 'fast': 'passed', 'release_seconds': 6.15, 'source_languages_changed': ['C#'], 'product': 'pending575', 'survey': {'covered': 12, 'open': 730, 'not_applicable': 0}, 'source': 'https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getlogicalprocessorinformationex'})
files = ['src/Baxy.Providers.Windows/SystemStatus/' + name for name in ('WindowsSystemStatusProbe.cs', 'WindowsSystemStatusProvider.cs', 'SystemStatusContracts.cs')]
files += ['src/Baxy.Core/Operations/' + name for name in ('CoreOperationModels.cs', 'SystemStatusHandler.cs')]
files += ['tests/Baxy.Providers.Windows.Tests/SystemStatus/' + name for name in ('WindowsSystemStatusProviderTests.cs', 'WindowsProcessorTopologyTests.cs')]
files += ['tests/Baxy.Integration.Tests/SystemStatusHandlerTests.cs']
write(out / 'SOURCES.json', {name: sha(root / name) for name in files})
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
with (root / '.gitattributes').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('/artifacts/comprobaciones/C03/astra-cpu-physical574/** -text\n')
(base / 'HANDOFF.md').write_text(note, encoding='utf-8', newline='\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n' + note)
state = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
state.update(checkpoint='574: native physical CPU count adopted; provider31/integration80 pass,0skips; Fast green. Survey12/730/0.', continuation='Publish574, verify CPU product575, then compound clock/mute first incorrect transform. Final C03 obligations open.', confirmedAtUtc=datetime.now(timezone.utc).isoformat())
write(base / 'RELEVO_ACTIVO.json', state)
print('574 validated; ready to publish and run product575.')
