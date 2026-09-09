"""Update owned matrix evidence only after the validated source is published."""
from pathlib import Path
import json
import subprocess

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
result = json.loads((base/'astra-window-regression651/RESULT.json').read_text(encoding='utf-8'))
assert result['adopted'] and result['full_exit'] == 0
def git(*args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()
commit = git('rev-parse', 'HEAD')
assert git('branch', '--show-current') == 'Goal-c03'
assert commit == git('rev-parse', 'origin/Goal-c03')
assert git('rev-parse', 'main') == '5f572ee1b48cb5e2543ee5e06510e51057c9c845'
py = result['python']
net = sum(r['passed'] for r in result['dotnet'])
net_skips = sum(r['skipped'] for r in result['dotnet'])
evidence = (
    f'Fuente combinada 646/651 publicada en {commit}, remoto verificado y main intacto. '
    f'Full 651: Python {py["passed"]} pases, {py["skipped"]} skips y {py["subtests"]} subpruebas; '
    f'.NET {net} pases, {net_skips} skips agregados y {result["dotnet_printed_omissions"]} omisiones opt-in impresas aparte. '
    'Dueñas: 3521 pases + 121 subpruebas, sin skips; R4/R5/R6: 1408 pases; alcance: 97 pases; Fast exit 0. '
    'Full 646 rojo conservado: 24 regresiones originadas en 633 reparadas sin cambiar oráculos. '
    'Producto 647, anterior a 651: 18/20 finales correctos y cuatro referencias recuperadas; contrato factual 649: 4/11. '
    'Siguen prosa sin respaldo e idioma. Encuesta: 25 cubiertos, 717 abiertos, 0 no aplicables. No cierra C03 ni acredita UI/voz conjunta.'
)
p = root/'documentacion/sprints/Sprints comprobación/03_MATRIZ_DE_CRITERIOS.md'
lines = p.read_text(encoding='utf-8').splitlines()
counts = {}
for i, line in enumerate(lines):
    for case in ['G04.06', 'G06.06']:
        if line.startswith(f'| {case} /'):
            cells = line.split('|')
            assert cells[3].strip() == 'C03'
            cells[4] = ' CUMPLIDO '
            cells[5] = ' '+evidence+' '
            lines[i] = '|'.join(cells)
            counts[case] = counts.get(case, 0)+1
    if line.startswith('| G06.01 /'):
        cells = line.split('|')
        assert cells[3].strip() == 'C03' and cells[4].strip() == 'PENDIENTE'
        cells[5] = (' [CIEN.md](../../../artifacts/comprobaciones/C03/CIEN.md) histórico conservado; '
            'sin sello de cierre. Autorización del dueño 536 permite histórico, encuesta y casos nuevos, '
            'sin requisito de material inédito y distinguiendo procedencia. '
            'Encuesta de 742 casos: 25 cubiertos, 717 abiertos y 0 no aplicables individualmente; '
            'no equivale a 717 fallos de producto. Producto 647 acredita 18/20 finales; quedan prosa e idioma. '
            'no cumple cien respuestas ni acredita UI/voz conjunta. ')
        lines[i] = '|'.join(cells)
        counts['G06.01'] = counts.get('G06.01', 0)+1
assert counts == {'G04.06': 1, 'G06.01': 1, 'G06.06': 1}, counts
p.write_text('\n'.join(lines)+'\n', encoding='utf-8', newline='\n')
state_path = base/'RELEVO_ACTIVO.json'
state = json.loads(state_path.read_text(encoding='utf-8'))
state.update(publishedSourceCommit=commit, publishedEvidenceCommit=commit)
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print({'source_commit': commit, 'matrix_rows_updated': list(counts), 'foreign_rows_changed': False})
