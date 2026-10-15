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
    ("literal_answers.py", "_literal_reply_defect"): (
        "GROUNDING", "a number in the reply of a said-back literal or a draw must be one the person said"),
    ("conversation_shape.py", "_shaped_presentation_text"): (
        "WORDING", "the person's message is the material of the prompt (a numbered list kept, anchor words); "
        "the shape was read by semantic.conversation"),
    ("conversation_contract.py", "_shaped_conversation_answer_violates_contract"): (
        "GROUNDING", "a maker or origin the person named is theirs to repeat (_INVENTED_ORIGIN on both texts); "
        "what was asked comes from semantic.conversation readers"),
    ("reply_claims.py", "visible_reply_claims_an_effect"): (
        "GROUNDING", "a claimed act that repeats the person's own words is not invented (asked_words)"),
    ("device_facts.py", "_screen_count_defect"): ("GROUNDING", "a number the person said may be repeated"),
    ("deterministic_finals.py", "_plain_words"): (
        "GROUNDING", "Estabilización F (_quotes_what_it_was_not_given): a quote over a result is checked literally "
        "against the payload and the person's own words, which may be quoted back"),
    ("agenda_facts.py", "_clocks_written_in_observed_titles.walk"): (
        "GROUNDING", "M134: clocks inside observed titles/names a verified operation returned, never the person's words",
    ),
    ("talk_memory_figures.py", "talk_memory_figures"): (
        "GROUNDING", "M95: a figure of a talk answer is the conversation's only when its words (the person's or BAXY's "
        "earlier answers) contain it, or the name it follows"),
    ("talk_memory_figures.py", "_without_memory_figures.carries"): (
        "GROUNDING", "ronda 22: the figures talk_memory_figures already found are looked for in the reply's own "
        "sentences and list items to drop them; the person's words are not read"),
    # Arranque honesto (r22): the model server's own output, kept for the startup failure's tail.
    ("llm_startup.py", "scrub_line"): (
        "OTHER", "a line the llama-server wrote, with its file paths masked (they carry the account name) and cut to "
        "its length; the person's words are not read here"),
    ("payload_fact_checks.py", "names_an_unseen_known_folder.named"): (
        "GROUNDING",
        "the reply's known-folder names (data _KNOWN_FOLDER_FORMS) compared with the observed facts of a known-folder "
        "operation: the place reported must be the one observed; the person's words are not read here",
    ),
    # M97 (reserve es315 «no cago…»).
    ("reply_language_checks.py", "visible_reply_says_a_vulgarity"): (
        "GROUNDING", "a vulgar word of the reply is allowed only when the person wrote it first"),
    ("failure_wording.py", "_failure_word_is_the_persons"): (
        "GROUNDING", "the «fallos» of the reply may be the person's own word said back, never BAXY's failure"),
    ("device_facts.py", "_ocr_unsupported_terms.stems"): (
        "GROUNDING", "a word of the screen report must be read on screen or said by the person"),
    ("search_report.py", "_search_report_unsourced_numbers"): ("GROUNDING", _GROUNDING_SEARCH),
    # M88 (DEV-D v3r D-p12-t2): a count said in words, grounded like one in digits.
    ("search_report.py", "_search_report_unsourced_counts"): ("GROUNDING", _GROUNDING_SEARCH),
    ("search_report.py", "_search_report_sentences"): ("GROUNDING", _GROUNDING_SEARCH),
    ("search_report.py", "_search_report_speaks_as_a_page"): ("GROUNDING", _GROUNDING_SEARCH),
    ("search_report.py", "_search_report_shows_the_search"): ("GROUNDING", _GROUNDING_SEARCH),
    ("search_report.py", "_search_report_offers_a_finder"): ("GROUNDING", _GROUNDING_SEARCH),
    # M168 (D77): a weekday or clock of a report of ESPN's calendar the person said themselves is theirs to repeat.
    ("search_report.py", "_match_report_unread"): ("GROUNDING", _GROUNDING_SEARCH),
    ("search_report.py", "_search_report_off_subject"): (
        "GROUNDING", "the proper names the person wrote are the subject the report must be about"),
    ("payload_fact_checks.py", "_headline_words"): (
        "GROUNDING", "M77: a question of the reply is folded to its words to tell whether it quotes an observed "
        "headline; nothing decides what was asked"),
    ("search_report.py", "_places_whole_address"): (
        "GROUNDING", "the tail of an address the person wrote themselves may be said back (M62)"),
    ("weather_facts.py", "_weather_fact_defect"): (
        "GROUNDING", "a number the person said is theirs to repeat, never a measurement; what the weather "
        "question asks is read by semantic.web"),
    ("visible_defect.py", "_unverified_present_fact"): (
        "GROUNDING", "a date or figure about now may only restate what the person said or what was read"),
    ("visible_defect.py", "compose_visible_defect"): (
        "GROUNDING", "identifiers and literals the person typed are allowed in the reply, and an echo of the "
        "request is rejected; every reading of what was asked is a semantic reader it calls"),
    ("unsupported_answers.py", "_unsupported_request_anchor_token"): (
        "WORDING", "picks which of the person's words a limit must quote (an anchor), not what they asked"),
    ("clarification_style.py", "_cut_request_tail"): ("WORDING", "the last words of a cut message, quoted back in the question"),
    ("clarification_style.py", "_bare_path_name"): ("WORDING", "the file name of a pasted path, quoted back in the question"),
    ("deterministic_finals.py", "_told_result_final"): (
        "WORDING",
        "A7 last resort: the day or later hour the person named picks which verified value the sentence tells",
    ),
    ("visible_defect.py", "_observed_identifier_tokens.walk"): (
        "GROUNDING",
        "A7 E4: identifiers inside observed values, so a fragment of an observed title is not internal code",
    ),
    ("visible_defect.py", "_observed_repeated_words.walk"): (
        "GROUNDING",
        "M172: words an observed value already repeats («Fru Fru»), so saying them is not a stutter",
    ),
    ("cu_reply_checks.py", "_folded_words"): (
        "GROUNDING",
        "cu-r16: a word of a mission final must be one of the facts, the person's own words or BAXY's vocabulary",
    ),
    ("cu_reply_checks.py", "_preterites"): (
        "GROUNDING",
        "cu-r17/r18: the first-person past forms of the verbs the person and the goal said, so a final telling that "
        "act («pegué», «envié») is grounded; decides no intention",
    ),
    ("visible_defect.py", "_said_misspelled"): (
        "GROUNDING",
        "A7 E1: a name in the reply checked against a word the person wrote with a typo",
    ),
    ("search_report.py", "_search_query_terms"): (
        "GROUNDING",
        "M51: the query's content words, the evidence a search result is about what was asked",
    ),
    ("llm_compose.py", "ComposeMixin._compose_partial_report"): (
        "GROUNDING",
        "M83: a name or figure a page carries is found data only when the person's request did not already say it",
    ),
    ("llm_clarify.py", "ClarifyMixin.clarify_unresolved_input"): (
        "WORDING", "the question BAXY writes must not echo the person's words (echo check); the kind of input "
        "was read by semantic.guards"),
    # ------------------------------------------------ other mind modules
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
    ("voice.py", "WakePhraseMatcher.strip"): ("INPUT", _WAKE),
    ("wake_cascade.py", "normalize_lexical_transcript"): ("INPUT", _WAKE),
    ("wake_verifier.py", "lexical_words"): ("INPUT", _WAKE),
    # ------------------------------------------------ computer use: the engine's step, after semantic.missions read
    ("cu_rules.py", "deterministic_step"): (
        "GROUNDING", "the goal is the sub-goal semantic.missions wrote; the article and the control kind said before "
        "a name only narrow which control of the view it names"),
    ("cu_goals.py", "_goal_target"): (
        "GROUNDING", "the goal is the sub-goal semantic.missions wrote; the article and the control kind said before "
        "a name only narrow which control of the view it names"),
    ("cu_goals.py", "_destination"): (
        "GROUNDING", "the place of a sub-goal semantic.missions wrote («ir a X»), its article dropped"),
    ("cu_goals.py", "reading_goal"): (
        "GROUNDING", "the head verb of the sub-goal semantic.missions wrote (or the question's look), matched against "
        "the floor data readGoal, so a reading never presses a switch on the way"),
    ("cu_by_name.py", "_unlisted_name_click"): (
        "GROUNDING", "the names of a sub-goal semantic.missions wrote, tried by label on the window; a name that "
        "removes or opens elsewhere is never clicked unseen"),
    ("cu_languages.py", "_translation_clickable"): (
        "GROUNDING", "the goal semantic.missions wrote, checked for asking an account act or another tab or window "
        "before a control found by the model's translation is clicked; the same guards the model's clicks pass"),
    ("cu_view.py", "_shown_as_words"): (
        "GROUNDING", "a name of the sub-goal's place (as said, from the table or translated) looked up as whole words "
        "in a control's name or the view's lines: a literal check against the screen, never a reading"),
    ("cu_lookup.py", "_view_resembles"): (
        "GROUNDING", "the names of the sub-goal's place (as said, from the table or translated) split into content "
        "words and looked up, literally, among the words of the view's controls' names (ronda 20 P1, v3-03): a check "
        "against the screen of whether a blind lookup may miss what the window shows, never a reading"),
    # Encargo S de estabilización: the place's own button and the acts in the person's name, against the view.
    ("cu_lookup.py", "_is_the_place"): (
        "GROUNDING", "the place of a sub-goal semantic.missions wrote, its article dropped, compared literally (or by the "
        "place table's other names) with a control's name: which control of the view is the place's own"),
    # Estabilización G2: a control or a written line that holds the place's name and adds words of its own.
    ("cu_view.py", "names_another_place"): (
        "GROUNDING", "the place of a sub-goal semantic.missions wrote looked up, literally and as whole words, in a "
        "control's name or a line of the window, whose other words (the window's, never the person's) tell whether it "
        "names another place («Pantalla de bloqueo»); decides no intention"),
    ("cu_unasked.py", "unasked_act"): (
        "GROUNDING", "the place of a sub-goal semantic.missions wrote compared literally with the name of the control "
        "to press (the control that IS the place only goes there); the act asked is read by semantic.account_acts"),
    ("cu_evidence.py", "_echoes_typing"): (
        "GROUNDING", "a cited evidence that repeats what BAXY typed in the sub-goal is its own echo, never arrival"),
    ("cu_acts.py", "typed_text"): (
        "INPUT", "the text to type keeps the person's words on one line (breaks and tabs become spaces): it is "
        "never read for an intention"),
    ("cu_unasked.py", "unasked_text"): (
        "GROUNDING", "a lone letter the model would type is accepted only when the request or the sub-goal says it as "
        "a word, literally (live v3-11); going to a place, a text only when one of its words is a word of the request, "
        "the sub-goal or its place's other names, literally (estabilización G2); decides no intention"),
    ("cu_evidence.py", "_cited_control_name"): (
        "OTHER", "the evidence is the model's citation of a control line as the step's prompt lists it («Kind «name» · "
        "states»), resolved against the view's controls; the person's words are not read here"),
    # Ronda 20 P4 (v3-08): a part new by identity after the command that creates what the goal names.
    ("cu_vocabulary.py", "_created_words"): (
        "GROUNDING", "the words of a written goal and of a command's name, cut and grouped by data "
        "«computerUse.evidence.creatingKin», compared with each other; the person's words are not read here"),
    ("cu_first_look.py", "_new_part_by_identity"): (
        "GROUNDING", "whether a goal semantic.missions wrote creates one thing (data «creatingGoal», "
        "«creatingQuantity») and the last click's command creates it («creatingCommand»), with the UIA ids of the "
        "view; the person's words are not read here"),
    # Revisión 2 de P4: a form's own button cited as the proof of a creation.
    ("cu_creation.py", "_form_button_cited"): (
        "GROUNDING", "whether a goal semantic.missions wrote creates something (data «creatingGoal») and the citation is "
        "a button the sub-goal brought (new on its first look or after its click) beside one that saves or confirms "
        "(data «commitControl»), naming none of the goal's words (data «creatingKin»); the person's words "
        "are not read here"),
    # Ronda 22 (pasada r18, t4-c06, t4-c13): mirror of EvidenceRefusal's «unrelated».
    ("cu_evidence.py", "_unrelated_evidence"): (
        "GROUNDING", "the stems of the sub-goal semantic.missions wrote (semantic.cu_buscar.proof_stems) compared with "
        "the pieces of the model's citation new on screen and the names of the controls a click chose, by data "
        "«computerUse.evidence.relevanceFillers», «computerUse.evidenceAliases», «creatingKin» and «noticeText» (only a "
        "notice that shares no stem is unrelated); the person's words are not read here"),
    ("cu_goals.py", "_goal_names_control"): (
        "GROUNDING", "the words of a control's name looked up, literally, among the words of the sub-goal "
        "semantic.missions wrote; decides no intention"),
    # Recibo del clic por estado (r15b v3-44): the rule's own presses (a written line, a name clicked by label alone)
    # pass the same help guard as the model's act.
    ("cu_unasked.py", "opens_help"): (
        "GROUNDING", "the words of a control's name or a line of the view matched, literally, against the offer to look "
        "something up in the help or on the web, and the sub-goal or the request only checked for help or web words "
        "the person said (_ASKS_HELP), never to decide an intention; the same guard the model's click passes"),
    # Ronda 17 menus-actos: the open/menu/double acts go through the guards of a click.
    ("cu_validate.py", "_checked_manner"): (
        "GROUNDING", "the model's open/menu/double act checked against the view's control (its kind, states and name) "
        "and against the sub-goal semantic.missions wrote, with the same guards as _checked_act (account, removal, "
        "scroll part); the person's words are not read here"),
    ("cu_validate.py", "_checked_act"): (
        "GROUNDING", "the model's act checked against the sub-goal semantic.missions wrote: its «ir a X» place, its "
        "«activar/seleccionar X» thing and whether it names a tab or window bound which control a click may press "
        "(the same guards as _translation_clickable); the request's new tab is semantic.cu_buscar.asks_a_new_tab"),
    ("cu_goals.py", "done_needs_an_act"): (
        "GROUNDING", "twin of ComputerUseSuccessCheck.Evidence.cs::DoneNeedsAnAct: whether a goal semantic.missions (or the decider) "
        "wrote is a place («ir a X», data «placeGoal»), a reading (data «computerUse.evidence.readGoal», or a goal "
        "with a question) or a goal of doing; the person's words are not read here"),
    ("cu_goals.py", "_search_goal"): (
        "GROUNDING", "twin of ComputerUseSuccessCheck.Evidence.cs::SearchGoal: whether a goal semantic.missions (or the decider) "
        "wrote is a search (data «computerUse.evidence.searchGoal»); the person's words are not read here"),
    ("cu_evidence.py", "acted_with_effect"): (
        "GROUNDING", "twin of ComputerUseSuccessCheck.Evidence.cs::ActedWithEffect: the verified steps of a sub-goal and their "
        "receipts; only whether the goal written is one of opening (data «computerUse.evidence.openGoal»); the "
        "person's words are not read here"),
    # Ronda 24 (pasada r23 v3-33): an option chosen is no product made.
    ("cu_evidence.py", "product_noun"): (
        "GROUNDING", "twin of ComputerUseSuccessCheck.Evidence.cs::ProductNoun: the noun of the product a goal semantic.missions (or "
        "the decider) wrote makes (data «computerUse.evidence.productGoal»), so a chosen option is not taken for it; "
        "the person's words are not read here"),
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
    # Computer use: the success check is a grammar the mind's reader (semantic/missions) writes; the App parses it.
    # Ronda 23 (pregunta-lee-lo-pertinente): the excerpt of the view puts first what shares a root with the question.
    ("ComputerUseSuccessCheck.Place.cs", "PlaceToggle"): (
        "GROUNDING", "the place of an atom of the success check semantic.missions wrote, its article dropped, compared "
        "literally with a button's name after a verb of the data computerUse.placeToggle; twin of the mind's "
        "cu_lookup.own_place_button"),
    ("ComputerUseMission.Final.cs", "BearsQuestionRoot"): (
        "GROUNDING", "orders the view's lines and controls for the model by a root they share with the question of the "
        "goal semantic.missions wrote («; y responder: …»); it decides no meaning, only which of the window's texts "
        "are shown first"),
    ("ComputerUseSuccessCheck.cs", "CountAtom"): (
        "GROUNDING", "parses the «count:<kind> <op> N» atom of the success check that semantic.missions wrote and "
        "counts the view's controls; the person's words are not read here"),
    # Revisión 1 de la ronda 24b (B4): the witness of a «count:» atom that closed a sub-goal is the count measured.
    ("ComputerUseSuccessCheck.cs", "CountSource"): (
        "GROUNDING", "parses the same «count:<kind> <op> N» atom (CountAtom's pattern) to quote, as the witness of the "
        "term that closed a sub-goal, how many controls of that kind the view counted; the person's words are not read "
        "here"),
    # Live y7: the «result:<expression>» atom semantic.missions writes for a calculation; the App reads the numbers
    # the screen shows (a display, a value) to compare them with the expression's value, never the person's words.
    ("ComputerUseSuccessCheck.Calculation.cs", "ShownNumbers"): (
        "GROUNDING", "reads the numbers on the view (display text, control values) for the «result:» atom of the "
        "success check that semantic.missions wrote; the person's words are not read here"),
    # Ronda 23, revisión 3: «10.000-1» of the «result:» atom read both with its mark decimal and as thousands grouped.
    ("ComputerUseSuccessCheck.Calculation.cs", "CalculationValues"): (
        "GROUNDING", "evaluates the expression of the «result:» atom of the success check that semantic.missions wrote, "
        "a number whose marks each group three digits read both as decimal and as thousands; it decides no meaning and "
        "the person's words are not read here"),
    # Ronda 20b, revisión 1 (bloqueante 4): «1500» held «value:horizontal=500» by containment.
    ("ComputerUseSuccessCheck.cs", "ValueHolds"): (
        "GROUNDING", "whether a field's value on the view holds the value of the «value:» atom semantic.missions "
        "wrote: a number within digit bounds, a text contained; the person's words are not read here"),
    # Revisión 2 de la ronda 22: which lines of the screen excerpt are a control's label.
    ("ComputerUseMission.Final.cs", "LabelWords"): (
        "GROUNDING", "the words of an OCR line and of a control's UIA name, compared to mark the excerpt's lines that "
        "are a control's label (ControlLines); the person's words are not read here"),
    # Ronda 21 (pasada r18 v3-26), review 2: the opening the engine put first restarts its sub-goal's clock.
    ("ComputerUseMission.cs", "RestartsSubgoalClock"): (
        "GROUNDING", "whether the goal semantic.missions (or the decider) wrote for a sub-goal is one of opening (data "
        "«computerUse.evidence.openGoal»), so the engine's opening put first in it is not its work and its clock "
        "starts after it; the person's words are not read here"),
    ("ComputerUseSuccessCheck.Evidence.cs", "SearchGoal"): (
        "GROUNDING", "whether a goal semantic.missions (or the decider) wrote is a search (data "
        "«computerUse.evidence.searchGoal»), so typing its query is its act; the person's words are not read here"),
    ("ComputerUseSuccessCheck.Evidence.cs", "ProofStems"): (
        "MIRROR", "twin of semantic.cu_buscar.proof_stems: the words of a written goal or of a window's text, cut and "
        "grouped by data; decides no intention"),
    # The mission's window by its title (ronda 12): the title is the window's, never the person's words.
    # Ronda 24 (pasada r23 t-form-2): a command that may erase or replace is let on the tied document only when the
    # request carries the verb of that very command's class (data «computerUse.contentErasing.requested»); revisión 3
    # de r24 (B2): only where an order stands (data «commandPosition», «commandPlace»: InCommandPosition).
    ("ComputerUseMissionWindow.cs", "RequestedOnTiedDocument"): (
        "GROUNDING", "the request's own words are the literal evidence that a pressed command of an erasing class was "
        "asked for (the class's verb in them); what the mission does is semantic.missions'; this only lets the guard "
        "pass an act already chosen"),
    ("ComputerUseMissionWindow.cs", "InCommandPosition"): (
        "GROUNDING", "the same literal evidence narrowed: the class's word counts only where an order stands (the "
        "request's start, a link, a courtesy or a modal, or the place named by the tied window's own application or "
        "title), never an adjective or noun of the same spelling; it only lets the guard pass an act already chosen"),
    ("ComputerUseMissionWindow.cs", "DocumentPart"): (
        "OTHER", "a window title's first segment (the document or the dialog, before « - » and the application's "
        "name); the person's words are not read here"),
    # cu-r16: the floor of a mission tells its parts from the goals semantic.missions wrote (data «computerUse.parts»).
    # cu-v3-elevacion (review, finding 2): the rights an app.open runs with are the App's to decide, never the model's.
    ("OperationFloor.cs", "AdministratorAsked"): (
        "MIRROR", "whether the person's request asks for administrator rights (data «administratorAsked.cues», whole "
        "words): the App decides the rights of an app.open itself and never takes an extracted forControl, so a raised "
        "window opens only when the person's own words ask for it (invariant 1: the kernel authorizes)"),
    # Ronda 24 (v3-59): a place's done whose citation shares no word with the place nor with the window's title.
    ("ComputerUseSuccessCheck.Evidence.cs", "CitationOffThePlace"): (
        "GROUNDING", "the place of the goal semantic.missions (or the decider) wrote («ir a X», OperationFloor.PlaceAsked) "
        "and the names its check and translation give it, compared word by word with the model's citation and the "
        "window's own process and title; it decides no meaning and the person's words are not read here"),
    # Revisión 1 de r24 (B2, v3-08): the citation is the whole text a verified typing put into a field the goal names.
    ("ComputerUseSuccessCheck.Form.cs", "SlotWritten"): (
        "GROUNDING", "the words of the goal written for the sub-goal, matched against the names of the view's fields "
        "and the text a verified typing step put there (twin of cu_evidence._slot_written); an observation of the "
        "screen and the receipts, the person's words are not read here"),
    # Review of cierre-de-subobjetivos (finding 3): only a goal of bringing something up is closed by what appeared.
    ("ComputerUseSuccessCheck.Evidence.cs", "BringsUpGoal"): (
        "GROUNDING", "whether a free goal semantic.missions (or the decider) wrote is one of opening or of going to a "
        "place (data «computerUse.evidence.openGoal», «placeGoal»), so the control its act brought up may close "
        "it; the person's words are not read here"),
    ("OperationFloor.cs", "Unanswered"): (
        "GROUNDING", "the question part of a goal semantic.missions wrote, said back in the honest limit of a mission "
        "that reached its place without reading the answer; the person's words are not read here"),
    ("OperationFloor.cs", "Filled"): (
        "WORDING", "revisión F: the placeholders of the floor's own data wording ({value}) filled from the observation; "
        "the person's words are not read here"),
    ("OperationFloor.cs", "PartMatch"): (
        "GROUNDING", "splits a goal that semantic.missions wrote («ir a X», «escribir X») into its object, to say it "
        "back from the facts; the person's words are not read here"),
    ("OperationFloor.cs", "PartObject"): (
        "GROUNDING", "trims the quotes and spaces of a goal's object or a typed step's text to compare it literally"),
    ("OperationFloor.cs", "CalculationShown"): (
        "GROUNDING", "the expression of a «calcular E» goal is evaluated and its value looked for, literally, in what "
        "the window shows; the person's words are not read here"),
    # M116: a failed step's facts carry its grounded arguments; this only shapes an argument value for display.
    ("AttemptedArguments.cs", "Said"): (
        "GROUNDING", "a grounded argument value shown as the person would say it: no ids, URL host/path only, a path's "
        "last name only; nothing of the person's words is read here"),
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
    paths = sorted(APP.glob("*.cs"))
    # A Regex field is called from every file of its partial class, and from another class by its qualified name.
    fields: set[str] = set()
    for path in paths:
        text = path.read_text(encoding="utf-8")
        fields |= set(re.findall(r"\bRegex[ \t]+(\w+)[ \t]*=", text))
        fields |= set(re.findall(r"partial[ \t]+Regex[ \t]+(\w+)\(\)", text))
    for path in paths:
        text = path.read_text(encoding="utf-8")
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
