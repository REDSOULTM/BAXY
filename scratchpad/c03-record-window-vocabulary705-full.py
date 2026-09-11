"""Persist the exact live Full handle and its candidate before waiting."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
out = base/'astra-window-vocabulary-source705'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
write = lambda p, v: p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
record = read(out/'CANDIDATE2.json')
assert all(sha(root/name) == expected for name, expected in record['sources'].items())
owners = Path(os.environ['TEMP'])/'c03-window-vocabulary705-dotnet-owners.log'
assert 'Superado:   167' in owners.read_text(encoding='utf-8-sig')
(out/'DOTNET-OWNERS.log').write_bytes(owners.read_bytes())
write(out/'FULL_RUNNING.json', {'utc': datetime.now(timezone.utc).isoformat(), 'sessionId': 61066,
      'candidate_sha256': sha(out/'CANDIDATE2.json'), 'python_owners_passed': 691,
      'dotnet_owners_passed': 167, 'skipped': 0, 'adopted': False,
      'log': 'TEMP/c03-window-vocabulary705-full.log', 'exit': 'TEMP/c03-window-vocabulary705-full-exit.json'})
state = read(base/'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), workStatus='window_vocabulary705_full_running',
             checkpoint='705 candidato compartido:691dueñasPython y167App,0skips. Full705 vivo61066, candidato2 sellado. Replay de borradores nativos:12/18ocurrencias694 ahora aceptadas sin editar;6de694 y18de704 siguen rechazadas por gramática. Encuesta26/716/0.',
             continuation='Recoger Full705 sesión61066 y TEMP/c03-window-vocabulary705-full{.log,-exit.json}; no reiniciar por timeout. Después validar producto/recuperación y decidir adopción705; no presentar replay como nuevas inferencias. Agente localizó H0023 pérdida window.resolve en domain_grounding; siguientes lecturas/frescura siguen abiertas.',
             activeValidation={'name': 'Full705', 'sessionId': 61066, 'status': 'running_exec_handle'},
             activeReadOnlyAgent=None)
write(base/'RELEVO_ACTIVO.json', state)
note = '''
## Candidato705 — Full en curso

691 pruebas Python y167 pruebas App pasan,0skips. La primera dueña ampliadaPython dejó689pass/1fallo: un nombre de archivo observado en minúscula se rechazaba como prosa lowercase. El mismo tratamiento de identidad se aplicó a esa comprobación léxica, conservando minúsculas fuera del nombre como fallo; se añadió el control y no se retiró ninguno. CANDIDATE2.json conserva la fuente actual y407archivosPython; PREREG preserva la anterior. Las huellasSTT se actualizan como declaración de código, no aceptación de audio.

Full705 inició en sesión61066 tras dueñas verdes, con logsTEMP/c03-window-vocabulary705-full.log yfull-exit.json. No hay inferencia ni producto nuevo. Replay técnico privado de borradores nativos:694H0104 tenía18ocurrencias/2borradores únicos;12ahora pasan idénticas y6siguen fallando por gramática. Las18ocurrencias/1borrador de ventanal704 siguen fallando. No es una nueva campaña LLM ni cobertura de encuesta. Fuente705 no adoptada ni publicada todavía; fuente703 sigue siendo la última adoptada. Encuesta26/716/0 yC03activo.

Exploración independiente704: H0023 sí sale del modelo comoaction/window.resolve; domain_grounding lo retira y domain_confirmation pide aclaración. Dueño __main__.py1537–1564/6210–6285. H0359 no llega a decisión:turn_runtime_failure, requiere causa interna con correlación correcta. H0532 ya sale del modelo comoconversation/knowledge, sin lectura y con17.18GB no observado; no atribuir ese último caso a una operación retirada. No aplicar prototype695 ni añadir alias del literal histórico.
'''
with (base/'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n'+note)
handoff = base/'HANDOFF.md'
previous = handoff.read_text(encoding='utf-8')
prefix = '''# Estado actual705 — candidato sin adoptar; Full en curso

Objetivo íntegro activo; dueño no tiene decisiones pendientes. El turno previo sólo aclaró metodología (no_progress); éste implementa y valida el bloqueo. No marcar goal completo. Mantener742/rev1248:26cubiertos/716abiertos/0NA, mainintacto yBAXYcerrado.

Fuente705: nuevoshelpers src/Baxy.App/ObservedResponseLiterals.cs ysrc/baxy_mind/observed_response_literals.py, usados porUserMessagePolicy/llm.py únicamente en vocabulario/códigos/minúscula inicial. Reconocen segmentos exactos title/processName bajo kindoperation,window.*,verified/succeededtrue,polaritysuccess; misión conserva sobres de steps. Hechos y texto público originales no se reescriben. Límite4096 se comprueba antes de enmascarar. No cambia prompt/sampler/modelo/kernel. Casos con títulos alterados, estados no verificados, jerga extra, foco invertido, nombre en minúscula ymisión están probados.

Dueñas:691Python/167App,0skip. Full vivo61066; logTEMP/c03-window-vocabulary705-full.log, salidaJSONfull-exit.json. Recoger esehandle, no repetir ni reiniciar por timeout. Artefactos astra-window-vocabulary-source705/{PREREG,CANDIDATE2,FULL_RUNNING,REPLAY}. CANDIDATE2sha fuentes vigentes; PREREG recoge revisión anterior. DeclaracionesSTT ytest_price_v8 actualizadas;407Python,árbolf137c37bdfff68369b233748b5e2a963c999c0d4ee4f0eced4e20281c408368e. Baselines/testerrores preservados. Noadopción aún; última fuente publicada703/commitc11007b0,estado83fef92c.

Replay privado LOCALAPPDATA/BAXY/C03-window-vocabulary705-private/REPLAY.json: borradores reales694H0104(18ocurrencias,2únicos) pasan12sin editar;6grammar siguenmal.704ventanal(18,1único) siguefallando. Sonfixturesdevalidación con trazas reales, no inferencias nuevas ni aceptación. Falta producto completo706(campaña aún no preparada) yadopción/publicación. No rerun de scriptsone-shot705; conservarresultados.

Siguiente: conFullverde, evidencia de producto y revisión/adopción705. Luego reparación de lectura/frescura: H0023 pierdewindow.resolve válida en__main__.py1537–1564,6210–6285;H0359 cae antesdedecisión;H0532 ya esknowledgesin lectura. No confundir las3causas ni aplicarproto695. RestoC03 completo másabajo. APLAZADOS/ghostsK2/prototype695 ajenossepreservan.

---

'''
handoff.write_text(prefix+previous, encoding='utf-8', newline='\n')
print({'full_session': 61066, 'owners': {'python': 691, 'dotnet': 167}, 'adopted': False})
