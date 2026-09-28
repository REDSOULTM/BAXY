# Decisiones tomadas sin el dueño — Fase 3.5b «comprensión natural» (Opus 5.5, 2026-09-25)

Criterio (goal): lo sellado; si no alcanza, la práctica establecida; entre dos, la más reversible y la que nunca afirma
algo que no ocurrió.

## D1. El HEAD de partida es 4f510ee7, no b34c3f39
Situación: al abrir la sesión la rama local estaba en `b34c3f39` y el remoto un commit por delante (`4f510ee7`, sólo
61 líneas de informe en `USO_REAL_2026-09-23.md`, subido por la sesión anterior). Elegido: avance rápido al remoto y
tag `opus-cn-inicio` en `4f510ee7`. El `src`, los `scripts` y las pruebas son byte a byte los de `b34c3f39`.
Revertir: mover el tag.

## D2. La verificación de la sesión anterior sigue y es la base de regresión
Situación: `verify_chain2.sh` (sesión anterior) corría sobre `b34c3f39` con la GPU y, al final, la ventana oficial.
Opciones: pararla y medir la base yo; dejarla terminar. Elegido: dejarla. Mide exactamente el `src` de partida con el
conjunto de regresión que el goal pide (742, capas, reserva MASSIVE, guion del dueño, held-out, cien, tandas); pararla
tiraría horas de GPU y dejaría la verificación de la sesión anterior sin cerrar. Mientras corre: nada de GPU ni de
ventana ni de `src` por mi parte; F1 avanza en CPU (conjuntos, oro, puntuador). Revertir: nada.

## D3. Los conjuntos DEV-A, DEV-B y FINAL viven fuera de git
Situación: los conjuntos mezclan frases públicas y conversaciones escritas por subagentes; la práctica de la campaña
(paso 6, tandas) es no versionarlos. FINAL no se puede abrir hasta el cierre y DEV-B no se mira por fallos.
Elegido: `%LOCALAPPDATA%\BAXY\comprension-2026-09-25\` (dura entre sesiones, fuera del árbol que exploran los
subagentes); en git sólo sus SHA-256 y los scripts que los construyen y puntúan. Revertir: copiarlos al árbol.

## D4. Qué cuenta como «ya visto» (exclusión de F1)
Situación: el goal pide excluir los 1 779 ids usados, las 742, las tandas, la reserva MASSIVE y todo lo que esté en los
índices del producto. Los ids no bastan (la misma frase aparece en varias particiones y fuentes). Elegido: exclusión
por **texto normalizado** (minúsculas, sin tildes ni puntuación) contra 79 464 textos: todo `*.jsonl` del scratchpad de
la sesión anterior (tandas 1–12 y 20, conversaciones escritas, desarrollo y reserva MASSIVE, capas, diagnósticos), el
registro de las 742, el corpus semántico, los guiones versionados de `C03/`, el índice de evidencia del turno
(MASSIVE train, PRESTO train, histórico), `historical_messages.jsonl`, el banco de intenciones y MASSIVE train es/en
entero; más los 13 371 SHA-256 de `historical_runtime_intents`. Fuentes nuevas: MTOP test/eval es/en (fuera del
índice, que usa train) y PRESTO test es/en (spanglish, disfluencias, auto-correcciones y seguimientos humanos con
contexto). Revertir: nada (sólo define los conjuntos).

## D5. Filtro de seguridad de los conjuntos
Situación: DEV-B y FINAL se corren en la ventana oficial con efectos reales. Elegido: el filtro de las tandas
(apagar, cerrar, borrar, enviar, llamar, comprar, red…) ampliado con responder correos, vaciar papelera e imprimir;
tope de 3 frases por intención y fuente en cada conjunto para que ninguna intención domine. Coste conocido: esas
familias quedan fuera de la medida de comprensión (las cubren las 742). Revertir: regenerar con otro filtro.

## D6. Escritura, oro y reparto sin sesgo entre conjuntos
Situación: si cada conjunto lo escribe un subagente distinto, DEV-B y FINAL tendrían otra distribución que DEV-A.
Elegido: tres escritores de sala limpia (sólo leen reglas del oro y catálogo compacto; mismo encargo, cada uno 18
conversaciones con los siete hablantes) y un reparto por hablante entre los tres conjuntos hecho por script; los
sueltos y las conversaciones públicas de los tres conjuntos se mezclan con ids opacos entre tres etiquetadores. Las
reglas del oro (`REGLAS_ORO.md`) son las del dueño (lo público se busca, lo propio no, lo completo no se repregunta,
cantidad relativa sin número se pregunta, límite llano, dato personal que falta se pregunta). Revertir: rehacer el
reparto con otra semilla.

## D7. Auditoría del oro y desacuerdos
Situación: el goal pide que un segundo subagente audite el 10 % del oro; DEV-B no se mira por fallos y FINAL no se
abre. Elegido: auditoría **a ciegas** (el auditor escribe su propio oro sin ver el primero) sobre una muestra
estratificada del 10 % de cada conjunto; acuerdo = los dos oros aceptan una decisión común. Los desacuerdos de DEV-A
los resuelvo yo; los de DEV-B y FINAL, un subagente adjudicador (yo sólo veo cuántos). Revertir: rehacer la muestra.

## D8. El conjunto de regresión por mecanismo
Situación: el goal pide «sin regresión en el conjunto de regresión» para cada mecanismo; entero (742, capas, reserva de
2 757, guion y held-out en la ventana) son ~2 h de GPU más la ventana. Elegido: cada mecanismo candidato se mide primero
en DEV-A + DEV-B + 742 + capa A (sólo decisión, ~25 min); sólo el que pasa la regla de DEV-B se mide además con la
reserva y las capas B/C, y el guion del dueño y el held-out se corren en la ventana en los hitos (antes de F5 y en
F6). Revertir: medirlo todo cada vez.

## D9. FINAL sellado
Elegido: FINAL se construye con los mismos scripts que imprimen sólo cifras; su texto no pasa por esta sesión; en git
va sólo su SHA-256. Sus desacuerdos de auditoría los resuelve un subagente. Revertir: no aplica.

## D10. Candidatos nuevos de F3 (pedido del dueño 2026-09-25 12:45)
El dueño pidió añadir «Qwen 3.8 4B» y revisar modelos nuevos del mes. Qwen3.8 oficial no tiene variante pequeña (27B,
Flash-Next 180B-A6B, 2,4T). Se añade la destilación comunitaria **empero-ai/Qwen3.8-4B-Distill** (Apache-2.0,
arquitectura Qwen3.5-4B, sin cifras publicadas de herramientas ni de español): GGUF del autor
`empero-ai/Qwen3.8-4B-Distill-GGUF@391fc7d1`, Q4_K_M (2 783 446 304 B, `dec96e8c…87c6790`) y Q5_K_M
(3 161 425 184 B, `735cd00b…0c0892`), SHA-256 verificados, en `D:\BAXYRuntime\experiments\models\qwen38-4b-distill-391fc7d1\`.
Ley 1: su arquitectura (DeltaNet híbrido) no reutiliza el prefijo del prompt en llama.cpp (#21831), que es el camino
caliente de un decisor con prompt fijo largo; se mide, no se supone. Otros nuevos a considerar en F3: IBM Granite 4.2
3B/8B (25-ago, Apache-2.0; 8B con RL agéntico) y el refresco de pesos de Gemma 4 E2B (15-jul, arreglos de tool calling).
Descartados por tamaño: Qwen3.6-35B-A3B, Nex-N2.5-mini (35B-A3B), Qwen3.8-27B.

## D11. Regla prerregistrada del torneo F3 (escrita antes de medir, 2026-09-25 15:25)
Configuración: la ganadora de F2 — decisor libre (`comprension-f1/free_model.py`, variante `min`, mismo prompt y
catálogo compacto para todos, plantilla de chat embebida del GGUF), `llama-server` b9980 con los flags del producto,
1 slot, 12 288 de contexto. Población: DEV-A + DEV-B (513 turnos), sólo decisión.
Candidatos: Qwen3.5-4B Q4_K_M (líder de F2), Qwen3-4B-Instruct-2507 Q4_K_M (actual), Qwen3.8-4B-Distill Q4_K_M,
Granite 4.2 3B Q4_K_M, Gemma 4 E2B Q4_K_M (pesos de julio), Phi-4-mini Q4_K_M, Qwen3-8B IQ3_XXS. Fuera por VRAM sin
medir: Granite 4.2 8B (Q3_K_S 3,94 GB + contexto), Qwen3.5-9B, Gemma 4 E4B, Qwen3-4B Q6/Q8. xLAM-2-3b sólo con el «sí»
del dueño (cc-by-nc-4.0).
Regla: un candidato **desplaza al líder** si (1) acierta **≥ +10 turnos** en A+B con McNemar exacto p < 0,10 sobre los
turnos emparejados, (2) no pierde más de 2 seguimientos (134), (3) decisión p50 ≤ 1,0 s y p90 ≤ 2,5 s, (4) pico de VRAM
del árbol del servidor ≤ 4 096 MiB medido, (5) licencia que permite uso comercial. Si ninguno cumple, sigue el líder.
Un candidato que queda a ≤ 5 turnos del líder con p ≥ 0,10 y ≥ 300 MiB menos de VRAM se informa como alternativa ligera
(ley 4), sin adoptarlo en F3. El ganador no entra al producto por ganar aquí: entra con el mecanismo de F4 medido en
DEV-B y el conjunto de regresión.
**Enmienda a D11 (≈15:22, antes de correr ningún candidato del torneo; el torneo empezó 15:23):** la variante `request` (el decisor reescribe
primero el último pedido como pedido completo y después decide) terminó después de escribir D11 y es la
configuración ganadora de F2: Qwen3.5-4B 189/260 y 204/253 (seguimientos 51/68 y 61/66) frente a 182 y 196 con `min`,
p50 0,67 s. El torneo se corre en `request`; el resto de la regla no cambia.

## D12. Regla de entrada de M1 (decisor en contexto + Qwen3.5-4B + 12 288 por ranura), escrita antes de medirlo
M1: `semantic/decider.py` + `LlmRuntime.decide_in_context` + `_context_decided_result`. Un mensaje con conversación
previa lo decide el decisor con la conversación entera; el primero de una conversación pasa por los lectores y, si
ninguno lo prueba, lo decide el decisor (reparto V2 de F2). El modelo del runtime pasa a Qwen3.5-4B Q4_K_M con 3
ranuras × 12 288 (3 708 MiB medidos). Entra si, con la cifra **estricta** de `comprension_eval.py` (decisión y
argumentos clave): DEV-B total ≥ 72,2 % (base 69,2 + 3) **o** seguimientos de DEV-B ≥ 58,0 % (base 53,0 + 5); y en
regresión: capa A ≥ 96,0 % (base 96,5), reserva MASSIVE ≥ 81,2 % (base 82,2), y cada decisión de las 742 distinta de
la base revisada una a una. Guion del dueño, held-out y cien se miden en la ventana en el hito de F5. Si no entra, se
revierte. Después de entrar, lo que sustituye (selector nativo, lista corta para decidir, vetos del camino del modelo,
re-armado del hueco, recuperación) se retira en commits medidos con el mismo conjunto.

## D13. LoRA del decisor: autorizado por el dueño, local (2026-09-25 ~20:45)
Pregunta (marcada PREGUNTAR en el goal), con la evidencia: DEV-B 77,1 % con M4; M3, M5 y M6 retirados porque no
mueven o empeoran; lo que queda son elecciones del modelo (operación hermana, actuar sobre comentarios, límites
falsos). Respuesta del dueño: **sí, local**, preguntando si cubre lo que AGENTS.md e identidad piden. Alcance acordado:
sólo la decisión (no la personalidad, que sigue en el prompt): el adaptador se aplica por petición únicamente a la
llamada del decisor; se declara en el manifiesto con su SHA-256; datos sintéticos de sala limpia disjuntos de DEV y
FINAL (`comprension-f1/brief/ENTRENAMIENTO.md`), ningún dato del dueño. Se juzga con la regla de siempre en DEV-B y el
conjunto de regresión; si no entra, se retira. Aviso de ley 1: el LoRA heredado de FunctionGemma aprendió su corpus y
fuera de él cayó (63/124). Los créditos de Claude no pagan GPU (lo preguntó el dueño): se entrena en la RTX 3060.

## D14. Receta del LoRA corregida por el estado del arte (pedido del dueño 2026-09-25 ~22:00)
El dueño pidió basar el ajuste en papers, documentación y experimentos de usuarios, no en conocimiento propio.
Hallazgos y cambios:
- **Unsloth, guía de Qwen3.5:** no recomienda QLoRA de 4 bits en Qwen3.5 («higher than normal quantization
  differences»); pide LoRA bf16 (~10 GB para el 4B), módulos q/k/v/o + gate/up/down, transformers v5, α ≥ r, dropout 0,
  lr 2e-4, 1–3 épocas, pérdida sólo en la respuesta. Medido aquí: bf16 no cabe en 6 GB; 8 bits, 10 GB y 255 s por paso.
- **llama.cpp #21125 + código del conversor b9980:** la conversión a GGUF de un LoRA de Qwen3.5 falla en
  `_reorder_v_heads`, que sólo se aplica a `linear_attn.*`. El primer piloto entrenaba esas proyecciones: se detuvo; el
  entrenamiento sólo toca atención completa y MLP.
- **Hammer (ICLR 2025):** enmascarar los nombres de función en ~33 % de los ejemplos (lee descripciones: sirve para
  catálogos nuevos, como los del motor de computer use) y ~10 % de ejemplos sin la función correcta (→ límite, no
  inventar operaciones). Añadido a `build_train.py`.
- **Gorilla (entrenamiento consciente del recuperador):** documentación en el prompt, a veces incompleta: confirma el
  catálogo parcial por ejemplo.
- **Internalizing Tool Knowledge (QLoRA, 2026):** Qwen3-4B, ~1 700 ejemplos, r 32, α 64, lr 2e-4, 2 épocas; olvido
  fuerte (61 % retenido). Aquí el adaptador sólo se aplica a la llamada del decisor: la redacción y el resto no se ven
  afectados.
Decisión del dueño: **piloto aquí (QLoRA 4 bits, receta corregida, para validar la dirección) y, si da lo esperado,
entrenamiento completo en bf16 en su PC principal (RTX 4060 Ti, 16 GB)** con un prompt que le preparo al agente de
ese PC (que va ~5 días atrás en el desarrollo).

## D15. Piloto 1 del LoRA: no mejora; receta de datos corregida (2026-09-25 ~23:45)
Piloto 1 (bf16 en redpc, 400 ejemplos, 23 min; pérdida de validación 0,346 → 0,125), el decisor aislado con el
catálogo entero, sólo decisión:

| | base | piloto 1 |
|---|---|---|
| DEV-A (se mira) | 198/260 | 199/260 (arregla 25, rompe 24) |
| DEV-B (ciego) | 208/253 = 82,2 % | 201/253 = 79,4 % |

En DEV-A arregla la elección entre operaciones hermanas (10 de 25) y rompe límites y preguntas que pasan a acción (17
de 24). Dos causas en los datos: (1) reparto sesgado a actuar (acción 61 %, límite 10 %, pregunta 3,8 %; DEV-A: 47 %,
20 %, 11,5 %); (2) atajo en el catálogo parcial: los ejemplos de acción traían la familia completa de la operación
correcta y los demás operaciones sueltas, así que «familia completa a la vista» significaba actuar, y en el producto
todas lo están. No se entrena el completo con esa receta. Cambios (datos, no reglas):
- **Negativos difíciles** (Hammer, ToolACE y xLAM usan ejemplos de irrelevancia y casi-acierto): 4 escritores de sala
  limpia (`brief/NEGATIVOS.md`), 400 conversaciones, 680 mensajes: 203 límites que suenan a una operación, 158 preguntas
  de verdad, con contraste (279 acciones que sí son y 40 charlas).
- **Catálogo que no depende de la respuesta**: familias completas al azar hasta ~60 operaciones, con las de la
  respuesta dentro; irrelevancia 15 % (las hermanas quedan a la vista). El catálogo entero del producto (~7 000 tokens)
  no cabe en bf16 en 16 GB en el backward (medido: sin memoria); la validación sí usa el catálogo entero.
- Datos v2: 2 654 ejemplos (acción 50 %, límite 21 %, charla 20 %, pregunta 8,5 %) + 127 de validación.
Regla para seguir: el piloto 2 (800 ejemplos) debe superar a la base en DEV-B sólo decisión; si no, el LoRA se da por
no rentable con estos datos y se vuelve a los mecanismos de F4.

## D16. Piloto 2 pasa por poco; entrenamiento completo (2026-09-26 ~01:15)
Piloto 2 (datos v2, 800 ejemplos, 72 min; pérdida de validación con el catálogo entero 0,380 → 0,139), sólo decisión:
DEV-A 203/260 (base 198; arregla 30, rompe 25); **DEV-B ciego 210/253 = 83,0 %** (base 208 = 82,2 %; piloto 1 201);
latencia p50 0,66 s (base 0,77); deriva de idioma de la reescritura 2/68 (base 22/100). Cumple la regla de D15. En
DEV-A el sesgo se invirtió: sobran límites (búsquedas públicas, clima y listas como «no lo hago»). Receta del
completo: los 2 654 ejemplos, 1 época, irrelevancia sintética 10 % (el valor de Hammer; los negativos escritos ya
traen los límites de casi-acierto), resto igual. Se mide igual que los pilotos; si entra, se integra con la regla de
D12 (DEV-B, capa A, reserva, revisión de las 742).

## D17. LoRA completo: +3,6 pts en DEV-B aislado; se mide integrado (2026-09-26 ~04:15)
`full1` (datos v3: 2 654 ejemplos, 1 época, 2 h 38 min en redpc; pérdida de validación con el catálogo entero
0,380 → 0,111; adaptador GGUF f16 42 MB). El decisor aislado, catálogo entero, sólo decisión:

| | base | piloto 1 | piloto 2 | completo |
|---|---|---|---|---|
| DEV-A (se mira) | 198/260 | 199 | 203 | **225/260 = 86,5 %** |
| DEV-B (ciego) | 208/253 = 82,2 % | 201 | 210 | **217/253 = 85,8 %** |
| seguimientos DEV-B | — | 62/66 | 58/66 | **61/66** |
| latencia p50 | 0,77 s | 0,74 s | 0,66 s | 0,65 s |
| deriva de idioma (DEV-A) | 22/100 | 2/133 | 2/68 | 2/84 |

Supera el umbral de F4 (DEV-B ≥ +3 pts). Se integra en el producto (`decider_adapter.py`, sólo en la llamada del
decisor) y se mide con la regla de D12 antes de entrar: DEV-B del producto, capa A ≥ 96,0 %, reserva ≥ 81,2 %,
cada cambio de las 742 revisado.

## D18. M8 entra: decisor en contexto + argumentos (M7) + LoRA del decisor (2026-09-26 ~05:30)
Regla de D12 sobre el producto (Qwen3.5-4B, 12 288 por ranura, adaptador `full1` sólo en la llamada del decisor):
DEV-B **78,3 %** (≥ 72,2; base 69,2), seguimientos DEV-B 80,3 % (base 53,0), DEV-A 82,7 % (base 59,6); capa A
**96,4 %** (≥ 96,0; base 96,5; registro real del dueño 92,3 %, base 90,1 %); reserva MASSIVE **84,0 %** (≥ 81,2; base
82,2; decisión p50 0,81 s, base 0,93); 742: 20 distintas de la base, revisadas una a una (8 mejor, 4 peor, 8 igual).
VRAM de pico del servidor con el adaptador y 3 decisiones concurrentes de ~6 700 tokens: **3 804 MiB** (≤ 4 096).
Runtime del producto registrado de nuevo (`register_mind_runtime.ps1 -DeciderAdapter`): GGUF Qwen3.5-4B
(`00fe7986…`) y `decider_adapter` (`45f4d730…`), respaldo del anterior en
`%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.before-m8-2026-09-26.json`. Pendiente para el Full verde (F6): la suite
tiene ~165 pruebas que fijan el camino viejo (selector y verificadores sobre turnos no probados, que ahora decide el
decisor) con LLM falsos sin `decide_in_context`: se retiran o se reescriben contra el decisor (ley 2). Los 4 peores de
las 742 (H0313 inventa, H0407, H0506 a nota, H0604 «llamo») van como datos al próximo ajuste, no como reglas.

## D19. Segundo ajuste del LoRA: planes, reacciones en conversación y lo propio (2026-09-26 ~11:30)
Las mediciones de M8–M13 dejaron tres huecos del decisor con LoRA: convierte los planes del dueño en una acción o en
charla (M9: capa A 70 %), contesta con una pregunta a comentarios y agradecimientos en conversación («gracias, así
está bien», «Me gusta como se desenvuelven»), y confunde lo propio («guardá que mi cumpleaños…» → nota, «Como me
llamo» → «no llamo», «nunca cierres spotify» → pregunta, «inactiva la alarma de la casa» → cancelar una alarma del
PC). Cuatro escritores de sala limpia (`brief/AJUSTE2.md`) escribieron 400 conversaciones, 810 mensajes (w14–w17:
166 mensajes con 2–3 operaciones, 152 charlas, 54 límites, 22 preguntas). Datos v4: 3 404 ejemplos. Receta igual a
`full1` (1 época, irrelevancia 10 %, familias de ~60 operaciones) para que la única diferencia sean los datos.
`full2` entra sólo si el decisor aislado no baja en DEV-B y, integrado, cumple la regla de D12 y mejora la capa A o la
reserva sin empeorar DEV-B; las 742 no se usan como datos.

## D20. `full2` entra (2026-09-26 ~17:00)
Decisor aislado: DEV-B 222/253 = 87,7 % (full1 217), seguimientos 63/66; DEV-A 220/260 (full1 225: más límites en
pedidos de listas y streaming). Integrado con M14–M17 (Qwen3.5-4B, 12 288/ranura): **DEV-B 81,8 %** (78,3), seguimientos
B **89,4 %** (80,3), sueltos B 76,8 %, DEV-A 81,9 % (82,7); capa A **96,5 %** (96,2; registro real 91,2 %, 742 97,2 %);
reserva **84,3 %** (84,0; decisión p50 0,81 s); 742: 18 distintas de la base (las 20 de M8 menos H0271 y H0414, que
vuelven a la base: 8 mejor, 4 peor —H0313, H0407, H0506, H0604, las mismas—, 6 igual); VRAM 3 804 MiB. Runtime
registrado con `decider-full2.gguf` (`01bf479a…`; respaldo `mind-runtime-v1.before-full2-2026-09-26.json`). App
real: guion 47/60 (+7 por revisar), held-out 26/30. Lección para el próximo ajuste: el encargo AJUSTE2 decía «límite
si todo depende de lo que no se hace» y el modelo lo generaliza: «abre steam y ve a la biblioteca» → límite, cuando
abrir Steam se hace; lo que se puede hacer de un pedido mixto se hace y lo demás se dice.

## D21. Tercer ajuste: lo que sí se hace; las puertas de regresión nunca entrenan (2026-09-26 ~17:50)
`full2` dice «no lo hago» a pedidos que el catálogo sí hace (DEV-A: «fire up steam», «añadir gaseosa a super», «what
are my lists», «Cancela todos los recordatorios de hoy»; guion: «abre steam y ve a la biblioteca» → límite, por una
regla de AJUSTE2 que el modelo generalizó). Encargo `brief/AJUSTE3.md` (sin frases de DEV ni de las puertas: sólo
formas): 4 escritores, 400 conversaciones, 828 mensajes (559 acciones con verbos y objetos poco comunes, 196 charlas en
conversación, 64 límites de contraste, 9 preguntas); pedidos mixtos → lo que se puede hacer. Irrelevancia sintética
5 % (antes 10 %). Auditoría de contaminación: los datos de `full2` compartían 54 órdenes cortas y genéricas con las
742, el guion y el held-out («abre la calculadora», «sube el volumen»; las deciden los lectores, no el decisor) y
ninguna frase peculiar; desde v5 `build_train.py` excluye los literales de las 742, el guion, el held-out y el
registro real (81 descartados en total). Datos v5: 4 119 ejemplos. `full3` entra con la regla de D19.

## D22. `full3` entra; la búsqueda web queda fuera de la comparación mientras la red esté marcada (2026-09-26 ~23:40)
Decisor aislado: DEV-B 225/253 = 88,9 % (full2 222), sueltos 103, seguimientos 64/66; DEV-A 230/260 (full2 220).
Integrado sobre M19: DEV-B 80,6 % con la misma decisión (214/253) que `full2` —6 arreglados y 9 rotos, McNemar
p = 0,61: ruido—; DEV-A **83,5 %** (81,9); capa A 96,1 % (≥ 96,0; frente a M19, −3 en las 742 y −2 en el registro
real, revisados: H0271 pasa a la pregunta que pide su oro, H0604 lee `system.identity` en vez de recordar, cuatro
filas del registro real mejoran —«abre steam y ve a la biblioteca» → app.open— y dos se vuelven búsquedas no pedidas);
reserva **85,2 %** (84,3). Cumple D19 y D12. Runtime registrado con `decider-full3.gguf` (`41f83fa4…`; respaldo
`mind-runtime-v1.before-full3-2026-09-26.json`; sólo cambia el adaptador, mismo base).
App real (23:24–23:30): guion 44/60 (+6), held-out 25/30. Las 7 diferencias con `full2` no son del adaptador: en 5
turnos web.search terminó `web_search_results_irrelevant` (la decisión fue idéntica) y en 1 un veto de redacción
(«los fallos» de la persona leídos como fallo afirmado, M21). A esa hora los motores tratan esta red como automatizada:
DuckDuckGo devuelve «anomaly» (202), Mojeek «your network appears to be sending automated queries» (403), Brave pide
captcha y Bing HTML responde otra cosa («Tortugas Ninja» a «la serie The Last of Us vale la pena», foros chinos a
«primer libro de zombies»); el filtro de pertinencia los rechaza bien. No se esquiva la detección de bots; las cifras
del guion y del held-out se repiten cuando la búsqueda vuelva, y hasta entonces los turnos de búsqueda se leen aparte.

## D23. Cuarto y quinto ajuste en uno solo: `full5` con los datos v7 (2026-09-27 ~02:45)
Meta pendiente: sueltos ≥ 88 % (DEV-B 74–77 %). Los 23 sueltos que fallan en DEV-A (el conjunto que sí se mira) caen
en tres grupos: lectores viejos que deciden antes (9; M9 y M10 ya mostraron que ceder todo rompe las 742 y el registro
real), el catálogo llano mal descrito (M22) y el decisor ante autocorrecciones, muletillas, mensajes largos y servicios
ajenos. Encargo `brief/AJUSTE4.md` (w22–w24, 300 conversaciones, 496 mensajes: autocorrecciones y muletillas; mensajes
largos con el contraste de conversación ajena; servicios ajenos → límite). Los fallos de la app real que no eran la
búsqueda (guion t57 «al volumen» → pregunta, held-out t14 «averiguá qué dijo la crítica» → pregunta, cien 038/077)
son seguimientos sobre lo que BAXY acaba de hacer o decir: `brief/AJUSTE5.md` (w25–w27, 300 conversaciones, 1 028
mensajes: remates y precisiones → charla que confirma; preguntas sobre la conversación → charla; encargos sobre el tema
ya hablado → web.search con el tema). Sólo formas; ninguna frase de DEV, FINAL ni de las puertas (y desde v6 también se
excluye cien). `full4` (datos v6) se lanzó a las 02:03 y se paró en el ejemplo 280 (4,2 s por ejemplo: dos ciclos de
5–6 h en vez de uno); `full5` = datos v7 (5 557 ejemplos, receta igual a `full3`), con el catálogo llano de M22 en el
entrenamiento y en la evaluación aislada de redpc (copiada allí antes de evaluar). Entra con la regla de D19 y D12.

## D24. `full5` no entra; el producto sigue con `full3` (2026-09-27 ~14:20)
Integrado (M25, mismo árbol que M23 más el adaptador): DEV-B 77,5 % (full3 80,2), sueltos B 71,2 % (74,4), DEV-A
81,9 % (85,0), capa A **95,8 %** (< 96,0; registro real 87,9 %), reserva 83,8 % (85,6; 37 arreglados, 88 rotos). Aislado,
DEV-A sólo decisión 227/260 frente a 230 de `full3`. Lección: los datos v7 subieron la charla de 997 a 1 412 ejemplos y
el decisor habla de más; seguir ajustando el LoRA no es el camino al 88 % de sueltos. Lo que sí mide la distancia: en
DEV-B `full3` aislado decide bien 225/253 y dentro del producto 212; por camino (agregados, DEV-B es ciego), los turnos
que no llegan al decisor pierden ≈ 13 (lectores de efectos 3, de conversación 2, conversación ajena 1, respuestas que
el contrato rechazó y la recuperación convirtió en pregunta 4, el propio camino del decisor 3). Siguiente: M10b (la
conversación ajena la lee el decisor) y, si pasa, los lectores de efectos; las respuestas rechazadas se atacan en la
redacción. (Lo que se midió para los lectores de efectos fue M9c, la versión estrecha: el lector cede sólo si el
decisor lee un límite; M9b —cederlo todo— es M9 y no se repitió.)

## D25. Etapa de preferencias (RPO) sobre `full3`: la ronda 1 no mueve nada; la ronda 2 sube el paso (2026-09-28 ~03:20)
Por qué preferencias y no más SFT: `full4` y `full5` empeoraron al sumar datos (cuotas por clase, Hammer 2410.04587;
When2Call 2504.18851: el SFT con negativos vuelve conservador al modelo y RPO no). Herramienta propia sin TRL
(precálculo de log-probs de referencia, pérdida sigmoide de DPO + NLL del elegido, β 0,1, α 1,0; probada en CPU 17/17).
Pares: 450 escritos en sala limpia (auditados: 448 bien) + 295 errores minados de `full3` sobre sus propios datos,
tope 60 por tipo → 480 de entrenamiento. Ronda 1 (lr 5·10⁻⁶, 1 época, acumulación 8 ≈ 60 pasos): aislado **igual**
que `full3` con el mismo catálogo (DEV-A 234, DEV-B 225, sueltos B 104). Demasiado suave: 5·10⁻⁶ es la tasa del
ajuste completo; con LoRA suele hacer falta un orden más. Ronda 2: lr 5·10⁻⁵, pares de la ronda 1 + errores minados
en frases que `full3` nunca vio, filtrados por la auditoría de etiquetas (173 → 77; se quita el contraste «dos temas
→ preguntar» de AJUSTE5 y se limita el remate a 2 por contraste) → 518. Entra con la regla de D19 y D12.

## D26. DEV-C sellado para confirmar (2026-09-28 ~03:50)
DEV-B decidió más de 20 mecanismos y su cifra ya está algo ajustada (goal v2 §3). DEV-C se construyó con el método de
F1 copiado sin cambios (reproducción byte a byte de los conjuntos de F1 antes de empezar): 125 sueltos con el mismo
reparto de fuentes que DEV-A (MASSIVE, MTOP, CLINC150, OVOS-ILENIA, CSTOP, PRESTO, oasst2), 103 turnos de 30
conversaciones públicas (PRESTO, SGD, oasst2) y 73 turnos de 18 conversaciones escritas en sala limpia (seis hablas,
dos en spanglish). Exclusión contra todo lo visto (DEV-A/B, FINAL, 742, guion, held-out, cien, registro real, reserva
MASSIVE, todo el entrenamiento y los pares, y los ficheros de las sesiones): 0 iguales, 0 hash, similitud máxima 0,84.
Oro: tres etiquetadores a ciegas con ids opacos y un **segundo etiquetado ciego completo** (no una muestra del 10 %):
acuerdo 299/301; los 2 desacuerdos, adjudicados. 301 filas, SHA-256 `7ffb35a3…f93a`. Regla: DEV-C no se mira ni se
itera; se corre sólo para confirmar un producto candidato antes de la ventana oficial (F5). Queda en la lista de
exclusión de todo entrenamiento futuro.

## D27. CAL: sesgo por decisión sobre la distribución del propio decisor (prerregistro, 2026-09-28 ~03:55)
Fuente: Batch Calibration (arXiv 2309.17249) y el análisis de fallos de DEV-A (el decisor pregunta donde las reglas
dicen límite). En la misma pasada se lee la distribución del modelo en el primer token del valor de `decision`
(log-probs sin gramática, 20 alternativas); se suma un sesgo por decisión y, si la elegida cambia, el turno se decodifica
otra vez con sólo esa decisión permitida (una acción forzada exige al menos una operación). Ajuste en DEV-A aislado
con veto a más acciones inventadas: meseta estable en preguntar −0,75, charla −0,25, límite +1,0 (acción 0);
`full3` aislado 234 → 244/260 (sueltos 109 → 118/125), inventadas 7 → 5, 10 arreglados y 0 rotos. Sesgos fijados
antes de ver DEV-B. Entra con D19 (DEV-B aislado sin bajar, sin más inventadas) y después D12 integrado (DEV-B,
capa A ≥ 96,0, reserva sin bajar, 742 revisadas: el riesgo es un límite falso a una orden del dueño).

**Resultado (04:05): retirado.** DEV-B aislado con los sesgos prerregistrados 227 → 226 (1 arreglado, 2 rotos;
sueltos 105 → 104), inventadas 6 → 4. No cumple D19. Lo que CAL ganó en DEV-A (+10) no generaliza, como el few-shot:
los fallos restantes de DEV-B no son de calibración de una clase. No se prueba otra combinación de sesgos (sería
iterar sobre DEV-B).

## D28. RPO ronda 2 retirada: el paso ×10 desplaza el decisor en todas direcciones (2026-09-28 05:47)
Ronda 2 (lr 5·10⁻⁵, 518 pares auditados, 1 época; relanzada a las 04:15 sin los 36 pares de control de ≈6 000 tokens
que desbordaban la VRAM de redpc). Entrenamiento con margen creciente (0,8 → 3,6) y deriva 3,6 frente a 0,3 de la
ronda 1. Aislado, mismo entorno que `full3m22`: DEV-A 234 → 210/260 (5 arreglados, 29 rotos: acciones → charla o
límite, límites → pregunta), DEV-B 225 → 208/253 (sueltos 104 → 89). **Retirado.** Lección: entre 5·10⁻⁶ (no mueve)
y 5·10⁻⁵ (rompe); un reintento sería un paso intermedio con β mayor para contener la deriva, y sólo después de agotar
los lectores y guardas (prioridad del dueño del 28-09).

## D29. Lectores y guardas (prioridad del dueño del 28-09): M32–M36, revisados antes de medir (2026-09-28 07:30)
El análisis por etapa mostró que en DEV-B la mayor pérdida frente al decisor aislado son turnos acertados que fallan al
redactar (la guarda rechaza todos los borradores) y que en la reserva los lectores ganan en neto salvo en casos
concretos. De ahí cinco estrechamientos, cada uno sobre un camino distinto:
- **M33** idioma de una redacción que lo nombra («escríbeme un mensaje en inglés…») = idioma de la respuesta, desde
  la lectura del pedido (`semantic/request._WRITING_REQUEST`); una pregunta sobre palabras no cuenta.
- **M35** guardas de redacción: lo que BAXY respondió o preguntó *a la persona* («te respondí», «respondí a tu
  mensaje») es conversación, no efecto; con «le», destinatario o canal sigue siendo efecto. En una presentación, los
  números que trae el pedido se pueden decir, pero nunca una fecha, edad o versión de BAXY.
- **M34** `overheard_speech` sólo si nada va dirigido a BAXY: vocativo, cortesía en un extremo, pregunta que empieza
  por palabra interrogativa, deseo al oyente u orden cerrada al inicio. La narración («como te decía…») sigue ajena.
- **M32** junto a la colección propia sólo un género nombrado dice qué poner («play my rock playlist»); los
  calificativos («mis preferidas», «de siempre») siguen preguntando.
- **M36** el acuse de una restricción nunca habla de BAXY en tercera persona (prompt).
Revisión independiente (REV2) antes de medir: M35a tal cual dejaba pasar efectos inventados («Respondí el correo de
tu jefe»), M35b orígenes inventados, M33 no se activaba en su propio ejemplo y M34 volvía dirigidas narraciones
ajenas; todo corregido con sus contraejemplos como pruebas. La primera medida de M33+M35 (m40) se detuvo por eso.
**Protocolo:** como cada mecanismo toca un camino distinto, se miden juntos (m41: DEV-A, DEV-B, capa A, 742, reserva)
y cada arreglo o rotura se atribuye por el camino que decidió el turno; un mecanismo con una rotura atribuida se
retira solo. Confirmación en DEV-C (base 645217a7 frente al candidato).
