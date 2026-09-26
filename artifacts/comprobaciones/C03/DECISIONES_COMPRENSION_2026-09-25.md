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
