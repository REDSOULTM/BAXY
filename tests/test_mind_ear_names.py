"""Aid «ear_known_names» (G11, uso real 2026-11-03: «Shbeomac» and «HBO Mac» heard for HBO Max, a service and not an
installed application): the ear's hotwords are the installed applications and games the model is shown and the
applications and services BAXY knows by name (app_aliases.v1.json); the installed ones stay apart for the aids that
read them."""
import json
from pathlib import Path

from baxy_mind.mind import _DATA

from test_mind_final import _mind

CATALOG = {"capabilities": [], "applicationCatalog": {"names": ["Spotify", "Bloc de notas"]},
           "gameCatalog": {"entries": [{"name": "Hollow Knight", "appId": "367520", "provider": "steam"}]}}
KNOWN = list(json.loads((_DATA / "app_aliases.v1.json").read_text(encoding="utf-8"))["applications"])


def test_the_ear_hears_the_services_baxy_knows_beside_the_installed_names(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [])
    mind.configure(CATALOG)
    assert mind.names == ["Spotify", "Bloc de notas", "Hollow Knight"]  # what «unopened_app» reads: installed only
    assert mind.heard[:3] == mind.names
    assert {"HBO Max", "Disney+", "Prime Video", "Netflix"} <= set(mind.heard)
    assert set(mind.heard) == set(mind.names) | set(KNOWN)
    assert len(mind.heard) == len(set(mind.heard))  # Spotify, known and installed, once


def test_without_the_aid_the_ear_hears_only_the_installed_names(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, _ = _mind(tmp_path, [])
    mind.configure(CATALOG)
    assert mind.heard == mind.names == ["Spotify", "Bloc de notas", "Hollow Knight"]
