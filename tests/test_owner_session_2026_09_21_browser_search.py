"""Owner session 2026-09-21 16:03 (perfil dev-mente-v2): «Dime que es power automate» was answered
from the model's memory; «pasame un link…, o mejor abrelo en mi navegador» and «abre una busqueda de
power automate en mi navegador» looped on a yes/no clarification that «Si»/«Confirmo» never closed.
Now the question is the public lookup, and a search in the person's browser — explicit or with the
pronoun taking the thing just asked about — is the reviewed navigation to the search page."""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind import effect_intent

APPS = ("Spotify", "Discord", "Steam", "Google Chrome")
AVAILABLE = frozenset({"web.search", "browser.navigate", "browser.navigate.named", "app.open", "browser.control", "web.page.read", "memory.status"})
URL_SCHEMA = {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"], "additionalProperties": False}


@pytest.mark.parametrize("text", ["Dime que es power automate", "decime qué es Kubernetes", "explicame que es docker", "tell me what is Kubernetes"])
def test_tell_me_what_something_is_becomes_the_public_lookup(text: str) -> None:
    assert effect_intent._entity_lookup_query(text) is not None
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPS, ())
    assert intent is not None and intent.operations == ("web.search",)


@pytest.mark.parametrize("text", ["Dime qué es una GPU", "dime que hora es"])
def test_definitions_and_the_clock_are_not_lookups(text: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPS, ())
    assert intent is None or "web.search" not in intent.operations


@pytest.mark.parametrize(
    "text",
    [
        "abre una busqueda de power automate en mi navegador",
        "busca power automate en mi navegador",
        "abre power automate en el navegador",
        "open a search for power automate in my browser",
        "search power automate in the browser",
    ],
)
def test_a_search_in_the_persons_browser_is_the_reviewed_navigation_to_the_search_page(text: str) -> None:
    assert effect_intent._browser_search_query(text) == "power automate"
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPS, ())
    assert intent is not None and intent.operations == ("browser.navigate",)
    assert mind._ground_explicit_arguments("browser.navigate", text, URL_SCHEMA, APPS) == {"url": "https://www.bing.com/search?q=power+automate"}


@pytest.mark.parametrize("text", ["abre el navegador", "abre una pestaña en mi navegador", "abrí un link en mi navegador", "abre google.com en el navegador", "abre youtube en mi navegador"])
def test_sites_urls_and_the_browser_itself_keep_their_own_readers(text: str) -> None:
    assert effect_intent._browser_search_query(text) is None


def test_open_it_in_my_browser_takes_the_thing_asked_about_two_turns_back() -> None:
    history = [
        {"role": "user", "content": "Dime que es power automate"},
        {"role": "assistant", "content": "Power Automate es una herramienta de Microsoft…"},
        {"role": "user", "content": "De donde sacaste esa info?"},
        {"role": "assistant", "content": "De mi conocimiento interno."},
        {"role": "user", "content": "pasame un link para verlo yo mismo, o mejor abrelo en mi navegador"},
    ]
    text = history[-1]["content"]
    intent = effect_intent.browser_search_pronoun_intent(text, history, AVAILABLE)
    assert intent is not None and intent.operations == ("browser.navigate",)
    assert mind._ground_explicit_arguments("browser.navigate", text, URL_SCHEMA, APPS, history=history) == {"url": "https://www.bing.com/search?q=power+automate"}
    assert effect_intent.browser_search_pronoun_intent(text, [{"role": "user", "content": "hola"}], AVAILABLE) is None


MSG_AVAILABLE = frozenset({"message.send", "message.send.test", "message.recipient.resolve", "message.draft", "email.send", "web.search", "browser.navigate", "app.open", "memory.status"})


@pytest.mark.parametrize(
    ("text", "recipient", "body", "channel"),
    [
        ("Mandale un mensaje a vicho por wsp diciendole hola", "vicho", "hola", "whatsapp"),
        ("escribile a Lucas en whatsapp que llego tarde", "Lucas", "llego tarde", "whatsapp"),
        ("mandale hola a vicho por wsp", "vicho", "hola", "whatsapp"),
    ],
)
def test_a_message_for_a_person_in_a_named_client_is_looked_up_there_and_sent(text: str, recipient: str, body: str, channel: str) -> None:
    # 16:07 «Mandale un mensaje a vicho por wsp diciendole hola» went to the forced test destination and died
    # on an unverified draft; daily use sends to the named person in the named client (confirmed).
    assert effect_intent.message_request_named_client(text) == (recipient, body, channel)
    intent = effect_intent.resolve_explicit_effects(text, MSG_AVAILABLE, APPS, ())
    assert intent is not None and intent.operations == ("message.recipient.resolve", "message.send")
    catalog = effect_intent.build_game_catalog_index(())
    assert mind._explicit_arguments_from_evidence("message.recipient.resolve", text, APPS, catalog) == {"channel": channel, "recipient": recipient}
    observations = [{"operation": "message.recipient.resolve", "verified": True, "status": "completed", "result": {"recipientId": "id-1"}}]
    assert mind._verified_message_send_arguments(text, observations) == {"recipientId": "id-1", "text": body}


def test_mail_keeps_its_own_reader() -> None:
    assert effect_intent.message_request_named_client("mandale un correo a ana@gmail.com diciendo hola") is None


@pytest.mark.parametrize(
    "text",
    [
        "Que fue lo ultimo que me dijo vicho en wsp",
        "Puedes leer una conversacion mia de whatsapp, quiero que leas lo ultimo que me dicho vicho",
        "qué me escribió mamá",
        "leéme el último mensaje de Pedro",
    ],
)
def test_reading_a_chat_is_a_plain_limit_not_a_misunderstanding(text: str) -> None:
    assert effect_intent.chat_read_request(effect_intent._fold(text))
    assert effect_intent.known_unsupported_effect_request(text, MSG_AVAILABLE)


def test_sending_and_mail_are_not_the_chat_reading_limit() -> None:
    for text in ("mandale a vicho que hola", "leeme el correo de ana"):
        assert not effect_intent.known_unsupported_effect_request(text, MSG_AVAILABLE)


STREAM_AVAILABLE = frozenset({"streaming.play.named", "streaming.navigate", "app.open", "web.search", "memory.status"})


@pytest.mark.parametrize(("text", "service", "title"), [("ponme daredevil en disney", "disney_plus", "daredevil"), ("poneme daredevil en disney plus", "disney_plus", "daredevil"), ("ponme stranger things en netflix", "netflix", "stranger things")])
def test_ponme_a_title_on_a_streaming_service_plays_it(text: str, service: str, title: str) -> None:
    # 16:09 «ponme daredevil en disney» → «No puedo poner Daredevil en Disney»; «Quiero ver daredevil en disney» played.
    intent = effect_intent.resolve_explicit_effects(text, STREAM_AVAILABLE, ("Spotify",), ())
    assert intent is not None and intent.operations == ("streaming.play.named",)
    assert mind._explicit_arguments_from_evidence("streaming.play.named", text, ("Spotify",), effect_intent.build_game_catalog_index(())) == {"service": service, "title": title}


def test_do_it_after_a_cancelled_request_redoes_that_request() -> None:
    # 16:05 «Hazla, te dije que si mil veces» → «No pude entender bien lo que me dijiste».
    history = [
        {"role": "user", "content": "abre una busqueda de power automate en mi navegador"},
        {"role": "assistant", "content": "¿Quieres confirmar o cancelar…?"},
        {"role": "user", "content": "no"},
        {"role": "assistant", "content": "La búsqueda no se realizó porque la solicitud fue cancelada."},
        {"role": "user", "content": "Hazla, te dije que si mil veces"},
    ]
    text = history[-1]["content"]
    intent = effect_intent.redo_previous_request_intent(text, history, AVAILABLE, APPS, ())
    assert intent is not None and intent.operations == ("browser.navigate",)
    assert mind._ground_explicit_arguments("browser.navigate", text, URL_SCHEMA, APPS, history=history) == {"url": "https://www.bing.com/search?q=power+automate"}
    assert effect_intent.redo_previous_request_intent("dale", [{"role": "user", "content": "hola"}], AVAILABLE, APPS, ()) is None


# --- The owner's mother, 19:27–19:41 (same profile) -------------------------------------------------------------

@pytest.mark.parametrize("text", ["Si tuvieras un sueno, cual te gustaria que fuera", "Pero imagina que tuvieras uno, como seria?"])
def test_a_counterfactual_question_to_the_assistant_is_answered_not_refused(text: str) -> None:
    decision = mind._explicit_stable_no_effect_turn_decision(text, None)
    assert decision is not None and decision["conversation_kind"] == "knowledge"


@pytest.mark.parametrize(("text", "topic"), [("dame info de la migrana", "la migrana"), ("dame información sobre la migraña", "la migraña"), ("give me information about Mars", "Mars")])
def test_information_about_a_topic_is_the_public_lookup(text: str, topic: str) -> None:
    assert effect_intent._topic_research_query(text) == topic
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPS, ())
    assert intent is not None and intent.operations == ("web.search",)


def test_the_clock_and_this_pc_are_not_topics() -> None:
    for text in ("dame la hora", "dame info de mi pc"):
        assert effect_intent._topic_research_query(text) is None


@pytest.mark.parametrize("text", ["hazme un curriculum", "formato de curriculum en word", "buscame un formato de oficiio en word", "hazme un triangulo con las estaciones del ano", "buscame palabras con a"])
def test_drafted_text_and_word_games_are_written_in_the_conversation(text: str) -> None:
    assert effect_intent.conversation_only_content_request(text)
    decision = mind._explicit_stable_no_effect_turn_decision(text, None)
    assert decision is not None and decision["conversation_kind"] == "knowledge"


@pytest.mark.parametrize("text", ["escribe una nota llamada lista con el texto pan", "hazme una lista de compras y guardala en el escritorio", "crea una nota llamada sol con el texto hola", "hazme un curriculum y guardalo", "abre word"])
def test_notes_files_and_openings_are_not_drafting(text: str) -> None:
    assert not effect_intent.conversation_only_content_request(text)


@pytest.mark.parametrize(("text", "app"), [("ponme word", "Word"), ("ponme el word por favor", "Word"), ("poneme spotify", "Spotify")])
def test_ponme_an_installed_app_opens_it(text: str, app: str) -> None:
    apps = ("Word", "Excel", "Spotify", "Discord", "Steam")
    available = frozenset({"app.open", "media.play.query", "memory.status", "web.search", "audio.volume"})
    intent = effect_intent.resolve_explicit_effects(text, available, apps, ())
    assert intent is not None and intent.operations == ("app.open",)
    assert mind._explicit_arguments_from_evidence("app.open", text, apps, effect_intent.build_game_catalog_index(())) == {"appId": app}


def test_ponme_music_and_the_volume_keep_their_readers() -> None:
    apps = ("Word", "Spotify")
    available = frozenset({"app.open", "media.play.query", "memory.status", "audio.volume"})
    assert effect_intent.resolve_explicit_clarification_intent("ponme una cancion", available, apps).operations == ("media.play.query",)
    assert effect_intent.resolve_explicit_effects("pon el volumen al 40", available, apps, ()).operations == ("audio.volume",)


def test_a_plain_yes_to_a_yes_no_clarification_closes_the_base_request() -> None:
    objective = "buscame un formato de oficiio en word aclaracion confiable del usuario: si"
    decision = mind._explicit_stable_no_effect_turn_decision(objective, [{"role": "user", "content": "x"}], pending_clarification=True)
    assert decision is not None and decision["conversation_kind"] == "knowledge"
    assert mind._explicit_stable_no_effect_turn_decision("subí el volumen de spotify aclaracion confiable del usuario: 20", [{"role": "user", "content": "x"}], pending_clarification=True) is None
