"""Pasada r15b v3-58: «abre edge y anda a la configuracion» → «busca cookies ahi en la configuracion».

The second request named «configuración», which is also the system's settings application; the engine typed
«cookies» into that application's search field (window «Configuración», process SystemSettings, the real view of the
run) and said «Listo, busqué «cookies» en «Configuración»». The place the request before went to inside the
conversation's application is that place again (``semantic.missions.follow_up_in_application``)."""

from baxy_mind.semantic import missions as semantic_missions

APPLICATIONS = (
    "Microsoft Edge",
    "Configuración",
    "Calculadora",
    "Paint",
    "Bloc de notas",
    "Explorador de archivos",
    "Opera GX",
)
OPERATIONS = ("mission.computer.use", "app.open")


def test_twin_v3_58_search_there_is_inside_the_place_gone_to() -> None:
    request = semantic_missions.follow_up_in_application(
        "busca cookies ahi en la configuracion",
        ["abre edge y anda a la configuracion"],
        OPERATIONS,
        APPLICATIONS,
    )

    assert request == "en Microsoft Edge, anda a la configuracion y busca cookies ahi"
    mission = semantic_missions.mission_request(request, APPLICATIONS)
    assert mission is not None
    assert [step.application for step in mission.steps] == ["Microsoft Edge", "Microsoft Edge"]
    assert [step.goal for step in mission.steps] == ["ir a configuracion", "buscar cookies"]


def test_twin_v3_58_english_keeps_the_conversation_application() -> None:
    request = semantic_missions.follow_up_in_application(
        "busca cookies ahi en la configuracion",
        ["abre edge y anda a la configuracion"],
        OPERATIONS,
        APPLICATIONS,
        english=True,
    )

    assert request is not None and request.startswith("in Microsoft Edge, ")


def test_counter_the_settings_application_alone_is_read_as_said() -> None:
    # No conversation before: «la configuración» is the installed application the person names.
    assert semantic_missions.follow_up_in_application(
        "busca cookies en la configuracion", [], OPERATIONS, APPLICATIONS,
    ) is None
    mission = semantic_missions.mission_request("busca cookies en la configuracion", APPLICATIONS)
    assert mission is not None and mission.application == "Configuración"


def test_counter_another_application_than_the_place_gone_to_is_read_as_said() -> None:
    # The request before went to «configuración» in Edge; «en Paint» names another application, read as said.
    assert semantic_missions.follow_up_in_application(
        "en paint selecciona el lapiz",
        ["abre edge y anda a la configuracion"],
        OPERATIONS,
        APPLICATIONS,
    ) is None


def test_counter_a_request_before_that_went_to_no_place() -> None:
    # «abre edge y busca gatos» went to no place: «la configuración» is the application named.
    assert semantic_missions.follow_up_in_application(
        "busca cookies ahi en la configuracion",
        ["abre edge y busca gatos"],
        OPERATIONS,
        APPLICATIONS,
    ) is None
