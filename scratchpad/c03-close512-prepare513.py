"""Close owner validation and make the integrated regression concrete."""
from datetime import datetime,timezone
import difflib,hashlib,json,os
from pathlib import Path
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
out=base/'astra-knowledge-history512';private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-knowledge-history512-private'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert '3406 passed, 121 subtests passed in 53.88s' in (out/'owners-final.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out/'fast.log').read_text(encoding='utf-8-sig')
files=['src/baxy_mind/llm.py','tests/test_turn_policy.py']
(out/'SOURCE.patch').write_text(''.join(''.join(difflib.unified_diff((private/Path(name).name).read_text(encoding='utf-8-sig').splitlines(True),(root/name).read_text(encoding='utf-8-sig').splitlines(True),fromfile='source506/'+name,tofile='source512/'+name)) for name in files),encoding='utf-8')
write(out/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'baseline':{'failed':6,'passed':1,'seconds':2.66},'focal':{'passed':7,'seconds':.76},'first_owners':{'failed':4,'passed':3402,'subtests_passed':121,'seconds':53.39,'session':8589,'exit':1},'test_contract_update':'Four expectations required the old message sequence. Their exact literals/authors were preserved in data; updated assertions require roundtrip equality and unchanged topic scoping/history, not fewer checks. Four-failure rerun4pass1.47s. Source unchanged after focal implementation.','owners':{'passed':3406,'subtests_passed':121,'skips':0,'seconds':53.88,'session':40969,'exit':0},'fast':{'passed':True,'release_seconds':3.55,'warnings':0,'errors':0,'session':32963,'exit':0},'source_sha256':{name:sha(root/name) for name in files},'change':'Direct knowledge quotes already scoped prior dialogue, preserving all bounded roles/literals; current user request untouched. Same history and provenance first system are used for repair. Semantic reading, stored history, raw audit counts and other presentation shapes remain original. No extra decoder, model, profile, memory entry or visible fixed answer.','limits':'511 private22/22 is not integrated or C03 acceptance; run513 with the actual registeredT0 pipeline next. No effects/UI/voice or Full yet.'})
(out/'RESULT.md').write_text('''# Conocimiento con procedencia conservada

La presentación de conocimiento recibe el historial ya acotado como datos citados con quién escribió cada mensaje. El pedido actual permanece separado e intacto. La regla de procedencia es la misma comprobada en511, y la reparación reutiliza tanto su sistema como sus datos. Los lectores semánticos, el historial almacenado, la auditoría y las demás formas de presentación conservan su contrato anterior. No se añade una generación, un nombre extraído ni una respuesta fija.

Baseline6fallos/1pass2,66s; focal7pass0,76s. La primera suite tuvo4fallos de expectativas de representación; cada literal/autor seguía presente y se actualizaron las aserciones a igualdad roundtrip y preservación del tema. Rerun4pass1,47s. Siete suites finales3406pass+121subtests,0skips53,88s. Fastverde;Release3,55s0warnings/errors. Sesiones40969/32963 cerradas y buildservers apagados.513 probará la integración real sin los hooks de tratamiento.
''',encoding='utf-8')
for name in ['CHECKPOINT.md','HANDOFF.md']:(out/(name.removesuffix('.md')+'-before.md')).write_bytes((base/name).read_bytes())
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
script=(root/'scratchpad/c03-audio-chat507.py').read_text(encoding='utf-8-sig').replace('507','513')
prior=json.loads((base/'astra-chat-provenance509/PREREG.json').read_text(encoding='utf-8-sig'))
extra=[]
for c in prior['cases'][7:11]:
 extra.append({k:v for k,v in c.items() if k not in ['case_id','profile']})
 extra[-1]['id']=c['case_id']
marker="manifest=Path(os.environ['LOCALAPPDATA'])"
script=script.replace(marker,'cases.extend('+repr(extra)+')\n'+marker,1)
start=script.index("'method':");end=script.index("'profile_reason':",start)
script=script[:start]+"'method':'Source512 integrated:14audio cases504 plus six conversation/name controls505 and four provenance/reference controls509;24total. Actual mind/turn/plan/arguments, current registered model/profile, actual catalog/E5. Observation only: no private treatment hooks, provider execution, shell or physical audio. Compare audio bindings and factual/natural conversations against507/511; no empty-selection-as-answer scoring.',"+script[end:]
target=root/'scratchpad/c03-audio-chat513.py';assert not target.exists();target.write_text(script,encoding='utf-8')
old=(base/'CHECKPOINT.md').read_text(encoding='utf-8-sig')
start=old.index('Cambios previos conservados:');end=old.index('\n507 cerrado',start)
legacy=old[start:end]
current='''# C03: fuente512 validada; protocolo513 preparado

Goal íntegro activo. Goal-c03/HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. C03_ASTRA_AUTORIDAD.md, identidad y AGENTS mandan; preservar WIP/main/evidencia. Sin agentes ni Full durante reparación. BAXY manual cerrado; encuesta742/rev1248 y procesos101140/29800 preservados.

Sin runtime/prueba/build activo. Fuente effect_intent503,__main__506,llm512. Siete owners3406pass+121subtests/0skips53,88s (40969exit0);Fastverde/Release3,55s0warnings/errors(32963exit0);buildservers cerrados.512PREREG/RESULT/SOURCE.patch/PINS completos; fallos y estados anteriores preservados. Registro13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed intacto.

512 cita el historial de conocimiento como datos con roles/literales íntegros; misma representación/procedencia al reparar. Mantiene historial original para lectores/auditoría/otrasformas y aplica el acotado de tema antes de citar. Baseline6fallos/1pass→7focalpass; primera suite4expectativasviejas(3402pass+121subtests), actualizadas para probar roundtrip/noamputación; rerun4pass. No modelo/profile nuevo, nombre hardcoded ni decoder adicional.

Siguiente: ejecutar scratchpad/c03-audio-chat513.py.24casos consumidos:14audio,6conversación/nombres,4procedencia/referencia. Protocolo real sin hooks de tratamiento; actualregistroT0. Verificar respuestas una a una, bindings y recursos. Sólo después pasar al resto de las ocho rutas y producto físico; no reservar/aprobar100humanos con esta tanda.

Evidencia reciente:504audio13/14propuestas+11/11bindings;owner46/51correctos,sin efectos.505 prueba que initial_reply publicaba prosa del selector;506retira el atajo/propagación,3404pass+121subtests/Fast.507integrado18/20útiles+11/11bindings, fallaban definición y recuerdo Morgan(asistente) sobreJordan(usuario).

508 perfilQwenoficialvsregistrado, semillas0/17:ambos5/7seed0y6/7seed17 (adjudicaciónv2, v1conservada por excesiva severidad ante un sentido válido de salida de audio).28/28generaciones/84stop; sólo sampling difiere, no mejoraperfil.509reglaprocedenciaconhistorial:original9/11+10/11,regla10/11+10/11;recall-enfalla4/4,otroscontrolesyapasaban. No adoptar regla sola ni más redacción.510misma regla/profile, cambia sólo representación íntegra dehistorial:original10/11+10/11,citado10/11+11/11;Jordancorrecto2/2yMorgancomoanteriorpalabra,peroother-personseed0 tieneaside.511cambia sóloT.7→0en22payloadspareados:22/22útiles,73stop,max85salida;RAM1766,328/GPU3497,559MiB63,984s. NoUI/voz/efectos/aceptación.512adopta representaciónenconocimientoconT0yaexistente, pendiente513.

Fuentes: Qwen2507modelcard para perfil; paper2602.24287v2 para contaminación del historial (la representación citada es hipótesis local, no implementación atribuida al paper). previous_dialogue_for_references_only es una clave de datos en llm7171/fuente506, no una función. Carter memoryaudit13/54–63 priorizabaOS ante conflicto: no se hereda esa regla contraria a identidad.

'''
(base/'CHECKPOINT.md').write_text(current+legacy,encoding='utf-8')
(base/'HANDOFF.md').write_text('''# Handoff C03 — fuente512 validada

Goal íntegro activo, Goal-c03/HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. C03_ASTRA_AUTORIDAD.md/identidad/AGENTS mandan; preservar WIP/main/evidencia/encuesta742rev1248. Sin agentes ni Full durante reparación; BAXY manual cerrado.

Fuente effect_intent503,__main__506,llm512.512 conserva historial/roles/literales como datos en conocimiento y reparación; otros lectores/formas/auditoría intactos.3406pass+121subtests/0skips53,88s(40969exit0);Fastverde/Release3,55s0warnings/errors(32963exit0). Buildservers apagados; no procesos activos. astra-knowledge-history512 contienePINS/RESULT/SOURCE.patch y anterioresCHECKPOINT/HANDOFF. Manifiesto13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed intacto.

Siguiente: scratchpad/c03-audio-chat513.py,24casos consumidos/protocolo real/sintratamiento. Verificar calidad/bindings/recursos; no sóloselecciónvacía. Después otrosbloqueosC03 yproducto físico. No editar fuente durante corridas.

504audio13/14 y11/11bindings.506retiróprosa delselector.50718/20 y11/11bindings.508perfilesempatan5/7+6/7(v2corrigejuiciosdefinición,v1guardada).509reglaprocedenciasolafallaJordan4/4:nootraredacción.510historialcitadocorrigeJordan2/2,mantienepalabrasdelasistente,unarespuestaaside.511T0enexactos22payloads→22/22útiles,73stop;RAM1,72GiB/GPU3,42GiB,sólo mente/conductor.512adoptado enfuente peroaúnfalta513; sin promoción demodelo.

Cierre pendiente íntegro: ocho rutas/742expectativas e incidentes264;100humanosfrescos certificados/congelados/100de100;averías/recuperación;UI/voz/audiofísico/ASR/wakey≤4GiBconjunto;runtime/instalación/C04–C09;Fullverde/publicaciónfuera de main. Reserva204potenciales/192únicos,0certificados/ejecutados;auditar exposición>483. Rechazos/modelos/rutasprivadas enCHECKPOINT eINVESTIGACION_MODELO_C03. No repetir campañas sin causa nueva.
''',encoding='utf-8')
r=json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'));r.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='Fuente512 validada3406pass+121subtests/Fastverde;sinprocesosactivos.',continuation='Ejecutar51324casos reales conregistroactual;después cerrarrestantesbloqueosC03.');write(base/'RELEVO_ACTIVO.json',r)
print('512 closed and pinned;513 prepared24 cases, no source changes needed to run.')
