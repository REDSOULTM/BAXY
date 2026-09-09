import json
from pathlib import Path

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
folders=['astra-negative-contract','astra-guard-format','astra-guard-unforced','astra-guard-scoped-reading','astra-native-scope','astra-native-scope-guarded']
total=0
lines=['# C03 — diagnóstico de clasificación y recuperación compuesta', '',
       'Tramo40, 2026-09-06. Diagnósticos locales sobre once entradas consumidas o controles sintéticos. '
       'No son cien turnos frescos, no ejecutan operaciones y no constituyen una prueba nueva de producto/UI. '
       'Se conservan todas las llamadas capturadas, incluidos reanálisis y respuestas fallidas.', '',
       '## Resultado que cambia la siguiente acción', '',
       'El selector nativo AUTO identifica correctamente el conjunto de operaciones en los once controles aislados, '
       'con un catálogo diagnóstico reducido. Cuando sus decisiones pasan por LlmRuntime.decide_turn, '
       'las dos peticiones españolas de hora tras negación pierden system.time, y la pregunta sobre aire pasa de '
       'conocimiento a unsupported. El guardia de tipo interpreta esas entradas incorrectamente; ésta es una '
       'degradación entre capas demostrada, no una incapacidad general del modelo para comprenderlas.', '',
       'No se promovió AUTO ni se retiraron sus validadores en el producto. Falta adaptar el contrato completo '
       'sin recuperar el modo required, conservar abstenciones reales, alcance de negación, argumentos y todas las rutas. '
       'Los rechazos anteriores de AUTO en35 preceden las reparaciones de fecha contextual y prohibiciones solas; '
       'eso justifica esta nueva medición sin repetirla por nostalgia.', '',
       '## Cambio integrado y validado', '',
       'apply_compound_effect_conservation_veto ya no transforma una propuesta incompleta en conversation/knowledge. '
       'Eleva PlannerContractError(unresolved_compound_effects) y reutiliza la recuperación de turno existente. '
       'Un test prueba dos intentos sin alcanzar presentación ni efectuar la lectura retenida. '
       'Las propuestas completas verificadas conservan su comportamiento. No hay nuevo texto visible fijo.', '',
       'Validación: suite dueña ampliada2621pass,0skip,48,54s; control nuevo y cuatro regresiones relacionadas5pass, '
       '889deselected,0skip,1,66s. Las cifras se solapan, no se suman como2626. Fast verde, build0errores/avisos, '
       'Ruffpassed. No Full final. Logs scratchpad/c03-compound-recovery-{final-owner,boundary,fast}.log.', '',
       '## Qué se descartó', '',
       'La gramática compacta y JSONSchema dieron las mismas once clasificaciones. Quitar la restricción de formato '
       'tampoco solucionó el problema y cortó dos explicaciones a64tokens. Separar spans antes de clasificar permitió '
       'copiar peticiones positivas, pero mantuvo etiquetas incorrectas y convirtió una traducción en lectura externa. '
       'Ninguna de estas variantes se adoptó. No continuar una serie de cambios de redacción o whitespace.', '']
for folder in folders:
    records=[json.loads(s) for s in (base/folder/'posts.jsonl').read_text(encoding='utf-8').splitlines()]
    total += len(records)
    lines += [f'## {folder}', '', f'{len(records)} llamadas capturadas. '
              f'[Prerregistro]({folder}/PREREG.json), [payloads completos]({folder}/posts.jsonl), '
              f'[resultados del adaptador]({folder}/replies.jsonl), [recursos]({folder}/RESULT.json).', '']
    for i,row in enumerate(records,1):
        label=row.get('case','')
        stage=row.get('stage') or row.get('payload',{}).get('response_format',{}).get('json_schema',{}).get('name','native_or_compact')
        messages=row['response'].get('choices',[])
        lines += [f'### Llamada {i} — {stage}', '', '**Entrada del caso**', '```text', label, '```', '',
                  '**Respuesta bruta literal**', '```text']
        for choice in messages:
            message=choice.get('message',{})
            lines.append(message.get('content') or '')
            if message.get('tool_calls'):
                lines += ['```', '', '**Tool calls del servidor (JSON serializado sin cambiar sus campos)**', '```json', json.dumps(message['tool_calls'],ensure_ascii=False,indent=2)]
        lines += ['```', '', 'finish_reason: '+', '.join(str(c.get('finish_reason')) for c in messages)+'.', '']
lines[3:3]=[f'Total: {total} llamadas al modelo capturadas en seis instrumentos. No equivale a {total} peticiones nuevas de usuario.', '']
(base/'PRUEBAS_CLASIFICACION_Y_RECUPERACION_C03.md').write_text('\n'.join(lines),encoding='utf-8')

(base/'INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md').write_text('''# C03 — formato, interpretación y herencia nativa

Consulta y medición:2026-09-06. ModeloQwen3-4B-Instruct-2507Q4_K_M, servidorllama.cppb9980,
registro intacto; no se extrapola a otros modelos o backends.

## Fuentes contrastadas

- [Let Me Speak Freely?](https://arxiv.org/abs/2408.02442) estudia deterioro bajo
  restricciones de formato en sus tareas/modelos. Aporta una hipótesis, no prueba
  de que el JSON perjudique este Qwen ni razón para quitar validación.
- [Réplica de los implementadores de dotTXT](https://blog.dottxt.co/say-what-you-mean.html)
  cuestiona comparaciones con prompts/plantillas diferentes y reproduce mejoras
  con generación estructurada. Por eso aquí se conservan mensajes, sampling,
  template y presupuesto al comparar GBNFcompacto con JSONSchema y formato libre.
- [CRANE](https://arxiv.org/abs/2502.09061) estudia razonamiento con generación
  restringida. Motiva separar interpretación y formato, sin convertirlo en receta
  probada para BAXY ni habilitar thinking en una revisión Instruct que no lo ofrece.
- [Ficha oficial del modelo exacto](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
  conserva la distinción Instruct/sin thinking; recomienda instrucciones de formato
  para evaluaciones. Su template nativo admite tools. Se mantiene la investigación
  de sampling33; no se atribuye una receta de otro modelo a esta cuantización.
- [Qwen function calling](https://qwen.readthedocs.io/en/stable/framework/function_call.html),
  ya contrastado34, respalda usar su protocolo de herramientas y devolver resultados;
  la sintaxis válida no acredita selección, autorización ni ejecución.

## Herencia concreta

biblioteca/gemma4-agent/documentacion/02_router/research/1_toolcalling.md distingue
sintaxis de decisión semántica, pero sus recomendaciones son paraGemma4E4B y no
se copian como configuraciónQwen. llm._compact_structured_grammar ya advierte
que la serialización influyó enGemma: se midió enQwen, no se asumió el resultado.
astra-context-contracts35 conserva una pruebaAUTO distinta de la selección forzada
required rechazada históricamente; sus fallos de fecha/prohibición tienen cambios
upstream posteriores. Se reutiliza ese selector y el formato nativo.

La fuente anterior ProbandoGemma4/gemma4_agent/agent_core/agent.py:2189 distingue
conocimiento paramétrico de estado local a partir del plan; el booleano
needs_pc_action no bastaba. Es evidencia contra confundir cualquier consulta
científica con lectura externa. No se copia su catálogo abierto ni su modelo.

## Evidencia local y decisión

astra-guard-format:onceclasificaciones idénticas aGBNFcompacto. Formato libre no
resuelve y trunca2a64tokens. Spans literales previos no corrigen etiquetas. No
promover estas variantes. El problema observado no queda explicado por whitespace.

astra-native-scope:AUTO conserva los11conjuntos de operaciones esperados en catálogo
reducido. astra-native-scope-guarded:el guardia de tipo retira las2lecturas españolas
correctas y convierte conocimiento del aire enunsupported. Se localiza degradación
en el ecosistema. Todavía no hay promoción ni prueba deproducto conAUTO.

Cambio40independiente:un veto compuesto levanta fallo de interpretación y usa
recuperación, en lugar de autorizar prosa paramétrica sobre un hecho no observado.
Pruebas y literales:PRUEBAS_CLASIFICACION_Y_RECUPERACION_C03.md.
''',encoding='utf-8')

p=base/'CHECKPOINT.md';text=p.read_text(encoding='utf-8')
text=text.replace('tramo 40 en curso','tramo 40',1)
text=text.replace('Activo29257: astra-native-scope,11controles con selectorAUTO heredado35, catálogo\ndiagnóstico reducido. No ejecuciones ni promoción. Motivo de revisar: dos fallos\nAUTO35 (fecha contextual/prohibición sola) tienen reparaciones upstream posteriores.\nRecoger mismohandle, no reiniciar. Falta informe literal40 y handoff finales.',
'''astra-native-scope29257terminal0:11/11conjuntos de operaciones correctos en catálogo
reducido;10,62s,GPU3495,56MiB. astra-native-scope-guarded80045terminal0:decide_turn
retira las2lecturas españolas correctas y convierte aire/knowledge enunsupported;
20,66s,GPU3499,56MiB. Es degradación demostrada entre selector y guardia. No promoción.
Todos los procesos propios terminales. PRUEBAS_CLASIFICACION_Y_RECUPERACION_C03.md
guarda todas las llamadas; INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md contrasta fuentes.

Siguiente: adoptar la interpretación nativaAUTO sólo cuando el flujo integrado
conserve positivos y abstenciones; sustituir el guardia de tipo que los degrada,
sin omitir catálogo, restricciones, argumentos, conservación ni autorizaciónCore.
El contrato global de negación también necesita resolución; no reponer sólo el
parche de cláusulas39. No volver a comparar whitespace ni ampliar prompts a ciegas.
Faltan desarrollo completo,100reservados/procedencia,ocho rutas,averías/UI/recursos,
contratos posteriores afectados,Full y publicación propia. Sin bloqueo externo.''')
p.write_text(text,encoding='utf-8')
(base/'ASTRA-TRAMO-40.md').write_text(f'''# C03 — tramo40, 2026-09-06

Progreso:corregido el destino de una propuesta compuesta incompleta y localizada
degradación de comprensión entre selección nativa y guardia de tipo.

__main__.apply_compound_effect_conservation_veto elevaPlannerContractError y usa
recuperación existente; no transforma el fallo enconversation/knowledge. Cuatro
tests de rechazo actualizados y nuevo control de dos intentos sin presentación.
2621pass dueños +5pass de frontera (solapados),0skips;Fastverde,0errores/avisos.

Seis instrumentos,{total}llamadas capturadas. FormatoJSON/GBNF no explica el fallo;
quitarformato/spans previos no resuelve. AUTO aislado11/11selecciones correctas;
decide_turn retira2lecturasES y convierteaire enunsupported. No se promovióAUTO.
Literales:PRUEBAS_CLASIFICACION_Y_RECUPERACION_C03.md. Fuentes e interpretación:
INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md. Sin operaciones ejecutadas/UI nueva.

Todos los procesos propios terminales0. Modelo/registro/main intactos. C03EN_CURSO,
sin bloqueo externo niFull/publicación/reserva100. Reanudar desdeCHECKPOINT40.
''',encoding='utf-8')
(base/'HANDOFF.md').write_text('''# Handoff — C03 — 2026-09-06 — tramo40

EN_CURSO/ACTIVE, sin bloqueo externo. Goal-c03, HEAD
2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. Cambios acumulados sin commit/push;
main/ajenos intactos. Todos los procesos propios terminales; sin subagentes.
El tramo32del resumen del goal es histórico: mandaCHECKPOINT40.

## Resultado decisivo
astra-native-scope:selector nativoAUTO heredado35 acierta11/11conjuntos de operaciones
en catálogo diagnóstico reducido. astra-native-scope-guarded:al añadirdecide_turn,
el guardia semántico retira2lecturasES tras negación y convierte conocimiento del
aire enunsupported. Estado erróneo nace antes del kernel; rawselector sí entiende.
No se promovióAUTO ni se tocaron sus validadores en producto.

## Fuente integrada40
__main__.apply_compound_effect_conservation_veto ya elevaPlannerContractError
unresolved_compound_effects; reutiliza dos intentos/recuperación y nunca convierte
una propuesta incompleta enknowledge. Cuatro tests de rechazo y un nuevo control
de no llegar a presentación. No afirmar que resuelve peticiones normales perdidas.

## Evidencia y descartes
PRUEBAS_CLASIFICACION_Y_RECUPERACION_C03.md:todos los payloads/respuestas enlazados.
INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md:papers, réplica dotTXT, Qwen y herencia.
GBNFcompacto versusJSONSchema:11clasificaciones idénticas. Sin formato y con spans
previos tampoco se resuelve. No repetir whitespace/prompts. Parche sólo en resolver
léxico39 retirado:no resolvía contrato global de negación y publicóhora inventada.

## Siguiente acción concreta
Revisar llm._decide_turn alrededor de la retirada porguard_state y el contrato
unresolved_compound_contract. Sustituir la interpretación que degradaAUTO; conservar
abstenciones, restricciones, argumentos, catálogo y autorizaciónCore. Medir integrado
antes de cambiar default/registro. Los fallosAUTO35 de fecha/prohibición preceden
sus reparaciones upstream; por eso esta reevaluación es nueva y justificada.

## Validación
python -m pytest tests/test_turn_policy.py tests/test_compose_contract.py
tests/test_effect_intent.py tests/test_c03_request_preservation.py
tests/test_compound_missions.py tests/test_price_v8_veto_damage_by_cause.py -q
→2621pass,0skip,48,54s. Nuevo control +4relacionados:5pass,889deselected,1,66s.
scripts/test_source_quality.ps1→Fastverde,build0errores/avisos;Ruffpassed.
Logs scratchpad/c03-compound-recovery-{final-owner,boundary,fast}.log. NoFull/UI40.

## Runtime y pendiente
Qwen3-4B-Instruct-2507Q4_K_M;llama.cppb9980;KVq8,4096×3slots;total≤4096MiB.
Registro SHA13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed intacto.
Python LOCALAPPDATA/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe.
Quedan desarrollo,100frescos/procedencia/ocho rutas,averías/recuperación,UI/recursos,
contratos afectados,Full y publicación fuera main. SSID sigue pendiente.
''',encoding='utf-8')
print(f'Tramo40: {total} llamadas literales, investigación, checkpoint y handoff actualizados.')
