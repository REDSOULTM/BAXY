from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-private-precedence418'
out.mkdir(exist_ok=False)
for name in ['baseline', 'fixture-failure', 'focal']:
    shutil.copyfile(Path(os.environ['TEMP']) / f'c03-memory418-{name}.log', out / f'{name}.log')
(out / 'DIAGNOSTICO.md').write_text('''# 418 — la ruta privada precede a una aclaración pública obsoleta

MindShellEndToEndTests nuevos reproducen cuatro solicitudes ES/EN de recall/status
tras «Haz eso»: antes sumaban dos decisiones públicas y no llegaban al journal
privado. El baseline conserva además un fallo de fixture al leer el journal con
FileShare incorrecto; no se presenta como cuatro fallos puros de producto.
El primer postcambio sólo falló por ese lector y por exigir un outbox existente
cuando no había ninguna operación. Se corrigieron los fixtures, sin relajar
la conducta: lectura compartida y ausencia explícita del outbox en cancelación.
Seis pruebas finales pasan (26 s, cero skips), sin cambios adicionales de producto.

MainWindowViewModel consume el resultado tipado de memoria antes de reutilizar
la aclaración pública. NoRoute y AskToSave conservan el flujo mental: un nombre
dicho en conversación no autoriza escritura. Las solicitudes reconocidas siguen
por MemoryTurnSession y mantienen confirmación exacta, cifrado y causas reales.
También se prueba solicitud de nombre faltante→cancelación sin operación.
No nueva lista de frases, caché de nombres, router ni compositor.

Herencia: MemoryTurnSession.TryResolveSaveInput ya cede ante una ruta privada
independiente; MindClarificationPolicy diferencia petición completa y fragmento.
La biblioteca gemma4-agent/.../02_router/research/7_nlu.md:24–34 propone contratos
de slots, pero su límite arbitrario de turnos no se adopta. La documentación
[Rasa Forms](https://legacy-docs-oss.rasa.com/docs/rasa/forms/) distingue entradas
que completan un slot de interrupciones que cambian el objetivo (consulta
2026-09-08). Se reutiliza aquí el contrato privado ya reconocido; no se importa
el framework ni se añade un clasificador. La adopción se decide con tests locales
y producto, no con métricas ajenas.

Regresión de owners en curso; Fast y producto419 todavía pendientes. No Full
durante reparación. Última fuente completamente validada antes de418:416.
''', encoding='utf-8', newline='\n')
source = (root / 'scratchpad/c03-product404b.py').read_text(encoding='utf-8')
for old, new in [('astra-stored-product404b', 'astra-private-product419'), ('C03-stored-product404b-private', 'C03-private-product419-private'), ('C03-stored-profile404b', 'C03-private-profile419'), ('c03-owner404b-hook', 'c03-owner419-hook')]:
    source = source.replace(old, new)
start = source.index('cases = [')
end = source.index('\ncommands =', start)
source = source[:start] + '''cases = [
    "My name is Jordan. Remember my name.",
    "confirm",
    "Abre una aplicación.",
    "What name have you saved in private memory?",
    "Me llamo Álvaro.",
    "Abre una aplicación.",
    "¿Qué nombre tienes guardado en tu memoria privada?",
    "¿Cómo me llamo?",
]
''' + source[end:]
fields = {
    'method': 'Eight synthetic development turns in a new isolated real conductor profile. Same404b name/enable/store/read/conversation sequence, with an underspecified application request inserted before each explicit stored-name read. Source418 gives the already typed private request precedence over the pending public clarification, preserving exact private confirmation. Source416 OS fix also present but no OS requests. No prompt/model/sampler/decision injection. Record whether each inserted request really leaves clarification pending; only then claim the targeted scenario was exercised. Not fresh acceptance, UI or physical voice.',
    'criteria': 'T1 honestly requests enabling, T2 accepts exact pending enable and resumes authorized synthetic save. T3/T6 clarify the missing application without inventing a target; T4/T7 perform a private recall despite that pending public clarification. Stored name is Jordan, current conversational name is Alvaro, with correct human subject and no unrequested overwrite. Prose failure is separate from successful private dispatch. Check every final, operation and native call; admission200 is not acceptance.'}
lines = []
for line in source.splitlines():
    key = next((k for k in fields if line.startswith('    ' + repr(k) + ':')), None)
    lines.append('    ' + repr(key) + ': ' + repr(fields[key]) + ',' if key else line)
source = '\n'.join(lines) + '\n'
target = root / 'scratchpad/c03-private-product419.py'
assert not target.exists()
compile(source, str(target), 'exec')
target.write_text(source, encoding='utf-8', newline='\n')
hook = root / 'scratchpad/c03-owner419-hook'
hook.mkdir(exist_ok=False)
text = (root / 'scratchpad/c03-owner404b-hook/sitecustomize.py').read_text(encoding='utf-8').replace('C03-stored-product404b-private', 'C03-private-product419-private')
(hook / 'sitecustomize.py').write_text(text, encoding='utf-8', newline='\n')
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    path = base / name
    text = path.read_text(encoding='utf-8').replace('memoria418 en diagnóstico', 'memoria418 en validación')
    start = text.index('Siguiente418:')
    end = text.index('\n\nPendiente:', start)
    text = text[:start] + '''418 corrige MainWindowViewModel: una ruta/contrato privado reconocido limpia
la aclaración pública anterior; NoRoute/AskToSave siguen por mente. Seis pruebas
focales pasan, 0 skips/26 s, incluidos faltar nombre→cancelar sin escribir.
Baseline reprodujo dos llamadas mentales extra y ausencia de lectura; también
hubo defectos de fixture (journal compartido/outbox inexistente), ya corregidos.
Owners de memoria/aclaración en curso; después Fast. Producto419 está preparado
en scratchpad/c03-private-product419.py (aún no ejecutar hasta validación).
Cerrar servidores de compilación inactivos antes para liberar su RAM; encuesta
no se toca. Ocho sintéticos: 404b más pedir app sin nombre antes de ambos recall.
Ver astra-private-precedence418/DIAGNOSTICO.md. No nueva fuente420 ni modelo activo.
''' + text[end:]
    path.write_text(text, encoding='utf-8', newline='\n')
path = base / 'RELEVO_ACTIVO.json'
relay = json.loads(path.read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint='Source418 focal6 pass; owners running;416/417 OS correction preserved.', continuation='Finish memory/clarification owner suite, run Fast, release idle build servers then product419, which is prepared only. Full C03 active.')
path.write_text(json.dumps(relay, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print('418 checkpoint current;419 prepared, not started')
