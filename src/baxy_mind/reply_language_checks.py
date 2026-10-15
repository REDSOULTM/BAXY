"""The form of a visible reply in Spanish and English: invented infinitives, broken plurals, cut words,
first person, case, article agreement, fixed stalls and contract tokens a person would read as broken.
"""

from __future__ import annotations

import json
import re
from typing import Iterable

from . import corrector
from .semantic.normalize import _policy_guard_text
from .semantic.request import fold as _reading_fold
from .semantic.conversation import requested_infinitive_stems
from .semantic.request import words_with_es_plural
from .request_intents import _message_response_language


# "No puedo riega los helechos" and "No puedo hacer pegar el tape" are the two
# shapes a small local model keeps producing after the modal. Spanish needs an
# infinitive there, and the extra "hacer" is redundant except in the idiomatic
# "hacer llegar" and "hacer saber". Measured at 16 of 314 replies across the
# sealed campaigns before this guard, so the turn retries instead of speaking
# broken Spanish.
_MALFORMED_MODAL_COMPLEMENT = re.compile(
    r"\bno\s+puedo\s+"
    r"(?!con\b|mas\b|sin\b|ni\b|que\b|nada\b|todavia\b|aun\b|"
    r"hacer\s+(?:llegar|saber)\b)"
    r"(?P<complement>[a-z]+)\b",
    re.IGNORECASE,
)
_REDUNDANT_MODAL_AUXILIARY = re.compile(
    r"\bno\s+puedo\s+hacer\s+(?!llegar\b|saber\b)[a-z]+(?:ar|er|ir)\b",
    re.IGNORECASE,
)
# "No puedo hacer tiende las sheets" passed under both guards above: the
# redundant-auxiliary rule requires an -ar/-er/-ir ending after "hacer", and
# "tiende" is conjugated, so it has none. What follows "hacer" is either an
# infinitive or a noun phrase; a bare conjugated verb is neither.
#
# The determiners are listed because "no puedo hacer **el riego** de los
# geranios" is correct Spanish and appeared in the same sealed population. A
# rule that only asked for an infinitive would have refused it.
_HACER_WITH_A_CONJUGATED_FORM = re.compile(
    r"\bno\s+puedo\s+hacer\s+"
    r"(?!llegar\b|saber\b)"
    r"(?!(?:el|la|los|las|un|una|unos|unas|mi|mis|tu|tus|su|sus|"
    r"este|esta|estos|estas|ese|esa|esos|esas|aquel|aquella|"
    r"lo|algo|nada|eso|esto|mucho|poco|otro|otra)\b)"
    r"(?P<complement>[a-z]+)\b",
    re.IGNORECASE,
)

# Spanish stem-changing verbs, written as (real infinitive, diphthong stem).
# The model keeps building an infinitive out of the *conjugated* stem: it hears
# "cuece" and writes "cuecer", hears "vierte" and writes "vertir", hears
# "tiende" and writes "tiender". Those end in -ar/-er/-ir like any infinitive,
# which is exactly why the ending check above cannot see them, and why R102
# recorded that only a verb lexicon would close it.
#
# The invented forms are *generated* from this table rather than listed, so
# adding a verb adds its error automatically and the two can never drift. Real
# infinitives that legitimately carry the diphthong -- amueblar, encuadrar,
# encuadernar, adenar -- are unaffected, because nothing is judged by shape:
# only these exact generated strings are refused.
_STEM_CHANGING_VERBS: tuple[tuple[str, str], ...] = (
    ("cocer", "cuec"),
    ("torcer", "tuerc"),
    ("moler", "muel"),
    ("mover", "muev"),
    ("volver", "vuelv"),
    ("morder", "muerd"),
    ("doler", "duel"),
    ("soler", "suel"),
    ("poder", "pued"),
    ("contar", "cuent"),
    ("encontrar", "encuentr"),
    ("recordar", "recuerd"),
    ("acordar", "acuerd"),
    ("colgar", "cuelg"),
    ("rogar", "rueg"),
    ("soltar", "suelt"),
    ("volar", "vuel"),
    ("soñar", "sueñ"),
    ("probar", "prueb"),
    ("aprobar", "aprueb"),
    ("costar", "cuest"),
    ("mostrar", "muestr"),
    ("dormir", "duerm"),
    ("morir", "muer"),
    ("verter", "viert"),
    ("tender", "tiend"),
    ("encender", "enciend"),
    ("perder", "pierd"),
    ("entender", "entiend"),
    ("querer", "quier"),
    ("cerrar", "cierr"),
    ("empezar", "empiez"),
    ("comenzar", "comienz"),
    ("despertar", "despiert"),
    ("sentar", "sient"),
    ("pensar", "piens"),
    ("regar", "rieg"),
    ("negar", "nieg"),
    ("helar", "hiel"),
    ("nevar", "niev"),
    ("temblar", "tiembl"),
    ("quebrar", "quiebr"),
    ("apretar", "apriet"),
    ("calentar", "calient"),
    ("sentir", "sient"),
    ("mentir", "mient"),
    ("preferir", "prefier"),
    ("herir", "hier"),
    ("hervir", "hierv"),
    ("advertir", "adviert"),
    ("convertir", "conviert"),
    ("tener", "tien"),
    ("venir", "vien"),
)


def _invented_infinitives() -> frozenset[str]:
    """Build the infinitives these verbs get wrongly turned into.

    Two mechanisms, both generated rather than listed. The first takes the
    diphthong stem: "cuece" becomes "cuecer". The second keeps the real stem
    and swaps the conjugation class: "verter" becomes "vertir", which the first
    mechanism cannot produce because nothing diphthongises.

    Anything the generators produce that is itself a real infinitive in the
    table is dropped, which is what keeps the pair sentar/sentir intact: both
    exist, and each would otherwise be generated as the other's error.
    """

    real_infinitives = {real for real, _ in _STEM_CHANGING_VERBS}
    endings = ("ar", "er", "ir")
    invented: set[str] = set()
    for real, diphthong in _STEM_CHANGING_VERBS:
        stems = [diphthong]
        if real.endswith(endings):
            stems.append(real[:-2])
        for stem in stems:
            for ending in endings:
                candidate = f"{stem}{ending}"
                if candidate not in real_infinitives:
                    invented.add(candidate)
    return frozenset(invented)


_INVENTED_INFINITIVES = _invented_infinitives()
# Where an infinitive is the only grammatical possibility, so consulting a
# generated lexicon there cannot collide with an ordinary noun or adjective.
_MODAL_COMPLEMENT_POSITION = re.compile(
    r"\b(?:no\s+)?(?:puedo|puedes|puede|podemos|pueden|"
    r"quiero|quieres|quiere|"
    r"voy\s+a|vas\s+a|va\s+a|vamos\s+a|van\s+a|"
    r"deb[eo]|debes|debemos|deben|suelo|sueles|suele|"
    r"para|sin|al|tras)\s+(?P<complement>[a-z]+)\b",
    re.IGNORECASE,
)


# Measured invented tokens that are not infinitives. The ending-based
# guardian never sees them: "Descalzica", "Inflata", "alredad", "cosear".
# This is a closed evidence set, not a vocabulary gate.
_MEASURED_INVENTED_VISIBLE_TOKENS = frozenset(
    {
        "descalzica",
        "inflata",
        "alredad",
        "cosear",
        "motherient",
        "spotifylight",
        "successfullyinished",
        "riagesystem",
        "volumor",
        "creadel",
        "relojillo",
        "abrbio",
        "washas",
        "tiempoempo",
        "silo",
        "silen",
        "silenci",
        "decirar",
        "talcr",
        "readver",
        "vme",
        "comprobo",
        "llamarar",
        "asistante",
        "nochesos",
        "enviaritar",
        "puedober",
        "fabric",
    }
)
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_FIXED_STALL_REPLIES = frozenset(
    {
        "un momento",
        "un momento.",
        "un momento…",
        "un momento...",
        "one moment",
        "one moment.",
        "one moment...",
        "one moment…",
    }
)


# M93 (DEV-D v3u D-w11-t1 «…un 100% de probabilidad de que llovenga.»): the model glued «venga» to the stem of
# another verb. «-tenga» and «-venga» are only the subjunctive of «tener» and «venir» and of the verbs made from them
# with their own prefixes («mantenga», «convenga»); any other stem in front of them is no Spanish word.
_TENER_VENIR_PREFIXES = {
    "t": frozenset({"", "ob", "con", "man", "de", "re", "sos", "entre", "abs", "a"}),
    "v": frozenset({"", "con", "pro", "inter", "pre", "sobre", "de", "a", "re", "contra", "circun", "sub"}),
}
_TENER_VENIR_SUBJUNCTIVE = re.compile(r"(?P<prefix>[a-zñ]*)(?P<stem>[tv])enga(?:s|mos|n)?")


def _invented_tener_venir_subjunctive(token: str) -> bool:
    found = _TENER_VENIR_SUBJUNCTIVE.fullmatch(token)
    return found is not None and found.group("prefix") not in _TENER_VENIR_PREFIXES[found.group("stem")]


def visible_reply_breaks_spanish_plural(value: object, request: object = "") -> bool:
    """M93 (DEV-D v3u D-s042 «No encargo pastels ni panaderías.» for «pastel de camote»): a Spanish reply writes a word
    of the request whose plural is «-es» (semantic.request.words_with_es_plural) with a bare English «-s»."""

    text = str(value or "")
    if _message_response_language(text) != "es":
        return False
    said = set(re.findall(r"[a-zñ]+", _reading_fold(text)))
    return any(word + "s" in said for word in words_with_es_plural(str(request or "")))


# M105 (DEV-D v4a D-s076 «…flexiones con peso y sentadillas búlgar.»): the model cut the last word of a clause; what is
# left is a singular-looking stem after a plural noun («sentadillas búlgar[as]»), which Spanish never writes. A plural
# noun in «-as»/«-os» and, closing the clause, a word in «-ar», «-or», «-al», «-il» or «-ul» with no plural «-s». Folded.
_CUT_AFTER_PLURAL = re.compile(
    r"\b(?P<noun>[a-zñ]{3,}[ao]s)\s+(?P<word>[a-zñ]{2,}(?:ar|or|al|il|ul))(?=\s*(?:[.,;:!)\n]|$))"
)
# Plural-looking words that are no noun before an adjective: articles, pronouns, numbers, adverbs, weekdays.
_NOT_A_PLURAL_NOUN = frozenset({
    "las", "los", "unas", "unos", "esas", "esos", "estas", "estos", "aquellas", "aquellos", "otras", "otros", "todas",
    "todos", "muchas", "muchos", "pocas", "pocos", "algunas", "algunos", "nosotras", "nosotros", "vosotras", "vosotros",
    "ellas", "ellos", "ambas", "ambos", "nuestras", "nuestros", "vuestras", "vuestros", "cuantas", "cuantos", "tantas",
    "tantos", "varias", "varios", "demas", "mas", "menos", "apenas", "quizas", "jamas", "atras", "despues", "antes",
    "entonces", "acaso", "dos", "tres", "seis", "vamos", "somos", "estamos", "tenemos", "hacemos", "podemos",
    "queremos", "vemos", "sabemos", "damos", "ponemos", "vas", "das", "estas", "eras", "fueras", "tienes",
})


def visible_reply_cuts_a_word(value: object) -> bool:
    """A Spanish reply whose clause ends in a word cut short after a plural noun (see above). The lexicon, when the
    runtime has it, keeps a word it knows, unless the word takes its plural by the same rule of the dictionary that
    made the noun before it plural: then the clause left it in the singular («ejercicio·s regular» for
    «regular·es»). An infinitive after a conjugated verb («necesitas descansar») shares no such rule and stays."""

    text = str(value or "")
    if _message_response_language(text) != "es":
        return False
    for found in _CUT_AFTER_PLURAL.finditer(_reading_fold(text)):
        if found.group("noun") in _NOT_A_PLURAL_NOUN:
            continue
        word = found.group("word")
        if (
            corrector.lexicon_available()
            and corrector.known_spanish(word)
            and not corrector.spanish_plural_flags(found.group("noun")) & corrector.spanish_plural_flags(word + "es")
        ):
            continue
        return True
    return False


def visible_reply_invents_a_spanish_infinitive(value: object) -> bool:
    """Reject prose that builds an infinitive out of a conjugated stem.

    "No puedo cuecer las lentejas" and "no puedo vertir la pintura" read as a
    broken product rather than a person speaking, and the ending-based guard
    cannot see them because -er and -ir are exactly what an infinitive ends in.
    Measured at 16 of 314 replies across the sealed campaigns before any guard,
    and still present on V1 as "que se caye la senal" and "que la pantalla
    mere".

    Only the complement of a modal is examined, never every word in the reply.
    Checking the whole text refused "la luz solar": the generator derives
    "solar" as an error of *soler*, and "solar" is an ordinary Spanish word. A
    generated lexicon collides with the real language, so it may only be
    consulted where an infinitive is the sole grammatical possibility.
    """

    folded = _policy_guard_text(value)
    if not folded:
        return False
    if any(
        token in _MEASURED_INVENTED_VISIBLE_TOKENS or _invented_tener_venir_subjunctive(token)
        for token in re.findall(r"[a-zñáéíóúü]+", folded)
    ):
        return True
    return any(
        found.group("complement") in _INVENTED_INFINITIVES
        for found in _MODAL_COMPLEMENT_POSITION.finditer(folded)
    )


# v3a-final F-s007 «…la función Smart Camera no la activan yo» and F-s077 «No leeo SMS»: BAXY speaks of himself in
# the first person singular. A plural verb with «yo» as its subject, or a first person made by adding «-o» to an
# «-eer» stem («leeo», «creeo»: the first person is «leo», «creo»), is broken Spanish. Twin of
# UserMessagePolicy.BreaksFirstPerson.
_PLURAL_VERB_WITH_YO = re.compile(r"\b(?:lo|la|los|las|le|les)\s+[a-z]{2,}(?:an|en)\s+yo\b")
_DOUBLED_E_FIRST_PERSON = re.compile(r"\b[a-z]+eeo\b")


# M54 (v3b-devD D-s004 «recomprar el último billete…» → «No recomprobo el billete…»): the first person a limit
# denies («no X-o») of a verb the person wrote as an infinitive. Folded.
_NEGATED_FIRST_PERSON_VERB = re.compile(
    r"(?:^|[.:;,!¡]\s*|\byo\s+)no\s+(?:(?:me|te|se|lo|la|los|las|le|les|nos)\s+)?([a-zñ]{4,}o)\b"
)


def _first_person_forms(stem: str) -> set[str]:
    """The present first persons a Spanish stem may take: regular, with its diphthong (recomiendo, cuento, adquiero),
    its closed vowel (repito), the -go of tener, poner, venir, salir, traer and decir (obtengo, propongo, distraigo,
    predigo, deshago), and the spelling changes of -cer/-cir, -ger/-gir, -guir and -uir (conozco, venzo, protejo,
    distingo, construyo)."""

    stems = {stem}
    for vowel, changed in (("e", "ie"), ("o", "ue"), ("e", "i"), ("i", "ie")):
        cut = stem.rfind(vowel)
        if cut > 0:
            stems.add(stem[:cut] + changed + stem[cut + 1:])
    forms: set[str] = set()
    for base in stems:
        forms |= {base + "o", base + "yo", base + "go", base + "igo"}
        if base.endswith("c"):
            forms |= {base[:-1] + "zco", base[:-1] + "zo", base[:-1] + "go"}
        if base.endswith("g"):
            forms.add(base[:-1] + "jo")
        if base.endswith("gu"):
            forms.add(base[:-1] + "o")
    return forms


def limit_breaks_the_asked_verb(value: object, request: object) -> bool:
    """The limit denies, in the first person, a verb the person wrote, conjugated into a word that is no form of it
    («recomprobo» for «recomprar»): the two share their first five letters, and it is none of its first persons."""

    stems = requested_infinitive_stems(request)
    if not stems:
        return False
    for found in _NEGATED_FIRST_PERSON_VERB.finditer(_reading_fold(str(value or ""))):
        verb = found.group(1)
        for stem in stems:
            if verb[:5] == stem[:5] and verb not in _first_person_forms(stem):
                return True
    return False


# M79 (DEV-D v3m s047 «Ahora se está pausado la canción "Noc turne" de Zeitgeister.»): «se» with «estar» and a
# participle mixes the passive («se ha pausado») with the state («está pausada»); no Spanish sentence says it. The
# gerund («se está pausando») is a different form and stays. Folded, quoted titles aside.
_REFLEXIVE_ESTAR_PARTICIPLE = re.compile(
    r"\bse\s+(?:esta|estan|estaba|estaban|estuvo|estara)\s+(?:ya\s+)?[a-z]{3,}(?:ado|ada|ados|adas|ido|ida|idos|idas)\b"
)


def visible_reply_breaks_estar_participle(value: object) -> bool:
    """«se está pausado»: a reflexive «estar» with a participle (see above)."""

    unquoted = re.sub(r"[«\"“][^»\"”]{1,400}[»\"”]", " ", str(value or ""))
    return _REFLEXIVE_ESTAR_PARTICIPLE.search(_reading_fold(unquoted)) is not None


# M97 (reserve es315 «por favor cállate por otra hora» → «Eso no lo hago: no cago por otra hora.»): the model's first
# person of a verb landed on a vulgar word. BAXY never says a vulgarity the person did not say first. Folded words.
_VULGAR_WORD = re.compile(
    r"\b(?:cag(?:o|as|a|an|ar|ue|ado|ada|ando|on)|mierdas?|jod(?:er|o|e|ido|ida|idos|idas)|put[oa]s?|"
    r"pendej[oa]s?|cabron(?:es|a|as)?|gilipollas|carajo|vergas?|ching(?:ar|a|o|ado|ada)|follar|follo|"
    r"fuck\w*|shit\w*|bitch\w*|asshole\w*|cunt\w*|crap)\b"
)


def visible_reply_says_a_vulgarity(value: object, request: object = "") -> bool:
    """A vulgar word in BAXY's reply that the person did not write (see above)."""

    said = set(_VULGAR_WORD.findall(_reading_fold(str(request or ""))))
    return any(word not in said for word in _VULGAR_WORD.findall(_reading_fold(str(value or ""))))


def visible_reply_breaks_first_person(value: object) -> bool:
    """BAXY's «yo» with a plural verb («no la activan yo») or an invented first person («leeo»)."""

    folded = _reading_fold(str(value or ""))
    return _PLURAL_VERB_WITH_YO.search(folded) is not None or _DOUBLED_E_FIRST_PERSON.search(folded) is not None


# v3a-final F-s074/F-s091 «…preventing access to the person's Outlook calendar or mail»: the reply speaks to the
# person («your calendar», «tu agenda»), never about them. Twin of UserMessagePolicy.SpeaksOfThePerson.
_PERSON_IN_THIRD = re.compile(
    r"\b(?:the|this)\s+(?:person|user)(?:'s|’s|s')(?!\w)|"
    r"\b(?:calendario|agenda|correos?|mails?|cuentas?|archivos?|carpetas?|tareas?|notas?|recordatorios?|listas?|"
    r"mensajes?|datos|musica|biblioteca|outlook|pc|equipo|computadora)\s+(?:\w+\s+)?de\s+la\s+persona\b"
)


# M62 (v3e2-final F-p07-t4 «Okay, that's all; see ya!» → «Have a great day, BAXY!»): BAXY is the one speaking; the
# person is never called by his name. Its name as a vocative: after a comma or a greeting and closing the sentence
# («…, BAXY!», «bye BAXY»), or opening it («BAXY, …»). «Hola, soy BAXY» names himself and stays.
_PERSON_CALLED_BAXY = re.compile(
    r"(?:,\s*|\b(?:hola|hi|hey|hello|bye|adios|chao|chau|gracias|thanks|thank\s+you|see\s+you|see\s+ya|goodbye|"
    r"good\s+bye|nos\s+vemos|hasta\s+luego|hasta\s+pronto|cuidate|take\s+care)\s+)baxy\s*(?:[!.?…]|$)|"
    r"^\W*baxy\s*,"
)


def visible_reply_calls_the_person_baxy(value: object) -> bool:
    """The reply addresses the person as «BAXY», BAXY's own name (see above)."""

    return any(
        _PERSON_CALLED_BAXY.search(_reading_fold(sentence).strip()) is not None
        for sentence in re.split(r"(?<=[.!?…])\s+", str(value or "").strip())
    )


def visible_reply_speaks_of_the_person(value: object, request: object = "") -> bool:
    """The reply names the person it is talking to in the third person (unless the person wrote it so)."""

    found = _PERSON_IN_THIRD.search(_reading_fold(str(value or "")))
    return found is not None and found.group(0) not in _reading_fold(str(request or ""))


# Tanda 3 «Prende la smart camera» → «Eso no lo hago: la smart camera no la prenDO.»: the model broke a word's
# case halfway and nothing read it. A word that turns to capitals after three lower-case letters is broken,
# unless the person wrote it that way (a brand, «macOS»).
_BROKEN_CASE_WORD = re.compile(r"\b[a-záéíóúüñ]{3,}[A-ZÁÉÍÓÚÜÑ]{2,}\b")


def visible_reply_breaks_word_case(value: object, request: object = "") -> bool:
    """A word of the reply switches to capitals mid-word, and the person did not write it so (see above)."""

    written = str(request or "")
    return any(found.group() not in written for found in _BROKEN_CASE_WORD.finditer(str(value or "")))


def visible_reply_is_a_fixed_stall(value: object) -> bool:
    """A canned «un momento…» is a fixed visible reply. Invariant 5."""

    folded = _policy_guard_text(value)
    return folded in _FIXED_STALL_REPLIES


_SNAKE_CODE = re.compile(r"\b[a-z]{2,}(?:_[a-z0-9]+){1,}\b")
_DOTTED_OP = re.compile(r"\b[a-z]{2,}(?:\.[a-z][a-z0-9]*){1,}\b")
_IDENTIFIER_TOKEN = re.compile(r"[\w-]+(?:[._][\w-]+)+")
# M108 (M107's report): the report of a verified effect leaked the contract in shapes the snake and dotted checks do
# not see — «verified=true succeeded=true», «succeeded: true», «{"state": "off"}», «TARGET_NOT_FOUND», «0x80070005»,
# «windowId». Judged on the report of a result (status, error) only, once links and mail addresses are out; a token the
# person wrote or the result observed (a file «miInforme.txt», a page quoting JSON, the code a window showed) is
# theirs. Product names keep their spelling («Baxy.App», «iPhone», «macOS», «RTX 4060 Ti»): none is a
# lowercase hump, a key with its value, an upper snake or a hex code. Twin: UserMessagePolicy.LeaksContractToken.
_CONTRACT_TOKENS = (
    re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{2,}=\S"),
    re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\s*[:=]\s*(?:true|false|null)\b", re.IGNORECASE),
    re.compile(r"\{\s*\"[^\"{}\n]{1,64}\"\s*:|\"[A-Za-z_][\w.-]{0,63}\"\s*:\s*(?:true|false|null|-?\d|\"|\{|\[)"),
    re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b"),
    re.compile(r"\b0x[0-9A-Fa-f]{4,}\b"),
    re.compile(r"\b[a-z]{2,}(?:[A-Z][a-z0-9]+)+\b"),
)
_LINK_OR_ADDRESS = re.compile(r"(?:\bhttps?://|\bwww\.)\S+|\b[\w.%+-]+@[\w-]+(?:\.[\w-]+)+\b", re.IGNORECASE)
# What a result says about itself, never what it observed.
_CONTRACT_FIELDS_NOT_OBSERVED = frozenset({
    "operation", "operations", "authority", "error", "errorCode", "code", "cause", "kind", "polarity", "diagnosticCode",
})


def _observed_strings(situation: object) -> str:
    """Every string the result observed (mission steps and reasons decoded)."""

    texts: list[str] = []

    def walk(value: object, key: str = "", depth: int = 0) -> None:
        if depth > 8 or key in _CONTRACT_FIELDS_NOT_OBSERVED:
            return
        if isinstance(value, str):
            if value.lstrip().startswith("{"):
                try:
                    decoded = json.loads(value)
                except ValueError:
                    decoded = None
                if isinstance(decoded, dict):
                    walk(decoded, key, depth + 1)
                    return
            texts.append(value)
        elif isinstance(value, dict):
            for child_key, child in value.items():
                walk(child, str(child_key), depth + 1)
        elif isinstance(value, (list, tuple)):
            for child in value:
                walk(child, key, depth + 1)

    walk(situation)
    return "\n".join(texts)


def visible_reply_leaks_a_contract_token(text: str, situation: object, own_words: Iterable[str] = ()) -> bool:
    """The report of a result names a contract token nobody said or observed (see above). A field named in prose before
    a colon («your open windows: …») is English, not the contract; only a field written with its value as the contract
    writes it is (key=value, a boolean or null, JSON)."""

    own = "\n".join((_observed_strings(situation), *own_words)).casefold()
    judged = _LINK_OR_ADDRESS.sub(" ", text or "")
    return any(
        found.group(0).casefold() not in own
        for pattern in _CONTRACT_TOKENS
        for found in pattern.finditer(judged)
    )


_WEB_HOST = re.compile(
    r"\b(?:https?://|www\.)(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+"
    r"[a-z]{2,63}\b",
    re.IGNORECASE,
)
_SUCCESS_OPENERS = re.compile(
    r"^\s*(?:listo\b|ready\b|done\b|¡?\s*listo)",
    re.IGNORECASE,
)
# «la cerrado de Edge», «el abierta de Steam»: a participle used as the action
# noun with the article of the other gender (owner's test 2026-09-21, turn 151).
_MISMATCHED_ACTION_NOUN = re.compile(
    r"\b(?:(?:la|una|esta|esa)\s+\w{3,}[ai]do|(?:el|un|este|ese)\s+(?!hada\b)\w{3,}[ai]da)\b(?!s)",
    re.IGNORECASE,
)
# Tanda 4c «Please decrease el brillo del screen un poco» → «¿Cuánto deseas reducir el brillo del pantalla?» and
# tanda-02 «Reducí el brillo del pantalla un 20 por ciento»: the person's Spanish article stayed in front of the
# English noun the model translated. The PC's own nouns carry their gender and the determiner agrees with it.
# Nouns that are also a verb form after an object clitic («la archivo», «que la ajuste») are left out.
# Folded determiner → the one of the other gender.
_AGREEING_DETERMINER = {
    "el": "la", "del": "de la", "al": "a la", "un": "una", "este": "esta", "ese": "esa",
    "ningun": "ninguna", "algun": "alguna",
    "la": "el", "una": "un", "esta": "este", "esa": "ese", "ninguna": "ningún", "alguna": "algún",
}
_FEMININE_PC_NOUNS = (
    r"pantalla|m[uú]sica|ventana|carpeta|aplicaci[oó]n|computadora|p[aá]gina|canci[oó]n|bater[ií]a|luz|"
    r"c[aá]mara|impresora|lista|alarma|nota|tecla|foto|imagen|pesta[nñ]a|configuraci[oó]n|conexi[oó]n|hora|"
    r"fecha|calculadora|papelera|memoria|contrase[nñ]a|tarea|b[uú]squeda|descarga|unidad"
)
_MASCULINE_PC_NOUNS = (
    r"volumen|brillo|sonido|nivel|teclado|navegador|micr[oó]fono|escritorio|sistema|correo|mensaje|v[ií]deo|"
    r"rat[oó]n|men[uú]|audio|portapapeles|recordatorio|clima|altavoz|parlante|disco|dispositivo|mapa|problema|"
    r"tema|perfil|programa|equipo"
)
_MISMATCHED_ARTICLE = re.compile(
    r"(?<!\w)(?:(?P<masculine>(?i:el|del|al|un|este|ese|ning[uú]n|alg[uú]n))\s+(?P<feminine_noun>"
    + _FEMININE_PC_NOUNS
    + r")|(?P<feminine>(?i:la|una|esta|esa|ninguna|alguna))\s+(?P<masculine_noun>"
    + _MASCULINE_PC_NOUNS
    + r"))(?!\w)"
)


def visible_reply_breaks_article_agreement(value: object) -> str:
    """The agreeing form («de la pantalla») of the first determiner that disagrees with its noun, or ``""``.

    Nouns are matched in lower case only: a capitalised word after the article is a name («el Red Dead»)."""

    match = _MISMATCHED_ARTICLE.search(str(value or ""))
    if match is None:
        return ""
    determiner = _reading_fold(match["masculine"] or match["feminine"])
    noun = match["feminine_noun"] or match["masculine_noun"]
    return f"{_AGREEING_DETERMINER[determiner]} {noun}"
