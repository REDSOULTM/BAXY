"""Build balanced minimal contrasts for the selector's residual boundaries."""

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

DEFAULT_HELDOUT = REPO / "experiments" / "mind_router_spike" / "data" / "exact_operation_development.v1.jsonl"
DEFAULT_OUTPUT = REPO / "artifacts" / "research" / "functiongemma_contrastive_seed.v3.jsonl"

AUTHORED: dict[str, list[tuple[str, str]]] = {
    "audio.volume": [
        ("es", "Fija el volumen general exactamente en 25 por ciento."),
        ("es", "Deja el sonido del equipo al 60 por ciento."),
        ("es", "Establece el nivel de audio en 42."),
        ("es", "Pon los parlantes del PC a volumen 80."),
        ("en", "Set the master volume to exactly 25 percent."),
        ("en", "Put the computer sound at 60 percent."),
        ("en", "Set the audio level to 42."),
        ("en", "Put the PC speakers at volume 80."),
    ],
    "audio.volume.adjust": [
        ("es", "Sube nueve puntos el volumen que hay ahora."),
        ("es", "Baja el audio actual en once puntos."),
        ("es", "Aumenta cinco puntos porcentuales desde el nivel actual."),
        ("es", "Reduce en ocho puntos el sonido del PC."),
        ("en", "Raise the current volume by nine points."),
        ("en", "Lower the current audio by eleven points."),
        ("en", "Increase it five percentage points from the current level."),
        ("en", "Reduce the PC sound by eight points."),
    ],
    "audio.microphone.mute": [
        ("es", "Mutea solamente el micrófono."),
        ("es", "Silencia la entrada de voz del computador."),
        ("es", "Desmutea el micro del sistema."),
        ("es", "Vuelve a encender la captura del micrófono."),
        ("en", "Mute only the microphone."),
        ("en", "Silence the computer voice input."),
        ("en", "Unmute the system mic."),
        ("en", "Turn the microphone capture back on."),
    ],
    "audio.mute": [
        ("es", "Mutea solamente los parlantes."),
        ("es", "Silencia la salida de sonido del computador."),
        ("es", "Desmutea el audio del sistema."),
        ("es", "Vuelve a encender el sonido de los altavoces."),
        ("en", "Mute only the speakers."),
        ("en", "Silence the computer audio output."),
        ("en", "Unmute the system audio."),
        ("en", "Turn the speaker sound back on."),
    ],
    "browser.navigate": [
        ("es", "En el navegador controlado, ve a https://docs.python.org."),
        ("es", "Navega la sesión web actual a https://openstreetmap.org."),
        ("es", "Abre https://example.net en la pestaña CDP actual."),
        ("es", "Lleva el navegador que ya controlas a https://news.ycombinator.com."),
        ("en", "In the controlled browser, go to https://docs.python.org."),
        ("en", "Navigate the current web session to https://openstreetmap.org."),
        ("en", "Open https://example.net in the current CDP tab."),
        ("en", "Take the browser you already control to https://news.ycombinator.com."),
    ],
    "browser.navigate.named": [
        ("es", "Con Opera, ve a https://docs.python.org."),
        ("es", "Navega el perfil de Opera a https://openstreetmap.org."),
        ("es", "Abre https://example.net específicamente en Opera."),
        ("es", "Lleva Opera a https://news.ycombinator.com."),
        ("en", "With Opera, go to https://docs.python.org."),
        ("en", "Navigate the Opera profile to https://openstreetmap.org."),
        ("en", "Open https://example.net specifically in Opera."),
        ("en", "Take Opera to https://news.ycombinator.com."),
    ],
    "browser.page.read": [
        ("es", "Lee el texto visible de esta página web."),
        ("es", "Dime el título y contenido que aparecen en la página actual."),
        ("es", "Extrae el texto que puedo ver en esta pestaña."),
        ("es", "Cuéntame qué dice la web abierta ahora, sin navegar."),
        ("en", "Read the visible text on this web page."),
        ("en", "Tell me the title and content shown on the current page."),
        ("en", "Extract the text I can see in this tab."),
        ("en", "Tell me what the open web page says without navigating."),
    ],
    "browser.control": [
        ("es", "Recarga esta página sin cambiar de URL."),
        ("es", "Desplázate hacia arriba en la web actual."),
        ("es", "Vuelve atrás en el historial de esta pestaña."),
        ("es", "Pon en pantalla completa el video de la página."),
        ("en", "Reload this page without changing its URL."),
        ("en", "Scroll up on the current web page."),
        ("en", "Go back in this tab's history."),
        ("en", "Make the page video full screen."),
    ],
    "clipboard.write.text": [
        ("es", "Pon 'documento aprobado' dentro del portapapeles."),
        ("es", "Reemplaza el portapapeles por la frase 'llamar mañana'."),
        ("es", "Copia el texto literal 'todo listo' al portapapeles sin usar una selección."),
        ("es", "Guarda 'reporte enviado' como contenido nuevo del portapapeles."),
        ("en", "Put 'document approved' into the clipboard."),
        ("en", "Replace the clipboard with the phrase 'call tomorrow'."),
        ("en", "Write the literal text 'all ready' to the clipboard without a selection."),
        ("en", "Store 'report sent' as the new clipboard contents."),
    ],
    "clipboard.paste": [
        ("es", "Pega aquí lo que ya está en el portapapeles."),
        ("es", "Inserta el contenido actual del portapapeles en el control enfocado."),
        ("es", "Haz Ctrl+V en este campo."),
        ("es", "Pega el texto copiado en la ventana activa."),
        ("en", "Paste here what is already on the clipboard."),
        ("en", "Insert the current clipboard contents into the focused control."),
        ("en", "Press Ctrl+V in this field."),
        ("en", "Paste the copied text into the active window."),
    ],
    "media.play.query": [
        ("es", "Pon Back in Black de AC/DC."),
        ("es", "Quiero escuchar Imagine de John Lennon."),
        ("es", "Busca en Spotify y reproduce Africa de Toto."),
        ("es", "Reproduce una canción de Shakira."),
        ("en", "Play Back in Black by AC/DC."),
        ("en", "I want to hear Imagine by John Lennon."),
        ("en", "Search Spotify and play Africa by Toto."),
        ("en", "Play a Shakira song."),
    ],
    "media.play.exact": [
        ("es", "Reproduce el resultado exacto de Spotify que ya resolviste."),
        ("es", "Inicia esa pista exacta seleccionada anteriormente."),
        ("es", "Pon la coincidencia exacta que acabamos de elegir."),
        ("es", "Reproduce ese título exacto ya identificado en Spotify."),
        ("en", "Play the exact Spotify result you already resolved."),
        ("en", "Start that exact track selected earlier."),
        ("en", "Play the exact match we just chose."),
        ("en", "Play that exact title already identified in Spotify."),
    ],
    "media.status": [
        ("es", "¿Qué tema se escucha actualmente?"),
        ("es", "Dime el artista y título que suenan ahora."),
        ("es", "Consulta el estado de la reproducción actual sin cambiarla."),
        ("es", "¿Está pausada la música que tengo puesta?"),
        ("en", "What track can I hear at the moment?"),
        ("en", "Tell me the artist and title playing now."),
        ("en", "Check current playback status without changing it."),
        ("en", "Is the music I have on currently paused?"),
    ],
    "media.control": [
        ("es", "Pausa la canción actual."),
        ("es", "Pasa a la pista siguiente."),
        ("es", "Continúa la reproducción que está pausada."),
        ("es", "Vuelve a la pista anterior."),
        ("en", "Pause the current song."),
        ("en", "Skip to the next track."),
        ("en", "Continue the playback that is paused."),
        ("en", "Go back to the previous track."),
    ],
}


def build(heldout_path: Path) -> list[dict[str, Any]]:
    catalog = catalog_by_name()
    heldout = {normalize_text(str(row["text"])) for row in read_jsonl(heldout_path)}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for operation, examples in sorted(AUTHORED.items()):
        family = operation.split(".", 1)[0]
        tools = selection_tools(catalog, [*family_operations(catalog, family), NO_ACTION_OPERATION])
        for language, text in examples:
            normalized = normalize_text(text)
            if normalized in heldout:
                raise ValueError(f"contrastive seed overlaps heldout: {text}")
            key = f"{family}:{normalized}"
            if key in seen:
                raise ValueError(f"duplicate contrastive text: {text}")
            seen.add(key)
            digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
            rows.append({
                "schema": "baxy.functiongemma-selection-row.v1",
                "case_id": f"contrastive-authored-{digest}",
                "language": language,
                "text": text,
                "operation": operation,
                "family": family,
                "source": "core-contract-authored-contrastive-v3",
                "tools": tools,
            })
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
        "schema": "baxy.functiongemma-contrastive-seed-build.v3",
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

