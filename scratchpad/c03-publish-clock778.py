"""Stage only adopted778 and its complete779/780 evidence; preserve unrelated WIP."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'CLOCK_SCOPE778'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only']).strip()
assert read(OUT / 'ADOPTION.json')['status'] == 'adopted_shared_input_scope_improvement'
pins = read(OUT / 'SOURCE_PINS.json')
assert all(sha(ROOT / p) == h for p, h in pins.items())
(BASE / 'HANDOFF.md').write_bytes('''# Handoff C03 — 778–780 — 2026-09-10

Goal activo en Goal-c03. Objetivo attachment58161a42, SHA621020a31266e98d043b07f214e8a8c6c3cb48f1287d27e411bf805402dadb86. Main intacto5f572ee1. Encuesta742/rev1248:26cubiertos/716abiertos/0NA; registro SHA7b60937e2a3b22d9d887d4e01849b3d0cb6225d0bf4fb78b9ccbde1eaf372d32. BAXY manual cerrado; ninguna pregunta pendiente. Preservar WIP ajeno.

778 adoptada en el commit que contiene este handoff. CLOCK_SCOPE778/VALIDATION.json:2298pass/1skipSTT/62,08s, Fast0, Release1,77s, cero advertencias/errores;104controles nuevos. Sesión70616 recogida0. Sin nuevo Full (sóloPython). Tres puertas temporales comparten petición completa y cabezas verbales; se conserva elipsis nominal contextual. Modelo/prompt/sampler/budget sin cambios. Programa407 SHA4d1f25644932b7acbf53d0e3844e4b22d91097d35efae8379eaebd7789b6fdb3. SOURCE_PINS actual5; CANDIDATE1_SOURCE_PINS y snapshots privados preservan el candidato anterior, no repinarlos. Primer candidato2274pass/1skipSTT/Fast0; el preflight detectó infinitivo pasarme, no un problema del envoltorio puedes. Familia modal corregida24pass y regresión completa repetida.

779:50turnos del producto,15originales+35variantes,48pass/2fail y49lecturas frescas. Los15originales pasan (772tenía11/15). t46/variant31: Marka las16horas y13minutos, dato correcto pero ortografía incorrecta. t50/variant35: No sé la hora exacta, sin Core tras t48hora explícita→t49¿Y la fecha?→t50¿Y la hora?. Conservar ambos, sin filtro literal de Marka.52,328s;3497,56MiB VRAM/2493,90MiB RSS sumada; todasguardas true,65474 recogida0.12referencias privadas añadidas, sin estados de cobertura nuevos.

780:50finales correctos (25hora/25fecha;25capturas UTC/offset),51posts,49raw=final y un reintento. Caso35: Son las12del mediodía es correcto para12:00, pero missing_name lo rechaza; retry Son las12:00 también correcto. Es veto falso de integración, no error del modelo. T0/max256/thinkingfalse/cachefalse en51posts, todos finishstop. Root revisó50 finales y el bruto rechazado; RO independiente recalculó50 offsets/fechas y confirmó.16,281s;3497,56MiB/757,52MiB RSS;21475 recogida0. Primer preflight falló antes de servidor/directorios por ignorar version en el fixture; se preservó version1 antes de la única pasada. CLOCK_VALUES780/CASOS_SINTETICOS.md contiene todos los casos. No UI/provider/voz/reserva ni cobertura automática.

Siguiente bloqueo real: cadena de elipsis. RO confirmado en __main__.py2580–2597 (sólo último texto humano),5859–5895/6217–6226 (lo propaga); effect_intent.py12697–12715 resuelve ese texto sin su propio antecedente. MindSidecarClient.cs450–483 y BuildMindHistory2310–2327 sólo serializan role/content, no intención previa tipada. El historial humano completo sí existe; inspeccionar cómo conservar la continuidad sin derivarla de prosa del asistente ni saltar cambios de tema. No implementación781 iniciada. Veto de mediodía780 también pendiente. Cualquier cambio C#+Python exige Full.

No repetir otro prompt de inventario tras768/771 sin mejora. Siguen pendientes inventario, RAM disponible/usable, Internet/interfaz, WLAN ampliada y CPU acumulada.775 actor batería publicado6a17d1c7;77717/17,77646/50 con4causalidades añadidas sin acreditar.699 aisló50tareas×6perfiles;73757paresK2, con3aciertos directos dañados por instruccionesBAXY. Qwen candidato provisional, sin ganador universal.

Full7 histórico:4574.NETpass/1skip+16omisiones;11399Pythonpass/3skips+466subtests. Faltan generalización742, reserva100, UI/loopback/AEC, recursos conjuntos≤4GiB, matriz y continuidadC04–C09, Full final. Ningún proceso de inferencia/prueba/gate activo. No rerun c03-adopt-clock778.py (ya mutó registro) ni prepare/reseal sobre carpetas selladas.
'''.encode('utf-8'))
paths = []
for folder, names in [
    (OUT, ['SOURCE_PINS.json', 'PROGRAM.json', 'PLAN.json', 'CANDIDATE1_SOURCE_PINS.json',
           'CANDIDATE1_PROGRAM.json', 'CANDIDATE2.json', 'baseline.log', 'baseline2.log', 'owners.log',
           'boundary.log', 'candidate1-final.log', 'candidate1-fast.log', 'modal-baseline.log',
           'modal-fixed.log', 'final.log', 'fast.log', 'VALIDATION.json', 'ADOPTION.json', 'REPORT.md']),
    (BASE / 'STATUS_BATCH779', ['PREREG.json', 'PROCESS.json', 'EXIT.json', 'RESOURCES.json',
                               'REVIEW_CAPTURE.json', 'RESULT.json', 'REGISTRY_UPDATE.json', 'REPORT.md']),
    (BASE / 'CLOCK_VALUES780', ['PREREG.json', 'READY.json', 'RESULT.json', 'ADJUDICATION.json',
                               'CASOS_SINTETICOS.md', 'REPORT.md']),
]:
    paths += [folder / name for name in names]
paths += [ROOT / 'scratchpad' / name for name in [
    'c03-prepare-clock778.py', 'c03-reseal-clock778.py', 'c03-status-batch779.py',
    'c03-review-status779.py', 'c03-prepare-clock-values780.py', 'c03-clock-values780.py',
    'c03-adopt-clock778.py', 'c03-publish-clock778.py']]
paths.append(BASE / 'BATTERY_ACTOR775/PUBLICATION.json')
for path in paths:
    path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
write(OUT / 'PINS.json', {p.relative_to(ROOT).as_posix(): sha(p) for p in paths})
paths += [OUT / 'PINS.json'] + [ROOT / p for p in pins] + [BASE / n for n in ['CHECKPOINT.md', 'HANDOFF.md', 'RELEVO_ACTIVO.json']]
subprocess.run(['git', 'add', '--', *[p.relative_to(ROOT).as_posix() for p in paths]], check=True)
subprocess.run(['git', 'diff', '--cached', '--check'], check=True)
print(json.dumps({'staged_paths': len(paths), 'source_pins': len(pins)}))
