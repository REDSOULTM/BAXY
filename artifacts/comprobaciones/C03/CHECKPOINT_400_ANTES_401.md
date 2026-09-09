# C03 — checkpoint396 — EN_CURSO

ACTUAL398/399:398 terminó exit0, handle69724 cerrado, RESULT/PINS completos.
5/8 útiles en contenido/decisión,3 fallos:393bT4 ahora español pero inventa cambio
de nombre guardado; Lina invierte sujeto (“Me llamas Lina”); llama inglesa se
interpreta como solicitud de visión. José inglés correcto pero metadata mixed
todavía por tilde. RecuerdoÁlvaro,mezcla,reloj,volumen útiles.397 conservado,
no declarar resuelto el turno sólo por arreglar idioma.
399 ACTIVO handle42200: scratchpad/c03-thinking399.py. Ocho payloads exactos
(393b2lecturas,3984primarias,3872cuentasWindows), dos perfiles secuenciales en
el mismo4B/quant/backend: baselineoff0 y thinkingon512, salida1024 paraambos,
sampler originalT0, reasoning separado deepseek. Ningúnprompt/historial/operación
cambia. Registro intacto; guarda GPU3800MiB/RAMlibre768MiB ytelemetríarequerida.
PREREG astra-thinking399/PREREG.json contiene fuentesoficiales verificadas,
comparación con recomendaciónT1 y límites. Modelo3.5 admite thinking; no aplicar
esta hipótesis al Instruct2507 registrado ni declararlaadoptada. Informes previos
no miden esta modalidad. Ver replies.jsonl y baseline/thinking512-resources.json.
Recoger resultado antes de editar/build/otro modelo. Ningún400 preparado.

Actualización397/398: última fuente Python397 validada, agrega frases funcionales
de nombre a request_reading y descarta la tilde aislada como evidencia española
en _reply_uses_opposite_language. Revisión corrigió substring white/These llamas
mediante límites de palabra para frases ES/EN. Focal final21pass0skip0,29s;
dueñas1364pass0skip6,14s; Fast finalverde/build1,22s sin warnings/errores.
Baseline7fail12pass0,60s; control nuevo antes de límite2fail19pass0,54s.
RESULT/PINS397 completos, validación previa conservada. Handles97254/75892cerrados.
398 ACTIVO handle69724, scratchpad/c03-language-mind398.py, ocho controles
fijados en c03-language-mind398-cases.json:393bT4 exacto e historial nativo,
cinco variantes de idioma/nombre y reloj/volumen fijo385. Mente completa;
observador sin inyección de respuesta, sin ejecución de operaciones/App/UI/voz.
ModeloQwen3.5-4B usual, registro intacto. Salidas astra-language-mind398/replies.jsonl,
privado LOCALAPPDATA/BAXY/C03-language-mind398-private. Recoger antes de otra
fuente/build/modelo. Ningún399 preparado. Memoria compuesta y ruta genérica siguen abiertas.

Goal completo activo, Goal-c03/HEAD2bf3d4c. Preservar WIP/main/evidencia; sin
agentes, commit/push ni Full durante reparación. BAXY manual cerrado.
16 mensajes directos y 742 registros rev1248 consolidados; automáticos excluidos.
Encuesta original/servidor101140 intactos. Todos los modelos/productos/tests de
389–396 cerrados; últimos handles62347,83555,15876,94185 cerraron exit0.

Última .NET393: preguntas explícitas de nombre guardado ES/EN cruzan la ruta
privada memory.recall exact/name. Focal20pass0skip1m08 (baseline10fail10pass1m26);
seis dueñas1996pass0skip2m59; Fast verde, build17,97s cero warnings/errors.
Última Python395: chat conserva presentation_history en bounded_chat_answer,
sin restaurar contexto excluido por un tema nuevo ni duplicar el pedido.
Focal3pass0skip0,67s (baseline2fail1pass1,80s); cinco dueñas1343pass0skip6,00s;
Fast verde, build1,52s cero warnings/errors. Pins actuales V8 actualizados por
395; seis artefactos/veredicto históricos intactos. No Full.

Producto393b seis sintéticos:1 útil,1 parcial,4 fallos. Se guardó Jordan en
perfil aislado; después declarar Álvaro no persistió. Journal: enable/save/3recall
completed, save inicial failed. T3 se leyó Jordan pero el compositor negó
recuerdos; T5 dijo “Mi nombre es Jordan”; T6 genérico leyó persistenciaJordan
en vez del contextoÁlvaro. T4 conversacional reconoció Álvaro en inglés.
Posts5/10 tienen la observación correcta; primer borrador ya erróneo.
No llamar a 1996tests una solución de esta composición. RESULT/PINS393b completos.

394 averías con primer borrador en idioma opuesto: retener historial2/5→4/5
estrictos+parcialÁlvaro por inventar “en tu último mensaje”.395 lo implementa.
396 implementación real sin hook:5/5 en esa corrida. Los cinco payloads son
idénticos a394variante, pero Álvaro ahora “Te llamas Álvaro”; variación de
inferencia no explicada por payload, no borrar parcial anterior ni certificar
estabilidad. RESULT/PINS394/395/396 escritos.

389RAM libre stop antes de respuesta;3909B no-mmap cabe aislado(2,85GiB GPU,
3,89GiB RAM) pero2/4identidad, sin mejora/no promoción.391promptselector5/8→4/8
rechazado.392resolvedorcontextual5/10 rechazado: terceros→usuario, guardado
inventado. No repetir esa estrategia, variantes346/347/349/316/317 ni ampliar
el catálogo público a memory.* (376fracasó, la ruta privada permanece sellada).

Siguiente: corregir la guardia de idioma demostrada en393bT4, sin editar nombres
ni prompts. llm._reply_uses_opposite_language3915 sólo rechaza si wanted==0.
“I understand you're Álvaro. I've noted your name.” evidencia(es2,en6) pasa por
la tilde del nombre. read_request(_policy_guard_text(text)) tiene es0,en4;
Sirve separar evidencia léxica de la tilde, manteniendo el bonus cuando hay
palabras españolas (Sí). “Te llamas Jordan” aún evidencia0,0; “Me llamo Jordan”
hereda idioma si falta tilde. Posible reutilización de frases funcionales en
request_reading._ES_PHRASES; todavía NO implementado ni script397 preparado.
Después: composición de memoria393b y consultas genéricas/humanidad siguen
abiertas. UserMessagePolicy.RequiredStructuredLiterals2531 sólo conserva
reason/title, no los records. No imponer nombre ni sujeto mediante prosa fija.

C03 restante íntegro: ocho rutas y fallos264/base742 (0 validados finales);
100 humanos frescos literales con procedencia/contexto congelados(0 certificados);
averías aparte; UI real; voz física/ASR/wake/recursos conjuntos<=4GB; runtime,
instalación y contratosC04–C09 sin ejecutar otros goals; Full final verde y
publicación fuera de main. Sin bloqueo externo/cierre/porcentaje o plazo inventado.
Historial: CHECKPOINT_393_ANTES_397.md y RESULT/PINS por tramo.
