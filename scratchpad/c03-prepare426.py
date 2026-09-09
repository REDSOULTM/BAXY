from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
out=base/'astra-host-memory425'
assert 'source_quality_gate_passed: mode=Fast' in (out/'fast.log').read_text(encoding='utf-8-sig')
report='''# 425 — perfil de RAM incorporado; owners y Fast verdes

LlmRuntime._server_command fija --cache-ram0 y añade --no-mmap con GPU.
CPU-only conserva mmap. Se retira la dependencia de flags inyectados por el
diagnóstico; sin nueva configuración de usuario, capa ni modelo. Contexto,
precisión KV, pesos,slots,sampler e historia se conservan. Evidencia423/424.

La extensión del contrato de perfil GPU falla antes del cambio por ausencia
de cache-ram. El filtro baseline no seleccionó CPU(no se atribuye un rojo CPU).
Después: pytest tests/test_planner.py -q -k 'slots or cpu' →6pass,0skips,0,63s.
pytest tests/test_planner.py tests/test_llm_transport.py tests/test_compose_contract.py
-q --tb=short →293pass+121subtests,0skips,2,34s.
scripts/test_source_quality.ps1 →Fast verde completo,build4,11s,0warnings/errors.
NoFull ni nueva certificación CPU/UI/voz. Servidores de ambosSDK cerrados después.

426 usa el código de producción con observador HTTP/commandline/log y mismos
8casos de desarrollo. El hook no añade cache-ram ni no-mmap: debe venir del
comando real. Fuente nueva425 invalida cualquier afirmación de gate final sobre
fuentes anteriores; repetir final runtime/Full sólo cuando C03 esté reparado.
Modelo registrado2507 intacto;4B3.5 sigue diagnóstico,no promoción.
'''
(out/'RESULT.md').write_text(report,encoding='utf-8',newline='\n')
paths=[out/n for n in ['PREREG.json','RESULT.md','baseline.log','focused.log','owners.log','fast.log']]+[root/n for n in ['src/baxy_mind/llm.py','tests/test_planner.py']]
(out/'PINS.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n',newline='\n')
target=root/'scratchpad/c03-private-product426.py';assert not target.exists()
source=(root/'scratchpad/c03-private-product423.py').read_text(encoding='utf-8').replace('423','426')
start=source.index("    'cache_change':");end=source.index("    'method':",start)
source=source[:start]+"    'production_verification': 'Source425 native command owns cache-ram0 and GPU no-mmap. Observer only records HTTP/process command and adds log/verbosity4; no loading flags injected. Same8cases/source418 behavior/profile/limits. No fresh acceptance, UI or physical voice.',\n"+source[end:]
source=source.replace('Source418 gives','Source418 gives')
compile(source,str(target),'exec');target.write_text(source,encoding='utf-8',newline='\n')
hook=root/'scratchpad/c03-owner426-hook';hook.mkdir(exist_ok=False)
observer=(root/'scratchpad/c03-owner423-hook/sitecustomize.py').read_text(encoding='utf-8').replace('423','426')
observer=observer.replace("'--no-mmap', '--cache-ram', '0', ",'')
observer=observer.replace('no_mmap_command','observed_command')
(hook/'sitecustomize.py').write_text(observer,encoding='utf-8',newline='\n')
checkpoint='''# C03 — fuente425 validada; producto426 preparado — EN_CURSO

Goal completo activo. Goal-c03/HEAD2bf3d4c. Preservar WIP/main/evidencia.
Sin agentes/commit/push/Full durante reparación. BAXY manual cerrado; encuesta
PID101140/padre29800 intacta. No modelos/builds activos al preparar426.
17 mensajes directos+742respuestas/rev1248 consolidados; automáticos excluidos.
Dueño prioriza mínimo RAM/VRAM con calidad; techo conjunto4GB, no consumo fijo.

## Fuente vigente y pruebas
425: llm._server_command cache-ram0, no-mmap conGPU;CPU conserva mmap.
6focales pass/0skips0,63s; planner+llm_transport+compose_contract293pass+
121subtests/0skips2,34s;Fast verde build4,11s/0warnings/errors. RESULT/PINS425.
No cambio pesos/contexto/slots/sampler/prompt.2507registrado,3.54Bdiagnóstico.
418: petición privada reconocida reemplaza aclaración pública;NoRoute/AskToSave
siguen mente.6focales/2007owners pass, runtimeExplicit omitido(no pass);
Fast18,01s.426debe comprobar producto.421–424confirman recallENtras aclaración;
ES alcanza motor pero dice«Mi nombre esJordan»(sujetoerróneo).
416: CaptionOS viaCIM local5s/cancelación/runner existente;36provider+193integration
pass/0skips;Fast18,76s.417producto8/9:Windows11ES/EN,RAM/CPUcorrectos;
cuentaT3aúnpidepermiso.410cuenta/recursos+catálogo;402/404memoria/395–397contexto
conservados. No repetir owners sin nueva fuente/fallo.

## Recursos: evidencia que decide
420sinbuild: corteRAM4730MiB/GPU3177,56,2finales.421no-mmap:4629,9MiB/corte,
4finales yT5procesado sinfinal.422atribución:5303,99MiB/corte,7terminales,
3útiles; servidor3676MiBRSS máximo,workerE5confirmado≈878MiB.
423no-mmap+cache0:3173,43MiBRAM/GPU3177,56,56s,sincorte,8terminales4útiles.
424mmap+cache0:5207,20MiBRAM,55,516s,8finalesidénticos. Ambosflagsnecesarios.
Todos sonRSSárbol, noRAMprivadacomprometida; noUI/vozfísicaconjunta/mínimoglobal.
426preparado: mismo423 con fuente425;hook sóloobserva, noinyectaflagsdecarga.

## Fallos y siguiente acción
T3«Abre una aplicación»: primariaapp.open correcta; domain_grounding la veta
por faltarappId, domain_confirmation pregunta permiso. T6mismafrase acaba
falsaunsupported. Reusar aclaración de argumento existente, sinautorizar target
inventado; inspeccionar payload exacto/historia antes de tocar. T5«Me llamoÁlvaro»
primariasystem.identityerrónea→composition_failed; T7recallESsujetoerróneo.
349source=user noayuda sujeto; RequiredBaxyActions devuelve[] enrecall(noimposición).
413/414earlyread13/15→14/15→14/15 intercambianfallos cold/warm: noadoptados.
Historia desdeHTTP conbienvenida, noactivity sola. Parser literal/genérico:
comprobar reachability antes de atribuir/regresionar. Ninguno nuevo adoptado.

Ejecutar: runtimePython -X utf8 scratchpad/c03-private-product426.py.
No fuente mientras corre. Recogerresources/EXIT/commandline/finales y registrar.
Después resolver aclaración de argumento o presentación humana con evidencia.
PendienteC03: ocho rutas/encuesta742/fallosmanuales264;0requisitosfinales y0/100
humanosfrescos certificados(204potenciales335reservados).Averías/recuperación,
UIreal/vozfísica/ASR/wake/≤4GBconjunto,runtime/instalación/contratosC04–C09,
Full final verde entero/publicación. Sinbloqueoexterno/porcentaje/ETA.
'''
for name in ['CHECKPOINT.md','HANDOFF.md']:
    p=base/name;archive=base/(name.removesuffix('.md')+'_424_ANTES_425.md');assert not archive.exists();archive.write_bytes(p.read_bytes());p.write_text(checkpoint,encoding='utf-8',newline='\n')
p=base/'RELEVO_ACTIVO.json';relay=json.loads(p.read_text(encoding='utf-8'));relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='425 native host-memory profile adopted;293+121subtests pass/Fast4.11s green. Bothflags justified423/424.',continuation='Run426 production verification, no loading-flag hook. Then resolve app missing-argument clarification and self-introduction/memory subject. Full C03 active.')
p.write_text(json.dumps(relay,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('425 recorded;426 prepared')
