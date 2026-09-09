"""Adopt corrected combined source after Full; leave original646 red intact."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
out = base/'astra-window-regression651'
assert not (out/'RESULT.json').exists()
assert read(base/'astra-context-source646/RESULT.json')['full_exit'] == 1
temp = Path(os.environ['TEMP'])
assert (temp/'c03-window651-full-exit.txt').read_text().strip() == '0'
full = (temp/'c03-window651-full.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Full' in full
dotnet = re.findall(r'Correctas! - Con error:\s*(\d+), Superado:\s*(\d+), Omitido:\s*(\d+), Total:\s*(\d+), Duración: (.+?) - (\S+\.dll)', full)
assert len(dotnet) == 5 and not sum(int(x[0]) for x in dotnet)
python = re.findall(r'(\d+) passed, (\d+) skipped, (\d+) subtests passed in ([\d.]+)s', full)
assert len(python) == 1
py_pass, py_skip, py_sub, py_seconds = python[0]
sources = read(out/'SOURCE.json')
assert all(sha(root/p) == value for p, value in sources['sources'].items())
for original, target in [('c03-window651-fast.log', 'FAST.log'), ('c03-window651-pins.log', 'DECLARATIONS.log'), ('c03-window651-full.log', 'FULL.log')]:
    (out/target).write_bytes((temp/original).read_bytes())
result = {'utc': datetime.now(timezone.utc).isoformat(), 'adopted': True, 'full_exit': 0,
    'python': {'passed': int(py_pass), 'skipped': int(py_skip), 'subtests': int(py_sub), 'seconds': float(py_seconds)},
    'dotnet': [dict(zip(['failed', 'passed', 'skipped', 'total', 'duration', 'suite'], [int(x[0]), int(x[1]), int(x[2]), int(x[3]), x[4], x[5]])) for x in dotnet],
    'dotnet_printed_omissions': len(re.findall(r'^\s*Omitidas ', full, re.MULTILINE)),
    'r456_passed': 1408, 'scope_passed': 97, 'owners': {'passed': 3521, 'subtests': 121, 'skipped': 0, 'seconds': 67.18},
    'declarations': {'passed': 17, 'environmental_skipped': 1},
    'fast_exit': 0, 'source_unchanged_during_full': True, 'source_files': sources['sources'],
    'git_source_files_lf': {p: hashlib.sha256((root/p).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in sources['sources']},
    'source_encoding_note': 'source_files pins the validated worktree bytes; git_source_files_lf pins the LF repository representation required by existing .gitattributes. No semantic source edit follows Full.',
    'context646_included': True, 'original_full646_preserved_red': True,
    'product647': {'correct': 18, 'total': 20, 'contextual_reads_repaired': 4, 'before651': True},
    'goal_complete': False, 'survey': {'covered': 25, 'open': 717, 'not_applicable': 0}}
net_pass = sum(r['passed'] for r in result['dotnet'])
net_skip = sum(r['skipped'] for r in result['dotnet'])
note = f'''# 651: regresión de ventanas reparada; conjunto con646 validado

La restricción633 perdió24peticiones de R4/R5/R6. Todas pasan antes de d5757c69 y fallan desde ese commit, conservando sus oráculos originales. Se recuperan front window, ventana frontal, por encima del resto y las lecturas del singular ventana en enumeraciones y sus cláusulas de lectura. Visible, plural, nombre de aplicación o ventana física no se convierten en foco. No se cambian expectativas, catálogo, modelo, perfil ni provider.

Validación:1408pruebas R4/R5/R6;97controles focales;3521dueñas+121subpruebas/0skips (67,18s). Declaraciones17pases/1skip ambiental. Fast exit0. Full exit0: Python{py_pass}pases/{py_skip}skips+{py_sub}subpruebas ({py_seconds}s); .NET{net_pass}pases/{net_skip}skip agregado y{result['dotnet_printed_omissions']}omisiones opt-in impresas aparte. No se cuentan skips como pases. La fuente permanece idéntica duranteFull.

Incluye646: la referencia se resuelve desde preguntas del usuario y se conserva hasta los argumentos, usando el historial existente del shell, sin estado nuevo ni frases visibles fijas.647, ejecutado antes de651, verificó18/20finales y4referencias recuperadas; no es una nueva corrida sobre651. Sus2defectos siguen abiertos: running sin observación del proceso y foco inglés respondido en español.649 conserva7fallos del contrato factual.646 queda sellado con su Full rojo original; la adopción del conjunto corregido se acredita aquí.

Encuesta25cubiertos/717abiertos/0NA. Sin cierre global, mínimo deRAM/VRAM ni crédito conjunto deUI/voz. Próximo:650 sobre primer borrador factual, reparación de alcance del compositor; idioma, encuesta, UI real, loopback/AEC, recuperación yFull final siguen pendientes. Ninguna decisión pendiente del dueño.
'''
seal(out, home, result, note, [])
state = read(base/'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), activeValidation=None,
    checkpoint=f'651Full0:Python{py_pass}/{py_skip}skips+{py_sub}subtests,.NET{net_pass}/{net_skip}skip;646rojo conservado.25/717/0.',
    continuation='Publicar646–649+651 tras auditoría de bytes.650 diagnóstico factual preparado/no ejecutado, requiereFull651. Después conservar hechos y alcance en compositor, resolver idioma has. UI/voz/encuesta/recuperación/Full final pendientes.',
    publishedSourceCommit='pending_publication_of_validated_source651', pendingOwnerClarification=None,
    previousGoalTurnClassification='progress', previousGoalTurnClassificationReason='24 foreground regressions repaired without oracle changes; combined contextual source passes Full.')
write(base/'RELEVO_ACTIVO.json', state)
(base/'HANDOFF.md').write_text('# Handoff C03 — 651 validada, publicación pendiente\n\n'+note, encoding='utf-8', newline='\n')
print({'source_adopted': 651, 'python': result['python'], 'dotnet_passed': net_pass, 'dotnet_skipped': net_skip, 'goal_complete': False})
