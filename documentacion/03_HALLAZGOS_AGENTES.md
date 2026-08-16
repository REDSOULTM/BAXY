# Hallazgos recuperados de agentes y auditorías

Este documento sintetiza una parte de las conclusiones visibles o respaldadas
por artefactos. El corpus completo recuperado se indexa en
documentacion\agentes; toda afirmación debe contrastarse antes de convertirse
en decisión.

## Cobertura de recuperación

- 424 sesiones locales examinadas.
- 322 sesiones descendientes recuperadas: 302 directas y 20 anidadas.
- 303 clasificadas como completadas y 19 como interrumpidas.
- 322 segmentos task-specific con hash, 386,18 MiB sin comprimir.
- 131,15 MiB comprimidos para los segmentos; el hilo raíz también se conserva.
- Informes, mensajes publicados, resúmenes expuestos, tools y outputs están en
  documentacion\agentes\privado, ignorado por Git.

El índice no demuestra que 322 conclusiones sean correctas. Sirve para poder
localizarlas, deduplicarlas y someterlas a evidencia primaria. Los agentes
compartieron contexto, por lo que repetir una afirmación no la convierte en una
medición independiente.

## Auditoría default_off_audit

Informe visible:

- Tool Ecosystem v2 era el predeterminado.
- Inventario estable declarado: 94 registradas, 91 seguras, 3 en cuarentena y
  39 workflows.
- Spotify estaba apagado por defecto.
- BAXY_SPOTIFY_PLAY_EXACT=1 creaba el perfil experimental 95/92/3/39.
- Steam, browser interactivo y gate físico final de Spotify seguían pendientes.
- El soak b9980 se aplazó al sábado como última misión.
- No se declaró GPU física de 4 GB ni corpus guiado de voz.
- En el momento del informe existían baterías backend 150/150, frontend 73/73 y
  lint focal limpio; la suite global todavía estaba pendiente.
- D52–D55 eran evidencia histórica y D58 reflejaba el estado vigente.

Uso en la reconstrucción:

- mantener perfiles estables y experimentales imposibles de confundir;
- no convertir counts en KPI de producto;
- conservar pendientes explícitos;
- no afirmar hardware o corpus no probados.

## Auditoría phase3_final_diff_audit

Veredicto visible: 0 P0 y 0 P1 en el diff auditado.

Conclusiones:

- El perfil estable exigía flags experimentales falsos, inventario 94/91 y
  ProductAttestation.
- Spotify opt-in exigía ExperimentalProductAttestation, feature singleton y
  95/92; también diferían contrato, dominio, epoch, counts y digest.
- El preview compuesto no ejecutaba efectos ni tocaba locks, misiones, ledger,
  replay store, providers o fallback.
- Los handles de Steam permanecían como referencias no resueltas durante
  preview.
- El canal público de resultados debía estar redactado y provider_data vacío.
- Título y artista solo podían validarse dentro del canal privado ligado a
  request, operación y result ID.
- Replay/idempotencia solo procedía tras resultado verificado, ledger
  completed y verificación SMTC independiente.
- El provider Spotify seguía opt-in y detrás de Gateway/Invoker.
- El gate sin --execute retornaba antes de variables, artefactos, modelos o
  apertura de Spotify.

Uso:

- preservar separación preview/efecto;
- generalizar identidad, idempotencia y canales privados;
- cambiar la UX, no eliminar la protección.

## Diagnóstico físico de Spotify

La conversación preservada registra esta secuencia:

1. Gemma generó una invocación válida para spotify.play_exact.
2. El resultado no cumplió el contrato final.
3. Los diagnósticos acotaron el fallo al proveedor físico, no al routing.
4. Inventariar siete procesos de Spotify podía tardar más que el timeout
   productivo de 8 segundos en frío.
5. Spotify clásico firmado por Spotify AB devolvía AUMID None.
6. Una regla pensada para Spotify Store exigía un AUMID incompatible y
   rechazaba siempre la instalación Win32 clásica.
7. Se amplió el presupuesto acotado y se corrigió la atestación para aceptar la
   identidad Win32 solo cuando firma, ejecutable, árbol y ausencia de paquete
   coincidieran.
8. Las correcciones focales reportaron 154/154 y el preflight físico devolvió
   ready.
9. El extracto disponible termina cuando se reejecutaría el gate físico; no hay
   evidencia visible suficiente para declarar la reproducción final aprobada.

Lección:

Routing correcto no equivale a misión completada. La verificación del proveedor
y la identidad del software instalado son parte del producto.

## Gemma 4 unificado

Un intento anterior de promoción terminó con:

- 0/11 activaciones;
- STT vacío;
- visión vacía;
- variación de VRAM que no correspondía al resultado esperado.

La hipótesis fue servidor equivocado o wiring roto. Debe tratarse como blocker
histórico hasta que una prueba de punta a punta demuestre:

- PID y parent correctos;
- executable y commit correctos;
- modelo y mmproj correctos;
- puerto exclusivo;
- request realmente recibido;
- salida atribuible al modelo;
- camino completo hasta router, STT y visión.

## Qwen-VL

Evidencia histórica comunicada:

- 2B Q4_K_M + mmproj: alrededor de 2713 MiB de VRAM, rápido, reconocía John
  Wick, pero fallaba con juegos como Elden Ring o Skyrim.
- 4B: alrededor de 4140 MiB, demasiado para el perfil base, sin resolver todos
  los fallos de identificación.
- 8B: demasiado pesado.

Conclusión provisional:

Qwen-VL 2B puede ser perfil visual opt-in; no es prueba suficiente para
reemplazar la visión base sin repetir corpus, ground truth y recursos.

## Soak y harness

- Un run inicial expuso problemas del harness.
- Otro falló a los 5231.640 segundos por WinError 5 al reemplazar
  heartbeat.json mientras un lector lo tenía abierto.
- Se añadieron reintentos de os.replace ante bloqueos transitorios de Windows.
- Un run posterior fue interrumpido por decisiones operativas y reinicio del
  equipo.
- No existe final.json validado con duración mínima de 86400 segundos.

El soak continúa pendiente y no debe presentarse como estabilidad aprobada.

## Experiencia de usuario

El usuario rechazó explícitamente que un visor privado de comandos o JSON fuera
la respuesta normal. Ejemplos como “pon música” deben terminar en una frase
natural que describa el efecto verificado.

También observó “BAXY core listo · 0 capacidades registradas”. Ese estado
demuestra que una GUI abierta no equivale a un producto conectado. El arranque
debe ser honesto y no presentarse como listo si las capacidades reales no
están registradas.

## Conteos de suite contradictorios

Un extracto de conversación registra 5.532 pruebas aprobadas y una omitida.
Otros resúmenes del hilo mencionaron 5.535 aprobadas y una omitida. La
discrepancia debe resolverse consultando artefactos/commits; ninguno de esos
conteos se hereda como evidencia del nuevo árbol.

## Recuperación de spotify_live_gate_design

La tarjeta visible se interpretó inicialmente como interrumpida. El archivo
local recuperado contiene una finalización e informe del agente
/root/spotify_live_gate_design. El informe diseñó el procedimiento del gate
físico de Spotify —incluidos identidad de Gemma, ledger, verificación SMTC,
replay con el mismo request ID y cleanup—, pero declaró explícitamente que no
abrió Spotify, no reprodujo contenido y no modificó archivos.

Por tanto, se conserva como diseño de prueba, no como acceptance física
aprobada. Esta corrección ilustra por qué las tarjetas de la UI y los resúmenes
manuales no sustituyen el segmento de sesión ni el artefacto ejecutado.
