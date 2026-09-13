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
| Archivos | 17 | 15 | Resuelta el 2026-09-13 (decisión del dueño, punto 2): proveedor de carpetas conocidas construido (BUILD1205) y medido en FILES1205 (+12). Restan borrados, listados y contenido dinámico. Frontera anterior: `filesystem.write.text`/`create.directory` confinados al sandbox (`ProductCatalog.cs:312–317, 490–501`; FILES1005/PLAN.md): «en el escritorio/Documentos» no se cumple sin proveedor nuevo para carpetas conocidas (10 escrituras/carpetas = infraestructura ≥10, declarada, no construida). Borrados (5) sólo con fixtures en carpetas personales, prohibido por FILES1005/1040. Listados (4) sin operación de listado de carpetas conocidas. | Decisión del dueño: proveedor de escritura en carpetas conocidas (≥10 abiertos) o cambiar expectativa. |
| Entrada incompleta | 27 | 0 | DIALOGUE1126: sin reparación justificada para la paráfrasis declarativa; NEXT1132 sólo 2 literales en borrador. | Hipótesis causal nueva en observation_ack. |
| Vídeo y series | 26 | 10 | Netflix (12) exige sesión CDP autenticada del dueño y entitlement (VIDEO1026/PLAN.md); Disney+/Prime sin mecanismo; YouTube (`media.play.youtube`) con efectos de navegador. | Login Netflix del dueño en el perfil del producto; YouTube aparte. |
| Mensajería | 25 | 7 | Tras 1140 quedan literales con destinatario/canal reales: enviar exige clientes y terceros (prohibido enviar por encuesta). Elegibles: aclaraciones y lecturas sin envío. | Panel de aclaraciones restantes sobre llm1136. |
| Apps | 25 | 6 | HUECO_LEXICO_APPS: 4 reparables por léxico tras localizar guardia previa; resto destinos ausentes (Photoshop, Steel, Mortal Kombat), erratas de transcripción con nota del dueño (preguntar/contexto), idiomas fuera de alcance (3 sin marca), compuesto con reloj. Respuesta veraz negativa/aclaración es acreditable si es útil. | Sonda settrace de la guardia + tanda de ausentes/erratas. |
| Audio | 24 | 1 | AUDIO1137: sin parche barato; reconocimiento de dirección/alcance sin cantidad requiere gramática nueva (2 literales). | Diseño acotado en effect_intent. |
| Agenda | 4 | 0 | Resuelta el 2026-09-13: el dueño decidió (DECISIONES_DUENO, punto 3) publicar el segundo entero hacia arriba; reparación TIME1139/SOURCE.json medida en TIME1185 (+2, seis tareas con due == NextRun). Resto del material 1134 medible con el mismo criterio. | Derivar de build_time1185.py; índices 3–9 y 14–24 del material 1134. |

Sin condición externa y con mecanismo demostrado: **notas** (12 abiertos, 8 llegan a
`note.create`/`note.list`, mecanismo demostrado en TASK_NOTE_REPAIR986 con 7/12 y +4),
**conocimiento/identidad/conversación** (sin efectos), **red sólo lectura** (`wifi.status`,
`network.ip.list`, `network.status`), **cierre de apps propias** (CLOSE1060 integrado sin
medir). Se avanza por ahí mientras las condiciones anteriores esperan al dueño.


## Actualización 2026-09-13 (tras las decisiones del dueño)

El dueño respondió las siete decisiones (DECISIONES_DUENO_2026-09-13.md): poder total en este PC (instalar, cerrar apps sin autorización por app), proveedor de carpetas conocidas autorizado, TIME1139 resuelto (medido en TIME1185), renombrado de claves de medidas (medido en SYSTEM1183), IP sin confirmación autorizada, y aplazar lo que exija sesiones ausentes (Netflix/Spotify) al otro PC. Las condiciones de Música y Vídeo pasan de «decisión del dueño» a «aplazado por sesión ausente»; Archivos y Cerrar apps quedan sin condición externa.

## Actualización 2026-09-13 (ARRANGE1229)

Organizar ventanas y pestañas pasa de 0/13 a 3/13. Los tres que llegaban al reconocedor (maximizar/minimizar la ventana en primer plano) se midieron sobre una ventana propia; la reparación fue de lectura (deícticos → window.active) porque el producto ejecuta window.maximize/minimize/restore sin confirmación y un inventario habría dejado la elección de la ventana al planificador. Los 10 restantes quedan condicionados con causa: minimizar todo ×3 y «Minimisa ópera.» actúan sobre ventanas del dueño; «traé chrome al frente» depende de SetForegroundWindow desde otro proceso (efecto incierto, no se repite sin una hipótesis nueva); «poné chrome a la izquierda» exige geometría que window.move no infiere; «cambiá a la otra ventana», «enfocá la mejor» ×2 tienen referente indeterminado; «cerrá todas las pestañas de chrome» no tiene mecanismo de pestañas.

## Actualización 2026-09-13 (APPS1231)

Abrir aplicaciones pasa de 29/54 a 34/54: la guardia léxica localizada con sonda settrace (`_is_direct_request` sin clítico ni «abrís/avrí», cortesía final, marco de hora dicha, alias inglés del Explorador) y la pista portuguesa «abre a» ante un nombre de aplicación se repararon y se midieron sobre la Calculadora real. Quedan 20 con causa: Explorador ×2 (verificación del proveedor por proceso nuevo; ventana en el shell) y destinos ausentes ×3 (sin lectura app.installed para software conocido) son reparables en la próxima tanda; compuesto ×1 (final omite la apertura; composición); Steam ×3 y erratas ×4 lanzarían el cliente del dueño (sesión/descargas) o exigen contexto para aclarar; Mortal Kombat ×2 (juego ausente); H0249 indeterminado; H0461 límite sin marca; idiomas ×3 sin marca.

## Actualización 2026-09-13 (APPS1237)

Abrir aplicaciones pasa de 34/54 a 39/54: las dos causas medidas en APPS1231 se repararon y se remidieron (Explorador: identidad de la entrada del shell por proceso y ventanas CabinetWClass, BUILD1237; destinos ausentes: lectura app.installed sobre el nombre de software conocido). Quedan 15: compuesto H0183 (composición de respuesta a efectos múltiples), Steam ×3 y erratas ×4 (lanzar el cliente del dueño o aclarar con contexto), Mortal Kombat ×2 (juego ausente vía game.launch), H0249 (indeterminado), H0461 (límite sin marca), idiomas ×3 (sin marca).

## Actualización 2026-09-13 (AUDIO1239)

Audio y volumen pasa de 27/51 a 39/51. La condición «reconocimiento de dirección/alcance sin cantidad requiere gramática nueva» (AUDIO1137) no aplicaba a los ocho relativos abiertos: la lectura determinista de aclaración ya existía y la regla del dueño (H0027) es preguntar la cantidad, así que sólo faltaba remedirlos y cubrir «suví», «es tarde …», «poné», el nivel absoluto con verbo de dirección y «ponelo en mute». Quedan 12: H0465 (eco del compositor con efecto verificado), compuestos ×2 (H0067 fecha, H0530 brillo sin proveedor), H0652 volumen por aplicación, H0075 «bajá la música» (ambiguo con descargar), H0439/H0713 pronombre sin contexto, idiomas ×4 sin marca.

## Actualización 2026-09-13 (FILES1243)

Archivos y carpetas pasa de 15/32 a 19/32: los borrados con fixtures propios en carpetas personales quedaron autorizados por la decisión del dueño (punto 2, FILES1205) y sólo faltaba el lector de borrado literal (papelera privada recuperable). Quedan 13: listados ×4 (revelarían nombres de archivos del dueño en artefactos públicos; medibles sólo con publicación sin nombres), carpeta ×1 (sin operación de borrado de carpetas), contenido dinámico ×2, comprimir/backup/resumir ×3 (sin operación), ruta suelta, «directorio actual» y recuento compuesto.

## Actualización 2026-09-13 (MEMORY1245)

Memoria personal pasa de 0/10 a 3/10 (afirmaciones sin pedido de persistencia). Condición nueva demostrada para los guardados (4 literales + variantes): la memoria privada está desactivada en un perfil fresco y su activación exige una confirmación de la App (no del kernel), que el instrumento de un turno no puede dar; reanudación con `turn.memory-confirm` en el host y un runner de dos fases (MEMORY1247). Los recuerdos (H0604, H0173) requieren un guardado previo en el mismo perfil: fuera del instrumento de un caso por turno.

## Actualización 2026-09-13 (MEMORY1253)

Memoria personal pasa de 3/10 a 5/10: los dos guardados de nombre (H0157, H0149) con sus variantes en español e inglés. Condiciones demostradas y resueltas en tres tandas: la activación de la memoria privada exige la confirmación de la App (`turn.memory-confirm`, BUILD1249); la finalización del guardado debe llevar el dato recordado y componerse contra el pedido original, no contra «confirmar» (BUILD1249/BUILD1253); el dato se cita sin traducir y el mensaje de fallo memory_disabled no afirma recordar (mente, 772a1671). Quedan 5: los dos guardados de dato (H0452 aprobado sin par por la comprobación literal demasiado estricta del candidato; H0506 y la variante en inglés sin final por la misma causa, corregida para MEMORY1255), los dos recuerdos (H0604, H0173: requieren un guardado previo en el mismo perfil, fuera del instrumento de un caso por turno) y H0174 (modelo).

## Actualización 2026-09-13 (MEMORY1255)

Memoria personal pasa de 5/10 a 7/10: los dos guardados de dato (H0452, H0506) con cuatro variantes de dato en español e inglés. La comprobación del dato recordado exige sus palabras de contenido sin traducir y admite el cambio de persona de la confirmación (mente, 88f5afdf). Quedan 3: los dos recuerdos (H0604, H0173) exigen un guardado previo en el mismo perfil, y el instrumento ejecuta un caso por perfil fresco (un turno más una confirmación); H0174 es calidad del modelo. La categoría queda condicionada por el diseño del instrumento, no por el producto.
