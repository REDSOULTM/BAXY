# Investigación de la Fase 3.5b (2026-09-27): qué dice la literatura y qué se prueba en BAXY

Tres informes de investigación web (sólo búsquedas técnicas genéricas: ninguna frase del dueño ni dato del producto
salió de esta máquina) y un análisis interno de fallos sobre lo que sí se mira (DEV-A, reserva; nunca DEV-B ni FINAL).
Los informes completos quedan en el scratchpad de la sesión (`research/R1_enrutamiento.md`, `R2_receta_lora.md`,
`R3_lengua_real.md`, `R4_taxonomia.md`); aquí va la evaluación contra BAXY y el orden de medida.

## Filtro de identidad (00_IDENTIDAD)

Toda opción pasa antes por las tres cosas que BAXY nunca hace: inventar que hizo algo, actuar sin que se lo pidan,
mandar datos fuera. Se descarta lo que suba las acciones sobre cosas que no se hacen (una acción inventada vetó M10c)
o que necesite servicios externos.

## Lo que ya sabemos por medida propia (y la literatura explica)

| hecho medido | explicación publicada |
|---|---|
| `full5` (+1 000 seguimientos, charla 22 → 25 %) y `full4` (+500 sueltos) empeoran en aislado y en integrado | cambiar la proporción de etiquetas en el SFT mueve la frontera de decisión más que la cantidad de datos (Hammer 2410.04587; When2Call 2504.18851: el SFT con negativos vuelve el modelo «demasiado conservador») |
| el decisor dice «límite» a 14 órdenes que el producto hace (M9c) | sobre-rechazo típico del SFT con irrelevancia; lo mueve mejor la preferencia (RPO/DPO) que más SFT (When2Call, EvoRefuse 2505.23473) |
| la conversación ajena no se separa por texto (M10, M10b, M10c) | la detección de destinatario sólo con texto ronda un 12 % de EER; con el turno anterior mejora (R3) |
| en DEV-B la clase que el producto pierde frente al decisor aislado es la charla (54/64 frente a 61/64) | — (propio): respuestas rechazadas por el contrato que la recuperación convierte en pregunta, y preguntas de conocimiento estable que se buscan |

## Opciones evaluadas

| # | opción | fuente | encaje con BAXY | riesgo de identidad | coste | decisión |
|---|---|---|---|---|---|---|
| M26 | quitar la pregunta-oferta final de una respuesta de charla en vez de rechazarla | propia (regla WEB1453) | alto: la charla es la clase que más pierde el producto | nulo: sólo se quita texto | minutos | **retirado**: 0 arreglados, 0 rotos |
| FS | few-shot dinámico: k≈4 turnos resueltos del banco de sala limpia (5 936, nunca DEV) al final del prompt del decisor, recuperados por trigramas | R1 (LangChain; Milios 2309.10954) | alto: sueltos; el banco ya existe y está equilibrado por construcción | medio: copiar la operación del vecino → se mide «inventadas copiadas» | +0,2–0,5 s prefill | **descartado**: DEV-A 234 → 238/240, DEV-B 225 → 221 (sueltos 104 → 98/99) con los dos bancos |
| CAL | sesgo calibrado sobre el token de decisión (logprobs de la misma pasada) | R1, R2 (Batch Calibration, Refusal Tokens) | medio: el error dominante no es una sola clase | alto si baja «límite»: inventa acciones | horas | después de FS; calibrar en DEV-A, verificar una vez en DEV-B, veto con 1 inventada |
| ARB | arbitraje lectores↔decisor por confianza (G-NLL de decisión+operación) con banda de pregunta | R1 (2604.22985; Amazon 2410.01627) | alto en teoría: M9c falló porque el decisor sustituye al lector sin medir su confianza | medio | días | candidata tras CAL |
| POD | podar el catálogo a ~60 operaciones alineado con el entrenamiento (el LoRA se entrenó con ~60 y se sirve con ~200) | R1 (TinyAgent 2409.00608) | medio | alto: operación podada → límite falso | días | sólo con recall@60 ≥ 0,995 medido antes |
| RPO | segunda etapa de preferencias con pares simétricos minados de errores reales (no del dev) | R2 (When2Call RPO, DiaTool 2504.02882) | alto para el sobre-rechazo | medio (pares sólo pro-acción inventan) | ~15 h de redpc + TRL | cuando FS/CAL se agoten |
| SFT6 | re-SFT con cuotas fijas (acción 50 / charla 21 / pregunta 17 / límite 12), datos nuevos que sustituyen, 2 épocas con checkpoints | R2 | medio | bajo | ~10 h | sólo junto con RPO |
| DIS | aumentar datos con disfluencias sintéticas (LARD) | R3 (DRES +23,5 en 3B) | bajo aquí: AJUSTE4 ya lo hizo y empeoró al sumarse | bajo | — | no, salvo como sustitución dentro de SFT6 |
| ADR | etiqueta «no dirigido a mí» con el turno anterior | R3 (Apple 4,8 % FA con contexto) | bajo: tres intentos fallaron por la conversación ajena real del dueño | alto (M10c inventó una alarma) | — | no |
| ASR | n-best del STT; actuar sólo si los dos mejores coinciden | R3 | fuera de alcance de esta fase (texto) | — | — | anotado para la fase de voz |

### Del análisis interno (R4: DEV-A 39 fallos, reserva 397 de los que ≈190 son reales)

| # | opción | casos (reserva + DEV-A) | riesgo | decisión |
|---|---|---|---|---|
| M27 | el lector de música pregunta «¿qué música?» sólo si, quitado el verbo y lo genérico (música, canción, algo, playlist, relleno), no queda nada con contenido: «pon música clásica», «canciones tristes», «la canción la macarena» ya dicen qué poner | 29 + 0 (los 21 de esa rama que hoy aciertan tienen reproducir en el oro) | 2 (reproducir es reversible) | **entró**: reserva 85,6 → 86,3 % (19 y 1), DEV y 742 iguales |
| L2 | lector de efectos: añadir/marcar en el calendario → crear, no listar; quitar acciones sin sustento (chiste → mensaje, «vaya» → OCR, luz/juego → YouTube) | ≈11 + 3 | 1 (quita acciones) | calendario: de 12 filas sólo 4 son reales (el resto es ruido de MASSIVE) y 2 son formas raras («do add this on my calendar»): **no vale una regla** |
| C1 | frase llana de `web.search`: información pública (fechas, cotizaciones, resultados, horarios), nunca contactos, correos, calendario ni archivos de la persona | ≈10 + 1 | 1 | con M22 como precedente (datos, no reglas) |
| C2 | frases de `media.play.query` (texto libre: género, ambiente, playlist; podcast sólo si una reproducción real lo prueba) y `media.control` (episodio) | ≈22 | 2 | con C1; «podcast» exige la prueba real antes |
| C3 | `weather.current` responde también si conviene abrigo, paraguas o gafas de sol | ≈8 + 1 | 1 | con C1 |
| A1 | argumentos: no preguntar un valor que ya está en el objetivo; `place` en `system.time` | 0 + 9 | 1 | aparte |
| — | la conversación ajena al decisor | ≈9 + 3 | — | **no**: M10, M10b, M10c (acción inventada) |
| — | capacidad parcial (hacer una parte y decir el resto: silencio con duración, subtítulos) | ≈9 | 3 | espera una regla del dueño |

Fallos del arnés, no del producto: `comprension_eval.run` no aterriza argumentos de las etiquetas `plan:` ni pide
`task.resolve.exact` antes de `task.delete`/`task.update`.

Descartadas por la literatura: autoconsistencia por votación (no supera a la G-NLL de una muestra y cuesta ×n) y
razonamiento dentro del JSON del decisor (sin mejora medida).

## Protocolo

Un cambio a la vez; DEV-A para mirar y ajustar, DEV-B sólo la cifra, FINAL una vez al cierre. Veto: una acción
inventada más (acción donde el oro no la tiene) invalida el cambio aunque suba el total. Entra con la regla de D12
(capa A ≥ 96,0 %, 742 revisadas, reserva sin bajar) y DEV-B sin bajar.

## Auditorías del 28-09 (agentes, sólo lectura)

- **Contaminación:** 32 396 textos de entrenamiento (SFT, pares, RPO, bancos few-shot) contra 2 830 protegidos (DEV-A,
  DEV-B, FINAL, 742, guion, held-out, cien, registro real). 0 filtraciones peculiares: las coincidencias exactas son
  órdenes cortas y genéricas («qué hora es», «cerralo») o frases hechas de BAXY en el historial; ninguna conversación
  comparte dos turnos con una protegida (similitud máxima con FINAL 0,73). Único caso dudoso de riesgo bajo: la pregunta
  del «dólar blue hoy» (coseno 0,88 con una fila de FINAL), la forma estándar en Argentina.
- **Calidad de las etiquetas de AJUSTE5:** en 144 pares minados revisados, 47 tienen el «chosen» dudoso: el contraste
  «dos temas → preguntar» (17) choca con la regla 3 (buscar los dos no rompe nada), 9 «charlas» donde preguntar
  también vale, 6 «charla frente a búsqueda» donde se busca. Explica en parte por qué `full5` empeoró. La ronda 2 de
  pares se filtra (173 → 77) y el cierre de remates se limita a 2 por contraste; AJUSTE5 no vuelve a entrenar sin esa
  revisión.

## Modelos base alternativos (R5, 28-09, sólo fuentes públicas)

Ninguno gana con claridad a Qwen3.5-4B en mensajes sueltos en español: BFCL v4 es 40 % agéntico y 30 % multivuelta
(mal proxy de una decisión cerrada de cuatro), nadie publica las subcifras de relevancia/irrelevancia y no existe un
banco de llamadas a herramientas en español para modelos pequeños. Un cambio de base exige un A/B local (mismo LoRA
sobre cada base, puntuado en el conjunto propio de sueltos).

| modelo | licencia | por qué entra o no |
|---|---|---|
| LFM2.5-2.6B | LFM Open v1.0 (gratis bajo 10 M USD de ingresos, no OSI) | única comparación directa: BFCLv4 56,9 frente a 50,6; KV mínima; **PREGUNTAR** por la licencia |
| Gemma 4 E4B | Apache-2.0 | mejor multilingüe que cabe (MMMLU 76,6), tokens nativos de funciones; BFCL menor; VRAM a medir |
| Granite 4.2 3B | Apache-2.0 | ganancia marginal (52,4 frente a 50,3), KV cara (q8_0 obligatoria) |
| Qwen3.5-4B Q5_K_M | la actual | base de comparación: ≈4,0 GB con KV q8_0, al borde del tope de 4 096 MiB |
| Hammer2.1, xLAM-2-3b, Arch-Function | no comerciales | fuera sin permiso del dueño |
| Phi-4-mini, Llama 3.2 3B, Qwen3.5-9B, MoE | — | no caben en 4 GB con 12k de contexto |

Decisión: no se cambia la base en esta fase salvo que el techo de sueltos quede medido como causa limitante tras CAL
y RPO; entonces el primer A/B es Gemma 4 E4B (Apache) y LFM2.5 sólo con el visto bueno del dueño.
