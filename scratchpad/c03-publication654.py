"""Record verified source publication without closing any additional criterion."""
from pathlib import Path
import json
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
def git(*args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()
commit = git('rev-parse', 'HEAD')
assert commit == git('rev-parse', 'origin/Goal-c03')
assert git('rev-parse', 'main') == '5f572ee1b48cb5e2543ee5e06510e51057c9c845'
assert json.loads((base / 'astra-language-source654/RESULT.json').read_text(encoding='utf-8'))['adopted']
evidence = (f' Fuente654 publicada en {commit}, remoto verificado. Dueñas3942 pases+121 subpruebas/0 skips, declaraciones22 pases/1 skip ambiental, Fast0. '
            'Producto655: original20/20, ampliado23/24; inglés del foco reparado, variante española con jerga pendiente. '
            'Contrato factual649 sigue abierto. Encuesta26/716/0. Full651 es línea base anterior, no Full654; sin cierre global ni crédito UI/voz conjunta. ')
p = root / 'documentacion/sprints/Sprints comprobación/03_MATRIZ_DE_CRITERIOS.md'
lines = p.read_text(encoding='utf-8').splitlines()
count = 0
for i, line in enumerate(lines):
    if any(line.startswith(f'| {case} /') for case in ['G04.06','G06.01','G06.06']):
        cells = line.split('|')
        assert cells[3].strip() == 'C03'
        cells[5] += evidence
        lines[i] = '|'.join(cells)
        count += 1
assert count == 3
p.write_text('\n'.join(lines)+'\n', encoding='utf-8', newline='\n')
state_path = base / 'RELEVO_ACTIVO.json'
state = json.loads(state_path.read_text(encoding='utf-8'))
state.update(publishedSourceCommit=commit,publishedEvidenceCommit=commit,
             continuation='656 diagnóstico semántico nativo en curso; recoger72764, revisar62 clasificaciones sin promover. Jerga española655 y contrato649 pendientes. Encuesta26/716/0.',
             activeValidation={'kind':'native_fact_judge656','sessionId':72764,'log':'TEMP/c03-native-fact-judge656.log'})
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as f:
    f.write('\n\n## Fuente654 publicada y contraste factual656\n\n'+evidence+'\n\n656 nativo activo72764:31 casos ×2 perfiles,11 del contrato649 y20 controles declarados de generalización. Clasifica apoyo/contradicción/desconocido contra observaciones. No sustituye el validador, no mide estilo ni suficiencia, no crédito de producto. Contraste MiniCheck/encuesta de autocorrección y receta Qwen enlazados en PREREG656. Registrar todos los aciertos y falsos rechazos, incluso si no mejora.\n')
print({'published_source':commit,'matrix_rows':count,'statuses_changed':False})
