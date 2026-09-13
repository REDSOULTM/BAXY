# Por qué las categorías de mayor masa están condicionadas — 2026-09-13 (Fable)

Orden por abiertos tras MESSAGING1140 (204/742). «Llegan» = resuelven en el reconocedor
determinista con la fuente actual (`scratchpad/c03-open-mass-by-reach.py`, baseline
regenerada en `BASE/C03-recogniser-baseline.json`). Ninguna condición se inventa aquí: cada
línea remite a la evidencia que la demostró. Una categoría condicionada no se salta: se
mide en cuanto la condición se resuelva o el dueño decida.

| Categoría | Abiertos | Llegan | Condición demostrada | Reanudación |
|---|---:|---:|---|---|
| Música | 33 | 19 | 12 Spotify condicionados a reconciliar el efecto incierto 962 (inv88672a39…) y a sesión/login real (`C03-music1083-proposal/PLAN.md`); lecturas H0224/H0543 exigen sesión SMTC real pausada con título largo y el parche MUSIC1127 está sobre llm antiguo (base aaa434, requiere rebase a 5ab7f598…) (`C03-music1127-repair/REVIEW.md`); «pará la música»/pausa exigen reproducción real. Elegibles sin efecto: H0333 y H0421. | Rebase 1127 y observar sesión real; tanda corta de abstención H0333/H0421 con pares. |
| Instalar/desinstalar | 31 | 0 | 10 Steam por título sin pertenencia verificable (INSTALL1128/ELIGIBILITY); Photoshop sin instalador/licencia; desinstalar Discord/Spotify del dueño es efecto destructivo no autorizado; Teams como proveedor incompatible (2). Sólo `instala requests con pip` (H0052) tiene mecanismo `package.install.*` sin condición externa. | Decisión del dueño sobre licencias Steam; H0052 aislado. |
| Web | 29 | 13 | WEB1102: búsquedas reales con resultados irrelevantes y efecto incierto índice2 (inv49443d6e…); WEB1114 sin parche para H0393/H0541; requiere navegador Edge propio del producto (perfil CDP). Sin causa nueva desde 1102. | Hipótesis nueva de relevancia de búsqueda o navegación nombrada (13 llegan: youtube/gmail/github). |
| Archivos | 29 | 3 | Frontera de producto: `filesystem.write.text`/`create.directory` confinados al sandbox (`ProductCatalog.cs:312–317, 490–501`; FILES1005/PLAN.md): «en el escritorio/Documentos» no se cumple sin proveedor nuevo para carpetas conocidas (10 escrituras/carpetas = infraestructura ≥10, declarada, no construida). Borrados (5) sólo con fixtures en carpetas personales, prohibido por FILES1005/1040. Listados (4) sin operación de listado de carpetas conocidas. | Decisión del dueño: proveedor de escritura en carpetas conocidas (≥10 abiertos) o cambiar expectativa. |
| Entrada incompleta | 27 | 0 | DIALOGUE1126: sin reparación justificada para la paráfrasis declarativa; NEXT1132 sólo 2 literales en borrador. | Hipótesis causal nueva en observation_ack. |
| Vídeo y series | 26 | 10 | Netflix (12) exige sesión CDP autenticada del dueño y entitlement (VIDEO1026/PLAN.md); Disney+/Prime sin mecanismo; YouTube (`media.play.youtube`) con efectos de navegador. | Login Netflix del dueño en el perfil del producto; YouTube aparte. |
| Mensajería | 25 | 7 | Tras 1140 quedan literales con destinatario/canal reales: enviar exige clientes y terceros (prohibido enviar por encuesta). Elegibles: aclaraciones y lecturas sin envío. | Panel de aclaraciones restantes sobre llm1136. |
| Apps | 25 | 6 | HUECO_LEXICO_APPS: 4 reparables por léxico tras localizar guardia previa; resto destinos ausentes (Photoshop, Steel, Mortal Kombat), erratas de transcripción con nota del dueño (preguntar/contexto), idiomas fuera de alcance (3 sin marca), compuesto con reloj. Respuesta veraz negativa/aclaración es acreditable si es útil. | Sonda settrace de la guardia + tanda de ausentes/erratas. |
| Audio | 24 | 1 | AUDIO1137: sin parche barato; reconocimiento de dirección/alcance sin cantidad requiere gramática nueva (2 literales). | Diseño acotado en effect_intent. |
| Agenda | 11 | 2 | Resuelta el 2026-09-13: el dueño decidió (DECISIONES_DUENO, punto 3) publicar el segundo entero hacia arriba; reparación TIME1139/SOURCE.json medida en TIME1185 (+2, seis tareas con due == NextRun). Resto del material 1134 medible con el mismo criterio. | Derivar de build_time1185.py; índices 3–9 y 14–24 del material 1134. |

Sin condición externa y con mecanismo demostrado: **notas** (12 abiertos, 8 llegan a
`note.create`/`note.list`, mecanismo demostrado en TASK_NOTE_REPAIR986 con 7/12 y +4),
**conocimiento/identidad/conversación** (sin efectos), **red sólo lectura** (`wifi.status`,
`network.ip.list`, `network.status`), **cierre de apps propias** (CLOSE1060 integrado sin
medir). Se avanza por ahí mientras las condiciones anteriores esperan al dueño.


## Actualización 2026-09-13 (tras las decisiones del dueño)

El dueño respondió las siete decisiones (DECISIONES_DUENO_2026-09-13.md): poder total en este PC (instalar, cerrar apps sin autorización por app), proveedor de carpetas conocidas autorizado, TIME1139 resuelto (medido en TIME1185), renombrado de claves de medidas (medido en SYSTEM1183), IP sin confirmación autorizada, y aplazar lo que exija sesiones ausentes (Netflix/Spotify) al otro PC. Las condiciones de Música y Vídeo pasan de «decisión del dueño» a «aplazado por sesión ausente»; Archivos y Cerrar apps quedan sin condición externa.
