# Goal y prompt de reanudación para Claude Fable 5.1 — C03 (2026-09-18)

Para pegar como GOAL de una sesión nueva de Fable 5.1 en el computador principal, tras
clonar/traer la rama `codex/kiro-goal-c03` y abrir el repo en Visual Studio / la terminal.

---

## GOAL (objetivo persistente)

Eres el **escritor raíz único** del goal **C03 (respuesta veraz de BAXY)** en la rama
`codex/kiro-goal-c03`. Tienes **dos cierres que lograr, y no son lo mismo**:

1. **El registro de 742 filas** (la encuesta privada): subir «cubiertos» de **653/742**
   hacia **742**, adjudicando con honestidad cada fila (crédito, límite honesto, o no
   aplica con su causa). Las *tandas* son el método; el registro es la fuente de verdad.
2. **El goal formal C03** (hoy **3/11** en las filas C03 formales): completarlo también.

Trabaja **autónomamente hasta el cierre demostrado de ambos**. No marques completado ni
bloqueado por cansancio, presupuesto o un fallo aislado. Reporta con honestidad: si algo
falla, dilo con la evidencia; si algo quedó fuera, dilo y por qué.

---

## PROMPT DE ARRANQUE (leer y ejecutar en orden)

### 1. Reanuda leyendo, no adivinando
- Confirma la rama: `git -C "<repo>" rev-parse --abbrev-ref HEAD` = `codex/kiro-goal-c03`;
  `git fetch` y `git log --oneline -5`. El último estado empujado incluye el mecanismo de
  envío de mensajería y la tanda MSGSEND1845 armada.
- **Lee `artifacts/comprobaciones/C03/HANDOFF.md`**: abre con un bloque **REANUDACIÓN** que
  dice el estado exacto (653/742, 16/35 categorías cerradas) y **la acción inmediata**.
- Lee `artifacts/comprobaciones/C03/CHECKPOINT.md` (primer bloque = vigente),
  `CURRENT_CATEGORY_COUNTS.md`, `CONDICIONES_POR_CATEGORIA_2026-09-13.md` (frentes y
  condiciones), y el `ESTADO_PARA_DUENO_*` más reciente.
- La **memoria** de la campaña (los aprendizajes por instrumento) vive en
  `~/.claude/projects/<slug>/memory/` de la máquina donde se trabajó; si no está en el
  computador principal, el HANDOFF y `CONDICIONES_*` bastan para continuar, pero conviene
  traerla.

### 2. Verifica las dependencias privadas (NO están en git, por privacidad)
Necesitas presente en el computador principal, bajo `C:/Users/<user>/AppData/Local/BAXY/`:
- `C03-survey-requirements336-private/requirements.jsonl` — **el registro de 742 filas**
  (fuente de verdad de cobertura). Sin esto no puedes medir ni adjudicar.
- Los instrumentos sellados `C03-*-instrument-v1`, el utillaje `C03-*-tooling`, los builds
  oficiales `C03-repairs*-build` y el runtime del producto `BAXYRuntime` (producto + mente
  + inferencia GPU) y Tesseract para OCR.
- Si falta algo, tráelo desde la máquina anterior (o pídeselo al dueño). No inventes el
  registro ni la cobertura.

### 3. Acción inmediata: MSGSEND1845 (envío real de mensajería, decisión §6)
Ya está **construido y armado** (falta sólo sellar y correr). Fuente comprometida en
`9ca7f569`. Utillaje en `BASE/C03-msgsend1845-tooling` (14 ficheros: make/resize/adapt,
`derive_msgsend1845.py`, `build_msgsend1845.py`, `setup_msgsend1845.sh`,
`decisions_msgsend1845_fill.py`, `docs_msgsend1845.py`, `write_results1845.py`,
`approve_message_send.py`, `msgsend_case.sh`). Pasos (escritor único):
1. Build oficial del HEAD: copia `build.py` de un `C03-repairs*-build` a
   `C03-repairs1845-build`, córrelo, `dotnet build-server shutdown`.
2. Sella: `derive_msgsend1845.py`, `build_msgsend1845.py`; `root_prepare.py` con
   `--expected-head <HEAD>` y `--expected-registry-sha256 <reg de CHROMETABS1843>`.
3. **PRUEBA SUPERVISADA = caso 0**: `bash msgsend_case.sh msgsend1845 0 whatsapp Musica`
   — es un envío real a **«Música»**. Verifica el recibo (`sent true`,
   `forcedDestination` = Música) y que el mensaje aparece en el chat (el adaptador ya lo
   corrobora por OCR). Sólo si verifica, corre 1–4 y adjudica (decisions →
   `root_adjudicate_from_decisions.py --apply` → publish → `docs_msgsend1845.py` → commit+push).
4. Acredita el literal H0005 (destinatario «Música» = destino forzado → fiel). Los
   literales a terceros (otras tandas de mensajería) se **miden pero quedan sin crédito con
   la causa**, por decisión del dueño.

### 4. Seguridad de mensajería (decisión del dueño §6) — canales de prueba propios
- Los sends van SIEMPRE, por construcción del adaptador (`ForcedTestDestination`), a los
  **canales de prueba del dueño**: WhatsApp → grupo **«Música»**, Discord → usuario
  **«Valeria»**. **Nunca al destinatario nombrado.** El final dice la verdad («lo envié a
  tu grupo de pruebas Música, no al chat de Lucas»).
- **Estos dos canales son 100 % seguros: los creó el dueño solamente para probar BAXY.** No
  son personales, no hay privacidad de terceros, y el envío está **autorizado por él**. No
  estás haciendo nada personal ni entrando en su privacidad.
- **Leer chats sigue fuera** («qué me escribió mamá»): defiere o límite honesto.

### 5. El método de tanda (para cada capacidad o repaso)
`make_<N>.py` (spec) → `next_tanda.py <spec.json>` → `derive_<N>.py` → `adapt_<N>.py` →
build oficial del HEAD → `build_<N>.py` (sella el instrumento) → `root_prepare.py` →
correr los 5 casos con su driver → `decisions_<N>_fill.py` →
`root_adjudicate_from_decisions.py --apply` → `root_publish_from_adjudication.py --apply` →
`docs_<N>.py` → commit + push. Panel típico: 1–2 literales + 2 variantes + 1–2 límites.
El delta de fuente es un **conjunto de nombres**; cambiar el contenido de un fichero ya en
el conjunto es gratis. Cada re-sello necesita nodos MSBuild en 0 (`dotnet build-server
shutdown` con el dotnet correcto; termina los nodos `nodemode:1` propios que queden).

### 6. Reglas duras del dueño (NUNCA romper)
- **No ejecutar tests** (ni dueñas, Fast ni Full). Compilar sí cuando cambie fuente
  compilada (`dotnet build src/Baxy.App/Baxy.App.csproj`); builds oficiales por `build.py`.
- **Escritor único, una sola inferencia GPU.** No abras dos corridas en paralelo.
- **Nunca bajes las guardas** (RAM libre inicial 4000 / mín 768 MiB; GPU stop 3800 / techo
  4096; 900 s por tanda / 120000 ms por turno). Si la RAM falta, el dueño autorizó cerrar
  lo necesario para liberarla (cerrar ordenado, sin perder documentos; nunca cerrar el IDE
  que aloja la sesión ni apagar/reiniciar el PC).
- **Nunca cierres las apps en primer plano del dueño** salvo autorización; nunca mates los
  nodos MSBuild de su IDE; nunca parchees un instrumento sellado; **nunca edites `src` entre
  la ejecución de una tanda y su adjudicación** (si hay que arreglar, abandona la corrida
  sin adjudicar, arregla, re-sella, re-corre).
- **Crédito** de un case_id sólo si su literal ejecutó en el candidato actual, fue útil y
  fiel, y **exactamente dos variantes en-tanda pasaron**. Los 3 negativos y los 18 sin marcar
  nunca se acreditan.
- **Stage rutas exactas** (`git add <ruta>`), **nunca `git add .`**. Preserva `main` y el
  WIP ajeno (`.codex/config.toml`, `AGENTS.md`, `documentacion/sprints/...`,
  `.codex-remote-attachments/`, `AUTORIZACION_ULTRA_*`, `DECISIONES_DUENO_2026-09-16.md`).
  La contabilidad por categoría sigue `SURVEY_TAXONOMY846.json`.
- **Atribución del commit** (línea final): `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- **No publiques textos privados de la encuesta** (ubicaciones, OCR de pantalla, títulos de
  juegos del dueño sólo hasheados, SSIDs enmascarados). Publica checkpoints.

### 7. Frentes conocidos (de `CONDICIONES_*` y el HANDOFF)
- **Mensajería**: MSGSEND1845 lista (arriba). Después, panel grande de mensajería (más
  literales de «Música» y de «Valeria»/Discord) sobre el mismo mecanismo; correo (mailto/
  Outlook) es un mecanismo aparte por construir.
- **Diferidos por el dueño**: streaming (sin fallback de navegador → punto 7), power
  (apagar/reiniciar).
- **Condicionado**: H0060 (el buscador público devuelve resultados no relacionados a
  preguntas de varias palabras).
- **Por construir (medibles)**: filas de UI/clic (Steam instalar, Among Us), Steam/Epic por
  GUI (computer-use), cadenas multi-paso (carpeta+zip, Opera+receta+captura+cierre).
- 18 filas sin marcar + 3 negativas nunca se acreditan; 7 fragmentos ininteligibles quedan
  como límite/aclaración honesta.

### 8. Estilo de trabajo esperado (para Fable 5.1)
- Actúa cuando tengas lo suficiente; no re-deduzcas lo ya establecido en el HANDOFF ni
  re-litigues decisiones del dueño ya tomadas.
- Prefiere leer los ficheros de estado y el código antes de suponer. Verifica cada cambio
  compilando y, cuando midas, ejecutando la tanda; no declares verde sin evidencia.
- Un fallo aislado no es el cierre: arréglalo (re-sella, re-corre) y sigue. El diagnóstico
  antes que la conjetura: cuando un compositor rechace, captura el borrador real y su motivo
  (log opt-in en `_capture_compose_stage`) en vez de adivinar.
- Cierra cada tanda commiteada y empujada; deja el árbol y el registro limpios; mantén el
  HANDOFF al día para que cualquier reanudación no pierda nada.

**Empieza por el paso 1 (leer el HANDOFF), luego el paso 2 (verificar el registro privado),
luego el paso 3 (correr MSGSEND1845 empezando por la prueba supervisada del caso 0).**
