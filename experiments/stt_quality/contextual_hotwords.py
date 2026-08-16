"""Deterministic Parakeet BPE compilation for contextual STT diagnostics."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import unicodedata


WORD_BOUNDARY = "\u2581"


def fold_surface(value: str) -> str:
    """Fold a human entity surface to the form used by Parakeet BPE pieces."""

    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )


def normalize_surface(value: str) -> str:
    """Return whitespace-separated alphanumeric words for BPE encoding."""

    words = [
        "".join(character for character in word if character.isalnum())
        for word in fold_surface(value.replace("_", " ")).split()
    ]
    return " ".join(word for word in words if word)


def load_bpe_pieces(tokens_path: Path) -> dict[str, tuple[str, ...]]:
    """Index ordinary BPE pieces by their first character."""

    by_initial: dict[str, list[str]] = {}
    for line in tokens_path.read_text(encoding="utf-8").splitlines():
        try:
            piece, token_id = line.rsplit(" ", 1)
        except ValueError:
            continue
        if (
            not token_id.isdigit()
            or not piece
            or piece.startswith("<")
            or any(character.isspace() for character in piece)
        ):
            continue
        by_initial.setdefault(piece[0], []).append(piece)
    return {
        initial: tuple(sorted(pieces, key=len, reverse=True))
        for initial, pieces in by_initial.items()
    }


def encode_surface(
    surface: str,
    pieces_by_initial: dict[str, tuple[str, ...]],
) -> tuple[str, ...] | None:
    """Return the minimum-piece exact BPE path for one entity surface."""

    normalized = normalize_surface(surface)
    if not normalized:
        return None
    value = WORD_BOUNDARY + WORD_BOUNDARY.join(normalized.split())
    best: list[tuple[str, ...] | None] = [None] * (len(value) + 1)
    best[0] = ()
    for index in range(len(value)):
        prefix = best[index]
        if prefix is None:
            continue
        for piece in pieces_by_initial.get(value[index], ()):
            if not value.startswith(piece, index):
                continue
            end = index + len(piece)
            candidate = (*prefix, piece)
            if best[end] is None or len(candidate) < len(best[end]):
                best[end] = candidate
    return best[-1]


def compile_hotwords(
    tokens_path: Path,
    terms: Iterable[str],
    *,
    maximum_terms: int = 64,
) -> tuple[str, tuple[dict[str, object], ...]]:
    """Compile unique authenticated terms into sherpa-onnx hotword paths."""

    if maximum_terms < 1:
        raise ValueError("contextual_hotword_maximum_terms_invalid")
    pieces_by_initial = load_bpe_pieces(tokens_path)
    paths: list[str] = []
    commitments: list[dict[str, object]] = []
    seen: set[str] = set()
    for term in terms:
        if len(paths) >= maximum_terms:
            break
        if not isinstance(term, str):
            raise TypeError("contextual_hotword_term_must_be_text")
        encoded = encode_surface(term, pieces_by_initial)
        if encoded is None:
            commitments.append({"surface": term, "encoded": False, "pieces": 0})
            continue
        path = " ".join(encoded)
        if path in seen:
            continue
        seen.add(path)
        paths.append(path)
        commitments.append(
            {"surface": term, "encoded": True, "pieces": len(encoded)}
        )
    return "/".join(paths), tuple(commitments)


def compile_stream_phrases(
    terms: Iterable[str],
    *,
    maximum_terms: int = 64,
) -> str:
    """Compile plain phrases for sherpa's ``modeling_unit=bpe`` stream API."""

    if maximum_terms < 1:
        raise ValueError("contextual_hotword_maximum_terms_invalid")
    phrases: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if len(phrases) >= maximum_terms:
            break
        if not isinstance(term, str):
            raise TypeError("contextual_hotword_term_must_be_text")
        phrase = normalize_surface(term)
        if phrase and phrase not in seen:
            seen.add(phrase)
            phrases.append(phrase)
    return "/".join(phrases)


def write_minimum_piece_vocab(tokens_path: Path, output_path: Path) -> None:
    """Derive a deterministic BPE vocab that selects minimum-piece paths.

    sherpa's in-memory hotword API always tokenizes phrases according to the
    configured modeling unit.  Parakeet ships ``tokens.txt`` but no original
    SentencePiece scores, so a score of -1 per valid piece deterministically
    reproduces minimum-piece segmentation without inventing any token.
    """

    if output_path.exists():
        raise FileExistsError("contextual_hotword_bpe_vocab_output_exists")
    pieces: list[str] = []
    seen: set[str] = set()
    for line in tokens_path.read_text(encoding="utf-8").splitlines():
        try:
            piece, token_id = line.rsplit(" ", 1)
        except ValueError:
            continue
        if not token_id.isdigit() or not piece or any(
            character.isspace() for character in piece
        ):
            continue
        if piece in seen:
            raise ValueError(f"contextual_hotword_duplicate_token:{piece}")
        seen.add(piece)
        pieces.append(piece)
    if not pieces:
        raise ValueError("contextual_hotword_empty_token_vocabulary")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(f"{piece}\t-1.0\n" for piece in pieces),
        encoding="utf-8",
        newline="\n",
    )
