# Computer use para un 4B local — investigación (2026-10-15, subagente del PC)

Advertencia: no hay resultados publicados de un modelo ≤ 8B con árbol UIA en escritorio. El único pequeño medido en
Windows (Phi-3-V, Windows Agent Arena) hace 1–4 %. Lo de abajo sale de ablaciones con modelos grandes y de las cifras
del propio Qwen.

## Evidencia

- **Windows Agent Arena / Navi** (arXiv 2409.08264, 2024): humanos 74,5 %; mejor GPT-4V+OmniParser+UIA 19,5 %;
  Phi-3-V 1,3–4,0 %. Las marcas UIA mejoran a los modelos abiertos un 52 %. Fallo típico: nombra bien el objetivo y
  elige mal el número de marca.
- **UFO2** (arXiv 2504.14603, 2025): sólo controles `is_visible` + `is_enabled`, con tipo, etiqueta, caja e id estable;
  límite de 30 pasos; las tareas que salen toman 6–10 pasos; > 62 % de los fallos = no encontrar el control. Valida cada
  acción (habilitado/visible) antes de ejecutarla y corta en el primer fallo.
- **OSWorld** (arXiv 2404.07972): árbol filtrado a nodos visibles con texto, tabla tab-separada (tag, nombre, texto,
  posición, tamaño); ~6k tokens cubren el 90 %; límite de 15 pasos. Más historial en texto ayuda; en capturas, no.
- **OS-Harm** (arXiv 2506.14866): árbol sólo 18–21 % frente a captura sola 5–15 % (modelos grandes).
- **iOSWorld** (arXiv 2606.09764, por resumen): a modelos menores el árbol completo los satura.
- **AgentOccam** (ICLR 2025, arXiv 2410.13825): sólo cambiar la observación y el juego de acciones (quitar redundancia,
  menos acciones y de más alto nivel, Markdown conciso) dio +161 %. Es la palanca permitida: presentación.
- **Qwen3.5-4B** tiene visión nativa (model card: ScreenSpot-Pro 60,3; OSWorld-Verified 35,6 con su propio arnés de
  capturas). mmproj F16 = 672 MB; 1 token por 32×32 px (1280×720 ≈ 900 tokens). Con el prefijo de 39k en KV, visión en
  GPU rompe los 4 GB (estimación); `--no-mmproj-offload` la deja en CPU.
- **Práctica:** Windows-MCP/Windows-Use (UIA primero, ids, WaitFor, 25 pasos; «no sirve para videojuegos»); docs de
  Anthropic computer use («a veces asume resultados»: verificar tras cada paso; atajos de teclado); docs de OpenAI CUA
  (estado fresco tras cada acción, verificar en la app y no en el mensaje final, límites de pasos); diferencias
  antes/después (Mobile-Agent-v2, arXiv 2406.01014) favorecen un diff en texto.

## Recomendaciones para BAXY

- **Vista:** una línea por control `[id] Tipo "Nombre" =valor {disabled|focused|checked}`; sin rect (a lo sumo zona
  gruesa); quitar OCR que repite nombres; título, foco, `(+N más — scroll)`; 40–60 controles (≤ 1,5k tokens); ids
  estables entre pasos.
- **Acciones mínimas:** click{id}, type{text,id?}, key{combo}, scroll{id?,dir}, abrir app, enfocar ventana, esperar,
  mirar (captura bajo pedido).
- **Tras cada acción:** ok/error + causa, eco de lo hecho y un diff de la vista; vista entera sólo si cambió la ventana;
  id inexistente o deshabilitado → error antes de ejecutar.
- **Límites:** ~15 pasos y un tope de tiempo; la misma acción tres veces se le devuelve como error.
- **Línea de las reglas:** legítimo = filtrar visibles/habilitados, ids estables, diffs, validar antes de ejecutar,
  límites, qué herramientas se muestran según el modo, captura bajo pedido. Zona gris = ordenar controles por relevancia
  a la meta, operaciones compuestas por app, scroll automático. Prohibido = reintentar con otra acción, completar
  argumentos, cualquier fallback que actúe cuando el modelo no.
