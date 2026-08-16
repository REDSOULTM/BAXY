# Carter — Capacidades actuales (2026-04-19)

Todo lo que Carter puede hacer hoy con herramientas reales, verificado contra el catálogo de tools registradas.

---

## Aplicaciones de escritorio

- Abrir cualquier app instalada (`app_open`) — ej. "abre Steam", "abre Chrome"
- Cerrar cualquier app en ejecución (`app_close`)
- Desinstalar una app de Windows (`app_uninstall`)
- Listar procesos en ejecución con CPU y RAM (`process_list`)
- Ver info de CPU/RAM de un proceso específico (`desktop_get_process_info`)

## Sistema

- Ver hora, fecha, zona horaria, timestamp Unix (`system_get_time`)
- Ver uso de CPU (`system_get_cpu_info`)
- Ver uso de RAM (`system_get_ram_info`)
- Ver espacio en disco (`system_get_disk_info`)
- Ver GPU (`system_get_gpu_info`)
- Ver batería y estado de carga (`system_get_battery`)
- Ver tiempo encendido (`system_get_uptime`)
- Ver idioma/locale (`system_get_locale`)
- Ver navegador predeterminado (`system_get_default_browser`)
- Ver monitores conectados (`system_list_monitors`)

## Audio y pantalla

- Subir/bajar/consultar volumen del sistema (`system_set_volume`, `system_get_volume`)
- Mutear/desmutear (`system_mute`)
- Subir/bajar/consultar brillo de pantalla (`system_set_brightness`, `system_get_brightness`)
- Activar/desactivar modo oscuro (`system_set_dark_mode`, `system_get_dark_mode`)
- Listar dispositivos de audio (`system_list_audio_devices`)
- Cambiar dispositivo de salida de audio predeterminado (`system_set_default_audio_device`)
- Ver dispositivo de audio activo (`system_get_audio_device`)

## Energía

- Apagar el PC (`power_shutdown`)
- Reiniciar el PC (`power_restart`)
- Bloquear la sesión (`power_lock`)
- Suspender (`power_sleep`)
- Hibernar (`power_hibernate`)
- Cerrar sesión (`power_signout`)

## Red / Wi-Fi

- Listar redes Wi-Fi visibles (`network_wifi_list`)
- Conectar a una red Wi-Fi guardada (`network_wifi_connect`)
- Desconectar Wi-Fi (`network_wifi_disconnect`)
- Ver IP local (`network_get_ip`)

## Notificaciones y voz

- Mostrar notificación toast de Windows (`notify_toast`)
- Hablar texto en voz alta con TTS del sistema (`notify_speak`)
- Reproducir sonido del sistema (`notify_sound`)

## Archivos y carpetas

- Leer un archivo de texto (`filesystem_read_text`)
- Crear/sobreescribir un archivo de texto (`filesystem_write_text`)
- Listar contenido de una carpeta (`filesystem_list_directory`)
- Buscar archivos por patrón glob (`filesystem_search_files`)
- Mover archivo o carpeta (`filesystem_move`)
- Copiar archivo o carpeta (`filesystem_copy`)
- Eliminar archivo o carpeta (`filesystem_delete`)
- Ver metadatos de un archivo (tamaño, fecha, tipo) (`filesystem_get_stat`)

## Navegador web

- Abrir una URL en el navegador (`web_open_url`)
- Buscar en Google y devolver resultados (`web_search`)
- Navegar a una URL con Playwright y leer el contenido (`web_navigate`)
- Hacer click en un elemento por selector o texto (`web_click`)
- Rellenar un campo de formulario (`web_fill`)
- Capturar screenshot del navegador (`web_screenshot`)
- Extraer texto, links o headings de una página (`web_extract`)
- Ejecutar JavaScript en la página (`web_eval`)
- Gestionar pestañas del navegador (`web_tabs`, `web_use_tab`)
- Gestionar perfiles de Chromium CDP (`web_profile_list/use/status/delete`)
- Extension Relay: ejecutar JS y extraer datos desde la extensión del navegador
- Conectar a Chromium existente via DevTools Protocol (`web_connect_cdp`)

## Ventanas

- Listar ventanas visibles (`window_list`)
- Traer ventana al frente (`window_focus`)
- Minimizar / maximizar / restaurar ventana (`window_minimize/maximize/restore`)
- Cerrar ventana (`window_close`)
- Inspeccionar ventana activa y sus controles UIA (`window_inspect_active`)
- Esperar a que aparezca una ventana (`window_wait_for`)

## Escritorio

- Copiar texto al portapapeles (`desktop_clipboard_set`)
- Leer contenido del portapapeles (`desktop_clipboard_get`)
- Abrir carpeta en el Explorador (`desktop_open_folder`)
- Capturar screenshot del escritorio completo (`desktop_screenshot`)

## Teclado y mouse

- Clic en coordenadas de pantalla (`input_mouse_click`) — funciona en apps CEF (Steam, Discord)
- Pulsar una tecla (`input_key_press`)
- Ejecutar atajo de teclado (`input_hotkey`) — ej. Ctrl+C, Alt+F4
- Escribir texto (`input_type_text`)

## Elementos UI (UIA / accesibilidad)

- Encontrar elemento por nombre y tipo de control (`ui_find_element`)
- Hacer click en un elemento UIA (`ui_invoke`)
- Escribir en un campo UIA (`ui_set_value`)
- Leer valor de un campo UIA (`ui_get_value`)

## Visión por computadora

- OCR: leer texto visible en pantalla (`vision_read_text_visual`)
- Encontrar elemento visual por descripción natural (`vision_find_element_visual`)
- Hacer click visual en elemento descrito (`vision_click_visual`)
- Describir lo que se ve en pantalla (`vision_describe_screen`)
- OmniParser: detectar todos los elementos GUI interactivos (`vision_omniparse_screen`)
- Set-of-Marks: anotar pantalla con bounding boxes y elegir elemento por descripción (`vision_som_select`)

## GUI Agent (agente visual completo)

- Click en elemento descrito en lenguaje natural — fallback UIA→visual (`gui_click`)
- Escribir en campo descrito en lenguaje natural (`gui_type`)
- Leer contenido visible de la pantalla (`gui_read`)
- Ejecutar tarea GUI multi-paso descrita en lenguaje natural (`gui_do`) — toma screenshot, decide, hace click, verifica, repite hasta terminar

## Terminal y comandos

- Ejecutar comando de sistema (`terminal_run_command`)
- Ejecutar código PowerShell (`terminal_run_powershell`)
- Instalar paquete con winget (`terminal_winget_install`)
- Buscar paquetes en winget (`terminal_winget_search`)
- Instalar paquete Python con pip (`terminal_pip_install`)
- Ejecutar comandos git (`terminal_git_run`) — status, log, diff, pull, clone, commit, push

## Descarga de archivos

- Descargar un archivo desde URL (`download_file`) — valida URL, bloquea ejecutables peligrosos, verifica SHA256
- Verificar accesibilidad de URL sin descargar (`download_status`)

## Tareas programadas (Windows)

- Crear tarea programada con schtasks (`scheduler_schedule_task`)
- Listar tareas programadas (`scheduler_list_tasks`)
- Eliminar tarea programada (`scheduler_delete_task`)
- Ejecutar tarea programada ahora (`scheduler_run_task`)

## Cola de tareas interna de Carter

- Listar tareas async en cola de Carter (`taskman_task_list`)
- Ver estado de una tarea (`taskman_task_status`)
- Cancelar tarea en ejecución (`taskman_task_cancel`)
- Esperar a que termine una tarea (`taskman_task_wait`)

## Office (Word, Excel, PowerPoint)

### Word
- Abrir / crear documento .docx
- Leer texto del documento
- Escribir / añadir texto
- Guardar / cerrar

### Excel
- Abrir / crear libro .xlsx
- Leer celda / rango de celdas
- Escribir en celda
- Guardar / cerrar

### PowerPoint
- Abrir / crear presentación .pptx
- Añadir slide con título y contenido
- Leer texto de un slide
- Guardar / cerrar

## Steam

- Abrir cliente de Steam (`steam_open_client`)
- Instalar juego por nombre o AppID (`steam_install`)
- Desinstalar juego (`steam_uninstall`)
- Lanzar juego instalado (`steam_run`)
- Cerrar juego en ejecución (`steam_stop`)
- Listar juegos instalados (`steam_list_installed`)
- Verificar si un juego está instalado (`steam_is_installed`)
- Buscar juegos en la Steam Store (`steam_search`)
- Abrir página de tienda de un juego (`steam_open_page`)

## Memoria persistente

- Guardar hecho, preferencia o configuración del usuario (`memory_save`)
- Recordar hecho guardado por clave (`memory_recall`)
- Buscar en la memoria local de Carter (`memory_search`)
- Escribir nota duradera en MEMORY.md (`memory_remember`)
- Promover contexto reciente a memoria duradera (`memory_promote`)
- Ver contexto completo de memoria de largo plazo (`memory_context`)
- Consolidación de memoria (dream) — compactar y reorganizar (`memory_dream`)
- Preview de consolidación sin escribir (`memory_dream_preview`)

## Skills (procedimientos locales)

- Listar skills disponibles (`skill_list`)
- Leer un skill (`skill_read`)
- Cargar cuerpo de un skill (`skill_load`)
- Ejecutar un skill con argumentos (`skill_run`)
- Crear o actualizar un skill (`skill_write`)
- Forzar recarga de skills desde disco (`skill_refresh`)
- Validar un skill (`skill_validate`)
- Ver recetas aprendidas de acciones exitosas (`skill_recipes`)

## Heartbeat (autonomía programada)

- Ver configuración y estado del heartbeat (`heartbeat_status`)
- Leer HEARTBEAT.md (`heartbeat_read`)
- Escribir/actualizar HEARTBEAT.md (`heartbeat_write`)
- Añadir tarea programada al heartbeat (`heartbeat_append_task`)

## Meta

- Listar todas las capabilities registradas (`meta_list_capabilities`)
- Describir en detalle una tool específica (`meta_describe_tool`)

---

## Lo que Carter NO puede hacer aún (próxima sesión con Codex)

| Categoría | Ejemplos |
|---|---|
| PDF | Leer texto de PDF, fusionar PDFs, exportar Word a PDF |
| Email | Enviar/leer emails (SMTP/IMAP) |
| Calendario | Crear/listar eventos de calendario |
| Audio/video | Transcribir audio (Whisper), convertir video, TTS a archivo |
| Archivos extra | Comprimir/descomprimir ZIP, renombrar masivo, leer líneas |
| Red extra | Ping, IP pública, check de puerto, DNS lookup, traceroute |
| Sistema extra | Listar apps instaladas, variables de entorno, apps de inicio, historial del portapapeles |
| Office extra | Charts en Excel, buscar/reemplazar en Word, exportar PDF |
| Código | Ejecutar scripts Python/Node, linting, formateo |
| Base de datos | Consultas SQLite, leer/convertir CSV |
| Recordatorios | Reminder con mensaje en hora específica |
