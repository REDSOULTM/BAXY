from pathlib import Path
import hashlib
import json

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-memory-feedback439'
(out/'RESULT.md').write_text('''# 439 — instrucción factual insuficiente

Ocho casos, once llamadas: las cinco respuestas sanas no se alteran ni se
regeneran; tres contradicciones reciben un feedback. Marta se corrige, Jordan
y Ana María siguen hablando como si fueran BAXY. 5/8→6/8 no cumple el criterio
prerregistrado de 8/8. Todos stop; sin fuente adoptada. No añadir una guarda que
convierta estos fallos en silencios. Recursos en resources.json, cliente cerrado.

440 será la última comparación de feedback: conservar también el borrador real
que se quiere corregir, como propone el mecanismo de refinamiento, en vez de
añadir una instrucción a una primera generación que no ve su error. Mismos datos,
feedback y controles; un reintento máximo. Si falla, abandonar esta estrategia.
''',encoding='utf-8',newline='\n')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
(out/'PINS.json').write_text(json.dumps({p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'},indent=2)+'\n',encoding='utf-8',newline='\n')
source=(root/'scratchpad/c03-memory-feedback439.py').read_text(encoding='utf-8')
source=source.replace('astra-memory-feedback439','astra-memory-refine440').replace('C03-memory-feedback439-private','C03-memory-refine440-private')
source=source.replace("Add the one preregistered factual correction to the existing system message; otherwise identical payload/settings.", "Keep the actual generated assistant draft and append one internal user-role correction using the same439 feedback; otherwise identical payload/settings. This internal feedback is not a new human declaration or acceptance case.")
source=source.replace("438 rejects tool roles on current3.5.", "439 system-only feedback failed2/3 targeted cases. Second and last comparison: let the model see its actual erroneous draft, as refinement requires.438 rejects tool roles on current3.5.")
source=source.replace("payload['messages'][0]['content']+='\\n'+FEEDBACK", "payload['messages'].extend([{'role':'assistant','content':row['answer']},{'role':'user','content':'Correct the preceding answer. '+FEEDBACK}])")
target=root/'scratchpad/c03-memory-refine440.py'
assert not target.exists()
target.write_text(source,encoding='utf-8',newline='\n')
print('439 rejected;440 prepared; source unchanged')
