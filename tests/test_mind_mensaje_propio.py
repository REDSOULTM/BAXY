"""Aid «message_text», MSG1 (owner, 2026-11-14 22:25: «si yo le digo, dile que llego a las 10, y el modelo literal
escribe que llego a las 10»; hub/int36h sent «Llegué a las 10.» 2 of 3 and «send me the link to the game»). The text of a
message or an email is written by the model in a closed question apart from the decision, as the person would write
it; a number, hour, date, name or address it brings that nobody gave goes back to it once, and dictated words go as
the decision wrote them."""
import json
from pathlib import Path

from baxy_mind import message_text
from test_mind_final import FakeServer, _call, _mind, _say


def _written(fields: dict) -> dict:
    return {"choices": [{"message": {"content": json.dumps(fields, ensure_ascii=False)}, "finish_reason": "stop"}]}


class Writer(FakeServer):
    """The decisions in ``replies``; the closed question of a message's text answered from ``texts``, in order."""

    def __init__(self, replies: list, texts: list) -> None:
        super().__init__(replies)
        self.texts = texts
        self.asked: list[dict] = []

    def chat(self, body: dict, timeout: float = 120.0, gives_way: bool = False) -> dict:
        if ((body.get("response_format") or {}).get("json_schema") or {}).get("name") == "mensaje":
            self.asked.append(json.loads(json.dumps(body)))
            return self.texts.pop(0)
        return super().chat(body, timeout, gives_way)


def _with_writer(tmp_path: Path, monkeypatch, replies: list, texts: list, writes: bool = True):
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    # MSG1B: the closed question that writes the text runs only when asked for (Mind._message_written).
    if writes:
        monkeypatch.setenv("BAXY_MSG1_REDACTA", "1")
    else:
        monkeypatch.delenv("BAXY_MSG1_REDACTA", raising=False)
    mind, _ = _mind(tmp_path, [])
    server = Writer(replies, texts)
    mind.server = server
    return mind, server


def _sent(mind) -> dict:
    calls = [c for m in mind.conversation for c in m.get("tool_calls") or []]
    return json.loads(calls[-1]["function"]["arguments"])


def test_the_order_words_go_as_the_person_would_write_them(tmp_path: Path, monkeypatch) -> None:
    order = {"channel": "whatsapp", "recipient": "Marta", "text": "que llego a las 10"}
    mind, server = _with_writer(tmp_path, monkeypatch, [_call("message_send", order)],
                                [_written({"e": "no", "t": "Llego a las 10"})])
    step = mind.decide(1, "dile a Marta por WhatsApp que llego a las 10")
    assert step["kind"] == "action" and step["arguments"]["text"] == "Llego a las 10"
    assert step["arguments"]["recipient"] == "Marta" and step["arguments"]["channel"] == "whatsapp"
    # The conversation carries the text that goes, and the question is asked after it, with the tools, typed.
    assert _sent(mind)["text"] == "Llego a las 10"
    asked = server.asked[0]
    assert asked["messages"][0]["role"] == "system" and asked["tool_choice"] == "none"
    assert "«dile a Marta por WhatsApp que llego a las 10»" in asked["messages"][-1]["content"]
    assert "chat message" in asked["messages"][-1]["content"]


def test_a_datum_nobody_gave_goes_back_once_and_the_text_written_again_goes(tmp_path: Path, monkeypatch) -> None:
    order = {"channel": "discord", "recipient": "Leo", "text": "si viene mañana"}
    mind, server = _with_writer(tmp_path, monkeypatch, [_call("message_send", order)],
                                [_written({"e": "no", "t": "¿Vienes mañana a las 9 a casa de Rocío?"}),
                                 _written({"e": "no", "t": "¿Vienes mañana?"})])
    step = mind.decide(1, "pregúntale a Leo por Discord si viene mañana")
    assert step["arguments"]["text"] == "¿Vienes mañana?"
    again = server.asked[1]["messages"][-1]["content"]
    assert "«9»" in again and "«Rocío»" in again


def test_still_unsaid_unreadable_or_dictated_the_decision_text_goes(tmp_path: Path, monkeypatch) -> None:
    order = {"channel": "whatsapp", "recipient": "Marta", "text": "nos vemos en la puerta del cine"}
    for texts in ([_written({"e": "no", "t": "Nos vemos a las 8"}), _written({"e": "no", "t": "Nos vemos a las 8"})],
                  [_say("no es un objeto")],
                  [{"choices": [{"message": {"content": '{"e":"no","t":"Nos vemos en'}, "finish_reason": "length"}]}],
                  [_written({"e": "yes", "t": "Nos vemos en la puerta del cine."})]):
        mind, server = _with_writer(tmp_path, monkeypatch, [_call("message_send", order)], texts)
        step = mind.decide(1, "dile a Marta por whatsapp exactamente esto: nos vemos en la puerta del cine")
        assert step["arguments"]["text"] == "nos vemos en la puerta del cine", texts
        assert server.texts == []


def test_a_text_in_quotes_goes_as_given_without_asking(tmp_path: Path, monkeypatch) -> None:
    order = {"channel": "whatsapp", "recipient": "Marta", "text": "Llego tarde, guárdame un sitio"}
    mind, server = _with_writer(tmp_path, monkeypatch, [_call("message_send", order)], [])
    step = mind.decide(1, "mándale a Marta por whatsapp «Llego tarde, guárdame un sitio»")
    assert step["arguments"]["text"] == "Llego tarde, guárdame un sitio" and server.asked == []


def test_an_email_gets_its_subject_and_body_and_other_tools_are_not_asked(tmp_path: Path, monkeypatch) -> None:
    order = {"to": "nico.ferrada@correo-prueba.cl", "text": "que la reunión se pasa al jueves"}
    mail = {"e": "no", "s": "Cambio de la reunión", "t": "Hola, Nico:\n\nLa reunión se pasa al jueves.\n\nSaludos"}
    mind, server = _with_writer(tmp_path, monkeypatch, [_call("email_send", order)], [_written(mail)])
    step = mind.decide(1, "mándale un correo a nico.ferrada@correo-prueba.cl diciendo que la reunión se pasa al jueves")
    assert step["arguments"]["subject"] == "Cambio de la reunión" and step["arguments"]["text"] == mail["t"]
    assert "email" in server.asked[0]["messages"][-1]["content"]
    typed = {"text": "hola mundo"}
    mind, server = _with_writer(tmp_path, monkeypatch, [_call("input_text_type", typed)], [])
    assert mind.decide(1, "escribe hola mundo")["arguments"]["text"] == "hola mundo" and server.asked == []


def test_the_aid_off_asks_nothing(tmp_path: Path, monkeypatch) -> None:
    order = {"channel": "whatsapp", "recipient": "Marta", "text": "que llego a las 10"}
    mind, server = _with_writer(tmp_path, monkeypatch, [_call("message_send", order)], [])
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    assert mind.decide(1, "dile a Marta por WhatsApp que llego a las 10")["arguments"]["text"] == "que llego a las 10"
    assert server.asked == []


def test_unsaid_compares_data_by_form() -> None:
    said = ["dile a la profe camila.rojas@liceo-prueba.cl que el pedido 4471 llega el jueves a las diez y media"]
    assert message_text.unsaid("Hola, Camila: el pedido 4471 llega el jueves a las 10:30. Saludos", said) == []
    assert message_text.unsaid("El pedido llega a las 22:30", said) == []          # the same hour, in 24 h
    assert message_text.unsaid("Hola, Camila: llega el viernes a las 11", said) == ["11", "viernes"]
    assert message_text.unsaid("Hola Profe, saludos de Rodrigo", said) == ["Rodrigo"]
    assert message_text.unsaid("Escríbeme a camila.rojas@liceo-prueba.cl o a otra@correo.cl", said) == ["otra@correo.cl"]
    # A capital that starts a sentence is no name; «I» and «I'm» are no names either.
    assert message_text.unsaid("Llego tarde. Guárdame un sitio. I'm late", ["llego tarde guardame un sitio"]) == []
    assert message_text.quoted("mándale «Llego tarde»", "llego tarde") and not message_text.quoted("dile hola", "hola")


def test_the_text_that_waits_for_the_yes_is_in_its_line(tmp_path: Path, monkeypatch) -> None:
    # Aid «message_text_told»: hub/int36h asked «¿Lo envías a Marta por WhatsApp?» with no word of what goes; the line of
    # the held call carries the text (and an email's subject) the call holds, for the model to say it.
    order = {"channel": "whatsapp", "recipient": "Marta", "text": "que llego a las 10"}
    mind, server = _with_writer(tmp_path, monkeypatch, [_call("message_send", order), _say("¿Le mando a Marta «Llego a las 10»?")],
                                [_written({"e": "no", "t": "Llego a las 10"})])
    mind.decide(1, "dile a Marta por WhatsApp que llego a las 10")
    mind.continue_turn(2, json.dumps({"status": "needs_confirmation", "next": "ask the person"}), final=True)
    told = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert "el texto de esta llamada es «Llego a las 10»; al preguntarle" in told
    mail = {"to": "nico.ferrada@correo-prueba.cl", "text": "Hola, Nico:\n\nLa reunión se pasa al jueves.", "subject": "Reunión"}
    mind, server = _with_writer(tmp_path, monkeypatch, [_call("email_send", mail), _say("¿Lo envío?")], [])
    monkeypatch.setenv("BAXY_AYUDAS", "message_text_told")
    mind.decide(1, "mándale un correo a nico.ferrada@correo-prueba.cl diciendo que la reunión se pasa al jueves")
    mind.continue_turn(2, json.dumps({"status": "needs_confirmation", "next": "ask the person"}), final=True)
    told = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert "«Hola, Nico:\n\nLa reunión se pasa al jueves.», con el asunto «Reunión»" in told and server.asked == []
    # Another call's line says nothing of it.
    mind, server = _with_writer(tmp_path, monkeypatch, [_call("input_text_type", {"text": "hola"}), _say("Listo.")], [])
    monkeypatch.setenv("BAXY_AYUDAS", "message_text_told")
    mind.decide(1, "escribe hola")
    mind.continue_turn(2, json.dumps({"status": "completed", "verification": "readback"}), final=True)
    assert "el texto de esta llamada" not in [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]


def test_a_word_with_a_capital_inside_is_one_name_and_the_draft_is_in_the_question(tmp_path: Path, monkeypatch) -> None:
    # MSG1B (sonda s0): «WhatsApp» in the text written read as the name «Whats» nobody said, and the text was dropped.
    said = ["text my brother on whatsapp that dinner is on saturday at 7"]
    assert message_text.unsaid("Dinner is on Saturday at 7, see you on WhatsApp", said) == []
    assert message_text.unsaid("La cena es el sábado a las 7", said) == ["sabado"]
    order = {"channel": "whatsapp", "recipient": "Marta", "text": "que llego a las 10"}
    mind, server = _with_writer(tmp_path, monkeypatch, [_call("message_send", order)],
                                [_written({"e": "no", "t": "Llego a las 10"})])
    mind.decide(1, "dile a Marta por WhatsApp que llego a las 10")
    # MSG1B: with the decision's draft (c3 left it out: «Sí» for a hug and a call, the whole order for others).
    assert "first draft, which may still be their order: «que llego a las 10»" in server.asked[0]["messages"][-1]["content"]


def test_by_default_the_text_is_the_decisions_and_its_line_quotes_it(tmp_path: Path, monkeypatch) -> None:
    # MSG1B: the closed question that writes the text is off unless BAXY_MSG1_REDACTA is «1» (it sent «yes» to a
    # person with a question that quoted another text); the line of the held call carries the decision's own text.
    order = {"channel": "whatsapp", "recipient": "Marta", "text": "Llego a las 10."}
    mind, server = _with_writer(tmp_path, monkeypatch, [_call("message_send", order), _say("¿Le mando: «Llego a las 10.»?")],
                                [], writes=False)
    step = mind.decide(1, "dile a Marta por WhatsApp que llego a las 10")
    assert step["arguments"]["text"] == "Llego a las 10." and server.asked == []
    mind.continue_turn(2, json.dumps({"status": "needs_confirmation", "next": "ask the person"}), final=True)
    told = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert "el texto de esta llamada es «Llego a las 10.»; al preguntarle" in told
