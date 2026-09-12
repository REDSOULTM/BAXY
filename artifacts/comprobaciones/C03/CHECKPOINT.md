# C03 — checkpoint del relevo en la máquina original

**126/742 cubiertos, 616 abiertos, 0 no aplican; 98 altas en la ventana de 24 h heredada; 0/35 categorías cerradas.** C03: 3/11 cumplidos, 5 contradichos, 3 pendientes. Sin estimación fiable de cierre completo. **RAM:** 32530 MiB totales, 11408 MiB libres; el servidor del modelo ocupó 708 MiB de working set en la comprobación de carga. **VRAM:** 16380 MiB totales; carga del modelo decidido con el perfil de producto midió 3513 MiB atribuibles por delta (5528 con servidor, 2015 sin él), bajo la guarda 3800 y el techo 4096. Picos de tanda propios: ninguno, no se ejecutó tanda aquí. **Pruebas omitidas:** suites dueñas, Fast y Full, por instrucción explícita del dueño; omitidas, no verdes. La ventana de 24 h es la heredada (cerrada 2026-09-12T01:51Z): recalcularla exige `verification_updated_at` del registro privado, que no está aquí, y no ha habido altas nuevas.

**Corrección de papeles.** REDPC es el BAXY original; el portátil sólo replicó el repositorio y su raíz en `D:` era porque su `C:` estaba lleno. El tramo de C03 desde el 2026-09-06 se ejecutó en la réplica, así que allí quedaron su evidencia privada y la descarga del modelo decidido. Donde este checkpoint diga «destino», léase esta máquina original.

**Runtime listo con el modelo de la decisión 792.** El modelo decidido no estaba aquí: vivía en `D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/`, carpeta que no existía en esta máquina, y de los 93 GGUF locales ninguno era el correcto —ojo con `assets/models/Qwen3-4B-Q4_K_M.gguf`, que se llama igual que el primer candidato del manifiesto pero el repositorio lo identifica como el modelo activo anterior, Instruct AWQ `7485fe6f…`. Raíz lo restauró desde la procedencia atestada que versiona `artifacts/research/qwen3_4b_instruct_2507_candidate_preregistration_20260811.json` (repositorio de cuantización, revisión fijada `a06e946b…`, Apache-2.0), siguiendo su orden congelado: `.partial`, 2 497 281 120 bytes exactos, SHA `3605803b…` exacto, y sólo entonces renombrado. No es campaña de modelos nueva ni sustitución. `bootstrap.ps1` falló primero con `runtime_lock_invalid` → `installed_missing` porque el venv de la mente estaba desfasado respecto al `pylock` de los 192 commits; instaló `pywebrtc-audio 0.2.0+baxy.1` y `sherpa-onnx 1.13.4+baxy.2` y terminó con «BAXY arranca: los activos obligatorios y el runtime registrado son validos». El modelo y el wake se declararon en el override oficial `assets.local.json`, con copia del manifiesto anterior en `mind-runtime-v1.json.pre-c03-relay.bak` y `wake_on_start` restaurado a `true`. Carga verificada con las banderas exactas de `llm.py:5520-5562`: 3 slots, 4096 por slot, `/health` ok. Es comprobación de runtime, no tanda.

**Relevo activo, no reanudación de la sesión pausada.** Máquina REDPC, raíz `C:/Users/usuario/Desktop/ETC/Programacion/BAXY Definitivo`, `Goal-c03` de `2bf3d4c5` a `ed305c38` por `merge --ff-only` (192 commits), worktree limpio antes y después, sin `reset`/`clean`/borrados, `main` intacta, WIP ajeno conservado (stash goal-10, ramas goal-10 y rewrite-10-11-descartado, tres worktrees en Temp). `2637d864`, `7a015914` y la fuente `20dab7ed` verificados como ancestros del tip. Sin otro escritor, conductor, pytest ni build. Había una instancia de producto del arranque automático de Windows (Baxy 29676, core 20504, llama-server 13588 con granite, cuatro pythons de la mente): cerrada por identidad de ruta, sin tocar aplicaciones del usuario. Compilación Release en el destino correcta, 0 advertencias y 0 errores en 21.46 s con el dotnet global 10.0.100 —aquí no existe `%USERPROFILE%/.dotnet`—, y `baxy-core.dll`/`baxy-core.exe` junto a `Baxy.exe` coinciden con los de `Baxy.Core`. Una compilación correcta no demuestra calidad ni interfaz.

**Bloqueo externo único: el paquete privado no está en esta máquina.** Búsqueda recursiva por nombre exacto de `C03_OPUS5_RELEVO_PRIVADO.zip` y `TRANSFER_MANIFEST.json` en C:/Users, D:, E:, F:, G: y J:, cero resultados; `%LOCALAPPDATA%/BAXY` tiene 1489 directorios pero ninguno `C03-*-private` y su evidencia más reciente es del 6 de septiembre. Sin `requirements.jsonl` no se escribe `verification_status` ni se sella panel nuevo: `SURVEY_TAXONOMY846.json` versionado sólo lleva case_id, categoría y estado, ningún literal. El bloqueo del modelo quedó resuelto por raíz y ya no hace falta trasladarlo. Solicitud exacta en `OPUS5_DESTINO/SOLICITUD_TRASLADO.md`; inventario en `OPUS5_DESTINO/DESTINO_INVENTARIO.json`.

**1025 cerrada en cobertura, abierta en causas.** Sin repetir la ejecución: 14 de 25 casos quedan juzgados (5 pasan, 9 fallan) y 11 esperan su texto terminal. **El crédito de 1025 es 3 y es definitivo**, porque las conductas de descripción de juegos y de comparación ficcional no pueden alcanzar dos variantes pertinentes en pie —dos de tres y una de dos ya fallaron— y KNOWLEDGE998, única tanda anterior de la categoría con adjudicación versionada, sólo cubrió aritmética, conversiones, sustancia/mezcla y estilo humorístico: ninguna variante suya es pertinente. Por eso H0236, H0239 y H0582 siguen open cualquiera sea el veredicto de su literal, y el registro 126 no cambia. Fallos con causa: H0278 fechó el estreno original de Marvel vs. Capcom en 2000 cuando fue arcade CPS-2 en 1998; H0366 atribuyó Doom Eternal a Bethesda Game Studios y 2023 cuando es id Software, Bethesda Softworks y 20 de marzo de 2020; H0424, H0645 y la variante inglesa respondieron con la identidad de BAXY en vez de preguntar el referente; una variante describió a Chell como hombre y Portal como mundos alternativos; Tetris y la comparación inglesa terminaron en composition_failed; dev-03 mezcló definición y error. Ningún fallo se acredita por fluidez. Detalle por caso en `KNOWLEDGE1025/ADJUDICATION_STATUS.json`.

**1024 revisada, no integrada.** `effect_intent.py` en destino es la base declarada (`3bb83dc8…`), inalterada desde `20dab7ed`. La revisión encontró que la puerta real es el `if` de las líneas 3170–3182, que hoy exige el sustantivo `recordatorio` y una cabeza de creación, y que `_time_only_reminder_request` tiene un segundo uso en la línea 13842 como abstención de la ruta de efecto que el diagnóstico 1024 no analiza. No se integra sin ver el diff real, decidir 13842 y medir el subconjunto con controles de aviso sin plazo, aviso con título ya dado y continuación con el título. Detalle en `AGENDA1024/ROOT_REVIEW_DESTINO.md`.

1022: 10literales+10variantes+5límites,21/25cumplen,+10créditos. CPU2,RAMtotal2,RAMdisponible1,RAMusada1,batería4, cada conducta con dos variantes actuales ES/EN. Valores contra recibos system.status frescos;17.18GB son17179869184bytes instalados, noGiB ni memoria libre. RAM usada deriva totalBytes−availableBytes; batería98%real. Cuatro límitesfallan: cita no explicada, condición futura rechazada, concepto convertido en lectura, narración termina en error. Nada mutado. ROOTf3df6a0aa9f101fdfc4dbf499e406bea8428245673364950826168564778cbbb.

Colecciónf42d77 de sesión74955,exit0,pinsintactos,0violaciones;85.75s,VRAM3497.56MiB,RAM2467.25MiB. Créditos escritos después de EXIT, sin atribuir ejecución en vivo. Fuente sin cambios. Siguiente conocimiento1025:10literales+10variantes+5límites ya sellados;28abiertos, delante de sistema19. Agenda1024parche externo recibido, no integrado ni medido; no se adopta una reparación a ciegas.

1021: 7 literales,10 variantes,5 límites; 6/22 cumplen y16 fallan. H0363 suma1: task.list actual vacío y dos variantes ES/EN conformes. Crédito escrito al adjudicar, después de recoger EXIT01416e, sin reclamar adjudicación duranteGPU. El ámbito observado es el perfil real de tareas de BAXY, sin fixtures ni inventario global. Las seis consultas de aclaración fallidas permanecen open con causa.

Fallos: cancelar alarma pregunta cuándo cancelarla en vez de cuál; avisos de30minutos/una hora vuelven a preguntar cuándo y confunden el actor; tarea para viernes llega a task.create inválido; recordar comprar pilas se interpreta como lectura. La invocación e48cd6fe-3264-492f-9f8f-d8b739329c03 conserva failed/invalid_task; effectMayHaveOccurred está ausente, no se interpreta como false. Tres lecturas posteriores del mismo store dieron vacío; no se ejecutó limpieza. Diagnóstico1023 separa las fronteras, reparación1024 sólo para avisos temporales en preparación externa.

1021 terminó exit0, pins intactos,0violaciones,98.25s. VRAM3499.56MiB y RAM2463.06MiB, picos separados bajo4GB; el muestreo de árbol puede incluir descendientes no exclusivos del modelo.85altas/24h supera20 sinFull. Suites/Fast/Full omitidas por orden del dueño, no aprobadas. Fuente20dab7ed y build1013 vigentes, sin cambios durante la tanda.

Siguiente elegible: SYSTEM1022,10literales+10variantes+5límites para CPU/RAM/nivelbatería; hasta10 créditos. Con29abiertos empata agenda29; las categorías de mayor masa conservan sus reanudaciones documentadas1005/1014/1017/1018/NEXT_989. H0675 y nueva infraestructura siguen aparcados. No repetir paneles enteros por fallos aislados ni interpretar efectos inciertos como resueltos.

Audio1016 ejecutó 10 literales, 12 variantes y 5 límites: 14/27 cumplen, 13 fallan. Nueve literales respondieron bien; sólo H0168/H0331 obtuvieron crédito: identificaron el dispositivo real, con variante inglesa actual y variante española previa848-dev-status-03 acreditada en861. La variante española actual falló y conserva su fallo. Los dos estados covered se escribieron al adjudicar, antes de cerrar categoría; no se atribuye adjudicación en vivo, porque EXIT ya existía. Registro108/634, sin inflar con variantes.

1020 reparó cantidad y silencio: 13 objetos originales,9/13 cumplen; en esos mismos objetos1016 había7/13. Los cuatro literales H0027/H0563/H0154/H0549 y sus cuatro variantes actuales ES/EN pasaron, añadiendo4créditos. Los cuatro límites fallidos siguen fallando, sin regresiones nuevas observadas en este material. Fuente1019 integrada en20dab7ed: dos lectores existentes,14inserciones/1eliminación, sin prompt ni respuestas fijas. Covered escrito al adjudicar los ocho casos objetivo antes del resto; EXIT ya existía, no se declara crédito duranteGPU.

Audio1016 y1020 recuperados con lectura fresca del mismoendpoint y tres llamadas cada uno:100silenciado→100sin silencio, igual al baseline observado. No reintentos ni restauración ciega. El worktree1019 se retiró tras integrar; parche y diagnóstico preservados. Preparación histórica1021:7literales de agenda,10variantes,5límites;22casos, hasta5créditos potenciales, runneren preparación. No se crean fixtures ni se repiten alarmas pendientes sin reparación.

Web1010 ejecutó cuatro objetos fallidos originales:0/4,+0. La captura privada1003, integrada en437e4183 y compilada en1013, demuestra resultados ajenos anteriores al filtro.1017 comparó cinco lecturas HTTP: cambiar orden/%20/+ en «la NASA» no arregla la respuesta RSS; «NASA» sola devuelve NASA. El título RSS conserva la consulta completa. No hay cambio de transporte demostrado; no se afloja relevancia ni se afirma una causa remota no observada. Reanudación en WEB_HTTP1017/DIAGNOSIS.json; no repetir1010/1017 sin hipótesis nueva.

Tramo previo1012:7/11,+3 H0216/H0534/H0619.998 había añadido6, de97a103. El candidato actual20dab7ed añade1019 a437e4183, sóloPython; build1013 reutilizado con fingerprint y binarios verificados. Main intacta. Compilación real1013 exit0; suites/Fast/Full omitidas por orden explícita del dueño, sin llamarlas aprobadas.

| Tanda | Cumplen/ejecutados | Créditos | VRAM MiB | RAM MiB | Segundos |
|---|---:|---:|---:|---:|---:|
|1012|7/11|3|3497.56|2352.08|37.187|
|1010|0/4|0|3497.56|2380.08|62.125|
|1016|14/27|2|3499.56|2460.30|111.016|
|1020|9/13|4|3499.56|2408.54|76.703|

Las cuatro terminaron exit0 con pins intactos y cero violaciones. RAM y VRAM son picos separados, inferiores a4GB; el muestreo de árbol puede incluir descendientes no exclusivos del modelo.84altas/24h supera el mínimo20, sin Full. RAM de arranque resuelta: dotnet global apagaba otra instalación; C:/Users/usuario/.dotnet/dotnet.exe build-server shutdown terminó los servidores restantes. No fue necesario cerrar apps del usuario; su autorización ya está concedida.

No repetir: elecciónQwen/backend/perfil792; herencia802; auditoría de frescura536; efectos Spotify962/Steam/Discord/Calculator/Settings/Explorer sin reconciliación exacta; fuente800 rechazada; paneles enteros por un fallo aislado. H0675/OCR/nuevos providers siguen aparcados. Objetos975/980/986 preservados, alarmas983 canceladas por identidad. IDs y reanudación de efectos inciertos en NEXT_989 (sólo historia de efectos/runtime, no fuente/build).

Orden por masa: apps40 y música39 tienen condiciones957/962/991; web36 queda temporalmente aparcado por1017; archivos32 conserva frontera1005. Mensajería1014:28envíos requieren autorización concreta/contexto;1aclaración sin contenido;2lecturas sin mecanismo. Install1018:19Steam con mecanismo existente pero requieren sesión/entitlement/recursos/reconciliación;12casos separados no justifican infraestructura común ficticia. Esa planificación histórica1021 está ejecutada arriba. Audio conserva24abiertos; los4objetivos1020 ya están acreditados.

Registro actual SHA `1a7ec3d381e4d972cb0bbdf9c55ed632216618e932614e31d2ea602a74a3eae6`. Clasificación846 inmutable;742case_ids, ordenados por abiertos:

| Categoría | Total | Cubiertos | Abiertos | No aplican |
|---|---:|---:|---:|---:|
| Abrir aplicaciones | 54 | 14 | 40 | 0 |
| Música | 39 | 0 | 39 | 0 |
| Navegación y búsqueda web | 46 | 10 | 36 | 0 |
| Archivos y carpetas | 32 | 0 | 32 | 0 |
| Entrada incompleta, ruido y control de diálogo | 34 | 3 | 31 | 0 |
| Mensajería | 31 | 0 | 31 | 0 |
| Instalar y desinstalar software | 31 | 0 | 31 | 0 |
| Alarmas, recordatorios, tareas y agenda | 38 | 9 | 29 | 0 |
| Vídeo y series | 26 | 0 | 26 | 0 |
| Conocimiento, razonamiento y creatividad verbal | 37 | 12 | 25 | 0 |
| Audio y volumen | 51 | 27 | 24 | 0 |
| Conversación social y ayuda general | 31 | 9 | 22 | 0 |
| Interacción dentro de aplicaciones | 22 | 0 | 22 | 0 |
| Hora y fecha | 23 | 3 | 20 | 0 |
| Red y Bluetooth | 21 | 1 | 20 | 0 |
| Cerrar aplicaciones y ventanas | 20 | 0 | 20 | 0 |
| Estado de hardware y sistema | 40 | 21 | 19 | 0 |
| Pantalla, captura e interpretación visual | 19 | 0 | 19 | 0 |
| Brillo y pantalla | 17 | 0 | 17 | 0 |
| Información web actual | 17 | 0 | 17 | 0 |
| Organizar ventanas y pestañas | 13 | 0 | 13 | 0 |
| Estado de ventanas y aplicaciones | 14 | 1 | 13 | 0 |
| Identidad y capacidades del asistente | 19 | 7 | 12 | 0 |
| Notas | 12 | 0 | 12 | 0 |
| Memoria personal | 10 | 0 | 10 | 0 |
| Correo | 6 | 0 | 6 | 0 |
| Bibliotecas y fichas de juegos | 6 | 0 | 6 | 0 |
| Contactos | 5 | 0 | 5 | 0 |
| Desarrollo y ejecución de comandos | 5 | 0 | 5 | 0 |
| Portapapeles | 3 | 0 | 3 | 0 |
| Restricciones negativas de apertura | 4 | 1 | 3 | 0 |
| Energía del sistema | 3 | 0 | 3 | 0 |
| Crear documentos y editar imágenes | 2 | 0 | 2 | 0 |
| Leer y resumir páginas web | 2 | 0 | 2 | 0 |
| Procesos | 9 | 8 | 1 | 0 |
