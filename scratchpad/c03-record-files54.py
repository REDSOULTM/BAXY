"""Record exact consumed development evidence, never human acceptance."""
from pathlib import Path
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
panels = ['files53-baseline', 'files53-candidate', 'files53-boundary', 'files54-literals']
lines = ['# C03 — lecturas de archivo, tramos53–54', '',
         'Cinco controles técnicos consumidos; no son reserva humana ni prueba de UI/voz.',
         'La confirmación del dueño sobre tres turnos ingleses sigue limitada a ADMISIBLE_DUENO; '
         'estos archivos no proceden de ella.'.replace('ADMISIBLE_DUENO', 'ADMISIBILIDAD_DUENO_2026-09-06.md'), '',
         'Se prepararon archivos UTF8, UTF8 inválido y dos homónimos dentro/fuera del sandbox. '
         'CASES.json conserva rutas, contenido esperado y hashes. No se solicitó escribir ni borrar.', '']
for panel in panels:
    directory = base / ('astra-' + panel)
    result = json.loads((directory / 'RESULT.json').read_text(encoding='utf-8'))
    turns = json.loads((directory / 'paired.json').read_text(encoding='utf-8'))
    useful = 2 if panel == 'files54-literals' else 1
    lines += [f'## {panel}: {useful}/5 útiles', '',
              f"{result['elapsedSeconds']}s; GPU{result['gpuPeakMiB']:.2f}MiB; RAM{result['ramPeakMiB']:.2f}MiB; "
              f"exit{result['exitCode']}; registro intacto={result['registrationUnchanged']}.", '',
              f'Evidencia: [paired.json](astra-{panel}/paired.json), '
              f'[CASES.json](astra-{panel}/CASES.json).', '']
    for index, turn in enumerate(turns):
        lines += [f"### {turn['turnId']}", '', f"Entrada: {turn['request']}", '',
                  f"Final ({turn['terminal']}): {turn['final']}", '']
        labels = list(dict.fromkeys(e['label'] for e in turn['publicEvents']
                                   if e.get('type') == 'boot_stage' and e.get('label')))
        for label in labels:
            lines += [f'Progreso visible: {label}', '']
        if index == 4:
            verdict = 'Útil: hora observada y sesión recuperada.'
        elif panel == 'files54-literals' and index == 1:
            verdict = 'Útil: contenido UTF8 real; búsqueda y lectura comparten la identidad verificada. '
            verdict += 'El progreso sólo narra trabajo pendiente.' if labels else 'Sin aviso verbal adicional.'
        elif panel == 'files53-baseline':
            verdict = 'No útil: repide ruta ya proporcionada o pide un ID interno; no leyó el archivo.'
        elif index == 1 and panel == 'files53-boundary':
            verdict = 'No útil: el provider sí leyó y el borrador fue fiel, pero el veto del filename impidió publicarlo.'
        elif index == 2:
            verdict = 'No útil: falta prosa final que conserve la causa real del archivo UTF8 inválido.'
        else:
            verdict = 'No útil: el error interno no explica el límite solicitado; no acredita búsqueda global ni identidad exterior.'
        lines += [f'Adjudicación: {verdict}', '']
(base / 'PRUEBAS_ARCHIVOS53_54.md').write_text('\n'.join(lines), encoding='utf-8')
paths = [
    'src/baxy_mind/planner.py', 'src/baxy_mind/__main__.py', 'src/baxy_mind/llm.py',
    'src/Baxy.Kernel/Planning/MissionPlanProposal.cs', 'src/Baxy.App/UserMessagePolicy.cs',
    'tests/test_turn_policy.py', 'tests/test_compose_contract.py',
    'tests/Baxy.Kernel.Tests/MissionPlanValidatorTests.cs',
    'tests/Baxy.Integration.Tests/PlannerAppBoundaryTests.cs',
    'tests/Baxy.Integration.Tests/C03FactPreservationTests.cs',
    'artifacts/comprobaciones/C03/PRUEBAS_ARCHIVOS53_54.md',
]
for panel in panels:
    paths += [f'artifacts/comprobaciones/C03/astra-{panel}/{name}'
              for name in ('RESULT.json', 'PREREG.json', 'CASES.json', 'paired.json')]
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
pins = {'kind': 'integrated files53/54 source and consumed development, not C03 acceptance',
        'runtimeManifestSha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
        'files': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}}
(base / 'TRAMO54_PINS.json').write_text(json.dumps(pins, indent=2), encoding='utf-8')
print(json.dumps({'report': 'PRUEBAS_ARCHIVOS53_54.md', 'panels': len(panels), 'sourcePins': len(paths)}))
