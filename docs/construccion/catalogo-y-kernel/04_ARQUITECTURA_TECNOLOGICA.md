# Arquitectura tecnológica — base aprobada y mapa de candidatos

## Estado de estas decisiones

El torneo reproducible cerró la arquitectura base el 2026-07-14. El ganador es
shell .NET 10 WPF + core .NET NativeAOT; WPF + Rust estático queda como fallback
Pareto. La decisión canónica está en
`contexto/04_arquitectura/ADR/ADR-0001-arquitectura-base-baxy-1.md` y el
scorecard en `artifacts/technology_tournament/round_b_scorecard.json`.

El resto de este documento conserva los candidatos informados por la historia
para que no se pierdan y para guiar torneos de subsistema. Ninguna pieza gana
por existir en `legacy/`, por comodidad ni por recomendación de un agente.
React, Tauri, Rust, Python, FastAPI, Gemma, llama.cpp, Piper, ONNX y SQLite
siguen siendo candidatos únicamente donde la decisión base no los cerró.

Lo único fijado de antemano es el resultado de producto:

- asistente local y privado para Windows;
- entrada por voz y texto, conversación natural y personalidad BAXY;
- ejecución de misiones reales concatenando capacidades;
- verificación antes de declarar éxito;
- confirmación proporcional al riesgo real;
- identidad visual de la GUI conservada, aunque pueda cambiar su tecnología;
- perfil cómodo en 4 GB de VRAM, cercano a 3 GB cuando sea viable;
- instalación, actualización, recuperación y desinstalación confiables;
- accesibilidad y degradación honesta.

Quedaron fijados el shell WPF, core NativeAOT, separación shell/core, frontera
JSONL stdin/stdout y ownership por Job Object. No están fijados base de datos,
runtime de inferencia, modelo, router, planner, VAD, STT, TTS, OCR,
computer-use ni instalador final.

## Torneo de arquitectura obligatorio

Antes de cerrar el diseño se comparan, como mínimo, arquitecturas completas de
estas familias:

1. core Python con shell nativo y runtimes sidecar;
2. core .NET/Windows App SDK con inferencia y componentes nativos;
3. core Rust con sidecars mínimos para modelos o automatización;
4. otra alternativa seria descubierta en la investigación, incluida una
   combinación distinta si evita las debilidades anteriores.

Para cada subsistema se estudian al menos tres alternativas viables cuando
existan y también la opción de eliminarlo o integrarlo en otra capa. No basta
una comparación documental: se implementa el menor corte vertical comparable
que permita medir una misión real de extremo a extremo.

La matriz ponderada inicial es:

| Criterio | Peso |
|---|---:|
| Misiones reales completadas y verificadas | 25 % |
| RAM, VRAM, disco y consumo en hardware objetivo | 15 % |
| Latencia de interacción y arranque | 10 % |
| UX conversacional y accesibilidad | 10 % |
| Privacidad y seguridad local | 10 % |
| Instalación, lifecycle, recuperación y cleanup | 10 % |
| Testabilidad, mantenibilidad y capacidad de depuración | 10 % |
| Licencia, madurez y riesgo de cadena de suministro | 5 % |
| Costo de migración y reutilización demostrablemente útil | 5 % |

Los pesos pueden corregirse antes de medir, con justificación de producto, pero
no después para favorecer a un ganador. Se publican hardware, versiones,
corpus, comandos, mediciones crudas, fallos y alternativas rechazadas. Una
opción no gana por sumar componentes localmente óptimos: debe probarse también
como sistema completo bajo concurrencia, fallos y presupuesto real.

La salida del torneo debe incluir una frontera de Pareto, el stack elegido, un
fallback reproducible y ADRs de las alternativas descartadas. Reutilizar código
histórico cuenta solo como una métrica de costo; no sustituye confiabilidad.

## Hipótesis históricas por parte

Esta tabla es un inventario de contendientes iniciales, no una decisión:

| Parte | Candidato histórico que debe competir | Papel a demostrar |
|---|---|---|
| GUI | React 19, TypeScript, Vite | Reutilizar el diseño actual y mostrar conversación/progreso |
| Shell Windows | Tauri 2 + WebView2 + Rust | Ventana, permisos, sidecars, instalación y lifecycle |
| Core | Python 3.12, asyncio, Pydantic 2 | Misiones, estados, contratos y coordinación |
| IPC local | FastAPI/Uvicorn, SSE, token efímero | Comunicación GUI/core solo en loopback |
| Cerebro local | Gemma 4 E2B QAT Q4_0 GGUF | Conversación, planificación acotada, visión/audio candidatos |
| Runtime LLM | llama.cpp/llama-server pinneado | Inferencia CPU/CUDA, schemas, métricas y multimodal |
| Routing | reglas + embeddings ONNX + Gemma sobre shortlist | Selección segura sin catálogo completo |
| Tool engine | operaciones Pydantic + DAG de misiones | Capacidades tipadas, composición y recuperación |
| Voz activa | WASAPI + Silero VAD ONNX + openWakeWord | Captura, detección de habla y wake word |
| STT | Gemma 4 si pasa gates; Qwen-ASR/Parakeet/Whisper fallback | Transcripción local con perfiles por idioma |
| TTS | Piper local | Respuesta de voz sin nube |
| Visión | Windows Graphics Capture + Windows OCR + Gemma 4 | Pantalla, OCR y comprensión corroborada |
| Computer-use | UI Automation, Win32/WinRT, Playwright | Actuar nativamente antes de usar visión/clics |
| Memoria | SQLite, WAL, FTS5, embeddings CPU | Preferencias, episodios y búsqueda local |
| Secretos | DPAPI/Credential Manager | Cifrado ligado al usuario de Windows |
| Procesos | Windows Job Objects | Ownership, límites, cleanup y reinicios |
| Observabilidad | JSONL redactado + SQLite de eventos | Evidencia, métricas y replay sin secretos |
| Pruebas | pytest, Hypothesis, Vitest, Playwright, gates Windows | Unitarias, contratos, E2E y físicas |
| Distribución | Tauri MSI/NSIS + sidecar compilado | Instalación, actualización, doctor y desinstalación |

El torneo no se limita a esa columna. Su lista inicial de contendientes debe
incluir al menos:

| Subsistema | Familias a comparar |
|---|---|
| GUI y shell | React conservado dentro de Tauri; WebView2 con host .NET/WinUI; UI nativa que reproduzca fielmente el diseño; Electron solo si justifica su costo |
| Core de misiones | Python; .NET; Rust; proceso único o combinación mínima de sidecars |
| IPC | sin IPC/proceso único; Named Pipes; loopback autenticado; gRPC o protocolo binario local |
| Inferencia | llama.cpp; ONNX Runtime/GenAI o DirectML cuando soporte el modelo; otro runtime local vigente con benchmark reproducible |
| Cerebro | multimodal unificado; modelos especialistas coordinados; rutas determinísticas sin LLM más modelo solo para conversación |
| Routing y planning | reglas + retrieval + LLM acotado; DSL/workflows con planner; modelo pequeño especializado; combinación con policy determinística |
| Voz/STT/TTS | VAD y wake históricos contra opciones nativas/WebRTC; Gemma/Qwen/Whisper/Parakeet; Piper/SAPI/otros motores locales medidos |
| Visión y OCR | modelo unificado; VLM especialista; OCR/UIA nativos; combinación corroborada |
| Computer-use | APIs de aplicación; Win32/WinRT/COM/UIA; DOM/CDP; visión e input simulado como último recurso |
| Memoria | SQLite/FTS; event store embebido; índice vectorial separado solo si aporta calidad; memoria mínima sin embeddings |
| Distribución | Tauri/WiX/NSIS; .NET single-file/MSIX; binario Rust nativo; otra opción que gane instalación y rollback |

Las familias no son cuotas ni ganadores anticipados. Se eliminan pronto las
incompatibles con Windows, privacidad, licencia o 4 GB; las restantes compiten
con el mismo corpus y el mismo protocolo.

## 1. Interfaz

### Candidato histórico

- React 19.
- TypeScript.
- Vite.
- CSS y componentes visuales recuperados de legacy\gui\ui_field.
- Tauri 2 como contenedor de escritorio sobre WebView2.

### Razón

La GUI actual ya expresa la identidad visual elegida por el usuario. React,
TypeScript y Vite ya estaban presentes en el último checkpoint. Tauri permite
un shell nativo pequeño y genera instaladores MSI mediante WiX o ejecutables
NSIS; en Windows usa WebView2.

### Contrato

- conversación como vista principal;
- estados listening, understanding, acting, verifying, done, blocked y failed;
- progreso en lenguaje humano;
- visor técnico apagado y opt-in;
- accesibilidad por teclado, lector de pantalla y contraste;
- ninguna respuesta depende de renderizar JSON.

### Gate

Comparar Tauri con el launcher WebView2 archivado en:

- RAM en idle;
- tiempo de arranque;
- comportamiento offline;
- accesibilidad;
- firma/instalación;
- control de sidecars;
- recuperación tras crash.

Si Tauri empeora materialmente el presupuesto, conservar React/Vite y usar el
launcher más ligero que cumpla lifecycle y seguridad.

Fuente:

https://v2.tauri.app/distribute/windows-installer/

## 2. Core de misiones

### Candidato histórico

- Python 3.12.
- asyncio para concurrencia controlada.
- Pydantic 2 y JSON Schema para todos los contratos.
- dataclasses/enums únicamente en componentes internos simples.
- httpx para clientes HTTP acotados.

### Responsabilidades

- ConversationState.
- MissionPlan y MissionStep.
- OperationRequest y OperationResult.
- Effect/Risk classification.
- autorización y grants.
- locks de recursos.
- ejecución, verificación y compensación.
- journal duradero.
- narración y memoria.

Python merece un prototipo porque gran parte de la evidencia, corpus, modelos y
automatización histórica vive en ese ecosistema. Eso reduce costo de migración,
pero no prueba que deba ser el core. Debe compararse con .NET, Rust y cualquier
alternativa seria en misiones, recursos, automatización Windows, empaquetado y
depuración. Tampoco se reescribe en Rust o .NET por ideología.

## 3. Comunicación GUI/core

### Candidato histórico

- Core FastAPI/Uvicorn en 127.0.0.1.
- Puerto efímero, nunca 0.0.0.0.
- token de sesión aleatorio entregado por el shell.
- validación estricta de Host, Origin y content type.
- SSE para eventos ordenados de progreso.
- HTTP para comandos idempotentes y adjuntos acotados.

En este candidato, el shell Tauri crea y supervisa el core. El core no se
anuncia en la red ni acepta peticiones sin identidad de sesión. Debe competir
con Windows Named Pipes, gRPC/IPC local y un proceso único; se mide superficie,
latencia, accesibilidad, recuperación y complejidad operativa.

## 4. Modelo principal y runtime

### Candidato histórico

- Gemma 4 E2B instruction-tuned.
- checkpoint oficial QAT Q4_0 GGUF.
- llama.cpp/llama-server fijado por commit y hashes.
- CUDA en NVIDIA, CPU fallback y perfiles alternativos medidos.

Google documenta que Gemma 4 E2B admite texto, imágenes, audio, function
calling y contexto de hasta 128K. Los checkpoints QAT GGUF están destinados a
llama.cpp y hardware de consumo. Esto lo convierte en el mejor candidato
inicial para el límite de 3–4 GB, no en ganador automático.

llama-server aporta:

- inferencia cuantizada CPU/GPU;
- API de chat;
- multimodal mediante libmtmd;
- function calling;
- respuestas restringidas por schema;
- health y métricas.

El soporte de audio de llama.cpp continúa descrito como altamente experimental
y existen issues recientes de parsing/tool calling en Gemma 4. Por tanto:

- no se confía directamente en tool calls sin parser y schema propios;
- el modelo solo recibe un shortlist;
- cada nombre y argumento se valida;
- el runtime se identifica por PID, parent, executable, commit, modelo, mmproj
  y puerto;
- audio, visión y routing tienen gates independientes.

Fuentes:

- https://ai.google.dev/gemma/docs/core/model_card_4
- https://ai.google.dev/gemma/docs/core
- https://ai.google.dev/gemma/docs/capabilities/text/function-calling-gemma4
- https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md
- https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md

### Perfil eco inicial que debe revalidarse

- un solo slot/usuario;
- parallelism 1;
- flash attention;
- KV cache cuantizada;
- contexto cercano a 6144 para interacción cotidiana;
- mmproj en CPU cuando reduzca VRAM sin latencia inaceptable;
- límite explícito de cache RAM;
- sin speculative/MTP en estable hasta probar estabilidad y presupuesto.

Los flags exactos se fijarán después de comprobar la versión de llama.cpp; no
se copian a ciegas entre releases.

## 5. Routing, planificación y tools

### Shortlist híbrido

1. Guardas determinísticas para negación, no_tool, dominios y efectos.
2. Recuperación semántica con embeddings pequeños ejecutados en CPU/ONNX.
3. Selección de candidatos por registro y contexto.
4. Gemma decide únicamente entre los candidatos.
5. Grounder determinístico resuelve entidades.
6. Policy engine autoriza.
7. Executor llama operaciones por allowlist.

### Operaciones

Cada operación incluye:

- nombre estable;
- schema Pydantic;
- efecto y riesgo;
- precondiciones;
- recursos y locks;
- timeout;
- ejecutor;
- verificador independiente;
- compensación o explicación de irreversibilidad;
- redacción de datos;
- pruebas.

### Misiones

Un MissionGraph/DAG representa dependencias y pasos paralelos. Permite que
Steam instale mientras Spotify reproduce, pero impide que una compra ocurra
sin autorización. Los workflows históricos son plantillas, no el único modo de
composición.

FunctionGemma 270M, el encoder histórico o un reranker compacto pueden
mantenerse como fallback solo si una evaluación demuestra ganancia real. No se
conservan por nostalgia.

## 6. Voz

### Captura

- WASAPI mediante una capa nativa o sounddevice/PortAudio.
- formato interno PCM mono 16 kHz.
- ring buffer acotado.
- device discovery y hotplug.
- loopback/AEC medido.

### VAD

Silero VAD v6 en ONNX/CPU es un candidato fuerte por ser pequeño, streaming y
multilingüe. Debe competir con WebRTC VAD, soluciones nativas y la opción que
mejor surja del corpus; ninguna ruta debe consumir VRAM reservada al LLM sin
una ganancia demostrada.

Fuente:

https://github.com/snakers4/silero-vad

### Wake word

- openWakeWord en ONNX como candidato.
- modelo histórico “Baxy” recuperado y reentrenado si el corpus lo justifica.
- segundo verificador por voz/contexto para reducir falsos positivos.
- push-to-talk siempre disponible.

openWakeWord soporta ONNX en Windows e integra VAD, pero su mantenimiento y
calidad para “Baxy” deben medirse contra los artefactos históricos.

Fuente:

https://github.com/dscripka/openWakeWord

### STT

Candidatos iniciales, sin orden de preferencia hasta medirlos:

1. Gemma 4 E2B audio como ruta unificada.
2. Qwen-ASR compatible con el runtime local para español/spanglish.
3. Whisper.cpp pequeño como fallback multilingüe.
4. Parakeet TDT int8 mediante sherpa-onnx para el perfil inglés.

Gemma solo será default si supera WAVs y voz real en español, inglés,
spanglish, nombres de aplicaciones, silencio y ruido. Google limita sus
entradas de audio a 30 segundos, por lo que la segmentación es obligatoria.

sherpa-onnx publica ejecutables Windows y un Parakeet TDT 0.6B int8, pero ese
perfil no sustituye por sí solo la cobertura multilingüe.

Fuentes:

- https://ai.google.dev/gemma/docs/capabilities/audio
- https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/nemo-transducer-models.html
- https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md

### TTS

Piper local es un candidato histórico:

- voz offline;
- streaming por frases;
- cancelación/interrupción;
- ducking;
- cola durable;
- pronunciaciones personalizadas.

El proyecto OHF Piper actual es GPL-3.0; antes de distribuir BAXY se realiza
una revisión de licencia y empaquetado.

Fuente:

https://github.com/OHF-voice/piper1-gpl

## 7. Visión y OCR

### Captura

- Windows Graphics Capture/WinRT para ventanas y pantalla.
- captura por demanda y con indicadores de privacidad.
- redacción o exclusión de regiones sensibles cuando corresponda.

### Ground truth

Antes del modelo:

- HWND;
- PID y árbol;
- executable y firma;
- título de ventana;
- UI Automation tree;
- OCR local.

Después Gemma 4 recibe imagen y contexto corroborado. La respuesta distingue
“veo”, “las señales indican” y “no puedo identificar”.

### OCR

- Windows.Media.Ocr como candidato local.
- Tesseract/otro OCR solo como fallback medido.
- Gemma 4 con mayor presupuesto visual para texto difícil.

Google documenta presupuestos visuales variables de 70 a 1120 tokens. BAXY
elige bajo para clasificación y alto para OCR, midiendo latencia y VRAM.

Fuente:

https://ai.google.dev/gemma/docs/capabilities/vision

## 8. Computer-use e integraciones

### Orden de preferencia

1. API o protocolo oficial.
2. Win32, WinRT, COM o UI Automation.
3. Playwright/CDP para navegador.
4. OCR + visión + input simulado como último recurso.

### Windows

- Microsoft UI Automation para inspección y acciones accesibles.
- Win32 para ventanas, procesos y foco.
- WinRT para multimedia, notificaciones, captura y APIs modernas.
- pywin32/comtypes en Python o windows-rs desde Rust para primitivas críticas.

Microsoft define UI Automation como el framework de accesibilidad que permite
consultar y manipular elementos de interfaz y automatizar pruebas.

Fuente:

https://learn.microsoft.com/en-us/windows/win32/winauto/entry-uiauto-win32

### Navegador

- Playwright sobre un perfil explícito o CDP controlado.
- locators por role/nombre accesible.
- verificación de URL, título y contenido.
- clic visual solo cuando DOM/accesibilidad no están disponibles.

Fuentes:

- https://playwright.dev/docs/locators
- https://playwright.dev/docs/accessibility-testing

### Office

- COM Automation para Word, Excel y PowerPoint.
- lectura del estado Saved/Dirty antes de cerrar.
- Open XML para documentos que no necesitan una aplicación abierta.
- LibreOffice CLI como fallback cuando corresponda.

### Multimedia

- SMTC/WinRT para now-playing y verificación.
- APIs oficiales de Spotify cuando el usuario conecte su cuenta.
- UIA/browser como fallback.
- nunca aceptar solo una tecla multimedia como prueba.

### Steam

- manifests y libraryfolders para estado local.
- protocolos Steam y UIA para iniciar instalaciones.
- verificación mediante appmanifest, proceso y progreso.
- compra fuera de alcance sin confirmación y flujo específico.

### Archivos

- pathlib y APIs Windows.
- Recycle Bin/IFileOperation para borrado recuperable.
- escritura temporal + fsync + reemplazo/reintento.
- journal y hashes en mutaciones importantes.

### Recordatorios

- SQLite como fuente de verdad.
- scheduler local durable.
- Task Scheduler de Windows solo cuando deba sobrevivir sin BAXY abierto.

## 9. Memoria y RAG

### Candidato histórico

- SQLite.
- WAL y transacciones.
- FTS5 para búsqueda lexical.
- embeddings compactos en CPU mediante ONNX Runtime.
- tablas separadas para preferencias, episodios, hechos, fuentes y expiración.

EmbeddingGemma o el MiniLM histórico se eligen mediante benchmarks de calidad,
latencia, RAM y tamaño. No consumen VRAM mientras Gemma principal está activo.

### Reglas

- todo elemento tiene procedencia y confianza;
- inferencias caducan o requieren confirmación;
- datos sensibles se cifran;
- exportar, editar y olvidar son funciones de producto;
- recuperación usa un presupuesto de contexto.

SQLite:

- https://www.sqlite.org/fts5.html
- https://www.sqlite.org/wal.html

ONNX Runtime admite CPU y varios execution providers. Para portabilidad Windows
se comparan WinML/CPU, otros runtimes y, si aporta valor neto, CUDA sin competir
con el presupuesto del LLM.

Fuentes:

- https://onnxruntime.ai/docs/execution-providers/
- https://onnxruntime.ai/docs/get-started/with-windows.html

## 10. Seguridad y privacidad

- DPAPI/Credential Manager para secretos.
- ACL del usuario en bases y logs.
- allowlist de operaciones.
- argumentos validados antes de ejecutar.
- sanitización de NUL y entradas multimodales.
- canales públicos redactados.
- logs sin prompts privados por defecto.
- confirmación por efecto real.
- límites de tamaño, tiempo y recursos.

DPAPI cifra datos ligados al usuario/equipo y verifica integridad al
desprotegerlos.

Fuente:

https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata

## 11. Lifecycle y recursos

- Windows Job Objects con KILL_ON_JOB_CLOSE.
- un ResourceArbiter decide qué modelo puede ocupar VRAM.
- llama-server, STT alternativo y visión pesada no se cargan a la vez sin
  presupuesto.
- health no basta: se valida identidad.
- puertos exclusivos y efímeros.
- cleanup al cerrar, crash o actualizar.
- límites y métricas por proceso.

Microsoft documenta Job Objects para gestionar árboles como una unidad,
terminarlos juntos y contabilizar recursos.

Fuente:

https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects

## 12. Observabilidad

- eventos estructurados con IDs no sensibles;
- SQLite para journal de misiones;
- JSONL redactado para diagnóstico;
- métricas de latencia, RAM, VRAM y retries;
- replay sin repetir efectos;
- nivel de diagnóstico opt-in.

La interfaz nunca muestra estas estructuras como respuesta del asistente.

## 13. Pruebas

- pytest para core e integraciones.
- Hypothesis para schemas, sanitización y estados.
- Vitest o Node Test para frontend.
- Playwright para GUI y browser.
- corpus JSONL de misiones históricas.
- gates Windows físicos separados de mocks.
- pruebas de voz y visión con ground truth.
- NVML/nvidia-smi para VRAM.
- ETW/psutil/Job Objects para procesos y recursos.

La acceptance se mide por misiones y estado final, no por cantidad de funciones.

## 14. Distribución

- El candidato Tauri puede generar MSI/NSIS; debe competir con MSIX, WiX,
  instaladores .NET y otras rutas reproducibles.
- Si gana un core Python, se comparan Nuitka, PyInstaller y sidecar/runtime
  administrado; .NET y Rust presentan sus rutas equivalentes.
- modelos se descargan por un manifest con hash o se ofrecen en bundle offline.
- doctor valida WebView2, runtime, modelos, audio, GPU y permisos.
- actualización conserva memoria y permite rollback.
- desinstalación ofrece conservar o borrar datos privados.

## Decisiones cerradas por la ronda B

- Shell Windows nativo .NET 10 WPF con core .NET 10 NativeAOT.
- JSONL UTF-8 por stdin/stdout, single-instance y Job Object como invariantes.
- WPF + core Rust estático como fallback Pareto reproducible.
- Los dos shells WebView2 medidos quedan descartados por el gate de red.

## Decisiones que permanecen abiertas

Estas elecciones exigen cortes productivos o torneos de subsistema:
- modelo unificado frente a especialistas y rutas determinísticas;
- llama.cpp frente a otros runtimes compatibles con el hardware objetivo;
- estrategia de router, planner, operaciones y composición;
- Gemma 4 STT frente a Qwen-ASR/Whisper/Parakeet;
- Gemma 4 visión frente a Qwen-VL opt-in;
- Piper frente a motores TTS locales alternativos;
- SQLite/FTS/embeddings frente a diseños de memoria más simples o distintos;
- wrappers, primitivas nativas y estrategia de computer-use;
- instalador productivo, firma, actualización, rollback y distribución;
- perfiles de inferencia, contexto, cache y fallbacks.

El torneo base registra ganador, hardware, corpus, versiones, hashes, métricas,
Pareto y razón. Eso no sustituye las pruebas físicas ni el cierre de los
subsistemas abiertos.
