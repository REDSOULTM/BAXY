"""Seal a completed successful cross-language Full, preserving omitted checks."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-cpu-adapter590'
raw = (Path(os.environ['TEMP']) / 'c03-adapter590-full.log').read_bytes()
log = raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
assert 'source_quality_gate_passed: mode=Full' in log
assert 'source_quality_check_failed' not in log
assert not (out / 'RESULT.json').exists()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


dotnet = []
pattern = r'Con error:\s*(\d+), Superado:\s*(\d+), Omitido:\s*(\d+), Total:\s*(\d+), Duración:\s*(.*?) - (\S+\.dll)'
for match in re.finditer(pattern, log):
    failed, passed, skipped, total = map(int, match.groups()[:4])
    assert failed == 0
    dotnet.append(dict(failed=failed, passed=passed, skipped=skipped, total=total,
                       duration=match[5], suite=match[6]))
assert len(dotnet) == 5, dotnet
python_summary = next(line for line in reversed(log.splitlines()) if re.search(r'\d+ passed', line))
assert not re.search(r'\d+ failed|\d+ errors?', python_summary)
python = {}
for label in ['passed', 'skipped', 'subtests passed']:
    match = re.search(r'(\d+) ' + label, python_summary)
    python[label.replace(' ', '_')] = int(match[1]) if match else 0
seconds = re.search(r' in ([\d.]+)s', python_summary)
python['seconds'] = float(seconds[1]) if seconds else None
release_time = re.findall(r'Tiempo transcurrido ([\d:.]+)', log)[0]
(out / 'full.log').write_bytes(raw)
(out / 'v8-pin.log').write_bytes((Path(os.environ['TEMP']) / 'c03-adapter590-v8-pin.log').read_bytes())
files = {p.relative_to(root).as_posix(): p for folder in ('experiments/voice_latency', 'scripts', 'src/baxy_mind') for p in (root / folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for name in sorted(files):
    digest.update(name.encode() + b'\n' + sha(files[name]).encode() + b'\n')
tree = json.loads((out / 'CURRENT_TREE.json').read_text(encoding='utf-8'))
assert digest.hexdigest() == tree['sha256'] and len(files) == tree['files']
result = {
    'utc': datetime.now(timezone.utc).isoformat(),
    'command': r'.\scripts\test_source_quality.ps1 -Mode Full',
    'gate_exit_code': 0, 'source_changed_during_run': False,
    'static_and_release': f'passed; Release {release_time},0warnings,0errors',
    'dotnet': dotnet, 'python': python,
    'dotnet_printed_omissions': len(re.findall(r'^\s*Omitidas ', log, re.M)),
    'omissions_note': 'Optional/environmental omissions are not passes or evidence of UI, hardware, acoustic or acceptance coverage. No skips or thresholds were added or relaxed by590.',
    'python_tree': tree, 'full_sha256': sha(out / 'full.log'),
    'registered_manifest_changed': False,
    'goal_status': 'EN_CURSO', 'survey': {'covered': 16, 'open': 726, 'not_applicable': 0},
    'product_validation': '591:17 correct CPU/control finals without hooks;592:29 correct/6 failed conversational finals on base. See separate complete reports; no registered adapter promotion.',
    'pending': 'Actual registered candidate and joint UI/voice/resources;592 identity presentation/grammar failures. Remaining survey, eight routes, recovery, acoustic and final acceptance remain open.',
}
write(out / 'RESULT.json', result)
dotnet_pass = sum(r['passed'] for r in dotnet)
dotnet_skip = sum(r['skipped'] for r in dotnet)
note = f'''# Fuente590: adaptador CPU y registro reproducible

Se incorpora el soporte opcional del adaptador cualificado en586/588/589. El perfil verifica el archivo, su hash y el modelo base. El servidor debe cargar el mismo archivo y confirmar escala cero antes de quedar listo. Cada petición ajena a resultados exclusivamente de CPU mantiene escala cero; sólo esa composición usa el perfil medido. No se copia el mecanismo experimental por hilo ni se añaden respuestas fijas o llamadas de composición. Los lectores C#, Python y PowerShell comparten el perfil cerrado. El manifiesto del usuario sigue intacto; incorporar soporte no promociona el adaptador.

Validación: `scripts/test_source_quality.ps1 -Mode Full`, salida0. Estática y Release aprobados, tiempo de compilación {release_time},0 advertencias/errores. .NET: {dotnet_pass} aprobadas,0 fallos,{dotnet_skip} omisiones en resúmenes; el log imprime {result['dotnet_printed_omissions']} omisiones opt-in en total. Python: {python['passed']} aprobadas,{python['skipped']} omisiones,{python['subtests_passed']} subpruebas aprobadas,{python['seconds']}s. Ninguna omisión acredita una prueba ejecutada. No se han añadido skips ni relajado umbrales. Dueñas previas:2240 pass+121 subtests/0 skips;32 pruebas nuevas finales;29 de descubrimiento C#/0 skips. Árbol Python `{tree['sha256']}`,404 archivos; sellos históricos intactos.

El primer Full se conserva en `full-before-current-pin.log`: .NET4452 pass/0 fallos/1 omisión agregada; Python10199 pass/1 fallo/3 omisiones/466 subpruebas,609,51s. Falló únicamente el hash del programa actual en la auditoría V8, que todavía apuntaba a fuente531. Se actualizó ese pin a la fuente590 revisada, sin modificar los seis sellos históricos, su aritmética ni veredicto; su suite completa pasó5/5 en0,40s. La segunda ejecución completa comprueba ese ajuste.

Producto591:17 finales correctos desde el módulo productivo, sin hooks; GPU3583,559MiB y árbol de Baxy.exe2427,707MiB de RAM. El perfil sigue siendo candidato por entorno. Producto592 con base sin adaptador:29/35 finales correctos;6 fallos conservados de identidad, atribución de nombre y gramática. Se cubren cuatro requisitos de agradecimiento y se reabre H0021 por la generalización inglesa fallida.

Encuesta16 cubiertos/726 abiertos/0 no aplicables,742/rev1248 original intacto. BAXY manual cerrado; sin decisión pendiente del dueño; C03 EN_CURSO. Faltan corregir592, verificar el registro sin override, recursos conjuntos con interfaz/voz, resto de encuesta/ocho rutas, recuperación y aceptación final. Este Full no cierra C03.
'''
(out / 'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
attributes = root / '.gitattributes'
line = '/artifacts/comprobaciones/C03/astra-cpu-adapter590/** -text'
assert line not in attributes.read_text(encoding='utf-8')
with attributes.open('a', encoding='utf-8', newline='\n') as stream:
    stream.write(line + '\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n' + note)
(base / 'HANDOFF.md').write_text(note, encoding='utf-8', newline='\n')
state = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
state.update(confirmedAtUtc=result['utc'], checkpoint='590: cross-language Full exit0; omissions disclosed, no source mutation during gate.59117 correct no-hook CPU finals;59229/35 correct,6 failures retained. CPU adapter support validated, manifest unchanged. Survey16/726/0.', continuation='Publish validated590 source and591/592 evidence. Diagnose592 knowledge-to-unsupported transformation, then repair identity/grammar. Joint UI/voice/memory and registered promotion pending; finish remaining C03 criteria.')
write(base / 'RELEVO_ACTIVO.json', state)
print(json.dumps(result, ensure_ascii=False))
