"""Build the final investigation from sealed runs and a manually reviewed decision."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696'
out = root / 'artifacts/comprobaciones/C03/K2_HORIZON_LATENCY697'

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def link(label, path):
    return f'[{label}](<{path.as_posix()}>)'

main = [
    ('qwen-registered1', 'Qwen Q4 actual, tres ranuras'),
    ('qwen-documented1', 'Qwen Q4, muestreo oficial, una ranura'),
    ('09-bf16-high-practical-parser697-1', 'K2 0.9 BF16 high, parser697'),
    ('37-q4-high-parser698-1', 'K2 3.7 Q4 high, parser698'),
    ('37-q4-low-parser698-1', 'K2 3.7 Q4 low, parser698'),
    ('37-q4-medium-parser698-1', 'K2 3.7 Q4 medium, parser698'),
    ('09-q8-low-parser698-1', 'K2 0.9 Q8 low, parser698'),
    ('09-q8-medium-parser698-1', 'K2 0.9 Q8 medium, parser698'),
]
historical = [
    ('q8-high-reference1', '0.9 Q8 high, contexto36k, backend696'),
    ('09-bf16-high-reference1', '0.9 BF16 high, contexto36k, backend696'),
    ('37-q4-high-cpu-kv1', '3.7 Q4 high, contexto36k, KV CPU'),
    ('37-q4-high-gpu8k1', '3.7 Q4 high, contexto8k, JSON, backend696'),
    ('37-q4-high-native-selectors1', '3.7 Q4 high, XML, sólo20 selectores'),
    ('37-q8-high-native-gpu24-noop1', '3.7 Q8 high,24capas GPU, parcial20'),
    ('09-bf16-high-native-selectors1', '0.9 BF16 high, XML, sólo20 selectores'),
    ('37-q4-low-native-gpu8k1', '3.7 Q4 low, backend696 con etiquetas visibles'),
    ('37-q4-low-parser697-1', '3.7 Q4 low, parser697'),
    ('37-q4-medium-parser697-1', '3.7 Q4 medium, parser697'),
    ('09-q8-medium-parser697-1', '0.9 Q8 medium, parser697'),
]
records = {}

def table(profiles):
    lines = ['| Perfil | Cumplen | Selección /20 | Prosa /30 | Mediana final s | Máximo s | VRAM / RAM GiB |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for tag, label in profiles:
        folder = base / ('run-' + tag)
        adj, m = read(folder/'ADJUDICATION.json'), read(folder/'MEASUREMENTS.json')
        assert adj['pass'] + adj['fail'] == m['responses']
        assert m['resources']['manifest_unchanged'] and not m['resources']['violations']
        records[tag] = {'label': label, 'adjudication': adj, 'measurements': m}
        prose = str(adj['prose_and_conversation_pass']) if m['responses'] == 50 else 'No medida'
        lines.append(f"| {link(label,folder/'ADJUDICATION.json')} | {adj['pass']}/{m['responses']} | {adj['selector_pass']} | {prose} | {m['seconds']['median']:.2f} | {m['seconds']['max']:.2f} | {m['resources']['gpu_peak_mib']/1024:.2f} / {m['resources']['ram_peak_mib']/1024:.2f} |")
    return '\n'.join(lines)

main_table, historical_table = table(main), table(historical)
decision = read(out/'MODEL_DECISION698.json')
assert decision['reviewed_tags'] == [tag for tag, _ in main]
bench = read(out/'bench-fixed/RESULTS.json')
bench_table = ['| Pesos | PP512 tokens/s, graph0 / graph1 | TG128 tokens/s, graph0 / graph1 | VRAM pico MiB |',
               '|---|---:|---:|---:|']
for index, label in [(0, '0.9B Q8'), (2, '0.9B BF16'), (4, '3.7B Q4')]:
    a, b = bench[index:index+2]
    assert a['exit'] == b['exit'] == 0 and not a['violation'] and not b['violation']
    pp = [next(r['avg_ts'] for r in p['rows'] if r['n_prompt'] == 512) for p in (a,b)]
    tg = [next(r['avg_ts'] for r in p['rows'] if r['n_gen'] == 128) for p in (a,b)]
    bench_table.append(f"| {label} | {pp[0]:.1f} / {pp[1]:.1f} | {tg[0]:.2f} / {tg[1]:.2f} | {a['gpu_peak_mib']:.1f} |")
baseline = {r['id']: r['pass'] for r in records['qwen-registered1']['adjudication']['rows']}
paired = {}
for tag, _ in main[2:]:
    candidate = {r['id']: r['pass'] for r in records[tag]['adjudication']['rows']}
    paired[tag] = {
        'candidate_only_pass': [k for k in baseline if candidate[k] and not baseline[k]],
        'qwen_only_pass': [k for k in baseline if baseline[k] and not candidate[k]],
        'note': 'Includes the repeated fixture writer521-6/10; not independent statistical evidence.'}
total = sum(r['measurements']['responses'] for r in records.values())
summary = {'utc': datetime.now(timezone.utc).isoformat(), 'decision': decision, 'records': records,
    'evaluable_completed_outputs': total, 'unique_panel_entries': 50, 'distinct_fixtures': 49,
    'paired_against_qwen': paired, 'fixed_token_benchmarks': bench,
    'production_manifest_unchanged': True, 'c03_coverage_added': 0}
(out/'SUMMARY698.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

report = f'''# K2 Horizon y BAXY: velocidad, memoria y calidad real

Investigación cerrada sobre las pruebas696–698 · equipo Windows con Ryzen7 5800H y RTX3060 Laptop · fuentes consultadas9–10 de septiembre de2026.

{decision['report_lead']}

La sospecha sobre la lentitud tenía fundamento: el pequeño K2 sí puede generar rápido en esta máquina. El benchmark fijo midió **171–173 tokens/s en0.9B Q8**, **unos112 en0.9B BF16** y **unos72 en3.7B Q4**. Las esperas extremas procedían de perfiles concretos: muchos tokens de razonamiento, trabajo trasladado a CPU, reservas grandes de contexto y defectos de compatibilidad. Esas causas se investigaron por separado y se conservaron también los intentos fallidos.

## La decisión para BAXY

{decision['report_rationale']}

Esta es una decisión sobre los perfiles locales medidos. No demuestra una superioridad universal de una familia de modelos, ni certifica que cualquiera de ellos ya cumpla todo C03. El criterio de BAXY sigue siendo conservar calidad y resultados verificables con el menor consumo que cumpla, respetando español, inglés y mezcla natural.

## Cuánto tarda una respuesta real

Estas filas usan el mismo panel de50 entradas:20 selecciones de operaciones y30 respuestas basadas en hechos o conversación. Los perfiles K2 de esta tabla ya incluyen la corrección de kwargs y delimitadores efectivos; parser698 añade además la transición de pensamiento a herramientas documentada por SGLang.

{main_table}

Los tiempos empiezan al enviar la petición al servidor listo y terminan al recibir su resultado. Incluyen procesar el contexto, generar pensamiento, generar respuesta y transferirla por la API local. **No incluyen arrancar BAXY ni reproducir la voz.** Tampoco se equipara un token de pensamiento al momento en que el usuario recibe una respuesta útil. Los recibos `READY.json` conservan por separado la carga del servidor; `MEASUREMENTS.json` conserva primer token, primer contenido y tiempo final.

La RAM es el máximo de memoria residente del árbol del servidor. La VRAM es la memoria dedicada atribuida a ese mismo árbol mediante los contadores de Windows. No son la RAM total del PC, un incremento respecto al reposo ni el consumo conjunto de BAXY. Los picos se muestrean cada250ms y pueden omitir un pico más breve. 1GiB=1024MiB; el presupuesto del producto es4096MiB, aunque la GPU de pruebas tiene6GiB físicos.

## Por qué un modelo pequeño podía parecer tan lento

**La longitud del pensamiento importa tanto como la velocidad por token.** El perfil inicial0.9B Q8, high y salida máxima32768, consumió434,06s en una negación y agotó el presupuesto sin entregar un final completo. Un modelo puede generar rápido y aun así tardar minutos si produce miles de tokens antes de responder. La tarjeta IFM recomienda high y un presupuesto amplio para evaluación; el apéndice distingue esos ensayos de los límites que conviene medir para una aplicación. [IFM0.9](https://huggingface.co/IFM/K2-Horizon-0.9B), [apéndice técnico](https://huggingface.co/IFM/K2-Horizon-0.9B/blob/main/APPENDIX.md).

**Parte del modelo grande trabajaba fuera de la GPU.** K2 comercial3.7B contiene aproximadamente5,06mil millones de parámetros incluyendo embeddings. El GGUFQ8 ocupa unos5GiB antes de caché y buffers. El intento con28capas GPU llegó a4154,707MiB durante la carga y se detuvo sin generar: ese perfil excede el techo. Con24capas y offload adicional desactivado, quedó bajo el límite, pero sus logs mostraron alrededor de20s de prefill y5tokens/s. Completó20selectores en1123,47s de servidor, y se interrumpió adaptativamente antes de los30casos de prosa. {link('Intento que excedió el techo',base/'run-37-q8-high-native-gpu28-1/RESOURCES.json')}, {link('parada documentada',base/'run-37-q8-high-native-gpu24-noop1/OPERATOR_STOP.json')}.

Esa parada no estaba preregistrada. Los30registros posteriores de cancelación/conexión se conservan, pero se excluyen del puntaje; no son30fallos del modelo. El perfil anterior también cambió offload y número de capas, por lo que no se atribuye toda la diferencia a cuantización.

**El contexto tiene coste aunque la pregunta sea corta.** Reservar36864tokens de caché no equivale a reservar8192. En3.7B Q4, mover la caché de CPU/contexto36k a GPU/contexto8k redujo el tiempo mediano observado de10,50 a3,91s en aquellas corridas; la RAM residente bajó de3,51 a0,82GiB, mientras la VRAM subió de3,00 a3,37GiB. Cambiaron varias condiciones y el presupuesto de salida: son perfiles de despliegue, no una estimación causal aislada del efecto de cada flag.

La literatura de FlashAttention explica por qué reducir transferencias entre niveles de memoria ayuda a la atención; no promete una aceleración universal para cualquier GPU o longitud. El backend compilado ya usa FlashAttention y CUDA Graphs, de modo que no había un interruptor básico omitido que multiplicara por diez la velocidad. [FlashAttention, Dao etal.](https://arxiv.org/abs/2205.14135), [NVIDIA sobre CUDA Graphs](https://developer.nvidia.com/blog/optimizing-llama-cpp-ai-inference-with-cuda-graphs/).

## Los errores de compatibilidad que sí se corrigieron

El soporte utilizado es el forkIFM `model/K2Horizon`, commit `35999d101cf2233fc54f09c3c8d599da7303ce02`. La consulta remota no encontró una revisión posterior en esa rama. El anuncio original lo presenta como soporte preliminar y reconoce fricción de versiones en3.7B/7B. Un reporte de otro usuario también documenta que el upstream probado no reconocía la arquitectura; ese caso es de Linux y no mide la latencia de este Windows. [Anuncio del soporte](https://github.com/ggml-org/llama.cpp/discussions/28308), [reporte de carga](https://github.com/ggml-org/llama.cpp/issues/28361).

1. **Unicode en Windows.** La expresión de división de tokens fallaba al cargar. Corregida esa incompatibilidad, aparecieron24discrepancias entre285entradas: faltaba normalización NFC. Con ambas correcciones se obtuvo285/285 frente al tokenizer oficial para las dos tallas. La misma comprobación se repite antes de cada panel K2. Esto acredita los tokens de esas entradas; no una igualdad de logits entre llama.cpp y Transformers.
2. **Opciones de plantilla ignoradas por el analizador.** El parser analizaba la plantilla con valores por defecto aunque la petición seleccionara otro formato de herramientas. Ahora recibe los kwargs efectivos, de modo que JSON yXML se analizan según la petición real.
3. **Delimitador incorrecto para low/medium.** El historial de la plantilla renderiza pensamiento con marcas high, mientras el prefijo de la nueva generación cambia según el esfuerzo. El analizador ahora usa ese prefijo efectivo. La fuga sistemática de `think_faster` en las respuestas low quedó corregida.
4. **Transición implícita a herramientas.** La implementación oficial permite que una apertura de herramientas termine el pensamiento sin un cierre explícito previo. Se incorporó esa regla. Los cierres de esfuerzos distintos siguen sin convertirse en prosa visible: varias generaciones medium emiten cierres incompatibles y quedan registradas como fallos del perfil, sin presentar su pensamiento como respuesta. [Parser oficial SGLang](https://github.com/sgl-project/sglang/blob/main/python/sglang/srt/parser/reasoning_parser.py#L440-L491).

El último cambio tiene un caso de reproducción anterior con36fallos. Después: **121tests y4539aserciones del autoparser;39tests y210aserciones PEG; cero fallos, excepciones y skips**. Se prueban los tres esfuerzos, prosa/XML/JSON, herramientas, delimitadores y fragmentos de streaming. El buildRelease usa CUDA13 ySM86. Los15EXE/DLL están fijados individualmente: el hash del pequeño `llama-server.exe` por sí solo no identifica la implementación que vive en las DLL. {link('Recibo y validación del backend final',out/'BACKEND_BUILD698.json')}.

Las correcciones están en un backend experimental aislado y su parche es reproducible. El manifiesto productivo de BAXY conserva su hash. No se han trasladado automáticamente esas modificaciones al runtime de uso habitual.

## Comprobación independiente de la GPU

Se ejecutó `llama-bench` con prompt512/generación128, tres repeticiones,8hilos, batch512/ubatch128, capas GPU99, FlashAttention y cachéQ8. Se comparó `GGML_CUDA_GRAPH_OPT=0/1` de forma secuencial, sin dos modelos simultáneos.

{chr(10).join(bench_table)}

`GRAPH_OPT` aportó aproximadamente1,4% en generación del pequeñoQ8 y prácticamente nada en BF16/Q4. Es una optimización distinta de CUDA Graphs, que ya estaban activados. La documentación del desarrollador presenta beneficios dependientes de arquitectura/carga; los resultados en MoE y otrasGPU no se pueden prometer para este modelo denso en una3060. [Análisis CUDA del desarrollador](https://github.com/ggml-org/llama.cpp/discussions/17621).

El benchmark fijo excluye tokenización, muestreo y la conversación completa. Sus contextos efectivos son mucho menores que los8192reservados por el servidor, por eso sus números de memoria y velocidad son distintos. No se usa su pico de2956MiB para afirmar que BAXY3.7B consume sólo esa memoria. Los logs de servidor incluyen además tasas reales de prefill/generación, y los últimos perfiles guardan el prefijo renderizado por `/apply-template` antes de inferir. [Método de llama-bench](https://github.com/ggml-org/llama.cpp/blob/master/tools/llama-bench/README.md), {link('mediciones locales completas',out/'bench-fixed/RESULTS.json')}.

Se investigó también `--backend-sampling`: en este fork es experimental e incompatible con el muestreador de gramática y con el de presupuesto de razonamiento. Las peticiones de herramientas usan gramática, por lo que activarlo indiscriminadamente no era una optimización válida. No se retiró esa restricción para obtener un número de velocidad mejor.

## Lo que enseñan las reproducciones de otros usuarios

La reproducción de answ_kaz, del4de septiembre, usa un MacBookAirM5 de16GB y el mismo commitIFM. Reporta unos111tokens/s en0.9B Q4 y problemas de naturalidad/conocimiento y bucles con ciertos ajustes. También compara cuantización con y sin matriz de importancia. Apoya investigar tokenizer, cuantización y longitud de razonamiento; sus cifras de Metal y japonés no acreditan velocidad en Windows ni calidad en español. [Experiencia y mediciones del usuario](https://note.com/answ_kaz/n/naf5011d5ff5d).

Otra reproducción documenta el arranque local en AppleSilicon con el fork adecuado y los formatos de razonamiento; sirve para contrastar el procedimiento, no como benchmark de esta GPU. [Guía de Farshid Pirahansiah](https://pirahansiah.com/notes/docs/llm/k2-horizon-local/).

Se priorizaron código del backend, tarjetas de autores, trabajos originales y relatos con configuración reproducible. Los resultados anunciados de matemáticas o programación no sustituyen las pruebas de un compañero de escritorio que debe respetar hechos, identidad, confirmaciones y operaciones actuales. Tampoco una puntuación de perplexity equivale por sí sola a calidad de BAXY.

## Cómo se evitó una comparación injusta

Se descargaron cinco archivos verificados:0.9Q8/Q4/BF16 y3.7Q4/Q8. **0.9Q4 sólo se descargó; no tiene evaluación aquí.** El BF160.9 del distribuidor NANI y el oficial IFM comparten el mismo objeto y SHA256; los metadatos locales deQ8/BF16 coinciden en arquitectura, dimensiones yRoPE. Eso reduce una duda de procedencia, pero no permite atribuir toda diferencia de una semilla a la cuantización.

Para K20.9 se utilizó temperatura0,6 y para3.7 temperatura1,0; top-p0,95, sin recorte top-k/min-p, repetición1 y semilla0. High con32768tokens se midió como referencia; luego se midieron8192de contexto/4096de salida y esfuerzos más bajos como opciones de interacción. Los niveles low/medium no se presentan como reproducción de los benchmarks high publicados. Los formatos JSON y Markdown/XML están identificados en cada preregistro. [Tarjeta3.7B](https://huggingface.co/IFM/K2-Horizon-3.7B).

Qwen tiene dos controles: su perfil registrado y otro con temperatura0,7, top-p0,8, top-k20, min-p0 y sin pensamiento, siguiendo su documentación. El segundo usa una ranura y8192de contexto; el actual tiene tres ranuras de4096. El control práctico limitó salida a4096 frente a16384recomendados, sin truncar respuestas. El ahorro de memoria al reducir ranuras no demuestra la misma capacidad concurrente. [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507).

Los50casos se fijaron antes de inferir. Uno está repetido literalmente, por lo que hay49fixtures distintos; varios contienen historial y no son una muestra aleatoria de todos los usuarios. Se adjudicaron argumentos, selección, hechos y lenguaje contra el criterio de cada caso; acertar el nombre de una función no da crédito automático. La revisión es manual y no ciega, con una sola semilla. Las diferencias pequeñas no son una prueba estadística de superioridad.

El panel de selección representa una fase que propone operaciones con argumentos vacíos deliberadamente. No prueba extracción completa de argumentos, autorización del kernel ni efectos sobre el PC. Un paquete carece de la herramienta de Internet: abstenerse es el límite correcto del modelo, pero no satisface la capacidad que BAXY debe implementar. Los históricos de hardware son evidencia suministrada para prosa; reutilizarlos al pedir una lectura nueva falla el criterio de frescura.

## Todas las corridas anteriores, incluidas las fallidas

Estas filas conservan resultados de la investigación y ayudan a explicar las correcciones. Los resultados de backend696/697 afectados por parsing **no se usan como una clasificación de capacidad intrínseca del modelo**.

{historical_table}

En total se conservaron **{total} resultados evaluables** de esas repeticiones del panel, además de smokes y el intento de carga rechazado. No son{total}mensajes únicos ni requisitos de C03 completados. {link('Resumen estructurado y diferencias por caso frente a Qwen',out/'SUMMARY698.json')}.

## Qué queda demostrado sobre RAM y VRAM

Varios servidores caben bajo4GiB. El pequeñoQ8 con contexto8k ronda1,36GiB de VRAM y medioGiB de RAM residente; BF16 ronda2,23GiB de VRAM y0,69GiB de RAM. Esos ahorros se miden junto a sus fallos de calidad y no bastan para adoptarlos.

**Todavía no está demostrado el mínimo de memoria de BAXY completo con calidad suficiente.** Windows, la interfaz, Python, buffers y voz usan RAM; colocar capas de inferencia enGPU no elimina esa memoria. Incluso el benchmark con todas las capas principales enGPU conserva un buffer de embeddings en memoria host. La medición conjunta debe incluir simultáneamente las piezas que el producto mantiene activas y la latencia hasta la voz.

Para una eventual promoción K2 faltan la validación del paquete completo de DLL en el manifiesto, el ajuste del runtime a su contexto/razonamiento, argumentos y kernel reales, salidas visibles, voz y consumo conjunto. Ningún resultado nativo de este informe sustituye esas comprobaciones. El ahorro deVRAM no autoriza bajar calidad ni convertir un estado incompleto en éxito.

El diagnóstico de lentitud y la comparación aquí descrita quedan documentados. **C03 sigue activo:26casos cubiertos,716abiertos,0no aplicables.** La campaña no ha añadido cobertura a la encuesta. La siguiente intervención debe actuar sobre los bloqueantes compartidos de frescura, alcance y presentación de hechos, con el modelo elegido y pruebas reales de producto.

## Evidencia reproducible

- {link('Plan común de50casos',base/'PANEL_PLAN.json')}: criterios anteriores a las generaciones.
- {link('Plan de controles finales',out/'CONTROLS698_PLAN.json')}: perfiles y ejecución secuencial.
- {link('Backend697',out/'BACKEND_BUILD.json')} y {link('backend698',out/'BACKEND_BUILD698.json')}: parches, hashes, compilación y pruebas.
- {link('Métricas y adjudicaciones consolidadas',out/'SUMMARY698.json')}: resultados completos, errores y diferencias por caso.
- Los prompts, respuestas completas y logs con contexto histórico permanecen en almacenamiento local privado; la evidencia pública conserva IDs, causas y hashes.

Validación: buildRelease y suites completas dueñas del parser verdes, paridad de tokenizer, prefijos efectivos en los controles698, recursos y manifiesto verificados por corrida. No es una aceptación integrada de BAXY ni un Full nuevo. Full693 permanece como evidencia de la fuente anterior, sin extenderlo a este backend experimental.
'''
# Readable units and prose; never rewrite paths, URLs, hashes or inline code.
segments = re.split(r'(`[^`]*`|\[[^\]]*\]\([^)]*\))', report)
for index in range(0, len(segments), 2):
    text = segments[index].replace('K20.9', 'K2 0.9').replace('etal.', 'et al.')
    text = re.sub(r'(?<=[0-9])(?=[A-Za-zÁÉÍÓÚÜÑáéíóúüñ])', ' ', text)
    text = re.sub(r'(?<=[A-Za-zÁÉÍÓÚÜÑáéíóúüñ])(?=[0-9])', ' ', text)
    text = re.sub(r'\b(Q|K|BF|SM) (\d+)', r'\1\2', text)
    text = re.sub(r'(\d+\.\d+) B\b', r'\1B', text)
    for a,b in [('forkIFM','fork IFM'),('yRoPE','y RoPE'),('MacBookAirM 5','MacBook Air M5'),
                ('deVRAM','de VRAM'),('50casos','50 casos'),('C 03','C03'),('5800 H','5800H'),
                ('GGUFQ 8','GGUF Q8'),('yXML','y XML'),('buildRelease','compilación Release'),
                ('ySM 86','y SM86'),('cachéQ 8','caché Q8'),('pequeñoQ 8','pequeño Q8'),
                ('otrasGPU','otras GPU'),('commitIFM','commit IFM'),('AppleSilicon','Apple Silicon'),
                ('BF160.9','BF16 de 0.9B'),('deQ 8','de Q8'),('medioGiB','medio GiB'),
                ('enGPU','en GPU'),('SHA 256','SHA-256'),('7 B','7B')]:
        text = text.replace(a,b)
    text = re.sub(r'([:;])(?=\d)', r'\1 ', text)
    text = re.sub(r'(?<=[A-Za-záéíóú]),(?=\d)', ', ', text)
    segments[index] = text
report = ''.join(segments)
(out/'REPORTE_FINAL.md').write_text(report,encoding='utf-8')
print(json.dumps({'report':str(out/'REPORTE_FINAL.md'),'evaluable_results':total,
    'report_sha256':hashlib.sha256((out/'REPORTE_FINAL.md').read_bytes()).hexdigest()},ensure_ascii=False))
