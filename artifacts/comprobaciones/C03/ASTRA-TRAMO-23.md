# C03 — tramo 23: ajuste pequeño viable bajo el techo de VRAM

2026-09-06. EN_CURSO. El tramo anterior produjo evidencia y descartó candidatos;
no fue una espera ni cierre. Este tramo hereda el mecanismo de entrenamiento y
demuestra viabilidad local; la calidad del adaptador se evalúa aparte.

## Entorno aislado y herencia

`D:/BAXYRuntime/python/c03-lora-v1` hereda como dependencia de lectura el site-packages
de `gpu-reranker-r157` mediante inherited_cuda_runtime.pth. Así se reutiliza
torch2.11.0+cu128 y transformers4.57.1 sin volver a descargar CUDA ni modificar ese
entorno. Se instalaron localmente peft0.18.1,accelerate1.12.0,bitsandbytes0.49.2,
pywin32 311. Importaciones CUDA verificadas; freeze en scratchpad/c03-training-environment.txt.
El Python y el registro del producto no se cambiaron.

Base entrenable Qwen/Qwen3-4B-Instruct-2507, revisión
`cdbee75f17c01a7cc42f958dc650907174af0554`, descargada y verificada en streaming:
10 archivos/8060896487 bytes/109,95s. Directorio
`D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-training-cdbee75f/`.
DOWNLOAD.json y VERIFIED.json guardan hashes individuales, incluido tokenizer.
No es otro candidato de familia: es el padre entrenable del Qwen4B evaluado.

La herencia de `../Probando Gemma 4/dataset_finetune/scripts/train_ft.py:130–180`
es pérdida sólo sobre la respuesta, excluyendo peticiones y resultados. El perfil
histórico batch4/8,4GB fue sustituido en el ensayo por NF4,bfloat16,batch1,rank8q/v,
checkpointing no reentrante. Se conservan embeddings congelados bfloat16 para no
duplicar su memoria. Sólo se calculan logits de posiciones de respuesta; no se
recortan peticiones ni hechos para que quepan. Ninguna de estas opciones es aún
un cambio de runtime del producto.

Referencias primarias consultadas para compatibilidad:
[bitsandbytes Windows](https://huggingface.co/docs/bitsandbytes/installation),
[PEFT cuantizado](https://huggingface.co/docs/peft/developer_guides/quantization),
[PyTorch CUDA](https://pytorch.org/get-started/previous-versions/).

## Medición previa y piloto

Primer smoke sesión38085 terminal0: tres pasos finitos,pero sin contador WDDM;
RESULT marca viable=false. Se identificó falta de win32pdh y se instaló pywin32
en el entorno aislado. No se declaró suficiente la cifra interna de PyTorch.

Repetición sesión4480 terminal0: `astra-lora-memory-measured/RESULT.json`.
Tres pasos,seq512,batch1,274 tokens reales/16 respuesta; pérdida5,18→3,95,
gradientes finitos no nulos. GPU atribuida3067,54MiB,PyTorch2918MiB,32,59s.
viable=true. Sólo los2949120 parámetros LoRA son entrenables. No prueba calidad.

Piloto sesión39737 terminal0:48ejemplos sintéticos propios,16 por idioma;
24 explicaciones y24 narraciones de audio. Dos épocas,acumulación4,24 actualizaciones,
max345tokens,sin truncar. Duración100,22s,GPU3025,54MiB,PyTorch2876MiB.
No se reutilizaron preguntas reservadas de aceptación ni observaciones actuales del PC.
Doce casos de desarrollo separados congelados antes de entrenar: conceptos distintos
y estados de audio con números no entrenados; no incluyen respuestas de entrenamiento.

Datos y separación: `astra-lora-pilot-data/MANIFEST.json`,TRAIN.jsonl,HOLDOUT.jsonl.
TRAIN SHA5675fae305364fe7d944f5f263d6dd6ee8328ff5738a14050c689d67a0cfbe3b.
HOLDOUT SHA62436f17ff9599bc4c31fc0a89ab853a69ada137e9a0b319ac57606e981abc6b.
La comparación de calidad se hace leyendo cada respuesta, no midiendo pérdida.

Adaptador guardado en `<base>/c03-pilot-lora-v1/`,safetensors SHA
`d7184fbd348f769dd207efd0957a55771f106fa5d95bed591eb60c386e987073`.
Convertido con llama.cpp b9980,arquitectura Qwen3ForCausalLM,sesión28911 terminal0:
`<base>/c03-pilot-lora-v1-f32.gguf`; log scratchpad/c03-pilot-lora-convert.log.

## Evaluación y reanudación

Comparación terminada sesión19910 terminal0,script scratchpad/c03-evaluate-lora-pilot.py,
log scratchpad/c03-evaluate-lora-pilot.log. Carpeta astra-lora-pilot-evaluation.
21casos idénticos por brazo:12holdout+9desarrollo anterior; una instancia a la vez,
Qwen GGUF anterior con/sin adaptador,misma muestra,sampler y payloads.
42respuestas adjudicadas: base7/21,piloto12/21; entre12holdout,5/12→9/12.
GPUbase3497,56MiB/21,77s;adaptador3519,56MiB/16,19s. Mejoran precisión de audio y
algunas respuestas mixtas,pero previous-t2 invierte muted=false; spanglish con
historial aún falla. No promovido. PRUEBAS_AJUSTE_C03.md incluye literales y razones.
No atribuir mejora de calidad a los smokes ni promover por el éxito del entrenamiento.

Segundo piloto sesión54754 TERMINAL0:84ejemplos (48anteriores+24conhistorial+
12resultadoscompuestos),mismoshiperparámetros y base inicial,sin continuar pesos v1.
Hipótesis concreta: faltaban en entrenamiento los dos formatos donde falla v1.
18holdout congelados (12previossinentrenar+6compuestosnuevos),datos en
astra-lora-pilot2-data,log scratchpad/c03-train-lora-pilot2.log.
TRAIN SHA40a8af2d593d58d7e293ed2820229ed525020399bcb9ad084d552c3433a5037b.
HOLDOUT SHAd1079d293f08b531f2e68696a900789b77746c1fe92d769a4de71508cf53e053.
Entrenamiento176,23s/GPU3027,54MiB,42actualizaciones,max403tokens. Adaptador v2
safetensors SHA31ff9fb2839f45b402b8d9c755ba2c539a442f2cb10f6badb912297c2f119423.
Conversión y evaluación sesión77884 TERMINAL0; GGUF en la base de entrenamiento,
`c03-pilot-lora-v2-f32.gguf`. Evaluación54respuestas: base10/27 y v2 21/27;
entre18holdout,8/18 y15/18. Se corrigieron los seis casos compuestos reservados,
pero quedan6fallos en idioma/precisión. PRUEBAS_AJUSTE_2_C03.md y ADJUDICACION.md
preservan respuestas y revisión individual. No tocar runtime ni lanzar tercero
sin mejora/cambio causal demostrado. Estos números no son completitud de C03.

## Recorrido integrado y fallo visible encontrado

Sesión78801 TERMINAL0; astra-lora-pilot2-product.21publicados,13aprobados y
8noaprobados.58,11s incluyendo33,109s de preparación; GPU3519,56MiB,
RAM5294,21MiB,registro intacto. Encoder CPU preparado22,578s/25156filas.
Se corrigió el observador de preparación (encoder era argumento posicional);
no es un cambio del servicio ni una mejora medida del arranque frío del producto.
Fixture C03TitleFixture PID1312 cerrada por BAXY, windowClosed=true, sin limpieza
externa. Confirmación, cancelación y nueva confirmación quedaron registradas.

t5 publicó «Son las tres y veintitres; it’s 13:23.»: contradicción que el
verificador sólo numérico no detectaba. t6 sólo español; t7 bienvenida duplicada;
t8 explicación imprecisa de cifrado; t9 reduce backup a archivo; t10 gramática;
t13 una oración cuando se pidieron dos; t15 definición de archivo poco útil.
No se reetiquetan como aciertos por haber publicado. No son100frescos ni UI final.

## Corrección del verificador y validación

llm.py hereda _PERCENTAGE_WORD_VALUES para cardinales ES/EN, añade una y
reconoce horas escritas en marcos explícitos «son las», «es la», «the time is».
Se validan todas las horas reconocidas, incluso si otra es correcta. Conteos
ambiguos tras «it is» siguen siendo conteos. No se recorta ni sustituye respuesta.
tests/test_c03_request_preservation.py cubre contradicción, formas válidas,
acentos, guiones, AM/PM, conteos ajenos y reintento del compositor.

`pytest tests/test_c03_request_preservation.py tests/test_compose_contract.py -q`:
125pass en1,22s; scratchpad/c03-word-clock-owner-final.log. Ruff verde.
`scripts/test_source_quality.ps1 -Mode Fast`: sesión23238 TERMINAL0,
source_quality_gate_passed: mode=Fast; build0advertencias/0errores.
Log scratchpad/c03-word-clock-fast.log. Full final no ejecutado: conducta aún roja.

astra-word-clock-replay reproduce hechos históricos13:23: borrador contradictorio
inyectado rechazado reversed_result; reintento real «Son las 13:23; son las 13:23».
Corrige hora, pero conserva repetición/idioma incorrecto. ES y EN correctos;
mixed «Son las 13:23; it’s 13:23.» repite traducción. GPU3517,56MiB/4,69s.
No efectos sobre el PC ni aceptación. Los prompts y la inyección están etiquetados.

## Entrega literal y contexto

PRUEBAS_RECIENTES_C03.md recoge21integrados+4replays con evaluación por turno.
PRUEBAS_AJUSTE_2_C03.md recoge54diagnósticos base/v2. Archivo completo regenerado:
PRUEBAS_C03_PARA_EMMAN.md,104capturas/1843turnos/1729terminales publicados;
verificación literal y SHA en manifests. No son1729aciertos. Scripts de exportación
c03-report-latest.py y c03-export-pruebas.py sólo leen capturas; no ejecutan modelo.
CHECKPOINT actualizado y HANDOFF breve para contexto. No se creó otra tarea.
Todas las sesiones descritas terminaron. No commit/push ni promoción del modelo.

Siguen pendientes los ocho recorridos integrados,100frescos,UIreal,recuperación final,
runtime registrado,Fullfinal,publicación fuera de main y contratos posteriores.
