# Carter v4 — Investigación profunda sobre el ecosistema de skills/MCP/integraciones (mayo 2026)

## TL;DR

- **Recomendación: HÍBRIDO (Opción D), pero asimétrico.** Mantené las 55 tools Python como núcleo no-negociable de Carter; agregá un **cliente MCP opcional, *off by default*** para escalar el catálogo (GitHub, Obsidian, filesystem, Postgres, etc.) sin reescribir nada; y adoptá el **formato SKILL.md de Anthropic como contenedor de "playbooks" locales** (instrucción + script Python opcional) porque el formato es abierto, multiproveedor y se ejecuta 100% local sin tocar la API de Anthropic. NO adoptes Claude Skills runtime, GPTs, Computer Use ni Operator: todos son SaaS obligatorio.
- **MCP en mayo 2026 ya es estándar de facto** (donado por Anthropic al Linux Foundation/Agentic AI Foundation en diciembre 2025; adoptado por OpenAI, Google, Microsoft; ~5.000 servidores públicos). Ollama **no habla MCP nativo todavía** (issue #7865 abierto), así que necesitás un bridge propio o `mcp-client-for-ollama` / MCPHost. Latencia típica stdio local: **4–10 ms por call** + el tiempo de la API real — tolerable para tu budget Alexa-tier (<2 s) si limitás a 3–8 servidores y desactivás warmups pesados.
- **Computer Use / Operator NO son una alternativa para Carter** y NO son complementarios al approach UIA + Win32 + frame-diff: requieren un VLM cloud (Claude Sonnet 4.5 / GPT-5.x), cuestan tokens de visión por cada screenshot, son lentos (segundos por click) y obligan a SaaS. El approach estructural de Carter es **estrictamente superior** para automatización local determinística; lo único que un VLM aportaría es robustez visual ante apps no-UIA, y eso podés cubrirlo a futuro con un VLM local pequeño (Qwen2.5-VL-7B en la 4060 Ti) como *fallback*, no como cerebro.

---

## 1. Glosario conceptual

### a) Anthropic Claude Skills (Agent Skills)

**Qué son técnicamente:** carpetas con un archivo `SKILL.md` (Markdown con frontmatter YAML) que empaquetan **instrucciones procedimentales + recursos opcionales** (scripts ejecutables, referencias, assets/templates). Anthropic las anunció a fines de 2025 y en diciembre de 2025 publicó la **especificación abierta "Agent Skills"** (agentskills.io) — adoptada también por OpenAI Codex CLI y por la comunidad. El formato es portable: el mismo skill funciona en claude.ai, Claude Code, ChatGPT Codex y cualquier agente que implemente el spec.

**Estructura canónica:**

```
my-skill/
├── SKILL.md           # OBLIGATORIO: frontmatter YAML + instrucciones Markdown
├── scripts/           # OPCIONAL: código Python/Bash determinístico
├── references/        # OPCIONAL: docs cargadas on-demand
└── assets/            # OPCIONAL: templates, fonts, imágenes
```

`SKILL.md` mínimo:
```yaml
---
name: my-skill-name           # 64 chars, lowercase + hyphens, no "claude"/"anthropic"
description: What this skill does and WHEN to use it (max 1024 chars)
disable-model-invocation: false
allowed-tools: Read, Grep      # opcional, restringe tools cuando el skill se invoca
---
# Instrucciones Markdown que el modelo lee cuando el skill se activa.
```

**Mecanismo de "progressive disclosure" (clave técnica):**

1. Al boot, el agente carga **solo el `name + description`** de TODOS los skills en el system prompt (cheap).
2. Cuando el modelo decide que un skill es relevante, **lee el `SKILL.md` completo** (lazy).
3. Solo si el SKILL.md lo referencia, carga `references/foo.md` o ejecuta `scripts/bar.py`.

**Cómo se diferencian de tools:** una tool ejecuta y devuelve resultado (un único call atómico). Un skill **prepara al modelo** inyectando instrucciones + opcionalmente herramientas restringidas + opcionalmente código ejecutable. Skills ≠ tools: skills *pueden contener* tools y prompts.

**Publicación / marketplace:** Anthropic mantiene `github.com/anthropics/skills` (skills oficiales: PDF, DOCX, XLSX, PPTX, skill-creator, brand-guidelines, etc.), distribuidos como "Claude Code Plugins". Existe **Anthropic Marketplace** (`https://marketplace.anthropic.com`) y catálogos comunitarios (claudeskills.info, skillsmp.com, claudemarketplaces.com con 140+ skills). Cualquiera puede publicar un marketplace propio con un `marketplace.json`.

**Ejecución 100% local sin API Anthropic:** **SÍ, totalmente posible.** El formato SKILL.md no depende del runtime de Anthropic — es solo Markdown + YAML + scripts. Cualquier agente loop que (1) inyecte el `description` en el system prompt, (2) detecte cuándo el modelo "pide" el skill, y (3) cargue SKILL.md + ejecute scripts, lo soporta. Hay implementaciones para Ollama (e.g., los plugins multi-LLM que listan Ollama como provider en aitmpl.com).

### b) OpenAI GPTs / Custom GPTs / Plugins (estado mayo 2026)

- **ChatGPT Plugins: muertos.** Deprecados oficialmente por OpenAI en abril de 2024 ("ChatGPT plugins have been deprecated").
- **Custom GPTs: vivos pero estancados.** Reemplazaron a los plugins en noviembre de 2023 con el GPT Store (enero 2024). Usan "Actions" (OpenAPI specs) para llamar APIs externas. Siguen disponibles en Plus/Enterprise pero el momentum del producto se mudó a la **Responses API** y a **ChatGPT Apps / MCP Apps**. La Assistants API se sunsetea el **26 de agosto de 2026** en favor de Responses API.
- **Tendencia clara mayo 2026:** OpenAI adoptó MCP en marzo de 2025; en septiembre de 2025 agregó MCP a ChatGPT Apps; co-desarrolló MCP Apps (interactive UI) con Anthropic. El *vendor format* (Custom GPTs) está siendo eclipsado por el *open standard* (MCP).
- **Para Carter: irrelevante.** Custom GPTs requieren cuenta ChatGPT Plus/Enterprise y solo corren en infraestructura OpenAI. Cero compatibilidad con local-first.

### c) MCP (Model Context Protocol)

**Origen y status:** anunciado por Anthropic en noviembre de 2024. **Donado al Agentic AI Foundation (Linux Foundation) en diciembre de 2025**, co-fundado por Anthropic, Block y OpenAI. Spec actual: **versión 2025-11-25**; roadmap 2026 publicado en marzo de 2026 enfocado en (1) escalabilidad transport, (2) comunicación agent-to-agent, (3) madurez de gobernanza, (4) enterprise readiness (audit trails, SSO, gateways).

**Cómo funciona técnicamente:**

- **Wire format:** JSON-RPC 2.0 (mismo que Language Server Protocol — la inspiración explícita).
- **Arquitectura:** Host (la app de IA) → Client (uno por servidor, dentro del host) → Server (el wrapper de la tool/data source).
- **Tres primitivas que un servidor expone:**
  - **Tools** — funciones invocables con side effects (`tools/call`).
  - **Resources** — data read-only direccionable por URI (`resources/read`).
  - **Prompts** — templates reusables.
- **Transports:**
  - **stdio** — el host hace `spawn` del servidor como child process; reads/writes a `stdin`/`stdout`. Latencia: **~4–10 ms** overhead. Recomendado para todo lo local.
  - **Streamable HTTP** (sucede a SSE legacy) — para servidores remotos. Auth vía OAuth 2.1 con dynamic client registration.
- **Sesión es stateful** dentro de la conexión (a diferencia de REST). Permite contexto multi-step.
- **Auth:** la spec no exige auth (gap de seguridad explícito — Knostic encontró ~2.000 servidores expuestos sin auth en julio 2025); cuando hay, el estándar emergente es **OAuth 2.1 + bearer token**. Servidores oficiales empresariales (GitHub remoto, Atlassian, Linear, Notion remoto, Slack) ya usan OAuth 2.1 con dynamic client registration.

**Estabilidad mayo 2026:** alta. SDK oficiales en Python, TypeScript, C#, Java, Swift; ~97 millones de descargas mensuales combinadas Python + TypeScript. Soporte nativo en Claude Desktop, Claude Code, Cursor, Windsurf, Zed, ChatGPT (desktop + apps), VS Code (vía Copilot 1.101+), Microsoft Copilot Studio, Replit. Adopción en motores: OpenAI, Google DeepMind, Microsoft. **Ollama todavía NO habla MCP nativo** (issue #7865 abierto a abril 2026): Ollama solo expone tool-calling vía `/api/chat`, así que necesitás un bridge.

**Bugs / limitaciones conocidas a mayo 2026:**

1. **Tenant isolation no resuelto en spec** (problema enterprise).
2. **Cost attribution / rate-limiting no estandarizado** — agentes invocan herramientas autónomamente sin governance.
3. **Configuración no portable** entre clients — cada cliente tiene su `config.json` propio.
4. **Gateway behavior indefinido** detrás de proxies/LBs (afinidad de sesión, propagación de auth).
5. **Token bloat:** cada servidor agrega N definiciones de tools al context window. Con 5–10 servidores podés sumar 50+ tool definitions al system prompt — pesado para qwen3:4b con 32K de context nativo.
6. **JSON Schema impedance mismatch:** Mastra reportó tasas de error de tool-calling de **15% sin compat layer, 3% con compat layer** en OpenAI/Anthropic/Gemini. Modelos pequeños (DeepSeek, Llama, **y por extensión qwen3:4b**) sufren más con schemas con `nullable`, `minLength`, etc.
7. **Cold starts** en servidores HTTP serverless: cientos de ms a multi-segundo en primera llamada.
8. **Modelos pequeños rinden peor con muchas tools.** El benchmark de MikeVeerman muestra que parameter count es un mal predictor; la fragilidad viene de tool count y tamaño de descripciones.

### d) OpenAI Function Calling vs Anthropic Tool Use vs Ollama tools

Conceptualmente **idénticos**: definís un schema (JSON Schema), el modelo decide cuándo llamar y devuelve `(name, arguments)` estructurados. **Sintácticamente diferentes:**

| Aspecto | OpenAI | Anthropic | Ollama (qwen3) |
|---|---|---|---|
| Campo de tools | `tools: [{type: "function", function: {...}}]` | `tools: [{name, description, input_schema}]` | `tools: [...]` (formato OpenAI-compatible) |
| Respuesta | `choices[0].message.tool_calls[]` | `content: [{type: "tool_use", ...}]` | OpenAI-compatible en `/v1/chat/completions`; nativo en `/api/chat` |
| Strict mode | Sí (`strict: true`) — schema garantizado | No estricto | No |
| Parallel tools | Sí | Sí | Depende del modelo (qwen3 sí) |

**Ollama tiene capa de compatibilidad bidireccional** OpenAI **y** Anthropic (vía `/v1/messages` con `ANTHROPIC_BASE_URL=http://localhost:11434`). Esto significa que **podés correr cualquier cliente Anthropic SDK contra Ollama sin tocar código**, lo cual abre la puerta a reusar muchas herramientas del ecosistema Claude apuntándolas a qwen3 local.

**Estándar emergente:** convergencia hacia MCP como capa "encima" del function calling. Function calling es la capa *modelo↔framework*; MCP es la capa *framework↔tool*. **No compiten, se complementan.** Tu agent loop de Carter sigue usando function calling de Ollama; lo que MCP agregaría es que esos tools se descubran dinámicamente desde un servidor externo en vez de estar hardcodeados con `@tool`.

### e) Computer Use (Anthropic) y Operator/CUA (OpenAI)

**Anthropic Computer Use** (octubre 2024, public beta; en mayo 2026 corre sobre Claude Sonnet 4.5 / Opus 4.7):
- **No es un modelo separado** — es un **tool especial** (`computer_use`) integrado en los modelos Claude entrenados para coordenadas pixel-perfect.
- Loop: screenshot → modelo analiza visualmente → emite `click(x,y)` / `type(text)` / `key(...)` → tu harness ejecuta → screenshot → repeat.
- Pixel counting desde bordes; resolución recomendada XGA (1024×768) para accuracy.
- **NO corre local.** Requiere API Anthropic con header `anthropic-beta: computer-use-2025-01-24`. El "demo Docker" que se distribuye solo es harness — el VLM corre en cloud.
- Costo: 466–499 tokens overhead por system prompt + tokens de visión por cada screenshot. Slow (segundos por step) y caro.
- OSWorld benchmark: 22% (Anthropic), human baseline 70–75%.

**OpenAI Operator / CUA** (enero 2025; integrado en ChatGPT como "agent mode" desde julio 2025; el sitio `operator.chatgpt.com` se sunseteó):
- Modelo separado: **`computer-use-preview`** (basado en GPT-4o + RL). En 2026 evolucionó a `gpt-5.4` con tool `computer_use` en la Responses API.
- Filosofía web-first (browser virtual en cloud OpenAI), aunque CUA en API permite también desktop con Playwright/Selenium en tu side.
- OSWorld 38.1%; WebVoyager 87%. Mejor que Computer Use en web, peor en desktop nativo según la versión 2025.
- **NO local.** Requiere `OPENAI_API_KEY`. El sample app `openai/openai-cua-sample-app` ejecuta Playwright local pero el cerebro VLM corre en OpenAI.

**Comparación con el approach de Carter (UIA + Win32 + frame-diff estructural):**

| Dimensión | Computer Use / Operator (visual) | Carter (estructural) |
|---|---|---|
| Cerebro | VLM cloud obligatorio | qwen3:4b local |
| Latencia por step | 1–5 s (screenshot + VLM) | 10–50 ms (UIA query) |
| Costo | $$$$ por screenshot | $0 |
| Determinismo | Bajo (pixel hunting falla con cambios visuales) | Alto (AutomationId no cambia) |
| Apps sin UIA (Steam, juegos) | Funciona | Falla — necesita fallback |
| Privacidad | Nula (cada pixel a Anthropic/OpenAI) | Total |
| Multi-idioma | Estructural automático (no depende de OCR) | Estructural automático |

**¿Complementarios?** Sí, pero solo como fallback de último recurso. **Recomendación honesta:** si en algún momento hits una app Win32 vieja o un juego sin UIA, integrá un **VLM local pequeño** (Qwen2.5-VL-7B-Instruct cabe en tu 16 GB de VRAM con quantización Q4_K_M) como tool `vision_fallback_click`, NO como cerebro. Mantenés UIA como path principal, VLM local solo cuando UIA devuelve árbol vacío. Esto preserva los seis valores no-negociables.

### f) LangChain / LlamaIndex Agents

- **LangChain** (~95K stars): framework, no agente. Ofrece catálogo gigante de "tools" wrappers (Google Search, Wikipedia, SQL, REPL, etc.) en `langchain-community`. La calidad varía y muchos están deprecados o requieren API keys.
- **LangGraph** (subproducto de LangChain Inc.): orquestador low-level basado en grafos. **Es el estándar 2026 para agent loops complejos** (durable execution, human-in-the-loop, time travel). Adoptado por Klarna, Replit, Elastic. MIT.
- **LlamaIndex**: tradicionalmente RAG-first; ahora también ofrece agents. Su catálogo de tools es más curado pero más chico que LangChain.

**Para Carter: NO adoptar full framework.** Tu agent loop con `@tool` decorators es más simple, más rápido, y no te ata a la inestabilidad de la API de LangChain (rompen API menor cada release). Lo que sí podés robar: los **patrones de LangGraph** (state machine explícita, checkpointing, interrupts para human-in-the-loop). Implementarlos en ~200 líneas Python propias da más control.

### g) Voyager skills / self-improving agents (Wang et al. 2023)

**Patrón académico (NeurIPS/TMLR 2023):**

1. **Automatic curriculum** — un planner LLM propone tareas calibradas al estado actual del agente.
2. **Skill library** — code snippets ejecutables (en el paper: JS/Mineflayer; portable a cualquier lenguaje) **indexados por embedding del nombre+descripción**. Cuando llega una tarea nueva, se hace top-k retrieval y se inyectan al prompt.
3. **Iterative prompting con self-verification** — bucle de hasta 4 rondas de refinamiento usando errores de ejecución + un segundo call al LLM como verificador.

**Frameworks que lo standardizan:**
- **JARVIS-1** (extensión multimodal de Voyager).
- **SAGE** (arXiv 2501.07278) — agrega RL para que las skills se actualicen también en fallos parciales, no solo en éxitos.
- **CAMEL / AutoGen** — ofrecen primitivas similares pero más enfocadas a multi-agent que a self-improvement individual.
- **Anthropic Skills** (ver punto a) son **conceptualmente Voyager pero curado por humanos en vez de auto-generado**: misma idea de "skill library indexada por description", sin el componente self-improving.

**Para Carter: aplicable parcialmente.** El patrón Voyager es la justificación teórica detrás de adoptar el formato SKILL.md. Lo que *no* deberías copiar de Voyager es el self-improving automático sobre Carter en producción — qwen3:4b no es lo bastante confiable para auto-generar Python que después se ejecute con permisos de tu Windows. Mantené las skills curadas a mano (o generadas en una sesión y revisadas antes de commit).

---

## 2. Estado real de integraciones oficiales (mayo 2026)

| App | MCP server oficial empresa | SDK Python oficial | API REST estable | Auth | Funciona offline-first |
|---|---|---|---|---|---|
| **Spotify** | **NO oficial.** Solo comunidad (`marcelmarais/spotify-mcp-server`, `varunneal/spotify-mcp` — este último marcado *Inactive March 2026*; "DJ Spotify" en Docker MCP Registry). Synter MCP es solo para Spotify Ads. | `spotipy` (mantenido por comunidad) | Sí, Web API estable | OAuth 2.0 + Spotify Premium para playback control | NO — requiere cloud Spotify |
| **Steam** | **NO oficial, casi nada de comunidad.** Web API de Steam existe pero MCP coverage es marginal. | `steam` (comunidad) | Sí, Steam Web API | API key personal | Local launching: sí (vía CLI `steam://`); datos: no |
| **Discord** | **NO oficial.** Múltiples comunidad (`v-3/discordmcp`, `SaseQ/discord-mcp`, `barryyip0625/mcp-discord`, `hanweg/mcp-discord`, `elyxlz/discord-mcp`). | `discord.py` (no es de Discord pero es referencia) | Sí | Bot token (necesitás crear bot) o user token (ToS gris) | NO |
| **Slack** | **SÍ oficial** (`slack.com/help/articles/48855576908307`). Streamable HTTP + OAuth 2.1. También community `korotovsky/slack-mcp-server` (modo "stealth"). | `slack-sdk` oficial | Sí | OAuth 2.1 (oficial) o tokens xoxb/xoxp | NO |
| **GitHub** | **SÍ oficial** (`github/github-mcp-server`, escrito en Go con Anthropic; reemplazó al de Anthropic en abril 2025). Remote en `https://api.githubcopilot.com/mcp/` con OAuth, o local con PAT. Soporte nativo en VS Code 1.101+. | `PyGithub` (no oficial Microsoft pero canónico) | Sí, REST + GraphQL | OAuth o PAT | NO (cloud) |
| **Notion** | **SÍ oficial** (`makenotion/notion-mcp-server` — Notion API 2025-09-03). Notion prioriza el remoto MCP en `notion.so`; el local repo "may sunset". | `notion-client` (oficial) | Sí | Integration token (auth interna) | NO |
| **Google Workspace (Calendar/Drive/Gmail)** | **SÍ desde Google** (Google publicó MCP servers para Drive, Calendar, Gmail vía Anthropic Connectors directory + comunidad fuerte). | SDKs `google-api-python-client`, `google-auth` oficiales | Sí | OAuth 2.0 (cliente desktop o service account) | NO |
| **Microsoft 365 (Outlook/OneDrive/Teams)** | **SÍ oficial Microsoft** (`microsoft/mcp` — catálogo de M365, Azure, etc.; `pnp/cli-microsoft365-mcp-server`; `Softeria/ms-365-mcp-server` con 200+ tools Graph API). | `msgraph-sdk-python` (preview oficial) | Sí, Microsoft Graph | OAuth 2.0 + Entra ID | NO |
| **YouTube** | **NO oficial Google.** Comunidad: `youtube-transcript-mcp`, NotebookLM connector. | `google-api-python-client` (Data API v3) | Sí | API key | NO |
| **WhatsApp** | **NO oficial Meta.** Comunidad densa pero **toda gris en ToS** (Baileys, whatsapp-web.js, lectura del SQLite local en macOS). Meta WhatsApp Business API es la única oficial → cloud + número aprobado. | No oficial | Solo Business API | API key + número aprobado | NO |
| **VS Code** | VS Code es el **cliente MCP**, no el servidor. Soporte nativo de servidores MCP desde 1.101 (Copilot Agent mode + MCP gallery). | API extensions JS/TS — no Python | N/A | N/A | Sí (es local) |
| **Chrome/Brave/Edge** | **NO MCP oficial.** Browser MCP (`browsermcp.io`), Playwright MCP, Brave Search MCP (la búsqueda, no el browser) son lo que existe. Para control real del browser local: extensión `browsermcp` + servidor MCP que habla por CDP. | `playwright`, `selenium`, `pychrome` | Chrome DevTools Protocol estable | N/A | Sí (CDP es local) |
| **Obsidian** | **NO oficial Obsidian Inc.** Múltiples comunidad muy maduros: `cyanheads/obsidian-mcp-server`, `MarkusPfundstein/mcp-obsidian`, `jacksteamdev/obsidian-mcp-tools` (este es *plugin* de Obsidian + binario firmado). Todos requieren el plugin **Local REST API** de Obsidian (gratis). | N/A | Local REST API (HTTP local con API key) | API key local | **SÍ (todo es local).** Mejor candidato MCP para Carter. |
| **Telegram** | **NO oficial Telegram.** Comunidad usa Bot API o MTProto vía `Telethon` / `pyrogram`. | `python-telegram-bot`, `Telethon` | Bot API estable | Bot token o MTProto session | NO |
| **Linear** | **SÍ oficial** (`https://mcp.linear.app/mcp`, Streamable HTTP + OAuth 2.1 dynamic client registration). | `linear-py` (comunidad) | GraphQL estable | OAuth 2.1 o personal API token | NO |
| **Jira / Atlassian** | **SÍ oficial** (Atlassian Rovo MCP Server — `https://mcp.atlassian.com/v1/`, soporta /sse y /mcp). | `atlassian-python-api` (comunidad) | REST estable | OAuth 2.1 (3LO) o API token | NO |

**Lectura para Carter:**

- **Para Carter, tres servidores MCP son claros candidatos local-first compatibles:** Obsidian (todo local), filesystem (oficial Anthropic, local), Git (oficial Anthropic, local). Estos no comprometen tus valores.
- **El resto requiere cloud + auth personal.** Adoptar GitHub MCP, Slack MCP, etc., es válido si el usuario ya tiene esa cuenta y quiere conectarla — pero debe ser **opt-in explícito por integración**, nunca on-by-default.
- **Spotify, Steam, Discord, WhatsApp, YouTube, Telegram NO tienen MCP oficial.** La calidad comunitaria es heterogénea. Si Carter ya tiene tools propias para esos (e.g., spotify control vía spotipy), no hay ganancia clara en migrarlas a MCP.

---

## 3. Análisis costo/beneficio: A vs B vs C vs D

| Criterio | A: Status quo (tools Python) | B: Cliente MCP + servers oficiales | C: Skills estilo Claude (locales) | D: Híbrido (recomendado) |
|---|---|---|---|---|
| **100% local** | ✅ Total | ⚠️ Depende del servidor (Obsidian/FS/Git sí; Slack/GitHub/Notion no) | ✅ Total | ✅ El core sí; MCP opcional opt-in |
| **Privacidad first** | ✅ | ⚠️ Cada servidor cloud filtra | ✅ | ✅ |
| **Sin per-app hardcodes** | ⚠️ 55 tools = 55 hardcodes; pero universales | ✅ Servidores son externos | ✅ Skills son data, no código de Carter | ✅ |
| **Multilingüe estructural** | ✅ El qwen3 maneja idiomas; el código no asume | ✅ MCP es schema-based, idioma-agnóstico | ✅ SKILL.md puede estar en cualquier idioma | ✅ |
| **Honestidad por construcción** | ✅ Vos controlás cada error | ⚠️ Servidores opacos pueden mentir (descripciones untrusted según spec MCP) | ⚠️ Skills mal escritas hacen "undertrigger" o "overtrigger" | ⚠️ Mitigable con auditoría |
| **Universal** | ✅ Cualquier app con Python lib | ✅ ~5.000 servidores disponibles | ⚠️ Skills son knowledge layer, no integración real | ✅ Lo mejor de todos |
| **Latencia (<2 s budget)** | ✅ Tool call ~ms | ⚠️ +4–10 ms stdio + cold start ocasional + HTTP RTT remoto | ✅ Skill load es solo lectura archivo | ✅ |
| **Mantenimiento** | ❌ Tu equipo escribe y mantiene 55 tools | ✅ Empresas mantienen sus servers | ⚠️ Vos mantenés skills | ⚠️ Dividido |
| **Compromiso con SaaS Anthropic/OpenAI** | ✅ Cero | ✅ Cero (MCP es Linux Foundation) | ✅ Cero (formato es abierto) | ✅ Cero |
| **Cerebro qwen3:4b funciona** | ✅ 55 tools cabe en context | ⚠️ Si agregás 5 servers con 10 tools c/u, context bloat real | ✅ Solo `description` precargado | ✅ Limitando MCP servers a 3–5 |
| **Universal/portable** | ❌ Lock-in al loop de Carter | ✅ MCP funciona en Cursor/Claude/etc. (vos podés re-usar tools en otros proyectos) | ✅ Skills funcionan en Claude Code, Codex, ChatGPT, Carter, etc. | ✅ |
| **Token cost en prompt** | Bajo (descripciones cortas) | Alto si muchos servers | Muy bajo (solo `description`) | Bajo si controlás |
| **Riesgo de drift / breakage** | Bajo (tu código) | Medio (deps externas) | Bajo (skills son texto) | Bajo |
| **Velocidad de adopción de nuevas integraciones** | ❌ Lento (codear cada tool) | ✅ Instantáneo (npx un server) | Medio (escribir skill) | ✅ |

**Veredicto:**

- **Opción A pura:** segura pero te condena a reinventar lo que el ecosistema ya hizo. Si querés agregar Linear o Atlassian o Obsidian, cada uno son días de código + mantenimiento de auth. **No escala.**
- **Opción B pura:** rompe valores no-negociables. Slack/GitHub/Notion/Spotify cloud-only. Además, qwen3:4b se va a ahogar con N×M tools de varios servers en context.
- **Opción C pura:** skills sin tools concretas son solo prompts glorificados. No cubren el dominio "ejecutar Python que controla Windows" — para eso necesitás tools reales.
- **Opción D (híbrido) — la única coherente con los seis valores:**

```
Carter v4 core:
  ├─ 55 tools Python @tool (núcleo, no negociable, todo local)
  ├─ Skills loader (formato SKILL.md, ~/.carter/skills/, all local)
  │     └─ Cada skill puede listar qué tools del core puede usar
  └─ MCP client OPCIONAL (off by default)
        ├─ Whitelist de servers en config
        ├─ Solo activar bajo demanda explícita
        └─ Empezar con: filesystem, obsidian, git
```

---

## 4. MCP deep-dive

### Servidores MCP confiables hoy (mayo 2026)

**Reference servers oficiales (mantenidos por el steering group MCP, en `modelcontextprotocol/servers`):**
- **Everything** — server de prueba con todas las primitivas
- **Fetch** — web fetching con conversión a formato LLM-friendly
- **Filesystem** — operaciones de archivo con allow-list de directorios. **Recomendado para Carter.**
- **Git** — read/search/manipulate repos. **Recomendado para Carter.**
- **Memory** — knowledge graph persistente
- **Sequential Thinking** — chain-of-thought structurado
- **Time** — conversiones de timezone

**Servidores oficiales de empresas (los que importan):**
- GitHub (`github/github-mcp-server`, Go, remote en api.githubcopilot.com/mcp/ + local Docker `ghcr.io/github/github-mcp-server`) — **oficial GitHub**
- Slack (Slack-hosted MCP, OAuth 2.1) — **oficial Slack**
- Notion (`makenotion/notion-mcp-server`) — **oficial Notion**
- Linear (`mcp.linear.app/mcp`, OAuth 2.1) — **oficial Linear**
- Atlassian (Rovo MCP, `mcp.atlassian.com/v1/`) — **oficial Atlassian**
- Microsoft (`microsoft/mcp`, multiples servers de Azure/M365/Foundry) — **oficial Microsoft**
- Cloudflare, AWS, Stripe, Hubspot — todos oficiales con OAuth

**Servidores comunitarios sólidos (relevantes para Carter):**
- Obsidian (`cyanheads/obsidian-mcp-server`, `MarkusPfundstein/mcp-obsidian`) — local-first
- Spotify (`marcelmarais/spotify-mcp-server`) — más mantenido que `varunneal/spotify-mcp`
- Brave Search (Brave-mantenido, requiere API key)
- Playwright / browser automation
- SQLite, PostgreSQL, MySQL servers

**Registry oficial:** `https://registry.modelcontextprotocol.io` (público desde 2025); plus catálogos `mcp.so`, `pulsemcp.com`, `mcpservers.org`, `glama.ai/mcp`. Más de **5.000 servidores públicos**.

### Cliente MCP Python (`mcp` package oficial)

Instalación:
```bash
pip install "mcp[cli]"
```

**Versión actual mayo 2026:** `1.27.0`. Mantenido por `modelcontextprotocol/python-sdk`, autoría Anthropic PBC, MIT.

**FastMCP 2.0** (`fastmcp` package por Prefect) es la herramienta de facto encima del SDK oficial — 70% de los servers MCP del ecosistema usan algún sabor de FastMCP. ~1M descargas/día.

**Integración mínima a un agent loop existente** (esquema para Carter):

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 1. Definir cómo levantar el server (stdio)
server_params = StdioServerParameters(
    command="uvx",
    args=["mcp-server-filesystem", "/home/user/Documents"],
)

# 2. Conectar
async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()

        # 3. Discover tools
        tools = await session.list_tools()
        # tools.tools = [Tool(name=..., description=..., inputSchema=...)]

        # 4. Inyectarlas al loop de Ollama:
        ollama_tools = [
            {"type": "function",
             "function": {"name": t.name,
                          "description": t.description,
                          "parameters": t.inputSchema}}
            for t in tools.tools
        ]

        # 5. Cuando qwen3 emite tool_call con name "read_file":
        result = await session.call_tool("read_file", {"path": "..."})
        # result.content[0].text es lo que devolvés al modelo
```

**Patrón recomendado para Carter:** un `MCPRegistry` que maneja el lifecycle de N sesiones MCP en paralelo, las inicializa lazy (solo cuando el usuario habilita un server), y expone un dict unificado `{tool_name: callable}` que tu loop core consume **igual** que tus tools `@tool`.

### Convivencia MCP tools + tools Python propias

Estrategia: **namespace + collision avoidance**.

```python
# Tus tools Python:
@tool(name="play_music")  # → registro local
def play_music(...): ...

# MCP tools auto-discovered:
# spotify_mcp_play, spotify_mcp_search  (prefijo del server)
```

Tu loop:
1. En cada turno, construye `tools = local_tools + active_mcp_tools`.
2. Si qwen3 llama `spotify_mcp_play`, hacé el dispatch al MCPRegistry.
3. Si llama `play_music`, hacé dispatch local.
4. **Honestidad**: si el MCP server está caído, devolvé un tool_result de error explícito al modelo, no un fallback silencioso.

### Latencia esperada

Mediciones del ecosistema (kumaran srinivasan, fast.io, oneuptime):
- **stdio local, server warm:** **4–10 ms** overhead de protocolo + tiempo del tool real.
- **stdio local, cold start:** 100–500 ms primer call (process spawn + imports).
- **HTTP local (servidor en mismo host):** 10–30 ms.
- **HTTP remoto (cloud server):** 100–500 ms RTT + proceso.
- **Tool call típico:** "<10 ms para query parsing y result formatting" (mindstudio).

**Para tu budget Alexa-tier <2 s:** stdio local te deja ~1.99 s para inferencia + tool execution real. **Aceptable**. Pero:
- **No abuses**: cada tool de un server agrega tokens al system prompt → más tiempo de inferencia. Si pasás de 30 tools totales, qwen3:4b empieza a degradar.
- **Pre-warm los servers**: spawneá los servers MCP al startup de Carter, no on-demand. Mantenelos como long-running processes hasta que el user los desactive.
- **Lazy-load tool definitions**: con muchos servers, considerá un router (el mismo qwen3 elige *qué grupo* de tools cargar antes de cada turno).

### Bugs/limitaciones a mayo 2026

Ya enumerados en §1c. Los críticos para Carter:
1. **Tool count inflation** en context window de qwen3:4b → mitigá limitando a 3–5 servers + filesystem/git/obsidian.
2. **JSON Schema impedance** con modelos pequeños → adoptá el patrón de Mastra: validar schema y reintentar con prompt-injection del schema cuando falla.
3. **Cold starts** → keep-alive.
4. **Sin tenant isolation / cost attribution** → no es problema en single-user local.
5. **Ollama no habla MCP nativo** → necesitás bridge propio (5 horas) o usar `mcp-client-for-ollama` / MCPHost / `ollama-mcp-bridge`.

---

## 5. Skills deep-dive (Anthropic Agent Skills)

### Estructura

Ya cubierto en §1a. Recapitulando con ejemplo concreto adaptado a Carter:

```
~/.carter/skills/
└── youtube-watch-later/
    ├── SKILL.md
    └── scripts/
        └── add_to_watch_later.py
```

`SKILL.md`:
```yaml
---
name: youtube-watch-later
description: |
  Agrega un video de YouTube a la lista "Ver más tarde" del usuario abriendo
  el browser y haciendo click en el botón "+ Ver más tarde". Usá esta skill
  cuando el usuario diga "guardá este video", "ver más tarde", "watch later",
  "save for later" en cualquier idioma, o cuando comparta un link de youtube.com
  o youtu.be sin contexto adicional.
allowed-tools: open_browser_url, click_element, find_element_by_text
---

# Workflow

1. Recibí la URL del video en el argumento `url`.
2. Llamá a `open_browser_url(url=url)`.
3. Esperá 1.5 s a que cargue (evitá frame-diff antes de eso).
4. Llamá a `find_element_by_text(text="+ Ver más tarde")` o el equivalente
   en el idioma de UI actual ("+ Watch later", "+ Más tarde").
5. Si no aparece en 5 s, llamá a `find_element_by_text(text="Save")`
   y luego buscá "Watch later" en el menu desplegable.
6. Llamá a `click_element(element_id=resultado del paso anterior)`.
7. Verificá con `find_element_by_text(text="Guardado")` o equivalente.

# Errores comunes
- Si el browser no está logueado en YouTube, devolvé al usuario un mensaje
  honesto "no estás logueado en YouTube en este browser" y NO intentes login.
- Si el botón cambió de label, FALLÁ explícitamente, no inventes alternatives.
```

### Cómo el modelo decide qué skill usar

Mecanismo de progressive disclosure:

1. **Boot:** el agente concatena los `description` de TODAS las skills disponibles en el system prompt como un bloque tipo:
   ```
   ## Available Skills
   - **youtube-watch-later**: Agrega un video de YouTube...
   - **summarize-pdf**: Extrae texto y genera resumen...
   - ...
   ```
2. **En cada turno**, qwen3 ve el system prompt + tu mensaje. Si una skill matchea (semánticamente), el modelo emite algo como `<load_skill name="youtube-watch-later"/>` (en la implementación de Anthropic; vos podés definir tu convención).
3. **Tu loop intercepta**, lee `SKILL.md`, lo inyecta como mensaje del sistema o user en la próxima ronda, y deja que el modelo continúe con instrucciones cargadas.
4. Si SKILL.md referencia `references/foo.md` y el modelo lo necesita, hace una segunda lectura. Si necesita ejecutar `scripts/add_to_watch_later.py`, eso pasa por tus tools (e.g., un tool `run_skill_script`).

**Problema conocido:** Anthropic admite que Claude tiende a *undertrigger* skills. Mitigación documentada: hacer descripciones "pushy" con muchos triggers explícitos ("usá esta skill SIEMPRE QUE el usuario mencione X, Y, Z, incluso si no lo pide explícitamente").

### Skills oficiales publicados por Anthropic

En `github.com/anthropics/skills`:
- **document-skills:** PDF, DOCX (Word), XLSX (Excel), PPTX (PowerPoint).
- **example-skills:** webapp-testing, mcp-server-generation, brand-guidelines, internal-comms.
- **skill-creator:** la skill que crea otras skills (meta).
- **claude-api:** referencia API + SDK docs.

Plus el ecosistema en `claudeskills.info` (140+), `skillsmp.com`, `aitmpl.com` (192+ con plugins multi-LLM Codex/Gemini/Qwen/Ollama).

### Cómo replicar el patrón sobre Ollama + qwen3:4b localmente

Implementación mínima en ~150 líneas Python:

```python
# carter_skills.py
from pathlib import Path
import yaml, re

class SkillRegistry:
    def __init__(self, skills_dir: Path):
        self.skills = {}
        for skill_md in skills_dir.glob("*/SKILL.md"):
            content = skill_md.read_text(encoding="utf-8")
            m = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.S)
            if not m: continue
            front = yaml.safe_load(m.group(1))
            self.skills[front["name"]] = {
                "description": front["description"],
                "allowed_tools": front.get("allowed-tools", "").split(),
                "body": m.group(2),
                "path": skill_md.parent,
            }

    def system_prompt_block(self) -> str:
        lines = ["## Habilidades disponibles", ""]
        for name, s in self.skills.items():
            lines.append(f"- **{name}**: {s['description']}")
        lines.append("")
        lines.append('Para activar una habilidad, emití <load_skill name="..."/> '
                     'antes de cualquier tool call. La habilidad se inyectará '
                     'en la conversación.')
        return "\n".join(lines)

    def load(self, name: str) -> str:
        s = self.skills.get(name)
        if not s: return f"Habilidad {name} no encontrada."
        return f"# Habilidad activada: {name}\n\n{s['body']}"
```

En tu agent loop:
```python
skills = SkillRegistry(Path.home() / ".carter" / "skills")
system_prompt += "\n\n" + skills.system_prompt_block()

# En cada turno, después de pedirle al modelo:
if match := re.search(r'<load_skill name="(\w[-\w]+)"\s*/>', model_output):
    skill_text = skills.load(match.group(1))
    messages.append({"role": "user", "content": skill_text})
    # re-llamar al modelo con skill cargada
```

Ventajas de este enfoque sobre adoptar el runtime de Anthropic:
- Cero dependencia cloud.
- Funciona idéntico con qwen3:4b (los descriptors son texto plano).
- Skills son **portables**: las mismas skills funcionan en Claude Code, Codex CLI, ChatGPT y Carter.
- Versionables en git (es un repo de Markdown + scripts).

---

## 6. Computer Use vs Carter

Ya cubierto extensivamente en §1e. Resumen decisional:

| | Carter UIA+Win32+frame-diff | Computer Use / Operator |
|---|---|---|
| **Localidad** | 100% local | Cloud-only (sin excepción) |
| **Latencia** | Decenas de ms | 1–5 s por step |
| **Costo** | $0 | $$$ por screenshot |
| **Determinismo** | Alto (AutomationId estable) | Bajo (pixel hunting brittle) |
| **Multilingüe** | Estructural — no le importa el idioma de la UI | Lee texto del screenshot, frágil con scripts no-latinos / fonts custom |
| **Privacidad** | Total | Cero |
| **Apps sin UIA / Win32 (Steam overlay, juegos, Electron mal hechos)** | Falla, necesita fallback | Funciona |
| **Cambios de UI** | Resiliente si AutomationId se mantiene | Frágil si el botón se mueve 20 px |

**¿Complementarios?** Sí, **solo en una dimensión específica**: el "long tail" de apps sin árbol de accesibilidad útil. Para esos casos, **NO uses Computer Use cloud.** Usá un VLM local (Qwen2.5-VL-7B, MiniCPM-V 2.6, ambos corren en tu 16 GB VRAM con Q4_K_M) como tool `vision_fallback_locate(target_description)` que devuelve coordenadas, y mantené el resto del approach estructural intacto.

**Veredicto para Carter v4:** ignorá Computer Use y Operator como dependencias. La filosofía local-first lo prohibe y técnicamente el approach estructural es superior para 95% de los casos. Si querés futuro-proof: dejá un *placeholder* en tu agente para `vision_fallback`, sin implementarlo todavía.

---

## 7. Patrones recomendados para asistentes locales 2026

### Frameworks que hacen bien partes del problema

- **Open Interpreter** — ejecuta código en respuesta a NL, con confirmation gates. Lección aplicable: el patrón "code execution as tool". Carter ya lo hace mejor (tools con schema), pero el modo "REPL" para el power-user puede ser una opción.
- **Continue.dev** — extension VS Code, soporte MCP nativo, integración local con Ollama. Lección: cómo **descubrir** y **gestionar** servers MCP desde una UI sin pesarlo todo en el cerebro.
- **LangGraph** — el patrón de state machine + checkpointing + interrupts es el correcto para agent loops complejos. Lección: si tu loop crece, evaluá adoptar la *idea* (no el código) — checkpointing del estado conversacional, interrupts para human-approval.
- **Jan.ai** — local-first AI assistant con stack Tauri + Ollama. Lección: empaquetado y distribución desktop-first.
- **`mcp-client-for-ollama` (jonigl)** — TUI para conectar Ollama a MCP servers, con human-in-the-loop. Buena referencia técnica del bridge.
- **MCPHost** (`mark3labs/mcphost`) — Go-based, multi-server, Ollama-friendly. Más estable que `ollama-mcp-bridge`.
- **Hermes Agent / Voyager-style** — no copies el self-improving en producción, pero el patrón de skill library indexada por embedding es **exactamente** lo que el formato SKILL.md hace.

### Stack moderno para asistente local 100% privado (mayo 2026)

```
┌─────────────────────────────────────────────────┐
│  CAPA UI (voz, texto, hotkeys)                   │
│   — Whisper.cpp local para STT                   │
│   — Piper / Kokoro TTS local                     │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│  AGENT LOOP (Python puro o LangGraph slim)       │
│   — Function calling vía Ollama tools API        │
│   — State machine con checkpointing local       │
│   — Interrupts para confirmaciones              │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│  CEREBRO: qwen3:4b-instruct-2507-q4_K_M (Ollama) │
│   — Tool calling nativo                          │
│   — 32K context (262K con YaRN)                  │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│  CAPACIDADES                                     │
│   ├─ 55 Tools Python @tool      [CORE]           │
│   ├─ Skills locales (SKILL.md)  [knowledge]      │
│   ├─ MCP Client opt-in          [extensibilidad] │
│   │     ├─ filesystem   [oficial, local]         │
│   │     ├─ git          [oficial, local]         │
│   │     ├─ obsidian     [community, local]       │
│   │     └─ <user-enabled>                        │
│   └─ VLM local fallback (futuro, placeholder)    │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│  MEMORIA / RAG LOCAL                             │
│   — SQLite + sqlite-vec                          │
│   — Embeddings: nomic-embed-text vía Ollama      │
└─────────────────────────────────────────────────┘
```

### Lecciones aplicables a Carter sin romper local-first

1. **Adoptá MCP como CONSUMIDOR opcional, no como núcleo.** Tus 55 tools siguen siendo el primary way to extend.
2. **Adoptá SKILL.md como contenedor de "playbooks" curados.** Un workflow tipo "preparar mi rutina matinal" es mejor expresado como skill (instrucciones + scripts) que como tool monolítica.
3. **NO adoptes LangGraph/LangChain runtime.** Tomá las ideas (state machine, checkpointing, time travel para debug), implementalas en 200 líneas. Vas a evitar deps inestables.
4. **Sí adoptá `mcp` Python SDK + FastMCP** si terminás creando servers MCP propios para *exponer* Carter a otros clientes (e.g., Claude Code consumiendo Carter). Pero no es prioridad.
5. **Implementá un VLM local (Qwen2.5-VL-7B Q4) como placeholder tool**, NO como cerebro. Mantenés el approach estructural; cubrís el long tail.
6. **No toques Computer Use, Operator, GPTs, Custom GPTs ni la API de Anthropic en runtime.** Todos rompen los seis valores no-negociables.

---

## Recomendación concreta para Carter v4

### Veredicto

**Adoptá la Opción D (híbrido) en este orden estricto, como tres fases incrementales. NO aceptes nada que rompa los seis valores no-negociables.**

### Fase 1 (semana 1–2): Skills locales (formato SKILL.md)

**Por qué primero:** zero risk, cero deps externas, 150 líneas de código, beneficio inmediato.

1. Implementar `SkillRegistry` (esquema en §5).
2. Crear `~/.carter/skills/` con 5–10 skills curadas que envuelvan workflows de tus 55 tools (e.g., `morning-routine`, `youtube-watch-later`, `prepare-meeting-notes`).
3. Inyectar el bloque de descripciones al system prompt.
4. Agregar el mecanismo de carga lazy.
5. Versionar skills en git, separado del código de Carter — esto permite que un usuario power agregue/edite skills sin tocar Python.

### Fase 2 (semana 3–4): Cliente MCP opcional

**Por qué segundo:** valor real pero requiere arquitectura cuidadosa.

1. Adoptar el package `mcp` oficial (Python SDK 1.27+).
2. Implementar `MCPRegistry` con whitelist en `config.toml`. **Default: vacío** (off by default).
3. Empezar habilitando solo **tres servidores 100% locales**: filesystem, git, obsidian. Ningún servicio cloud por defecto.
4. Pre-warm de servers al startup, no on-demand (evita cold starts dentro del budget de 2 s).
5. Namespace de tools (e.g., `mcp_obsidian_search`) para evitar colisiones con tus 55 tools.
6. Logging por tool call (latencia, éxito, errores) — base para honestidad.
7. Retry + schema-injection fallback a la Mastra para mejorar tool reliability con qwen3:4b.

### Fase 3 (mes 2): MCP cloud servers opt-in + VLM local fallback

**Por qué último:** son las features más controvertibles.

1. **MCP cloud opt-in:** documentar cómo el usuario habilita GitHub MCP, Linear MCP, Notion MCP. **Cada uno requiere consentimiento explícito y entiende que rompe localidad.** Mostrar un warning en CLI/UI: "Estás por habilitar GitHub MCP. Esto enviará datos a GitHub y requiere OAuth. ¿Continuar? [y/N]".
2. **VLM local fallback:** integrar Qwen2.5-VL-7B-Instruct (~5 GB Q4_K_M en VRAM) como tool `vision_fallback_locate(description)` para apps sin UIA. Latencia esperada ~500 ms en RTX 4060 Ti — solo aceptable como fallback, no como path principal.
3. **NO** integrar Computer Use, Operator, Custom GPTs, ni la Skills API hosteada de Anthropic — todos rompen valores.

### Triggers para "no, status quo"

Quedate en Opción A (status quo, sin MCP ni Skills) si **cualquiera** de estos hold:

- **Tu loop ya tiene problemas de tool reliability con 55 tools.** Si qwen3:4b ya falla 5–10% de las tool calls, agregar MCP servers (que suman tools al context) lo va a empeorar. Resolvé reliability primero.
- **No tenés un usuario que pida integraciones específicas.** Si nadie pidió "quiero que Carter lea mi vault de Obsidian" o "quiero que cree issues en GitHub", no agregues complejidad por especulación.
- **Tu budget de latencia ya está agotado.** Si tus turnos llegan a 1.8–1.9 s con qwen3 + 55 tools, MCP overhead te tira fuera del budget Alexa-tier.
- **No tenés bandwidth de mantenimiento.** MCP servers comunitarios rompen API. Si vos sos un equipo de uno, sumar 5 deps externas es deuda futura grande.
- **Honestidad-by-construcción es realmente innegociable.** Los servers MCP comunitarios traen tool descriptions que la spec de Anthropic explícitamente marca como **untrusted**. Auditás cada uno o no los uses.

### Triggers para acelerar

Saltá a fase 2 ya si:
- Un usuario power te pide acceso a Obsidian/Git/filesystem desde Carter — el MCP server oficial te lo da en 30 minutos vs. una semana de tool propia.
- Estás duplicando funcionalidad que un MCP oficial ya resuelve mejor (ej: vos escribiendo wrapper de la GitHub API cuando `github-mcp-server` existe maintained por GitHub).
- Querés que Carter sea **consumible** por otros clients (Claude Desktop, Cursor, VS Code) — para eso necesitás *exponer* Carter como server MCP, lo que solo tiene sentido si ya implementaste el cliente.

### Pasos accionables resumen (lista corta)

1. ☐ Implementar SkillRegistry con SKILL.md loader (~150 líneas) [Fase 1]
2. ☐ Curar 5–10 skills iniciales en `~/.carter/skills/` versionado en git [Fase 1]
3. ☐ Probar con qwen3:4b: ¿el modelo activa skills correctamente? Iterar descripciones "pushy" hasta que sí [Fase 1]
4. ☐ Adoptar `mcp` Python SDK; implementar MCPRegistry off-by-default [Fase 2]
5. ☐ Habilitar filesystem + git + obsidian MCP local [Fase 2]
6. ☐ Implementar retry con schema-injection para tool reliability [Fase 2]
7. ☐ Logging detallado de cada tool call (latencia, success, errors) [Fase 2]
8. ☐ Documentar opt-in para servers cloud (GitHub, Linear, Notion) con warning explícito [Fase 3]
9. ☐ Integrar Qwen2.5-VL-7B local como tool `vision_fallback_locate` [Fase 3]
10. ☐ NUNCA: adoptar Computer Use, Operator, Custom GPTs, Skills API hosteada, o LangChain como dependencia runtime.

---

## Caveats

- **Las fechas y versiones reportadas para 2026** (e.g., MCP spec 2025-11-25, donación al Linux Foundation en diciembre 2025, GPT-5.4 en ChatGPT, MCP Apps SEP-1865) provienen de fuentes web variadas. Algunas fuentes pueden mezclar fechas reales con proyecciones; verificá las versiones exactas en `modelcontextprotocol.io/specification` antes de implementar.
- **Benchmarks de tool calling de qwen3:4b son escasos.** El paper técnico de Qwen3 sugiere que el 4B mantiene capacidad agentic, pero benchmarks comunitarios independientes (MikeVeerman) indican que parameter count es mal predictor — necesitás benchmarkear *con tus tools concretas* antes de asumir reliability.
- **El ecosistema MCP cambia rápido.** Servers comunitarios marcados "Inactive March 2026" (e.g., `varunneal/spotify-mcp`) son señal de que la adopción no es uniforme. Auditá cada server antes de productivizarlo.
- **El nombre y mecánica de "Computer Use" / "Operator" / "CUA"** evolucionó tres veces entre 2024–2026 (Operator standalone → ChatGPT agent mode → tool en Responses API). La conclusión "no es local, no adoptes" es estable; los detalles internos pueden haber cambiado de nuevo a mayo 2026.
- **"100% local" es un espectro.** MCP filesystem es 100% local; MCP Brave Search hace HTTP a Brave. Auditá cada server activo y mantené un dashboard claro al usuario de qué se está mandando fuera.
- **Honestidad por construcción tiene un costo.** La spec MCP indica explícitamente "tool descriptions should be considered untrusted unless from a trusted server". Si tomás este valor en serio, NO podés conectar servers comunitarios sin leer el código fuente de cada uno. Eso es trabajo real.
- **JSON Schema impedance** entre tu schema interno (`@tool`) y el de los servers MCP es un problema operativo real, no teórico. Mastra lo cuantificó en 15% de error rate sin compat layer. Reservá tiempo para esto en Fase 2.
- **No verifiqué directamente** si Anthropic oficialmente publicó un MCP server para servicios propios más allá del filesystem/git ejemplo, ni el estado exacto de "MCP Apps" (formato interactive UI) — la información proviene de blogs y aggregators que pueden ser optimistas. La conclusión arquitectónica (no adoptar runtime cloud) no depende de estos detalles.