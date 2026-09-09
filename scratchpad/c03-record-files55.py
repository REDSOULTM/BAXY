from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
lines = ['# C03 — tipos de error y diagnóstico55', '',
         'Controles técnicos, no reserva humana ni UI/audio. Ambos paneles:1/5 útil, sólo la hora.', '']
paths = ['src/Baxy.App/MainWindowViewModel.cs', 'src/Baxy.App/UserMessagePolicy.cs']
for name in ('files55-trace', 'files55-reason'):
    directory = base / ('astra-' + name)
    result = json.loads((directory / 'RESULT.json').read_text(encoding='utf-8'))
    lines += [f'## {name}', '',
              f"exit{result['exitCode']};{result['elapsedSeconds']}s;GPU{result['gpuPeakMiB']:.2f}MiB;"
              f"RAM{result['ramPeakMiB']:.2f}MiB;registro intacto={result['registrationUnchanged']}.", '']
    for turn in json.loads((directory / 'paired.json').read_text(encoding='utf-8')):
        lines += [f"### {turn['turnId']}", '', f"Entrada: {turn['request']}", '',
                  f"Final ({turn['terminal']}): {turn['final']}", '']
        labels = list(dict.fromkeys(e['label'] for e in turn['publicEvents']
                                   if e.get('type') == 'boot_stage' and e.get('label')))
        for label in labels:
            lines += [f'Progreso visible: {label}', '']
        lines += [('Útil: hora observada y sesión recuperada.' if turn['turnId'] == 't5'
                   else 'No útil: la causa no permite resolver el pedido o falta prosa final. '
                        'Encontrar una entrada no basta para afirmar que se leyó. '
                        'El progreso de t3 en reason infiere UTF8 del nombre antes de una observación.'), '']
    lines += [f'[Hechos, borradores y vetos](astra-{name}/paired.json).', '']
    paths += [f'artifacts/comprobaciones/C03/astra-{name}/{file}'
              for file in ('RESULT.json', 'PREREG.json', 'paired.json')]
report = base / 'PRUEBAS_TIPOS_ERROR55.md'
report.write_text('\n'.join(lines), encoding='utf-8')
paths += ['artifacts/comprobaciones/C03/PRUEBAS_TIPOS_ERROR55.md']
(base / 'TRAMO55_PINS.json').write_text(json.dumps({
    'scope': 'C# repair source and consumed diagnostic captures; not complete C03 acceptance',
    'files': {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths}
}, indent=2), encoding='utf-8')
print('PRUEBAS_TIPOS_ERROR55.md y TRAMO55_PINS.json escritos')
