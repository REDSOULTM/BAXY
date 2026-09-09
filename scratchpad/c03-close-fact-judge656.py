"""Reject the insufficient native judge and leave the next factual work explicit."""
from pathlib import Path
import statistics

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
out = base / 'astra-native-fact-judge656'
private = home / 'C03-native-fact-judge656-private'
assert not (out / 'RESULT.json').exists()
panel = read(private / 'panel.json')
responses = rows(private / 'responses.jsonl')
assert len(panel) == len(responses) == 62
adjudication = []
for case, response in zip(panel, responses):
    assert (case['case_id'], case['arm']) == (response['case_id'], response['arm'])
    choice = response['response']['choices'][0]
    parsed = json.loads(choice['message']['content'])
    assert choice['finish_reason'] == 'stop'
    assert set(parsed) == {'label'} and parsed['label'] in {'supported','contradicted','unknown'}
    expected_accept = case['expected_label'] == 'supported'
    actual_accept = parsed['label'] == 'supported'
    adjudication.append({**case, 'actual_label': parsed['label'],
        'exact_correct': parsed['label'] == case['expected_label'],
        'binary_correct': actual_accept == expected_accept,
        'false_accept': actual_accept and not expected_accept,
        'false_reject': expected_accept and not actual_accept,
        'seconds': response['seconds'], 'finish_reason': choice['finish_reason']})
stats = {}
for arm in ['greedy','documented']:
    selected = [r for r in adjudication if r['arm'] == arm]
    stats[arm] = {key: sum(r[key] for r in selected) for key in ['exact_correct','binary_correct','false_accept','false_reject']}
    stats[arm].update(total=len(selected), median_seconds=statistics.median(r['seconds'] for r in selected),
                     max_seconds=max(r['seconds'] for r in selected),
                     false_accept_cases=[r['case_id'] for r in selected if r['false_accept']],
                     original649_binary_correct=sum(r['binary_correct'] for r in selected[:11]))
    assert stats[arm]['exact_correct'] == 26 and stats[arm]['binary_correct'] == 27
    assert stats[arm]['false_accept'] == 4 and stats[arm]['false_reject'] == 0
    assert stats[arm]['original649_binary_correct'] == 9
write(private / 'adjudication.json', adjudication)
report = ['# Juez factual656: insuficiente, no incorporado']
for r in adjudication:
    report += ['## '+r['case_id']+' / '+r['arm'], json.dumps(r['facts'],ensure_ascii=False),
               r['reply'], f"Expected {r['expected_label']}; actual {r['actual_label']}; binary correct {r['binary_correct']}; {r['seconds']:.6f}s; EOS."]
report += ['## Comparación con649',
           'Original11: existing public validator4/11, native judge9/11 binary in each profile. Additional20 include empty user_text: baseline_defect can include language/style checks and is retained raw, not claimed as a comparable pure factual score.',
           'The native task scores truth against supplied observations only. It does not evaluate completeness, requested language, utility or naturalness.']
(private / 'RESULT.md').write_text('\n\n'.join(report)+'\n', encoding='utf-8', newline='\n')
resources = read(out / 'RESOURCES.json')
assert resources['complete'] and resources['manifest_unchanged'] and not resources['violations']
note = '''# 656 — el mismo modelo no basta como juez factual

Dos perfiles de Qwen2507, greedy y receta documentada, producen las mismas decisiones:26/31 etiquetas exactas y27/31 decisiones de aceptar/rechazar. Ningún falso rechazo, pero cuatro falsas aceptaciones: dos afirmaciones de estado de proceso sin observar, otra con una aplicación llamada Running, y una afirmación sobre Chrome cuando la observación corresponde a Orbit23. También llama contradicción a un estado de proceso desconocido en el borrador real647. Los62 resultados terminan por EOS; no son cortes.

Sobre los11 controles originales649 mejora de4/11 a9/11 decisiones binarias, pero sigue aceptando dos errores. Los20 añadidos incluyen nombres, cantidades, rangos, negaciones, abstenciones, sujeto distinto, unidades y lecturas frente a efectos. Su baseline_defect bruto puede incluir idioma/estilo por texto vacío; no se usa como comparación factual equivalente. Los perfiles no cambian los cuatro errores. No se incorpora este juez ni se añade su llamada al producto.

Medianas cercanas a0,25s por clasificación; GPU3497,559MiB,RAM734,102MiB,18,953s de campaña,sin infracciones. Son recursos del servidor diagnóstico, no incremento ni mínimo de BAXY. Registro y fuentes intactos. La comprobación sólo evaluó apoyo factual, no naturalidad ni suficiencia. El contrato649 y la jerga de655 siguen pendientes; encuesta26/716/0. Próxima estrategia: contrastar verificación factual entrenada y representación explícita de observaciones, con casos bilingües y recursos medidos, antes de otra regla por frase o una capa de runtime. No repetir este juez con otro seed buscando un verde.
'''
seal(out, private, {'adopted': False, 'source_modified': False, 'stats': stats,
    'all_62_eos': True, 'resources': resources, 'product_or_ui_or_voice_credit': False,
    'baseline649_binary_correct': 4, 'baseline649_total': 11,
    'baseline_extra_cases_comparable_pure_fact_score': False}, note,
    ['panel.json','requests.jsonl','responses.jsonl','server.log','launch.log','adjudication.json','RESULT.md'])
state_path = base / 'RELEVO_ACTIVO.json'
state = read(state_path)
state.update(checkpoint='654 publicada;655 original20/20 y ampliado23/24.656 juez nativo rechazado:4 falsas aceptaciones por perfil. Encuesta26/716/0.',
             continuation='Contrato factual649: contrastar verificación entrenada/representación de hechos antes de modificar runtime. Reparar jerga española655. Ninguna decisión pendiente ni proceso activo.', activeValidation=None)
write(state_path,state)
handoff = '''# C03 — fuente654 publicada; veracidad y naturalidad siguen abiertas

Goal activo en Goal-c03. Fuente vigente b8a7399b1b1d39c701941ef24bc67f86db8f2fcf, push y remoto verificados. Main intacto5f572ee1b48cb5e2543ee5e06510e51057c9c845. Sin agentes, decisiones pendientes ni campañas activas. BAXY manual cerrado. Histórico/encuesta/nuevos autorizados por536, con procedencia honesta y generalización ES/EN. Objetivo completo en attachment b424eff2-0702-4cc9-871a-451d31ecf314/goal-objective.md; leer antes de seguir.

## Fuente y evidencia vigente

652 (d9fdf54ef75d8a0c686f44b124df2ef9334d7019) limita prosa a instalación/ventanas observadas: nativo6507/8→8/8; producto65319/20. LLM SHA e6993ddb155b9586dd178e5814604eb4ec25f7baf853d68a9c855d3d6e41de45. 654 neutraliza has compartido y añade participios comunes a las tablas existentes. Reader SHA5598275ce957f36430063a0f4fb1811b87ec9bc077fb09900c5c69684c139025; árbolPython bdcb3f8cbfcaa4f428cbf2329a3cd250c8c97b62c1018ab3594fe6fa9c10cadf. Ningún modelo, detector ni respuesta fija añadido.

654: baseline13 fallos/27 pases en40 controles; lector300 pases. Integradas3942 pases+121 subpruebas/0 skips,71s. Declaraciones22 pases/1 skip ambiental,2,56s. Fast0,Release27,65s,sin warnings/errores. Producto655: original20/20; ampliado23/24. Sólo cambia t10 entre los20originales: The ChatGPT window has focus. Las16 lecturas por app y4referencias siguen correctas. Nueva t24: La ventana activa es ChatGPT. Está maximizada y está en el foreground. Se cuenta fallo de naturalidad, no de estado; no atribuir regresión a654 sin baseline de esa variante. Todas24actividades igualan finales. Snapshots independientes de AUMID/cuentas y foreground coinciden antes/después; no captura continua ni UI. GPU3497,559MiB,RAM1864,781MiB,37,766s; no mínimo/ahorro/UI+voz conjunto.

656 terminado, sesión72764 recogida exit0. Juez nativo Qwen:31casos×2perfiles,26/31exactas,27/31binarias,4falsas aceptaciones/0falsos rechazos por perfil; todos62EOS. Original6494/11→9/11binarias, pero siguen procesos no observados. Falla además entidad ajena y app llamada Running. NOadoptado, no runtime editado. Véase RESULT/PREREG en astra-native-fact-judge656 y reporte privado completo. Bibliografía MiniCheck, revisión de autocorrección y recetaQwen ya enlazada. No repetir seeds/prompt equivalente. Evaluar verificador entrenado/representación explícita de hechos con perfil bilingüe y recursos antes de editar.

## Estado general y siguiente

Auditar/publicar656 y documentación de publicación654 antes de otra fuente. Scripts prepare654,close654-655,publication654,close656 YAejecutados,no repetir. Auditorías audit-publication654-655 y futura656 son de sólo lectura. Artefactos -text: conservar bytes. Matriz propia actualizada sin cerrar filas nuevas ni ajenas.

Contrato factual649 permanece abierto:7aceptaciones incorrectas de11controles en validador actual. No basta prohibir running ni rechazar abstenciones verdaderas. Fuente652 mejora generación, no demuestra un validador completo. Jerga española655 es otro defecto. Siguen encuesta,ocho rutas,UI real,loopback completo/AEC separado,error→restauración→normal y Full final. ContinuidadC04–C09 documentada,no ejecutar esos goals.

Encuesta742/rev1248:26cubiertos/716abiertos/0NA. Sólo H0040 acreditado en653 con16variantes. SHAprivado237c14900a9e36e2e5f6071f132ad916a234ecb39a77e0dd497ef2565eceb2b7; original y3negativos/18sinmarca intactos. No cobertura por mera familia.

Full651 previo exit0:Python10411 pases/3skips+466subpruebas,732,07s;.NET4469pases/1skip agregado y16omisiones opt-in aparte. No Full654. Full646 rojo original preservado;24regresiones633 reparadas651 sin cambiar oráculos. El encargo exige Full al adoptar C#+Python juntos y al cierre,no cada edición Python.

## Entorno

Registro SHA13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed. Qwen3-4B-Instruct-2507 Q4_K_M y b9980 registrados intactos. CPUproseadapter590 opcional,no promovido. Python C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe -X utf8. Dotnet C:/Users/usuario/.dotnet/dotnet.exe. No solapar build/Full e inferencia. Lectura UTF-8-sig en JSONL conBOM. No grep sobre tests/data enormes ni recorrer artifacts/biblioteca.

Desktop disponible mediante tools.mcp__node_repl__js y @oai/sky; skill computer-use/guidance/confirmations/api leídos. Re-listar y observar antes de actuar; comprobar foco antes de escribir; no mezclar shellUIA. DiagnósticoUI py main.py, cerrar propia instancia; no repetir launcher315 que deja abierto. Voz259 sólo eco puro, no voz humanaC08. Goal sigue activo hasta probar cierre real.
'''
(base / 'HANDOFF.md').write_text(handoff,encoding='utf-8',newline='\n')
print({'adopted':False,'stats':stats,'no_active_processes_from_this_campaign':True})
