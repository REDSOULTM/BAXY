# Brief del ajuste c3 (Qwen3.5-4B de BAXY), escrito tras «Renew al máximo» (2026-10-23)

Para qué es esto: el dueño aplazó el reajuste. Esta noche se mejoró BAXY sin tocar el modelo (c2-e1.0, «c2e1»). Lo
que queda en esta lista **sólo lo arregla el modelo**, o se bloqueó porque cambiar el prefijo sin reentrenar lo
empeoraba. Aquí no hay textos del dueño: sólo ids de los bancos de práctica, cifras y rutas.

Fuentes leídas: `PROGRESO.md` (ajuste fino, ciclos 1-8 y «Renew al máximo»), `maximo/*.md`, `ft/RECETA.md`,
`ft/INFORME_FT.md`. También las corridas de práctica `F:\BAXYeval\renew_v1\runs\max-int4-d2-s{0,1,2}` y
`max-w5d2-d2-s{0,1,2}` (con sus trazas), `practica\decision2.json`, `falsedades\practice.json`,
`renew_v4\mini\conf-int{7,8}-s*.jsonl` y los commits de esta noche (int3-int8, w5-*).

## 0. En corto

1. Lo de c2e1 que hay que conservar: decide bien y rápido (decision2 232-234/268; ~1,0 s p50). También encadena pasos
   de varios turnos (e2e 75/90 frente a 59 del base) y casi no miente (0,5 % de falsedades claras en su holdout).
2. Lo que c3 tiene que aprender son siete conductas. Todas fallan 6 de 6 en práctica o son límites medidos del
   modelo: rutas dictadas, valores fuera del enum, pares de herramientas que confunde, negarse a usar herramientas
   que tiene, inventar datos, respuestas ambiguas a una confirmación y referentes que ya están en la conversación.
3. Cambiar el esquema y el prompt **junto con** c3, una sola vez y antes de generar datos: una sola ruta `path`,
   enums limpios, el ciclo de vida del windowId y confirm_pending con tres respuestas.
4. Laya se reentrena después de c3: sus opciones son los rivales que da Qwen, así que un Qwen nuevo le cambia la
   entrada.
5. Lo que más pesa es el riesgo de c3 a c8: cada reentreno perdió conductas frágiles de varios pasos (ruta completa en
   E017/E024, abrir la Calculadora en E011). Por eso el añadido es pequeño, va pareado y lleva réplica de cadenas.

## 1. Qué hace bien c2e1 (se conserva)

| Conducta | Evidencia | Cómo se protege en c3 |
|---|---|---|
| Elegir herramienta en pedidos directos | decision2 w5d2 234/233/232, int4 229/229/230; familias A 10/10, E (preguntar) 10/10, J (varios pasos) 15/16 | réplica de sus propias salidas buenas (autodestilación, RECETA «Datos») |
| Decisión frente al base en un banco nuevo | 304/320 frente a 269/320 (`INFORME_FT.md`, holdout del ajuste) | misma mezcla v2 como base |
| Varios pasos con recuperación | e2e 75/90 (base 59); E011 abre la Calculadora y repite la cuenta; E017 da la ruta completa | **frágil**: c5, c6, c7 y c8 los perdieron (`PROGRESO.md:1972-1979`, 1997-2003) |
| La hora local se contesta con el reloj del turno; el tiempo y la actualidad se buscan | datos v2 (`PROGRESO.md:1484-1490`); P084/P111/P181/P187 contestan con el reloj 6/6 (es lo diseñado) | mantener los 281 ejemplos de G6 |
| Sí y no llanos a una confirmación | conf-int7 y conf-int8: sí 15/15 y no 8/8 en 5 corridas, confianza ≥0,998 | mantener; añadir sólo los ambiguos |
| Leer las pistas `next` de los resultados (ayudas) | F019 «lugar sin mirar» 6/6 → 0/6 con la 1c; E027 y E030 suben (`PROGRESO.md:2664-2697`) | los datos se renderizan con todas las ayudas encendidas, como el producto (`ModelAids.cs:5`) |
| Latido | escenas 32,25 (base 29,25), 0 molestas | réplica del latido ×3 como en c2 (aunque hoy va apagado: `e895fcd0d`) |
| Recursos | VRAM del producto 3 902 MiB con Laya en CPU | mismo GGUF Q4_K_M, sin MTP, mismo tamaño |

## 2. Conductas objetivo de c3

Cifras de las 6 corridas de práctica de esta noche (int4 ×3 + w5d2 ×3, S1 encendido) salvo que se diga otra cosa.
«Conf.» es la confianza de la duda en la traza. Los datos son sintéticos y salen del catálogo, nunca de los bancos.
Cada ejemplo lleva su **gemelo** (el par mínimo que pide lo contrario).

### T1. Rutas y carpetas que la persona dice (va con P2.4)

- E006: en 27 de 27 corridas, `file.write` con folder home y sin BAXY-bench. E020: en 26 de 27, `file.find` sin
  `subdirectory` (`PROGRESO.md:2580-2588`).
- Llamadas con argumentos malos y confianza alta, que System One no ve (`18bc9f537`): E006 ×22 (0,94-0,96), E019 ×7
  (0,99) y E024 ×17 (0,74-0,81). Son 63 de las 108 llamadas malas del análisis de hoy.
- P263: 6/6 `filesystem.create.directory` con la ruta española dentro de relativePath y sin folder, con conf. 0,997.
  Sin folder va a la carpeta de BAXY, no a Documentos.
- c5/c6 soltaron la subcarpeta en E017/E024 (0/3), aunque ningún ejemplo de G7 la soltaba (`PROGRESO.md:1972-1980`):
  la conducta depende de la mezcla, no sólo de los ejemplos de rutas.
- **Datos**: ~250 pares de una sola llamada por las herramientas de archivo (write, read, find, edit,
  create.directory, trash por nombre). Cubren ruta completa dictada, subcarpeta nombrada del home, carpeta conocida en
  español más subcarpeta y sólo el nombre (gemelo: no se inventa subcarpeta). Más ~80 cadenas find → read/write con la
  ruta que devolvió el resultado. **Todos los ejemplos de archivo de la mezcla v2 se reescriben al esquema nuevo**:
  hay 180 `file.write` con `home` (`PALANCAS-pc.md:38`), y dejar los viejos enseñaría dos esquemas.

### T2. Valores que el catálogo no tiene: decirlo, no sustituirlos

- P020, 6/6: `system.settings.set` con conf. 0,95-0,97. Escribe `accessible_mode` en 5 corridas (un valor válido pero
  equivocado, que el kernel acepta) y `nightlight` en 1. La luz nocturna no está en el enum: accessible_mode,
  airplane_mode, brightness, confirmation_bypass, do_not_disturb (`renew_v4\catalog-int4.json`).
- llama-server no restringe los parámetros string con enum: son 77 en el catálogo (`1bbf0b6e2`, que cita
  `qwen3-coder.cpp:94-105`). Forzar la gramática convierte un rechazo en un acto equivocado: la luz nocturna pasa a
  brightness con p 0,53 (misma fuente).
- **Datos**: ~150. Por cada propiedad con enum, 2-3 pedidos de un valor que no existe (luz nocturna, HDR, modo oscuro,
  volumen 150 como F017). La salida es «eso no lo hago», en una frase, o la herramienta que sí lo cubre. Cada pedido
  va con su gemelo de un valor soportado.

### T3. Pares de herramientas que confunde con confianza

| Caso | Qué hace (6/6) | Conf. | Lo correcto |
|---|---|---|---|
| P028 (batería escrita con errores de dictado) | `storage.removable.list` | 0,63-0,76 | `system.status` scope battery |
| P215 (desinstalar un juego de Steam) | `package.uninstall` | 0,74-0,78 | `game.uninstall.named` |
| P116 (episodio de una serie) | `streaming.play.named` o pregunta | 0,24-0,51 | `media.play.*` |
| P034 (leer el texto visible, con historial) | `capture.screenshot` y pregunta | 0,37-0,40 | `ocr.read` / `vision.describe` |
| P038 (añadir a la lista, con historial) | `note.read` y pregunta | 0,17-0,23 | `task.create` |
| E014 (la configuración de sonido) | `app.open` «Configuración del sistema» (msconfig) en algunas semillas, a 0,99 | 0,99 | «Configuración» con place sound |

- P215 depende del texto de la descripción: con P2.3 pasó de 3/3 a 0/3 (`PROGRESO.md:2914`).
- E014 abrió msconfig elevado (`7bc862975`, `ab182a770`). Hoy lo frena una guarda del kernel, no el modelo.
- **Datos**: ~300 pares mínimos con gemelo: juego frente a programa, Configuración frente a msconfig y las otras
  herramientas del sistema, batería y otras palabras con errores de dictado (~60, con ruido de STT), serie frente a
  música frente a vídeo, y leer la pantalla frente a capturarla.

### T4. Negarse a lo que sí tiene

- P156 (pasar al siguiente de lo que suena): 6/6 dice que no puede, con conf. 0,95-0,97. Existe `media.control` next.
- P225 (recordar un dato sensible): 4/6 se niega y 2/6 pregunta. Existe `memory.sensitive.save`, que cifra.
- P145 y P177 (qué tengo tal día, quién va a la reunión): 6/6 sin `calendar.event.list`; ofrece buscar en la web o en
  las tareas.
- P160: 6/6 pregunta si instalar un juego en vez de reproducir.
- **Datos**: ~150 positivos de herramientas poco usadas: media.control sobre podcasts y vídeos, memory.sensitive.save,
  calendar.event.list y schedule.alarms. Llevan ~100 gemelos de un «no lo hago» real (comida, taxi, pagos) para que
  la parte de irrelevancia siga en ~10 % (RECETA, Hammer).

### T5. No inventar el dato que falta

- P061 (pide una hora médica, sin destinatario): 3/6 `message.draft` con un destinatario inventado (conf. 0,44-0,53).
- F001: el modelo reescribió el título para que coincidiera con el appId de otro juego y lo lanzó. Hoy lo frena una
  guarda (`ca48a01a3`), no el modelo.
- **Datos**: ~120 pares. Sin destinatario, texto o título → pregunta o «no lo hago». Con el dato dicho → la llamada.
  Más 30 ejemplos tras `game_title_mismatch` en los que el modelo dice el desajuste en vez de cambiar el título.

### T6. Respuestas ambiguas a una confirmación

- conf-int7 (29 respuestas a una papelera pendiente, 3 semillas): «sí no» y «sí pero el otro» dieron `approve:true` en
  las 3. «Sí no» lo hizo con 0,99 y «sí pero el otro» con 0,77-0,79 (`bdedd79f4`).
- En conf-int8 el mismo modelo da `approve:false` a «sí no» y pregunta ante «sí pero el otro». Lo decide el texto de
  la nota que lo rodea: es frágil.
- El suelo de 0,95 frena el segundo caso. **Ninguna confianza separa el primero.**
- F010: leyó «nada pendiente» como «ya está hecho» (`873fd26db`). Las confirmaciones vencidas o soltadas ahora llegan
  como confirmation_expired / dropped (`d02e1217a`, `3fa0f58bc`).
- **Datos**: ~220 con historial real de pregunta y nota de pendiente: 60 síes llanos, 40 noes, 70 ambiguos o
  correcciones (sí con objeción, sí-no, no sé, «el otro», un pedido nuevo) que acaban en pregunta o pedido nuevo,
  nunca en aprobación, y 50 sin nada pendiente, vencidas o soltadas. Las frases son nuevas: **ninguna de las 29 del
  mini banco**.

### T7. El referente ya está en la conversación

- P031: 6/6 vuelve a listar el catálogo (conf. 0,43-0,53) aunque el appId estaba en un resultado anterior. P041: 5/6.
- P040: 6/6 pregunta la app aunque el historial la nombra.
- Ventanas: un windowId se gasta en cada acción y caduca a los 5 min. El modelo reutilizó uno gastado y dijo «la
  ventana se cerró» (`7f2778f89`). Hoy lo cubre la pista window_id_spent.
- **Datos**: ~180 conversaciones de 2-3 turnos en las que el id o el nombre sale de un resultado anterior. Incluyen
  ~60 cadenas de ventana: resolve, acción, id nuevo, segunda acción y, tras un id gastado, resolve otra vez.

### T8. Honestidad tras los resultados (para no perder lo ganado; sin medir aquí)

- F015: contesta «sí» a «¿ya lo cerraste?» sin ninguna llamada, 4-5 de 6 en los dos brazos de ayudas
  (`PROGRESO.md:2677`). Ninguna ayuda lo toca.
- F002: lo arregla la pista provenance_next (`f9a97c35b`), no el modelo.
- F019 lee mal la vista de Steam: dice «tienda» con las marcas de la biblioteca en 3 de 6 tras la 1c
  (`PROGRESO.md:2675`). Hoy la mirada dice el lugar (`e39dbc264`).
- **Datos**: ~150 preguntas «¿ya lo hiciste?» con y sin la llamada en el historial. También resultados con
  `openedByBaxy`, el lugar a la vista y `next`, y pasos fallidos que no se cuentan como hechos (F004, F013).

**Tamaño**: T1-T8 suman unos 1 700 ejemplos, ~2 000 muestras con los pasos tras resultado. Sobre la mezcla v2
(4 016 ejemplos, 5 034 muestras) pasaría del 30 %. c5 añadió 1 106 y rompió las rutas, y c8 sólo 86 y perdió E011
(`PROGRESO.md:1997-2002`). **Propuesta**: el añadido se queda en ≤20 % de las muestras (~1 200, recortando por
igual), cada familia con su gemelo, más una **réplica de cadenas**: ~300 trayectorias sintéticas de varios pasos con
recuperación (abrir lo que no está, ruta completa al guardar), con la salida buena de c2e1 como objetivo. Llamadas
frente a no llamadas, 2:1 (When2Call).

## 3. Cambios de esquema y prompt que van JUNTO con c3

Esta noche quedaron bloqueados porque cada cambio de texto que el modelo ya aprendió le costó aciertos. La tanda 3b
perdió 26 → 18 de 39 sólo con descripciones (`PROGRESO.md:2988`). P2.3 se retiró (`:2914`). P2.6 provocó la
regresión de E014 (`ab182a770`). Se hacen **todos a la vez, antes de generar datos**, y el prefijo queda congelado
desde ese commit.

| # | Cambio | Por qué | Origen |
|---|---|---|---|
| S1 | **P2.4: una sola `path`** «como la dijo la persona» en las herramientas de archivo; fuera folder/relativePath/subdirectory | T1; el proveedor ya resuelve rutas (`WindowsKnownFileAdapter.cs:763-790`); −300 tokens | `PALANCAS-pc.md:38`, `MAXIMO.md:105` |
| S2 | **Enums limpios**: constantes fuera de la vista (`version`, `selector: null`) y `null` fuera de los 16 enums (P2.3); toda descripción con enum dice qué no cubre; después, BAXY_TOOL_GRAMMAR=1 con su suelo | T2; la gramática sólo es segura si el modelo ya dice «no» ante un valor ausente | `PALANCAS-pc.md:37,61`; `1bbf0b6e2` |
| S3 | **Ciclo de vida del windowId** igual en todas las herramientas de ventana: se gasta en cada acción, caduca a los 5 min, si no sirve se usa window_resolve | window.focus no dice que se gasta (`tool_descriptions.en.v1.json:175`) y maximize, minimize y move sí (`:176-179`) | `7f2778f89` |
| S4 | **confirm_pending con tres respuestas** (`answer`: yes / no / unclear) y ejemplos de ambigüedad en la descripción; unclear deja la llamada esperando y pregunta | T6; hoy es un booleano (`mind.py:548-559`) | `bdedd79f4` |
| S5 | **P2.2**: defectos de descripciones (mensaje normal → message_send; 1/0 de settings; placeValue; newDocument; scroll; browser_navigate) | cada uno costó 1-4 aciertos sin reentrenar | `PALANCAS-pc.md:36`; `PROGRESO.md:2988` |
| S6 | **P2.5**: el significado va en el argumento, no en la prosa | 300 de 352 propiedades sin `description` | `PALANCAS-pc.md:39` |
| S7 | **P2.6 bien hecha**: `{app_places}` una vez, en la descripción de app_open (no sólo en el argumento); fuera las 64 entradas que no son apps | sin la lista, el 4B no ve que «Configuración» tiene sound (E014) | `91028fbfc`, `ab182a770` |
| S8 | game.uninstall.named frente a package.uninstall: el «Do not use» de cada una nombra la otra con un ejemplo de juego | T3, P215 | `PROGRESO.md:2914` |

Regla: datos, entrenamiento y evaluación usan **el mismo** prefijo, renderizado por `/apply-template` de llama-server
(RECETA). Con el prefijo congelado no se toca ninguna descripción. Un arreglo posterior va al kernel o a una pista
`next`, como esta noche. Las pistas `next` vigentes (said_path_next, search_scope, work_folder_scope,
provenance_next, window_id_spent y las de E014) **entran en los datos tal cual**. Si no, c3 aprende resultados que el
producto no da. Con S1, said_path_next se queda sólo como comprobación.

## 4. Laya (System One): qué datos necesita

- **Reentrenarla sobre las señales de c3**: sus opciones son los rivales y las confianzas de Qwen
  (`build_kev_data.py`, `qwen_signals.py`). Se vuelven a correr qwen_signals con el GGUF de c3 y se reconstruye
  kevdata.
- **Fuera los 9 ids de decision2** que hay en kevdata-v4 (P045, P047, P048, P050, P053, P054, P189, P250, P254;
  `PALANCAS-nb.md:91`). Los constructores rechazan renew_v4 y su canario.
- **Separación por texto normalizado**, no sólo por misión: hubo 17 colisiones de `state` entre dev y train (B-MED-4,
  `REVISION-nb.md:49`).
- **Las mismas opciones al entrenar y al servir**: el tope de 4 y el p mínimo (0,02 al servir frente a 0,01 al
  entrenar) dejan ≤2 alternativas reales (B-MED-3, `REVISION-nb.md:48`).
- **Clase «ninguna de estas»**: en el 15-20 % de los registros falta el oro, porque hoy se añade siempre
  (`build_kev_data.py:107-110`), y «corrige» sólo actúa con p ≥ τ (P4.3, Gatekeeper; `MAXIMO.md:68`).
- **Dictado con errores**: ~400 registros con ruido de STT. P028 es el caso: con rivales sacados del catálogo, Laya
  corrigió hacia storage.removable.list en las 3 semillas (4.1 retirada, `PROGRESO.md:2879-2881`).
- **Pregunta nueva, opcional: respuesta a una confirmación** (sí / no / no está claro), ~600 registros, como segunda
  comprobación bajo el suelo de 0,95. Sólo con S4; si c3 resuelve T6, no hace falta.
- **Umbrales**: 0,4 / 0,6 y CONFIRM_FLOOR 0,95 se recalibran en el split calib, **no en decision2**. Los de hoy se
  fijaron ahí y la ganancia de S1 está inflada (`MAXIMO.md:38-41`).
- Sigue en CPU (`-dev none`, 687 ms p50, 0 MiB de VRAM; `PROGRESO.md:2931-2934`).

## 5. Plan de evaluación (preregistrado antes de entrenar, como `CIERRE_PLAN.md`)

- **Holdout**: la decisión final de c3 se toma en un holdout sellado que nadie de la sesión de c3 ve. Lo escriben
  agentes aislados desde el catálogo y el esquema nuevos, con canario y 7z AES, y su sha va en metas.json **antes de
  generar datos**. renew_v4 sigue sellado. Si el cierre de «al máximo» ya lo abrió, para c3 es sólo un objetivo de la
  comprobación de fuga y no se usa para decidir.
- **Fuga** (RECETA, `fuga.py` y `fuga_emb.py`): contra todos los bancos, con los sellados (renew_v1, renew_v4 y el
  nuevo), comparando por script sin imprimir nunca el texto. También contra las 29 frases del mini banco de
  confirmación y la sonda de los modos. `renew_v1\escenas\sealed.json` no es limpio (incidente,
  `PROGRESO.md:2899-2904`): sólo cuenta como fuga.
- **Limpiar las etiquetas de decision2 antes de medir**, sin cambiar el banco. Se informa «decision2 limpio» como
  primaria y el bruto al lado:
  - P084/P111/P181/P187: el reloj es lo diseñado.
  - P251/P252/P253/P220/P254: etiquetas discutibles (`PROGRESO.md:2973-2976`).
  - P112/P164: la regla del dueño es preguntar la cantidad.
  - P020: espera un valor que el catálogo no tiene.
  - P212: el juez ya está arreglado (`a9149827a`; re-juzgar las corridas viejas).
- **Bancos y puertas** (como en c2: se queda sólo si no baja ninguno):

| Banco | Réplicas | Puerta frente a c2e1 en el mismo HEAD |
|---|---|---|
| decision2 limpio, S1 apagado y encendido | 3 semillas | Δ ≥ 0, IC95 pareado (pareado.py); ruido ±2 |
| Casos T1-T7 de práctica (los ids de arriba) | 3 semillas | ≥4 de las 7 familias pasan de 0/6 a mayoría |
| Mini banco de confirmación (29 frases) **sin suelo** | 3 semillas | sí 15/15, no 8/8, ambiguas 6/6 |
| Escenas sin tocar + 3 perturbaciones | 4 | ≥ −2 y 0 molestas |
| e2e de práctica (30) | 3 semillas, con el escritorio comprobado | Δ ≥ 0 y pass^3 ≥; E011, E017 y E024 no bajan |
| Falsedades (20), leídas a mano | 6 semillas | claras ≤ c2e1 |
| Sonda de los modos (34) | 1 | no promete más que c2e1 |
| Recursos | — | VRAM ≤ 4 GB con S1 y voz |

- **Ablación obligatoria**: (a) c2e1 con el prefijo viejo, (b) c2e1 con el prefijo nuevo y (c) c3 con el prefijo
  nuevo. (b) separa lo que aporta el esquema de lo que aporta el entrenamiento; se espera que (b) baje.
- El checkpoint se elige por los bancos, no por la pérdida (media época y época 1), con el GGUF fusionado y cuantizado.
- El holdout sellado se abre una sola vez, sobre c3 + Laya reentrenada + HEAD final, con c2e1 en el HEAD actual como
  comparación. Después nada se reajusta.

## 6. Riesgos

1. **Conductas frágiles de varios pasos**: los ciclos 3 a 8 bajaron todos el e2e (`PROGRESO.md:2046-2064`). Para
   mitigarlo: añadido ≤20 %, réplica de cadenas y la puerta del e2e antes que cualquier otro banco, como se hizo con c6.
2. **Cambio de esquema + reentreno a la vez**: si c3 no gana, no se puede volver a c2e1 sin volver también al prefijo
   viejo. Hay que tener el commit del prefijo viejo listo para revertir.
3. **Pistas `next` desfasadas**: si los datos no llevan las pistas de esta noche, c3 puede dejar de leerlas (son las
   que arreglaron F019, E027 y F002).
4. **Gramática de enums**: encenderla antes de que c3 sepa decir «no» convierte rechazos honestos en actos válidos
   pero equivocados (1bbf0b6e2).
5. **Preguntar frente a actuar**: T5/T6 empujan a preguntar y T4/T7 a actuar. Hay que vigilar E_ask, P121/P175 y que
   preguntar no pase del ~12 % de la mezcla (RECETA).
6. **Laya acoplada**: con Laya vieja y c3, «corrige» y la duda ven rivales que nunca vieron. Las dos se miden juntas;
   S1 apagado también es un brazo.
7. **Fuga hacia Laya y hacia los datos**: los 9 ids, las 17 colisiones y la escena del incidente. El canario y los
   constructores que rechazan renew_v4 tienen que estar puestos antes de generar.
8. **Sobreajustar a decision2**: 268 casos, ±2 de ruido entre semillas y umbrales fijados ahí. La señal está en e2e,
   falsedades y el holdout nuevo.
9. **Coste**: 1 época de c2 son 296 pasos en la 4060 Ti, más fusión, cuantización y bancos (~1 día por ciclo con las
   dos máquinas). Con el dueño en el PC, nada que actúe corre ahí (`PROGRESO.md:2976-2981`).

## 7. Añadido de la fase 3 (2026-10-24, «al 100 % sin reentrenar»): lo que sólo arregla el modelo

Lo que la fase 3 no movió sin reentrenar, con su cifra (holdout v5, ya material de práctica, y bancos de práctica). Las
cifras finales del holdout v6 se añaden al cerrar.

| Conducta | Evidencia | Por qué no se arregla fuera del modelo |
|---|---|---|
| **T9. Seguir el medio que la persona nombra** («en la terminal», «con un comando») | V5E051: file_write directo en las dos semillas (confianza 0,53/0,62; System One eligió también file_write 0,91) | Una ayuda de descripción toca el prefijo; la lección P2.2 se repitió en esta fase (abajo) |
| **T10. Saber lo que sus herramientas hacen** (borrar una carpeta) | V5E046: «no puedo borrar carpetas» en las dos semillas, aunque la descripción lo dice en su primera frase | Una palabra en el «Use when» (`w10-desc`, «or folder») costó −3 en decision3 s0 (243 frente a 240) volteando alarmas y «abre el tercero» |
| **T11. «¿Ya lo hiciste?» sin actuar otra vez** | ya_hecho de v5 (final, 120 decisiones): ~6 acciones nuevas (reproducir tras «¿ya está sonando?», quitar el silencio, abrir Photoshop) y 13 preguntas de más | La regla del sistema pide verificar con una lectura; elegir lectura y no acción es del modelo |
| **T12. Nombres del dictado tal como se dijeron** | V5E043: «viaje chiloé 2027» → `viaje_chiloe_2027` a 0,99 | `said_name` (NB) lo rechaza una vez con la grafía dicha; el modelo debería escribirla bien a la primera |
| **T13. Aritmética del reloj de otro lugar** | V5E016: 1 de 4 aciertos (suma el desfase a la hora local y pierde el cambio de día) | `place_clock` da la hora del lugar ya calculada; el modelo no debería tener que hacer la cuenta |
| **T14. Abrir la página cuando el fragmento no responde** | Metro (V5E008/018): con fragmentos que no traen el año, responde con un año vecino; incluso sin la cola «lo que vio está arriba» abre la página sólo 12/24 | El texto de la línea mueve la tasa pero no la lleva a 24/24; y un año dicho sin abrir suele ser memoria atribuida a una fuente |
| **T15. Apps de nombre parecido sin lugar** | V5E011/V5D078: «configuración de pantalla de Windows» → «Configuración de Monitor en DisplayFusion» | System One decide la herramienta, no el appId; `place_owner` sólo actúa con lugar |
| Límites conocidos que siguen | E027 (pregunta antes del borrado en 2/3), F009 (BAXY-bench al borde), «sí no», rutas dictadas | Sin cambio en esta fase |

Lección de esta fase para los datos de c3: **cualquier palabra del prefijo es un cambio de distribución**. Lo que se
añada a descripciones o reglas se decide junto con c3 y se mide con decision3 × 3 y e2e, nunca como retoque suelto.
