from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import os
import psutil
import urllib.request

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui288-private'
now=datetime.now(timezone.utc).isoformat()
report='''# C03 — UI, truncamiento y abstención285–291

Estado EN_CURSO. Única fuente adoptada continúa284. No adoptar285–291.

## Verificación del cambio284

Fast287 completo: source_quality_gate_passed: mode=Fast. Compilación Release
4,45s,0 advertencias,0 errores. Log astra-runtime287/fast.log. No Full.
Integra también266/267. Pruebas dueñas284:1012pass0skip5,20s,ruff verde.
UI288 real (py main.py, Qwen3.5 mismo override264, fuente284):
«quien soy» → «Tu nombre de usuario en el sistema es usuario.» Visible en pantalla,
21:24:43→21:24:45 hora local, tras system.identity leído y verificado.
Se observó estado Speaking, sin grabación física nueva: no acreditar audio físico.

## Comparaciones de conversación285–287

285 reconstruyó diálogo desde UI282 para índice5 y capturó payload de chat,
pero usó el default0,7 en vez del0 del caller real __main__:6432. No llamarlo
replay fiel del turno original. Su último print falló por encoding de consola,
después de obtener respuesta; no es fallo del LLM. Los logs se preservan.
286 corrige temperatura0 y salida ASCII de consola (JSON guardado UTF8).
Comparó presencia de instrucción de etapa y diálogo, más identidad mínima.
No reprodujo la negativa original; aparecieron nombres de museos no acreditados.
No adoptar supresión de instrucciones ni historial basándose en ese diagnóstico.
287 repitió los mismos payloads con modelo2507 registrado y servidor/perfil
constantes. Tampoco certifica calidad; identidad mínima trunca en ambos modelos.
No promovido ni cambiado registro. SHA del modelo2507 y registro verificadas.
Servidor287 terminado en finally, MODEL_STOP.json. La comparación de prosa no
diagnosticaba la primera frontera errónea del turno inicial de París.

## Primera frontera errónea recuperada en UI288

«Hola hablame de paris, donde podria ir?» →
«No puedo darte recomendaciones porque la interpretación de tu solicitud falló.»
En esta sesión el contexto previo es el control de identidad; no idéntico264,
pero reproduce el mismo resultado visible y ahora conserva los payloads internos.

HTTP7: selector nativo con28tools, auto,256tokens,temperatura0; comienza a
redactar recomendaciones en lugar de terminar la selección. finish_reason=length,
256tokens de salida,2246 de entrada,11,438s. llm.py rechaza selección truncada.
HTTP9: repite el selector y agota presupuesto local (TimeoutError a3,672s).
HTTP10: recuperación pide preferencia de experiencia. HTTP11: compositor de error
genera una recomendación útil, pero omite la causa de fallo suministrada; el
validador la rechaza correctamente para ese contrato. HTTP12 formula el fallo.
El problema inicial no es que ese compositor desconozca París: es el selector.
No aceptar decisiones truncadas ni atribuir éxito a la recuperación.
Logs completos privados C03-ui288-private/http-posts.jsonl, turn-audit.jsonl,
compose-audit.jsonl. Observador delega sin modificar payload/respuesta/algoritmos.

## Decisión sobre289–291

Herencia: biblioteca/gemma4-agent/documentacion/02_router/research/1_toolcalling.md
333–335 propone required permanente con resultado conversacional; 4–5 separa
sintaxis de semántica. INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md recuerda el
required de efectos antes rechazado. Aquí se probó un resultado interno sin
autoridad ejecutable, no forzar una operación después de una abstención.
Contraste oficial consultado2026-09-07:
https://raw.githubusercontent.com/ggml-org/llama.cpp/b9980/docs/function-calling.md
El documento acredita soporte nativo/plantillas; el comportamiento required con
Qwen3.5 concreto se midió localmente, no se dedujo de la tabla de familias.

289:14 llamadas,7 controles antes/después. Required + baxy_no_effect_decision
(sin argumentos ni autoridad), cambiando sólo frases incompatibles del selector.
París: antes length8,547s, después decisión sin efecto tool_calls3,031s.
Identidad, apertura simple, estado de ventana y música conservan selección.
app05 sigue confundido con game.install.status y cmp01 sigue omitiendo app.open.
No declarar7/7. Los expected de med04 son alternativas, no compuesto.

290:22 llamadas,11 controles históricos de alcance reconstruidos por builder
actual con descripciones autenticadas y subconjunto original. La propuesta
pierde scope3 «no abras Steam, dime la hora» (retira reloj permitido) y scope7
traducción (propone reloj). Baseline actual ya falla scope8 y scope10; no
atribuir a la propuesta esos errores anteriores. Propuesta descartada.

291:18 llamadas, sólo cambia descripción de la decisión vacía por predicado
de cero efectos en el pedido entero. Recupera scope3, pero pierde apertura simple,
scope6 prohibición de herramientas, mantiene error de traducción y falla scope8.
Segunda propuesta descartada. NO seguir otro barrido de nombre/prompt/descriptor
de abstención ni esconder regresiones con bypass posterior.

Siguiente estrategia: mantener AUTO y estudiar terminación del canal libre del
selector con el contrato/parser del backend, o sustituir esa representación
completa conservando los18 controles. No aumentar límites a ciegas, relajar
validación de length, forzar efectos ni añadir patrón París. Investigar mecanismo
antes de implementar. Corpus final100 permanece separado de estos controles.

Instancia264 cerrada sólo después de comprobar SHA de transcripción282. Árbol
propio completo terminado, cuestionario excluido. Nueva UI288 queda abierta sin
temporizador; cuestionario742 sigue en63179, sin editar marcas. Ocho rutas,
100/100frescos, averías/recuperación, voz/ASR/recursos finales, runtime/instalación,
continuidadC04–C09, Full y publicación fuera main pendientes. No bloqueo externo.
'''
(out/'UI_Y_TERMINACION285_291.md').write_text(report,encoding='utf-8')
app=psutil.Process(57420)
assert abs(app.create_time()-1788827018.593568)<.01
backend=next(p for p in app.children(recursive=True) if p.name()=='llama-server.exe')
args=backend.cmdline()
with urllib.request.urlopen('http://127.0.0.1:63179/',timeout=5) as response:
    questionnaire_ok=response.status==200
snapshot={'utc':now,'app':{'pid':app.pid,'created':app.create_time(),'exe':app.exe()},
    'backend':{'pid':backend.pid,'created':backend.create_time(),'args':args},
    'questionnaireAvailable':questionnaire_ok,'questionnairePid':101140,
    'privateLogs':str(private),'appAutomaticClose':False,'sourceChangesAfter284':False,
    'files':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['src/baxy_mind/llm.py','tests/test_compose_contract.py','src/baxy_mind/effect_intent.py','artifacts/comprobaciones/C03/UI_Y_TERMINACION285_291.md']}}
(out/'TRAMO285_291_PINS.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
checkpoint='''# C03 — checkpoint291 — EN_CURSO

UI_Y_TERMINACION285_291.md es último informe. Fuente adoptada284 sin cambios
después.1012pass0skip5,20s/ruff y Fast287 integrado VERDE (build4,45s0warn/error).
UI288 real verifica «quien soy» → cuentaWindows usuario; no memoria personal.

UI288 reproduce primer fallo París. HTTP7selectorAUTO se pone a redactar,
trunca256tokens(11,438s); HTTP9repite y TimeoutError3,672s; después compositor
de error termina diciendo interpretación fallida. PRIMERA FRONTERA selector,
no compositor final. Payloads exactos privados C03-ui288-private/http-posts.jsonl.
285prosa usótemp0,7por error;286corrige0;287modelo2507no demuestra reparación.
NO adoptar cambios de historial/prompt de esas ablaciones.

289required+resultadointerno sin efecto arregla truncamientoParís.290scope
regresa negación parcial y traducción.291descriptorpedidoentero recuperauna
pero pierde apertura/prohibición/traducción. Ambas DESCARTADAS. No más
nombre/prompt/descriptor de abstención, ni aceptar length ni patronesParís.
SIGUIENTE estrategia: estudiar terminación del canal libre AUTO en backend
o sustituir representación completa; conservar18controles289/290 y18salidas291.
No otra ampliación ciega de tokens. No cambios producción289–291 ni Full.

Instancia264 terminada tras preservar conversación completa282 (63humanos58BAXY)
en %LOCALAPPDATA%/BAXY/C03-owner264-heap280/TRANSCRIPT282.json y .md; no subir
heap ni texto completo. Nueva instancia288ABI real abierta: App57420 creado
1788827018.593568, backend66944 puerto58635, launcher44792. Qwen3.5override,
fuente284, observadorHTTP local sinmutación en scratchpad/c03-ui288-hook.
Sin temporizador/cierre. No probar nativo si /slots tiene actividad del dueño.
Servidor2507de287terminado. Registro13b971… sin promoción.

Cuestionario742 http://127.0.0.1:63179/ PID101140 vivo, SIN cierre automático.
answers.json del dueño en C03-owner-questionnaire-20260907: no borrar,
sobrescribir, rellenar ni congelar mientras revisa. Autoría y capacidad separadas;
tres ingleses antes admitidos siguen vigentes. UI288 controlesagente nofrescos.

Goal-c03/HEAD2bf3d4c preservar WIP/main. Fuente266/267 integradaFast287.
Recursos2603516,66MiBGPU/4822,60MiBRAM con captura/AEC/Piper,sin ASRhumano;
no hay nueva medición integral en288. Wake aún sin certificar. Ocho rutas,
100/100humanosfrescos sin congelar, averías/recuperación, UI/voz/ASR/recursosfinales,
runtime/instalación, continuidadC04–C09, Full y publicación fuera main pendientes.
Sin bloqueo externo. Todo el goal sigue activo; nada reducido a este diagnóstico.
'''
for name in ['CHECKPOINT.md','HANDOFF.md']:
    (out/name).write_text(checkpoint,encoding='utf-8')
path=out/'RELEVO_ACTIVO.json'
record=json.loads(path.read_text(encoding='utf-8'))
record.update(confirmedAtUtc=now,checkpoint='291: source284 verified in actual UI and Fast287 green; Paris native truncation reproduced, explicit-none289-291 rejected by scope regressions.',continuation='Change strategy to backend AUTO free-channel termination/representation; no more no-effect descriptor sweep. Preserve open UI288 and owner questionnaire.')
record['userOwnedInstance']={'pid':app.pid,'createTime':app.create_time(),'automaticClose':False,'launcher':44792,'privateLogs':str(private),'instruction':'Keep UI288 open for development and possible owner use;264 complete transcript preserved privately. Distinguish agent288 controls from owner264 input.','processRevalidated':True}
path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'checkpoint':291,'questionnaireAvailable':questionnaire_ok,'app':app.pid,'backend':backend.pid,'sourceAdopted':284,'fast':'green'}))
