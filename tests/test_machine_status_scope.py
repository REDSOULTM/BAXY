"""El cálculo de alcance de `system.status` como propiedad protegida.

`_machine_status_scopes` es la base de un candidato medido: aportar el `scope`
de forma determinista retiraría la mayor parte de los ~1,37 s que hoy cuesta el
grounding de argumentos en la ruta de acción. Antes de que ese candidato pueda
promoverse, la propiedad que lo hace seguro tiene que estar congelada: el
cálculo o nombra exactamente el alcance correcto o no nombra ninguno, pero
nunca nombra uno equivocado.

Estas pruebas no promueven el candidato; protegen su precondición.
"""

from __future__ import annotations

import pytest

from baxy_mind.effect_intent import (
    _fold,
    _machine_status_scopes,
    _system_status_domain,
)


# Enum cerrado del descriptor `system.status` del catálogo.
CATALOG_SCOPES = frozenset(
    {
        "battery",
        "cpu",
        "cpu_memory",
        "disk",
        "gpu_identity",
        "gpu_usage",
        "memory",
        "os",
        "os_memory",
        "summary",
    }
)

# Alcances internos del reconocedor y cómo se proyectan al enum del catálogo.
_INTERNAL_TO_CATALOG = {
    "battery": "battery",
    "cpu": "cpu",
    "memory": "memory",
    "disk": "disk",
    "os": "os",
    "gpu": "gpu_identity|gpu_usage",
}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("cuanta bateria queda", {"battery"}),
        ("¿Cuánta batería le queda al equipo?", {"battery"}),
        ("battery level please", {"battery"}),
        ("está cargando la batería", {"battery"}),
        ("cuantos nucleos tiene el procesador", {"cpu"}),
        ("current cpu load", {"cpu"}),
        ("cuanta ram tengo", {"memory"}),
        ("how much ram is in use right now", {"memory"}),
        ("cuanto espacio libre queda en el disco", {"disk"}),
        ("free disk space please", {"disk"}),
        ("espacio disponible en la unidad c", {"disk"}),
        ("que gpu tiene este equipo", {"gpu"}),
        ("cuanta vram se esta usando", {"gpu"}),
        ("dime la version de windows que tengo", {"os"}),
        ("which windows version am i running", {"os"}),
        # Parejas que el enum del catálogo sí mide en una sola lectura.
        ("revisa cpu y ram", {"cpu", "memory"}),
        ("qué windows tengo y cuánta ram tiene esta máquina", {"os", "memory"}),
    ],
)
def test_the_named_scope_is_exactly_the_measured_one(
    text: str,
    expected: set[str],
) -> None:
    assert _machine_status_scopes(_fold(text)) == expected


@pytest.mark.parametrize(
    "text",
    [
        # Adversariales: el dominio se rechaza, así que no hay alcance que
        # aportar y el grounding actual se conserva íntegro.
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
def test_an_adversarial_request_never_reaches_the_scope_calculation(
    text: str,
) -> None:
    assert _system_status_domain(_fold(text)) is False


@pytest.mark.parametrize(
    "text",
    [
        "cuanta bateria queda y cuanta ram tengo",
        "cuanto disco libre hay y cuanta bateria queda",
    ],
)
def test_a_combination_the_enum_cannot_measure_is_never_reduced_to_one_scope(
    text: str,
) -> None:
    named = _machine_status_scopes(_fold(text))
    assert len(named) >= 2
    assert named not in ({"cpu", "memory"}, {"os", "memory"})


def test_every_internal_scope_maps_into_the_closed_catalog_enum() -> None:
    for internal, catalog in _INTERNAL_TO_CATALOG.items():
        for name in catalog.split("|"):
            assert name in CATALOG_SCOPES, internal
