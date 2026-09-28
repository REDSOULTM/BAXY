"""Goal v3 paso 5 (M50): independent review of v3a-final, the official window run of the development set.

«La charla, el código y las explicaciones las escribe el modelo.» Every draft here is the one the run recorded
(compose-audit.jsonl, or the published reply when the mind wrote it directly):

- code asked for and not written (F-p10-t1/t2, F-w07-t1/t2/t3, F-w12-t1/t2, F-w14-t1/t2/t3): the mind wrote the
  code and the App refused it as internal code, the composer refused it the same way, or a SQL query was read as
  English and the turn asked back; the prompts said «una frase» and «no muestres códigos»;
- limits written wrong (F-s007 «no la activan yo», F-s077 «No leeo SMS», F-w11-t1 tacos «no los preparo yo»);
- the person named in the third person (F-s074, F-s091 «the person's Outlook calendar»);
- two tasks titled «ice cream» told as «dos entradas para helado» (F-w05-t4, F-w14-t4).
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import llm
from baxy_mind.semantic.conversation import asks_for_code, asks_to_order

AVERAGE = "baxy hazme una función en python que saque la media de una lista de números"
EXPENSES = (
    "Che, mirá, estoy armando un scriptcito en Python para ordenar los gastos del mes, ¿viste? ¿Me escribís una "
    "función que reciba una lista de montos y me devuelva el total y el promedio?"
)
SQL = "baxy escribeme un query de sql q me saque los users activos del ultimo mes"
CALCULATOR = (
    "Podrías decirme como crear una interfaz sencilla (también conocida como gui) de una calculadora para el lenguaje "
    "de programación Python? intenta encontrar un código que sirva tanto para una calculadora corriente como para una "
    "calculadora científica, gracias."
)


class ChatRecorder(llm.LlmRuntime):
    def __init__(self, replies: list[tuple[str, str]]) -> None:
        self._gguf = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
        self.replies = iter(replies)
        self.payloads: list[dict] = []

    def _post(self, payload: dict, **_: object) -> dict:
        self.payloads.append(payload)
        content, finish = next(self.replies)
        return {"choices": [{"message": {"content": content}, "finish_reason": finish}]}


def _system_text(payload: dict) -> str:
    return " ".join(str(message["content"]) for message in payload["messages"] if message["role"] == "system")


# --- what asks for code -------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "asked",
    [AVERAGE, EXPENSES, SQL, CALCULATOR, "mola ahora pásamela a javascript",
     "Buenísimo. ¿Y me la pasás a JavaScript? Es para una paginita", "ahora en typescript",
     "write a python function that reverses a string", "can you give me a SQL query for active users"],
)
def test_code_is_asked(asked: str) -> None:
    assert asks_for_code(asked)


@pytest.mark.parametrize(
    "said",
    ["qué es una función lineal", "qué tengo pendiente para hoy", "abre python", "pásame la sal",
     "copialo al clipboard", "qué hace el comando ls", "busca el pdf del contrato"],
)
def test_other_requests_ask_for_no_code(said: str) -> None:
    assert not asks_for_code(said)


@pytest.mark.parametrize(
    ("current", "prior"),
    [("vale pero que ignore los negativos", AVERAGE), ("ahora q salgan ordenados por fecha, los mas recientes primero", SQL),
     ("Si por favor me gustaría que me mostraras el ejemplo de la calculadora científica", CALCULATOR)],
)
def test_a_change_to_code_asked_before_is_code(current: str, prior: str) -> None:
    assert not asks_for_code(current)
    assert asks_for_code(current, (prior,))


# --- the mind writes it -------------------------------------------------------------------------------------------

def test_a_function_asked_for_is_written_with_room_for_it() -> None:
    reply = "def calcular_media(lista):\n    if not lista:\n        return 0\n    return sum(lista) / len(lista)"
    client = ChatRecorder([(reply, "stop")])
    answer, _ = client.chat(AVERAGE, history=[], conversation_kind="knowledge", response_language="es")
    assert answer == reply
    assert client.payloads[0]["max_tokens"] == llm.CODE_REPLY_MAX_TOKENS
    assert llm.CODE_REQUEST_PROMPT in _system_text(client.payloads[0])


def test_a_sql_query_is_not_an_english_reply() -> None:
    # F-w14-t1 (turn-audit request 1065): the query failed wrong_language twice and the turn asked back.
    query = "SELECT * FROM users WHERE last_login >= CURRENT_DATE - INTERVAL '30 days';"
    client = ChatRecorder([(query, "stop")])
    answer, _ = client.chat(SQL, history=[], conversation_kind="knowledge", response_language="es")
    assert answer == query
    assert len(client.payloads) == 1


def test_a_follow_up_to_code_writes_the_code_again() -> None:
    history = [{"role": "user", "content": CALCULATOR},
               {"role": "assistant", "content": "Para crear una interfaz gráfica en Python, puedes usar Tkinter."}]
    reply = "Aquí va:\n```python\nimport tkinter as tk\nimport math\n```"
    client = ChatRecorder([(reply, "stop")])
    answer, _ = client.chat(
        "Si por favor me gustaría que me mostraras el ejemplo de la calculadora científica",
        history=history, conversation_kind="knowledge", response_language="es",
    )
    assert answer == reply
    assert llm.CODE_REQUEST_PROMPT in _system_text(client.payloads[0])


def test_code_cut_by_its_budget_is_never_published() -> None:
    client = ChatRecorder([("```python\ndef calcular(montos):\n    total = sum(", "length")])
    with pytest.raises(llm.ConversationReplyContractError) as rejected:
        client.chat(AVERAGE, history=[], conversation_kind="knowledge", response_language="es")
    assert rejected.value.audit_reason == "truncated_code"


def test_a_plain_question_keeps_its_short_answer() -> None:
    client = ChatRecorder([("Un agujero negro es una región donde la gravedad no deja escapar la luz.", "stop")])
    client.chat("qué es un agujero negro", history=[], conversation_kind="knowledge", response_language="es")
    assert client.payloads[0]["max_tokens"] == 128
    assert llm.CODE_REQUEST_PROMPT not in _system_text(client.payloads[0])


def test_the_composer_keeps_the_code_asked_for() -> None:
    # F-w12-t1 compose-audit: the conversation fallback's first draft died as internal_code.
    draft = "Aquí tienes la función: `def calcular_gastos(montos): return sum(montos), sum(montos) / len(montos)`"
    facts = {"situation": json.dumps({"kind": "conversation"})}
    assert llm.compose_visible_defect(draft, "conversation", EXPENSES, facts) == ""
    assert llm.compose_visible_defect(draft, "conversation", "qué es un promedio", facts) == "internal_code"
    # Prose around the code is still judged.
    leaking = "Uso task.list para eso: `def media(l): return sum(l) / len(l)`"
    assert llm.compose_visible_defect(leaking, "conversation", EXPENSES, facts) == "internal_code"


def test_the_composer_is_told_to_write_the_code() -> None:
    class Recorder(llm.LlmRuntime):
        def __init__(self) -> None:
            self._gguf = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
            self.requests: list[dict] = []

        def _post(self, payload: dict, **_: object) -> dict:
            self.requests.append(payload)
            return {"choices": [{"message": {"content": "```javascript\nconst total = montos.reduce((a, b) => a + b, 0);\n```"},
                                 "finish_reason": "stop"}]}

    client = Recorder()
    client.compose_user_message(
        "Buenísimo. ¿Y me la pasás a JavaScript? Es para una paginita", "conversation",
        {"situation": json.dumps({"kind": "conversation"}), "priorRequests": [EXPENSES]},
    )
    assert llm.CODE_REQUEST_PROMPT in client.requests[0]["messages"][-1]["content"]


# --- limits -------------------------------------------------------------------------------------------------------

def test_a_limit_with_a_plural_verb_for_baxy_is_rewritten() -> None:
    # F-s007 (published by the mind's limit).
    assert llm._unsupported_answer_contract_failure(
        "Eso no lo hago: la función Smart Camera no la activan yo.", "Pon la función Smart Camera",
    ) == "unsupported_broken_person"
    assert llm._unsupported_answer_contract_failure(
        "Eso no lo hago: la función Smart Camera no la activo yo.", "Pon la función Smart Camera",
    ) == ""


def test_an_invented_first_person_is_not_published() -> None:
    # F-s077 compose-audit (retry draft, published): the limit's recovery composition.
    situation = json.dumps({"kind": "failure", "cause": "out_of_catalog", "polarity": "failure"})
    asked = "Vas a leer los cuatro primeros SMSs"
    assert llm.compose_visible_defect(
        "No leeo SMS ni mensajes de texto.", "error", asked, {"situation": situation},
    ) == "broken_person_conjugation"
    assert llm.compose_visible_defect("No leo SMS ni mensajes de texto.", "error", asked, {"situation": situation}) == ""


def test_ordering_food_is_not_making_it() -> None:
    # F-w11-t1 (published by the mind's limit).
    asked = "pideme unos tacos al pastor porfa q ya va a empesar el partido"
    assert asks_to_order(asked)
    assert llm._unsupported_answer_contract_failure(
        "Eso no lo hago: los tacos al pastor del partido no los preparo yo.", asked,
    ) == "unsupported_changed_act"
    assert llm._unsupported_answer_contract_failure("Eso no lo hago: los tacos al pastor no los pido yo.", asked) == ""
    assert "pedir o comprar algo no es prepararlo" in llm.UNSUPPORTED_PRESENTATION_PROMPT


# --- the person is spoken to --------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("asked", "draft"),
    [
        ("Show the emails, actually, the audio messages.",
         "The attempt to retrieve emails and audio messages failed because Outlook is not configured on this PC, "
         "preventing access to the person's Outlook calendar or mail."),
        ("Anything I should do after work today",
         "The calendar operation failed because Outlook is not configured on this computer, preventing access to the "
         "person's calendar or email."),
    ],
)
def test_the_person_is_not_named_in_the_third_person(asked: str, draft: str) -> None:
    situation = json.dumps({"kind": "failure", "polarity": "failure", "operation": "calendar.event.list",
                            "cause": "outlook_profile_not_configured"})
    assert llm.compose_visible_defect(draft, "error", asked, {"situation": situation}) == "third_person_addressee"
    assert llm.compose_visible_defect(
        "I can't reach your Outlook calendar or mail because Outlook isn't set up on this PC.", "error", asked,
        {"situation": situation},
    ) == ""
    assert "the person's" not in llm._CAUSE_FACT["outlook_profile_not_configured"]


# --- tasks are named by their titles ------------------------------------------------------------------------------

def _tasks(*titles: str) -> dict:
    return {
        "operation": "task.list",
        "seen": {"tasks": [{"taskId": f"id-{index}", "title": title, "completed": False, "deleted": False, "version": 1}
                           for index, title in enumerate(titles)], "count": len(titles), "mode": "tasks", "limit": 20},
    }


@pytest.mark.parametrize(
    ("payload", "draft"),
    [
        (_tasks("palta y pisco", "ice cream", "ice cream"),
         "Tienes tres tareas pendientes: comprar palta y pisco, y dos entradas para helado."),
        (_tasks("Renew my driver's license in California", "palta y pisco", "ice cream", "ice cream"),
         "Tienes cuatro tareas pendientes: renovar tu licencia de conducir en California, comprar palta y pisco, y dos "
         "entradas para helado."),
    ],
)
def test_a_task_is_named_by_its_title(payload: dict, draft: str) -> None:
    # F-w05-t4 / F-w14-t4 compose-audit (published first drafts).
    assert llm._payload_fact_defect(draft, payload, "qué más tengo pendiente") == "task_title_not_named"
    named = "Tienes pendientes " + ", ".join(f"«{title}»" for title in dict.fromkeys(
        task["title"] for task in payload["seen"]["tasks"])) + "; «ice cream» está dos veces."
    assert llm._payload_fact_defect(named, payload, "qué más tengo pendiente") == ""


def test_the_composer_asks_for_the_titles_and_rewrites_a_translated_list() -> None:
    class Recorder(llm.LlmRuntime):
        def __init__(self, replies: list[str]) -> None:
            self._gguf = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
            self.replies = iter(replies)
            self.requests: list[dict] = []

        def _post(self, payload: dict, **_: object) -> dict:
            self.requests.append(payload)
            return {"choices": [{"message": {"content": next(self.replies)}, "finish_reason": "stop"}]}

    good = "Tienes pendientes «palta y pisco» y «ice cream», que está dos veces."
    client = Recorder(["Tienes tres tareas pendientes: comprar palta y pisco, y dos entradas para helado.", good, good])
    situation = {"kind": "operation", "operation": "task.list", "polarity": "success", "verified": True,
                 "succeeded": True, "observed": _tasks("palta y pisco", "ice cream", "ice cream")["seen"]}
    reply = client.compose_user_message(
        "genial tío oye y aparte de eso qué más tengo pendiente", "status", {"situation": json.dumps(situation)},
    )
    assert reply == good
    assert "tal cual" in client.requests[0]["messages"][-1]["content"]
