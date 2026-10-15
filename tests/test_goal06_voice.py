"""Goal 06: personalidad en el prompt, narrate usa compose, caminos feos sin constante."""

from pathlib import Path
import inspect
import json

from baxy_mind import llm as llm_mod
from baxy_mind.llm_prompts import (
    GRANITE_CLOCK_EN_USER_MESSAGE_PROMPT,
    GRANITE_CLOCK_USER_MESSAGE_PROMPT,
    GRANITE_CONTINUE_EN_CPU_USER_MESSAGE_PROMPT,
    GRANITE_CONTINUE_EN_USER_MESSAGE_PROMPT,
    GRANITE_WELCOME_EN_USER_MESSAGE_PROMPT,
    GRANITE_WELCOME_USER_MESSAGE_PROMPT,
    _public_compose_sampling,
)
from baxy_mind.compose_instructions import _compose_shape_instruction
from baxy_mind.compose_payload import _compose_situation_payload
from baxy_mind.request_intents import (
    _looks_like_capability_question,
    _looks_like_refuse_question,
)
from baxy_mind.draft_cleanup import _strip_prompt_labels
from baxy_mind.visible_defect import compose_visible_defect
from baxy_mind.request_intents import _message_response_language
from baxy_mind.llm_prompts import SYSTEM_PROMPT
from baxy_mind.reply_language_checks import (
    visible_reply_invents_a_spanish_infinitive,
    visible_reply_is_a_fixed_stall,
)
from baxy_mind.clock_facts import _local_clock_from_observed
from baxy_mind.llm_prompts import (
    CPU_USER_MESSAGE_PROMPT,
    GRANITE_CPU_USER_MESSAGE_PROMPT,
    GRANITE_USER_MESSAGE_PROMPT,
    NARRATOR_PROMPT,
    USER_MESSAGE_PROMPT,
)


ROOT = Path(__file__).resolve().parents[1]
MIND = ROOT / "src/baxy_mind"
# The sidecar's entry and the modules it was split into; each cause is worded in one of them.
SIDECAR = "".join(
    (MIND / f"{name}.py").read_text(encoding="utf-8")
    for name in (
        "__main__",
        "sidecar_budgets",
        "turn_audit",
        "request_lane",
        "sidecar_lifecycle",
        "tool_catalog",
        "turn_history",
        "argument_grounding",
        "plan_dependencies",
        "decided_arguments",
        "plan_shape",
        "direct_arguments",
        "turn_recovery",
        "operation_contract",
        "turn_gates",
        "turn_decisions",
        "engine_handoff",
        "compose_facts",
        "send_offer",
        "turn_followups",
        "context_decision",
        "turn_decide",
    )
)
EARLY_NOTICE = (MIND / "turn_decide.py").read_text(encoding="utf-8")
RECOVERY = (MIND / "turn_recovery.py").read_text(encoding="utf-8")


def test_early_signal_production_path_uses_compose_not_snippet_template() -> None:
    assert "formulate_progress" not in SIDECAR
    assert '"cause": "acting"' in EARLY_NOTICE


def test_early_signal_preserves_phase_and_is_optional_when_composition_fails() -> None:
    from baxy_mind.turn_decide import _emit_early_turn_signal
    from baxy_mind.first_signal import PATH_MODEL, PendingTurnSignal

    captured = []
    signals = []
    signaled = []

    class Composer:
        fail = True

        def compose_user_message(self, request, intent, facts, *, timeout):
            captured.append((request, intent, facts, timeout))
            if self.fail:
                raise TimeoutError("optional inference failed")
            return "Estoy preparando los pasos de la solicitud."

    composer = Composer()
    kwargs = dict(path=PATH_MODEL, objective="Lee el archivo.", request_id="p1",
                  on_signal=PendingTurnSignal(signals.append, notice_after=0.0),
                  already_signaled=signaled,
                  llm=composer, phase="preparing_steps")
    # The notice is worded on its own thread (it never delays the decision).
    _emit_early_turn_signal(**kwargs).join(timeout=5)
    assert signals == [] and signaled == []
    composer.fail = False
    _emit_early_turn_signal(**kwargs).join(timeout=5)
    assert _emit_early_turn_signal(**kwargs) is None
    assert len(captured) == 2
    assert captured[1][0:2] == ("Lee el archivo.", "status")
    assert json.loads(captured[1][2]["situation"])["phase"] == "preparing_steps"
    assert captured[1][2]["traceId"] == "p1"
    assert captured[1][3] == 2.5
    assert len(signals) == 1 and signals[0]["id"] == "p1"
    assert signals[0]["text"] == "Estoy preparando los pasos de la solicitud."


def test_personality_lives_in_the_editable_prompt() -> None:
    prompt = USER_MESSAGE_PROMPT + "\n" + SYSTEM_PROMPT + "\n" + CPU_USER_MESSAGE_PROMPT
    assert "compañero" in prompt
    assert "un él" in prompt
    assert "Tuteas" in prompt
    # Personality belongs to the prompt; visible sentences belong to the model.
    assert "«Listo,»" not in USER_MESSAGE_PROMPT
    assert "«No pude:»" not in USER_MESSAGE_PROMPT
    assert "idioma del pedido" in prompt
    assert "fine-tun" not in prompt.casefold()
    assert NARRATOR_PROMPT == USER_MESSAGE_PROMPT
    granite = GRANITE_USER_MESSAGE_PROMPT + "\n" + GRANITE_CPU_USER_MESSAGE_PROMPT
    assert "compañero" in granite
    assert "un él" in granite
    assert "Tuteas" in granite
    assert "idioma del pedido" in granite
    assert "vive en el PC" not in GRANITE_USER_MESSAGE_PROMPT
    assert "Primera persona" not in GRANITE_USER_MESSAGE_PROMPT
    assert "hay red" not in granite.casefold()
    assert "fuera de mundo" not in granite.casefold()
    assert "kind=welcome" not in granite
    assert "no pude encontrarlo" not in granite.casefold()
    assert "unclear" not in granite.casefold()


def test_composition_reproducibility_follows_the_sampling_actually_used() -> None:
    """Latency 2026-09-23: the shell repeats a refused composition only when
    the writer could answer it differently; greedy or seeded decoding cannot."""

    class SeededCpuAdapter:
        @staticmethod
        def sampling() -> dict:
            return {"temperature": 0.7, "seed": 0}

    cpu_facts = {
        "situation": json.dumps(
            {"kind": "status", "polarity": "success", "observed": {"cpu": {"usagePercent": 12}}}
        )
    }
    plain_facts = {"situation": json.dumps({"kind": "status", "polarity": "success"})}
    runtime = object.__new__(llm_mod.LlmRuntime)
    runtime._cpu_prose_adapter = None
    runtime._gguf = r"D:\BAXYRuntime\assets\models\Qwen3-4B-Q4_K_M.gguf"
    assert runtime.composition_is_reproducible(plain_facts) is True
    runtime._gguf = r"D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf"
    assert runtime.composition_is_reproducible(plain_facts) is False
    runtime._cpu_prose_adapter = SeededCpuAdapter()
    assert runtime.composition_is_reproducible(cpu_facts) is True
    assert runtime.composition_is_reproducible(plain_facts) is False


def test_public_compose_profile_follows_gguf() -> None:
    qwen = r"D:\BAXYRuntime\assets\models\Qwen3-4B-Q4_K_M.gguf"
    granite = r"D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf"
    assert _public_compose_sampling(qwen) == {"temperature": 0.0}
    assert _public_compose_sampling(granite) == {"temperature": 1.0, "top_p": 0.95}
    assert _message_response_language("book a room on Deimos") == "en"
    assert _message_response_language("don't launch Notepad") == "en"
    assert _message_response_language("qué hora es") == "es"
    assert _strip_prompt_labels("<think></think>Soy BAXY, un compañero que vive en el PC.") == (
        "Soy BAXY, un compañero que vive en el PC."
    )

    captured: list[dict] = []

    class FakeClient(llm_mod.LlmRuntime):
        def __init__(self, gguf: str) -> None:  # noqa: D107
            self._gguf = gguf

        def _post(self, payload):  # noqa: ANN001
            captured.append(payload)
            return {"choices": [{"message": {"content": "<think></think>Soy BAXY."}}]}

    granite_client = FakeClient(granite)
    text = granite_client.compose_user_message(
        "quién eres",
        "welcome",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    )
    assert text == "Soy BAXY."
    assert captured[0]["temperature"] == 1.0
    assert captured[0]["top_p"] == 0.95
    assert captured[0]["messages"][0]["content"] == GRANITE_WELCOME_USER_MESSAGE_PROMPT
    captured.clear()
    granite_client.compose_user_message(
        "what is UTC, one line",
        "conversation",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    )
    knowledge = json.dumps(captured[-1], ensure_ascii=False)
    assert "hay red" not in knowledge.casefold()
    assert "Do not greet" in captured[-1]["messages"][1]["content"]
    assert "Do not configure" in captured[-1]["messages"][1]["content"]
    assert "Do not restate the request" in captured[-1]["messages"][1]["content"]
    captured.clear()
    granite_client.compose_user_message(
        "define huso horario, una frase",
        "conversation",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    )
    define_extra = captured[-1]["messages"][1]["content"]
    assert "Do not configure" in define_extra
    assert "define huso horario, una frase" in define_extra
    assert "Answer the person's actual question directly" in define_extra
    captured.clear()
    granite_client.compose_user_message(
        "qué puedes hacer en este equipo",
        "conversation",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    )
    capability_extra = captured[0]["messages"][1]["content"]
    assert "name three or four entries of can" in capability_extra
    captured.clear()
    granite_client.compose_user_message(
        "Hola, ¿qué puedes hacer?",
        "conversation",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    )
    r01_extra = captured[0]["messages"][1]["content"]
    assert "name three or four entries of can" in r01_extra
    assert "Greet briefly" not in r01_extra
    assert "Reply I don't do that" not in r01_extra
    captured.clear()
    granite_client.compose_user_message(
        "Explícame con calma qué puedes hacer en este PC y qué no haces, sin abrir nada.",
        "conversation",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    )
    r10_extra = captured[0]["messages"][1]["content"]
    assert "name three or four entries of can" in r10_extra
    assert "situation: {}" not in r10_extra
    assert '"situation": {"situation"' not in r10_extra
    assert "Reply I don't do that" not in r10_extra
    assert "JSON" in r10_extra
    assert "One short sentence" in r10_extra
    captured.clear()
    granite_client.compose_user_message(
        "don't open Calculator",
        "conversation",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    )
    constraint_extra = captured[0]["messages"][1]["content"]
    assert "will not open" in constraint_extra
    assert "Reply I don't do that" not in constraint_extra
    captured.clear()
    granite_client.compose_user_message(
        "Who is speaking",
        "conversation",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    )
    identity_extra = captured[0]["messages"][1]["content"]
    assert "Name BAXY" in identity_extra
    assert compose_visible_defect(
        "I don't do that.",
        "conversation",
        "don't open Calculator",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "reversed_result"
    assert compose_visible_defect(
        "I will not open Calculator.",
        "conversation",
        "don't open Calculator",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "Continue in one short sentence without opening apps.",
        "conversation",
        "keep going without opening apps",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "copied_instruction"
    assert compose_visible_defect(
        "Please specify the PC network name.",
        "status",
        "are you connected?",
        {
            "situation": json.dumps(
                {
                    "kind": "operation",
                    "operation": "network.status",
                    "polarity": "success",
                    "observed": {"online": True},
                },
                ensure_ascii=False,
            )
        },
    ) == "copied_instruction"
    assert compose_visible_defect(
        "En este PC abro programas, leo la hora y el audio. No abro nada ahora.",
        "conversation",
        "Explícame con calma qué puedes hacer en este PC y qué no haces, sin abrir nada.",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == ""
    assert "Do not configure" not in capability_extra
    assert "Explain the concept" not in capability_extra
    captured.clear()
    granite_client.compose_user_message(
        "traduce 'hello' al español, nada más",
        "conversation",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    )
    translation = captured[-1]["messages"][1]["content"]
    assert "Give only the translation" in translation
    assert "Do not greet" in translation
    assert "Do not refuse" in translation
    captured.clear()
    granite_client.compose_user_message(
        "keep going without opening apps",
        "conversation",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    )
    continue_payload = _compose_situation_payload(
        {"kind": "conversation", "polarity": "success"},
        "en",
        "keep going without opening apps",
    )
    assert continue_payload.get("effect") is None
    assert "continuing" not in continue_payload
    assert continue_payload.get("opening") == "none"
    assert "apps" not in continue_payload
    continue_system = captured[0]["messages"][0]["content"]
    assert continue_system == GRANITE_CONTINUE_EN_USER_MESSAGE_PROMPT
    assert continue_system != GRANITE_USER_MESSAGE_PROMPT
    assert "Tuteas" not in continue_system
    assert "Eres BAXY" not in continue_system
    assert GRANITE_CONTINUE_EN_CPU_USER_MESSAGE_PROMPT.startswith("You are BAXY")
    continue_extra = captured[0]["messages"][1]["content"]
    assert "keep going without opening apps" in continue_extra
    assert "continuing" not in continue_extra
    assert '"opening": "none"' in continue_extra
    assert '"apps": "none"' not in continue_extra
    assert "effect" not in continue_extra
    # cien-36 047/067 (7ffb1cb0f): the constraint names no application, so the
    # instruction says «open nothing» instead of ordering one to be named.
    assert "open nothing" in continue_extra
    assert "will not open" not in continue_extra
    assert "English only." not in continue_extra
    assert "Name continue and limit" not in continue_extra
    assert "Keep talking" not in continue_extra
    assert "Stay in the conversation" not in continue_extra
    assert "Continue in one short sentence" not in continue_extra
    # El contrato de idioma viaja siempre: sin él, «sigue charlando sin abrir
    # programas» se contestó en inglés (panel-opus-2/027).
    assert "Mandatory language" in continue_extra
    assert "One short sentence of the facts" not in continue_extra
    # «Qué no haces» pregunta por el límite, no por las capacidades: con la
    # lista delante el modelo la negaba entera (panel-opus-2/017 y /030).
    assert _looks_like_refuse_question("What will you never do")
    assert _looks_like_refuse_question("qué no haces, una frase")
    assert _looks_like_refuse_question("qué no haces en este PC, sin abrir nada")
    assert not _looks_like_capability_question("qué no haces, una frase")
    assert _looks_like_capability_question("qué puedes hacer en este PC")
    captured.clear()
    granite_client.compose_user_message(
        "qué no haces, una frase",
        "conversation",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    )
    limits_extra = captured[0]["messages"][1]["content"]
    # cien-36 023/082/017 (2402dd591): «qué no haces» said the PC gives orders;
    # the instruction now says BAXY only does what the person asks for.
    assert "only do what the person asks you for" in limits_extra
    assert "obey no machine" in limits_extra
    assert "Never list what you do as things you refuse" in limits_extra
    assert "name three or four entries of can" not in limits_extra
    assert "Reply I don't do that" not in limits_extra
    captured.clear()
    clock_facts = {
        "situation": json.dumps(
            {
                "kind": "operation",
                "operation": "system.time",
                "polarity": "success",
                "observed": {
                    "utc": "2026-09-05T12:08:00.0000000+00:00",
                    "localUtcOffsetMinutes": -240,
                },
            },
            ensure_ascii=False,
        )
    }
    granite_client.compose_user_message(
        "¿Qué hora es?",
        "status",
        clock_facts,
    )
    assert captured[0]["messages"][0]["content"] == GRANITE_CLOCK_USER_MESSAGE_PROMPT
    assert "Tuteas" not in captured[0]["messages"][0]["content"]
    captured.clear()
    granite_client.compose_user_message(
        "What time is it?",
        "status",
        clock_facts,
    )
    assert captured[0]["messages"][0]["content"] == GRANITE_CLOCK_EN_USER_MESSAGE_PROMPT
    captured.clear()
    granite_client.compose_user_message(
        "close that",
        "conversation",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    )
    close_extra = captured[0]["messages"][1]["content"]
    assert "Ask one short question that names the missing target" in close_extra
    captured.clear()
    granite_client.compose_user_message(
        "Hi there",
        "welcome",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    )
    hi_extra = captured[0]["messages"][1]["content"]
    assert captured[0]["messages"][0]["content"] == GRANITE_WELCOME_EN_USER_MESSAGE_PROMPT
    assert '"greeting":' not in hi_extra
    assert hi_extra.startswith("Hi there\n")
    assert "Greet briefly" not in hi_extra
    assert "English only" not in hi_extra
    captured.clear()
    granite_client.compose_user_message(
        "are you connected?",
        "status",
        {"situation": '{"kind":"operation","operation":"network.status","polarity":"success"}'},
    )
    net_extra = captured[0]["messages"][1]["content"]
    assert "Say whether this PC is online" in net_extra
    assert "Name seen.online" not in net_extra
    assert "Do not introduce yourself" in net_extra
    captured.clear()
    granite_client.compose_user_message(
        "What will you refuse to do",
        "conversation",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    )
    refuse_q = captured[0]["messages"][1]["content"]
    assert "only do what the person asks you for" in refuse_q
    assert "moral category" not in refuse_q
    assert "limit of this PC" not in refuse_q
    assert "Never list what you do as things you refuse" in refuse_q
    assert "Do not invent laws" not in refuse_q
    assert "hardware specs" not in refuse_q
    assert "Do not introduce yourself" in refuse_q
    assert "Do not refuse." not in refuse_q
    assert "Name what is in seen" not in refuse_q
    assert "Do not say harm" not in refuse_q
    assert len(captured) >= 2
    retry_user = captured[1]["messages"][1]["content"]
    assert "borrador anterior" not in retry_user.casefold()
    assert "effect is closed" not in retry_user.casefold()
    assert "only facts in seen" not in retry_user.casefold()
    assert "do not say harm" not in retry_user.casefold()
    captured.clear()
    granite_client.compose_user_message(
        "book a room on Deimos",
        "error",
        {"situation": '{"kind":"failure","cause":"out_of_catalog","polarity":"failure"}'},
    )
    refuse = captured[0]["messages"][1]["content"]
    # El prompt nombra el hecho; no dicta la frase visible.
    assert "outside what you do on this PC" in refuse
    assert "I don't do that" not in refuse
    assert "eso no lo hago" not in refuse.casefold()
    assert "Start with I couldn't" not in refuse
    captured.clear()
    qwen_client = FakeClient(qwen)
    qwen_client.compose_user_message(
        "quién eres",
        "welcome",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    )
    assert captured[0]["temperature"] == 0.0
    assert "top_p" not in captured[0]
    assert captured[0]["messages"][0]["content"] == USER_MESSAGE_PROMPT
    assert compose_visible_defect(
        "I cannot fabric a clock time.",
        "error",
        "fabricate a clock time",
        {"situation": '{"kind":"failure","cause":"out_of_catalog","polarity":"failure"}'},
    ) == "invented"
    assert compose_visible_defect(
        "No puedo abrir Steam.",
        "error",
        "no abras Steam",
        {"situation": '{"kind":"failure","cause":"out_of_catalog","polarity":"failure"}'},
    ) == "reversed_result"
    assert compose_visible_defect(
        "Sí, tengo internet.",
        "status",
        "¿Tengo internet?",
        {"situation": '{"kind":"operation","operation":"network.status","polarity":"success"}'},
    ) == "wrong_actor"


def test_shape_instruction_is_not_the_published_sentence() -> None:
    open_es = _compose_shape_instruction(
        {"polarity": "success", "observed": {"app": "Word"}},
        "es",
        "abre Word",
    )
    assert "Listo, Word está abierto" not in open_es
    assert "observed.app" in open_es
    open_en = _compose_shape_instruction(
        {"polarity": "success", "observed": {"app": "Word"}},
        "en",
        "open Word",
    )
    assert "Word is open" not in open_en
    note = _compose_shape_instruction(
        {"polarity": "success", "observed": {"title": "Ideas"}},
        "es",
        "crea una nota Ideas",
    )
    assert "la nota Ideas está creada" not in note
    welcome = _compose_shape_instruction(
        {"kind": "welcome", "polarity": "success"},
        "en",
        "hi",
    )
    assert welcome == ""
    clock_shape = _compose_shape_instruction(
        {
            "polarity": "success",
            "observed": {
                "utc": "2026-09-03T06:57:52.1829160+00:00",
                "localUtcOffsetMinutes": -240,
            },
        },
        "en",
        "clock please",
    )
    assert "seen.time" not in clock_shape
    assert "State the time in clock" in clock_shape
    close = _compose_shape_instruction(
        {"kind": "operation", "polarity": "success"},
        "en",
        "close the window",
    )
    assert "The window is closed." not in close
    assert "Name the window" not in close


def test_compose_payload_does_not_contain_published_sentences() -> None:
    captured: list[dict] = []

    class FakeClient(llm_mod.LlmRuntime):
        def __init__(self) -> None:  # noqa: D107
            pass

        def _post(self, payload):  # noqa: ANN001
            captured.append(payload)
            return {"choices": [{"message": {"content": "Listo, Word está abierto."}}]}

    client = FakeClient()
    client.compose_user_message(
        "abre Word",
        "status",
        {
            "situation": (
                '{"kind":"operation","operation":"app.open","polarity":"success",'
                '"verified":true,"observed":{"app":"Word"}}'
            )
        },
    )
    blob = json.dumps(captured, ensure_ascii=False)
    assert "Listo, Word está abierto" not in blob
    captured.clear()
    client.compose_user_message(
        "ábrela",
        "clarification",
        {"situation": '{"kind":"clarification","cause":"ambiguous_request","polarity":"pending"}'},
    )
    blob = json.dumps(captured, ensure_ascii=False)
    assert "¿Qué quieres abrir?" not in blob
    assert "What do you want to open?" not in blob
    captured.clear()
    client.compose_user_message(
        "abre Steam",
        "error",
        {
            "situation": (
                '{"kind":"failure","cause":"app_not_found","polarity":"failure",'
                '"target":"Steam"}'
            )
        },
    )
    blob = json.dumps(captured, ensure_ascii=False)
    assert "no la encontré" not in blob.casefold()
    assert "Listo, Word está abierto" not in blob
    assert compose_visible_defect(
        "The app is open.",
        "status",
        "open Discord",
        {
            "situation": (
                '{"kind":"operation","polarity":"success",'
                '"observed":{"app":"Discord"}}'
            )
        },
    ) == "missing_name"
    assert compose_visible_defect(
        "Hola, ¿cómo te va?",
        "welcome",
        "",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "Listo, Steam está abierto.",
        "status",
        "cierra Steam",
        {
            "situation": (
                '{"kind":"operation","polarity":"success","observed":{"app":"Steam"}}'
            )
        },
    ) == "reversed_result"
    assert compose_visible_defect(
        "Sigo trabajando en el estado observable.",
        "status",
        "abre Steam y ve a la biblioteca",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    ) == "internal_code"
    assert compose_visible_defect(
        "I couldn't: I opened Word.",
        "error",
        "open Word and wipe the disk",
        {
            "situation": (
                '{"kind":"failure","cause":"mission_failed","polarity":"failure"}'
            )
        },
    ) == "reversed_polarity"
    assert compose_visible_defect(
        "I couldn't.",
        "status",
        "open Steam and go to the library",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    ) == "acting_asserted"
    assert compose_visible_defect(
        "Hola.",
        "status",
        "abre Steam y ve a la biblioteca",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    ) == "acting_asserted"
    assert compose_visible_defect(
        "Sigo adelante.",
        "status",
        "abre Steam y ve a la biblioteca",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "Digo que sí.",
        "status",
        "abre Steam y ve a la biblioteca",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    ) == "acting_asserted"
    assert compose_visible_defect(
        "Still working.",
        "status",
        "open Steam and go to the library",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "I'm here.",
        "status",
        "open Steam and go to the library",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    ) == "acting_asserted"
    assert compose_visible_defect(
        "Progreso, sin el resultado.",
        "status",
        "abre Steam y ve a la biblioteca",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    ) == "copied_instruction"
    assert compose_visible_defect(
        "I couldn't: the mute feature is active.",
        "status",
        "mute the speakers",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":true}}'
            )
        },
    ) == "asserted_failure"
    assert compose_visible_defect(
        "La persona está muda.",
        "status",
        "silencia los altavoces",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":true}}'
            )
        },
    ) == "missing_name"
    captured.clear()
    client.compose_user_message(
        "abre Steam y ve a la biblioteca",
        "status",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    )
    for payload in captured:
        system = payload["messages"][0]["content"]
        user = payload["messages"][1]["content"]
        # La corrección de un reintento se añade al sistema, nunca a los hechos.
        assert system.startswith(CPU_USER_MESSAGE_PROMPT)
        assert "estado observable" not in system
        # Source98: progress describes the current state. The requested future
        # effect still determines language but must not prime a claimed action.
        assert "Texto original de la persona:" not in user
        assert "Steam" not in user
        assert "Idioma obligatorio: español" in system + user
        assert '"state": "in progress"' in user
        assert '"outcome": "completed"' not in user
    captured.clear()
    client.compose_user_message(
        "open Word and wipe the disk",
        "error",
        {
            "situation": (
                '{"kind":"failure","cause":"mission_failed","polarity":"failure",'
                '"steps":["I opened Word."]}'
            )
        },
    )
    blob = json.dumps(captured, ensure_ascii=False)
    assert "I opened Word" not in blob


def test_narrate_is_compose_not_a_parallel_prompt() -> None:
    source = inspect.getsource(llm_mod.LlmRuntime.narrate)
    assert "compose_user_message" in source
    assert "NARRATOR_PROMPT" not in source


def test_recovery_compose_does_not_pass_a_spanish_constant() -> None:
    assert "No pude completar el análisis de tu petición." not in SIDECAR
    # Tanda 4 2026-09-24: the recovery asks the missing piece through the
    # clarification cause; it still passes a cause code, never visible text.
    assert '"cause": "ambiguous_request"' in RECOVERY


def test_invented_infinitives_and_stalls_are_still_rejected() -> None:
    assert visible_reply_invents_a_spanish_infinitive("No puedo cuecer las lentejas.")
    assert visible_reply_invents_a_spanish_infinitive("Cambia tetera por Descalzica.")
    assert visible_reply_invents_a_spanish_infinitive(
        "Listo, Abrbió Word y creó la nota."
    )
    assert visible_reply_invents_a_spanish_infinitive(
        "The window washas been closed."
    )
    assert visible_reply_invents_a_spanish_infinitive(
        "Los altavoces están silo."
    )
    assert visible_reply_invents_a_spanish_infinitive(
        "No puedo decirar el día actual sin ver la pantalla."
    )
    assert visible_reply_invents_a_spanish_infinitive("No puedo fabricar una hora talcr.")
    assert visible_reply_invents_a_spanish_infinitive(
        "Want me to readver the current date and time?"
    )
    assert visible_reply_invents_a_spanish_infinitive(
        "Quieres que vme la Papelera de reciclaje?"
    )
    assert visible_reply_invents_a_spanish_infinitive(
        "¿Quieres que te comprobo si una aplicación está instalada?"
    )
    assert visible_reply_invents_a_spanish_infinitive(
        "No puedo llamarar a un taxi en Marte."
    )
    assert visible_reply_invents_a_spanish_infinitive("Buenos nochesos.")
    assert visible_reply_is_a_fixed_stall("un momento…")
    assert not visible_reply_is_a_fixed_stall("Listo, Spotify está abierto y sonando")


def test_compose_visible_defect_rejects_polarity_codes_and_copied_names() -> None:
    fail = {"situation": '{"kind":"failure","cause":"timeout","polarity":"failure","target":"Chrome"}'}
    assert compose_visible_defect(
        "Listo, Chrome no respondió.", "error", "cierra Chrome", fail
    ) == "reversed_polarity"
    assert compose_visible_defect(
        "No pude: provider_down", "error", "abre Spotify", fail
    ) == "internal_code"
    assert compose_visible_defect(
        "No pude: Spotify no responde.",
        "error",
        "cierra Chrome",
        fail,
    ) == "unmentioned_name"
    assert compose_visible_defect(
        "No pude: se agotó el tiempo.",
        "error",
        "cierra Chrome",
        fail,
    ) == ""
    assert compose_visible_defect(
        "Listo, hola.",
        "welcome",
        "hola",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == "welcome_opener"
    assert compose_visible_defect(
        "Listo, confirmar.",
        "confirmation",
        "borra la nota",
        {"situation": '{"kind":"confirmation","polarity":"pending","choices":["confirmar","cancelar"]}'},
    ) == "confirmation_asserted"
    assert compose_visible_defect(
        "¿Lo borro?",
        "confirmation",
        "borra la nota",
        {"situation": '{"kind":"confirmation","polarity":"pending","choices":["confirmar","cancelar"]}'},
    ) == "missing_confirmation_choice"
    # Prueba del dueño 2026-09-21, turno 151: el participio como sustantivo con el
    # artículo del otro género no es una pregunta bien formada.
    assert compose_visible_defect(
        "¿Quieres confirmar o cancelar la cerrado de Edge?",
        "confirmation",
        "cierra edge",
        {"situation": '{"kind":"confirmation","polarity":"pending","choices":["confirmar","cancelar"]}'},
    ) == "malformed_action_noun"
    assert compose_visible_defect(
        "¿Quieres confirmar o cancelar el cierre de Edge?",
        "confirmation",
        "cierra edge",
        {"situation": '{"kind":"confirmation","polarity":"pending","choices":["confirmar","cancelar"]}'},
    ) == ""
    # Prueba del dueño 2026-09-21, turno 205: el micrófono ya en el estado pedido
    # es la causa tipada del fallo; nombrarla no es una afirmación de más, y «no
    # cambió nada» dice el fallo entero.
    already_muted = (
        '{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],'
        '"reason":"{\\"kind\\":\\"operation\\",\\"operation\\":\\"audio.microphone.mute\\",'
        '\\"polarity\\":\\"failure\\",\\"verified\\":false,\\"succeeded\\":false,'
        '\\"error\\":\\"microphone_already_muted\\"}"}'
    )
    assert compose_visible_defect(
        "El micrófono ya estaba silenciado, así que no cambió nada.",
        "error",
        "silencia mi microfono",
        {"situation": already_muted},
    ) == ""
    assert compose_visible_defect(
        "No pude silenciar el micrófono porque ya estaba silenciado.",
        "error",
        "silencia mi microfono",
        {"situation": already_muted},
    ) == ""
    # ctx-dueno-05: a failure said as «no se realizó la acción» after a completed
    # first step is a failure said entire.
    click_failed = (
        '{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":1,'
        '"steps":["{\\"kind\\":\\"operation\\",\\"operation\\":\\"app.open\\",\\"polarity\\":\\"success\\",'
        '\\"verified\\":true,\\"succeeded\\":true,\\"observed\\":{\\"appId\\":\\"Steam\\",\\"displayName\\":\\"Steam\\"}}"],'
        '"reason":"{\\"kind\\":\\"operation\\",\\"operation\\":\\"input.visible.click\\",'
        '\\"polarity\\":\\"failure\\",\\"verified\\":false,\\"succeeded\\":false,'
        '\\"error\\":\\"visible_button_not_found\\"}"}'
    )
    assert compose_visible_defect(
        "Abrí Steam e intenté hacer clic en «Crash Bandicoot», pero no hay nada en la pantalla con ese nombre, así que no se realizó la acción.",
        "error",
        "en steam ve a crash bandicoot",
        {"situation": click_failed},
    ) == ""
    # ctx-dueno-07: the family code carries its fact into the failure payload.
    from baxy_mind.compose_situation import _has_cause_fact
    from baxy_mind.compose_situation import _cause_in_prose
    assert _has_cause_fact("youtube_playback_not_verified_watch_ready0_playing_network2_source_none")
    assert "did not start playing" in _cause_in_prose(
        "youtube_playback_not_verified_watch_ready0_playing_network2_source_none", "es"
    )
    assert not _has_cause_fact("some_unknown_code")
    # AIRPLANE2043: the radios already in the requested state are a named fact.
    assert "already off" in _cause_in_prose("airplane_mode_already_off", "es")
    assert "already on" in _cause_in_prose("airplane_mode_already_on", "es")
    # WALLPAPER2037 (notebook): the narrator's copy of the wallpaper receipt has no
    # RGB code and no previous-wallpaper path; the checks still see the colour.
    from baxy_mind.compose_payload import _compose_situation_payload
    wallpaper = {
        "kind": "operation", "operation": "desktop.wallpaper.set", "polarity": "success",
        "verified": True, "succeeded": True,
        "observed": {"mode": "solid_color", "color": "red", "rgb": "170 20 20",
                     "previousWallpaper": "C:/private/prev.jpg", "authority": "spi_registry_postread"},
    }
    projected = _compose_situation_payload(wallpaper, "en")
    assert projected["seen"]["color"] == "red"
    assert "rgb" not in projected["seen"] and "previousWallpaper" not in projected["seen"]
    # WALLPAPER2039: the verified change is an effect, not a read («I set …» stays).
    assert projected.get("effect") == "applied"
    from baxy_mind.payload_fact_checks import _payload_fact_defect
    assert _payload_fact_defect("I set the wallpaper to solid red.", projected, "set the wallpaper to red") == ""
    assert compose_visible_defect(
        "I set the wallpaper to solid red.",
        "status",
        "set the wallpaper to red",
        {"situation": json.dumps(wallpaper)},
    ) == ""
    # WINGET2083 «instala 7-Zip»: «no se puede confirmar» states the failure.
    _install_unverified = json.dumps({
        "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
        "reason": json.dumps({"kind": "operation", "operation": "package.install.commit", "polarity": "failure",
                              "verified": False, "succeeded": False, "error": "winget_install_not_verified"}),
    })
    assert compose_visible_defect(
        "El instalador de 7-Zip terminó, pero el paquete no aparece en la lista de instalados, así que no se puede "
        "confirmar que se haya instalado.",
        "error", "instala 7-Zip", {"situation": _install_unverified},
    ) == ""

    # SHELL2075 H0245 «ejecuta ls» with no output: «No hubo salida» says there was none.
    _ran_silent = _compose_situation_payload({
        "kind": "operation", "operation": "shell.command.run", "polarity": "success",
        "verified": True, "succeeded": True,
        "observed": {"version": 1, "command": "ls", "cwd": "C:/perfil/shell-cwd", "exitCode": 0,
                     "stdout": "", "stderr": "", "lineCount": 0, "lines": [], "truncated": False,
                     "authority": "shell_process_exit_and_captured_output"},
    }, "es")
    assert _payload_fact_defect(
        "Ejecuté ls en la carpeta actual y salió bien. No hubo salida.", _ran_silent, "ejecuta ls") == ""
    assert _payload_fact_defect(
        "Ejecuté ls en la carpeta actual y salió bien.", _ran_silent, "ejecuta ls") == "missing_state"

    # EXPLORER2069 H0701: the count names the folder the Explorer had in front.
    _counted = _compose_situation_payload({
        "kind": "operation", "operation": "filesystem.explorer.count", "polarity": "success",
        "verified": True, "succeeded": True,
        "observed": {"version": 1, "folderName": "raiz_conteo", "source": "explorer_foreground",
                     "extension": ".py", "count": 3, "filesInFolder": 4},
    }, "es")
    assert _counted["seen"]["folderName"] == "raiz_conteo"
    assert _payload_fact_defect(
        "Hay 3 archivos .py en el directorio actual.", _counted,
        "Dime cuantos archivos .py hay en el directorio actual") == "missing_state"
    assert _payload_fact_defect(
        "En raiz_conteo, la carpeta que tenés delante, hay 3 archivos .py.", _counted,
        "Dime cuantos archivos .py hay en el directorio actual") == ""

    # EXPLORER2071 H0701: the folder's observed name is not internal jargon.
    from baxy_mind.observed_response_literals import without_observed_names
    _counted_situation = json.dumps({
        "kind": "operation", "operation": "filesystem.explorer.count", "polarity": "success",
        "verified": True, "succeeded": True,
        "observed": {"version": 1, "folderName": "raiz_conteo", "source": "explorer_foreground",
                     "extension": ".py", "count": 3, "filesInFolder": 4},
    })
    assert "raiz_conteo" not in without_observed_names(
        "En el directorio raiz_conteo hay 3 archivos .py.", json.loads(_counted_situation))
    assert compose_visible_defect(
        "En el directorio raiz_conteo hay 3 archivos .py.",
        "status", "Dime cuantos archivos .py hay en el directorio actual", {"situation": _counted_situation},
    ) == ""

    # TEXTREAD2063 H0299: the file's own words are observed data, even a forbidden term.
    _roadmap = json.dumps({
        "kind": "operation", "operation": "document.text.read", "polarity": "success",
        "verified": True, "succeeded": True,
        "observed": {"version": 1, "reviewLabel": "ROADMAP.md", "folder": "desktop", "bytes": 186,
                     "lines": 11, "characters": 183, "truncated": False,
                     "text": "# ROADMAP\n\n## Fase 1: agente local\nEl agente corre en la PC y lee el catalogo.\n",
                     "authority": "windows_known_text_file_utf8_read"},
    })
    assert compose_visible_defect(
        'Se leyó el archivo nombrado ROADMAP.md, que tiene 11 líneas. Empieza así: "# ROADMAP ## Fase 1: agente local '
        'El agente corre en la PC y lee el catalogo."',
        "status", "%USERPROFILE%\\Desktop\\raiz_textos\\ROADMAP.md", {"situation": _roadmap},
    ) == ""

    # MEME2055 «Tienes algun meme?»: the picture the viewer shows is named by its file.
    _meme_mission = {"situation": json.dumps({
        "kind": "status", "cause": "mission_completed", "polarity": "success", "stepCount": 2,
        "steps": [
            json.dumps({"kind": "operation", "operation": "web.download", "polarity": "success", "verified": True,
                        "succeeded": True, "observed": {"version": 1, "sourceUrl": "https://example.org/i/meme.jpg",
                                                         "query": "meme", "folder": "pictures", "name": "meme.jpg",
                                                         "bytes": 12345, "contentType": "image/jpeg"}}),
            json.dumps({"kind": "operation", "operation": "file.open", "polarity": "success", "verified": True,
                        "succeeded": True, "observed": {"version": 1, "folder": "pictures", "name": "meme.jpg",
                                                         "windowTitle": "meme.jpg", "processId": 9276}}),
        ],
    })}
    assert compose_visible_defect(
        "Sí, ya tengo un meme descargado y abierto en la carpeta de imágenes.",
        "status", "Tienes algun meme?", _meme_mission,
    ) == "missing_name"
    assert compose_visible_defect(
        "Descargué meme.jpg en Imágenes y lo abrí en el visor.",
        "status", "Tienes algun meme?", _meme_mission,
    ) == ""
    # PPTX2051 «make a presentation about dogs with 5 slides»: the package was
    # written and file.open could not be verified; the English final that says
    # both is neither reversed nor missing the failure.
    _pptx_open_unverified = json.dumps({
        "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 1,
        "steps": [json.dumps({"kind": "operation", "operation": "document.presentation.create", "polarity": "success",
                              "verified": True, "succeeded": True,
                              "observed": {"version": 1, "title": "Dogs", "folder": "documents", "name": "Dogs.pptx", "slideCount": 5}})],
        "reason": json.dumps({"kind": "operation", "operation": "file.open", "polarity": "failure", "verified": False,
                              "succeeded": False, "error": "file_open_not_verified"}),
    })
    assert compose_visible_defect(
        "The file was created and sent to the application, but no window or process appeared to confirm it opened, so the opening cannot be verified.",
        "error", "make a presentation about dogs with 5 slides", {"situation": _pptx_open_unverified},
    ) == ""
    assert compose_visible_defect(
        "The file was sent to its application but no window or process appeared, so the opening is not confirmed.",
        "error", "make a presentation about dogs with 5 slides", {"situation": _pptx_open_unverified},
    ) == ""
    assert compose_visible_defect(
        "I opened the presentation in PowerPoint.",
        "error", "make a presentation about dogs with 5 slides", {"situation": _pptx_open_unverified},
    ) == "reversed_polarity"
    # DOWNLOAD2047: the typed download causes narrated in the person's words.
    def _download_failure(err: str) -> str:
        step = json.dumps({"kind": "operation", "operation": "web.download", "polarity": "failure",
                           "verified": False, "succeeded": False, "error": err})
        return json.dumps({"kind": "failure", "polarity": "failure", "cause": "mission_failed",
                           "stepCount": 0, "steps": [], "reason": step})
    assert compose_visible_defect(
        "No se pudo descargar porque la dirección no respondió, así que nada se guardó.",
        "error", "descargá https://example.com/index.html en descargas",
        {"situation": _download_failure("download_source_unavailable")},
    ) == ""
    assert compose_visible_defect(
        "La página no tiene imagen de portada, por eso no se guardó nada.",
        "error", "bajá la portada de es.wikipedia.org a imágenes",
        {"situation": _download_failure("download_page_without_image")},
    ) == ""
    # DOWNLOAD2047: the file just written is observed data, never a dotted code.
    downloaded = json.dumps({"kind": "operation", "operation": "web.download", "polarity": "success",
                             "verified": True, "succeeded": True,
                             "observed": {"version": 1, "sourceUrl": "https://upload.wikimedia.org/wikipedia/en/thumb/8/80/Wikipedia-logo-v2.svg/250px-Wikipedia-logo-v2.svg.png",
                                          "folder": "desktop", "name": "250px-Wikipedia-logo-v2.svg.png", "bytes": 59357,
                                          "contentType": "image/png", "authority": "downloaded_file_size_postread"}})
    assert compose_visible_defect(
        "Descargué la imagen de portada de wikipedia.org y la guardé en el escritorio con el nombre 250px-Wikipedia-logo-v2.svg.png.",
        "status", "descarga la imagen de portada de wikipedia.org y guardala en el escritorio",
        {"situation": downloaded},
    ) == ""
    unmuted = (
        '{"kind":"operation","operation":"audio.microphone.mute","polarity":"success","verified":true,'
        '"succeeded":true,"observed":{"version":1,"baselineMuted":true,"muted":false,'
        '"authority":"windows_core_audio_capture_endpoint_postread"}}'
    )
    assert compose_visible_defect(
        "Tu micrófono está activo de nuevo.",
        "status",
        "activa mi microfono",
        {"situation": unmuted},
    ) == ""
    assert compose_visible_defect(
        "Mi micrófono está silenciado.",
        "status",
        "activa mi microfono",
        {"situation": unmuted},
    ) == "reversed_mute"
    assert compose_visible_defect(
        "¿Confirmas o cancelas que cierre la ventana abierta de Edge?",
        "confirmation",
        "cierra edge",
        {"situation": '{"kind":"confirmation","polarity":"pending","choices":["confirmar","cancelar"]}'},
    ) == ""
    assert compose_visible_defect(
        "No pude: Spotify no responde.",
        "error",
        "open Spotify",
        {
            "situation": (
                '{"kind":"failure","cause":"provider_down",'
                '"polarity":"failure","target":"Spotify"}'
            )
        },
    ) == "wrong_language"
    assert compose_visible_defect(
        "I couldn't: the provider is down.",
        "error",
        "open Spotify",
        {
            "situation": (
                '{"kind":"failure","cause":"provider_down",'
                '"polarity":"failure","target":"Spotify"}'
            )
        },
    ) == "internal_code"
    assert compose_visible_defect(
        "No pude: eso no lo hago.",
        "error",
        "order a pizza",
        {"situation": '{"kind":"failure","cause":"out_of_catalog","polarity":"failure"}'},
    ) == "wrong_language"
    # Fuera de catálogo no hubo intento: «I couldn't» afirma uno que no ocurrió,
    # y decir el límite ya no obliga a abrir con el marcador de fallo.
    assert compose_visible_defect(
        "I couldn't: I don't do that.",
        "error",
        "order a pizza",
        {"situation": '{"kind":"failure","cause":"out_of_catalog","polarity":"failure"}'},
    ) == "extra_claim"
    assert compose_visible_defect(
        "I don't do that on this PC.",
        "error",
        "order a pizza",
        {"situation": '{"kind":"failure","cause":"out_of_catalog","polarity":"failure"}'},
    ) == ""
    assert compose_visible_defect(
        "I don't do that.",
        "error",
        "don't open Steam",
        {"situation": '{"kind":"failure","cause":"out_of_catalog","polarity":"failure"}'},
    ) == "reversed_result"
    assert compose_visible_defect(
        "Eso no lo hago.",
        "error",
        "no abras Steam",
        {"situation": '{"kind":"failure","cause":"out_of_catalog","polarity":"failure"}'},
    ) == "reversed_result"
    assert compose_visible_defect(
        "¿Confirmas o cancelas borrar la nota?",
        "confirmation",
        "borra la nota",
        {"situation": '{"kind":"confirmation","polarity":"pending","choices":["confirmar","cancelar"]}'},
    ) == ""
    assert compose_visible_defect(
        "Do you confirm?",
        "confirmation",
        "delete the note Ideas",
        {"situation": '{"kind":"confirmation","polarity":"pending","choices":["confirm","cancel"]}'},
    ) == "missing_confirmation_choice"
    assert compose_visible_defect(
        "No la encontré.",
        "error",
        "abre Firefox",
        {"situation": '{"kind":"failure","cause":"app_not_found","polarity":"failure","target":"Firefox"}'},
    ) == ""
    assert compose_visible_defect(
        "Listo, Discord se silenció.",
        "status",
        "open Discord y silencia",
        {
            "situation": (
                '{"kind":"operation","operation":"app.open",'
                '"polarity":"success","observed":{"app":"Discord"}}'
            )
        },
    ) == "extra_claim"
    assert compose_visible_defect(
        "Listo, el estado observable es que el audio no está mutado.",
        "status",
        "reactiva el audio",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":false}}'
            )
        },
    ) == "internal_code"
    assert compose_visible_defect(
        "Muted: false.",
        "status",
        "unmute the audio",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":false}}'
            )
        },
    ) == "internal_code"
    assert compose_visible_defect(
        "Muted.",
        "status",
        "mute the speakers",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":true}}'
            )
        },
    ) == "copied_instruction"
    assert compose_visible_defect(
        "Unmuted.",
        "status",
        "unmute the audio",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":false}}'
            )
        },
    ) == "copied_instruction"
    assert compose_visible_defect(
        "The speakers are muted.",
        "status",
        "mute the speakers",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":true}}'
            )
        },
    ) == ""
    assert compose_visible_defect(
        "The audio is unmuted.",
        "status",
        "unmute the audio",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":false}}'
            )
        },
    ) == ""
    assert compose_visible_defect(
        "Listo, los altavoces están silenciados.",
        "status",
        "silencia los altavoces",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":true}}'
            )
        },
    ) == ""
    assert compose_visible_defect(
        "Listo, el volumen está mutado.",
        "status",
        "silencia los altavoces",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":true}}'
            )
        },
    ) == "extra_claim"
    assert compose_visible_defect(
        "I couldn't: the wait ran out.",
        "error",
        "close Chrome",
        {"situation": '{"kind":"failure","cause":"timeout","polarity":"failure","target":"Chrome"}'},
    ) == ""
    assert compose_visible_defect(
        "I couldn't: wait ended.",
        "error",
        "close Chrome",
        {"situation": '{"kind":"failure","cause":"timeout","polarity":"failure","target":"Chrome"}'},
    ) == "copied_instruction"
    assert compose_visible_defect(
        "I couldn't: the wait ended ended ended.",
        "error",
        "close Chrome",
        {"situation": '{"kind":"failure","cause":"timeout","polarity":"failure","target":"Chrome"}'},
    ) == "invented"
    assert compose_visible_defect(
        "I couldn't: mission unfinished.",
        "error",
        "open Word and wipe the disk",
        {"situation": '{"kind":"failure","cause":"mission_failed","polarity":"failure"}'},
    ) == "copied_instruction"
    assert compose_visible_defect(
        "I couldn't: I don't do that.",
        "error",
        "open Word and wipe the disk",
        {"situation": '{"kind":"failure","cause":"mission_failed","polarity":"failure"}'},
    ) == ""
    assert compose_visible_defect(
        "No pude: no respondo.",
        "error",
        "abre Steam y borra el disco",
        {"situation": '{"kind":"failure","cause":"mission_failed","polarity":"failure"}'},
    ) == "extra_claim"
    assert compose_visible_defect(
        "No pude: eso no lo hago.",
        "error",
        "abre Steam y borra el disco",
        {"situation": '{"kind":"failure","cause":"mission_failed","polarity":"failure"}'},
    ) == ""
    assert compose_visible_defect(
        "La volumen está en 10.",
        "status",
        "pon el volumen a 10",
        {
            "situation": (
                '{"kind":"operation","polarity":"success","observed":{"level":10}}'
            )
        },
    ) == "wrong_gender"
    assert compose_visible_defect(
        "No pude: el tiempo tiempo se agotó el tiempo.",
        "error",
        "abre Calculadora",
        {
            "situation": (
                '{"kind":"failure","cause":"timeout","polarity":"failure",'
                '"target":"Calculadora"}'
            )
        },
    ) == "invented"
    assert compose_visible_defect(
        "La hora localTime es 22:10.",
        "status",
        "qué hora es ahora",
        {
            "situation": (
                '{"kind":"operation","operation":"system.time",'
                '"polarity":"success","observed":{"localTime":"22:10"}}'
            )
        },
    ) == "internal_code"
    time_contract = (
        '{"kind":"operation","operation":"system.time","polarity":"success",'
        '"observed":{"version":1,"utc":"2026-09-03T02:10:00.0000000+00:00",'
        '"localUtcOffsetMinutes":-240}}'
    )
    assert compose_visible_defect(
        "Listo, son las 22:10.",
        "status",
        "qué hora es ahora",
        {"situation": time_contract},
    ) == ""
    assert compose_visible_defect(
        "Listo, son las 2:10.",
        "status",
        "qué hora es ahora",
        {"situation": time_contract},
    ) == "missing_name"
    assert compose_visible_defect(
        "No pude: no pude encontrarlo.",
        "status",
        "qué hora es ahora",
        {"situation": time_contract},
    ) == "asserted_failure"
    assert compose_visible_defect(
        "Listo, el volumen está en 100 y son las 14:30.",
        "status",
        "Dime la hora y el estado del audio.",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.volume",'
                '"polarity":"success","observed":{"level":100}}'
            )
        },
    ) == "extra_claim"
    assert compose_visible_defect(
        "Sigo, el estado es que Steam está abierto.",
        "status",
        "abre Steam y ve a la biblioteca",
        {"situation": '{"kind":"status","cause":"acting","polarity":"success"}'},
    ) == "internal_code"
    assert compose_visible_defect(
        'Gamma, el título es "Gamma".',
        "status",
        "crea la nota Gamma",
        {
            "situation": (
                '{"kind":"operation","operation":"note.create",'
                '"polarity":"success","observed":{"title":"Gamma"}}'
            )
        },
    ) == "copied_instruction"
    assert compose_visible_defect(
        "La nota Gamma está abierta.",
        "status",
        "crea la nota Gamma",
        {
            "situation": (
                '{"kind":"operation","operation":"note.create",'
                '"polarity":"success","observed":{"title":"Gamma"}}'
            )
        },
    ) == "extra_claim"
    assert compose_visible_defect(
        "La ventanaien la ventana.",
        "status",
        "cierra la ventana",
        {"situation": '{"kind":"operation","operation":"app.close","polarity":"success"}'},
    ) == "invented"
    assert compose_visible_defect(
        "La ventana activa.",
        "status",
        "cierra la ventana activa",
        {"situation": '{"kind":"operation","operation":"app.close","polarity":"success"}'},
    ) == "missing_state"
    assert compose_visible_defect(
        "La ventana está cerrada.",
        "status",
        "cierra la ventana",
        {"situation": '{"kind":"operation","operation":"app.close","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "No pude: la terminal ya terminado de esperar.",
        "error",
        "abre la terminal",
        {"situation": '{"kind":"failure","cause":"timeout","polarity":"failure","target":"Terminal"}'},
    ) == "invented"
    assert compose_visible_defect(
        "Estado observable: El audio ya fue reactivado.",
        "status",
        "reactiva el audio",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":false}}'
            )
        },
    ) == ""
    assert compose_visible_defect(
        "Listo, el audio ya no está silenciado.",
        "status",
        "reactiva el audio",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":false}}'
            )
        },
    ) == ""
    assert compose_visible_defect(
        "Los altavoces están silo.",
        "status",
        "silencia los altavoces",
        {
            "situation": (
                '{"kind":"operation","operation":"audio.mute",'
                '"polarity":"success","observed":{"muted":true}}'
            )
        },
    ) == "invented"
    assert compose_visible_defect(
        "Spotifylight is playing.",
        "status",
        "open Spotify",
        {
            "situation": (
                '{"kind":"operation","operation":"app.open","polarity":"success",'
                '"observed":{"app":"Spotify","playing":true}}'
            )
        },
    ) == "invented"
    assert compose_visible_defect(
        "Listo, Word está abierto.",
        "status",
        "abre Word",
        {
            "situation": (
                '{"kind":"operation","operation":"app.open","polarity":"success",'
                '"observed":{"app":"Word"}}'
            )
        },
    ) == ""
    assert compose_visible_defect(
        "Say Word is open.",
        "status",
        "open Word",
        {
            "situation": (
                '{"kind":"operation","operation":"app.open","polarity":"success",'
                '"observed":{"app":"Word"}}'
            )
        },
    ) == "copied_instruction"
    assert compose_visible_defect(
        "el volumen está en 80.",
        "status",
        "sube el volumen a 80",
        {
            "situation": (
                '{"kind":"operation","polarity":"success","observed":{"level":80}}'
            )
        },
    ) == "lowercase"
    assert compose_visible_defect(
        "Calculadora está abierto.",
        "status",
        "abre Calculadora",
        {
            "situation": (
                '{"kind":"operation","polarity":"success","observed":{"app":"Calculadora"}}'
            )
        },
    ) == "wrong_gender"
    assert compose_visible_defect(
        "Clarify what you mean.",
        "clarification",
        "close it",
        {"situation": '{"kind":"clarification","polarity":"pending"}'},
    ) == "clarification_not_a_question"
    mission_facts = {
        "situation": (
            '{"kind":"status","cause":"mission_completed","polarity":"success",'
            '"steps":["Abrí Word.","Creé la nota «Borrador»."]}'
        )
    }
    assert compose_visible_defect(
        "Listo, la nota «Borrador» fue creada con éxito.",
        "status",
        "abre Word y crea una nota",
        mission_facts,
    ) == "missing_name"
    assert compose_visible_defect(
        "Listo, Abrí Word y creé la nota «Borrador».",
        "status",
        "abre Word y crea una nota",
        mission_facts,
    ) == ""
    assert compose_visible_defect(
        "No pude: se agotó el tiempo.",
        "error",
        "close Chrome",
        fail,
    ) == "wrong_language"


def test_compose_rejects_invented_words_on_the_shipped_entry(monkeypatch) -> None:
    captured: list[str] = []

    class FakeClient(llm_mod.LlmRuntime):
        def __init__(self) -> None:  # noqa: D107
            pass

        def _post(self, payload):  # noqa: ANN001
            _ = payload
            return {"choices": [{"message": {"content": "No puedo cuecer las lentejas."}}]}

    client = FakeClient()
    text = client.compose_user_message(
        "cierra la olla",
        "error",
        {"situation": '{"kind":"failure","cause":"timeout","polarity":"failure"}'},
    )
    captured.append(text)
    assert text == ""


def test_system_time_contract_is_utc_and_offset_not_localtime() -> None:
    observed = {
        "version": 1,
        "utc": "2026-09-03T06:57:52.1829160+00:00",
        "localUtcOffsetMinutes": -240,
    }
    assert _local_clock_from_observed(observed) == "02:57"
    assert _local_clock_from_observed({"localTime": "22:10"}) is None
    payload = _compose_situation_payload(
        {
            "kind": "operation",
            "polarity": "success",
            "observed": observed,
        },
        "es",
        "¿Qué hora es?",
    )
    assert payload["clock"] == "02:57"
    assert "seen" not in payload
    assert "utc" not in payload
    assert "localUtcOffsetMinutes" not in payload
    assert "localTime" not in payload
    assert "polarity" not in payload
    assert "kind" not in payload
    net_payload = _compose_situation_payload(
        {
            "operation": "network.status",
            "polarity": "success",
            "observed": {
                "online": True,
                "connectedInterfaceCount": 24,
                "interfaceTypes": ["ethernet", "wireless80211"],
            },
        },
        "en",
        "are you connected?",
    )
    assert net_payload["seen"] == {"online": True}

    captured: list[dict] = []

    class FakeClient(llm_mod.LlmRuntime):
        def __init__(self) -> None:  # noqa: D107
            pass

        def _post(self, payload):  # noqa: ANN001
            captured.append(payload)
            return {"choices": [{"message": {"content": "Listo, son las 2:57."}}]}

    client = FakeClient()
    text = client.compose_user_message(
        "¿Qué hora es?",
        "status",
        {
            "situation": json.dumps(
                {
                    "kind": "operation",
                    "operation": "system.time",
                    "polarity": "success",
                    "observed": observed,
                },
                ensure_ascii=False,
            )
        },
    )
    assert text == "Listo, son las 2:57."
    blob = json.dumps(captured, ensure_ascii=False)
    assert "02:57" in blob
    assert "clock" in blob
    assert "Do not introduce yourself" in blob
    assert "State the time in clock" in blob
    assert "Do not set the clock" in blob
    assert "Do not describe presence" in blob
    captured.clear()
    granite_clock_audio = FakeClient()
    granite_clock_audio.compose_user_message(
        "Dime la hora y el estado del audio.",
        "status",
        {
            "situation": json.dumps(
                {
                    "kind": "status",
                    "cause": "mission_completed",
                    "polarity": "success",
                    "steps": [
                        json.dumps(
                            {
                                "observed": {
                                    "utc": "2026-09-05T09:14:00+00:00",
                                    "localUtcOffsetMinutes": -240,
                                }
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {"observed": {"muted": False, "level": 40}},
                            ensure_ascii=False,
                        ),
                    ],
                },
                ensure_ascii=False,
            )
        },
    )
    clock_audio_blob = json.dumps(captured, ensure_ascii=False)
    assert "05:14" in clock_audio_blob
    assert "clock" in clock_audio_blob
    assert "Name the local clock and mute or volume" in clock_audio_blob
    assert "Name only the local clock" not in clock_audio_blob
    assert "system.time" not in clock_audio_blob
    assert '"steps"' not in clock_audio_blob
    assert compose_visible_defect(
        "05:14",
        "status",
        "Dime la hora y el estado del audio.",
        {
            "situation": json.dumps(
                {
                    "kind": "status",
                    "cause": "mission_completed",
                    "polarity": "success",
                    "steps": [
                        json.dumps(
                            {
                                "observed": {
                                    "utc": "2026-09-05T09:14:00+00:00",
                                    "localUtcOffsetMinutes": -240,
                                }
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {"observed": {"muted": False, "level": 40}},
                            ensure_ascii=False,
                        ),
                    ],
                },
                ensure_ascii=False,
            )
        },
    ) == "missing_name"
    assert compose_visible_defect(
        "Son las 05:14 y el volumen 40 no está silenciado.",
        "status",
        "Dime la hora y el estado del audio.",
        {
            "situation": json.dumps(
                {
                    "kind": "status",
                    "cause": "mission_completed",
                    "polarity": "success",
                    "steps": [
                        json.dumps(
                            {
                                "observed": {
                                    "utc": "2026-09-05T09:14:00+00:00",
                                    "localUtcOffsetMinutes": -240,
                                }
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {"observed": {"muted": False, "level": 40}},
                            ensure_ascii=False,
                        ),
                    ],
                },
                ensure_ascii=False,
            )
        },
    ) == ""
    live_audio_facts = {
        "situation": json.dumps(
            {
                "kind": "status",
                "cause": "mission_completed",
                "polarity": "success",
                "steps": [
                    json.dumps(
                        {
                            "observed": {
                                "utc": "2026-09-05T10:01:00+00:00",
                                "localUtcOffsetMinutes": -240,
                            }
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {
                            "observed": {
                                "operation": "audio.status",
                                "state": {"volumePercent": 40, "muted": False},
                            }
                        },
                        ensure_ascii=False,
                    ),
                ],
            },
            ensure_ascii=False,
        )
    }
    captured.clear()
    granite_clock_audio.compose_user_message(
        "Dime la hora y el estado del audio.",
        "status",
        live_audio_facts,
    )
    live_blob = json.dumps(captured, ensure_ascii=False)
    assert "06:01" in live_blob
    assert "Name the local clock and mute or volume" in live_blob
    assert "volumePercent" not in live_blob
    assert compose_visible_defect(
        "06:01",
        "status",
        "Dime la hora y el estado del audio.",
        live_audio_facts,
    ) == "missing_name"
    assert compose_visible_defect(
        "Son las 06:01 y el volumen 40 no está silenciado.",
        "status",
        "Dime la hora y el estado del audio.",
        live_audio_facts,
    ) == ""
    assert compose_visible_defect(
        "La hora y el estado del audio.",
        "status",
        "Dime la hora y el estado del audio.",
        {
            "situation": json.dumps(
                {
                    "kind": "status",
                    "cause": "mission_completed",
                    "polarity": "success",
                    "steps": [
                        json.dumps(
                            {
                                "observed": {
                                    "utc": "2026-09-05T09:14:00+00:00",
                                    "localUtcOffsetMinutes": -240,
                                }
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {"observed": {"muted": False, "level": 40}},
                            ensure_ascii=False,
                        ),
                    ],
                },
                ensure_ascii=False,
            )
        },
    ) == "extra_claim"
    assert "localTime" not in blob
    assert "localUtcOffsetMinutes" not in blob
    assert "Tipo de respuesta" not in blob
    clock_only_facts = {
        "situation": json.dumps(
            {
                "kind": "operation",
                "operation": "system.time",
                "polarity": "success",
                "observed": {
                    "utc": "2026-09-05T12:08:00.0000000+00:00",
                    "localUtcOffsetMinutes": -240,
                },
            },
            ensure_ascii=False,
        )
    }
    assert compose_visible_defect(
        "BAXY, hoy es las 08:08 y tú eres parte de esta situación.",
        "status",
        "¿Qué hora es?",
        clock_only_facts,
    ) == "extra_claim"
    assert compose_visible_defect(
        "BAXY te dice que a las 08:08, sigue adelante con confianza.",
        "status",
        "¿Qué hora es?",
        clock_only_facts,
    ) == "extra_claim"
    assert compose_visible_defect(
        "08:08",
        "status",
        "¿Qué hora es?",
        clock_only_facts,
    ) == ""
    assert compose_visible_defect(
        "Status: success at 02:53",
        "status",
        "clock please",
        {
            "situation": json.dumps(
                {
                    "kind": "operation",
                    "operation": "system.time",
                    "polarity": "success",
                    "observed": observed,
                },
                ensure_ascii=False,
            )
        },
    ) == "internal_code"
    assert compose_visible_defect(
        "I cannot proceed with this request due to a failure in request analysis.",
        "welcome",
        "just say hi",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == "internal_code"
    assert compose_visible_defect(
        'El mensaje es: "Listo, REDPC\\usuario".',
        "welcome",
        "tú eres un él, no?",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == "internal_code"
    assert compose_visible_defect(
        "No pude: no pude usar esa respuesta.",
        "welcome",
        "Hola, ¿qué puedes hacer?",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == "internal_code"
    assert compose_visible_defect(
        "No pude: no pude usar esa respuesta.",
        "error",
        "Hola",
        {"situation": '{"kind":"failure","cause":"out_of_catalog","polarity":"failure"}'},
    ) in {"internal_code", "extra_claim"}
    assert compose_visible_defect(
        "I cannot reserving a cabin on Ganymede.",
        "error",
        "reserve a cabin on Ganymede",
        {"situation": '{"kind":"failure","cause":"out_of_catalog","polarity":"failure"}'},
    ) == "invented"
    assert compose_visible_defect(
        "¿Qué significa exactamente \"UTC\" en este contexto?",
        "clarification",
        "One sentence: define UTC.",
        {"situation": '{"kind":"clarification","cause":"ambiguous_request","polarity":"pending"}'},
    ) == "internal_code"
    assert compose_visible_defect(
        "UTC is the time standard other zones offset from.",
        "clarification",
        "One sentence: define UTC.",
        {"situation": '{"kind":"clarification","cause":"ambiguous_request","polarity":"pending"}'},
    ) == ""
    assert compose_visible_defect(
        "What is a time zone?",
        "clarification",
        "what is a time zone, one line",
        {"situation": '{"kind":"clarification","cause":"ambiguous_request","polarity":"pending"}'},
    ) == "knowledge_question"
    assert compose_visible_defect(
        "No pude entender la solicitud.",
        "clarification",
        "define UTC in one sentence",
        {"situation": '{"kind":"clarification","cause":"ambiguous_request","polarity":"pending"}'},
    ) == "internal_code"
    assert compose_visible_defect(
        "Hi.",
        "welcome",
        "traduce 'hello' al español, nada más",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == "wrong_language"
    assert compose_visible_defect(
        "Hola.",
        "conversation",
        "traduce 'hello' al español, nada más",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "Buenos días.",
        "conversation",
        "traduce 'good morning' al español, nada más",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "Hola, ¿en qué puedo ayudarte hoy?",
        "conversation",
        "traduce 'good morning' al español, nada más",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "extra_claim"
    assert compose_visible_defect(
        "Eso no lo hago.",
        "conversation",
        "keep going without opening apps",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "asserted_failure"
    assert compose_visible_defect(
        "I'll keep going without opening apps.",
        "conversation",
        "keep going without opening apps",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "Buenos días, compa.",
        "welcome",
        "Buenos días, compa",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "Good afternoon.",
        "welcome",
        "Good afternoon",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "I will not open apps.",
        "conversation",
        "keep going without opening apps",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "I cannot complete that request.",
        "conversation",
        "close that",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "clarification_not_a_question"
    assert compose_visible_defect(
        "Which window or document should I close?",
        "conversation",
        "close that",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "Hi.",
        "conversation",
        "traduce 'hello' al español, nada más",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "wrong_language"
    assert compose_visible_defect(
        "I don't do that.",
        "conversation",
        "What will you refuse to do",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "I will not perform any action that violates ethical guidelines or legal requirements.",
        "conversation",
        "What will you refuse to do",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "extra_claim"
    assert compose_visible_defect(
        "I cannot refuse to do what was asked.",
        "conversation",
        "What will you refuse to do",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "reversed_result"
    assert compose_visible_defect(
        "The PC has a maximum RAM capacity of 64 GB.",
        "conversation",
        "What will you refuse to do",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "extra_claim"
    # Describir el encargo en vez de contestarlo se nombra por lo que es.
    assert compose_visible_defect(
        "I understand the situation and will respond in English as requested.",
        "conversation",
        "What will you refuse to do",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "copied_instruction"
    assert compose_visible_defect(
        "I am BAXY and I am present on the PC.",
        "conversation",
        "What will you refuse to do",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "extra_claim"
    assert compose_visible_defect(
        "I am BAXY, and I see the situation is successful.",
        "conversation",
        "What will you refuse to do",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "extra_claim"
    assert compose_visible_defect(
        "I have seen the previous draft and will proceed with the new instruction based on the current facts.",
        "conversation",
        "What will you refuse to do",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "internal_code"
    assert compose_visible_defect(
        "The effect is closed.",
        "conversation",
        "What will you refuse to do",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "extra_claim"
    assert compose_visible_defect(
        "I will not do harmful acts.",
        "conversation",
        "What will you refuse to do",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "extra_claim"
    assert compose_visible_defect(
        "I will not do harmful things.",
        "conversation",
        "What will you refuse to do",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "extra_claim"
    assert compose_visible_defect(
        "I will not steal.",
        "conversation",
        "What will you refuse to do",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "extra_claim"
    assert compose_visible_defect(
        "I will not book a room on Deimos.",
        "conversation",
        "What will you refuse to do",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "I don't do that.",
        "conversation",
        "what is a time zone, one line",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "asserted_failure"
    assert compose_visible_defect(
        "I'm connected.",
        "status",
        "are you connected?",
        {"situation": '{"kind":"operation","operation":"network.status","polarity":"success"}'},
    ) == "wrong_actor"
    assert compose_visible_defect(
        "I am not connected.",
        "status",
        "are you connected?",
        {"situation": '{"kind":"operation","operation":"network.status","polarity":"success"}'},
    ) == "wrong_actor"
    assert compose_visible_defect(
        "The PC has a network.",
        "status",
        "are you connected?",
        {"situation": '{"kind":"operation","operation":"network.status","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "I am online.",
        "status",
        "are you connected?",
        {"situation": '{"kind":"operation","operation":"network.status","polarity":"success"}'},
    ) == "wrong_actor"
    assert compose_visible_defect(
        "Name the PC network, not yourself.",
        "status",
        "are you connected?",
        {"situation": '{"kind":"operation","operation":"network.status","polarity":"success"}'},
    ) == "copied_instruction"
    assert compose_visible_defect(
        "I see the clock is 04:13 and I'm BAXY living on the PC.",
        "status",
        "clock please",
        {
            "situation": json.dumps(
                {
                    "kind": "operation",
                    "operation": "system.time",
                    "polarity": "success",
                    "observed": {
                        "utc": "2026-09-05T08:13:00+00:00",
                        "localUtcOffsetMinutes": -240,
                    },
                },
                ensure_ascii=False,
            )
        },
    ) == "extra_claim"
    assert compose_visible_defect(
        "I've seen you at 03:46 and am here to help.",
        "status",
        "clock please",
        {
            "situation": json.dumps(
                {
                    "kind": "operation",
                    "operation": "system.time",
                    "polarity": "success",
                    "observed": {
                        "utc": "2026-09-03T07:46:00+00:00",
                        "localUtcOffsetMinutes": -240,
                    },
                },
                ensure_ascii=False,
            )
        },
    ) == "extra_claim"
    assert compose_visible_defect(
        "Buenos días",
        "conversation",
        "Hola, ¿qué puedes hacer?",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "knowledge_greeting"
    assert compose_visible_defect(
        "No tengo acceso a ningún dato adicional; solo sabía que debía responder en español con una frase.",
        "conversation",
        "Explícame con calma qué puedes hacer en este PC y qué no haces, sin abrir nada.",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "internal_code"
    assert compose_visible_defect(
        "Puedo abrir programas y no abro nada que no pidas.",
        "conversation",
        "Explícame con calma qué puedes hacer en este PC y qué no haces, sin abrir nada.",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "Puedo abrir programas y decir la hora en este PC.",
        "conversation",
        "Hola, ¿qué puedes hacer?",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "Hi.",
        "welcome",
        "Hey",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "Hi there! Buenos días! ¿En qué puedo ayudarte hoy?",
        "welcome",
        "Hi there",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == "wrong_language"
    assert compose_visible_defect(
        "Hola, ¿en qué puedo ayudarte hoy?",
        "welcome",
        "Hola, buenas",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "No puedo ayudar porque no tengo herramientas disponibles.",
        "welcome",
        "Hola, buenas",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == "reversed_polarity"
    assert compose_visible_defect(
        "BAXY está listo para trabajar en el borrador del welcome con éxito.",
        "welcome",
        "Hola, buenas",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == "internal_code"
    assert compose_visible_defect(
        "Hi.",
        "error",
        "Hey",
        {"situation": '{"kind":"failure","cause":"ambiguous_request","polarity":"failure"}'},
    ) == "missing_failure"
    assert compose_visible_defect(
        "Configuro el huso horario de forma centralizada.",
        "conversation",
        "define huso horario, una frase",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == "copied_instruction"
    assert compose_visible_defect(
        "Un huso horario es una región que comparte la misma hora civil.",
        "conversation",
        "define huso horario, una frase",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "Puedo abrir programas y decir la hora en este equipo.",
        "conversation",
        "qué puedes hacer en este equipo",
        {"situation": '{"kind":"conversation","polarity":"success"}'},
    ) == ""
    assert compose_visible_defect(
        "Listo, 24 interfaces conectadas, 14 de ellas son ethernet.",
        "status",
        "online?",
        {"situation": '{"kind":"operation","operation":"network.status","polarity":"success"}'},
    ) == "extra_claim"
    assert compose_visible_defect(
        "Hi, I'm BAXY.",
        "welcome",
        "why do time zones exist",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == "knowledge_greeting"
    assert compose_visible_defect(
        "Hi, I'm BAXY.",
        "welcome",
        "traduce 'hello' al español, nada más",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == "wrong_language"
    assert compose_visible_defect(
        "Huso horario definido, una frase.",
        "welcome",
        "define huso horario, una frase",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == "internal_code"
    assert compose_visible_defect(
        "My name is Qwen.",
        "welcome",
        "introduce yourself",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == "internal_code"
    assert compose_visible_defect(
        "Hello, I'm here.",
        "welcome",
        "why do time zones exist",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) == "knowledge_greeting"
    assert compose_visible_defect(
        "BAXY is at 17:17.",
        "status",
        "time now",
        {
            "situation": (
                '{"kind":"operation","operation":"system.time","polarity":"success",'
                '"observed":{"utc":"2026-09-04T21:17:00+00:00","localUtcOffsetMinutes":-240}}'
            )
        },
    ) == "extra_claim"
    assert compose_visible_defect(
        "Hola, BAXY.",
        "clarification",
        "En una frase, qué es un huso horario",
        {"situation": '{"kind":"clarification","cause":"ambiguous_request","polarity":"pending"}'},
    ) == "knowledge_greeting"
    assert compose_visible_defect(
        "The time zone is Central European Time (CET).",
        "clarification",
        "define time zone in one sentence",
        {"situation": '{"kind":"clarification","cause":"ambiguous_request","polarity":"pending"}'},
    ) == "invented"
    assert compose_visible_defect(
        'I do not know what the user is referring to with "this machine".',
        "welcome",
        "what do you do on this machine?",
        {"situation": '{"kind":"welcome","polarity":"success"}'},
    ) in {"internal_code", "missing_name"}
    assert compose_visible_defect(
        "Hecho ya ocurrido a las 15:19.",
        "status",
        "qué marca el reloj",
        {
            "situation": (
                '{"kind":"operation","operation":"system.time","polarity":"success",'
                '"observed":{"utc":"2026-09-04T19:19:00+00:00","localUtcOffsetMinutes":-240}}'
            )
        },
    ) == "copied_instruction"
