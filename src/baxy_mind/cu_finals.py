"""The finals a mission is told with from its facts alone (operation_floor.v1.json «computerUse»): its parts,
a place reached, a calculation the window shows, a question's answer, a limit, and what was left unread.
"""

from __future__ import annotations

import re
from fractions import Fraction

from . import operation_floor
from .semantic.claims import weak_proof
from .semantic.colours import colour_shades
from .semantic import app_places, mission_answer
from . import cu_chat_lines as chat_lines
from .semantic.chats import has_written_entries, last_written, last_written_by
from .semantic.messaging import proven_sent
from .semantic.missions import QUESTION_MARK, _restore, fold, names_a_blank_document
from .semantic.normalize import fold_in_place
from .semantic.limits import DEVICE_STOP, LIMIT_STOP, PLACE_SEARCH_STOP, limits_data
from .cu_vocabulary import _BIDI_MARKS, _PARTS, _PLACE_GOAL, _evidence_rules, _floor_name
from .cu_view import _bare, _shown_as_words
from .cu_goals import _calm_caps, _place_of, _spelled
from .cu_history import _may_have_acted, only_opened
from .cu_text_place import _names_a_part
from .cu_documents import _document_part, _title_names_a_document
from .cu_projection import _STOP_CAUSES, _chosen_shade, _strong_arrival, project_seen


_PART_GOALS: dict[str, re.Pattern[str]] = {
    kind: re.compile(_PARTS[kind], re.IGNORECASE)
    for kind in ("select", "create", "click", "type", "search", "calculate", "key", "mode", "send")
}
_ONE_GENDERED_WORD = re.compile(r"^[a-z]+[oa]$")
_PART_QUOTES = "«»\"“”'"
# Live 2026-10-07: «calcular 1.500 + 500» read as 1,5 + 500. A «.» followed by exactly three digits groups thousands
# (the Chilean writing); a comma after them is the decimal one.
_CALC_TOKEN = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?(?![\d.])|\d+(?:[.,]\d+)?|\S")
_GROUPED_NUMBER = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?")
# What a window writes of the expression itself («La expresión es 144 ÷ 12=») never proves its value.
_WRITTEN_EXPRESSION = re.compile(r"\d[\d.,]*(?:\s*[-+×÷*/xX]\s*\(?\s*\d[\d.,]*\)?)+\s*=?")
_LONGEST_DECIMALS = 10


def _part_object(value: object) -> str:
    return " ".join(str(value or "").split()).strip(_PART_QUOTES + " .;:") if isinstance(value, str) else ""


def _mode_chosen(asked: str, done: list[dict], app: str) -> str:
    """Live 2026-10-07 (cu-r20): the mode a goal «activar modo X» reached by choosing it, as the window writes it
    without the application's name («Científica Calculadora» → «Científica» for «activar modo cientifico», either
    gender); "" when no click chose it or a switch set it (data «computerUse.parts.mode»). Twin of the App's
    OperationFloor.ModeChosen."""

    wanted = fold(asked)
    if not wanted:
        return ""
    names = {wanted}
    if _ONE_GENDERED_WORD.match(wanted):
        names.add(wanted[:-1] + ("a" if wanted[-1] == "o" else "o"))
    app_words = set(fold(app).split())
    chosen = ""
    for step in done:
        name = _floor_name(step.get("name"))
        if step.get("operation") != "input.visible.click" or not name:
            continue
        mode = " ".join(word for word in name.split() if fold(word) not in app_words)
        if not mode or fold(mode) not in names:
            continue
        if step.get("kind") in _PARTS["switchKinds"]:
            return ""
        chosen = _calm_caps(mode)
    return chosen


def _calculated(tokens: list[str]) -> Fraction | None:
    """The value of an arithmetic expression (numbers, + - × ÷ and parentheses), or None when it is no such thing."""

    position = 0

    def peek() -> str | None:
        return tokens[position] if position < len(tokens) else None

    def factor() -> Fraction | None:
        nonlocal position
        token = peek()
        if token == "-":
            position += 1
            inner = factor()
            return None if inner is None else -inner
        if token == "(":
            position += 1
            inner = expression()
            if inner is None or peek() != ")":
                return None
            position += 1
            return inner
        if token is not None and token[0].isdigit():
            position += 1
            plain = token.replace(".", "") if _GROUPED_NUMBER.fullmatch(token) else token
            return Fraction(plain.replace(",", "."))
        return None

    def term() -> Fraction | None:
        nonlocal position
        value = factor()
        while value is not None and peek() in {"×", "÷"}:
            operator = peek()
            position += 1
            right = factor()
            if right is None or (operator == "÷" and right == 0):
                return None
            value = value * right if operator == "×" else value / right
        return value

    def expression() -> Fraction | None:
        nonlocal position
        value = term()
        while value is not None and peek() in {"+", "-"}:
            operator = peek()
            position += 1
            right = term()
            if right is None:
                return None
            value = value + right if operator == "+" else value - right
        return value

    value = expression()
    return value if position == len(tokens) else None


def _value_spellings(value: Fraction) -> list[str]:
    """How a window may write ``value``: plain, with its thousands grouped, with a decimal point or comma; [] when it
    has no finite decimal writing."""

    denominator, twos, fives = value.denominator, 0, 0
    while denominator % 2 == 0:
        denominator, twos = denominator // 2, twos + 1
    while denominator % 5 == 0:
        denominator, fives = denominator // 5, fives + 1
    decimals = max(twos, fives)
    if denominator != 1 or decimals > _LONGEST_DECIMALS:
        return []
    sign = "-" if value < 0 else ""
    scaled = abs(value.numerator) * (10 ** decimals) // value.denominator
    whole, fraction = divmod(scaled, 10 ** decimals) if decimals else (scaled, 0)
    digits = str(whole)
    groups = [digits[max(0, end - 3):end] for end in range(len(digits), 0, -3)][::-1]
    spellings: list[str] = []
    for separator in ("", ".", ",", " ", "\u00a0"):
        if separator and len(groups) < 2:
            continue
        integer = separator.join(groups)
        if not decimals:
            spellings.append(sign + integer)
            continue
        tail = str(fraction).rjust(decimals, "0")
        spellings.extend(
            sign + integer + point + tail for point in (".", ",") if point != separator
        )
    return spellings


def _calculation_shown(expression: str, texts: list[str]) -> tuple[str, str] | None:
    """(expression as said, value as the window writes it) for «calcular E» when the window shows E's value."""

    operators: dict[str, str] = _PARTS["operators"]
    tokens = [operators.get(token, token) for token in _CALC_TOKEN.findall(expression)]
    if not tokens or any(not (token[0].isdigit() or token in {"+", "-", "×", "÷", "(", ")"}) for token in tokens):
        return None
    value = _calculated(tokens)
    if value is None:
        return None
    shown = [_WRITTEN_EXPRESSION.sub(" ", " ".join(_BIDI_MARKS.sub("", text).split())) for text in texts]
    for spelling in _value_spellings(value):
        pattern = re.compile(r"(?<![\d.,])" + re.escape(spelling) + r"(?![\d]|[.,]\d)")
        if any(pattern.search(text) for text in shown):
            said = " ".join(tokens).replace("( ", "(").replace(" )", ")")
            return said, spelling
    return None


def _screen_texts(observed: dict) -> list[str]:
    screen = observed.get("screen") if isinstance(observed.get("screen"), dict) else {}
    texts: list[str] = []
    for key in ("numbers", "lines"):
        texts.extend(item for item in screen.get(key) or () if isinstance(item, str))
    for item in screen.get("values") or ():
        if isinstance(item, dict):
            texts.extend(value for value in (item.get("name"), item.get("value")) if isinstance(value, str))
    texts.extend(value for value in (screen.get("title"),) if isinstance(value, str))
    return texts


def _join(items: list[str], english: bool) -> str:
    said = operation_floor.floor_data()["templates"]["en" if english else "es"]
    return items[0] if len(items) == 1 else said["list"].join(items[:-1]) + said["and"] + items[-1]


def _parts_final(observed: dict, seen: dict, english: bool, names: list[str], app: str) -> tuple[str, bool]:
    """(the sentence of a reached mission told part by part, whether every name in it is the window's own spelling or
    the text typed); ("", False) when one of its parts cannot be told from the facts."""

    goal = seen.get("goal")
    subgoals = [item for item in seen.get("subgoals") or () if isinstance(item, dict)]
    parts = [(item.get("goal"), item.get("application")) for item in subgoals] or [
        (part, seen.get("application")) for part in str(goal or "").split(_PARTS["chain"])
    ]
    # What each part's own window showed when it was reached (only a part before the last carries it).
    part_numbers = [[value for value in item.get("numbers") or () if isinstance(value, str)] for item in subgoals]
    language = "en" if english else "es"
    said, quote = _PARTS[language], operation_floor.floor_data()["templates"][language]["quote"]
    raw_steps = observed.get("steps") if isinstance(observed.get("steps"), list) else []
    done = [step for step in raw_steps if isinstance(step, dict) and step.get("ok") is True]
    typed = [
        fold(_part_object(step.get("text"))) for step in done
        if step.get("operation") == "input.text.type" and isinstance(step.get("text"), str)
    ]
    texts = _screen_texts(observed)
    raw_parts = [
        item for item in (observed.get("subgoals") if isinstance(observed.get("subgoals"), list) else [])[:8]
        if isinstance(item, dict)
    ]
    clauses: list[tuple[str, str, str, bool]] = []  # (kind, said, application, the window's own spelling)
    # Review 1 of r24b (B1): the place clauses a focused field proved (data «computerUse.searchOpened.atoms»): the
    # search opened, never a place reached. A part's proof is its sub-goal's; a goal split by the chain, the mission's.
    opened: set[int] = set()
    already_at: set[int] = set()  # the clauses of places the window was already in (ronda 24b, x10)
    keyed: set[str] = set()
    written: dict[int, str] = {}  # the text each type clause wrote (encargo E: the one a send part sent)
    # Encargo E: a chat writes its people and channels with a sigil («@Ron92»); the place is that name without it.
    sigils = _PARTS["nameSigils"]
    unsigiled = [name[1:] for name in names if name[:1] in sigils and name[1:].strip()]

    def by_address(position: int) -> list[dict]:
        # Estabilización, encargo C (banco f2c x10, lug-2): the openings of the part that opened its place by the
        # address its data declare; the place is then told with the person's word for it, and a search with its query.
        alone = not subgoals and len(parts) == 1
        return [step for step in done if step.get("operation") == "app.open" and step.get("placeOpened") is True
                and (alone or step.get("subgoal") == position)]

    def proved(position: int, picked: bool = False) -> tuple[str | None, bool]:
        # Ronda 24b (x10), r30: (the name the term that held read in the part's window, as the window writes it: the
        # App's «arrivedAs», the mark «BIBLIOTECA», «Cronómetro» for «ir a stopwatch», the verified click «Borrador» for
        # «seleccionar eraser»; whether the part was found already there). Only of a part an act got there, found
        # already there or reached on a strong term; a part reached with no act on a weak term keeps the window's
        # names only. A mission of one goal carries it itself (its arrivedAs, its steps, its term).
        # Revisión de r30: never from a term that arrived by resemblance («ir a language» closed on
        # «control:hora e idioma:current&similar:…»: where the window is, not that it is what was asked; the model
        # words it under the book of acts), and a pick only after an act of the part («Lápiz» found chosen with no act
        # was not picked by BAXY: «elegí» is the only sentence a pick has).
        alone = not subgoals and len(parts) == 1
        item = subgoals[position] if position < len(subgoals) else {}
        source = observed if alone else item
        raw_item = raw_parts[position] if position < len(raw_parts) else source
        arrived = source.get("arrivedAs").strip() if isinstance(source.get("arrivedAs"), str) else ""
        acted = any(map(_may_have_acted, raw_steps)) if alone else item.get("acted") is True
        already = item.get("alreadyThere") is True and position < len(parts) - 1
        # Revisión 2 (B3: Steam launched by the mission on «BIBLIOTECA», «ir a biblioteca» held on the mark, then
        # «Tienda»: the final said only «estoy en «Tienda»»): a part reached on a strong term is verified even with
        # no act and never «already» (the launch left it there); it is told as passed through, never left out.
        strong = (alone or item.get("reached") is True) and _strong_arrival(raw_item.get("satisfiedBy"))
        told = (acted if picked else acted or already or strong) and not _resembled(raw_item.get("satisfiedBy"))
        return (_calm_caps(arrived) if arrived and told else None), already

    for position, (part, part_app) in enumerate(parts):
        part = part.strip() if isinstance(part, str) else ""
        where = _floor_name(part_app) or app
        if not part or QUESTION_MARK in part:
            return "", False
        if _PART_GOALS["key"].match(part):
            # A key is never told (the instruction's «never the keys»); its application is told by another part.
            keyed.add(where)
            continue
        found = _PART_GOALS["mode"].match(part)
        if found is not None:
            mode = _mode_chosen(_floor_name(_part_object(found.group(1))), done, where)
            if not mode:
                return "", False
            clauses.append(("place", quote.format(value=mode), where, True))
            continue
        place = _PLACE_GOAL.match(part)
        if place is not None:
            asked = _floor_name(_part_object(place.group(1)))
            if not asked:
                return "", False
            own, already = proved(position)
            spelled = _spelled(asked, names) or _spelled(asked, unsigiled) or own
            if raw_parts:
                proof = raw_parts[position].get("satisfiedBy") if position < len(raw_parts) else None
            else:
                proof = observed.get("satisfiedBy") if position == len(parts) - 1 else None
            if _search_opened_proof(proof):
                opened.add(len(clauses))
            if already and spelled is not None:
                already_at.add(len(clauses))
            # Banco c2 (y10: «Done, I went through «store» and I'm now in «Biblioteca»»): a place opened by its address
            # is told as the person said it, in their language, never as the window spells it.
            addressed = bool(by_address(position))
            clauses.append(("place", quote.format(value=asked if addressed else spelled or asked), where,
                            spelled is not None or addressed))
            continue
        found = _PART_GOALS["create"].match(part)
        if found is not None:
            # Revisión 2 de r24b (B2, n6): a blank item created is told by what the mission made (data
            # «parts.createSource»): the document the window shows at the end, made by the opening that saw it made or
            # by the verified click on the offer. Only as the last part (no earlier window is kept), never when nothing
            # of the mission made it (the blank document already there is no creation).
            # Revisión 3 (B1): only the whole blank document (data «parts.createScopeSource») and only a new one the
            # mission made; the offer clicked with an unnamed document in front and no proof of a new one is told as
            # chosen, as a «seleccionar» part is; anything else (the person's «Proyectos» or «Informe» in front, a
            # click judged by the model alone) is no parts final.
            asked = _floor_name(_part_object(found.group(1)))
            if position != len(parts) - 1 or not names_a_blank_document(asked):
                return "", False
            created = _created_document(done, observed)
            if created:
                clauses.append(("create", said["create"].format(items=quote.format(value=created)), where, True))
                continue
            if not _offer_chosen(asked, done, observed):
                return "", False
            spelled = _spelled(asked, names)
            clauses.append(("select", quote.format(value=spelled or asked), where, spelled is not None))
            continue
        found = _PART_GOALS["select"].match(part)
        if found is not None:
            asked = _floor_name(_part_object(found.group(1)))
            if not asked:
                return "", False
            shade = _chosen_shade(part, done)
            if shade is not None and fold(shade["chosen"]) != fold(asked):
                colour = next(iter(colour_shades(shade["asked"], language)), str(shade["asked"]))
                item = said["shadeItem"].format(chosen=shade["chosen"], asked=colour.casefold())
                clauses.append(("select", item, where, True))
                continue
            spelled = _spelled(asked, names) or proved(position, picked=True)[0]
            clauses.append(("select", quote.format(value=spelled or asked), where, spelled is not None))
            continue
        found = _PART_GOALS["click"].match(part)
        if found is not None:
            # v3-43 r11: a click part is told by its verified click on the control it names, never as «lo hice en X».
            asked = _floor_name(_part_object(found.group(1)))
            clicked = next((
                name for step in done
                if step.get("operation") == "input.visible.click"
                and fold(name := _floor_name(step.get("name"))) == fold(asked)
            ), "") if asked else ""
            if not clicked:
                return "", False
            screen = seen.get("screen") if isinstance(seen.get("screen"), dict) else {}
            title = _floor_name(screen.get("title"))
            if title and fold(title) == fold(asked):
                clauses.append(("place", quote.format(value=title), where, True))
            else:
                clauses.append(("click", said["click"].format(items=quote.format(value=clicked)), where, True))
            continue
        found = _PART_GOALS["type"].match(part)
        if found is not None:
            text = _part_object(found.group(1))
            if not text or fold(text) not in typed or not where:
                return "", False
            written[len(clauses)] = text
            clauses.append(("type", quote.format(value=text), where, True))
            continue
        if _PART_GOALS["send"].match(part) is not None:
            # Encargo E (banco i1 c6): the send told with what it sent, never «escribí» alone, only when the part held
            # on the text the App saw sent and that text is the one the part before it typed, in the same application;
            # the place reached right before that in it is who it went to.
            if raw_parts:
                proof = raw_parts[position].get("satisfiedBy") if position < len(raw_parts) else None
            else:
                proof = observed.get("satisfiedBy") if position == len(parts) - 1 else None
            last = len(clauses) - 1
            if (
                last < 0 or clauses[last][0] != "type" or clauses[last][2] != where
                or not proven_sent(proof) or proven_sent(proof) != fold(written.get(last, ""))
            ):
                return "", False
            texts = clauses.pop()[1]
            to = clauses.pop() if clauses and clauses[-1][0] == "place" and clauses[-1][2] == where else None
            opened.discard(len(clauses))
            already_at.discard(len(clauses))
            sent = (said["sendTo"].format(texts=texts, place=to[1], app=quote.format(value=where)) if to is not None
                    else said["send"].format(texts=texts, app=quote.format(value=where)))
            clauses.append(("send", sent, where, to is None or to[3]))
            continue
        found = _PART_GOALS["search"].match(part)
        if found is not None:
            query = _part_object(found.group(1))
            searched = [_floor_name(step.get("placeValue")) for step in by_address(position)
                        if fold(query) in fold(step.get("placeValue"))]
            if not query or not (searched or any(fold(query) in text for text in typed)) or not where:
                return "", False
            # The query opened by the address is the person's whole one («Los Bunkers»), the goal's may have lost its
            # article.
            query = next((value for value in searched if value), query)
            search = said["search"].format(query=quote.format(value=query), app=quote.format(value=where))
            clauses.append(("search", search, where, True))
            continue
        found = _PART_GOALS["calculate"].match(part)
        # Only the calculating window's own display proves the value: a chain that ends in another application shows
        # that one's numbers («Línea 1, Columna 13» of the Bloc de notas).
        window = observed.get("window") if isinstance(observed.get("window"), dict) else {}
        title = window.get("title") if isinstance(window.get("title"), str) else ""
        ends_here = bool(where) and (fold(where) == fold(app) or fold(where) in fold(title))
        own = part_numbers[position] if position < len(part_numbers) else []
        shown = None
        if found is not None and own:
            # The part's own window when it was reached: the calculating window's display, wherever the chain ended.
            shown = _calculation_shown(found.group(1), own)
        elif found is not None and ends_here:
            shown = _calculation_shown(found.group(1), texts)
        if shown is None:
            return "", False
        if len(parts) == 1:
            return said["calculateAlone"].format(expression=shown[0], value=shown[1]) + ".", True
        clauses.append(("calculate", said["calculate"].format(expression=shown[0], value=shown[1]), where, True))
    if not clauses:
        return "", False
    if len(clauses) == 1 and clauses[0][0] == "place":
        # r30: the sentence of a search a focused field proved opened names its field, never the place asked.
        return _place_said(observed, english).format(place=clauses[0][1]) + ".", clauses[0][3] or 0 in opened
    told: list[str] = []
    # Keys pressed in an application no other part is told in (a paste in another window) are the model's to word.
    spelled_all = keyed <= {clause[2] for clause in clauses}
    index = 0
    while index < len(clauses):
        kind, text, where, spelled = clauses[index]
        run = [(text, spelled)]
        run_at = [index]
        while (
            index + 1 < len(clauses) and kind in {"place", "select", "type"}
            and clauses[index + 1][0] == kind and clauses[index + 1][2] == where
        ):
            index += 1
            run.append((clauses[index][1], clauses[index][3]))
            run_at.append(index)
        if kind == "place":
            # Live 2026-10-07: «ir a cotele» in Discord then «ir a tienda» in Steam came out «estoy en «TIENDA»»; a
            # mission across applications tells each place with its application.
            crossed = len({fold(clause[2]) for clause in clauses}) > 1
            # A search a focused field proved opened is no place passed through (review 1 of r24b, B1).
            first = index - len(run) + 1
            places = [(name, ok) for offset, (name, ok) in enumerate(run) if first + offset not in opened]
            if index == len(clauses) - 1:
                # Only the places the window spelled are told as passed through; the last is where the mission is.
                # A search a focused field proved opened is none of them (review 1 of r24b, B1). Ronda 24b (x10): a
                # place the window was already in, with no act, is told as such, never left out.
                before = [(pair, at) for pair, at in zip(run, run_at) if at != index and at not in opened]
                found_there = [name for (name, ok), at in before if ok and at in already_at]
                passed = [name for (name, ok), at in before if ok and at not in already_at]
                if found_there:
                    told.append(said["alreadyPlaces"].format(places=_join(found_there, english)))
                if passed:
                    told.append(said["places"].format(places=_join(passed, english)))
                if index in opened:
                    # The last part is where the cursor is: the search opened and its field, never «ya estoy en».
                    told.append(_search_opened_clause(observed, english))
                else:
                    last = said["lastPlaceIn"] if crossed and where else said["lastPlace"]
                    if found_there and not passed:
                        last = said["lastPlaceInNow"] if crossed and where else said["lastPlaceNow"]
                    told.append(last.format(place=run[-1][0], app=quote.format(value=where)))
                    spelled_all = spelled_all and run[-1][1]
            elif where and fold(where) != fold(clauses[index + 1][2]) and places:
                # A place in an application the mission then left is told with it.
                found_there = all(at in already_at for at in run_at if at not in opened)
                told.append(said["alreadyPlacesIn" if found_there else "placesIn"].format(
                    places=_join([name for name, _ in places], english), app=quote.format(value=where)))
                spelled_all = spelled_all and all(ok for _, ok in places)
            # A place passed on the way to another part of the same application is not told.
            index += 1
            continue
        spelled_all = spelled_all and all(ok for _, ok in run)
        if kind == "select":
            told.append(said["select"].format(items=_join([name for name, _ in run], english)))
        elif kind == "type":
            told.append(said["type"].format(texts=_join([name for name, _ in run], english), app=quote.format(value=where)))
        else:
            told.append(text)
        index += 1
    if len(told) == 1 and clauses[-1][0] == "place" and told[0] == said["lastPlace"].format(place=clauses[-1][1]):
        # The places passed were not the window's spelling: only where the mission is is told.
        return _floor_said(english)["place"].format(place=clauses[-1][1]) + ".", spelled_all
    return said["clauses"].format(clauses=_join(told, english)) + ".", spelled_all


def _created_document(done: list[dict], observed: dict) -> str:
    """Revisión 2 de r24b (B2, n6), twin of the App's OperationFloor.MadeDocument: the document a creating part made,
    as its window's title writes it («Documento1» of «Documento1 - Word»). Revisión 3 (B1: a verified click whose name
    matched the part, on «Proyectos - Explorador de archivos» or «Informe - Word», was told «creé «Proyectos»»): only
    a new document proves it, never a click's name. The title names a document with no name yet (evidence
    «untitledDocument», «defaultDocument»), and a step of the mission made exactly that one: the opening that made the
    new document and saw it made (``newDocument``), or the click whose receipt recorded the document it created
    (``createdDocument``, the App's ComputerUseMissionWindow.NoteCreatedDocument). "" otherwise."""

    written = _unnamed_document_in_front(observed)
    if not written:
        return ""
    made = any(
        (step.get("operation") == "app.open" and step.get("newDocument") is True)
        or (
            step.get("operation") == "input.visible.click"
            and _document_part(_floor_name(step.get("createdDocument")))[1] == _document_part(written)[1]
        )
        for step in done
    )
    return written if made else ""


def _offer_chosen(asked: str, done: list[dict], observed: dict) -> bool:
    """Revisión 3 de r24b (B1), twin of the App's OperationFloor.OfferChosen: the offer the part names was clicked
    and verified, and the window now shows a document with no name yet: the offer was chosen, nothing proves the
    document new (another unnamed one may have been there), so it is never told as created."""

    return bool(_unnamed_document_in_front(observed)) and any(
        step.get("operation") == "input.visible.click" and fold(_floor_name(step.get("name"))) == fold(asked)
        for step in done
    )


def _unnamed_document_in_front(observed: dict) -> str:
    """The document part of the final window's title as written («Documento1»), when it is a name no document is saved
    under (evidence «untitledDocument», «defaultDocument»); "" otherwise."""

    window = observed.get("window") if isinstance(observed.get("window"), dict) else {}
    title = window.get("title") if isinstance(window.get("title"), str) else ""
    if not _title_names_a_document(title):
        return ""
    written, document = _document_part(title)
    rules = _evidence_rules()
    if not document or not (re.match(rules["untitledDocument"], document) or re.match(rules["defaultDocument"], document)):
        return ""
    return _floor_name(written.lstrip("*").strip())


def _floor_said(english: bool) -> dict:
    return operation_floor.floor_data()["computerUse"]["en" if english else "es"]


def _place_said(observed: dict, english: bool) -> str:
    """The sentence of a place reached: «Ya estás en {place}» when the mission did nothing on the way (its check held on
    the first look; opening the application is no act there: v3 punto 5, Steam already on its library), else the
    place reached. A click that pressed but whose post-read did not hold is an act (review 2026-10-07: BAXY navigated
    there, the person was not «already» in it). Review r10a finding 1: «already» only when the check that held proves
    it by itself and as planned, in a window that was already open (``_proved_on_first_look``); otherwise the hedge.
    Twin of the App's OperationFloor.PlaceSaid."""

    data = operation_floor.floor_data()["computerUse"]
    language = "en" if english else "es"
    opened = _search_opened_said(observed, english)
    if opened:
        return opened
    steps = observed.get("steps") if isinstance(observed.get("steps"), list) else []
    if any(_may_have_acted(step) for step in steps):
        return _floor_said(english)["place"]
    launched = any(
        isinstance(step, dict) and step.get("operation") == "app.open" and step.get("alreadyRunning") is not True
        for step in steps
    )
    if _proved_on_first_look(observed):
        return _floor_said(english)["place"] if launched else data["placeAlready"][language]
    return data["placeSeems"][language if launched else language + "Already"]


def _search_opened_proof(term: object) -> bool:
    """Whether a check's term was proved by an atom of ``computerUse.searchOpened.atoms`` (a focused field). Twin of the
    App's OperationFloor.SearchOpenedProof."""

    atoms = operation_floor.floor_data()["computerUse"]["searchOpened"]["atoms"]
    return isinstance(term, str) and any(atom.split(":", 1)[0].strip().casefold() in atoms for atom in term.split("&"))


def _search_opened_clause(observed: dict, english: bool) -> str:
    """Review 1 of r24b (B1): the clause of a chain's last part a focused field proved: the search opened and the field
    the cursor is in (observed focusedField), told among the other parts. Twin of OperationFloor.SearchOpenedClause."""

    data = operation_floor.floor_data()["computerUse"]["searchOpened"]
    language = "en" if english else "es"
    field = _floor_name(observed.get("focusedField"))
    if not field:
        return data[language + "ClauseNoField"]
    quote = operation_floor.floor_data()["templates"][language]["quote"]
    return data[language + "Clause"].replace("{field}", quote.format(value=field))


def _search_opened_said(observed: dict, english: bool) -> str:
    """Ronda 24b (banco r23 x7, «Listo, estoy en «search»»): the sentence of an arrival only a focused field proved
    (data «computerUse.searchOpened.atoms»): the search opened and the field the cursor is in, never a place reached.
    Empty for any other proof. A template for ``.format(place=…)``, so the field's braces are doubled. Twin of the App's
    OperationFloor.SearchOpenedSaid."""

    data = operation_floor.floor_data()["computerUse"]["searchOpened"]
    subgoals = [item for item in observed.get("subgoals") or () if isinstance(item, dict)]
    term = subgoals[-1].get("satisfiedBy") if subgoals else observed.get("satisfiedBy")
    if not _search_opened_proof(term):
        return ""
    language = "en" if english else "es"
    field = _floor_name(observed.get("focusedField"))
    if not field:
        return data[language + "NoField"]
    quote = operation_floor.floor_data()["templates"][language]["quote"]
    named = quote.format(value=field).replace("{", "{{").replace("}", "}}")
    return data[language].replace("{field}", named)


def _proved_on_first_look(observed: dict) -> bool:
    """The term that satisfied the mission's (last) check proves the arrival by itself: neither the model's evidence nor
    an alternative (``placeAlready.weakTerms``), no atom of an arrival by resemblance (``weakAtoms``), and one of the
    terms the plan's check lists, not one an alias renamed."""

    rules = operation_floor.floor_data()["computerUse"]["placeAlready"]
    subgoals = [item for item in observed.get("subgoals") or () if isinstance(item, dict)]
    last = subgoals[-1] if subgoals else {}
    term = last.get("satisfiedBy") if subgoals else observed.get("satisfiedBy")
    check = last.get("successCheck") if subgoals else observed.get("successCheck")
    if not isinstance(term, str) or not term.strip() or term in rules["weakTerms"] or "|" in term or _resembled(term):
        return False
    planned = {item.strip() for item in check.split("|")} if isinstance(check, str) else set()
    return term.strip() in planned


def _resembled(term: object) -> bool:
    """Whether a term carries an atom of an arrival by resemblance (data ``placeAlready.weakAtoms``). Twin of the App's
    OperationFloor.Resembled."""

    weak = operation_floor.floor_data()["computerUse"]["placeAlready"]["weakAtoms"]
    return isinstance(term, str) and any(atom.split(":", 1)[0].strip().casefold() in weak for atom in term.split("&"))


# Live 2026-10-07 (cu-r19): «Llegué al modo Oscuro.», «Llegué a la zona horaria y es (UTC-04:00) Santiago.» A reached
# mission whose question one fact of the window answers alone is answered from that fact (data «computerUse.answer»):
# the option the question names that the window shows selected, or the one value its noun names. Mind only: the App
# leaves every mission with a question to the mind.
_ANSWER: dict = operation_floor.floor_data()["computerUse"]["answer"]
_ANSWER_OPTIONS = re.compile(_ANSWER["options"], re.IGNORECASE)
_ANSWER_NOUN = re.compile(_ANSWER["noun"], re.IGNORECASE)
_ANSWER_NUMBER = re.compile(_ANSWER["number"])
_ANSWER_SHAPES = [
    (re.compile(shape["noun"], re.IGNORECASE), re.compile(shape["value"], re.IGNORECASE)) for shape in _ANSWER["shapes"]
]


def _answer_words(text: str) -> list[str]:
    return [word for word in re.findall(r"[a-z0-9]+", fold(text)) if word not in _ANSWER["articles"]]


_ANSWER_LABELLED = re.compile(_ANSWER["labelled"])


def _labelled_answer(question: str, screen: dict) -> str:
    """Pasada r15b (v3-61): the one line «label: value» of the window whose label words are all words of the question
    («Último examen: 08-10-2026 10:28 (examen rápido)» for «decime cuándo fue el último examen de virus»), as the window
    writes it; "" with none or several (data «computerUse.answer.labelled»)."""

    asked = set(_answer_words(question))
    found: dict[str, str] = {}
    for key in ("numbers", "lines"):
        for text in screen.get(key) or ():
            line = " ".join(_BIDI_MARKS.sub("", text).split()) if isinstance(text, str) else ""
            match = _ANSWER_LABELLED.match(line)
            if match is None or not re.search(r"\w", match.group("value")):
                continue
            label = _answer_words(match.group("label"))
            if not label or not set(label) <= asked or max(map(len, label)) < _ANSWER["labelMinimum"]:
                continue
            name = _floor_name(line)
            if name:
                found.setdefault(fold(name), name)
    return next(iter(found.values())) if len(found) == 1 else ""


def _last_written_answer(question: str, seen: dict, english: bool) -> str:
    """Imprescindibles de mensajería («qué me escribió Ron92»): the last entry of the conversation the window shows
    that names the person asked about as its author, quoted with its time; that it shows none of theirs when it shows
    others'. "" when the question names no author (the chat of a group) or no conversation was read: the lines are then
    the model's to answer from (data «computerUse.answer.lastWritten»)."""

    asked = last_written(question)
    entries = [entry for entry in seen.get("messages") or () if isinstance(entry, str)]
    if asked is not None and not (asked.author is not None and has_written_entries(entries)):
        return _chat_lines_answer(asked, question, seen, english)
    if asked is None or asked.author is None or not has_written_entries(entries):
        return ""
    said = _ANSWER["lastWritten"]["en" if english else "es"]
    quote = operation_floor.floor_data()["templates"]["en" if english else "es"]["quote"]
    author = _restore(asked.author, question)
    found = last_written_by(asked.author, entries)
    if found is None:
        return said["none"].format(author=author) + "."
    text, time = found
    return said["timed" if time else "text"].format(author=author, value=quote.format(value=text), time=time) + "."


def _chat_lines_answer(asked, question: str, seen: dict, english: bool) -> str:
    """Encargo IMP4: the answer read from the lines of a chat drawn without an accessible tree (``seen.chatLines``, the
    region of the application's data «conversation»): the last bubble not the person's own, with its time; that every
    bubble is theirs; with no bubble read, that none could be read (encargo WR: never a draft over the interface's lines,
    «fue «Borrar todo» (22:55)»)."""

    region = app_places.conversation(seen.get("application"))
    lines = seen.get("chatLines")
    if region is None or not isinstance(lines, list):
        return ""
    found = chat_lines.last_written(lines, region)
    said = _ANSWER["lastWritten"]["en" if english else "es"]
    quote = operation_floor.floor_data()["templates"]["en" if english else "es"]["quote"]
    author = _restore(asked.author, question) if asked.author else ""
    if found is None:
        return (said["unread"].format(author=author) if author else said["unreadAny"]) + "."
    if found == "own":
        return (said["none"].format(author=author) if author else said["ownOnly"]) + "."
    if author and asked.chat != asked.author and fold(found.author).strip() != fold(asked.author).strip():
        # Someone wrote last in a group, but the lines do not say it was who the question names: nothing is attributed.
        # (A chat gone to by the person's own name is theirs: every bubble not the person's is that person's.)
        return ""
    value = quote.format(value=found.text)
    if author:
        return said["timed"].format(author=author, value=value, time=found.time) + "."
    return said["timedAny"].format(value=value, time=found.time) + "."


_DEVICE_ROW = re.compile(r"^(?P<name>[^,:]+)[,:](?P<rest>.*)$")


def _device_rows(screen: dict) -> list[tuple[str, str, str]]:
    """Encargo H3: the rows of the window that are a device's — a name, then a category label or a connection state
    in the same row («BT5.2 Mouse, categoría Mouse, …, estado Emparejado», «WH-1000XM4: Conectado») — as (name, the
    state that row writes or "", the folded row), one per name, in the window's order. A state alone in its line is
    nobody's."""

    devices = mission_answer.devices()
    rows: dict[str, tuple[str, str, str]] = {}
    for key in ("numbers", "lines"):
        for text in screen.get(key) or ():
            found = _DEVICE_ROW.match(" ".join(_BIDI_MARKS.sub("", text).split())) if isinstance(text, str) else None
            name = _floor_name(found.group("name")) if found is not None else ""
            if not name or fold(name).strip() in mission_answer.screen_states():
                continue
            rest = found.group("rest")
            spans = [
                (match.end(), len(state), match.start())
                for state in mission_answer.screen_states()
                for match in re.finditer(rf"(?<![a-z0-9]){re.escape(state)}(?![a-z0-9])", fold_in_place(rest))
            ]
            end, _, start = max(spans) if spans else (0, 0, 0)
            state = rest[start:end]
            folded = fold(f"{name} {rest}")
            if not state and not any(mission_answer.has_phrase(folded, label) for label in devices["categoryLabels"]):
                continue
            if state or fold(name) not in rows:
                rows[fold(name)] = (name, state[:1].upper() + state[1:], folded)
    return list(rows.values())


def _device_answer(question: str, screen: dict, english: bool) -> str:
    """Encargo H3 (tanda n5 t3-c09: «vi que los auriculares están conectados» over a TV «No conectado» and a loose
    «Conectado»): a question about the state of a device kind is answered from the window's device rows: those of the
    kind (a word of its name or its category), each with the state its own row writes; with none, that the kind was
    not seen and the rows there are, if any. "" when the question asks no device's state."""

    asked = mission_answer.device_asked(question)
    if asked is None:
        return ""
    devices = mission_answer.devices()
    terms = (*devices["kinds"][asked[0]]["words"], *devices["kinds"][asked[0]]["categories"])
    said = devices["en" if english else "es"]
    quote = operation_floor.floor_data()["templates"]["en" if english else "es"]["quote"]
    rows = _device_rows(screen)
    matched = [row for row in rows if any(mission_answer.has_phrase(row[2], term) for term in terms)]
    if not rows:
        return said["none"].format(kind=asked[1]) + "."
    listed = [
        said["item"].format(name=quote.format(value=name), state=state) if state else quote.format(value=name)
        for name, state, _ in (matched or rows)[:devices["listed"]]
    ]
    if matched:
        return said["seen"].format(devices=_join(listed, english)) + "."
    return said["notSeen"].format(kind=asked[1], devices=_join(listed, english)) + "."


def question_answer(seen: dict, english: bool) -> str:
    """The answer to a reached mission's question when exactly one fact of the window gives it; "" otherwise."""

    question = " ".join(str(seen.get("question") or "").split()).strip(" .?¿!¡")
    screen = seen.get("screen") if isinstance(seen.get("screen"), dict) else {}
    if seen.get("reached") is not True or not question:
        return ""
    if last_written(question) is not None:
        return _last_written_answer(question, seen, english)
    device = _device_answer(question, screen, english)
    if device:
        return device
    values = [item for item in screen.get("values") or () if isinstance(item, dict)]
    said = _ANSWER["en" if english else "es"]
    quote = operation_floor.floor_data()["templates"]["en" if english else "es"]["quote"]
    asked = _ANSWER_OPTIONS.match(question)
    if asked is not None:
        options = {fold(asked.group("first")), fold(asked.group("second"))}
        chosen = {
            _floor_name(item.get("name")) for item in values
            if str(item.get("state") or "").casefold() in _ANSWER["selectedStates"] and fold(item.get("name")) in options
        } - {""}
        if len(chosen) != 1:
            return ""
        return said["option"].format(noun=asked.group("noun"), value=quote.format(value=next(iter(chosen)))) + "."
    asked = _ANSWER_NOUN.match(question)
    words = _answer_words(asked.group("noun")) if asked is not None else []
    if not words:
        line = _labelled_answer(question, screen)
        return said["line"].format(value=quote.format(value=line)) + "." if line else ""
    noun = asked.group("noun")
    named = {
        _floor_name(item.get("value")) for item in values
        if isinstance(item.get("value"), str) and set(words) <= set(_answer_words(str(item.get("name") or "")))
    }
    if not named:
        bare = " ".join(words)
        shapes = [value for noun_shape, value in _ANSWER_SHAPES if noun_shape.match(bare)]
        texts = [
            " ".join(_BIDI_MARKS.sub("", text).split()) for key in ("numbers", "lines")
            for text in screen.get(key) or () if isinstance(text, str)
        ]
        named = {_floor_name(text) for text in texts if any(shape.match(text) for shape in shapes)}
    if not named:
        line = _labelled_answer(question, screen)
        return said["line"].format(value=quote.format(value=line)) + "." if line else ""
    if len(named) != 1 or "" in named:
        return ""
    value = next(iter(named))
    if _ANSWER_NUMBER.match(value):
        return said["number"].format(noun=noun, value=value) + "."
    return said["text"].format(noun=noun, value=quote.format(value=value)) + "."


# A chain that ran out of its steps or its time (estabilización L: «tareas de muchos pasos»): said by the floor too.
_LONG_TASK_STOPS = frozenset({"computer_use_budget_exhausted", "computer_use_time_exhausted"})


_DONE_GOALS: dict[str, re.Pattern[str]] = {
    kind: re.compile(pattern) for kind, pattern in limits_data().get("doneGoals", {}).items()
}


def _done_clause(goal: str, folded: str, said: dict, quote: str, named) -> str:
    """The clause a sub-goal the floor knows how to say is told with (review of L2, C4), "" for any other."""

    typed = _PART_GOALS["type"].match(goal)
    if typed is not None and _part_object(typed.group(1)):
        return said["typed"].format(text=quote.format(value=_part_object(typed.group(1))))
    for kind, template, slot in (("select", "selected", "items"), ("click", "clicked", "items")):
        found = _PART_GOALS[kind].match(goal)
        if found is not None and _part_object(found.group(1)):
            return said[template].format(**{slot: named(_part_object(found.group(1)))})
    searched = _PART_GOALS["search"].match(goal)
    if searched is not None and _part_object(searched.group(1)):
        return said["searched"].format(query=quote.format(value=_part_object(searched.group(1))))
    if _PART_GOALS["create"].match(goal) is not None or _DONE_GOALS["created"].match(folded) is not None:
        return said["created"]
    filled = _DONE_GOALS["filled"].match(goal)
    if filled is not None:
        # A path is told by its file's name («D:\…\informe.docx» → «informe.docx»).
        value = re.split(r"[\\/]", _part_object(filled.group(2)))[-1]
        return said["filled"].format(value=quote.format(value=value), field=named(_part_object(filled.group(1))))
    for kind in ("opened", "switchedOn", "switchedOff"):
        found = _DONE_GOALS[kind].match(folded)
        if found is not None and _part_object(found.group(1)):
            return said[kind].format(item=named(_part_object(found.group(1))))
    return said["sent"] if _DONE_GOALS["sent"].match(folded) is not None else ""


def _done_before(observed: dict, seen: dict, english: bool) -> str:
    """Review of L, H5; review of L2, C3, C4: what the sub-goals reached before the stop did, so a limit never hides
    the part that had an effect (a radio switched off, a message sent), each in a clause the floor knows how to say
    (data «computerUse.limits» es/en; the names as the window spells them): the place got to («llegué a «X»», or «ya
    estabas en «X»» when no act got there), the text typed, the thing created, chosen, clicked or searched, a switch
    turned on or off, the message sent. A sub-goal of no such kind is quoted, as the last resort, under one «hice». A
    sub-goal reached with no act of its own did nothing and is never told as done. "" with none."""

    said = limits_data()["en" if english else "es"]
    quote = operation_floor.floor_data()["templates"]["en" if english else "es"]["quote"]
    names = _window_names(observed, seen)
    told: list[str] = []
    quoted: list[str] = []

    def named(value: str) -> str:
        return quote.format(value=_spelled(value, names) or value)

    for item in seen.get("subgoals") or ():
        if not isinstance(item, dict) or item.get("reached") is not True:
            continue
        goal = str(item.get("goal") or "").strip()
        place = _floor_name(item.get("arrivedAs")) or _place_of(goal, names)
        if place:
            told.append((said["already"] if item.get("acted") is False else said["reached"]).format(
                place=quote.format(value=place)))
            continue
        if item.get("acted") is False:
            # Review of L2, C3: a sub-goal reached with no act of its own (the radio was already on) did nothing.
            continue
        folded = fold(goal)
        said_as = _done_clause(goal, folded, said, quote, named)
        if said_as:
            told.append(said_as)
        elif goal:
            quoted.append(quote.format(value=goal))
    if quoted:
        told.append(said["did"].format(goals=_join(quoted, english)))
    return _join(told, english) if told else ""


def _place_search_cause(observed: dict, seen: dict, lang: str) -> str:
    """Estabilización L3: the search the place does not take, said with the place and where it can be searched instead
    (data app_places «said», «within»; limits «placeSearch»): «el buscador de la biblioteca no me deja escribir; si
    querés, lo busco en la tienda». "" when the data do not say both."""

    stopped = next((item for item in seen.get("subgoals") or ()
                    if isinstance(item, dict) and item.get("reached") is not True), None) or {}
    application = stopped.get("application") or seen.get("application") or observed.get("application")
    place = app_places.search_limit(application, stopped.get("goal") or "", observed.get("goal") or "")
    named = app_places.said_as(application, place, lang)
    offer = app_places.said_as(application, app_places.search_offer(application), lang)
    return limits_data()[lang]["placeSearch"].format(place=named, offer=offer) if named and offer else ""


def limit_final(observed: dict, english: bool) -> str:
    """Estabilización L (decisión 6 del dueño; review of L, H5): a mission that stopped on a limit is told by the floor,
    never drafted: what it did before (``_done_before``), then the limit with its cause (causes
    «computer_use_limit_<kind>»; a device the computer lacks, with the device read: «afterDevice», «bare»), and what it
    typed in the stopped part. A chain that ran out of its steps or its time is told the same way («stopped»). "" for any
    other stop."""

    stop = str(observed.get("stoppedBy") or "")
    chained = isinstance(observed.get("subgoals"), list) and bool(observed.get("subgoals"))
    if not stop.startswith(LIMIT_STOP) and not (chained and stop in _LONG_TASK_STOPS):
        return ""
    lang = "en" if english else "es"
    said = limits_data()[lang]
    quote = operation_floor.floor_data()["templates"][lang]["quote"]
    seen = project_seen(observed, lang)
    done = _done_before(observed, seen, english)
    device = limits_data()["devices"].get(str(observed.get("absentDevice") or ""))
    if stop == DEVICE_STOP:
        if not isinstance(device, dict):
            return ""
        told = (said["afterDevice"] if done else said["bare"]).format(
            done=done, device=quote.format(value=device["name"]), cause=device[lang])
    else:
        cause = _place_search_cause(observed, seen, lang) if stop == PLACE_SEARCH_STOP else ""
        cause = cause or _STOP_CAUSES.get(stop, {}).get(lang, "")
        if not cause:
            return ""
        if stop in limits_data()["absences"]["stops"]:
            # Encargo IMP2: what the request would end is not there; said whole, never as a thing BAXY cannot do.
            told = (said["absentAfter"] if done else said["absent"]).format(done=done, cause=cause)
        elif stop.startswith(LIMIT_STOP):
            told = (said["after"] if done else said["head"]).format(done=done, cause=cause)
        else:
            told = (said["stoppedAfter"] if done else said["stopped"]).format(done=done, cause=cause)
    raw_steps = observed.get("steps") if isinstance(observed.get("steps"), list) else []
    stopped_at = next((index for index, item in enumerate(seen.get("subgoals") or ())
                       if isinstance(item, dict) and item.get("reached") is not True), None)
    # What it typed in the part it stopped in (the parts reached told it already).
    left = [step for step in raw_steps if isinstance(step, dict)
            and (stopped_at is None or step.get("subgoal") in (None, stopped_at))]
    return told[:1].upper() + told[1:] + _typed_left(left, english) + "."


def floor_first(observed: dict, english: bool, succeeded: bool) -> str:
    """The final a mission without a question is told with before any draft (voice audit 2026-10-07): its parts
    from the facts when every name in them is the window's or the person's own, or a failure with its typed cause;
    "" when the model has to word it (a question about the window, a part the facts cannot tell). A stop on a limit
    is the floor's always (``limit_final``)."""

    limit = "" if succeeded else limit_final(observed, english)
    if limit:
        return limit
    seen = project_seen(observed, "en" if english else "es")
    if seen.get("question"):
        return question_answer(seen, english) if succeeded else ""
    if succeeded:
        if seen.get("reached") is not True:
            return ""
        already = already_chosen_sentence(observed, seen, english)
        if already:
            return already
        sentence, preferred = _parts_final(observed, seen, english, _window_names(observed, seen), _mission_app(seen, observed))
        return sentence if preferred else ""
    if seen.get("subgoals") or str(observed.get("stoppedBy") or "") not in _STOP_CAUSES:
        return ""
    sentence = floor_sentence(observed, english, succeeded)
    return sentence if not sentence.startswith(_floor_said(english)["not"] + ":") else ""


def already_chosen_sentence(observed: dict, seen: dict, english: bool) -> str:
    """Pasada v3 r9 (v3-13): a mission of one goal reached on an option it names that was chosen before any act touched
    it (the App's «alreadyChosen», or ``_held_before_acting``) is told as it was: «Oscuro ya estaba elegido en
    Reproductor multimedia». Encargo H1: an application the mission launched to see it is said too («Abrí
    «Configuración» y «Oscuro» ya estaba elegido»). "" otherwise."""

    if seen.get("subgoals") or seen.get("reached") is not True:
        return ""
    chosen = _floor_name(observed.get("alreadyChosen")) or _held_before_acting(observed)
    if not chosen:
        return ""
    data = operation_floor.floor_data()
    lang = "en" if english else "es"
    quote = data["templates"][lang]["quote"]
    template = data["computerUse"]["alreadyChosen"]
    app = _mission_app(seen, observed)
    key = lang + ("Opened" if app and _opened_by_mission(observed) else "" if app else "Bare")
    said = template[key].format(seen=quote.format(value=chosen), app=quote.format(value=app))
    return said[:1].upper() + said[1:] + "."


def _opened_by_mission(observed: dict) -> bool:
    """Encargo H1: an opening of the mission verified that it started the application (receipt «alreadyRunning» false,
    the word cu_projection.describe_step tells it with). Twin of the App's OperationFloor.OpenedByMission."""

    return any(
        isinstance(step, dict) and step.get("operation") == "app.open" and step.get("ok") is True
        and step.get("alreadyRunning") is False
        for step in observed.get("steps") or ()
    )


def _held_before_acting(observed: dict) -> str:
    """Encargo H1 (tandas fin1/fin2 t4-c04 t3 «pon el modo oscuro» answered «Lo hice» over a Configuración that already
    showed «Oscuro»; t3-c18 t2 «elegí el modo Programador» after a click that only opened the navigation, where
    «Programador» showed chosen; t2-c04 t4 «regresa la escala a 100» over «100% (recomendado)» already chosen): the
    option a reached mission of one goal holds, shown chosen, that no act of the mission chose. Its name as the window
    writes it: the arrival the check that held read (a control atom in a chosen state, proved by itself and as
    planned), or the model's citation when it names a value the screen shows chosen. No act chose it when no key was
    sent, no text but a search, and no click named it, switched or selected anything; a click may only have brought it
    into view (its «appeared» holds it as words; the result of a search, whatever its label holds of the name) and,
    after that, only opened a list. With no act at all it held on the first look. "" otherwise: the final is told as before."""

    if observed.get("reached") is not True or observed.get("subgoals"):
        return ""
    term = observed.get("satisfiedBy")
    chosen_states = {"on", "selected"}
    if isinstance(term, str) and term in operation_floor.floor_data()["computerUse"]["weakDone"]["weakTerms"]:
        chosen = _floor_name(observed.get("evidence"))
        screen = observed.get("screen") if isinstance(observed.get("screen"), dict) else {}
        if not any(
            isinstance(item, dict) and _bare(item.get("name")) == _bare(chosen)
            and chosen_states & set(str(item.get("state") or "").split())
            for item in screen.get("values") or ()
        ):
            return ""
    elif _proved_on_first_look(observed) and any(
        atom.split(":")[0].strip() == "control" and atom.rsplit(":", 1)[-1].strip() in chosen_states
        for atom in str(term).split("&")
    ):
        chosen = _floor_name(observed.get("arrivedAs"))
    else:
        return ""
    wanted = _bare(chosen)
    revealed = searched = False
    acting = [
        step for step in observed.get("steps") or ()
        if isinstance(step, dict) and step.get("operation") != "app.open" and _may_have_acted(step)
    ]
    for step in acting:
        if step.get("operation") == "input.scroll":
            continue
        if step.get("operation") == "input.text.type" and step.get("intoSearch") is True:
            # Encargo TZ-OSC2 (tandas z5-z8 t4-c04 t3, «elegí el modo Oscuro» after «oscuro» typed into the window's
            # search and a click on its result): a search typed chooses nothing, but the option counts only once a
            # later click brings it into view (a list filtered as it is typed may select it).
            revealed, searched = False, True
            continue
        if step.get("operation") != "input.visible.click" or step.get("toggled") is True or step.get("selected") is True:
            return ""
        labels = [_bare(step.get(key)) for key in ("label", "name")]
        # The search's result whose new view holds the option («broughtNew», «appeared») was not on it, whatever its
        # label holds of the name («Activar el modo oscuro para aplicaciones»); one named exactly as the option chose it.
        result = searched and step.get("broughtNew") is True and any(
            _shown_as_words(wanted, _bare(name)) for name in step.get("appeared") or () if isinstance(name, str))
        searched = False
        if wanted in labels or (not result and any(_shown_as_words(wanted, label) for label in labels)):
            return ""
        if revealed:
            if not (step.get("opener") is True or step.get("method") == "expand" or only_opened(step)):
                return ""
        elif any(_shown_as_words(wanted, _bare(name)) for name in step.get("appeared") or () if isinstance(name, str)):
            revealed = True
    return chosen if wanted and (revealed or not acting) else ""


def _acted(raw_steps: list) -> bool:
    """A verified step of the mission besides opening the application."""

    return any(
        isinstance(step, dict) and step.get("ok") is True and step.get("operation") not in {None, "app.open"}
        for step in raw_steps
    )


def _weakly_reached(observed: dict) -> bool:
    """Ronda 22: a reached mission (or one of its reached sub-goals) whose term only the model's citation, an alternative
    or a resemblance gave (``semantic.claims.weak_proof``). A mission that carries no term keeps its final. Twin of
    OperationFloor.WeaklyReached."""

    subgoals = [item for item in observed.get("subgoals") or () if isinstance(item, dict) and item.get("reached") is True]
    terms = [item.get("satisfiedBy") for item in subgoals] if subgoals else [observed.get("satisfiedBy")]
    # Revisión 3 de r24b (B1): a focused field (computerUse.searchOpened.atoms) is weak for the book of acts, not for
    # this final: the search opened is said by searchOpened, and a chain whose first part a focused field proved and
    # whose last part a strong atom proved was told «la pantalla todavía no muestra que haya quedado hecho», denying
    # what was verified. Those atoms are taken out of the term before it is judged (twin: weakDone.weakAtoms has no
    # focus).
    opened = operation_floor.floor_data()["computerUse"]["searchOpened"]["atoms"]

    def weak(term: str) -> bool:
        if "|" in term:
            return True
        rest = "&".join(atom for atom in term.split("&") if atom.split(":", 1)[0].strip().casefold() not in opened)
        return bool(rest.strip()) and weak_proof(rest)

    return any(isinstance(term, str) and term.strip() and weak(term) for term in terms)


def _weak_seen(raw_steps: list, screen: dict | None) -> tuple[str, str] | None:
    """Ronda 24 (pasada r23, v3-14): what the screen shows of the mission's last verified click, when its arrival is weak:
    the one value of the window (``screen.values``) in a chosen state (on, selected) whose name the click's label holds as
    whole words («Fecha de modificación» on, after a click on «Opción de ordenación Fecha de modificación
    seleccionada»): (name, state). None when no value or two relate (no guess). Twin of OperationFloor.WeakSeen."""

    clicks = [
        step for step in raw_steps
        if isinstance(step, dict) and step.get("ok") is True and step.get("operation") == "input.visible.click"
        and not only_opened(step)
    ]
    label = _bare(clicks[-1].get("label")) if clicks else ""
    values = screen.get("values") if isinstance(screen, dict) else None
    if not label or not isinstance(values, list):
        return None
    found = {}
    for item in values:
        if not isinstance(item, dict):
            continue
        states = str(item.get("state") or "").split()
        state = "on" if "on" in states else "selected" if "selected" in states else ""
        name = str(item.get("name") or "").strip()
        if state and name and _shown_as_words(_bare(name), label):
            found[name] = state
    return next(iter(found.items())) if len(found) == 1 else None


def _weak_done(raw_steps: list, app: str, english: bool, screen: dict | None = None) -> str:
    """Ronda 22 (data «computerUse.weakDone»): the verified acts besides opening the application, counted, and the
    result not shown on screen. Ronda 24 (pasada r23, v3-14): when the screen shows the value the last click named in a
    chosen state (``_weak_seen``), that observed fact is said instead, never denied (data «weakDone.seen»)."""

    data = operation_floor.floor_data()
    language = "en" if english else "es"
    weak = data["computerUse"]["weakDone"]
    quote = data["templates"][language]["quote"]
    shown = _weak_seen(raw_steps, screen)
    if shown is not None:
        name, state = shown
        return weak["seen"][language].format(
            app=quote.format(value=app), value=quote.format(value=name), state=weak["seen"]["states"][language][state]) + "."
    count = sum(
        1 for step in raw_steps
        if isinstance(step, dict) and step.get("ok") is True and step.get("operation") not in {None, "app.open"}
    )
    template = weak[language + "One" if count == 1 else language]
    # Revisión 1 de r22 (hallazgo d): the count in words, never a figure nothing on screen showed.
    words = weak["countWords"][language]
    said = words[count - 1] if count <= len(words) else weak["countMany"][language]
    return template.format(count=said, app=quote.format(value=app)) + "."


def _window_names(observed: dict, seen: dict) -> list[str]:
    raw_steps = observed.get("steps") if isinstance(observed.get("steps"), list) else []
    screen = seen.get("screen") if isinstance(seen.get("screen"), dict) else {}
    return [
        name for value in (
            *(step.get("name") for step in raw_steps if isinstance(step, dict) and step.get("ok") is True),
            *(item.get("name") for item in screen.get("values") or () if isinstance(item, dict)),
            *(line for line in screen.get("lines") or () if isinstance(line, str)),
            seen.get("windowTitle"),
        ) if (name := _floor_name(value))
    ]


def _mission_app(seen: dict, observed: dict | None = None) -> str:
    """The application a final names: the one said, else the title of the window read, only when that window is one
    asked for. Ronda 24 (pasada r23 t-drag-2): the App marks a window nobody asked for (no application said, no tie, no
    binding, not the window the person pointed at) with ``windowAsked`` false, and its title never names the place
    («No pude hacerlo en «Spotify Premium»»); twin of OperationFloor.ComputerUse."""

    said = _floor_name(seen.get("application"))
    if said or (isinstance(observed, dict) and observed.get("windowAsked") is False):
        return said
    return _floor_name(seen.get("windowTitle"))


def floor_sentence(observed: dict, english: bool, succeeded: bool) -> str:
    """The plain final of a mission said from its facts alone (data/operation_floor.v1.json «computerUse»), or ""
    when they hold nothing to say."""

    seen = project_seen(observed, "en" if english else "es")
    if seen.get("question"):
        answer = question_answer(seen, english) if succeeded else ""
        if answer or not (succeeded and seen.get("reached") is True):
            return answer
        # v3 r5a M3: reached, and no fact of the window answers the question: said so, never a list of the steps.
        return unanswered_sentence(observed, seen, english)
    if succeeded and seen.get("reached") is True:
        already = already_chosen_sentence(observed, seen, english)
        if already:
            return already
        told, _ = _parts_final(observed, seen, english, _window_names(observed, seen), _mission_app(seen, observed))
        if told:
            return told
    data = operation_floor.floor_data()
    said = data["computerUse"]["en" if english else "es"]
    quote = data["templates"]["en" if english else "es"]["quote"]
    raw_steps = observed.get("steps") if isinstance(observed.get("steps"), list) else []
    screen = seen.get("screen") if isinstance(seen.get("screen"), dict) else {}
    names = [
        name for value in (
            *(step.get("name") for step in raw_steps if isinstance(step, dict) and step.get("ok") is True),
            *(item.get("name") for item in screen.get("values") or () if isinstance(item, dict)),
        ) if (name := _floor_name(value))
    ]
    app = _mission_app(seen, observed)
    if succeeded and seen.get("reached") is True:
        shade = seen.get("chosenShade")
        if isinstance(shade, dict) and "shade" in said and _floor_name(shade.get("chosen")):
            # The colour in the final's language («blue» said to a Spanish final is «azul»).
            asked = next(iter(colour_shades(shade.get("asked"), "en" if english else "es")), str(shade.get("asked")))
            return said["shade"].format(chosen=_floor_name(shade.get("chosen")), asked=asked.casefold()) + "."
        # Revisión 1 de r24b (B3): an arrival only a focused field proved is told as the search opened even when the
        # window does not spell the place asked («ir a search» on a Spanish window); never «lo hice en X» nor the
        # weak count of a result (focus is a weak atom of semantic.claims.weak_proof).
        opened = _search_opened_said(observed, english)
        if opened:
            return opened + "."
        goals = [item.get("goal") for item in seen.get("subgoals") or () if isinstance(item, dict)] or [seen.get("goal")]
        place = _place_of(goals[-1], names)
        if place:
            return _place_said(observed, english).format(place=quote.format(value=place)) + "."
        # «Listo, lo hice en X» only after a verified act besides opening the application (falsos éxitos v3 M1), and
        # only when a check of the window proved it (ronda 22, pasada r18 t3-c18, t3-c19, t4-c06): on the model's own
        # citation or a resemblance the acts are counted and the result is not told as done (data «weakDone»).
        if not app or not _acted(raw_steps):
            return ""
        if _weakly_reached(observed):
            return _weak_done(raw_steps, app, english, screen)
        return said["app"].format(app=quote.format(value=app)) + "."
    if succeeded:
        # A verified result that does not say it reached anything is never told as a failure.
        return ""
    seen_not_done = _floor_name(observed.get("seenNotDone"))
    if seen_not_done and str(observed.get("stoppedBy") or "") == "computer_use_seen_not_done" and not _acted(raw_steps):
        # Seen, not done (falsos éxitos v3 M1): nothing of its own was done and what the model cited already shows.
        template = data["computerUse"]["seenNotDone"]
        lang = "en" if english else "es"
        if app:
            return template[lang].format(seen=quote.format(value=seen_not_done), app=quote.format(value=app)) + "."
        return template[lang + "Bare"].format(seen=quote.format(value=seen_not_done)) + "."
    place = _place_of(seen.get("firstUnreached") or seen.get("goal"), names)
    if place and str(observed.get("stoppedBy") or "") == "computer_use_already_there_unconfirmed":
        # The click on the place's own name left the window as it was (live v2-s12: Steam already on its library):
        # probably there already, never told as arrived.
        return data["computerUse"]["alreadyThere"]["en" if english else "es"].format(
            place=quote.format(value=place)) + "."
    # Encargo H1 (tandas fin1/fin2 t3-c02 t1): the application the mission started is said before what it could not do.
    opened = "Opened" if app and _opened_by_mission(observed) else ""
    if place:
        head = said["notPlace" + opened].format(place=quote.format(value=place), app=quote.format(value=app))
    elif app:
        head = said["notApp" + opened].format(app=quote.format(value=app))
    else:
        head = said["not"]
    cause = seen.get("stoppedBecause") if str(observed.get("stoppedBy") or "") in _STOP_CAUSES else None
    told = said["cause"].format(head=head, cause=cause) if isinstance(cause, str) and cause.strip() else head
    return told + _typed_left(raw_steps, english) + "."


_UNANSWERED: dict = operation_floor.floor_data()["computerUse"]["unanswered"]
_READ_FAILURE = re.compile(_UNANSWERED["readFailure"])
_ARRIVAL_DENIED = re.compile(_UNANSWERED["arrivalDenied"])
_PLACE_OBJECT_LEAD = re.compile(_UNANSWERED["placeObjectLead"])
_PLACE_QUOTES = "«»\"“”'"


def _unanswered_place(observed: dict, seen: dict) -> str:
    goals = [item.get("goal") for item in seen.get("subgoals") or () if isinstance(item, dict)] or [seen.get("goal")]
    goal = str(goals[-1] or "").split(QUESTION_MARK)[0].strip()
    return _place_of(goal, _window_names(observed, seen)) or _mission_app(seen, observed)


def unanswered_sentence(observed: dict, seen: dict, english: bool) -> str:
    """v3 r5a M3 (v3-43): «Llegué a «Opciones de energía», pero no pude leer en la pantalla la respuesta a «…».» — a
    mission that reached its place with a question no fact of the window answers; "" without a place or a question."""

    question = " ".join(str(seen.get("question") or "").split()).strip(" .?¿!¡")
    place = _unanswered_place(observed, seen)
    if not question or not place:
        return ""
    quote = operation_floor.floor_data()["templates"]["en" if english else "es"]["quote"]
    return _UNANSWERED["en" if english else "es"].format(
        place=quote.format(value=place), question=quote.format(value=question)) + "."


def reached_but_unread(folded_reply: str, observed: dict) -> bool:
    """v3 r5a M3: a draft over a mission that reached its place with a question, which says it could not read or see the
    answer without denying the arrival («No pude ver qué plan está activo: la página seguía cargando»). Such a draft
    tells no failure of the mission (it is the floor's own unanswered_sentence); one that denies the arrival does."""

    if observed.get("reached") is not True:
        return False
    seen = project_seen(observed, "es")
    if not seen.get("question"):
        return False
    if _READ_FAILURE.search(folded_reply) is None or _ARRIVAL_DENIED.search(folded_reply) is not None:
        return False
    # Review of M3: «No se muestra Opciones de energía; no pude ver el plan.» denies the place itself, not the answer.
    # A read failure whose object (right after it, or its subject right before it) is the place reached is a denied
    # arrival.
    return not _read_failure_names_place(folded_reply, fold(_unanswered_place(observed, seen)))


def _read_failure_names_place(folded_reply: str, place: str) -> bool:
    if not place:
        return False
    for found in _READ_FAILURE.finditer(folded_reply):
        after = folded_reply[found.end():].lstrip()
        lead = _PLACE_OBJECT_LEAD.match(after)
        if lead is not None:
            after = after[lead.end():]
        if after.lstrip(_PLACE_QUOTES).startswith(place):
            return True
        if folded_reply[:found.start()].rstrip().rstrip(_PLACE_QUOTES).endswith(place):
            return True
    return False


def read_failure_residue(folded_reply: str) -> str:
    """The draft without what it says it could not read or see: what is left must tell no failure of the mission for
    the honest «couldn't read the answer» to stand (review of M3: «No pude hacerlo: no se ve ningún plan.»)."""

    return _READ_FAILURE.sub(" ", folded_reply)


def _typed_left(steps: list, english: bool) -> str:
    """Falsos éxitos v3 M4 (t-form-2: «No pude hacerlo en «Bloc de notas»…» after typing «casa» and «hogar» into the
    document): a mission that did not get there says the texts it left typed. Twin of the App's
    OperationFloor.TypedLeft."""

    data = operation_floor.floor_data()
    quote = data["templates"]["en" if english else "es"]["quote"]
    said = _floor_said(english)
    texts = [
        # Ronda 20 P1: a text that went into a part of a document the step did not choose says that part.
        said["typedPart"].format(text=quote.format(value=text), field=quote.format(value=_floor_name(step.get("into"))))
        if _typed_into_unnamed_part(step) else quote.format(value=text)
        for step in steps
        if isinstance(step, dict) and step.get("ok") is True and step.get("operation") == "input.text.type"
        # Encargo TZ-DC3 (banco zt1 c6): a text the look after it did not show («arrived» false, the App's
        # MarkAppeared) is no text left typed: the final says only the rest.
        and step.get("arrived") is not False
        and (text := _floor_name(step.get("text")))
    ]
    # Ronda 24 (pasada r23 v3-11: «no lo abrí ni lo creé yo… no escribí nada» after «Agregar página» made «Sin
    # título»): what the mission left counts what it created too (the click's «createdDocument»), first.
    created = [
        said["createdThing"].format(document=quote.format(value=document), label=quote.format(value=label))
        for step in steps
        if isinstance(step, dict) and step.get("ok") is True and step.get("operation") == "input.visible.click"
        and (document := _floor_name(step.get("createdDocument"))) and (label := _floor_name(step.get("label")))
    ]
    if created:
        typed = said["createdAndTyped"].format(texts=_join(texts, english)) if texts else ""
        return said["createdLeft"].format(created=_join(created, english)) + typed
    return said["typedLeft"].format(texts=_join(texts, english)) if texts else ""


def _typed_into_unnamed_part(step: dict) -> bool:
    """Ronda 20 P1 (v3-11 t2): a step written at the caret whose receipt says the text went into a part of a document
    other than its body (data «computerUse.documentPart» over the folded «into»). «into» is what had the keyboard on
    the view before the step: a step that chose its field («field») was delivered there by the provider, wherever the
    keyboard was (review of r20 P1, finding 2), and so was one the App gave the index of the field the sub-goal's last
    click aimed at. An index the App read from the focus («atCaret»: window.focused carries its «i») is no choice of
    the step (review 2, finding 1). Twin of the App's OperationFloor.TypedIntoUnnamedPart."""

    if str(step.get("field") or "").strip() or (step.get("index") is not None and step.get("atCaret") is not True):
        return False
    # Review 3 of r20 P1 (B1): «intoDocument», the App saw that the control's name is the one the window's title gives
    # the document itself (``_names_the_window``): its body, whatever words the person's file name holds.
    return step.get("intoDocument") is not True and _names_a_part(step.get("into"))
