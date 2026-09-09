"""Record the independently verified publication of the fresh-read repair."""
from pathlib import Path
from datetime import datetime, timezone
import json
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
assert commit.startswith('68a27bde')
assert subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/Goal-c03'], cwd=root, text=True).split()[0] == commit
p = base / 'RELEVO_ACTIVO.json'
s = json.loads(p.read_text(encoding='utf-8'))
s.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), publishedSourceCommit=commit,
    publishedEvidenceCommit=commit, checkpoint='683 publicada'+commit+';7682dueñas/0skip,600declaraciones/1skip ambiental,Fast0;6847/7lecturas y4/7finales.',
    continuation='Reparar distinción entre respuesta de identidad y Booleano de foco en window_prose_facts, con datos reales684 y variantes; conservar verificación de contradicciones.683publicada, encuesta26/716/0, ninguna campaña activa.')
p.write_text(json.dumps(s, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
p = base / 'HANDOFF.md'
text = p.read_text(encoding='utf-8').replace('fuente683 adoptada; publicar antes de otra reparación', 'fuente683 publicada; verificación de identidad pendiente')
text = text.replace('Fuente anterior680publicadae2ad0b5c, HEAD previo8c79def4. Ahora683adoptada y aún sin commit.', 'Fuente683publicada'+commit+', remoto verificado. Este registro sólo cambia documentación.')
text = text.replace('Siguiente tras publicación:', 'Siguiente:')
p.write_text(text, encoding='utf-8', newline='\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n# Publicación683 verificada\n\nFuente y evidencias683–685 publicadas en '+commit+'; remoto verificado, main intacto.19pins públicos/índice, privados, fuentes/tree, manifiesto y encuesta auditados; BAXY cerrado. No nueva encuesta:26cubiertos/716abiertos/0NA. Siguiente: distinguir preguntas de identidad de ventana de preguntas Booleanas para eliminar los falsos missing_fact de684 sin dejar pasar contradicciones. C03 EN_CURSO.\n')
p = root / 'documentacion/sprints/Sprints comprobación/03_MATRIZ_DE_CRITERIOS.md'
lines = p.read_text(encoding='utf-8-sig').splitlines()
for i, line in enumerate(lines):
    if line.startswith('| G04.06 /') or line.startswith('| G06.06 /'):
        assert line.endswith('|')
        lines[i] = line[:-1] + ' Fuente683publicada'+commit+' y remoto verificado;7682dueñas/0skip y Fast0, evidencias683–685selladas. C03global abierto. |'
p.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
print({'published_source': commit, 'remote_verified': True})
