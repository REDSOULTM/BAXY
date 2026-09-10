"""Record validated source760 and stage only the files belonging to this repair."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'SEMANTIC_INVENTORY760'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert git('branch', '--show-current').decode().strip() == 'Goal-c03'
assert not git('diff', '--cached', '--name-only').strip()
assert git('rev-parse', 'main').decode().strip() == '5f572ee1b48cb5e2543ee5e06510e51057c9c845'
pins = json.loads((OUT / 'SOURCE_PINS.json').read_text(encoding='utf-8'))
assert all(sha(ROOT / path) == digest for path, digest in pins.items())
for name in ['integrity-final', 'fast']:
    log = Path(os.environ['TEMP']) / f'c03-inventory760-{name}.log'
    data = log.read_bytes()
    assert (b'474 passed, 1 skipped' if name == 'integrity-final' else b'source_quality_gate_passed: mode=Fast') in data
    (OUT / f'{name}.log').write_bytes(data.replace(b'\r\n', b'\n'))
runtime = 'C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe -X utf8 -m pytest '
write(OUT / 'VALIDATION.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'new_tests': 119,
    'broad_owner_command': runtime + 'tests/test_c03_inventory_semantic_projection.py tests/test_c03_window_inventory.py tests/test_c03_window_facts.py tests/test_c03_window_state_facts.py tests/test_c03_window_prose_projection.py tests/test_c03_window_focus_apposition.py tests/test_c03_observed_window_vocabulary.py tests/test_effect_intent.py tests/test_c03_request_preservation.py tests/test_turn_policy.py tests/test_planner.py -q',
    'broad_owners': {'passed': 4303, 'subtests_passed': 121, 'seconds': 72.25, 'scope': 'Before the final10 factual-scope contrasts; final affected owners below supersede those window checks.'},
    'final_owner_command': runtime + 'tests/test_c03_inventory_semantic_projection.py tests/test_c03_window_inventory.py tests/test_c03_window_facts.py tests/test_c03_window_state_facts.py tests/test_c03_window_prose_projection.py tests/test_c03_window_focus_apposition.py tests/test_c03_observed_window_vocabulary.py -q',
    'final_window_owners': {'passed': 950, 'failed': 0, 'seconds': 4.48},
    'integrity_command': runtime + 'tests/test_c03_inventory_semantic_projection.py tests/test_c03_window_inventory.py tests/test_c03_window_facts.py tests/test_c03_fronted_machine_status.py tests/test_price_v8_veto_damage_by_cause.py tests/test_stt_quality_evaluators.py tests/test_validate_physical_wake_v17_program.py -q',
    'final_integrity': {'passed': 474, 'failed': 0, 'environmental_skips': 1, 'seconds': 5.82,
                        'skip_reason': 'Private blind STT campaign inputs absent; not a pass.'},
    'fast_command': 'scripts/test_source_quality.ps1 -Mode Fast', 'fast_exit_code': 0,
    'release_seconds': 25.13, 'warnings': 0, 'errors': 0, 'final_pins_unchanged': True,
    'suite_counts_overlap': True, 'full_rerun': False,
    'full_reason': 'Only Python source changed; objective requires Full on shared C#+Python adoption and at final closure. Historical Full7 remains historical.',
    'real_model_or_ui_credit': False, 'survey_credit': 0,
})
write(OUT / 'ADOPTION.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'status': 'source_adopted_after_owner_tests_and_fast',
    'commit': 'The commit containing this receipt', 'source_pins_file': 'SOURCE_PINS.json',
    'model_or_budget_promotion': False, 'survey_counts': {'covered': 26, 'open': 716, 'not_applicable': 0},
    'product_acceptance_pending': 'Registered73 product regression, generalized coverage and all remaining C03 closure requirements.',
})
report = '''# Inventario: página explícita y hechos no observados

BAXY conserva el inventario canónico y entrega al redactor una copia que distingue cuántas ventanas contiene la página de cuántas hay en el inventario seleccionado. La enumeración puede haber terminado aunque la página sólo contenga parte del resultado. Si el total no se conoce, permanece desconocido.

Para una petición reconocida de nombres o cantidad, esa copia conserva todas las identidades y sus repeticiones, retirando coordenadas, dimensiones y estados no pedidos. Los controles incluyen páginas de 1, 20 y 50 entradas. Una petición de posición, tamaño, estado o foco conserva sus detalles. La proyección reutiliza la interpretación existente; no añade ejemplos de la encuesta ni un segundo selector.

La observación no registra fechas de apertura. Ahora lo declara al redactor y el verificador rechaza las afirmaciones de recencia o cronología cubiertas por su contrato. Conserva títulos que contengan ese vocabulario y distingue la frescura de una lectura de la edad de las ventanas. No se cambia la respuesta para hacerla pasar. Las comprobaciones se aplican igual a ambas familias de modelos; los dobles de prueba no acreditan calidad de los modelos reales.

El bloqueo está documentado en [753–759](../INVENTORY_PROJECTION759/REPORT.md): quitar geometría no pedida evitó truncar la lista, pero las candidatas aún confundían el alcance o inventaban recencia. Esta fuente adopta la corrección de representación y comprobación; todavía debe medirse su efecto sobre los turnos reales. No se cambia el modelo, su muestreo, los prompts ni los presupuestos.

Validación: 119 controles nuevos. Suite amplia inicial: 4303 pass y 121 subtests. Tras la revisión final, 950 pass en las dueñas de ventanas y 474 pass / 1 skip ambiental en integración de prosa y huellas. Las suites se solapan. El skip corresponde a datos privados STT ausentes y no acredita voz. Fast terminó con exit0; Release25,13s, cero advertencias y errores. Comandos y resultados exactos en VALIDATION.json; fallos intermedios preservados.

Se actualizan las declaraciones actuales STT y V8 contra el programa de 407 archivos. Los sellos históricos y los pins de751 permanecen intactos. SOURCE_PINS.json fija las seis rutas de esta adopción y se verificó que no cambiaron durante la validación final.

Siguiente: la misma categoría registrada de73 turnos, con hechos frescos y perfil aislado, para observar composición y regresiones. No es una comparación nativa K2–Qwen ni una prueba de interfaz o voz. C03 sigue abierto:26 requisitos cubiertos,716 abiertos,0 no aplicables. Faltan la generalización completa, reserva, UI/voz, recursos conjuntos, matriz/continuidad y Full final.
'''
(OUT / 'REPORT.md').write_bytes(report.encode('utf-8'))
checkpoint = ('760 adoptado tras950pass finales de ventana,474pass/1skip ambiental de integridad y Fast exit0/Release25,13s/0advertencias/0errores. '
              '4303pass+121subtests previas con solapamiento;119controles nuevos.6pins fuente intactos. '
              'Programa407=7fbbf3a59f96fdcf799dc50583bb846792908866f990e3443c2b0f33448fd6c9. '
              'Semántica de página explícita, proyección conserva identidades y detalles solicitados; recencia sin fechas rechazada. '
              'No cambia modelo/prompt/presupuesto; sin inferencia nueva ni cobertura. Publicar y seguir categoría73 condriver761.26/716/0, C03 activo.\n\n')
cp = BASE / 'CHECKPOINT.md'
cp.write_bytes(checkpoint.encode('utf-8') + cp.read_bytes())
hp = BASE / 'HANDOFF.md'
old = hp.read_text(encoding='utf-8')
new = '''# Handoff C03 — fuente760 — 2026-09-10

Goal íntegro activo, rama Goal-c03, main intacto. Encuesta742/rev1248:26 cubiertos/716 abiertos/0NA. Sin preguntas pendientes. BAXY manual cerrado; diagnósticos autorizados.

760 adopta proyección factual de página y comprobación de recencia no observada. SEMANTIC_INVENTORY760/REPORT.md, VALIDATION.json y SOURCE_PINS.json contienen alcance, comandos y seis huellas. Programa407=7fbbf3a59f96fdcf799dc50583bb846792908866f990e3443c2b0f33448fd6c9. Las declaraciones vigentes STT/V8 coinciden; no tocar sellos históricos751/v17. Fuente validada y lista para publicar; no editar antes de publicación/regresión.

950pass finales de ventanas;474pass/1skip ambiental de integridad,5,82s;4303pass+121subtests previas,72,25s, con solapamiento. Fast69845 terminal0 recogido;Release25,13s/0warn/0error.119 controles nuevos; fallos iniciales conservados. No Full nuevo por cambio sólo Python; Full final pendiente. Full7 histórico4574.NETpass/1skip agregado+16omisiones opt-in;11399Pythonpass/3skips+466subtests, exit0.

Siguiente: ejecutar scratchpad/c03-status-batch761.py con el Python registrado, después de publicar760. Reutiliza los73casos originales689/729 y criterios sin cambios; pins760, modelo/manifiesto registrado, perfil privado nuevo, wakeoff, lecturas sin efectos. Preparador c03-prepare-status761.py ya ejecutado; no repetirlo. No hay inferencia activa al escribir. Capturar sesión/PID en RELEVO tras lanzar y recoger el mismo proceso. Su resultado es producto sin UI/voz, no ranking nativo ni cobertura automática.

Primera revisión: inventarios H0023/H0103 ahora con proyección compacta y alcance; conservar todos los datos/identidades y rechazar recencia no medida. Después adjudicar los73 y comparar pérdidas por capa con752B. No sumar suites solapadas ni aprobar únicamente por terminal completed.

Otros bloqueos752B: inventario H0209/H0663/EN vetado; foco fiel rechazado; lecturas omitidas/frescura; RAM total llamada disponible; interfaz-up no es Internet; CPU acumulada no es consumo actual. Foco: window_prose_facts.window_subject reconoce la ventana/the window pero no el ventanal; las relativas identificadoras de los dos borradores738 tampoco están ligadas. Reparar estructuralmente con variantes/contrastes tras observar761, no una excepción literal ni editar durante la corrida.

Evidencia753–759 publicadaa4c95c61:754–756 instrucciones solas no reparan truncación;757 reduce1533→678tokens y6,547→3,750s al quitar detalles no pedidos;759 completa20/24 pero inventa recencia, rechazada.44pins públicos verificados. Actual760 aún sin crédito real. Diferencia44–50t/s aislado vs76producto no atribuida;OMP/MKL4 no la explica;cwd distinto es hipótesis.4s es referencia implementada, C07 certifica latencia.

La preocupación del dueño sobre sesgo porQwen se conserva:699 contiene300respuestas nativas sin BAXY,50completas×6perfiles;73757paresK2,14sóloBAXY/3sólo directo, no ganador universal. Recetas propias por modelo; verdad/autorización comunes.

Registro privado actual SHA f6f2b1ac779c767b59740c3a2da2532b53e1044596eac329597f9b8c1c20ebff intacto. Faltan cobertura completa, reserva, UI/loopback/AEC, recursos conjuntos≤4GiB, matriz/continuidad y Full final. Goal no completo; no reducir alcance. Preservar WIP ajeno.
'''
assert 'diagnóstico759' in old
hp.write_bytes(new.encode('utf-8'))
rp = BASE / 'RELEVO_ACTIVO.json'
relevo = json.loads(rp.read_text(encoding='utf-8-sig'))
relevo.update(workStatus='semantic_inventory760_adopted_pending_publication', checkpoint=checkpoint.strip(),
              activeValidation=None, continuation='Publish validated760 and execute prepared registered73 runner761 with runtime Python; no owner question pending.')
write(rp, relevo)
artifacts = ['SOURCE_PINS.json', 'PROGRAM.json', 'PLAN.json', 'VALIDATION.json', 'ADOPTION.json', 'REPORT.md',
             'initial.log', 'initial2.log', 'focused.log', 'owners.log', 'final-owners.log',
             'integrity-before-pins.log', 'integrity-final.log', 'fast.log']
paths = [OUT / name for name in artifacts] + [BASE / 'INVENTORY_PROJECTION759/PUBLICATION.json']
drivers = ['c03-prepare-inventory760.py', 'c03-adopt-inventory760.py', 'c03-prepare-status761.py', 'c03-status-batch761.py']
paths.extend(ROOT / 'scratchpad' / name for name in drivers)
for path in paths:
    path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
artifact_pins = {path.relative_to(ROOT).as_posix(): sha(path) for path in paths}
write(OUT / 'PINS.json', artifact_pins)
paths.append(OUT / 'PINS.json')
paths.extend(ROOT / path for path in pins)
paths.extend(BASE / name for name in ['CHECKPOINT.md', 'HANDOFF.md', 'RELEVO_ACTIVO.json'])
relative = [path.relative_to(ROOT).as_posix() for path in paths]
git('add', '--', *relative)
staged = set(git('diff', '--cached', '--name-only', '-z').decode().strip('\0').split('\0'))
assert staged == set(relative)
for path, digest in {**artifact_pins, **pins}.items():
    assert hashlib.sha256(git('show', ':' + path)).hexdigest() == digest, path
assert not git('diff', '--cached', '--check', '--', *pins).strip()
# Original pytest tracebacks contain trailing whitespace. Preserve that evidence;
# it is not a source formatting failure and the Fast source gate passed.
print(json.dumps({'staged_files': len(relative), 'source_pins': len(pins), 'artifact_pins': len(artifact_pins)}))
