"""Few-shot dinámico para el turno de ACCIÓN (tool-calling).

Causa raíz del residual de tool-calling (~75% medido en vivo con el system
completo, 2026-06-10): "first-token misalignment" — sin un sesgo hacia el trigger
`<|tool_call|>` en el PRIMER token, un SLM de 2B "narra" ("Voy a abrir…") en vez
de disparar la tool, y por la causa autoregresiva se compromete a narrar.

Fuente: `documentacion/02_router/research/1_toolcalling.md` (40+ fuentes;
Cappelletti et al. arXiv 2505.15323 "first-token misalignment"; Meta-Tool
arXiv 2604.20148: few-shot +21.5pp en strict tool-calling de SLMs — el dato más
sólido). `inv1_toolcalling_medido_2026_05_23.md` descartó esta palanca "porque
sin thinking ya da 6/6 en el setup medido (comandos crisp)", PERO dejó pendiente
EXPLÍCITO: "re-medir si el 2/6 aparece en prod con el prompt completo". Ese
escenario se materializó (75% en vivo) -> se implementa ahora.

DISEÑO: para el turno de acción (hay tools ofrecidas, ninguna corrió aún), se
anteponen 1-2 pares (user ejemplo -> assistant tool_call) de las tools que el
router YA seleccionó. Son mensajes OpenAI normales (role assistant + tool_calls);
el chat_template de Gemma 4 los renderiza al formato nativo
`<|tool_call|>call:NAME{...}<|/tool_call|>` (NO se escribe ese string a mano: el
template lo hace, igual que el runtime real). Esto NO es una respuesta enlatada ni
un short-circuit: el LLM sigue decidiendo; el few-shot solo sesga el primer token
hacia "disparar una tool" en vez de "narrar". Estructural, multilingüe, cacheable.

Gate: GEMMA4_ACTION_FEWSHOT=0 desactiva. Default ON.
"""
from __future__ import annotations

import os
from typing import Any

# Un ejemplo CANÓNICO por tool: (user_text, tool_name, arguments). El user_text es
# un comando crisp neutro; el assistant responde SOLO con la tool-call (sin prosa)
# -> enseña la FORMA "comando -> dispara tool de una", no el contenido. Cubrir las
# tools del set del turno; el router pasa 4-6, tomamos 1-2 con ejemplo disponible.
# NO es una tabla de respuestas: es el few-shot de FORMATO que la literatura valida.
_CANONICAL: dict[str, tuple[str, dict[str, Any]]] = {
    "audio":            ("sube el volumen", {"action": "set", "level": 70}),
    "device_settings":  ("sube el brillo", {"action": "brightness_up"}),
    "app":              ("abrí Spotify", {"action": "open", "name": "Spotify"}),
    "window":           ("maximizá la ventana", {"action": "maximize"}),
    "reminder":         ("recordame comprar pan", {"action": "create", "title": "comprar pan"}),
    "browser":          ("abrí google.com", {"action": "open", "url": "google.com"}),
    "system":           ("qué hora es", {"action": "time"}),
    "media":            ("poné música", {"action": "play"}),
    "web":              ("buscá noticias de hoy", {"action": "search", "query": "noticias de hoy"}),
    "computer_use":     ("escribí hola", {"action": "type", "text": "hola"}),
    "screenshot":       ("sacá una captura", {"action": "capture"}),
    "vision":           ("qué hay en la pantalla", {"action": "describe"}),
    "steam":            ("abrí Steam", {"action": "open"}),
    "office":           ("creá un documento de Word", {"action": "create_word"}),
    "clipboard":        ("copiá esto", {"action": "copy"}),
}

# Tools que NUNCA deben aparecer como ejemplo de acción (no son acciones físicas
# que el few-shot deba sesgar; pueden inducir falsos disparos).
_SKIP = frozenset({"session", "safety", "state", "verify", "knowledge"})

_MAX_SHOTS = 2  # la curva se aplana tras 2 (PromptHub; añadir más a veces empeora)


def _enabled() -> bool:
    return os.environ.get("GEMMA4_ACTION_FEWSHOT", "1").strip().lower() \
        not in {"0", "false", "no", "off"}


def build_action_fewshot(tool_names: list[str] | None) -> list[dict[str, Any]]:
    """Devuelve mensajes few-shot (pares user->assistant-tool_call) para el turno
    de acción, en formato OpenAI (el chat_template los renderiza a nativo).

    Toma hasta _MAX_SHOTS tools del set ofrecido que tengan ejemplo canónico,
    preservando el ORDEN del router (la primera tool del subset es la más probable
    -> su ejemplo va primero, reforzando la decisión correcta). Vacío si gate off,
    sin tools, o ninguna tiene ejemplo.
    """
    if not _enabled() or not tool_names:
        return []
    msgs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name in tool_names:
        if name in _SKIP or name in seen or name not in _CANONICAL:
            continue
        seen.add(name)
        user_ex, args = _CANONICAL[name]
        msgs.append({"role": "user", "content": user_ex})
        msgs.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "type": "function",
                "function": {"name": name, "arguments": _dumps(args)},
            }],
        })
        if len(seen) >= _MAX_SHOTS:
            break
    return msgs


def _dumps(args: dict[str, Any]) -> str:
    import json
    return json.dumps(args, ensure_ascii=False)
