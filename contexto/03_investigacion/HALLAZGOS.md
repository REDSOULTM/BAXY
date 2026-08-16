# Hallazgos de investigación

## 2026-07-14 — arranque

- Branch y commit coinciden con la línea base esperada; árbol inicialmente
  limpio. Evidencia: Git local. Confianza: alta.
- El manifiesto de agentes parsea 322 registros únicos, 303 completados y 19
  interrumpidos, con hashes SHA-256 bien formados y sin duplicados. Evidencia:
  validación local de `documentacion/agentes/manifest.json`. Confianza: alta.
- `Probando Gemma 4` tiene 34 entradas locales y `FunctionGemma` no tiene Git;
  los commits solos no bastan para un cutoff reproducible. Impacto: generar
  manifiestos por archivo antes de extraer. Confianza: alta.
- Ninguna opción tecnológica del handoff está aprobada. Impacto: publicar el
  protocolo y ejecutar cortes comparables antes del ADR final.
- El estado sucio de Carter contiene 56.353 entradas; 29.347 existen en el
  working tree y 26.458 archivos capaces de aportar mensajes/evidencia quedaron
  ligados por SHA-256. Impacto: usar HEAD + overlay, no asumir que la carpeta
  equivale al commit. Confianza: alta.
- FunctionGemma quedó fijado mediante 885 archivos (1.785.215.157 bytes) y el
  historial local de Gemma mediante 170 archivos (31.930.550 bytes). El digest
  global fue idéntico en dos ejecuciones. Confianza: alta.
- El primer congelador omitía inputs ignorados por Git y parseaba rutas con
  espacios entrecomilladas como nombres inexistentes. El extractor fail-closed
  reveló ambos defectos. Se corrigieron con cuatro fuentes lógicas explícitas,
  status Git NUL-safe y lectura desde blobs/checkpoints o bytes verificados.
  El cutoff corregido tiene 17 fuentes y digest `85929373…b7eb3fbd` idéntico en
  dos pasadas. Confianza: alta.

## 2026-07-14 — torneo tecnológico

- Los tres cores de ronda A aprobaron 48/48 casos cada uno. Rust dominó el
  corte aislado de rendimiento y .NET avanzó por la regla congelada de menos de
  siete puntos. Evidencia: `artifacts/technology_tournament/round_a_scorecard.json`.
  Confianza: alta. Impacto: profundizar Rust y .NET como sistemas Windows.
  Destino: ronda B.
- Los árboles WebView2 medidos abrieron conexiones o bindings de red y
  consumieron 371–444 MiB idle y 815–923 MiB pico. Evidencia:
  `artifacts/technology_tournament/raw/round_b_dotnet_webview_rejected_network.json`
  y `round_b_tauri_rust_rejected_network.json`. Confianza: alta para esos
  hashes y host. Impacto: ambos quedaron descalificados por gate duro. Destino:
  ADR-0001; la evidencia rechazada se conserva.
- La revisión previa al ADR detectó que T16 se autoaprobaba sin ejercer el
  parser y que el observador de red no fallaba cerrado. Además, los raws debían
  ligar los hashes de harness y casos. Evidencia: auditoría de
  `experiments/technology_tournament/round_b/harness.ps1` y el generador de
  score. Confianza: alta. Impacto: invalida
  las corridas y score anteriores como cierre final, aunque no borra sus datos.
  Destino: endurecer, repetir y regenerar el scorecard antes del ADR.
- La repetición corregida ejecutó T16 por transporte crudo, hizo fail-closed la
  red y ligó hashes de harness/protocolo/casos. Ambos finalistas aprobaron
  34/34 × 3; la suite de evidencia aprobó 41/41. Evidencia: seis raws finales y
  `artifacts/technology_tournament/round_b_scorecard.json`. Confianza: alta.
  Impacto: elimina los P1 del medidor y habilita el cierre. Destino: ADR-0001.
- El score final eligió WPF + .NET NativeAOT con 82,004484 frente a 79,992351
  de WPF + Rust estático; ambos permanecen en Pareto. Evidencia: scorecard SHA
  `e5f99d74…b8d71190`. Confianza: alta; pesos y nueve dimensiones congelados.
  Impacto: .NET puro es base y Rust fallback. Destino: fase 4.
- Dos réplicas exactas de fuentes y outputs separados en el mismo host, con
  caches globales compartidas, produjeron árboles y hashes idénticos para WPF,
  NativeAOT y Rust. .NET SDK/Rust quedaron fijados; MSVC/Windows SDK solo
  observados y ligados.
  Evidencia: `artifacts/technology_tournament/raw/round_b_reproducibility.json`.
  Confianza: alta para los 19 inputs y receta registrados. Alcance: same-host,
  caches compartidas, sin clean-room ni cross-host. Impacto: 1/2 en la celda;
  no prueba VM limpia ni instalador final. Destino: Must 6.
- Una ejecución lifecycle secuencial reveló que una excepción temprana del
  harness podía dejar shell/core vivos y provocar un mutex/race en el siguiente
  candidato. Era un fallo del medidor, no del contendiente. Se corrigió haciendo
  que `Start-Baxy` registre procesos desde el arranque, centralizando cleanup y
  restauración de entorno en `finally` y convirtiendo los gates finales en
  salida dura. Ambos candidatos repitieron luego el lifecycle aislado sin
  huérfanos. Evidencia:
  `experiments/technology_tournament/round_b/lifecycle_harness.ps1` y los dos
  JSON `artifacts/technology_tournament/raw/round_b_lifecycle_*.json`.
  Confianza: alta. Impacto: evita falsos fallos y
  contaminación entre candidatos. Destino: regresión del harness.
- Los SBOM registran cinco componentes en .NET puro y doce en el híbrido. No
  existe licencia first-party, Authenticode, firma de manifests/journal ni
  manifiesto exacto de bibliotecas MSVC/UCRT estáticas. Evidencia:
  `artifacts/technology_tournament/raw/round_b_supply_chain.json`. Confianza:
  alta. Impacto: no afirmar autenticidad o distribución final. Destino:
  empaquetado productivo y revisión de release. El icono embebido tampoco tiene
  autor, licencia o procedencia registrados.
- UIA, foco, contraste y un área equivalente de 900×520 DIPs están medidos,
  pero no Narrator/NVDA, DPI físico al 200 % ni reduced motion. La GPU de 16 GB
  midió 26,52 MiB para el corte sin modelos. Confianza: alta sobre lo observado.
  Impacto: no cerrar accesibilidad física ni perfil de 4 GB. Destino: Must 12 y
  13.

## 2026-07-15 — distribución reproducible

- El primer A/B Release del producto aisló una única fuente de
  no-determinismo: tres copias del `TimeDateStamp` que `link.exe` insertaba en
  el PE NativeAOT. Código, datos y secciones restantes eran idénticos.
  Evidencia: comparación binaria de dos snapshots Git aislados. Confianza:
  alta. Impacto: `SOURCE_DATE_EPOCH`, `PathMap` y `Deterministic` no bastan para
  el enlace nativo; `Baxy.Core` debe pasar `/Brepro`.
- Tras fijar `/Brepro`, dos builds limpios del commit `aac3e05` coincidieron
  byte a byte en sus siete archivos y dos empaquetados coincidieron en un ZIP
  Stored canónico de nueve entradas. Evidencia:
  `artifacts/product/product_package_gate.json`, SHA-256 del ZIP
  `11971bc0501598009145506f815407ec42a7c8fde2e88996815c1d2eaf3e7ba9`.
  Confianza: alta para este host, SDK y caches. Impacto: el instalador puede
  consumir un contrato exacto `baxy-product-build-v3`.
- El build limpio es autocontenido: el gate GPU NativeAOT y un smoke WPF con
  resolución externa de .NET deshabilitada pasaron sin procesos ni datos de
  prueba residuales. Evidencia: gate versionado y captura inspeccionada.
  Confianza: alta para este host. Alcance: no acredita Windows limpio,
  cross-host, firma, integración Windows, update, rollback o uninstall.
- Los ejecutables first-party siguen sin Authenticode y el manifiesto declara
  `authenticity=not_provided`. SHA-256 verifica consistencia contra metadata
  confiada, no identidad del editor ni resistencia a reemplazar todo el
  paquete. Impacto: B-005 permanece abierto y el progreso no cambia de 5/15.

## 2026-07-15 — Setup embebido reproducible

- Dos cadenas desde snapshots aislados de `5dad02a` produjeron el mismo
  `Baxy.Setup.exe`: 85.858.304 bytes, SHA-256 `50b8b8d4…2c7a`. Los publishes y
  los outputs finales verificaron físicamente el paquete embebido. Evidencia:
  `artifacts/setup/setup_package_gate.json`. Confianza: alta same-host.
- El gate físico encontró dos fallos que los tests contractuales no recorrían:
  una coma doble de `PathMap` se convertía en otra propiedad MSBuild, y una
  atestación dentro de `inputRoot` violaba el layout exacto ZIP+sidecar en la
  revalidación posterior. Ambos fallaron antes de promoción y quedaron ligados
  a regresión. Impacto: los builds físicos A/B son obligatorios, no decorativos.
- NativeAOT, PE y verificación embebida no equivalen a instalación limpia. La
  ruta canónica no se mutó; faltan integración Windows, primer inicio, update,
  rollback compatible con datos y uninstall. Impacto: B-005 cambia de forma,
  pero permanece abierto y el progreso continúa en 5/15.
- El Setup sigue `NotSigned`; el linker/Windows SDK y caches son del host.
  Confianza: hashes/reproducibilidad acreditan consistencia, no editor ni
  cross-host. Destino: firma y gate en VM limpia.

## 2026-07-15 — poda anti-overengineering de uninstall

- Gate 14 y las regresiones históricas exigen resultado físico —instalar,
  actualizar, rollback, keep/purge, checksum y cero procesos BAXY—, pero ninguna
  fuente exige coordinator, worker propio, handoff, journal HMAC, Run/RunOnce,
  Restart Manager o recuperación de apagón para uninstall. Confianza: alta.
  Impacto: esas piezas no tienen prueba roja de corpus y se eliminan.
- El bloque retirado aporta más de 16.600 líneas tracked borradas en el diff actual. El
  reemplazo completo está en una fachada de 418 líneas físicas y reutiliza los mutex,
  estado de integración, shortcut y registro que también sirven a install,
  update y rollback. Impacto: la solución vuelve a estar por debajo de la alarma
  de 1.500 líneas para este subsistema.
- Una prueba Windows real copió `cmd.exe` dentro de una raíz `BAXY`, lo mantuvo
  ejecutándose y confirmó que `Directory.Move` podía renombrar el directorio.
  Esto habilita la solución convencional: mover primero a un sibling único y
  borrar luego con el `cmd.exe` de System32, sin worker BAXY.
- La revisión física encontró que Windows sí bloquea el rename o purge cuando
  el directorio de trabajo del propio proceso permanece dentro del árbol que se
  eliminará. La corrección mínima cambia siempre el CWD al padre canónico de la
  instalación antes del move; regresiones separadas cubren CWD en InstallationRoot
  y dentro de DataRoot. No fue necesario Restart Manager ni coordinación.
- El primer gate del cleaner quedó rojo: pasar el comando compuesto mediante
  `ProcessStartInfo.ArgumentList` iniciaba `cmd.exe`, pero no borraba el
  tombstone. El argumento explícito `/s /c "<comando>"` sí borró el árbol y una
  regresión adicional ejerció retry con un archivo que negaba delete sharing.
  Confianza: alta; se observó físicamente, no por inspección estática.
- `ResolveForUninstall` no inspecciona la hoja `%LOCALAPPDATA%\BAXY`; keep-data
  no llama APIs sobre ella. Purge conserva una forma destructiva única con token
  de confirmación exacto. El perfil actual contiene datos BAXY preexistentes, de
  modo que el gate purge completo debe ejecutarse en un perfil desechable o VM,
  no sobre esos datos.

## 2026-07-15 — recorrido físico parcial de Gate 14

- Desde el HEAD limpio `d69a960` se construyeron una entrega predecesora 1.0.0
  y dos réplicas candidatas 1.0.1. Las réplicas A/B coincidieron byte a byte en
  los ocho archivos del producto, los dos del paquete y los tres del Setup.
  El Setup 1.0.1 mide 87.016.960 bytes y su SHA-256 es
  `fe2b16c14a7369713cb76333ce8a248b27ede216c357a45c55d253e5ee9b5be5`.
  Confianza: alta same-host; no acredita cross-host ni editor porque permanece
  `NotSigned`.
- El artefacto real instaló 1.0.0, actualizó a 1.0.1, conservó 1.0.0 en
  `current.previous`, hizo rollback a 1.0.0 dejando 1.0.1 como anterior y se
  desinstaló con keep-data. InstallationRoot, shortcut, registro y tombstones
  quedaron ausentes, no quedaron procesos BAXY y un canary propio permaneció
  byte-idéntico. Evidencia:
  `artifacts/setup/gate14_lifecycle_gate.json`. Confianza: alta para el perfil y
  host observados.
- Dos fallos previos fueron del harness y ocurrieron antes de mutar el lifecycle:
  una llamada .NET sin el prefijo de tipo y una sobrecarga estática no disponible
  en Windows PowerShell 5.1. Se retiró únicamente la carpeta de canary vacía y
  se verificó 1.0.0 comprometido antes de reanudar. No se atribuyen al producto.
- Gate 14 no se promueve: el perfil contenía tres entradas BAXY preexistentes,
  por lo que no era limpio y purge-data se omitió deliberadamente. Primer inicio
  instalado, purge y ausencia final de DataRoot todavía requieren una cuenta o
  VM desechable.

## 2026-07-15 — cierre de Gate 11

- Dos capturas del release 1.0.1 dieron rojo en “misión no visible”, pero el
  parser, el core NativeAOT y un E2E del ViewModel completaron la operación exacta
  en alrededor de un segundo, con `verified=true`, una nota durable y el mensaje
  `Guardé la nota «Compras».`. El fallo quedó localizado al oráculo UIA, no a la
  operación ni a su proyección. Confianza: alta.
- El observador mezclaba tres hechos —efecto durable, editor listo y peer UIA— y
  recorría todo el árbol accesible bajo carga. Se separaron: el gate exige una
  nota durable y editor reactivado, registra UIA por separado y captura píxeles
  nativos para inspección visual. Esto simplifica el diagnóstico sin relajar el
  resultado físico.
- Un segundo rojo del nuevo oráculo tenía una causa reproducible de encoding:
  Windows PowerShell 5.1 interpreta un `.ps1` UTF-8 sin BOM mediante la página
  ANSI, de modo que los literales `é/«»` no podían coincidir. Construir esos
  caracteres por code point, como ya hacía el request `café`, cerró la regresión.
- La corrida final acreditó WPF + core, nota durable, respuesta visible y UIA,
  captura nativa 980×680 sin reescalado, cero procesos y raíz aislada eliminada.
  Pasaron además 14/14 contratos de shell y 22/22 regresiones de packaging.
  Evidencia: `artifacts/product/gui_capture_gate.json` y su PNG
  content-addressed. Gate 11 se aprueba; no se extrapola certificación de cada
  monitor o lector de pantalla.
