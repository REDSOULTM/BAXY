# BAXY Renew — progreso (sesión líder, PC)

Goal: `PROMPT_GOAL_RENEW.md`. Estado estructurado: `metas.json`. Notas del notebook: `PROGRESO-nb.md`.

## 2026-10-15

**Marco.**
- Recordatorio horario (:17) creado con CronCreate; caduca el 2026-10-22.
- Bancos fuera del repo, en `F:\BAXYeval\renew_v1\`: el repo sube a GitHub (público) y los bancos llevan pedidos
  reales del dueño (`historical_missions.jsonl` es privado). El notebook los trae por `scp` cuando los necesite.
- Los bancos sellados los escriben subagentes, para que la sesión que ajusta no los vea:
  - holdout de decisión: los dos holdouts del torneo (40 + 50, nombres de herramienta mapeados al catálogo de Renew),
    una muestra de MASSIVE es/en y una muestra de los pedidos reales del dueño;
  - escenas del instinto: práctica (abierta, 40), sellado (60) y la parte del latido del holdout (10);
  - extremo a extremo: herramientas, computer use, agente y voz, juzgados por el estado del mundo (no por nombres de
    operación, así siguen valiendo si cambian las herramientas); práctica abierta y sellado;
  - falsedades: conversaciones con guion que se auditan contra el journal; práctica abierta y sellado.
- Holdout final = decisión + extremo a extremo sellado + latido sellado; la meta de ≥ 85 % se cuenta sobre el total.

**Choques anotados.**
- `AGENTS.md` dice «subagentes, por defecto no»; el prompt del goal manda usarlos con libertad. Manda el prompt.
- `00_IDENTIDAD.md`: en modo Normal «apagar va directo»; el latido, por decisión del 2026-10-15, siempre propone apagar.
  Se aplica sólo a lo que el latido hace por instinto: un pedido explícito sigue la tabla de modos.
- Traspaso: «el latido se pausa si el dueño juega o la GPU está ocupada» frente a «si juega, sólo una notificación» (y
  escenas de juego que esperan actuar). Decisión: mientras juega se salta el latido periódico de 5 min; un latido por
  cambio (empezó un juego, vence un recordatorio) sí corre, y avisa por notificación.
- Los bancos e2e y de falsedades sellados no traían `SEALED-*.md` del subagente: el líder calculó su sha256 sin abrirlos
  (ficheros sin cambios desde 04:05 y 04:09) y lo anotó en `metas.json`.
- Exposición de herramientas: el dueño pidió «skills a demanda o lo que diga la evidencia, medido contra todas en el
  prompt». Medido (notebook, 270 casos): el 4B nunca llamó a `skill_read`; gana «todas en el prompt con guías».

**Arnés nuevo (commit siguiente a 06c7eb81).**
- Mente: conversación de sesión con llamadas y resultados; `turn.result` con argumentos; `turn.confirm` (botones) y
  `confirm_pending` (respuesta por voz o texto, sin lista de palabras); `turn.continue final`; semilla fija.
- App: `NativeTurnLoop` (kernel → Core → resultado verificado al modelo, hasta 15 movimientos), `MainWindowViewModel`,
  `MindSidecarClient` y conductor reescritos; `POST /confirmation/answer` en el canal de la UI; ~25k líneas de legado
  fuera. Enmascarado de secretos conservado en `SensitiveText`.
- Fusionado del notebook: Piper residente (`voice_output.py`), limpieza de pruebas heredadas, JSON y scripts.
- Humo en el producto real (`F:\BAXYeval\renew_v1\runs\smoke1`): 6 turnos completos; voz empieza 0,9–1,4 s tras el
  texto en turnos de una llamada. Visto: tras `app.close` con `invalid_or_expired_window_id` el modelo dijo «el Bloc de
  notas ya no está abierto» (interpretación falsa) → banco de falsedades.
- Trampa: un perfil del conductor en `F:` falla al preparar el almacén privado (ACL); usar el perfil por defecto en C:.

**Práctica.** `r2-conv-seed` (cases.json): 80/90, p50 0,69 s, VRAM 4,7 GB (sobre el límite). Banco de práctica 2:
`F:\BAXYeval\renew_v1\practica\decision2.json` (270 casos, 131 operaciones).

**Computer use (primera vuelta).** Vista compacta desde el recibo completo (el kernel recortaba a 20 controles),
regla 9 del prompt y descripciones de mirar/clic. Steam → biblioteca en 3 pasos; calculadora y bloc de notas salen en
la práctica e2e. Proveedor: `app.open` de la Calculadora precargada no verificaba (arreglado, prueba nueva).

**Práctica e2e p1 (30 casos, producto real, antes de los arreglos de la tarde): 12/30.** herramientas 5/10, computer
use 3/8, agente 2/8, voz 2/4; voz a los p50 3,1 s (incluye turnos de muchos pasos). Causas: faltan herramientas de
agente con rutas generales (notebook); el runner cortaba la voz al mandar el turno siguiente (arreglado); el reloj se
copiaba al portapapeles (arreglado); `browser.page.read` leía el navegador del dueño (arreglado); el cierre por
presupuesto publicaba XML (arreglado: sin herramientas); E026 «para» → `system.power` bloqueó la pantalla (prompt
pendiente); E015 el oráculo exige ver ≥ 4 juegos instalados y la biblioteca abrió en «TODOS (1426)»: caso dudoso.

**Latido.** Mente en dos pasos (JSON: análisis y si interviene; luego herramientas). Escenas de práctica: un token de
silencio se elegía en 40/40 (57,5 %, todo silencio); con análisis primero 29/40 = 72,5 %, molestas 1/20. App: disparo
cada 5 min y por cambios, momento con señales genéricas, canal por actividad, propuestas retenidas, botones Sí/No.
Probado en el producto (P002 propuesta y «No», P001 silencio). Sin memoria ni recordatorios en el momento todavía: el
modelo los puede leer con sus herramientas.

**Pruebas de Providers:** 5 de `VisibleClick…` fallan en este escritorio (dependen de la ventana real al frente; no
tocan lo cambiado; en el notebook pasan).
