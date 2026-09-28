# Goal v2 — Fase 3.5b «comprensión natural» (2026-09-28)

Sustituye como goal a `PROMPT_OPUS_COMPRENSION_NATURAL_2026-09-25.md`, que sigue valiendo como detalle de método
(F0–F6, conjuntos, oro, puntuador). Lo redactó la sesión revisora a pedido del dueño, después de leer los 34 mensajes
del dueño en la sesión d9cf3ea0 y la síntesis de sus 135 mensajes en las 8 sesiones C03
(`%LOCALAPPDATA%\BAXY\comprension-2026-09-25\DUENO_sintesis.md`). El bloque de abajo es el texto de `/goal`; el anexo
son las reglas completas y se lee entero al empezar y tras cada compactación.

## Texto para `/goal`

```
Goal: Fase 3.5b «comprensión natural». Reglas completas: artifacts/comprobaciones/C03/GOAL_COMPRENSION_NATURAL_v2_2026-09-28.md
(léelo entero al empezar y tras cada compactación; junto con AGENTS.md y documentacion/00_IDENTIDAD.md).

BAXY, un compañero tipo Jarvis en el PC, entiende a CUALQUIER persona (español de cualquier país, inglés, spanglish,
erratas, dictado), en la app real y mensaje tras mensaje: hace lo que el catálogo hace, pregunta sólo lo que de verdad
falta, dice sus límites en llano y nunca inventa un efecto ni un dato.

Cierra cuando, con el FINAL sellado corrido UNA vez en la ventana oficial y revisado por un revisor independiente:
total ≥ 85 %, sueltos ≥ 88 %, seguimientos ≥ 80 %, 0 inventados, ⚠ ≤ 1 %; y además guion del dueño ≥ 53/60,
held-out ≥ 29/30, cien 100/100, reserva MASSIVE ≥ 88 %, capa A ≥ 96 %, 742 sin cambios sin revisar, Full verde,
latencia visible p50 ≤ 3 s y lo fácil ≤ 5 s, VRAM ≤ 4 096 MiB; informe COMPRENSION_NATURAL_<fecha>.md,
SEMANTICA.md al día, commit y push (nunca merge a main). Hoy: DEV-B 80,2 % (sueltos 74,4, seguimientos 87,9),
guion 51/60, cien 96/100, reserva 86,2 %. El hueco son los SUELTOS.

Cómo trabajas: sin parar ni esperar ocioso (mientras algo corre, investigas, preparas y mides lo siguiente; notebook y
redpc trabajando a la vez); varios recordatorios siempre (latido de trabajo cada 5 min, de estado cada 12, uno a la
hora estimada de cada fin más uno de respaldo, y un vigía por tarea); subagentes sin límite cuando sirvan, verificando
que funcionan y borrando sus worktrees; decides con el estado del arte (papers, documentación, experiencias reales),
sin mandar nunca datos del dueño ni del producto a la web; heredas lo ya hecho en esta rama y en los BAXY anteriores
antes de construir; un cambio a la vez, medido (DEV-A se mira, DEV-B sólo la cifra, confirmación en un DEV-C nuevo,
FINAL una vez); lo que no mueve nada se retira. Informas al dueño sin que pregunte, en español, con cifras y tablas
cortas, y actualizas su página de progreso en cada informe. Sólo preguntas lo marcado PREGUNTAR en el anexo.
Nunca: cerrar VS Code, reiniciar/apagar/cerrar sesión, matar procesos por un patrón corto, enviar/comprar/borrar
de verdad fuera de los canales de prueba, relajar pruebas, git add . / squash / rebase, editar src con una corrida
en marcha.
```

## Anexo — reglas completas

### 1. Dónde estás (2026-09-28 03:00)

- Rama `codex/kiro-goal-c03`, **41 commits locales sin subir** desde el 25-09 (origin en `b7261cc7`). Primer paso:
  push (sin reescribir historia). Desde ahora, **push tras cada mecanismo que entra y al menos una vez por hora de
  trabajo**: un disco o un reinicio no puede llevarse días de trabajo.
- Producto: Qwen3.5-4B + LoRA del decisor `full3` (D22), mecanismos M8–M30 según `COMPRENSION_PROGRESO.md`.
  Estado por fase, decisiones D1…, investigación y revisión independiente: `COMPRENSION_PROGRESO.md`,
  `DECISIONES_COMPRENSION_2026-09-25.md`, `comprension-f1/INVESTIGACION_2026-09-27.md`,
  `comprension-f1/REVISION_INDEPENDIENTE_2026-09-27.md`.
- Seguimientos de conversación ya sobre la meta (87,9 % en DEV-B). **El hueco son los mensajes sueltos (74,4 % contra
  88 %)**, luego el guion del dueño (51 → 53), la cien (96 → 100) y la reserva (86,2 → 88).

### 2. Lo que el dueño quiere de BAXY (no negociable)

- Un Jarvis que vive en el PC y hace lo que se le pide; «entenderle a la primera siempre», a cualquiera y no sólo al
  dueño («el problema es darle el Baxi a otra persona que no hable como yo»). Español, inglés y spanglish.
- Funciona en la **app real, un mensaje tras otro**; lo que sólo funciona suelto o sólo con la forma de hablar del
  dueño no cuenta como entendido.
- Las 742 son la especificación y los ejemplos de los que generalizar; los límites están en la encuesta y en la
  documentación. «Son capacidades, no límites»: nunca un límite falso a algo que el catálogo hace.
- Habla corto, cálido y seguro («conciso y de una»); la búsqueda web es invisible (nunca «según tal página» ni
  «busqué en internet»; el dato sigue saliendo sólo de lo que dicen las páginas). «Eso no lo hago» para los límites.
- Latencia lo más cerca posible del tiempo del propio modelo; lo sencillo nunca más de 5 s.
- Corrige lo mal oído (la errata suele ser del oído de BAXY). Volumen o brillo relativo sin cantidad → pregunta
  cuánto. Confirma sólo lo destructivo. Nunca inventa que hizo algo, nunca actúa sin que se lo pidan, nunca manda
  datos fuera; modelo local; la personalidad vive en el prompt (no se afina).
- Generalizar, no parchear: nada de reglas por frase ni por app, listas de apps en duro ni capas o routers apilados;
  un regex vale si cubre una forma general. «Hacer más con menos» (ley 2).
- El LoRA del decisor tiene que servir también al **computer use** que viene: entrenado para lo que BAXY hace en su
  totalidad, no sólo para estos conjuntos.

### 3. Cómo quiere que trabajes

- **Sin parar.** Nunca esperes ocioso a que termine un entrenamiento, una medida o redpc: en ese tiempo investigas,
  analizas fallos de DEV-A, preparas datos, escribes pruebas, lanzas subagentes y evalúas la siguiente opción. Si
  redpc está ocupado, el notebook trabaja a la vez, y al revés. Nunca termines un turno ofreciendo seguir cuando nada
  bloquea.
- **Recordatorios múltiples, nunca uno solo:** un latido de trabajo cada 5 min que te pone a trabajar, un latido de
  estado cada 12 min, un recordatorio a la hora estimada de cada fin más uno de respaldo después, y un vigía en
  segundo plano por tarea larga que avisa al terminar. Antes de prometer una hora, mide la velocidad real (redpc se
  frena si el dueño lo usa).
- **Recursos al máximo, con criterio:** permiso total para subagentes (investigación, escritores de sala limpia,
  etiquetadores, revisores, documentación, herramientas). Comprueba que cada uno produce lo pedido; borra su
  worktree al fusionar (31 llenaron C: una vez) y vigila el disco.
- **Estado del arte, siempre:** antes de decidir un método (entrenamiento, datos, decodificación, arquitectura),
  busca papers, documentación y experiencias de usuarios reales, y cita las fuentes en la decisión. Nunca mandes
  frases del dueño, conjuntos ni datos del producto a la web.
- **Heredar antes de construir (ley 1):** revisa lo que ya resolvieron los commits de esta rama desde la 3.5, la
  biblioteca y los BAXY anteriores (skill `evidencia-baxy`) antes de escribir algo nuevo.
- **Método:** un cambio a la vez, con regla prerregistrada; DEV-A se mira, DEV-B sólo su cifra; veto a cualquier
  acción inventada; lo que no mueve nada se retira (balance de líneas y reglas en cada commit de lectura).
- **DEV-B está gastado:** se ha usado para decidir más de 20 mecanismos, así que su cifra ya está algo ajustada.
  Antes de F5, construye un **DEV-C** nuevo (≈250 turnos, mismas reglas de F1, sala limpia, sin nada ya visto ni
  nada del entrenamiento) y confirma allí; DEV-C se usa para confirmar, no para iterar. El FINAL sigue sellado y
  se corre una sola vez.
- **Datos de entrenamiento limpios:** nunca DEV-A/B/C, FINAL, 742, guion, held-out ni registro real; las etiquetas
  minadas se auditan (un tercio de AJUSTE5 salió dudoso) antes de entrenar.
- **Probar como un usuario:** la cifra que manda al final es la de la app oficial, mensaje tras mensaje, con
  mensajes nunca vistos.

### 4. Informes al dueño

- Sin que pregunte (tuvo que pedirlo más de 20 veces): al entrar o salir cada mecanismo, al terminar cada
  entrenamiento o medida larga y, como mínimo, cada 2–3 h de trabajo.
- En español, cifras y no narrativa: porcentaje de avance, qué se hizo, qué falta, en tablas cortas; veraz y no
  superficial; explica cualquier cifra que parezca contradictoria.
- Actualiza en cada informe su página de progreso (mismo enlace, publicada con `url`):
  https://claude.ai/artifact/WGrkjuE4jhsEsX87b4MbYW
- Cuando haga falta que otro agente o PC haga algo (redpc, SSH), dale un prompt completo, listo para copiar y
  pegar, y sigue trabajando.

### 5. redpc (RTX 4060 Ti 16 GB por SSH/Tailscale)

- Entrena allí (LoRA autorizado, D13). Si el SSH cae o el dueño apaga el PC: rescata el checkpoint, dale un prompt
  para su agente del SSH y sigue con el notebook. Avísale cuando redpc quede libre (tiene pendiente limpiar
  OpenSSH, que puede pedir reinicio: sólo él decide cuándo).

### 6. Límites duros

- No se toca el catálogo, los riesgos ni el motor de computer use (`fable/computer-use-engine`); nunca merge a
  `main`. Confirmación ligada a la invocación exacta; cero respuestas visibles fijas; nada afirmado sin verificar.
- VS Code nunca se cierra (ventana guardia en todo guion con efectos). Ningún reinicio, apagado, suspensión ni cierre
  de sesión (mira si hay reinicio pendiente antes de corridas largas). Nunca matar procesos por un patrón corto:
  ruta completa y lista antes de detener (un `*m32*` mató 54 procesos). Ningún llama-server huérfano antes de medir.
- Volumen, micrófono y brillo se leen antes y se devuelven como estaban (el audio del dueño está en 0 silenciado:
  se deja así).
- Envíos reales de prueba sólo a WhatsApp «Música», Discord «Ron92» y la casilla de pruebas; ninguna compra,
  borrado real ni llamada.
- Nunca relajar pruebas (skip, xfail, umbrales) para dar verde. Nunca `git add .`, squash ni rebase; nunca editar
  `src` con una corrida en marcha.
- VRAM ≤ 4 096 MiB de pico con el contexto real en la RTX 3060 Laptop (6 GB físicos; el tope es del dueño).

### 7. PREGUNTAR (sólo esto)

- Adoptar un modelo con licencia no comercial (xLAM u otro).
- Cualquier cosa que cambie la identidad de BAXY o una decisión sellada del dueño.
- Idioma: sigue español + inglés + spanglish (el dueño preguntó el 25-09 por «sólo español» y no decidió).

### 8. Si el FINAL queda corto

Entre 80 y 85 %: se informa como parcial, con la causa limitante medida (por ejemplo, el techo del modelo en sueltos)
y qué haría falta. No hay otra ronda sobre el FINAL; una ronda nueva exige un conjunto nuevo sellado.
