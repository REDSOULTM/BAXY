"""«abrir el archivo …»: one file.open with the mission's application, and the cause a failed opening is said
with.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from . import effect_intent, operation_floor
from .cu_acts import _none


# Why a file.open of the sub-goal did not open the file, by the provider's code: said, never tried another way (floor
# data «computerUse.fileNotOpened», in both languages: the decision's reason and the final's cause).
_FILE_OPEN_FAILURES: dict = operation_floor.floor_data()["computerUse"]["fileNotOpened"]
FILE_NOT_OPENED = "file_not_opened"


def file_not_opened_cause(code: str | None, name: str, application: str | None, language: str) -> str:
    """The cause a failed file.open is said with («no encontré el archivo «x.png» en tus carpetas …»): the provider's
    code, «notShown» for a file opened whose window never showed it."""

    lang = "en" if language == "en" else "es"
    quote = operation_floor.floor_data()["templates"][lang]["quote"]
    said = _FILE_OPEN_FAILURES.get(str(code or ""), _FILE_OPEN_FAILURES["other"])
    template = said[lang] if isinstance(said, dict) else _FILE_OPEN_FAILURES["other"][lang]
    return template.format(name=quote.format(value=name), application=quote.format(value=application or ""))


def open_file_step(
    target: str,
    application: str | None,
    history: list[dict],
    application_names: Iterable[str] | effect_intent.ApplicationCatalogIndex,
) -> dict[str, object]:
    """cu-v3-abrir-archivo (r9 v3-15, v3-17, v3-18: the gallery searched, the dialog never found): the sub-goal «abrir
    el archivo <ruta o nombre>» is one file.open with the mission's application, the file by its known folder and its
    path inside it (or its name alone, which the provider looks for in the known folders and never guesses between
    two). Tried once: a failure is said with its cause, a file opened and not in front is not opened again."""

    from . import known_folders
    from .known_folders import known_place

    name = Path(target).name or target
    opened = [step for step in history if isinstance(step, dict) and step.get("operation") == "file.open"]
    def not_opened(cause: str) -> dict[str, object]:
        # The code carries the cause (review, finding 4): the App keeps it for the final, said in its language.
        return _none(file_not_opened_cause(cause, name, application, "es"), code=f"{FILE_NOT_OPENED}:{cause}")

    if opened:
        last = opened[-1]
        if last.get("ok") is True:
            return not_opened("notShown")
        error = str(last.get("error") or "")
        return not_opened(error if isinstance(_FILE_OPEN_FAILURES.get(error), dict) and error != "notShown" else "other")
    if Path(target).is_absolute():
        place = known_place(target)
        if place is None:
            return not_opened("file_not_found")
        folder, relative = place
    else:
        # A name alone (review, finding 6): the one file of that name in the known folders; two are said, never one
        # of them opened (the provider takes the folder it is given first).
        # A walk cut short proves nothing: when the provider looks the name up itself (it lies directly in no folder
        # it would be handed), it decides, never opening one of two and saying when its own search was cut short.
        found = known_folders.located_files(target)
        if found is None and not known_folders.left_to_the_provider(target, "documents"):
            return not_opened("file_search_incomplete")
        if found is not None and len(found) > 1:
            return not_opened("file_ambiguous")
        place = known_place(found[0]) if found else None
        folder, relative = place if place is not None else ("documents", target)
    arguments: dict[str, object] = {"folder": folder, "name": relative}
    if application:
        app_id = effect_intent.resolve_application_catalog_app_id(f"abre {application}", application_names)
        if app_id is None:
            return not_opened("app_not_found")
        arguments["application"] = app_id
    return {"operation": "file.open", "arguments": arguments, "reason": f"abrir «{name}» con la aplicación pedida"}
