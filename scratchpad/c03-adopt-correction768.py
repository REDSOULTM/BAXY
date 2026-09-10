"""Publishable checkpoint after sealed768 owners, window integrity and Fast."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'INVENTORY_CORRECTION768'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only']).strip()
assert not (OUT / 'ADOPTION.json').exists()
pins = read(OUT / 'SOURCE_PINS.json')
assert all(sha(ROOT / p) == h for p,h in pins.items())
assert all(sha(ROOT / p) == h for p,h in read(BASE / 'DENSE_INVENTORY764/SOURCE_PINS.json').items())
for name, marker in [('owners-sealed', b'775 passed in 5.34s'), ('integrity', b'1011 passed, 1 skipped in 5.96s'),
                     ('fast', b'source_quality_gate_passed: mode=Fast')]:
    data = (Path(os.environ['TEMP']) / ('c03-inventory-correction768-' + name + '.log')).read_bytes().replace(b'\r\n', b'\n')
    assert marker in data
    (OUT / (name + '.log')).write_bytes(data)
now = datetime.now(timezone.utc).isoformat()
write(OUT / 'VALIDATION.json', {'utc': now,
    'python': 'C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe',
    'owner_arguments': '-X utf8 -m pytest tests/test_c03_inventory_semantic_projection.py tests/test_c03_window_state_facts.py tests/test_c03_window_focus_coverage.py tests/test_compose_contract.py tests/test_c03_request_preservation.py -q',
    'owners': {'passed': 775, 'failed': 0, 'skipped': 0, 'seconds': 5.34, 'new_cases': 24},
    'integrity_selection': "git ls-files 'tests/test_c03_window*.py' plus test_c03_observed_window_vocabulary.py, test_price_v8_veto_damage_by_cause.py, test_stt_quality_evaluators.py, test_validate_physical_wake_v17_program.py; -X utf8 -m pytest <files> -q",
    'integrity_files': subprocess.check_output(['git', 'ls-files', 'tests/test_c03_window*.py'], text=True).splitlines()
        + ['tests/test_c03_observed_window_vocabulary.py', 'tests/test_price_v8_veto_damage_by_cause.py',
           'tests/test_stt_quality_evaluators.py', 'tests/test_validate_physical_wake_v17_program.py'],
    'integrity': {'passed': 1011, 'failed': 0, 'environmental_skips': 1, 'seconds': 5.96,
        'skip': 'Blind STT campaign inputs absent; not a pass or voice credit'},
    'fast_command': 'scripts/test_source_quality.ps1 -Mode Fast', 'fast_exit_code': 0,
    'fast_session': 52587, 'terminal_collected': True, 'release_seconds': 22.36, 'warnings': 0, 'errors': 0,
    'source_and_declaration_pins_unchanged': True,
    'offline_parity': 'CAPTURED_PARITY.json:9 unique captured window drafts retain their prior decisions; one now carries unsupported chronology feedback.',
    'full_new': False, 'full_reason': 'Python-only source adoption; no C#+Python shared adoption. Final Full required.',
    'coverage_added': 0, 'product_pending': 'Prepared769 complete73 original panel/criteria with postbuild DLL seal.'})
write(OUT / 'ADOPTION.json', {'utc': now, 'status': 'adopted_after_owners_integrity_fast',
    'source_pins': 'SOURCE_PINS.json', 'first_attempt_model_profile_sampler_budget_unchanged': True,
    'retry_instructions_changed': True, 'factual_acceptance_rules_unchanged': True,
    'coverage_added': 0, 'commit': 'Containing commit'})
(OUT / 'REPORT.md').write_bytes('''# Corregir el dato sin perder la lista

El canal de corrección factual de ventanas ahora conserva la causa concreta cuando un borrador inventa la cronología de apertura: esa cronología no fue observada. El mismo canal ya corregía contradicciones de foco. Se amplía su responsabilidad de hechos de ventanas y se retira el nombre anterior; no se añade otro narrador ni un camino por modelo.

Los reintentos de inventario dejan de exigir una sola frase y conservan la lista pedida y su alcance de página. Las identidades y cantidades permanecen una vez en los hechos originales; no se duplican como otra lista en la corrección. El borrador rechazado sigue siendo evidencia para el modelo, nunca una respuesta prefabricada. No se cambia primer intento, modelo, sampler, presupuesto ni regla de aceptación factual.

775 pruebas dueñas pasan, incluidas24 nuevas combinaciones de español/inglés, rutas Qwen/K2, páginas2/7,20/25,3/3 y segundo/tercer intento. La revisión completa de ventanas e integridad tiene1011pass y1skip ambiental por entradas STT privadas ausentes. Fast pasó, Release22,36s, cero advertencias y errores. Los siete pins de fuente/declaraciones permanecen intactos. Las suites se solapan: no sumar sus cantidades.

Las nueve combinaciones únicas de borrador y hechos de ventanas capturadas en767 mantienen exactamente su decisión factual anterior. Una recibe ahora la causa estructurada que faltaba. Es una comprobación determinista sobre evidencia capturada; no demuestra todavía que la inferencia real corrija y entregue el inventario.

El primer test nuevo comparaba también la ubicación de la instrucción de idioma, que BAXY ya mueve del usuario al sistema al reintentar. Se corrigió ese aserto para comparar solicitud y hechos decodificados, manteniendo la exigencia de respuesta completa. El fallo inicial se conserva. La corrida769 preparada usará los mismos73casos y el runtime registrado, después de publicar esta fuente. Encuesta26cubiertos/716abiertos/0NA, sin UI/voz/reserva ni aceptación final; C03 activo.
'''.encode('utf-8'))
note = ('768 adoptado: corrección factual conserva causa de recencia no observada y permite lista/página completa en retry/third; '
    'sin cambiar primer intento/modelo/sampler/presupuesto/verificador.775owners pass/0skip/5,34s,1011integridad pass/1skipSTT/5,96s; '
    'Fast0 sesión52587 recogida,Release22,36s.7pins intactos,9borradores previos conservan decisión. '
    'Publicar768 y ejecutar769 completo73; no inferencia activa.26/716/0.\n\n')
cp = BASE / 'CHECKPOINT.md'
pending = cp.with_suffix('.pending.md')
pending.write_bytes(note.encode('utf-8') + cp.read_bytes())
pending.replace(cp)
relevo = read(BASE / 'RELEVO_ACTIVO.json')
relevo.update(checkpoint=note.strip(), confirmedAtUtc=now, activeValidation=None,
    workStatus='inventory_correction768_adopted_pending_publication',
    continuation='Publish768 then execute scratchpad/c03-status-batch769.py with registered Python. Require all exit guards and adjudicate73 against original criteria.')
write(BASE / 'RELEVO_ACTIVO.json', relevo)
handoff = BASE / 'HANDOFF.md'
old = handoff.read_text(encoding='utf-8')
start = old.index('767 adjudicada')
tail = old[start:]
tail_start = tail.index('Otros bloqueos:')
tail = tail[:tail.index('Siguiente:')] + tail[tail_start:]
handoff.write_bytes(('''# Handoff C03 —768 —2026-09-10

Goal activo en Goal-c03, main intacto5f572ee1. Encuesta742/rev1248:26cubiertos/716abiertos/0NA; registroSHA dd88ee5458ef8cb0637993ba33429ae42fc4bc67974b656ce0e046eadacc40f4. Sin pregunta pendiente. BAXY manual cerrado.52587Fast terminó0/recogido, no inferencia ni gate activos. Preservar WIP ajeno.

768 adoptado, pendiente publicar. INVENTORY_CORRECTION768/VALIDATION.json:775owners/0skip/5,34s;1011window-integridad/1skipSTT/5,96s;Fast0,Release22,36s. Siete pins actuales. Programa407=ba7851452608e5e8fb1d6bb5601764fe0cfe02069379cd8369654a6f8936e3de, mismas3raíces. No tocar pins históricos760/766 ni wakev17. Python-only, no Full nuevo.

Se reutiliza window_fact_feedback (renombrado del canal de foco) para informar cronología de apertura no observada; retry/third de inventarios preservan lista y página sin exigir una frase. Primer intento, sampler, modelo, presupuesto y verificador intactos.9 borradores previos conservan decisiones.24 pruebas nuevas; primer aserto erróneo sobre ubicación del idioma está preservado. Mejora real de inferencia no acreditada todavía.

Siguiente: publicar768 y ejecutar scratchpad/c03-status-batch769.py con Python registrado C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe -X utf8. Mismos73casos y criterios689/729, sin hooks. Usa main.compile_if_needed antes de sellar DLL; no editar fuentes durante corrida. Reviewer769 preparado. Todas las guardas EXIT deben ser true; no puntuar desde terminal solamente.

''' + tail).encode('utf-8'))
artifact_names = ['PLAN.json', 'PROGRAM.json', 'SOURCE_PINS.json', 'owners-before-seal.log',
    'owners-initial-before-seal.log', 'owners-sealed.log', 'integrity.log', 'fast.log',
    'CAPTURED_PARITY.json', 'VALIDATION.json', 'ADOPTION.json', 'REPORT.md']
paths = [OUT / name for name in artifact_names] + [ROOT / 'scratchpad' / name for name in [
    'c03-prepare-correction768.py', 'c03-check-correction768.py', 'c03-adopt-correction768.py',
    'c03-status-batch769.py', 'c03-review-status769.py']]
assert all(b'\r\n' not in p.read_bytes() for p in paths)
artifact_pins = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
write(OUT / 'PINS.json', artifact_pins)
paths += [OUT / 'PINS.json'] + [ROOT / p for p in pins] + [BASE / name for name in ['CHECKPOINT.md', 'HANDOFF.md', 'RELEVO_ACTIVO.json']]
relative = [p.relative_to(ROOT).as_posix() for p in paths]
subprocess.run(['git', 'add', '--', *relative], check=True)
assert set(subprocess.check_output(['git', 'diff', '--cached', '--name-only'], text=True).splitlines()) == set(relative)
for p,h in {**pins, **artifact_pins}.items():
    assert hashlib.sha256(subprocess.check_output(['git', 'show', ':' + p])).hexdigest() == h, p
subprocess.run(['git', 'diff', '--cached', '--check'], check=True)
print(json.dumps({'source_pins': len(pins), 'artifact_pins': len(artifact_pins), 'staged_files': len(relative)}))
