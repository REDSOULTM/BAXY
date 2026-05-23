# 04.04 — Slot-filling cuando faltan parámetros

> Cuándo: el usuario pide algo que requiere un parámetro que NO está en el
> input, ej: "ponme algo en Netflix" (falta el perfil de Netflix).
> **Fuente:** `agent.py:1067-1086` (continuation hint en select_tool_names) +
> `planner.py:select_tool_names` + el LLM mismo (decide preguntar al user).

## Concepto clave

El proyecto **no implementa slot-filling explícito** (no hay máquina de
estados "missing slot → ask → fill"). El patrón real es:

1. El **LLM decide** preguntar al usuario cuando le falta info (vía CORE_PROMPT
   que le dice "ASK don't ASSUME").
2. El usuario responde con texto corto ("Ema", "el de Juan").
3. El **router detecta continuation** (`last_assistant_text` contiene "perfil"/
   "profile" + streaming brand) y **fuerza `media` en el subset** aunque el
   regex no matche por ser texto corto.
4. El **TTL `INHERIT_TTL_SEC=300s`** evita heredar tools peligrosos si el
   usuario volvió tras mucho tiempo.

## Fig 4.04 — Slot-filling con continuation hint

```mermaid
sequenceDiagram
    autonumber
    participant U as Usuario
    participant AG as Gemma4Agent
    participant Sel as select_tool_names
    participant LLC as LLMClient
    participant LP as llama-server
    participant TR as ToolRegistry
    participant Mem as MemoryStore

    Note over U: TURN N
    U->>AG: "ponme algo en Netflix"
    AG->>Sel: select_tool_names(text, plan, last_assistant_text=None)
    Sel->>Sel: _suggest_tools → ["media", "browser"]
    Sel-->>AG: subset=["media", "browser", ..., "session"]
    AG->>LLC: chat(messages, tools=subset)
    LLC->>LP: POST
    LP-->>LLC: reply text "¿En qué perfil de Netflix?"<br/>(SIN tool_call)
    LLC-->>AG: response

    Note over AG: Sin tool calls — el LLM eligió PREGUNTAR<br/>antes de actuar
    AG->>AG: guards passthrough
    AG->>AG: append assistant text to history
    AG->>U: "¿En qué perfil de Netflix?"

    Note over U: TURN N+1
    U->>AG: "Ema"

    Note over AG: text muy corto, regex no matchea nada
    AG->>AG: raw_text_early = "Ema"
    AG->>AG: last_assistant_text = "¿En qué perfil de Netflix?" (de history)
    AG->>Sel: select_tool_names(text, plan, last_assistant_text="¿En qué perfil...")
    Sel->>Sel: _suggest_tools("Ema") → []
    Sel->>Sel: continuation hint detection:<br/>last_assistant contiene "perfil" AND<br/>("netflix"|"disney"|"hbo"|"max"|"prime"|"amazon"|"spotify")
    Sel->>Sel: short input (word_count<=6) + not casual
    Sel->>Sel: prepend "media" al subset
    Sel-->>AG: subset=["media", ..., "session"]

    AG->>LLC: chat(messages, tools=subset con media disponible)
    LLC->>LP: POST
    LP-->>LLC: tool_call: media(action="play", platform="netflix", profile="Ema", title="...")
    AG->>TR: execute("media", args)
    TR->>TR: ...
    TR-->>AG: ToolResult(ok=true)
    AG->>LLC: chat (continue con tool result)
    LLC-->>AG: reply "Listo, abriendo Ema en Netflix"
    AG->>U: reply
```

## Path alternativo: short continuation + INHERIT TOOLS

Cuando `select_tool_names` devuelve `[]` Y el input es ≤6 palabras y no es
saludo, el agente **hereda las tools del turn anterior** (`agent.py:1093-1186`):

```mermaid
sequenceDiagram
    autonumber
    participant U as Usuario
    participant AG as Gemma4Agent
    participant Sel as select_tool_names
    participant Hist as self.history

    Note over U: TURN N: agente ejecutó web research<br/>y mostró 3 fuentes
    Note over U: TURN N+1
    U->>AG: "Prefiero cronologico"
    AG->>Sel: select_tool_names(text, ...)
    Sel-->>AG: subset=[] (regex no matchea)
    AG->>AG: is_short_continuation = (raw_text and word_count <=6) = True
    AG->>AG: gap = now - self._last_turn_ts
    alt gap > 300s (INHERIT_TTL_SEC)
        AG->>AG: trace inherit_tools_ttl_expired<br/>NO heredar
    else gap <= 300s
        AG->>Hist: reverse iterate
        loop hasta encontrar assistant turn con tool_calls
            Hist-->>AG: msg
            alt msg.role == "tool"
                AG->>AG: prev_tools.append(name)
            else msg.role == "assistant" with tool_calls
                AG->>AG: prev_tools.extend(tool_calls names)
                AG->>AG: BREAK
            end
        end
        AG->>AG: filtrar DANGEROUS_TOOLS_NEVER_INHERIT<br/>(whatsapp, file_delete, subprocess, shell, ...)
        AG->>AG: subset = prev_tools filtrado
    end

    AG->>AG: LLM call con subset heredado
```

## Hallazgos a `_findings_seed.md`

- **No hay slot-filling explícito** — todo se delega al LLM (que decide cuándo preguntar) + continuation hint (que mantiene la tool en subset). Funciona pero **es difícil de testear**: para cada caso "user pregunta X → agente pregunta Y → user responde Z" hay que reproducir el history completo.
- **Continuation hint con regex hardcoded para 7 plataformas de streaming**: `\b(netflix|disney|hbo|max|prime|amazon|spotify)\b` (`planner.py:114`). Cualquier plataforma nueva (Tidal, YouTube Music, Apple TV) no dispara el hint.
- **INHERIT_TTL_SEC y DANGEROUS_TOOLS_NEVER_INHERIT son knobs en `agent.py` top-level.** Ya en findings (LOW) — sugerencia: mover a `inherit_tools.py`.
- **Continuation hint heuristic "word_count <= 6"** es frágil. "Pongo Ema entonces" (3 palabras) cabe; "Quiero verlo con el perfil de Ema" (7) no. Tradeoff aceptable, pero anotar.
- **El `_phrase_fires` y `_recent_recalls` agregan complejidad ortogonal al slot-filling** — si una phrase-trigger routine matcheó, suprimimos `session` del subset; si experience.recall trajo un turn pasado relevante, lo inyectamos al system_prompt. Cada uno afecta lo que el LLM ve sin que sea "slot fill" estrictamente.
