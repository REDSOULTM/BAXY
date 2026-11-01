# Prompt de continuación — dejar BAXY estable (2026-10-10)

Escrito para Claude Opus 5.5 en Claude Code, esfuerzo `high`. Es tu instrucción completa y manda sobre
`PROMPT_CONTINUACION_V3_2026-10-10.md` y `PROMPT_CIERRE_V3.md` en lo que los contradiga. Léela entera antes de actuar.

<mision>
Deja BAXY como un programa terminado y estable, lo antes posible. No lo agrandes.

BAXY es un asistente local de Windows (.NET 10 + mente en Python + interfaz React) que entiende órdenes en español,
inglés y spanglish y las ejecuta, incluido manejar aplicaciones por su interfaz («computer use»). Tras más de 30
rondas de arreglos, cada regla nueva arregló un caso y movió otro: el mismo código da 66 o 68 de 72 según la corrida,
la misma frase se decide distinto según lo que se habló antes, y el redactor llegó a afirmar un envío que no ocurrió.
El autor necesita el programa ya, y prefiere un BAXY que haga menos cosas pero siempre igual y que diga con
honestidad lo que no hace. Por eso esta misión no gana casos nuevos: quita variación, quita lo que sobra y fija los
límites.

El criterio de diseño, en sus palabras: no existe un computer use «mágico», y forzarlo es lo que hizo tan difícil la
misión anterior. BAXY corre con un modelo local de 4B y 4 GB de VRAM; el arnés lo ha acercado mucho a modelos mayores,
pero un 4B no hace lo que hace un 20B. La meta es que BAXY haga, al máximo y siempre, lo que puede hacer con esos
requisitos, no que aparente más. Ante la duda entre añadir una regla para rescatar un caso difícil o declararlo
límite, declara el límite.

Queda fuera la transcripción de voz y la palabra de activación: el autor las desarrolla en repos aparte y las
conectará después. No las toques ni las midas; sólo deja documentado y sin cambios el punto donde se conectan.
</mision>

<identidad>
El producto que entregas es el que describe `documentacion/00_IDENTIDAD.md` (decisiones de diseño; léelo entero en el
arranque). Si una decisión tuya la contradice, cambia la tuya. Lo que más pesa en esta misión:
- **Un compañero tipo Jarvis, un él, que se llama BAXY.** Habla cálido y breve, tuteando, y confirma el estado
  observable: «Listo, Spotify está abierto y sonando». Ni «Listo» a secas ni un párrafo.
- **Cuando falla, plano y con la causa**, sin disculpas. **Cuando no entiende, una pregunta corta.** **«Eso no lo
  hago»** antes que un apaño que casi funciona: los límites de esta misión son esa frase puesta en práctica.
- **Tres cosas que nunca hace:** inventar que hizo algo, actuar sin que se lo pidan, mandar datos del usuario fuera.
- **Para cualquiera, en español, en inglés y en spanglish.** Ninguna decisión se justifica con un gusto personal.
- **Cubrir el PC, no las apps.** El código no nombra ninguna aplicación. Lo propio de cada una (cómo se lanza, cómo
  se llaman sus secciones) vive en ficheros de datos que cualquiera puede ampliar para otra app.
- **Nada se apila.** Una capa nueva retira la que sustituye en el mismo cambio; cero código muerto; una
  responsabilidad por pieza. El refactor de la fase 3 es esta parte de la identidad, no un extra.
- **Honestidad:** la señal temprana no afirma un resultado; la afirmación llega verificada; si la verificación la
  desmiente, BAXY se corrige solo.
Aclaraciones de diseño del 2026-10-10, ya escritas al final de ese documento: se confirma lo que destruye datos y
también lo que sale al mundo; estable antes que amplio; y la velocidad se mide contra el tiempo del propio modelo.

**«Listo» incluye comprobar en vivo, en los dos PC, estas cuatro partes de la identidad:**
1. Vive en la bandeja del sistema, arranca solo con Windows y se queda.
2. Habla siempre: cada respuesta se dice en voz alta, con su voz en español neutro (es la voz de salida; la
   transcripción y la palabra de activación siguen fuera).
3. La memoria se puede ver, editar y borrar entera.
4. El modo bypass (ajuste consciente, a la vista) y el modo accesible de la interfaz funcionan.
Si alguna no funciona, es un rojo de esta misión, no un aplazado.
</identidad>

<decisiones_del_autor>
Tomadas el 2026-10-10 respondiendo preguntas directas. No las reabras; si una resulta imposible, dilo con la medida.
1. **Estable antes que amplio.** Se acepta que la cifra del banco baje (por ejemplo de 67 a unos 60 de 72) si los
   que quedan pasan siempre. Lo que se caiga pasa a límite declarado.
2. **«No molestar», en su forma simple.** La regla que queda es: BAXY nunca escribe ni hace clic en la ventana de la
   persona. Para lo demás puede traer su aplicación al frente mientras actúa y devolver el frente al terminar. La
   maquinaria que sólo existía para actuar por detrás o en pausas se puede retirar si al medir simplifica y estabiliza.
3. **Entrega: los dos PC del autor** (notebook y PC). Instalador y PC limpio quedan para la fase de escalado.
4. **Lo imprescindible** (debe quedar 3/3; es lo que el autor usa):
   - Windows básico: Configuración, Explorador de archivos, Bloc de notas, Calculadora, Reloj, Paint.
   - Spotify: buscar, ir a secciones, reproducir.
   - Discord y WhatsApp: abrir un chat o canal; enviar un mensaje a un contacto (con confirmación antes de enviar);
     leer lo último que le escribieron; en Discord, entrar o salir de un canal de voz (con confirmación).
   - Steam: lanzar un juego instalado; ir a la biblioteca, la tienda o la página de un juego; buscar un juego;
     instalar o desinstalar (con confirmación).
   Office (Word, Excel, PowerPoint) y el resto son «mejor esfuerzo»: lo que no llegue a 3/3 pasa a límite.
5. **Lo imprescindible se consigue con mecanismos genéricos y datos, no forzando la interfaz ni con código por
   app.** Steam casi no expone su interfaz: investiga primero la vía que no depende de ella (lanzar por protocolo,
   datos locales de la biblioteca, las operaciones `game.*` del catálogo) y exprésala como un mecanismo general cuyo
   dato por aplicación vive en ficheros de datos. Lo mismo para WhatsApp y Discord: una operación directa y
   verificable antes que una cadena de clics. Si tras investigar un imprescindible no llega a 3/3 con un mecanismo
   fiable, no lo fuerces ni lo declares límite por tu cuenta: informa al autor con la causa medida y sigue.
6. **Ante un límite:** BAXY lo dice corto, con la causa, y deja a la persona lo más cerca posible por la parte segura
   («Eso no lo puedo hacer; te dejé Word abierto en el documento»). Nunca actúa a medias sin decirlo.
7. **Refactor profundo pero verificado** (fase 3 completa), con el banco y la suite como prueba de que nada cambia.
8. **Confirmación.** En modo Normal BAXY confirma lo que destruye datos (borrar, sobrescribir, cerrar sin guardar) y
   lo que sale al mundo (enviar un mensaje, entrar a voz, publicar, comprar, instalar o desinstalar). En modo bypass
   no pregunta.
9. **Todas las pruebas se corren en modo bypass** (orden de diseño). Como en bypass nada frena un error, las pruebas
   sólo pueden tocar blancos seguros: mensajes únicamente al MD «Ron92» o al canal «Música» de Discord; borrados y
   sobrescrituras sólo dentro de carpetas de prueba creadas por el arnés; cierres sólo de ventanas que abrió la
   prueba; instalar o desinstalar en Steam sólo con «Super Meat Boy», el juego que el autor dejó para estas pruebas; ningún
   otro juego se instala ni se desinstala, y al terminar queda como estaba al empezar. Además, y para no entregar sin probar el modo
   por defecto, un caso por familia en modo Normal que compruebe que la pregunta de confirmación sale y es fiel.
10. **Velocidad: acercarse al máximo al tiempo del propio modelo.** No hay una cifra fija de segundos. Mide por
   turno el tiempo total, el tiempo de modelo y la sobrecarga de BAXY (total menos modelo); la meta es que la
   sobrecarga sea la mínima medible, y se baja quitando capas, nunca añadiendo. Informa las tres cifras.
11. **El modelo local no se cambia** (4B, VRAM ≤ 4 GB): confirmado por el autor. No lo propongas como salida; lo que
   ese modelo no alcance con el arnés es un límite.
12. **La señal antes de 3 segundos se mantiene** como comportamiento de la identidad: si va a tardar, BAXY avisa, y
   ese aviso nunca afirma un resultado.
</decisiones_del_autor>

<arranque>
Sé literal con estos pasos; son los que evitan repetir trabajo.
1. Trabaja desde `%LOCALAPPDATA%\BAXY\cu-v3-docs` (rama `fable/cu-universal-v3`) para documentos y fusiones. El
   checkout principal `%USERPROFILE%\BAXY Definitivo` es el que se mide en vivo.
2. Lee, en este orden: la sección «CIERRE DE SESIÓN» y sus dos añadidos al final de
   `documentacion/computer-use/TRASPASO_V3_2026-10-09.md`; las cuatro últimas filas de `PROGRESO_V3.md`; `AGENTS.md`.
3. Recoge lo que quedó sin juzgar: el banco B de la ronda 30 (`%LOCALAPPDATA%\BAXY\cu-v3\banco_Br30.txt`) y el
   barrido de PC (`D:\BAXYWork\suites_r30b\estado.txt`). El traspaso trae los comandos exactos.
4. Comprueba el entorno: tu propia ventana protegida (ver límites duros); ningún `Baxy`, `baxy-core` ni `llama-server` huérfano en ninguna de las dos
   máquinas; Office cerrado por COM (`cu-v3\cerrar_office.ps1`); `ssh PC` responde.
5. Crea `documentacion/computer-use/ESTABILIDAD.json` (formato abajo) y escribe la fila de arranque en
   `PROGRESO_V3.md` con la hora real (`date +%H:%M`).
</arranque>

<orden_de_trabajo>
Cuatro fases, en este orden. Cada una termina con un commit y una fila en `PROGRESO_V3.md`.

**Fase 0 — Cerrar v3 con lo ya medido (objetivo: pocas horas).** Sin rondas nuevas.
- Juzga el banco de la ronda 30 contra el de la 29 (`comparar_banco.py`; jueces independientes sólo para los casos
  que cambian). Entra a v3 si no pierde ningún caso logrado atribuible a la ronda, no hay falsos éxitos y la latencia
  no sube más de un 5 %. Si no pasa, entra el plan B ya medido: el commit 298cb591a.
- De las ramas `r31`, sólo «libro en blanco» (addde7133) puede entrar, y sólo si una corrida en vivo de u5 y n6 no
  pierde nada. «Efecto incierto» y «mandale es enviar» no entran ahora: van a `documentacion/APLAZADOS.md` con su
  informe.
- Cierre formal según `PROMPT_CIERRE_V3.md` §6, con base `origin/main` 50d5c7ed6: merges `--no-ff` v3 →
  `codex/kiro-objetivo-c03` → `main`; lee `docs/PUBLICACION_Y_DATOS_PRIVADOS.md` y comprueba que no entra evidencia
  privada (si aparece, para y dilo); `scripts/test_source_quality.ps1 -Mode Full` verde sobre `main`; push de las dos
  ramas comprobado con `git ls-remote origin`. Este push está autorizado por el autor.
- Informe final de v3 como artifact, con la cifra real de cada criterio. Las metas no alcanzadas se informan con su
  cifra y su causa medida; no se retoca nada para acercarlas.

**Fase 1 — Medir la variación.** Sin esta línea base, «estable» no significa nada.
- Mismo commit, tres corridas del banco B con estado base limpio; dos corridas de las tandas t1–t4 en PC.
- Vuelca el resultado por caso en `ESTABILIDAD.json`. Los casos que no son 3/3 ni 0/3, y los turnos que cambian
  entre corridas, son tu lista de trabajo.
- Clasifica cada uno por su causa medida: estado que deja el arnés o la corrida anterior; decisión de un modelo en
  empate; carrera de tiempos; memoria de procedimientos que se aprende y se olvida; regla que depende del orden.

**Fase 2 — Estabilizar.** Un caso inestable se resuelve de una de dos formas: pasa a 3/3, o deja de intentarse y BAXY
responde corto, con la causa, que eso no lo hace. Las dos cuentan como éxito; lo que no cuenta es «a veces».
- Primero el arnés: cada caso empieza en un estado verificado y lo deja limpio. Un fallo con estado sucio se repite,
  no se cuenta.
- Donde un lector sin modelo ya prueba la operación en las palabras de la persona, esa prueba decide. La decisión de
  un turno no puede depender del estado de caché que dejó la conversación anterior (ver
  `cu-v3\r26\r31-m1-mandale-borrador.md`, que trae un replay exacto).
- Lo que el suelo determinista de frases sabe decir no lo redacta el modelo. Ningún final afirma algo no verificado.
- La memoria de procedimientos o da el mismo resultado con y sin procedimiento aprendido, o se apaga.
- Valida cada arreglo con tres corridas de los casos afectados, no con una.

**Fase 3 — Refactorizar sin cambiar comportamiento.** Sólo cuando la fase 2 esté medida. Cada paso se comprueba con la
suite completa en PC y una corrida del banco: si cambia la firma de un solo caso, se revierte.
- Parte por responsabilidad los ficheros gigantes: `src/baxy_mind/llm.py`, `src/baxy_mind/computer_use.py`,
  `src/Baxy.App/ComputerUseMission.cs`, `src/baxy_mind/__main__.py`.
- Dos piezas se pueden REESCRIBIR limpias en vez de partirse, si su libro de cuentas lo justifica: el decisor de
  pasos del computer use y la pila de vetos del redactor. Es reemplazo de una pieza, nunca del producto: detrás del
  mismo contrato, con las mismas pruebas, y entra sólo si el banco ×3 iguala o mejora a la pieza vieja, que se borra
  en el mismo cambio. BAXY no se empieza de cero (identidad: «no hay una quinta reescritura»).
- Una sola fuente para la lógica que hoy vive gemela en C# y Python.
- Una lista, un autor y un significado para cada lista de lectura; hoy hay varias con el mismo nombre y usos distintos.
- Libro de cuentas de cada veto del redactor y cada guarda del motor con la evidencia de `cu-v3\`: se retira el que
  estorba más de lo que acierta. El saldo de reglas de la misión debe ser negativo.
- Comentarios que digan qué hace el código y por qué, no la historia de las rondas.
- Limpieza: unos 60 worktrees viejos de agentes, ramas aparcadas, scripts sueltos que deban vivir en `scripts/`.
</orden_de_trabajo>

<limites_de_partida>
El autor ya aprobó (2026-10-10) que BAXY tenga límites realistas. Estos salen de lo medido y son límites desde el
primer día: no gastes tiempo intentando arreglarlos. En cada uno BAXY debe responder corto, con la causa, sin actuar a
medias, y eso sí se comprueba en vivo.
- Arrastrar y soltar; scroll largo en listas virtualizadas; clic derecho sobre un elemento.
- Controles que no entran en lo que ve el modelo (cintas de Office: negrita, insertar tabla y similares).
- Aplicaciones que corren como administrador.
- Tareas de muchos pasos encadenados en aplicaciones fuera de las que cubre el banco.
- Órdenes sin aplicación nombrada («guarda esto») cuando la persona trabaja en otra ventana: se pregunta en cuál.
- Lo que depende de hardware o cuentas que el equipo no tiene (Wi-Fi en un equipo sin Wi-Fi, servicios sin sesión).
La fase 1 puede añadir límites a esta lista (un caso que no llega a 3/3 con un arreglo pequeño y general pasa a
límite); quitar uno exige haberlo medido 3/3.
</limites_de_partida>

<entregables>
- `documentacion/LIMITES_DE_BAXY.md`, para el autor: lo que BAXY hace siempre (por familia, con un ejemplo), y lo
  que no hace y dice que no hace. Sin lista de «a veces»: al terminar no debe quedar ninguno.
- `ESTABILIDAD.json` y un `ESTABILIDAD.md` corto que lo resuma.
- Un documento de una página «cómo escalar desde aquí»: los requisitos que quedaron anotados y el punto de conexión
  de la transcripción y la palabra de activación.
- Traspaso y `PROGRESO_V3.md` al día.
</entregables>

<estado_en_ficheros>
Tu contexto se compactará automáticamente cuando se llene y podrás seguir desde donde ibas, así que no cierres antes
por presupuesto de tokens. Lo que te sostiene entre contextos son tres cosas: git, `PROGRESO_V3.md` (notas libres con
hora) y `ESTABILIDAD.json` (estado estructurado). Actualiza el JSON al terminar cada corrida, con esta forma:

```json
{"commit": "abc123", "banco": {"corridas": 3, "estables_3de3": 0, "limites_declarados": 0, "inestables": 0,
 "casos": [{"caso": "u9", "resultados": ["ok", "fallo", "ok"], "causa": "estado: cursor en el buscador", "estado": "pendiente"}]},
 "tandas": {"corridas": 2, "turnos_que_cambian": []},
 "fases": {"0": "hecha", "1": "en curso", "2": "pendiente", "3": "pendiente"}}
```
</estado_en_ficheros>

<como_trabajar>
El tiempo importa: no gastes tiempo que se pueda evitar, y cuanto antes haya un resultado correcto, mejor.
- **Dos máquinas.** PC (`ssh PC`) compila, prueba y corre agentes; el notebook sólo ejecuta BAXY en vivo. El
  notebook es el cuello de botella: mientras corre un banco, ten agentes analizando o arreglando en PC.
- **Subagentes** para trabajo paralelo e independiente: una causa por rama, un revisor adversarial independiente por
  rama y jueces para lo medido en vivo. Como mucho 3–4 a la vez. Para una búsqueda o una edición de un fichero,
  hazlo tú. Los revisores encuentran más cuando ejecutan funciones puras que cuando sólo leen. Las reglas comunes de
  los encargos están en `cu-v3\encargo_reglas_r26.md`: adáptalas a esta misión antes de usarlas.
- **Juzga sólo lo que cambia:** `comparar_banco.py`, `comparar_tanda.py`, `resumen_lote.py`.
- **Cada cambio retira lo que sustituye** y declara su saldo de líneas. La causa se arregla donde se produce. Nada por
  frase ni por aplicación: los nombres de apps viven en datos y las lecturas en `src/baxy_mind/semantic/`.
- **Tests:** es inaceptable borrar, saltar o debilitar un test; puede esconder una función rota. Si un test fija un
  comportamiento que retiras a propósito, se reescribe para el correcto y lo dices con la evidencia.
- **Investiga antes de afirmar.** No des una causa por buena sin haberla medido; hoy tres hipótesis razonables
  resultaron falsas al medirlas.
- **Git:** commits pequeños en español terminados en `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`;
  nunca `git add .`, rebase ni squash; merges `--no-ff`; para deshacer, `git revert`.
</como_trabajar>

<limites_duros>
El PC es desechable y no hace falta pedir permiso, salvo estos límites, que no se cruzan por ningún motivo:
- Nunca cierres ni mates la ventana donde vives (Visual Studio Code o la terminal desde la que corres): si muere, la
  sesión muere. Antes de la primera corrida en vivo, comprueba que el proceso de ESA ventana está en la lista que el
  arnés y los cierres de BAXY nunca tocan (hoy protege VS Code y Opera); si corres en una terminal, añádela. Las
  pruebas van en bypass: nada más frena un «ciérralo» mal entendido.
- Nunca reinicies, apagues ni cierres sesión.
- Nunca mates procesos por nombre corto: sólo por PID exacto y listando antes. Word y Excel se cierran por COM (matar
  Word por PID lo deja en recuperación y reabre documentos del autor).
- Envíos de prueba sólo a Discord (MD «Ron92» o canal «Música»). Ningún clic que cambie la cuenta. Opera es del autor.
- VRAM ≤ 4 GB, sin modelo de visión. Sólo español, inglés y spanglish.
- En PC no toques el checkout del autor, `C:\ProgramData\ssh`, el firewall, `sshd` ni la tarea «BAXY sshd
  watchdog».
</limites_duros>

<como_terminan_tus_turnos>
Un mensaje sin llamada a herramienta termina tu turno y el trabajo se para hasta que alguien escriba. El autor no
quiere que pares en estos cuatro casos: un resumen largo que anuncia el siguiente paso sin darlo; una oferta de
seguir «salvo que prefieras otra cosa»; una lista de decisiones que, según tú mismo, no bloquean el resto; o decidir
que es buen momento para informar porque el turno fue largo. Las notas de estado van en el mismo mensaje que tu
siguiente llamada a herramienta. Si algo que lanzaste sigue corriendo (un banco, un agente), la tarea no ha terminado.

Las únicas paradas que sí quiere: cuando nada puede avanzar sin él, cuando aparece evidencia privada antes de un
push, o cuando el siguiente paso cruzaría un límite duro. Si tienes una duda que cambia el rumbo, pregúntale una vez
y sigue con lo que no depende de la respuesta.

Infórmale en español, corto, con cifras y con la causa medida de lo que no salga: una línea al empezar cada fase y un
resumen al cerrarla.
</como_terminan_tus_turnos>

<hecho_cuando>
1. v3 cerrado: `main` fusionado, Full verde, push comprobado e informe con cifras reales.
2. Banco ×3 con cada caso en 3/3 o declarado límite; tandas ×2 sin turnos que cambien; cero falsos éxitos y cero
   finales que afirmen lo que no ocurrió.
3. Refactor hecho con las firmas del banco iguales antes y después, y saldo de reglas negativo.
4. `LIMITES_DE_BAXY.md` entregado y cada límite comprobado en vivo.
5. Full verde al final, con skip/xfail sin subir respecto del inicio.
</hecho_cuando>
