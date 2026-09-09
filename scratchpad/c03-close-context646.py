"""Adopt the contextual read only after the combined source passes Full."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
out = base/'astra-context-source646'
assert not (out/'RESULT.json').exists()
temp = Path(os.environ['TEMP'])
assert (temp/'c03-context646-full-exit.txt').read_text().strip() == '0'
full = (temp/'c03-context646-full.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Full' in full
dotnet = re.findall(r'Correctas! - Con error:\s*(\d+), Superado:\s*(\d+), Omitido:\s*(\d+), Total:\s*(\d+), Duración: (.+?) - (\S+\.dll)', full)
assert len(dotnet) == 5 and not sum(int(x[0]) for x in dotnet)
python = re.findall(r'(\d+) passed, (\d+) skipped, (\d+) subtests passed in ([\d.]+)s', full)
assert len(python) == 1
py_pass, py_skip, py_sub, py_seconds = python[0]
prereg = read(out/'PREREG.json')
assert all(sha(root/p) == value for p, value in prereg['sources'].items())
assert read(base/'astra-context-product647/RESULT.json')['correct'] == 18
for original, target in [('c03-context646-fast.log', 'FAST.log'), ('c03-context646-pins.log', 'DECLARATIONS.log'), ('c03-context646-full.log', 'FULL.log')]:
    (out/target).write_bytes((temp/original).read_bytes())
result = {'utc': datetime.now(timezone.utc).isoformat(), 'adopted': True, 'full_exit': 0,
    'python': {'passed': int(py_pass), 'skipped': int(py_skip), 'subtests': int(py_sub), 'seconds': float(py_seconds)},
    'dotnet': [dict(zip(['failed', 'passed', 'skipped', 'total', 'duration', 'suite'], [int(x[0]), int(x[1]), int(x[2]), int(x[3]), x[4], x[5]])) for x in dotnet],
    'dotnet_printed_omissions': len(re.findall(r'^\s*Omitidas ', full, re.MULTILINE)),
    'owners': {'passed': 3505, 'subtests': 121, 'skipped': 0, 'seconds': 63.07},
    'declarations': {'passed': 17, 'environmental_skipped': 1},
    'targeted_passed': 50, 'fast_exit': 0, 'source_unchanged_during_full': True,
    'source_files': prereg['sources'], 'product647': {'correct': 18, 'total': 20, 'contextual_reads_repaired': 4},
    'goal_complete': False, 'survey': {'covered': 25, 'open': 717, 'not_applicable': 0}}
write(out/'RESULT.json', result)
net_pass = sum(r['passed'] for r in result['dotnet']); net_skip = sum(r['skipped'] for r in result['dotnet'])
note = f'''# Fuente 646 adoptada — continuidad de referencia hasta los argumentos

La mente resuelve referencias acotadas desde preguntas del usuario y conserva el pedido original. Selección y argumentos usan la misma resolución; el shell pasa el historial existente a la extracción. Un tema nuevo o una referencia sin resolver corta la cadena. Identidad del catálogo y esquema se comprueban otra vez; ninguna respuesta del asistente aporta autoridad de identidad. No hay otro estado, modelo, proceso residente ni frase final fija.

Validación: 46 rojos iniciales → 50 focales verdes; 3505 dueñas +121 subpruebas, 0 skips (63,07 s). Declaraciones:17 pass/1 skip ambiental, separado de los pases. Fast exit0, Release21,24s. Full exit0: Python {py_pass} pass/{py_skip} skips +{py_sub} subpruebas ({py_seconds}s); .NET {net_pass} pass/{net_skip} skip agregado, cero fallos. Hay además {result['dotnet_printed_omissions']} omisiones impresas de pruebas opt-in, registradas aparte. Fuente comprobada intacta durante Full. Ninguna suite, umbral o prueba se relajó. Esta adopción no cierra C03.

647 repite exactamente642:18/20finales frente a15. Las cuatro referencias ahora llegan con nombre correcto a una lectura nueva;16lecturas por aplicación conservan nombre/cantidad. Sigue abierto t15: el compositor añade que Spotify está running sin observar procesos. También persiste el foco inglés→español. H0040 queda abierto por la afirmación sin respaldo; encuesta25/717/0.648 aclara que WhatsApp tiene ventanas en dos procesos del mismo paquete; la identidad se consultó después de las instantáneas, con compatibilidad de nombre/creación explícita.

647: GPU3497,559MiB/RAM2290,973MiB/91,563s incluyen NativeAOT; sin infracciones. Sin UI/voz conjunta ni mínimo global. Siguiente: reparación factual del compositor;649 confirma que el validador también acepta contradicciones de instalación/cantidad, no sólo liveness. El idioma has es otra frontera. Continúan encuesta, rutas de prosa, UI real, loopback/AEC, recuperación y Full final.
'''
(out/'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
write(out/'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
with (root/'.gitattributes').open('a', encoding='utf-8', newline='\n') as f:
    f.write('/artifacts/comprobaciones/C03/astra-context-source646/** -text\n')
with (base/'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as f: f.write('\n\n'+note)
state = read(base/'RELEVO_ACTIVO.json')
state.pop('activeValidation', None)
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint=f'646 validada Full0:Python{py_pass}/{py_skip}skips+{py_sub}subtests,.NET{net_pass}/{net_skip}skip.647:18/20,4referencias reparadas.649carenciafactual.25/717/0.',
    continuation='Publicar646–649 y actualizar H0040 sin cambiar cobertura. Después reparar conservación factual del compositor: no inferir procesos desde instalación/ventanas ni invertir installed/count. No más ajuste de prompt645. Foco inglés has sigue pendiente. Sin validaciones o campañas activas.',
    publishedSourceCommit='pending_publication_of_validated_source646', pendingOwnerClarification=None,
    previousGoalTurnClassification='progress', previousGoalTurnClassificationReason='Contextual references verified in product and combined source validated with Full; independent649 exposes factual validation boundary.')
write(base/'RELEVO_ACTIVO.json', state)
(base/'HANDOFF.md').write_text('# Handoff C03 — 646 validada, publicación pendiente\n\n'+note,
    encoding='utf-8', newline='\n')
print({'source_adopted': 646, 'python': result['python'], 'dotnet_passed': net_pass, 'dotnet_skipped': net_skip, 'goal_complete': False})
