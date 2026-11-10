"""Los textos de licencia que el paquete debe entregar están en licenses/ y son los de cada licencia (encargo LIC1)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

LICENSES = Path(__file__).resolve().parents[1] / "licenses"
# Una frase que sólo está en el texto completo: un fichero truncado o equivocado no pasa.
TEXTS = {
    "Apache-2.0.txt": "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION",
    "Qwen3.5-4B-LICENSE.txt": "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION",
    "CC-BY-4.0.txt": "Attribution 4.0 International Public License",
    "CC-BY-SA-4.0.txt": "Attribution-ShareAlike 4.0 International Public License",
    "OpenRAIL-M-Supertonic-3.txt": "Attachment A",
    "Inter-OFL.txt": "The Inter Project Authors",
    "JetBrainsMono-OFL.txt": "The JetBrains Mono Project Authors",
    "ChakraPetch-OFL.txt": "The Chakra Petch Project Authors",
    "dotnet-LICENSE.txt": ".NET Foundation",
    "WebView2-LICENSE.txt": "Microsoft Corporation",
    "WebView2-NOTICE.txt": "NOTICES",
    "Python-Licenses-and-Acknowledgements.txt": "Licenses and Acknowledgements for Incorporated Software",
}


@pytest.mark.parametrize(("name", "phrase"), TEXTS.items())
def test_the_full_text_is_there(name: str, phrase: str) -> None:
    text = (LICENSES / name).read_text(encoding="utf-8", errors="replace")
    assert phrase in text


def test_openrail_keeps_its_thirteen_use_restrictions() -> None:
    text = (LICENSES / "OpenRAIL-M-Supertonic-3.txt").read_text(encoding="utf-8")
    attachment = text[text.rindex("Attachment A") :]
    assert re.findall(r"^\(([a-z])\)", attachment, re.MULTILINE) == list("abcdefghijklm")


def test_every_listed_file_exists_and_every_text_has_its_source() -> None:
    readme = (LICENSES / "README.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| `([^`]+)` \| .+ \| <(https://[^>]+)> \| `([0-9a-f]{64})` \|$", readme, re.MULTILINE)
    listed = {name for name, _, _ in rows}
    notices = {
        "README.md", "ATRIBUCIONES_MODELOS.md", "FUENTES.md", "CRATES_RUST.md", "PALABRA_DE_ACTIVACION.md", "PRIVACIDAD.md",
        "FUENTES_GPL.md",  # the public repository's offer for its history
    }
    on_disk = {path.name for path in LICENSES.iterdir()} - notices
    assert listed == on_disk
    assert set(TEXTS) <= listed


def test_the_source_notice_names_a_fixed_commit_and_eigens_source() -> None:
    sources = (LICENSES / "FUENTES.md").read_text(encoding="utf-8")
    assert "142807252687d81b40d6315f23470a1512a00de3" in sources
    assert "eigen-5.0.1.tar.gz" in sources
    assert "e9c326dc8c05cd1e044c71f30f1b2e34a6161a3b6ecf445d56b53ff1669e3dec" in sources


def test_the_package_gets_the_licenses_folder() -> None:
    build = (LICENSES.parent / "scripts" / "build_steam.ps1").read_text(encoding="utf-8")
    assert "Join-Path $repo 'licenses\\*'" in build


def test_the_notices_say_what_left_and_what_stays() -> None:
    notices = (LICENSES.parent / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "el barrido de los binarios de 1.3.0 no halló código GPL ni LGPL" in notices
    assert "### 0. Lo que se quitó en 1.3.0, y Eigen (MPL-2.0), que queda" in notices
    assert "1.2.0 y 1.2.1, ya distribuidas, siguen llevando eSpeak NG" in notices
    assert "releases/tag/fuentes-terceros" in notices
    assert "**Eigen, MPL-2.0:**" in notices


# LIC2 (owner, 2026-11-08): one legal name wherever BAXY says who gives it, and the same terms in the installer's agreement
# and in Steam's EULA: any use, no restriction of the developer's own, the voice's OpenRAIL-M use restrictions passed on
# to the user (its paragraph 5 requires it), and a privacy section that names what leaves the PC.
LEGAL_NAME = "Emmanuel Antonio Villacura Arancibia"
AGREEMENTS = {
    "src/Baxy.Installer/Assets/license/en.txt": "en",
    "src/Baxy.Installer/Assets/license/es.txt": "es",
    "documentacion/steam/EULA.md": "en es",
    "documentacion/itchio/LEGAL.md": "es en",  # LEG1: itch.io's copy is an agreement like the other two
}


def _repo_text(path: str) -> str:
    return " ".join((LICENSES.parent / path).read_text(encoding="utf-8").split())


@pytest.mark.parametrize("path", ["LICENSE", "THIRD_PARTY_NOTICES.md", "licenses/PRIVACIDAD.md", *AGREEMENTS])
def test_one_legal_name_says_who_gives_baxy(path: str) -> None:
    text = _repo_text(path)
    assert LEGAL_NAME in text
    assert "Emmanuel Villacura" not in text


@pytest.mark.parametrize("path", sorted(AGREEMENTS))
def test_the_agreements_allow_any_use_and_pass_on_the_voices_restrictions(path: str) -> None:
    text = _repo_text(path)
    languages = AGREEMENTS[path].split()
    for language in languages:
        assert {"en": "for any purpose, personal or commercial", "es": "para cualquier fin, personal o comercial"}[language] in text
        assert {"en": "To provide medical advice and medical results interpretation;",
                "es": "Para dar consejo médico o interpretar resultados médicos;"}[language] in text
    for words in ("personal use only", "for your personal use", "uso personal solamente", "para tu uso personal"):
        assert words not in text
    # The thirteen use restrictions of Attachment A, (a) to (m), once per language.
    assert len(re.findall(r"(?:^| )\(([a-m])\) ", text)) == 13 * len(languages)


# Each service that receives something when the person asks BAXY for it, as licenses/PRIVACIDAD.md names it, and GeoNames,
# which BAXY carries inside and which receives nothing.
SERVICES = ("MET Norway", "ipwho.is", "DuckDuckGo", "Wikipedia", "Photon", "OpenStreetMap", "Frankfurter", "YouTube",
            "Hugging Face", "GeoNames")


def test_the_privacy_policy_names_what_leaves_the_pc_and_goes_with_the_package() -> None:
    policy = _repo_text("licenses/PRIVACIDAD.md")
    for service in SERVICES:
        assert policy.count(service) >= 2, service  # in Spanish and in English
    assert "El desarrollador no recibe nada tuyo" in policy
    assert "The developer receives nothing of yours" in policy
    assert "GeoNames no recibe nada" in policy
    assert "aceptados por el desarrollador el 2026-11-08" in policy
    assert "no la ha revisado un abogado" in policy
    assert "`PRIVACIDAD.md`" in (LICENSES / "README.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("path", sorted(AGREEMENTS))
def test_the_agreements_privacy_names_the_services_and_points_to_the_policy(path: str) -> None:
    text = _repo_text(path)
    for language in AGREEMENTS[path].split():
        assert {"en": "the developer receives nothing of yours", "es": "el desarrollador no recibe nada tuyo"}[language] in text
    for service in SERVICES[:-1]:
        assert service in text, service
    assert "licenses/PRIVACIDAD.md" in text
    assert "BAXY does not send what you say or your files to any service" not in text
    assert "BAXY no envía lo que le dices ni tus archivos a ningún servicio" not in text


def test_the_notices_name_the_services_of_today() -> None:
    notices = (LICENSES.parent / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    services = notices[notices.index("## Servicios en la red que BAXY consulta al usarse"):notices.index("## Historia pública")]
    assert "| Photon de komoot, con datos de OpenStreetMap" in services
    assert "**Nominatim ya no se usa (LIC2):**" in services
    assert "| YouTube (elegir el primer vídeo de una búsqueda)" in services
    assert "**Riesgo aceptado por el dueño**, pendiente del permiso de DuckDuckGo" in services
    assert "| Hugging Face (modelo ajustado opcional)" in services
    assert "[`licenses/PRIVACIDAD.md`](licenses/PRIVACIDAD.md)" in services


# INT12: Settings → Model → Local (modelos-abiertos) sends what the person types to Hugging Face's search and downloads
# Ollama's ZIP from GitHub, which brings «GPU library dependencies for Nvidia» (ollama/docs/windows.mdx, read 2026-11-08):
# the policy, the agreements and the notices say so, and Settings does not call that download «MIT» alone.
def test_settings_local_models_are_in_the_policy_the_agreements_and_the_notices() -> None:
    policy = _repo_text("licenses/PRIVACIDAD.md")
    assert "| Buscar un modelo local (sólo si lo haces en Ajustes → Modelo → Local) | Hugging Face |" in policy
    assert "| Searching for a local model (only if you do it in Settings → Model → Local) | Hugging Face |" in policy
    assert policy.count("| GitHub |") == 4  # Ollama and, since INT19, updating BAXY, in each language
    for path in AGREEMENTS:
        text = _repo_text(path)
        for language in AGREEMENTS[path].split():
            assert {"en": "and your IP to GitHub to download Ollama", "es": "y tu IP a GitHub para bajar Ollama"}[language] in text
    notices = (LICENSES.parent / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "| Hugging Face (buscar e instalar un modelo local)" in notices
    assert "| GitHub (ZIP independiente de Ollama, para un modelo local)" in notices
    settings = (LICENSES.parent / "src/Baxy.FieldUi/src/components/panels/SettingsPanel.tsx").read_text(encoding="utf-8")
    assert "licencia MIT)" not in settings and "MIT license)" not in settings
    assert "trae bibliotecas CUDA de NVIDIA con su propia licencia" in settings


def test_the_rust_crates_file_lists_what_the_wheels_declare() -> None:
    crates = (LICENSES / "CRATES_RUST.md").read_text(encoding="utf-8")
    assert "Unicode-3.0" in crates
    assert "Zlib" in crates
    assert "`pydantic_core`" in crates
    assert "`jiter`" in crates


def test_numpys_notices_the_wheel_does_not_carry_are_here() -> None:
    assert "Redistribution" in (LICENSES / "pocketfft-LICENSE.md").read_text(encoding="utf-8")
    msun = (LICENSES / "numpy-msun-NOTICE.txt").read_text(encoding="utf-8")
    assert "David Schultz" in msun
    assert "Sun Microsystems" in msun


def test_no_notice_keeps_a_file_the_package_no_longer_has() -> None:
    readme = (LICENSES / "README.md").read_text(encoding="utf-8")
    assert "sherpa-onnx-c-api" not in readme
    assert "FUENTES_GPL" not in readme
    assert "FUENTES_GPL" not in (LICENSES.parent / "scripts" / "build_steam.ps1").read_text(encoding="utf-8")


def test_the_wake_word_notices_are_of_v7a_and_its_training_is_declared() -> None:
    # DET1: the official detector is k6r-v7a since 1.3.2 («sin la serie»); what it learned from is in PALABRA_DE_ACTIVACION.md.
    notices = (LICENSES.parent / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    models = (LICENSES / "ATRIBUCIONES_MODELOS.md").read_text(encoding="utf-8")
    wake = (LICENSES / "PALABRA_DE_ACTIVACION.md").read_text(encoding="utf-8")
    assert "`baxy-wake-k6r-v7a` desde 1.3.2" in notices
    assert "| Palabra de activación `baxy-wake-k6r-v7a`" in notices
    assert "`licenses/PALABRA_DE_ACTIVACION.md`" in notices
    assert "the `baxy-wake-k6r-v7a` package since 1.3.2" in models
    assert "CC BY-SA 4.0" in wake
    assert "L2-ARCTIC" in wake


def test_the_texts_say_the_package_carries_the_stock_model_and_the_tuned_one_is_downloaded_on_request() -> None:
    # QWB2 (owner's order of 2026-11-07): the package carries Qwen3.5-4B as Unsloth publishes it; BAXY's tuned model is
    # downloaded only when the person asks, from a URL pinned to its commit and kept only with its SHA-256.
    root = LICENSES.parent
    tuned_url = ("https://huggingface.co/REDSOULTM/BAXY-Qwen3.5-4B-GGUF/resolve/da66d8bbb0b90ae15fc54cb4386370a4a471d54f/"
                 "BAXY-Qwen3.5-4B-c4-Q4_K_M.gguf")
    tuned_sha = "2c445631782a5c27b9948369e9432309528688b9b761fce56586d796ea2f57c7"
    stock_sha = "00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4"
    notices = (root / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    models = (LICENSES / "ATRIBUCIONES_MODELOS.md").read_text(encoding="utf-8")
    for text in (notices, models):
        assert tuned_url in text and tuned_sha in text and stock_sha in text
        assert "e87f176479d0855a907a41277aca2f8ee7a09523" in text
    assert "se descarga si la persona lo pide" in notices
    assert "Los paquetes desde 1.2.0 llevan" not in notices
    assert "downloaded only if the person asks" in models
    assert "`BAXY-Qwen3.5-4B-ft-c3-c4c2_1-sA-Q4_K_M.gguf`: **changed by the BAXY project.**" not in models
    for path in (root / "documentacion" / "steam" / "EULA.md", root / "src" / "Baxy.Installer" / "Assets" / "license" / "es.txt",
                 root / "src" / "Baxy.Installer" / "Assets" / "license" / "en.txt"):
        text = path.read_text(encoding="utf-8")
        assert "es un ajuste de Qwen3.5-4B" not in text and "is a fine-tune of Qwen3.5-4B" not in text, path
        assert "Unsloth" in text, path


# INT11 (owner's order of 2026-11-08, ~01:45): BAXY includes only the stock Qwen3.5-4B; the tuned model is an unofficial
# extra its author publishes apart on Hugging Face, not part of the official product or of what is sold, and optional. No
# text says that offering it apart removes the risk with Anthropic (its training used data generated with Claude).
UNOFFICIAL_EXTRA = {
    "en": ("only the stock Qwen3.5-4B", "unofficial extra", "not part of the official product or of what is sold"),
    "es": ("sólo Qwen3.5-4B de serie", "extra no oficial", "no forma parte del producto oficial ni de lo que se vende"),
}
NEVER_ABOUT_THE_RISK = ("elimina el riesgo", "elimina ese riesgo", "sin riesgo con Anthropic", "eliminates the risk",
                        "removes the risk", "no risk with Anthropic")
TEXTS_WITH_THE_MODEL = {
    "THIRD_PARTY_NOTICES.md": ("es",),
    "licenses/ATRIBUCIONES_MODELOS.md": ("en",),
    "documentacion/steam/EULA.md": ("en", "es"),
    "src/Baxy.Installer/Assets/license/en.txt": ("en",),
    "src/Baxy.Installer/Assets/license/es.txt": ("es",),
    "documentacion/itchio/LEGAL.md": ("en", "es"),
}


@pytest.mark.parametrize("path", sorted(TEXTS_WITH_THE_MODEL))
def test_the_tuned_model_is_an_unofficial_extra_and_nothing_says_the_risk_is_gone(path: str) -> None:
    text = " ".join((LICENSES.parent / path).read_text(encoding="utf-8").split())
    for language in TEXTS_WITH_THE_MODEL[path]:
        for words in UNOFFICIAL_EXTRA[language]:
            assert words in text, (language, words)
    for words in NEVER_ABOUT_THE_RISK:
        assert words not in text, words


STORE_TEXTS = ("documentacion/STEAM_PUBLICACION.md", "documentacion/itchio/PAGINA.md")


@pytest.mark.parametrize("path", STORE_TEXTS)
def test_the_store_texts_call_the_tuned_model_an_unofficial_extra_and_the_stock_one_not_baxys_own(path: str) -> None:
    # INT11, after a blind review: the store pages kept «a fine-tune made by the BAXY project», «BAXY's optional fine-tune» and
    # «Piensa con un modelo propio» (the package carries the stock model, unchanged).
    text = " ".join((LICENSES.parent / path).read_text(encoding="utf-8").replace("\n> ", "\n").split())
    assert "extra no oficial" in text and "unofficial extra" in text
    for words in ("Piensa con un modelo propio", "thinks with its own model", "made by the BAXY project)",
                  "el ajuste opcional de BAXY", "BAXY's optional fine-tune", "modelo ajustado de BAXY, una descarga opcional"):
        assert words not in text, words


# LEG1 (2026-11-09, REV_LEGAL LEG-01): itch.io's agreement, the two store pages and the README still said that BAXY sends
# nothing of the person's to any service, while the code sends the query to DuckDuckGo (WebBrowserAdapter.cs:871), the place's
# coordinates and the IP to MET Norway (MetNorwayWeatherAdapter.cs:34), the IP to ipwho.is (PublicPlaceLocator.cs:33), and so
# on. Every public text says what the installer's agreement, Steam's EULA and licenses/PRIVACIDAD.md say: who receives what,
# and when. The phrase cannot come back to any of them.
PUBLIC_PRIVACY = {
    "src/Baxy.Installer/Assets/license/en.txt": {"en": "5. Privacy "},
    "src/Baxy.Installer/Assets/license/es.txt": {"es": "5. Privacidad "},
    "documentacion/steam/EULA.md": {"en": "5. Privacy ", "es": "5. Privacidad "},
    "documentacion/itchio/LEGAL.md": {"es": "5. Privacidad ", "en": "5. Privacy "},
    "documentacion/STEAM_PUBLICACION.md": {"es": "**Tuyo y privado.**", "en": "**Yours and private.**"},
    "documentacion/itchio/PAGINA.md": {"es": "**Tuyo y privado.**", "en": "**Yours and private.**"},
    "README.md": {"es": "**Local y privado.**"},
}
PUBLIC_PRIVACY_CASES = [(path, language) for path in sorted(PUBLIC_PRIVACY) for language in PUBLIC_PRIVACY[path]]
SENDS_NOTHING = re.compile(
    r"no env[ií]a lo que le dices ni tus archivos|send what you say or your files to any service"
    r"|no manda nada tuyo fuera|sends nothing of yours out|sin enviar datos a ning[uú]n lado"
    r"|no env[ií]a contenido de la persona a ning[uú]n lado", re.IGNORECASE)
WHAT_LEAVES = {"es": r"lo que pides buscar, a .+? para bajar Ollama", "en": r"what you ask to search for, to .+? to download Ollama"}


def _public(path: str) -> str:
    raw = LICENSES.parent.joinpath(path).read_bytes().decode("utf-8")
    return " ".join(raw.replace("\r\n", "\n").replace("\n> ", "\n").split())


def _privacy(path: str, language: str) -> str:
    """The privacy section or paragraph of a public text, up to the next title."""
    rest = _public(path).split(PUBLIC_PRIVACY[path][language], 1)[1]
    return re.split(r" 6\. | \*\*| ## ", rest, maxsplit=1)[0].rstrip(" #>")


@pytest.mark.parametrize("path", sorted({*PUBLIC_PRIVACY, "licenses/PRIVACIDAD.md", "THIRD_PARTY_NOTICES.md"}))
def test_no_public_text_says_that_baxy_sends_nothing_to_any_service(path: str) -> None:
    assert SENDS_NOTHING.search(_public(path)) is None


@pytest.mark.parametrize("path, language", PUBLIC_PRIVACY_CASES)
def test_every_public_text_names_who_receives_what_and_points_to_the_policy(path: str, language: str) -> None:
    privacy = _privacy(path, language)
    for service in (*SERVICES[:-1], "GitHub"):
        assert service in privacy, service
    assert "licenses/PRIVACIDAD.md" in privacy
    if path != "README.md":  # the README speaks of «la persona», not to her
        assert {"en": "the developer receives nothing of yours", "es": "el desarrollador no recibe nada tuyo"}[language] in privacy


@pytest.mark.parametrize("path, language", [case for case in PUBLIC_PRIVACY_CASES if case[0] != "README.md"])
def test_every_public_text_lists_what_the_installers_agreement_lists(path: str, language: str) -> None:
    installer = re.search(WHAT_LEAVES[language], _privacy(f"src/Baxy.Installer/Assets/license/{language}.txt", language))
    assert installer is not None
    assert installer.group() in _privacy(path, language)


def test_itchios_privacy_section_is_steams_but_for_how_each_copy_is_updated() -> None:
    steam, itch = "documentacion/steam/EULA.md", "documentacion/itchio/LEGAL.md"
    for position, language in enumerate(("en", "es")):
        of_steam = _privacy(steam, language).replace(UPDATE_AGREEMENT[steam][position], "<update>")
        of_itch = _privacy(itch, language).replace(UPDATE_AGREEMENT[itch][position], "<update>")
        assert "<update>" in of_steam
        assert of_itch == of_steam, language


# LEG1 (LEG-04): the title of a game asked for by its name goes to the Steam store when no installed game bears it
# (SteamLocalAdapter.cs:639-679 to install it, with pieces of the title at :685-700; :826-877 to open its page; the address
# is Steam's «titles» in app_places.v1.json). No text said so. And the code reaches more than the policy listed: a file
# asked for by its address (WindowsFileToolsAdapter.cs:55-62), a ping (WindowsNetworkDiagnosticProvider.cs:95-108), what
# the person's browser or app opens (UserBrowserSurface.cs:722-728), a command the person asks to run (the «network»
# effect of shell.command.run, ProductCatalog.cs:1684), BAXY's parts the installer downloads from GitHub
# (PartFetcher.cs:29-34), and WebView2, which the App itself downloads when Windows lacks it (WebView2Runtime.cs:10-18).
STEAM_STORE = {
    "es": "el título de un juego que pides instalar o ver en la tienda de Steam y que no está entre tus juegos instalados, a "
          "esa tienda (Valve); la página que pides leer o el fichero que pides descargar, a su sitio;",
    "en": "the title of a game you ask to install or to see in the Steam store and that is not among your installed games, "
          "to that store (Valve); the page you ask to read or the file you ask to download, to its site;",
}
POLICY_LEG04 = (
    "| Instalar un juego de Steam por su nombre, o ver su página en la tienda (sólo si no está entre tus juegos instalados) "
    "| La tienda de Steam (Valve) | El título que pides y tu IP; al instalar, si la tienda no tiene un juego con ese título, "
    "también trozos del título (el título sin una de sus palabras, o una palabra sola) "
    "| <https://store.steampowered.com/privacy_agreement/> |",
    "| Installing a Steam game by its name, or seeing its page in the store (only if it is not among your installed games) "
    "| The Steam store (Valve) | The title you ask for and your IP; when installing, if the store has no game with that "
    "title, also pieces of the title (the title without one of its words, or one word alone) "
    "| <https://store.steampowered.com/privacy_agreement/> |",
    "| Una página web concreta, o un fichero que pides descargar de una dirección | El sitio de esa página o de ese fichero |",
    "| A given web page, or a file you ask to download from an address | That page's or that file's site |",
    "| Comprobar si una máquina o un sitio responde (ping) | La máquina o el sitio que nombras |",
    "| Checking whether a machine or a site answers (ping) | The machine or the site you name |",
    "| Abrir un sitio, una búsqueda o un título en tu navegador o en una aplicación (por ejemplo YouTube, Netflix o Steam) |",
    "| Opening a site, a search or a title in your browser or in an app (for example YouTube, Netflix or Steam) |",
    "| Ejecutar un comando en la terminal | Lo que ese comando contacte |",
    "| Running a command in the terminal | Whatever that command contacts |",
    "El instalador de la copia de GitHub baja de GitHub las piezas de BAXY, y de Microsoft, si faltan, WebView2 y el runtime "
    "de Visual C++: GitHub y Microsoft reciben tu IP.",
    "The installer of the copy from GitHub downloads BAXY's parts from GitHub and, if they are missing, WebView2 and the "
    "Visual C++ runtime from Microsoft: GitHub and Microsoft receive your IP.",
    "Las copias de Steam y de itch.io no tienen instalador: las baja su tienda, y si a Windows le falta WebView2, BAXY lo "
    "descarga de Microsoft al arrancar.",
    "The copies from Steam and itch.io have no installer: their store downloads them, and if Windows lacks WebView2, BAXY "
    "downloads it from Microsoft when it starts.",
)


def test_the_store_that_receives_a_games_title_is_the_one_the_policy_names() -> None:
    places = json.loads(LICENSES.parent.joinpath("src/baxy_mind/data/app_places.v1.json").read_bytes())
    asked = [application["titles"]["address"] for application in places["applications"].values() if "titles" in application]
    assert asked and all(address.startswith("https://store.steampowered.com/") for address in asked), asked
    policy = _flat("licenses/PRIVACIDAD.md")
    for words in POLICY_LEG04:
        assert words in policy, words[:70]


@pytest.mark.parametrize("path, language", [case for case in PUBLIC_PRIVACY_CASES if case[0] != "README.md"])
def test_every_public_text_says_that_a_games_title_goes_to_the_steam_store(path: str, language: str) -> None:
    assert STEAM_STORE[language] in _privacy(path, language)


def test_the_readme_names_the_steam_store_and_the_file_that_is_downloaded() -> None:
    privacy = _privacy("README.md", "es")
    assert "el título de un juego que se pide instalar o ver en la tienda de Steam y que no está instalado, a esa tienda" in privacy
    assert "la página que se pide leer o el fichero que se pide descargar, a su sitio" in privacy


# LEG1 (LEG-08): the texts said that something leaves the PC «only when you ask», and the copy from GitHub asks GitHub for
# a new version once at each start, on until the person switches it off (FieldProductChannel.cs:139-158; FieldSettings.cs:91
# «UpdateNotice», true by default; GitHubLatestRelease.cs:28), and the App downloads WebView2 from Microsoft when Windows
# lacks it, without a question (MainWindow.xaml.cs:143-154, WebView2Runtime.cs:10-18). The texts say what happens.
ONLY_WHEN_ASKED = re.compile(
    r"sale de tu computador s[oó]lo cuando|leaves your computer only when|empiezan siempre porque|always start because"
    r"|no manda nada tuyo: s[oó]lo|sends nothing of yours: only", re.IGNORECASE)
WHEN_ASKED = {
    "es": "Cuando le pides a BAXY algo que necesita un servicio de internet, sale de tu computador sólo lo necesario para ese "
          "pedido: lo que pides buscar, a",
    "en": "When you ask BAXY for something that needs an internet service, only what that request needs leaves your computer: "
          "what you ask to search for, to",
}
UNASKED_INSTALLER = {
    "es": "El instalador baja de GitHub las piezas de BAXY y, si a Windows le faltan, WebView2 y el runtime de Visual C++ de "
          "Microsoft; si WebView2 falta al arrancar, BAXY lo descarga de Microsoft sin preguntar.",
    "en": "The installer downloads BAXY's parts from GitHub and, if Windows lacks them, WebView2 and the Visual C++ runtime "
          "from Microsoft; if WebView2 is missing at start, BAXY downloads it from Microsoft without asking.",
}
UNASKED_STORE = {
    "es": "Si a Windows le falta WebView2 de Microsoft, que BAXY necesita para su ventana, BAXY lo descarga de Microsoft al "
          "arrancar, sin que se lo pidas.",
    "en": "If Windows lacks Microsoft's WebView2, which BAXY needs for its window, BAXY downloads it from Microsoft at start, "
          "without being asked.",
}
POLICY_LEG08 = (
    "salvo en los casos de abajo. Casi todos empiezan porque **tú pides algo** que necesita un servicio de internet, y "
    "entonces sólo sale lo necesario para ese pedido; los que BAXY hace sin que se lo pidas están en «Sin que lo pidas», más "
    "abajo.",
    "except in the cases below. Almost all of them start because **you ask for something** that needs an internet service, "
    "and then only what that request needs is sent; those BAXY does without being asked are under «Without being asked», "
    "further down.",
    "**Qué sale y a quién**, cuando le pides algo a BAXY o, donde la fila lo dice, sin pedirlo:",
    "**What is sent, and to whom**, when you ask BAXY for something or, where the row says so, without asking:",
    "**Sin que lo pidas.** En la copia de GitHub, BAXY busca una versión nueva una vez en cada arranque (la fila «Buscar una "
    "versión nueva» de la tabla), y deja de hacerlo si apagas «Avisar de versiones nuevas» en Ajustes → General → Versión. Y, "
    "en cualquier copia, si a Windows le falta WebView2 de Microsoft, que BAXY necesita para su ventana, BAXY lo descarga de "
    "Microsoft al arrancar: Microsoft recibe tu IP.",
    "**Without being asked.** In the copy from GitHub, BAXY looks for a new version once at each start (the row «Looking for "
    "a new version» in the table), and stops doing so if you switch off «Tell me about new versions» in Settings → General → "
    "Version. And, in any copy, if Windows lacks Microsoft's WebView2, which BAXY needs for its window, BAXY downloads it "
    "from Microsoft when it starts: Microsoft receives your IP.",
)


@pytest.mark.parametrize("path", sorted({*PUBLIC_PRIVACY, "licenses/PRIVACIDAD.md"}))
def test_no_public_text_says_that_something_leaves_only_when_the_person_asks(path: str) -> None:
    assert ONLY_WHEN_ASKED.search(_public(path)) is None


def test_the_policy_says_what_baxy_does_without_being_asked() -> None:
    policy = _flat("licenses/PRIVACIDAD.md")
    for words in POLICY_LEG08:
        assert words in policy, words[:70]


@pytest.mark.parametrize("path, language", [case for case in PUBLIC_PRIVACY_CASES if case[0] in AGREEMENTS])
def test_each_agreement_says_what_its_copy_does_without_being_asked(path: str, language: str) -> None:
    privacy = _privacy(path, language)
    assert WHEN_ASKED[language] in privacy
    assert (UNASKED_INSTALLER if "Installer" in path else UNASKED_STORE)[language] in privacy


def test_the_readme_says_that_the_copy_from_github_looks_for_a_new_version_at_each_start() -> None:
    assert ("La copia de GitHub pregunta además a GitHub en cada arranque si hay una versión nueva, salvo que se apague en "
            "Ajustes") in _privacy("README.md", "es")


# LEG1 (LEG-07): NVIDIA answered on 2026-11-08 the question about section 2.1 of the CUDA EULA («only for use in systems with
# NVIDIA GPUs») and a single package whose CUDA files also land on PCs without an NVIDIA card, where they are never loaded
# (MindRuntimeDiscovery.cs:104-110 and :539-543: the CUDA server only with a PCI 10DE card): not prohibited, and consistent
# with the license as described. The texts still called it an open doubt. The answer is archived with its date, its channel,
# what it said and its limit, without a name or an address, and every text that named the doubt cites it. The other doubt,
# whether the NVIDIA part of the GitHub release counts as «distributed standalone», was not asked: it stays open.
NVIDIA_ANSWER = "documentacion/release/RESPUESTA_NVIDIA_CUDA_2_1.md"
CUDA_SAID_OPEN = (
    "Sigue abierta la duda del apartado 2.1", "con esa duda de lectura abierta", "hay que leerlas antes de publicar",
    "que la revisión legal debe confirmar", "según la revisión legal de la EULA de CUDA", "sólo si el EULA de CUDA lo exige",
    "confirmar la redistribución de CUDA",
)
TEXTS_WITH_THE_CUDA_DOUBT = (
    "THIRD_PARTY_NOTICES.md", "documentacion/STEAM_PUBLICACION.md", "documentacion/itchio/EMPAQUETADO.md",
    "documentacion/itchio/LEGAL.md", "documentacion/itchio/README.md",
)


def test_nvidias_answer_is_archived_with_its_date_its_channel_what_it_said_and_its_limit() -> None:
    answer = _flat(NVIDIA_ANSWER)
    for words in ("2026-11-08", "buzón de consultas de licencia", "apartado 2.1", "**no está prohibido**",
                  "**es coherente con los términos de la licencia**", "no un cambio de la EULA",
                  "El original está en el correo del desarrollador", "no es una cita literal"):
        assert words in answer, words
    assert "@" not in answer


@pytest.mark.parametrize("path", TEXTS_WITH_THE_CUDA_DOUBT)
def test_no_text_calls_the_single_package_an_open_doubt_after_nvidias_answer(path: str) -> None:
    text = _flat(path)
    for words in CUDA_SAID_OPEN:
        assert words not in text, words
    assert "RESPUESTA_NVIDIA_CUDA_2_1.md" in text and "2026-11-08" in text


def test_the_notices_say_what_nvidia_answered_its_limit_and_the_doubt_it_was_not_asked() -> None:
    notices = _flat("THIRD_PARTY_NOTICES.md")
    assert "Es la lectura de NVIDIA para el caso descrito, no un cambio de la EULA" in notices
    assert "si eso basta para «no se distribuyen sueltos» no lo dice la EULA. Sólo NVIDIA lo cierra" in notices
    assert "la respuesta del 2026-11-08 no trata esta otra duda" in notices
    assert "**Sin revisión jurídica.**" in notices.split("## Runtime CUDA 12 en el paquete", 1)[1]


# LEG1 (LEG-10): the notices travel inside the package (build_steam.ps1:263), and their table of models said «Lo aporta la
# persona» of pieces the package carries (build_steam.ps1:5-14 and :246-257: llama, llama-vulkan, voice, stt) and listed, with
# nothing to tell them apart, pieces only the source code names (assets.manifest.json, voice.py): each row says which it is.
CARRIED = {
    "| llama.cpp (`llama-server`) |": "**En el paquete** de Steam y de GitHub, carpetas `llama` (CUDA) y `llama-vulkan` (Vulkan)",
    "| Runtime CUDA 12 (": "**En el paquete** de Steam y de GitHub, carpeta `llama`",
    "| Supertonic 3 (voz) |": "**En el paquete** de Steam y de GitHub, carpeta `voice`",
    "| Parakeet Ultra (reconocimiento) |": "**En el paquete** de Steam y de GitHub, carpeta `stt`",
}
NOT_CARRIED = {
    "| Laya (System One, decisor en CPU) |": "el producto no lo usa por defecto; sólo lo carga quien lo aporta y lo nombra con `BAXY_S1_GGUF`",
    "| Gemma 4 E2B (": "Lo nombra `assets.manifest.json`, para ejecutar BAXY desde el código fuente; lo aporta la persona",
    "| Parakeet TDT 0.6B v3 (alternativa) |": "Lo nombra `assets.manifest.json`, para ejecutar BAXY desde el código fuente; lo aporta la persona",
    "| Nemotron 3.5 ASR streaming (opcional) |": "Lo nombra `assets.manifest.json`, para ejecutar BAXY desde el código fuente; lo aporta la persona",
    "| Palabra de activación «k4» |": "ni se distribuye ya: el paquete lleva `baxy-wake-k6r-v7a`",
}


def _notices_row(start: str) -> str:
    lines = (LICENSES.parent / "THIRD_PARTY_NOTICES.md").read_bytes().decode().splitlines()
    return next((line for line in lines if line.startswith(start)), "")


@pytest.mark.parametrize("start", sorted(CARRIED))
def test_a_piece_the_package_carries_is_not_said_to_be_brought_by_the_person(start: str) -> None:
    row = _notices_row(start)
    assert CARRIED[start] in row
    assert "Lo aporta la persona" not in row


@pytest.mark.parametrize("start", sorted(NOT_CARRIED))
def test_a_piece_only_the_source_code_names_is_said_not_to_come_in_the_package(start: str) -> None:
    row = _notices_row(start)
    assert "| **No va en el paquete" in row and NOT_CARRIED[start] in row
    assert "| Lo aporta la persona" not in row


def test_the_itchio_procedure_no_longer_says_the_packages_model_is_checked_by_hand() -> None:
    # build_steam.ps1:53-58 and :174-176 refuse any other GGUF; check_package_licenses.py:56-62 refuses the tuned one.
    procedure = _flat("documentacion/itchio/EMPAQUETADO.md")
    assert "Hasta que `hub/qwb2` fije el modelo" not in procedure and "se comprueba a mano el SHA-256" not in procedure
    assert ("`scripts/build_steam.ps1` ya lo fija: no arma el paquete si el GGUF que recibe no tiene ese SHA-256, y "
            "`scripts/check_package_licenses.py` rechaza un paquete que lleve el ajustado") in procedure


# LEG1 (LEG-11): the table of services had no row for what the copy from GitHub asks api.github.com at each start
# (FieldProductChannel.cs:139-158, Operations/GitHubLatestRelease.cs:28) nor for what its installer downloads from GitHub
# (PartFetcher.cs:29-34), and said only the installer downloads WebView2: in the copies of Steam and itch.io it is the App
# (WebView2Runtime.cs:10-18).
def test_the_notices_name_github_for_the_new_version_and_the_app_that_downloads_webview2() -> None:
    services = _flat("THIRD_PARTY_NOTICES.md").split("## Servicios en la red que BAXY consulta al usarse", 1)[1]
    services = services.split("## Historia pública", 1)[0]
    assert "cuando le pide algo o, donde la fila lo dice, sin que lo pida" in services
    version = _notices_row("| GitHub (buscar una versión nueva; sólo en la copia de GitHub) |")
    for words in ("api.github.com", "`GitHubLatestRelease.cs`", "`FieldProductChannel.cs`", "una vez en cada arranque",
                  "60 requests per hour", "excessively frequent", "leídos 2026-11-09",
                  "sin que la persona lo pida, salvo que apague «Avisar de versiones nuevas»"):
        assert words in version, words
    parts = _notices_row("| GitHub (las piezas de BAXY que baja el instalador, y el instalador nuevo al actualizar) |")
    assert "`PartFetcher.cs`" in parts and "`BaxyUpdateHandler.cs`" in parts
    microsoft = _notices_row("| Visual C++ Redistributable y WebView2 de Microsoft |")
    assert "`src/Baxy.App/WebView2Runtime.cs`" in microsoft
    assert ("WebView2 lo baja también la App al arrancar si falta, sin preguntar: en las copias de Steam y de itch.io, que no "
            "pasan por el instalador, es ella quien lo hace") in microsoft


def test_the_package_inventory_names_the_stock_model_and_met_norway_is_no_longer_open() -> None:
    notices = (LICENSES.parent / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "| Modelo de BAXY y proyector de visión |" not in notices
    assert "| Qwen3.5-4B de serie y proyector de visión |" in notices
    assert "el modelo de BAXY y el proyector" not in (LICENSES / "README.md").read_text(encoding="utf-8")
    itch = LICENSES.parent / "documentacion" / "itchio"
    for name in ("LEGAL.md", "README.md"):
        text = " ".join((itch / name).read_text(encoding="utf-8").split())
        assert "MET Norway: términos por aceptar" not in text and "MET Norway (aceptación de términos)" not in text, name


# The owner's decision (2026-11-08): BAXY distributes v7a officially, also when it is sold, and the texts carry a notice,
# not a pending permission. The notice says what is true (WakewordBaxy/ENTREGA.md, INFORME_DET1): no L2-ARCTIC audio and no
# third-party model inside; 2.3 % synthetic examples from a Piper voice derived from L2-ARCTIC; Kroko imitated without its
# weights (0 of 127 tensors); the earlier detectors withdrawn; BAXY's reading not reviewed by a lawyer. It never claims a
# permission nobody gave, nor that those data were left out of the training.
NOTICE = {
    "en": (
        "it was not trained on L2-ARCTIC recordings",
        "synthetic audio generated with a third-party Piper voice (en_US-l2arctic-medium) that was trained on L2-ARCTIC (CC BY-NC 4.0",
        "an indirect inheritance",
        "none of its 127 tensors of 64 values or more is identical to one of that encoder's (exact comparison; smaller tensors were not compared)",
        "(k4, k5 and v3b2) are no longer distributed",
        "this reading has not been reviewed by a lawyer",
    ),
    "es": (
        "no se entrenó con grabaciones de L2-ARCTIC",
        "audio sintético generado con una voz Piper de terceros (en_US-l2arctic-medium) que sí se entrenó con L2-ARCTIC (CC BY-NC 4.0",
        "herencia indirecta",
        "ninguno de sus 127 tensores de 64 valores o más es idéntico a uno de ese codificador (comparación exacta; los tensores más pequeños no se compararon)",
        "(k4, k5 y v3b2) ya no se distribuyen",
        "esta interpretación no la ha revisado un abogado",
    ),
}
NEVER = (
    "commercial use of the detector is pending",
    "el uso comercial del detector está pendiente",
    "El uso comercial está",
    "commercial use permitted by",
    "uso comercial permitido por",
    "permission from its authors was given",
    "no entrenamos",
    "we did not train",
    "nada que ver con L2-ARCTIC",
    "nothing to do with L2-ARCTIC",
    "Nothing in this agreement restricts the rights CC BY-SA 4.0 gives you",
    "attribution is given as a precaution",
    "atribución se da por prudencia",
)
TEXTS_WITH_THE_NOTICE = {
    "documentacion/steam/EULA.md": ("en", "es"),
    "src/Baxy.Installer/Assets/license/en.txt": ("en",),
    "src/Baxy.Installer/Assets/license/es.txt": ("es",),
    "licenses/PALABRA_DE_ACTIVACION.md": ("es",),
}


@pytest.mark.parametrize("path", sorted(TEXTS_WITH_THE_NOTICE))
def test_the_detector_texts_carry_the_notice_and_no_permission_nobody_gave(path: str) -> None:
    # Markdown wraps its lines: the words are compared with the whitespace collapsed.
    text = " ".join((LICENSES.parent / path).read_text(encoding="utf-8").split())
    for language in TEXTS_WITH_THE_NOTICE[path]:
        for words in NOTICE[language]:
            assert words in text, (language, words)
    for words in NEVER:
        assert words not in text, words


def test_the_detectors_credits_stay() -> None:
    wake = (LICENSES / "PALABRA_DE_ACTIVACION.md").read_text(encoding="utf-8")
    assert "Kroko ASR, de Banafo." in wake
    assert "L2-ARCTIC, de Texas A&M University e Iowa State University." in wake
    assert "CC BY-SA 4.0" in wake


def test_the_notices_say_the_detector_goes_with_a_notice() -> None:
    notices = (LICENSES.parent / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "el detector de `wake` bajo CC BY-SA 4.0, con el aviso de `licenses/PALABRA_DE_ACTIVACION.md`" in notices
    for words in NEVER:
        assert words not in notices, words


def test_the_met_norway_terms_were_accepted_by_the_owner() -> None:
    notices = (LICENSES.parent / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert (
        "Términos de servicio de MET Norway (api.met.no/doc/TermsOfService) leídos y aceptados por el titular de BAXY el "
        "2026-11-08; el contacto del User-Agent es el repositorio público con issues"
    ) in notices
    assert "queda para el dueño" not in notices


# LIC2 (2026-11-08): CC BY-SA 4.0, 3(b), «You may not offer or impose any additional or different terms or conditions»: the
# agreements say they add none for the detector.
NO_ADDED_TERMS = {
    "en": "This agreement adds no term that limits what CC BY-SA 4.0 lets you do with the detector.",
    "es": "Este acuerdo no añade ninguna condición que limite lo que CC BY-SA 4.0 te permite hacer con el detector.",
}
AGREEMENTS_WITH_THE_DETECTOR = {
    "documentacion/steam/EULA.md": ("en", "es"),
    "src/Baxy.Installer/Assets/license/en.txt": ("en",),
    "src/Baxy.Installer/Assets/license/es.txt": ("es",),
}


@pytest.mark.parametrize("path", sorted(AGREEMENTS_WITH_THE_DETECTOR))
def test_the_agreements_add_no_term_to_the_detectors_cc_by_sa(path: str) -> None:
    text = (LICENSES.parent / path).read_text(encoding="utf-8")
    for language in AGREEMENTS_WITH_THE_DETECTOR[path]:
        assert NO_ADDED_TERMS[language] in text


def test_the_friends_permission_is_said_to_be_by_word_until_it_is_written() -> None:
    # LIC2: Ley 19.628, art. 4, «La autorización debe constar por escrito»; today it was given by word.
    wake = (LICENSES / "PALABRA_DE_ACTIVACION.md").read_text(encoding="utf-8")
    assert "| Con su permiso, dado de palabra; por escrito, pendiente |" in wake
    assert "| Con su permiso | — |" not in wake



def _flat(path: str) -> str:
    return " ".join((LICENSES.parent / path).read_text(encoding="utf-8").split())


def test_the_model_attributions_carry_the_detectors_notice() -> None:
    # INT11 §3: ATRIBUCIONES_MODELOS.md goes in the package and still read «Still open … non-commercial», pointing to a section
    # of PALABRA_DE_ACTIVACION.md that no longer exists.
    models = _flat("licenses/ATRIBUCIONES_MODELOS.md")
    for words in NOTICE["en"]:
        assert words in models, words
    assert "«Aviso»" in models
    assert "Still open" not in models
    assert "non-commercial), and its training" not in models
    for words in NEVER:
        assert words not in models, words


def test_the_notices_give_the_detectors_notice_not_an_open_question() -> None:
    notices = _flat("THIRD_PARTY_NOTICES.md")
    assert "Sigue abierto en v7a" not in notices
    assert "Lo que dice el aviso de v7a" in notices
    assert "v7a se distribuye con el aviso de `licenses/PALABRA_DE_ACTIVACION.md`" in notices
    assert "porque aprendió de material con esa licencia" not in notices


def test_the_detectors_cc_by_sa_is_said_to_be_a_precaution() -> None:
    # LIC2: with 0/127 tensors equal, v7a is reasonably not adapted material; licensing it CC BY-SA 4.0 is complying by excess.
    wake = _flat("licenses/PALABRA_DE_ACTIVACION.md")
    assert "porque aprendió de material con esa licencia" not in wake
    assert "por prudencia" in wake
    assert "obra propia" in wake


def test_the_release_notes_say_the_package_carries_the_stock_model() -> None:
    notes = _flat("documentacion/release/NOTAS_1.3.2.md")
    assert "stock Qwen3.5-4B" in notes
    assert "Qwen3.5-4B de serie" in notes
    assert "unofficial extra" in notes
    assert "extra no oficial" in notes


# INT14 (2026-11-08), blind review of the merged texts: with lessac beside L2-ARCTIC and Kroko, «los dos se atribuyen» no
# longer says which two, lessac was credited nowhere and missing from the open questions, and LEGAL.md's notes on itself
# named a branch that is gone and a difference that is not the only one.
def test_the_store_texts_say_what_is_credited_and_lessac_is_still_open() -> None:
    for path in ("documentacion/itchio/PAGINA.md", "documentacion/itchio/PRECIO_Y_CUENTA.md"):
        text = _flat(path)
        assert "os dos se atribuyen" not in text, path
        assert "Both are credited" not in text, path
        assert "L2-ARCTIC, los datos Blizzard 2013, RyanSpeech y Kroko se atribuyen" in text, path
    assert "L2-ARCTIC, the Blizzard 2013 data, RyanSpeech and Kroko are credited" in _flat("documentacion/itchio/PAGINA.md")
    credits = _flat("licenses/PALABRA_DE_ACTIVACION.md").split("## Créditos", 1)[1]
    assert "Blizzard 2013, de Lessac Technologies y Voice Factory" in credits
    pending = _flat("THIRD_PARTY_NOTICES.md").split("## Pendiente o sin confirmar", 1)[1].split("2. **Higgsfield", 1)[0]
    still_open = _flat("documentacion/itchio/README.md").split("Cuestiones abiertas", 1)[1][:900]
    for text in (pending, still_open):
        for words in ("lessac", "50,1 %", "CSTR", "RyanSpeech"):
            assert words in text, words
    legal = _flat("documentacion/itchio/LEGAL.md")
    assert "de esa rama" not in legal
    assert "Ya no se dice «pendiente»" not in legal


def _sentences(path: str, start: str) -> list[str]:
    paragraph = next(line for line in (LICENSES.parent / path).read_text(encoding="utf-8").splitlines()
                     if line.startswith("- " + start))
    return re.split(r"(?<=\.) (?=[A-Z])", paragraph[2:])


# INT14: what LEGAL.md says of the installer's agreement beside Steam's detector paragraph, sentence by sentence.
@pytest.mark.parametrize("language, recognizer, detector", [
    ("es", "El reconocedor de voz deriva", "El detector de la palabra"),
    ("en", "The speech recognizer derives", "The wake word detector"),
])
def test_the_installers_detector_paragraph_differs_from_steams_only_where_legal_says(
        language: str, recognizer: str, detector: str) -> None:
    steam = _sentences("documentacion/steam/EULA.md", detector)
    installer = _sentences(f"src/Baxy.Installer/Assets/license/{language}.txt", recognizer)
    added = [s for s in installer if s not in steam]
    removed = [s for s in steam if s not in installer]
    # LEG1 (REV_LEGAL LEG-03): Steam's no longer says that the card «lists every dataset, their licenses and their credits»,
    # so nothing of Steam's is missing from the installer's.
    assert removed == []
    assert len(added) == 2, added
    assert "Parakeet" in added[0] and "ATRIBUCIONES_MODELOS.md" in added[1], added


# LEG1 (2026-11-09, REV_LEGAL LEG-03): licenses/PALABRA_DE_ACTIVACION.md has rows whose license is «por confirmar» and
# sources «sin leer» (its table of what the detector learned from), so no agreement may say that it lists every dataset and
# model with their licenses and credits: all of them say what the installer's says.
WHAT_THE_CARD_SAYS = {
    "es": "licenses/PALABRA_DE_ACTIVACION.md dice de qué aprendió y da el crédito de cada fuente.",
    "en": "licenses/PALABRA_DE_ACTIVACION.md says what it learned from and gives each source's credit.",
}


@pytest.mark.parametrize("path", sorted(AGREEMENTS))
def test_no_agreement_says_that_the_detectors_card_lists_every_dataset_and_license(path: str) -> None:
    text = _repo_text(path)
    for language in AGREEMENTS[path].split():
        assert WHAT_THE_CARD_SAYS[language] in text, language
    for words in ("lista cada conjunto de datos", "lists every dataset"):
        assert words not in text, words


def test_the_detectors_card_still_has_rows_it_cannot_vouch_for() -> None:
    # If one day every row is confirmed, the agreements may say more; until then the test above holds them.
    card = _repo_text("licenses/PALABRA_DE_ACTIVACION.md")
    assert "por confirmar" in card or "sin leer" in card or "desconocido" in card



# INT12 (2026-11-08): what the measurement says is that no tensor of v7a equals one of Kroko's, not that it copied nothing;
# the notice names the other voices it learned from, and the 9 Piper voices fine-tuned from lessac (Blizzard 2013, research
# only), per their rhasspy/piper-voices cards, with their share of the examples pending measurement.
LESSAC_VOICES = (
    "en_US-libritts_r-medium, en_GB-vctk-medium, en_US-l2arctic-medium, es_ES-sharvard-medium, en_US-arctic-medium, "
    "es_ES-davefx-medium, es_AR-daniela-high"
)
MORE_NOTICE = {
    "en": (
        "Eight Piper voices used (" + LESSAC_VOICES + " and pt_BR-faber-medium) were fine-tuned from the Piper voice lessac, "
        "and es_MX-ald-medium from es_ES-davefx-medium; lessac was trained on Blizzard 2013 data (Lessac Technologies and Voice "
        "Factory) licensed for research only. Those nine voices make up 50.1 % of its 59,363 training examples (48.96 % "
        "directly and 1.14 % through es_MX-ald-medium); v7a was not trained on those recordings (an indirect inheritance, like "
        "L2-ARCTIC). On 2026-11-08 CSTR was asked to pass a request for permission to Lessac Technologies and Voice Factory, "
        "their rights holders.",
        "recordings of the developer and of friends of the developer, used with their permission given by word; written "
        "permission is pending.",
        "0.89 % of its examples (531) are synthetic audio from the Piper voices es_ES-mls_10246-low and es_ES-mls_9972-low, "
        "fine-tuned from the Piper voice en_US-ryan-low, which was trained on RyanSpeech (University of Denver) under a "
        "non-commercial license (CC BY-NC-SA 4.0 according to that voice's card; its authors' paper says CC BY-NC-ND); v7a "
        "was not trained on those recordings (an indirect inheritance, which is credited), and BAXY cannot grant the rights of "
        "RyanSpeech's holders.",
    ),
    "es": (
        "Ocho voces Piper usadas (" + LESSAC_VOICES + " y pt_BR-faber-medium) se ajustaron a partir de la voz Piper lessac, y es_MX-ald-medium a partir de "
        "es_ES-davefx-medium; lessac se entrenó con datos Blizzard 2013 (Lessac Technologies y Voice Factory) cuya licencia es "
        "sólo para investigación. Esas nueve voces son el 50,1 % de sus 59.363 ejemplos de entrenamiento (48,96 % directo y "
        "1,14 % a través de es_MX-ald-medium); v7a no se entrenó con esas grabaciones (herencia indirecta, como L2-ARCTIC). El "
        "2026-11-08 se escribió a CSTR para que pase la petición de permiso a Lessac Technologies y Voice Factory, sus "
        "titulares.",
        "grabaciones del desarrollador y de amigos suyos, usadas con su permiso dado de palabra; el permiso por escrito está "
        "pendiente.",
        "El 0,89 % de sus ejemplos (531) es audio sintético de las voces Piper es_ES-mls_10246-low y es_ES-mls_9972-low, "
        "ajustadas a partir de la voz Piper en_US-ryan-low, que se entrenó con RyanSpeech (Universidad de Denver), de licencia "
        "no comercial (CC BY-NC-SA 4.0 según la ficha de esa voz; el artículo de sus autores dice CC BY-NC-ND); v7a no se "
        "entrenó con esas grabaciones (herencia indirecta, que se atribuye), y BAXY no puede conceder los derechos de los "
        "titulares de RyanSpeech.",
    ),
}
AGREEMENT_COPIES = {
    "documentacion/steam/EULA.md": ("en", "es"),
    "src/Baxy.Installer/Assets/license/en.txt": ("en",),
    "src/Baxy.Installer/Assets/license/es.txt": ("es",),
    "documentacion/itchio/LEGAL.md": ("en", "es"),
}


@pytest.mark.parametrize("path", sorted(AGREEMENT_COPIES))
def test_the_agreements_name_every_voice_the_detector_learned_from(path: str) -> None:
    text = _flat(path)
    for language in AGREEMENT_COPIES[path]:
        for words in MORE_NOTICE[language]:
            assert words in text, (language, words[:60])
        assert NOTICE[language][3] in text, language
    assert "copying its weights" not in text
    assert "copiar sus pesos" not in text


def test_palabra_names_the_lessac_lineage_and_separates_arctic_from_riccardo() -> None:
    wake = _flat("licenses/PALABRA_DE_ACTIVACION.md")
    assert MORE_NOTICE["es"][0] in wake
    raw = (LICENSES / "PALABRA_DE_ACTIVACION.md").read_text(encoding="utf-8")
    assert "| Voces Piper `arctic` y `riccardo` |" not in raw
    assert "| Voz Piper `en_US-arctic-medium` |" in raw
    assert "| Voz Piper `riccardo` |" in raw


def test_no_text_says_the_detector_copied_nothing() -> None:
    for path in ("licenses/ATRIBUCIONES_MODELOS.md", "documentacion/release/NOTAS_1.3.2.md", "documentacion/itchio/PAGINA.md",
                 "documentacion/itchio/PRECIO_Y_CUENTA.md"):
        text = _flat(path)
        assert "copying its weights" not in text, path
        assert "copiar sus pesos" not in text, path


def test_ipwhois_is_not_said_to_be_free_while_its_terms_say_otherwise() -> None:
    notices = _flat("THIRD_PARTY_NOTICES.md")
    assert "Libre según su documentación" not in notices
    assert "Se les escribió el 2026-11-08 pidiendo que lo confirmen por escrito; sin respuesta todavía" in notices


def test_the_vision_projector_is_said_to_come_in_the_package() -> None:
    raw = (LICENSES.parent / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    row = next(line for line in raw.splitlines() if line.startswith("| Visión: proyector Qwen3.5-4B |"))
    assert "Lo aporta la persona" not in row
    assert "**En el paquete** de Steam y de GitHub, carpeta `models`" in row



# INT13's blind review (2026-11-08): the detector's grant says what BAXY can grant (its own model, under CC BY-SA 4.0) and that
# it grants nothing that belongs to third parties; the agreements say the same of the whole program; the measurement is said as
# measured (exact identity, tensors of 64 values or more); the lessac lineage is in every notice; itch.io's agreement keeps
# Steam's detector paragraph word for word, as its own pages claim.
GRANT = {
    "en": "BAXY licenses under CC BY-SA 4.0 the rights it has over the model it trained, and can grant no rights that belong "
          "to third parties over the data and models it learned from.",
    "es": "BAXY licencia bajo CC BY-SA 4.0 los derechos que tenga sobre el modelo que entrenó, y no puede conceder derechos "
          "que pertenezcan a terceros sobre los datos y modelos de los que aprendió.",
}
ONLY_OURS = {
    "en": "The developer can grant only the rights that are the developer's, and grants none that belong to third parties.",
    "es": "El desarrollador sólo puede conceder los derechos que son suyos, y no concede ninguno que pertenezca a terceros.",
}
NOT_AS_MEASURED = ("sin llevar sus pesos", "without carrying its weights", "sin copiar sus pesos", "without copying its weights",
                   "no lleva sus pesos", "143a2fac0", "modelos de terceros", "third-party model", "pesos de otros modelos",
                   "sin sus pesos", "no contiene ese audio", "does not contain that audio", "lo que es suyo",
                   "what is BAXY's in it", "términos de BAXY, que", "BAXY's terms, which",
                   # INT15: the grant formula the steam-depot fix left in STEAM_PUBLICACION's detector row
                   "lo distribuye bajo sus términos")


@pytest.mark.parametrize("path", sorted(AGREEMENT_COPIES))
def test_the_agreements_grant_only_what_is_baxys(path: str) -> None:
    text = _flat(path)
    for language in AGREEMENT_COPIES[path]:
        assert GRANT[language] in text, language
        assert ONLY_OURS[language] in text, language
        assert NOTICE[language][4] in text, language


def test_palabra_grants_only_what_is_baxys_and_its_piper_row_names_lessac() -> None:
    wake = _flat("licenses/PALABRA_DE_ACTIVACION.md")
    assert GRANT["es"] in wake
    raw = (LICENSES / "PALABRA_DE_ACTIVACION.md").read_text(encoding="utf-8")
    row = next(line for line in raw.splitlines() if line.startswith("| Voces Piper (ejemplos sintéticos) |"))
    assert "lessac" in row and "sólo investigación" in row


@pytest.mark.parametrize("path, language", [
    ("THIRD_PARTY_NOTICES.md", "es"), ("licenses/ATRIBUCIONES_MODELOS.md", "en"), ("documentacion/itchio/PAGINA.md", "es"),
    ("documentacion/itchio/PAGINA.md", "en"), ("documentacion/release/NOTAS_1.3.2.md", "es"),
    ("documentacion/release/NOTAS_1.3.2.md", "en"),
])
def test_every_notice_names_the_lessac_lineage(path: str, language: str) -> None:
    text = _flat(path)
    assert MORE_NOTICE[language][0] in text, (path, language)
    assert ("research only" if language == "en" else "sólo para investigación") in text, (path, language)
    assert ("can grant no rights that belong to third parties" if language == "en"
            else "no puede conceder derechos que pertenezcan a terceros") in text, (path, language)


@pytest.mark.parametrize("path", [
    "documentacion/steam/EULA.md", "src/Baxy.Installer/Assets/license/en.txt", "src/Baxy.Installer/Assets/license/es.txt",
    "documentacion/itchio/LEGAL.md", "documentacion/itchio/PAGINA.md", "documentacion/itchio/PRECIO_Y_CUENTA.md",
    "licenses/PALABRA_DE_ACTIVACION.md", "licenses/ATRIBUCIONES_MODELOS.md", "documentacion/release/NOTAS_1.3.2.md",
    "THIRD_PARTY_NOTICES.md", "documentacion/STEAM_PUBLICACION.md",
])
def test_the_kroko_comparison_is_said_as_measured(path: str) -> None:
    text = _flat(path)
    for words in NOT_AS_MEASURED:
        assert words not in text, (path, words)


def test_itchios_detector_paragraph_is_steams_word_for_word() -> None:
    def bullets(path: str) -> list[str]:
        raw = (LICENSES.parent / path).read_text(encoding="utf-8")
        return [line for line in raw.splitlines()
                if line.startswith(("- The wake word detector (wake folder)", "- El detector de la palabra de activación (carpeta wake)"))]
    steam = bullets("documentacion/steam/EULA.md")
    assert len(steam) == 2
    # Each language's paragraph, word for word; itch.io gives Spanish first.
    assert sorted(bullets("documentacion/itchio/LEGAL.md")) == sorted(steam)



# INT14 (2026-11-08): the agreements' only restrictions include the third parties' rights the developer cannot grant; PALABRA's
# «Aviso» and ATRIBUCIONES' notice say the same sentences (one in Spanish, one in English); the Steam row says only what was
# measured and names lessac.
RESTRICTIONS = {
    "en": "the only ones are those set by those licenses and the rights of third parties that the developer cannot grant "
          "(section 2)",
    "es": "las únicas son las que ponen esas licencias y los derechos de terceros que el desarrollador no puede conceder "
          "(sección 2)",
}
NOTICE_SENTENCES = {
    "es": (
        GRANT["es"],
        "no se entrenó con grabaciones de L2-ARCTIC: el 2,3 % de sus ejemplos de entrenamiento es audio sintético generado con "
        "una voz Piper de terceros (en_US-l2arctic-medium) que sí se entrenó con L2-ARCTIC (CC BY-NC 4.0, Texas A&M University "
        "e Iowa State University), una herencia indirecta, que se atribuye.",
        MORE_NOTICE["es"][0],
        "Aprendió a imitar el codificador en español de Kroko ASR (Banafo), y se atribuye a Kroko; lo medido, el 2026-11-07, es "
        "que " + NOTICE["es"][3] + ".",
        "Los detectores anteriores que llevaban Kroko o audio de una serie de televisión (k4, k5 y v3b2) ya no se distribuyen.",
        "BAXY considera el detector una obra propia, distinta de esos datos y modelos; esta interpretación no la ha revisado un "
        "abogado.",
    ),
    "en": (
        GRANT["en"],
        "was not trained on L2-ARCTIC recordings: 2.3 % of its training examples are synthetic audio generated with a "
        "third-party Piper voice (en_US-l2arctic-medium) that was trained on L2-ARCTIC (CC BY-NC 4.0, Texas A&M University and "
        "Iowa State University), an indirect inheritance, which is credited.",
        MORE_NOTICE["en"][0],
        "It learned to imitate the Spanish encoder of Kroko ASR (Banafo), and Kroko is credited; what was measured, on "
        "2026-11-07, is that " + NOTICE["en"][3] + ".",
        "The earlier detectors that carried Kroko or audio from a TV series (k4, k5 and v3b2) are no longer distributed.",
        "BAXY considers the detector its own work, distinct from those data and models; this reading has not been reviewed by a "
        "lawyer.",
    ),
}


@pytest.mark.parametrize("path", sorted(AGREEMENT_COPIES))
def test_the_agreements_name_the_third_parties_rights_among_the_restrictions(path: str) -> None:
    text = _flat(path)
    for language in AGREEMENT_COPIES[path]:
        assert RESTRICTIONS[language] in text, language


@pytest.mark.parametrize("path, language", [
    ("licenses/PALABRA_DE_ACTIVACION.md", "es"), ("licenses/ATRIBUCIONES_MODELOS.md", "en"),
    ("documentacion/steam/EULA.md", "es"), ("documentacion/steam/EULA.md", "en"),
    ("src/Baxy.Installer/Assets/license/en.txt", "en"), ("src/Baxy.Installer/Assets/license/es.txt", "es"),
])
def test_every_copy_of_the_notice_says_the_same_sentences(path: str, language: str) -> None:
    text = _flat(path)
    for sentence in NOTICE_SENTENCES[language]:
        assert sentence in text, (path, sentence[:60])


def test_the_steam_row_of_the_detector_says_what_was_measured_and_names_lessac() -> None:
    raw = (LICENSES.parent / "documentacion" / "STEAM_PUBLICACION.md").read_text(encoding="utf-8")
    row = next(line for line in raw.splitlines() if line.startswith("| Palabra de activación (k6r-v7a"))
    assert "lessac" in row
    assert "ninguno de sus 127 tensores de 64 valores o más es idéntico" in row
    # INT15: the same grant as the notice and the agreements, and no more
    assert "licencia bajo CC BY-SA 4.0 los derechos que tenga sobre el modelo que entrenó" in row
    assert "no puede conceder los de terceros" in row


# INT15 (2026-11-08): the detector's permission comes after its caveat, and only for what BAXY can grant.
DETECTOR_PERMISSION = "En lo que BAXY puede conceder, puedes usarlo, copiarlo, modificarlo y redistribuirlo"


def test_the_detectors_permission_comes_after_its_caveat_and_only_for_what_baxy_can_grant() -> None:
    text = _flat("licenses/PALABRA_DE_ACTIVACION.md")
    section = text[text.index("## Licencia del detector"):text.index("## Aviso")]
    assert DETECTOR_PERMISSION in section
    assert section.index(GRANT["es"]) < section.index(DETECTOR_PERMISSION)
    assert section.lower().count("puedes usarlo") == 1


# INT15 (2026-11-08): beside the unofficial extra goes what its Hugging Face card says it was trained on, in the same words;
# what is published (the package, the agreements, the itch.io page) does not name the tool the data was generated with.
TUNED_DATA = {
    "es": "El ajuste se entrenó con conversaciones sintéticas con recibos de trazas reales; no se usó texto privado de ninguna "
          "persona.",
    "en": "The fine-tune was trained on synthetic conversations whose tool receipts are taken from real traces; no private user "
          "text was used.",
}
TEXTS_WITH_THE_EXTRA = {
    "documentacion/steam/EULA.md": ("en", "es"), "src/Baxy.Installer/Assets/license/en.txt": ("en",),
    "src/Baxy.Installer/Assets/license/es.txt": ("es",), "documentacion/itchio/LEGAL.md": ("es", "en"),
    "documentacion/itchio/PAGINA.md": ("es", "en"), "licenses/ATRIBUCIONES_MODELOS.md": ("en",),
    "THIRD_PARTY_NOTICES.md": ("es",), "documentacion/release/NOTAS_1.3.2.md": ("en", "es"),
}
PUBLISHED_FROM = {
    "documentacion/steam/EULA.md": "## English", "documentacion/itchio/LEGAL.md": "## Español (",
    "documentacion/itchio/PAGINA.md": "## 3. Descripción",
}


@pytest.mark.parametrize("path", sorted(TEXTS_WITH_THE_EXTRA))
def test_the_unofficial_extra_says_what_its_card_says_it_was_trained_on(path: str) -> None:
    text = _flat(path)
    for language in TEXTS_WITH_THE_EXTRA[path]:
        assert TUNED_DATA[language] in text, language


def _published(path: str) -> str:
    text = (LICENSES.parent / path).read_text(encoding="utf-8")
    start = PUBLISHED_FROM.get(path)
    if start is None:
        return text
    text = text[text.index(start):]
    return text[:text.index("## 4. Imágenes")] if path.endswith("PAGINA.md") else text


@pytest.mark.parametrize("path", sorted(
    [*PUBLISHED_FROM, "src/Baxy.Installer/Assets/license/en.txt", "src/Baxy.Installer/Assets/license/es.txt",
     "THIRD_PARTY_NOTICES.md"] + [f"licenses/{p.name}" for p in LICENSES.glob("*.md")]))
def test_what_is_published_does_not_name_the_tool_the_tuning_data_came_from(path: str) -> None:
    assert "Claude" not in _published(path)


# INT16 (2026-11-08, wakeword 06d55ae): the lessac share is measured, two mls voices inherit RyanSpeech, and es_MX-claude-high's
# lineage is unknown; no text says the share is still to be measured.
WITH_THE_LINEAGE = sorted({*TEXTS_WITH_THE_NOTICE, "documentacion/itchio/PAGINA.md", "documentacion/itchio/PRECIO_Y_CUENTA.md",
                           "documentacion/itchio/LEGAL.md", "documentacion/itchio/README.md", "documentacion/STEAM_PUBLICACION.md",
                           "documentacion/release/NOTAS_1.3.2.md", "THIRD_PARTY_NOTICES.md"})


@pytest.mark.parametrize("path", WITH_THE_LINEAGE)
def test_no_text_says_the_lessac_share_is_still_to_be_measured(path: str) -> None:
    text = _flat(path)
    for words in ("pendiente de medir", "pending measurement", "ejemplos sin medir", "ejemplos está sin medir"):
        assert words not in text, words
    if "lessac" in text:
        assert "50,1 %" in text or "50.1 %" in text
        assert "RyanSpeech" in text


@pytest.mark.parametrize("path", sorted(AGREEMENT_COPIES))
def test_the_agreements_carry_the_ryan_lineage_after_cstr(path: str) -> None:
    text = _flat(path)
    for language in AGREEMENT_COPIES[path]:
        cstr, ryan = MORE_NOTICE[language][0], MORE_NOTICE[language][2]
        assert cstr + " " + ryan in text, language


def test_palabra_lists_the_ryan_voices_the_unknown_claude_voice_and_credits_ryanspeech() -> None:
    raw = (LICENSES / "PALABRA_DE_ACTIVACION.md").read_text(encoding="utf-8")
    rows = [line for line in raw.splitlines() if line.startswith("| ")]
    mls = next(line for line in rows if "es_ES-mls_10246-low" in line)
    assert "es_ES-mls_9972-low" in mls and "531" in mls and "RyanSpeech" in mls and "no comercial" in mls
    claude = next(line for line in rows if "es_MX-claude-high" in line)
    assert "desconocido" in claude and "See URL above" in claude
    credits = _flat("licenses/PALABRA_DE_ACTIVACION.md").split("## Créditos")[1]
    assert "RyanSpeech, de Rohola Zandie, Mohammad H. Mahoor, Julia Madsen y Eshrat S. Emamian" in credits


# INT18 (2026-11-09): the historical note on the agreements names the third parties' rights too; the policy and the agreements
# name the «Other» server, the optional vision a local model brings, who names a conversation, and where the named
# conversations are kept.
def test_the_notes_on_the_agreements_name_the_rights_that_cannot_be_granted() -> None:
    text = _flat("THIRD_PARTY_NOTICES.md")
    assert ("las únicas son las de las licencias de terceros y los derechos de terceros que no se pueden conceder") in text


OTHER_SERVER = {
    "en": "or another server under «Other» that is not on your computer, then while that option is on, what you say and what BAXY "
          "reads for you (including text and images from your screen, files and web pages) is sent to that company or server",
    "es": "u otro servidor en «Otra» que no esté en tu computador, mientras esa opción esté activa, lo que digas y lo que BAXY "
          "lea para ti (incluidos textos e imágenes de tu pantalla, archivos y páginas web) se envía a esa empresa o servidor",
}


@pytest.mark.parametrize("path", sorted(AGREEMENT_COPIES))
def test_the_agreements_name_the_other_server(path: str) -> None:
    text = _flat(path)
    for language in AGREEMENT_COPIES[path]:
        assert OTHER_SERVER[language] in text, language


POLICY_INT18 = (
    "Esa empresa (Anthropic, OpenAI o Google), o el servidor que escribas en «Otra» si no está en tu computador",
    "That company (Anthropic, OpenAI or Google), or the server you enter under «Other» if it is not on your computer",
    "Tu IP y el modelo que se baja (y su visión, si la eliges)",
    "Your IP and the model downloaded (and its vision, if you choose it)",
    "El nombre de cada conversación lo pone un modelo de este computador (el de BAXY u Ollama); si usas una empresa de IA u "
    "«Otra», la conversación se queda con sus primeras palabras y su nombre no se le pide.",
    "Each conversation is named by a model on this computer (BAXY's or Ollama's); if you use an AI company or «Other», the "
    "conversation keeps its first words and its name is not asked of it.",
    "Las últimas 50 conversaciones, con su nombre, se guardan ahí cifradas para tu usuario de Windows, y puedes borrarlas.",
    "Your last 50 conversations, with their names, are kept there encrypted for your Windows user, and you can delete them.",
    "Última actualización: 9 de noviembre de 2026 · Last updated: November 9, 2026",
)


def test_the_policy_names_the_other_server_the_vision_who_names_a_conversation_and_where_it_is_kept() -> None:
    text = _flat("licenses/PRIVACIDAD.md")
    for words in POLICY_INT18:
        assert words in text, words[:60]


# INT19 (2026-11-09): «Versión» and baxy.update ask GitHub only in the copy from GitHub; the policy says what, when and what
# not, and each agreement says it for its own copy (src/Baxy.Core/Operations/BaxyUpdateHandler.cs, GitHubLatestRelease.cs).
UPDATE_ROWS = ('| Buscar una versión nueva (sólo en la copia de GitHub: una vez en cada arranque, salvo que apagues «Avisar de versiones nuevas» en Ajustes → General → Versión, y cuando buscas actualizaciones o se lo pides a BAXY) | GitHub (api.github.com) | Tu IP y la versión de BAXY instalada; pide la última versión publicada de REDSOULTM/BAXY | <https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement> |', '| Actualizar BAXY (sólo en la copia de GitHub, y sólo si eliges actualizar) | GitHub | Tu IP y la versión de BAXY; se baja el instalador nuevo, que se comprueba con su SHA-256 antes de abrirlo | <https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement> |', '| Looking for a new version (only in the copy from GitHub: once at each start, unless you switch off «Tell me about new versions» in Settings → General → Version, and when you check for updates or ask BAXY) | GitHub (api.github.com) | Your IP and the installed version of BAXY; it asks for the latest published version of REDSOULTM/BAXY | <https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement> |', "| Updating BAXY (only in the copy from GitHub, and only if you choose to update) | GitHub | Your IP and BAXY's version; the new installer is downloaded and checked against its SHA-256 before it is opened | <https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement> |")
UPDATE_NOT_SENT = ('Buscar una versión nueva no manda nada de lo que dices ni de tus archivos: sólo la versión de BAXY, desde tu IP. Las copias de Steam y de itch.io no preguntan a GitHub. La de Steam la actualiza Steam, y la de itch.io, la app de itch.io si la instalaste con ella: «Abrir en Steam» o «Abrir en itch.io» (o pedirle a BAXY que se actualice) abre la biblioteca de Steam o la página de BAXY en itch.io. Una copia bajada de la página de itch.io sin su app no se actualiza sola: la versión nueva se baja de esa misma página.', "Looking for a new version sends nothing you say and none of your files: only BAXY's version, from your IP. The copies from Steam and itch.io do not ask GitHub. Steam updates the one from Steam, and the itch app updates the one from itch.io if you installed it with that app: «Open in Steam» or «Open in itch.io» (or asking BAXY to update) opens Steam's library or BAXY's page on itch.io. A copy downloaded from the itch.io page without its app is not updated by itself: you download the new version from that same page.")
# LEG1 (LEG-13): «BAXY de itch.io lo actualiza la app de itch.io» is only true of a copy the itch app installed: «Players who
# prefer downloading directly rather than using the itch app don't get automatic updates»
# (https://itch.io/docs/butler/pushing.html, read 2026-11-09), that copy never asks GitHub (BaxyUpdateHandler.cs:67-70 and
# :97) and, with no receipt of the itch app, it does not know its page either (BaxyDistribution.cs:53-68,
# BaxyUpdateHandler.cs:139-142).
ITCH_UPDATE = {
    "es": ("BAXY instalado con la app de itch.io lo actualiza esa app: no pregunta a GitHub por versiones nuevas, y «Abrir en "
           "itch.io» en Ajustes (o pedirle a BAXY que se actualice) abre la página de BAXY en itch.io. Si lo bajaste de la "
           "página de itch.io sin su app, nada lo actualiza solo: tampoco pregunta a GitHub, y la versión nueva se baja de esa "
           "misma página."),
    "en": ("BAXY installed with the itch app is updated by that app: it does not ask GitHub for new versions, and «Open in "
           "itch.io» in Settings (or asking BAXY to update) opens BAXY's page on itch.io. If you downloaded it from the itch.io "
           "page without its app, nothing updates it by itself: it does not ask GitHub either, and you download the new "
           "version from that same page."),
}
UPDATE_AGREEMENT = {
    "src/Baxy.Installer/Assets/license/en.txt": ("it receives a ping from your IP. Without being asked, BAXY sends its version and your IP to GitHub (api.github.com) to look for a new version, once at each start, unless you switch off «Tell me about new versions» in Settings → General → Version; the same is sent when you check for updates or ask BAXY, and if you choose to update, the new installer is downloaded from GitHub and checked against its SHA-256.",),
    "src/Baxy.Installer/Assets/license/es.txt": ('recibe un ping desde tu IP. Sin que se lo pidas, BAXY manda su versión y tu IP a GitHub (api.github.com) para buscar una versión nueva, una vez en cada arranque, salvo que apagues «Avisar de versiones nuevas» en Ajustes → General → Versión; lo mismo sale cuando buscas actualizaciones o se lo pides a BAXY, y si eliges actualizar, el instalador nuevo se baja de GitHub y se comprueba con su SHA-256.',),
    "documentacion/steam/EULA.md": ("BAXY bought on Steam is updated by Steam: it does not ask GitHub for new versions, and «Open in Steam» in Settings (or asking BAXY to update) opens Steam's library.", 'BAXY comprado en Steam lo actualiza Steam: no pregunta a GitHub por versiones nuevas, y «Abrir en Steam» en Ajustes (o pedirle a BAXY que se actualice) abre la biblioteca de Steam.'),
    "documentacion/itchio/LEGAL.md": (ITCH_UPDATE["en"], ITCH_UPDATE["es"]),
}


def test_itchios_agreement_does_not_promise_updates_to_a_copy_downloaded_without_the_itch_app() -> None:
    agreement = _flat("documentacion/itchio/LEGAL.md")
    assert ITCH_UPDATE["es"] in agreement and ITCH_UPDATE["en"] in agreement
    assert "BAXY de itch.io lo actualiza la app de itch.io" not in agreement
    assert "BAXY from itch.io is updated by the itch app" not in agreement


# LEG1 (LEG-15): the headers of itch.io's texts still dated them to 2026-11-07 against 8d89ab0f8, before LIC2 and LEG1.
@pytest.mark.parametrize("path", ["documentacion/itchio/LEGAL.md", "documentacion/itchio/PAGINA.md"])
def test_the_header_of_itchios_texts_says_when_they_were_last_brought_up_to_date(path: str) -> None:
    assert "la última vez el 2026-11-09 (LEG1, sobre `hub/int20-final` 5af388064)" in _flat(path)[:1400]


def test_the_policy_says_what_looking_for_a_new_version_asks_github_when_and_what_it_does_not_send() -> None:
    policy = _repo_text("licenses/PRIVACIDAD.md")
    for row in UPDATE_ROWS:
        assert row in policy, row[:60]
    text = _flat("licenses/PRIVACIDAD.md")
    for words in UPDATE_NOT_SENT:
        assert words in text, words[:60]


@pytest.mark.parametrize("path", sorted(UPDATE_AGREEMENT))
def test_each_agreement_says_how_its_copy_is_updated(path: str) -> None:
    text = _flat(path)
    for words in UPDATE_AGREEMENT[path]:
        assert words in text, words[:60]
    if "Installer" not in path:
        assert "api.github.com" not in text


# PRV1 (revisión de privacidad 2026-11-09, PRIV-02): the policy said the conversations are kept encrypted and nothing of
# the two logs kept in clear text (about 108 MB of what the person said) nor of the screens captured. The same sentence,
# in each language, in the policy and in every agreement: what stays unencrypted, where and how much. Revisión a ciegas:
# a PC that updates keeps the logs an earlier version wrote with the words, and nothing but «Olvidar todo» (or their
# rotation) removes them, so the sentence says that too rather than «no words» of files that still hold them.
KEPT_IN_CLEAR = {
    "es": ("BAXY deja además, en su carpeta de datos (%LOCALAPPDATA%\\BAXY), registros técnicos sin cifrar. Los dos que "
           "anotan cada turno (renew\\turns.jsonl, hasta unos 100 MB, y 1\\conversation\\conversation.v1.jsonl, hasta 8 MB) "
           "guardan la hora, cuánto tardó y qué operaciones se usaron, no lo que dices ni lo que BAXY responde, salvo que tú "
           "lo actives en tu computador para diagnosticar un fallo (variable BAXY_TRACE_WORDS=1); un registro de errores "
           "puede citar un fragmento de lo que el modelo escribía cuando falló. Lo que una versión anterior de BAXY ya "
           "hubiera anotado en ellos, con lo que dijiste, sigue ahí hasta que uses «Olvidar todo». Cuando BAXY mira tu "
           "pantalla guarda la captura, sin cifrar, en 1\\captures sólo mientras atiende ese pedido: la borra al terminarlo "
           "y al cerrarse. «Olvidar todo» borra esos registros y las capturas junto con las conversaciones."),
    "en": ("BAXY also leaves unencrypted technical logs in its data folder (%LOCALAPPDATA%\\BAXY). The two that note each "
           "turn (renew\\turns.jsonl, up to about 100 MB, and 1\\conversation\\conversation.v1.jsonl, up to 8 MB) keep the "
           "time, how long it took and which operations were used, not what you say nor what BAXY answers, unless you turn "
           "that on in your computer to diagnose a fault (the BAXY_TRACE_WORDS=1 variable); an error log may quote a "
           "fragment of what the model was writing when it failed. What an earlier version of BAXY had already noted in "
           "them, with what you said, stays there until you use «Forget everything». When BAXY looks at your screen it "
           "keeps the capture, unencrypted, in 1\\captures only while it handles that request: it deletes it when the "
           "request ends and when BAXY closes. «Forget everything» deletes those logs and the captures along with the "
           "conversations."),
}


@pytest.mark.parametrize("path, languages", [("licenses/PRIVACIDAD.md", "es en"), *AGREEMENTS.items()])
def test_the_policy_and_the_agreements_say_what_stays_unencrypted_where_and_how_much(path: str, languages: str) -> None:
    text = _repo_text(path)
    for language in languages.split():
        assert text.count(KEPT_IN_CLEAR[language]) == 1, (path, language)


def test_what_the_texts_say_stays_unencrypted_is_what_the_code_keeps() -> None:
    # The sentence is held to the code: the files' names and places, their caps, and that no words are kept unless asked.
    from baxy_mind.__main__ import TRACE_LIMIT_BYTES, trace_dir, trace_words
    from baxy_mind.mind import Mind
    root = LICENSES.parent
    megabyte = 1024 * 1024
    assert 2 * TRACE_LIMIT_BYTES == 100 * megabyte  # turns.jsonl and the one archive kept beside it
    assert trace_dir({"LOCALAPPDATA": "X"}).parts[-2:] == ("BAXY", "renew")
    assert '"turns.jsonl"' in (root / "src/baxy_mind/__main__.py").read_text(encoding="utf-8")
    assert trace_words({"LOCALAPPDATA": "X"}) is False and trace_words({"BAXY_TRACE_WORDS": "1"}) is True
    assert not {"text", "content", "arguments", "written", "own", "system_one"} & Mind.TRACE_FACTS
    bounded = (root / "src/Baxy.App/BoundedJsonlFile.cs").read_text(encoding="utf-8")
    assert "DefaultMaximumBytes = 4L * 1024 * 1024;" in bounded and 'ArchiveSuffix = ".1"' in bounded  # 8 MB with its archive
    log = (root / "src/Baxy.App/ConversationLog.cs").read_text(encoding="utf-8")
    assert 'ResolveDataRoot(), "conversation")' in log and '"conversation.v1.jsonl"' in log
    assert 'WordsEnvironmentVariable = "BAXY_TRACE_WORDS"' in log
    assert 'if (_keepsWords)\n            {\n                payload["text"] = message.Body;' in log
    # The data root is «1» under %LOCALAPPDATA%\BAXY, and the engine's captures are in it.
    assert all('"BAXY",\n                "1")' in (root / source).read_text(encoding="utf-8")
               for source in ("src/Baxy.App/MemoryOperationProtection.cs", "src/Baxy.Core/Program.cs"))
    assert 'Path.Combine(dataRoot, "captures")' in (root / "src/Baxy.Core/Program.cs").read_text(encoding="utf-8")
    model = (root / "src/Baxy.App/MainWindowViewModel.cs").read_text(encoding="utf-8")
    assert 'ResolveDataRoot(), "captures")' in model and model.count("ClearCapturesNoCallWaitsFor();") == 2
    # «Olvidar todo» / «Forget everything» is the button's own text.
    panel = (root / "src/Baxy.FieldUi/src/components/panels/MemoryPanel.tsx").read_text(encoding="utf-8")
    assert "t('Olvidar todo', 'Forget everything')" in panel


# LEG1 (blind review, 2026-11-09): what two readers who had not seen the diff found against the code.
#
# The policy said «no salen de tu computador, salvo en los casos de abajo» and had no row for what leaves through the
# person's own programs when BAXY drives them: a message (ProductCatalog.cs:1415, channels discord and whatsapp), an email or
# an appointment through Outlook (ProductCatalog.cs:613 and :360, MicrosoftAccountAdapter.cs:18) and a program that winget
# installs (WingetPackageAdapter.cs:140-143 and :376; its default sources are Microsoft's:
# https://learn.microsoft.com/en-us/windows/package-manager/winget/source, read 2026-11-09). The list of the agreements and
# of the store pages read as closed and left those out, with the browser, the terminal and the ping the policy already had.
OWN_PROGRAMS = {
    "es": ("Lo que pides abrir, enviar, instalar o ejecutar con tu navegador u otro programa tuyo (por ejemplo un sitio, un "
           "mensaje por Discord o WhatsApp, un correo por Outlook, un programa con winget o un comando de terminal) sale por "
           "ese programa, bajo sus condiciones; y si pides comprobar si una máquina responde, recibe un ping desde tu IP."),
    "en": ("What you ask to open, send, install or run with your browser or another program of yours (for example a site, a "
           "message through Discord or WhatsApp, an email through Outlook, a program with winget or a terminal command) leaves "
           "through that program, under its terms; and if you ask to check whether a machine answers, it receives a ping from "
           "your IP."),
}
OWN_PROGRAM_ROWS = (
    "| Enviar un mensaje (por Discord o WhatsApp) o un correo, o crear una cita (por Outlook) | Esa aplicación tuya, con tu "
    "cuenta, y su servicio | El texto y el destinatario que dices, o la cita; los envía esa aplicación, no BAXY | Las de ese "
    "servicio |",
    "| Instalar un programa, o desinstalarlo, con winget (el gestor de paquetes de Windows) | Las fuentes de winget de tu "
    "Windows (de serie, el catálogo de winget y el de la Microsoft Store, los dos de Microsoft) y, al instalar, el sitio del "
    "que winget baja el instalador | El nombre o el identificador del programa que pides, y tu IP; lo envía winget, no BAXY | "
    "Las de Microsoft para winget (<https://learn.microsoft.com/windows/package-manager/winget/source> nombra sus fuentes) y "
    "las de ese sitio. BAXY llama a winget con las opciones que aceptan por ti los acuerdos de la fuente y, al instalar, "
    "los del paquete (`--accept-source-agreements`, `--accept-package-agreements`): winget no te pregunta por ellos |",
    "| Sending a message (through Discord or WhatsApp) or an email, or creating an appointment (through Outlook) | That app "
    "of yours, with your account, and its service | The text and the recipient you say, or the appointment; that app sends "
    "them, not BAXY | That service's |",
    "| Installing a program, or uninstalling it, with winget (Windows' package manager) | The winget sources of your Windows "
    "(by default winget's catalog and the Microsoft Store's, both Microsoft's) and, when installing, the site winget downloads "
    "the installer from | The name or the identifier of the program you ask for, and your IP; winget sends it, not BAXY | "
    "Microsoft's for winget (<https://learn.microsoft.com/windows/package-manager/winget/source> names its sources) and that "
    "site's. BAXY calls winget with the options that accept for you the source's agreements and, when installing, the "
    "package's (`--accept-source-agreements`, `--accept-package-agreements`): winget does not ask you about them |",
)


def test_the_policy_has_a_row_for_what_leaves_through_the_persons_own_programs() -> None:
    policy = _repo_text("licenses/PRIVACIDAD.md")
    for row in OWN_PROGRAM_ROWS:
        assert row in policy, row[:60]


@pytest.mark.parametrize("path, language", [case for case in PUBLIC_PRIVACY_CASES if case[0] != "README.md"])
def test_every_public_text_says_that_what_is_done_with_the_persons_programs_leaves_through_them(path: str, language: str) -> None:
    assert OWN_PROGRAMS[language] in _privacy(path, language)


def test_the_readme_says_what_leaves_through_the_persons_programs_and_that_baxy_downloads_webview2() -> None:
    privacy = _privacy("README.md", "es")
    assert ("Lo que se pide abrir, enviar, instalar o ejecutar con el navegador u otro programa de la persona (un sitio, un "
            "mensaje, un correo, un programa con winget, un comando) sale por ese programa; y si se pide comprobar si una "
            "máquina responde, recibe un ping.") in privacy
    assert "si a Windows le falta WebView2 de Microsoft, BAXY lo descarga de Microsoft al arrancar, sin preguntar" in privacy


# The store pages listed what leaves when asked and were silent on the one thing a copy from a store sends unasked: the App
# downloads WebView2 from Microsoft at start if Windows lacks it (WebView2Runtime.cs:10-18). The agreements already say it.
@pytest.mark.parametrize("path", ["documentacion/STEAM_PUBLICACION.md", "documentacion/itchio/PAGINA.md"])
@pytest.mark.parametrize("language", ["es", "en"])
def test_the_store_pages_say_that_baxy_downloads_webview2_at_start_without_being_asked(path: str, language: str) -> None:
    assert UNASKED_STORE[language] in _privacy(path, language)


# A web search carries the country Windows has set when the engine has it in the language of the search
# (WebBrowserAdapter.cs:79 and :883-890, «kl»; HomeRegion.cs:12-20). And a local model alone is downloaded by BAXY itself from
# huggingface.co (OpenModels.cs:536-541 and :605-607); only with its vision does Ollama pull it (OpenModels.cs:422-470).
def test_the_policy_says_the_country_a_search_carries_and_who_asks_hugging_face_for_a_local_model() -> None:
    policy = _repo_text("licenses/PRIVACIDAD.md")
    assert ("Lo que pides buscar (y tu ciudad y su país si pides «cerca de mí»), con el país que tienes puesto en Windows si el buscador "
            "lo ofrece en el idioma de la búsqueda, desde tu IP,") in policy
    assert ('What you ask to search for (and your city and its country if you ask "near me"), with the country set in Windows if the search '
            "engine offers it in the language of the search, from your IP,") in policy
    assert "| Hugging Face; lo pide BAXY y, si eliges su visión, Ollama |" in policy
    assert "| Hugging Face; asked by BAXY and, if you choose its vision, by Ollama |" in policy
    assert "pedido por Ollama" not in policy and "asked by Ollama |" not in policy
    notices = _repo_text("THIRD_PARTY_NOTICES.md")
    assert "el modelo lo baja Ollama de hf.co" not in notices
    assert ("el modelo solo lo baja BAXY de huggingface.co, lo comprueba con su SHA-256 y se lo da a Ollama; con su visión, lo "
            "baja Ollama de hf.co") in notices


# The policy said of every copy from itch.io what is only true of one the itch app installed (see ITCH_UPDATE).
def test_the_policy_does_not_say_that_a_store_updates_a_copy_downloaded_from_itchios_page() -> None:
    policy = _repo_text("licenses/PRIVACIDAD.md")
    assert "las actualiza su tienda, y «Abrir en Steam»" not in policy
    assert "their store updates them, and «Open in Steam»" not in policy


# Steam's Early Access answer said «Necesita una GPU NVIDIA de 4 GB; con otra GPU o sin GPU, hoy no funciona», and the App
# starts the Vulkan server with an AMD or an Intel card (MindRuntimeDiscovery.cs:106-111; the installer's warnings,
# Baxy.Installer/Texts.cs:126-130). It says what itch.io's page says (PAGINA.md, «Requisitos y estado»).
def test_steams_early_access_answer_does_not_say_that_baxy_only_runs_on_nvidia() -> None:
    steam = _public("documentacion/STEAM_PUBLICACION.md")
    assert "con otra GPU o sin GPU, hoy no funciona" not in steam
    assert "with another GPU, or none, it doesn't run today" not in steam
    assert ("Necesita una tarjeta gráfica de 4 GB: con NVIDIA está probado, con AMD está en pruebas y con Intel no se ha "
            "probado. Sin una tarjeta NVIDIA, AMD o Intel no arranca.") in steam
    assert ("It needs a 4 GB graphics card: it is tested with NVIDIA, in testing with AMD and untested with Intel. Without an "
            "NVIDIA, AMD or Intel card it does not start.") in steam
    assert "AMD, sólo cuando el paquete elija Vulkan" not in steam


# The same document said the App has no Run key in src/: it has one (WindowsAutostartRegistration.cs:300), and writes it only
# from the folder of GitHub's installer or the development checkout (MayRegister, :168-176; IsUnderInstallationRoot).
def test_steams_notes_do_not_say_that_the_app_has_no_run_key() -> None:
    steam = _public("documentacion/STEAM_PUBLICACION.md")
    assert "no hay clave `Run` en `src/`" not in steam
    assert "la copia de Steam no lo registra" in steam
    assert "`src/Baxy.App/WindowsAutostartRegistration.cs`, `MayRegister`" in steam


# LEG-10 wrote that the package carries llama's folders «tal como las publica la release oficial»: the script copies only the
# files the server uses and adds the Visual C++ runtime (build_steam.ps1:111-129 and :239-244). And the section on what the
# person installs said so of WebView2 with no word of the installer or the App, which the row of services does say.
def test_the_notices_say_which_files_of_llama_the_package_carries_and_who_installs_webview2() -> None:
    row = _notices_row("| llama.cpp (`llama-server`) |")
    assert "tal como las publica la release oficial" not in row
    assert "sólo los ficheros que copia `scripts/build_steam.ps1` (`Copy-ServerFolder`" in row
    assert "sin las demás herramientas de la release, y con el runtime de Visual C++ al lado" in row
    section = _repo_text("THIRD_PARTY_NOTICES.md").split("### 5. Python, .NET y Edge que la persona instala", 1)[1]
    section = section.split("### 6. ", 1)[0]
    assert section.startswith(" Para ejecutar BAXY desde el código fuente, CPython 3.12")
    assert ("WebView2 no va en ningún paquete: a quien usa BAXY instalado se lo baja de Microsoft el instalador o, si falta al "
            "arrancar, la App") in section


# The internal notes of itch.io's agreement still listed the model's line and the detector's paragraph as its differences
# with the installer's, which the notes below them deny, and called the detector's notice a change of itch.io's.
def test_itchios_notes_say_todays_differences_with_the_installers_agreement() -> None:
    notes = _public("documentacion/itchio/LEGAL.md").split("## Español (`BAXY-licencia-es.txt`)", 1)[0]
    assert "Sólo cambian: el canal" not in notes
    assert "y que el detector de activación va con **un aviso**" not in notes
    assert "La línea del modelo y el párrafo del detector ya no cambian:" in notes
    assert "el mismo que en los otros dos acuerdos" in notes
    installer = _repo_text("src/Baxy.Installer/Assets/license/es.txt")
    assert "que sólo vienen en la parte para tarjetas NVIDIA (carpeta llama)" in installer  # the CUDA difference the notes name


# LEG1 (second blind review, 2026-11-09): what two more readers who had not seen the diff found against the code.
#
# «Cerca de mí» adds to what is searched the city and its country that ipwho.is gave (WebBrowserAdapter.cs:924-943 and
# :975-988, `NearAsync`): to Photon, to DuckDuckGo and to Wikipedia. The policy said the city in two of the three rows, and
# the agreements and the pages only «lo que pides buscar».
NEAR_ME = {
    "es": "a DuckDuckGo, Wikipedia o Photon (datos de OpenStreetMap), con tu ciudad y su país si pides algo «cerca de mí»;",
    "en": 'to DuckDuckGo, Wikipedia or Photon (OpenStreetMap data), with your city and its country if you ask for something '
          '"near me";',
}


@pytest.mark.parametrize("path, language", [case for case in PUBLIC_PRIVACY_CASES if case[0] != "README.md"])
def test_every_public_text_says_that_a_search_near_me_carries_the_city_and_its_country(path: str, language: str) -> None:
    assert NEAR_ME[language] in _privacy(path, language)


def test_the_policy_says_near_me_in_the_three_rows_that_carry_it() -> None:
    policy = _repo_text("licenses/PRIVACIDAD.md")
    assert "| Lo que pides buscar (y tu ciudad y su país si pides «cerca de mí») y el idioma |" in policy
    assert "| El lugar y la clase de sitio (y tu ciudad y su país si pides «cerca de mí») |" in policy
    assert '| What you ask to search for (and your city and its country if you ask "near me") and the language |' in policy
    assert '| The place and the kind of place (and your city and its country if you ask "near me") |' in policy
    assert "tu ciudad si pides" not in policy and "your city if you ask" not in policy


# The README's summary left out three things its own list implies are all: the name typed to search a model, the ping, and
# that with the person's own key of an AI company what is said and read goes to that company (external_model.py).
def test_the_readme_names_the_model_search_the_ping_and_the_persons_own_key() -> None:
    privacy = _privacy("README.md", "es")
    assert ("a DuckDuckGo, Wikipedia o Photon (datos de OpenStreetMap), con la ciudad y su país si se pide algo «cerca de "
            "mí»;") in privacy
    assert "al buscar o bajar un modelo desde Ajustes, el nombre que se escribe y la IP a Hugging Face, y la IP a GitHub" in privacy
    assert "Si la persona conecta su propia clave de una empresa de IA, u otro servidor en «Otra»" in privacy


# A page that is read and a file that is downloaded are asked for by BAXY under its own name («BAXY/1.0 page-read»,
# SearchPageReader.cs:17; «Mozilla/5.0 BAXY/1.0 file-download», WindowsFileToolsAdapter.cs:62), not «as a browser does», and
# a page whose text its scripts draw is loaded in the hidden WebView2 (WebBrowserAdapter.cs:364-372). After opening an
# address in the person's browser BAXY asks the site itself, with a HEAD request, whether the page answers
# (UserBrowserSurface.cs:244-245; SearchPageReader.cs:110-123). A model search also asks Hugging Face for each model found
# and for the first megabyte of some of its files (OpenModels.cs:258-259, :283 and :392-396).
POLICY_REQUESTS = (
    "| Tu IP y la dirección, en una petición que lleva el nombre de BAXY; si la página sólo muestra su texto con scripts, la "
    "carga el navegador WebView2 oculto de la fila de arriba |",
    "| Lo que pides abrir o buscar, y lo que ese navegador o esa aplicación mande por su cuenta; al abrir una dirección en tu "
    "navegador, BAXY pregunta además a ese sitio, con una petición propia desde tu IP, si la página responde |",
    "| El nombre que escribes y tu IP; BAXY pide además a Hugging Face los datos de los modelos que aparecen y el principio de "
    "algunos de sus ficheros |",
    "| Your IP and the address, in a request that carries BAXY's name; if the page only shows its text through scripts, the "
    "hidden WebView2 browser of the row above loads it |",
    "| What you ask to open or search for, and whatever that browser or app sends on its own; when opening an address in your "
    "browser, BAXY also asks that site, with a request of its own from your IP, whether the page answers |",
    "| The name you type and your IP; BAXY also asks Hugging Face for the details of the models that come up and for the "
    "beginning of some of their files |",
)


def test_the_policy_says_the_requests_baxy_itself_makes_to_a_site_and_to_hugging_face() -> None:
    policy = _repo_text("licenses/PRIVACIDAD.md")
    for row in POLICY_REQUESTS:
        assert row in policy, row[:60]
    assert "como al abrirla en un navegador" not in policy and "as when opening it in a browser" not in policy


# The hidden browser's folder («webview2-search» in the data root) keeps what the pages it read left, and BAXY empties it
# before a reader starts on it past 100 MiB (HiddenPageReaderHost.cs:36-53).
def test_the_policy_says_where_what_the_hidden_browser_reads_is_kept() -> None:
    policy = _repo_text("licenses/PRIVACIDAD.md")
    assert ("Lo que dejan las páginas que lee el navegador WebView2 oculto (su caché y lo que cada sitio guarda) queda en un "
            "perfil aparte dentro de esa carpeta, y BAXY lo vacía, antes de usarlo otra vez, si pasa de 100 MB.") in policy
    assert ("What the pages read by the hidden WebView2 browser leave (its cache and what each site stores) stays in a "
            "separate profile inside that folder, and BAXY empties it, before using it again, if it exceeds 100 MB.") in policy


# itch.io's agreement opened with «que la app de itch.io instala y mantiene al día», and its page sold «las actualizaciones
# automáticas», with no word of the copy downloaded from the page without the app, which nothing updates
# (BaxyDistribution.cs:53-68; https://itch.io/docs/butler/, read 2026-11-09). Section 5 of the agreement already says it.
def test_itchios_agreement_and_page_do_not_promise_updates_to_a_copy_downloaded_without_the_app() -> None:
    legal = _public("documentacion/itchio/LEGAL.md")
    assert "que la app de itch.io instala y mantiene al día si la usas (sección 5):" in legal
    assert "installed and kept up to date by the itch.io app if you use it (section 5):" in legal
    page = _public("documentacion/itchio/PAGINA.md")
    assert ("las actualizaciones automáticas. Si lo bajas de esta página sin la app, no se actualiza solo: la versión nueva se "
            "baja de aquí.") in page
    assert ("with automatic updates. If you download it from this page without the app, it does not update itself: you "
            "download the new version from here.") in page


# NVIDIA was asked about one package, naming Steam's depot (documentacion/release/RESPUESTA_NVIDIA_CUDA_2_1.md, «La
# pregunta»). itch.io's upload is the same folder (scripts/build_steam.ps1, `Channel`), so BAXY reads the answer as covering
# it; the texts of itch.io gave that reading as NVIDIA's own words.
@pytest.mark.parametrize("path", ["documentacion/itchio/LEGAL.md", "documentacion/itchio/EMPAQUETADO.md",
                                  "documentacion/itchio/README.md", NVIDIA_ANSWER])
def test_no_text_says_that_nvidia_answered_about_itchios_package(path: str) -> None:
    text = _public(path)
    assert "depot de Steam" in text
    assert "lectura de BAXY" in text
    assert "el paquete de Steam, y el de itch.io, que es la misma carpeta, puede llevar" not in text


# Steam's notes said «en otra carpeta, Ajustes lo dice»: what Settings shows there is the hint written for the development
# copy (SettingsPanel.tsx, `autostartBlocked === 'not_this_copy'`), untrue of a copy from a store. And their build command
# left out parameters the script refuses to run without.
def test_steams_notes_say_what_settings_shows_and_give_a_build_command_that_runs() -> None:
    notes = _public("documentacion/STEAM_PUBLICACION.md")
    assert "Ajustes lo dice" not in notes
    assert "Ajustes muestra entonces el aviso escrito para la copia de desarrollo" in notes
    script = LICENSES.parent.joinpath("scripts", "build_steam.ps1").read_bytes().decode()
    # The script's own parameters: its first param block, which ends where its body starts (its functions have theirs).
    own = script[script.index("\nparam("):script.index("$ErrorActionPreference")]
    mandatory = re.findall(r"\[Parameter\(Mandatory = \$true\)\]\[string\]\$(\w+)", own)
    assert len(mandatory) >= 6
    command = next(line for line in notes.split("```") if "build_steam.ps1 -" in line)
    for name in mandatory:
        assert f"-{name} " in command, name


# The package of itch.io is the folder of Steam's (build_steam.ps1, `Channel`: only distribution.json changes), and the
# notices, which travel inside it, never named it. Two wheels of the lock were said to be «en el repo» and «se instala» and
# are inside the package's Python (build_steam.ps1:207-211; pylock.runtime-win-x64.toml). And the row of the AI companies
# left out the server the person may write under «Otra».
def test_the_notices_name_itchios_package_and_what_its_python_carries() -> None:
    notices = _repo_text("THIRD_PARTY_NOTICES.md")
    assert ("**El paquete de itch.io es esta misma carpeta:** la arma el mismo script con `-Channel itch`, que sólo cambia el "
            "canal escrito en `distribution.json`.") in notices
    assert "Los paquetes de Steam, de itch.io y de GitHub sí los llevan" in notices
    assert "instalada del lock, **en el paquete**, dentro de `python`" in _notices_row("| Silero VAD v6 |")
    assert "**en el paquete**, dentro de `python`" in _notices_row("| ONNX Runtime |")
    assert "o el servidor que la persona escriba en «Otra»" in _notices_row("| Modelos por API (")


def test_itchios_notes_date_the_last_comparison_with_the_installers_agreement() -> None:
    notes = _public("documentacion/itchio/LEGAL.md")
    assert "(comprobadas con `diff` el 2026-11-07 y comparadas de nuevo el 2026-11-09)" in notes



# The store pages said less than the agreements about the person's own key: no word of the server written under «Otra»,
# nor that what BAXY reads (screen, files, pages) goes with what is said (EULA.md, section 5; src/baxy_mind/external_model.py).
OWN_KEY_ON_THE_PAGES = {
    ("documentacion/STEAM_PUBLICACION.md", "es"):
        "en Ajustes puedes conectar tu propia clave de una empresa de IA, u otro servidor en «Otra» que no esté en tu PC: "
        "mientras esté activo, lo que digas y lo que BAXY lea para ti (incluidos textos e imágenes de tu pantalla, archivos y "
        "páginas web) se envía a esa empresa o servidor, y lo paga tu cuenta.",
    ("documentacion/STEAM_PUBLICACION.md", "en"):
        "you can connect your own key from an AI company in Settings, or another server under «Other» that is not on your "
        "PC: while that's on, what you say and what BAXY reads for you (including text and images from your screen, files and "
        "web pages) goes to that company or server, and your account pays for it.",
    ("documentacion/itchio/PAGINA.md", "es"):
        "o conectar tu propia clave de una empresa de IA, u otro servidor en «Otra» que no esté en tu PC. Esa opción viene "
        "apagada; mientras esté activa, lo que le digas y lo que BAXY lea para ti (incluidos textos e imágenes de tu pantalla, "
        "archivos y páginas web) va a esa empresa o servidor, bajo sus condiciones y a tu costo.",
    ("documentacion/itchio/PAGINA.md", "en"):
        "or connect your own key from an AI company, or another server under «Other» that is not on your PC. That option is "
        "off by default; while it is on, what you say and what BAXY reads for you (including text and images from your "
        "screen, files and web pages) goes to that company or server, under its terms and at your cost.",
}


@pytest.mark.parametrize("path, language", sorted(OWN_KEY_ON_THE_PAGES))
def test_the_store_pages_say_of_the_persons_own_key_what_the_agreements_say(path: str, language: str) -> None:
    page = _public(path)
    assert OWN_KEY_ON_THE_PAGES[path, language] in page
    assert "lo que le pases a BAXY se envía a esa empresa" not in page and "what you give BAXY goes to that" not in page


# Steam's notes ask the store page to say that uninstalling from Steam leaves the tuned model behind
# (STEAM_PUBLICACION.md, row «Modelo»), and no page said it. The data folder holds it (TunedModel.cs:77, `<data>\models`) with
# what BAXY remembers; a copy from a store has no uninstaller (build_steam.ps1 writes no install script), so nothing deletes
# that folder. Only the installer's uninstaller does, when asked (Texts.cs, `UninstallDelete`; CommandLine.cs, --delete-data).
DATA_STAYS = {
    ("documentacion/STEAM_PUBLICACION.md", "es"):
        "Lo que recuerda lo puedes ver, editar y borrar. Se guarda en tu PC, en la carpeta de datos de BAXY "
        "(%LOCALAPPDATA%\\BAXY), junto con el modelo ajustado si lo bajas: desinstalar BAXY desde Steam no borra esa carpeta, "
        "que puedes borrar a mano.",
    ("documentacion/STEAM_PUBLICACION.md", "en"):
        "You can see, edit and delete what it remembers. It is kept on your PC, in BAXY's data folder "
        "(%LOCALAPPDATA%\\BAXY), together with the fine-tuned model if you download it: uninstalling BAXY from Steam does not "
        "delete that folder, which you can delete by hand.",
    ("documentacion/itchio/PAGINA.md", "es"):
        "Lo que recuerda lo ves, lo editas y lo borras tú. Se guarda en tu PC, en la carpeta de datos de BAXY "
        "(%LOCALAPPDATA%\\BAXY), junto con el modelo ajustado si lo bajas: desinstalar BAXY con la app de itch.io, o borrar la "
        "carpeta donde lo pusiste, no borra esa carpeta de datos, que puedes borrar a mano.",
    ("documentacion/itchio/PAGINA.md", "en"):
        "You see, edit and delete what it remembers. It is kept on your PC, in BAXY's data folder (%LOCALAPPDATA%\\BAXY), "
        "together with the fine-tuned model if you download it: uninstalling BAXY with the itch.io app, or deleting the folder "
        "you put it in, does not delete that data folder, which you can delete by hand.",
}


@pytest.mark.parametrize("path, language", sorted(DATA_STAYS))
def test_the_store_pages_say_that_uninstalling_from_the_store_leaves_the_data_folder(path: str, language: str) -> None:
    assert DATA_STAYS[path, language] in _privacy(path, language)


def test_the_policy_says_which_uninstall_removes_the_data_folder() -> None:
    policy = " ".join(_repo_text("licenses/PRIVACIDAD.md").split())
    assert "desinstalar BAXY borrando sus datos quita esa carpeta" not in policy
    assert "uninstalling BAXY with its data removes that folder" not in policy
    assert ("Puedes ver, editar y borrar lo que BAXY recuerda, y el desinstalador de la copia de GitHub quita esa carpeta si "
            "eliges borrar tus datos. Las copias de Steam y de itch.io no tienen desinstalador propio: desinstalarlas (desde "
            "Steam, con la app de itch.io o borrando su carpeta) no borra esa carpeta de datos, que puedes borrar a mano. Ahí "
            "queda también el modelo ajustado opcional, si lo bajaste.") in policy
    assert ("You can view, edit and delete what BAXY remembers, and the uninstaller of the copy from GitHub removes that "
            "folder if you choose to delete your data. The copies from Steam and itch.io have no uninstaller of their own: "
            "uninstalling them (from Steam, with the itch.io app or by deleting their folder) does not delete that data "
            "folder, which you can delete by hand. The optional fine-tuned model, if you downloaded it, is kept there too."
            ) in policy


# BAXY's own requests carry its name in their User-Agent, and the policy said so only of MET Norway: ProductIdentity.cs:15
# (name, version and the project's address: MET Norway, Wikipedia, Photon, Frankfurter), WebBrowserAdapter.cs:73 (ipwho.is),
# YouTubeSearch.cs:26, OpenModels.cs:74 and TunedModel.cs:49 (Hugging Face, GitHub), BaxyUpdateHandler.cs:58 and the
# installer's Program.cs:230 (GitHub), SearchPageReader.cs:17 and WindowsFileToolsAdapter.cs:62 (a page, a file). The Steam
# store's client (SteamLocalAdapter.cs:864) and the WebView2 download (WebView2Runtime.cs:36) carry none, so they are not named.
def test_the_policy_says_which_requests_say_they_come_from_baxy() -> None:
    policy = " ".join(_repo_text("licenses/PRIVACIDAD.md").split())
    assert ("**Cómo se presenta BAXY.** Las peticiones que BAXY hace él mismo a MET Norway, ipwho.is, Wikipedia, Photon, "
            "Frankfurter, YouTube, Hugging Face y GitHub, y las de leer una página o descargar un fichero, dicen que vienen de "
            "BAXY: llevan su nombre y, algunas, su versión y una dirección del proyecto en GitHub. Lo que carga el "
            "navegador WebView2 oculto (la búsqueda en DuckDuckGo y las páginas que sólo muestran su texto con scripts) se "
            "presenta como ese navegador, sin el nombre de BAXY. **Sin que lo pidas.**") in policy
    assert ("**How BAXY introduces itself.** The requests BAXY makes itself to MET Norway, ipwho.is, Wikipedia, Photon, "
            "Frankfurter, YouTube, Hugging Face and GitHub, and those to read a page or download a file, say they come from "
            "BAXY: they carry its name and, some of them, its version and an address of the project on GitHub. What the "
            "hidden WebView2 browser loads (the search on DuckDuckGo and the pages that only show their text through "
            "scripts) introduces itself as that browser, without BAXY's name. **Without being asked.**") in policy
    # The hidden browser sets no User-Agent of its own (HiddenPageReader.cs, HiddenPageReaderHost.cs): WebView2's goes.
    for hidden in ("Baxy.App/HiddenPageReader.cs", "Baxy.Providers.Windows/External/HiddenPageReaderHost.cs"):
        assert "useragent" not in LICENSES.parent.joinpath("src", hidden).read_bytes().decode("utf-8").lower(), hidden
    source = LICENSES.parent / "src"
    for file, words in (("Baxy.Providers.Windows/External/ProductIdentity.cs", '"BAXY/"'),
                        ("Baxy.Providers.Windows/External/WebBrowserAdapter.cs", '"BAXY/1.0 structured-search"'),
                        ("Baxy.Providers.Windows/External/YouTubeSearch.cs", '"Mozilla/5.0 BAXY/1.0"'),
                        ("Baxy.App/OpenModels.cs", 'UserAgent.ParseAdd("BAXY")'),
                        ("Baxy.App/TunedModel.cs", 'UserAgent.ParseAdd("BAXY")'),
                        ("Baxy.Core/Operations/BaxyUpdateHandler.cs", '$"BAXY/{'),
                        ("Baxy.Installer/Program.cs", '"BAXY-Instalador/"'),
                        ("Baxy.Providers.Windows/External/SearchPageReader.cs", '"BAXY/1.0 page-read"'),
                        ("Baxy.Providers.Windows/External/WindowsFileToolsAdapter.cs", '"Mozilla/5.0 BAXY/1.0 file-download"')):
        assert words in source.joinpath(file).read_bytes().decode("utf-8"), file


# The README's summary left out the installer's own downloads (Prerequisites.cs:16-17; the pieces, from the release on
# GitHub), which the policy tells under «Microsoft y la tienda», and the server under «Otra».
def test_the_readme_says_what_the_installer_downloads_and_names_the_other_server() -> None:
    privacy = _privacy("README.md", "es")
    assert ("Si la persona conecta su propia clave de una empresa de IA, u otro servidor en «Otra» que no esté en su máquina, "
            "lo que dice y lo que BAXY lee para ella (pantalla, archivos y páginas incluidos) va a esa empresa o servidor."
            ) in privacy
    assert ("El instalador de la copia de GitHub baja de GitHub las piezas de BAXY y, de Microsoft, si faltan, WebView2 y el "
            "runtime de Visual C++.") in privacy


# «no todos son libres» said in Spanish something other than «not all of them are permissive».
def test_itchios_page_says_the_same_of_the_licenses_in_both_languages() -> None:
    page = _public("documentacion/itchio/PAGINA.md")
    assert "Cada componente conserva su licencia y no todas son permisivas:" in page
    assert "Each component keeps its own license and not all of them are permissive:" in page
    assert "no todos son libres" not in page
