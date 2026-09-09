"""Close the source ownership change and prepare its real protocol regression."""
from datetime import datetime,timezone
import difflib,hashlib,json,os
from pathlib import Path
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
out=base/'astra-chat-owner506';private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-chat-owner506-private'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert '3404 passed, 121 subtests passed in 53.88s' in (out/'owners.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out/'fast.log').read_text(encoding='utf-8-sig')
files=['src/baxy_mind/llm.py','src/baxy_mind/__main__.py','tests/test_turn_policy.py']
(out/'SOURCE.patch').write_text(''.join(''.join(difflib.unified_diff((private/Path(name).name).read_text(encoding='utf-8-sig').splitlines(True),(root/name).read_text(encoding='utf-8-sig').splitlines(True),fromfile='before506/'+name,tofile='source506/'+name)) for name in files),encoding='utf-8')
write(out/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'baseline':{'failed':2,'passed':7,'seconds':1.95},'focal':{'passed':9,'seconds':.83},'owners':{'passed':3404,'subtests_passed':121,'skips':0,'seconds':53.88,'session':38298,'exit':0},'fast':{'passed':True,'release_seconds':3.32,'warnings':0,'errors':0,'session':16397,'exit':0},'source_sha256':{name:sha(root/name) for name in files},'change':'Remove native conversation_reply production/propagation and initial_reply chat bypass. Existing proper chat generation and speculative chat cache remain; guards and context scoping unchanged. No prompts, sampler or model changed.','limits':'505 two quality failures remain; integrated protocol507 next. No Full, UI, effects or acceptance.'})
(out/'RESULT.md').write_text('''# La conversación redacta la respuesta

Se retiró por completo el transporte conversation_reply desde el selector nativo hasta chat y el parámetro initial_reply que omitía su generación. La conversación existente conserva identidad, idioma, historial, guardas y reparaciones. El cache de conversación especulativa permanece: ya contiene una respuesta generada por chat, no prosa de selección. No se añadieron prompts, respuestas fijas ni capas.

Baseline2fallos/7pass; final9pass0,83s. Siete suites3404pass y121subtests, cero skips,53,88s. Fast verde; Release3,32s sin warnings/errors. Sesiones38298/16397 recogidas exit0; servidores de build cerrados. La definición inexacta y el recuerdo falso de505 siguen abiertos y no se ocultan tras estas pruebas verdes.
''',encoding='utf-8')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
script=(root/'scratchpad/c03-audio-mind504.py').read_text(encoding='utf-8-sig').replace('504','507')
panel=json.loads((base/'astra-chat-draft505/PREREG.json').read_text(encoding='utf-8-sig'))['cases'][1:]
marker="manifest=Path(os.environ['LOCALAPPDATA'])"
assert marker in script
script=script.replace(marker,'cases.extend('+repr(panel)+')\n'+marker,1)
start=script.index("'method':");end=script.index("'profile_reason':",start)
script=script[:start]+"'method':'Source506 integrated into actual mind/turn/plan/arguments, no treatment hook. Same14audio cases as504 plus six consumed conversation/name controls from505.20 total. Only existing observation hooks; actual catalog/E5. No provider execution, shell or audio.',"+script[end:]
target=root/'scratchpad/c03-audio-chat507.py';assert not target.exists();target.write_text(script,encoding='utf-8')
checkpoint=base/'CHECKPOINT.md';s=checkpoint.read_text(encoding='utf-8-sig')
start=s.index('Siguiente506,');end=s.index('\nCambios previos',start)
s=s[:start]+'''506 validado: la prosa del selector ya no entra a conversación. Parámetros/propagación retirados; misma generación/guardas/cache de chat. Baseline2fallos/7pass→9pass0,83s. Owners3404pass+121subtests,0skips53,88s (38298exit0). Fastverde/Release3,32s0warnings/errors (16397exit0). Buildservers cerrados. Fuente effect_intent503,__main__506,llm506. No runtime/prueba/build activo.

Siguiente507: ejecutar scratchpad/c03-audio-chat507.py. Mismos14audio+6conversación de505, sin hook de tratamiento.20total; validar propuesta/argumentos y no adjudicar definiciones/recall por selección vacía. Después, comparar perfil oficial Qwen2507 en conversación antes de tratar fallos restantes como incapacidad de modelo. Fuente primaria perfil ya verificada; no otro barrido de selector. Paper2602.24287v2 describe contaminación por respuestas propias y filtrado selectivo, no acredita borrar todo historial.505privateHTTP25 recibe Jordan humano y Morgan asistente correctamente tipados; falla el razonamiento de procedencia. Carter memory audit13/54–63 distingue fuente pero propone OS prioritario, contrario a identidad vigente: no heredar esa regla.
''' + s[end:]
s=s.replace('# C03: fuente 503 validada y protocolo 504 cerrado','# C03: fuente 506 validada; protocolo 507 preparado')
s=s.replace('Fuente effect_intent503, __main__501, llm466. Siete suites3404pass+121subtests/0skips52,86s y Fast verde/Release3,25s0warnings/errors; sesiones7688 y60961 cerradas.','Fuente effect_intent503, __main__506, llm506. Validación506:3404pass+121subtests/0skips53,88s y Fastverde/Release3,32s0warnings/errors; sesiones38298 y16397 cerradas.')
checkpoint.write_text(s,encoding='utf-8')
(base/'HANDOFF.md').write_text('''# Handoff C03 — fuente506 validada

Goal íntegro activo, Goal-c03/HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. C03_ASTRA_AUTORIDAD.md/identidad/AGENTS mandan; preservar WIP, main, evidencia y encuesta742/rev1248. Sin agentes ni Full durante reparación; BAXY manual cerrado.

Fuente effect_intent503,__main__506,llm506.506 retira prosa del selector/initial_reply, sin prompts ni modelo nuevos. Siete owners3404pass+121subtests/0skips53,88s; Fastverde/Release3,32s0warnings/errors. Sesiones38298/16397 cerradas, buildservers apagados. No procesos activos. PREREG/RESULT/PINS/SOURCE.patch en astra-chat-owner506; manifiesto13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed intacto.

504:13/14propuestas y11/11bindings; audio owner46/51 correcto, sin efectos físicos.505 par privado4/7→5/7; separando chat se corrige prosa interna/actor del nombre, pero definición contiene hecho falso y recall-en repiteMorgan(asistente) sobreJordan(usuario). No aceptar estos fallos por tests verdes. Recursos505RAM1,73GiB/GPU3,42GiB, sólo mente/conductor. Runtime candidato no promovido.

Siguiente: ejecutar scratchpad/c03-audio-chat507.py (20casos consumidos, protocolo real; ningún efecto). Después aislar perfil oficial Qwen2507 de conversación con controles/semillas; luego procedencia si persiste. Paper https://arxiv.org/abs/2602.24287v2 orienta contaminación del historial; no autoriza filtrado global. No editar fuente durante runtime/tests/build.

Cierre pendiente íntegro: ocho rutas y742expectativas/incidentess264;100humanosfrescos certificados/congelados/100de100; averías/recuperación; UI/voz/audiofísico/ASR/wake y≤4GiBconjunto; runtime/instalación/C04–C09; Fullverde/publicación fuera de main. Reserva204potenciales/192únicos,0certificados y0ejecutados; refrescar exposición>483. Detalles/rechazos en CHECKPOINT.md e INVESTIGACION_MODELO_C03.md. No repetir campañas cerradas sin causa nueva.
''',encoding='utf-8')
r=json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'));r.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='Fuente506 validada; sin procesos activos.',continuation='Ejecutar50720casos reales de protocolo; después perfil de conversación y procedencia. C03 íntegro activo.');write(base/'RELEVO_ACTIVO.json',r)
print('506 closed;507 prepared20cases, no runtime launched yet.')
