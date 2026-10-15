"""El parecido de significado entre el lugar que nombra un objetivo y los nombres de la vista (goal v3, P1 de
r5a/decision.md): «video library» en un Reproductor en español es «Biblioteca de videos», «firewall & network
protection» es «Firewall y protección de red» con el orden cambiado. El encoder E5 que la mente ya carga compara la
etiqueta (y los nombres que dio el traductor de etiquetas) con cada nombre de la vista; el resultado ordena lo que ve
el modelo y, sólo por encima de un umbral y con margen sobre el segundo, deja un clic sin modelo.

Funciones puras: el encoder se recibe como argumento (``encode(textos, prefix="query"|"passage")`` con filas
normalizadas) y un error o un plazo agotado del encoder vale como «sin parecidos», así que el comportamiento literal
no cambia cuando el encoder no responde. Sin aplicaciones: ``computer_use`` aplica además sus filtros de seguridad
(interruptores, quitar, cuenta, otra ventana, marco, contenido de mensajes).
"""

from __future__ import annotations

import re
import time
import unicodedata
from collections import OrderedDict
from typing import Any, Callable, Iterable

from ..operation_floor import floor_data

# Calibrado sobre los pares medidos de la pasada r3 (r5a/decision.md, e5-small, prefijos query/passage) y los pares
# español/inglés de la tabla de etiquetas puestos en vistas reales del banco: con estos dos valores el clic sin modelo
# acierta en todos los pares con llegada verificada y nunca se dispara en una vista sin el destino
# (tests/test_cu_v3_semejanza.py fija la medida). Por debajo, el parecido sólo ordena y se le muestra al modelo.
CLICK_SIMILARITY = 0.86
CLICK_MARGIN = 0.03
# Desde aquí un nombre se le muestra al modelo como «parecido al objetivo» y el reintento tras un rechazo lo nombra.
HINT_SIMILARITY = 0.84
SHOWN_SIMILAR = 5
# Un paso no gasta más que esto en el encoder (el presupuesto interactivo de la mente, router.py).
ENCODER_BUDGET_SECONDS = 0.75
# Un nombre de control es corto; un texto más largo es contenido y no se compara.
_LONGEST_NAME = 80
_CACHE_LIMIT = 4096


def comparable(name: object) -> bool:
    """Un nombre que ``similar_names`` compara: con texto y no más largo que un nombre de control."""

    text = str(name or "").strip()
    return bool(text) and len(text) <= _LONGEST_NAME

# Los actos que deshacen o repiten el último cambio llevan el nombre de ese cambio («Deshacer Insertar tabla»): se
# parecen al objetivo que lo pidió y nunca son su lugar (contracaso medido en t-form-3).
_UNDO_REDO_NAME = re.compile(r"^(?:deshacer|rehacer|repetir|undo|redo|repeat)\b")
# Los botones que cierran o cambian el tamaño de una ventana llevan el nombre de la ventana («Cerrar Reproductor
# multimedia», 0,811 para «video library» en v3-14): nunca son el lugar de un objetivo.
_WINDOW_FRAME_ACT = re.compile(r"^(?:cerrar|close|minimizar|minimize|maximizar|maximize|restaurar|restore)\b")
# Lo que separa un nombre de su extensión («Biblioteca de videos, 3 elementos», «Nueva diapositiva (Ctrl+M)»).
_EXTENSION_SEPARATORS = (" (", ",", ":", " -", " ·", " |")
# Un campo que busca por su nombre (P4): «Buscar:», «Buscar en documento», «Search», «Find», «Filtrar».
_SEARCH_FIELD_NAME = re.compile(r"^(?:buscar|busqueda|search|find|filtrar|filter)\b|\b(?:buscar|busqueda|search)\b")
# Un cuadro de texto enriquecido (Document) es un campo de búsqueda sólo si su nombre ENTERO es una etiqueta de
# búsqueda («Buscar:», «Search», «Find…»): un Document cuyo nombre sólo contiene la palabra («Búsqueda de empleo», el
# título de un documento; «Spotify – Buscar», el título de una ventana web) es el trabajo de la persona.
# Revisión 1 de r24b (B3): el patrón es dato (operation_floor.v1.json «computerUse.searchField.label»), que la App lee
# igual (OperationFloor.SearchLabelName) para no tomar un documento por buscador.
_SEARCH_LABEL = re.compile(floor_data()["computerUse"]["searchField"]["label"])


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    return " ".join("".join(character for character in text if not unicodedata.combining(character)).split())


def undoes_or_repeats(name: object) -> bool:
    """«Deshacer Insertar tabla», «Rehacer», «Repetir escritura», «Undo»: un acto sobre el último cambio."""

    return _UNDO_REDO_NAME.match(_fold(name)) is not None


def acts_on_the_window(name: object) -> bool:
    """«Cerrar Reproductor multimedia», «Minimizar», «Restore»: a button of the window's frame by what it does."""

    return _WINDOW_FRAME_ACT.match(_fold(name)) is not None


def names_a_search(name: object) -> bool:
    """Un nombre de campo que dice que busca («Buscar:», «Buscar en documento», «Search mail», «Find»)."""

    return _SEARCH_FIELD_NAME.search(_fold(name)) is not None


def is_search_label(name: object) -> bool:
    """El nombre entero es una etiqueta de búsqueda, sin más palabras («Buscar:», «Search», «Find…»)."""

    return _SEARCH_LABEL.match(_fold(name).strip().rstrip(":.…").strip()) is not None


def same_name_extension(left: object, right: object) -> bool:
    """Dos nombres que son el mismo nombre, o uno el otro con una extensión («Vídeo» y «Vídeo, 2 elementos»)."""

    a, b = _fold(left).strip(), _fold(right).strip()
    if not a or not b:
        return False
    if a == b:
        return True
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    return long.startswith(short) and any(long[len(short):].startswith(mark) for mark in _EXTENSION_SEPARATORS)


class EmbeddingCache:
    """Las filas del encoder por (prefijo, texto), compartidas entre pasos: los nombres de una ventana se repiten de un
    paso al siguiente, así que un paso sólo codifica los nombres nuevos. Acotada (la más vieja sale primero)."""

    def __init__(self, limit: int = _CACHE_LIMIT) -> None:
        self._rows: OrderedDict[tuple[str, str], Any] = OrderedDict()
        self._limit = max(1, int(limit))

    def get(self, prefix: str, text: str) -> Any:
        row = self._rows.get((prefix, text))
        if row is not None:
            self._rows.move_to_end((prefix, text))
        return row

    def put(self, prefix: str, text: str, row: Any) -> None:
        self._rows[(prefix, text)] = row
        self._rows.move_to_end((prefix, text))
        while len(self._rows) > self._limit:
            self._rows.popitem(last=False)

    def __len__(self) -> int:
        return len(self._rows)


def _rows(encode: Callable[..., Any], texts: list[str], prefix: str, cache: EmbeddingCache | None) -> list[Any]:
    missing = [text for text in dict.fromkeys(texts) if cache is None or cache.get(prefix, text) is None]
    fresh: dict[str, Any] = {}
    if missing:
        encoded = encode(missing, prefix=prefix)
        if len(encoded) != len(missing):
            raise ValueError("el encoder devolvió otra cantidad de filas")
        for text, row in zip(missing, encoded):
            fresh[text] = row
            if cache is not None:
                cache.put(prefix, text, row)
    return [fresh[text] if text in fresh else cache.get(prefix, text) for text in texts]  # type: ignore[union-attr]


def _dot(left: Any, right: Any) -> float:
    return float(sum(float(a) * float(b) for a, b in zip(left, right))) if not hasattr(left, "dot") else float(left.dot(right))


def similar_names(
    label: str,
    names: Iterable[object],
    encode: Callable[..., Any] | None,
    *,
    other_labels: Iterable[object] = (),
    cache: EmbeddingCache | None = None,
    budget_seconds: float = ENCODER_BUDGET_SECONDS,
) -> tuple[tuple[str, float], ...]:
    """Los nombres distintos de ``names`` con su parecido a la etiqueta (coseno E5, query contra passage), del más
    parecido al menos; con ``other_labels`` (los nombres que dio el traductor) cuenta el mayor parecido a cualquiera
    de ellas. Vacío sin encoder, sin etiqueta, cuando el encoder falla o cuando se pasó el presupuesto."""

    if encode is None:
        return ()
    queries = [text for text in dict.fromkeys(str(item).strip() for item in (label, *other_labels)) if text]
    shown = [
        text for text in dict.fromkeys(str(item).strip() for item in names if isinstance(item, str))
        if text and len(text) <= _LONGEST_NAME
    ]
    if not queries or not shown:
        return ()
    started = time.monotonic()
    try:
        query_rows = _rows(encode, queries, "query", cache)
        if time.monotonic() - started > budget_seconds:
            return ()
        name_rows = _rows(encode, shown, "passage", cache)
    except Exception:  # noqa: BLE001 - el encoder es consultivo: cualquier fallo es «sin parecidos»
        return ()
    if time.monotonic() - started > budget_seconds:
        return ()
    scored = [
        (name, round(max(_dot(row, query) for query in query_rows), 4))
        for name, row in zip(shown, name_rows)
    ]
    order = sorted(range(len(scored)), key=lambda position: (-scored[position][1], position))
    return tuple(scored[position] for position in order)


def runner_up(scored: tuple[tuple[str, float], ...], top: str) -> float:
    """El parecido del mejor nombre que no es ``top`` ni una extensión de él (0 si no hay otro)."""

    return max((score for name, score in scored if not same_name_extension(name, top)), default=0.0)


def semantic_pick(
    scored: tuple[tuple[str, float], ...],
    eligible: Callable[[str], bool],
    *,
    similarity: float = CLICK_SIMILARITY,
    margin: float = CLICK_MARGIN,
) -> str | None:
    """El nombre que se puede pulsar sin modelo: el más parecido, con parecido ≥ ``similarity``, con ``margin`` sobre
    el mejor nombre distinto (aunque ese otro no se pueda pulsar: un «Deshacer Insertar tabla» cerca de «Tabla» es
    duda) y que ``eligible`` acepta (los filtros de seguridad del motor). Si no, ninguno: decide el modelo."""

    if not scored:
        return None
    top, score = scored[0]
    if score < similarity or score - runner_up(scored, top) < margin:
        return None
    return top if eligible(top) else None


def similar_hints(
    scored: tuple[tuple[str, float], ...],
    eligible: Callable[[str], bool],
    *,
    floor: float = HINT_SIMILARITY,
    limit: int = SHOWN_SIMILAR,
) -> tuple[str, ...]:
    """Los nombres que se le muestran al modelo como parecidos al objetivo: parecido ≥ ``floor``, aceptados por
    ``eligible``, a lo sumo ``limit``, del más parecido al menos."""

    return tuple(name for name, score in scored if score >= floor and eligible(name))[: max(0, limit)]
