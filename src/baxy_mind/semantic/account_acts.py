"""Controls whose click changes the person's account or what is installed (live 2026-10-07, z7: going to «Tu biblioteca»
on a music app the model clicked «Seguir a Tu biblioteca», «Siguiendo…» and «Guardar La biblioteca de media noche en Tu
Biblioteca»). Such a click is the person's to ask for: the engine presses one only when the goal names that act."""

from __future__ import annotations

import re
import unicodedata

# Each act with the words its control and a goal that asks for it say, in Spanish and English (folded, no accents).
_ACTS: dict[str, tuple[str, ...]] = {
    "follow": ("seguir", "siguiendo", "dejar de seguir", "follow", "following", "unfollow"),
    "save": ("guardar", "guardado", "guarda", "save", "saved", "anadir a", "agregar a", "add to", "quitar de",
             "eliminar de", "remove from"),
    "like": ("me gusta", "like", "liked"),
    "subscribe": ("suscribir", "suscribirse", "suscribirme", "suscrito", "subscribe", "subscribed", "unirse", "unirme",
                  "join", "joined"),
    "install": ("obtener", "instalar", "install", "get", "comprar", "buy", "adquirir"),
}
# Goal verbs that ask for each act (imperative or infinitive as the reader leaves them).
_ASKS: dict[str, tuple[str, ...]] = {
    "follow": ("segui", "seguir", "sigue", "follow", "unfollow", "deja de seguir", "dejar de seguir"),
    "save": ("guarda", "guardar", "guardame", "save", "anadi", "anadir", "agrega", "agregar", "add"),
    "like": ("me gusta", "like", "dale like", "dale me gusta"),
    "subscribe": ("suscribi", "suscribir", "subscribe", "uni", "unirse", "join"),
    "install": ("instala", "instalar", "install", "descarga", "descargar", "get", "obtene", "obtener"),
}


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return " ".join("".join(ch for ch in text if not unicodedata.combining(ch)).split())


def _words(words: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(r"(?:^|\b)(?:" + "|".join(re.escape(word) for word in words) + r")\b")


_ACT_PATTERNS = {act: _words(words) for act, words in _ACTS.items()}
_ASK_PATTERNS = {act: _words(words) for act, words in _ASKS.items()}


def account_act(label: object) -> str | None:
    """The account act a control's name performs («Seguir a X» → follow), or None."""

    folded = _fold(label)
    return next((act for act, pattern in _ACT_PATTERNS.items() if pattern.search(folded)), None)


def goal_asks_for(goal: object, act: str) -> bool:
    """The goal itself asks for that act («seguí a X», «guardá la playlist», «instalá Spotify»)."""

    pattern = _ASK_PATTERNS.get(act)
    return pattern is not None and pattern.search(_fold(goal)) is not None
