"""Pre-dispatch safety hook for purchase / paid-action attempts.

When safety_enabled, this hook intercepts tool_calls whose args
contain checkout-pattern URLs or paid-action keywords. The hook
returns {"block": True, ...} (the dispatcher refuses the call and
returns a synthetic needs_confirmation result) or {"block": False}
(the call proceeds).

When safety is OFF, the dispatcher still calls the hook and emits
a 'safety_hook_match' trace event with enforced=False so
operators can see when paid-pattern args slipped through. The
call itself proceeds in that case.

Structural detection — operates on args (URLs, action names) but
NEVER on user text or LLM reply text.

Hotfix I 2026-05-17.
"""
from __future__ import annotations

import re
from typing import Any


# URL patterns observed in real checkout / payment flows. Each
# pattern is anchored to the URL structure (host + path
# segment), not free text. Adding a pattern requires a real
# checkout URL example as backing — do NOT speculate.
_CHECKOUT_URL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"://(www\.)?steampowered\.com/checkout", re.IGNORECASE),
    re.compile(r"://store\.steampowered\.com/checkout", re.IGNORECASE),
    re.compile(r"://(www\.)?epicgames\.com/store/.*/checkout", re.IGNORECASE),
    re.compile(r"://(www\.)?gog\.com/checkout", re.IGNORECASE),
    re.compile(r"://(www\.)?microsoft\.com/.*/checkout", re.IGNORECASE),
    re.compile(r"://(www\.)?paypal\.com/checkoutnow", re.IGNORECASE),
    re.compile(r"://checkout\.stripe\.com/", re.IGNORECASE),
    re.compile(r"://(www\.)?amazon\.com/gp/buy", re.IGNORECASE),
    re.compile(r"://(www\.)?amazon\.[a-z.]+/gp/buy", re.IGNORECASE),
)


# (tool_name, action) pairs that imply money movement regardless
# of args. These come from the schema definitions, NOT user text.
_PAID_ACTION_NAMES: frozenset[tuple[str, str]] = frozenset({
    ("steam", "purchase"),
    ("steam", "buy"),
    ("game_launcher", "purchase"),
    ("browser", "checkout"),
    # browser(action='open', url='...checkout...') is caught by
    # the URL pattern check above, not by action name.
})


def evaluate_tool_call(
    tool_name: str,
    action: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Inspect a planned tool_call.

    Returns one of:
      {"block": False}
        The call is safe to dispatch.

      {"block": True, "reason": str, "pattern": str}
        A checkout-pattern URL or paid action was detected. The
        caller decides whether to hard-block (safety_enabled) or
        just warn-and-proceed.
    """
    url = args.get("url") or args.get("href") or ""
    if isinstance(url, str) and url:
        for pat in _CHECKOUT_URL_PATTERNS:
            if pat.search(url):
                return {
                    "block": True,
                    "reason": (
                        "URL matches a known checkout pattern. "
                        "Confirm with user before proceeding."
                    ),
                    "pattern": pat.pattern,
                }

    key = (tool_name, action)
    if key in _PAID_ACTION_NAMES:
        return {
            "block": True,
            "reason": (
                f"{tool_name}.{action} is a paid action. "
                "Confirm with user before proceeding."
            ),
            "pattern": f"action:{tool_name}.{action}",
        }

    # HUECO CERRADO 2026-05-26: un click GENÉRICO (gui/computer_use/uia) se
    # colaba en una pantalla de PAGO — no es URL de checkout ni tool
    # 'steam.purchase'. Caso real: gui(click_button, label="Comprar") en Steam.
    # Decisión de producto (2026-05-26): si la ventana AL FRENTE es una tienda/
    # checkout, CUALQUIER click pide confirmación — sin depender del label del
    # botón (clasificarlo por su texto corto es frágil; un falso-negativo COBRA
    # plata, mucho peor que pedir confirmar una vez de más). La señal fuerte y
    # fiable es el ESTADO DEL SO (título de la ventana = tienda conocida). El
    # usuario hands-free igual avanza diciendo "sí" al handshake. Navegar/abrir
    # la tienda NO se bloquea: solo los CLICKS dentro de un checkout.
    if tool_name in {"gui", "computer_use", "uia"} and _is_click(args):
        if _foreground_is_checkout():
            return {
                "block": True,
                "reason": (
                    "Click on a store/checkout screen could spend money. "
                    "Stop before charging; confirm with the user (say yes/no)."
                ),
                "pattern": "gui_click_on_checkout_window",
            }

    return {"block": False}


def _is_click(args: dict[str, Any]) -> bool:
    """True si el tool_call es un CLICK (algo que puede avanzar un pago). Cubre
    gui.click/click_button/click_text. Para computer_use, su goal corre clicks
    internamente, así que un goal sobre una ventana de checkout también cuenta."""
    if not isinstance(args, dict):
        return False
    action = str(args.get("action") or "").casefold()
    if action in {"click", "click_button", "click_text", "double_click", "right_click"}:
        return True
    # computer_use no usa 'action' pero sí 'goal'; un objetivo dentro de un
    # checkout puede ejecutar el click de pago -> tratarlo como click.
    if "goal" in args:
        return True
    return False


# Marcas de pago/checkout en el titulo de la ventana al frente. No basta con el
# nombre de la tienda ("Steam", "Amazon", etc.): eso bloquearia navegacion normal
# y romperia movilidad. Exigimos estado de pago/carrito/checkout o proveedor de
# pago explicito.
_PAYMENT_PROVIDER_MARKERS = (
    "paypal", "stripe", "mercado pago", "mercadopago", "checkout.stripe.com",
)

_CHECKOUT_STATE_MARKERS = (
    "checkout", "payment", "billing", "cart", "basket", "order review",
    "place order", "pay now",
    "pago", "pagar", "carrito", "cesta", "finalizar compra",
    "confirmar compra", "pedido", "facturacion", "facturación",
    "pagamento", "carrinho", "paiement", "panier", "warenkorb", "zahlung",
    "kasse", "carrello", "ordine",
)


def _foreground_is_checkout() -> bool:
    """True si la ventana al frente parece una tienda/checkout, por su título.
    Estado del SO (Win32 GetForegroundWindow). Fallback seguro: si no se puede
    leer el título, devuelve False (no bloquea de más)."""
    try:
        from .computer_use import _foreground_title
        title = (_foreground_title() or "").casefold()
    except Exception:
        return False
    if not title:
        return False
    if any(m in title for m in _PAYMENT_PROVIDER_MARKERS):
        return True
    return any(m in title for m in _CHECKOUT_STATE_MARKERS)
