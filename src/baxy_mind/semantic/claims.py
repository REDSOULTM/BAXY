"""What a reply claims BAXY did, and which acts the turn's operations can back (falsos éxitos v3, M4).

Live 2026-10-07 (v3 first pass): «Listo, abrí OBS Studio y creé una nueva escena llamada Pruebas.» after a single
``app.open``; «Copié la imagen prueba.png…» from a mission that took no step; «He guardado el texto en
Documentos/baxy-prueba-v3/baxy-nota1.txt.» where the facts held only the file's name; and, in uso real tanda 1, «Abrí la
carpeta «facturas octubre»» for a folder that was created. The composer told the request, not the facts.

The book of acts is a positive list (data/act_claims.v1.json): each operation declares the lemmas of the acts it can
state — the verb of its plain clause in data/operation_floor.v1.json, its ``operationActs`` and their ``groups``, and its
``exactActs`` as they are — and a
reply may say in the first person past only acts some verified operation of the turn backs. These readers read BAXY's
reply, never the person's request. Quoted text («…», "…") is the screen's or the person's own words and is left out; a
question reports nothing; a denied act («no la creé», «I didn't create it») is no claim.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from . import voice_register
from . import cu_tipos
from .normalize import fold, fold_in_place

_DATA = Path(__file__).resolve().parent.parent / "data" / "act_claims.v1.json"
_FLOOR = Path(__file__).resolve().parent.parent / "data" / "operation_floor.v1.json"
_CLITICS = ("nos", "les", "los", "las", "me", "te", "se", "lo", "la", "le")


@lru_cache(maxsize=1)
def data() -> dict:
    return json.loads(_DATA.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _floor_operations() -> dict:
    return json.loads(_FLOOR.read_text(encoding="utf-8"))["operations"]


def _infinitive(word: str) -> str:
    clitic = next((c for c in _CLITICS if word.endswith(c) and word[: -len(c)].endswith(("ar", "er", "ir"))), "")
    return word[: len(word) - len(clitic)]


# ---------------------------------------------------------------- the reader: acts told in the first person past
@lru_cache(maxsize=1)
def _preterites() -> dict[str, str]:
    """First person singular preterite (accented, as written) -> infinitive."""

    known = dict(voice_register.act_preterite_lemmas())
    for infinitive in data()["extraInfinitives"]:
        if infinitive.endswith("ar"):
            known.setdefault(voice_register.preterite_ar(infinitive), infinitive)
        else:
            known.setdefault(infinitive[:-2] + "í", infinitive)
    known.update(data()["irregularPreterites"])
    # «esté» is the subjunctive of «estar», whose preterite is «estuve»: no act.
    return {word: lemma for word, lemma in known.items() if lemma not in data()["notActs"]}


@lru_cache(maxsize=1)
def _known_infinitives() -> frozenset[str]:
    return frozenset(_preterites().values())


@lru_cache(maxsize=1)
def _known_folded() -> dict[str, str]:
    """Each known infinitive folded («anadir») -> as written («añadir»)."""

    return {fold(item): item for item in _known_infinitives()}


def _participle_lemma(word: str) -> str:
    """The infinitive of a participle («creada» -> «crear»), only when the data knows the verb: an unknown participle
    («estado», «tenido» before the data knew «tener») is no claim, as claimed_acts promises."""

    folded = fold(word)
    known = _known_folded()
    # The data lists the masculine singular («abierto»); «abierta», «abiertos», «abiertas» are the same participle.
    masculine = re.sub(r"(?:a|os|as)$", "o", folded)
    irregular = data()["irregularParticiples"].get(folded) or data()["irregularParticiples"].get(masculine)
    if irregular:
        return known.get(fold(irregular), "")
    for ending in ("ado", "ada", "ados", "adas"):
        if folded.endswith(ending) and len(folded) > len(ending) + 1:
            return known.get(folded[: -len(ending)] + "ar", "")
    for ending in ("ido", "ida", "idos", "idas"):
        if folded.endswith(ending) and len(folded) > len(ending) + 1:
            stem = folded[: -len(ending)]
            return known.get(stem + "er") or known.get(stem + "ir", "")
    return ""


@lru_cache(maxsize=1)
def _third_preterites() -> dict[str, str]:
    """Third person preterite (folded) -> infinitive, for the reflexive passive («se creó», «se guardaron»)."""

    forms: dict[str, str] = {}
    for folded, infinitive in _known_folded().items():
        stem, ending = folded[:-2], folded[-2:]
        if ending == "ar":
            forms.setdefault(stem + "o", infinitive)
            forms.setdefault(stem + "aron", infinitive)
        elif ending in {"er", "ir"}:
            forms.setdefault(stem + "io", infinitive)
            forms.setdefault(stem + "ieron", infinitive)
    forms.update({fold(word): lemma for word, lemma in data()["irregularThirdPreterites"].items()})
    return {word: lemma for word, lemma in forms.items() if lemma not in data()["notActs"]}


@lru_cache(maxsize=1)
def _third_singulars() -> dict[str, str]:
    """Third person singular preterite as written («abrió», «copió», «hizo») -> infinitive. Accented, unlike the folded
    table above: folded «copio» is also the present («copio el texto»), which tells nothing done."""

    forms: dict[str, str] = {}
    for infinitive in _known_infinitives():
        lowered = infinitive.casefold()
        if lowered.endswith("ar"):
            forms.setdefault(lowered[:-2] + "ó", infinitive)
        elif lowered.endswith(("er", "ir")):
            forms.setdefault(lowered[:-2] + "ió", infinitive)
    forms.update(
        {word.casefold(): lemma for word, lemma in data()["irregularThirdPreterites"].items() if not word.endswith("n")}
    )
    return {word: lemma for word, lemma in forms.items() if lemma not in data()["notActs"]}


def _subjectless_acts(lowered: str) -> list[tuple[str, frozenset[str]]]:
    """v3-27 r9 «Abrió el mapa de caracteres y copió el símbolo del euro.» (no step at all): a past told with no subject
    is BAXY's own act told in the third person (or in English with no «I»: «Opened Character Map and copied…»). Read
    only from the start of the sentence and along the clauses joined to it, each opened by the verb (after a lead such
    as «ya», «luego» or a clitic, or a one-word interjection before it: «Listo, abrió…»); a clause with a subject or
    anything else before its verb ends the reading («la ventana se cerró y abrió otra», «dijiste que abrió…»). A verb
    followed by «a»/«de» opens a periphrasis («empezó a sonar», «terminó de cargar») and tells no act of its own."""

    rule = data()["subjectless"]
    leads = {fold(item) for item in rule["leads"]}
    english_leads = set(data()["englishLeads"])
    base_forms = set(rule["englishBaseForms"])
    singulars = _third_singulars()
    english = data()["english"]
    found: list[tuple[str, frozenset[str]]] = []
    for clause in _CLAUSE_SPLIT.split(lowered):
        words = _WORD.findall(clause)
        index = 0
        while index < len(words) and (fold(words[index]) in leads or words[index] in english_leads):
            index += 1
        if index >= len(words):
            continue
        word, after = words[index], words[index + 1:]
        lemma = singulars.get(word)
        if lemma and not (after and after[0] in {"a", "de"}):
            told = _act_told(lemma, " ".join(words[:index]), " ".join(after))
            if told:
                found.append((word, frozenset({told})))
            continue
        lemmas = english.get(word)
        if lemmas and word not in base_forms:
            found.append((word, frozenset(lemmas)))
            continue
        if len(words) == 1 and not found:
            continue
        break
    return found


_QUOTED = re.compile(r"«[^»]*»|\"[^\"]*\"|“[^”]*”")
_CLAUSE_SPLIT = re.compile(r"[,;:]|\s(?:y|e|pero|aunque|and|but)\s")
_NEGATED_BEFORE = re.compile(
    r"\b(?:no|nunca|jamas|ni|sin|aun\s+no|todavia\s+no)\s+(?:(?:me|te|se|lo|la|los|las|le|les|ya)\s+)*$"
)
_PERFECT = re.compile(
    r"\b(?:(?:me|te|se|lo|la|los|las|le|les)\s+)?(?:he|hemos)\s+(?:ya\s+)?(?P<participle>[a-záéíóúüñ]+)\b"
)
_JOINED_PARTICIPLE = re.compile(r"(?:,|\s(?:y|e)\b)\s+(?:(?:ya|tambien|también|luego|despues|después)\s+)?(?P<participle>[a-záéíóúüñ]+)\b")
_WORD = re.compile(r"[a-záéíóúüñ]+")
_REFLEXIVE_PASSIVE = re.compile(r"\bse\s+(?P<verb>[a-záéíóúüñ]+)\b")
_PERFECT_AUXILIARY = frozenset({"he", "hemos", "ya"})


def _sentences(text: object) -> list[str]:
    """The reply's sentences that report, quotes taken out; a question reports nothing."""

    unquoted = _QUOTED.sub(" ", str(text or "").replace("’", "'"))
    return [
        part for part in re.findall(r"[^.!?\n]+[.!?\n]*", unquoted)
        if part.strip() and "?" not in part and "¿" not in part
    ]


def _denied(before: str) -> bool:
    """The act is denied («no la creé») or only supposed: a clause opened by «si» («no pude confirmar si se hizo», «no
    sé si se guardó») asks or supposes, it does not tell. «sí» (yes) keeps its accent and is no supposition."""

    # fold() trims the trailing space the clitic needs before the verb.
    clause = _CLAUSE_SPLIT.split(fold(before) + " ")[-1]
    if _NEGATED_BEFORE.search(clause) is not None:
        return True
    raw_clause = _CLAUSE_SPLIT.split(before.casefold() + " ")[-1]
    return re.search(r"\b(?:" + "|".join(data()["supposing"]) + r")\b", raw_clause) is not None


@lru_cache(maxsize=1)
def _english_leads() -> str:
    return "|".join(re.escape(item) for item in data()["englishLeads"])


def _act_told(lemma: str, before: str, after: str) -> str:
    """The act a read verb tells, or "": an auxiliary («he conseguido», «tuve que», «logré») tells the infinitive that
    follows it and nothing without one («lo he logrado»); a pro-verb over what was already said («lo hice», «ya lo he
    hecho») tells no new act."""

    auxiliaries = data()["auxiliaries"]
    if lemma in auxiliaries["lemmas"]:
        links = set(auxiliaries["links"])
        following = [word for word in _WORD.findall(after)[:3] if word not in links]
        if not following:
            return ""
        return _known_folded().get(fold(_infinitive(following[0])), "")
    pro_verbs = data()["proVerbs"]
    if lemma in pro_verbs["lemmas"]:
        previous = [word for word in _WORD.findall(before) if word not in _PERFECT_AUXILIARY]
        if previous and previous[-1] in pro_verbs["objects"]:
            return ""
    return lemma


def observed_stop(observed: object) -> bool:
    """The operation observed its own stop: a non-empty stop fact (``stopFacts.facts``, ``stoppedBy``)."""

    return isinstance(observed, dict) and any(
        isinstance(observed.get(fact), str) and observed[fact].strip() for fact in data()["stopFacts"]["facts"]
    )


def _stop_told_alone(lemmas: Iterable[str], before: str, after: str) -> bool:
    """Estabilidad cu-v3 2026-10-08 (v2-g1 «…así que paré a mitad para no estorbarte»; review r2 finding 1): a stop
    told of BAXY's own work, with no object — nothing follows it but a pause or one of ``stopFacts.tails`` («a mitad»,
    «porque…», «halfway») and no object clitic precedes it. «Paré la música», «la detuve», «I stopped the music» stop a
    thing: an act that needs its operation, whatever stop the turn observed."""

    stops = data()["stopFacts"]
    if not set(lemmas) & set(stops["lemmas"]):
        return False
    previous = [word for word in _WORD.findall(before) if word not in _PERFECT_AUXILIARY]
    if previous and previous[-1] in stops["objectClitics"]:
        return False
    rest = fold(after)
    if not rest or not rest[0].isalnum():
        return True
    return any(re.match(rf"{re.escape(fold(tail))}\b", rest) for tail in stops["tails"])


def claimed_acts(
    text: object, third_person: bool = True, own_stop: bool = False,
) -> list[tuple[str, frozenset[str]]]:
    """Each act the reply tells as BAXY's own in the past: (the word as written, the lemmas it may stand for).
    Spanish: a first person preterite («creé», «puse»), «he + participio» («he creado»), the participle a result is
    left in («te dejé creada», «quedó creada»), the reflexive passive («se creó») and a past with no subject at the
    start of the sentence («Abrió el mapa… y copió…», ``_subjectless_acts``) — the third person ones only
    with ``third_person``, since a failure explains what happened in them («se presionó antes de…»), and only for
    acts on the PC's things (the world's events are told so too: «el partido ya se jugó»); English: «I + past»
    («I created»), and a past joined to it («…and saved»). Only verbs the data knows are read: an unknown word is
    no claim (the list is positive on the side of what is allowed, not of what is read). With ``own_stop`` (the turn
    observed its own stop), a stop told of BAXY's own work is no act (``_stop_told_alone``)."""

    preterites = _preterites()
    english = data()["english"]
    rule = data()["resultatives"]
    own_results = {fold(item) for item in rule["firstPerson"]}
    third_results = {fold(item) for item in rule["thirdPerson"]} if third_person else set()
    third_acts = {fold(item) for item in rule["thirdPersonActs"]}
    third = _third_preterites()
    found: list[tuple[str, frozenset[str]]] = []
    for sentence in _sentences(text):
        lowered = sentence.casefold()
        words = list(_WORD.finditer(lowered))
        for index, match in enumerate(words):
            word = match.group(0)
            before, after = lowered[: match.start()], lowered[match.end():]
            if fold(word) in own_results | third_results and index + 1 < len(words):
                # «te dejé creada la escena», «quedó creada»: the participle is the act told; in the third person
                # only an act on the PC's things (thirdPersonActs), the world's events are told so too.
                following = words[index + 1].group(0)
                lemma = _participle_lemma(following)
                if lemma and (fold(word) in own_results or fold(lemma) in third_acts):
                    if not _denied(before):
                        found.append((f"{word} {following}", frozenset({lemma})))
                    continue
            lemma = preterites.get(word)
            if lemma and not _denied(before):
                lemma = _act_told(lemma, before, after)
                if lemma and not (own_stop and _stop_told_alone((lemma,), before, after)):
                    found.append((word, frozenset({lemma})))
        for match in _PERFECT.finditer(lowered):
            lemma = _participle_lemma(match.group("participle"))
            before = lowered[: match.start("participle")]
            if lemma and not _denied(lowered[: match.start()]):
                lemma = _act_told(lemma, before, lowered[match.end():])
                if lemma:
                    if not (own_stop and _stop_told_alone((lemma,), before, lowered[match.end():])):
                        found.append((match.group(0), frozenset({lemma})))
                    # «He abierto el mapa de caracteres y copiado el símbolo»: the auxiliary also tells each participle
                    # joined to it (v3-27 r7: «copiado» rode on «he abierto» after one input.keyboard.open).
                    # Only the invariable participle the perfect takes («copiado», «escrito»): one that agrees with a
                    # noun («la carpeta, ordenada por fecha», «la ventana, cerrada antes») describes it and tells no act.
                    # An auxiliary tells the infinitive after it, as in the perfect itself («y conseguido copiar»).
                    for joined in _JOINED_PARTICIPLE.finditer(lowered, match.end()):
                        participle = joined.group("participle")
                        if not fold(participle).endswith("o"):
                            continue
                        more = _participle_lemma(participle)
                        if more:
                            more = _act_told(more, lowered[: joined.start("participle")], lowered[joined.end():])
                        if more:
                            found.append((joined.group(0).strip(", "), frozenset({more})))
        if third_person:
            found.extend(_subjectless_acts(lowered))
        for match in _REFLEXIVE_PASSIVE.finditer(lowered) if third_person else ():
            lemma = third.get(fold(match.group("verb")))
            if lemma and fold(lemma) in third_acts and not _denied(lowered[: match.start()]):
                found.append((match.group(0), frozenset({lemma})))
        leads = _english_leads()
        for match in re.finditer(
            rf"\bi(?:'ve|\s+have)?\s+(?:(?:{leads})\s+)*(?P<verb>[a-z]+)\b", lowered
        ):
            lemmas = english.get(match.group("verb"))
            if not lemmas:
                continue
            rest = lowered[match.end():]
            if not (own_stop and _stop_told_alone(lemmas, "", rest)):
                found.append((match.group(0), frozenset(lemmas)))
            for joined in re.finditer(rf"(?:,|\band\b|\bthen\b)\s+(?:(?:{leads})\s+)*(?P<verb>[a-z]+)\b", rest):
                more = english.get(joined.group("verb"))
                if more and not (own_stop and _stop_told_alone(more, "", rest[joined.end():])):
                    found.append((joined.group(0).strip(", "), frozenset(more)))
    return found


# ---------------------------------------------------------------- attempts the reply tells (v3 r5a M6)
@lru_cache(maxsize=1)
def _english_bases() -> dict[str, frozenset[str]]:
    """The base form and the gerund of each English past the data knows («clicked» -> «click», «clicking»)."""

    bases: dict[str, frozenset[str]] = {}
    for past, lemmas in data()["english"].items():
        if not past.endswith("ed"):
            continue
        for base in (past[:-2], past[:-1]):
            if len(base) >= 3:
                bases.setdefault(base, frozenset(lemmas))
                bases.setdefault((base[:-1] if base.endswith("e") else base) + "ing", frozenset(lemmas))
    return bases


@lru_cache(maxsize=1)
def _attempt_patterns() -> tuple[re.Pattern[str], re.Pattern[str]]:
    rule = data()["attempts"]
    leads = sorted(rule["es"], key=len, reverse=True)
    spanish = re.compile(
        r"\b(?P<lead>" + "|".join(re.escape(item).replace(r"\ ", r"\s+") for item in leads) + r")\b"
        r"(?:\s+(?P<verb>[a-z]+(?:\s+[a-z]+){0,2}))?"
    )
    english_leads = sorted(rule["en"], key=len, reverse=True)
    english = re.compile(
        r"\bi(?:'ve|\s+have)?\s+(?:(?:" + _english_leads() + r")\s+)*(?P<lead>"
        + "|".join(re.escape(item).replace(r"\ ", r"\s+") for item in english_leads) + r")\b"
        r"(?:\s+(?P<verb>[a-z]+(?:\s+[a-z]+){0,2}))?"
    )
    return spanish, english


def _attempted_lemmas(words: str, english: bool) -> frozenset[str]:
    """The act an attempt names («abrir la pestaña» -> abrir, «hacer clic» -> pulsar, «click» -> pulsar); empty when the
    data does not know it."""

    words = words.strip()
    for phrase, lemmas in data()["attempts"]["phrases"].items():
        if words == phrase or words.startswith(phrase + " "):
            return frozenset(lemmas)
    first = words.split()[0] if words else ""
    if not first:
        return frozenset()
    if english:
        return _english_bases().get(first, frozenset())
    lemma = _known_folded().get(fold(_infinitive(first)), "")
    return frozenset({lemma}) if lemma else frozenset()


def claimed_attempts(text: object) -> list[tuple[str, frozenset[str]]]:
    """Each attempt the reply tells as BAXY's own («intenté pulsar Detalles», «traté de abrirla», «I tried to click
    Details»): (the words, the lemmas of the act tried; empty when the act is not one the data knows). A denied or
    supposed attempt («no intenté nada», «si lo intenté») is no claim; quotes and questions are left out."""

    spanish, english = _attempt_patterns()
    found: list[tuple[str, frozenset[str]]] = []
    for sentence in _sentences(text):
        folded = fold(sentence)
        for match in spanish.finditer(folded):
            previous = _WORD.findall(folded[: match.start()])
            # «se trate de», «que lo intente»: a subjunctive supposes, it tells no attempt.
            subjunctive = bool(previous) and (
                previous[-1] in {"se", "que"} or (previous[-1] in _CLITICS and previous[-2:-1] == ["que"])
            )
            if _denied(folded[: match.start()]) or subjunctive:
                continue
            found.append((match.group(0).strip(), _attempted_lemmas(match.group("verb") or "", False)))
        lowered = sentence.casefold().replace("’", "'")
        for match in english.finditer(lowered):
            found.append((match.group(0).strip(), _attempted_lemmas(match.group("verb") or "", True)))
    return found


def unbacked_attempt(text: object, step_operations: Iterable[str]) -> str:
    """The first attempt the reply tells that no step of the mission made, done or failed, or "" (v3 r5a M6). With no
    step at all every attempt is unbacked: only the cause the mission stopped on can be said. With steps, an attempt
    whose act the data knows needs a step of an operation that states it; one it does not know is not judged."""

    attempts = claimed_attempts(text)
    if not attempts:
        return ""
    operations = [str(item) for item in step_operations if str(item or "")]
    if not operations:
        return attempts[0][0]
    backed: set[str] = set()
    for operation in operations:
        backed |= operation_acts(operation) or frozenset()
    allowed = {fold(item) for item in backed}
    for words, lemmas in attempts:
        if lemmas and not any(fold(lemma) in allowed for lemma in lemmas):
            return words
    return ""


# ---------------------------------------------------------------- the book: acts an operation backs
@lru_cache(maxsize=512)
def operation_acts(operation: str) -> frozenset[str] | None:
    """The lemmas a verified ``operation`` can state, or None when no data names the operation (not judged)."""

    entry = _floor_operations().get(operation)
    declared = data()["operationActs"].get(operation)
    exact = data()["exactActs"].get(operation) if operation != "source" else None
    if entry is None and declared is None and exact is None:
        return None
    own: set[str] = set(declared or ())
    if entry is not None:
        variants = entry.get("variants") or {}
        # Review of cu-v3-documento-nuevo (finding 1): a variant keyed by an observed fact of ``factActs`` (app.open
        # «newDocument» -> crear) is an act of its own, backed only when the step observed it (``observed_acts``):
        # every verified opening backing «crear» let «Abrí OBS; la escena quedó creada» through.
        if variants.get("key") in data()["factActs"]:
            variants = {}
        variants = variants.get("values") or {}
        for clause in (entry["es"][0], *(variant["es"][0] for variant in variants.values())):
            own.add(_infinitive(clause.split()[0]))
    groups = data()["groups"]
    # exactActs (review r2 finding 4): lemmas backed as they are, never widened by groups.
    return frozenset(own | {other for lemma in own for other in groups.get(lemma, ())} | set(exact or ()))


def neutral_acts() -> frozenset[str]:
    return frozenset(data()["neutral"])


def weak_proof(satisfied_by: object) -> bool:
    """A mission's arrival that proves no act: none, the model's own cited evidence, an alternative, or one marked as
    reached through a name picked by resemblance (``weakAtoms``, review r10a finding 5)."""

    return (
        not isinstance(satisfied_by, str)
        or not satisfied_by.strip()
        or satisfied_by in data()["weakProof"]
        or "|" in satisfied_by
        or any(atom.split(":", 1)[0].strip().casefold() in data()["weakAtoms"] for atom in satisfied_by.split("&"))
    )


_NEGATION_BEFORE = re.compile(r"\b(?:no|nunca|jamas|aun\s+no|todavia\s+no)\s+(?:(?:me|te|se|lo|la|los|las|le|les)\s+)*$")


def denied_acts(text: object) -> frozenset[str]:
    """The acts the reply says were not done, in the first person past («no puse los bunkers», «no lo cerré») or the
    reflexive passive («no se pusieron», «no se cerró»): their lemmas. Uso real t2-r4 c01-1: three honest finals of a
    play stopped by the person («No puse los bunkers en Spotify porque…», «No se pusieron…») died wanting «no pude».
    Only a plain negation denies: a supposition («no sé si se puso») and «sin» tell nothing done or not."""

    preterites = _preterites()
    third = _third_preterites()
    denied: set[str] = set()
    for sentence in _sentences(text):
        lowered = sentence.casefold()
        for match in _WORD.finditer(lowered):
            lemma = preterites.get(match.group(0))
            if lemma and _negated(lowered[: match.start()]):
                denied.add(lemma)
        for match in _REFLEXIVE_PASSIVE.finditer(lowered):
            lemma = third.get(fold(match.group("verb")))
            if lemma and _negated(lowered[: match.start()]):
                denied.add(lemma)
    return frozenset(denied)


def _negated(before: str) -> bool:
    clause = _CLAUSE_SPLIT.split(fold(before) + " ")[-1]
    return _NEGATION_BEFORE.search(clause) is not None


def unbacked_act(text: object, backed: Iterable[str], third_person: bool = True, own_stop: bool = False) -> str:
    """The first act the reply tells that no lemma in ``backed`` stands for, or "". ``own_stop``: the turn observed its
    own stop (``observed_stop``), so a stop told of BAXY's own work is no act (``claimed_acts``)."""

    allowed = {fold(item) for item in backed}
    for word, lemmas in claimed_acts(text, third_person, own_stop):
        if not any(fold(lemma) in allowed for lemma in lemmas):
            return word
    return ""


# ---------------------------------------------------------------- the object of an act told (ronda 19)
def _object_words(clause: str) -> list[str]:
    rule = data()["screenObject"]
    return [
        word for word in re.findall(r"[a-z]+|\d+", clause)
        if word.isdigit() or len(word) >= rule["minLength"]
    ]


def _object_of(clause: str) -> str:
    """Revisión r19 (bloqueante d): the clause after an act up to where its place or manner begins
    (``screenObject.placeEnds``): «programmer in the calculator window» → «programmer», «a pantalla en 2 pasos» →
    «a pantalla». A lead first in the clause («clicked on Decimal») is the verb's own, not a place."""

    leads = data()["screenObject"]["placeEnds"]["leads"]
    pattern = "|".join(
        r"\s+".join(re.escape(word) for word in item.split()) for item in sorted(leads, key=len, reverse=True)
    )
    for match in re.finditer(rf"\b(?:{pattern})\b", clause):
        if re.search(r"[a-z0-9]", clause[:match.start()]):
            return clause[:match.start()]
    return clause


def screen_seen(observed: object) -> str:
    """Revisión r19 (bloqueante d): what a computer-use result saw, folded: its values only, never the facts' keys nor
    the window's identity (``screenObject.identity.keys``: its process, its title), which name the app and not a value
    an act could only have seen."""

    skip = set(data()["screenObject"]["identity"]["keys"])
    values: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key not in skip:
                    walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)
        elif value is not None and not isinstance(value, bool):
            values.append(str(value))

    walk(observed)
    return fold(" | ".join(values))


def _held_by(word: str, folded: str) -> bool:
    """The word stands in the folded facts: whole, or as the stem of a longer word there («pincel» / «pinceles»)."""

    if word.isdigit():
        return re.search(rf"(?<!\d){word}(?!\d)", folded) is not None
    return re.search(rf"\b{re.escape(word)}", folded) is not None


def _sentences_with_names(text: object) -> list[str]:
    """Revisión r19 (bloqueante 6): the reply's sentences that report, as ``_sentences`` gives them but with their
    quoted names kept (a full stop inside a quote does not end the sentence), so the object of an act can be a name
    the reply quotes."""

    unquoted_ends = r"(?:«[^»]*»|“[^”]*”|\"[^\"]*\"|[^.!?\n])+[.!?\n]*"
    return [
        part for part in re.findall(unquoted_ends, str(text or "").replace("’", "'"))
        if part.strip() and "?" not in _QUOTED.sub(" ", part) and "¿" not in _QUOTED.sub(" ", part)
    ]


def _named_words(sentence: str) -> set[str]:
    """Revisión r19 (bloqueante 6): the words a sentence gives as names, folded: capitalised past its first word
    («elegí el modo Decimal», «I selected Decimal mode»), outside quotes."""

    tokens = re.findall(r"[^\W\d_]+", _QUOTED.sub(" ", sentence))
    return {fold(token) for token in tokens[1:] if token[0].isupper() and len(token) > 1}


def screen_only_object(text: object, done: str, seen: str) -> str:
    """Ronda 19 (r17 t3-c18/2 «…y elegí el modo Decimal», t3-c19/3 «…y ahora el pincel está listo», t2-c04 «He cambiado
    la escala a 125…»): the first word of what an act told in the first person acts on (up to the end of its clause,
    or to where its place begins: revisión r19), or of a thing told as ready (``screenObject.ready``), that the steps
    done and the goal (``done``, folded) do not hold while the screen does (``seen``, folded: ``screen_seen``) — or a
    number neither holds. "" when every object is backed. A question tells nothing; what the screen shows said as such
    («quedó en Decimal») tells no act. Ronda 24 (pasada r23, v3-62 «I found the active network is Red privada»; r23
    t3-c09 «Vi que los SLEVE EVO están emparejados»): an act of observing (``screenObject.observing``: ver, leer,
    encontrar, comprobar…, and ``screenObject.looks.lemmas``) that tells a state acts on nothing; what it names is what
    the screen shows, never an object only the screen backs. With a direct object and no state («Vi el modo Decimal»)
    its object stays judged, and a later act that takes it up («…y lo elegí») acts on it."""

    rule = data()["screenObject"]
    observing = {fold(item) for item in rule["observing"]["words"]}
    ready = "|".join(r"\s+".join(re.escape(word) for word in item.split()) for item in rule["ready"])
    articles = "|".join(re.escape(item) for item in rule["articles"])
    positional = set(rule["positional"]["words"])
    for sentence in _sentences_with_names(text):
        folded = fold(sentence)
        names = _named_words(sentence)
        clauses: list[str] = []
        looks = rule["looks"]
        looked: list[str] = []
        for word, lemmas in claimed_acts(sentence, third_person=False):
            start = folded.find(fold(word))
            if start < 0:
                continue
            rest = folded[start + len(fold(word)):]
            clause = _object_of(_CLAUSE_SPLIT.split(rest + " ")[0])
            before = re.findall(r"[a-z]+", folded[:start])[-1:]
            after = re.findall(r"[a-z]+", rest)[:1]
            if (lemmas and lemmas <= set(looks["lemmas"])) or fold(word) in observing or (
                {fold(lemma) for lemma in lemmas} & observing
            ):
                # Ronda 24 (r23 t3-c09 «vi que los SLEVE EVO están emparejados»; pasada r23 v3-62 «I found the active
                # network is Red privada»): a look that tells a state acts on nothing; what it saw is the screen's, said
                # as such. Revisión 1 de r24 (bloqueante 1): only that look — after a state lead («que», «that») or with
                # a verb of state in its clause (``looks.stateVerbs``) — («vi el modo Decimal…» keeps its object), and
                # what it saw stays for a later act that takes it up.
                looked.append(_CLAUSE_SPLIT.split(rest + " ")[0])
                if after and after[0] in looks["stateLeads"]:
                    continue
                if set(re.findall(r"[a-z]+", _CLAUSE_SPLIT.split(rest + " ")[0])) & set(looks["stateVerbs"]):
                    continue
            elif looked and set(before + after) & set(looks["clitics"]):
                # «Vi el modo Decimal en el Programador y lo elegí.»: «lo» is what the look saw.
                clauses.append(_object_of(looked[-1]))
            clauses.append(clause)
        for match in re.finditer(rf"\b(?:{articles})\s+(?P<thing>[a-z]+)\s+(?:{ready})\b", folded):
            clauses.append(match.group("thing"))
        for clause in clauses:
            if re.search(r"[«“\"]", clause):
                # Revisión r19 (bloqueante 6): «abrí el video «Gatos graciosos 2024»» acts on the quoted name; the
                # word before it says its kind, which the screen may show anywhere («Reproducir video»).
                continue
            words = _object_words(clause)
            if any(word in names for word in words):
                # The name the reply gives («el modo Decimal», «Decimal mode») is the object, not its kind.
                words = [word for word in words if word in names or word.isdigit()]
            elif positional & set(re.findall(r"[a-z]+", clause)):
                # «abrí el primer video» acts on a place in a list, not on a value only the screen shows.
                words = [word for word in words if word.isdigit()]
            for word in words:
                if _held_by(word, done):
                    continue
                if word.isdigit():
                    if not _held_by(word, seen):
                        return word
                elif _held_by(word, seen):
                    return word
    return ""


# ---------------------------------------------------------------- places the reply names
_PATH = re.compile(r"(?<![\w:/\\.])(?:[a-z]:[\\/])?[\w.\-]+(?:[\\/][\w.\-]+)+", re.IGNORECASE)
_URL = re.compile(r"\bhttps?://\S+|\bwww\.\S+|\b[\w-]+\.(?:com|org|net|cl|es|io|tv|app|ai|dev)\b/\S*", re.IGNORECASE)


def _path_shaped(parts: list[str], rooted: bool) -> bool:
    """A drive-rooted path, or parts a path has: none of a single character and one with a word («baxy-prueba-v3»);
    a unit («µg/m³», «km/h») or «y/o» is not a place."""

    shape = data()["pathShape"]
    if rooted:
        return True
    word = re.compile(r"[^\W\d_]{%d,}" % shape["wordMinimum"])
    return all(len(part) >= shape["segmentMinimum"] for part in parts) and any(word.search(part) for part in parts)


def named_places(text: object) -> list[str]:
    """The paths («Documentos/baxy-prueba-v3/nota.txt») and folders named after «carpeta»/«folder» the reply says,
    each as its parts: what must have been observed for the reply to say the thing is there."""

    raw = _URL.sub(" ", str(text or ""))
    places: list[str] = []
    for match in _PATH.finditer(raw):
        parts = [
            part.rstrip(".") for part in re.split(r"[\\/]", match.group(0)) if part and not part.endswith(":")
        ]
        if len(parts) >= data()["pathSegmentMinimum"] and _path_shaped(parts, bool(match.group(0)[1:3] in {":\\", ":/"})):
            places.extend(parts)
    words = "|".join(re.escape(item) for items in data()["folderWords"].values() for item in items)
    for match in re.finditer(
        rf"\b(?:{words})\s+(?:de\s+|called\s+|named\s+)?(?:«(?P<quoted>[^»]+)»|(?P<bare>[\w.\-]*[\-_.\d][\w.\-]*))",
        raw,
        re.IGNORECASE,
    ):
        bare = (match.group("bare") or "").rstrip(".")
        if match.group("quoted") or re.search(r"[\-_.\d]", bare):
            places.append(match.group("quoted") or bare)
    return [place.strip() for place in places if place and place.strip()]


# ---------------------------------------------------------------- the machine's state in a reply that read nothing
@lru_cache(maxsize=1)
def _machine_patterns() -> tuple[re.Pattern[str], re.Pattern[str]]:
    words = data()["machineState"]
    return (
        re.compile(r"\b(?:" + "|".join(words["anchors"]) + r")\b"),
        re.compile(r"\b(?:" + "|".join(words["claims"]) + r")\b"),
    )


@lru_cache(maxsize=1)
def _machine_help() -> tuple[re.Pattern[str], re.Pattern[str]]:
    words = data()["machineState"]["notClaims"]
    return (
        re.compile(r"\b(?:" + "|".join(words["obligations"]) + r")\b"),
        re.compile(r"^\s*(?:(?:y|pero|and|but|o|or)\s+)?(?:" + "|".join(words["conditionals"]) + r")\b"),
    )


def claims_machine_state(text: object) -> str:
    """A sentence that states how this PC is (or what it lacks) — «En la configuración actual de seguridad de Windows
    no hay un registro…» — anchored to the person's machine. A reply that read nothing cannot say it. Help is not a
    state: an obligation («en tu PC hay que abrir…», «you have to…») says what to do, and a conditional clause («si en
    tu equipo no aparece la opción, …») supposes, so both are left out. Returns the sentence, or ""."""

    anchor, claim = _machine_patterns()
    obligation, conditional = _machine_help()
    for sentence in _sentences(text):
        clauses = [
            obligation.sub(" ", clause)
            for clause in re.split(r"[,;:]", fold(sentence))
            if conditional.search(clause) is None
        ]
        folded = " ".join(clauses)
        if anchor.search(folded) is not None and claim.search(folded) is not None:
            return sentence.strip()
    return ""


# ---------------------------------------------------------------- the service where something was put on
def service_operations() -> frozenset[str]:
    return frozenset(data()["servicePlace"]["operations"])


def service_of(operation: object, provider: object) -> str:
    """The service a play result names: its observed provider, else the one its operation always plays in."""

    return service_name(provider) or service_name(data()["servicePlace"]["operationService"].get(str(operation or "")))


def service_name(provider: object) -> str:
    """How the service of ``seen.provider`` is written («youtube» -> «YouTube», «spotify» -> «Spotify»), or ""."""

    key = fold(provider)
    if not key or re.fullmatch(r"[a-z0-9+]+", key) is None:
        return ""
    return data()["servicePlace"]["names"].get(key) or key[:1].upper() + key[1:]


def service_place(provider: object, english: bool) -> str:
    """« en YouTube» / « on Spotify», or "" when there is no service to name."""

    name = service_name(provider)
    return data()["servicePlace"]["en" if english else "es"].format(service=name) if name else ""


def unmatched_play(operation: object, observed: object) -> str:
    """Revisión 1 r24u (bloqueante 1, t2-c01 «Fother Muckers» told as «los bunkers»): the query of a verified play
    whose receipt says what plays was not shown to be what the query asked for (``matchesQuery`` false), or "". The
    field absent (an older script, the exact mode) or true says nothing here (data: act_claims ``unmatchedPlay``)."""

    rule = data()["unmatchedPlay"]
    if str(operation or "") not in rule["operations"] or not isinstance(observed, dict):
        return ""
    if observed.get("matchesQuery") is not False:
        return ""
    query = observed.get("query")
    return query.strip() if isinstance(query, str) else ""


def unmatched_play_clause(query: str, english: bool) -> str:
    """The clause said beside what plays when it was not shown to be ``query`` («; no comprobé que sea «los
    bunkers»»), or "" without a query."""

    query = str(query or "").replace("«", "").replace("»", "").strip()
    return data()["unmatchedPlay"]["en" if english else "es"].format(query=query) if query else ""


def tells_unmatched_play(text: object) -> bool:
    """A reply over an unmatched play says, in either language, that it was not checked to be what was asked (the
    mark of ``unmatchedPlay``), so it cannot be read as the request done."""

    folded = " " + re.sub(r"[^a-z0-9]+", " ", fold(text)) + " "
    return any(f" {mark} " in folded for mark in data()["unmatchedPlay"]["mark"].values())


def names_the_service(text: object, provider: object) -> bool:
    """The reply names the service (spaces and case aside: «You Tube», «youtube»)."""

    key = re.sub(r"[^a-z0-9+]", "", fold(provider))
    return not key or key in re.sub(r"[^a-z0-9+]", "", fold(text))


def template_suffices(defect: str, operation: object = "") -> bool:
    """A draft refused for this defect is not worded again when the turn's template says the result: the template
    already names what was missing. The book's own defects always; the name and state ones only for what plays (uso
    real tanda 1: three drafts died on missing_name before «Está en pausa …»), so the other reads keep their own
    repairs (inventory, scope limit, last resort)."""

    rule = data()["templateSuffices"]
    return defect in rule["defects"] or (
        defect in rule["namedDefects"] and str(operation or "") in rule["namedOperations"]
    )


def observed_acts(operation: str, observed: object) -> frozenset[str]:
    """The acts a verified ``operation`` backs for what it observed: its variant by ``observedActs`` (browser.control
    «close_all» -> cerrar) and each true fact of ``factActs`` (clientOpened -> abrir), each widened by its groups."""

    if not isinstance(observed, dict):
        return frozenset()
    own: set[str] = set()
    variant = data()["observedActs"].get(operation)
    if isinstance(variant, dict):
        value = str(observed.get(variant["key"]) or "")
        own.update(variant["values"].get(value, ()))
        qualifier = variant.get("qualifier")
        if qualifier and observed.get(qualifier):
            # Review r10a finding 4: Enter backs «enviar» only towards a message composer («enter/message_composer»).
            own.update(variant["values"].get(value + "/" + str(observed.get(qualifier)), ()))
    if operation in data()["labelActs"]["operations"]:
        own.update(label_acts(observed.get("label") or observed.get("name")))
    for fact, lemmas in data()["factActs"].items():
        if fact != "source" and observed.get(fact) is True:
            own.update(lemmas)
    groups = data()["groups"]
    return frozenset(own | {other for lemma in own for other in groups.get(lemma, ())})


def unreached_qualified_acts(observed: object) -> frozenset[str]:
    """Ronda 24b (banco r23 c6: «lo envié» over an Enter that fell on the search holding the text): the acts a key backs
    only by where it was aimed (``observedActs`` «tecla/target»: Enter towards a message box backs «enviar») that a
    sub-goal of the mission naming that act did not reach (its check, ``sent:``, saw nothing sent). A step aimed there
    no longer backs them: the screen said otherwise. Widened by their groups; empty when no such sub-goal failed."""

    if not isinstance(observed, dict):
        return frozenset()
    qualified: set[str] = set()
    for variant in data()["observedActs"].values():
        if isinstance(variant, dict) and variant.get("qualifier"):
            for key, lemmas in variant["values"].items():
                if "/" in key:
                    qualified.update(lemmas)
    parts = [part for part in observed.get("subgoals") or () if isinstance(part, dict)] or [observed]
    unreached: set[str] = set()
    for part in parts:
        if part.get("reached") is not True:
            unreached |= goal_acts(part.get("goal")) & qualified
    groups = data()["groups"]
    return frozenset(unreached | {other for lemma in unreached for other in groups.get(lemma, ())})


def held_state_acts(observed: object) -> frozenset[str]:
    """Ronda 22 (r18 t4-c07, t1-c13 «Creé la carpeta» over a folder that existed): the acts a verified mutation does
    not back when its receipt found the state already there (``heldState.facts`` true: reachedState, alreadyInState),
    each widened by its groups; empty when the receipt changed something."""

    held = data()["heldState"]
    if not isinstance(observed, dict) or not any(observed.get(fact) is True for fact in held["facts"]):
        return frozenset()
    groups = data()["groups"]
    own = set(held["acts"])
    return frozenset(own | {other for lemma in own for other in groups.get(lemma, ())})


def label_acts(label: object) -> frozenset[str]:
    """The acts the label of a pressed control says (review r10a finding 4): each word of it that is a verb the book
    knows in the infinitive («Guardar», «Cerrar sesión»), and the whole label or a word of it listed in
    ``labelActs.words`` («Save», «=»). A label that names no act («Biblioteca», «Pantalla») backs none."""

    folded = " ".join(fold(str(label or "")).split())
    if not folded:
        return frozenset()
    words = data()["labelActs"]["words"]
    known = _known_folded()
    own = {words[folded]} if folded in words else set()
    for word in re.findall(r"[a-z0-9]+|[^\sa-z0-9]", folded):
        if word in known:
            own.add(known[word])
        elif word in words:
            own.add(words[word])
    return frozenset(own)


def goal_acts(goal: object) -> frozenset[str]:
    """The act a mission's goal names by its leading verb («crear una escena» -> crear, «turn on wifi» -> encender),
    widened by its groups: what a strong arrival at that goal backs besides its steps (review r10a, finding 4)."""

    words = fold(str(goal or "")).split()
    if not words:
        return frozenset()
    named = data()["labelActs"]["words"]
    known = _known_folded()
    lemma = (
        named.get(" ".join(words[:2])) or known.get(_infinitive(words[0])) or known.get(words[0]) or named.get(words[0])
    )
    if not lemma:
        return frozenset()
    return frozenset({lemma, *data()["groups"].get(lemma, ())})


def acts_only_neutral(acts: Iterable[str]) -> bool:
    """Every act is one that changes nothing (a read): such a turn is judged by the read-only check instead."""

    return set(acts) <= set(neutral_acts())


# Semilla fix2 (2026-10-08): after a Google search was opened and nothing read it, «No hay películas de suspenso del
# 2026 disponibles en Google porque aún no se han estrenado.» and «…y el resultado confirma que aún no hay películas
# disponibles…». What a page or its results hold, show or confirm is told only from a read of it. Read on the folded
# reply (no accents), quoted words aside.
_PAGE_CONTENT = re.compile(
    r"\b(?:hay|habia|existen?|existia|existian)\b"
    r"|\b(?:aparecen?|aparecia|aparecian|figuran?|se\s+muestran?|mostraba|mostraban)\b"
    r"|\b(?:encontre|encontramos|encontro|encontraron|se\s+encuentran?)\b"
    r"|\b(?:resultados?|pagina|busqueda)\b[^.;]{0,40}\b(?:confirman?|indican?|dicen?|muestran?|senalan?)\b"
    r"|\b(?:confirman?|indican?|segun)\b[^.;]{0,40}\b(?:resultados?|pagina|busqueda)\b"
    r"|\bdisponibles?\b|\bestrenad[oa]s?\b|\bse\s+han\s+estrenado\b"
    r"|\bthere\s+(?:is|are|were|was)\b|\bno\s+results?\b|\bresults?\s+(?:show|shows|showed|list|confirm|confirms)\b"
    r"|\b(?:i\s+found|available|released)\b"
)


def tells_page_content(text: object) -> bool:
    """BAXY's reply says what a page or its search results hold (quoted words aside: the query itself is quoted)."""

    folded = fold(_QUOTED.sub(" ", str(text or "")))
    return _PAGE_CONTENT.search(folded) is not None


# ---------------------------------------------------------------- parts and causes a failed mission's final tells
def _content_words(folded: str, minimum: int) -> list[str]:
    function = {fold(word) for word in data()["unreachedParts"]["functionWords"]}
    return [
        word for word in re.findall(r"[a-z0-9]+", folded)
        if word not in function and (len(word) >= minimum or word.isdigit())
    ]


def part_head(goal: object) -> str:
    """The object a part of a mission names: the first content word after its leading verb («ir a editor de la
    imagen…» -> «editor», «ponele un filtro blanco y negro» -> «filtro»), folded; "" when it has none. The verb's
    complement and the control's class (``unreachedParts.controlWords``: «hacer clic en reemplazar todo» ->
    «reemplazar», «pulsá el botón Aceptar» -> «aceptar», «abrí la pestaña Ver» -> «ver») are skipped while a word
    follows them (revisión 2 de r20 P5, bloqueante 1.ii)."""

    rule = data()["unreachedParts"]
    words = fold(str(goal or "")).split()
    content = _content_words(" ".join(words[1:]), int(rule["minimumWord"]))
    control = {fold(word) for word in rule["controlWords"]}
    while len(content) > 1 and content[0] in control:
        content = content[1:]
    return content[0] if content else ""


def _told_span(clause: str) -> str:
    """The part of a clause that tells what was done: up to the first purpose lead («para llegar al editor», «to open
    the editor», ``unreachedParts.purposeLeads`` and «to» + a verb, ``purposeVerbs``) or attempt lead («intenté entrar
    al editor», «I tried to open it», data ``attempts``), whichever comes first. What follows one of them is what the
    act was for or what was only tried, never an act told (revisión 1 de r20 P5, hallazgo 1)."""

    rule = data()["unreachedParts"]
    attempts = data()["attempts"]
    leads = [fold(lead).split() for lead in [*rule["purposeLeads"], *attempts["es"], *attempts["en"]]]
    verbs = {fold(verb) for verb in rule["purposeVerbs"]} | set(_english_bases())
    words = [(match.start(), fold(match.group(0))) for match in re.finditer(r"[^\W_]+(?:'[^\W_]+)?", clause)]
    folded = [word for _, word in words]
    for index, (start, word) in enumerate(words):
        if word == "to" and index + 1 < len(folded) and folded[index + 1] in verbs:
            return clause[:start]
        if any(lead and folded[index: index + len(lead)] == lead for lead in leads):
            return clause[:start]
    return clause


def claims_unreached_part(text: object, goal: object, backers: Iterable[object] = ()) -> str:
    """Ronda 20 P5 (pasada r18 v3-16, «Llegué al editor de la imagen pero no pude poner el filtro…» over the part «ir a
    editor de la imagen…» not reached): the clause of the reply that tells, in the first person past (claimed_acts with
    no third person), an act over the object a part not reached names, or "". Only what the clause tells as done counts
    (``_told_span``): the object of a purpose («Hice clic en «Editar» para llegar al editor») or of an attempt («Intenté
    entrar al editor») is no claim. A backer (a verified step's label, a reached part's goal) that names that object
    backs the clause: the act may be told of it. Quotes count for the object («Llegué a «Filtros»») but never for the
    act; a question tells nothing."""

    head = part_head(goal)
    if not head:
        return ""
    named = re.compile(rf"\b{re.escape(head)}\b")
    if any(named.search(fold(str(backer or ""))) for backer in backers):
        return ""
    causes = "|".join(re.escape(lead).replace(r"\ ", r"\s+") for lead in data()["toldCauses"]["leads"])
    split = re.compile(rf"{data()['unreachedParts']['clauseSplit']}|\b(?:{causes})\b")
    for sentence in re.findall(r"[^.!?\n]+[.!?\n]*", str(text or "").replace("’", "'")):
        if "?" in sentence or "¿" in sentence:
            continue
        for clause in split.split(_QUOTED.sub(lambda quoted: quoted.group(0).replace(",", " "), sentence.casefold())):
            told = _told_span(clause)
            if told.strip() and _act_over(told, claimed_acts(told, third_person=False), named):
                return clause.strip()
    return ""


def search_told_as_place(text: object, fields: Iterable[object] = ()) -> str:
    """Revisión 1 de r24b (B3, banco r23 x7 «Ya estamos en la pestaña de búsqueda de Spotify» over a click on «Buscar»
    that only brought the keyboard to a field): the clause of the reply that tells, in the first or second person, that
    BAXY or the person is in, got to or went to the search (``searchToldAsPlace.arrival``), its object up to the end of
    the clause or ``objectEnd`` naming the search (``objects``) or one of ``fields`` (the label of a focus atom); "" when
    none does. «se abrió la búsqueda y el cursor está en …», the template's own words, tells no place; a question tells
    nothing. Revisión 2 de r24b (B1): a quotation is the window's words, not the reply's: its «?» («¿Qué quieres
    reproducir?») neither ends a sentence, nor splits a clause, nor makes it a question; a field's own signs are read
    as blanks in its name and in its quotation alike."""

    rule = data()["searchToldAsPlace"]
    # The signs inside a quotation (and inside a name) are its own: they never split the clause.
    unsigned = re.compile(r"[.;:!?,¿¡]")
    names = [name for name in (fold(unsigned.sub(" ", str(raw))) for raw in (*rule["objects"], *fields)) if name]
    if not names:
        return ""
    named = re.compile(r"(?<![^\W_])(?:" + "|".join(re.escape(name) for name in names) + r")(?![^\W_])")
    arrival = re.compile(rule["arrival"])
    end = re.compile(rule["objectEnd"])
    split = re.compile(data()["unreachedParts"]["clauseSplit"])
    said = str(text or "").replace("’", "'")
    # The sentences are cut on the reply with its quotations blanked (same length) and read on the reply itself.
    blanked = _QUOTED.sub(lambda quoted: " " * len(quoted.group(0)), said)
    for bounds in re.finditer(r"[^.!?\n]+[.!?\n]*", blanked):
        if "?" in bounds.group(0) or "¿" in bounds.group(0):
            continue
        sentence = said[bounds.start():bounds.end()]
        folded = fold(_QUOTED.sub(lambda quoted: unsigned.sub(" ", quoted.group(0)), sentence))
        for clause in split.split(folded):
            for found in arrival.finditer(clause):
                tail = end.split(clause[found.end():], maxsplit=1)[0]
                if named.search(tail):
                    return clause.strip()
    return ""


def _act_over(told: str, acts: list[tuple[str, frozenset[str]]], named: re.Pattern) -> bool:
    """Whether one of ``acts`` (claimed_acts of ``told``) is told over the object ``named``: the object follows the
    act's word with no denial (``unreachedParts.denials``) between them. «No pude hacer clic en la pestaña Transiciones»
    with a «hice» after it tells no act over «transiciones»; «Entré en Colores y puse el tema oscuro» tells «puse» over
    «tema» (revisión 2 de r20 P5, bloqueante 1.i). The cause after a lead (``toldCauses.leads``) is a clause of its
    own (claims_unreached_part)."""

    denials = {fold(word) for word in data()["unreachedParts"]["denials"]}
    masked = _QUOTED.sub(lambda quoted: " " * len(quoted.group(0)), told)
    for word, _ in acts:
        found = re.search(rf"(?<![^\W_]){re.escape(word)}(?![^\W_])", masked)
        tail = fold(told[found.end() if found else 0:])
        hit = named.search(tail)
        if hit and not any(token in denials for token in re.findall(r"[a-z0-9']+", tail[: hit.start()])):
            return True
    return False


def told_causes(text: object) -> list[str]:
    """The causes a reply gives after one of ``toldCauses.leads`` («…porque la pantalla se quedó bloqueada»), folded,
    each up to the end of its clause (``unreachedParts.clauseSplit``, as claims_unreached_part reads it: what follows a
    comma or «aunque» is another thing, revisión 3 de r20 P5, bloqueante 2); a leading split with nothing before it
    («porque, al final, …») is skipped."""

    leads = "|".join(re.escape(fold(lead)).replace(r"\ ", r"\s+") for lead in data()["toldCauses"]["leads"])
    split = re.compile(data()["unreachedParts"]["clauseSplit"])
    folded = fold(_QUOTED.sub(" ", str(text or "").replace("’", "'")))
    causes: list[str] = []
    for found in re.finditer(rf"\b(?:{leads})\b(?=([^.;!?]*))", folded):
        cause = next((segment.strip() for segment in split.split(found.group(1)) if segment and segment.strip()), "")
        if cause:
            causes.append(cause)
    return causes


def stop_families(stop: object) -> frozenset[str]:
    """The kinds of cause (``toldCauses.families``) the observed cause of a stop is, by its code (stoppedBy, or the key
    of a refined cause): data ``toldCauses.stopFamilies``. Telling that cause with the words of its kind invents
    nothing, whatever words the stop's own text uses (revisión 3 de r20 P5, bloqueante 1: «…porque tardó demasiado» on
    computer_use_time_exhausted, «se agotó el tiempo previsto»)."""

    return frozenset(data()["toldCauses"]["stopFamilies"].get(str(stop or ""), ()))


def _family_told(cause: str, name: str, family: re.Pattern) -> bool:
    """Whether ``cause`` says the kind ``family``: a match not denied. A match denied by a word of
    ``unreachedParts.denials`` or ``toldCauses.denials`` at most ``denialReach`` words before it, with no
    ``denialScopeEnds`` between them («aunque no apareció ningún error», «sin ningún error en la pantalla»), says the
    kind is absent; a kind of ``negatedFamilies`` («no había internet», «sin permisos») is told even denied."""

    rule = data()["toldCauses"]
    if name in rule["negatedFamilies"]:
        return family.search(cause) is not None
    denials = {fold(word) for word in [*data()["unreachedParts"]["denials"], *rule["denials"]]}
    ends = {fold(word) for word in rule["denialScopeEnds"]}
    reach = int(rule["denialReach"])
    for hit in family.finditer(cause):
        before = re.findall(r"[a-z0-9']+", cause[: hit.start()])[-reach:]
        scope = before[max((index + 1 for index, word in enumerate(before) if word in ends), default=0):]
        if not any(word in denials for word in scope):
            return True
    return False


def invented_cause(text: object, facts: Iterable[object], stops: Iterable[object] = ()) -> str:
    """Ronda 20 P5 (pasada r18 v3-16, «…porque la pantalla se quedó bloqueada» over a stop on no visible step): the
    first cause the reply gives (told_causes) that says a kind of cause (``toldCauses.families``: a locked screen, a
    frozen application, a covering window, a permission, the network, an error, a sign-in, an update, a wait) that no
    fact of the mission says, or "". A cause of no known kind is no invention: a light rewording of the observed one
    («no vi ningún control para continuar», «I didn't find a control to continue») passes (revisión 1, hallazgo 2).
    The kinds of the stop's own cause (``stops``: its codes, stop_families) are known whatever the facts' words
    (revisión 3, bloqueante 1), and a kind the cause denies is not told (_family_told, bloqueante 2)."""

    families = {name: re.compile(pattern) for name, pattern in data()["toldCauses"]["families"].items()}
    known = " | ".join(fold(str(fact or "")) for fact in facts)
    own = frozenset().union(*(stop_families(stop) for stop in stops))
    for cause in told_causes(text):
        if any(
            name not in own and _family_told(cause, name, family) and not family.search(known)
            for name, family in families.items()
        ):
            return cause
    return ""


def _attempt_words() -> frozenset[str]:
    """The word of each attempt lead (data ``attempts``, folded) that claimed_acts reads as an act («intenté», «I
    tried», «he intentado»): its longest word. An attempt opens no scope of its own (revisión 3 de la ronda 20b,
    bloqueante 2): what follows it was only tried."""

    attempts = data()["attempts"]
    return frozenset(max(fold(lead).split(), key=len) for lead in [*attempts["es"], *attempts["en"]] if lead.strip())


def _phrases(words: Iterable[str]) -> re.Pattern[str] | None:
    """A pattern for any of ``words`` (folded), each a whole word or words."""

    folded = [fold(word) for word in words if str(word).strip()]
    if not folded:
        return None
    return re.compile(
        r"(?<![^\W_])(?:" + "|".join(re.escape(word).replace(r"\ ", r"\s+") for word in folded) + r")(?![^\W_])")


def _denial_scope(said: str, clause: str, figure_at: int) -> int:
    """Where the denials that may deny a figure at ``figure_at`` of ``clause`` (folded, quotes masked; ``said``: the same
    span as written, for the acts) start (revisión
    2 de la ronda 20b, bloqueante 3: «No dibujé el rectángulo y dejé el lienzo en 500 por 500» denied the 500 with the
    denial of another act). A denial denies the figure only between the last act told in the first person before it
    (``claimed_acts`` with no third person: the criterion of r20 P5, ``_act_over``; an attempt, ``_attempt_words``, is
    no such act) and the figure; a coordination (``unsustainedFigures.coordination``) whose conjunct before the figure
    is no ellipsis starts a scope of its own («y el lienzo quedó en…», «y el lienzo está en…», «and the canvas is…»),
    while an elliptical one («…ni el alto en 600», «no pude poner el ancho en 800 y el alto en 600») keeps the denial
    before it. A conjunct is elliptical when, as written (accents kept, no minimum length), it says one word only that
    is no function word (revisión 3, bloqueante 3: «está» is no «esta», «is» is a word)."""

    rule = data()["unsustainedFigures"]
    function = {fold(word) for word in data()["unreachedParts"]["functionWords"]}
    attempts = _attempt_words()
    start = 0
    before = clause[:figure_at]
    written = fold_in_place(said[:figure_at])
    for word, _ in claimed_acts(said[:figure_at], third_person=False):
        if fold(word).split()[-1] in attempts:
            continue
        for found in re.finditer(rf"(?<![^\W_]){re.escape(fold_in_place(word))}(?![^\W_])", written):
            start = max(start, found.end())
    joins = "|".join(re.escape(fold(word)) for word in rule["coordination"])
    for found in re.finditer(rf"\b(?:{joins})\b", before):
        conjunct = [
            word for word in re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", said[found.end():figure_at].casefold())
            if word not in function
        ]
        if len(conjunct) > 1:
            start = max(start, found.end())
    return start


def _asserted_statements(text: object) -> list[list[str]]:
    """The figures (``unsustainedFigures.figure``, folded) the reply asserts, grouped by the clause that says them
    (``unreachedParts.clauseSplit``, a cause after one of ``toldCauses.leads`` is a clause of its own): outside quotes,
    and not denied in their own clause. A figure is denied by a denial (``unreachedParts.denials``,
    ``unsustainedFigures.denials``), an attempt lead (data ``attempts``) or a request lead
    (``unsustainedFigures.requests``) within its scope (``_denial_scope``: after the last act told before it, or the
    coordination that starts another statement), or by a denial of the verb (``afterDenials``) among the
    ``afterWindow`` words that follow it when no act in the first person precedes it in its clause. «…pero no pude
    dejar el alto en 600», «I couldn't set it to 600», «No pude escribir 2026» assert no 600 nor 2026 (revisión 1 de
    la ronda 20b, bloqueante 2); «No dibujé el rectángulo y dejé el lienzo en 500 por 500» asserts both 500 (revisión
    2, bloqueante 3); «Intenté escribir 2026», «I was unable to type 2026», «…en 450 en vez de 600», «Pediste 600 de
    alto», «…pero 2026 no aparece» assert none (revisión 3, bloqueante 2). A decimal separator («12,5») splits no
    clause. One entry per time the clause says the figure."""

    rule = data()["unreachedParts"]
    own = data()["unsustainedFigures"]
    figure = re.compile(own["figure"])
    denials = {fold(word) for word in rule["denials"]}
    attempts = _attempt_words()
    leads = [phrase for phrase in (
        _phrases(own["denials"]), _phrases([*data()["attempts"]["es"], *data()["attempts"]["en"]]),
        _phrases(own["requests"]),
    ) if phrase is not None]
    window = int(own["afterWindow"])
    after_denials = {fold(word) for word in own["afterDenials"]}
    causes = "|".join(re.escape(fold(lead)).replace(r"\ ", r"\s+") for lead in data()["toldCauses"]["leads"])
    split = re.compile(rf"{rule['clauseSplit']}|\b(?:{causes})\b")
    masked = _QUOTED.sub(lambda quoted: " " * len(quoted.group(0)), str(text or "").replace("’", "'"))
    folded = fold_in_place(masked)
    guarded = re.sub(r"(?<=[0-9])[.,](?=[0-9])", "0", folded)
    statements: list[list[str]] = []
    start = 0
    for end in [*(found.start() for found in split.finditer(guarded)), len(folded)]:
        clause = folded[start:end]
        guard = guarded[start:end]
        said = masked[start:end]
        asserted: list[str] = []
        for found in figure.finditer(guard):
            scope = clause[_denial_scope(said, clause, found.start()): found.start()]
            if any(token in denials for token in re.findall(r"[a-z0-9']+", scope)):
                continue
            if any(lead.search(scope) for lead in leads):
                continue
            following = re.findall(r"[a-z0-9']+", clause[found.end():])[:window]
            if any(token in after_denials for token in following) and not [
                word for word, _ in claimed_acts(said[: found.start()], third_person=False)
                if fold(word).split()[-1] not in attempts
            ]:
                continue
            asserted.append(clause[found.start(): found.end()])
        if asserted:
            statements.append(asserted)
        start = end
    return statements


def _asserted_figures(text: object) -> list[str]:
    """Every figure the reply asserts (``_asserted_statements``), one entry per time it says it."""

    return [said for statement in _asserted_statements(text) for said in statement]


def unsustained_figure(
    text: object, parts: Iterable[object], screen: Iterable[object] = (), fields: Iterable[object] = (),
) -> str:
    """Ronda 20b (pasada r18 t-long-3: «I managed to resize the canvas to 500 by 500 pixels» over a canvas left at
    177×500): the first figure the reply asserts (``_asserted_figures``: outside quotes, never denied) that a part of the
    mission asks for more times than the reached parts that say it sustain in the last reading, or "".

    A figure is sustained by a reached part that says it, and by nothing else (revisión 1, bloqueante 1: a number the
    screen shows is no value the mission set). That part sustains it in the last reading: when the reading shows the
    part's field by name (``fields``: its {name, value}, ``cu_tipos.field_names``), only if that field holds it
    (``cu_tipos.value_holds``: «1500» never holds 500); else, a part of a form (``fieldGoal``) whose run was reached
    whole sustains it (the form held as one unit and was accepted) as many times as a pair of the last reading that
    shows one of its figures shows it (``pairShown``, revisión 2, bloqueante 1: a field that recalculates the other when
    the form is accepted leaves «177 x 500px» on the status bar with every part reached), and one whose run was not
    sustains it only as many times as one text of the last reading (``screen``) shows it. «500 by 500» says 500 twice:
    the width reached with the height recalculated, over a status bar «177 x 500px», sustains one. ``parts``: the
    mission's parts in order ({goal, reached})."""

    rule = data()["unsustainedFigures"]
    figure = re.compile(rule["figure"])
    field_goal = re.compile(rule["fieldGoal"])
    listed = [part for part in parts if isinstance(part, dict)]
    runs: list[list[dict]] = []
    for part in listed:
        if field_goal.search(fold(str(part.get("goal") or ""))):
            if runs and runs[-1] and field_goal.search(fold(str(runs[-1][-1].get("goal") or ""))):
                runs[-1].append(part)
                continue
        runs.append([part])
    shown_fields = [
        (fold(str(item.get("name") or "")), fold(str(item.get("value") or "")))
        for item in fields if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    shown_texts = [fold(str(shown or "")) for shown in screen if str(shown or "").strip()]

    def on_screen(said: str) -> int:
        return max((sum(found.group(0) == said for found in figure.finditer(shown)) for shown in shown_texts), default=0)

    pair = re.compile(rule["pairShown"])
    shown_pairs = [
        [fold(found.group(side)) for side in ("first", "second")]
        for shown in shown_texts for found in pair.finditer(shown)
    ]
    asked: set[str] = set()
    tied: dict[str, int] = {}
    untied: dict[str, int] = {}
    for run in runs:
        whole = all(part.get("reached") is True for part in run)
        # Revisión 2 (bloqueante 1): a run reached whole sustains its figures as many times as a pair of the last
        # reading that shows one of them («177 x 500px» after a form of 500 by 500) shows each; no such pair, as many
        # times as its parts say it.
        accepted: dict[str, int] = {}
        for part in run:
            goal = fold(str(part.get("goal") or ""))
            said = [found.group(0) for found in figure.finditer(goal)]
            asked |= set(said)
            if part.get("reached") is not True:
                continue
            field = field_goal.search(goal)
            names = cu_tipos.field_names(field.group("field").strip()) if field and field.group("field") else ()
            values = [value for name, value in shown_fields if any(fold(own) in name for own in names)]
            for figure_said in said:
                if values:
                    if any(cu_tipos.value_holds(value, figure_said) for value in values):
                        tied[figure_said] = tied.get(figure_said, 0) + 1
                elif whole:
                    accepted[figure_said] = accepted.get(figure_said, 0) + 1
                else:
                    untied[figure_said] = untied.get(figure_said, 0) + 1
        said_pairs = [shown for shown in shown_pairs if set(shown) & set(accepted)] if len(run) > 1 else []
        for figure_said, count in accepted.items():
            held = max((shown.count(figure_said) for shown in said_pairs), default=count)
            tied[figure_said] = tied.get(figure_said, 0) + min(count, held)
    # Revisión 3 (bloqueante 1): the times a figure is told are counted within one statement; told again in another
    # («…en 800 y el alto en 600; ahora la imagen mide 800 x 600») it is the same figure, not one more.
    for statement in _asserted_statements(text):
        told: dict[str, int] = {}
        for said in statement:
            if said not in asked:
                continue
            told[said] = told.get(said, 0) + 1
            if told[said] > tied.get(said, 0) + min(untied.get(said, 0), on_screen(said)):
                return said
    return ""
