"""What a store's package carries besides the common folder of scripts/build_steam.ps1, each file from one place of the
repository:

    steam   installscript.vdf: what Steam runs when the app is uninstalled (scripts/steam/installscript.vdf, INS-1). Its
            agreement is not a file: Steam shows the one of Steamworks' EULA field (documentacion/steam/EULA.md).
    itch    .itch.toml, the manifest itch.io's app reads at the root (documentacion/itchio/itch.toml,
            https://itch.io/docs/itch/integrating/manifest.html), and the license agreement in Spanish and English under
            licenses, with the names GitHub's installer gives its own (src/Baxy.Installer/WindowsIntegration.cs): itch.io
            has no screen to accept one, so that file is where its buyer reads it. The texts are the two sections of
            documentacion/itchio/LEGAL.md that name those files, without the Markdown.

    <python> -X utf8 scripts/package_channel.py --depot <package folder> --channel itch

build_steam.ps1 writes them with this; check_package_licenses.py asks the package for the same bytes."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parent.parent
STEAM_UNINSTALL = REPOSITORY / "scripts" / "steam" / "installscript.vdf"
ITCH_MANIFEST = REPOSITORY / "documentacion" / "itchio" / "itch.toml"
ITCH_LEGAL = REPOSITORY / "documentacion" / "itchio" / "LEGAL.md"
ITCH_AGREEMENTS = ("BAXY-licencia-es.txt", "BAXY-license-en.txt")
# «## Español (`BAXY-licencia-es.txt`)»: the heading of a section that is a file of the package.
_FILE_HEADING = re.compile(r"## .*\(`([^`]+)`\)\s*")


def itch_agreements(document: Path = ITCH_LEGAL) -> dict[str, bytes]:
    """Each agreement by its file name: the lines under its heading, up to the next heading or rule."""
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in document.read_text(encoding="utf-8").splitlines():
        heading = _FILE_HEADING.fullmatch(line)
        if heading:
            current = sections.setdefault(heading.group(1), [])
        elif line.startswith("## ") or line.strip() == "---":
            current = None
        elif current is not None:
            current.append(line.rstrip())
    texts = {name: "\n".join(sections.get(name, ())).strip("\n") for name in ITCH_AGREEMENTS}
    if missing := [name for name, text in texts.items() if not text]:
        raise SystemExit(f"{document} has no text for {', '.join(missing)}")
    return {name: (text + "\n").encode("utf-8") for name, text in texts.items()}


def files(channel: str) -> dict[str, bytes]:
    """The files of ``channel``'s package, by their path in it, with their bytes."""
    if channel == "steam":
        return {STEAM_UNINSTALL.name: STEAM_UNINSTALL.read_bytes()}
    if channel == "itch":
        agreements = {f"licenses/{name}": text for name, text in itch_agreements().items()}
        return {".itch.toml": ITCH_MANIFEST.read_bytes(), **agreements}
    return {}


def write(depot: Path, channel: str) -> list[str]:
    """Writes ``channel``'s files in ``depot`` and returns their names. A file already there is not replaced."""
    wanted = files(channel)
    if taken := [name for name in wanted if (depot / name).exists()]:
        raise SystemExit(f"{depot} already has {', '.join(taken)}")
    for name, content in wanted.items():
        (depot / name).parent.mkdir(parents=True, exist_ok=True)
        (depot / name).write_bytes(content)
    return list(wanted)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depot", required=True, type=Path)
    parser.add_argument("--channel", required=True)
    arguments = parser.parse_args()
    written = write(arguments.depot, arguments.channel)
    print(f"package_channel: {arguments.channel}, {len(written)} files")


if __name__ == "__main__":
    main()
