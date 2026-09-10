"""Publish bounded composition selection only after its owners and Fast pass."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'DENSE_INVENTORY764'
now = datetime.now(timezone.utc).isoformat()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
read = lambda path: json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert subprocess.check_output(['git', 'branch', '--show-current'], text=True).strip() == 'Goal-c03'
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only']).strip()
pins = read(out / 'SOURCE_PINS.json')
assert all(sha(root / path) == digest for path, digest in pins.items())
assert all(sha(root / path) == digest for path, digest in read(base / 'SEMANTIC_INVENTORY760/SOURCE_PINS.json').items())
for name in ['owners', 'fast']:
    data = (Path(os.environ['TEMP']) / f'c03-dense764-{name}.log').read_bytes().replace(b'\r\n', b'\n')
    assert (b'Superado:   136, Omitido:     0' if name == 'owners' else b'source_quality_gate_passed: mode=Fast') in data
    (out / f'{name}.log').write_bytes(data)
write(out / 'VALIDATION.json', {
    'utc': now,
    'owner_command': 'dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal --filter FullyQualifiedName~PlannerAppBoundaryTests',
    'owners': {'passed': 136, 'failed': 0, 'skipped': 0, 'duration_display': '6s', 'new_cases': 22},
    'fast_command': 'scripts/test_source_quality.ps1 -Mode Fast', 'fast_exit_code': 0,
    'source_pins_unchanged': True, 'python760_pins_unchanged': True,
    'full_new': False, 'full_reason': 'Only C# source changed; no shared protocol or Python change. Final Full remains required; no C03 closure is claimed.',
    'real_model_product_regression_pending': 'STATUS_BATCH765, same73 cases and frozen criteria',
})
write(out / 'ADOPTION.json', {'utc': now, 'status': 'source_adopted_after_owners_and_fast',
    'source_pins': 'SOURCE_PINS.json', 'commit': 'Containing commit', 'model_or_global_timeout_changed': False,
    'survey_counts': {'covered': 26, 'open': 716, 'not_applicable': 0}, 'coverage_added': 0})
(out / 'REPORT.md').write_bytes('''# Presupuesto de composición para inventarios verificados

La frontera compartida de composición reconoce ahora los inventarios de window.resolve que llegan dentro del JSON de situation. Cuando están verificados y han tenido éxito, usa los umbrales densos existentes: ocho entradas o512caracteres de inventario. Los datos y el contrato factual no se modifican. No depende del nombre del modelo ni de una forma de respuesta.

Esto reutiliza el límite existente de10s en la App, nueve para el modelo en GPU. Las respuestas ordinarias conservan5s/4s; CPU mantiene sus dos presupuestos60/130s. La selección no concede éxito a datos no verificados ni garantiza que cualquier lista termine dentro del plazo. El problema medido está en762–763: una lista completa20/24 tardaba4,141s y recibía cuatro, seguida de reintentos.

Validación:136 pruebas dueñas,0 fallos,0 skips;22 controles nuevos, incluidos los límites7/8, tamaños0/1/20/50, identidad larga, verificación fallida o mal tipada, JSON inválido y paso por ModelMessageComposer.CreateFacts. Fast pasó y los pins de fuente permanecieron intactos. Comandos y logs en VALIDATION.json. No Full nuevo en esta adopción sólo C#; el Full final sigue pendiente.

Siguiente: regresión registrada765 de los mismos73 casos completos, con hechos frescos, para comprobar entrega y regresiones. No es una comparación nativa de modelos ni acredita UI/voz o consumo conjunto. Fuente Python760, modelo, sampler y prompt permanecen intactos. Encuesta26cubiertos/716abiertos/0NA; C03 activo.
'''.encode('utf-8'))
checkpoint = ('764adoptado: selector de presupuesto reconoce inventario observado verificado en situation; '
    'umbrales8/512 y presupuestosexistentes, sin cambiode modelo/prompt/facts. '
    '136dueñas pass/0fail/0skip y Fast exit0;2fuentes764 y6pins760 intactos. '
    'Publicar y ejecutar driver765 preparado con73casos completos, no editar durante la corrida.26/716/0, C03activo.\n\n')
cp = base / 'CHECKPOINT.md'
pending = cp.with_suffix('.pending.md')
pending.write_bytes(checkpoint.encode('utf-8') + cp.read_bytes())
pending.replace(cp)
hp = base / 'HANDOFF.md'
handoff = hp.read_text(encoding='utf-8').replace(
    'Siguiente: src/Baxy.App/MindSidecarClient.cs:170 SelectMessageCompositionTimeout. Clasifica dense sólo por requiredFacts>=8/>=512caracteres o partialMission; window.resolve20 llega en situation JSON string, no requiredFacts. Usar política dense existente(10sApp/9smodelo) para inventario sustancial verificado, con contrastes dueños PlannerAppBoundaryTests.cs:371–462. No timeoutglobal/prompt/modelo nuevo. Root implementa; revisión acotada sólo lectura ya recibida.',
    '764adoptado: MindSidecarClient selecciona política dense existente para inventarios verificados de situation.136dueñas verdes/0skips, Fast exit0, pins2fuentes764+6fuentes760 intactos. DENSE_INVENTORY764/REPORT.md y VALIDATION.json. Publicar y ejecutar scratchpad/c03-status-batch765.py con Python registrado:73casos completos originales, mismos criterios/runtime, pins760+764. Preparador765 ya ejecutado; no repetir. No editar fuente durante la corrida; registrar sesión/PID y adjudicar terminales/facts. Sin UI/voz/cobertura automática.')
assert handoff != hp.read_text(encoding='utf-8')
hp.write_bytes(handoff.encode('utf-8'))
rp = base / 'RELEVO_ACTIVO.json'
r = read(rp)
r.update(confirmedAtUtc=now, checkpoint=checkpoint.strip(), activeValidation=None,
    workStatus='dense_inventory764_adopted_pending_publication',
    continuation='Publish validated764 then run prepared registered73 driver765; do not edit source during inference.')
write(rp, r)
paths = [out / name for name in ['SOURCE_PINS.json','PLAN.json','owners.log','fast.log','VALIDATION.json','ADOPTION.json','REPORT.md']]
paths.extend(root / 'scratchpad' / name for name in ['c03-prepare-status765.py','c03-status-batch765.py','c03-adopt-dense764.py'])
paths.append(base / 'INVENTORY_OUTPUT763/PUBLICATION.json')
artifact_pins = {p.relative_to(root).as_posix(): sha(p) for p in paths}
write(out / 'PINS.json', artifact_pins)
paths.append(out / 'PINS.json')
paths.extend(root / path for path in pins)
paths.extend(base / name for name in ['CHECKPOINT.md','HANDOFF.md','RELEVO_ACTIVO.json'])
relative = [p.relative_to(root).as_posix() for p in paths]
subprocess.run(['git','add','--',*relative], check=True)
assert set(subprocess.check_output(['git','diff','--cached','--name-only'],text=True).splitlines()) == set(relative)
for path, digest in {**artifact_pins, **pins}.items():
    assert hashlib.sha256(subprocess.check_output(['git','show',':'+path])).hexdigest() == digest, path
subprocess.run(['git','diff','--cached','--check'], check=True)
print(json.dumps({'source_pins':len(pins),'artifact_pins':len(artifact_pins),'staged':len(paths)}))
