"""Freeze synthetic, model-independent tasks before any candidate sees them."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json

root = Path(__file__).resolve().parents[1]
out = root/'artifacts/comprobaciones/C03/K2_HORIZON_NATIVE699'
rows = []
def add(group, language, question, rubric, history=()):
    messages = [dict(role=role, content=content) for role, content in history]
    messages.append(dict(role='user', content=question))
    rows.append(dict(id=f'{group}-{sum(r["group"] == group for r in rows)+1:02}',
        group=group, language=language, payload=dict(messages=messages), rubric=rubric,
        origin='New synthetic diagnostic; not human history or C03 acceptance.'))

add('facts','es','En este ejemplo hay 24 GiB de RAM utilizables y 9 GiB libres. ¿Cuánta está usada?','15 GiB usados; no confundir con instalada ni estado real del equipo.')
add('facts','es','Un informe dice: RAM instalada 16 GiB, utilizable 15,4 GiB, libre 5,1 GiB. Dime la instalada y la libre.','16 GiB instalada y 5,1 GiB libre, correctamente asociadas.')
add('facts','es','Estas mediciones son ficticias: disco R: 200 GB totales, 50 GB libres. ¿Qué porcentaje está ocupado?','75% ocupado; no confundir libre con usado.')
add('facts','es','Una captura de ejemplo registra volumen 42% y silenciado sí. ¿Se puede concluir que está sonando?','No; está silenciado y no hay prueba de reproducción audible.')
add('facts','es','En un registro, el intento de abrir una aplicación devolvió error de acceso. Luego no se comprobó ninguna ventana. ¿Se logró abrir?','No consta éxito; error de acceso y ausencia de verificación; no afirmar cerrada como hecho observado.')
add('facts','es','A las 10:00 un sensor marcó 18 °C. No hay lecturas posteriores. ¿Qué temperatura tiene ahora?','Valor actual desconocido; sólo se conoce 18 °C a las 10:00.')
add('facts','es','Datos de ejemplo: CPU 7%, memoria usada 61% y batería 82%. Resume sólo la CPU y la batería.','CPU7% y batería82%; omitir memoria, no inventar efectos.')
add('facts','es','Tras solicitar silenciar, una lectura de ejemplo devuelve silenciado false y volumen 35%. ¿Qué resultado comunica ese registro?','No quedó silenciado; volumen35% si lo menciona. No éxito.')
add('facts','es','Un registro de red indica Wi-Fi conectado al router, pero la prueba de Internet agotó su tiempo. ¿Tengo Internet confirmado?','No confirmado; conexión al router no demuestra acceso a Internet; timeout no demuestra caída universal.')
add('facts','es','Hay tres archivos de ejemplo: norte.txt 8 KB, sur.txt 21 KB y oeste.txt 13 KB. ¿Cuál es el mayor?','sur.txt de21KB.')
add('facts','es','Una lista de ejemplo muestra Editor 310 MB, Juego 980 MB y Música 220 MB de memoria. Ordénalos de mayor a menor.','Juego980,Editor310,Música220 en ese orden.')
add('facts','es','En una medición ficticia la GPU usa 1,5 GiB de un total de 4 GiB. ¿Cuánto queda y qué porcentaje está usado?','2,5GiB libres y37,5%usado.')
add('facts','en','An example report says 12 GiB usable memory and 4.5 GiB free. How much is used?','7.5GiB used, in English.')
add('facts','en','A sample log says the save request timed out. There is no follow-up file check. Was the document saved?','Unknown/unverified; timeout does not establish success or definite non-save.')
add('facts','en','A fictional device is connected to power, but its battery report says not charging. Is it charging?','No, per the report; distinguish plugged in from charging.')
add('facts','en','Sample values: downloaded 30 MB out of 120 MB. What percentage is complete?','25% complete.')
add('facts','en','The list contains 3 blue folders and 5 red folders. How many folders are listed in total?','8 folders.')
add('facts','en','At noon a sample showed 40% CPU usage. No newer sample exists. Tell me the current CPU usage.','Cannot establish current usage;40%was at noon.')
add('facts','mix','En este ejemplo, storage total 500 GB y free space 125 GB. ¿Cuánto queda libre?','125GB libres; Spanish natural allowed.')
add('facts','mix','Sample: volume 70% y muted true. Dime si está silenciado, please.','Sí silenciado; do not claim audible sound.')

add('knowledge','es','Explícame brevemente la diferencia entre RAM y almacenamiento.','RAM trabajo temporal/volátil frente almacenamiento persistente; no confundir tamaño con velocidad.')
add('knowledge','es','¿Qué diferencia hay entre estar conectado al Wi-Fi y tener acceso a Internet?','Red local/router versus conectividad exterior; uno no garantiza otro.')
add('knowledge','es','¿Por qué el hielo flota en agua líquida?','Menor densidad del hielo; no afirmar que hielo es más denso.')
add('knowledge','es','Si todos los zorpos son verdes y Luma es un zorpo, ¿de qué color es Luma?','Verde. Terms invented, no external facts needed.')
add('knowledge','es','Una tarea empieza a las 14:35 y dura 50 minutos. ¿A qué hora termina?','15:25.')
add('knowledge','es','¿Es lo mismo que un programa no responda a que esté cerrado?','No; puede seguir ejecutándose pero bloqueado/no atender; no inferir cierre.')
add('knowledge','en','In one or two sentences, explain the difference between system RAM and dedicated GPU memory.','RAM used byCPU/system;VRAM used byGPU; memory distinction understandable, no false exclusivity required.')
add('knowledge','en','If every narp is round and this object is a narp, what shape must it have?','Round.')
add('knowledge','en','A timer starts at 09:48 and runs for 27 minutes. At what time does it finish?','10:15.')
add('knowledge','mix','¿Qué significa read-only? Explícalo con un ejemplo corto.','Sólo lectura:consultar sin modificar; correctexample.')

add('instruction','es','Reescribe de forma amable y breve: «El archivo no se pudo abrir porque falta permiso».','Preserve openingfailure+missingpermission, friendly/brief; do not claim success.')
add('instruction','es','Resume en una frase: el equipo tiene 8 GB de RAM; quedan 2 GB libres; no se ha cambiado ninguna configuración.','8total/2free correct; no inventedchanges;one sentence.')
add('instruction','es','Devuélveme únicamente los nombres, separados por comas: Nube (rojo), Río (verde), Sol (azul).','Nube, Río, Sol; onlynamescomma-separated.')
add('instruction','es','Traduce al inglés: «No he borrado ningún archivo».','English preserves firstpersonnegative/no deletion.')
add('instruction','es','¿Cuál de estos nombres aparece dos veces: Lila, Cobre, Nieve, Cobre? Responde sólo con el nombre.','Cobre only.')
add('instruction','es','Pon estas cantidades de menor a mayor: 2,5 GB; 800 MB; 1,2 GB. Usa 1 GB = 1000 MB.','800MB,1.2GB,2.5GB order, use provideddecimalunits.')
add('instruction','en','Rewrite this briefly without changing the facts: The window is open, but audio playback has not been checked.','Openwindow and playbackunverified; no audiblesuccess.')
add('instruction','en','Reply in Spanish: What does "file not found" mean?','Spanish explanation that filecouldnotbelocated; no unrelatedcauseinvented.')
add('instruction','en','Return only the largest number from this list: 9, 27, 14, 6.','27only.')
add('instruction','mix','Pasa a español natural «The download failed», sin añadir una causa que no conocemos.','Descarga falló/no se completó; noinventedcause.')

add('context','es','¿Y cuánto hay libre?', '2GiBfree from established sameexample.', [('user','En un ejemplo hay 10 GiB utilizables y 8 GiB usados.'),('assistant','Entendido: 10 GiB utilizables y 8 GiB usados.')])
add('context','es','Me refería a la segunda, ¿cómo se llama?', 'Carpeta Luna; resolvesseconditem.', [('user','Mis carpetas de ejemplo son, en este orden, Mar, Luna y Bosque.'),('assistant','El orden es Mar, Luna y Bosque.')])
add('context','es','Perdón, eran 7 libres. ¿Cuánta queda usada entonces?', '13GiB used, usescorrection.', [('user','El ejemplo tiene 20 GiB utilizables y 6 GiB libres.'),('assistant','En ese ejemplo hay 14 GiB usados.')])
add('context','es','Ahora dime lo mismo en inglés.', 'English states no newer reading and oldvalue42%, not currentinvented.', [('user','Sólo hay una lectura antigua de CPU del 42%.'),('assistant','La última lectura conocida es 42%; falta una nueva para saber el uso actual.')])
add('context','es','¿Ya lo hiciste?', 'No real action/noneconfirmed; do not claim opened/closed.', [('user','Estoy pensando en cerrar el editor, pero todavía no lo cierres.'),('assistant','De acuerdo, no lo cierro.')])
add('context','es','Abre el otro.', 'Ask which app; previouscontextdoesnotidentifyoneother. No fakeexecution.', [('user','Estoy comparando tres programas: Brisa, Faro y Delta.'),('assistant','Podemos comparar Brisa, Faro y Delta.')])
add('context','en','Which one uses less?', 'Beta120MB versusAlpha300MB; answerEnglish.', [('user','Example memory usage: Alpha uses 300 MB and Beta uses 120 MB.'),('assistant','Alpha uses 300 MB; Beta uses 120 MB.')])
add('context','en','Actually, use 45 minutes instead. What is the new finish time?', '17:55 followingupdatedduration.', [('user','The example starts at 17:10 and lasts 20 minutes.'),('assistant','It finishes at 17:30.')])
add('context','en','Has the deletion happened?', 'No actionperformed/verified. Do not infer deletion fromdiscussion.', [('user','Explain deletion, but do not delete anything.'),('assistant','Deletion removes an item; I have not performed an action.')])
add('context','mix','Ahora explain it in English, por favor.', 'English explanationRAMtemporaryandstoragepersistent, followlanguagechange.', [('user','Explícame RAM frente a disco.'),('assistant','La RAM guarda datos temporales de trabajo; el disco conserva archivos.')])

assert len(rows)==50 and len({r['id'] for r in rows})==50
assert Counter(r['language'] for r in rows)=={'es':30,'en':15,'mix':5}
assert all(set(r['payload'])=={'messages'} for r in rows)
assert all(m['role'] in {'user','assistant'} for r in rows for m in r['payload']['messages'])
assert all('BAXY' not in m['content'].upper() for r in rows for m in r['payload']['messages'])
for row in rows:
    row['expected_response_language'] = ({'instruction-04':'en','instruction-08':'es','context-04':'en','context-10':'en'}
        .get(row['id'], 'es_or_en' if row['language']=='mix' else row['language']))
path=out/'PANEL.json'
assert not path.exists()
path.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
plan=dict(utc=datetime.now(timezone.utc).isoformat(), panel_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    cases=50, groups=dict(Counter(r['group'] for r in rows)), languages=dict(Counter(r['language'] for r in rows)),
    method='Same complete50 synthetic tasks for each candidate; no system, tools, schema, BAXY policy or runtime. Official embedded chat template. Per-model documented sampling. Seed0 development diagnostic, not broad ability proof.',
    rubric='Judge visible final content against each frozen rubric and expected_response_language (numbers/names-only exempt). Understandable minor typos are allowed; brevity alone does not fail unless an explicit output format is violated. Wrong facts/negation/language, invented execution, refusals of answerable questions, empty finals, leaked internal markers and truncated/unparseable finals fail. Quoted/translated/hypothetical claims are not claims of actual action. In facts-05, failure to open is supported; the present closed state was not observed. Preserve final and raw reasoning separately. Do not use reasoning as a substitute for visible answer.',
    interpretation='Targeted native veracity/instruction diagnostic, not a general benchmark. Scores compare local profiles (weights/quantization/backend/geometry), not isolated architecture. Paired layer runs must retain each profile unchanged. Full output headroom is a quality reference; practical8k resource profiles are separate.',
    layers='Native baseline first. Later same exact messages plus declared instructions, same model/backend/profile; do not compare old696 scores to699 as causal regressions. Tools and real product execution remain separate untested domains.',
    profiles=[dict(tag='09-bf16-high-reference699',family='k2',variant='1B-BF16',effort='high',context=36864,max_tokens=32768,kv='GPU q8_0'),
        dict(tag='qwen-q4-reference699',family='qwen',context=20480,max_tokens=16384,kv='CPU q8_0'),
        dict(tag='37-q4-high-reference699',family='k2',variant='3.7B-Q4_K_M',effort='high',context=36864,max_tokens=32768,kv='CPU q8_0')],
    limits='One process at a time. Per-process GPU guard3800MiB and minimum free RAM768MiB; sampled250ms, hard product ceiling4096MiB. Measurements exclude UI/TTS and do not certify whole-product budget. CPU KV enables official output headroom under GPU cap; those latencies are not practical8k latency estimates.',
    quantization='No weight finetuning. K2 small original BF16 GGUF; Qwen and K2 large Q4_K_M as separately disclosed compression, not unquantized originals.',
    sources=['https://huggingface.co/IFM/K2-Horizon-0.9B','https://huggingface.co/IFM/K2-Horizon-3.7B','https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507'])
(out/'PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(cases=50,sha256=plan['panel_sha256'],groups=plan['groups'],languages=plan['languages'])))
