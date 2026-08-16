# Meta vigente de BAXY

Estado: **vigente desde 2026-08-01**. Sustituye cualquier enunciado de objetivo
anterior. No sustituye el contrato de producto ni la decisión de arquitectura:
los presupone.

El estado ejecutable del MVP del 11 de agosto, con su recuperación de contexto,
está indexado en [00_MVP_2026-08-11.md](00_MVP_2026-08-11.md). Es un adelanto y
no reduce los criterios de cierre de esta meta.

La baseline operativa vigente del MVP es
[00_MVP_CONSOLIDADO_2026-08-11.md](00_MVP_CONSOLIDADO_2026-08-11.md), medida en
la campaña de tarde del mismo día. Sobre el árbol final cerró la compuerta Full
(11/11 etapas, **3.799 pruebas .NET** y **7.976 Python + 446 subpruebas**, cero
fallos), ambos perfiles de hardware —GPU 45/45 con VRAM pico 3.065,6 MiB de
3.072; CPU 45/45 con RAM pico 5.807,2 MiB de 8.192— y los dos cortes de
exactitud que dependían de este árbol:

- **Corte A** sobre un oráculo R2 fresco: **169/169**, 31 familias, es 80/80,
  en 39/39 y spanglish 39/39, con cero efectos inseguros. Partido por causa:
  recuperación 1,0 y **decisión cruda 0,9747**. Con 169 casos la cota binomial
  unilateral al 95 % es 0,982, así que **no** se declara el 99,9 % del corte.
- **Corte C**: R4 se abrió una sola vez y cerró 2/6 misiones. Se aisló la causa
  —una cláusula dependiente perdía la cabeza de su cláusula gobernante—, se
  reparó y se volvió a medir sobre un **R5 disjunto**: **6/6 misiones y 25/25
  pasos verificados**, con cero efectos ambiguos. R4 no se reutilizó para
  ajustar.

En el camino se cerraron dos pérdidas de conservación que habrían ejecutado un
subconjunto silencioso de la misión pedida, una de ellas preexistente. También
quedó documentado que el congelamiento del árbol wake ya estaba roto antes de
esa campaña, de modo que el `source_quality_full` declarado por el ledger del
mediodía no era cierto para ese árbol.

El MVP está entregado y medido. La **meta general no** está cumplida: siguen
abiertos los cortes B y D sobre este árbol, la voz física, la wake word y el
ciclo limpio de instalación.

La compuerta física wake v17 ya se abrió una sola vez el 11 de agosto dentro
de su ventana autorizada. La captura RAW cerró 48 positivos y 96 negativos en
602,8 s, sin reintentos, con correlación mínima 0,317, SNR mínimo 42,69 dB,
cero audio pre/post retenido y cero efectos. El recibo combinado autoritativo
quedó **rechazado**: 46/48 positivos, 0/96 falsas activaciones, p50 0,407 s y
p95 1,008 s. Identidades, fuentes, disyunción y efectos pasaron; falló sólo
`positiveHitsExact`, por dos candidatos acústicos que la verificación léxica
rechazó. No se ajustaron umbrales, no se repitió la captura y wake sigue sin
promoción. La evidencia y los cinco SHA-256 están en R87 del registro de
mantenibilidad.

Como diagnóstico posterior, el mismo candidato congelado se midió contra el
corpus físico v20 ya abierto, capturado antes de v17 y con cero fuentes en
común. Cascade y la fusión cerraron 48/48 y 0/96, con p95 cascade 0,684 s;
endpoint cerró 27/48 y 0/96. Esto es evidencia de desarrollo, no promoción:
confirma que v17 expuso una esquina léxica concreta, pero no borra su rechazo
ni autoriza ajustar con esos dos fallos. R88 conserva el prerregistro y hashes.

Una medición adversarial posterior encontró una segunda causa que impide
promover el candidato congelado: sobre el corpus físico abierto de confusiones
de endpoint, cascade aceptó 16/24 positivos pero produjo **10/96 falsas
activaciones**. Seis provinieron de interpretar la frase española literal
`vas y ...` como alias dividido, una de aceptar `basic ...` sin el gate
acústico de 4,0 y tres de la ruta log-mel dependiente sólo del upstream físico
expandido. El rescate `basic` condicionado al gate existente pasó de forma
aislada —1 positivo, 0/96 negativos confusables y 0/28.539 OpenSLR—, pero una
defensa léxica aplicada a la ruta expandida fue rechazada: quitó sus tres
falsas activaciones, dejó las siete léxicas y perdió 12/48 positivos de v20.
No se leyó v17, no se modificó el runtime y esa defensa no se adoptará. R89
conserva programas, prerregistro, resultados y hashes; wake sigue abierto por
cobertura y seguridad.

El cambio de enfoque acústico open-vocabulary también quedó medido y
rechazado. HyperSpotter Conformer cerró, respectivamente, 10/24, 21/48 y
38/48 positivos en los corpus abiertos endpoint-confusable, v20 y humano v14,
con 14/96, 5/96 y 19/96 falsas activaciones. HyperSpotter Whisper mejoró la
cobertura a 19/24, 36/48 y 42/48, pero empeoró la seguridad a 25/96, 18/96 y
32/96. No se ajustó el umbral 0,5, no se leyó v17 y ninguno modifica ni puede
promover el runtime. R90 conserva el programa seguro, los bindings y ambos
resultados. La siguiente línea ya no será otra regla genérica: requiere un
clasificador acústico discriminativo específico de BAXY, entrenado sólo con
fuentes de desarrollo y evaluado después en una campaña física fresca y
disjunta.

La primera comprobación del nuevo enfoque aisló antes los rasgos de prosodia y
forma espectral para no volver a entrenar a ciegas. Sobre 408 audios y tres
folds que dejan fuera un corpus físico completo, ningún clasificador preservó
seguridad y cobertura: el RBF conservador aceptó 0/120 positivos y produjo
13/288 falsas activaciones; los modelos con más cobertura llegaron a 45/120,
48/120 y 67/120, pero con 94, 100 y 180 falsas activaciones. El diagnóstico no
elige candidato ni umbral productivo. R91 conserva programa, binding, pruebas
y resultado. La línea siguiente debe combinar representación fonética
aprendida y prosodia bajo partición por corpus; la prosodia aislada ya quedó
descartada.

La representación fonética aprendida también quedó medida bajo separación por
corpus completo. Se extrajeron de forma reproducible 44.590 frames de 1.024
dimensiones para los 408 audios físicos abiertos usando la capa 2 de un
Wav2Vec2 congelado. Dos clasificadores BAXY-específicos fueron rechazados: el
primero combinó ramas fonética y prosódica; el segundo añadió 4.670 ejemplos
sintéticos exclusivamente al ajuste. Ninguno preservó los positivos actuales
en todos los corpus y semillas, y el segundo mostró una inestabilidad extrema
—por ejemplo, 25/48 frente a 1/48 en v20—. No se congeló candidato ni se tocó
el runtime. R92 conserva extractor, bindings, pruebas, reportes y hashes. El
techo obliga ahora a dejar de clasificar globalmente: la siguiente medición
actúa sólo sobre la ruta de alias dividido responsable de seis falsos `vas y
...`, conservando sin cambios todas las demás rutas.

Dos confirmaciones CTC limitadas a esa ruta también quedaron rechazadas. La
primera exigió una secuencia fonética exacta y eliminó los 10 negativos
divididos, pero perdió 19/19 positivos. La segunda usó el margen QbT 0,5 ya
publicado sobre el intervalo de las dos primeras palabras de Parakeet; conservó
sólo 5/19 positivos y aceptó 8/10 negativos. Ninguna se aplicó al runtime ni
justifica ajustar un margen con estos corpus abiertos. R93 conserva programas,
bindings, pruebas y reportes. La siguiente prueba reutiliza el gate acústico
directo 4,0 ya calibrado y aprobado para `basic`, aplicado exclusivamente al
alias dividido; no introduce un umbral nuevo.

Estado de validación más reciente: el primer oráculo sellado contra el árbol
posterior a las reparaciones abrió en **88/169** y descubrió que los cierres
«con eso termina mi solicitud» / «that completes my request» contaminaban el
retrieval y la decisión. La rama privada de memoria ya está reparada con una
gramática terminal acotada y pasa **16/16** en desarrollo. Como wake v17 fue
rechazado, no liberó el congelamiento: la reparación equivalente de Mind y el
contrato CPU de 120 s siguen preparados, pero no están aplicados al árbol.
La evidencia y la separación por causa están en R69–R71 del registro de
mantenibilidad; ese corpus abierto no se puede reutilizar para promover la
corrección.

El MVP del 11 de agosto está listo y su compuerta integral vigente, repetida
después de la revisión física de presentación, pasó 3.784 pruebas .NET, 7.859
pruebas Python y 443 subpruebas, con cero fallos. La ventana ya identifica el
Qwen 3 activo, nace dentro del área de trabajo y presenta ajustes nativos de
solo lectura sin controles históricos falsos. Una
medición posterior de 90 solicitudes Qwen cerró GPU 45/45, pero dejó roja la
compuerta CPU: el gate impone 19 s aunque el runtime productivo CPU usa 120 s.
El caso fallido respondió correctamente en 12,425 s al repetirlo con el
contrato productivo. No se interpreta como aprobado: el defecto del gate se
repara y la medición completa se repite después de abrir wake v17.

También se midió Qwen3.5-4B Q4_K_M como candidato aislado, sin cambiar el MVP.
Aunque llama.cpp b9980 lo cargó, quedó rechazado: 11 errores semánticos GPU y
12 CPU en la carga de 45 solicitudes por perfil, pico GPU de 3.077,6 MiB y más
RAM y latencia de narración que Qwen3-4B. El modelo activo permanece Qwen3-4B;
prerregistro, medición y rechazo están indexados en el ledger vigente.

Phi-4-mini-instruct Q4_K_M también se midió con el mismo contrato. Entró más
holgado en VRAM, pero falló 3 contratos GPU y 4 CPU y narró más lento que
Qwen3-4B en GPU. Quedó igualmente rechazado. La elección de Qwen3-4B para el
MVP ya no es sólo heredada: venció localmente a los dos candidatos externos.

Qwen3-4B-Instruct-2507 Q4_K_M fue el tercer candidato aislado. Como era más
rápido, se sometió a una comparación sellada A-B-B-A: el activo pasó 180/180
contratos, mientras 2507 cerró 178/180 y repitió exactamente el mismo fallo
GPU de `arguments-06` en ambas corridas. La latencia no compensa una falla
reproducible. Quedó rechazado sin cambiar el manifest; Qwen3-4B sigue siendo
el mejor modelo local demostrado para este MVP.

La adquisición humana STT ya no depende de una descarga manual frágil. Un
plan sellado liga Common Voice SPS4 es/en y Bangor Miami a tres IDs oficiales
de Mozilla Data Collective, y un descargador probado valida identidad, nombre,
tamaño y SHA-256, con reanudación conservadora. Aún no se descargó nada: MDC
exige aceptar los términos en su web y disponer de `MDC_API_KEY`; esta sesión
no tiene navegador autenticado ni credencial. No se abrió audio ni referencias.

Ledger compacto vigente para recuperar la campaña sin leer todo el historial:
`artifacts/fixes/integral_review_ledger_20260811.json`. Este archivo supersede
el ledger del 10 de agosto y enlaza el MVP, el fallo current-tree R1, las
reservas STT y el programa físico wake v17 suplementado.

El cierre inmediato está indexado en dos runbooks: la apertura física exacta
en `documentacion/00_WAKE_V17_RUNBOOK_2026-08-11.md` y la secuencia posterior
en `documentacion/00_POST_WAKE_RUNBOOK_2026-08-11.md`. El estado de los cortes
A–D vive en
`artifacts/development/current_tree_cuts_readiness_audit_20260811.json`: los
cuatro programas están preparados sin abrir sus salidas y D conserva intactos
su prerregistro y claim one-shot; las
tres misiones físicas es/en/spanglish quedaron congeladas en
`artifacts/development/physical_dependent_missions_preregistration_20260811.json`;
su runner físico de texto/voz y el certificador de reparaciones quedaron ligados
en
`artifacts/development/physical_dependent_missions_program_supplement_20260811.json`;
y la restauración sin apertura de la fuente oficial MTOP quedó registrada en
`artifacts/development/mtop_official_test_source_restoration_20260811.json`.
La ruta para cerrar Gate 14 sin tocar el perfil real quedó prerregistrada en
`artifacts/development/clean_lifecycle_local_account_preregistration_20260811.json`:
una cuenta local estándar, efímera y ligada por SID debe demostrar perfil y
ventana aislados antes de ejecutar el gate; todavía no se creó ninguna cuenta
ni se ejecutó Setup.
Ninguno de esos prerregistros equivale a aprobación: sus recibos planeados
siguen ausentes hasta ejecutar cada compuerta una sola vez bajo su contrato.

---

## 1. El norte

BAXY es un asistente local para Windows que se siente como Jarvis de uso diario
en un PC normal. La persona habla o escribe cualquier cosa, en español, inglés o
spanglish, y BAXY lo entiende, lo hace, comprueba que pasó y lo cuenta en una
frase. Sin nube, sin APIs de pago, sin enviar datos a ningún lado.

La sensación de Jarvis no viene de terminar rápido. Viene de que **nunca hay
silencio muerto**, de que **nunca miente** y de que **entiende a la primera**.
Esas tres son el producto.

---

## 2. Invariantes — no se re-derivan

Esto es arquitectura, no tecnología. Se conserva pase lo que pase.

1. **El catálogo tipado es la única fuente de operaciones.** Texto, corpus,
   skills, UI, modelos y prompts no pueden agregar una operación ni elevar su
   autoridad. La mente propone; el kernel autoriza; el provider ejecuta.
2. **Nada se afirma sin verificar.** Un resultado sólo se declara cuando un
   verificador independiente confirma el estado observable. "Se envió el
   comando" no es "se completó la misión".
3. **Estados terminales honestos.** `pending` significa exclusivamente
   reintentable. Un efecto externo ambiguo no reintentable es `failed` terminal
   con `effectMayHaveOccurred`, y no se replanea ni se repite a ciegas hasta
   reconciliar el estado.
4. **La confirmación se liga a la invocación exacta**, no a la intención
   aproximada.
5. **Journal y replay** sobre respuestas terminales.
6. **Cero respuestas visibles fijas.** El modelo formula cada mensaje. Una
   constante de fallback en pantalla es un defecto de producto, no un
   degradado aceptable.
7. **Local y privado por defecto.** La persona puede inspeccionar, corregir y
   borrar todo lo que BAXY sabe de ella.

---

## 3. Todo lo demás se re-deriva — y es obligatorio hacerlo

**Nada de la pila actual es un compromiso.** El modelo decisor, su tamaño,
cuantización y runtime; el mecanismo de tool calling; el recuperador y el
shortlist; el reconocedor determinista; el planner; STT, wake word, VAD y TTS;
la memoria, el retrieval y el grounding; la estrategia de computer-use. Todo
está permanentemente en revisión.

La tecnología de hoy no es la de hace seis meses. **El agente tiene autoridad
total para reemplazar cualquier pieza por el mejor estado del arte disponible
en el momento en que trabaja**, y la obligación de comprobar cuál es ese estado
del arte en vez de asumirlo.

### Procedimiento obligatorio antes de adoptar cualquier pieza

1. **Investigar el presente, no la memoria.** Leer documentación oficial
   vigente, releases, papers y benchmarks del momento. La memoria del agente
   está desactualizada por construcción; tratarla como hipótesis, nunca como
   hecho.
2. **Medir en esta máquina.** Un benchmark ajeno no autoriza nada. Se mide
   sobre el hardware real de BAXY, con su corpus y su carga.
3. **A/B físico con árbol congelado**, orden ABBA, y publicación del artefacto.
4. **Publicar también lo rechazado y por qué.** Un candidato descartado con
   mecanismo entendido vale tanto como uno promovido.
5. **Un techo obliga a cambiar de enfoque, no a seguir puliendo.** Cuando una
   línea deja de dar ganancias medibles, se investiga la alternativa
   arquitectónica, no se le sacan milisegundos.

---

## 4. Criterios de aceptación

### 4.1 Exactitud — cuatro cortes, cuatro oráculos ciegos

Un solo número global sobre un corpus congelado premia el overfitting. Se mide
por población, con oráculos regenerables que **jamás se usan para ajustar**.

| Corte | Población | Barra |
|---|---|---|
| **A — Núcleo autenticado** | Familias y operaciones del catálogo, formulaciones vistas | **> 95 %** exactitud exacta de intención y operación |
| **B — Generalización** | Paráfrasis y formulaciones **no vistas** de esas mismas capacidades, es / en / spanglish | **> 90 %**, con trayectoria publicada hacia 99 % |
| **C — Misiones compuestas** | Objetivos que exigen concatenar operaciones dependientes | **> 90 %** de planes completos, verificados y sin paso huérfano |
| **D — Población abierta real** | Cualquier cosa que una persona diga, incluyendo lo que cae fuera del catálogo | **100 % duro**, ver abajo |

**Barras revisadas el 2026-08-15** por decisión del responsable del producto:
A pasa de ≥ 99,9 % a **> 95 %**, B de ≥ 95 % a **> 90 %** y C de ≥ 95 % a
**> 90 %**. El corte D **no se toca**: no se mide por acierto sino por
honestidad, y sus tres ceros —0 efectos no solicitados, 0 éxitos no verificados,
0 respuestas visibles fijas— son invariantes, no umbrales.

Consecuencia que conviene tener presente: con A en 95 % sobre 169 operaciones,
hasta ocho pueden fallar sin que el corte lo detecte, así que la advertencia
original sigue en pie por otra vía — **un fallo sistemático de una familia
entera no cabe en ese margen aunque la aritmética lo permita**, y se trata como
defecto abierto aunque el porcentaje pase.

El corte D no se mide por acierto. Se mide por honestidad, y no admite margen:

- **0 efectos no solicitados.**
- **0 éxitos no verificados.**
- **0 respuestas visibles fijas.**
- Cuando la petición cae fuera de lo que BAXY puede hacer: abstención o
  aclaración útil formulada por el modelo. Nunca una operación inventada,
  nunca un efecto "parecido", nunca una constante.

**El 0,1 % de margen de A existe para no fingir un 100 %, no para tolerar una
familia rota.** Un fallo sistemático de una familia entera no cabe en ese
margen aunque la aritmética lo permita.

### 4.2 Toda tasa se parte por causa

Ninguna cifra de exactitud se reporta agregada. Siempre partida en:

- **recuperación** — la operación correcta ni siquiera llegó a ofrecerse;
- **decisión** — estaba ofrecida y el modelo eligió mal;
- **vetos** — se decidió bien y una compuerta posterior retiró el efecto.

Los tres tienen arreglos opuestos. Un número mezclado manda el siguiente cambio
al blanco equivocado.

### 4.3 Latencia — el reloj es la primera señal

| Tramo | Objetivo |
|---|---|
| **Primera señal** — acuse, inicio de habla o de acción visible | **p50 ≤ 1,0 s · p95 ≤ 2,0 s** |
| Acción simple completa y verificada | p50 ≤ 2,5 s |
| Voz: fin de habla → primera señal | p50 ≤ 1,5 s |
| Misión compuesta | Sin techo fijo. Narración de hito cada ≤ 3 s de trabajo sin salida visible |

O la **mejor frontera Pareto demostrable**, si se prueba que el techo es
inalcanzable sin ceder exactitud o seguridad — con el rechazo documentado y
medido, nunca asumido.

### 4.4 Presupuesto de hardware

- **Perfil certificado: GPU de 4 GB de VRAM.** Todo lo residente entra en ese
  presupuesto. Voz y STT corren en CPU y no consumen VRAM.
- **Perfil CPU: ≤ 8 GB de RAM.** Misma barra de exactitud y **misma barra de
  seguridad** — BAXY nunca miente ni actúa distinto por correr en CPU. Sólo
  tarda más, con techos propios, publicados y medidos. Caída automática cuando
  no hay GPU o cuando la GPU está ocupada por el usuario.
- BAXY no le pelea la máquina a su dueño. Si hay carga interactiva pesada en
  primer plano, cede recursos.

### 4.5 Voz

Wake word y transcripción que funcionen de verdad en español, inglés y
spanglish, con acentos reales y en la sala real del usuario — no sólo sobre
audio limpio de laboratorio. La calidad se mide contra voces diversas en
holdout, no contra la voz del desarrollador.

---

## 5. Disciplina de medición

Reglas pagadas con corridas perdidas. No son sugerencias.

1. **Nunca medir sobre el corpus que el componente ya posee.** Infla todo. El
   holdout es ciego, congelado y nunca se usa para ajustar.
2. **Leer los textos visibles, no sólo las decisiones contractuales.** Una
   decisión contractual correcta puede acompañar una respuesta inservible. Toda
   compuerta de turno lee `reply_text` y busca constantes conocidas.
3. **Congelar el árbol antes de un probe.** Editar código con una corrida en
   vuelo la invalida: las sesiones posteriores ejecutan código distinto. Si hay
   que editar, se mata la corrida, se borra la telemetría parcial y se relanza.
4. **Instrumentar el crudo.** Qué se le ofreció al modelo y qué propuso *antes*
   de que cualquier veto lo toque.
5. **La igualdad exacta contra un baseline sólo puede aprobar variantes donde
   el baseline ya acertaba.** Cuando un cambio *corrige* una respuesta, la
   puerta es un oráculo, no el modelo anterior.
6. Todo dataset y artefacto se regenera desde scripts versionados.

---

## 6. Lo entregable no tiene bugs

BAXY se entrega **sin bugs**. No "con defectos conocidos documentados", no "con
pendientes menores", no "con un fallo heredado que ya venía de antes". Sin
bugs.

Como "no existe ningún bug" no se puede demostrar, la barra operativa es otra,
exacta y sí demostrable:

> **Cero defectos conocidos abiertos en el entregable.** Todo defecto que una
> prueba, compuerta, probe, corrida física o lectura de artefacto haya sacado a
> la luz se cierra **arreglándolo**. Un defecto ya surfaceado no admite ninguna
> otra forma de cierre.

### Formas prohibidas de "cerrar" un defecto

- bajar el umbral de la compuerta que lo detectó;
- marcar la prueba como `skip`, `xfail` u omisión;
- moverlo a una lista de pendientes o de *known issues*;
- reetiquetarlo como limitación ambiental;
- declararlo fuera del alcance de esta pasada;
- envolverlo en un fallback que lo oculta en lugar de repararlo;
- justificarlo porque es antiguo, ajeno, heredado o caro.

**Un fallo heredado sigue siendo un fallo del entregable.** Que ya estuviera
ahí antes de esta pasada no lo saca del producto que la persona recibe.

### Bug frente a limitación ambiental

Esta frontera es el único hueco por donde se escapa un entregable roto, así que
es estricta:

- **Limitación ambiental** — la causa está **fuera del código de BAXY** y BAXY
  no puede repararla: no hay GPU, no hay micrófono, el certificado de firma no
  está comprado, el sistema operativo no expone la API. Se nombra una por una,
  se cubre con un degradado honesto y medido, y se declara en la entrega.
- **Bug** — todo lo demás. Si la causa vive en el código, el contrato, el
  prompt, el corpus, el modelo elegido o cualquier configuración que BAXY
  controla, es un bug. Difícil, caro o viejo no lo vuelve ambiental.

Toda omisión ambiental existente se re-audita una por una bajo esta definición
antes de la entrega. Las que no la cumplan pasan a ser bugs y se arreglan.

### Casos vigentes que este criterio alcanza

No son ejemplos hipotéticos: son los que hoy están abiertos.

- La compuerta física wake v17 ya se abrió una sola vez y quedó rechazada por
  cobertura positiva: 46/48, 0/96 y latencia dentro del contrato. Además, el
  corpus confusable abierto expuso 10/96 falsas activaciones; wake no está
  promovida.
- La gramática terminal equivalente de Mind sigue pendiente por el congelamiento
  anterior a v17. Después exige regresiones metamórficas y un R2 ciego distinto
  de R1.
- `measure_mind_budget.py` fuerza el timeout HTTP de 19 s de GPU también sobre
  CPU. El producto respondió correctamente al caso diagnóstico con 120 s, pero
  la compuerta completa continúa roja hasta reparar el contrato y repetirla.
- Los cortes current-tree A–D, la voz física completa y las misiones compuestas
  físicas todavía no están cerrados sobre oráculos frescos.
- ~~El ciclo limpio actual carece de un Setup atestado del árbol final y de una
  cuenta o VM Windows desechable.~~ **Retirado del alcance el 2026-08-15**: no
  hay cuenta ni equipo desechable disponible, así que este punto no se mide, no
  cuenta como pendiente y no bloquea la entrega.

### Casos de esta lista ya cerrados

- El launcher y su descubrimiento asíncrono vigente tienen prueba actual y las
  compuertas Fast/Full verdes.
- Las condiciones de omisión relevantes de esta máquina se ejecutaron de forma
  focalizada: 10/10 .NET y 34/34 Python, con 0 omitidas.
- La ruta visible excepcional de `message.compose` ya no publica una constante
  ni pierde confirmaciones: conserva una cola ordenada y sólo publica prosa
  formulada y validada por el modelo. Sus cuatro pruebas focalizadas y la
  compuerta integral posterior están verdes.

---

## 7. Definición de terminado

**Decisión de disciplina de sellado, 2026-08-15.** Un preregistro sellado se
audita por la **integridad de su sello**, no por su regeneración desde el árbol
presente. La regeneración exacta se exige mientras el sello está vivo; una vez
consumido, o una vez que una de sus entradas versionadas cambia legítimamente,
el artefacto se conserva como evidencia histórica y deja de exigírsele que un
constructor actual lo reproduzca. Un sello que puede reconstruirse desde el
estado de hoy no está sellando nada. Esta decisión gobierna las nueve pruebas
que R279 dejó abiertas y **no** autoriza relajar ninguna otra comprobación:
quien la aplique debe verificar el hash publicado del artefacto, no omitir la
prueba.

**Alcance retirado, 2026-08-15.** La instalación limpia y el primer arranque en
cuenta o VM desechable salen de la definición de terminado por decisión del
responsable del producto.

La meta **no** se declara cumplida hasta que, simultáneamente:

- **cero defectos conocidos abiertos**, según la sección 6;
- las compuertas de fuente cierren verdes — **toda compuerta en rojo bloquea la
  entrega**, sin excepción y sin nota al pie;
- los cuatro cortes de exactitud cierren sobre oráculos ciegos regenerables;
- las misiones compuestas se ejecuten end-to-end **por texto** en la máquina
  física, abriendo el producto y verificando efectos reales. La ejecución por
  voz queda diferida junto con el resto de la superficie de voz;
- los perfiles GPU y CPU cierren ambos, cada uno contra sus techos;
- y las únicas limitaciones restantes sean **ambientales según la definición
  estricta**, explícitas, cubiertas y nombradas una por una.

Un preflight en `failed`, un falso positivo inseguro o una constante visible en
pantalla bloquean el cierre por sí solos, sin importar cuánto haya mejorado el
resto.

**Reportar el estado con fidelidad.** Si algo falla, se dice con su salida. Si
un paso se saltó, se dice. "Terminado" sólo se escribe cuando está hecho y
verificado.

---

## 8. Autonomía

Autoridad total delegada. Decidir sin consultar, ejecutar, medir, publicar el
resultado — incluido el negativo. No pedir aprobación para avanzar, no delegar
decisiones técnicas, no detenerse en el primer error.

Detenerse sólo ante un bloqueo real: algo que no se puede obtener desde el
repositorio, la máquina o la documentación pública.

**Lo mejor para BAXY, siempre.**
