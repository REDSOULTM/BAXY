"""Aid «said_file_name», I7 (AMD A2, 06-11, L6-ES2: 3 of 3): «crea un archivo llamado nota.txt en la carpeta …\\no-existe»
became file_write to «…\\no-existe.txt», a name nobody said, and the reply told it as the file asked for. Only the form is
compared: the person's words name a file (a name with an extension) and the path writes another of the same extension
that neither they nor any result said. Nothing is written; the result says both names, as data, and the model decides
again, once per turn."""
import json
from pathlib import Path

from test_mind_final import _call, _mind, _say

DONE = json.dumps({"status": "completed", "verification": "readback"})
ASKED = r"Crea recado.txt en la carpeta C:\Users\ana\Pruebas\sin-crear con el texto hola"


def _not_run(mind) -> list[dict]:
    told = []
    for message in mind.conversation:
        if message["role"] == "tool" and str(message.get("content")).startswith("{"):
            body = json.loads(str(message["content"]).split("\n", 1)[0])
            if body.get("status") == "not_run":
                told.append(body)
    return told


def test_a_path_that_writes_a_file_nobody_named_goes_back_with_the_name_said(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("file_write", {"path": r"C:\Users\ana\Pruebas\sin-crear.txt", "text": "hola"}),
                               _call("file_write", {"path": r"C:\Users\ana\Pruebas\sin-crear\recado.txt", "text": "hola"}),
                               _say("Listo.")])
    step = mind.decide(1, ASKED)
    assert step["kind"] == "action" and step["arguments"]["path"].endswith(r"sin-crear\recado.txt")
    told = _not_run(mind)
    assert len(told) == 1 and told[0]["said"] == ["recado.txt"] and told[0]["written"] == "sin-crear.txt"


def test_it_is_told_once_and_the_models_next_write_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    wrong = _call("file_write", {"path": r"C:\Users\ana\Pruebas\sin-crear.txt", "text": "hola"})
    mind, _ = _mind(tmp_path, [wrong, wrong])
    assert mind.decide(1, ASKED)["arguments"]["path"].endswith("sin-crear.txt")
    assert len(_not_run(mind)) == 1


def test_a_name_the_person_said_is_written(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("file_write", {"path": "Documentos/recado.txt", "text": "hola"})])
    assert mind.decide(1, "guarda hola en recado.txt de mis documentos")["operation"] == "file_write"
    assert _not_run(mind) == []


def test_a_name_chosen_when_the_person_named_no_file_is_written(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("file_write", {"path": "Escritorio/lista_compra.txt", "text": "pan"})])
    assert mind.decide(1, "haz un archivo en el escritorio con la lista de la compra: pan")["operation"] == "file_write"
    assert _not_run(mind) == []


def test_a_name_of_another_kind_said_does_not_count(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("file_write", {"path": "Escritorio/enlaces.txt", "text": "ejemplo.org"})])
    assert mind.decide(1, "apunta ejemplo.org en un archivo del escritorio")["operation"] == "file_write"
    assert _not_run(mind) == []


def test_a_name_a_result_showed_is_written(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    found = json.dumps({"status": "completed", "verification": "output_only",
                        "observed": {"files": [{"name": "recado-2.txt", "path": "Documentos/recado-2.txt"}]}})
    mind, _ = _mind(tmp_path, [_call("file_find", {"query": "recado"}),
                               _call("file_write", {"path": "Documentos/recado-2.txt", "text": "hola", "append": True})])
    assert mind.decide(1, "añade hola a recado.txt")["operation"] == "file_find"
    assert mind.continue_turn(2, found)["operation"] == "file_write"
    assert _not_run(mind) == []


def test_without_the_aid_it_is_written(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, _ = _mind(tmp_path, [_call("file_write", {"path": r"C:\Users\ana\Pruebas\sin-crear.txt", "text": "hola"})])
    assert mind.decide(1, ASKED)["operation"] == "file_write"
