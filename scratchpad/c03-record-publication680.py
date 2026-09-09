"""Record an already verified source publication without changing sealed evidence."""
from pathlib import Path
from datetime import datetime, timezone
import json
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
assert commit == 'e2ad0b5c6058d75b077ebc0549273a9945db9d4a'
remote = subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/Goal-c03'], cwd=root, text=True).split()[0]
assert remote == commit
state_path = base / 'RELEVO_ACTIVO.json'
state = json.loads(state_path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), publishedSourceCommit=commit,
    publishedEvidenceCommit=commit,
    checkpoint='680 publicada'+commit+'; título reparado;2589dueñas+121subtests/0skip,600declaraciones/1skip ambiental,Fast0;679 corregido3/7,6814/7,682 completo.',
    continuation='Reparar lectura fresca de t3/t5 sin cambiar sus entradas: effect_intent.py y frontera observation_not_recital en __main__.py. Prosa mixta682 permanece abierta. Encuesta26/716/0 y alcance íntegroC03; no publicación pendiente de fuente680.')
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
path = base / 'HANDOFF.md'
text = path.read_text(encoding='utf-8').replace('fuente680 adoptada; publicación pendiente', 'fuente680 publicada; lecturas frescas pendientes')
text = text.replace('Fuente anterior publicada2138d2d6; HEAD previo a680d7776f8e.', 'Fuente680 publicada en'+commit+', remoto verificado. Este registro sólo cambia documentación.')
text = text.replace('Siguiente tras publicación:', 'Siguiente:')
path.write_text(text, encoding='utf-8', newline='\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n# Publicación680 verificada\n\nFuente/evidencias publicadas en '+commit+', remoto Goal-c03 verificado; main intacto.25pins públicos y de índice, privados, fuente/tree, encuesta y manifiesto auditados. Producto cerrado, sin campañas pendientes. Los logs crudos preservan CRLF y tres espacios finales de pytest; el chequeo de whitespace de fuente/documentación está limpio, no se reescriben logs sellados para cambiar su formato. Siguiente: lectura fresca t3/t5; prosa mixta682 abierta. Encuesta26cubiertos/716abiertos/0NA; C03 EN_CURSO.\n')
path = root / 'documentacion/sprints/Sprints comprobación/03_MATRIZ_DE_CRITERIOS.md'
lines = path.read_text(encoding='utf-8-sig').splitlines()
for index, line in enumerate(lines):
    if line.startswith('| G04.06 /') or line.startswith('| G06.06 /'):
        assert line.endswith('|')
        lines[index] = line[:-1] + ' Fuente680 publicada'+commit+' y remoto verificado, dueñas2589+121subtests/0skip y Fast0; evidencia679/681/682 sellada. C03 global continúa abierto. |'
path.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
print({'published_source': commit, 'remote_verified': True})
