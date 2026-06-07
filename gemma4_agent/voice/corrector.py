"""RapidFuzz post-corrector against domain inventory.

Whisper-small with
`language='es'` will phoneticise English nouns ("Chrome" -> "Aurekrom",
"Benson Boone" -> "Benson Mould"). Re-training Whisper to handle this
is out of scope (CPU-only constraint, multi-user). Instead, we do
DETERMINISTIC fuzzy-matching of the raw Whisper output against a
finite set of known entities (apps, artists, songs, verbs).

Algorithm:
  1. Tokenise the Whisper output (whitespace).
  2. For each position, try 1-, 2-, and 3-gram windows.
  3. For each window, RapidFuzz.process.extractOne against EVERY
     category in the inventory (accent-stripped, lowercased).
  4. If any match scores ≥ THRESHOLD (default 78), replace the window
     with the canonical form and advance the cursor by the gram size.
  5. Otherwise, keep the original token and advance by 1.

Properties:
  - Deterministic: same input → same output (regression-testable).
  - Bounded latency: O(N * M) where N = transcript tokens, M = inventory
    size. With M < 200, runs in single-digit milliseconds.
  - Conservative: keeps original token unless a CLEAR fuzzy match exists.
    Lower threshold → over-correction. Higher → misses good corrections.

Inspired by commercial Alexa/Google personalized entity resolution.
"""
from __future__ import annotations

import logging
import unicodedata
from typing import Sequence

logger = logging.getLogger(__name__)


# Match threshold (0-100). Below this, we keep the original token.
# 78 is too strict for phonetic mistranscriptions (measured):
#   'aurekrom' vs 'chrome' = 43 (Whisper's mistranscription score)
#   'benson mould' vs 'benson boone' = 66
#   'cross' vs 'chrome' = 55
# These are string-edit distances. We ALSO compare phonetic codes
# (Metaphone) below — see PHONETIC_THRESHOLD.
DEFAULT_THRESHOLD = 65

# Phonetic threshold (0-100). Applied to fuzz.ratio OVER the Metaphone codes
# of the window vs the inventory item. Los anglicismos que Whisper-small
# fonetiza al español ("Chrome"->"aurekrom", "Steam"->"estimulo",
# "Gemma"->"jema", "Spotify"->"espotify") son matches FONÉTICOS, inalcanzables
# por edit-distance de texto. Medido contra casos reales: positivos
# ("estimulo"->steam=75, "espotify"->spotify=93, "netflis"->netflix=91,
# "jema"->gemma=100) caen ≥75; negativos (palabras comunes "abre"=40, "pon"=40,
# "musica"=36, "hola"=22) caen ≤40. 72 separa limpio sin falsos positivos.
# Fuente: Sun et al. arXiv
# 2309.09552, +10% recall code-switching con phonetic matching + Whisper frozen).
# jellyfish.metaphone es inglés-tuned, lo cual ENCAJA: el problema es justamente
# anglicismos ingleses mal oídos en fonología española.
PHONETIC_THRESHOLD = 78

# jellyfish es opcional: si falta, el corrector degrada a solo-texto (la rama
# fonética se desactiva, sin romper). Se carga una vez a nivel módulo.
try:
    import jellyfish as _jellyfish
    _HAS_PHONETIC = True
except Exception:  # pragma: no cover - depende del entorno
    _jellyfish = None
    _HAS_PHONETIC = False


# Stop-list de palabras españolas frecuentes que NUNCA deben corregirse contra
# el inventario, aunque colisionen fuzzy/fonéticamente con un verbo o app. Sin
# esta lista el corrector corrompe palabras válidas del español: "musica"->
# "buscar" (txt_adj 67>umbral), "guerra"->"cierra"/"sierra". Sun et al.
# recomienda exactamente este "cap" de vocabulario frecuente contra
# over-correction. Normalizado (sin
# acentos). Solo palabras de contenido común que colisionan; NO incluir términos
# que el user podría querer como nombre propio.
_SPANISH_STOPWORDS = frozenset({
    "musica", "cancion", "canciones", "tema", "temas", "video", "videos",
    "guerra", "tierra", "sierra", "fecha", "hora", "dia", "noche", "tarde",
    "luz", "ventana", "ventanas", "volumen", "sistema", "pantalla", "archivo",
    "carpeta", "correo", "mensaje", "foto", "imagen", "musical",
    "hola", "gracias", "adios", "bien", "mal", "ahora", "luego", "hoy", "manana",
    "que", "cual", "quien", "como", "cuando", "donde", "porque", "cuanto",
    # números en palabra: nunca son nombres propios; protegen dictados con
    # cifras (sin esto "treinta"->"Torrent", medido sobre FLEURS).
    "cero", "uno", "una", "dos", "tres", "cuatro", "cinco", "seis", "siete",
    "ocho", "nueve", "diez", "once", "doce", "veinte", "treinta", "cuarenta",
    "cincuenta", "cien", "ciento", "mil", "millon", "millones", "medio",
    # preposiciones/conjunciones cortas que colisionan con verbos ("en"->"enciende")
    "en", "de", "la", "el", "lo", "un", "una", "con", "por", "para", "del",
    "los", "las", "al", "se", "su", "mi", "tu", "y", "o", "a",
})


# Verbos de COMANDO que licencian corregir el TOKEN SIGUIENTE (el argumento).
# Diseño estructural: corregir token-por-token sobre TODO el transcript corrompe
# habla real ("persona"->"prende", "el hombre"->"el Chrome"). Los nombres
# propios del inventario aparecen en POSICIÓN DE ARGUMENTO: "abre <APP>",
# "pon <X> en <STREAMER>". Frases declarativas conversacionales ("la granizada
# destruyó...") NO tienen verbo-de-comando inicial, así que NO se corrigen. Esto
# elimina la corrupción de raíz sin una lista infinita de stopwords. (patrón
# Alexa/Google "skill prefix biasing": el ASR solo resuelve el slot tras el
# intent.)
_COMMAND_VERB_ROOTS = (
    "abre", "abri", "cierra", "cerr", "pon", "pone", "ponme", "reproduc",
    "toca", "play", "prende", "prend", "enciende", "encende", "busca", "busc",
    "mira", "ver", "escucha", "escuch", "open", "close", "watch", "search",
    "mete", "metel", "dale", "lanza", "ejecuta", "inicia", "arranca",
)
# Conectores que licencian corregir el siguiente token ("X en <STREAMER>",
# "cancion de <ARTIST>"). Posición de argumento secundaria.
_ARG_CONNECTORS = frozenset({"en", "de", "del", "con", "a"})


def _licenses_next(token_norm: str) -> bool:
    """True si `token_norm` es un verbo de comando o conector que habilita la
    corrección del token siguiente (posición de argumento)."""
    if token_norm in _ARG_CONNECTORS:
        return True
    return any(token_norm.startswith(r) for r in _COMMAND_VERB_ROOTS)


def _normalise(s: str) -> str:
    """Lowercase + strip accents/diacritics + strip punctuation, for fair
    comparison. Parakeet appends '.' to the last token of EVERY utterance and
    varies hyphens/apostrophes ("Counter-Strike", "Baldur's"); leaving that
    punctuation in degraded the fuzzy/phonetic match of the final token — which
    is usually the proper name we most need to rescue ("Kimp."!=gimp, "red."!=
    reddit). Map every non-alphanumeric to a space and collapse, so window and
    inventory are normalised identically."""
    s = s.lower()
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    s = "".join(c if (c.isalnum() or c.isspace()) else " " for c in s)
    return " ".join(s.split())


def _metaphone(s: str) -> str:
    """Metaphone code INGLÉS de un string ya normalizado (sin espacios -> junta
    tokens). Cadena vacía si jellyfish no está o el input es trivial."""
    if not _HAS_PHONETIC or not s:
        return ""
    try:
        # Metaphone de la frase sin espacios: "espotify"->"ESPTF". Para n-gramas
        # quitamos espacios para una sola clave fonética comparable.
        return _jellyfish.metaphone(s.replace(" ", ""))
    except Exception:
        return ""


# Spanish Metaphone (Mosquera 2012): segunda clave fonética, codificada según
# fonología ESPAÑOLA. Necesaria porque Parakeet (multilingüe, sesgo es) fusiona
# nombres ingleses a sonido español ("vlc"->"BLC", "netflis", "disnei"); el
# Metaphone inglés no acerca esos códigos pero el español sí. Medido:
# blc/vlc ES=100 (EN=67), netflis/netflix ES=100, disnei/disney ES=100. Para
# fusiones donde Parakeet PIERDE fonemas (crumb/chrome, echo/edge) el inglés
# sigue siendo mejor -> usamos el MÁXIMO de ambas codificaciones (dual ES↔EN),
# que domina a cualquiera sola (codificación dual + match cruzado).
try:
    from gemma4_agent.voice.phonetic_es import spanish_metaphone as _spanish_metaphone
    _HAS_ES_PHONETIC = True
except Exception:  # pragma: no cover
    _spanish_metaphone = None
    _HAS_ES_PHONETIC = False


# Gate de LONGITUD de enunciado (anti-overfit, medido): un asistente de voz
# recibe COMANDOS, no párrafos. Los comandos son cortos (sobre 84 reales:
# p50=3 tokens, p90=6, MAX=8; 81/84 ≤6); el habla declarativa es larga
# (sobre 180 clips humanos FLEURS+chileno: p50=21 tokens, solo 18/180 ≤6). Con el
# inventario grande (discovery, 125+ apps) el corrector corrompe 20/180 frases
# declarativas ("Esto"->"stop", "repollo"->"Apollo", "setenta"->"Counter-Strike").
# Solución estructural (slot por posición): NO corregir enunciados largos. Umbral
# 8 = el máximo real de un comando medido. Esto protege a CUALQUIER usuario
# hablando frases largas sin perder ninguna corrección de comando real.
# (anti-regresión por dominio; uso universal, no overfit a una voz.)
MAX_COMMAND_TOKENS = 8


def _metaphone_es(s: str) -> str:
    """Spanish Metaphone de un string ya normalizado (sin espacios)."""
    if not _HAS_ES_PHONETIC or not s:
        return ""
    try:
        return _spanish_metaphone(s.replace(" ", ""))
    except Exception:
        return ""


class FuzzyCorrector:
    """Stateless. Constructed once with an inventory; reused across turns."""

    def __init__(
        self,
        inventory: dict[str, list[str]],
        threshold: int = DEFAULT_THRESHOLD,
    ) -> None:
        self._inventory = inventory
        self._threshold = threshold
        self._phonetic_threshold = PHONETIC_THRESHOLD
        # Pre-normalize + pre-Metaphone (EN y ES) cada categoría para comparar
        # rápido. Guardamos el original para devolver la forma canónica. Tupla:
        # (texto_norm, metaphone_EN, metaphone_ES, original).
        self._normalized: dict[str, list[tuple[str, str, str, str]]] = {}
        for cat, items in inventory.items():
            self._normalized[cat] = [
                (_normalise(x), _metaphone(_normalise(x)),
                 _metaphone_es(_normalise(x)), x)
                for x in items
            ]

    def correct(self, transcript: str) -> str:
        """Apply fuzzy correction to a Whisper raw transcript.

        Algorithm:
          For each position i, try ALL n-gram windows (3, 2, 1).
          For each window+inventory-item pair, compute the match score.
          Pick the window-replacement-size triple that maximizes score,
          BUT require the match to actually cover the window (no
          replacing 2 tokens with 1 unless the 2-gram is a near-perfect
          match to the candidate).
        """
        try:
            from rapidfuzz import fuzz
        except ImportError as exc:
            logger.warning(
                "rapidfuzz unavailable; correction disabled: %s", exc,
            )
            return transcript

        tokens = transcript.split()
        # Gate de longitud: enunciados largos = habla declarativa, no comandos.
        # No los tocamos (protege voz real de cualquier usuario; ver
        # MAX_COMMAND_TOKENS). El comando más largo de RED son 8 tokens.
        if len(tokens) > MAX_COMMAND_TOKENS:
            return transcript
        out: list[str] = []
        i = 0
        n = len(tokens)
        while i < n:
            best_replacement: str = tokens[i]
            best_score: float = 0
            best_size: int = 1
            # GATE POSICIONAL: solo corregimos un token si está en
            # posición de ARGUMENTO de comando — i.e. el token anterior (en la
            # SALIDA ya corregida) es un verbo de comando o un conector. La
            # posición 0 siempre es corregible (puede ser el verbo mismo, p.ej.
            # "habre"->"abre"). Esto evita corromper habla declarativa real.
            prev_norm = _normalise(out[-1]) if out else ""
            is_command_start = (i == 0)
            in_arg_position = is_command_start or _licenses_next(prev_norm)
            # DOS REGÍMENES (medido contra 180 clips reales):
            #   - En posición de comando/argumento -> corrección PLENA (texto +
            #     fonético, thresholds normales): ahí es donde viven los nombres
            #     propios y el contexto es seguro.
            #   - Fuera de esa posición (habla declarativa) -> NO desactivamos
            #     del todo (un nombre propio fuerte como "netflis"->Netflix
            #     puede aparecer suelto), pero SÍ endurecemos: solo TEXTO (sin
            #     fonético, que es el que más corrompía) y threshold alto (75),
            #     sin verbos. Así "netflis"(86)/"disnei"(83) pasan pero
            #     "hombre"->Chrome(67)/"persona"->prende(40) no.
            strict_mode = not in_arg_position
            # En posición de argumento (no inicio) NUNCA corregimos a un verbo:
            # los args son nombres propios. En strict_mode tampoco.
            skip_verbs = (not is_command_start)
            text_threshold = 75 if strict_mode else self._threshold
            for ngram in (3, 2, 1):
                if i + ngram > n:
                    continue
                window_tokens = tokens[i:i + ngram]
                window = " ".join(window_tokens)
                window_norm = _normalise(window)
                # Stop-list guard: una palabra española común y válida no se
                # corrige aunque colisione con un verbo/app del inventario.
                #   - 1-grama exacto en la stop-list -> no corregir.
                #   - multi-grama que CONTIENE una stopword -> no colapsar (ej.
                #     "en disnei" no debe volverse "enciende"; "en" debe quedar
                #     suelto y "disnei" matchear como 1-grama). Esto evita que un
                #     2-grama con preposición absorba el token real (sin esto
                #     "pon loki en disnei" -> "...enciende").
                norm_parts = [_normalise(t) for t in window_tokens]
                if any(p in _SPANISH_STOPWORDS for p in norm_parts):
                    continue
                window_meta = _metaphone(window_norm)
                window_meta_es = _metaphone_es(window_norm)
                for cat, normalized_items in self._normalized.items():
                    # No corregir a un verbo si: estamos en posición de argumento
                    # (los args son nombres propios), o el window es multi-token
                    # (un verbo de comando es UNA palabra; corregir 2-gram->verbo
                    # colapsa erróneamente, p.ej. "si busca"->"buscar").
                    if cat == "verbs" and (skip_verbs or ngram > 1):
                        continue
                    for norm_item, meta_item, meta_item_es, orig_item in normalized_items:
                        # (1) Rama TEXTUAL: fuzz.ratio sobre el texto normalizado.
                        score = fuzz.ratio(window_norm, norm_item)
                        # Length penalty: if window and candidate have
                        # very different lengths, the score is inflated
                        # by partial overlap (e.g. 'abre chrome' partly
                        # matches 'chrome' because 'chrome' is in there).
                        # Penalize so a 1-gram clean match beats a 2-gram
                        # partial match.
                        len_diff = abs(len(window_norm) - len(norm_item))
                        len_max = max(len(window_norm), len(norm_item), 1)
                        coverage = 1.0 - (len_diff / len_max)
                        adjusted = score * coverage
                        passes_text = adjusted >= text_threshold

                        # (2) Rama FONÉTICA: fuzz.ratio sobre los códigos
                        # Metaphone. Atrapa anglicismos fonetizados que el texto
                        # no alcanza ("jema"->gemma, "netflis"->netflix,
                        # "disnei"->disney).
                        #
                        # GATE anti-falso-positivo (medido): el
                        # fonético solo NO separa anglicismos reales de palabras
                        # españolas que colisionan ("ventana"~"finder" FNTN/FNTR
                        # =75, "cierra"~"sierra"=100). Por eso exigimos TAMBIÉN un
                        # piso de similitud TEXTUAL (>=45): un anglicismo mal oído
                        # comparte letras con su target ("netflis"/"netflix"
                        # txt=86, "jema"/"gemma" txt=67), pero una palabra
                        # española distinta no ("ventana"/"finder" txt=15). Así
                        # la rama fonética solo "rescata" tokens ya plausiblemente
                        # parecidos, no inventa correcciones sobre vocabulario
                        # común (cap del corrector contra over-correction de
                        # vocabulario frecuente).
                        # Fonético: NO en strict_mode (declarativo) y NO para
                        # verbos. Los verbos son cortos y colisionan fonéticamente
                        # ("cuales"->close KLS/KLS=100, "fue"->ver) — se corrigen
                        # solo por texto (se oyen razonablemente bien). El fonético
                        # se reserva para nombres propios (apps/artistas/canciones).
                        # Codificación DUAL ES↔EN: tomamos el MÁXIMO de la
                        # similitud fonética inglesa y española. Cada fusión usa
                        # la codificación que mejor la captura: anglicismos
                        # fonetizados al español ("blc"->vlc, "netflis"->netflix)
                        # puntúan alto en ES; fusiones con pérdida de fonemas
                        # ("crumb"->chrome) puntúan mejor en EN. El máximo domina
                        # a cualquiera sola sin bajar el piso. (Plan §Axis-3.)
                        passes_phon = False
                        phon_adjusted = 0.0
                        if (not strict_mode and cat != "verbs"
                                and score >= 50):
                            cands = []
                            if window_meta and meta_item:
                                m_diff = abs(len(window_meta) - len(meta_item))
                                m_max = max(len(window_meta), len(meta_item), 1)
                                cands.append(fuzz.ratio(window_meta, meta_item)
                                             * (1.0 - m_diff / m_max))
                            if window_meta_es and meta_item_es:
                                e_diff = abs(len(window_meta_es) - len(meta_item_es))
                                e_max = max(len(window_meta_es), len(meta_item_es), 1)
                                cands.append(fuzz.ratio(window_meta_es, meta_item_es)
                                             * (1.0 - e_diff / e_max))
                            if cands:
                                phon_adjusted = max(cands)
                                passes_phon = phon_adjusted >= self._phonetic_threshold

                        if not (passes_text or passes_phon):
                            continue
                        # Score efectivo = el mejor de las dos ramas, para que
                        # el desempate elija el candidato más fuerte globalmente.
                        effective = max(adjusted, phon_adjusted)
                        if effective > best_score:
                            best_score = effective
                            best_replacement = orig_item
                            best_size = ngram
            out.append(best_replacement)
            i += best_size
        return " ".join(out)

    def strip_wake_phrase(self, transcript: str) -> str:
        """Remove a leading wake phrase from the transcript.

        The wake detector fires when the wake word is heard. The STT then
        often transcribes the wake phrase too (because the audio clip
        captured by the state machine includes the wake). The LLM
        downstream doesn't need it as input.

        Two-stage match on the first 1-3 tokens:

          1. EXACT (normalised) — any known wake phrase. Cheap, certain.
          2. PHONETIC (fuzzy) — the wake word "baxy" is an invented word
             OUTSIDE the STT vocabulary, so Parakeet maps it to the nearest
             REAL word: "Bixby", "Paxi", "Max", "Vaxi"... Exact match misses
             those, leaking the mis-heard name into the command ("Bixby,
             ¿qué juego...?" confuses the LLM). We compare the FIRST token's
             dual ES/EN Metaphone code against each wake word and strip it if
             the phonetic similarity is high. Thresholds are MEASURED
             (scripts/_diag/_diag_wake_strip_threshold.py):
               - ≥ 80 with NO trailing punctuation: 0 false positives over
                 20 real command openers ("busca"=67, "máximo"=60 stay below).
               - ≥ 72 IF the token ends in a comma — the comma is the pause
                 after the wake ("Paxi, va a...", "Bixby, ¿qué..."), strong
                 evidence of wake; no command opener appears comma-terminated.
             This is safe ONLY because strip_wake_phrase runs strictly AFTER
             a wake fired (pipeline.py), so the first token is a strong wake
             candidate by construction. We never fuzzy-strip beyond token 1.

        Returns the transcript with the wake-word prefix stripped, if matched.
        Otherwise returns the transcript intact.
        """
        wake_words = self._inventory.get("wake_words", [])
        if not wake_words:
            return transcript
        tokens = transcript.split()
        if not tokens:
            return ""
        # Stage 1: EXACT match on the first 1-3 tokens (covers "hey baxy",
        # "baxy", "baxi", "backsy" — anything spelled as a known variant).
        for ngram in (3, 2, 1):
            if ngram > len(tokens):
                continue
            prefix_norm = _normalise(" ".join(tokens[:ngram]))
            for wake in wake_words:
                if _normalise(wake) == prefix_norm:
                    return " ".join(tokens[ngram:])
        # Stage 2: PHONETIC fuzzy match on the FIRST token only. Catches the
        # STT mis-hearings of the invented wake word.
        first_raw = tokens[0]
        # A trailing comma is the post-wake pause -> stronger evidence -> laxer
        # threshold. Detect it on the RAW token, before normalisation strips it.
        has_pause = first_raw.rstrip().endswith((",", ";", ":"))
        threshold = 72 if has_pause else 80
        first_norm = _normalise(first_raw)
        if first_norm and self._phonetic_wake_match(first_norm, wake_words, threshold):
            return " ".join(tokens[1:])
        return transcript

    def _phonetic_wake_match(
        self, token_norm: str, wake_words: Sequence[str], threshold: float
    ) -> bool:
        """True if the normalised token is a phonetic match for any single-word
        wake word, at or above `threshold`. Uses the same dual ES/EN Metaphone
        + RapidFuzz machinery as correct(); falls back to text ratio if the
        phonetic backend is unavailable. Only single-word wake words are
        considered (multi-word phrases are handled by the exact stage)."""
        try:
            from rapidfuzz import fuzz
        except Exception:
            return False
        for wake in wake_words:
            w = _normalise(wake)
            if not w or " " in w:  # single-word wakes only here
                continue
            text_score = fuzz.ratio(token_norm, w)
            en = _metaphone(token_norm), _metaphone(w)
            es = _metaphone_es(token_norm), _metaphone_es(w)
            phon = 0.0
            if en[0] and en[1]:
                phon = max(phon, fuzz.ratio(en[0], en[1]))
            if es[0] and es[1]:
                phon = max(phon, fuzz.ratio(es[0], es[1]))
            if max(text_score, phon) >= threshold:
                return True
        return False
