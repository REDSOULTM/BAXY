"""Stage adopted781/782 only; retain unrelated work and historical seals."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'CLOCK_CONTEXT781'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only']).strip()
assert read(OUT / 'ADOPTION.json')['status'] == 'adopted_contiguous_human_clock_context'
pins = read(OUT / 'SOURCE_PINS.json')
assert all(sha(ROOT / p) == h for p,h in pins.items())
registry = read(BASE / 'STATUS_BATCH782/REGISTRY_UPDATE.json')
state = read(BASE / 'RELEVO_ACTIVO.json')
state.update(surveyVerificationCounts=registry['counts'], surveyRegistrySha256=registry['after_sha256'])
write(BASE / 'RELEVO_ACTIVO.json', state)
(BASE / 'HANDOFF.md').write_bytes('''# Handoff C03 — 781/782 — 2026-09-10

Goal activo, Goal-c03; objetivo attachment58161a42 SHA621020a31266e98d043b07f214e8a8c6c3cb48f1287d27e411bf805402dadb86. Main intacto5f572ee1. BAXY manual cerrado, ninguna pregunta pendiente. Preservar WIP ajeno.

781 adoptada en el commit que contiene este handoff. Contexto de elipsis humanas contiguas, sin cruzar tema ni usar prosa del asistente. llm.py/prompt/modelo/receta intactos. Programa407 SHA5f730245123224a2958f3d6f79b210e6402ed22d30792667243cc76786da601b;8pins en CLOCK_CONTEXT781/SOURCE_PINS.json. VALIDATION:3403pass/1skipSTT/67,45s;Fast0,Release18,82s,0warnings/errors;62controles nuevos.47671 recogida0. No nuevo Full para sóloPython; Full final sigue obligatorio.

782 terminó81959 exit0, todasguardastrue:73/74 correctos,74lecturas frescas,0reintentos,55,563s. Panel50 de779 ahora49/50;15originales y24nuevascontinuaciones correctos. t50 arreglado375,295ms; cambio16:34→16:35 en t57 se refleja. t46/variant779-31 sigue «Marka las16:34.»: falta ortográfica real, sin filtro literal. Pico3497,56MiB VRAM/2470,38MiB RSS sumada; no UI/voz/reserva/recursosfinales. Root leyó todos los finales; RESULT y adjudicación privada completos.

Encuesta742/rev1248:28cubiertos/714abiertos/0NA; SHA3b3705303db6a86af77a0f7568ea8c0977a1d551401dab48d0501b115ef8df2b. H0180/H0499 cubiertos conscientemente como FECHA: originales779/782, variantesES/EN/mezcla/modalidad/orden/referencias y25fechas sintéticas780 con meses/años/bisiestos/UTC+offset. llm.py no cambió781.12filas reciben evidencia, sólo2estado; autoría/expectativas protegidas, respaldo privado yREGISTRY_UPDATE. No crédito a toda la categoría hora.

Siguiente: falso veto780-35. Para12:00 el modelo produjo «Son las12del mediodía.», missing_name lo rechazó y retry «Son las12:00.» pasó; ambos eran correctos. Revisar llm.py3104–3170 (_clock_tokens/_clock_appears),3763–3768 y4765–4779. Parser compartido debe representar todos los valores y conservar contradicciones/AMPM; nada de excepción literal a missing_name. RO propuso extractor de pares hora/minuto para numéricos y mediodía/medianoche, con límites contra antes de, once del, mediodía y cinco. No fuente/test de esta reparación empezados. Todos los agentes están ociosos; no inferencias ni tests activos.

Marka779 viene del content bruto del modelo, no transformación BAXY: compose-audit t46 first yllm.py10022–10028/3639–3653. Sin prueba de defecto general del modelo nativo. No adoptar reemplazo/veto literal.

699:300respuestas nativas, mismas50tareas×6perfiles;737:57paresK2,3aciertos directos dañados al añadir prompt (H0037,H0600,processes-top3-en). Una pasada no mide variabilidad ni una regla individual. Qwen provisional. No repetir prompt de inventario tras768/771 sin mejora; pendientes inventario,RAMdisponible/usable,Internet/interfaz,WLAN,CPUacumulada,causalidadbatería776.

Full7 histórico4574.NETpass/1skip+16omisiones;11399Pythonpass/3skips+466subtests. Faltan generalización742, reserva100, UI/loopback/AEC, consumo conjunto≤4GiB, matriz/continuidadC04–C09 yFull final. No rerun prepare/adopt781 ni782 sobre carpetas selladas; publicación778 receipt se incluye aquí.
'''.encode('utf-8'))
paths = []
for folder,names in [
    (OUT,['SOURCE_PINS.json','PROGRAM.json','PLAN.json','baseline.log','fixed.log','final.log','fast.log','VALIDATION.json','ADOPTION.json','REPORT.md']),
    (BASE/'STATUS_BATCH782',['PREREG.json','PROCESS.json','EXIT.json','RESOURCES.json','REVIEW_CAPTURE.json','RESULT.json','REGISTRY_UPDATE.json','REPORT.md']),
]:
    paths += [folder/name for name in names]
paths += [ROOT/'scratchpad'/name for name in ['c03-prepare-clock-context781.py','c03-status-batch782.py','c03-review-status782.py','c03-adopt-clock-context781.py','c03-publish-clock-context781.py']]
paths += [BASE/'CLOCK_SCOPE778/PUBLICATION.json']
for p in paths:
    p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n'))
write(OUT/'PINS.json',{p.relative_to(ROOT).as_posix():sha(p) for p in paths})
paths += [OUT/'PINS.json'] + [ROOT/p for p in pins] + [BASE/n for n in ['CHECKPOINT.md','HANDOFF.md','RELEVO_ACTIVO.json']]
subprocess.run(['git','add','--',*[p.relative_to(ROOT).as_posix() for p in paths]],check=True)
subprocess.run(['git','diff','--cached','--check'],check=True)
print(json.dumps({'staged_paths':len(paths),'source_pins':len(pins)}))
