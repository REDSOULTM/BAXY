# Latido de BAXY Renew: fallos de práctica y cambios de presentación

Investigación de solo lectura, 2026-10-15. Fuentes locales: `src/baxy_mind/mind.py` (HEAD `f2a9c1b7e`),
`src/Baxy.App/{Heartbeat,HeartbeatMoment,NativeTurnLoop}.cs`, `src/Baxy.Kernel/Policy/RiskPolicy.cs`,
`scripts/renew/bench_escenas.py`, `scripts/renew/catalog_equivalence.json`, `<evaluacion>\renew_v1\escenas\{README.md,practice.json}`,
`runs\pc\p13-escenas.{jsonl,trace.jsonl,out}`, `runs\nb-r2-escenas.{jsonl,trace.jsonl}`, `runs\catalog.configure.json`.
No abrí `sealed.json`, `holdout_latido.json` ni nada SEALED.

## 0. Antes de comparar: las dos corridas no midieron lo mismo

| | p13 (PC) | nb-r2 (notebook) |
|---|---|---|
| Hora | 15:29 (alrededor de `f95de6e39`, 15:31) | 17:56 (después de `9e3c4536c`, 17:03) |
| `Texto en pantalla` en el momento | **sí** | **no** (`9e3c4536c` lo quitó: «la App nunca lo manda») |
| Catálogo | el de `%LOCALAPPDATA%` 13:15, con `message.send` | sin `message.send` (P025 usó `message.draft`) |
| Juez | sin `failures` ni `excluded`; propuesta = solo riesgo alto | sin `excluded`; propuesta = solo riesgo alto |
| Retenciones de la App en el latido | solo riesgos | solo riesgos (el retener red/entrada llegó a las 18:23; `media.control`, a las 19:39) |

Evidencia: el `prompt_n` de la decisión cambia justo en las escenas con `screen_text` (P002 519→490, P016 573→544,
P020 543→527, P024 552→527, P026 519→495, P034 538→517) y es igual en las que no lo tienen (P008 513/513, P015 543/543,
P023 561/561, P012 535/535). Por eso un «flip» puede venir del cambio del momento, del catálogo o del hardware. Es ruido
puro solo cuando el prompt es idéntico, y eso pasa en **P008** y **P023** (mismo `prompt_n`, decisión voraz, distinta en
PC y notebook: diferencias numéricas del backend en una decisión al borde).

## 1. Escenas falladas

Ambas corridas sacaron 32/40 con 23/23 silencios. Fallaron 8 cada una:

- **Estables** (fallan en las dos): **P002, P015, P016, P023, P035**.
- **Cambiantes**: fallan solo en p13 **P008, P020, P034**; fallan solo en nb-r2 **P024, P025, P026**.

En la tabla, «decide» resume el JSON del primer paso: los motivos llenos y el valor de `intervenir`.

| Esc. | Contexto clave | Esperado | p13 | nb-r2 | Por qué falló |
|---|---|---|---|---|---|
| **P002** disco | libre, Steam: «download failed… 35 GB», `disk_free_gb=4`, `recycle_bin_gb=28` | propose `system.recyclebin.empty`, voz | decide bloqueo «disco lleno» → INT; **act** `shell.command.run` `robocopy Downloads Downloads /E…` (sin sentido) | mismo decide; propose `filesystem.known.trash.named` `{fileName:"temp_cache"}` (archivo inventado) | La decisión acierta, pero la herramienta es incorrecta. El análisis nunca menciona la papelera, y al segundo paso solo pasa `analisis`, que no la nombra. El dato aparece como `recycle_bin_gb=28`, una clave cruda que no se parece al texto de la herramienta («Empty the Windows Recycle Bin»). Además, todas las descripciones son del tipo «Use when: vacía la papelera», es decir, de un pedido, y en el latido nadie pide nada. **Fallo estable de herramienta.** |
| **P008** noche | 03:10, ausente, `idle_min=95`, memoria «si se queda dormido con el PC prendido, quiere que se apague» | propose `system.power`, notif. | preferencia llena pero `intervenir=false`: «no hay indicio de que esté durmiendo» | INT → propose `system.power` ✔ | Mismo prompt y distinta salida: es ruido en una decisión al borde. La señal de dormido (95 min sin tocar el PC a las 3 a. m.) está repartida entre la línea Momento (`ausente`) y el final de la línea PC (`idle_min=95`), y el modelo no la junta. |
| **P015** recordatorios | 09:40, **jugando**, recordatorio «Certamen 1 Cálculo II» 10:00 | say, notif. | vence lleno «Certamen… a las 10:00» pero `false`: «no hay bloqueo ni preferencia que requiera intervención inmediata» | idéntico | Lo bloquea la frase de BEAT_RULES «Si juega, está en llamada o viendo algo, interviene sólo por un motivo **1, 2 o urgente**», que deja fuera al motivo 3, y el modelo no ve «urgente» en 20 min. Además, la hora llega en ISO (`2026-10-16T10:00:00-03:00`) y el modelo tiene que restar contra `now`. **Estable, de presentación.** |
| **P016** ausente | ausente 15 min, clase grabada en YouTube sonando, memoria «ve las clases grabadas en YouTube» | act `media.control`, notif. | sin motivos → `false` | idéntico | Ningún motivo cubre «algo que corre y se pierde sin nadie». Hoy además la App **retiene `media.control`** en el latido (`f2a9c1b7e`), así que pausar sería *propose* y el juez lo daría por malo igual. Ver §3. |
| **P020** llamada | llamada Discord + Spotify; memoria «cuando entra a una llamada prefiere que la música se pause» | act media/volumen, notif. | preferencia «ninguna» aunque el análisis la cita; `false` | preferencia «media playing: Spotify» (mal llenada) → INT → `media.control` pause ✔ | El campo `preferencia` se llena mal: el análisis ve la preferencia y el campo dice «ninguna». La corrida verde acertó por casualidad. Con la retención actual, `media.control` sería *propose*; solo `audio.app.volume.*` seguiría contando como *act*. |
| **P023** recordatorios | 19:00, **viendo** Netflix; pidió «recuérdame a las 7 pagar la luz»; recordatorio vence 19:00 | act `notification.schedule` (hoy `schedule.alarms` create) | vence lleno, `false` («no hay acción que haya pedido») | INT → `memory.recall`×4 → say «Ya es la hora de pagar la luz.» | En p13 lo bloquean la cláusula de foco y el campo pedido mal llenado («ninguno» con el pedido a la vista). En nb-r2 hizo lo útil (una notificación), pero la escena pide *act*. Además repitió `memory.recall` aunque BEAT_ACT dice «no lo busques». La etiqueta es dudosa (§3). |
| **P024** red | ausente 40 min, red caída, perfil «VTR-Casa»; memoria «deja descargas de Steam cuando sale» | act `wifi.connect.named`, notif. | INT → `web.search` «VTR-Casa wifi conectado» (sin red) → `wifi.connect.named` ✔ | preferencia y bloqueo llenos, pero `false`: «no hay indicio de que esté saliendo ahora» | En nb-r2 leyó mal la actividad: `ausente` e `idle_min=40` no le dijeron «salió». En p13 el primer paso fue `web.search`, que hoy la App **retiene** (ReachesTheNetwork), así que ese camino hoy sería *propose* y fallaría. |
| **P025** mensajes | libre; «cuando termine el render avísale a la Cata por WhatsApp»; export terminado | propose `message.send`, voz | propose `message.send` ✔ (catálogo viejo) | **act** `message.draft` (contó como molesta) | `message.send` ya no existe (`catalog_equivalence`: `op: null`). Con el juez actual la escena queda **excluida**. Hoy `message.draft` lo retiene la App (SendsInputToAWindow), o sea que sería *propose*, que es lo correcto en el producto. No es de presentación (§3). |
| **P026** batería | trabajando en Word sin guardar, batería 8 % sin cargador | say, voz | INT → `memory.recall`×4 → say ✔ | INT → **act** `system.settings.set {airplane_mode:1}` | Actuó en vez de avisar: activó modo avión sin pedido ni preferencia. BEAT_ACT dice «si hay que hacer algo de bajo riesgo, hazlo», y la regla 1 de BEAT_SYSTEM («llámala sin pedir permiso») empuja a actuar. |
| **P034** descargas | libre; hace 12 min «avísame cuando termine de bajar el pdf de física»; descarga terminada | say, voz | pedido «ninguno»; análisis «ya terminó… **cumpliendo** lo que la persona pidió» → `false` | INT → ask_user «¿Quieres que te envíe el archivo…?» (cuenta como say ✔) | Trampa de redacción: «pedido = qué te pidió antes y **se cumple** ahora». El modelo lee «se cumple» como «ya está cumplido, no hay nada que hacer». La corrida verde acertó con una frase rara. |
| **P035** noche | 01:50 libre en Reels; memoria y recordatorio: clase a las 08:30 | say, voz | vence lleno «Clase de Cálculo (…08:30)», `false` | idéntico | Con la regla actual («vence ahora o muy pronto») la decisión del modelo es coherente: faltan 6 h 40 min. Ningún motivo cubre «trasnochar antes de un compromiso temprano». **Estable**, y la más arriesgada de arreglar (§2-G). |

### Aciertos de baja calidad (el juez los da por buenos)

- **P012**, en las dos corridas: el campo pedido sale «ninguno», pero aun así interviene. La respuesta es un ask_user: «¿Quieres que le conteste al correo de Rojas?» y «¿Quieres que te avise que el profe Rojas ya respondió…?». El autor pidió que le avisaran, no que le preguntaran.
- **P004 nb-r2**: dice «BAXY: … **voy a cerrar** las pestañas de Chrome». Anuncia una acción que no hizo, con un prefijo «BAXY:».
- **P004 p13**: propone en texto «¿Quieres que cierre las 62 pestañas?».

### Patrones en las 40 decisiones

1. **Motivo lleno pero `intervenir=false`**: P015, P023 y P035 (vence), y P024 nb (bloqueo y preferencia). El análisis repite «no hay pedido, preferencia ni bloqueo», como si `vence` no contara.
2. **Campo pedido o preferencia mal llenado aunque el análisis lo ve**: pedido en P012 (ambas), P034 p13 y P023 p13; preferencia en P020 (ambas).
3. **En los silencios también hay campos llenos**: P030 (preferencia «lofi para programar») y P032 (vence «Llamar al dentista», en 3 h). Hoy los salva el juicio final de `intervenir`. Por eso **no conviene** hacer `intervenir` mecánico («true si hay algún motivo lleno») sin antes limpiar esos campos (§2-A2).
4. El segundo paso usa ask_user como forma de «decir» algo y a veces actúa sin que nadie lo respalde (P026).

## 2. Cambios de presentación propuestos

Todos son texto del prompt o formato del momento, o protocolo/inferencia. No añaden listas, vetos ni pasos en código.
Orden sugerido para la A/B: **B → C → A1 → D → E**. G va aparte. Cada brazo debe correr en PC **y** notebook con `--src`,
y la condición de aceptación es 23/23 silencios en ambas máquinas.

### Fuentes de diseño

- **Horvitz, *Principles of Mixed-Initiative User Interfaces* (CHI 1999)**, <https://www.erichorvitz.com/chi99horvitz.pdf>. Actuar solo cuando el valor esperado supera al de no hacer nada, considerar la atención del usuario al decidir el momento, y que el coste de molestar sin necesidad es real. Respalda que un compromiso a 20 min sí justifique interrumpir aunque juegue, mientras uno a 3 h no.
- **Amershi et al., *Guidelines for Human-AI Interaction* (CHI 2019)**, <https://www.microsoft.com/en-us/research/blog/guidelines-for-human-ai-interaction-design/>. La G3, «Time services based on context», dice que el momento de actuar o interrumpir depende de la tarea actual. Respalda que la cláusula de foco nombre explícitamente lo crítico en tiempo.
- **ProactiveBench, Lu et al. (ICLR 2025)**, <https://arxiv.org/abs/2410.12361>, y **PRISM**, <https://arxiv.org/abs/2602.01532>, ambos citados en el README. La falsa alarma es el error caro y el umbral debe subir con su coste. Por eso cada cambio de abajo **acota** un motivo (menos de una hora; «un gusto no cuenta») en vez de ampliarlo.
- **Pu et al. (CHI 2025)**, <https://arxiv.org/abs/2502.18658>. La proactividad interrumpe el flujo y conviene adaptarla a lo que el usuario está haciendo.
- **OpenClaw heartbeat**, <https://docs.openclaw.ai/gateway/heartbeat>. «Keep it tiny… to avoid prompt bloat» y «Do not infer or repeat old tasks». Respalda cambiar palabras sin alargar mucho.
- **Fatemi et al., *Test of Time* (ICLR 2025)**, <https://arxiv.org/abs/2406.09170>. Los LLM fallan en aritmética temporal. Respalda dar los tiempos ya relativos, como ya se hace con «hace N min» en la conversación.
- **Liu et al., *Lost in the Middle***, <https://arxiv.org/abs/2307.03172>. Lo que queda en medio del contexto se usa peor. Respalda acercar la evidencia de cada motivo a su instrucción.
- **Tam et al., *Let Me Speak Freely?* (EMNLP 2024)**, <https://arxiv.org/abs/2408.02442>. El JSON restringido degrada el razonamiento y el razonamiento libre seguido del formato lo conserva. Respalda que el segundo paso reciba los motivos como prosa y no como JSON (§2-E), coherente con lo observado en P023.
- **Qwen3.5-4B, model card**, <https://huggingface.co/Qwen/Qwen3.5-4B>. No da guía de *system prompt* para el modo sin pensamiento. Para tareas generales recomienda `temperature=0.7, top_p=0.8, top_k=20, presence_penalty=1.5`, y dice que el historial debe llevar solo la salida final, que es lo que ya hace la mente.
- **Qwen function calling**, <https://qwen.readthedocs.io/en/latest/framework/function_call.html>. Plantilla estilo Hermes, «the messages should contain as much available information as possible» (su ejemplo pone la fecha en el mensaje del usuario) y «It is not guaranteed that the model generation will always follow the protocol». Respalda poner los hechos legibles en el mensaje y no esperar que el modelo los derive.

### A. Definiciones de los motivos (BEAT_DECIDE)

Objetivo: P034, P012, P023 (campo pedido), P020, P008, P024 (campo preferencia), P015 y P023 (campo vence), P002 (campo bloqueo).

Actual:
```
pedido = qué te pidió antes y se cumple ahora, o «ninguno»; preferencia = qué preferencia suya aplica ahora, o «ninguna»;
vence = qué vence ahora o muy pronto, o «nada»; bloqueo = qué la bloquea o le hará perder trabajo, o «nada»;
analisis = en una frase, qué está pasando; intervenir = true si algún motivo es real, false si no.
```
Propuesto (A1, conserva el juicio final):
```
pedido = qué te pidió en la conversación para cuando pasara algo que acaba de pasar («avísame cuando…», «recuérdame…»),
o «ninguno»; preferencia = qué recuerdas que quiere que pase en una situación que se da ahora («cuando…, quiere…»; un
gusto no cuenta), o «ninguna»; vence = qué recordatorio o evento vence en menos de una hora, o «nada»; bloqueo = qué la
bloquea o le hará perder trabajo y qué dato de arriba lo muestra, o «nada»; analisis = en una frase, qué está pasando;
intervenir = true si algún motivo aplica ahora y no se lo avisaste ya, false si no.
```
- Por qué: «se cumple» es ambiguo y P034 lo leyó como «ya está cumplido». Los ejemplos entre comillas son texto del prompt, no listas en código. «Un gusto no cuenta» separa la preferencia accionable de P020 y P008 del gusto de P030 y P039, que deben callar. «Menos de una hora» saca a P032 (3 h) y deja a P015 (20 min) y P023 (ahora).
- Riesgo para silencios: **bajo, y debería bajar**. Los silencios con campos llenos (P030, P032) quedan fuera por definición. P021 y P036 siguen cubiertos por «no se lo avisaste ya». Hay que vigilar P009 («los sábados no tiene clases») y P017 («estudia en la biblioteca los jueves»): son hechos, no «quiere que pase».
- **A2** (solo si A1 deja vacíos los campos de P030 y P032 en ambas máquinas): `intervenir = true si escribiste un motivo distinto de «ninguno»/«nada», false si no.` Ataca el patrón 1 de §1, pero **riesgo alto** mientras los campos se llenen de más.

### B. Cláusula de foco y motivos 1-3 (BEAT_RULES)

Objetivo: **P015, P023** (estables o casi), P034 y P012.

| Actual | Propuesto |
|---|---|
| `1. Algo que la persona te pidió antes y que ahora se cumple (avisarle, recordarle, enviar algo).` | `1. Algo que la persona te pidió para cuando pasara algo, y eso acaba de pasar (avísame cuando…, recuérdame…, cuando termine mándale…).` |
| `2. Una preferencia suya que recuerdas y que aplica a lo que está pasando ahora.` | `2. Algo que recuerdas que quiere que pase en una situación («cuando…», «si…»), y esa situación se da ahora. Un gusto suyo no es un pedido.` |
| `3. Un recordatorio o evento que vence ahora o muy pronto.` | `3. Un recordatorio o evento que vence en menos de una hora.` |
| `Si juega, está en llamada o viendo algo, interviene sólo por un motivo 1, 2 o urgente.` | `Si juega, está en llamada o viendo algo, interviene sólo por un motivo 1, 2 o 3, o si algo está por cortarle lo que hace (batería o disco que se acaban), y sólo con un aviso corto.` |

- Por qué: en el texto actual, «urgente» deja fuera al motivo 3 justo cuando la persona está ocupada. Así P015 y P023 (p13) llenaron vence y callaron. El criterio 4 del README pide exactamente esa excepción («certamen en 20 min, disco que corta una grabación, batería que se va»).
- Riesgo para silencios: en práctica, **ningún** silencio con la persona jugando, viendo o en llamada (P003, P006, P009, P010, P013, P018, P022, P029, P038) tiene un recordatorio a menos de una hora, ni batería o disco críticos. P038 (pico de ping recuperado) no entra en «batería o disco». El riesgo está en *sealed*: un recordatorio de menos de una hora sin importancia, mientras juega, pasaría a notificación. Eso es coherente con la regla del README, así que el riesgo es aceptable.

### C. Cómo se dice el momento (`beat_message`)

Objetivo: **P015, P023, P035** (tiempos), **P008, P024, P016** (ausencia) y P002 (dato de la papelera).

1. **Hora y recordatorios relativos**, igual que ya se hace con `hace N min` en la conversación:
   - `Momento: viernes 2026-10-16T09:40:00-03:00 · la persona está: jugando`
     → `Momento: viernes 16/10, 09:40 · la persona está: jugando`
   - `Recordatorios: Certamen 1 Cálculo II (online) (2026-10-16T10:00:00-03:00)`
     → `Recordatorios: Certamen 1 Cálculo II (online) (hoy 10:00, en 20 min)`. Para P023 diría «vence ahora (19:00)», para P032 «en 3 h» y para P035 «hoy 08:30, en 6 h 40 min».
   - Es formato de un dato que ya está, el mismo que la App muestra para la historia. No decide nada.
2. **Ausencia en la línea del momento**: `la persona está: ausente` → `la persona está: ausente (no toca el PC hace 95 min)`, usando el `idle_min` que la App ya manda (`HeartbeatMoment.Machine`). Hoy ese dato queda al final de la línea PC, separado del estado. En P024 nb el modelo no relacionó «ausente» con «sale» y en P008 p13 no vio «dormido».
3. **Línea PC legible por sufijo**, sin diccionario de palabras: `_pct` → «N %», `_gb` → «N GB», `_min` → «N min», `_` → espacio, y `True`/`False` → «sí»/«no». Por ejemplo, `recycle_bin_gb=28` → `recycle bin 28 GB` y `plugged=False` → `plugged no`. Así el dato coincide con «Empty the Windows Recycle Bin» y con lo que dice BEAT_ACT. La App no manda el tamaño de la papelera (§3), así que para P002 esto solo ayuda en el banco.
4. *(Medir aparte.)* **Orden**: Momento, *Cambios desde el último latido* (lo que despertó el latido), Al frente, Ventanas, PC, y al final Conversación, Lo que recuerdas y Recordatorios, en el orden de los campos del JSON (pedido, preferencia, vence), pegados a las reglas. Base: *Lost in the Middle* y el orden de lectura de los campos.

- Riesgo para silencios: C1 y C2 son bajos (P005, P037: una ausencia corta o un regreso no tienen motivo). C3 es nulo. C4 es desconocido, por eso va en un brazo propio.

### D. Segundo paso (BEAT_ACT): avisar, hacer o proponer

Objetivo: **P026 nb** (modo avión), **P004 nb** («voy a cerrar»), P012 y P034 (preguntas en vez de aviso), **P002** (herramienta), P023 (repetir `memory.recall`). Solo corre si `intervenir=true`, así que **no toca los silencios**.

Actual:
```
Interviene ahora según tu análisis; lo que recuerdas de la persona ya está arriba, no lo busques. Si basta con avisarle
algo (lo que pidió saber, un recordatorio que vence, una alerta), díselo en una frase sin usar herramientas. Si hay que
hacer algo de bajo riesgo, hazlo con su herramienta. Lo de alto riesgo (…) no lo preguntes en texto: llama a su
herramienta y el sistema le pedirá el sí a la persona antes de hacerlo. Nunca escribas en sus ventanas ni digas que
hiciste algo que no hiciste. Háblale de tú.
```
Propuesto:
```
Interviene ahora según tu análisis; lo que recuerdas de la persona ya está arriba, no lo busques. Si basta con que sepa
algo (lo que pidió saber, algo que vence, una alerta), díselo en una frase, sin herramientas y sin preguntarle. Haz tú
con su herramienta sólo lo de bajo riesgo que un pedido o una preferencia suya pide, o reconectar lo que se cayó; si no,
avísale. Lo de alto riesgo (borrar, vaciar la papelera, enviar un mensaje, apagar o reiniciar, cerrar o forzar el cierre
de una app) no lo preguntes en texto: llama a la herramienta que quita la causa que viste arriba y el sistema le pedirá
el sí antes. Nunca escribas en sus ventanas ni digas que hiciste o harás algo que no hiciste. Háblale de tú.
```
- Por qué: el criterio 2 del README dice que una acción la vuelven esperable una preferencia o un pedido. Las escenas *act* de práctica que siguen siendo posibles (P007, P020, P024, P027, P028) tienen ese respaldo o son reconectar. P026 y P004 son *say*, sin respaldo. «Sin preguntarle» evita el ask_user en P012 y P034. «Harás» ataca el «voy a cerrar» de P004. «La herramienta que quita la causa» empuja a P002 desde «disco lleno» hacia la papelera.
- Riesgo: P016 pasaría a *say*, pero hoy no se puede acertar igual (media.control retenido, §3). Para P002 cabe un *say* («tu disco está lleno») en vez de *propose*: hay que medirlo.
- Opcional, **D2**: quitar también de BEAT_SYSTEM la regla 1 («llámala sin pedir permiso») y la 3 (ask_user), que son reglas para cuando alguien pide algo. Es el mismo mecanismo que ya se midió con `_ASKED_IF_DONE` (31 → 34). Hay que confirmar que el prefijo cacheado del latido sigue siendo uno solo.

### E. Protocolo: que el segundo paso lea los motivos, no solo el análisis

Hoy `beat()` pasa al segundo paso solo `decision["analisis"]` como texto del asistente. Los motivos que el modelo ya escribió («bloqueo: disco lleno…», «pedido: avisarle a Cata…») se pierden. Propuesta: el texto del asistente sea el análisis seguido de los motivos llenos en prosa, por ejemplo `«… Motivo: pedido: avisarle a Cata por WhatsApp que ya está el video.»`. Sigue sin ser JSON, que es lo que causó el problema de P023, y está respaldado por *Let Me Speak Freely?*. Objetivo: P002 (con C3 y A, el campo bloqueo traería «papelera 28 GB»), P023 y P034. Riesgo nulo para silencios.

### F. Inferencia: medir el margen, no solo el voto

P008 y P023 cambiaron de decisión con el **mismo prompt** entre PC y notebook. Propuesta: pedir `n_probs`/logprobs del token `true`/`false` de `intervenir` y guardarlo en la traza. Una escena con margen chico es frágil aunque salga bien, y con el margen se ve si A, B o C la alejan del borde sin depender de la suerte del backend. También conviene que `warm()` cachee `BEAT_SYSTEM`: el primer latido relee el sistema (P001 `prompt_n` 973 contra unos 500). Es solo rendimiento.

### G. Opcional y arriesgado: P035 (trasnochar)

Añadir al motivo 3: `… o, si ya es de madrugada, algo suyo de mañana temprano.` Con C1 («hoy 08:30, en 6 h 40 min») le serviría al modelo. Riesgo **medio** para *sealed*, que tiene 5 escenas de noche: en una de madrugada en la que estudia o trabaja con un compromiso temprano podría esperarse silencio. Recomiendo medirlo en un brazo propio y aceptarlo solo con 23/23 en las dos máquinas.

### Qué escena ataca cada cambio

| Cambio | Escenas | Riesgo para silencios |
|---|---|---|
| B (foco y motivos 1-3) | P015, P023, P034, P012 | bajo |
| C1, C2 (tiempos relativos y ausencia) | P015, P023, P035, P008, P024 | bajo |
| A1 (definiciones) | P034, P012, P020, P008, P024, P002 | bajo, mejora P030 y P032 |
| D (avisar, hacer o proponer) | P026, P004, P012, P034, P002, P023 | nulo |
| E (motivos al 2.º paso) | P002, P023, P034 | nulo |
| C3 (PC legible) | P002, P026 | nulo |
| F (margen) | P008, P023 (diagnóstico) | nulo |
| G (madrugada) | P035 | medio |
| A2 (intervenir mecánico) | P015, P023, P024, P035 | alto si no se limpian antes los campos |

## 3. Lo que no es presentación

1. **La lista de retenciones de la App choca con las etiquetas *act*.** Desde `f2a9c1b7e` (19:39), `SendsInputToAWindow` incluye **`media.control`**, y ya incluía `window.minimize`, `window.minimize.all`, `browser.control` y otros. El juez (`heartbeat_holds`) los lee y los cuenta como *propose*. Consecuencias:
   - **P016** (`ops_any` = solo `media.control`) **no se puede acertar** como *act*.
   - **P020** solo puede acertar con `audio.app.volume.*`.
   - El README nombra como *act* «pausar media» y «minimizar». Si *sealed* tiene escenas así (10 *act*), no se pueden cumplir.
   - Además, `web.search` está retenido (ReachesTheNetwork), así que el camino que siguió p13 en P024 hoy daría *propose*.
   - Hace falta una decisión de diseño: o la App deja correr esas operaciones en el latido, o las escenas aceptan *propose* para ellas.
2. **El juez no modela las confirmaciones del kernel.** `RiskPolicy.Evaluate` pide confirmación también según la invocación: `ShellMayChange`, `ReachesAPerson`, `CannotBeUndone`, `LosesTheSession`, `MayCloseAWindow`, y además `email.send` y `calendar.event.create`. El `robocopy` de P002 en p13 (`shell.command.run`, riesgo `low_reversible`) contó como *act*. En el producto el kernel lo frenaría con `needs_confirmation`, o sea que sería una propuesta. El juez debería contar como *propose* lo que el kernel desafía, o la App retener `shell.command.run` en el latido.
3. **`message.send` se retiró del catálogo** (`catalog_equivalence.json`: `"message.send": {"op": null}`), así que **P025 queda excluida**. El 32/40 de p13 usó un catálogo viejo. En el producto actual, lo correcto es `message.draft`, retenido como propuesta. Conviene reetiquetar P025 con `ops_any: ["message.draft"]`.
4. **P023 pide algo que el producto ya hace solo.** La App obtiene los recordatorios de `schedule.alarms list` (`MainWindowViewModel.PendingRemindersAsync`) y esos «suenan en este PC» (descripción de `schedule.alarms`). El README dice lo mismo en P032: «ya sonará a su hora». El *act* esperado (`notification.schedule` → `schedule.alarms create`) crearía un duplicado. Lo que hizo nb-r2 (*say* por notificación) es lo útil. Propongo `kind: say`, canal notificación.
5. **P002 depende de datos que la App no observa y su cuenta no cierra.** `HeartbeatMoment.Machine` solo manda `gpu_busy`, `ram_pct`, `battery_pct`, `plugged`, `disk_free_gb`, `internet` e `idle_min`: no hay `recycle_bin_gb`. Tampoco existe el evento «download failed»: `Heartbeat` solo anota `app opened`, `internet connectivity`, `battery below 20/10 %`, `user idle`, `file appeared in Descargas` y `tick`. Y 4 GB + 28 GB = 32 GB, menos que los 35 GB que pide: vaciar la papelera no destraba la descarga.
6. **Las escenas traen un momento más rico que el del producto.** Campos `screen_text` (quitado de la mente en `9e3c4536c`), `proc_top`, `output_volume`, `brightness`, `spotify_volume`, `wifi_profiles_in_range`, `unsaved_windows`, `not_responding_s`, `latency_ms` y `network` (la App manda `internet`). Eventos «media playing», «call started», «reminder due», «calendar:», «new email», «message arrived», «battery critical», «ram above 95 %», «export finished» y similares, que la App no produce. Lo que se ajuste con estas escenas puede no transferirse al producto. Hay que decidir si la App debe observarlos o si las escenas deben usar solo los campos y eventos de la App.
7. **El canal no coincide.** El juez y el README usan voz para `libre` **o `trabajando`**. La App habla solo con `libre` (`HeartbeatMoment.Speaks`) y `Activity()` **nunca devuelve `trabajando`**. Las escenas P004, P014, P017, P026, P027, P030 y P039 usan una actividad que el producto no produce.
8. **P005**: dice `ausente` con 6 min de inactividad; la App marca ausente recién a los 10 min (`AwayAfter`). Es menor, porque la escena es de silencio.
9. **El juez es laxo con *say*.** Cualquier texto vale: preguntas que ofrecen acciones no pedidas (P012 en las dos corridas, P034 nb), anunciar «voy a cerrar» sin hacerlo (P004 nb) o el prefijo «BAXY:». Habría que revisar las respuestas con el juez de falsedades.
10. **Decisión de diseño**: `system.settings.set` (modo avión, no molestar) es `privacy_sensitive` y corre solo en un latido. P026 nb activó modo avión mientras la persona trabajaba.
11. **Comparabilidad**: p13 y nb-r2 difieren en el momento (`screen_text`), el catálogo, la versión del juez y el hardware (§0). Para separar ruido de efecto, hay que volver a correr la base con HEAD en las dos máquinas antes de medir los brazos.
