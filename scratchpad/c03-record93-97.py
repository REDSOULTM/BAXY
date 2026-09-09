from pathlib import Path
import json
import hashlib

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
names = {93: 'astra-progress-thinking93', 94: 'astra-progress-thinking94',
    95: 'astra-progress-sampling95', 96: 'astra-progress-state96', 97: 'astra-progress-stages97'}
lines = ['# C03 — progreso: perfil y alcance de hechos93–97', '',
    '93: el límite efectivo por HTTP era19s aunque begin_request pedía90; el wrapper '
    'permitía hasta2 intentos. Timeout sin respuesta observada,59047exit1. No demuestra '
    'calidad ni capacidad semántica.94 conserva exactamente primer caso y perfil, pero '
    'usa HTTP nativo único con120s. Termina length:2048tokens de razonamiento,7902caracteres, '
    'content vacío;27,361s de generación. No sirve como aviso temprano y no se adopta.', '',
    '95 compara el perfil oficial non-thinking general con semillas0,1,2 prefijadas. '
    'No es fiable: t1/s1 inventa lectura y posiciones de corrupción; t2/s1 niega acceso '
    'local; t3/s0,s1 afirman lectura; t4/s1 inventa un segundo; t5/s0 inventa falta de '
    'información, s1 invierte a bajar y escribe pido; t6/s0 invierte actor, s2 lee otra vez. '
    'Todos los18 resultados se conservan. No se selecciona una semilla favorable ni se '
    'promueve sampler. Estado/prompt/modelo no cambian en el producto.', '',
    'Fuentes consultadas2026-09-07: [Qwen3.5-4B oficial](https://huggingface.co/Qwen/Qwen3.5-4B) '
    'documenta thinking por defecto y perfil general sin pensamiento0.7/top-p0.8/top-k20/'
    'min-p0/presencia1.5/repetición1; [llama.cpp b9980](https://github.com/ggml-org/llama.cpp/blob/b9980/tools/server/README.md) '
    'documenta reasoning on/off, presupuesto y separación deepseek. Se contrastaron '
    'estos perfiles en el GGUF local, no se tomaron los benchmarks de familia como aceptación.', '',
    '96 cambia la autoridad de datos del aviso: sólo estado actual e idioma, retirando '
    'el pedido de acción todavía sin interpretar del narrador. La solicitud sigue intacta '
    'para decidir/ejecutar. Dos paquetes distintos (es/en), no seis casos independientes '
    'después de retirar sus textos. Ya no anticipa acciones, pero traduce understanding '
    'de forma poco natural.97 proyecta actividad concreta (reviewing request, preparing '
    'steps, working current step) y comprueba paso2/3. Ocho combinaciones de fase/idioma '
    'compatibles: ninguna inventa lectura ni resultado, números preservados. Redacción '
    'inglesa acting algo repetitiva, sin contradicción. Es candidato de proyección, '
    'no validación integrada ni UI. Reutiliza instrucción y sampler originales.', '',
    'Fuente92 permanece; ningún cambio de progreso todavía. Todos los perfiles quedaron '
    'cerrados, registro intacto; no procesos propios activos.98 debe transportar fase real '
    'desde FieldBridgeContract, sólo hechos al narrador y descartar composición obsoleta. '
    'No sumar otra plantilla ni modificar el pedido que recibe el planner.', '']
for number, name in names.items():
    out = base / name
    lines += [f'## Recursos{number}', '', (out / 'RESULT.json').read_text(encoding='utf-8'), '']
    posts = out / 'posts.jsonl'
    if posts.exists():
        for row in [json.loads(s) for s in posts.read_text(encoding='utf-8').splitlines()]:
            choice = row['response']['choices'][0]
            lines += [f'### {number}/{row["turn"]}/{row["variant"]}', '',
                'Final nativo: ' + (choice['message'].get('content') or '(sin contenido final)'), '',
                'finish_reason: ' + choice['finish_reason'], '']
report = base / 'PRUEBAS_PROGRESO93_97.md'
report.write_text('\n'.join(lines), encoding='utf-8')
for number, name in names.items():
    out = base / name
    files = [report, out / 'PREREG.json', out / 'RESULT.json']
    files += [p for p in (out / 'posts.jsonl', out / 'SERVER_COMMAND.json') if p.exists()]
    (base / f'TRAMO{number}_PINS.json').write_text(json.dumps({'scope': 'Native progress profiles and stage projection, not acceptance',
        'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}, indent=2), encoding='utf-8')
path = base / 'CHECKPOINT.md'
text = path.read_text(encoding='utf-8')
start = text.index('Único proceso propio activo: prototipo nativo93')
end = text.index('\n## Decisiones y pruebas', start)
text = text[:start] + '''Sin procesos/modelos propios activos.93 timeout por límite19s del wrapper;
94 HTTP nativo único alcanza2048tokens pensando y no da final; no adoptar.
95 perfil oficial non-thinking con3semillas produce invenciones; no adoptar.
96 retira el objetivo no interpretado del narrador, conservando estado/idioma:
deja de anticipar acciones.97 comprueba4fases/datos x2idiomas:8compatibles,
con paso2/3 fiel. Proyección candidata, no fuente ni UI integrada todavía.
PRUEBAS_PROGRESO93_97.md y pins fijan todo. Siguiente98: transportar fase real
desde FieldBridgeContract; narrar sólo datos actuales; descartar aviso si el
turno/fase cambió mientras se componía. Planner conserva el pedido original.
No modelos/samplers/prompts nuevos. Pruebas dueñas antes de producto/UI.
''' + text[end:]
path.write_text(text, encoding='utf-8')
path = base / 'HANDOFF.md'
text = path.read_text(encoding='utf-8')
start = text.index('Único proceso activo93')
end = text.index('\nAnterior81', start)
text = text[:start] + '''Sin procesos/modelos propios activos.93 timeout;94 pensando2048tokens sin final;
95 sampler oficial no fiable. NO adoptar perfiles.96 sólo datos de actividad
actual elimina inferencia del objetivo futuro;97 cuatro fases/datos x2idiomas
da8compatibles, paso2/3 preservado. PRUEBAS_PROGRESO93_97.md y pins.
Siguiente98: fase real del FieldBridge, sólo datos en narrador, descarte de
aviso obsoleto. Sin fuente de progreso todavía. Modelo sigue override.
''' + text[end:]
path.write_text(text, encoding='utf-8')
path = base / 'RELEVO_ACTIVO.json'
relay = json.loads(path.read_text(encoding='utf-8'))
relay.update(checkpoint='Fuente92: recuperación4/4;97 ocho combinaciones de fase/idioma compatibles; C03 EN_CURSO',
    continuation='Sin procesos activos.98: fase real, datos actuales al narrador y descarte de hitos obsoletos. Perfiles93/94/95 sin adoptar. Modelo override, no Full.')
path.write_text(json.dumps(relay, ensure_ascii=False, indent=2), encoding='utf-8')
