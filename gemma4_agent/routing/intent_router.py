"""Semantic intent classification — universal, multilingual, keyword-free.

Sprint 8 (2026-05-20): the keyword/regex router missed informational
questions ("quién es X", "who is X", "de qué trata X") because the
intent lives in the *wording*, not in any single keyword, and varies by
language. Measured info-recall over 367 real queries was 0.48.

Instead of more keywords (fragile, per-language), we classify the user's
INTENT semantically: compare the query embedding against two anchor
centroids — "is this asking for INFORMATION about the world?" vs "is
this asking to DO something on the computer?". The anchors are short
phrases in several languages; their mean is a robust centroid. This is a
2-class semantic classifier, not a 65-way tool match, so it stays sharp
even on short queries ("quién es batman") where matching against tool
descriptions is too noisy.

Reuses the already-loaded multilingual embedding model from
semantic_router (paraphrase-multilingual-MiniLM-L12-v2, 50+ languages),
so there's no extra model load.

Public API:
    classify_intent(text) -> IntentScores(info, action, margin)
    wants_knowledge(text) -> bool   # info intent with clear margin
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Gate LÉXICO interrogativo (zero-ML, sub-ms). Complemento DETERMINISTA del
# clasificador semántico. Dos usos (2026-05-23, informe latencia/router):
#   1. Fallback cuando el modelo de embeddings NO cargó (classify_intent=None):
#      una pregunta clara ("¿qué es Mortal Kombat?") debe ir a INFO aunque el
#      router esté degradado, en vez de caer al fallback que solo ofrecía office
#      (el bug que torchcodec destapó). [[project_torchcodec_breaks_router]]
#   2. Prior: refuerza la rama info cuando hay interrogativa sin verbo de acción.
# Las palabras interrogativas son conjunto CERRADO por idioma -> regex casi
# perfecta en es/en/pt/it. NO sustituye al semántico (que generaliza), lo respalda.
_WH_WORDS = (
    # español (con y sin tilde — el ASR a veces no la pone)
    r"qu[eé]|qui[eé]n|qui[eé]nes|c[oó]mo|d[oó]nde|cu[aá]ndo|por\s*qu[eé]|"
    r"cu[aá]l|cu[aá]les|cu[aá]nto|cu[aá]ntos|cu[aá]nta|cu[aá]ntas|"
    # inglés
    r"what|who|how|where|when|why|which|whose|"
    # portugués / italiano
    r"o\s*que|quem|onde|quando|qual|quais|quanto|"
    r"cosa|chi|dove|quando|perch[eé]|quale|quali"
)
_WH_RE = re.compile(r"(?:^|\b)(?:" + _WH_WORDS + r")\b", re.IGNORECASE)
_Q_MARK_RE = re.compile(r"[¿?]")
# Verbos de COMANDO (acción sobre la PC). Si aparecen, NO es pregunta-info aunque
# tenga forma interrogativa ("¿podés abrir Spotify?" es acción). Multi-idioma.
_ACTION_VERBS = frozenset({
    "abre", "abrir", "abreme", "ábreme", "abrime", "lanza", "lanzá", "ejecuta",
    "ejecutá", "inicia", "arranca", "cierra", "cerrar", "cerrá",
    "reproduce", "reproducir", "reproducí", "pon", "poné", "ponme", "play",
    "crea", "crear", "creá", "creame", "créame", "genera", "generá",
    "envia", "envía", "enviar", "manda", "mandá", "mándale", "mandale", "send",
    "busca", "buscar", "buscá", "descarga", "descargar", "instala", "instalar",
    "sube", "subí", "baja", "bajá", "apaga", "apagá", "enciende", "prende",
    "open", "close", "create", "launch", "start", "stop", "search", "download",
})


def is_question_lexical(text: str) -> tuple[bool, float]:
    """(es_pregunta_informativa, confianza) por léxico puro. Sin ML, sub-ms.

    Devuelve True solo si hay señal interrogativa (wh-word y/o '¿?') Y NO hay un
    verbo de comando explícito (que la volvería acción). Funciona aunque el
    modelo de embeddings esté caído — ese es el punto."""
    if not text or not text.strip():
        return (False, 0.0)
    t = text.strip().lower()
    has_q = bool(_Q_MARK_RE.search(t))
    has_wh = bool(_WH_RE.search(t))
    if not (has_q or has_wh):
        return (False, 0.0)
    # verbo de comando en los primeros tokens -> es acción, no pregunta-info
    toks = re.findall(r"[a-záéíóúüñ]+", t)
    if any(v in _ACTION_VERBS for v in toks[:3]):
        return (False, 0.0)
    if has_wh and has_q:
        return (True, 0.95)
    if has_wh:
        return (True, 0.80)
    return (True, 0.55)  # solo signo de pregunta

# Anchor phrases per intent, in several languages. The MEAN of each
# group's embeddings is the centroid we compare against. More languages
# here = better coverage; these cover the romance/germanic/english core
# and the model generalizes to the rest via its multilingual training.
_INFO_ANCHORS = [
    # English — people, things, concepts, how/why, who-did/when/where
    "who is this person", "what is this thing", "tell me about this",
    "what is this movie or game about", "how did this happen",
    "general knowledge question about the world",
    "what is this concept", "what does this word mean",
    "how does this technology work", "explain this topic to me",
    "who did or made or directed or invented this",
    "when did this happen", "where is this place",
    "which one is the biggest best or first",
    # Spanish
    "quien es esta persona", "que es esto", "de que trata esto",
    "hablame sobre algo", "de que murio alguien",
    "informacion sobre una pelicula juego o persona",
    "que es este concepto", "como funciona esta tecnologia",
    "explicame este tema", "que significa esta palabra",
    # English/Spanish — searching the INTERNET for external info (prices,
    # news, images, how-to) as opposed to searching local files.
    "search the internet for something", "look up prices online",
    "find news or images about a topic on the web",
    "busca en internet", "busca precios o descuentos online",
    "busca noticias o imagenes en la web", "busca en google",
    "busca como hacer algo en internet",
    # Portuguese / French / German / Italian
    "quem e essa pessoa", "qui est cette personne",
    "wer ist diese person", "chi e questa persona",
    "de quoi parle ce film", "worum geht es",
    "was bedeutet das", "che cosa significa",
    "procurar na internet", "chercher sur internet",
    "im internet suchen", "cercare su internet",
]

_ACTION_ANCHORS = [
    # English
    "open an application", "close a window", "play music",
    "take a screenshot", "send a message", "install something",
    "do something on my computer", "control the pc",
    "reply to a message", "answer her message", "text mom that i'm coming",
    # Spanish
    "abre una aplicacion", "cierra una ventana", "pon musica",
    "manda un mensaje", "instala algo", "saca una captura de pantalla",
    # responder/contestar un mensaje ES una acción (no charla), aunque el cuerpo
    # sea corto ("que ya voy", "que sí"): el destinatario lo hace acción.
    "respondele a mama que ya voy", "contestale a juan que llego tarde",
    "respondele que despues hablamos", "mandale un mensaje a alguien",
    # Portuguese / French / German / Italian
    "abrir um aplicativo", "ouvrir une application",
    "eine anwendung offnen", "apri unapplicazione",
    "envoyer un message", "eine nachricht senden",
    "responder a mensagem", "repondre au message", "auf die nachricht antworten",
]

# Chitchat / contentless utterances. Critical third class: short
# acknowledgements, greetings and filler ("jajaja", "nada", "ok", "oye",
# "que?") embed close to the info centroid by accident (they're not
# action-like) and would otherwise be misread as informational and pull
# a web lookup. An explicit chitchat centroid lets us require info to
# beat chitchat too, so only genuine questions about the world qualify.
_CHITCHAT_ANCHORS = [
    # English
    "hello", "hi", "thanks", "ok", "yeah", "lol", "haha", "umm", "hmm",
    "never mind", "i dont understand", "wait", "sorry", "bye",
    # Spanish
    "hola", "gracias", "si", "no", "bueno", "dale", "aja", "oye", "ya",
    "nada", "que tal", "como estas", "no entiendo", "repite", "espera",
    "perdon", "adios", "chau", "listo", "jaja",
    # Portuguese / French / German / Italian
    "obrigado", "merci", "danke", "grazie", "ciao", "salut",
    # emphatic thanks / greetings (full phrases embed differently)
    "thank you so much", "muchas gracias", "danke schon", "danke sehr",
    "merci beaucoup", "muito obrigado", "grazie mille", "mil gracias",
    "buenas", "buenas que tal", "todo bien", "tudo bem",
]

# Questions about the ASSISTANT ITSELF or its policy ("quién eres", "qué
# puedes hacer", "cuál es tu prioridad", "qué?"). These are interrogative
# but the answer comes from the agent's own identity/system prompt, NOT a
# web lookup — so they must not pull web/knowledge. A dedicated centroid
# separates them from genuine world questions, which the chitchat/info
# margins alone can't (they sit close to info).
_SELF_ANCHORS = [
    # English
    "who are you", "what are you", "what can you do", "what is your name",
    "what is your purpose", "what is your priority", "are you an ai",
    "do you have feelings", "what?", "what do you mean",
    # Spanish
    "quien eres", "que eres", "que puedes hacer", "como te llamas",
    "cual es tu proposito", "cual es tu prioridad", "eres una ia",
    "tienes sentimientos", "que?", "que quieres decir", "quien sos",
    # Portuguese / French / German / Italian
    "quem es voce", "qui es tu", "wer bist du", "chi sei",
    "que peux tu faire", "was kannst du",
]

# META-DIRECTIVES: the user is instructing the agent about HOW to behave or
# answer THIS turn, not asking it to act on the world. Two flavours, both of
# which must NOT pull domain tools (all four 2026-05-21 research models flagged
# this as the missing 5th class behind the 0.51 no-tool keep):
#   (a) explicit tool policy: "no uses tools", "responde sin herramientas",
#       "usa tools solo si hace falta", "no abras el navegador".
#   (b) mission-behavior policy: "arregla todo el repo como sea", "termina la
#       misión dejando log y limpieza", "acepta todos los permisos", "no
#       mezcles bugfix con deuda" — directives about the run, not a discrete
#       command the router should map to one tool. The LLM/orchestrator handles
#       these; the router should abstain rather than guess a tool.
# These embed near action/info today (they contain verbs like "usa", "abre",
# "termina") so the chitchat/selfref centroids miss them. A dedicated centroid
# pulls them out. Multilingual anchors so it generalizes, not a keyword list.
#
# IMPORTANT scoping lesson (2026-05-21 dev measurement): the FIRST cut also
# included mission-behaviour anchors ("termina la misión dejando log", "arregla
# el repo como sea", "si el tool call falla repregunta"). Those absorbed real
# commands-with-a-qualifier ("corre hardcode_guard si existe", "lista procesos
# Python", "resume el log sin cargar todo") and cost 2.4 pts of recall on dev.
# A command WITH a constraint is still a command. So META is scoped TIGHTLY to
# explicit TOOL/ANSWER POLICY only — "should I use tools at all / how should I
# answer" — never mission constraints. The mission directives that are truly
# no-tool ("arregla el repo") are better left to the abstain head (Step 2),
# which sees the whole feature vector, not this single centroid.
_META_ANCHORS = [
    # English — explicit tool/answer policy
    "do not use any tools for this answer", "answer without using tools",
    "reply in plain text without tools", "do not use any tool just talk",
    "answer this question without calling any function",
    # Spanish — explicit tool/answer policy
    "no uses herramientas para esta respuesta",
    "responde sin usar herramientas", "responde en texto plano sin tools",
    "no llames ninguna herramienta solo responde",
    "contesta esta pregunta sin usar ninguna funcion",
    # Portuguese / French / German / Italian — policy core
    "nao use ferramentas nesta resposta", "n'utilise pas d'outils pour repondre",
    "benutze keine werkzeuge antworte nur", "non usare strumenti rispondi solo",
]

# wants_knowledge fires only when INFO is the DOMINANT class — it must beat
# action by a margin AND be the argmax over chitchat and self-reference.
# Tuned on the historical corpus: genuine world questions in any language
# clear it ("quién es X", "what is X about"); smalltalk and bare names lose
# because chitchat outranks info there ("Ema", "no entiendo nada"); commands
# lose because action wins. No absolute-score cutoff (that dropped real
# low-signal queries like "what is quantum computing"); the argmax does it.
_VS_ACTION_MARGIN = float(os.environ.get("GEMMA4_INTENT_VS_ACTION", "0.05"))
# Conversational abstention gate (is_conversational): how much the
# conversational classes (chitchat ∪ selfref) must outrank the worldly
# classes (action ∪ info) before we suppress the semantic router's noisy
# domain-tool suggestions. Tuned on the dev split only.
_CONV_MARGIN = float(os.environ.get("GEMMA4_INTENT_CONV_MARGIN", "0.03"))
# Conversational abstention gate (is_conversational): how much the
# conversational classes (chitchat ∪ selfref) must outrank the worldly
# classes (action ∪ info) before we suppress the semantic router's noisy
# domain-tool suggestions. Tuned on the dev split only.
_CONV_MARGIN = float(os.environ.get("GEMMA4_INTENT_CONV_MARGIN", "0.03"))
# Absolute floor a query's META score must clear (in addition to being the
# argmax) before we treat it as a tool/answer-policy directive. Genuine meta
# phrasings ("no uses herramientas", "responde sin tools") score ~0.45-0.65 on
# the tight anchor set; commands-with-a-qualifier peak below this. Tuned on dev.
_META_FLOOR = float(os.environ.get("GEMMA4_INTENT_META_FLOOR", "0.36"))


@dataclass(frozen=True)
class IntentScores:
    info: float
    action: float
    chitchat: float = 0.0
    selfref: float = 0.0
    meta: float = 0.0

    @property
    def margin(self) -> float:
        """Info margin over the strongest competing class."""
        return self.info - max(self.action, self.chitchat, self.selfref, self.meta)


class _Centroids:
    info: Any = None
    action: Any = None
    chitchat: Any = None
    selfref: Any = None
    meta: Any = None
    ready: bool = False


_C = _Centroids()


def _ensure_centroids() -> bool:
    if _C.ready:
        return _C.info is not None
    try:
        from . import semantic_router as sr
        if not sr._ensure_loaded():
            _C.ready = True
            return False
        import numpy as np
        model = sr._STATE.model

        def _centroid(anchors: list[str]) -> Any:
            e = model.encode(anchors, normalize_embeddings=True).mean(0)
            return np.asarray(e / (np.linalg.norm(e) or 1.0), dtype="float32")

        _C.info = _centroid(_INFO_ANCHORS)
        _C.action = _centroid(_ACTION_ANCHORS)
        _C.chitchat = _centroid(_CHITCHAT_ANCHORS)
        _C.selfref = _centroid(_SELF_ANCHORS)
        _C.meta = _centroid(_META_ANCHORS)
        _C.ready = True
        return True
    except Exception:
        _C.ready = True
        return False


def classify_intent(text: str) -> IntentScores | None:
    """Return IntentScores or None if the embedding model is unavailable."""
    if not text or not text.strip():
        return None
    if not _ensure_centroids() or _C.info is None:
        return None
    try:
        from . import semantic_router as sr
        import numpy as np
        # Use the LRU-cached embedding so multiple intent checks on the same
        # turn (is_conversational + wants_knowledge + the planner's gate) cost
        # ONE encode, not three — matters for the per-turn latency budget.
        qe = sr.embed(text)
        if qe is None:
            qe = sr._STATE.model.encode([text], normalize_embeddings=True)[0]
        qe = np.asarray(qe, dtype="float32")
        return IntentScores(
            info=float(qe @ _C.info),
            action=float(qe @ _C.action),
            chitchat=float(qe @ _C.chitchat),
            selfref=float(qe @ _C.selfref),
            meta=float(qe @ _C.meta) if _C.meta is not None else 0.0,
        )
    except Exception:
        return None


def is_conversational(text: str) -> bool:
    """True when the query is dominantly CONVERSATIONAL — chitchat or a
    question about the assistant itself — rather than a request for a
    domain action or world knowledge.

    Used by the planner as an ABSTENTION GATE for the semantic router.
    The semantic stage (suggest_tools_semantic) always returns its top-k
    tools for ANY input above a low cosine floor, so on smalltalk and
    self-reference turns ("quién eres", "gracias", "jajaja", "no entiendo")
    it over-offers domain tools the user never asked for. When this returns
    True we suppress that semantic union, because the turn is not asking the
    PC to do anything.

    Decision is purely semantic (no keywords): the conversational classes
    (chitchat ∪ selfref) must BOTH outrank action AND outrank info — i.e.
    the strongest signal is "talking", not "do X" and not "tell me about
    the world". The action/info guards keep real commands and real
    questions from being silenced:
      - "abre Steam"        → action highest        → NOT conversational
      - "quién es Batman"   → info highest           → NOT conversational
      - "quién eres"        → selfref highest         → conversational
      - "gracias" / "ok"    → chitchat highest        → conversational
      - "no entiendo nada"  → chitchat highest        → conversational

    A small margin (_CONV_MARGIN) avoids silencing borderline turns where
    action/info are essentially tied with the conversational classes.
    """
    s = classify_intent(text)
    return _is_conversational_scores(s)


def _is_conversational_scores(s: IntentScores | None) -> bool:
    """Decision from precomputed scores (one embed serves both gates)."""
    if s is None:
        return False
    # Never suppress a genuine world-knowledge question, even if it embeds
    # close to chitchat ("¿quién es el mejor?", "háblame de la peli X").
    if _wants_knowledge_scores(s):
        return False
    # meta-directives ("no uses herramientas", "responde sin tools") steer how
    # to answer, not what to do — suppress the domain union. META is gated more
    # strictly than chitchat/selfref: it must be the argmax AND clear an
    # absolute floor, because its anchors sit closer to action/info (they
    # contain verbs) and a loose gate cost recall on commands-with-qualifiers.
    if (s.meta >= _META_FLOOR and s.meta >= max(s.action, s.info, s.chitchat,
                                                s.selfref)):
        return True
    conv = max(s.chitchat, s.selfref)
    worldly = max(s.action, s.info)
    return (conv - worldly) >= _CONV_MARGIN


def wants_knowledge(text: str) -> bool:
    """True when the query is an informational question about the WORLD
    (any language): info intent must be the dominant class, beating
    action, chitchat AND self-reference. This keeps web/knowledge out of:
      - smalltalk ("jajaja", "nada")             → chitchat wins
      - PC commands ("abre Steam")               → action wins
      - questions about the agent ("quién eres")  → selfref wins
    while still firing for "quién es X", "what is X about", "de qué murió
    X" in any language. Used by the planner so the LLM can look things up
    even when no keyword fired.

    FALLBACK LÉXICO (2026-05-23): si el modelo de embeddings no cargó
    (classify_intent → None), una pregunta interrogativa clara SIN verbo de
    comando se trata como info igual. Esto evita el mis-ruteo a 'office' que
    pasó cuando torchcodec rompió el router en silencio."""
    s = classify_intent(text)
    if s is None:
        # Router degradado: confiar en el léxico para no mis-rutear preguntas.
        is_q, conf = is_question_lexical(text)
        return is_q and conf >= 0.80
    return _wants_knowledge_scores(s)


def _wants_knowledge_scores(s: IntentScores | None) -> bool:
    if s is None:
        return False
    # info must be the DOMINANT class — beat action by a margin AND be at
    # least as strong as chitchat and self-reference. Requiring info to be
    # the argmax (not merely "not dominated by 0.12") is what stops filler
    # and bare names from pulling web/knowledge: "Ema" (chitchat 0.616 >
    # info 0.508) and "no entiendo nada" (chitchat > info) are blocked,
    # while genuine world-questions in any language ("quién es X", "what is
    # X about") clear it because info wins there. Measured on dev: this
    # raised NO-TOOL keep ~0.09 for ~0.005 recall (a handful of in-isolation-
    # ambiguous turns like "¿quién es el mejor?" that the agent resolves
    # from history anyway).
    return (
        (s.info - s.action) >= _VS_ACTION_MARGIN
        and s.info >= s.chitchat
        and s.info >= s.selfref
        # "responde sin herramientas: qué es Batman" is info-shaped but the
        # user forbade tools — meta must not be the winner, or we'd pull web.
        and s.info >= s.meta
    )


def router_health() -> tuple[bool, str]:
    """Health-check del router semántico. (sano, detalle).

    Falla RUIDOSO si el modelo de embeddings no cargó — el caso torchcodec dejó
    el router vacío SIN avisar y mis-ruteó todo. Probar en el arranque y exponer
    a la UI/logs. Probes en 4 idiomas: una pregunta info debe clasificar info>
    action; un comando debe clasificar action>info."""
    if not _ensure_centroids() or _C.info is None:
        return (False, "encoder de embeddings no cargó (¿torchcodec/optimum/"
                       "tensorflow instalado? rompe sentence-transformers)")
    probes = [
        ("¿qué es python?", True), ("what is mortal kombat?", True),
        ("abre whatsapp", False), ("pon música", False),
    ]
    for q, expect_info in probes:
        s = classify_intent(q)
        if s is None:
            return (False, f"classify_intent devolvió None para {q!r}")
        got_info = s.info > s.action
        if got_info != expect_info:
            return (False, f"probe {q!r}: esperaba info={expect_info} "
                           f"pero info={s.info:.2f} action={s.action:.2f}")
    return (True, "router OK (4/4 probes)")


# ---------------------------------------------------------------------------
# Intención de COMPRA/BÚSQUEDA EN TIENDA WEB (2026-05-26). Caso real: "comprá un
# juego en Instant Gaming" se mis-ruteaba a game_launcher/app porque el NOMBRE
# de la tienda ("Instant Gaming") embebe cerca de las tools de juegos. Ninguna
# descripción de tool lo vence (las negaciones no funcionan en espacio de
# embeddings). Solución: clasificar la INTENCIÓN ("buscar/comprar un producto en
# una tienda online") por embeddings multilingües; cuando dispara, el planner
# mete browser/browser_real al frente del subset. Ataca la intención de compra,
# no pelea con el nombre de marca — generaliza a Epic/GOG/Amazon/etc.
# CUMPLE las reglas: embeddings multilingües + margen + fallback seguro.
# ---------------------------------------------------------------------------
_SHOP_ANCHORS = [
    # es — comprar/buscar un producto o juego en una tienda online
    "comprar un juego en una tienda online", "comprar algo por internet",
    "ir a la pagina de una tienda online",
    "abrir el sitio web de una tienda",
    "buscar un juego para comprar en una tienda web",
    "buscar un titulo de juego en una tienda digital",
    "buscar un producto en una tienda web por nombre",
    "ir a una tienda online y comprar un juego",
    "comprame este juego en la tienda", "agregar un producto al carrito y comprar",
    "buscar el precio de un juego en una tienda online",
    "comprar en instant gaming", "comprar en la tienda de epic o gog",
    "buscar un juego en instant gaming", "buscar el ultimo juego en la tienda online",
    "ver un juego en instant gaming para comprarlo",
    # en
    "buy a game on an online store", "purchase something online",
    "go to the website of an online store",
    "open an online store website",
    "find a game to buy on a web store", "add a product to the cart and check out",
    "shop for a game on a store website",
    "search a game title on a digital game store",
    "open an online shop and find a product",
    # pt / fr / de / it
    "comprar um jogo numa loja online", "acheter un jeu sur une boutique en ligne",
    "ein spiel in einem online shop kaufen", "comprare un gioco in un negozio online",
]
_NOSHOP_ANCHORS = [
    # es — NO es comprar en tienda: lanzar instalado, abrir app, preguntar, charlar
    "lanzar un juego que ya tengo instalado", "abrir una aplicación instalada",
    "abrir steam", "jugar un juego instalado", "qué es este juego",
    "poner música", "mandar un mensaje", "hola cómo estás",
    # en
    "launch an installed game", "open an installed application", "open steam",
    "what is this game about", "play music", "send a message", "hello",
    # pt / fr / de / it
    "abrir um aplicativo instalado", "ouvrir une application installée",
    "ein installiertes spiel starten", "aprire un'app installata",
]


class _ShopCentroids:
    shop: Any = None
    noshop: Any = None
    ready: bool = False


_SHOP = _ShopCentroids()
# Margen (shop - noshop) para considerar intención de compra-en-tienda. Tuneado
# conservador: solo dispara cuando la intención de compra-online es clara.
_SHOP_MARGIN = float(os.environ.get("GEMMA4_SHOP_MARGIN", "0.03"))


def _ensure_shop_centroids() -> bool:
    if _SHOP.ready:
        return _SHOP.shop is not None
    try:
        from . import semantic_router as sr
        if not sr._ensure_loaded():
            _SHOP.ready = True
            return False
        import numpy as np
        model = sr._STATE.model

        def _centroid(anchors: list[str]) -> Any:
            e = model.encode(anchors, normalize_embeddings=True).mean(0)
            return np.asarray(e / (np.linalg.norm(e) or 1.0), dtype="float32")

        _SHOP.shop = _centroid(_SHOP_ANCHORS)
        _SHOP.noshop = _centroid(_NOSHOP_ANCHORS)
        _SHOP.ready = True
        return True
    except Exception:
        _SHOP.ready = True
        return False


def wants_web_store(text: str) -> bool:
    """True si el turno pide BUSCAR o COMPRAR un producto/juego en una TIENDA WEB
    (Instant Gaming, Epic, GOG, Amazon...). Multilingüe, por embeddings. El
    planner lo usa para subir browser/browser_real al subset. Fallback seguro:
    sin encoder -> False (no fuerza nada)."""
    txt = (text or "").strip()
    if len(txt) < 3:
        return False
    if not _ensure_shop_centroids() or _SHOP.shop is None:
        return False
    try:
        from . import semantic_router as sr
        import numpy as np
        q = sr.embed(txt)
        if q is None:
            q = sr._STATE.model.encode([txt], normalize_embeddings=True)[0]
        q = np.asarray(q, dtype="float32")
        return (float(q @ _SHOP.shop) - float(q @ _SHOP.noshop)) >= _SHOP_MARGIN
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Intención de NAVEGAR A UNA WEB (2026-05-27). Caso medido: "andá a la página de
# Instant Gaming" / "entrá a youtube" ruteaban inconsistente (browser / web-a-
# Google / computer_use) porque el subset ofrecía 4 tools de navegación y el 4B
# elegía mal (web=Google en vez de abrir el sitio), o game_launcher ganaba por la
# colisión de marca. Este clasificador detecta "IR A una página/sitio/URL" para
# que el planner lidere con browser/browser_real y SAQUE web/game_launcher (que
# son para preguntar / lanzar instalado, NO para navegar). Embeddings, fallback
# seguro. Distinto de wants_web_store (comprar): navegar incluye abrir cualquier
# sitio, no solo tiendas.
# ---------------------------------------------------------------------------
_NAV_ANCHORS = [
    # es
    "andá a la página de youtube", "entrá a ese sitio web", "abrí esa página",
    "navegá a github punto com", "llevame a la web de instant gaming",
    "entrá a la tienda online", "abrí el sitio en el navegador", "ir a una url",
    "metete en esa página web",
    # en
    "go to the youtube page", "open that website", "navigate to github dot com",
    "take me to the instant gaming site", "open the url in the browser",
    # pt / fr / de / it
    "vá para o site", "va sur ce site web", "geh auf die webseite",
    "vai a quel sito web",
]
_NONAV_ANCHORS = [
    # NO es navegar: preguntar info, lanzar app instalada, charlar, operar app
    "qué es python", "quién ganó el mundial", "cuánto cuesta esto",
    "lanzá un juego que tengo instalado", "abrí spotify instalado",
    "poné música", "mandá un mensaje", "hola cómo estás",
    "what is this about", "play music", "launch an installed game",
    "send a message", "open an installed app",
]


class _NavCentroids:
    nav: Any = None
    nonav: Any = None
    ready: bool = False


_NAV = _NavCentroids()
_NAV_MARGIN = float(os.environ.get("GEMMA4_NAV_MARGIN", "0.06"))


def _ensure_nav_centroids() -> bool:
    if _NAV.ready:
        return _NAV.nav is not None
    try:
        from . import semantic_router as sr
        if not sr._ensure_loaded():
            _NAV.ready = True
            return False
        import numpy as np
        model = sr._STATE.model

        def _centroid(anchors: list[str]) -> Any:
            e = model.encode(anchors, normalize_embeddings=True).mean(0)
            return np.asarray(e / (np.linalg.norm(e) or 1.0), dtype="float32")

        _NAV.nav = _centroid(_NAV_ANCHORS)
        _NAV.nonav = _centroid(_NONAV_ANCHORS)
        _NAV.ready = True
        return True
    except Exception:
        _NAV.ready = True
        return False


def wants_web_navigation(text: str) -> bool:
    """True si el turno pide IR A una página/sitio/URL en el navegador (navegar),
    distinto de preguntar info o lanzar una app instalada. El planner lo usa para
    liderar con browser/browser_real y sacar web/game_launcher del subset.
    Multilingüe, fallback seguro."""
    txt = (text or "").strip()
    if len(txt) < 3:
        return False
    if not _ensure_nav_centroids() or _NAV.nav is None:
        return False
    try:
        from . import semantic_router as sr
        import numpy as np
        q = sr.embed(txt)
        if q is None:
            q = sr._STATE.model.encode([txt], normalize_embeddings=True)[0]
        q = np.asarray(q, dtype="float32")
        return (float(q @ _NAV.nav) - float(q @ _NAV.nonav)) >= _NAV_MARGIN
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Intención de MANDAR UN EMAIL (2026-05-27). El 4B ni emite el tool-call de email
# (medido: reply vacío). Para un usuario sin manos, mandar correo por voz es
# diario. Este clasificador detecta "mandá/escribí un correo a X" para que la red
# determinista abra el redactor web pre-rellenado (sin token, usa la sesión
# logueada). Distinto de notas/mensajes-de-chat. Embeddings, fallback seguro.
# ---------------------------------------------------------------------------
_EMAIL_ANCHORS = [
    "manda un correo a juan", "escribi un email a ana", "envia un mail a soporte",
    "mandale un correo electronico a mi jefe", "redacta un email para el profe",
    "escribile un correo a maria diciendo que llego tarde",
    "mandale un correo a ana arroba gmail diciendo que llego tarde",
    "envia un mail a pedro@empresa.com con el asunto reunion",
    "send an email to john@gmail.com saying i'm late",
    "send an email to john", "write a mail to support", "email my boss",
    "envia um email", "envoyer un courriel", "schreib eine email", "manda una mail",
]
_NOEMAIL_ANCHORS = [
    # NO es email: mensaje de chat, nota, llamada, pregunta, navegar
    "mandale un mensaje a juan por whatsapp", "escribile a ana en discord",
    "anota que tengo que llamar al medico", "recordame algo",
    "llama a mi mama", "que es el correo electronico", "abri gmail",
    "send a whatsapp message", "take a note", "what is email", "open gmail",
]


class _EmailCentroids:
    em: Any = None
    noem: Any = None
    ready: bool = False


_EMAIL = _EmailCentroids()
_EMAIL_MARGIN = float(os.environ.get("GEMMA4_EMAIL_MARGIN", "0.08"))


def _ensure_email_centroids() -> bool:
    if _EMAIL.ready:
        return _EMAIL.em is not None
    try:
        from . import semantic_router as sr
        if not sr._ensure_loaded():
            _EMAIL.ready = True
            return False
        import numpy as np
        model = sr._STATE.model

        def _centroid(anchors: list[str]) -> Any:
            e = model.encode(anchors, normalize_embeddings=True).mean(0)
            return np.asarray(e / (np.linalg.norm(e) or 1.0), dtype="float32")

        _EMAIL.em = _centroid(_EMAIL_ANCHORS)
        _EMAIL.noem = _centroid(_NOEMAIL_ANCHORS)
        _EMAIL.ready = True
        return True
    except Exception:
        _EMAIL.ready = True
        return False


def wants_send_email(text: str) -> bool:
    """True si el turno pide MANDAR/ESCRIBIR un CORREO (email), distinto de nota/
    mensaje-de-chat/llamada. Multilingüe, fallback seguro. La red determinista lo
    usa para abrir el redactor web pre-rellenado."""
    txt = (text or "").strip()
    if len(txt) < 5:
        return False
    if not _ensure_email_centroids() or _EMAIL.em is None:
        return False
    try:
        from . import semantic_router as sr
        import numpy as np
        q = sr.embed(txt)
        if q is None:
            q = sr._STATE.model.encode([txt], normalize_embeddings=True)[0]
        q = np.asarray(q, dtype="float32")
        return (float(q @ _EMAIL.em) - float(q @ _EMAIL.noem)) >= _EMAIL_MARGIN
    except Exception:
        return False
