from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess
root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-context-answer555'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert '1936 passed' in (out/'owners-after.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out/'fast.log').read_text(encoding='utf-8-sig')
assert 'All checks passed!' in (out/'ruff-tests.log').read_text(encoding='utf-8-sig')
(out/'test_planner.py.before').write_bytes(subprocess.run(['git','show','HEAD:tests/test_planner.py'],cwd=root,capture_output=True,check=True).stdout)
note='''# Tramo555 — interpretación interna separada de respuesta visible

La captura nativa543:27 produce direct_answer idéntica a «Eso era todo, gracias.» y resolved_meaning «El usuario ha indicado…». El código descartaba el eco y publicaba ese segundo campo. Se elimina únicamente esta alternativa: sólo direct_answer puede publicarse; si no sirve, se usa el reintento directo acotado que ya existía y se conserva ValueError si vuelve a fallar. Sin plantilla visible, capa nueva ni cambio de modelo.

Test-first5 fallos/1pass; focal6pass0,67s. Dueñas iniciales2fallos/1934pass mostraron pruebas antiguas que exigían publicar resolved_meaning; se actualizaron para exigir el reintento, la causa original y una respuesta dirigida a la persona. Dueñas finales1936pass+121subtests,0skips,17,15s. STT12pass/1skip ambiental,1,32s. Fast verde, Release21,57s,0advertencias/errores. Ruff de las dos pruebas después de corregirlas verde. Árbol STT actual5a3d37d79c0e4b7366c3d7857b699a32c9d6e1b84df9d794f89bc3dea890415d/403archivos; históricos intactos. SóloPython; Full final pendiente.

Encuesta7cubiertos/735abiertos/0NA, sin crédito aún para despedida: falta producto556. Preparada una corrida aislada con contexto CPU/volumen, despedidasES/EN y recuerdo literal, sinUI/voz. No reabrir BAXY manualmente.

554 no llegó a lanzar el modelo: su preflight esperó20 escritores y encontró18 porque la despedida iba por otro resolvedor. Esa diferencia permitió identificar la transformación errónea de555. No se adjudica calidad ni recursos aGemma554; la comparación no se ejecutó y deja de ser el siguiente paso.
'''
(out/'RESULT.md').write_text(note,encoding='utf-8',newline='\n')
write(out/'RESULT.json',{'adopted':True,'owners':{'passed':1936,'subtests':121,'skips':0,'seconds':17.15},'stt_declarations':{'passed':12,'environmental_skips':1,'seconds':1.32},'fast':'passed','release_seconds':21.57,'product_verification':'pending556','survey':{'covered':7,'open':735,'not_applicable':0}})
preflight=base/'astra-gemma-current-writer554'
(preflight/'RESULT.md').write_text('''# Gemma554 — no ejecutado

El preflight esperaba20 casos de escritor y obtuvo18; abortó antes de crear servidor o hacer inferencia. El supuesto incorrecto era que la despedida pasaba por la misma composición. La captura543:27 demuestra otro resolvedor y la publicación indebida de resolved_meaning. Se abandona este ensayo de modelo en favor de reparar esa transformación en555. No hay medición ni rechazo del modelo aquí; script conserva la hipótesis inicial y la aserción que falló.
''',encoding='utf-8',newline='\n')
with (root/'.gitattributes').open('a',encoding='utf-8',newline='\n') as stream:
    for folder in ('astra-gemma-current-writer554','astra-context-answer555'):
        stream.write('/artifacts/comprobaciones/C03/'+folder+'/** -text\n')
        path=base/folder
        write(path/'PINS.json',{p.name:sha(p) for p in path.iterdir() if p.is_file() and p.name!='PINS.json'})
with (base/'CHECKPOINT.md').open('a',encoding='utf-8',newline='\n') as stream:stream.write('\n\n'+note)
handoff=base/'HANDOFF.md'
handoff.write_text('# Handoff C03 — 555\n\n'+note.split('\n\n',1)[1]+'\nAntecedentes553 (sus fallos siguen salvo verificación posterior):\n\n'+handoff.read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
state=read(base/'RELEVO_ACTIVO.json')
state.update(checkpoint='555: internal resolved meaning no longer published;1936pass+121subtests/Fast green; product556 pending.',continuation='Publish source555 then verify contextual closings and literal recall in product556. Survey7/735/0; C03 active.',confirmedAtUtc=datetime.now(timezone.utc).isoformat())
write(base/'RELEVO_ACTIVO.json',state)
print('Source555 adopted with green owners and checkpoint; product556 pending.')
