"""How this model writes a call, read from its own chat template (MOD3), never from its name.

The mind was written for Qwen3.5's format (qwen3-coder XML: «<tool_call>\\n<function=NAME>», tokenizer.chat_template of
the model file), and read it by hand in five places: the doubt (doubt.py), a call left as text (Mind._next), the stop of
a stub called again (STUB_AGAIN), the read ahead (Mind.prefill) and a fill (LlmServer.fill_call). llama-server already
parses each model's calls by its template (``--jinja``; llama.cpp docs/function-calling.md); what the mind still needs
is read here the same way llama.cpp's own template analysis does it (common/chat.cpp at b11609, the differential
rendering of a template with and without a call): the template renders a few probe conversations (/apply-template) and
the format is what changes between them. Whatever cannot be read from them is None, and the part of the mind that
needs it is off for this model (and its row says so: Mind.warm, «warm.format»).
"""
from __future__ import annotations

import json
import re
import urllib.error
from dataclasses import dataclass
from typing import Any, Callable, Iterable

# Probe texts: none is a substring of a template's own text.
SYSTEM = "PROBE-S-7f3a"
ASKED = "PROBE-U-7f3a"
SAID = "PROBE-A-7f3a"
AFTER = "PROBE-V-7f3a"
RESULT = "PROBE-R-7f3a"
FIRST = "probe_first_7f3a"
SECOND = "probe_second_7f3a"
TOOLS = [{"type": "function", "function": {"name": name, "description": "probe", "parameters": {
    "type": "object", "properties": {"flag": {"type": "boolean"}, "word": {"type": "string"}}}}}
    for name in (FIRST, SECOND)]

# The shape of a call written as JSON, as a template's own format or not ({"name": ..., "arguments": {...}}): the keys
# llama.cpp's parsers read for a JSON call (common/chat.cpp at b11609: «name» with «arguments» or «parameters»).
_JSON_ARGUMENTS = ("arguments", "parameters")
# The form of a model's control token written as text: «<|name|>», «<|name>», «<name|>» (Llama 3.2's «<|python_tag|>»
# before a call, Gemma 4's «<|tool_call>» … «<tool_call|>»); no word for the person has it.
_CONTROL = re.compile(r"<\|[a-z_]+\|?>|<[a-z_]+\|>")
# The tags of the two XML call formats llama.cpp parses (common/chat.cpp at b11609: Hermes 2 Pro's «<tool_call>», the
# qwen3-coder «<function=…>»), written by a model whose own template has other marks.
_TAGS = re.compile(r"</?tool_call>|<function=")

Render = Callable[[list[dict[str, Any]], list[dict[str, Any]], bool], str]


@dataclass(frozen=True)
class CallFormat:
    """What a reply holds where it calls a tool, as this model's template writes it."""

    opening: str  # from the start of the reply to the name: «<tool_call>\n<function=»
    name_end: str  # the text the template writes right after the name, before the arguments: «>\n»
    again: str | None  # after a call, up to the next call's name: «</tool_call>\n<tool_call>\n<function=»
    turn_end: str | None  # what ends a message before the next one: «<|im_end|>\n»
    user_open: str | None  # what opens the person's message: «<|im_start|>user\n»
    bools_as_text: bool  # the template writes a call's boolean as Python's «True»: given as text «true» it is unchanged
    nulls_as_text: bool = False  # DIAX2: and a call's null as Python's «None»: given as text «null» it is unchanged

    @property
    def name_stop(self) -> str:
        """The character that ends a name being written."""
        return self.name_end[:1]

    @property
    def marks(self) -> tuple[str, ...]:
        """The pieces of the opening that only a call writes (Qwen3.5: «<tool_call>», «<function=»); a piece of one or
        two characters (a quote) is not a mark."""
        return tuple(piece for piece in self.opening.split() if len(piece) >= 3)

    @property
    def first_mark(self) -> str:
        """The opening's first piece (Qwen3.5: «<tool_call>»): when it is one token, sampling it is opening a call."""
        return self.opening.split()[0] if self.opening.split() else self.opening

    @property
    def name_open(self) -> str:
        """What the opening writes after its first piece, up to the name (Qwen3.5: «<function=»)."""
        return self.opening[len(self.first_mark):].lstrip()

    def stub_again(self, wire: str) -> str | None:
        """Where a call to ``wire`` begins after another call in the same reply (STUB_AGAIN), or None."""
        return None if self.again is None else f"{self.again}{wire}{self.name_stop}"

    def call_start(self, wire: str) -> str:
        """A call to ``wire`` written up to its arguments (LlmServer.fill_call)."""
        return f"{self.opening}{wire}{self.name_end}"


# The format the mind was written and measured with: Qwen3.5's template (the 4B of the package, MOD2 §2), what derive
# reads from it. Before the warm-up reads the model's own, and for the parts calibrated on it (the decision's sampling).
CALIBRATED = CallFormat(opening="<tool_call>\n<function=", name_end=">\n", again="</tool_call>\n<tool_call>\n<function=",
                        turn_end="<|im_end|>\n", user_open="<|im_start|>user\n", bools_as_text=True,
                        nulls_as_text=True)


def _common(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def _call(name: str, arguments: dict[str, Any], index: int = 0) -> dict[str, Any]:
    return {"id": f"call_{index}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments)}}


class Unrendered(Exception):
    """The server renders no template (the translator to Ollama or an API answers /apply-template with nothing)."""


def _refused(error: Exception) -> bool:
    """Whether a probe failed because of the template (it raised, or the server refused it: an HTTP status), not because
    the server could not be reached (that is the start's own failure, as a vocabulary that could not be read was)."""
    return isinstance(error, urllib.error.HTTPError) or not isinstance(error, OSError)


def derive(render: Render) -> CallFormat | None:
    """The format from probe conversations rendered by the model's template (``render(messages, tools,
    add_generation_prompt)``); None when the template writes no call this way (the probes cannot tell it). Raises
    Unrendered when it renders nothing at all, and what ``render`` raises when the server cannot be reached."""
    head = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": ASKED}]
    tail = [{"role": "user", "content": AFTER}]

    def called(calls: list[dict[str, Any]]) -> str:
        results = [{"role": "tool", "tool_call_id": c["id"], "content": RESULT} for c in calls]
        return render([*head, {"role": "assistant", "content": "", "tool_calls": calls}, *results, *tail], TOOLS, True)

    def probe(make: Callable[[], str]) -> str | None:
        try:
            return make()
        except Exception as error:  # noqa: BLE001 - a template that cannot render this probe gives none of it
            if not _refused(error):
                raise
            return None

    def main(make: Callable[[], str]) -> str | None:
        # The three probes the format needs: a server that refuses one (an HTTP status) is no template read, and the
        # mind keeps the format it had (review REVX1: an error of one request left the 4B without its own).
        try:
            return make()
        except urllib.error.HTTPError as error:
            raise Unrendered(f"the server refused a probe: {error.code}") from error
        except Exception as error:  # noqa: BLE001 - a template that raises on a probe writes no call this way
            if not _refused(error):
                raise
            return None

    words = main(lambda: render([*head, {"role": "assistant", "content": SAID}, *tail], TOOLS, True))
    if words is not None and not words.strip():
        raise Unrendered("the server renders no template")
    one = main(lambda: called([_call(FIRST, {})]))
    filled = main(lambda: called([_call(FIRST, {"word": "x"})]))
    if words is None or one is None or filled is None:
        return None
    asked_at = words.rfind(ASKED)
    # The call's name after the person's message, where the reply is (a template that writes the tools in the system
    # message but not a reply's calls has the name only before it).
    if (asked_at < 0 or SAID not in words or one.rfind(ASKED) != asked_at or one.find(FIRST, asked_at) < 0
            or filled.find(FIRST, asked_at) < 0):
        return None
    before = one[asked_at + len(ASKED):one.find(FIRST, asked_at)]
    # The reply is written after the generation prompt (what the template adds after the last message to open the
    # model's turn: «<|im_end|>\n<|im_start|>assistant\n»); a template may write a past call's turn otherwise than the
    # one it opens (Granite 4.2: «<think></think>» on a line of its own), so the call's opening is what follows the
    # longest end of that prompt the call's turn also holds, without the blank space before it.
    header = words[asked_at + len(ASKED):words.find(SAID, asked_at)]  # a past reply in words: the turn that opens it
    prompt = words[words.rfind(AFTER) + len(AFTER):]
    ends = [header] if header and before.startswith(header) else [
        prompt[i:] for i in range(len(prompt)) if len(prompt[i:].strip()) >= 4 and prompt[i:] in before]
    if not ends:
        return None
    opening = before[before.rfind(ends[0]) + len(ends[0]):].lstrip()
    if not opening:
        return None
    after_one = one[one.find(FIRST, asked_at) + len(FIRST):]
    after_filled = filled[filled.find(FIRST, asked_at) + len(FIRST):]
    shared = after_one[:_common(after_one, after_filled)]
    # Up to a line's end when the arguments begin on a line of their own (Qwen3.5 «>\n<parameter=…»), so a piece both
    # renderings share by chance («<» of «</function>» and «<parameter=») is not taken for the name's end.
    name_end = shared[:shared.rfind("\n") + 1] if "\n" in shared else shared
    if not name_end:
        return None
    turn_end = user_open = None
    asked = probe(lambda: render(head, TOOLS, False))  # the person's message closed, nothing after it
    if asked is not None and ASKED in asked:
        end = asked[asked.rfind(ASKED) + len(ASKED):]
        next_turn = words[words.find(SAID) + len(SAID):words.rfind(AFTER)]  # the model's message ends, the person's opens
        if end and next_turn.startswith(end) and len(next_turn) > len(end):
            turn_end, user_open = end, next_turn[len(end):]
    again = None
    two = probe(lambda: called([_call(FIRST, {}, 0), _call(SECOND, {}, 1)]))  # one call per reply: it raises
    if two is not None and two.find(FIRST, asked_at) >= 0 and two.find(SECOND, asked_at) > two.find(FIRST, asked_at):
        between = two[two.find(FIRST, asked_at) + len(FIRST):two.find(SECOND, asked_at)]
        # The first call's own end: what follows its name when it is the reply's last call, up to the turn's end (else
        # what both renderings share, which may run on into a character the next call and the turn's end begin with,
        # «<» in Granite 4.2).
        own = after_one[:after_one.find(turn_end)] if turn_end and turn_end in after_one else ""
        own = own if own and between.startswith(own) else between[:_common(between, after_one)]
        closed = own.rstrip("\n")
        again = closed[closed.rfind("\n") + 1:] + between[len(closed):] if closed else None
    # DIAX2: the same probe writes a null, so the warm-up asks the server no more than before.
    flagged = probe(lambda: called([_call(FIRST, {"flag": True, "word": None})]))
    written = flagged[flagged.find(FIRST, asked_at):] if flagged is not None and flagged.find(FIRST, asked_at) >= 0 else ""
    bools_as_text = "True" in written and "true" not in written
    nulls_as_text = "None" in written and "null" not in written
    return CallFormat(opening=opening, name_end=name_end, again=again, turn_end=turn_end, user_open=user_open,
                      bools_as_text=bools_as_text, nulls_as_text=nulls_as_text)


def thought_end(thinking: str, plain: str) -> str | None:
    """MODX2: the mark that closes this model's thought, from the generation prompt its template writes with thinking on
    (``thinking``) and off (``plain``), the same conversation: what the prompt off adds past their common part when that
    is one mark (Granite 4.2: on «…assistant\n<think>\n», off «…assistant\n<think></think>» → «</think>»; Qwen3.5: off
    «…<think>\n\n</think>\n\n» → «</think>»). None when the two do not differ so (a template that writes the thought
    elsewhere, Gemma 4's «<|think|>» in the system turn, or none). MOD3: Granite 4.2 begins most replies with that mark
    again after its prompt's empty thought, and it reached the person; a reply that begins with it closes an empty
    thought, as llama.cpp's reasoning parser reads a prompt whose thought is open (common/chat.cpp at b11609,
    thinking_forced_open), so what follows it is the reply (LlmServer._after_thought)."""
    common = _common(thinking, plain)
    mark = plain[common:].strip()
    if not mark or any(c.isspace() for c in mark) or not mark.startswith("<") or not mark.endswith(">"):
        return None
    return mark if thinking[common:].strip() == "" else None


def _arguments(value: Any) -> bool:
    """A call's arguments: an object, or a string that is one (OpenAI's «arguments»)."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return False
    return isinstance(value, dict)


def _json_call(value: Any) -> bool:
    return (isinstance(value, dict) and isinstance(value.get("name") or value.get("function"), (str, dict))
            and any(_arguments(value.get(key)) for key in _JSON_ARGUMENTS if key in value))


def _markup(call_format: CallFormat | None) -> tuple[str, ...]:
    """The marks of the opening that are markup («<tool_call>», «<|tool_call>call:»); one of plain text (Llama 3.2's
    «{"name":») is also how a JSON example begins, and a call of that form is told by its name (_named)."""
    return tuple(m for m in call_format.marks if set(m) & set("<|[")) if call_format is not None else ()


def _named(text: str, names: Iterable[str]) -> bool:
    """One of the tools called by its name: «"name": "app_open"» (a JSON call, also one cut short), or the name opening
    the reply (or after a control token such as Mistral's «[TOOL_CALLS]») with its arguments: «app_open(…)»,
    «[web_search(…)]», «file_read[ARGS]{…}». The names are the catalog's: no word of the person is compared."""
    for name in names:
        at = re.escape(name)
        if re.search(rf'"name"\s*:\s*"{at}"', text) or re.match(rf"(?:\W{{0,3}}|\[[A-Z_]+\]){at}\s*[(\[{{]", text):
            return True
    return False


def written_call(content: str, call_format: CallFormat | None, names: Iterable[str] = (), by_form: bool = True) -> bool:
    """Whether a reply's words hold a call written as text, by its form: a markup mark of this model's call opening, a
    model's control token («<|python_tag|>», «<|tool_call>»: llama.cpp writes one into content when it parses no call),
    the tags of an XML call, a JSON call anywhere in them (an object, or a list of objects, with a name and its
    arguments), or one of the tools ``names`` written as called (_named). Never by what the words say. Not ``by_form``
    (a model whose call opens with a token of its own, which a words-only answer cannot sample: Mind.text_calls_by_form),
    only the marks of its opening, as the mind always read Qwen3.5's («<tool_call>», «<function=»)."""
    text = (content or "").strip()
    if not text:
        return False
    if any(mark in text for mark in _markup(call_format)):
        return True
    if not by_form:
        return False
    if _CONTROL.search(text) or _TAGS.search(text) or _named(text, names):
        return True
    decoder = json.JSONDecoder()
    for at, char in enumerate(text):
        if char not in "{[":
            continue
        try:
            value, _ = decoder.raw_decode(text, at)
        except json.JSONDecodeError:
            continue
        if _json_call(value) or (isinstance(value, list) and value and all(_json_call(v) for v in value)):
            return True
    return False


def may_be_call(content: str, call_format: CallFormat | None, names: Iterable[str] = (), by_form: bool = True) -> bool:
    """While a reply streams, whether what it wrote so far may still become a call written as text (written_call): a
    mark of the opening, a control token, a JSON call begun («{"name"»), a reply that begins as a JSON object, or a tool
    of ``names`` written as called. Then it is no longer told to the voice; the reply itself still goes its way when it
    is whole. Not ``by_form``, only the marks of the opening (written_call)."""
    text = (content or "").lstrip()
    if call_format is not None and any(mark in content for mark in call_format.marks):
        return True
    if not by_form:
        return False
    return (bool(_CONTROL.search(content) or _TAGS.search(content)) or '{"name"' in content
            or text.startswith(("{", "[{")) or _named(text, names))
