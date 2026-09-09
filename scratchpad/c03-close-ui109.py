from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-ui109'
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
prereg = json.loads((out / 'PREREG.json').read_text(encoding='utf-8-sig'))
actual = {p: sha(root / p) for p in prereg['files']}
changes = {p:{'preregistered':old,'afterLaunch':actual[p]} for p,old in prereg['files'].items() if actual[p] != old}
registration = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
assert sha(registration) == prereg['registrationSha256']
(out / 'SOURCE_AFTER.json').write_text(json.dumps({'changesSincePreregistration':changes, 'files':actual, 'registrationUnchanged':True}, indent=2), encoding='utf-8', newline='\n')
for name in ['dotnet','fast','build']:
    shutil.copyfile(Path(os.environ['TEMP']) / f'c03-ui108-{name}.log', out / f'source108-{name}.log')
shutil.copyfile(Path(os.environ['TEMP']) / 'c03-ui109-launch.log', out / 'launch.log')
current = '''## Estado actual y siguiente acción

Fuente108/UI109 verificada: fallo real del servidor muestra Error en el grafo y
Response error en región alert, mantiene entrada utilizable; al restaurar el mismo
servidor responde Son las07:02. y retira el error. PRUEBAS_UI109.md/ASTRA-TRAMO-108.md.
HasCompositionError notifica, state/ bootstrap proyectan error; cola pendiente
proyecta thinking sin bloquear entrada. Diagnóstico tipado conservado, código
interno retirado de actividad. Etiquetas de estado, no prosa de respuesta fija.
Mismo reducer React; sin otro bridge/modelo/prompt ni autoridad.

pnpm build exit0;169tests .NET pass/0skips/6s,94729exit0; Fast77667exit0,
Release19,29s,0avisos/errores. Sello38archivos
99FF9838C07CE32F25F329AACF830F62D8DD70C5931E26C2EC483B710B2CA657.
ORIGIN/ADR-0008 actualizados; bundles index-Dh8gdcnz.js e index-B7EBy9jN.css.
No repetir verdes sin nuevo cambio/fallo ni Full durante reparación.

UI109 launcher4252exit0 (App/Core AOT), monitor94971exit0:169,50s,
GPU3505,1484375MiB,RAM5514,2890625MiB; sin voz, arranque previo excluido.
Suspensión99128exit0:80,16s, reanudado a10:02:09.671UTC. App37276/server20156
terminados con ruta verificada tras guardar respuesta. Sin procesos propios.
Sky3148270 obsoleto. Core12A2E21648EA14D059ACE672C8C44E867368016D98BC940F10D19894F95C0008.
Registro intacto; Qwen3.5 override/wake0, no promoción ni audio físico.

UI107: recuperación real y confirmación/cancelación/cierre fieles; fixture31896
conservada al cancelar y cerrada por BAXY al confirmar. PRUEBAS_UI107.md. No repetir.
103/UI104: progreso visible ES/EN y ocho finales fieles; 106 averías/restauración
conductor mismoPID. Reportes conservados; no son reserva100 ni aceptación acústica.

Siguiente: comprobación de voz/audio físico y4GB combinado con este candidato,
heredando evidencia45/83 antes de preparar otra corrida. Sin subagentes ni otra
colección de prompts. Preview105 vistos0–154/239; falta revisar155–238 y seleccionar
100humanos literales/contextuales frescos, congelar antes de ejecutar. Tres ingleses
confirmados por dueño registrados; no preguntar ni extender a742. Promoción con
regresión de roles, runtime registrado, continuidadC04–C09, Full final verde y
publicación fuera de main siguen pendientes. C03 EN_CURSO, sin cierre parcial.

'''
for name in ['CHECKPOINT','HANDOFF']:
    with (base / f'{name}_HISTORICO_HASTA108.md').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write((base / f'{name}.md').read_text(encoding='utf-8-sig'))
checkpoint = base / 'CHECKPOINT.md'
text = checkpoint.read_text(encoding='utf-8-sig')
start, end = text.index('## Estado actual'), text.index('## Decisiones y pruebas')
text = text[:start] + current + text[end:]
tail = text.find('\nUI109 ACTIVO:')
if tail >= 0:
    text = text[:tail] + '\n'
checkpoint.write_text(text, encoding='utf-8', newline='\n')
header = '''# Handoff C03 — fuente108/UI109 — 2026-09-07

Tarea01a07974-2a33-7ed3-ba87-2436944e8115, Goal-c03,
HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. Goal activo e íntegro;
CHECKPOINT manda. Sin commit/push/main ni subagentes; preservar WIP/evidencia.

'''
(base / 'HANDOFF.md').write_text(header + current + '''Python312 para pytest, resolvedor predeterminado para calidad, py main.py GUI.
UI sólo Computer Use sky/node_repl. Ventana anterior muerta; obtener una nueva.
''', encoding='utf-8', newline='\n')
relay_path = base / 'RELEVO_ACTIVO.json'
relay = json.loads(relay_path.read_text(encoding='utf-8-sig'))
relay.update(confirmedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    checkpoint='Fuente108/UI109: error visible y recuperación real;169tests/Fast verdes; C03 EN_CURSO',
    continuation='Sin procesos propios ni suspensión. Heredar voz45/83 para audio físico y4GB combinado, luego reserva100/promoción/cierre completo. CHECKPOINT manda. No repetir paneles verdes ni Full durante reparación.')
relay_path.write_text(json.dumps(relay, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
paths = [base / 'ASTRA-TRAMO-108.md', base / 'PRUEBAS_UI107.md', base / 'PRUEBAS_UI109.md',
    out / 'PREREG.json', out / 'SOURCE_AFTER.json', out / 'RUNTIME_AFTER_LAUNCH.json',
    out / 'RESOURCES.json', out / 'RESUMED.json', root / 'src/Baxy.FieldUi/ORIGIN.md']
(base / 'TRAMO108_109_PINS.json').write_text(json.dumps({'scope':'Source108 owner tests169/Fast, UI109 real error and recovery; C03 remains incomplete', 'files':{p.relative_to(root).as_posix():sha(p) for p in paths}}, indent=2), encoding='utf-8', newline='\n')
print(json.dumps({'preregisteredFileChanges':changes, 'checkpoint':'108/UI109, no active processes'}, ensure_ascii=False))
