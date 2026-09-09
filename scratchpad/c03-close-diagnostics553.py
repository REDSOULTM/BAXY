"""Close bounded diagnostics honestly and publish a small actionable handoff."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os
root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
local=Path(os.environ['LOCALAPPDATA'])/'BAXY'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

notes={
 'astra-e5-backend547':'''Primera comparación secuencial del mismo E5 sobre742 entradas de encuesta. Torch848,918MiB; ONNX FP32833,344MiB; INT8494,547MiB. Diagnóstico de throughput, no latencia de producto. FP32 mínimo coseno0,998346; cero cambios de vecino del banco congelado. INT8 cambia108 vecinos, sin que ese banco tenga autoridad de ejecución.548 identifica exactamente dos diferencias de tokenización(H0166/H0704): AutoTokenizer agrega WhitespaceSplit y modifica el normalizador del tokenizer.json; se exporta su backend efectivo.549 corrige esta diferencia sin cambiar modelo ni corpus. No adoptar desde547.''',
 'astra-e5-retrieval549':'''Comparación con tokenizador efectivo548 y PlannerCatalog real, query/passage correctos. FP32 y no-arena: equivalencia numérica(errores de componente≤1,94e-7), cero cambios de inclusión o primera operación entre742 mensajes; dos cambios de orden enH0183/H0258. RAM pico1226,387 y1225,820MiB frente a832,992MiB deTorch. No-arena no ahorra RAM en esta carga. INT8491,789MiB pero cambia206 primeras operaciones e inclusión en742/742; no significa206 errores demostrados, sí ausencia de equivalencia y de prueba de calidad suficiente. Consultas individuales calientes: Torch16–39ms, FP327–23ms, INT83–15ms; no son latencia extremo a extremo ni presupuesto UI/voz. Ningún backend adoptado.''',
 'astra-e5-avx2550':'''Intento de construcción abortado antes de cuantizar: falta ml_dtypes en la instalación aislada deONNX1.22.0. No es fallo del encoder ni resultado de calidad. Se instaló la dependencia enD:/BAXYRuntime/experiments/python/onnx550, sin modificar producción, y se reanudó como551. Se conservan traceback y recursos originales.''',
 'astra-e5-avx2551':'''Construcción e inferencia AVX2 completadas sin cortes. ONNX dinámico QInt8 por canal con reduce_range=True, MatMul/Gather, mismo FP32. La documentación deORT propone este perfil para saturación U8S8 enAVX2 sinVNNI; la hipótesis no se da por demostrada. Construcción2459,328MiB, inferencia491,363MiB. Mínimo coseno0,986444/media0,996460;188 primeras operaciones distintas y741 cambios de inclusión, frente a206/742 conel archivoVNNI. Mejora insuficiente para adoptar o declarar igual calidad. El harness terminó con import faltante al adjudicar; c03-finish-avx2551.py completó sólo la comparación con los arrays ya guardados, sin repetir construcción ni inferencia. Dos perfiles cuantizados medidos: cerrar esta línea y conservarTorch. Advertencia deORT sobre preprocesamiento preservada; no representa una búsqueda exhaustiva ni descarta otras optimizaciones futuras.''',
}
for folder,note in notes.items():
    path=base/folder
    (path/'RESULT.md').write_text('# '+folder+'\n\n'+note+'\n\nFuentes: [eficiencia de Sentence Transformers](https://www.sbert.net/docs/sentence_transformer/usage/efficiency.html), [cuantización ORT](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html).\n',encoding='utf-8',newline='\n')

for number in (552,553):
    folder=f'astra-native-quantities{number}'
    private=local/f'C03-native-quantities{number}-private'
    out=base/folder
    requests=[json.loads(s) for s in (private/'requests.jsonl').read_text(encoding='utf-8-sig').splitlines()]
    responses=[json.loads(s) for s in (private/'responses.jsonl').read_text(encoding='utf-8-sig').splitlines()]
    assert len(requests)==len(responses)==22
    assert all(r['response']['choices'][0]['finish_reason']=='stop' for r in responses)
    resources=read(out/'RESOURCES.json')
    assert resources['completed'] and not resources['violations'] and resources['manifest_unchanged']
    note=('GiB derivados arreglan magnitud pero el modelo publica frecuentemente GB para valores binarios. Añade principal a la RTX3060 sin evidencia y confunde conteo de tarjetas/instancias. Rechazado.' if number==552 else 'GB decimales derivados corrigen las cifras:6287261696bytes→6.29GB, disco127255064576→127.26GB. Sigue añadiendo principal a la RTX3060 y trata adaptadores/instancias como dos tarjetas físicas sin haberlo verificado. El sujeto Tengo para RAM total y prosa innecesaria siguen. No adoptar globalmente; los resultados favorables de números no borran afirmaciones nuevas. Tras dos comparaciones de unidades, cerrar esta línea de enriquecimiento genérico.')
    lines=[f'# Cantidades nativas{number}','',note,'','22 respuestas con EOS. Es aislamiento nativo, sin producto/UI/voz. El control541:63 hereda la proyección equivocada previa542 y carece de adaptadores: no puede repararse con unidades; queda etiquetado como control de evidencia insuficiente.','']
    for request,response in zip(requests,responses):
        assert request['case']==response['case'] and request['profile']==response['profile']
        lines += [f"## {response['case']} · {response['profile']}",'',request['payload']['messages'][-1]['content'],'',response['response']['choices'][0]['message']['content'],'']
    (private/'RESULT.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    write(out/'RESULT.json',{'responses':22,'finish_stop':22,'adopted':False,'adjudication':note,'resources':resources,'private_report':str(private/'RESULT.md'),'private_report_sha256':sha(private/'RESULT.md'),'requests_sha256':sha(private/'requests.jsonl'),'responses_sha256':sha(private/'responses.jsonl')})
    (out/'RESULT.md').write_text(f'# Cantidades{number}\n\n'+note+'\n\n22 respuestas EOS; aislamiento nativo conQwen2507/b9980. Recurso y literales privados referenciados enRESULT.json. No cambia fuente, modelo ni runtime; no acredita encuesta adicional.\n',encoding='utf-8',newline='\n')

folders=[*notes,'astra-native-quantities552','astra-native-quantities553']
with (root/'.gitattributes').open('a',encoding='utf-8',newline='\n') as stream:
    for folder in folders:
        stream.write('/artifacts/comprobaciones/C03/'+folder+'/** -text\n')
        out=base/folder
        write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})

handoff='''# Handoff C03 — 553

Goal API active; C03 EN_CURSO, rama Goal-c03, tarea01a07974-2a33-7ed3-ba87-2436944e8115. Autorización536 resuelve históricos/reserva; ninguna decisión pendiente del dueño. BAXY manual cerrado, encuesta original742/rev1248 intacta; sin subagentes. Main5f572ee1b48cb5e2543ee5e06510e51057c9c845 intacto.

Fuente adoptada publicada:1d08cc297547ebc1d38d98492a41973816423416. effect_intent545 conserva consultas coordinadas ES/EN, how much/many, decime y preguntas de cantidad; mantiene scopes combinados CPU/RAM y OS/RAM, negaciones, otros dispositivos, citas y catálogo incompleto. Dueñas3699 pass+121 subtests,0 skips,56,21s; STT12 pass/1 skip ambiental1,46s. Fast verde, Release21,23s,0 advertencias/errores. Sin source después545. Árbol STT399e73203f5eafca73a8573083703cd2e10756b2c8544e992c8c40cb24b80138/403ficheros, sellos históricos intactos. __main__530,llm520,C#516. Full526 rojo con25 fallos reparados por dueñas528–531; Full final todavía pendiente.

Encuesta:7 cubiertos/735 abiertos/0 no aplicables. H0002,H0016,H0021,H0041,H0042,H0062 y nuevoH0079. Registro privado336 y resumen público actualizados, negativos3/sin marca18 preservados. Producto546:6 finales, exit0/sin cortes, GPU3497,559MiB/RAM1893,363MiB,28,296s. Hora+batería literal/inglés/orden inverso contrastadas con ambos hechos nativos. Controles fecha+RAM, disco+batería y scope OS/RAM completados; sujeto/unidades de recursos quedan abiertos. SinUI/voz, no consumo conjunto final. c03-close546.py ya ejecutado: NO volver a adjudicar duplicando evidencias.

E5:544 assets FP32/INT8 del checkpoint614241f6 verificados fuera del snapshot firmado.547 compara742 mensajes;548 demuestra que AutoTokenizer modifica normalizador/WhitespaceSplit y guarda effective-tokenizer548.json privado.549 usa tokenizador real y PlannerCatalog:FP32 error≤1,94e-7,0 cambios de inclusión/top1,2 órdenes(H0183/H0258);RAM1226MiB frenteTorch833MiB, no-arena no mejora. INT8~492MiB pero206 top1/742 inclusiones distintas.550 falla por dependencia ml_dtypes, reparada sólo en herramientas externas;551 cuantiza por canal/reduce_range AVX2:491MiB,188 top1/741 inclusiones distintas. Construcción/inferencia exit0; adjudicación falló por src ausente y se completó con finish-avx2551 sin repetir modelos. Ningún cambio de producción. Dos perfiles cuantizados insuficientes; no seguir ajustando esta línea sin causa nueva. No declarar que toda cuantización es mala ni que206 discrepancias sean errores adjudicados. ORT recomienda optimización previa, warning conservado.

Cantidades552/553:11 capturas541/543/546 ×2 brazos,22 EOS por campaña, Qwen2507/b9980. GiB derivados552 se narranGB, rechazado. GB decimales553 mejora números pero añade principal a RTX3060 y conteo físico de tarjetas sin acreditarlo; tampoco se adopta globalmente. El control541:63 carece de adaptadores por alcance antiguo, explícitamente insuficiente:542 ya reparó la interpretación real. Informes privados incluyen literal, payload y respuesta por brazo. NO repetir enriquecimiento genérico tras estas dos comparaciones; cambiar estrategia basada en primera transformación errónea.

Bloqueos concretos restantes: guardado con metadatos internos y negación de capacidad cuando memoria está desactivada(521; pruebas537–540 rechazadas); CPU total atribuida aBAXY,16 lógicos llamados núcleos, despedida española metanarrada, curiosidades inventadas, disco plural rechazado, presentación de GPU/adaptadores/unidades. Registro de541/543 preserva pruebas por caso. Estado abierto no equivale a todos fallos; falta adjudicación individual del resto. Priorizar contrato semántico de respuesta y calidad real sobre nuevos barridos de flags.

Siguiente: resolver el primer fallo de propiedad/sujeto y capacidad con evidencia nativa y producto, generalizar ES/EN; revisar herencia Gemma antes de otro ensayo de modelo, sin asumir que un default lo descarta. Evitar replicar537–540/552–553,523sampler/524Qwen3.5/525quitarpregunta. Luego rutas8, encuesta restante, UI de escritorio real, loopback completo/AEC supresión, recursos conjuntos y Full final. Voz humana/wake/FAR-FRR sonC08 con evidencia/reanudación, sin cerrar su fila. Conductor no acredita UI/voz. No cerrar aplicaciones ajenas para liberar RAM.

No procesos de ensayo pendientes:546(95343),547(68723),549(24475),550(salió1 por dependencia),551(84438, terminó1 en adjudicación ya recuperada),552(44772),553(78102) recogidos. Encoder runtime y manifest13b971b3 intactos. Scripts/reports546–553 documentales; source545 ya publicado. Actualizar checkpoint y publicar esta tanda; .gitattributes conserva bytes sellados y verificarPINS indexados antes de push.
'''
(base/'HANDOFF.md').write_text(handoff,encoding='utf-8',newline='\n')
with (base/'CHECKPOINT.md').open('a',encoding='utf-8',newline='\n') as stream:
    stream.write('\n\n## Tramo553 — diagnósticos cerrados sin alterar producción\n\nEncoder:547–551 concluyen sin promoción; comparación con tokenizer real yPlannerCatalog en549, AVX2reduce_range551 insuficiente. Fallo de dependencia550 y recuperación de adjudicación551 documentados aparte. Cantidades552/553 corrigen algunas cifras pero introducen unidades/afirmaciones no verificadas:22EOS porcampaña,no adopción. Cambiar estrategia, no repetir estos enriquecimientos genéricos. Fuente545 y modelo registrado intactos; encuesta7/735/0. HANDOFF553 contiene rutas y reanudación. Ninguna decisión pendiente del dueño; C03 EN_CURSO.\n')
state=read(base/'RELEVO_ACTIVO.json')
state.update(goalStatus='active',checkpoint='553: encoder and numeric-evidence diagnostics closed without adoption; source545 published; survey7/735/0.',continuation='Resolve source/subject and capability semantics using native evidence and real product; no more generic numeric enrichment or unchanged quantization trials. Full C03 still open.',confirmedAtUtc=datetime.now(timezone.utc).isoformat())
write(base/'RELEVO_ACTIVO.json',state)
matrix=root/'documentacion/sprints/Sprints comprobación/03_MATRIZ_DE_CRITERIOS.md'
text=matrix.read_text(encoding='utf-8')
old='HEAD=origin/Goal-c03=120713be877aaf426820174ece35a642923f5eda, árbol limpio al comprobarlo tras push531; main intacto5f572ee. Incluye control892c506 y corrección88fca650. Dueñas528/530/531 y Fast verdes;'
new='Fuente adoptada HEAD=origin/Goal-c03=1d08cc297547ebc1d38d98492a41973816423416 al publicar545; sin fuente propia pendiente después. Main intacto5f572ee. Incluye control892c506 y correcciones528–545. Dueñas545:3699 pass+121 subtests,0 skips; Fast verde, Release21,23s sin advertencias/errores;'
assert text.count(old)==2
matrix.write_text(text.replace(old,new),encoding='utf-8',newline='\n')
print('Diagnostics closed; no source or runtime adoption.')
