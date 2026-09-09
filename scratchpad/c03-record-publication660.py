"""Record the verified source publication, without closing any criterion."""
from pathlib import Path
import json
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
commit = 'db47edca6f521e29ca102b830b2134f3489337b9'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip() == commit
remote = subprocess.check_output(['git','ls-remote','--heads','origin','Goal-c03'],cwd=root,text=True).split()[0]
assert remote == commit
note = ('Fuente660 publicada en '+commit+', remoto verificado y main intacto. '
        'Contrato factual acotado: misma cohorte104 mejora60 fallos/44 pases a104 pases; '
        'compositor completo con transporte simulado, sin otro modelo ni inferencia. '
        'Dueñas4046 pases+121 subpruebas/0 skips; declaraciones22 pases/1 skip ambiental; Fast0. '
        'Producto661 mantiene23/24 y las24 respuestas655 sin cambios; jerga española pendiente. '
        'Full651 es línea base anterior, no Full660 ni cierre global. '
        'Encuesta26/716/0; UI/voz conjunta, cobertura y Full final siguen pendientes.')
matrix = root / 'documentacion/sprints/Sprints comprobación/03_MATRIZ_DE_CRITERIOS.md'
lines = matrix.read_text(encoding='utf-8').splitlines()
assert not any(commit in line for line in lines)
count = 0
for index,line in enumerate(lines):
    if line.startswith(('| G04.06 /','| G06.01 /')):
        assert '| C03 |' in line
        lines[index] = line[:-1]+' '+note+' |'
        count += 1
assert count == 2
matrix.write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
state_path = base / 'RELEVO_ACTIVO.json'
state = json.loads(state_path.read_text(encoding='utf-8-sig'))
state.update(publishedSourceCommit=commit,publishedEvidenceCommit=commit,
             checkpoint=note,activeValidation=None,
             continuation='Aislar fuga del metadato foreground en prosa655/661 con payload y primera petición reales. Después continuar encuesta y cierreC03. No decisiones pendientes ni procesos activos.',
             previousGoalTurnClassification='progress',
             previousGoalTurnClassificationReason='Contrato factual660 adoptado y publicado;104 focales,4046 dueñas+121 subpruebas,Fast verde; producto661 sin regresión observada.')
state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for name in ['CHECKPOINT.md','HANDOFF.md']:
    with (base/name).open('a',encoding='utf-8',newline='\n') as stream:
        stream.write('\n\n## Publicación660 verificada — estado vigente\n\n'+note+'\n\n'
            'Sesiones79799/85214/6196 terminadas y recogidas exit0. BAXY manual cerrado; no campaña activa. '
            'Prepare660,close660-661,record-publication660 ejecutados: no repetir. Auditoría660-661 de sólo lectura:19 pins públicos y fuentes/privados/registro/encuesta/main verificados; índice auditado antes del commit. '
            'Siguiente: diagnóstico de la fuga foreground con el primer borrador real t24 de655/661 y controles ES/EN, conservando todos los hechos; sin vetar una palabra ni añadir respuestas fijas. '
            'Índice de biblioteca y títulos revisados; falta contraste acotado y prueba nativa para ese siguiente defecto. No se ha iniciado ni editado otra fuente.\n')
print({'publication':commit,'matrix_rows_annotated':count,'status_changed':False,'goal_complete':False})
