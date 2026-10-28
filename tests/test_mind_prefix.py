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


def test_the_raw_pointer_tool_tells_the_model_it_neither_drags_nor_draws(tmp_path: Path) -> None:
    # Feria, caso 18: asked to draw lines on a drawing canvas, the model said it could draw and sent clicks on one point;
    # no tool holds a button down while moving (dragging was retired from the catalog as a declared limit).
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [{"name": "input.pointer.control", "description": "Click.", "argumentsSchema": {
        "type": "object", "properties": {"action": {"type": "string"}}, "required": ["action"]}}]})
    tool = next(t for t in mind.tools if t["function"]["name"] == "input_pointer_control")["function"]
    assert "It cannot drag or draw" in tool["description"]
    # Only dragging with the mouse is the limit: a whole window still moves with its own tools.
    assert "no tool drags or draws with the mouse (moving a whole window is window_move" in tool["description"]


def test_the_document_tool_says_how_much_text_fits_in_one_decision(tmp_path: Path) -> None:
    # Review R6 and PC-L: a decision holds 768 tokens (DECISION_TOKENS), about 380 Spanish words in one call at ~2
    # tokens a word (measured on the notebook); the description says a conservative 350, not the 250 of 512 tokens.
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [{"name": "office.document.create", "description": "Create.", "argumentsSchema": {
        "type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}}]})
    tool = next(t for t in mind.tools if t["function"]["name"] == "office_document_create")["function"]
    assert "about 350 words of text at most" in tool["description"]
    assert "250 words" not in tool["description"]


def test_the_document_tool_says_it_does_not_open_word_and_how_to_show_the_file(tmp_path: Path) -> None:
    # Feria NB, humo f74f0d0eb: asked to open Word and write a long story there, the model opened Word, clicked its
    # blank document and typed ~50 words in 55 s; nothing told it that office_document_create writes the file without
    # opening Word, nor how to show it after (file_open finds it in Documents\BAXY), nor that the typing tool is not
    # the way to compose a text for Word.
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [{"name": name, "description": "Do.", "argumentsSchema": {
        "type": "object", "properties": {"title": {"type": "string"}}}}
        for name in ("office.document.create", "input.text.type", "app.open")]})
    tools = {t["function"]["name"]: t["function"]["description"] for t in mind.tools}
    assert "written without opening Word" in tools["office_document_create"]
    assert "file_open, folder documents and name «BAXY\\» followed by the result's name" in tools[
        "office_document_create"]
    assert "a text to compose for Word (a story, a letter, an essay: use office_document_create" in tools[
        "input_text_type"]
    assert "open it first (app_open) and write the stated text there (a text you compose for Word goes to " \
           "office_document_create)" in tools["input_text_type"]
    assert "opening Word to write a text you compose (use office_document_create" in tools["app_open"]


def test_the_power_tool_says_what_each_action_does_to_the_pc(tmp_path: Path) -> None:
    # R6-PC-6: in the long session, with history, signing out came out as system_power shutdown in 4 of 6 sessions; the
    # action's five values reached the model bare and the tool's «Use when» named every transition but signing out. In
    # Bypass (and in normal mode, by the identity) a power transition runs unasked: what tells the values apart is what
    # the model reads.
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [{"name": "system.power", "description": "Power.", "argumentsSchema": {
        "type": "object", "properties": {"action": {"type": "string", "enum": [
            "lock", "restart", "shutdown", "signout", "sleep"]}}, "required": ["action"]}}]})
    tool = next(t for t in mind.tools if t["function"]["name"] == "system_power")["function"]
    action = tool["parameters"]["properties"]["action"]
    meaning = action["description"]
    for value in action["enum"]:
        assert f"{value}:" in meaning
    assert "signout: the person's Windows session ends" in meaning and "the PC stays on" in meaning
    assert "shutdown: the PC turns off" in meaning
    assert "cierra sesión" in tool["description"]
