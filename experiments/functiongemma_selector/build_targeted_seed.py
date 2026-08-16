"""Build contract-authored rows for leaves the generation committee under-covered."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
from typing import Any

from selector_common import (
    NO_ACTION_OPERATION,
    REPO,
    catalog_by_name,
    family_operations,
    normalize_text,
    read_jsonl,
    selection_tools,
    sha256,
    write_jsonl,
)

DEFAULT_HELDOUT = (
    REPO
    / "experiments"
    / "mind_router_spike"
    / "data"
    / "exact_operation_development.v1.jsonl"
)
DEFAULT_OUTPUT = REPO / "artifacts" / "research" / "functiongemma_targeted_seed.v1.jsonl"

# These utterances are authored from the exact Core descriptions and schemas.
# They intentionally express distinctions that the generator or reviewer
# collapsed. None is copied from the development oracle.
AUTHORED: dict[str, list[tuple[str, str]]] = {
    "audio.mute": [
        ("es", "Deja en silencio los parlantes del computador."),
        ("es", "Quita el mute de la salida de audio del equipo."),
        ("es", "Silencia por completo el sonido del sistema."),
        ("es", "Vuelve a activar el audio general del PC."),
        ("en", "Mute the computer speaker output."),
        ("en", "Unmute the PC's main audio output."),
        ("en", "Silence all system sound."),
        ("en", "Turn the computer sound back on."),
    ],
    "clipboard.copy": [
        ("es", "Copia la selección actual al portapapeles."),
        ("es", "Haz Ctrl+C con lo que tengo seleccionado."),
        ("es", "Guarda en el portapapeles el texto seleccionado."),
        ("es", "Copia este contenido seleccionado, sin pegarlo."),
        ("en", "Copy the current selection to the clipboard."),
        ("en", "Press Ctrl+C on what I selected."),
        ("en", "Put the selected text on the clipboard."),
        ("en", "Copy this selected content without pasting it."),
    ],
    "email.latest.reply": [
        ("es", "Responde el correo más reciente diciendo que llegaré a las cinco."),
        ("es", "Contesta al último email con: recibido, gracias."),
        ("es", "Respóndele al mensaje más nuevo de Outlook que estoy de acuerdo."),
        ("es", "Al correo que acaba de llegar, responde que lo revisaré mañana."),
        ("en", "Reply to the latest email saying I'll arrive at five."),
        ("en", "Answer the newest Outlook message with: received, thanks."),
        ("en", "Reply to the most recent email that I agree."),
        ("en", "Tell the sender of the latest message I'll review it tomorrow."),
    ],
    "filesystem.known.search": [
        ("es", "Busca informe-final.pdf dentro de mis Descargas."),
        ("es", "Encuentra archivos llamados presupuesto en mis Documentos."),
        ("es", "Busca en el Escritorio un archivo cuyo nombre contenga reunión."),
        ("es", "Revisa mis carpetas conocidas por un archivo llamado contrato.docx."),
        ("en", "Find final-report.pdf in my Downloads folder."),
        ("en", "Search my Documents for files named budget."),
        ("en", "Look on my Desktop for a file with meeting in its name."),
        ("en", "Search my standard Windows folders for contract.docx."),
    ],
    "filesystem.known.trash.named": [
        ("es", "Manda borrador.docx de Descargas a la papelera recuperable."),
        ("es", "Elimina informe-viejo.pdf de mis Documentos de forma recuperable."),
        ("es", "Mueve captura-antigua.png del Escritorio a la papelera."),
        ("es", "Busca temporal.txt en mis carpetas conocidas y envíalo a la papelera."),
        ("en", "Move draft.docx from Downloads to the recoverable trash."),
        ("en", "Trash old-report.pdf from my Documents folder."),
        ("en", "Move old-screenshot.png from the Desktop to trash."),
        ("en", "Find temporary.txt in my standard folders and trash it."),
    ],
    "filesystem.sandbox.move.named": [
        ("es", "Dentro del sandbox, mueve reporte.txt a archivo/reporte.txt."),
        ("es", "Mueve la copia única notas.md del sandbox a documentos/notas.md."),
        ("es", "En el espacio privado, pasa datos.csv a procesados/datos.csv."),
        ("es", "Reubica salida.log dentro del sandbox en logs/salida.log."),
        ("en", "Inside the sandbox, move report.txt to archive/report.txt."),
        ("en", "Move the unique notes.md sandbox file to documents/notes.md."),
        ("en", "In the private sandbox, move data.csv to processed/data.csv."),
        ("en", "Relocate output.log within the sandbox to logs/output.log."),
    ],
    "media.control": [
        ("es", "Pausa lo que está sonando ahora."),
        ("es", "Salta a la siguiente pista de la sesión actual."),
        ("es", "Reanuda la reproducción multimedia actual."),
        ("es", "Detén la música que se está reproduciendo."),
        ("en", "Pause the media playing right now."),
        ("en", "Skip to the next track in the current session."),
        ("en", "Resume the current media playback."),
        ("en", "Stop the music that is currently playing."),
    ],
    "package.install.commit": [
        ("es", "Sí, instala ahora el paquete de winget que acabas de preparar."),
        ("es", "Confirma y ejecuta esa instalación de paquete pendiente."),
        ("es", "Continúa con la instalación preparada y comprueba el recibo."),
        ("es", "Autoriza la instalación de winget que revisamos recién."),
        ("en", "Yes, install the winget package you just prepared."),
        ("en", "Confirm and run that pending package installation."),
        ("en", "Proceed with the prepared installation and check its receipt."),
        ("en", "Authorize the winget installation we just reviewed."),
    ],
    "system.settings.set": [
        ("es", "Pon el brillo exactamente al 40 por ciento."),
        ("es", "Fija la luz nocturna en 70 por ciento."),
        ("es", "Establece no molestar al cien por ciento."),
        ("es", "Deja el brillo del monitor en 55, no lo ajustes relativamente."),
        ("en", "Set the screen brightness to exactly 40 percent."),
        ("en", "Set night light to 70 percent."),
        ("en", "Set do not disturb to one hundred percent."),
        ("en", "Put monitor brightness at 55, not a relative adjustment."),
    ],
    "wifi.connect": [
        ("es", "Conecta ese perfil Wi-Fi que acabas de resolver."),
        ("es", "Usa el perfil WLAN seleccionado y conéctalo ahora."),
        ("es", "Conecta el perfil guardado que elegimos en el paso anterior."),
        ("es", "Activa esa identidad de red ya resuelta, sin volver a buscarla por nombre."),
        ("en", "Connect the Wi-Fi profile you just resolved."),
        ("en", "Use the selected WLAN profile and connect it now."),
        ("en", "Connect the saved profile chosen in the previous step."),
        ("en", "Connect that already resolved network identity without looking it up by name."),
    ],
}


def build(heldout_path: Path) -> list[dict[str, Any]]:
    catalog = catalog_by_name()
    unknown = set(AUTHORED) - catalog.keys()
    if unknown:
        raise ValueError(f"targeted seed references unknown operations: {sorted(unknown)}")
    heldout = {normalize_text(str(row["text"])) for row in read_jsonl(heldout_path)}
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for operation, examples in sorted(AUTHORED.items()):
        family = operation.split(".", 1)[0]
        tools = selection_tools(
            catalog, [*family_operations(catalog, family), NO_ACTION_OPERATION]
        )
        for language, text in examples:
            normalized = normalize_text(text)
            if normalized in heldout:
                raise ValueError(f"targeted seed overlaps heldout: {text}")
            key = f"{family}:{normalized}"
            if key in seen:
                raise ValueError(f"duplicate targeted text: {text}")
            seen.add(key)
            digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
            rows.append(
                {
                    "schema": "baxy.functiongemma-selection-row.v1",
                    "case_id": f"contract-authored-{digest}",
                    "language": language,
                    "text": text,
                    "operation": operation,
                    "family": family,
                    "source": "core-contract-authored-targeted-v1",
                    "tools": tools,
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--heldout", type=Path, default=DEFAULT_HELDOUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.heldout = args.heldout.resolve(strict=True)
    args.output = args.output.resolve()
    rows = build(args.heldout)
    write_jsonl(args.output, rows)
    report: dict[str, Any] = {
        "schema": "baxy.functiongemma-targeted-seed-build.v1",
        "rows": len(rows),
        "operations": dict(collections.Counter(row["operation"] for row in rows)),
        "languages": dict(collections.Counter(row["language"] for row in rows)),
        "heldout_exact_overlap": 0,
        "heldout_sha256": sha256(args.heldout),
        "output": str(args.output),
        "output_sha256": sha256(args.output),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

