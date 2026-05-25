"""Splitter de comandos multi-intent — MULTILINGÜE (investigación 7, 2026-05-23).

"abrí Spotify y bajá el volumen" son DOS acciones. Un 4B causal colapsa el
multi-intent (MIDLM, COLING 2025: la atención causal no maneja multi-intent como
un 7B bidireccional). La cura NO es agrandar el modelo: es partir el enunciado en
cláusulas ANTES de que el LLM lo vea y rutear cada una como su propio turno.

UNIVERSAL (CLAUDE.md: la app la usa cualquier hablante; nada de regex es-only):
  - Capa 1 (rápida, español): regex de verbos imperativos. Atajo barato exacto.
  - Capa 2 (multilingüe): si la capa 1 no parte, intentar partir en una
    CONJUNCIÓN de cualquier idioma (y/and/e/und/et/o/or/oder...) y CONFIRMAR por
    EMBEDDINGS que lo que sigue es una ACCIÓN (no un sustantivo). Así
    "open Spotify and turn down the volume" parte, pero "Tom and Jerry" /
    "salt and pepper" / "music by the Beatles" NO (la parte tras la conjunción
    puntúa como sintagma nominal, no como acción). Mismo encoder multilingüe del
    router. Cabe en vram4 (un encode MiniLM ~<30ms, sólo si hay conjunción).

FALLBACK SEGURO: si el encoder no está, la capa 2 se apaga (sólo capa 1 español);
un multi-intent no detectado degrada ELEGANTEMENTE (el LLM ve el comando entero,
status quo). Conservador (Park et al. arXiv:2108.01812: no romper lo que anda).
"""
from __future__ import annotations

import os
import re

# Verbos imperativos español (es rioplatense/voseo + estándar) — CAPA 1 rápida.
# Formas con clítico (abrilo, ponelo...) van PRIMERO; SIN \b al final.
_IMPERATIVE = (
    r"abril[oa]|cerral[oa]|mostral[oa]|reprodu[cz]il[oa]|ponel[oa]|m[áa]ndalo|"
    r"mandalo|le[ée]lo|"
    r"abr[ií]|abrime|cerr[áa]|cierra|cerrame|ponel[ea]|pon[eé]|pon|ponme|"
    r"baj[áa]|baja|sub[íi]|sube|mand[áa]|manda|mandale|m[áa]ndale|"
    r"busc[áa]|busca|buscame|and[áa]|anda|reproduc[íie]|reproduce|"
    r"mut[eé]a?|silenci[áa]|mostr[áa]|muestra|mostrame|empez[áa]|empieza|"
    r"par[áa]|para|pausa|paus[áa]|reanud[áa]|reanuda|llam[áa]|llama|"
    r"escrib[íi]|escribe|tecle[áa]|teclea|tipe[áa]|tipea|digit[áa]|digita|"
    r"crea|cre[áa]|apag[áa]|apaga|prend[ée]|prende|"
    r"enciend[ee]|cancel[áa]|cancela|borr[áa]|borra|elimin[áa]|elimina|"
    # verbos de CLICK/INTERACCIÓN (Fase B computer-use): "apretá/clickeá/tocá/
    # seleccioná/elegí <botón>". Sin estos, una cadena "...y apretá enter" no
    # partía la 3ra cláusula. Voseo + estándar.
    r"apret[áa]|apreta|clicke[áa]|clickea|click[ée]a?|toc[áa]|toca|"
    r"seleccion[áa]|selecciona|eleg[íi]|elige|presion[áa]|presiona|"
    r"guard[áa]|guarda|confirm[áa]|confirma|acept[áa]|acepta|activ[áa]|activa|"
    r"desactiv[áa]|desactiva|"
    # verbos de NAVEGACIÓN: "andá/ve/navegá a <sección>".
    r"naveg[áa]|navega|dirig[íi]te|ve\s+a|and[áa]\s+a"
)

_SPLIT_RE = re.compile(
    r"\s*(?:"
    r";\s+(?=(?:" + _IMPERATIVE + r"))"
    r"|,?\s+(?:y|e|o)\s+(?:despu[ée]s\s+|luego\s+|tambi[ée]n\s+)?(?=(?:" + _IMPERATIVE + r"))"
    # ASÍNDETON: coma SIN conjunción seguida de un imperativo ("abrí la calc,
    # escribí X y apretá enter"). 2026-05-24: el eval Tier-4 mostró que la coma
    # antes de la 1ra acción dejaba dos acciones pegadas en una cláusula -> el 4B
    # abría pero no tecleaba. Requiere un VERBO imperativo tras la coma, así
    # "sal, pimienta, azúcar" (sustantivos) NO parte.
    r"|,\s+(?=(?:" + _IMPERATIVE + r"))"
    r"|\s+(?:despu[ée]s|luego)\s+(?=(?:" + _IMPERATIVE + r"))"
    r")",
    re.IGNORECASE,
)

# CAPA 2: conjunciones coordinantes multi-idioma (closed set, language-agnostic).
# Sólo conjunción entre espacios (no "Disney" partido). El "?" de "después/luego"
# español ya lo cubre la capa 1; acá conectores neutrales de varios idiomas.
# OJO: NO incluir "o" suelta — es artículo en portugués ("abre o Spotify") y
# disparaba splits espurios. Para disyunción usamos las formas largas
# (or/oder/ou/oppure). "e"/"y" sí ("and" en es/pt/it, rara vez artículo).
_CONJUNCTION_RE = re.compile(
    r"\s+(?:y|e|and|then|or|ou|et|puis|und|dann|oder|poi|oppure)\s+"
    r"(?:then\s+|after\s+that\s+|afterwards\s+|depois\s+|ensuite\s+|danach\s+)?",
    re.IGNORECASE,
)

# Clítico/anáfora español que indica dependencia de la cláusula previa. CAPA 1.
_DEP_RE = re.compile(
    r"\b(?:lo|la|los|las|le|les|eso|ese|esa|aquel)\b"
    r"|(?:abril[oa]|cerral[oa]|ci[ée]rral[oa]|cierral[oa]|mostral[oa]|"
    r"mu[ée]stral[oa]|reprodu[cz]il[oa]|ponel[oa]|m[áa]ndalo|mandalo|"
    r"le[ée]lo|leel[oa]|p[áa]usal[oa]|pausal[oa])",
    re.IGNORECASE,
)

# Cap de cláusulas por misión. **VERIFICADO = 3** (2026-05-24): cadenas de 2-3
# pasos (abrir+escribir+enter) se midieron estables contra el SO real con
# falso-PASS 0%. El soporte del código llega a más, pero NO se afirma >3: las
# cadenas de 4-5 pasos no se pudieron verificar ESTABLES (la capa de tecleo del
# SO —SendKeys a apps recién abiertas— se degrada de forma no-determinista bajo
# carga; ver memoria project_gui_chains). Mantener el cap en lo MEDIDO, no en lo
# aspiracional. >3 cláusulas = no partir (status quo: el LLM ve el comando entero).
MAX_CLAUSES = 3

# Margen mínimo (action - noun) para tratar una cláusula como ACCIÓN (medido:
# acciones multi-idioma ~+0.24..+0.51, sintagmas nominales ~-0.24..-0.33).
_ACTION_MARGIN = float(os.environ.get("GEMMA4_SPLIT_ACTION_MARGIN", "0.05"))

_ACTION_ANCHORS = [
    "bajá el volumen", "abrí la calculadora", "poné música", "cerrá la ventana",
    "turn down the volume", "open the calculator", "play music", "close the window",
    "baixa o volume", "abre a calculadora", "mach das leiser", "öffne den rechner",
    "monte le son", "ouvre la calculatrice", "abbassa il volume", "apri la calcolatrice",
]
_NOUN_ANCHORS = [
    "sal y pimienta", "Tom y Jerry", "la lista de compras", "una banda llamada Queen",
    "salt and pepper", "the shopping list", "music by the Beatles", "a band called Queen",
    "sel et poivre", "Salz und Pfeffer", "sale e pepe", "uma lista de compras",
]


class _ActionCentroids:
    __slots__ = ("ready", "action", "noun")

    def __init__(self) -> None:
        self.ready = False
        self.action = None
        self.noun = None


_AC = _ActionCentroids()


def _ensure_action_centroids() -> bool:
    if _AC.ready:
        return _AC.action is not None
    try:
        from . import semantic_router as sr
        if not sr._ensure_loaded():
            _AC.ready = True
            return False
        import numpy as np
        model = sr._STATE.model

        def _centroid(anchors):
            e = model.encode(anchors, normalize_embeddings=True).mean(0)
            return np.asarray(e / (np.linalg.norm(e) or 1.0), dtype="float32")

        _AC.action = _centroid(_ACTION_ANCHORS)
        _AC.noun = _centroid(_NOUN_ANCHORS)
        _AC.ready = True
        return True
    except Exception:
        _AC.ready = True
        return False


def _is_action_clause(clause: str) -> bool:
    """True si la cláusula puntúa como ACCIÓN (no sintagma nominal), por
    embeddings multilingües. False si no hay encoder (capa 2 se apaga)."""
    if not _ensure_action_centroids() or _AC.action is None:
        return False
    try:
        from . import semantic_router as sr
        import numpy as np
        q = sr.embed(clause)
        if q is None:
            q = sr._STATE.model.encode([clause], normalize_embeddings=True)[0]
        q = np.asarray(q, dtype="float32")
        return float(q @ _AC.action) - float(q @ _AC.noun) >= _ACTION_MARGIN
    except Exception:
        return False


def _semantic_enabled() -> bool:
    raw = (os.environ.get("GEMMA4_SPLIT_MULTILANG") or "").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _split_multilingual(utterance: str) -> list[str]:
    """CAPA 2: parte en una conjunción multi-idioma SOLO si ambas partes
    puntúan como acción. Devuelve [utterance] si no hay split confiable."""
    if not _semantic_enabled():
        return [utterance]
    # candidatos de split: cada ocurrencia de una conjunción.
    matches = list(_CONJUNCTION_RE.finditer(utterance))
    if not matches:
        return [utterance]
    # Demasiadas conjunciones = probablemente ruido / lista; no confiar (cap).
    if len(matches) >= MAX_CLAUSES:
        return [utterance]
    # probar el PRIMER punto de conjunción que produzca dos cláusulas-acción.
    for mt in matches:
        left = utterance[:mt.start()].strip(" ,.;")
        right = utterance[mt.end():].strip(" ,.;")
        if len(left.split()) < 2 or len(right.split()) < 1:
            continue
        # ambas partes deben ser acción (la derecha es la clave: "Jerry" no lo es)
        if _is_action_clause(left) and _is_action_clause(right):
            # recursar sobre la derecha por si hay 3 acciones, respetando el cap
            rest = _split_multilingual(right)
            parts = [left, *rest]
            if len(parts) <= MAX_CLAUSES:
                return parts
            return [utterance]
    return [utterance]


# Verbos de PURA navegación/dirección ("ir a", "entrar a") — un prefijo de
# CONTEXTO, NO una acción que produzca un efecto por sí sola. Deliberadamente NO
# incluye "abrí/abre/open": abrir una app SÍ es una acción que encadena ("abrí la
# calc y escribí 2+2" son 2 acciones reales). "Ve a discord" no hace nada solo —
# es el contexto de lo que sigue.
_PURE_NAV_VERB = re.compile(
    r"^\s*(?:"
    r"entr[áa]\w*|entra|and[áa]\w*|anda|naveg[áa]\w*|navega|dirig[íi]te|ve|"   # es
    r"go|navigate|"                                                            # en
    r"vai|va|entre"                                                            # pt/it/fr
    r")\b"
    r"(?:\s+(?:a|al|to|para|dans|au|in|nel|su|n[oa]))?"
    r"[\s:]+",
    re.IGNORECASE,
)


def _is_bare_nav_to_app(clause: str) -> bool:
    """True si la cláusula es SOLO "ir/entrar a <app>" (prefijo de contexto), sin
    una acción propia adentro. P.ej. "Ve a discord" sí; "abrí la calc y escribí 2+2"
    NO (abrir es acción que encadena, por eso _PURE_NAV_VERB excluye 'abrí'/'open').
    Estructural: matchea un verbo de PURA navegación y el resto es corto (≤3 tokens,
    el nombre de la app) y NO contiene otro verbo imperativo. Sirve para NO partir
    "Ve a discord y pon el chat de X" (es UNA navegación-en-app: partirla pierde el
    "discord" de la 2da cláusula)."""
    if not clause:
        return False
    m = _PURE_NAV_VERB.match(clause)
    if not m:
        return False
    rest = clause[m.end():].strip(" ,.;:")
    if not rest or len(rest.split()) > 3:
        return False  # vacío o demasiado largo -> no es un simple "ir a <app>"
    # si el resto YA contiene un verbo imperativo, no es navegación pura.
    if re.search(_IMPERATIVE, rest, re.IGNORECASE):
        return False
    return True


def split_command(utterance: str) -> list[str]:
    """Parte un enunciado en cláusulas de acción. Devuelve [utterance] si no hay
    multi-intent claro (caso normal). Nunca lanza.

    Capa 1 (español, rápida) primero; si no parte, capa 2 (multilingüe semántica)."""
    if not utterance or not utterance.strip():
        return [utterance]
    # CAPA 1: regex español (exacta, barata, ya validada).
    parts = [p.strip(" ,.;") for p in _SPLIT_RE.split(utterance) if p and p.strip(" ,.;")]
    if len(parts) > 1:
        # NO PARTIR cuando la 1ra cláusula es un "ir/entrar a <app>" puro: es un
        # PREFIJO DE CONTEXTO de lo que sigue, no una acción aparte. Bug medido
        # 2026-05-25: "Ve a discord y pon el chat de cbayeah" se partía en
        # ["Ve a discord","pon el chat de cbayeah"]; la 2da, aislada, perdía
        # "discord" -> el router la mandaba a WhatsApp (whatsapp=0.58) y abría el
        # chat en la app equivocada. Manteniéndolas juntas, _window_title_in_text
        # ve "discord", matchea la ventana abierta y rutea a navegación-en-app.
        if _is_bare_nav_to_app(parts[0]):
            return [utterance]
        if len(parts) > MAX_CLAUSES:
            return [utterance]
        return parts
    # CAPA 2: multilingüe (solo si capa 1 no partió).
    return _split_multilingual(utterance)


def has_back_reference(clause: str) -> bool:
    """True si la cláusula tiene un clítico/deíctico que refiere a algo previo."""
    return bool(_DEP_RE.search(clause))


def plan_clauses(utterance: str) -> list[dict]:
    """Devuelve [{text, depends_on_prev}] por cláusula. depends_on_prev=True =>
    ejecutar serializado (el resultado de la anterior alimenta esta)."""
    clauses = split_command(utterance)
    return [{"text": c, "depends_on_prev": i > 0 and has_back_reference(c)}
            for i, c in enumerate(clauses)]


# --- Extracción de payload de ESCRITURA (Fase 2 computer-use) ----------------
# Una cláusula "escribí/tecleá/type <texto>" en un contexto GUI debe ir a la
# macro determinista type_into, NO a que el 4B forme la llamada. El verbo de
# escritura inicial es vocabulario CERRADO y morfológico (no clasifica intención
# global, solo SEPARA el verbo del payload) -> stems multi-idioma para EXTRAER.
# Comillas: si el texto va entre comillas, se respeta literal.
_WRITE_VERB_STEM = re.compile(
    r"^\s*(?:"
    r"escrib[íie]\w*|tecle[áa]\w*|tipe[áa]\w*|digit[áa]\w*|"          # es
    r"type|write|enter|input|"                                        # en
    r"escrev[ae]\w*|digit[ae]\w*|"                                    # pt
    r"[ée]cri[st]\w*|tap[ae]\w*|"                                     # fr
    r"schreib\w*|tipp\w*|"                                            # de
    r"scriv[ie]\w*"                                                   # it
    r")\b[\s:]+",
    re.IGNORECASE,
)


def extract_write_payload(clause: str) -> str | None:
    """Si la cláusula es "<verbo-escribir> <texto>", devuelve <texto> (a tipear).
    None si no es una cláusula de escritura. ESTRUCTURAL: solo separa el verbo
    inicial del payload; la decisión de USARLO (contexto GUI presente) la toma el
    caller. Universal por los stems multi-idioma; el payload es lo que el usuario
    quiere teclear, en cualquier idioma."""
    if not clause or not clause.strip():
        return None
    m = _WRITE_VERB_STEM.match(clause)
    if not m:
        return None
    payload = clause[m.end():].strip()
    # quitar comillas envolventes si las hay
    if len(payload) >= 2 and payload[0] in "\"'«" and payload[-1] in "\"'»":
        payload = payload[1:-1].strip()
    return payload or None


# --- Extracción de TARGET de CLICK (Fase B computer-use) ---------------------
# Simétrico a la escritura: una cláusula "apretá/clickeá/tocá/seleccioná <botón>"
# en contexto GUI debe ir a la macro determinista click_button(label) — UIA find
# por Name + InvokePattern + verify — NO a que el 4B forme la llamada (medido
# flojo encadenando). El verbo de click es vocabulario CERRADO y morfológico
# (solo SEPARA verbo de label) -> stems multi-idioma. Universal.
_CLICK_VERB_STEM = re.compile(
    r"^\s*(?:"
    r"apret[áa]\w*|clicke[áa]\w*|click\w*|toc[áa]\w*|toca\w*|"            # es
    r"seleccion[áa]\w*|elegí|elige|elig[ée]\w*|presion[áa]\w*|"          # es
    r"click|press|tap|select|choose|hit|"                                # en
    r"clic\w*|aperte\w*|toqu\w*|selecion\w*|"                            # pt
    r"clique\w*|appuie\w*|s[ée]lectionne\w*|"                            # fr
    r"klick\w*|dr[üu]ck\w*|w[äa]hl\w*|"                                   # de
    r"clicc\w*|premi\w*|selezion\w*"                                      # it
    r")\b[\s:]+",
    re.IGNORECASE,
)

# Preposiciones/artículos que pueden quedar entre el verbo-click y el label en
# varios idiomas ("clickeá EN EL botón", "clique EM Enviar", "klick AUF OK").
# Se quitan del frente del label para que el Name UIA matchee. Closed set,
# multi-idioma; conservador (solo al principio del label).
_CLICK_LEAD = re.compile(
    r"^(?:"
    r"en\s+el|en\s+la|en|el|la|los|las|sobre|"      # es
    r"on\s+the|on|the|"                              # en
    r"em|no|na|"                                     # pt
    r"sur\s+le|sur|le|"                              # fr
    r"auf\s+das|auf\s+den|auf|"                      # de
    r"su|sul|sulla"                                  # it
    r")\s+",
    re.IGNORECASE,
)

# Palabras que indican que el "click" es sobre coordenadas/posición, no un
# control nombrado -> NO mandar a click_button (que busca por Name). Conservador.
_CLICK_POSITIONAL = re.compile(
    r"\b(?:aqu[íi]|ah[íi]|all[íi]|ac[áa]|here|there|esta?\s+posici[óo]n|"
    r"esquina|corner|centro|center|coordenada)\b", re.IGNORECASE)


# Teclas físicas: si el "target" de un click es una tecla (enter, tab, esc...),
# NO es un botón nombrado -> va a keypress, no a click_button. Vocabulario CERRADO
# de teclas (nombres físicos, no traducibles en su mayoría). El caller decide.
_KEY_NAMES = frozenset({
    "enter", "intro", "return", "tab", "esc", "escape", "space", "espacio",
    "backspace", "retroceso", "delete", "supr", "suprimir", "del",
    "arriba", "abajo", "izquierda", "derecha", "up", "down", "left", "right",
    "home", "end", "inicio", "fin", "pageup", "pagedown", "f1", "f2", "f3",
    "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
})


def is_key_name(label: str | None) -> bool:
    """True si `label` es el nombre de una tecla física (enter/tab/esc/...),
    no un control nombrado. El caller manda esto a keypress, no a click_button."""
    if not label:
        return False
    return label.strip().casefold() in _KEY_NAMES


def extract_click_target(clause: str) -> str | None:
    """Si la cláusula es "<verbo-click> <label>", devuelve <label> (botón a
    clickear por Name UIA). None si no es una cláusula de click, o si refiere a
    una posición/coordenada (eso es gui.click crudo, no click_button). ESTRUCTURAL:
    solo separa el verbo inicial del label; la decisión de USARLO (contexto GUI)
    la toma el caller. Universal por los stems multi-idioma."""
    if not clause or not clause.strip():
        return None
    m = _CLICK_VERB_STEM.match(clause)
    if not m:
        return None
    label = clause[m.end():].strip()
    if not label:
        return None
    # quitar preposición/artículo de enlace ("en el", "em", "auf"...).
    label = _CLICK_LEAD.sub("", label, count=1).strip()
    if not label:
        return None
    # click posicional ("clickeá ahí", "click aquí") -> no es por Name.
    if _CLICK_POSITIONAL.search(label):
        return None
    # quitar comillas envolventes y artículos/punto final residuales.
    if len(label) >= 2 and label[0] in "\"'«" and label[-1] in "\"'»":
        label = label[1:-1].strip()
    return label.strip(" .,;") or None


# --- NAVEGACIÓN-EN-APP (2026-05-25, validación Discord) ---------------------
# "entrá/andá/ve a [el servidor/canal/pestaña/sección] <TARGET> [de la app]" en una
# app YA abierta -> el TARGET es un control a clickear por Name UIA. El 4B no forma
# la llamada uia desde estos verbos ambiguos (medido: dice "no tengo herramienta"),
# así que el caller usa esto para sacar el TARGET y ejecutar click_button directo
# (macro determinista, patrón Agent-S2). Estructural + multi-idioma.
_NAV_VERB_STEM = re.compile(
    r"^\s*(?:"
    r"entr[áa]\w*|entra|and[áa]\w*|anda|naveg[áa]\w*|dirig[íi]te|"          # es
    r"abr[íi]\w*|abre|ve|"                                                  # es
    r"enter|go|navigate|open|"                                             # en
    r"vai|va|entre"                                                        # pt/it/fr
    r")\b"
    # preposición/dirección OPCIONAL tras el verbo ("entra A", "ve A", "go TO").
    r"(?:\s+(?:a|al|to|para|dans|au|in|nel|su|n[oa]))?"
    r"[\s:]+",
    re.IGNORECASE,
)
# Conectores que preceden al TARGET dentro de la app, multi-idioma. "al servidor X",
# "al canal X", "a la pestaña X", "a la sección X", "to the channel X". Se quitan
# para dejar solo el nombre del control. NO incluye el nombre de la app (ver abajo).
# Sustantivos-contenedor que preceden al TARGET ("[al] canal X", "[el] servidor X",
# "[la] pestaña X"). Multi-idioma. Se pelan CON o SIN preposición/artículo delante,
# porque _NAV_VERB_STEM ya consumió la preposición ("entra al" -> "canal X"). Se
# aplica REPETIDO (sub con loop) para encadenar "al servidor X" -> "X".
_NAV_CONTAINER = (
    r"servidor|canal|pestani?a|secci[óo]n|conversaci[óo]n|chat|grupo|"
    r"server|channel|tab|section|conversation|group|"
    r"servidor|canale|scheda|sezione|"
    r"serveur|cha[iî]ne|onglet"
)
_NAV_LEAD = re.compile(
    r"^(?:"
    # preposición/artículo de dirección, opcional.
    r"(?:a[l]?|to(?:\s+the)?|a\s+la|a\s+las|au|aux|no|na|nel|nella|al|su)\s+"
    r")?"
    # sustantivo-contenedor opcional (+ artículo opcional), seguido de espacio.
    r"(?:(?:el|la|los|las|the|le|il|lo)\s+)?(?:" + _NAV_CONTAINER + r")\b\s+",
    re.IGNORECASE,
)
# fallback: solo preposición/artículo de dirección sin contenedor ("a X", "to X").
_NAV_PREP_ONLY = re.compile(
    r"^(?:a[l]?|to(?:\s+the)?|a\s+la|a\s+las|au|aux|no|na|nel|nella|su)\s+",
    re.IGNORECASE,
)


def extract_nav_target(clause: str, *, app_hint: str = "") -> str | None:
    """Si la cláusula es "<verbo-nav> [app] [al servidor/canal] <TARGET>", devuelve
    <TARGET> (control a clickear por Name UIA dentro de la app abierta). None si no
    es navegación-en-app. ESTRUCTURAL: separa verbo + conectores + (opcional) el
    nombre de la app; el caller decide usarlo (app abierta confirmada por estado SO).

    app_hint: si se pasa el nombre de la app abierta (ej "Discord"), se quita del
    target para no confundir "entrá a Discord al servidor X" -> "X" (no "Discord X").
    """
    if not clause or not clause.strip():
        return None
    m = _NAV_VERB_STEM.match(clause)
    if not m:
        return None
    rest = clause[m.end():].strip()
    if not rest:
        return None
    # quitar el nombre de la app si aparece al principio ("Discord al servidor X").
    if app_hint:
        ah = app_hint.strip()
        # el hint puede ser un título de ventana ("Amigos - Discord"); usar sus
        # tokens significativos para pelar el nombre de app del frente del target.
        for tok in re.findall(r"\w+", ah.lower()):
            if len(tok) >= 4:
                rest = re.sub(r"^\s*" + re.escape(tok) + r"\b", "", rest,
                              count=1, flags=re.IGNORECASE).strip(" ,-:")
    # quitar conectores ("al servidor", "el canal", "a la pestaña"...) REPETIDO:
    # tras pelar la app puede quedar "al servidor X" -> "servidor X" -> "X".
    for _ in range(3):
        new = _NAV_LEAD.sub("", rest, count=1).strip()
        if new == rest:
            break
        rest = new
    # fallback: si quedó una preposición de dirección suelta ("a X", "to X").
    rest = _NAV_PREP_ONLY.sub("", rest, count=1).strip()
    if not rest:
        return None
    if len(rest) >= 2 and rest[0] in "\"'«" and rest[-1] in "\"'»":
        rest = rest[1:-1].strip()
    return rest.strip(" .,;") or None
