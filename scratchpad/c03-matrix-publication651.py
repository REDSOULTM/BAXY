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
    f'Fuente combinada646/651 publicada {commit}, remoto verificado y main intacto. '
    f'Full651: Python{py["passed"]}pases/{py["skipped"]}skips+{py["subtests"]}subpruebas; '
    f'.NET{net}pases/{net_skips}skips agregados y{result["dotnet_printed_omissions"]}omisiones opt-in impresas aparte. '
    '3521dueñas+121subpruebas/0skips,1408R4/R5/R6,97scope,Fast0. '
    'Full646rojo conservado:24regresiones originadas en633 reparadas sin cambiar oráculos. '
    '647 antes de651:18/20finales y4referencias recuperadas;649 contrato factual4/11. '
    'Siguen prosa sin respaldo e idioma;25/717/0. No cierreC03 ni UI/voz conjunta.'
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
            'sin sello de cierre. Autorización del dueño536 permite histórico, encuesta y casos nuevos, '
            'sin requisito de material inédito y distinguiendo procedencia. '
            'Encuesta742:25cubiertos/717abiertos/0no aplicables individualmente; '
            'no equivale a717fallos de producto.647acredita18/20finales, quedan prosa/idioma; '
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
