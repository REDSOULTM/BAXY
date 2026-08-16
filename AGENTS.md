# BAXY: guía obligatoria para agentes

## Ubicación canónica

El checkout que contiene este archivo es el repositorio activo y la única
fuente de verdad de BAXY. No deduzcas su ubicación desde una letra de unidad,
el Escritorio de un usuario ni la presencia de OneDrive o una unión.

- Localiza la raíz con `git rev-parse --show-toplevel`.
- Comprueba que esa raíz contiene `Baxy.slnx`, `main.py` y este `AGENTS.md`.
- Rama base de mantenimiento: `codex/baxy-rebuild-v3`.

Antes de actuar, ejecuta:

```powershell
git rev-parse --show-toplevel
git status --short --branch
```

El primer comando debe resolver al mismo checkout que contiene este archivo.
No clones, reconstruyas ni copies el proyecto a otra carpeta para continuar
una tarea.

## No empezar de cero

BAXY ya es un producto integrado y probado. Conserva el trabajo existente, los
commits, los corpus canónicos y los cambios de otros agentes. No sustituyas la
implementación actual por un prototipo ni uses `legacy/` como código activo.

Después de este archivo, lee en este orden solo lo necesario para la tarea:

1. `README.md` para la entrada diaria y el estado general.
2. `documentacion/01_ARQUITECTURA/GUIA_AGENTES_IA/README.md` para elegir el
   mapa de ownership, build, contratos, recetas o validación que corresponda.
3. `documentacion/00_LEEME.md` si necesitas recorrer el archivo técnico e
   histórico.
4. `AGENT_HANDOFF.md` únicamente si necesitas restaurar corpus o activos
   ignorados.
5. `BAXY_GPT56_ULTRA_PROMPT.md` como contrato histórico de alcance, no como una
   orden de reiniciar la reconstrucción.

## Mapa del proyecto

- `main.py`: punto de entrada único de desarrollo; carga Python directamente y
  recompila .NET solo cuando detecta cambios que lo requieren.
- `src/Baxy.App`: interfaz de escritorio WPF/WebView2.
- `src/Baxy.Contracts`: contratos compartidos y protocolo `baxy.local.v1`.
- `src/Baxy.Kernel`: catálogo, schema, riesgo, confirmación, journal y replay.
- `src/Baxy.Security.Windows`: DPAPI, cifrado, integridad y rutas privadas.
- `src/Baxy.Providers.Windows`: acciones reales de Windows y aplicaciones.
- `src/Baxy.Core`: composition root y ejecución verificada NativeAOT.
- `src/Baxy.FieldUi`: presentación React histórica servida por WebView2; su
  `dist/` está versionado y sellado por ADR-0008.
- `src/Baxy.Setup`: instalador, actualización y rollback.
- `src/baxy_mind`: router, planner, lenguaje natural, STT y TTS.
- `tests`: cinco proyectos NUnit y pruebas Python de mente, build y corpus.
- `scripts`: compilación, empaquetado, instalación y compuertas físicas.
- `artifacts`: evidencia y salidas de validación.
- `experiments`: investigación reproducible; no es runtime productivo.
- `legacy`: generaciones anteriores conservadas como referencia de solo
  lectura.

## Runtime e instalación

No edites binarios instalados. Cambia el código del repositorio, prueba y
construye mediante los scripts. Una instalación, actualización, rollback o
desinstalación real se hace únicamente con un `Baxy.Setup.exe` atestado y con
autorización explícita.

- Instalación activa:
  `%LOCALAPPDATA%\Programs\BAXY`
- Manifest del runtime local:
  `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json`
- Descriptor común de activos: `assets.manifest.json`.
- Override local, fuera de Git:
  `%LOCALAPPDATA%\BAXYRuntime\assets.local.json` o `BAXY_ASSETS_OVERRIDE`.
- El runtime registrado conserva rutas absolutas y hashes en
  `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json`.

Prepara o diagnostica otro equipo con `scripts\bootstrap.ps1`. El bootstrap
instala dependencias fijadas, pero no descarga modelos automáticamente.

Los modelos Gemma, llama.cpp y Parakeet no viven dentro del repositorio y no
deben duplicarse.

## Estado certificado en este notebook

La única baseline operativa vigente —conteos, omisiones, último extremo
validado, publicaciones e instalación comprobada— está en
`documentacion/01_ARQUITECTURA/REGISTRO_DE_MANTENIBILIDAD.md`. No copies sus
números a este archivo: cambian con cada campaña.

El conteo vigente del catálogo se fija en sus pruebas y en el registro de
mantenibilidad; esta guía no lo duplica. App valida el proceso Core que inicia
y compara exactamente sus descriptores compilados; esta frontera no es una
firma criptográfica del hello. Calendario y correo requieren un perfil de
Outlook configurado en Windows.

Las acciones externas sensibles (enviar, borrar, imprimir, emparejar,
instalar o cambiar cuentas/redes) deben probarse con contratos o simulaciones
salvo autorización explícita para un objetivo real. Nunca presentes un efecto
no verificado como realizado.

## Experiencia del usuario

BAXY habla con una persona, no con un técnico. Toda respuesta visible debe ser
natural, breve y formulada por el LLM. Los detalles internos pueden aparecer
solo como diagnóstico opcional. Si una acción falla, BAXY debe decirlo con
lenguaje humano y un código estable, sin mostrar JSON, nombres de clases,
estados del router ni trazas.
