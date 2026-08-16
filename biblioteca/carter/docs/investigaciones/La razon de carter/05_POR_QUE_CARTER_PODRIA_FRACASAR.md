# 05 - Por que Carter podria fracasar

Fecha de generacion: 2026-05-08

## Veredicto critico

Carter puede fracasar aunque la arquitectura sea buena. La razon principal: su promesa toca el lugar mas dificil de los agentes actuales, que es actuar en una PC real con apps desordenadas, estado cambiante, lenguaje ambiguo, safety real y latencia baja.

## Riesgos duros

| Riesgo | Por que puede matar la tesis | Evidencia o senal local |
|---|---|---|
| Limitaciones del modelo local | Un 4B local puede no sostener razonamiento, replanificacion o lenguaje ambiguo. | El reporte 540 menciona rendirse, no entender o no tener herramienta como patron de fallo. |
| GUI moderna dificil | CEF/Chromium, Electron, canvas, custom controls y escalado DPI rompen UIA/OCR. | `gui_universal.py` declara tiers, pero VLM no aparece activo; C13 GUI es debil en reporte local. |
| Apps como Steam/Discord/Spotify | Launchers, actualizaciones, overlays y ventanas custom hacen dificil verificar exito real. | `apps.py` mejora Steam manifests/protocols, pero eso no resuelve interaccion dentro de cada app. |
| Fragilidad Windows automation | Hotkeys, foco, permisos, UAC, idioma, tema y multi-monitor cambian resultados. | `gui.py` usa pyautogui/Win+arrows/frame diff; util pero fragil. |
| Competidores cloud/VLM | Agent-S y modelos multimodales pueden ver y razonar mejor sobre pantalla. | Agent-S declara resultados OSWorld/WindowsAgentArena fuertes en README. |
| Scope demasiado grande | Apps, archivos, terminal, browser, registry, Steam, GUI, memoria, voz y vision pueden dispersar el proyecto. | La lista de tools ya es amplia; las categorias debiles son precisamente integracion compleja. |
| Riesgo academico | Puede parecer integracion de APIs, no investigacion. | La contribucion debe formularse alrededor de verificacion/evaluacion, no "hice un asistente". |
| Mantenimiento | Windows, apps, browsers y modelos cambian constantemente. | Resolvers y verifiers requieren actualizacion continua. |
| Benchmarks propios sesgados | La matrix 540 ayuda, pero si no es publica/reproducible no convence. | Hay conflicto entre numeros del prompt y reporte local. |
| Auditor automatico defectuoso | Falsos positivos/falsos negativos pueden ocultar fallos reales. | `CARTER_540_REAL_PROGRESS_REPORT.md` muestra 489 automatico vs 417 manual. |
| Latency blow-up | Vision, 14B, best-of-N o multi-step pueden romper experiencia tipo Alexa. | El reporte sugiere modelos mas grandes para mayor score, pero eso tensiona latencia. |
| Safety | Un agente OS puede borrar, mover, ejecutar o filtrar datos por error. | Safety existe, pero prompt/command injection necesita pruebas adversariales. |
| UX | Si pide confirmacion demasiado o falla con lenguaje natural, el usuario vuelve al mouse. | Fallos por "no te entendi" destruyen confianza rapidamente. |

## Donde Carter pierde claramente hoy

- Contra Agent-S en GUI research y benchmarks publicados.
- Contra OpenHands en coding agent y SWE-bench.
- Contra Open Interpreter en ejecucion flexible de codigo local.
- Contra AutoGPT en plataforma de workflows continuos y builder.
- Contra LangGraph/AutoGen en framework general para agentes.
- Contra openclaw en asistente multi-canal y ecosistema de dispositivos.
- Contra Mark-XXXIX en demo live multimodal/voz si se compara solo espectacularidad.

Esto no invalida Carter, pero obliga a no mentir sobre el eje competitivo.

## Debilidad mas peligrosa: fake success

La peor falla no es fallar. La peor falla es decir que hizo algo sin haberlo hecho. Carter reconoce este problema en su arquitectura con `verify.py` y `verifier_orchestrator.py`, pero la matrix local muestra que la auditoria automatica todavia sobreestima. Si Carter no logra ser mas honesto que competidores, pierde su mayor razon de existir.

## Debilidad tecnica: verifiers superficiales

Un verifier puede comprobar que existe un archivo, que una ventana cambio o que un proceso corre. Eso no siempre comprueba la intencion del usuario. Ejemplos:

- Abrir Steam no significa abrir el juego correcto.
- Cambiar una ventana no significa organizar el escritorio como el usuario queria.
- Exit code 0 no significa que el comando hizo lo correcto semanticamente.
- Frame diff no significa exito, solo cambio visual.

La tesis necesita distinguir verificacion estructural de verificacion semantica.

## Debilidad de producto: demasiada amplitud

Si Carter intenta cubrir voz, vision, browser, office, gaming, terminal, files, registry, automation, memory y skills al mismo tiempo, puede terminar mediocre en todo. Producto final razonable significa cerrar un set pequeno de tareas de alto valor, no completar una lista infinita de capacidades.

## Debilidad academica: contribucion mal formulada

"Un asistente local para Windows" puede sonar a integracion. Una tesis defendible debe decir:

- que problema mide,
- que baseline compara,
- que metrica mejora,
- que tradeoff acepta,
- que limitaciones reconoce.

Sin eso, Carter es proyecto de software interesante, no tesis fuerte.

## Clasificación de afirmaciones

Evidencia: reporte 540 local, categorias debiles, codigo de GUI/verifiers/safety, READMEs de competidores.

Inferencia: competidores cloud/VLM tienen ventaja natural en GUI visual compleja.

Hipotesis: usuarios toleraran menos capacidad si reciben privacidad y honestidad.

Opinion estrategica: Carter debe recortar scope antes de presentarse publicamente.

Claim no defendible: "Carter es seguro porque tiene confirmaciones"; safety requiere pruebas adversariales, no solo prompts.

## Limitaciones de este análisis

No se hizo pentest, fuzzing, prueba con usuarios ni evaluacion multi-hardware. Este informe identifica riesgos por arquitectura y evidencia local, no fallos demostrados en cada app.

## Qué falta verificar

- Apps Electron/CEF reales: Discord, Spotify, Steam, VS Code, navegador.
- Multi-monitor, DPI alto, idioma Windows distinto, permisos UAC.
- Prompt injection desde web/file/clipboard.
- Recovery real despues de tool failure.
- Comparacion con usuario manual y competidores.

## Conclusión honesta

Carter fracasa si intenta venderse como asistente universal antes de demostrar robustez. Su oportunidad existe, pero tambien es facil destruirla: bastan GUI fragil, evaluacion sesgada o safety superficial para que parezca otro demo agentico mas.
