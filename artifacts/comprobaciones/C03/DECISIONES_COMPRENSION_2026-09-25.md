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

## D30. RPO ronda 3 retirada; se cierra la vía de preferencias sobre `full3` (2026-09-28 10:02)
Ronda 3: paso intermedio (lr 1,5·10⁻⁵), β 0,3 para contener la deriva, 749 pares (los 517 de la ronda 2 sin la
coincidencia con DEV-C + 232 nuevos auditados: fragmentos pelados y preguntas sobre la conversación). Deriva final
0,97 (ronda 2: 3,6). Aislado, mismo entorno que `full3m22`: DEV-A 234 → 230 (3 arreglados, 7 rotos, sobre todo
acciones → pregunta), DEV-B 225 → 219 (sueltos 104 → 89 en la ronda 2, → 99 en la 3). **Retirada.**
Tres rondas (5·10⁻⁶ sin efecto; 5·10⁻⁵ rompe; 1,5·10⁻⁵ con β 0,3 retrocede): con estos pares, la etapa de
preferencias no mejora a `full3`. Se cierra esta vía en la fase; `full3` sigue siendo el decisor del producto.

## D31. Se corre el FINAL (F6), una sola vez (2026-09-28 11:30)
Por qué ahora: tras `full3` ninguna palanca del decisor mejora el ciego (SFT `full4`/`full5`, few-shot, CAL, tres
rondas de preferencias, cuantización); los lectores y guardas quedaron estrechados y confirmados en DEV-C (246/301,
0 rotos); en la app real se arreglaron las causas de fallo que se repetían (M37–M41 y el bloqueo de la captura de la
ventana activa, a7f528ec). Lo que falla ahora es disperso, una causa por turno. El goal (§8) prevé informar un
resultado entre 80 y 85 % como parcial con la causa medida; no hay otra ronda sobre este FINAL.
Protocolo (el ensayado en DEV-A, `scratchpad/cn/window_run.sh`): producto en a7f528ec+ con `full3`, app real con el
conductor (misma admisión, turno y publicación que la ventana), ventana guardia que mantiene VS Code a salvo, volumen,
silencio y brillo del dueño leídos antes y devueltos después, un «cancel» antes de cada conversación nueva,
auditorías de turno, traza y redacción. Puntuación con `comprension_eval score` sobre los registros de
`comprension_window records`; revisión turno a turno (inventado, ⚠, bien) por un subagente que no escribió ni arregló
nada, con la rúbrica de la meta. SHA-256 del FINAL verificado antes de correr: `e05cf27e…d993` (202 turnos).
Referencia en la app real: DEV-A 80,8 % (sueltos 83,2 %, seguimientos 73,5 %, 3,5 % de turnos con fallo de redacción).

## D32. Búsqueda: automática, sin claves, no comercial por ahora (dueño, 2026-09-28 ~15:00)
Respuestas del dueño (paso 2 del goal v3): «ni yo ni los usuarios deberíamos poner nada en la app, sólo debería
funcionar» → ninguna API que pida cuenta o clave del dueño o de la persona; el producto no es comercial por ahora
(los términos «no comercial» de fuentes abiertas valen hoy y se revisan si cambia); si no hay fuente, BAXY lo dice y
ofrece abrir el navegador; las peticiones a Wikimedia se identifican con la URL del repositorio de GitHub
(`https://github.com/REDSOULTM/baxy-assistant`). Vía elegida (R6): APIs abiertas por dominio (Wikipedia REST es→en,
Wikidata, Open-Meteo que ya se usa, Frankfurter para divisas, RSS/GDELT para noticias) y, para lo general, la
búsqueda hecha por el navegador del propio usuario a ritmo humano en vez de peticiones HTTP sueltas; sólo sale la
consulta. La medida de búsqueda va aparte hasta que la fuente funcione.

## D33. Argumentos en la salida del decisor (paso 3, prerregistro 2026-09-28 ~15:10)
Experimento aislado en DEV-A con `full3` sin reentrenar: el esquema lleva `arguments` y cada operación del catálogo
su firma de campos (sin identificadores). Decisión 234 → 237/260, estricta 185 → 188; en las 57 acciones con dato
de oro, el dato está en los argumentos del decisor en 55 (fallan `task.delete` con la etiqueta traducida y
`file.open` sin el nombre). En el FINAL gastado (ahora desarrollo) 12 fallos son acciones bien decididas que el paso
de argumentos repreguntó. Mecanismo M42: el decisor devuelve los argumentos; el paso de argumentos los usa como
datos ya dados (anclados en lo dicho: un valor que no aparece en el mensaje, la conversación o la reescritura no
entra; las horas pasan por `temporal`, nunca el ISO del modelo) y sólo pregunta lo que falte.
Regla: se adopta si en DEV-A (app real) las repreguntas de datos dados bajan y no hay rotos atribuidos; se confirma
en DEV-C (mente) sin bajar de 246/301; latencia p50 del decisor + ≤ 0,4 s.

## D34. FINAL-2 y DEV-D sellados (paso 1 del goal v3, 2026-09-28 ~14:40)
Método de DEV-C: particiones de validación/test públicas (MASSIVE val+test, MTOP test+eval, CLINC test+val, ilenia,
CSTOP eval+test, PRESTO test, SGD test, oasst2-es validación), exclusión por igualdad, hashes y trigramas ≥ 0,85 contra
todo lo visto (DEV-A/B/C, FINAL, pares, ventanas, cien, scratchpads; DEV-D también contra FINAL-2), auditoría
independiente con 0 violaciones; conversaciones de sala limpia escritas aparte. Oro: 3 etiquetadores por conjunto
(lotes opacos), auditoría ciega completa por otros 2, adjudicador para los desacuerdos.
- **FINAL-2**: 338 turnos (125 sueltos + 127 de 38 conversaciones públicas + 86 escritos), acuerdo ciego 337/338,
  1 adjudicado. SHA-256 `0f497ea2e148766e9bb5f68b08059f4d29f196cd376210e379347409d92dd312`. Se corre UNA vez al cierre
  (paso 9), en la app real con revisor independiente. Nota de honestidad: el informe del adjudicador mostró a la raíz
  el texto de un turno (LF2-0028:t4, una confirmación «Yes, that's the one…»); ningún mecanismo se ajusta sobre él.
- **DEV-D**: 332 turnos (125 + 125 de 37 conversaciones + 82 escritos), acuerdo 331/332, 1 adjudicado. SHA-256
  `7c91c653395dad307e8c825bd4465c200166240b215b367ee895dee038575017`. Conjunto de iteración (se miran sus fallos).
- El FINAL gastado (`e05cf27e…d993`) pasa a desarrollo. Todo dato de entrenamiento generado desde ahora excluye
  FINAL-2 y DEV-D por huellas.

## D35. Conocimiento honesto: atribución y lo que no se puede comprobar (dueño, 2026-09-28 ~15:50)
Tras R8 (`research/R8_conocimiento_honesto.md`): recetas, obras, cifras y datos con fecha se consultan antes de
afirmar (Wikibooks/Wikipedia/Wikidata; cálculos con un evaluador determinista con unidades). Respuestas del dueño:
- **Atribución (CC BY-SA)**: la respuesta no nombra la fuente (sigue la búsqueda invisible); en la app aparece un
  enlace discreto «fuente» debajo del mensaje, que no se lee en voz alta.
- **Sin fuente**: BAXY responde de memoria y lo avisa en corto («de memoria, puede no ser exacto»); no se calla.

## D36. v3a medido (9c56adbc: M42–M48, A7, búsqueda D32) — resultado mixto (2026-09-28 15:50)
| medida | base | v3a |
|---|---|---|
| FINAL gastado, mismo revisor | 108/202 | 99/202 (8 mejoran por decisión; 17 empeoran, 13 por búsqueda) |
| FINAL gastado, automática | 150/202 | 155/202 |
| ⚠ FINAL / DEV-A ventana | 10 / 9 | 2 / 6 |
| DEV-A ventana | 210/260 | 209/260 |
| DEV-C (sellado, mente) | 246/301 | 253/301 (11 arreglados, 4 rotos) |
| capa A | 96,4 % | 96,5 % |
| reserva MASSIVE | 86,4 % | 85,7 % (33 rotos, 22 por el decisor) |
| latencia p50 FINAL | 2,1 s | 3,1 s |
Lectura: la decisión y los argumentos mejoran (DEV-C +7, repreguntas 16 → 13); la búsqueda sin Bing retrocede (se
arregla en M51 con fuentes abiertas y veto de respuestas desde resultados que no tratan de lo preguntado); la latencia
no viene de los tokens del decisor (aislado +0,16 s: lat49 A 0,73 / B 0,89 / C 0,89 s; decisión 235/237/236) sino de
otra parte del turno: M49 aplica las variantes C (argumentos sólo al actuar) y mide los tiempos del decisor en la
auditoría. 742: 19 decisiones distintas a revisar.

## D37. v3b medido (49775ca4: v3a + M49–M52, M50, M51, último recurso de media) (2026-09-28 21:25)
| medida | base | v3a | v3b |
|---|---|---|---|
| FINAL gastado, revisor (mismo) | 108/202 | 99/202 | **126/202 = 62,4 %** |
| FINAL gastado, automática | 150 | 155 | 162 (80,2 %) |
| ⚠ / inventados / repreguntas (FINAL) | 10 / 2 / 16 | 2 / 5 / 13 | 2 / 3 / 12 |
| latencia p50 FINAL | 2,1 s | 3,1 s | 2,4 s |
| DEV-D ventana (base de iteración) | — | — | 256/332 = 77,1 %, ⚠ 3 |
| DEV-C (mente) | 246 | 253 | 252 |
| reserva | 86,4 % | 85,7 % | 85,7 % |
| capa A | 96,4 % | 96,5 % | 96,4 % |
| 742 | — | 19 distintas (revisadas) | 0 distintas frente a v3a |
Se adoptan M49 (latencia: argumentos sólo al actuar), M52 (hueco reservado sólo para el decisor; reprocesos del
catálogo 24 → 1 de 195, p90 3,58 → 2,09 s), M50 (código pedido), M51 (búsqueda pertinente con fuentes abiertas) y el
último recurso de media: el revisor sube 18 turnos sobre la base, sin retroceso en DEV-C, reserva, capa A ni 742.
Registro real: log:86 («hazme un triángulo con las estaciones del año») pasa de charla a web.search (a revisar).
Siguiente: v3c = + M53 (conocimiento consultado, D35), M54 (redacción fiel a las lecturas), M55 (colocar ventanas).

## D38. v3c medido (426d08e7: v3b + M53 conocimiento consultado, M54 redacción fiel a las lecturas, M55 ventanas) (2026-09-28 23:10)
| medida | v3b | v3c |
|---|---|---|
| FINAL gastado, revisor (mismo) | 126/202 | **128/202 = 63,4 %** (11 mejoran, 9 empeoran: 6 por la búsqueda general caída en esta red) |
| inventados / ⚠ / repreguntas | 3 / 2 / 12 | 2 / 3 / 11 |
| DEV-D ventana | 256/332 | 256/332 |
| DEV-C (mente) | 252/301 | 250/301 (2 rotos) |
| reserva | 85,7 % | 85,6 % (2 rotos) |
| capa A / 742 | 96,4 % / = | 96,4 % / 0 distintas |
| VRAM BAXY (pico en la app) | — | ≈ 4 042 MiB (meta ≤ 3 800) |
Se adoptan M53 (recetas, argumentos y rankings consultados en Wikimedia; «de memoria, puede no ser exacto» sin
fuente; cálculo con unidades; enlace «fuente»), M54 y M55. Los retrocesos medidos son de la búsqueda general
(DuckDuckGo vuelve a dar captcha en esta red) y de lectores que M56 corrige (el SQL mandado a la web, «latest song» como
ranking, lugares de otra ciudad, colocar ventanas cuando una app no está abierta). Paso 7: M57 permite medir 2 huecos.

## D39. «Cancela las alarmas» en plural: todas, confirmando (dueño, 2026-09-29 ~00:10)
Sustituye la rama plural de la regla de uso real del 24-09 (que preguntaba «¿Qué alarma deseas cancelar?» y el revisor
contaba como repregunta, F-s040): BAXY lee las alarmas pendientes y pregunta con la lista («Tienes 3 alarmas (7:00,
8:30 y 12:00). ¿Las cancelo todas?»); cancela sólo si la persona dice que sí; con una sola la nombra y confirma; sin
ninguna, lo dice.

## D40. v3d medido (bb1ab315: v3c + M56) y paso 7 con 2 huecos (2026-09-29 00:10)
FINAL gastado, mismo revisor: **133/202 = 65,8 %** (v3c 128; +10/−5), 1 inventado, ⚠ 3, 12 repreguntas, búsqueda
caída 1 (v3c 17). Automática 162/202. DEV-D con 2 huecos (M57): 260/332 (v3c 256) pero ⚠ 8 (2,4 %) y el pico de VRAM
sólo baja 160 MiB (BAXY ≈ 3 750–3 880 MiB): 2 huecos no se adopta. Se mide KV q4_0 con 3 huecos (M59).

## D41. Paso 7 (VRAM): caché V en q4_0, K en q8_0, 3 huecos × 12 288 (2026-09-29 ~04:10)
| variante | servidor (matriz) | calidad (sobre v3d, mente) |
|---|---|---|
| K q8 / V q8, 3 huecos (antes) | 3 724 MiB | referencia: reserva 85,7 % |
| 2 huecos (M57) | ≈ 3 436 | DEV-D ventana 260 (+4) pero ⚠ 8 (2,4 %); pico real sólo −160 MiB |
| K q4 / V q4 | 3 441 | 742 =; reserva 85,5 % (+12/−19, «por favor apaga» → system.power) |
| **K q8 / V q4 (M59)** | **3 440** | 742 un cambio (H0271 pregunta qué componente); reserva 85,6 % (+7/−11, ninguno peligroso) |
Con V en q4 el pico de BAXY en la app debería quedar ≈ 3,74–3,77 GB (se mide en v3e con muestreo cada 5 s). Además:
el literal «No lo encontré.» que A7 dejó en la App se quita (censo de prosa visible fija en cero).
**Corrección (05:10):** K q8 / V q4 no tiene núcleo rápido de flash attention para tipos mixtos en este llama.cpp:
decisiones 2,5× más lentas (reserva p50 0,91 → 2,34 s) y la corrida v3e en la app agotó tiempos (descartada). M59 se
revierte (V sigue a K). K+V q4 es rápido pero lleva «por favor apaga» a system.power, que va sin confirmación: descartado.

## D42. v3e2 medido (fa35fcba: v3d + M58, D39, M60, censo; KV q8) (2026-09-29 05:15)
FINAL gastado en la app real, mismo revisor: **146/202 = 72,3 %** (v3d 133; +15/−2), automática 165/202 = 81,7 %,
2 inventados (s040 cuenta mal las alarmas; w13-t2 cuenta de litros desde un precio de tanque), ⚠ 1 (0,5 %), repreguntas
7 (v3d 12), búsqueda caída 0, latencia p50 2,47 s. VRAM medida por proceso (contadores de Windows): pico 3 876 MiB, todo
llama-server (App y mente sin GPU) → 76 MiB sobre la meta; M61 baja el contexto por hueco a 10 240.
Quedan 56: búsqueda 14 (lo personal a la web s014/s034/s048, resultados ajenos), argumentos 10, límites 9, redacción 8,
conocimiento 8, otros 7. M62 (mecanismos) en curso; límites y lo personal van al decisor (full6, P2).

## D43. Paso 7 cumplido: contexto por hueco 10 240 (M61) (2026-09-29 07:40)
Medido por proceso en la app real (contadores de Windows, App + mente + llama-server): con 3 × 10 240 el pico de BAXY es
**3 778 MiB** (con 3 × 12 288 era 3 876–3 908). Sin retroceso: DEV-D ventana 263/332 (v3e2 267; los 4 de diferencia son
titulares, Spotify y una búsqueda, contenido que cambia con la hora, ninguno de contexto), 742 y registro real sin
cambios, reserva 85,7 % (+2/−3), latencia de decisión p50 0,90 s. Se adopta. El margen es de 22 MiB: cualquier cambio de
modelo, adaptador o contexto vuelve a medirse por proceso (scratchpad/cn/vram_procs.ps1).

## D44. v3f medido (96cbee8e: v3e2 + M61 + M62) (2026-09-29 08:20)
FINAL gastado en la app real, mismo revisor: **149/202 = 73,8 %** (v3e2 146; +9/−5), **0 inventados**, ⚠ 2 (1,0 %),
repreguntas 7, búsqueda caída 0, automática 164/202, VRAM por proceso 3 750 MiB. Quedan 53: búsqueda 13 (lo personal
a la web s014/s034/s048, resultados ajenos, Polvorista mal anclada), argumentos 11, límites 9, conocimiento 8, otros 9,
redacción 3. Siguiente: M63 (la App exige «08:00» literal y veta «8:00», F-s019; «llovizna … 0 %» contradictorio;
ancla de la Plaza del Polvorista) y el decisor (full6 con argumentos; P1/P2) para límites, lo personal y repreguntas.

## D45. Regresión del guion y el held-out; M64 y M65 (2026-09-29 ~10:30)
Guion del dueño y held-out en la app real sobre 0ef2d86b: 42/60 (+7 por revisar) y 25/30 (+1), frente a 48/60 y
28/30 en conv-m35 (b73137f4). Causa común de lo grave: M42/M49 cambiaron el prompt del decisor (firmas de campos,
formato con argumentos) y el LoRA `full3` se entrenó con el anterior; en contexto decide distinto: «Perfecto muy bien»
→ abrió Steam, «Di la palabra "algo"» → escribió en la ventana activa, y la guarda M19 tomó «Cierra» por un objeto no
dicho («Cerrá» antes). M65 añade guardas generales después del decisor (una reacción social nunca actúa; escribir en el
PC exige un verbo de escribir), arregla la raíz del verbo en M19 (diptongos) y saca las opiniones y reseñas de la
enciclopedia. M64: la reescritura del decisor no puede introducir números, unidades, fechas, horas ni nombres no dichos
(20/20 marcadas en la revisión eran introducciones reales) y «no lo encontré» nombra lo buscado. `full6` (entrenado con
el prompt nuevo y argumentos) debe quitar la deriva de raíz; hasta entonces las guardas quedan.

## D46. `full6` rechazado (2026-09-29 ~13:10)
`full6` = LoRA r16 bf16, 1 época sobre P0 (2 103 respuestas con argumentos anidados por operación, prompt nuevo), en
redpc. Aislado en DEV-A con el prompt de la app: decisión **227/260 frente a 236–237 de `full3`** (arreglados 4, rotos
14, McNemar p = 0,03), más aclaraciones (35 → 42). Con el esquema plano de la app (M49) `full6` emitía un escalar por
operación (`{"app.open": 1}`) y fallaba argumentos (42/57); con un esquema anidado igual al de su entrenamiento los
argumentos son **53/57 frente a 54/57** de `full3`, así que la caída de argumentos era del formato, no del modelo. La
de decisión sigue: no cumple la regla (decisión ≥ `full3`, argumentos ≥ 55/57, ninguna clase −2 pts). Se queda `full3`
con las guardas M64/M65. El siguiente LoRA se entrena con el formato de argumentos plano que pide la app (o la app pasa
al anidado, medido igual), con P0 + P1 + P2 y cuotas por clase para no perder decisión.

## D47. DEV-D con revisor independiente: 64 %, no 80 % (2026-09-29 ~17:40)
Corrección: las cifras de DEV-D en ventana citadas hasta ahora (v3e2/v3f 267/332 = 80,4 %) eran la puntuación
**automática** (decisión + argumentos), no la del revisor. El mismo revisor independiente del FINAL revisó DEV-D por
primera vez: **v3l (a017d6fc, M67–M73) 212/332 = 63,9 %**; con el mismo criterio v3f 215/332 = 64,8 % (−3, dentro del
ruido; 5 turnos de v3l cayeron porque el navegador del producto no respondió). Inventados 11 (v3f 8), ⚠ 7 = 2,1 %
(3 por el veto de «could not be reached», M74), repreguntas de datos dados 15. No-ok por causa: argumentos o
repregunta 31, búsqueda 27, límites o alcance 19, otros 16, redacción 14, conocimiento o código 13.
En paralelo, el guion del dueño sube a 56/60 y el held-out a 28/30 (v3k), cien 98/100: lo arreglado por M64–M74 son
los casos del dueño; en DEV-D (conversaciones escritas y corpus públicos) la distancia a la meta de FINAL-2 (≥ 85 %)
sigue siendo ≈ 21 puntos. Siguiente: tres frentes con mecanismos generales (repreguntas/lugar por defecto/jerga,
informes de búsqueda que inventan o dicen «no encontré» con el dato leído, límites falsos y fechas fuera de alcance)
y el decisor (full7, full8).

## D48. DEV-D v3m: 241/332 = 72,6 % con revisor (d946de8b = M74–M78) (2026-09-29 ~20:10)
Mismo revisor independiente y criterio que D47: **v3m 241/332 = 72,6 %** (v3l 212, v3f 215): arreglados 36, rotos 7.
Inventados 8 (11), ⚠ 4 = 1,2 % (7), repreguntas de datos dados 6 (15). Automática 270/332 = 81,3 % (v3l 264), VRAM
pico por proceso 3 784 MiB, p50 decisión 2,22 s. No-ok por causa: argumentos o repregunta 19 (31), redacción 19 (14),
búsqueda 16 (27), conocimiento o código 13 (13), límite o alcance 12 (19), otros 12 (16). Rotos: s007 ⚠, s047 frase
rota, s104 repregunta hora teniendo «18:00», s125 vencidos→retiros, p19-t2 «no encontré» con el reparto leído, p27-t4
incoherente, w19-t4 jerga de fallo. Siguiente: redacción (idioma de la conversación, dato pedido y no el de ahora,
frases rotas), argumentos residuales (task.update parcial, hora con parte del día pasada), búsqueda y conocimiento.

## D49. `full7` rechazado; la causa común con `full6` son las parejas mínimas; `full8` → `full9` (2026-09-30 13:30)
`full7` (P0 sólo con T1–T21 = datos de `full3` con argumentos; 3 170) aislado en DEV-A con el esquema anidado:
decisión **227/260** (igual que `full6`; `full3` 237), arreglados 9, rotos 16, argumentos 49/52. Quitar T22–T27 no
lo arregló. Los rotos que comparten `full6` y `full7` y no tiene `full3`: «Dime el pronóstico», «I need weather info
now», «Cancela mi temporizador», «mutealo un toque» → clarify. Lo único de P0 que `full3` no tenía y enseña eso son
las **parejas mínimas** (una acción con el dato quitado → clarify, R7 §2.3): el modelo generaliza «falta un valor →
pregunta» a campos con valor por defecto. `full8` (P0 + públicas + T22–T27 con cuotas, con parejas y 11 % de clarify)
murió a la 01:10 en el ejemplo 1 600 (redpc se suspendió) y no se relanza tal cual: **`full9`** = los mismos datos sin
parejas y con clarify en 6,1 % (como `full3`), 4 587 ejemplos, lanzado 13:25 con un seguro de no-suspensión sólo mientras
entrena (SetThreadExecutionState; sin tocar la configuración de energía). Regla igual: decisión ≥ 237, argumentos
≥ 55/57, ninguna clase −2 pts, luego integrado.

## D50. DEV-D v3o: 261/332 = 78,6 % con revisor (5761e1ab = M79–M82) (2026-09-30 ~15:20)
Mismo revisor y criterio: **v3o 261/332 = 78,6 %** (v3m 241, v3l 212): arreglados 26, rotos 6. Inventados 3 (8),
⚠ 5 = 1,5 % (4), repreguntas de datos dados 1 (6). Automática 273/332 = 82,2 %; VRAM pico por proceso 3 790 MiB;
p50 decisión 2,15 s. El aislamiento de alarmas por raíz de datos (M80) funciona en la app. No-ok por causa: búsqueda 15,
argumentos 14, límite o alcance 12, conocimiento o código 10, redacción 10, otros 10. Rotos: p24-t2 repregunta,
p27-t1 recomendación sin título, p31-t2 contradicción, p35-t2 ⚠, w08-t2 partido ya pasado como próximo, w08-t3
repregunta la fecha recién dada. Batería previa (d946de8b): 742 sin cambios, capa A 96,5 %, reserva 85,8 %, DEV-C 252.
Distancia a la meta de FINAL-2 (≥ 85 %): ≈ 6,4 puntos en DEV-D.

## D51. DEV-D v3r: 284/332 = 85,5 % con revisor (50cee2c6 = M83–M86) (2026-09-30 ~18:00)
Mismo revisor y criterio: **v3r 284/332 = 85,5 %** (v3o 261, v3m 241, v3l 212): arreglados 32, rotos 9. Automática
286/332 = 86,1 % (+19/−6, McNemar p = 0,015), VRAM pico por proceso 3 754 MiB, p50 decisión 2,05 s. Inventados 3 (s111
distancia Barcelona–París de memoria y errónea; p12-t2 «five 24/7 stores» no leído; p24-t5 confirmación sin efecto),
⚠ 5 = 1,5 % (s001, s025, p23-t2, p24-t1, p29-t2: nuevos, en turnos tocados por M83/M85 → agente M87), repreguntas 1.
Conocimiento sin aviso errado: sal para la pasta, cucharaditas, gramos de harina. Rotos: p20-t2 servicio no reconoce
Palo Alto, p34-t3 vago, p37-t2 repregunta, w05-t3 sin el disco, w10-t4 YouTube sin sonar, w11-t5 Spotify tiempo agotado.
Estado frente a las metas de cierre: DEV-D revisor ≥ 85 % alcanzado en desarrollo; faltan ⚠ ≤ 1 %, 0 inventados,
automática ≥ 90 %, held-out ≥ 29/30 («cerralo», decisor → full9), reserva ≥ 88 %, cien 100/100 y Full. FINAL-2 no se
corre hasta que DEV-D sostenga las metas con margen.

## D52. DEV-D v3u: 283/332 = 85,2 % (30861483 = M87–M90); las cifras de memoria se cortan (2026-09-30 ~20:15)
Mismo revisor: **v3u 283/332 = 85,2 %** (v3r 284): arreglados 13, rotos 14. ⚠ **1 = 0,3 %** (v3r 5), repreguntas 1,
inventados 4 (s061 atribución a un artículo; s111, p29-t2, w01-t3 = cifras dichas de memoria y erróneas). Automática
290/332 = 87,3 %; VRAM 3 758 MiB. Las cantidades de cocina se buscan pero la redacción no usa lo leído (w01-t2 «a gusto»
con «10 g por litro» leído; w10-t2 sin gramos). Decisión de producto, compatible con D35 y el paso 6 del goal: la
respuesta de memoria con aviso (D35) queda para lo que no es una cifra; cuando lo pedido es una cantidad, distancia,
duración, fecha o recuento, se dice que no se encontró (paso 6: las cifras se buscan antes de afirmar; si no se puede,
se dice). Agentes M92 (memoria y cifras, cocina con lo leído) y M93 (rotos y redacción de v3u).

## D53 — 2026-10-01: escala y sopa de LoRA sin entrenar, retirada (regla prerregistrada)

Investigación R9 (con fuentes: WiSE-FT, Model soups, LoRA Soups) propuso escalar `full3` o promediarlo con `full1`/`full2`
sin reentrenar. Regla de entrada fijada antes de medir: DEV-A ≥ base + 2 y DEV-D ≥ base + 2, sin perder > 2 puntos en
ninguna clase, inventadas no peor, argumentos ≥ 55/57, latencia de generación ≤ base + 50 ms. Arnés aislado (variante C,
servidor nuevo por variante; el control V0a = V0b reproduce exacto 237/260 y 300/332). Resultados (DEV-A / DEV-D):
`full3`×0,8 237 / 304; ×1,2 231 / 298; `full3`+`full2` viva 233 / 298; tercios viva 234 / 306; fusionadas a rango 16
233 / 304 y 231 / 305 (la fusión no reproduce la sopa viva: `full1`–`full3` son casi ortogonales, 72–82 % de energía).
Ninguna cumple → se queda `full3`×1,0 y se cierra la vía. También descartado el catálogo reducido por familias (etapa 0:
cobertura 0,904 con el diseño prerregistrado a ≤ 80 operaciones y +0,8 s por turno). Ficheros en el scratchpad
`cn/soup/exp1_table.md` y `cn/catred/ETAPA0.md`.

## D54 — 2026-10-01: auditoría de la reserva (decisión pendiente del dueño)

Auditoría independiente de los 346 fallos de la reserva (v3w, 2 411/2 757 = 87,5 %): A 126 BAXY se equivoca, B 114 la
especificación automática (derivada de MASSIVE) está mal según las reglas del dueño, C 87 ambiguos, D 19 ininteligibles.
Con B corregido sería 91,6 %. No se cambian las etiquetas sin el dueño (no relajar pruebas); los A se atacan en código
(M97: +19/−0 en réplica sin GPU).

## D55 — 2026-10-01: DEV-E, medidor imparcial antes del FINAL-2

DEV-D sube (automática 80 → 91 %, revisor 64 → 89 %) pero DEV-C, sellado y leído sólo en agregado, no se mueve (252 → 251/301).
Para no gastar el FINAL-2 a ciegas se crea DEV-E: 299 turnos (124 sueltos + 45 conversaciones), sala limpia con cinco
escritores independientes (ocho hablas), doble etiquetado ciego (acuerdo 300/300 con la regla de DEV-D; lista exacta 90,3 %;
33 dudosos adjudicados, 1 eliminado), exclusión contra los conjuntos protegidos y los datos de entrenamiento (73 textos
reescritos, segunda pasada 0). SHA-256 `1a8b0f3f…f8020`. Regla: DEV-E sólo mide; se leen sus agregados (automática y
cifra del revisor), nunca sus filas ni sus fallos para arreglar. Si DEV-E queda lejos de las metas, el FINAL-2 no se corre
todavía. Las huellas de exclusión de los datos de entrenamiento deben incluir DEV-E antes de generar más datos.

## D56 — 2026-10-01: full9 rechazado; continuar full3 en vez de reentrenar desde cero

`full9` (p0v5 + públicas con cuota + T22–T27, sin parejas mínimas) medido aislado con la regla de exp1: DEV-A decisión 228
frente a 237 de `full3` (esquema anidado y esquema del producto, igual), DEV-D 290 frente a 300, búsqueda y aclaración peores;
argumentos 50/54. Las mezclas `full3`+`full9` tampoco cumplen la regla. Es el sexto reentrenamiento desde la base que decide
peor que `full3` (full4–full9). `full10` (la misma receta + 682 formas de sala limpia) se detuvo al empezar. Siguiente vía:
`full11a`, continuar el propio `full3` (su adaptador como punto de partida) con una pasada a lr 5e-5 sobre 1 200 filas de
sus datos originales (réplica, para no olvidar) y las 682 formas nuevas. Misma regla de entrada para adoptarlo.

## D57 — 2026-10-01: el decisor generaliza; la brecha está en el código que lo rodea

`full11a` (continuar `full3` con 1 200 filas propias + 682 formas nuevas, lr 5e-5) no cumple la regla: DEV-A 231 (−6),
DEV-D 300 (=). Para juzgar sin el sesgo de selección de `full3` (elegido por DEV-A/DEV-B) se midieron aislados los tres
decisores en DEV-E (sólo agregados) y DEV-F (iterable): `full3` 293/299 y 270/280, `full11a` 293 y 267, `full9` 290 y 263.
`full3` se queda. Hallazgo: el decisor solo acierta la decisión en el 98 % de DEV-E y el 96 % de DEV-F, pero el producto
en la app real sólo en el 85 % y el 87 %. La app pierde decisiones correctas del decisor (DEV-E agregado: camino del
decisor 24, lectores de efectos 7, recuperación 6, conversación explícita 4, aclaración explícita 2). La brecha de
generalización (DEV-D 92 % frente a DEV-E/F 85–87 %) es del código alrededor del decisor —lectores y reglas afinados con
frases vistas—, no del modelo. Siguiente paso: que el producto confíe en el decisor (M112) y que los argumentos del decisor
lleguen intactos (M110, M111), medido en DEV-F y confirmado en DEV-E por agregados.

## D58 — 2026-10-01 (dueño): BAXY ayuda al decisor, nunca es un lastre

Regla del dueño: el código de BAXY alrededor del decisor no puede empeorar lo que el modelo acierta; sólo puede ayudarle en
sus errores. Métrica fija desde ahora en cada medida: «lastre» = turnos en que el decisor aislado (mismo prompt y
historial) acierta y el producto falla, en decisión y en argumentos; meta 0. Cada lector, guarda o corrección lleva su
cuenta de arreglos frente a roturas contra el decisor aislado (DEV-D, DEV-F, reserva; DEV-E sólo en agregado) y se estrecha
a los errores del modelo o se retira si resta. Excepciones sólo explícitas: seguridad (VS Code, política de riesgo, envíos
reales) y reglas del dueño ya escritas (D35 recetas y cifras buscadas, volumen relativo sin cantidad pregunta, etc.).
Nota de honestidad: el 98 % del decisor es sólo la decisión en DEV-E aislado; la puntuación del producto (decisión,
argumentos y ejecución) es 76,6 % en DEV-E, así que la meta del FINAL-2 (≥ 90 %) no está cumplida.

## D59 — 2026-10-02 (dueño): respuestas a las decisiones pendientes

1. **BAXY se adapta al PC.** WhatsApp y Discord están instalados y con sesión: si un pedido de mensaje los encuentra
   cerrados, BAXY los abre para dejar el borrador (nunca envía sin confirmación). Después de cada prueba se cierra lo que la
   prueba abrió; si falta RAM se puede cerrar lo necesario (autorización 2026-09-17). Outlook no está configurado: BAXY lo dice.
2. **Reserva:** se corrigen las 114 etiquetas de la clase B de la auditoría (D54), con registro de cada cambio y su motivo;
   la versión anterior se conserva y las cifras se dan con ambas mientras dure la transición.
3. **«baja las luces» sin habitación:** BAXY controla el notebook, no la casa → límite («no controlo las luces de tu casa»).
4. **Playlist por propósito** («pon mi playlist de gym», «party songs»): buscar y reproducir música para ese propósito.
5. **Lista nueva sin ítems:** se crea vacía y se ofrece agregar cosas.
6. **«Avísame cuando haya noticias de X»:** límite honesto (no vigila) y ofrecer buscar ahora.
7. **Turno no entendido sin pregunta válida:** una pregunta corta con las palabras de la persona (no un «no pude entender» fijo).
8. **Análisis de empresas reales (FODA…):** consultar primero la empresa y escribir con lo leído (+1–2 s).

**D59, adenda (dueño, 2026-10-02):** Outlook no se configura en este PC. BAXY conserva la capacidad de correo; cuando el
cliente no está configurado lo dice con honestidad (nombrando lo que se intentó, M116) y eso cuenta como conducta correcta.

## D60 — 2026-10-02 (dueño): las cosas se abren en el navegador del usuario

Lo web (navegar, YouTube, Disney+, HBO, Netflix…) se abre en el navegador predeterminado del usuario —en este PC, Opera, con
sus sesiones iniciadas—, no en el perfil Edge propio del producto, y BAXY debe poder usarlo (verificar lo que suena y
controlarlo). Agente M122: historial de cómo lo hacían BAXYs anteriores, diseño (UserChoice, ShellExecute, SMTC/UIA para
verificar sin tomar el perfil), implementación; Edge queda sólo como respaldo explícito. Nunca reiniciar ni cerrar el
navegador del usuario, ni leer sus datos de navegación.

## D61. Hora sin am/pm, app ausente y recetas/cifras (dueño, 2026-10-02 ~12:00)
Tres choques entre literales revisados y etiquetas de conjuntos (M126), resueltos por el dueño:
1. **«Pon una alarma a las 7» sin mañana/tarde → la próxima 7 que venga**, sin preguntar (si son las 15:00, las
   19:00). Sustituye a lo revisado en H0036, H0197, H0222, H0234, H0473 y H0119 (preguntaban am/pm); las etiquetas
   v2 de la reserva ya pedían actuar.
2. **«Abre Obsidian» con la app no instalada → comprobar y decir que no está instalada** (`app.installed`), como
   lo revisado (H0289, H0558, H0249, H0503, H0691). El oro de DEV-F y de la reserva v2 acepta esa respuesta.
3. **Recetas y cifras → buscar primero (D35 se mantiene).** En los conjuntos DEV, donde el oro dice responder de
   memoria y BAXY consultó por D35, ambas cuentan como correctas; se informan las dos cifras (oro original y D35).

## D62. v4j medido (main 62ec7c38: M124 regresiones v4i, M125 sin saludo en el decisor) (2026-10-02 12:10)
DEV-F 238/280 = 85,0 % (v4i 239; p50 2,60 s) · DEV-E 236/299 = 78,9 % (v4i 235; p50 2,55 s) · DEV-D 304/332 =
91,6 % (v4i 300; p50 1,99 s) · reserva v1 89,6 % / v2 93,6 % (= v4i, 0/0) · 742: 0 cambios frente a v4i · capa A
+2 (log:38 límite de leer chats, log:104 CV en la conversación) · guion 54/60 (+3 por revisar) · held-out 30/30 ·
DEV-C 253/301. A/B M125 (53 min GPU): ni los flags del servidor ni el saludo explican que el decisor de la App
escriba otra cosa (cambian ≤ 8 decisiones por conjunto, neto ≈ 0). M128: 11 de 19 de esas divergencias en F/D se
deben a turnos previos que fallaron en esta máquina (el historial vivido no trae el dato que el oro da por sabido).

## D61b. Hora sin mañana/tarde en un día nombrado (dueño, 2026-10-02 ~13:00)
M129 aplicó D61 al pie de la letra y «agendá una reunión el viernes a las 3» quedaba a las 03:00. Decisión del dueño:
en un día que la persona nombra (mañana, el viernes, una fecha), 1–6 es la tarde, 7–11 la mañana y 12 el mediodía;
hoy sigue D61 (la próxima vez que llega) y una hora ya pasada que rueda sola a mañana también. Lo dicho («de la
madrugada», «am», 24 h) manda siempre. Mecanismo M130 (`_canonical_due_utc`), integrado tras v4k.

## D63. v4k medido (main ad77e102: M126 lectores, M127 argumentos, M128 historial, M129 D61) (2026-10-02 15:50)
Oro original → con D61 (`score --d35 --accept`): DEV-F 238 → 242/280 = 86,4 % (p50 2,78 s) · DEV-E 239 → 246/299 =
82,3 % (p50 2,67 s; v4j 236 → 245) · DEV-D 305 → 309/332 = 93,1 % (p50 2,02 s) · reserva v1 89,9 % / v2 93,9 %
(+8/−0) · 742: sólo los 6 cambios de D61 · capa A sin cambios · DEV-C 257/301 = 85,4 % (v4j 253) · held-out 30/30 ·
guion 52/60 + 4 por revisar (t36 Steam «biblioteca» no encontrada: inestable conocido, en v4j bien) · VRAM pico 3 798
MiB. Lastre de decisión frente al decisor aislado: DEV-E 41 → 36 (11 cambiadas después, mayormente D35; 14 el decisor
de la App escribió otra cosa; 10 lectores de primer turno), DEV-F 20, DEV-D 12. Siguiente: M131 (lectores de primer
turno sin arreglos esperan al decisor) y M130 (D61b) a la ronda v4l.

## D64. v4l medido (main aa8c94a5: M130 D61b, M131 búsqueda de primer turno espera al decisor) (2026-10-02 19:05)
Con D61 (`--d35 --accept`): DEV-F 239/280 = 85,4 % (v4k 242; p50 2,83 s) · DEV-E 248/299 = 82,9 % (v4k 246; p50
2,60 s) · DEV-D 308/332 = 92,8 % (v4k 309; p50 2,00 s) · reserva 89,9 / 93,9 % (0/0) · 742 y capa A sin cambios ·
DEV-C 257/301 · held-out 30/30 · guion 49/60 + 7 por revisar (16, 17 y 54 pasan de bien a revisar con respuestas
correctas a la vista; Steam t36/t38/t42 falla en v4k y v4l: Steam arranca en frío porque cada corrida lo cierra) ·
VRAM 3 794 MiB · Full verde (pytest 22 427, Integración 4 020). Diferencias de ±3 entre rondas: se mide la varianza de
corrida a corrida con el mismo build (v4l2) antes de atribuirlas. Fallos de DEV-E (agregado): primer turno 150/169,
tras turno bien 98/111, tras turno fallido 12/19 — sin una causa dominante; 20 de 22 de argumentos también los falla el
decisor aislado.

## D65. Varianza de corrida a corrida y siguiente vía: full12 (2026-10-02 20:15)
Repetición con el mismo build (v4l2 frente a v4l): DEV-F +2/−1 turnos cambian de veredicto, DEV-E +2/−0, DEV-D 0/−3;
con D61: F 241 (v4l 239), E 248 (248), D 305 (308). Diferencias de ±3 entre rondas son ruido; DEV-E se estabiliza en
≈ 82,9 % con los mecanismos alrededor del decisor. Siguiente vía (paso 3 del plan): `full12` = continuar `full3`
entrenando sólo los tokens de los argumentos (la decisión fuera de la pérdida), lr bajo, datos de entrenamiento sin
solapamiento con evaluación. Regla prerregistrada: decisión ≥ full3 − 2 en DEV-F/D/E y argumentos ≥ full3 + 5 en F+D
sin bajar en E.

## D66. v4m medido (main afa40592: M133 app ausente D61.2, M134 redacciones sin final) (2026-10-03 00:50)
Con D61: DEV-F 241/280 = 86,1 % (p50 2,64 s) · DEV-E 250/299 = 83,6 % (p50 2,75 s) · DEV-D 306/332 = 92,2 % (p50
1,98 s) — dentro del ruido ±3 de v4l. Sin final: F 0 (2–3), D 1 (2), E 5/299 (5–6). Reserva 89,9 / 93,9 % · 742: sólo
H0406 → `app.installed` (D61.2) · capa A sin cambios · DEV-C 257/301 · held-out 30/30 · guion 52/60 + 4 por revisar
(Steam t36/t38/t42 sigue: M132 entra en v4n) · VRAM 3 796 MiB. full12: OOM en redpc a ~920/2 141 (23:08), reanudado
desde el ejemplo 800 a las 00:11. Incidente M132 (~22:30): en una prueba en vivo con el dueño usando el PC, el clic por
OCR pulsó «biblioteca» una vez en el panel de VS Code; M132 ata el clic a la ventana de la app abierta.

## D67. El lastre de seguimiento es del historial vivido; DEV-G para ver lo que falla en primer turno (2026-10-03 01:40)
1. **Corrida vivida** (full3 aislado, perfil app, sobre DEV-F/DEV-D con el historial que la App vivió en v4m en vez del
   del oro): el lastre de decisión cae de 14 a 1 en F y de 13 a 3 en D; el de argumentos, de 9 a 4 y de 1 a 1. Con el
   mismo historial, el decisor aislado falla donde falla el producto: el lastre de seguimiento no es código alrededor del
   decisor, sino turnos anteriores que en este PC salen distintos del oro (un PDF que no existe, una búsqueda sin la hora
   del partido, una oferta de bajar el brillo que no se hizo). Lastre de código real que queda en F/D: ≈ 5 turnos.
2. En DEV-E (agregado) el lastre de v4m es 42 = decisor en contexto, seguimiento 17 + primer turno 13; lectores
   explícitos de primer turno 8; conversación explícita 3; recuperación 1. Los 24 de primer turno no dependen del
   historial y F/D (iterados) casi no los tienen (≈ 2). Para verlos sin abrir DEV-E se crea **DEV-G**.
3. **DEV-G** (`sets/DEV-G.jsonl`, sha256 `796f828b…e222e`, 300 turnos: 125 sueltos + 45 conversaciones de 3–5 turnos,
   ocho hablas): mismo encargo de escritor que DEV-E y cadena de `build_f.py` (`dev_g/build_g.py`); cinco escritores de
   sala limpia de tres familias de modelos; reglas de oro de E más las del dueño D59–D61 (reglas 11–19); exclusión en
   tres rondas (91 → 2 → 0 coincidencias, cada texto reescrito por su escritor) con las huellas protegidas + las de E y F
   + `excl_extra_g.npz` (DEV-F y los datos de full12); doble etiquetado ciego (acuerdo compatible 300/300, conjunto
   idéntico 85,7 %); adjudicador ciego en 94 filas (1: 74, 2: 10, nueva: 10, 0 descartadas); el coordinador devolvió
   `ask` a dos recordatorios sin hora (X001, X006: la regla 11 trata la hora sin mañana/tarde, no la hora que falta; 3 de
   4 etiquetas lo aceptaban). Decisor aislado full3 en DEV-G: decisión 295/300, argumentos 167/179 (en E: 293/299). DEV-G
   es **iterable**; DEV-E sigue sólo como medida.
4. M135 (rama `opus/m135-borrado-inventado`): un informe de una operación que no borra no puede decir que algo se
   borró (F-w47-t2 «Se borró el borrador…», igual en v4i, v4k y v4m); entra en la ronda siguiente a v4n.

## D68. full12 rechazado por su regla prerregistrada; v4n medido (2026-10-03 04:00)
1. **full12** (full3 continuado entrenando sólo los tokens de los argumentos, lr 3e-5, 1 época, 2 141 ejemplos sin
   solapamiento; reanudado tras un OOM desde el ejemplo 800; GGUF sha256 `e815194e…`), medido con `full12/REGLA.md`
   (decisor aislado, perfil app, misma sesión que R0 = full3): decisión F 258/280 (full3 270), D 282/332 (301), E 283/299
   (293); argumentos F+D 217 (228), E 141/160 (146). Falla las dos partes de la regla: **rechazado, se queda full3**.
   Enmascarar la decisión en la pérdida no la protege (los pesos son compartidos) y tampoco mejora los argumentos. Es el
   séptimo adaptador (full4–full9, full11a, full12) que no supera a full3; no se reentrena mirando estos conjuntos.
2. **v4n** (main a4d067df: M132 clic atado a la app abierta, Steam en frío, PotPlayer), con D61: DEV-F 243/280 = 86,8 %
   (v4m 241; p50 2,58 s), DEV-E 250/299 = 83,6 % (= v4m; p50 2,71 s), DEV-D 306/332 = 92,2 % (= v4m; p50 1,93 s), todo
   dentro del ruido ±3. DEV-C 257/301 = 85,4 % (=). Guion **53/60** + 4 por revisar (v4m 52; meta 53 cumplida),
   held-out 30/30, cien-120 100/100 publicadas, 0 efectos de más (frente a cien-119 sólo cambian redacciones). El pytest
   completo de la cadena dio 56 fallos + 24 errores, todos 0xC0000142 (procesos hijo powershell/git que no arrancaron);
   los 80 repetidos pasan; Integración 4 031/4 031.

## D69. v4o: los arreglos hallados en DEV-G se generalizan en parte a DEV-E; DEV-H (2026-10-03 08:00)
1. **DEV-G en la App (v4n, main 7412b381)**: 243/300 = 81,0 % con D35 (DEV-E 83,6 %); decisor aislado 295/300; lastre 51
   (27 decisión + 24 argumentos), 28 de ellos en primer turno. A diferencia de F/D, con el historial vivido el lastre
   apenas baja (27 → 21): es código. Con el mismo prompt (prompt_n idéntico) el decisor de la App y el aislado discrepan
   en ≈ 4 turnos casi empatados (no invarianza por lote de llama.cpp); no se persigue.
2. Mecanismos sobre DEV-G (filas iterables; reglas de entrada: prueba con la fila real, variantes propias, casos que no
   cambian, familia C03 verde): **M135** veto de un borrado afirmado sin operación que borre; **M136** los argumentos del
   decisor llegan a los campos del esquema (clave por operación, prefijo «app» → appId, parte dicha de un nombre de app,
   all_known para la carpeta no dicha de una lectura, «he bajado» = Descargas); **M137** «X antes» de una hora dicha y la
   hora suelta movida con su parte del día; **M138** lectores de primer turno estrechados (pregunta antes del «?», «check
   si tengo internet», «donde anda mi compadre», borrador «diciendo que…», «pa las 7», «some X», «in spotify»; offline
   DEV-G +7 decisiones, D/F/reserva/742 sin cambios); **M139** una respuesta de conversación o de recuperación no promete
   un acto en el mundo («I will get a pepperoni pie delivered» → límite) y ocho redacciones sin final; arreglos de
   integración (sin igualdad de texto en el decisor; error que afirma el acto = missing_failure). Full verde (pytest
   22 603, Integración 4 060). main 0db83e48.
3. **v4o** (con D61): **DEV-G 269/300 = 89,7 %** (+28/−3; de los 3 rotos: un artefacto del registro, un historial vivido
   distinto y un «Can't» de un título → M140), **DEV-E 257/299 = 86,0 %** (v4n 250; +10/−5; lastre 42 → 37), DEV-F
   243/280 = 86,8 % (=), DEV-D 305/332 = 91,9 % (v4n 306). El 90 % de DEV-E exige 269 (+12).
4. Después de v4o, en integración: **M140** (título y artista observados por cualquier operación media.* no son un fallo
   dicho) y **M141** (los argumentos del decisor llegan a los pasos de los planes; el código que BAXY acaba de escribir
   va al archivo pedido). Pendiente de diseño: «pásame esta ventana a la izquierda» (la ventana del frente es la de BAXY)
   y note.update tras crear la nota (falta encadenar note.read → note.update en el Kernel).
5. **DEV-H** (`sets/DEV-H.jsonl`, sha256 `8b7e94ec…903ee`, 300 turnos, misma forma que DEV-E y DEV-G, regla 20 del
   dueño añadida: recordatorio sin hora acepta la operación o preguntar): 5 escritores de sala limpia, exclusión en tres
   rondas (91 → 1 → 0, incluidas las huellas de DEV-G), doble etiquetado ciego (acuerdo 300/300, conjunto idéntico
   83,3 %), adjudicador en 95 filas (1: 63, 2: 15, nueva: 15, unión: 2, 0 descartadas). Iterable; sirve para no seguir
   iterando sobre DEV-G ya mirado.

## D70. v4p y v4q: DEV-G y DEV-H suben, DEV-E se queda en 86 % (2026-10-03 14:45)
1. **v4p** (main 88c8e4b8: M140 título observado, M141 argumentos del decisor en planes y código a archivo, M142 pista
   «ya estaba abierta» impersonal), con D61: DEV-E 256/299 = 85,6 %, DEV-G 269/300, **DEV-H 258/300 = 86,0 %** (primera
   medida limpia: la de v4o corrió con un llama-server de una evaluación aislada al lado —carrera en `gpu.flag`— y se
   descartó), DEV-F 241, DEV-D 305; reserva 90,0 / 94,0 % (0/0), 742 sin cambios, DEV-C 255, held-out 30/30 (M142
   recuperó «abrí el bloc de notas»), guion 52/60 + 5 por revisar (t21 cierra Edge igual que en v4o con otra redacción;
   t42 Steam inestable).
2. **v4q** (main con M143 lectores de DEV-H —incluido el arreglo de seguridad «escríbeme en python…» que armaba un
   message.send— y M144 avisos en conversación: respuestas cortas a la pregunta de la hora, «half three», «la misma
   hora», D61b con la parte del día del decisor), Full verde (pytest 22 754, Integración 4 060): **DEV-H 276/300 = 92,0 %**
   (+21/−3), **DEV-G 270/300 = 90,0 %**, **DEV-E 257/299 = 86,0 %** (= v4o). Lo hallado en G y H no son las clases que
   fallan en E: tres rondas seguidas en 256–257.
3. En G y H, de 36 turnos con la decisión bien y los argumentos mal (v4p), ≈ 9 son del entorno de la corrida (ventanas
   de apps que el conjunto supone abiertas; alarmas de otras conversaciones a la misma hora), ≈ 5 del puntuador (un
   recordatorio puesto a la hora absoluta correcta frente a «30 min» en el oro) y el resto reales (la mitad ya en
   M143/M144). Dos huecos de producto detrás de lo que parecía entorno → **M145** («esta ventana» = la del frente para
   operaciones de ventana no destructivas; mover o cancelar el aviso que puso esta conversación aunque haya otros a la
   misma hora). Los ⚠ sin final de DEV-E oscilan 1–6 por ronda (meta ≤ 3); en G/F/D/H los que quedan son vetos de
   redacción sobre respuestas verdaderas → **M146**.

## D71. Decisiones del dueño (2026-10-03 ~18:45): lo hecho cuenta aunque se diga distinto; «ventana activa»
1. **Puntuación:** un turno cuenta como completo si BAXY hizo lo que había que hacer, aunque el dato quede dicho de otra
   forma («25-minute» = «25 minutos»; «media hora» = 30 minutos; «hora y media» = 90). Se implementa como equivalencias
   generales de forma en el puntuador (`comprension_eval`: guiones como espacios, duraciones habladas con su número de
   minutos), nunca como aceptación de un resultado distinto; se siguen informando la cifra estricta y la de D61.
2. **«La ventana activa» es la ventana donde la persona está actuando.** Con Opera delante y YouTube detrás, «cierra la
   ventana activa» cierra Opera, nunca YouTube. Cuando la persona escribe en BAXY, la ventana de BAXY queda delante pero
   no es la suya: la ventana activa es la que usaba justo antes (la siguiente en el orden de apilado que no sea de BAXY).
   Vale igual para «esta ventana» en acomodar, maximizar o minimizar (M145). Cerrar sigue pidiendo confirmación; un
   pronombre con antecedente («ciérralo» tras «abre X») sigue siendo X (M118); nunca VS Code por error (D17).

## D72. v4r y v4s; incidencia de sello de DEV-E (2026-10-03 21:30)
1. **v4r** (main a496b0a3: M145 ventana del frente y aviso propio, M146 vetos de redacción de más, M147 un nombre que busca
   un servicio va como lo escribió la persona): **DEV-E 262/299 = 87,6 %** (+4/−1; ⚠ 1/299), DEV-G 276/300 = 92,0 %, DEV-H
   281/300 = 93,7 %, DEV-F 243, DEV-D 305, held-out 30/30, guion 52/60 + 6 por revisar (t16/t17: YouTube devolvió otro
   vídeo; t21/t54 redacción; mismo comportamiento que v4q), reserva 89,9/94,0 % (0/0), 742 sin cambios, cien-124 100/100.
   El pytest de la primera cadena de v4r se detuvo por PID y se relanzó porque M147 entró en `integ/v3z` a mitad de
   pytest (regla nueva: no fusionar en integración mientras una cadena prueba sobre ella).
2. **v4s** (M148 «recuérdame eso» y cuentas de tiempo, M149 ventana activa = la de la persona, D71.2): **DEV-E 263/299 =
   88,0 %** (+1/0). En DEV-E quedan 15 turnos con la decisión bien y el dato mal (sólo cuentas): 8 sin argumentos (BAXY
   preguntó: 3 por el camino de lectores sin consultar al decisor, 5 por el decisor en contexto cuyos campos se
   descartaron) y 6 con otro dato verificado → **M150** (antes de preguntar, usar lo que el decisor escribió).
3. **Incidencia:** al buscar corridas, el agente de M150 imprimió por error con un glob una línea de
   `window/v4r-devE/RUN.jsonl` (un turno). Declaró no usarla; el coordinador no la vio. M150 se diseñó con los agregados
   de E citados arriba y filas de F/D/G/H. Se deja constancia por la regla de sello de DEV-E (D55).

## D73. M150 no era la causa; los finales vetados de task.list; DEV-I; M151–M153 (2026-10-04 04:00)
1. **v4t** (M150) dio DEV-E 256 (0 arreglados / 7 rotos frente a v4s, p = 0,016), con la búsqueda web caída en 9 turnos.
   **v4t2** (mismo build, búsqueda estable) dio 257 y **v4u** (M150 retirado, `integ/v3z` 5188260f; entre los builds de v4s
   y v4u sólo cambian pins y documentos) dio 256 frente a v4s: 0 / 7 otra vez. M150 se retiró con una atribución
   equivocada: la caída la tiene también el código de v4s. No se reintroduce a ciegas; su idea queda anotada.
2. **Causa de la oscilación, medida sólo con metadatos de DEV-E** (estado terminal, código de veto, bytes, claves; ningún
   texto): los turnos terminados `filtered: no_response` son 1 en v4s y 5 en v4u (4 task.list y 1 notification.schedule).
   En task.list, la guarda veta como `reversed_result` (3) o `task_title_not_named` (1) el borrador de un listado de 7
   tareas pendientes. Con el presupuesto de redacción no da tiempo a otro intento y el turno acaba sin respuesta. Es
   estocástico: los mismos turnos se publicaron en v4s. En el aviso fueron tres `extra_claim`. Los otros rotos de v4u son
   argumentos con fecha (scheduledDay) y una búsqueda. Lección: una ronda que sube o baja ±7 en DEV-E con ≤ 1 turno de
   código cambiado se mira primero en los terminales, antes de atribuirla al mecanismo. Un estado de 263 no es todavía
   una línea base estable.
3. **DEV-I sellado** (sha 2c6a5975…, 300 turnos: 125 sueltos, 45 conversaciones de 175 turnos). Con la forma de DEV-E y
   las reglas de oro 11–20. Lo escribieron 5 escritores de sala limpia en 3 rondas de exclusión (118 → 3 → 0 coincidencias,
   todo reescrito por su autor y nada descartado). Pasadas ciegas A (Opus) y B (Sonnet): acuerdo de primera etiqueta
   300/300; 92 filas al adjudicador ciego (83 «1», 4 «2», 4 unión; ningún descarte). Iterable.
4. **Mecanismos.**
   - **M151**: el archivo que BAXY acaba de nombrar se lee al pedir su contenido («qué dice», «read it», «give us the
     gist») o se elige entre los listados por ordinal o palabra («the signed one», «la de pisos», «abre el segundo»). La
     extensión decide la operación; la carpeta, la última línea que la nombró. Arregla 8 filas de F/G/H; se activa en 11 de
     todas las filas con historial de F/G/H/I.
   - **M152**: «pon un recordatorio en una hora para X» se lee sin modelo; un «N antes de algo sin hora» que el decisor
     reescribió como «en N» pregunta en vez de programar una hora que nadie dijo. De las 9 filas de avisos que fallaban,
     7 son de historial vivido (la búsqueda no dio la hora del partido, Outlook sin configurar, falta un fichero): ahí
     preguntar es lo correcto.
   - **M153** (en curso): ningún turno entendido y hecho termina sin respuesta porque la guarda vete su borrador; vetos
     falsos sobre listados de tareas y suelo determinista de lo observado.
   - Se descartaron como mecanismos los fallos de ventanas y batería de F/G/H: el turno anterior, ejecutado de verdad,
     dio otra respuesta (D67).

## D74. DEV-I base, v4v (M151–M153), D73 del puntuador, M154–M157 (2026-10-04 10:40)
1. **DEV-I en la App, base v4u** (= código de v4s): 262/300 = 87,3 % con D61 (estricta 258); decisor aislado 293/300 en
   decisión. Lastre de decisión 17 y de argumentos 14, en su mayoría en mensajes sueltos (sin historial vivido): código.
2. **Puntuador, D73** (capa D61, la cifra estricta no cambia): cuando el oro acepta `ask` y BAXY sólo publicó una
   aclaración (todas las rutas del turno son `clarification`, aunque la decisión interna fuera una acción a la que le
   faltaba un dato), el turno cuenta. DEV-E +0; DEV-I +4; F/G/H/D +1 cada uno.
3. **v4v** (main 11ce91da: M151 archivo nombrado, M152 avisos, M153 vetos falsos sobre títulos citados y respaldo dentro
   del turno). **DEV-E 262/299 = 87,6 %** (estricta 251; +6/0 frente a v4u, p = 0,03; 1/2 frente a v4s); **0 turnos
   `filtered`** (v4s 1, v4u 5): la oscilación de D73 desaparece. DEV-G 277 (92,3 %), DEV-H 279 (93,0 %), DEV-F 245
   (87,5 %), DEV-D 308 (92,8 %), DEV-I 264 (88,0 %); reserva 90,0 / 94,0 % (0/0), 742 sin cambios, DEV-C 84,7 %, cien-128
   100/100, held-out 30/30, guion 52/60 + 5 por revisar (el nuevo «??» es t21: «confirmo» tras «cierra edge» cerró Edge;
   correcto, con otra redacción → 53).
4. **M151 no se ve en la App**: en la corrida en vivo, la respuesta anterior de BAXY nunca nombra el archivo, porque los
   ficheros que suponen las conversaciones no existen en este PC (D67). Probado con el historial escrito; queda en el
   producto.
5. **Mecanismos para v4w** (integ/v3z 161a0e1a):
   - **M154**: una conversión de moneda o un tipo de cambio se consulta (Frankfurter), nunca de memoria. La guarda M81
     separa la pregunta del motivo de la persona («que tengo que cambiar…», «mi viejo me preguntó…»), que no es un dato
     propio. Frankfurter: «mexican peso» devolvía CLP; ahora MXN.
   - **M155**: los lectores de primer turno no pisan al decisor («en media hora» no es «media»; un elogio no es «tareas»;
     «qué horas» no es portugués; «alarm for 6 to get up» aplica D61). **Seguridad**: una orden de no enviar («leave it
     for me to send», «pero no se lo mandes») sin cliente nombrado acababa en `message.send`; ahora es borrador, y un
     envío del decisor con esa orden también. I-s111 («búscame en YouTube…») se deja en la búsqueda por el literal
     revisado H0728 (WEB1481), aunque el oro de DEV-I diga reproducir.
   - **M156**: «a las 6 30» son las 6:30 (antes las 18:00); servicio y luego título con errata («disney plus
     intensamnete 2»); un nombre de app que suena igual («afinity foto») no es inventado.
   - En el merge de M155 con M156 quedó un conflicto real en `semantic/temporal.py` committeado con sus marcadores
     (cbd2eae2), resuelto en 161a0e1a antes de cualquier prueba o push.
   - **M157** (en curso): M147 no se aplica en la App en su propia fila (F-w05-t5: la consulta a Spotify fue «Javier
     Mené» en v4u y en v4v); «tradúceme eso al inglés» → búsqueda; una nota con el título como contenido.
