"""Inventory of the regular expressions that read text outside ``src/baxy_mind/semantic/`` (owner, 2026-09-24).

    python scripts/inventory_reading_outside_semantic.py            # summary
    python scripts/inventory_reading_outside_semantic.py --write    # regenerate the table in artifacts/
    python scripts/inventory_reading_outside_semantic.py --check    # exit 1 on an unreviewed reader of the person

Every regex site in the mind modules outside ``semantic/`` and in ``src/Baxy.App`` is found (``re.*``, a compiled
pattern's methods, the grammar's ``_has``/``_match``, C# ``Regex.*``, ``Regex`` fields and generated regexes). Its
target is traced back to a parameter — inside the function, then through every caller in the mind — and labelled:
the person's words (``PERSON``), BAXY's own text — a draft, a reply, a question it asks (``BAXY``) — or something
else (a hash, a path, a catalog name, an observation: ``OTHER``). Each function that applies a pattern to the
person's words carries one reviewed class in ``REVIEWED``:

- ``READING``   decides what the person asked; its home is ``semantic/`` (listed here only while it is not);
- ``WORDING``   the person's words are material of BAXY's reply or of its check (an echo, a quote kept, the language
                to answer in), not a reading of the request;
- ``GROUNDING`` the person's words are the evidence a proposed value is checked against, literally;
- ``INPUT``     speech before it is a request (the wake word, a transcript, the listening switch);
- ``INDEX``     the words tokenized for a lexical index (skill passages); no pattern decides a meaning;
- ``MIRROR``    the App enforces, on what it publishes, stores or runs, a rule whose reading the mind also makes.

The App's files carry one class each (``APP_FILES``, with ``APP_METHODS`` where a method differs); ``READING``
there is listed with the reason it is still the App's. The table: ``artifacts/comprobaciones/C03/
UNIFICACION_LECTURA_2026-09-25.md`` (its generated part is rewritten by ``--write``). ``--root`` inventories another
tree (the base of the unification was counted on an extract of ``b0190b9e``).
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MIND = REPO / "src" / "baxy_mind"
APP = REPO / "src" / "Baxy.App"
TABLE = REPO / "artifacts" / "comprobaciones" / "C03" / "UNIFICACION_LECTURA_2026-09-25.md"

PERSON, BAXY, MIXED, OTHER, UNKNOWN = "PERSON", "BAXY", "MIXED", "OTHER", "UNKNOWN"

# ------------------------------------------------------------------ parameter names, by default
PY_PERSON = frozenset({
    "user_text", "objective", "request", "request_text", "current", "evidence", "utterance", "semantic_text",
    "transcript", "previous_user_text", "prior_user_texts", "current_request", "ask", "literal_evidence",
    "user_request", "pending_objective",
})
PY_BAXY = frozenset({
    "draft", "reply", "candidate", "final", "final_content", "prose", "question", "reply_text", "composed",
    "intro", "folded_reply", "visible", "answer_text", "narration",
})
CS_PERSON = frozenset({
    "userText", "user", "objective", "request", "input", "utterance", "transcript", "priorUserText",
    "rearmedObjective", "userMessage",
})
CS_BAXY = frozenset({"reply", "draft", "modelText", "result", "composed", "candidate", "replyText", "response"})

# message["text"], message.get("pendingObjective"): the person's message as the shell sends it.
_PERSON_KEYS = frozenset({"text", "pendingObjective", "objective"})
_MESSAGE_NAMES = frozenset({"message"})
# Calls that return the same text transformed (folded, stripped, cut, joined); any other call starts a new value.
_STRING_METHODS = frozenset({
    "casefold", "lower", "upper", "strip", "lstrip", "rstrip", "replace", "split", "rsplit", "partition",
    "rpartition", "join", "group", "groups", "groupdict", "format", "splitlines", "title", "capitalize",
    "removeprefix", "removesuffix", "translate", "expandtabs", "center", "ljust", "rjust", "start", "end", "span",
})
_TRANSFORMS = frozenset({
    "str", "fold", "_fold", "_reading_fold", "read_fold", "_policy_guard_text", "_strip_request_envelope",
    "_accent_folded_with_punctuation", "_fold_dialogue_text", "_normalized_dialogue_text", "identity_text",
    "normalize", "clause_literal", "sorted", "list", "tuple", "set", "frozenset", "reversed", "iter", "next",
    "FoldForPolicy", "_strip_prompt_labels", "_without_leading_duration_preface", "_strip_trailing_social_closure",
    "_strip_explicit_no_action_frame", "_accent_fold", "enumerate", "zip", "filter", "map",
})

# (file, function) -> {parameter or local: label}, where the name says less than the code does.
SEEDS: dict[tuple[str, str], dict[str, str]] = {
    ("historical_intents.py", "HistoricalIntentRegistry.__init__"): {"rows": OTHER},
    ("voice.py", "WakePhraseMatcher.__init__"): {"aliases": OTHER},
    ("voice_output.py", "_clean_text"): {"value": BAXY},
    ("window_prose_facts.py", "_inventory_identity_counts.process_annotation"): {"match": BAXY},
    ("corrector.py", "unknown_words"): {"known_names": OTHER},
}

_GROUNDING_SEARCH = ("the person's words (and the pages read) are the evidence each word, number or name of the "
                     "search report is checked against; nothing decides what was asked")
_WAKE = "the transcript before it is a request: wake-word and listening checks run on speech, not on a request"
_GROUNDING = "a value the model proposed is accepted only when the person's words contain it literally"

# (file, function) -> (class, reason). Only functions that apply a pattern to the person's words are listed.
REVIEWED: dict[tuple[str, str], tuple[str, str]] = {
    # ------------------------------------------------ llm: the composer's checks and the prompt's material
    ("llm.py", "_literal_reply_defect"): (
        "GROUNDING", "a number in the reply of a said-back literal or a draw must be one the person said"),
    ("llm.py", "_shaped_presentation_text"): (
        "WORDING", "the person's message is the material of the prompt (a numbered list kept, anchor words); "
        "the shape was read by semantic.conversation"),
    ("llm.py", "_shaped_conversation_answer_violates_contract"): (
        "GROUNDING", "a maker or origin the person named is theirs to repeat (_INVENTED_ORIGIN on both texts); "
        "what was asked comes from semantic.conversation readers"),
    ("llm.py", "visible_reply_claims_an_effect"): (
        "GROUNDING", "a claimed act that repeats the person's own words is not invented (asked_words)"),
    ("llm.py", "_screen_count_defect"): ("GROUNDING", "a number the person said may be repeated"),
    ("llm.py", "_ocr_unsupported_terms.stems"): (
        "GROUNDING", "a word of the screen report must be read on screen or said by the person"),
    ("llm.py", "_search_report_unsourced_numbers"): ("GROUNDING", _GROUNDING_SEARCH),
    ("llm.py", "_search_report_unsourced_words"): ("GROUNDING", _GROUNDING_SEARCH),
    ("llm.py", "_search_report_speaks_as_a_page"): ("GROUNDING", _GROUNDING_SEARCH),
    ("llm.py", "_search_report_shows_the_search"): ("GROUNDING", _GROUNDING_SEARCH),
    ("llm.py", "_search_report_off_subject"): (
        "GROUNDING", "the proper names the person wrote are the subject the report must be about"),
    ("llm.py", "_weather_fact_defect"): (
        "GROUNDING", "a number the person said is theirs to repeat, never a measurement; what the weather "
        "question asks is read by semantic.web"),
    ("llm.py", "_unverified_present_fact"): (
        "GROUNDING", "a date or figure about now may only restate what the person said or what was read"),
    ("llm.py", "compose_visible_defect"): (
        "GROUNDING", "identifiers and literals the person typed are allowed in the reply, and an echo of the "
        "request is rejected; every reading of what was asked is a semantic reader it calls"),
    ("llm.py", "_unsupported_request_anchor_token"): (
        "WORDING", "picks which of the person's words a limit must quote (an anchor), not what they asked"),
    ("llm.py", "_cut_request_tail"): ("WORDING", "the last words of a cut message, quoted back in the question"),
    ("llm.py", "_bare_path_name"): ("WORDING", "the file name of a pasted path, quoted back in the question"),
    ("llm.py", "LlmRuntime.clarify_unresolved_input"): (
        "WORDING", "the question BAXY writes must not echo the person's words (echo check); the kind of input "
        "was read by semantic.guards"),
    # ------------------------------------------------ other mind modules
    ("first_signal.py", "_snippet"): ("WORDING", "the request quoted in the fixture's progress line"),
    ("planner.py", "_tokens"): ("GROUNDING", _GROUNDING),
    ("planner.py", "_grounding_tokens"): ("GROUNDING", _GROUNDING),
    ("planner.py", "_value_is_grounded"): ("GROUNDING", _GROUNDING),
    ("planner.py", "_number_is_grounded"): ("GROUNDING", _GROUNDING),
    ("skill_registry.py", "_token_sequence"): (
        "INDEX", "the request tokenized to rank skill passages lexically; no pattern decides a meaning"),
    ("corrector.py", "unknown_words"): (
        "INPUT", "the ear's repair (lo mal dicho lo arregla BAXY): words checked against the catalog lexicon "
        "before any reading; decides no intention (module contract)"),
    ("corrector.py", "unintelligible_input"): (
        "INPUT", "the noise check of the ear's repair, consumed by semantic.guards; decides no intention"),
    ("asr_fusion.py", "_exhaustive_report_language"): (
        "INPUT", "selection between ASR hypotheses; the product does not import asr_fusion (tests and a "
        "revalidation script do): a candidate for APLAZADOS, not a reader of the turn"),
    ("asr_fusion.py", "_terminal_status_effect"): (
        "INPUT", "selection between ASR hypotheses (not imported by the product)"),
    ("voice.py", "WakePhraseMatcher.strip"): ("INPUT", _WAKE),
    ("wake_cascade.py", "normalize_lexical_transcript"): ("INPUT", _WAKE),
    ("wake_verifier.py", "lexical_words"): ("INPUT", _WAKE),
}

# The App (C#): one class per file, with the methods that differ.
APP_FILES: dict[str, tuple[str, str]] = {
    "NaturalMemoryRequestParser.cs": (
        "READING", "App-owned private-memory route (save, recall, forget) decided before the mind; SEMANTICA "
        "«Destino» schedules it as semantic/memory.py. Moving it routes memory turns through the mind and "
        "re-decides where the private store's reading lives: a protocol change, not a behaviour-identical move"),
    "NaturalNoteRequestParser.cs": (
        "READING", "the App's quick-note route (MainWindowViewModel, MissionInput) beside the mind's note readers "
        "(semantic/notes): two readers of one thing, kept until the App takes the mind's note decision, a "
        "routing change to measure in the window"),
    "NaturalSystemStatusRequestParser.cs": (
        "READING", "shell shortcut «hora» → system.time without a mind round-trip (latency); the mind reads the "
        "same request (semantic.network); UserMessagePolicy also judges clock replies with it"),
    "NaturalApplicationRequestParser.cs": (
        "READING", "App open route and the alias normalization of an extracted application argument; the mind "
        "reads the same requests (semantic.apps)"),
    "NaturalAudioRequestParser.cs": (
        "READING", "App audio route (volume, audited correction); the mind reads the same requests "
        "(semantic.audio, semantic.levels)"),
    "UserMessagePolicy.cs": (
        "MIRROR", "the App's policy on every text it publishes, its own fallbacks included: a reply is judged "
        "against what was asked, so the policy reads the request with twins of the mind's readers (calendar "
        "parts, countdown, clitic volume, visual content, out-of-world); consuming the mind's reading needs the "
        "compose result to carry it"),
    "MemoryOperationProtection.cs": (
        "MIRROR", "the App runs a memory operation only on the person's explicit confirm/cancel of that exact "
        "invocation (invariant 4) and never stores a secret"),
    "NoteDisambiguation.cs": (
        "MIRROR", "the person's choice among the notes the App listed, bound to that pending list"),
    "VoiceListenCommand.cs": ("INPUT", "the listening switch, which must work without the mind"),
    "ObservedResponseLiterals.cs": ("WORDING", "observed names masked in BAXY's own text"),
    "FieldProductChannel.cs": ("OTHER", "model identity strings of the runtime manifest"),
}
APP_METHODS: dict[tuple[str, str], tuple[str, str]] = {
    ("NaturalMemoryRequestParser.cs", "ContainsSensitiveMaterial"): (
        "MIRROR", "the App refuses to store a secret whatever was read (also used by MemoryOperationProtection)"),
    ("NaturalMemoryRequestParser.cs", "TryCreateSensitiveSave"): (
        "MIRROR", "a secret offered to the private memory is refused by the App that stores it"),
    ("NaturalMemoryRequestParser.cs", "TrySafeSensitiveCapturedValue"): (
        "MIRROR", "the value to store is checked by the App that stores it"),
    ("NaturalMemoryRequestParser.cs", "TrySafeCapturedValue"): (
        "MIRROR", "the value to store is checked by the App that stores it"),
    ("NaturalMemoryRequestParser.cs", "LooksLikeCredentialToken"): (
        "MIRROR", "the App refuses to store a credential"),
    ("NaturalApplicationRequestParser.cs", "TryNormalizeKnownAlias"): (
        "GROUNDING", "an application argument the mind extracted is normalized to a catalog alias"),
    ("UserMessagePolicy.cs", "Error"): ("OTHER", "a stable diagnostic code, not text"),
    ("UserMessagePolicy.cs", "RequiredBaxyActions"): ("OTHER", "the situation JSON the App composed"),
    ("UserMessagePolicy.cs", "RequiredLiteralFacts"): ("OTHER", "the situation JSON the App composed"),
}


@dataclass(frozen=True)
class Site:
    file: str
    line: int
    function: str
    call: str
    target: str
    label: str


# ------------------------------------------------------------------ Python
_RE_METHODS = frozenset({"search", "match", "fullmatch", "findall", "finditer", "sub", "subn", "split"})


def _compiled_names() -> frozenset[str]:
    names: set[str] = set()
    for path in MIND.rglob("*.py"):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and value.func.attr == "compile" \
                    and isinstance(value.func.value, ast.Name) and value.func.value.id == "re":
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                names.update(target.id for target in targets if isinstance(target, ast.Name))
    return frozenset(names)


def _regex_target(node: ast.Call, compiled: frozenset[str]) -> tuple[str, ast.expr | None] | None:
    function = node.func
    if isinstance(function, ast.Attribute):
        base = function.value
        if isinstance(base, ast.Name) and base.id == "re" and function.attr in _RE_METHODS:
            index = 2 if function.attr in {"sub", "subn"} else 1
            return f"re.{function.attr}", (node.args[index] if len(node.args) > index else None)
        base_name = base.attr if isinstance(base, ast.Attribute) else base.id if isinstance(base, ast.Name) else None
        if function.attr in _RE_METHODS and base_name in compiled:
            index = 1 if function.attr in {"sub", "subn"} else 0
            return f"{base_name}.{function.attr}", (node.args[index] if len(node.args) > index else None)
        if function.attr in {"_has", "_match"}:
            return function.attr, (node.args[0] if node.args else None)
    if isinstance(function, ast.Name) and function.id in {"_has", "_match"}:
        return function.id, (node.args[0] if node.args else None)
    return None


def _is_message(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id in _MESSAGE_NAMES


def _names(node: ast.AST | None) -> set[str]:
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name)} if node is not None else set()


def _join(labels: set[str]) -> str:
    """The person's words and BAXY's together are MIXED; an unresolved parameter stays visible."""

    if MIXED in labels or {PERSON, BAXY} <= labels:
        return MIXED
    if PERSON in labels:
        return PERSON
    unknown = sorted(label for label in labels if label.startswith(UNKNOWN))
    if unknown:
        return unknown[0]
    return BAXY if BAXY in labels else OTHER


def _assigned(target: ast.AST) -> list[str]:
    return [child.id for child in ast.walk(target) if isinstance(child, ast.Name)]


@dataclass
class _Function:
    file: str
    qualname: str
    node: ast.FunctionDef | ast.AsyncFunctionDef
    parent: _Function | None
    is_method: bool


def _functions() -> list[_Function]:
    found: list[_Function] = []
    for path in sorted(MIND.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))

        def walk(body: list[ast.AST], prefix: str, parent: _Function | None, in_class: bool) -> None:
            for node in body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    function = _Function(path.name, prefix + node.name, node, parent, in_class)
                    found.append(function)
                    walk(list(ast.iter_child_nodes(node)), function.qualname + ".", function, False)
                elif isinstance(node, ast.ClassDef):
                    walk(node.body, prefix + node.name + ".", parent, True)
                elif isinstance(node, ast.stmt):
                    walk(list(ast.iter_child_nodes(node)), prefix, parent, in_class)

        walk(tree.body, "", None, False)
    return found


def _own_nodes(function: ast.AST) -> list[ast.AST]:
    """The function's nodes without its nested functions (each is analysed on its own)."""

    nodes: list[ast.AST] = []

    def collect(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            nodes.append(child)
            collect(child)

    collect(function)
    return nodes


def _parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    return [argument.arg for argument in node.args.posonlyargs + node.args.args + node.args.kwonlyargs]


def _default_label(name: str) -> str:
    if name in {"self", "cls"}:
        return OTHER
    return PERSON if name in PY_PERSON else BAXY if name in PY_BAXY else f"{UNKNOWN}:{name}"


def _analyse(
    function: _Function, inherited: dict[str, str], from_callers: dict[tuple[str, str, str], str],
    compiled: frozenset[str],
) -> tuple[dict[str, str], list[Site], list[tuple[str, list[tuple[object, str]]]]]:
    labels = dict(inherited)
    seeds = SEEDS.get((function.file, function.qualname), {})
    for name in _parameters(function.node):
        label = seeds.get(name) or _default_label(name)
        if label.startswith(UNKNOWN) and (function.file, function.qualname, name) in from_callers:
            label = from_callers[(function.file, function.qualname, name)]
        labels[name] = label
    for name, label in seeds.items():
        labels.setdefault(name, label)
    nodes = _own_nodes(function.node)

    def label_of(expression: ast.AST | None) -> str:
        """Whose text a value is. Only text transforms carry it: a call that computes something new (a model
        reply, a count, a lookup) starts a value of its own."""

        if expression is None or isinstance(expression, ast.Constant):
            return OTHER
        if isinstance(expression, ast.Name):
            return labels.get(expression.id, OTHER)
        if isinstance(expression, ast.Subscript):
            key = expression.slice
            if isinstance(key, ast.Constant) and key.value in _PERSON_KEYS and _is_message(expression.value):
                return PERSON
            return label_of(expression.value)
        if isinstance(expression, ast.Attribute):
            return label_of(expression.value)
        if isinstance(expression, ast.Call):
            function = expression.func
            arguments = list(expression.args) + [keyword.value for keyword in expression.keywords]
            if _regex_target(expression, compiled) is not None:
                return label_of(_regex_target(expression, compiled)[1])
            if isinstance(function, ast.Attribute):
                if function.attr == "get" and arguments and isinstance(arguments[0], ast.Constant) \
                        and arguments[0].value in _PERSON_KEYS and _is_message(function.value):
                    return PERSON
                if function.attr in _STRING_METHODS:
                    return _join({label_of(function.value), *(label_of(argument) for argument in arguments)})
            name = function.id if isinstance(function, ast.Name) else function.attr \
                if isinstance(function, ast.Attribute) else None
            if name in _TRANSFORMS:
                return _join({label_of(argument) for argument in arguments})
            return OTHER
        if isinstance(expression, (ast.Compare, ast.Lambda)):
            return OTHER
        return _join({label_of(child) for child in ast.iter_child_nodes(expression)
                      if isinstance(child, (ast.expr, ast.comprehension, ast.keyword))})

    for _ in range(4):
        for node in nodes:
            pairs: list[tuple[ast.AST, ast.AST | None]] = []
            if isinstance(node, ast.Assign):
                pairs = [(target, node.value) for target in node.targets]
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
                pairs = [(node.target, node.value)]
            elif isinstance(node, (ast.For, ast.comprehension)):
                pairs = [(node.target, node.iter)]
            elif isinstance(node, ast.withitem) and node.optional_vars is not None:
                pairs = [(node.optional_vars, node.context_expr)]
            for target, value in pairs:
                label = label_of(value)
                if label == OTHER:
                    continue
                for name in _assigned(target):
                    previous = labels.get(name, OTHER)
                    joined = _join({previous, label})
                    if joined != previous and not seeds.get(name):
                        labels[name] = joined
    sites: list[Site] = []
    calls: list[tuple[str, list[tuple[object, str]]]] = []
    for node in nodes:
        if not isinstance(node, ast.Call):
            continue
        found = _regex_target(node, compiled)
        if found is not None:
            call, target = found
            sites.append(Site(function.file, node.lineno, function.qualname, call,
                              ast.unparse(target)[:80] if target is not None else "?", label_of(target)))
            continue
        callee = node.func
        name = callee.id if isinstance(callee, ast.Name) else callee.attr if isinstance(callee, ast.Attribute) else None
        if name is None:
            continue
        bound: list[tuple[object, str]] = [(index, label_of(argument)) for index, argument in enumerate(node.args)
                                           if not isinstance(argument, ast.Starred)]
        bound += [(keyword.arg, label_of(keyword.value)) for keyword in node.keywords if keyword.arg]
        calls.append((name, bound))
    return labels, sites, calls


def python_sites() -> list[Site]:
    compiled = _compiled_names()
    functions = _functions()
    by_name: dict[str, list[_Function]] = defaultdict(list)
    for function in functions:
        by_name[function.qualname.rsplit(".", 1)[-1]].append(function)
    from_callers: dict[tuple[str, str, str], str] = {}
    sites: list[Site] = []
    for _ in range(10):
        sites = []
        evidence: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        labels_of: dict[int, dict[str, str]] = {}
        for function in functions:
            inherited = labels_of.get(id(function.parent), {}) if function.parent is not None else {}
            labels, found, calls = _analyse(function, inherited, from_callers, compiled)
            labels_of[id(function)] = labels
            sites.extend(found)
            for name, bound in calls:
                targets = by_name.get(name, [])
                if len(targets) != 1:
                    continue
                target = targets[0]
                parameters = _parameters(target.node)
                positional = parameters[1:] if target.is_method else parameters
                for slot, label in bound:
                    parameter = positional[slot] if isinstance(slot, int) and slot < len(positional) else slot
                    if isinstance(parameter, str) and parameter in parameters:
                        evidence[(target.file, target.qualname, parameter)].add(label)
        resolved = {}
        for key, labels in evidence.items():
            joined = _join(labels)
            if not joined.startswith(UNKNOWN):
                resolved[key] = joined
        if resolved == from_callers:
            break
        from_callers = resolved
    for path in sorted(MIND.glob("*.py")):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and (found := _regex_target(child, compiled)) is not None:
                    call, target = found
                    sites.append(Site(path.name, child.lineno, "<module>", call,
                                      ast.unparse(target)[:80] if target is not None else "?", OTHER))
    return sites


# ------------------------------------------------------------------ C#
_CS_KEYWORDS = frozenset({"if", "while", "for", "foreach", "switch", "return", "new", "catch", "using", "lock", "when"})
_CS_METHOD = re.compile(
    r"^[ \t]*(?:(?:public|private|internal|protected|static|override|async|sealed|partial|virtual|unsafe|extern|new)"
    r"[ \t]+)+(?!class\b|record\b|struct\b|enum\b|interface\b|const\b|readonly\b|event\b)"
    r"[\w<>\[\],.?() ]*?[ \t](?P<name>\w+)[ \t]*(?:<[^>()]*>)?\((?P<params>[^)]*)",
    re.MULTILINE,
)
_CS_LOCAL = re.compile(
    r"^[ \t]+(?:static[ \t]+)?[\w<>\[\],.?]+[ \t]+(?P<name>\w+)\((?P<params>[^)]*)\)[ \t]*(?:=>)?[ \t]*$",
    re.MULTILINE,
)
_CS_STATIC_CALL = re.compile(r"\bRegex\.(?P<method>IsMatch|Match|Matches|Replace|Split|Count)\(")


def _cs_argument(text: str, start: int) -> str:
    depth, index, quote = 0, start, None
    while index < len(text):
        character = text[index]
        if quote is not None:
            if character == '"' and (quote == "@" or text[index - 1] != "\\"):
                quote = None
        elif character == '"':
            quote = "@" if text[index - 1] == "@" else '"'
        elif character in "([{":
            depth += 1
        elif character in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif character == "," and depth == 0:
            break
        index += 1
    return " ".join(text[start:index].split())


def _cs_parameters(raw: str) -> list[str]:
    names = []
    for part in raw.split(","):
        words = re.findall(r"\w+", part.split("=")[0])
        if words:
            names.append(words[-1])
    return names


def cs_sites() -> list[Site]:
    sites: list[Site] = []
    for path in sorted(APP.glob("*.cs")):
        text = path.read_text(encoding="utf-8")
        fields = set(re.findall(r"\bRegex[ \t]+(\w+)[ \t]*=", text))
        fields |= set(re.findall(r"partial[ \t]+Regex[ \t]+(\w+)\(\)", text))
        methods = [(match.start(), match["name"], _cs_parameters(match["params"]))
                   for pattern in (_CS_METHOD, _CS_LOCAL) for match in pattern.finditer(text)
                   if match["name"] not in _CS_KEYWORDS]
        methods.sort()
        found: list[tuple[int, str, str]] = [
            (match.start(), f"Regex.{match['method']}", _cs_argument(text, match.end()))
            for match in _CS_STATIC_CALL.finditer(text)
        ]
        if fields:
            field_call = re.compile(r"\b(?P<field>" + "|".join(sorted(fields)) + r")(?:\(\))?\.(?P<method>IsMatch|"
                                    r"Match|Matches|Replace|Split|Count)\(")
            found += [(match.start(), f"{match['field']}.{match['method']}", _cs_argument(text, match.end()))
                      for match in field_call.finditer(text)]
        for position, call, target in sorted(found):
            owner = [method for method in methods if method[0] < position]
            name, parameters = (owner[-1][1], owner[-1][2]) if owner else ("<type>", [])
            seeds = SEEDS.get((path.name, name), {})
            labels = set()
            for word in set(re.findall(r"\b\w+\b", re.sub(r'@?"(?:[^"\\]|\\.)*"', " ", target))):
                if word in seeds:
                    labels.add(seeds[word])
                elif word in CS_PERSON:
                    labels.add(PERSON)
                elif word in CS_BAXY:
                    labels.add(BAXY)
                elif word in parameters:
                    labels.add(f"{UNKNOWN}:{word}")
            line = text.count("\n", 0, position) + 1
            sites.append(Site(path.name, line, name, call, target[:80], _join(labels) if labels else OTHER))
    return sites


# ------------------------------------------------------------------ report
_START = "<!-- inventario:inicio (generado por scripts/inventory_reading_outside_semantic.py --write) -->"
_END = "<!-- inventario:fin -->"
_READS_THE_PERSON = frozenset({PERSON, MIXED})


def _reads_the_person(site: Site) -> bool:
    return site.label in _READS_THE_PERSON or site.label.startswith(UNKNOWN)


def classify(sites: list[Site]) -> dict[tuple[str, str], tuple[str, str]]:
    by_function: dict[tuple[str, str], list[Site]] = defaultdict(list)
    for site in sites:
        by_function[(site.file, site.function)].append(site)
    classes: dict[tuple[str, str], tuple[str, str]] = {}
    for key, found in by_function.items():
        if key in REVIEWED:
            classes[key] = REVIEWED[key]
        elif key[0].endswith(".cs") and (key in APP_METHODS or key[0] in APP_FILES):
            classes[key] = APP_METHODS.get(key) or APP_FILES[key[0]]
        elif any(_reads_the_person(site) for site in found):
            classes[key] = ("UNREVIEWED", "")
        elif any(site.label == BAXY for site in found):
            classes[key] = ("WORDING", "patterns on BAXY's own text only")
        else:
            classes[key] = ("OTHER", "patterns on neither the person's nor BAXY's text")
    return classes


def configure(root: Path) -> None:
    global MIND, APP
    MIND = root / "src" / "baxy_mind"
    APP = root / "src" / "Baxy.App"


def summary(sites: list[Site], classes: dict[tuple[str, str], tuple[str, str]]) -> dict[str, object]:
    person_functions = {(site.file, site.function) for site in sites if _reads_the_person(site)}
    mind = [site for site in sites if site.file.endswith(".py")]
    app = [site for site in sites if site.file.endswith(".cs")]
    by_class: Counter[str] = Counter()
    for key in person_functions:
        by_class[classes[key][0]] += 1
    return {
        "regex_sites": {"mind_outside_semantic": len(mind), "app": len(app)},
        "sites_on_the_person": {
            "mind_outside_semantic": sum(_reads_the_person(site) for site in mind),
            "app": sum(_reads_the_person(site) for site in app),
        },
        "functions_on_the_person": {
            "mind_outside_semantic": len({key for key in person_functions if key[0].endswith(".py")}),
            "app": len({key for key in person_functions if key[0].endswith(".cs")}),
        },
        "functions_on_the_person_by_class": dict(sorted(by_class.items())),
    }


def table(sites: list[Site], classes: dict[tuple[str, str], tuple[str, str]]) -> str:
    by_function: dict[tuple[str, str], list[Site]] = defaultdict(list)
    for site in sites:
        by_function[(site.file, site.function)].append(site)
    order = {"READING": 0, "UNREVIEWED": 0, "MIRROR": 1, "INPUT": 2, "INDEX": 3, "GROUNDING": 4, "WORDING": 5}
    out = ["**Mente, fuera de `semantic/`**: cada función que aplica un patrón a las palabras de la persona.", "",
           "| Fichero | Función | Líneas | Clase | Por qué |", "|---|---|---|---|---|"]
    person = [(key, found) for key, found in by_function.items()
              if key[0].endswith(".py") and any(_reads_the_person(site) for site in found)]
    person.sort(key=lambda item: (order.get(classes[item[0]][0], 9), item[0]))
    for (file, function), found in person:
        lines = ", ".join(str(site.line) for site in found if _reads_the_person(site))
        kind, reason = classes[(file, function)]
        out.append(f"| `{file}` | `{function}` | {lines} | {kind} | {reason.replace('|', '/')} |")
    rest: dict[str, Counter[str]] = defaultdict(Counter)
    for key, found in by_function.items():
        if key[0].endswith(".py") and not any(_reads_the_person(site) for site in found):
            rest[key[0]][classes[key][0]] += len(found)
    out += ["", "El resto de los patrones de la mente fuera de `semantic/` no lee el texto de la persona:", "",
            "| Fichero | WORDING (texto de BAXY) | OTHER (hashes, rutas, observaciones, catálogo) |", "|---|---|---|"]
    out += [f"| `{file}` | {rest[file]['WORDING']} | {rest[file]['OTHER']} |" for file in sorted(rest)]
    out += ["", "**App (`src/Baxy.App`)**: por fichero; «sobre la persona» cuenta los sitios cuyo argumento es el texto "
            "de la persona según su nombre (userText, input, command, text…).", "",
            "| Fichero | Patrones | Sobre la persona | Clase | Por qué |", "|---|---|---|---|---|"]
    app_files = sorted({site.file for site in sites if site.file.endswith(".cs")})
    for file in app_files:
        found = [site for site in sites if site.file == file]
        kind, reason = APP_FILES.get(file, ("UNREVIEWED", ""))
        out.append(f"| `{file}` | {len(found)} | {sum(_reads_the_person(site) for site in found)} | {kind} | "
                   f"{reason.replace('|', '/')} |")
    overrides = sorted(key for key in APP_METHODS if any(site.file == key[0] for site in sites))
    if overrides:
        out += ["", "Métodos de la App con otra clase que la de su fichero:", "",
                "| Fichero | Método | Clase | Por qué |", "|---|---|---|---|"]
        out += [f"| `{file}` | `{method}` | {APP_METHODS[(file, method)][0]} | {APP_METHODS[(file, method)][1]} |"
                for file, method in overrides]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPO, help="a tree to inventory (default: this checkout)")
    parser.add_argument("--write", action="store_true", help="rewrite the generated part of the table")
    parser.add_argument("--check", action="store_true", help="exit 1 on a reader of the person not reviewed")
    parser.add_argument("--raw", action="store_true", help="print every function that reads the person's words")
    arguments = parser.parse_args()
    configure(arguments.root)
    sites = python_sites() + cs_sites()
    classes = classify(sites)
    if arguments.raw:
        by_function: dict[tuple[str, str], list[Site]] = defaultdict(list)
        for site in sites:
            by_function[(site.file, site.function)].append(site)
        for key, found in by_function.items():
            if not any(_reads_the_person(site) for site in found):
                continue
            print(f"{key[0]}::{key[1]} [{classes[key][0]}] n={len(found)} L{found[0].line}")
            for site in found:
                if _reads_the_person(site):
                    print(f"    {site.line:>6} {site.label:<18} {site.call:<22} {site.target}")
    counts = summary(sites, classes)
    print(json.dumps(counts, indent=1, ensure_ascii=False))
    if arguments.write:
        text = TABLE.read_text(encoding="utf-8")
        head, _, rest = text.partition(_START)
        _, _, tail = rest.partition(_END)
        generated = f"{_START}\n\n```json\n{json.dumps(counts, indent=1, ensure_ascii=False)}\n```\n\n" \
            f"{table(sites, classes)}\n\n{_END}"
        TABLE.write_bytes((head + generated + tail).encode("utf-8"))
    unreviewed = sorted({key for key, value in classes.items() if value[0] == "UNREVIEWED"})
    if arguments.check and unreviewed:
        for key in unreviewed:
            print("unreviewed:", "::".join(key))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
