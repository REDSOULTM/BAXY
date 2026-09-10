"""Publish adopted783 with immutable runtime/test evidence and canonical Git bytes."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'NAMED_CLOCK783'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only']).strip()
assert read(OUT/'ADOPTION.json')['status'] == 'adopted_shared_exact_clock_values'
pins = read(OUT/'PUBLICATION_SOURCE_PINS.json')
assert all(sha(ROOT/p) == h for p,h in pins.items())
normalization = read(OUT/'PUBLICATION_NORMALIZATION.json')
snapshot = Path(normalization['private_validated_snapshot'])
assert sha(snapshot) == normalization['validated_raw_sha256']
assert snapshot.read_bytes().replace(b'\r\n',b'\n') == (ROOT/normalization['path']).read_bytes()
raw = (Path(os.environ['TEMP'])/'c03-clock783-canonical-test.log').read_text(encoding='utf-8-sig')
assert '202 passed in 1.77s' in raw
(OUT/'canonical-test.log').write_bytes(('\n'.join(l.rstrip() for l in raw.splitlines())+'\n').encode())
normalization.update(owner_passed=202, owner_failed=0, owner_skipped=0, owner_seconds=1.77,
    command='registered Python -X utf8 -m pytest tests/test_c03_request_preservation.py -q')
write(OUT/'PUBLICATION_NORMALIZATION.json',normalization)
(BASE/'HANDOFF.md').write_bytes('''# Handoff C03 — 783/784 — 2026-09-10

Goal activo en Goal-c03, objetivo attachment58161a42 SHA621020a31266e98d043b07f214e8a8c6c3cb48f1287d27e411bf805402dadb86. Main intacto5f572ee1. BAXY manual cerrado; ninguna pregunta pendiente. Preservar WIP ajeno. Sin procesos de inferencia/tests/gates activos; agentes ociosos.

783 adoptada en este commit. llm.py comparte extracción/comprobación de valores exactos de reloj entre ambos validadores. Acepta formas declarativas de mediodía/medianoche, preserva contradicciones, minutos y12AM/PM. Modelo,backend,plantilla,prompt,sampler,budget intactos. NAMED_CLOCK783/VALIDATION:1523pass/1skipSTT/10,23s;Fast0/Release18,99s;81828 recogida0.75controles nuevos. Programa407 SHA29640b414f0040a77343c05a9d183d2ffaf9a82938d4e168dd16abe023b983f4.

784: mismos50casos/IDs/valores/criterios y50primerosHTTPpayloads de780.50/50correctos,50raw=final,0reintentos;49finales iguales. clock780-35 ahora conserva «Son las12del mediodía.»: idéntico bruto correcto que780vetó. No cambio de prompt ni receta para conseguirlo.17,219s;3497,56MiB VRAM/757,21MiB RSS del compositor; todasguardastrue;37453 recogida0. Root leyó50finales completos. No UI/provider/voz/reserva/recursosconjuntosfinales. Preflight inicial paró antes de inferencia por palabra pytest en el comando padre; se lanzó driver intacto por separado.

Sellos: SOURCE_PINS conserva8huellas usadas en la corrida. PUBLICATION_SOURCE_PINS identifica la única diferencia posterior: normalizar CRLF→LF del test_request_preservation según .gitattributes. PUBLICATION_NORMALIZATION acredita equivalencia exacta, respaldo privado del original y202pass/0skip/1,77s del owner con LF. Ninguna fuente runtime cambió ni se repinó evidencia histórica.

781/782 publicado f6f037cf: continuidad humana de hora→fecha→hora reparada.782=73/74,74lecturas,24nuevosencadenados correctos; t50 pasó a375,295ms. Sólo t46/clock-variant779-31 mantiene «Marka». Es content bruto del modelo bajo promptBAXY, no transformación posterior; no atribuirlo al modelo nativo ni introducir veto/reemplazo literal.

Encuesta742/rev1248:28cubiertos/714abiertos/0NA, SHA3b3705303db6a86af77a0f7568ea8c0977a1d551401dab48d0501b115ef8df2b. Fecha H0180/H0499 cubierta conscientemente por779/780/782;784 mantiene los25casos de fecha.783no añade cobertura. Autoría/expectativas preservadas.

Siguiente: atribuir el defecto ortográfico sin otro parche literal, o avanzar la siguiente categoría bloqueante de lectura con método distinto para inventarios (768/771 no mejoraron). Siguen RAMdisponible/usable,Internet/interfaz,WLAN,CPUacumulada,causalidad776.699 comparó mismos50×6perfiles sinBAXY;737observó3aciertos K2 directos dañados por el prompt (H0037,H0600,processes-top3-en), una pasada. Qwen provisional. No presentar las860respuestas previas como modelo aislado.

Full7 histórico:4574.NETpass/1skip+16omisiones;11399Pythonpass/3skips+466subtests. Faltan generalización742,reserva100,UI/loopback/AEC,recursosconjuntos≤4GiB,matriz/continuidadC04–C09 yFull final. No nuevoFull para783sóloPython; obligatorio para cambioC#+Python y cierre. No rerun prepare/adopt783 ni784 en directorios sellados.
'''.encode('utf-8'))
paths = []
for folder,names in [
    (OUT,['SOURCE_PINS.json','PUBLICATION_SOURCE_PINS.json','PUBLICATION_NORMALIZATION.json','PROGRAM.json','PLAN.json',
          'baseline.log','owners.log','fixed.log','final.log','fast.log','canonical-test.log','PREFLIGHT784.json','VALIDATION.json','ADOPTION.json','REPORT.md']),
    (BASE/'CLOCK_VALUES784',['PREREG.json','READY.json','RESULT.json','ADJUDICATION.json','CASOS_SINTETICOS.md']),
]:
    paths += [folder/n for n in names]
paths += [ROOT/'scratchpad'/n for n in ['c03-prepare-named-clock783.py','c03-clock-values784.py','c03-adopt-named-clock783.py','c03-publish-named-clock783.py']]
paths += [BASE/'CLOCK_CONTEXT781/PUBLICATION.json']
for p in paths:
    p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n'))
write(OUT/'PINS.json',{p.relative_to(ROOT).as_posix():sha(p) for p in paths})
paths += [OUT/'PINS.json']+[ROOT/p for p in pins]+[BASE/n for n in ['CHECKPOINT.md','HANDOFF.md','RELEVO_ACTIVO.json']]
subprocess.run(['git','add','--',*[p.relative_to(ROOT).as_posix() for p in paths]],check=True)
subprocess.run(['git','diff','--cached','--check'],check=True)
print(json.dumps({'staged_paths':len(paths),'source_pins':len(pins)}))
