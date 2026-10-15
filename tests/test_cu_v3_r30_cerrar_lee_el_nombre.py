"""r30/r31 (tandas b2 y c28u, t2-c03 t2 «ya cierra configuracion que me esta laggeando el valorant»): the decider chose
app.close and ``window.resolve`` looked for an application called «ya cierra configuracion» (app_not_found, «No se cerró
la ventana de "ya cierra configuracion" porque no se encontró»). The application of an already decided window order
(close, focus, minimize, placing) is the one the order names: read whole first, then without the spoken link before it
and without the clause that tells why (``patterns.window_order_application``, the one place the four readings share).

r31 rewrote r30's ``close_order_alone`` / ``order_before_its_reason`` (revisión u1a): they cut at the first reason word
without trying the whole order («cierra Just Cause 3» → «cierra Just»), served the close only, and read a fourth list of
reason openers. The tests of those two helpers are rewritten here over what production runs."""

from __future__ import annotations

import itertools
import re

import pytest

from baxy_mind import effect_intent
from baxy_mind.planner import validate_json_schema_instance
from baxy_mind.semantic import apps, arguments, dialogue, lexicon, missions, patterns, windows
from baxy_mind.semantic.normalize import fold
from baxy_mind import plan_shape
from baxy_mind import argument_grounding

# Test data: a catalog with names that hold a word a reason may open with («cause», «because», «que», «so», «of»).
_APPLICATIONS = (
    "Configuración", "Calculadora", "Discord", "VALORANT", "Bloc de notas", "Visual Studio Code", "Word", "Excel",
    "Spotify", "Steam", "Reloj", "Opera GX", "Google Chrome", "Just Cause 3", "Just Dance", "Because Music",
    "Call of Duty", "Qué Pasa", "Netflix", "Paint 3D",
)
_AVAILABLE = (
    "app.close", "app.open", "window.resolve", "window.active", "window.focus", "window.minimize", "window.snap",
    "media.control", "mission.computer.use",
)
_RESOLVE_SCHEMA = {
    "type": "object",
    "properties": {
        "applicationName": {"type": "string", "maxLength": 256},
        "byTitle": {"type": "boolean"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
        "offset": {"type": "integer", "minimum": 0},
        "process": {"type": "string", "maxLength": 260},
    },
    "required": [],
    "additionalProperties": False,
}


def _resolved(evidence: str) -> object:
    return arguments._explicit_arguments_from_evidence("window.resolve", evidence, _APPLICATIONS)


@pytest.mark.parametrize(
    ("evidence", "application"),
    [
        ("ya cierra configuracion que me esta laggeando el valorant", "Configuración"),
        # The measured phrase in chat writing (revisión u1a, row 17).
        ("ya cierra configuracion q me esta laggeando el valorant", "Configuración"),
        ("ya cierra configuracion", "Configuración"),
        ("ya cierra discord", "Discord"),
        ("cierra discord porfa", "Discord"),
        ("cierra discord que me lagea", "Discord"),
        ("cierra discord k me lagea", "Discord"),
        ("ya cierra discord xq me lagea", "Discord"),
        ("close discord cuz it lags", "Discord"),
        ("close discord because valorant is lagging", "Discord"),
        ("close discord so I can focus", "Discord"),
        ("oye, cierra el Bloc de notas porque ya terminé", "Bloc de notas"),
        ("ok cierra el bloc de notas", "Bloc de notas"),
        ("bueno cierra discord", "Discord"),
        ("okey cierra discord", "Discord"),
        ("bien cierra discord", "Discord"),
        ("perfecto cierra discord", "Discord"),
        ("ya pues cierra discord", "Discord"),
        ("vale y ahora cierra spotify porque me distrae", "Spotify"),
        ("cierra discord que me lagea porfa", "Discord"),
        ("cierra discord porfa, que me lagea", "Discord"),
        # The order as the readers already read it alone keeps its reading.
        ("cierra configuracion", "Configuración"),
        ("Cierra la ventana de Configuración.", "Configuración"),
        ("Cierra la Calculadora.", "Calculadora"),
        # An application that is not open is still looked for by its name: the Core answers that no window was found.
        ("ya cierra steam que ya no lo uso", "Steam"),
    ],
)
def test_the_application_of_a_close_is_the_one_its_order_names(evidence: str, application: str) -> None:
    assert _resolved(evidence) == {"applicationName": application}


@pytest.mark.parametrize(
    ("evidence", "application"),
    [
        # Revisión u1a, finding 1: the whole order is read before anything is cut, so a name that holds a word a reason
        # opens with keeps its reading (r30 read «cierra Just» and «cierra»).
        ("cierra Just Cause 3", "Just Cause 3"),
        ("cierra Because Music", "Because Music"),
        ("cierra Qué Pasa", "Qué Pasa"),
        ("cierra Call of Duty", "Call of Duty"),
        ("cierra just dance", "Just Dance"),
        ("cierra Visual Studio Code", "Visual Studio Code"),
        ("minimiza just cause 3", "Just Cause 3"),
        ("minimiza because music", "Because Music"),
        ("switch to just cause 3", "Just Cause 3"),
        ("bring Call of Duty to the front", "Call of Duty"),
        ("pon just cause 3 a la derecha", "Just Cause 3"),
        ("pon because music a la izquierda", "Because Music"),
        # With a reason after such a name, the longest order that reads wins: the name keeps its own «cause», «que».
        ("cierra el just cause porque se pegó", "Just Cause 3"),
        ("ya cierra because music que me distrae", "Because Music"),
        ("ya cierra qué pasa que me distrae", "Qué Pasa"),
        ("cierra call of duty so i can work", "Call of Duty"),
        ("ya minimiza because music porque me distrae", "Because Music"),
        ("ok enfoca just cause 3 because i need it", "Just Cause 3"),
    ],
)
def test_a_name_that_holds_a_reason_word_is_read_whole(evidence: str, application: str) -> None:
    assert _resolved(evidence) == {"applicationName": application}


def test_an_order_the_readers_read_whole_is_never_read_from_a_cut() -> None:
    # What 298cb591a read from the whole order is what is read now, whatever the cuts would give.
    for evidence in (
        "cierra Just Cause 3", "cierra Because Music", "cierra Qué Pasa", "cierra Call of Duty", "cierra discord",
        "enfoca chrome", "trae chrome al frente", "focus chrome", "minimiza discord", "minimiza because music",
        "pon chrome a la izquierda", "put chrome on the left", "pon because music a la izquierda",
        "Cierra la ventana de Configuración.",
    ):
        whole = (
            effect_intent.resolve_application_snap_name(evidence, _APPLICATIONS)
            or effect_intent.resolve_application_close_name(evidence, _APPLICATIONS)
            or effect_intent.resolve_application_focus_name(evidence, _APPLICATIONS)
            or effect_intent.resolve_application_minimize_name(evidence, _APPLICATIONS)
        )
        assert whole is not None, evidence
        assert patterns.window_order_application(evidence, _APPLICATIONS) == whole, evidence


_ORDERS = (
    "cierra {}", "cierra el {}", "close {}", "enfoca {}", "focus {}", "trae {} al frente", "bring {} to the front",
    "minimiza {}", "minimize {}", "pon {} a la izquierda", "put {} on the left",
)
_LINKS = ("", "oye ", "ya ", "okey ", "bro ", "ok, ", "bueno ", "vale y ahora ", "and now ")
_REASONS = (
    "", " porque me distrae", " que me tapa el juego", " q me tapa el juego", " xq me lagea", " cuz it lags",
    " because valorant is lagging", " so I can focus", " ya que termine",
)


def test_the_four_window_orders_read_their_application_with_a_link_and_a_reason() -> None:
    # Revisión u1a, finding 2: one reading for close, focus, minimize and placing, in Spanish, English and Spanglish.
    unread = [
        (evidence, read)
        for order, link, reason, (said, application) in itertools.product(
            _ORDERS, _LINKS, _REASONS, (("discord", "Discord"), ("chrome", "Google Chrome")),
        )
        for evidence in (f"{link}{order.format(said)}{reason}",)
        for read in (_resolved(evidence),)
        if read != {"applicationName": application}
    ]
    assert unread == []


@pytest.mark.parametrize(
    "evidence",
    [
        # «que no…» also says which one («la ventana que no responde»): it is no reason opener, and the name is not
        # read from an order whose end nobody can tell.
        "ya cierra steam que no lo uso",
        "cierra la ventana que no responde",
        "cierra la ventana que dice error",
        "bro enfoca chrome que no lo veo",
        # What BAXY did for the person says which one too (revisión u1a, finding 6).
        "cierra el Chrome que me abriste recién",
        "cierra el discord que me mandaste",
        "minimiza el chrome q me abriste",
    ],
)
def test_what_may_say_which_one_is_not_cut_as_a_reason(evidence: str) -> None:
    read = _resolved(evidence)

    assert read is None or "applicationName" not in read


@pytest.mark.parametrize(
    "evidence",
    [
        "ciérrala",
        "ya ciérrala",
        "cerralo",
        "close it",
        "cierra eso",
        # A pointer with a reason names nothing, whatever the reason names (2026-09-22: never the window in front).
        "ya ciérrala que me lagea",
        "ciérrala que me esta laggeando el valorant",
        "cierra eso que me lagea discord",
        "close it cuz discord lags",
        "cierra esta ventana que me lagea el discord",
        "close this window because discord is lagging",
        "pon esta ventana a la izquierda que me tapa",
        "minimiza la ventana que me molesta",
        "ya minimiza todo",
        # An order taken back, denied or said for later or for another device is no order to read a name from.
        "cierra discord que me lagea o mejor no",
        "cierra discord que me lagea pero no lo cierres todavia",
        "cierra discord o mejor no porque lo estoy usando",
        "no cierres discord porque lo uso",
        "ya no cierres discord",
        "mañana cierra discord que me lagea",
        "cierra netflix que me quedó abierto en el celular",
        # Several applications, a name only part of two, and what is no window order at all.
        "cierra Word y Excel porque ya terminé",
        "cierra just",
        "cierra just porque se pegó",
        "right click en discord",
        "bien hecho, cierra",
        # Re-revisión u2: «cause» is no reason opener of a window order (a name holds it); as at 298cb591a.
        "close Notepad cause I'm done",
    ],
)
def test_an_order_that_names_no_application_reads_none(evidence: str) -> None:
    assert patterns.window_order_application(evidence, _APPLICATIONS) is None
    read = _resolved(evidence)
    assert read is None or "applicationName" not in read


@pytest.mark.parametrize("evidence", ["ciérrala", "ya ciérrala", "cerralo", "close it", "cierra eso", "ya ciérrala que me lagea"])
def test_a_pointer_is_read_as_the_window_in_front_by_the_plan(evidence: str) -> None:
    # Revisión u1a, finding 9: r30 asserted ``closes_the_active_window(close_order_alone(x))``, a composition
    # production never ran. The plan (``__main__._expand_effect_plan``) is where the pointer is judged: its close
    # reads the window in front first (window.active), where the M19/M118 guard judges it.
    assert plan_shape._expand_effect_plan(("app.close",), (evidence,))[0][0] == "window.active"


@pytest.mark.parametrize(
    ("text", "decided", "application"),
    [
        ("ya cierra configuracion que me esta laggeando el valorant", "app.close", "Configuración"),
        ("ya cierra configuracion q me esta laggeando el valorant", "app.close", "Configuración"),
        ("ya minimiza discord", "window.minimize", "Discord"),
        ("ok minimiza spotify que me tapa", "window.minimize", "Spotify"),
        ("ya enfoca chrome", "window.focus", "Google Chrome"),
        ("okey pon chrome a la izquierda que me tapa el word", "window.snap", "Google Chrome"),
        ("cierra Just Cause 3", "app.close", "Just Cause 3"),
    ],
)
def test_the_whole_route_from_the_persons_text_to_the_arguments(text: str, decided: str, application: str) -> None:
    # The operation is the one the readers read in the person's text; where they read none (the decider chose it in
    # the measured turn), the decided one with the person's text as its evidence. Then the plan and its arguments.
    read = effect_intent.resolve_explicit_effects(text, _AVAILABLE, _APPLICATIONS)
    operations, evidence = (tuple(read.operations), tuple(read.evidence)) if read is not None else ((decided,), (text,))
    assert operations == (decided,)

    steps = plan_shape._explicit_plan_skeleton(operations, evidence)["steps"]

    assert [step["operation"] for step in steps] == ["window.resolve", decided]
    grounded = argument_grounding._ground_explicit_arguments("window.resolve", steps[0]["purpose"], _RESOLVE_SCHEMA, _APPLICATIONS)
    assert grounded == {"applicationName": application}
    assert validate_json_schema_instance(grounded, _RESOLVE_SCHEMA)
    assert argument_grounding._normalize_grounded_operation_arguments("window.resolve", grounded, text) == grounded


@pytest.mark.parametrize(
    ("request_said", "order"),
    [
        ("cierra configuracion que me esta laggeando el valorant", "cierra configuracion"),
        ("cierra discord porque me distrae", "cierra discord"),
        ("close discord cuz it lags", "close discord"),
        ("cierra discord, que me lagea", "cierra discord"),
        ("cierra discord q me lagea", "cierra discord"),
        ("close discord so I can focus", "close discord"),
        ("cierra esta ventana que me lagea", "cierra esta ventana"),
        # One cut, at the last clause of why: what it leaves is never shortened again.
        ("cierra el just cause porque se pegó", "cierra el just cause"),
        ("cierra just cause 3 porque se pegó", "cierra just cause 3"),
        # Revisión u2, finding 2: the rest of a name is no clause («cause 3», «since dawn», «cause»).
        ("cierra just cause 3", None),
        ("cierra just cause 4", None),
        ("minimiza lost cause", None),
        ("enfoca dead since dawn", None),
        ("cierra el just cause por favor", None),
        ("cierra just cause ya mismo", None),
        ("close just cause right now", None),
        ("cierra just cause que se pegó", None),
        # The cost, accepted: «cause» opens no reason of a window order, so this one reads as at 298cb591a.
        ("close notepad cause i'm done", None),
        ("cierra discord", None),
        ("cierra discord porfa", None),
        # «que» alone and what BAXY did say which one; a reason that takes the order back is no reason.
        ("cierra la ventana que dice error", None),
        ("cierra el chrome que me abriste recién", None),
        ("cierra discord que me lagea pero no lo cierres todavia", None),
        # A purpose with BAXY as its subject is another order, never a reason.
        ("abre chrome para que busques vuelos a lima", None),
        ("", None),
    ],
)
def test_the_order_ends_where_its_reason_begins(request_said: str, order: str | None) -> None:
    assert dialogue.order_before_its_reason(request_said) == order


@pytest.mark.parametrize(
    ("evidence", "catalog"),
    [
        # Revisión u2, finding 2: the application named is not in the catalog and another shares its first word. A cut
        # inside the name never names that other one (r31 first version: «cierra just» → Just Dance).
        ("cierra just cause 3", ("Just Dance", "Discord")),
        ("ya cierra just cause 3", ("Just Dance", "Discord")),
        ("cierra just cause 3 porque se pegó", ("Just Dance", "Discord")),
        ("cierra just cause 4", ("Just Cause 3", "Discord")),
        ("minimiza lost cause", ("Lost Ark", "Discord")),
        ("enfoca dead since dawn", ("Dead Cells", "Discord")),
        # Re-revisión u2: the same with an ordinary tail after the name. «cause», «since» and «cos» open no reason of
        # a window order: a name holds them.
        ("cierra el just cause por favor", ("Just Dance", "Discord")),
        ("cierra just cause ya mismo", ("Just Dance", "Discord")),
        ("close just cause right now", ("Just Dance", "Discord")),
        ("cierra just cause que se pegó", ("Just Dance", "Discord")),
        ("cierra just cause ahora porfa", ("Just Dance", "Discord")),
        ("cierra just cause definitive edition", ("Just Dance", "Discord")),
        ("minimiza dead since the beginning", ("Dead Cells", "Discord")),
    ],
)
def test_a_cut_inside_a_name_the_catalog_lacks_names_no_other_application(evidence: str, catalog: tuple) -> None:
    assert patterns.window_order_application(evidence, catalog) is None
    read = arguments._explicit_arguments_from_evidence("window.resolve", evidence, catalog)
    assert read is None or "applicationName" not in read


_PAIR_APPLICATIONS = (
    "Discord", "Word", "Excel", "Spotify", "Steam", "Google Chrome", "Just Cause 3", "Dead Since Dawn",
    "Life As It Is", "Microsoft Edge", "Bloc de notas",
)


@pytest.mark.parametrize(
    ("text", "windows_placed"),
    [
        # Revisión u2, finding 1: the second name of a pair keeps the reason word it holds. As 298cb591a read them.
        ("pon chrome y just cause 3 lado a lado", (("Google Chrome", "left"), ("Just Cause 3", "right"))),
        ("pon el word y el just cause 3 uno al lado del otro", (("Word", "left"), ("Just Cause 3", "right"))),
        ("put chrome and just cause 3 side by side", (("Google Chrome", "left"), ("Just Cause 3", "right"))),
        ("pon lado a lado chrome y just cause 3", (("Google Chrome", "left"), ("Just Cause 3", "right"))),
        ("divide la pantalla entre chrome y just cause 3", (("Google Chrome", "left"), ("Just Cause 3", "right"))),
        ("pon steam y dead since dawn lado a lado", (("Steam", "left"), ("Dead Since Dawn", "right"))),
        ("pon spotify y life as it is lado a lado", (("Spotify", "left"), ("Life As It Is", "right"))),
        ("pon el word y el edge uno al lado del otro", (("Word", "left"), ("Microsoft Edge", "right"))),
    ],
)
def test_two_windows_side_by_side_read_as_before(text: str, windows_placed: tuple) -> None:
    pairs = effect_intent.application_snap_pairs(text, _PAIR_APPLICATIONS)

    assert pairs is not None and tuple(pair[:2] for pair in pairs) == windows_placed
    decided = effect_intent.resolve_explicit_effects(text, (*_AVAILABLE, "streaming.play.named", "web.search"), _PAIR_APPLICATIONS)
    assert decided is not None and tuple(decided.operations) == ("window.snap",)


@pytest.mark.parametrize(
    "text",
    [
        # What ends a placing is what ended it before r31; these read nothing then and read nothing now.
        "pon el word y el edge uno al lado del otro que los necesito",
        "pon word y edge lado a lado que me sirve",
        "pon chrome a la izquierda que me tapa el word",
    ],
)
def test_a_placing_gains_no_reason_opener(text: str) -> None:
    assert effect_intent.application_snap_pairs(text, _PAIR_APPLICATIONS) is None
    assert not windows.two_things_side_by_side("tú y yo lado a lado que me encanta")
    assert not windows.two_things_side_by_side("you and me side by side cause i love it")


@pytest.mark.parametrize(
    ("said", "title"),
    [
        # Revisión u2, finding 3: a title said after its service keeps «as it», «as i», «pues», «BC». As 298cb591a.
        ("pon en netflix As Good as It Gets", "As Good as It Gets"),
        ("pon en netflix Just As I Am", "Just As I Am"),
        ("pon en netflix Take Me As I Am", "Take Me As I Am"),
        ("pon en netflix Do As I Say", "Do As I Say"),
        ("pon en netflix Life As It Is", "Life As It Is"),
        ("pon en netflix 10,000 BC", "10,000 BC"),
        ("pon en netflix One Million Years BC", "One Million Years BC"),
        ("pon en netflix Y pues nada", "Y pues nada"),
        ("play on netflix Good as I Been to You", "Good as I Been to You"),
        ("pon en netflix Porque te vas", "Porque te vas"),
        ("pon en netflix Since U Been Gone", "Since U Been Gone"),
        ("pon en disney plus bluey pues la quieren ver los chicos", "bluey pues la quieren ver los chicos"),
        ("pon en netflix dark cuz i like it", "dark cuz i like it"),
        # … and still ends where it did (M156).
        ("pone en disney plus intensamnete 2 q la quieren ver los chicos", "intensamnete 2"),
        ("pon en netflix dark porque me la recomendaron", "dark"),
        ("pon en netflix dark que me la recomendaron", "dark"),
        ("pon en netflix dark so that we can watch it", "dark"),
    ],
)
def test_a_title_said_after_its_service_reads_as_before(said: str, title: str) -> None:
    read = arguments._explicit_arguments_from_evidence("streaming.play.named", said)

    assert read is not None and read["title"] == title


@pytest.mark.parametrize(
    ("said", "closes_a_pronoun"),
    [
        ("ciérralo", True), ("ya, ciérrala", True), ("okey ciérrala", True), ("oye ciérrala", True), ("ok close that", True),
        # Revisión u2, finding 4: said after «abre X», «después lo cierras» is «not yet», never a close now; a vocative
        # that is a common noun reads no third person («hermano la cierra»). As 298cb591a: none is the bare pronoun.
        ("después lo cierras", False), ("luego la cierras", False), ("luego ciérralo", False), ("después ciérralo", False),
        ("ok luego lo cierras", False), ("también ciérralo", False), ("also close it", False), ("bro ciérralo", False),
        ("mira ciérralo", False), ("hermano la cierra", False), ("viejo lo cierra", False), ("socio la cierra", False),
        ("mate la cierra", False), ("right click en discord", False),
    ],
)
def test_the_bare_close_pronoun_reads_as_before(said: str, closes_a_pronoun: bool) -> None:
    assert apps.bare_close_pronoun(fold(said))[0] is closes_a_pronoun


@pytest.mark.parametrize(
    ("rest", "only_a_reason"),
    [
        ("que me esta laggeando el valorant", True),
        ("porque me lagea", True), ("xq me lagea", True), ("cuz it lags", True), ("as i said", True), ("pues me lagea", True),
        ("que ya no lo uso", True),
        # Revisión u2, finding 5: «que me insiste…» is a reason as it was (no rule of «-iste» here) …
        ("que me insiste con las notificaciones", True),
        ("que me abriste recién", True),
        # … and a purpose is no reason: the order said back never drops «para que busques…» in silence.
        ("para que busques vuelos a lima", False), ("pa que busques vuelos", False),
        ("so that you can open steam", False), ("so i can focus", False), ("so we can talk", False),
        # Chat writing was never the said-back's list.
        ("q me esta laggeando el valorant", False), ("k me lagea", False), ("bc it lags", False), ("coz it lags", False),
        ("que dice error", False), ("que no lo uso", False), ("que me lagea o mejor no", False),
    ],
)
def test_what_follows_the_order_said_back_reads_as_before(rest: str, only_a_reason: bool) -> None:
    assert dialogue.only_gives_a_reason(rest) is only_a_reason


def test_each_reader_ends_at_its_own_view_of_the_one_list_and_gains_nothing() -> None:
    # Revisión u2: one source (``lexicon.REASON_OPENERS``), a declared view per reader, each the set it read at
    # 298cb591a — written out here, so a word added to the list reaches no reader unseen.
    said_back = {
        "porque", "porq", "pq", "xq", "pues", "ya que", "puesto que", "dado que", "que me", "que nos", "que te",
        "que ya no", "because", "since", "cause", "cuz", "cos", "as it", "as i",
    }
    chat_que = {f"{que} {clitic}" for que in ("q", "k") for clitic in ("me", "nos", "te")}
    title = {
        "porque", "porq", "pq", "xq", "ya que", "pa que", "para que", "because", "cause", "since", "que me", "que te",
        "que nos", *chat_que,
    }
    assert lexicon.REASONS_SAID_BACK == said_back
    assert lexicon.REASONS_AFTER_A_TITLE == title
    assert lexicon.REASONS_AFTER_A_PLACING == {"porque", "because"}
    # The window order is the new reader: r30's list without the openers a name also holds («just cause», «dead since
    # dawn», «as it is»; re-revisión u2), plus the chat «q/k me» of the measured phrase and «so I…» (encargo R31-U2).
    in_names = {"cause", "since", "cos", "as it", "as i"}
    assert lexicon.REASONS_OF_A_WINDOW_ORDER == (said_back - in_names) | chat_que | {"so i"}
    views = (
        lexicon.REASONS_SAID_BACK, lexicon.REASONS_AFTER_A_TITLE, lexicon.REASONS_AFTER_A_PLACING,
        lexicon.REASONS_OF_A_WINDOW_ORDER,
    )
    assert all(view <= lexicon.REASON_OPENERS for view in views)
    assert set().union(*views) == lexicon.REASON_OPENERS
    for view in views:
        for opener in view:
            assert re.fullmatch(lexicon.reason_opening(view), opener), opener
    # The placing tail is the six openings of before: «so», «so that», «para», «para que», «porque», «because».
    for opening in ("so", "so that", "para", "para que", "porque", "because"):
        assert re.fullmatch(windows._PLACING_REASON_TAIL, f" {opening} los veo"), opening
    for opening in ("que me", "since", "cause", "pues", "as it"):
        assert not re.fullmatch(windows._PLACING_REASON_TAIL, f" {opening} los veo"), opening


def test_what_ends_a_song_is_narrower_and_tied_to_the_list() -> None:
    # ``_NAMED_CLAUSE_END`` stays apart for a real reason: what plays is free text, and songs are called «Since U
    # Been Gone», «As It Was», «Que me quedes tú». Its two reason words are the list's.
    for word in ("porque", "because"):
        assert word in lexicon.REASON_OPENERS
        assert arguments._NAMED_CLAUSE_END.search(f"cumbia {word} si") is not None
    for title in ("since u been gone", "as it was", "que me quedes tu", "la cancion cause i love you"):
        assert arguments._NAMED_CLAUSE_END.search(title) is None, title


def test_one_list_of_spoken_links_and_the_view_of_the_bare_pronoun() -> None:
    # Every word the mission reader (``missions.without_spoken_link``) or the request envelope drops before an order
    # is a spoken link of the one list: the window order reads the same with it (r30: «okey cierra discord» read
    # nothing while «okey ciérrala» did).
    link = re.compile(rf"(?:{lexicon.SPOKEN_LINK})(?:[\s,]+(?:{lexicon.SPOKEN_LINK}))*", re.IGNORECASE)
    dropped = (
        *lexicon.ACKNOWLEDGEMENTS, "ya", "ahora", "luego", "después", "entonces", "también", "y ahora", "and now",
        "then", "also", "vale y ahora", "ok, también", "oye", "bro", "okey", "bien", "perfecto", "pues", "alright",
    )
    for said in dropped:
        assert link.fullmatch(fold(said)), said
        assert patterns.window_order_application(f"{said} cierra discord", _APPLICATIONS) == "Discord", said
        assert patterns.window_order_application(f"{said} minimiza discord", _APPLICATIONS) == "Discord", said
    for said in ("ok", "vale y ahora", "and now", "ok, también"):
        assert missions.without_spoken_link(f"{said} cierra discord") == "cierra discord", said
    # The bare pronoun keeps the fillers M96 measured, a declared view of the list: it gains none.
    pointer = {
        "ya", "ok", "okay", "okey", "vale", "dale", "bueno", "listo", "bien", "perfecto", "ahora", "entonces", "y",
        "pues", "oye", "che", "baxy", "now", "alright", "right", "then", "so", "and", "hey", "por favor", "porfa",
        "please",
    }
    assert pointer <= lexicon.SPOKEN_LINKS
    for word in lexicon.SPOKEN_LINKS:
        assert apps.bare_close_pronoun(f"{word} cierrala")[0] is (word in pointer), word
    # A link is dropped only before the head a reader anchors on: free text keeps its words.
    assert missions.without_spoken_link("right click en discord") == "right click en discord"
    assert patterns.window_order_application("right click en discord", _APPLICATIONS) is None
