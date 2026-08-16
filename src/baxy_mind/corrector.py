"""Corrección contextual conservadora del transcript de voz.

El corrector no reconoce comandos ni decide intenciones. Sólo puede recuperar
entidades cerradas que proceden del catálogo autenticado y exige evidencia
fonética/textual fuerte, un ganador único y margen suficiente. Si el ASR o el
catálogo no aportan esa evidencia, conserva literalmente el transcript.

La política de turnos recibe después el texto y conserva toda la autoridad
sobre conversación, acción y plan.
"""

from __future__ import annotations

import logging
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

logger = logging.getLogger(__name__)


# A textual match alone must be strong. The phonetic branch is useful for
# cross-language brand names, but is accepted only together with a meaningful
# textual overlap and a unique winner. All values are fixed algorithmic
# confidence floors, never phrase rules.
DEFAULT_TEXT_THRESHOLD = 82.0
PHONETIC_THRESHOLD = 85.0
MINIMUM_PHONETIC_TEXT_SCORE = 65.0
MINIMUM_LENGTH_RATIO = 0.64
MINIMUM_WINNER_MARGIN = 7.0
MAX_CATALOG_TERM_TOKENS = 4
MAX_CATALOG_TERM_CHARS = 96

# These are canonical JSON-schema field identifiers, not natural-language
# triggers. Values admitted here are closed provider/destination entities; an
# action enum such as media control state is deliberately not a correction
# candidate because post-ASR correction must never manufacture an effect.
_ENTITY_SCHEMA_FIELDS = frozenset({"provider", "service", "channel"})

# jellyfish es opcional: si falta, el corrector degrada a solo-texto (la rama
# fonética se desactiva, sin romper). Se carga una vez a nivel módulo.
try:
    import jellyfish as _jellyfish
    _HAS_PHONETIC = True
except Exception:  # pragma: no cover - depende del entorno
    _jellyfish = None
    _HAS_PHONETIC = False


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
    from .phonetic_es import spanish_metaphone as _spanish_metaphone
    _HAS_ES_PHONETIC = True
except Exception:  # pragma: no cover
    _spanish_metaphone = None
    _HAS_ES_PHONETIC = False


def _metaphone_es(s: str) -> str:
    """Spanish Metaphone de un string ya normalizado (sin espacios)."""
    if not _HAS_ES_PHONETIC or not s:
        return ""
    try:
        return _spanish_metaphone(s.replace(" ", ""))
    except Exception:
        return ""


def catalog_correction_terms(tools: object) -> tuple[str, ...]:
    """Derive correctable entities from authenticated argument contracts.

    Only closed enum/const values of entity-bearing schema fields are used.
    Descriptions, operation names and user phrases are intentionally ignored:
    they are useful retrieval evidence but are not safe post-ASR replacements.
    """

    if not isinstance(tools, list):
        return ()
    by_key: dict[str, str] = {}
    for tool in tools:
        function = tool.get("function") if isinstance(tool, dict) else None
        schema = function.get("parameters") if isinstance(function, dict) else None
        properties = schema.get("properties") if isinstance(schema, dict) else None
        if not isinstance(properties, dict):
            continue
        for field, contract in properties.items():
            if field not in _ENTITY_SCHEMA_FIELDS or not isinstance(contract, dict):
                continue
            values: list[Any] = []
            enum = contract.get("enum")
            if isinstance(enum, list):
                values.extend(enum)
            if "const" in contract:
                values.append(contract["const"])
            for value in values:
                if not isinstance(value, str):
                    continue
                display = " ".join(value.replace("_", " ").split())
                key = _normalise(display)
                compact = key.replace(" ", "")
                if (
                    not key
                    or not 4 <= len(compact) <= MAX_CATALOG_TERM_CHARS
                    or len(key.split()) > MAX_CATALOG_TERM_TOKENS
                    or not any(character.isalpha() for character in key)
                ):
                    continue
                by_key.setdefault(key, display)
    return tuple(by_key[key] for key in sorted(by_key))


def _boundary_punctuation(value: str) -> tuple[str, str]:
    start = 0
    end = len(value)
    while start < end and not value[start].isalnum():
        start += 1
    while end > start and not value[end - 1].isalnum():
        end -= 1
    return value[:start], value[end:]


class FuzzyCorrector:
    """Stateless catalog-entity corrector, reused across ASR turns."""

    def __init__(
        self,
        inventory: Iterable[str] | Mapping[str, Sequence[str]],
        threshold: float = DEFAULT_TEXT_THRESHOLD,
        *,
        minimum_margin: float = MINIMUM_WINNER_MARGIN,
    ) -> None:
        wake_words: tuple[str, ...] = ()
        if isinstance(inventory, Mapping):
            wake_words = tuple(inventory.get("wake_words", ()))
            terms = [
                value
                for category, values in inventory.items()
                if category != "wake_words"
                for value in values
            ]
        else:
            terms = list(inventory)
        self._wake_words = wake_words
        self._threshold = float(threshold)
        self._phonetic_threshold = PHONETIC_THRESHOLD
        self._minimum_margin = float(minimum_margin)
        unique: dict[str, str] = {}
        for raw in terms:
            if not isinstance(raw, str):
                continue
            original = " ".join(raw.split())
            normalized = _normalise(original)
            compact = normalized.replace(" ", "")
            if (
                not normalized
                or not 4 <= len(compact) <= MAX_CATALOG_TERM_CHARS
                or len(normalized.split()) > MAX_CATALOG_TERM_TOKENS
            ):
                continue
            unique.setdefault(normalized, original)
        self._normalized = tuple(
            (
                normalized,
                _metaphone(normalized),
                _metaphone_es(normalized),
                unique[normalized],
            )
            for normalized in sorted(unique)
        )

    def needs_contextual_support(self, transcript: str) -> bool:
        """Whether an acoustic n-best pass could safely resolve one entity.

        This does not change text. It identifies the narrow region where the
        primary ASR hypothesis has meaningful textual overlap and a strong,
        unique phonetic winner, but deliberately lacks the independent
        evidence required by :meth:`correct`.
        """

        if not transcript or not self._normalized:
            return False
        try:
            from rapidfuzz import fuzz
        except ImportError:
            return False

        tokens = transcript.split()
        ranked: list[tuple[float, str]] = []
        for start in range(len(tokens)):
            for size in range(
                1,
                min(MAX_CATALOG_TERM_TOKENS, len(tokens) - start) + 1,
            ):
                window_norm = _normalise(" ".join(tokens[start:start + size]))
                compact_window = window_norm.replace(" ", "")
                if len(compact_window) < 4:
                    continue
                window_meta = _metaphone(window_norm)
                window_meta_es = _metaphone_es(window_norm)
                for norm_item, meta_item, meta_item_es, original in self._normalized:
                    compact_item = norm_item.replace(" ", "")
                    length_ratio = min(
                        len(compact_window),
                        len(compact_item),
                    ) / max(len(compact_window), len(compact_item), 1)
                    if length_ratio < MINIMUM_LENGTH_RATIO:
                        continue
                    text_score = float(fuzz.ratio(window_norm, norm_item))
                    if text_score >= self._threshold or text_score < MINIMUM_PHONETIC_TEXT_SCORE:
                        continue
                    phonetic_scores: list[float] = []
                    if window_meta and meta_item:
                        phonetic_scores.append(float(fuzz.ratio(window_meta, meta_item)))
                    if window_meta_es and meta_item_es:
                        phonetic_scores.append(
                            float(fuzz.ratio(window_meta_es, meta_item_es))
                        )
                    phonetic_score = max(phonetic_scores, default=0.0)
                    if phonetic_score >= self._phonetic_threshold:
                        ranked.append((max(text_score, phonetic_score), original))

        if not ranked:
            return False
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        best_score, best_replacement = ranked[0]
        runner_up = next(
            (
                score
                for score, replacement in ranked[1:]
                if replacement != best_replacement
            ),
            0.0,
        )
        return best_score - runner_up >= self._minimum_margin

    def correct(
        self,
        transcript: str,
        *,
        alternatives: Sequence[str] = (),
    ) -> str:
        """Recover only uniquely supported catalog entities from ASR text.

        The primary hypothesis may win through strong textual evidence. A
        weaker text/strong phonetic match additionally requires independent
        support from an ASR alternative; without n-best evidence it abstains.
        """

        if not transcript or not self._normalized:
            return transcript
        try:
            from rapidfuzz import fuzz
        except ImportError as exc:
            logger.warning(
                "rapidfuzz unavailable; correction disabled: %s", exc,
            )
            return transcript

        tokens = transcript.split()
        alternative_keys: set[str] = set()
        for value in alternatives:
            if not isinstance(value, str):
                continue
            alternative_tokens = _normalise(value).split()
            for start in range(len(alternative_tokens)):
                for size in range(
                    1,
                    min(
                        MAX_CATALOG_TERM_TOKENS,
                        len(alternative_tokens) - start,
                    )
                    + 1,
                ):
                    alternative_keys.add(
                        " ".join(alternative_tokens[start:start + size])
                    )
        out: list[str] = []
        i = 0
        n = len(tokens)
        while i < n:
            ranked: list[tuple[float, int, str]] = []
            for ngram in range(1, min(MAX_CATALOG_TERM_TOKENS, n - i) + 1):
                if i + ngram > n:
                    continue
                window_tokens = tokens[i:i + ngram]
                window = " ".join(window_tokens)
                window_norm = _normalise(window)
                compact_window = window_norm.replace(" ", "")
                if len(compact_window) < 4:
                    continue
                window_meta = _metaphone(window_norm)
                window_meta_es = _metaphone_es(window_norm)
                for norm_item, meta_item, meta_item_es, original in self._normalized:
                    compact_item = norm_item.replace(" ", "")
                    length_ratio = min(
                        len(compact_window),
                        len(compact_item),
                    ) / max(len(compact_window), len(compact_item), 1)
                    if length_ratio < MINIMUM_LENGTH_RATIO:
                        continue
                    text_score = float(fuzz.ratio(window_norm, norm_item))
                    phonetic_scores: list[float] = []
                    if window_meta and meta_item:
                        phonetic_scores.append(
                            float(fuzz.ratio(window_meta, meta_item))
                        )
                    if window_meta_es and meta_item_es:
                        phonetic_scores.append(
                            float(fuzz.ratio(window_meta_es, meta_item_es))
                        )
                    phonetic_score = max(phonetic_scores, default=0.0)
                    if not (
                        text_score >= self._threshold
                        or (
                            norm_item in alternative_keys
                            and
                            text_score >= MINIMUM_PHONETIC_TEXT_SCORE
                            and phonetic_score >= self._phonetic_threshold
                        )
                    ):
                        continue
                    effective = max(text_score, phonetic_score)
                    ranked.append((effective, ngram, original))

            if not ranked:
                out.append(tokens[i])
                i += 1
                continue
            ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
            best_score, best_size, best_replacement = ranked[0]
            runner_up = next(
                (
                    score
                    for score, size, replacement in ranked[1:]
                    if replacement != best_replacement or size != best_size
                ),
                0.0,
            )
            if best_score - runner_up < self._minimum_margin:
                out.append(tokens[i])
                i += 1
                continue
            original_window = " ".join(tokens[i:i + best_size])
            if _normalise(original_window) == _normalise(best_replacement):
                out.extend(tokens[i:i + best_size])
            else:
                leading, _ = _boundary_punctuation(tokens[i])
                _, trailing = _boundary_punctuation(tokens[i + best_size - 1])
                out.append(f"{leading}{best_replacement}{trailing}")
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
        wake_words = self._wake_words
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
