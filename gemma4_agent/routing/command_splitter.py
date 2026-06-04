"""Splitter de comandos multi-intent — MULTILINGÜE.

"abrí Spotify y bajá el volumen" son DOS acciones. Un 4B causal colapsa el
multi-intent (MIDLM, COLING 2025: la atención causal no maneja multi-intent como
un 7B bidireccional). La cura NO es agrandar el modelo: es partir el enunciado en
cláusulas ANTES de que el LLM lo vea y rutear cada una como su propio turno.

UNIVERSAL (la app la usa cualquier hablante; nada de regex es-only):
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

from .arithmetic import arith_expr_for_calc  # standalone (stdlib), sin ciclo

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
    # verbos de CLICK/INTERACCIÓN (computer-use): "apretá/clickeá/tocá/
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
    # escribí X y apretá enter"). Sin esta rama, la coma antes de la 1ra acción
    # dejaba dos acciones pegadas en una cláusula -> el 4B abría pero no tecleaba.
    # Requiere un VERBO imperativo tras la coma, así "sal, pimienta, azúcar"
    # (sustantivos) NO parte.
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

# Cap de cláusulas por misión. **VERIFICADO = 3**: cadenas de 2-3 pasos
# (abrir+escribir+enter) se midieron estables contra el SO real con falso-PASS
# 0%. El soporte del código llega a más, pero NO se afirma >3: las cadenas de
# 4-5 pasos no se pudieron verificar ESTABLES (la capa de tecleo del SO
# —SendKeys a apps recién abiertas— se degrada de forma no-determinista bajo
# carga). Mantener el cap en lo MEDIDO, no en lo aspiracional. >3 cláusulas =
# no partir (status quo: el LLM ve el comando entero).
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


# Disfluencias/muletillas INICIALES del habla (ruido del STT, NO comando): non-léxicas
# universales (eh/ah/um...) + repeat-markers ("dije,...") + wake-word/vocativo. Se quitan
# como RUIDO antes de partir (no deciden intención — igual que el wake-word). El `[\s,]+`
# separador y `(?=\S)`-implícito por el `+` evitan comer prefijos de palabras reales
# ('ahora' NO -> 'ah'+'ora'; 'umbral' NO -> 'um'+'bral'). EXCLUYE léxicas ambiguas
# (este/a ver/bueno) que pueden ser contenido ('este documento', 'a ver las tareas').
_LEADING_FILLER_RE = re.compile(
    r"^\s*(?:(?:eh+|ah+|oh+|um+|uh+|em+|ehm|mmm+|hmm+|aj[áa]|"        # non-léxicas
    r"dij[eo]|digo|"                                                  # repeat-markers
    r"hey\s+gemma|ok\s+gemma|che\s+gemma|gemma)"                      # wake-word/vocativo
    r"[\s,]+)+",
    re.IGNORECASE)


def split_command(utterance: str) -> list[str]:
    """Parte un enunciado en cláusulas de acción. Devuelve [utterance] si no hay
    multi-intent claro (caso normal). Nunca lanza.

    Capa 1 (español, rápida) primero; si no parte, capa 2 (multilingüe semántica)."""
    if not utterance or not utterance.strip():
        return [utterance]
    # Quitar disfluencias/muletillas INICIALES (ruido del STT, NO comando) antes de
    # partir. Sin esto, "Eh, pon una canción" -> ['Eh','pon una canción'] y la
    # cláusula 'Eh' generaba un reply junk ("listo, cancelo") que se concatenaba.
    # Se quitan como RUIDO (igual que el wake-word), no deciden intención.
    _clean = _LEADING_FILLER_RE.sub("", utterance).strip()
    if _clean:
        utterance = _clean
    # CAPA 1: regex español (exacta, barata, ya validada).
    parts = [p.strip(" ,.;") for p in _SPLIT_RE.split(utterance) if p and p.strip(" ,.;")]
    if len(parts) > 1:
        # NO PARTIR cuando la 1ra cláusula es un "ir/entrar a <app>" puro: es un
        # PREFIJO DE CONTEXTO de lo que sigue, no una acción aparte. Bug que cura:
        # "Ve a discord y pon el chat de cbayeah" se partía en
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


# "abrilo/lanzalo/abrí eso/open it": ABRIR (lanzar) el REFERENTE de la cláusula
# previa. Verbo de apertura/lanzamiento + (clítico/pronombre opcional), SIN target
# explícito (si hay target propio como "abrí el bloc" NO matchea -> es su propia
# acción). Cura el encadenamiento dependiente "instalá VLC Y ABRILO": sin esto,
# 'abrilo' leakeaba como texto porque package no está en el carry GUI.
_DEP_OPEN_RE = re.compile(
    r"^\s*(?:abr[íia]\w*|abrir|abre|lanz[áa]\w*|ejecut[áa]\w*|corr[ée]\w*|"   # es
    r"open|launch|run|start|"                                                  # en
    r"abra|abrí\w*|lance\w*|"                                                  # pt
    r"ouvre\w*|lance\w*|[öo]ffne\w*|apri\w*|avvia\w*)"                          # fr/de/it
    r"\s*(?:lo|la|los|las|le|eso|esa|esto|aquello|it|that|them|"
    r"el\s+programa|la\s+app|the\s+app)?\s*$",
    re.IGNORECASE)


def is_dependent_open(clause: str) -> bool:
    """True si la cláusula es un 'abrilo/lanzalo/abrí eso' BARE: abrir/lanzar el
    REFERENTE de la cláusula previa (sin target explícito). El caller resuelve el
    referente al target de la cláusula anterior."""
    return bool(clause and _DEP_OPEN_RE.match(clause.strip()))


# OPEN PELADO de una app: "abrí la calculadora", "abrí discord". MEDIDO: el
# router/4B NO rutea ciertos nombres a app.open de forma CONSISTENTE ("abrí la
# calculadora"/"abrí discord" -> NADA 3/3, pero "abrí spotify" -> app 3/3). La
# tool app.open SÍ resuelve todos (calc.exe etc.). Detector
# estructural -> el caller INTENTA app.open(nombre); si resuelve a una app, listo;
# si no (carpeta/URL/chat), cae al flujo normal (la tool es la guarda de precisión).
# SOLO verbos de ABRIR-APP. NO "ejecutar/run/start": "ejecuta pytest"/"run pytest"
# es un COMANDO (terminal), no abrir-app — incluirlos hacía que el short-circuit
# secuestrara 42 comandos shell del dataset y, peor, "ejecuta pytest" caía al
# fallback web de app.open (pytest→pytest.org) y MENTÍA "Listo, abrí pytest" (BUG
# real medido eval run2, 2026-06-04). "ejecutar X" llega ahora al router+LLM, que
# ya ofrecen terminal/developer y desambiguan bien (verificado en vivo). El único
# "ejecuta <app>" del dataset (taskkill) ya cae por _NON_APP_MARK (tiene '/').
_APP_OPEN_VERB = re.compile(
    r"^\s*(?:abr[íi]\w*|abre|abrir|abrime|lanz[áa]\w*|"                           # es
    r"open|launch|"                                                               # en
    r"abra|ouvre|lance|[öo]ffne|starte|apri|avvia)\s+",                           # pt/fr/de/it
    re.IGNORECASE)
# marcadores de NO-app: chat/canal (in-app), carpeta (filesystem), URL/sitio (browser).
_NON_APP_MARK = re.compile(
    r"\b(?:chat|canal|conversaci[óo]n|grupo|carpeta|folder|directorio|"
    r"p[áa]gina|sitio|website|http|www)\b|[/@]|\.\w{2,4}\b",
    re.IGNORECASE)
_OPEN_LEAD_ART = re.compile(r"^(?:el|la|los|las|the|un|una|mi|le|les|der|die|das|il|lo)\s+",
                            re.IGNORECASE)


def extract_app_open(clause: str) -> str | None:
    """Si la cláusula es "abrí/abre/open <app>" (open PELADO de una app, nombre corto,
    sin acción ni marcadores de chat/carpeta/URL), devuelve el nombre de la app (sin
    artículo). None si no. El caller intenta app.open(nombre) y SOLO se queda con el
    resultado si la tool resolvió a una app real (si no, sigue el flujo normal)."""
    if not clause or not clause.strip():
        return None
    c = clause.strip()
    m = _APP_OPEN_VERB.match(c)
    if not m:
        return None
    rest = c[m.end():].strip(" .,:;\"'«»")
    if not rest or len(rest.split()) > 4:        # nombre de app corto
        return None
    if _NON_APP_MARK.search(rest):               # chat/carpeta/URL -> no es app.open
        return None
    rest = _OPEN_LEAD_ART.sub("", rest).strip()
    return rest or None


def plan_clauses(utterance: str) -> list[dict]:
    """Devuelve [{text, depends_on_prev}] por cláusula. depends_on_prev=True =>
    ejecutar serializado (el resultado de la anterior alimenta esta)."""
    clauses = split_command(utterance)
    return [{"text": c, "depends_on_prev": i > 0 and has_back_reference(c)}
            for i, c in enumerate(clauses)]


# --- Extracción de payload de ESCRITURA (computer-use) -----------------------
# Una cláusula "escribí/tecleá/type <texto>" en un contexto GUI debe ir a la
# macro determinista type_into, NO a que el 4B forme la llamada. El verbo de
# escritura inicial es vocabulario CERRADO y morfológico (no clasifica intención
# global, solo SEPARA el verbo del payload) -> stems multi-idioma para EXTRAER.
# Comillas: si el texto va entre comillas, se respeta literal.
_WRITE_VERB_STEM = re.compile(
    r"^\s*(?:"
    r"escr[íi]b\w*|tecle[áa]\w*|tipe[áa]\w*|digit[áa]\w*|"          # es
    r"type|write|enter|input|"                                        # en
    r"escrev[ae]\w*|digit[ae]\w*|"                                    # pt
    r"[ée]cri[st]\w*|tap[ae]\w*|"                                     # fr
    r"schreib\w*|tipp\w*|"                                            # de
    r"scriv[ie]\w*"                                                   # it
    r")\b[\s:]+",
    re.IGNORECASE,
)


# --- Extracción de MENSAJE-A-CONTACTO (computer-use en apps de chat) ----------
# "escribe/mandale/decile A <contacto> [en <app>] [y dile/que] <mensaje>". A
# diferencia de extract_nav_target (que solo ABRE un chat), esto separa el
# CONTACTO del MENSAJE para enviar. Verbo de envío + "a <contacto>" + (opcional
# "en <app>") + (conector "y dile/decile/que/:") + mensaje. Estructural y
# multi-idioma (stems); el caller confirma por estado del SO (app abierta).
_MSG_VERB_STEM = re.compile(
    r"^\s*(?:"
    r"escr[íi]b\w*|mand[áa]\w*|manda\w*|m[áa]ndale|mandale|decil[ée]?|"   # es
    r"dile|dec[íi]\w*|envi[áa]\w*|envia\w*|"                                # es
    r"respond[ée]\w*|respondele|contest[áae]\w*|contestale|"               # es (responder)
    r"write|send|message|msg|text|tell|repl(?:y|ies|ied)|answer|"          # en (+reply/answer)
    r"escrev[ae]\w*|mand[ae]\w*|envi[ae]\w*|respond[ae]\w*|"               # pt
    r"[ée]cri[st]\w*|envoie\w*|r[ée]ponds?\w*|"                            # fr (répondre)
    r"schreib\w*|schick\w*|antworte\w*|"                                    # de (antworten)
    r"scriv[ie]\w*|invia\w*|rispondi\w*"                                    # it (rispondere)
    r")\b",
    re.IGNORECASE,
)
# conector que separa el (contacto [en app]) del MENSAJE. El cuerpo arranca tras
# un conector explícito de "decir": "y dile que", "decile", "diciendo", "and tell
# them", ":" ... NO incluye un "que" suelto (ambiguo). Multi-idioma.
# NOTA sobre "que": en español "dile QUE haces" -> el mensaje es "que haces" (=
# "¿qué hacés?"). Quitar "que" cambiaría el sentido. Por eso el lead consume el
# verbo de decir (y la conjunción previa) pero NO el "que" siguiente: queda en el
# mensaje. Solo ":" como conector explícito sí se consume entero.
_MSG_BODY_LEAD = re.compile(
    r"(?:^|\s)(?:"
    r"(?:y\s+|e\s+|and\s+|et\s+|und\s+)?"
    r"(?:d[ií]gan?le|d[ií]le|dec[íi]le|tell\s+(?:him|her|them)|"
    r"sag\s+(?:ihm|ihr|ihnen)|dis[\s-]?lui|dici[ée]ndo(?:le)?|saying)"
    r"|:\s*)\s*",
    re.IGNORECASE,
)
# "en <app>" al final del contacto, para pelarlo. App = una palabra (no frase).
_MSG_APP_TAIL = re.compile(
    r"\s+(?:en|in|on|im|su|no|dans)\s+\w+\s*$", re.IGNORECASE)
# Apps de MENSAJERÍA con UI propia (set cerrado y finito + fonéticas de Whisper).
# Solo se usan para decidir si pelar un "en <app>" residual del CUERPO de un
# mensaje (no para routing). Cerrado = seguro: no toca palabras comunes ("casa",
# "bar", "10 minutos"). Incluye WhatsApp porque "a Ana en WhatsApp que ..." cae
# en el mismo PASO 1-fallback.
_MSG_KNOWN_APP_RE = re.compile(
    r"(?:whatsapp|wsp|wpp|wasap|guasap|discord|telegram|slack|teams|signal|"
    r"messenger|instagram|insta|skype|sms)",
    re.IGNORECASE)


def extract_message_to(clause: str, *, app_hint: str = "") -> tuple[str, str] | None:
    """Si la cláusula es "escribe/mandale a <CONTACTO> [en <app>] [y dile/que]
    <MENSAJE>", devuelve (contacto, mensaje). None si no es un envío-de-mensaje.
    El mensaje puede venir vacío (solo "escribe a X") -> mensaje "". ESTRUCTURAL:
    separa verbo + 'a <contacto>' + ('en <app>') + conector + mensaje. El caller
    confirma por estado del SO (app abierta) y ejecuta el cómo (quick-switcher +
    type + Enter). app_hint quita el nombre de app del contacto si se coló.

    Ejemplos:
      "escribe a cbayeah en discord y dile que haces" -> ("cbayeah", "que haces")
      "mandale a juan en discord: nos vemos"          -> ("juan", "nos vemos")
      "decile a GordoFriki que llego tarde"           -> ("GordoFriki", "llego tarde")
    """
    if not clause or not clause.strip():
        return None
    m = _MSG_VERB_STEM.match(clause)
    if not m:
        return None
    rest = clause[m.end():].strip(" ,:")
    # "a <contacto>" — la preposición de destinatario es OBLIGATORIA: separa un
    # ENVÍO-A-ALGUIEN ("escribe A juan ...") de un tecleo-en-app ("escribí 2+2",
    # "escribí hola mundo" en la calc/notepad, que NO llevan "a <persona>"). Sin la
    # preposición de destinatario NO es un mensaje -> None (lo maneja el flujo de
    # escritura-en-app, no el de mensajería). Evita mis-parsear "escribí 2+2" como
    # "mandar 2+2 al contacto ''". (Verbos como mandale/decile YA implican
    # destinatario aunque no repitan "a": ese caso se cubre abajo.)
    _verb = clause[m.start():m.end()].strip().lower()
    # ¿El verbo IMPLICA un destinatario que sigue (y por eso puede omitir el "a
    # <quién>")? SOLO si lleva el CLÍTICO DATIVO es/pt "-le/-les" sobre una raíz
    # de ENVIAR/DECIR/ESCRIBIR (mandaLE, deciLE, diLE, escribiLE, envíaLE) o es un
    # verbo en/persona-directa (tell/text/message/msg). Los imperativos PELADOS
    # multi-idioma (manda, envía, escribí, decí, send, write, schick, envoie,
    # invia) NO implican destinatario: exigen un "a/to/para/à/an <quién>"
    # explícito. Mide la FORMA (morfología), no listas de nombres.
    #
    # BUG QUE ESTO CURA: "manda un mensaje por wsp" (SIN destinatario) — el stem
    # pelado `mand` hacía implies=True, no
    # exigía "a", y el PASO 3 agarraba el 1er token "un" (artículo) como contacto
    # -> "Abrí el chat con un". Mismo bug-class en de/fr/it ("schick eine
    # nachricht"). Ahora sin clítico ni "a" -> None -> el LLM pregunta a quién.
    #
    # Excluye los verbos de RESPUESTA (respondeLE/contestaLE): tienen "-le" pero
    # su destinatario es el ÚLTIMO que escribió, no uno que sigue en el texto; el
    # flujo de reply-a-último los maneja (y este extractor debe devolver None).
    _verb_implies_recipient = bool(
        (re.search(r"(?:le|les)$", _verb)
         and re.match(r"(?:m[áa]nd|mand|dec|d[íi]|escr[íi]b|env[íi])", _verb))
        or re.match(r"(?:tell|text|message|msg)\b", _verb))
    m_to = re.match(r"^(?:a|al|to|para|à|an)\s+", rest, flags=re.IGNORECASE)
    if m_to:
        rest = rest[m_to.end():].strip()
    elif not _verb_implies_recipient:
        # "escribe/write/type X" SIN "a" y sin verbo-de-mensajería -> tecleo, no msg.
        return None
    if not rest:
        return None
    # PASO 1: separar el cuerpo por el conector explícito ("y dile que", ":", ...),
    # ANTES de tocar "en app" (así "...y dile que haces" deja body="que haces").
    contact, body = rest, ""
    mb = _MSG_BODY_LEAD.search(rest)
    if mb and mb.start() > 0:
        contact = rest[:mb.start()].strip(" ,:")
        body = rest[mb.end():].strip(" ,:")
    else:
        # Fallback "que/that": DESPUÉS de "a <contacto>", un "que" suelto SÍ marca
        # el inicio del cuerpo de forma fiable ("a juan QUE llego en 10" -> contacto
        # juan, body "que llego en 10"). Acá ya consumimos la preposición de
        # destinatario, así que no hay la ambigüedad del "que" general. PRESERVAMOS
        # el "que" en el cuerpo (comportamiento histórico: "que" cambia el sentido).
        # Esto evita que el separador "en <app>" mal-lea "en 10 minutos" como app=10.
        mq = re.search(r"\s+(?:que|that|qu[ei]|dass|che)\s+", contact, flags=re.IGNORECASE)
        if mq and mq.start() > 0:
            contact, body = contact[:mq.start()].strip(" ,:"), contact[mq.start():].strip(" ,:")
    # PASO 2: en lo que quedó como "contacto", separar "en <app> [mensaje]". Tras
    # "en <app>" puede venir DIRECTAMENTE el mensaje sin conector ("a cbayeah en
    # discord hola" -> contacto=cbayeah, body=hola). Capturamos app y resto.
    mapp = re.search(r"\s+(?:en|in|on|im|su|no|dans)\s+(\w+)\b\s*(.*)$",
                     contact, flags=re.IGNORECASE)
    if mapp:
        tail = mapp.group(2).strip(" ,:")        # lo que sigue al nombre de app
        contact = contact[:mapp.start()].strip(" ,:")
        if tail and not body:                    # mensaje pegado tras "en app"
            body = tail
    # PASO 2b: el "en <app>" puede haber quedado al FINAL del CUERPO, no del
    # contacto, cuando el "que" precede al "en app" ("a Juan QUE voy ... EN
    # Discord" -> PASO 1 dejó body="que voy ... en Discord"). Pelarlo del body
    # SOLO si la última palabra es una APP DE MENSAJERÍA conocida — distingue
    # "en Discord" (app) de "en casa"/"en 10 minutos" (lugar/tiempo legítimos del
    # mensaje). MEDIDO: el pelado ciego rompía "te espero en casa"->"te espero"
    # y AppResol(fuzzy) matcheaba "casa" como app (CLAUDE.md: medí, no celebré).
    # Las apps de mensajería son un set CERRADO y finito -> cobertura segura,
    # multi-idioma, sin tocar palabras comunes. (Si la app está en el app_hint
    # del SO, también vale.)
    if body:
        mtail = _MSG_APP_TAIL.search(body)
        if mtail:
            tail_word = re.findall(r"\w+", mtail.group(0))[-1].lower()  # palabra tras "en"
            _is_app = bool(_MSG_KNOWN_APP_RE.fullmatch(tail_word)) or (
                bool(app_hint) and tail_word in app_hint.lower())
            if _is_app:
                body = _MSG_APP_TAIL.sub("", body).strip(" ,:")
    # PASO 3 (fallback): si NO hubo conector ni "en app" y el contacto tiene varias
    # palabras, la 1ª es el contacto y el resto el mensaje ("CbaYeah hola como va",
    # "juan hola"). Conservador: el contacto suele ser UNA palabra (handle/nombre).
    if not body and " " in contact:
        first, rest2 = contact.split(" ", 1)
        contact, body = first, rest2.strip()
    # pelar SOLO el nombre de la APP del contacto (no cualquier token del título).
    # El app_hint puede ser un título "@CbaYeah - Discord" cuyo PRIMER segmento es el
    # chat activo (= puede ser el propio contacto) y el ÚLTIMO es la app ("Discord").
    # Pelar todos los tokens borraría el contacto. Usamos solo el último segmento.
    if app_hint:
        app_seg = app_hint.split(" - ")[-1]
        for tok in re.findall(r"\w+", app_seg.lower()):
            if len(tok) >= 4:
                contact = re.sub(r"\b" + re.escape(tok) + r"\b", "", contact,
                                 flags=re.IGNORECASE).strip(" ,:")
    contact = contact.strip(" ,:\"'«»")
    body = body.strip(" \"'«»")
    if not contact or len(contact) < 2:
        return None
    return (contact, body)


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


# --- Detección de ACCIÓN-EN-APP / META para el orquestador computer_use -------
# ACCESIBILIDAD (núcleo del producto): el usuario dicta y el agente debe ACTUAR en
# una app/pantalla — escribir, clickear, o "andá a X y hacé Y". MEDIDO: estos
# pedidos casi NUNCA llegaban a computer_use — el 4B charlaba
# ("escribí sigue en claude code"→"Sigo en Claude Code"), respondía la pregunta
# ("en claude code escribí quién eres"→la contestaba), o el router los mandaba a
# notes_tasks/local_search/browser/whatsapp/nada. Solo ~1/10 llegaba al orquestador.
# Este detector ESTRUCTURAL (gramática multi-idioma, NO listas de apps ni de
# intenciones) reconoce la FORMA "acción dirigida a una app". NO es un macro
# por-intención: es UNA capa que detecta la forma; el orquestador resuelve el QUÉ
# universalmente. La PRECISIÓN de los casos ambiguos ("escribí X en <Y>") la cierra
# el caller verificando por ESTADO DEL SO que <Y> sea una app/ventana real (así
# 'anotá la reunión en mi lista' NO se hijackea -> sigue yendo a notes).
#
# Verbos de ACCIÓN-EN-APP: tipear/clickear/poner/hacer-en. Excluye a propósito
# buscar/reproducir/abrir-simple (tienen tools dedicadas: web/media/app que andan).
_AA_ACT = (
    r"escr[íi]b\w*|tecle[áa]\w*|tipe[áa]\w*|digit[áa]\w*|"             # es escribir
    r"pon[ée]\w*|col[oó]c\w*|met[ée]\w*|"                                 # es poner
    r"clicke[áa]\w*|click\w*|apret[áa]\w*|toc[áa]\w*|"                    # es click
    r"seleccion[áa]\w*|presion[áa]\w*|marc[áa]\w*|"                       # es click2
    r"type|write|input|enter|put|click|press|tap|select|check|"          # en
    r"escrev\w*|clic\w*|"                                                 # pt
    r"[ée]cri\w*|clique\w*|"                                              # fr
    r"schreib\w*|tipp\w*|klick\w*|"                                       # de
    r"scriv\w*|clicc\w*|premi\w*"                                         # it
)
# Verbos de NAVEGACIÓN a una app/sitio (para "andá a X y <acción> Y").
_AA_NAV = (
    r"ve|and[áa]|anda|abr[íi]|abre|abrir|entr[áa]|entra|llev[áa]me|"      # es
    r"go|open|navigate|head|launch|"                                     # en
    r"abra|v[áa]|entre|ouvre|va|[öo]ffne|geh|apri|vai"                   # pt/fr/de/it
)
_AA_CONN = (r"y|e|and|then|luego|despu[ée]s|after|et|puis|und|dann|poi|o")
_AA_PREP = (r"a|al|to|para|en|in|into|on|n[oa]|su|the|im|dans")

# A: "andá a <X> y <acción> ..." (nav + acción). El contexto nav+conector garantiza
# una META de computadora; la acción admite verbos IN-APP INEQUÍVOCOS: tipear,
# clickear, guardar/cerrar/borrar. NO incluye mandar/buscar/reproducir (solapan con
# whatsapp/web/media), NI poné/colocá/metá/put (AMBIGUOS: 'abrí Spotify y poné rock'
# = PLAY=media, no tipear — MEDIDO que el inherit los mandaba a type).
# Conjunto CURADO explícito (no hereda _AA_ACT, que sí trae poné para el caso
# 'poné X en notepad' donde el 'en notepad' lo desambigua).
_AA_ACT_NAV = (
    r"escr[íi]b\w*|tecle[áa]\w*|tipe[áa]\w*|digit[áa]\w*|type|write|input|"        # tipear
    r"clicke[áa]\w*|click\w*|apret[áa]\w*|toc[áa]\w*|seleccion[áa]\w*|presion[áa]\w*|"  # click es
    r"press|tap|select|clic\w*|clique\w*|klick\w*|clicc\w*|premi\w*|"             # click otros
    r"cerr[áa]\w*|guard[áa]\w*|borr[áa]\w*|elimin[áa]\w*|close|save|delete")       # in-app
_AA_NAV_ACTION = re.compile(
    r"\b(?:" + _AA_NAV + r")\b\s+(?:" + _AA_PREP + r")?\s*\S+.*?"
    r"\s+(?:" + _AA_CONN + r")\s+(?:luego\s+|despu[ée]s\s+|then\s+)?"
    r"(?:" + _AA_ACT_NAV + r")\b", re.IGNORECASE)
# A2: "<nav> a <dest> en <app>" — navegar a un DESTINO dentro de una app NOMBRADA
# ('ve a Cotele en Discord', 'entrá al canal general en Discord', 'abrí la playlist X
# en Spotify'). MEDIDO: "Ve a Cotele en Discord" no llegaba a
# computer_use (ve=nav, sin verbo de acción ni 2da cláusula -> extract_app_action=None
# -> el 4B no emitía tool -> "No alcancé a completar"). El orquestador hace
# focus_app(app)+open_chat(dest). verify_app gatea (la app debe ser real). EXCLUYE
# navegadores: 've a github en Opera' tiene tool dedicada (browser.open con target).
_BROWSER_APP_RE = re.compile(
    r"^(?:el\s+|la\s+|mi\s+)?(?:navegador|browser|chrome|opera(?:\s*gx)?|firefox|"
    r"edge|safari|brave|chromium|explorer|naveg\w*)\b", re.IGNORECASE)
_AA_NAV_IN_APP = re.compile(
    r"^\s*(?:" + _AA_NAV + r")\b\s+(?:(?:a|al|hacia|to|into|para|hasta)\s+)?"
    r"(?P<dest>.+?)\s+(?:en|in|into|dentro\s+de|dans|im|su)\s+(?P<app>\S.*)$",
    re.IGNORECASE)
# B: "<acción> <payload> en|a <app>" — ambiguo -> verify_app. Incluye "a" (caso
# real "escribile sigue A claude code") pero SIEMPRE gateado por el OS-check del
# caller: 'escribile a juan' -> app_hint='juan' no es ventana -> NO dispara cu
# (sigue a whatsapp). Solo 'a <app-abierta>' rutea al orquestador.
_AA_ACT_IN_APP = re.compile(
    r"\b(?:" + _AA_ACT + r")\b.*?\s+(?:en|in|into|on|sobre|dentro\s+de|dans|im|su|no|a|al)\s+(?P<app>.+)$",
    re.IGNORECASE)
# B2: "en <app> <acción> ..." (app primero) — ambiguo -> verify_app.
_AA_IN_APP_ACT = re.compile(
    r"^\s*(?:en|in|into|on|dentro\s+de|dans|im|su|no)\s+(?P<app>.+?)\s+(?:" + _AA_ACT + r")\b",
    re.IGNORECASE)
# C: acción de PANTALLA explícita (screenshot). Alta precisión, sin app.
_AA_SCREEN = re.compile(
    r"\b(?:captura(?:r|me)?(?:\s+de)?\s+(?:pantalla|la\s+pantalla)|screenshot|"
    r"screen\s*shot|print\s*screen|pantallazo|"
    r"saca\w*\s+(?:una\s+|me\s+)?(?:foto|captura)\s+(?:de\s+)?(?:la\s+)?pantalla)\b",
    re.IGNORECASE)
# Vocativo/wake-word inicial: "gemma, ...", "hey gemma ...", "ok gemma ...". (?=\S)
# exige contenido después (no vacía "gemma" solo).
_re_strip_wake = re.compile(r"^(?:hey\s+|ok\s+|oye\s+|che\s+)?gemma[\s,]+(?=\S)", re.IGNORECASE)


def extract_app_action(clause: str) -> dict | None:
    """Si la cláusula es una ACCIÓN-EN-APP/META para el orquestador computer_use,
    devuelve {goal, app_hint, verify_app, pattern}; None si no. ESTRUCTURAL
    (gramática, no contenido/listas). `verify_app=True` => el caller DEBE confirmar
    por estado del SO que `app_hint` es una app/ventana real antes de rutear (cura
    de precisión: 'poné X en mi lista' no es computer_use). Ver comentario de bloque."""
    if not clause or not clause.strip():
        return None
    c = clause.strip()
    # quitar el vocativo/wake-word inicial ("gemma, ...") — el user lo antepone seguido
    # (MEDIDO: "gemma Ve a Cotele en Discord", "gemma Suma 2+2"). Es el nombre del
    # asistente, seguro de quitar; el `^...(?=\S)` evita vaciar la cláusula.
    _wo_wake = _re_strip_wake.sub("", c)
    if _wo_wake:
        c = _wo_wake
    if _AA_SCREEN.search(c):
        return {"goal": c, "app_hint": None, "verify_app": False, "pattern": "screen"}
    if _AA_NAV_ACTION.search(c):
        return {"goal": c, "app_hint": None, "verify_app": False, "pattern": "nav_action"}
    m = _AA_NAV_IN_APP.search(c)
    if m:
        _nav_app = m.group("app").strip(" .,:\"'«»")
        # navegadores tienen tool dedicada (browser.open por nombre/target) -> no cu.
        if _nav_app and not _BROWSER_APP_RE.match(_nav_app):
            return {"goal": c, "app_hint": _nav_app,
                    "verify_app": True, "pattern": "nav_in_app"}
    m = _AA_IN_APP_ACT.search(c)
    if m:
        return {"goal": c, "app_hint": m.group("app").strip(" .,:\"'«»"),
                "verify_app": True, "pattern": "in_app_act"}
    m = _AA_ACT_IN_APP.search(c)
    if m:
        return {"goal": c, "app_hint": m.group("app").strip(" .,:\"'«»"),
                "verify_app": True, "pattern": "act_in_app"}
    return None


# Operación aritmética EN LA CALCULADORA: "suma 2+2 en la calculadora", "en la calc
# hacé 5*3", "calculá 10/2 con la calculadora", "Suma dos más dos en la Calculadora".
# MEDIDO: el 4B tipeaba `gui.type("2+2")` SIN enfocar la Calc -> el sendinput iba a
# la ventana equivocada (reporta ok:True igual) -> el verifier no encontraba "2+2"
# en la Calc ("type failed") -> el agente REINTENTABA idéntico 4 veces ("4 no
# confirmadas" + 18s). Fix: detectar [app calculadora + expresión aritmética pura]
# y devolver {'expr': '2+2'} para que el caller arme el plan DETERMINISTA
# [focus_app(calc), type(expr), keypress(enter)] (abre/enfoca ANTES de tipear).
# ESTRUCTURAL (gramática + aritmética, NO listas de intenciones).
_CALC_APP_RE = re.compile(
    r"\b(?:calculadora|calculator|calcolatrice|calculatrice|rechner|kalkulator|calc)\b",
    re.IGNORECASE)


def parse_calc_action(clause: str) -> dict | None:
    """Si la cláusula pide una operación aritmética EN LA CALCULADORA, devuelve
    {'expr': '<expresión compacta a tipear>'}; None si no. Requiere AMBOS: mención de
    la app calculadora Y que el resto reduzca a aritmética pura (alta precisión: 'abrí
    la calculadora' sola -> None; 'anotá la cuenta en la calculadora que diga X' -> None)."""
    if not clause or not clause.strip():
        return None
    if not _CALC_APP_RE.search(clause):
        return None
    # quitar la mención de la app ("en la calculadora", "con la calc", "la calculadora")
    txt = re.sub(
        r"\b(?:en|con|usando|using|in|im|dans|na|sobre|use|usa|abr[íi]\w*|abre|open|"
        r"desde|from)\s+(?:la|el|the|mi|tu|una?|der|die|das)?\s*"
        r"(?:calculadora|calculator|calcolatrice|calculatrice|rechner|kalkulator|calc)\b",
        " ", clause, flags=re.IGNORECASE)
    txt = _CALC_APP_RE.sub(" ", txt)   # cualquier mención residual de la app
    expr = arith_expr_for_calc(txt)
    if not expr:
        return None
    return {"expr": expr}


# Verbos de MOVIMIENTO a un destino DENTRO de una app (NO 'abrí/abre/open' = app-open
# AMBIGUO). Para el chain-context: "abrí Discord y ANDÁ AL canal X" -> la 2da cláusula
# navega DENTRO de la app abierta por la 1ra; sola, el 4B la PIERDE (charla).
_BARE_NAV_VERB = (
    r"and[áa]|anda|entr[áa]|entra|ve|vamos|vam[oó]nos|llev[áa]me|"          # es
    r"naveg[áa]|navega|and[áa]te|"
    r"go|navigate|head|switch|"                                            # en
    r"v[áa]|entre|va|vai|geh"                                              # pt/fr/de/it
)
_BARE_INAPP_NAV = re.compile(
    r"^\s*(?:" + _BARE_NAV_VERB + r")\b\s+(?:a|al|hacia|to|into|en|para)\s+\S+",
    re.IGNORECASE)


def is_bare_inapp_nav(clause: str) -> bool:
    """True si la cláusula es una NAVEGACIÓN pelada a un destino ('andá al canal X',
    've a la playlist Y', 'entrá a la pestaña Z'). Para el chain-context: navegar
    DENTRO de la app que abrió la cláusula previa. Excluye 'abrí/abre/open' (ambiguo
    con abrir-app) y los verbos de tipeo/click/envío (manejados por sus macros
    ANTES en _run_multi_intent). ESTRUCTURAL, multi-idioma. El caller la gatea por
    carry_window (solo aplica mid-chain) y rutea a cu(goal + 'en <app>')."""
    if not clause or not clause.strip():
        return False
    return bool(_BARE_INAPP_NAV.match(clause.strip()))


# Pedido de LEER/MOSTRAR lo que hay EN PANTALLA. Para el chain-context: tras navegar
# a una PÁGINA (browser), "mostrame/leeme/ve las tareas" debe LEER la pantalla por
# visión, NO la tool LOCAL (notes_tasks). Caso de referencia: "entrá a Canvas y
# MOSTRAME las tareas que debo hacer". Verbos VISUALES (mostrar/leer/mirar/ver), NO
# 'decime/dime' (ambiguo: "decime qué hora es" no es leer-pantalla).
_READ_SCREEN_RE = re.compile(
    r"^\s*(?:mostr[áa]\w*|mu[ée]str\w*|mostrame|"          # mostrame/muestra
    r"le[ée]me|leeme|le[ée]\b|leer\b|"                     # leeme/leé/leer
    r"mir[áa]\w*|mira\b|f[íi]jate|fijate|"                 # mirá/fijate
    r"ve\b|v[ée]\b|"                                       # ve/vé (mirar; 've a X'=nav lo agarra antes)
    r"show(?:\s+me)?|read)\b\s+\S+",
    re.IGNORECASE)


def is_read_screen_request(clause: str) -> bool:
    """True si la cláusula pide LEER/MOSTRAR lo que hay EN PANTALLA ('mostrame las
    tareas', 'leeme lo que dice', 've las tareas'). Para el chain-context: tras navegar
    a una página/app, leer su CONTENIDO por VISIÓN, no una tool local (notes_tasks).
    El caller la gatea por carry de navegación web (browser). ESTRUCTURAL. 've a X' (nav)
    lo agarra is_bare_inapp_nav ANTES; acá 've <sustantivo>' = mirar. Excluye 'decime/
    dime' (ambiguo). Ej: 'entrá a Canvas y mostrame las tareas'."""
    if not clause or not clause.strip():
        return False
    if is_bare_inapp_nav(clause):  # "ve a X" = NAVEGAR (otro macro), no leer-pantalla
        return False
    return bool(_READ_SCREEN_RE.match(clause.strip()))


# Verbos de TIPEO (subconjunto de _AA_ACT: solo escribir/teclear/poner, NO click).
# Para construir un PLAN DETERMINISTA focus_app+type sin depender del 4B planner
# (que a veces devuelve plan vacío o mete toda la frase como texto — MEDIDO).
_AA_TYPE_VERB = re.compile(
    r"(?:escr[íi]b\w*|tecle[áa]\w*|tipe[áa]\w*|digit[áa]\w*|"
    r"pon[ée]\w*|col[oó]c\w*|met[ée]\w*|"
    r"type|write|input|enter|put|"
    r"escrev\w*|[ée]cri\w*|schreib\w*|tipp\w*|scriv\w*)", re.IGNORECASE)
# Localizadores preferidos (en/in/on...) y de respaldo (a/al). "a" es ambiguo
# ("a las 5") -> se prueba SOLO si no hay un "en". 2 pasadas.
_AA_LOC_PREF = r"en|in|into|on|sobre|dentro\s+de|dans|im|su"
_AA_NAV_RE = re.compile(r"\b(?:" + _AA_NAV + r")\b\s+(?:" + _AA_PREP + r")?\s*", re.IGNORECASE)
_AA_CONN_RE = re.compile(r"\s+(?:" + _AA_CONN + r")\s+(?:luego\s+|despu[ée]s\s+|then\s+)?", re.IGNORECASE)


def _strip_quotes(s: str) -> str:
    s = (s or "").strip(" .,:;\"'«»")
    return s


def parse_type_action(clause: str) -> dict | None:
    """Extrae {app, payload} de un pedido de TIPEO-EN-APP para construir un plan
    DETERMINISTA focus_app(app)+type(payload). None si no es un type-action limpio
    (el caller cae al planner del 4B). ESTRUCTURAL, multi-idioma. Cubre:
      "escribí X en/a APP", "en APP escribí X", "andá a APP y escribí X".
    Dos pasadas para el localizador (prefiere 'en' sobre 'a' -> 'poné R a las 5 en
    notepad' = payload 'R a las 5', app 'notepad', no 'las 5')."""
    if not clause or not clause.strip():
        return None
    c = clause.strip()
    # 1) NAV + TYPE: "andá a APP y escribí X"
    nav = _AA_NAV_RE.match(c)
    if nav:
        rest = c[nav.end():]
        conn = _AA_CONN_RE.search(rest)
        if conn:
            app = _strip_quotes(rest[:conn.start()])
            after = rest[conn.end():]
            vt = _AA_TYPE_VERB.match(after)
            if vt and app:
                payload = _strip_quotes(after[vt.end():])
                if payload:
                    return {"app": app, "payload": payload, "pattern": "nav_type"}
    # 2) IN_APP + TYPE: "en APP escribí X"
    m_in = re.match(r"^\s*(?:en|in|into|on|dentro\s+de|dans|im|su)\s+(?P<app>.+?)\s+"
                    r"(?P<rest>(?:escr[íi]b\w*|tecle[áa]\w*|tipe[áa]\w*|type|write|"
                    r"pon[ée]\w*|escrev\w*|[ée]cri\w*|schreib\w*|scriv\w*)\b.*)$",
                    c, flags=re.IGNORECASE)
    if m_in:
        app = _strip_quotes(m_in.group("app"))
        vt = _AA_TYPE_VERB.match(m_in.group("rest"))
        if vt and app:
            payload = _strip_quotes(m_in.group("rest")[vt.end():])
            if payload:
                return {"app": app, "payload": payload, "pattern": "in_app_type"}
    # 3) TYPE + "en/a" APP: "escribí X en APP" (prefiere 'en', respaldo 'a')
    vt = _AA_TYPE_VERB.match(c)
    if vt:
        body = c[vt.end():]
        for loc in (_AA_LOC_PREF, r"a|al"):
            # ÚLTIMO localizador (para 'X a las 5 en notepad' tomar el 'en' final)
            matches = list(re.finditer(r"\s+(?:" + loc + r")\s+", body, flags=re.IGNORECASE))
            if matches:
                last = matches[-1]
                payload = _strip_quotes(body[:last.start()])
                app = _strip_quotes(body[last.end():])
                if payload and app:
                    return {"app": app, "payload": payload, "pattern": "type_in_app"}
    return None


# --- Extracción de TARGET de CLICK (computer-use) ----------------------------
# Simétrico a la escritura: una cláusula "apretá/clickeá/tocá/seleccioná <botón>"
# en contexto GUI debe ir a la macro determinista click_button(label) — UIA find
# por Name + InvokePattern + verify — NO a que el 4B forme la llamada (medido
# flojo encadenando). El verbo de click es vocabulario CERRADO y morfológico
# (solo SEPARA verbo de label) -> stems multi-idioma. Universal.
_CLICK_VERB_STEM = re.compile(
    r"^\s*(?:"
    # PERÍFRASIS OPCIONAL "hacé/haz/hagá/dale/dá click", "make/do/give a click",
    # "faz/fai/mach ... click" (BUG real #click_boton, 2026-06-04: "hace click en
    # el botón rojo" no matcheaba -> el 4B respondía cualquier cosa). El lookahead
    # (?=...click...) hace que la perífrasis SOLO se consuma si el sustantivo que
    # sigue ES click/clic -> "hacé la tarea"/"haz que suene rock" NO matchean
    # (sin sobre-captura, sin listas por idioma). Mide la FORMA.
    r"(?:hac[eéê]?r?|haz|hag[áa]|dale|d[áa]|"                             # es
    r"mak(?:e|é)|do|give|"                                                # en
    r"fa(?:zer|z|ça)|fai(?:re|s)|mach(?:e|en)?)"                          # pt/fr/de
    r"\s+(?:un[ao]?\s+|a\s+|the\s+|el\s+)?"                               # artículo opcional
    r"(?=cl[íi]?c|click|klick|clic|clicc)"                                # lookahead: SÍ es click
    r")?\s*"
    r"(?:"
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


# PULSAR UNA TECLA EN UNA APP (accesibilidad). MEDIDO: "en la
# calculadora apretá el 5" -> extract_app_action lo detecta (pattern=in_app_act,
# app_hint='la calculadora') pero NO había constructor de plan determinista para un
# keypress simple -> caía a computer_use(goal genérico) -> el 4B planner devolvía "no
# pude planificar la acción" para un keypress trivial. (En cambio "abrí la calculadora
# y apretá el 5" SÍ andaba: toma el patrón nav_action.) Análogo a parse_type_action /
# parse_calc_action: detecta ESTRUCTURALMENTE "<verbo-pulsar> <TECLA> en <app>" (y "en
# <app> <verbo-pulsar> <TECLA>") y devuelve {app, key} para que el caller arme el plan
# DETERMINISTA [focus_app(app), keypress(key)] saltando el planner del 4B.
#
# PRECISIÓN (no robarle a otras tools): la TECLA debe ser un token CORTO e inequívoco
# — un dígito 0-9, una tecla NOMBRADA (_KEY_NAMES: enter/escape/tab/flechas/F1...) o
# una letra sola. Si el "target" es una palabra de contenido ('enviar', 'una canción',
# 'guardar') -> None: eso es un BOTÓN (click_button) o PLAY (media), no keypress. Si es
# texto largo -> None: eso lo cubre parse_type_action. Así "apretá enviar en WhatsApp"
# y "tocá una canción en Spotify" NO matchean. ESTRUCTURAL + multi-idioma (es/en/pt/it/
# fr/de) por morfología del verbo, NO listas de intenciones.
#
# Verbos de PULSAR-TECLA: subconjunto morfológico de _AA_ACT (apretar/presionar/pulsar/
# tocar/press/tap/hit/...). NO incluye 'click/clickear/clic' ni 'hacé clic' (eso busca
# un control por Name = click_button, no una tecla física). NO incluye 'escribir/poner/
# teclear' (texto = parse_type_action). NO incluye 'sumá/restá' (aritmética = parse_calc).
_KP_VERB = (
    r"apret[áa]\w*|apreta|apriet\w*|"                                   # es apretar
    r"presion[áa]\w*|presiona\w*|puls[áa]\w*|pulsa\w*|"                 # es presionar/pulsar
    r"toc[áa]\w*|toca\w*|"                                              # es tocar
    r"press(?:ed|es|ing)?|tap(?:ped|s|ping)?|hit\w*|"                  # en
    r"aperte\w*|aperta\w*|toqu\w*|"                                     # pt
    r"appui\w*|appuie\w*|"                                              # fr
    r"dr[üu]ck\w*|tipp\w*|"                                             # de pulsar/teclear-tecla
    r"premi\w*|schiacc\w*"                                              # it premere/schiacciare
)
# Localizador app-segundo ("... en <app>") — preferimos 'en'/'in' (no 'a', ambiguo).
_KP_LOC = r"en|in|into|on|sobre|dentro\s+de|dans|im|su|no"
# Artículo/conector opcional entre el verbo y la TECLA ("apretá EL 5", "press THE enter,
# "toca a tecla X"). Closed set multi-idioma, sólo al frente del target.
_KP_KEY_LEAD = re.compile(
    r"^(?:(?:el|la|los|las|the|le|il|lo|der|die|das|a|o)\s+)?"
    r"(?:(?:tecla|key|botón|boton|taste|tasto|touche|tecla)\s+)?",
    re.IGNORECASE,
)
# "en <app> <verbo> <tecla>" (app primero). El verbo NO al frente.
_KP_IN_APP = re.compile(
    r"^\s*(?:" + _KP_LOC + r")\s+(?P<app>.+?)\s+(?:" + _KP_VERB + r")\b\s*(?P<key>.+)$",
    re.IGNORECASE,
)
# "<verbo> <tecla> en <app>" (acción primero). 'en'/'in' obligatorio (no 'a').
_KP_ACT_IN = re.compile(
    r"^\s*(?:" + _KP_VERB + r")\b\s+(?P<key>.+?)\s+(?:" + _KP_LOC + r")\s+(?P<app>\S.*)$",
    re.IGNORECASE,
)


def _kp_normalize_key(raw: str | None) -> str | None:
    """Devuelve la TECLA canónica si `raw` es un token inequívoco para keypress
    (un dígito 0-9, una tecla nombrada de _KEY_NAMES, o una letra sola); None si es
    una palabra de contenido / texto largo (-> botón o type, NO keypress). Pela el
    artículo/conector inicial ('el', 'the', 'tecla'...) y comillas/puntuación. Mapea
    sinónimos de tecla al nombre físico (intro->enter, espacio->space, ...)."""
    if not raw:
        return None
    key = _KP_KEY_LEAD.sub("", raw.strip(), count=1).strip()
    key = key.strip(" .,;:!?\"'«»()[]")
    if not key:
        return None
    low = key.casefold()
    # 1) tecla NOMBRADA (enter/tab/escape/flechas/F1...): vocabulario CERRADO físico.
    if is_key_name(key):
        return _KP_KEY_CANON.get(low, low)
    # 2) un único dígito (0-9): inequívoco. (Sólo UNO: "apretá 25" = ambiguo -> None.)
    if len(key) == 1 and key.isdigit():
        return key
    # 3) una sola letra (alfabética, 1 char): "apretá la a" -> 'a'. Multi-idioma por
    #    .isalpha() (cubre acentos/ñ); el caller lo manda como tecla literal.
    if len(key) == 1 and key.isalpha():
        return low
    return None


# Sinónimos de tecla -> nombre físico que entiende gui.keypress (intro/retorno=enter,
# espacio=space, supr=delete...). Closed set, multi-idioma; NO contenido.
_KP_KEY_CANON = {
    "intro": "enter", "return": "enter", "retorno": "enter",
    "espacio": "space", "tabulador": "tab",
    "supr": "delete", "suprimir": "delete", "del": "delete",
    "retroceso": "backspace",
    "arriba": "up", "abajo": "down", "izquierda": "left", "derecha": "right",
    "inicio": "home", "fin": "end",
}


def parse_keypress_action(clause: str) -> dict | None:
    """Extrae {app, key, pattern} de un pedido de PULSAR-UNA-TECLA-EN-APP para
    construir un plan DETERMINISTA [focus_app(app), keypress(key)]. None si no es un
    keypress-action limpio (cae a parse_type_action / parse_calc / el planner del 4B).
    ESTRUCTURAL, multi-idioma. Cubre:
      "apretá/presioná/tocá/pulsá/press/tap <TECLA> en <app>"  y
      "en <app> apretá/presioná/... <TECLA>".
    PRECISIÓN: la TECLA debe ser inequívoca (dígito 0-9 / tecla nombrada / letra sola);
    si es palabra de contenido ('enviar', 'una canción') o texto largo -> None (eso es
    botón=click_button o texto=type, no keypress)."""
    if not clause or not clause.strip():
        return None
    c = clause.strip()
    # 1) "en <app> <verbo> <tecla>" (app primero).
    m = _KP_IN_APP.match(c)
    if m:
        app = _strip_quotes(m.group("app"))
        key = _kp_normalize_key(m.group("key"))
        if app and key:
            return {"app": app, "key": key, "pattern": "in_app_keypress"}
    # 2) "<verbo> <tecla> en <app>" (acción primero). 'en'/'in' obligatorio (no 'a',
    #    que es ambiguo: 'apretá a las 5' no es una tecla). El último localizador manda
    #    para que 'apretá la X en la calc' tome 'la calc' como app.
    vm = re.match(r"^\s*(?:" + _KP_VERB + r")\b", c, re.IGNORECASE)
    if vm:
        body = c[vm.end():]
        matches = list(re.finditer(r"\s+(?:" + _KP_LOC + r")\s+", body, re.IGNORECASE))
        if matches:
            last = matches[-1]
            key = _kp_normalize_key(body[:last.start()])
            app = _strip_quotes(body[last.end():])
            if app and key:
                return {"app": app, "key": key, "pattern": "keypress_in_app"}
    return None


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


# --- NAVEGACIÓN-EN-APP ------------------------------------------------------
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
    r"(?:(?:el|la|los|las|the|le|il|lo)\s+)?(?:" + _NAV_CONTAINER + r")\b\s+"
    # "de/del/of" opcional tras el contenedor ("canal DE soporte", "chat DE juan").
    r"(?:(?:de|del|of|do|da)\s+)?",
    re.IGNORECASE,
)
# fallback: solo preposición/artículo de dirección sin contenedor ("a X", "to X").
_NAV_PREP_ONLY = re.compile(
    r"^(?:a[l]?|to(?:\s+the)?|a\s+la|a\s+las|au|aux|no|na|nel|nella|su)\s+",
    re.IGNORECASE,
)
# Lead-in de SEGUNDA acción tras un "ve a <app>": una conjunción opcional + un verbo
# de abrir/mostrar/poner + (artículo) + (contenedor "chat/canal...") + ("de"). P.ej.
# "Ve a discord [y pon el chat de] cbayeah" -> "cbayeah". Multi-idioma básico. Se
# pela DESPUÉS de quitar la app del frente. Estructural (verbos, no nombres de app).
_NAV_SECOND_ACTION_LEAD = re.compile(
    r"^(?:y|e|and|und|et)?\s*"                                        # conjunción opc.
    r"(?:pon[eé]?|poner|abr[íi]|abrir|abre|mostr[áa]|muestra|mostrar|"  # verbos open/show
    r"llev[áa]me?|ll[ée]vame|anda?|and[áa]|ve|open|show|go\s+to)\s+"
    r"(?:(?:el|la|los|las|the|le|il)\s+)?"                            # artículo opc.
    r"(?:(?:" + _NAV_CONTAINER + r")\s+)?"                            # contenedor opc.
    r"(?:de|del|of|do|da)?\s*",                                       # "de" opc.
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
    # pelar el lead-in de una SEGUNDA acción ("a discord [y pon el chat de] X"):
    # tras quitar la app del frente queda "[a] y pon el chat de X" o "al chat de X".
    # Primero limpiar una preposición de dirección suelta que quedó ("a y pon..." ->
    # "y pon...") y luego el lead de la 2da acción -> deja el target limpio.
    rest = _NAV_PREP_ONLY.sub("", rest, count=1).strip()
    new = _NAV_SECOND_ACTION_LEAD.sub("", rest, count=1).strip(" ,-:")
    if new and new != rest:
        rest = new
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
