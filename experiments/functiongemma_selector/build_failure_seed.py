"""Author concrete counterexamples for deterministic held-out failure clusters."""

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
DEFAULT_OUTPUT = REPO / "artifacts" / "research" / "functiongemma_failure_seed.v2.jsonl"

AUTHORED: dict[str, list[tuple[str, str]]] = {
    "audio.volume.adjust": [
        ("es", "Incrementa siete puntos porcentuales el volumen actual."),
        ("es", "Reduce doce puntos el nivel de sonido que tengo ahora."),
        ("es", "Desde el volumen actual, súbemelo ocho puntos."),
        ("es", "Bájale seis puntos al sonido del equipo."),
        ("en", "Raise the current volume by seven percentage points."),
        ("en", "Reduce the sound level by twelve points."),
        ("en", "From its current level, turn the volume up eight points."),
        ("en", "Bring the computer sound down by six points."),
    ],
    "browser.control": [
        ("es", "Vuelve a cargar la página web que estoy viendo."),
        ("es", "Desplaza la página actual hacia abajo."),
        ("es", "Regresa a la página anterior en esta pestaña."),
        ("es", "Cierra la página web actual."),
        ("en", "Reload the web page I'm viewing."),
        ("en", "Scroll the current page down."),
        ("en", "Go back to the previous page in this tab."),
        ("en", "Close the current web page."),
    ],
    "browser.navigate.named": [
        ("es", "Ve a https://openai.com usando específicamente Opera."),
        ("es", "Abre https://wikipedia.org en el perfil privado de Opera."),
        ("es", "Navega a https://example.org con Opera, no con otro navegador."),
        ("es", "Usa Opera para entrar a https://github.com."),
        ("en", "Go to https://openai.com specifically with Opera."),
        ("en", "Open https://wikipedia.org in Opera's private profile."),
        ("en", "Navigate to https://example.org using Opera, not another browser."),
        ("en", "Use Opera to visit https://github.com."),
    ],
    "clipboard.write.text": [
        ("es", "Reemplaza el portapapeles con el texto: informe terminado."),
        ("es", "Guarda la frase 'llamar al banco' en el portapapeles."),
        ("es", "Pon exactamente 'listo para enviar' en el portapapeles, sin pegarlo."),
        ("es", "Escribe 'reunión a las diez' dentro del portapapeles."),
        ("en", "Replace the clipboard contents with: report finished."),
        ("en", "Store the phrase 'call the bank' in the clipboard."),
        ("en", "Put exactly 'ready to send' on the clipboard without pasting it."),
        ("en", "Write 'meeting at ten' into the clipboard."),
    ],
    "media.play.exact": [
        ("es", "Reproduce ese resultado exacto de Spotify que acabamos de seleccionar."),
        ("es", "Abre la pista exacta ya resuelta en Spotify."),
        ("es", "Pon exactamente el resultado de Spotify elegido en el paso anterior."),
        ("es", "Inicia esa coincidencia musical exacta que ya encontraste."),
        ("en", "Play the exact Spotify result we just selected."),
        ("en", "Start the exact track already resolved in Spotify."),
        ("en", "Play exactly the Spotify result chosen in the previous step."),
        ("en", "Start that exact music match you already found."),
    ],
    "media.play.query": [
        ("es", "Pon una canción de Queen en Spotify."),
        ("es", "Reproduce Hotel California de Eagles."),
        ("es", "Busca y pon Billie Jean de Michael Jackson."),
        ("es", "Quiero escuchar Dreams de Fleetwood Mac."),
        ("en", "Play a Queen song on Spotify."),
        ("en", "Play Hotel California by the Eagles."),
        ("en", "Find and play Billie Jean by Michael Jackson."),
        ("en", "I want to hear Dreams by Fleetwood Mac."),
    ],
    "media.status": [
        ("es", "Dime qué canción está sonando ahora mismo."),
        ("es", "¿Quién canta la música que se reproduce ahora?"),
        ("es", "Muéstrame título y artista de la reproducción actual."),
        ("es", "¿La sesión multimedia actual está pausada o sonando?"),
        ("en", "Tell me which song is currently playing."),
        ("en", "Who is the artist playing right now?"),
        ("en", "Show the title and artist of the current playback."),
        ("en", "Is the current media session paused or playing?"),
    ],
    "reminder.create": [
        ("es", "Avísame de comprar leche mañana a las nueve."),
        ("es", "Crea un recordatorio para llamar a Ana el viernes a mediodía."),
        ("es", "Recuérdame pagar la cuenta el lunes a las ocho."),
        ("es", "Programa un recordatorio: tomar la medicina esta noche a las diez."),
        ("en", "Remind me to buy milk tomorrow at nine."),
        ("en", "Create a reminder to call Ana Friday at noon."),
        ("en", "Remind me to pay the bill Monday at eight."),
        ("en", "Schedule a reminder to take my medicine tonight at ten."),
    ],
    "system.status": [
        ("es", "Consulta cuánta RAM está ocupada en este momento."),
        ("es", "Muéstrame el uso actual de CPU y memoria."),
        ("es", "¿Cuánto espacio libre queda en el disco?"),
        ("es", "Dime el uso de la GPU de este computador ahora."),
        ("en", "Check how much RAM is in use right now."),
        ("en", "Show current CPU and memory usage."),
        ("en", "How much free disk space is left?"),
        ("en", "Tell me this computer's current GPU usage."),
    ],
}


def build(heldout_path: Path) -> list[dict[str, Any]]:
    catalog = catalog_by_name()
    heldout = {normalize_text(str(row["text"])) for row in read_jsonl(heldout_path)}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for operation, examples in sorted(AUTHORED.items()):
        if operation not in catalog:
            raise ValueError(f"unknown operation: {operation}")
        family = operation.split(".", 1)[0]
        tools = selection_tools(
            catalog, [*family_operations(catalog, family), NO_ACTION_OPERATION]
        )
        for language, text in examples:
            normalized = normalize_text(text)
            if normalized in heldout:
                raise ValueError(f"failure seed overlaps heldout: {text}")
            key = f"{family}:{normalized}"
            if key in seen:
                raise ValueError(f"duplicate failure seed text: {text}")
            seen.add(key)
            digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
            rows.append(
                {
                    "schema": "baxy.functiongemma-selection-row.v1",
                    "case_id": f"failure-authored-{digest}",
                    "language": language,
                    "text": text,
                    "operation": operation,
                    "family": family,
                    "source": "core-contract-authored-targeted-v2",
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
        "schema": "baxy.functiongemma-failure-seed-build.v2",
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

