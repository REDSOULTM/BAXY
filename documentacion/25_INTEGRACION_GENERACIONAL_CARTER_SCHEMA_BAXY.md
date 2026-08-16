# Integración generacional Carter → Schema Agent → BAXY

Fecha de corte: 2026-07-22.

## Alcance auditado

Esta integración compara por comportamiento los árboles e historiales disponibles,
porque las ramas Python antiguas y la reconstrucción .NET actual no comparten un
ancestro Git utilizable. Se inspeccionaron `origin/main`, `origin/Dev`,
`origin/Tools-Reduce`, `origin/vram4_lean`, la etiqueta `v0.9.2`, el historial de la
rama `codex/baxy-rebuild-v3`, los ledgers y auditorías congelados y los catálogos:

- Carter v1/v2, Carter universal y Carter v4/v5;
- Probando Gemma 4 y la generación de Schema Agent;
- los 60 schemas individuales y los 16 schemas consolidados;
- FunctionGemma, el router lean y el perfil de 4 GiB;
- BAXY clean, BAXY unificado y Tool Ecosystem v2;
- la reconstrucción BAXY 1.0 en .NET/WPF con mente local Python.

El archivo histórico `tool_schemas_slim.json` contiene 525 entradas, pero ese número
no representa 525 funciones completas: incluye alias, operaciones de estado,
duplicados por dominio, stubs `needs_implementation`, adaptadores sin dependencia y
acciones que sólo fueron validadas con dispatch simulado. La propia auditoría Carter
540 documentó 489 aprobaciones automáticas frente a 417 efectos reales. Por ello la
regla de integración es: contrato único, provider real, postlectura independiente y
respuesta honesta; nunca sumar un nombre al catálogo para aparentar cobertura.

## Resultado de la comparación

| Familia histórica | Mejor aprendizaje recuperado | Estado en BAXY actual |
|---|---|---|
| Sistema, batería, disco, CPU, RAM y GPU | lecturas locales acotadas y medibles | integrado en `system.status`, con scopes verificables |
| Audio y dispositivos | leer antes/después y no confundir volumen con reproducción | integrado en audio, micrófono, media y periféricos |
| Apps y ventanas | resolver identidad antes de actuar; UIA antes que coordenadas | integrado con catálogo Inicio, identidad de ventana y postlectura |
| Teclado, ratón y GUI | SendInput acotado, UIA→OCR→visión, nunca éxito por dispatch | integrado en input, captura, OCR y visión |
| Browser/CDP | sesión local autenticada, URL final observada y lectura de la pestaña activa | navegación/control existentes; recuperados ahora `browser.page.read` y `browser.tabs.list` |
| Web, streaming y media | separar búsqueda, navegación y playback realmente observado | integrado con contratos distintos y progreso de video/postlectura |
| Archivos y backup | sandbox/raíces conocidas, prepare/commit y restauración verificable | integrado sin terminal arbitraria ni borrado ciego |
| Notas, tareas, calendario, alarmas y rutinas | identidad estable, revisión CAS y persistencia | integrado con operaciones tipadas y restaurables |
| Wi-Fi, Bluetooth, ajustes y periféricos | APIs oficiales y estados físicos; aclarar si falta hardware | integrado con gates de hardware explícitos |
| Memoria | DPAPI, sensibilidad, redacción de secretos y olvido verificable | integrado; se descartó el recall implícito invasivo antes de cada turno |
| Planner Carter/Tool Ecosystem v2 | DAG durable, dependencias tipadas, confirmación, leases y replan acotado | integrado en planner .NET; máximo dos replans y fail-closed ante efecto ambiguo |
| Voz Carter/FunctionGemma | Parakeet local, VAD, wake word, AEC/ducking y degradación honesta | integrado en la mente local y sus gates físicos |
| Router Schema Agent/FunctionGemma | shortlist, schemas compactos y rutas deterministas rápidas | integrado con catálogo autenticado y fast paths ES/EN/Spanglish |
| Perfil lean | no duplicar agentes por tier y cargar modelos una sola vez | integrado mediante runtime externo registrado y arranque resiliente |

## Recuperación nueva de esta pasada

### `browser.page.read`

Recupera `active_tab`, `active_tab_title` y `extract` de las generaciones Python sin
copiar su navegador monolítico. Lee por CDP sólo la página de la sesión local de BAXY,
valida URL HTTP(S) y estado del documento, limita el texto a 32.768 caracteres y no
produce efecto. Se clasifica como `privacy_sensitive` porque puede exponer contenido
visible. Las solicitudes «resume la página actual» y «summarize current page» usan
esta ruta DOM rápida antes de recurrir a captura + visión.

### `browser.tabs.list`

Recupera `tabs`/`active_tab` como snapshot de targets CDP. Enumera hasta 50 pestañas
web con identidad, título y URL, excluye targets internos y no modifica ni activa
pestañas. Cubre directamente «cuántas pestañas tengo abiertas» y su variante inglesa.

Ambas capacidades atraviesan el mismo catálogo firmado, handler del core, provider
Windows, proyección segura del planner y narrador que el resto del producto. No son
atajos laterales.

## Componentes históricos que deliberadamente no se copiaron

No se consideran “lo mejor” y por tanto no entran:

- clicks por coordenadas, `eval`, terminal arbitraria y ejecución de código generado;
- escritura libre de registro, firewall, servicios, DNS o variables de entorno;
- `git commit/push`, compras, mensajes o formularios sin identidad y confirmación;
- aliases que inflan el prompt (`notes`, `note_list`, `create_note`, etc.);
- herramientas que sólo respondían `needs_dependency`/`needs_implementation`;
- contenedores, bases de datos, smart-home, finanzas, creatividad y watchers sin un
  backend instalado, autoridad explícita y verificador físico;
- recall automático de memoria privada antes de cada turno;
- loops ReAct abiertos, retries ciegos y routers LLM adicionales que aumentaban
  latencia y propagaban errores;
- perfiles completos duplicados por VRAM, Whisper cuando Parakeet medido es la ruta
  elegida, y modelos/backend no atestados en el notebook.

Estos rechazos preservan funcionalidad real: cuando exista un backend autorizado, una
capacidad nueva debe entrar con schema acotado, riesgo correcto, prueba negativa,
postlectura y evidencia física, no resucitando un stub histórico.

## Invariantes finales

1. `Completed` sólo existe con verificación; dispatch no equivale a efecto.
2. Un efecto ambiguo se conserva y no se repite ni replantea a ciegas.
3. Las operaciones de riesgo exigen confirmación/identidad donde corresponde.
4. La mente sólo puede planear operaciones anunciadas por el core autenticado.
5. Las rutas simples y de lectura evitan el LLM cuando existe una respuesta local
   determinista, preservando el objetivo de menos de cuatro segundos.
6. El catálogo productivo queda en 169 operaciones públicas verificables más
   `app.status` interno; no se contabilizan alias ni stubs.
