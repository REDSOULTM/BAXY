"""Detección de idioma para el reply post-tool (es/en/pt/fr/de/it), extraída de
agent.py (split del archivo-dios, 2026-06-19). Híbrido medido (verbo imperativo +
signos exclusivos + py3langid restringido) robusto en comandos cortos. SOLO decide
el IDIOMA del reply — la intención la decide el router por embeddings.

Mide la FORMA del texto (verbos/signos del idioma), NUNCA decide el contenido de la
respuesta (eso lo genera el LLM): es una guarda estructural, no una tabla enlatada.
`detect_lang_strong_signal` (señal char/verbo fuerte) vive en latency_helpers (leaf,
no cicla). agent.py re-exporta todo esto para reply_repair / agent_runner.
"""
from __future__ import annotations

from .latency_helpers import detect_lang_strong_signal as _detect_lang_strong_signal

_LANGID_SET = ("en", "es", "pt", "fr", "de", "it")

# Verbos IMPERATIVOS de comando por idioma — desempate para inputs CORTOS donde
# el clasificador estadístico falla (medido: py3langid da "open spotify"/"close
# chrome"/"open notepad" -> 'de' porque Spotify/Chrome son nombres propios
# internacionales sin señal de idioma). NO son respuestas enlatadas ni deciden la
# respuesta — solo desambiguan el IDIOMA del comando (mide la FORMA verbal, lo que
# el se permite como guarda estructural). El reply lo sigue generando el LLM.
# Medido: detector híbrido 15/16 vs py3langid solo 8/14.
_IMPERATIVE_VERBS = (
    ("en", (" open ", " close ", " play ", " mute ", " unmute ", " set ", " take ",
            " show ", " turn ", " stop ", " start ", " search ", " lower ", " raise ",
            " maximize ", " minimize ", " lock ", " pause ", " skip ", " next ")),
    ("it", (" apri ", " chiudi ", " imposta ", " riproduci ", " metti ", " cerca ",
            " abbassa ", " alza ", " disattiva ", " attiva ", " vai ", " digita ",
            " scrivi ", " leggi ", " mostra ")),
    ("fr", (" ouvre ", " ferme ", " mets ", " fais ", " lance ", " cherche ",
            " baisse ", " monte ", " coupe ", " active ", " écris ", " tape ",
            " lis ", " montre ")),
    ("de", (" öffne ", " schließe ", " schliesse ", " stell ", " spiele ", " starte ",
            " suche ", " mach ", " schalte ", " erhöhe ", " lies ", " tippe ",
            " schreib ", " zeig ")),
    ("pt", (" abre ", " fecha ", " coloca ", " tira ", " toca ", " procura ",
            " abaixa ", " aumenta ", " silencia ", " liga ")),
    ("es", (" abrí ", " cerrá ", " poné ", " subí ", " bajá ", " buscá ", " cerra ",
            " silenciá ", " mostrá ", " sacá ", " pausá ",
            # tuteo frecuente exclusivo es (pt: diz-me/me diga, dá-me; it: dimmi):
            # MEDIDO 2026-06-11 "dime la hora" → py3langid fr → rewrite roto.
            " dime ", " decime ", " dame ", " muéstrame ", " dimelo ", " dímelo ",
            # imperativos tú/neutro SIN tilde (voz/teclado descuidado). MEDIDO
            # 2026-06-12: "pone rock en spotify" → py3langid fr → repair
            # reescribió un reply es CORRECTO al francés; "Abri Spotify y pone
            # rock" → en ("Done, I put some rock..."). "pon"/"pone"/"abri" no
            # son palabra funcional de los otros 5 idiomas soportados (it
            # "pone"=3ª persona de porre, no imperativo de comando).
            " pon ", " pone ", " abri ")),
)


_SPANISH_LEAK_MARKERS = (
    # marcas ES INEQUÍVOCAS en confirmaciones post-acción (el reply leakeado típico).
    # Verbos ES 1ª persona pretérito (con tilde — distinguen de pt "fechei"/it/fr) +
    # variantes con diptongo ("cierré", "minimicé") + frases ES que NO coinciden
    # token-a-token en pt/fr/de/it + el caveat ES de soften_unverified_launch. NO
    # incluye "Listo," solo (el modelo lo prefija a un cuerpo PT correcto -> falso+).
    # Mide la FORMA, no decide la respuesta: solo señala que el reply quedó en ES.
    # Lista deliberadamente amplia en variantes verbales (el 4B escribe "cerré"/
    # "cierré"); ampliarla es legítimo (detector de FORMA, no tabla de respuestas).
    "abrí", "cerré", "cierré", "saqué", "silencié", "minimicé", "maximicé",
    "ajusté", "configuré", "dejé el volumen", "lo hice", "lo que pediste",
    " pediste", "está abierto", "la captura", "la pantalla", "verifiqué",
    "el trabajo de impresión", "puse lo que", "tomé la captura", "se tomó",
    "el volumen está", "el volumen a", "el volumen en", "la ventana que",
    "que me indicaste", "no pude confirmar", "que se completara", "cola de impresión",
)


def _looks_spanish(text: str) -> bool:
    """True si `text` tiene marcadores INEQUÍVOCOS de español (para detectar que un
    reply post-acción leakeó a ES cuando el user pidió otro idioma). Robusto donde
    py3langid falla (un "Listo, cerré Chrome" corto se mis-detecta como fr). Mide la
    FORMA (verbos ES 1ª persona + "Listo,"), no decide la respuesta. Conservador:
    requiere una marca ES fuerte — no se dispara con texto en/pt/fr/de/it."""
    if not text:
        return False
    low = f" {text.lower()} "
    return any(m in low for m in _SPANISH_LEAK_MARKERS)


def _detect_lang(text: str) -> str:
    """Detecta el idioma de `text` entre los 6 soportados, robusto en comandos
    CORTOS. Estrategia híbrida (medida 15/16): (1) verbo imperativo distintivo del
    comando (desempate de FORMA para inputs de 2 palabras donde lo estadístico
    falla), (2) py3langid restringido a nuestros idiomas, (3) fallback `_guess_lang`
    si py3langid no está. SOLO para decidir el idioma del reply post-tool (no decide
    intención — eso es el router por embeddings).

    Por qué la lista de verbos: py3langid manda "open spotify"/"close chrome" a
    'de' (nombres propios internacionales sin señal); el verbo imperativo es la
    única señal de idioma fiable en esos casos. Es desambiguación de idioma por la
    FORMA verbal, NO una tabla de respuestas — el reply lo genera el LLM."""
    t = (text or "").strip()
    if not t:
        return "es"
    strong = _detect_lang_strong_signal(t)
    if strong:
        return strong
    tl = t.lower()
    # (0) SIGNOS/LETRAS EXCLUSIVOS del español: ¿ ¡ ñ no existen en en/fr/de/it; el
    # pt usa ñ raramente (não, mas no ñ). Señal ESTRUCTURAL inequívoca (un carácter
    # del idioma, no una keyword de contenido) que py3langid IGNORA: medido,
    # clasificaba "¿Qué es Mortal Kombat?" como 'fr' por los acentos + nombre propio.
    # (Bug 2026-06-08.) Esto NO es hardcode de respuestas: es ortografía del idioma.
    if any(ch in tl for ch in ("¿", "¡", "ñ")):
        return "es"
    # (1) verbo imperativo distintivo (señal fuerte en comandos cortos)
    s = f" {tl} "
    for lang, verbs in _IMPERATIVE_VERBS:
        if any(v in s for v in verbs):
            return lang
    # (2) py3langid restringido. ANTES de clasificar, quitamos los NOMBRES PROPIOS
    # (palabras Capitalizadas no-iniciales: 'Mortal', 'Kombat', 'Chrome') porque
    # dominan la clasificación de frases cortas y la desvían (medido: 'háblame de
    # Mortal Kombat' -> 'fr' por el nombre extranjero). Sin ellos, py3langid ve las
    # palabras FUNCIONALES del idioma (háblame, de, qué...). Señal estructural
    # (capitalización), no keywords. Si quedan pocas palabras, usamos el texto crudo.
    try:
        import py3langid as _langid
        try:
            _langid.set_languages(list(_LANGID_SET))
        except Exception:
            pass
        _words = t.split()
        _funcional = " ".join(
            [w for i, w in enumerate(_words)
             if i == 0 or not w[:1].isupper()]) if len(_words) >= 2 else t
        _clf_text = _funcional if len(_funcional.split()) >= 2 else t
        lang, _conf = _langid.classify(_clf_text)
        if lang in _LANGID_SET:
            return lang
    except Exception:
        pass
    # (3) fallback: sin keyword-guesser (reply_validator removido en
    # Experimentando) -> default es. El idioma del reply lo elige el LLM nativo.
    return "es"


_FIXED_LANGS = frozenset({"es", "en", "pt", "fr", "de", "it"})
_LANG_NAMES = {"en": "English", "es": "Spanish", "pt": "Portuguese",
               "fr": "French", "de": "German", "it": "Italian"}


def _os_ui_lang() -> str | None:
    """Idioma de la UI del SISTEMA OPERATIVO (es/en/pt/fr/de/it) o None. En Windows
    es lo que el user configuró como su idioma -> es su idioma real, igual que
    Discord/Spotify defaultean a él. Robusto: GetUserDefaultUILanguage + locale."""
    code = None
    try:
        import ctypes
        import locale as _loc
        _id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        code = (_loc.windows_locale.get(_id) or "")
    except Exception:
        code = None
    if not code:
        try:
            import locale as _loc
            code = (_loc.getdefaultlocale()[0] or "")
        except Exception:
            code = ""
    pref = (code or "").strip().lower().replace("_", "-").split("-")[0]
    return pref if pref in _FIXED_LANGS else None


def _reply_lang(text: str) -> str:
    """Idioma del reply (2026-06-08). Jerarquía: (1) SELECTOR explícito del user
    (GEMMA4_VOICE_LANG fijo) -> ese idioma, sin auto-detectar. (2) Modo Automático:
    anclar al idioma del SO (es_MX -> es) y solo cambiar si el texto es CLARAMENTE
    de otro idioma (la capa de signos/verbos de _detect_lang lo desambigua fuerte).
    Esto evita el drift a fr/pt en frases cortas con nombres propios (medido: "háblame
    de Mortal Kombat" -> fr): el SO del user es español, así que ancla a es. (3) Sin
    SO detectable -> _detect_lang puro. NO modifica _detect_lang."""
    import os as _os_lang
    fixed = (_os_lang.environ.get("GEMMA4_VOICE_LANG") or "").strip().lower()
    fixed = fixed.replace("_", "-").split("-")[0]   # 'es-419' -> 'es'
    if fixed in _FIXED_LANGS:
        return fixed
    # Señal FUERTE (char/verbo exclusivo) -> gana siempre.
    strong = _detect_lang_strong_signal(text)
    if strong:
        return strong
    # Detección ROBUSTA (py3langid + verbos + quita nombres propios). Si da un
    # idioma del set, lo respetamos: anclar al SO sobre una detección clara rompía
    # a TODOS los usuarios no-español ("tell me the time"/"druck mir das PDF" ->
    # respuesta en ES). _detect_lang YA protege el caso de drift por nombre propio
    # ("háblame de Mortal Kombat" -> es), así que confiar en él es seguro. El ancla
    # al SO queda solo como desempate cuando _detect_lang no concluye (frase vacía/
    # ambigua) — bug de "language confusion" cazado en la mission-eval 2026-06-10.
    detected = _detect_lang(text)
    if detected in _FIXED_LANGS:
        return detected
    os_lang = _os_ui_lang()
    if os_lang is not None:
        return os_lang
    return detected


def _detect_lang_is_strong(text: str, detected: str) -> bool:
    """¿La detección de idioma vino de una señal FUERTE (char/verbo exclusivo) y no
    de la estadística frágil? Reusa las capas 0/1 de _detect_lang: si el texto tiene
    ¿¡ñ -> es fuerte; si tiene un verbo imperativo del idioma detectado -> fuerte."""
    tl = (text or "").lower()
    if detected == "es" and any(ch in tl for ch in ("¿", "¡", "ñ")):
        return True
    strong = _detect_lang_strong_signal(text)
    if strong:
        return detected == strong
    s = f" {tl} "
    for lang, verbs in _IMPERATIVE_VERBS:
        if lang == detected and any(v in s for v in verbs):
            return True
    return False
