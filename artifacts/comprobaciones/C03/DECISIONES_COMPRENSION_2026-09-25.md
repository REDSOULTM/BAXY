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
