"""What the model reads of the tools (the prefix, BAXY Renew al máximo P2.6): the installed applications offered to
app_open leave out what nobody opens as an application."""
from pathlib import Path

from test_mind_final import _mind


def _installed(tmp_path: Path, names: list[str]) -> str:
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [{"name": "app.open", "description": "Open an app.", "argumentsSchema": {
        "type": "object", "properties": {"appId": {"type": "string"}, "place": {"type": "string"}}}}],
        "applicationCatalog": {"names": names}})
    tool = next(t for t in mind.tools if t["function"]["name"] == "app_open")["function"]
    # The places are named in the description as the model learnt them (taking them out of it made the model open
    # msconfig for «abre la configuración de sonido», e2e E014, 2026-10-22) and in the argument.
    assert tool["description"].count("«Steam» (") == 1
    return tool["description"].split("Installed applications (use one of these names as appId): ")[1]


def test_the_installed_applications_leave_out_uninstallers_help_manuals_and_web_pages_by_the_shape_of_their_name(
        tmp_path: Path) -> None:
    kept = ["Revo Uninstaller Pro", "Bloc de notas", "ESET Online Scanner", "Wallpaper Engine", "iLok License Manager",
            "Navegador Web", "Licensing Settings"]
    left = ["Uninstall Foo 2026", "UninstallBar", "Un-install Baz Pro", "Desinstalar Qux", "Qux Service Uninstall",
            "7-Zip Help", "Ayuda WinRAR", "Foo Help File", "HWiNFO Manual", "Python 3.13 Manuals (64-bit)",
            "Bar User Guide en", "Documentación de Foo", "CMake Documentation", "Dokumentation", "SharpKeys FAQ",
            "Git Release Notes", "Foo What's New", "Qué hay de nuevo en la última versión", "license",
            "License (English)", "Foo License Agreement", "Foo skin format reference", "VideoLAN Website",
            "Foo en la Web", "wxWidgets on the Web", "Configuration tutorial (online)"]
    listed = _installed(tmp_path, kept + left)
    assert listed == "; ".join(kept) + "."
