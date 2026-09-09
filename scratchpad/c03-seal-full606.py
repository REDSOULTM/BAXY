"""Seal the completed606 Full; refuses unfinished/red runs or changed Python tree."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-language-literals606'
raw = (Path(os.environ['TEMP']) / 'c03-language606-full.log').read_bytes()
log = raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
assert 'source_quality_gate_passed: mode=Full' in log
assert 'source_quality_check_failed' not in log
assert not (out / 'RESULT.json').exists()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


tree = json.loads((out / 'CURRENT_TREE.json').read_text(encoding='utf-8'))
files = {p.relative_to(root).as_posix():p for folder in ['experiments/voice_latency', 'scripts', 'src/baxy_mind'] for p in (root / folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for name in sorted(files):
    digest.update(name.encode() + b'\n' + sha(files[name]).encode() + b'\n')
assert digest.hexdigest() == tree['sha256'] and len(files) == tree['files']
dotnet = []
for match in re.finditer(r'Con error:\s*(\d+), Superado:\s*(\d+), Omitido:\s*(\d+), Total:\s*(\d+), Duración:\s*(.*?) - (\S+\.dll)', log):
    failed, passed, skipped, total = map(int, match.groups()[:4])
    assert failed == 0
    dotnet.append({'failed': failed, 'passed': passed, 'skipped': skipped, 'total': total, 'duration': match[5], 'suite': match[6]})
assert len(dotnet) == 5
summary = next(line for line in reversed(log.splitlines()) if re.search(r'\d+ passed', line))
assert not re.search(r'\d+ failed|\d+ errors?', summary)
python = {}
for label in ['passed', 'skipped', 'subtests passed']:
    match = re.search(r'(\d+) ' + label, summary)
    python[label.replace(' ', '_')] = int(match[1]) if match else 0
python['seconds'] = float(re.search(r' in ([\d.]+)s', summary)[1])
release_time = re.findall(r'Tiempo transcurrido ([\d:.]+)', log)[0]
(out / 'full.log').write_bytes(raw)
result = {'utc': datetime.now(timezone.utc).isoformat(), 'command': r'.\scripts\test_source_quality.ps1 -Mode Full',
          'gate_exit_code': 0, 'source_changed_during_run': False, 'python_tree': tree,
          'dotnet': dotnet, 'python': python, 'release_time': release_time,
          'dotnet_printed_omissions': len(re.findall(r'^\s*Omitidas ', log, re.M)),
          'omissions_note': 'Existing environmental/opt-in omissions are not passes and give no UI, audio or acceptance credit; none added or relaxed.',
          'full_sha256': sha(out / 'full.log'), 'survey': {'covered':24, 'open':718, 'not_applicable':0},
          'product605': {'correct_finals':33, 'total':35, 'ui_or_voice_credit':False},
          'goal_status':'EN_CURSO', 'registered_manifest_changed':False}
write(out / 'RESULT.json', result)
note = f'''# Fuente606: reparación de idioma y literales validada

602 repara un borrador completo de conocimiento cuando sólo falla idioma traduciéndolo en el reintento existente, sin añadir llamadas ni borrar el historial.604 detecta frases en el idioma opuesto aunque la apertura sea correcta.606 conserva citas y código literal para no introducir falsos rechazos. La revisión y las pruebas ES/EN preservan nombres, números, autores, texto citado, contracciones, código, cortes y todos los rechazos finales. No se modifica el modelo, backend, plantilla registrada ni el perfil CPU.

Full salida0: Python{python['passed']} pass,{python['skipped']} omisiones,{python['subtests_passed']} subpruebas,{python['seconds']}s. .NET{sum(row['passed'] for row in dotnet)} pass,0 fallos,{sum(row['skipped'] for row in dotnet)} omisión agregada; el log imprime{result['dotnet_printed_omissions']} omisiones opt-in. Estática y Release aprobados,{release_time},0 advertencias/errores. Ninguna omisión es una prueba realizada ni acredita UI/voz. No se añadió skip ni se relajaron umbrales. Árbol Python{tree['sha256']},404archivos, sin cambiar durante Full; sólo pins actuales V8/STT actualizados, históricos intactos.

Producto605 sin hooks ni override da33/35finales correctos, conserva los agradecimientos y las dos identidades inglesas y la conversación breve. Permanecen H0012 y Atlas. La revisión606 posterior sólo cambia literales/código; su contrato específico pasa y este Full lo integra. Encuesta24cubiertos/718abiertos/0NA;742/rev1248 original intacto. El conteo de finales no acredita la ruta completa de progreso ni UI/voz. C03 sigue activo: registroCPU, recursos conjuntos, prosa de progreso, restantes conductas y aceptación final siguen pendientes. BAXY manual cerrado, sin decisión pendiente del dueño.
'''
(out / 'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
write(out / 'PINS.json', {p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
attributes = root / '.gitattributes'
line = '/artifacts/comprobaciones/C03/astra-language-literals606/** -text'
assert line not in attributes.read_text(encoding='utf-8')
with attributes.open('a', encoding='utf-8', newline='\n') as stream:
    stream.write(line + '\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n' + note)
(base / 'HANDOFF.md').write_text(note + '\nSiguiente: revisar PINS y publicar fuentes602/604/606 y evidencia593–605. Después comparar la proyección de incomplete_effect a unsupported paraH0012: dos prompts594/595 no pasan y no se adoptan. Atlas y prosa de progreso son causas distintas; H0021 requiere su propio literal. Mantener pins actuales V8/STT al editar, sin tocar históricos.\n', encoding='utf-8', newline='\n')
state = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
state.update(confirmedAtUtc=result['utc'], checkpoint=f"606 Full0: Python{python['passed']}pass/{python['skipped']}skips/{python['subtests_passed']}subtests; .NET{sum(row['passed'] for row in dotnet)}pass/1omisión agregada.60533/35finales. Encuesta24/718/0. Fuente pendiente de publicación.", continuation='Revisar diff/PINS y publicar602/604/606 con593–605. Luego proyecciónH0012, Atlas, prosa progreso, UI/voz/memoria conjunta, registroCPU y restanteC03. No inferencia ni compuerta activas al sellar.')
write(base / 'RELEVO_ACTIVO.json', state)
print(json.dumps(result, ensure_ascii=False))
