"""cu-v3-abrir-archivo: a file named to open in an application is opened with that application by the shell.

Pass r9 (cu-v3/v3_pasada_r9_parcial_veredictos.json, model_calls.jsonl of v2-<case>): v3-15 «abre la foto paisaje.jpg
que esta en Documentos\\baxy-prueba-v3 en fotos, editala y girala…», v3-17 «abre la imagen prueba.png de la carpeta
baxy-prueba-v3 en fotos» and v3-18 «open paisaje.jpg in photos and tell me the image dimensions» planned the first
sub-goal «abrir el dialogo de abrir» (checked by a «Nombre de archivo» field): Fotos' gallery has no Open dialog, and
the model clicked «Ventana emergente», «Buscar en la galería» and typed in the gallery's search until it gave up. The
sub-goal is now «abrir el archivo <ruta>», the typed file.open with the mission's application (the shell hands the file
to it, no key, no dialog), and the mission goes on in the window it opens.

The views are the real ones of the r9 pass (step 1 of v3-15 and v3-17: the gallery; v3-18: another image open).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from baxy_mind import computer_use, known_folders
from baxy_mind import cu_projection
from baxy_mind import cu_finals
from baxy_mind.semantic import cu_tipos, missions

OPENED = cu_tipos.FILE_OPENED

APPS = (
    "BAXY", "Bloc de notas", "Discord", "Fotos", "Google Chrome", "Microsoft Edge", "Notas rápidas", "OBS Studio",
    "OneNote", "Paint", "PowerPoint", "Spotify", "Steam", "Terminal",
)

V3_15 = (
    "abre la foto paisaje.jpg que esta en Documentos\\baxy-prueba-v3 en fotos, editala y girala a la derecha pero no "
    "la guardes"
)
V3_17 = "abre la imagen prueba.png de la carpeta baxy-prueba-v3 en fotos"
V3_18 = "open paisaje.jpg in photos and tell me the image dimensions"


def _control(i: int, kind: str, name: str, state: str = "") -> dict:
    return {"i": i, "kind": kind, "name": name, "state": state}


# r9 v3-15 step 1 (and v3-17 turn 1): the gallery of Fotos, as the engine saw it.
GALLERY = {
    "window": {"title": "Fotos", "process": "Photos"},
    "controls": [
        _control(3, "Button", "Cerrar navegación"), _control(4, "ListItem", "Galería", "selected"),
        _control(5, "Button", "Agregar carpeta"), _control(6, "ListItem", "Favoritos"),
        _control(7, "ListItem", "OneDrive - Personal"), _control(8, "ListItem", "Fotos en iCloud"),
        _control(9, "ListItem", "Este equipo", "expanded"), _control(10, "ListItem", "Imágenes", "collapsed"),
        _control(11, "Button", "Seleccionar elementos"), _control(12, "Button", "Iniciar presentación"),
        _control(17, "Button", "Captura de pantalla 2026-10-07 042618.png"),
        _control(18, "Button", "Captura de pantalla 2026-10-06 200933.png"),
        {"i": 28, "kind": "Edit", "name": "Buscar en la galería", "state": "", "value": "copia"},
        _control(29, "Button", "Importar fotos", "collapsed"), _control(30, "Button", "Configuración"),
        _control(34, "Window", "Ventana emergente"),
    ],
    "text": {"TL": ["copia", "Galería", "Favoritos"], "L": ["OneDrive - Personal", "Este equipo", "Imágenes"]},
}
# r9 v3-18: Fotos showing another image (a screenshot of 625 x 847), the window BAXY found in front of it.
OTHER_IMAGE = {
    "window": {"title": "Captura de pantalla 2026-10-07 042618.png", "process": "Photos"},
    "controls": [_control(0, "Button", "Editar"), _control(1, "Slider", "Zoom")],
    "text": {"T": ["PNG", "625 x 847", "65.6 KB", "Editar"]},
}
# The person's own window in front (the engine opens the file behind it).
PERSON = {"window": {"title": "Documento - Word", "process": "WINWORD"}, "controls": [], "text": {}}


class _NoModel:
    """No model call is needed to open a file the request names."""

    def __getattr__(self, name: str):  # pragma: no cover - a call is the failure
        raise AssertionError(f"the model was asked ({name})")


@pytest.fixture
def folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    documents = tmp_path / "Documentos"
    pictures = tmp_path / "Imagenes"
    (documents / "baxy-prueba-v3").mkdir(parents=True)
    pictures.mkdir()
    for name in ("paisaje.jpg", "prueba.png", "foto.png"):
        (documents / "baxy-prueba-v3" / name).write_bytes(b"x")
    monkeypatch.setattr(
        known_folders, "known_folder",
        lambda folder: {"documents": str(documents), "pictures": str(pictures)}.get(folder),
    )
    return documents / "baxy-prueba-v3"


def _step(goal: str, view: dict, history: list[dict] | None = None, application: str | None = "Fotos") -> dict:
    return computer_use.decide_step(
        _NoModel(), objective=goal, goal=goal, application=application, success_check=None, view=view,
        history=history or [], budget_left=10, application_names=APPS,
    )


def test_the_plan_opens_the_file_first_never_through_a_dialog(folders: Path) -> None:
    fifteen = missions.mission_request(V3_15, APPS)
    assert fifteen is not None and fifteen.application == "Fotos"
    assert [(step.goal, step.success_check) for step in fifteen.steps][0] == (
        f"abrir el archivo {folders / 'paisaje.jpg'}", f"title:paisaje&{OPENED}")
    assert [step.goal for step in fifteen.steps][1:] == ["editala", "girala a la derecha pero no la guardes"]
    seventeen = missions.mission_request(V3_17, APPS)
    assert seventeen is not None and seventeen.application == "Fotos"
    assert (seventeen.goal, seventeen.success_check) == (
        f"abrir el archivo {folders / 'prueba.png'}", f"title:prueba&{OPENED}")
    eighteen = missions.mission_request(V3_18, APPS)
    assert eighteen is not None and eighteen.application == "Fotos"
    assert eighteen.success_check == f"title:paisaje&{OPENED}"
    assert eighteen.goal.startswith(f"abrir el archivo {folders / 'paisaje.jpg'}")
    # The question rides on the goal, for the final to answer from the window the file opened in.
    assert eighteen.goal.endswith("tell me the image dimensions")
    for mission in (fifteen, seventeen, eighteen):
        goals = [step.goal for step in mission.steps] or [mission.goal]
        assert not any("dialogo" in goal or goal.startswith("poner nombre de archivo") for goal in goals)


@pytest.mark.parametrize(("case", "view"), [("v3-15", GALLERY), ("v3-17", GALLERY), ("v3-18", OTHER_IMAGE),
                                             ("behind the person", PERSON)])
def test_the_engine_opens_the_file_with_the_application_by_the_shell(folders: Path, case: str, view: dict) -> None:
    name = "prueba.png" if case == "v3-17" else "paisaje.jpg"
    decision = _step(f"abrir el archivo {folders / name}", view)
    assert decision["operation"] == "file.open", case
    assert decision["arguments"] == {"folder": "documents", "name": f"baxy-prueba-v3\\{name}", "application": "Fotos"}
    # The question tail of v3-18 is the final's, never part of the file.
    asked = _step(f"abrir el archivo {folders / 'paisaje.jpg'}{computer_use.QUESTION_MARK}tell me the dimensions", view)
    assert asked["arguments"]["name"] == "baxy-prueba-v3\\paisaje.jpg"


def test_a_name_alone_is_looked_for_by_the_provider(folders: Path) -> None:
    decision = _step("abrir el archivo nada.jpg", GALLERY)
    assert decision["operation"] == "file.open"
    assert decision["arguments"] == {"folder": "documents", "name": "nada.jpg", "application": "Fotos"}
    # The one file of that name in the known folders is opened where it is.
    one = _step("abrir el archivo paisaje.jpg", GALLERY)
    assert one["arguments"] == {"folder": "documents", "name": "baxy-prueba-v3\\paisaje.jpg", "application": "Fotos"}
    # With no application, the file's own one opens it.
    assert "application" not in _step("abrir el archivo paisaje.jpg", PERSON, application=None)["arguments"]


def test_two_files_of_one_name_are_said_never_one_of_them_opened(folders: Path) -> None:
    """Review, finding 6: Documentos\\dup.png and Imágenes\\dup.png; the provider would take the folder it is given
    first (Documentos) and answer for the wrong image. The mind says there are two and opens none."""

    (folders.parent / "dup.png").write_bytes(b"x")
    (folders.parent.parent / "Imagenes" / "dup.png").write_bytes(b"x")
    assert missions._file_reads("abri dup.png") == [("abrir el archivo dup.png", f"title:dup&{OPENED}", False)]
    decision = _step("abrir el archivo dup.png", GALLERY)
    assert decision["operation"] == "none" and decision["code"] == "file_not_opened:file_ambiguous"
    assert "más de un archivo «dup.png»" in str(decision["reason"])


def test_a_walk_cut_short_leaves_the_name_to_the_provider_search(folders: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """redpc 2026-10-09: a profile past the mind's entry budget stopped every name said alone with
    «file_search_incomplete» before any file.open. The cut walk proves nothing: a name lying directly in no folder the
    provider is handed goes to the provider, whose own search never opens one of two and says when it was cut."""

    monkeypatch.setattr(known_folders, "_SEARCH_ENTRIES", 1)
    assert known_folders.located_files("nada.jpg") is None
    decision = _step("abrir el archivo nada.jpg", GALLERY)
    assert decision["operation"] == "file.open"
    assert decision["arguments"] == {"folder": "documents", "name": "nada.jpg", "application": "Fotos"}


def test_a_walk_cut_short_never_opens_the_file_the_provider_is_handed(folders: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Counter-case: Documentos\\solo.png lies in the folder the provider is handed, which opens it without looking
    further; with the walk cut short, a second «solo.png» elsewhere is not ruled out, so nothing is opened."""

    (folders.parent / "solo.png").write_bytes(b"x")
    monkeypatch.setattr(known_folders, "_SEARCH_ENTRIES", 1)
    decision = _step("abrir el archivo solo.png", GALLERY)
    assert decision["operation"] == "none" and decision["code"] == "file_not_opened:file_search_incomplete"


@pytest.mark.parametrize(
    ("error", "cause", "said"),
    [("file_ambiguous", "file_ambiguous", "más de un archivo"), ("file_not_found", "file_not_found", "no encontré el archivo"),
     ("app_file_not_accepted", "app_file_not_accepted", "Windows no tiene a «Fotos»"),
     # cu-v3-archivo-empaquetado (live v3-15/v3-17): Fotos is listed for .jpg and the shell did not hand it the file:
     # the cause says so, never that Windows does not list it.
     ("app_file_activation_failed", "app_file_activation_failed",
      "«Fotos» abre archivos como «paisaje.jpg», pero Windows no logró entregárselo"),
     ("file_open_not_verified", "other", "no pude abrir")],
)
def test_a_file_not_opened_is_said_never_searched_for_in_the_window(
    folders: Path, error: str, cause: str, said: str,
) -> None:
    """Counter-case: two files with the name, none, or an application that takes none: the cause is said; the engine
    never clicks the gallery, types in its search or opens the file again."""

    failed = [{"operation": "file.open", "folder": "documents", "name": "paisaje.jpg", "ok": False, "error": error}]
    decision = _step("abrir el archivo paisaje.jpg", GALLERY, failed)
    assert decision["operation"] == "none" and decision["code"] == f"file_not_opened:{cause}"
    assert said in str(decision["reason"])
    assert (cause == "app_file_not_accepted") == ("no tiene a" in str(decision["reason"]))


def test_a_file_opened_is_never_opened_again(folders: Path) -> None:
    opened = [{"operation": "file.open", "ok": True, "windowTitle": "paisaje.jpg", "processId": 7}]
    assert _step(f"abrir el archivo {folders / 'paisaje.jpg'}", GALLERY, opened)["operation"] == "none"


def test_a_path_outside_the_known_folders_or_an_unknown_application_opens_nothing(folders: Path) -> None:
    """Counter-cases (safety): nothing outside the person's known folders is opened, and an application that is not
    installed is never guessed."""

    outside = _step("abrir el archivo C:\\Windows\\System32\\drivers\\etc\\hosts.txt", GALLERY)
    assert outside["operation"] == "none" and outside["code"] == "file_not_opened:file_not_found"
    unknown = _step(f"abrir el archivo {folders / 'paisaje.jpg'}", GALLERY, application="Lightroom Classic")
    assert unknown["operation"] == "none" and unknown["code"] == "file_not_opened:app_not_found"


def test_a_route_said_still_opens_the_file_through_the_dialog(folders: Path) -> None:
    """Counter-case: «… desde Archivo > Abrir» names the window's own dialog: the route, the name field and Abrir."""

    mission = missions.mission_request(
        "abrime el archivo prueba.png que esta en Documentos\\baxy-prueba-v3, desde Archivo > Abrir del Bloc de notas",
        APPS,
    )
    assert mission is not None
    goals = [step.goal for step in mission.steps]
    assert goals == ["hacer clic en archivo", "hacer clic en abrir",
                     f"poner nombre de archivo en {folders / 'prueba.png'}", "hacer clic en abrir"]
    assert mission.steps[-1].success_check == "title:prueba"


# ------------------------------------------------------------ revisión adversarial de la rama


def test_the_window_of_the_application_proves_the_file_only_after_its_file_open(folders: Path) -> None:
    """Finding 2: «abrí notas.txt en el bloc de notas» with the Bloc de notas on another file, and «abre foto.png en
    fotos» with the gallery titled «Fotos»: the stem is in the application's own window, so the check asks for the
    sub-goal's own file.open too."""

    (folders / "notas.txt").write_bytes(b"x")
    for said, stem in (("abri notas.txt en el bloc de notas", "notas"), ("abre foto.png en fotos", "foto")):
        mission = missions.mission_request(said, APPS)
        assert mission is not None and mission.success_check == f"title:{stem}&{OPENED}", said


@pytest.mark.parametrize(
    ("said", "application", "name"),
    [("abri discord y despues abri foto.png", "Discord", "foto.png"),
     ("abri la terminal y abri notas.txt", "Terminal", "notas.txt")],
)
def test_an_application_opened_by_its_own_order_is_opened_before_the_file(
    folders: Path, said: str, application: str, name: str,
) -> None:
    """Finding 3: the first order was lost (one mission «abrir el archivo» in Discord, never opened). The application
    is opened first; the file then goes to it only if Windows lists it to open that type (provider)."""

    (folders / "notas.txt").write_bytes(b"x")
    mission = missions.mission_request(said, APPS)
    assert mission is not None
    assert [(step.application, step.goal) for step in mission.steps] == [
        (application, f"abrir {application}"), (application, f"abrir el archivo {folders / name}")]


def test_a_file_not_opened_reaches_the_final_with_its_cause() -> None:
    """Finding 4: the stop says why (both languages), and the step is never named by its operation."""

    observed = {
        "goal": "abrir el archivo dup.png", "application": "Fotos", "reached": False,
        "stoppedBy": "computer_use_file_not_opened", "fileNotOpened": "file_ambiguous",
        "steps": [{"operation": "file.open", "ok": False, "error": "file_not_found", "name": "dup.png"}],
    }
    spanish = cu_projection.project_seen(observed, "es")
    english = cu_projection.project_seen(observed, "en")
    assert spanish["stoppedBecause"] == "hay más de un archivo «dup.png» en tus carpetas y no sé cuál abrir"
    assert "more than one file" in str(english["stoppedBecause"]) and "dup.png" in str(english["stoppedBecause"])
    assert spanish["stepsFailed"] == ["intentó abrir «dup.png»"]
    assert not any("file.open" in str(value) for value in (*spanish.values(), *english.values()))
    chained = {
        "goal": "abrir Discord; luego abrir el archivo D:\\Perfil\\Documentos\\foto.png", "reached": False,
        "stoppedBy": "computer_use_file_not_opened", "fileNotOpened": "app_file_not_accepted", "steps": [],
        "subgoals": [{"goal": "abrir Discord", "application": "Discord", "reached": True},
                     {"goal": "abrir el archivo D:\\Perfil\\Documentos\\foto.png", "application": "Discord",
                      "reached": False}],
    }
    assert cu_projection.project_seen(chained, "es")["stoppedBecause"] == (
        "Windows no tiene a «Discord» entre las aplicaciones que abren archivos como «foto.png»")
    # The floor final says it too.
    assert "más de un archivo" in cu_finals.floor_sentence(observed, False, False)


def test_the_open_dialog_said_as_the_means_is_used(folders: Path) -> None:
    """Finding 5 (t-file-4 «…, usa el Abrir de Paint»): an explicit way to do it is never ignored. Counter-case: with
    no means said, the shell opens it."""

    said = "abre foto.png en paint, esta en documentos\\baxy-prueba-v3, usa el abrir de paint"
    mission = missions.mission_request(said, APPS)
    assert mission is not None
    assert [step.goal for step in mission.steps] == [
        "abrir el dialogo de abrir", f"poner nombre de archivo en {folders / 'foto.png'}", "hacer clic en abrir"]
    assert mission.steps[-1].success_check == "title:foto"
    plain = missions.mission_request("abre foto.png en paint, esta en documentos\\baxy-prueba-v3", APPS)
    assert plain is not None and plain.goal == f"abrir el archivo {folders / 'foto.png'}"
