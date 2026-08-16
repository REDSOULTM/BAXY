"""El `scope` de `system.status` aportado sin modelo, y sus límites.

El seam es el mismo que ya usan los demás argumentos explícitos
(`_ground_explicit_arguments`): si el texto contiene el literal, no se le
pregunta al modelo. La propiedad que hace esto seguro y que aquí se congela es
que el reconocedor **o nombra el alcance correcto o no nombra ninguno**, nunca
uno equivocado. Core sigue validando schema, riesgo y confirmación.
"""

from __future__ import annotations

import pytest

from baxy_mind.__main__ import (
    _explicit_system_status_scope,
    _SYSTEM_STATUS_SCOPES,
)


@pytest.mark.parametrize(
    ("text", "scope"),
    [
        ("cuanta bateria queda", "battery"),
        ("¿Cuánta batería le queda al equipo?", "battery"),
        ("battery level please", "battery"),
        ("está cargando la batería", "battery"),
        ("che baxy fijate cuanta bateria le queda al notebook", "battery"),
        ("cuantos nucleos tiene el procesador", "cpu"),
        ("current cpu load", "cpu"),
        ("check el cpu usage porfa", "cpu"),
        ("cuanta ram tengo", "memory"),
        ("how much ram is in use right now", "memory"),
        ("ram disponible ahora mismo", "memory"),
        ("cuanto espacio libre queda en el disco", "disk"),
        ("free disk space please", "disk"),
        ("espacio disponible en la unidad c", "disk"),
        ("que gpu tiene este equipo", "gpu_identity"),
        ("what gpu is in this machine", "gpu_identity"),
        ("cuanta vram se esta usando", "gpu_usage"),
        ("show vram usage", "gpu_usage"),
        ("dime la version de windows que tengo", "os"),
        ("which windows version am i running", "os"),
        ("como anda la pc en general", "summary"),
        ("estado del sistema por favor", "summary"),
        ("how is my computer doing", "summary"),
        # Parejas que el enum del catálogo mide en una sola lectura.
        ("revisa cpu y ram", "cpu_memory"),
        ("qué windows tengo y cuánta ram tiene esta máquina", "os_memory"),
    ],
)
def test_an_unambiguous_scope_is_supplied_without_the_model(
    text: str,
    scope: str,
) -> None:
    supplied = _explicit_system_status_scope(text)
    assert supplied == {"scope": scope}
    assert scope in _SYSTEM_STATUS_SCOPES


@pytest.mark.parametrize(
    "text",
    [
        # Dos alcances que el enum no mide de una vez.
        "cuanta bateria queda y cuanta ram tengo",
        "cuanto disco libre hay y cuanta bateria queda",
        # GPU sin decir si se pregunta identidad o uso.
        "chequea la vram porfa",
        "muestra mi VRAM",
        # Clases adversariales: el dominio ya las rechaza.
        "a que temperatura esta la gpu",
        "que esta usando la vram ahora",
        "cuanta ram usa parekeet",
        "cuanta bateria tenia ayer",
        "cuanta ram tendria con 32 gb",
        "cuanta vram usara realmente",
        "cuanta bateria tiene mi auto",
        "how much vram does a 4090 have",
        "que gpu me recomiendas comprar",
        "por que mi gpu no se usa",
        "cuanta vram usa chrome",
    ],
)
def test_anything_ambiguous_keeps_the_existing_grounding(text: str) -> None:
    assert _explicit_system_status_scope(text) is None


def test_a_supplied_scope_always_belongs_to_the_closed_catalog_enum() -> None:
    texts = [
        "cuanta bateria queda",
        "revisa cpu y ram",
        "como anda la pc en general",
        "cuanta vram se esta usando",
        "dime la version de windows que tengo",
    ]
    for text in texts:
        supplied = _explicit_system_status_scope(text)
        assert supplied is not None
        assert supplied["scope"] in _SYSTEM_STATUS_SCOPES, text
