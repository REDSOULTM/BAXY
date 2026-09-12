# C03 — checkpoint tras SYSTEM1028 en la máquina original

**130/742 cubiertos, 612 abiertos, 0 no aplican; 102 altas en la ventana de 24 h recalculada aquí; 0/35 categorías cerradas.** C03: 3/11 cumplidos, 5 contradichos, 3 pendientes. Sin estimación fiable de cierre completo. **RAM:** pico de tanda 2587,37 MiB, 32530 MiB totales en la máquina. **VRAM:** pico de tanda 3494,93 MiB, por debajo de la guarda 3800 y del techo 4096; carga del modelo medida aparte en 3513 MiB atribuibles. **Pruebas omitidas:** suites dueñas, Fast y Full, por instrucción explícita del dueño; omitidas, no verdes, no aprobadas. Registro actual SHA `af5ccd83c2e6d567a9631b540f76fde011670fe9aba2de8f4777cb7cb3a0dccd`, contado desde el registro privado restaurado, no desde un contador heredado.

**Papeles de las máquinas, corregidos por el dueño.** REDPC es el BAXY original; el portátil sólo replicó el repositorio y su raíz en `D:` era porque su `C:` estaba lleno. El tramo de C03 del 6 al 12 de septiembre se ejecutó en la réplica, y de ahí venían su evidencia privada y la descarga del modelo decidido.

**Paquete privado recibido y verificado.** ZIP SHA `95bc3f23…fd8c704`, 2 025 743 bytes, 95/95 entradas coincidentes con `TRANSFER_MANIFEST.json`. Extraído en carpeta nueva `C03-opus5-relevo-destino`, sin sobreescribir nada. Registro restaurado en SHA `1a7ec3d3…`, 742 filas, 126 covered y 616 open al llegar, exactamente lo declarado. Rutas históricas del portátil leídas sin editar sus bytes.

**Runtime de esta máquina, listo con el modelo de la decisión 792.** El GGUF decidido no estaba aquí: vivía en `D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/` y esa carpeta no existía; de los 93 GGUF locales ninguno era el correcto, y `assets/models/Qwen3-4B-Q4_K_M.gguf` se llama igual que el primer candidato del manifiesto pero es el modelo activo anterior, Instruct AWQ `7485fe6f…`. Raíz lo restauró desde la procedencia atestada que versiona `artifacts/research/qwen3_4b_instruct_2507_candidate_preregistration_20260811.json`, con su orden congelado: `.partial`, 2 497 281 120 bytes exactos, SHA `3605803b…` exacto, y sólo entonces renombrado. `bootstrap.ps1` falló primero con `runtime_lock_invalid` → `installed_missing` porque el venv de la mente estaba desfasado respecto al `pylock` de los 192 commits; instaló `pywebrtc-audio 0.2.0+baxy.1` y `sherpa-onnx 1.13.4+baxy.2` y quedó válido. Modelo y wake declarados en el override oficial `assets.local.json`, manifiesto anterior respaldado y `wake_on_start` restaurado a `true`. No es campaña de modelos nueva ni sustitución silenciosa.

**1025 cerrada por completo, sin repetir su ejecución.** Los 25 terminales leídos y juzgados contra su criterio sellado: 13 cumplen, 12 fallan. Crédito 3, el ya escrito antes de la pausa; esta adjudicación no añadió ninguno y los contadores no se movieron por ella. Tres literales cumplen y siguen open por falta de par: H0236 con dos de tres variantes de juegos caídas, H0239 y H0582 con una de dos de comparación caída. Fallos con causa: Marvel vs. Capcom fechado en 2000 cuando el estreno original fue arcade en 1998; Doom Eternal atribuido a Bethesda Game Studios, a 2023 y a enemigos alienígenas cuando es id Software, Bethesda Softworks, 20 de marzo de 2020 y demonios; Chell descrita como hombre y Portal como mundos alternativos; H0424, H0645 y dev-10 respondieron con la identidad de BAXY en vez de preguntar el referente; dos composition_failed por reintentos agotados; dos fallos de runtime cuyo mensaje de error se compuso junto al contenido y filtró vocabulario interno; una instrucción diferida ejecutada; una cita explicada con el destinatario invertido. Detalle en `KNOWLEDGE1025/ROOT_ADJUDICATION.json`.

**Referente ausente: causa demostrada, reparación no escrita.** `_deictic_open_request` en `__main__.py:2818` sólo reconoce aperturas, así que `missing_open_referent` (`:5831`) nunca llega a llamar a `llm.clarify_missing_referent`, que existe y está sana. Los `decision_path` de los 25 turnos lo confirman: ninguno usó `deictic_referent_clarification`. `read_request` no trae intents para esos literales, luego el veto `nothing_to_clarify` no interviene. No se integra la ampliación sin controles: «su» en español es también tratamiento formal y una regla amplia rompería «¿Cuál es su nombre?» dirigido a BAXY, en una categoría con 7 cubiertos. `KNOWLEDGE1025/DIAGNOSIS_REFERENTE_AUSENTE.md`.

**SYSTEM1028: primera tanda propia, +4 cubiertos.** 31 casos sellados antes de ejecutar, exit0, 31 terminales, 31 controles, 0 violaciones, 154,8 s. 14 cumplen y 17 fallan. Créditos: H0539 y H0655 de memoria instalada con el par heredado de 1022 dev-03/dev-04, declarado en el PLAN antes de ejecutar; H0442 de espacio libre con par fresco dev-01/dev-02; H0422 de identidad de máquina y usuario con par fresco dev-11/dev-12. H0037 cumple —respondió con verdad que este equipo no tiene batería y está en corriente— y H0114 cumple con cifra real de VRAM, pero ambos siguen open porque sus conductas no dejaron dos variantes en pie. Cinco abiertos de la categoría quedan aparcados con razón y sin rellenar: resolución, Hz del monitor, número de monitores y versión de Python instalada no tienen operación en el catálogo tipado, y cuatro casos no justifican infraestructura de vídeo nueva, así que la categoría no puede cerrarse. Una primera medición se detuvo a 1,3 s con `sealed_input_or_source_changed` porque el arranque del producto sustituye el Core junto a `Baxy.exe` por el publicado AOT; se conserva en `stopped-run-1`. La comprobación heredada de Core efectivo igual a publicado era correcta y mi debilitamiento previo estaba equivocado: revertido.

**Tres causas transversales con su primera transformación incorrecta identificada, en `SYSTEM1028/DIAGNOSIS.md`.** El compositor es fiel al payload en las tres; el payload llega mal. A: una lectura que sí está en el catálogo se clasifica `out_of_catalog` en la decisión —`__main__.py:6638-6655`— aunque la misma tanda la ejecutó por otra formulación; seis casos. B: la mitad temporal de una petición compuesta se pierde en la decisión y después se **inventa** en el texto publicado, «Hoy es 5 de abril de 2025» contra el 12 de septiembre de 2026 real; sus dos variantes eligieron la otra salida, declarar la hora indisponible. C: se elige el scope `summary`, que no incluye GPU, para una pregunta que nombra la GPU, y luego se declara sin acceso lo que el mismo `summary` sí traía para batería. Ninguna necesita infraestructura nueva. La asimetría de idioma queda anotada como observación, sin campaña.

**No repetir:** elección Qwen/backend/perfil 792; herencia 802; auditoría de frescura 536; web 1010/1017 sin hipótesis nueva; fuente 800 rechazada; paneles enteros por un fallo aislado; H0675, OCR y providers nuevos siguen aparcados. Efectos Spotify 962, Steam, Discord, Calculator, Settings y Explorer son del PC réplica: no se reconcilian ejecutando acciones sobre apps homónimas de aquí. Objetos 975/980/986 preservados. Sin limpieza global.

**Orden por masa abierta:** apps 40, música 39, web 36, archivos 32, aclaración 31, mensajería 31, instalación 31, agenda 29, vídeo 26, conocimiento 22, audio 24, conversación 22, interacción en apps 22. Las tres causas transversales de 1028 atraviesan varias de ellas, así que repararlas rinde más que otra tanda ancha. Agenda tiene además el parche 1024 recibido y revisado, sin integrar ni medir: su punto abierto es el segundo uso de `_time_only_reminder_request` en `effect_intent.py:13842`, que es una abstención de la ruta de efecto que su diagnóstico no analiza.

| Tanda | Cumplen/ejecutados | Créditos | VRAM MiB | RAM MiB | Segundos |
|---|---:|---:|---:|---:|---:|
|1021|6/22|1|3499.56|2463.06|98.25|
|1022|21/25|10|3497.56|2467.25|85.75|
|1025|13/25|3|3499.56|2435.66|191.56|
|1028|14/31|4|3494.93|2587.37|154.80|

Todas terminaron exit0 con pins intactos y cero violaciones. RAM y VRAM son picos separados, por debajo de 4 GB; el muestreo de árbol puede incluir descendientes no exclusivos del modelo.

| Categoría | Total | Cubiertos | Abiertos |
|---|---:|---:|---:|
| Abrir aplicaciones | 54 | 14 | 40 |
| Música | 39 | 0 | 39 |
| Navegación y búsqueda web | 46 | 10 | 36 |
| Archivos y carpetas | 32 | 0 | 32 |
| Entrada incompleta, ruido y control de diálogo | 34 | 3 | 31 |
| Mensajería | 31 | 0 | 31 |
| Instalar y desinstalar software | 31 | 0 | 31 |
| Alarmas, recordatorios, tareas y agenda | 38 | 9 | 29 |
| Vídeo y series | 26 | 0 | 26 |
| Audio y volumen | 51 | 27 | 24 |
| Conocimiento, razonamiento y creatividad verbal | 37 | 15 | 22 |
| Conversación social y ayuda general | 31 | 9 | 22 |
| Interacción dentro de aplicaciones | 22 | 0 | 22 |
| Hora y fecha | 23 | 3 | 20 |
| Red y Bluetooth | 21 | 1 | 20 |
| Cerrar aplicaciones y ventanas | 20 | 0 | 20 |
| Pantalla, captura e interpretación visual | 19 | 0 | 19 |
| Brillo y pantalla | 17 | 0 | 17 |
| Información web actual | 17 | 0 | 17 |
| Estado de hardware y sistema | 40 | 25 | 15 |
| Organizar ventanas y pestañas | 13 | 0 | 13 |
| Estado de ventanas y aplicaciones | 14 | 1 | 13 |
| Identidad y capacidades del asistente | 19 | 7 | 12 |
| Notas | 12 | 0 | 12 |
| Memoria personal | 10 | 0 | 10 |
| Correo | 6 | 0 | 6 |
| Bibliotecas y fichas de juegos | 6 | 0 | 6 |
| Contactos | 5 | 0 | 5 |
| Desarrollo y ejecución de comandos | 5 | 0 | 5 |
| Portapapeles | 3 | 0 | 3 |
| Restricciones negativas de apertura | 4 | 1 | 3 |
| Energía del sistema | 3 | 0 | 3 |
| Crear documentos y editar imágenes | 2 | 0 | 2 |
| Leer y resumir páginas web | 2 | 0 | 2 |
| Procesos | 9 | 8 | 1 |
