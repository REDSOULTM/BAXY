"""Record verified source publication without changing product or survey data."""
from pathlib import Path
from datetime import datetime, timezone
import json
import subprocess

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
commit='2138d2d6e96d79c2cda025bd9f7c2367744abb3b'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==commit
assert subprocess.check_output(['git','ls-remote','origin','refs/heads/Goal-c03'],cwd=root,text=True).split()[0]==commit
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=root,text=True).strip()
state_path=base/'RELEVO_ACTIVO.json'
state=json.loads(state_path.read_text(encoding='utf-8-sig'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),publishedSourceCommit=commit,publishedEvidenceCommit=commit,
    checkpoint='676 publicada2138d2d6;dueñas2566+121subtests/0skips,declaraciones600/1skip ambiental,Fast0;67717/17 y67824/24.',
    continuation='Siguiente: acreditar H0104 con literal y variantes del producto, sin crédito por familia. Fuente676 publicada y árbol limpio al verificar remoto; main/registro/encuesta intactos. Resto C03 completo sigue abierto.',activeValidation=None)
state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
handoff=base/'HANDOFF.md'
text=handoff.read_text(encoding='utf-8')
text=text.replace('# C03 — fuente676 adoptada; publicación pendiente de verificar','# C03 — fuente676 publicada; continuación de cobertura')
text=text.replace('Último HEAD publicado antes de676: a97e1142fad493af888d0c56a240a79947379f7c.', 'Fuente676 publicada en2138d2d6e96d79c2cda025bd9f7c2367744abb3b, remoto verificado y árbol limpio. Este registro de publicación sólo cambia documentación.')
text=text.replace('Siguiente acción: auditar y publicar676–678 antes de otra fuente. Después H0104', 'Siguiente acción: H0104')
text=text.replace('La auditoría nueva de publicación será de sólo lectura.', 'Auditoría audit-publication676-678 pasó:21pins públicos/índice,privados,fuentes/declaraciones/main/registro/encuesta verificados. Es de sólo lectura; record-publication676 ya ejecutado.')
handoff.write_text(text,encoding='utf-8',newline='\n')
note='\n\n## Publicación676 verificada\n\nFuente2138d2d6e96d79c2cda025bd9f7c2367744abb3b coincide con origin/Goal-c03; árbol limpio y main intacto al verificar. Auditoría21pins públicos/índice, privados y fuentes/declaraciones/registro/encuesta correcta. Dueñas2566+121subpruebas/0skips, declaraciones600pases/1skip ambiental, Fast0; compositor67717/17 y producto67824/24. Encuesta26/716/0; ninguna fila global de C03 se cierra con esta tanda.\n'
with (base/'CHECKPOINT.md').open('a',encoding='utf-8',newline='\n') as stream: stream.write(note)
matrix=root/'documentacion/sprints/Sprints comprobación/03_MATRIZ_DE_CRITERIOS.md'
lines=matrix.read_text(encoding='utf-8').splitlines()
for i,line in enumerate(lines):
    if line.startswith('| G04.06 /') or line.startswith('| G06.06 /'):
        assert line.endswith('|')
        lines[i]=line[:-1]+' Fuente676 publicada2138d2d6e96d79c2cda025bd9f7c2367744abb3b, remoto/árbol limpio verificados. Dueñas2566+121subpruebas/0skips,declaraciones600pases/1skip ambiental,Fast0; compositor67717/17 y producto67824/24. Full651 sigue baseline anterior; no cierre global ni UI/voz conjunta. |'
matrix.write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
print({'published_source':commit,'remote_verified':True,'goal_complete':False})
