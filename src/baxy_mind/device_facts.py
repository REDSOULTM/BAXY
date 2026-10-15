"""Facts of device reads: memory and OS version, brightness and other levels, recognized screen text, Python
packages, window snaps, wifi scans, captures and the parts of a request the operation could not take.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .semantic import captures as semantic_captures
from .semantic import acts_on_result as semantic_acts_on_result
from .semantic.request import fold as _reading_fold
from .compose_situation import _decoded_reason, _situation_steps


def _memory_value_forms(value: object) -> list[str]:
    """Decimal spellings a draft may use for an observed GB value (16.5395 → 16.54, 16,54, 16.5, 16,5, 17)."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return []
    forms = set()
    for digits in (2, 1, 0):
        rounded = f"{number:.{digits}f}"
        forms.add(rounded)
        forms.add(rounded.replace(".", ","))
    return sorted(forms, key=len, reverse=True)


def _invented_windows_version(text: str, os_facts: dict) -> bool:
    """A feature-update name («22H2») or a version number absent from the observed os facts."""

    observed = " ".join(str(value) for value in os_facts.values() if isinstance(value, (str, int, float)))
    folded = text.casefold()
    if re.search(r"\b\d{2}h[12]\b", folded) and not re.search(r"\b\d{2}h[12]\b", observed.casefold()):
        return True
    observed_numbers = set(re.findall(r"\d+", observed))
    for match in re.finditer(r"\b(?:version|versión|build|compilación|compilacion)\s+(\d+(?:\.\d+)*)", folded):
        if any(part not in observed_numbers for part in match.group(1).split(".")):
            return True
    return False


def _memory_capacity_figures(memory: object) -> tuple[str, str] | None:
    """(installed, total) in GB with two decimals when both are observed and differ."""

    if not isinstance(memory, dict):
        return None
    total, installed = memory.get("totalBytes"), memory.get("installedBytes")
    if isinstance(memory.get("total"), dict) or isinstance(memory.get("installed_capacity"), dict):
        # Already projected: {"value": 16.5395, "unit": "GB"}.
        total = (memory.get("total") or {}).get("value") if isinstance(memory.get("total"), dict) else None
        installed = (memory.get("installed_capacity") or {}).get("value") if isinstance(memory.get("installed_capacity"), dict) else None
        if not isinstance(total, (int, float)) or not isinstance(installed, (int, float)):
            return None
        total_gb, installed_gb = float(total), float(installed)
    else:
        if not isinstance(total, (int, float)) or not isinstance(installed, (int, float)) or isinstance(total, bool) or isinstance(installed, bool):
            return None
        # The same unit as the projection (measurement_prose_projection.WINDOWS_GB, v3 r5a M4).
        total_gb, installed_gb = float(total) / 2**30, float(installed) / 2**30
    if installed_gb < total_gb or abs(total_gb - installed_gb) < 0.05:
        return None
    return f"{installed_gb:.2f}", f"{total_gb:.2f}"


def _memory_capacity_note(memory: object, language: str) -> str:
    figures = _memory_capacity_figures(memory)
    if figures is None:
        return ""
    installed, total = figures
    if language == "en":
        return (
            f" The RAM installed in this machine is installed_capacity, {installed} GB:"
            " when asked how much RAM the PC has, give that figure and call it"
            f" installed. total, {total} GB, is what the system can use: if you"
            " mention it, call it usable or total, never installed."
        )
    return (
        f" La RAM instalada en este equipo es installed_capacity, {installed.replace('.', ',')} GB:"
        " si preguntan cuánta RAM tiene el PC, da esa cifra y llámala instalada."
        f" total, {total.replace('.', ',')} GB, es la que el sistema puede usar: si la"
        " mencionas, llámala utilizable o total, nunca instalada."
    )


def _mislabelled_installed_memory(text: str, memory: dict) -> bool:
    """A total or usable figure called «instalada»/«installed» when the observed installed value differs."""

    total = memory.get("total") or {}
    installed = memory.get("installed_capacity") or {}
    if not isinstance(total, dict) or not isinstance(installed, dict):
        return False
    total_value, installed_value = total.get("value"), installed.get("value")
    if not isinstance(total_value, (int, float)) or not isinstance(installed_value, (int, float)):
        return False
    if abs(float(total_value) - float(installed_value)) < 0.05:
        return False
    folded = text.casefold()
    installed_forms = set(_memory_value_forms(installed_value))
    for form in _memory_value_forms(total_value):
        if form in installed_forms:
            continue
        for match in re.finditer(re.escape(form), folded):
            window = folded[match.end():match.end() + 40]
            if re.search(r"\b(?:instalad[oa]s?|installed)\b", window):
                return True
    return False


_BRIGHTNESS_EXTREME_CLAIM = re.compile(
    r"(?<!\w)(?:(?:al|a|en\s+el|en|at|on|to)\s+)?(?P<extreme>maximo|minimo|max|min|tope|full|maximum|minimum|100\s*%|0\s*%)(?!\w)"
)
_BRIGHTNESS_NEGATION_BEFORE = re.compile(r"\b(?:no|not|isn'?t|nunca|never|tampoco|ni|sin)\b")


def _observed_brightness_values(seen: dict) -> list[int]:
    values: list[int] = []
    if seen.get("setting") != "brightness":
        return values
    if isinstance(seen.get("value"), (int, float)) and not isinstance(seen.get("value"), bool):
        values.append(int(seen["value"]))
    for monitor in seen.get("monitors") or []:
        if isinstance(monitor, dict) and isinstance(monitor.get("value"), (int, float)) and not isinstance(monitor.get("value"), bool):
            values.append(int(monitor["value"]))
    return values


_LEVEL_OPERATIONS = frozenset({"system.settings.set", "system.settings.adjust", "audio.volume", "audio.volume.adjust"})
_RAISED_CLAIM = re.compile(
    r"(?<!\w)(?:subí|subió|subid[oa]|aument[éó]|aumentad[oa]|increment[éó]|incrementad[oa]|elev[éó]|elevad[oa]|"
    r"raised|increased|brightened|turned\s+(?:[\w']+\s+){0,3}up|went\s+up)(?!\w)",
    re.IGNORECASE,
)
_LOWERED_CLAIM = re.compile(
    r"(?<!\w)(?:bajé|bajó|bajad[oa]|reduj[eo]|reducí|reducid[oa]|disminuí|disminuyó|disminuid[oa]|atenu[éó]|"
    r"atenuad[oa]|lowered|decreased|reduced|dimmed|turned\s+(?:[\w']+\s+){0,3}down|went\s+down)(?!\w)",
    re.IGNORECASE,
)


def _observed_level_change(seen: dict) -> tuple[int, int] | None:
    """The level before and after an observed set or adjustment, when the receipt read both."""

    def first_number(*values: object) -> int | None:
        for value in values:
            if isinstance(value, list) and value:
                value = value[0]
            if isinstance(value, dict):
                value = value.get("volumePercent")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return int(value)
        return None

    before = first_number(seen.get("before"), seen.get("baselineValues"), seen.get("baselineLevel"), seen.get("baseline"))
    after = first_number(seen.get("values"), seen.get("final"), seen.get("value"), seen.get("level"))
    return None if before is None or after is None else (before, after)


def _observed_levels(payload: dict) -> list[dict]:
    """What was seen of each level set or adjustment the payload reports: its own operation, and each step of a
    mission (``completedStepsInOrder``)."""

    found = []
    if payload.get("operation") in _LEVEL_OPERATIONS and isinstance(payload.get("seen"), dict):
        found.append(payload["seen"])
    for step in payload.get("completedStepsInOrder") or ():
        result = step.get("resultAtThisStep") if isinstance(step, dict) else None
        if (
            isinstance(result, dict)
            and (result.get("operation") or step.get("operation")) in _LEVEL_OPERATIONS
            and isinstance(result.get("seen"), dict)
        ):
            found.append(result["seen"])
    return found


def _unobserved_direction(text: str, levels: list[dict]) -> bool:
    """Tanda 4c «Incrementa el brightness al level 8» (the brightness was 100) → «El brightness se incrementó al
    nivel 8.»: the direction was the person's verb, not an observation. A raise or a lowering is said only as the
    observed levels show it; when the receipt did not read the level before, no direction is said at all.

    Revisión r19b: a mission is judged by each of its level steps (_observed_levels), not only a lone operation;
    a direction said needs one step whose readings show it («Bajé el brillo al 30 % y abrí la Calculadora» over a
    set from 10 is refused as one operation would be)."""

    raised = _RAISED_CLAIM.search(text) is not None
    lowered = _LOWERED_CLAIM.search(text) is not None
    if not levels or not (raised or lowered):
        return False
    changes = [change for change in map(_observed_level_change, levels) if change is not None]
    return (raised and not any(after > before for before, after in changes)) or (
        lowered and not any(after < before for before, after in changes)
    )


def _contradicted_brightness_extreme(text: str, seen: dict) -> str:
    """BRIGHT1319 H0674: «El brillo está en el máximo.» with an observed 60.

    An affirmed extreme (max/min, 100 %/0 %) that the observed values do not
    reach contradicts the reading; a negated one («no está al máximo») is the
    correct answer and passes.
    """
    values = _observed_brightness_values(seen)
    if not values:
        return ""
    folded = _reading_fold(text)
    for match in _BRIGHTNESS_EXTREME_CLAIM.finditer(folded):
        if _BRIGHTNESS_NEGATION_BEFORE.search(folded[max(0, match.start() - 24):match.start()]):
            continue
        extreme = match.group("extreme").replace(" ", "")
        if extreme in {"maximo", "max", "tope", "full", "maximum", "100%"} and any(v < 100 for v in values):
            return "contradicted_maximum"
        if extreme in {"minimo", "min", "minimum", "0%"} and any(v > 0 for v in values):
            return "contradicted_minimum"
    return ""


# Framing vocabulary a screen-reading report may use without it appearing in
# the recognized text (folded 4-letter stems): the act of reading, the screen,
# lines and text, and the ordinary connectives around a quotation.
_OCR_FRAMING_STEMS = frozenset({
    # reading, the screen, lines, quoting
    "pant", "scre", "text", "lect", "leid", "leyo", "leer", "lei", "reco", "line",
    "mues", "most", "show", "disp", "apar", "appe", "dice", "dijo", "says", "said",
    "vist", "visi", "visu", "escr", "pala", "word", "cita", "quot", "capt", "imag", "foto",
    "pict", "desc", "cann", "uniej", "pued", "puedo", "veo", "cont", "incl", "tien",
    "encu", "esta", "hay", "ests", "sigu", "foll", "here",
    # position words about the screen
    "prin", "arri", "abaj", "izqu", "dere", "part", "zona", "area", "medi", "cent",
    "lado", "junt", "cerc",
    # connectives and quantifiers
    "what", "with", "this", "that", "from", "have", "there", "these", "those", "also",
    "like", "such", "them", "they", "some", "seve", "abou", "amon", "entr", "entre",
    "ella", "ello", "sobr", "desd", "hast", "tamb", "como", "pero", "para", "porq",
    "cuan", "dond", "algu", "otro", "otra", "todo", "toda", "cada", "much", "poco",
    "vari", "solo", "unic", "mism", "prop", "prim", "segu", "terc", "ulti", "final",
    "lueg", "desp", "ante", "ento", "term", "logr", "lleg", "reci", "clar", "legi",
    "borr", "peque", "gran", "corto", "larg", "brev", "resu",
})


def _screen_text_excerpt(recognized: str, lines: int = 3, width: int = 120) -> list[str]:
    """The first lines with real content, each capped, from a recognized screen text."""

    chosen: list[str] = []
    for raw in recognized.split("\n"):
        line = " ".join(raw.split())
        if len(line) < 12 or sum(ch.isalpha() for ch in line) < 6:
            continue
        chosen.append(line if len(line) <= width else line[:width].rstrip() + "…")
        if len(chosen) >= lines:
            break
    if not chosen:
        flat = " ".join(recognized.split())
        chosen = [flat[:width].rstrip() + ("…" if len(flat) > width else "")] if flat else []
    return chosen


def _opens_with_observed_identifier(lead: str, situation: dict) -> bool:
    """PIP1819: «requests ya está instalado…» opens with the package identifier as
    observed (seen.package); an identifier keeps its spelling, lowercase included."""

    for source in (situation.get("seen"), situation.get("observed")):
        if not isinstance(source, dict):
            continue
        for key in ("package", "name", "title", "query"):
            value = source.get(key)
            if not isinstance(value, str) or not value.strip():
                continue
            value = value.strip()
            if value[0].isalpha() and value[0].islower() and lead.startswith(value) and (
                len(lead) == len(value) or not lead[len(value)].isalnum()
            ):
                return True
    return False


def _project_python_package_status(seen: dict) -> dict:
    """PIP1819: installedIn (with the package version), notInstalledIn and noPipIn
    as exact Python version strings, instead of the per-Python entries."""

    entries = seen.get("pythons") if isinstance(seen.get("pythons"), list) else []
    installed_in: list[str] = []
    not_installed_in: list[str] = []
    no_pip_in: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("pythonVersion") or entry.get("displayName") or "").strip()
        if not label:
            continue
        if entry.get("pipAvailable") is False:
            no_pip_in.append(label)
        elif entry.get("installed") is True:
            package_version = entry.get("packageVersion")
            installed_in.append(
                f"{label} ({package_version})" if isinstance(package_version, str) and package_version else label
            )
        else:
            not_installed_in.append(label)
    return {
        "package": seen.get("package"),
        "installedIn": installed_in,
        "notInstalledIn": not_installed_in,
        "noPipIn": no_pip_in,
        "installedCount": len(installed_in),
    }


def _python_package_state_defect(text: str, seen: dict) -> str:
    """PIP1817: «numpy no está instalado en ninguna versión» with two installs in the
    receipt, «Pandas is not installed. It is available in…»: the overall state said
    must be the observed one."""

    if isinstance(seen.get("installedIn"), list):
        installed = [str(x) for x in seen["installedIn"]]
    else:
        installed = [
            str(entry.get("pythonVersion") or "")
            for entry in (seen.get("pythons") or [])
            if isinstance(entry, dict) and entry.get("installed") is True
        ]
    folded = _reading_fold(text)
    denies = re.search(
        r"\bno esta instalad[oa] en ning|\bnot installed in any|\bno esta en ning|"
        r"(?:^|[.;:!?]\s*)[^.;:!?]*?\b(?:no esta|no se encuentra) instalad[oa]\s*(?:[.;!]|$)|"
        r"(?:^|[.;:!?]\s*)[^.;:!?]*?\b(?:is not|isn't|is n't) installed\s*(?:[.;!]|$)",
        folded,
    )
    affirms = re.search(
        r"(?<!no )(?<!not )\b(?:ya esta|esta|is|is already|already) instal(?:ado|ada|led)\b",
        folded,
    )
    if installed and denies is not None:
        return "package_state_reversed"
    if not installed and affirms is not None and denies is None:
        return "package_state_reversed"
    return ""


def _screen_line_count(payload: dict) -> int | None:
    """The recognized line count of a verified OCR read, single-step or mission-shaped."""

    seen = payload.get("seen")
    if payload.get("operation") == "ocr.read" and isinstance(seen, dict) and type(seen.get("lineCount")) is int:
        return seen["lineCount"]
    for step in payload.get("completedStepsInOrder") or []:
        if isinstance(step, dict) and step.get("operation") == "ocr.read":
            result = step.get("resultAtThisStep")
            step_seen = result.get("seen") if isinstance(result, dict) else None
            if isinstance(step_seen, dict) and type(step_seen.get("lineCount")) is int:
                return step_seen["lineCount"]
    return None


def _screen_count_defect(text: str, payload: dict, user_text: str) -> str:
    """SCREEN1809: «The screen shows 3 lines» counted the excerpt; the only count
    a screen reading may state is seen.lineCount (quoted lines keep their own numbers)."""

    line_count = _screen_line_count(payload)
    if line_count is None:
        return ""
    prose = re.sub(r'[«"“][^»"”]{1,4096}[»"”]', " ", text)
    prose = re.sub(r"'[^']{1,4096}'", " ", prose)
    allowed = {str(line_count)} | set(re.findall(r"\d+", user_text or ""))
    for number in re.findall(r"(?<![\w.,-])\d+(?![\w.,-])", prose):
        if number not in allowed:
            return "screen_wrong_count"
    return ""


def _recognized_screen_text(payload: dict) -> str | None:
    """The verified OCR text in a compose payload, single-step or mission-shaped."""

    seen = payload.get("seen")
    if payload.get("operation") == "ocr.read" and isinstance(seen, dict):
        text = seen.get("text")
        if isinstance(text, str) and text.strip():
            return text
    for step in payload.get("completedStepsInOrder") or []:
        if isinstance(step, dict) and step.get("operation") == "ocr.read":
            result = step.get("resultAtThisStep")
            step_seen = result.get("seen") if isinstance(result, dict) else None
            text = step_seen.get("text") if isinstance(step_seen, dict) else None
            if isinstance(text, str) and text.strip():
                return text
    return None


@lru_cache(maxsize=1)
def _capture_saved_folder_names() -> dict:
    return json.loads((Path(__file__).resolve().parent / "data" / "capture_saved_folders.v1.json").read_text(encoding="utf-8"))


def _capture_saved_folder_name(folder: object, language: str) -> str | None:
    """Ronda 22: the visible name of the known folder a capture was saved to (data/capture_saved_folders.v1.json)."""

    names = _capture_saved_folder_names()["folders"].get(folder) if isinstance(folder, str) else None
    return names.get("en" if language == "en" else "es") if isinstance(names, dict) else None


def _capture_operations_of(situation: object) -> bool:
    """Revisión r22: the situation is a capture, or a mission one of whose steps (or its failed reason) is one."""

    if not isinstance(situation, dict):
        return False
    if situation.get("operation") in semantic_captures.CAPTURE_OPERATIONS:
        return True
    reason = _decoded_reason(situation)
    steps = [*_situation_steps(situation), *([reason] if isinstance(reason, dict) else [])]
    return any(isinstance(step, dict) and step.get("operation") in semantic_captures.CAPTURE_OPERATIONS for step in steps)


def _capture_unmet_facts(situation: object, user_text: str, language: str) -> list[dict]:
    """Revisión r22 (bloqueante 1): every place the person asked the capture to be kept in that the operation could not
    take («…en mi pendrive», «…en el escritorio y en documentos»), as ``notDone`` (the act from data, the place as
    said), so the final says it was not saved there instead of losing it in silence."""

    if not user_text or not _capture_operations_of(situation):
        return []
    action = _capture_saved_folder_names()["notKept"]["en" if language == "en" else "es"]
    return [{"action": action, "target": place} for place in semantic_captures.capture_unmet_places(user_text)]


def _capture_unmet_targets(payload: object) -> list[str]:
    """The places a capture was asked to be kept in and was not (``notDone`` items of the act notKept)."""

    not_done = payload.get("notDone") if isinstance(payload, dict) else None
    actions = set(_capture_saved_folder_names()["notKept"].values())
    return [
        item["target"] for item in (not_done if isinstance(not_done, list) else [])
        if isinstance(item, dict) and item.get("action") in actions and isinstance(item.get("target"), str)
    ]


_PLACE_OWNER = re.compile(r"^(?:(?:mi|mis|my|tu|tus|your|el|la|los|las|the|a|an)\s+)+")
_UNMET_DENIED = re.compile(
    r"\b(?:no|not|nunca|never|tampoco|couldn'?t|could\s+not|can'?t|cannot|didn'?t|did\s+not|wasn'?t|unable|imposible)\b"
)


def _capture_unmet_untold(text: str, payload: dict) -> bool:
    """Revisión r22: a final over a capture asked to be kept somewhere it could not be names each such place, as not
    done in its own clause («No pude guardarla en tu pendrive»); a draft that leaves it out or tells it kept there is
    a defect."""

    folded = _reading_fold(text)
    for target in _capture_unmet_targets(payload):
        core = _PLACE_OWNER.sub("", _reading_fold(target)).strip()
        if not core:
            continue
        told = any(
            _UNMET_DENIED.search(re.split(r"[.;:!?]", folded[: match.start()])[-1])
            for match in re.finditer(r"\b" + re.escape(core) + r"\b", folded)
        )
        if not told:
            return True
    return False


def _capture_unmet_floor(payload: dict, language: str) -> str:
    """Revisión r22: the floor's sentence for each place the capture was not kept in (data notKeptFloor)."""

    template = _capture_saved_folder_names()["notKeptFloor"]["en" if language == "en" else "es"]
    return " ".join(template.format(place=" ".join(target.split())) for target in _capture_unmet_targets(payload))


def _unreceived_facts(situation: object, language: str) -> list[dict]:
    """Revisión 2 de r22 (bloqueante 3): the parts of the request the operation's schema could not receive (the mind
    reads them from the person's own message, semantic.acts_on_result, into ``situation.unreceived``), as ``notDone``:
    the act from data, the part as said."""

    parts = situation.get("unreceived") if isinstance(situation, dict) else None
    acts = semantic_acts_on_result.data()
    told = []
    for part in parts if isinstance(parts, list) else ():
        if not isinstance(part, dict) or not isinstance(part.get("said"), str) or not part["said"].strip():
            continue
        entry = acts["name"] if part.get("act") == "name" else acts["acts"].get(part.get("act"))
        if isinstance(entry, dict):
            told.append({"action": entry["action"]["en" if language == "en" else "es"], "target": part["said"].strip()})
    return told


def _unreceived_entries(payload: object) -> list[tuple[dict, str]]:
    """(the act's data entry, the part as said) of each ``notDone`` item that is a part not received."""

    acts = semantic_acts_on_result.data()
    by_action = {
        action: entry
        for entry in (*acts["acts"].values(), acts["name"])
        for action in entry["action"].values()
    }
    not_done = payload.get("notDone") if isinstance(payload, dict) else None
    return [
        (by_action[item["action"]], item["target"])
        for item in (not_done if isinstance(not_done, list) else [])
        if isinstance(item, dict) and item.get("action") in by_action and isinstance(item.get("target"), str)
    ]


def _unreceived_untold(text: str, payload: dict) -> bool:
    """Revisión 2 de r22: a final over a request with a part the operation could not receive says that part was not
    done — a sentence that denies, naming a word of the part or the act's own verb; a draft that leaves it out (or
    tells it done) is a defect."""

    entries = _unreceived_entries(payload)
    if not entries:
        return False
    sentences = [part for part in re.split(r"[.;!?]", _reading_fold(text)) if _UNMET_DENIED.search(part)]
    for entry, said in entries:
        words = {word for word in re.findall(r"\w{4,}", _reading_fold(said))}
        stems = {_reading_fold(stem) for stem in (*entry.get("es", ()), *entry.get("en", ()))}
        if not any(
            any(re.search(r"\b" + re.escape(word) + r"\b", sentence) for word in words)
            or any(re.search(r"\b" + re.escape(stem), sentence) for stem in stems)
            for sentence in sentences
        ):
            return True
    return False


def _unreceived_floor(payload: dict, language: str) -> str:
    """Revisión 2 de r22: the floor's sentence for each part not received (data ``floor``)."""

    key = "en" if language == "en" else "es"
    return " ".join(entry["floor"][key].format(said=" ".join(said.split())) for entry, said in _unreceived_entries(payload))


_LISTING_SHOWN_NAMES = 6
_KNOWN_FOLDER_LABELS = {
    "desktop": ("el escritorio", "the desktop"),
    "downloads": ("Descargas", "Downloads"),
    "documents": ("Documentos", "Documents"),
}


def _snap_beyond_half(payload: object) -> dict | None:
    """M159 (DEV-I v4w I-s048 «pasame la ventana de spotify a la derecha»): the verified window.snap observation of a
    window that is flush against the asked side but larger than the half (``fitsInHalf`` false: its own minimum is
    wider), single-step or among a plan's completed steps. None for every other result, a fitting snap included."""

    if not isinstance(payload, dict):
        return None
    seen = payload.get("seen")
    if payload.get("operation") == "window.snap" and isinstance(seen, dict) and seen.get("fitsInHalf") is False:
        return seen
    for step in payload.get("completedStepsInOrder") or []:
        if isinstance(step, dict):
            found = _snap_beyond_half(step.get("resultAtThisStep"))
            if found is not None:
                return found
    return None


# M159: BAXY's reply (folded) says the window did not fit in the half: «no cabe», «ocupa un poco más», «más ancha
# que la mitad», «doesn't fit», «wider than half», «a bit more», or names its minimum.
_SAYS_BEYOND_HALF = re.compile(
    r"\b(?:no\s+(?:me\s+|le\s+|se\s+)?(?:cabe|cupo|entra|entro|alcanza)|"
    r"(?:doesn['’]?t|does\s+not|didn['’]?t|did\s+not|can['’]?t|cannot|won['’]?t|wouldn['’]?t)\s+fit|"
    r"mas\s+(?:ancha|ancho|grande|espacio|de\s+(?:la\s+)?(?:mitad|media))|"
    r"mas\s+que\s+(?:la\s+)?(?:mitad|media)|"
    r"ocup\w*\s+(?:un\s+poco\s+|algo\s+|apenas\s+)?mas|"
    r"(?:wider|larger|bigger|more)\s+than\s+(?:the\s+)?half|"
    r"(?:a\s+(?:bit|little)|slightly|somewhat)\s+(?:more|wider|larger|bigger)|"
    r"minim[ao]s?|minimum)\b"
)


def _snap_beyond_half_untold(reply: str, payload: dict) -> bool:
    """M159: the window did not fit in the half and the reply does not say so; «la puse en la mitad derecha» alone
    would tell a half it does not occupy."""

    return _snap_beyond_half(payload) is not None and _SAYS_BEYOND_HALF.search(_reading_fold(reply)) is None


def _wifi_scan_networks_in_situation(situation: dict) -> dict | None:
    """NETWORK1737: the verified wifi.scan observation of a situation, single-step
    or mission-shaped (radio switched on, then scanned)."""

    def from_node(node: object) -> dict | None:
        if isinstance(node, str):
            try:
                node = json.loads(node)
            except (ValueError, TypeError):
                return None
        if not isinstance(node, dict):
            return None
        if node.get("operation") == "wifi.scan" and node.get("verified") is True and node.get("succeeded") is True:
            observed = node.get("observed")
            if isinstance(observed, dict) and isinstance(observed.get("networks"), list):
                return observed
        for step in node.get("steps") or []:
            found = from_node(step)
            if found:
                return found
        return None

    return from_node(situation)


def _recognized_screen_text_in_situation(situation: dict) -> str | None:
    """The verified OCR text in a situation, single-step or mission-shaped."""

    def from_node(node: object) -> str | None:
        if isinstance(node, str):
            try:
                node = json.loads(node)
            except (ValueError, TypeError):
                return None
        if not isinstance(node, dict):
            return None
        if (
            node.get("operation") == "ocr.read"
            and node.get("verified") is True
            and node.get("succeeded") is True
        ):
            observed = node.get("observed")
            text = observed.get("text") if isinstance(observed, dict) else None
            if isinstance(text, str) and text.strip():
                return text
        for step in node.get("steps") or []:
            found = from_node(step)
            if found:
                return found
        return None

    return from_node(situation)


def _ocr_unsupported_terms(text: str, recognized: str, user_text: str) -> list[str]:
    """Content words of a screen-reading report that the recognized text lacks."""

    def stems(value: str) -> set[str]:
        return {
            word[:4]
            for word in re.findall(r"[a-z0-9]{4,}", _reading_fold(value))
        }

    allowed = stems(recognized) | stems(user_text) | _OCR_FRAMING_STEMS
    unsupported: list[str] = []
    # A quotation may carry the JSON escapes of the excerpt («…\\n…»); they are
    # separators, not words.
    text = re.sub(r"\\[nrt]", " ", text)
    for word in re.findall(r"[a-z0-9]{5,}", _reading_fold(text)):
        if word[:4] not in allowed and word not in unsupported:
            unsupported.append(word)
    return unsupported
