"""Build a candidate-independent SAPI corpus for a fresh physical wake gate.

The corpus is generated only after the candidate is frozen.  This program never
loads or scores the candidate; it records its hash solely to prove temporal
ordering and to make accidental reuse visible in the resulting manifest.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import shutil
import tempfile
from typing import Any
import wave


SCHEMA = "baxy.sapi-wake-physical-holdout-source.v1"


@dataclass(frozen=True)
class UtteranceSpec:
    label: str
    language: str
    text: str
    rate: int
    volume: int


_POSITIVE_TEXTS = {
    "es": (
        "Basi",
        "Baxi",
        "Baxy",
        "Basi dime la hora",
        "Baxi abre la calculadora",
        "Baxy baja un poco el volumen",
        "Basi what time is it",
        "Baxi dime el clima de hoy",
        "Baxy what apps are running",
        "Baxi abre Spotify por favor",
        "Baxy dime cuánta batería queda",
        "Basi pon pausa",
        "Baxi qué tengo abierto",
        "Baxy recuérdame llamar mañana",
    ),
    "en": (
        "Baxy",
        "Backsy",
        "Basi",
        "Baxy tell me the time",
        "Backsy open the calculator",
        "Basi turn the volume down",
        "Baxy dime la hora",
        "Backsy open Spotify please",
        "Basi how much battery is left",
        "Backsy mute the computer",
        "Basi remember water tomorrow",
        "Baxy pause the music",
        "Backsy what is open right now",
        "Basi recuérdame llamar mañana",
    ),
}

_NEGATIVE_TEXTS = {
    "es": (
        "así está bien",
        "casi termino",
        "la base sigue firme",
        "el taxi ya llegó",
        "eso es básico",
        "pásame el vaso",
        "sí dime la hora",
        "abre la calculadora",
        "baja un poco el volumen",
        "dime cuánta batería queda",
        "pon pausa por favor",
        "qué tengo abierto",
        "recuérdame llamar mañana",
        "la frase se parece bastante",
        "vacía la lista anterior",
        "Maxi viene en camino",
        "Betsy llamó temprano",
        "Bessie cerró la puerta",
        "la caja está vacía",
        "mira hacia atrás y sigue",
        "parece fácil pero no lo es",
        "esta es una conversación normal",
        "puedes escucharme desde aquí",
        "todavía queda trabajo pendiente",
    ),
    "en": (
        "backseat drivers are distracting",
        "Betsy called this morning",
        "Bessie closed the door",
        "the box is empty",
        "I can almost see it",
        "the basic plan still works",
        "yes tell me the time",
        "open the calculator",
        "turn the volume down",
        "how much battery is left",
        "pause the music please",
        "what is open right now",
        "remind me to call tomorrow",
        "the phrase sounds rather similar",
        "Maxi is already on the way",
        "back see whether the light is on",
        "boxing practice starts at six",
        "the taxi has just arrived",
        "this is an ordinary conversation",
        "can you hear me from over there",
        "there is still some work pending",
        "please read the next sentence",
        "everything is quiet in the room",
        "we should check the result again",
    ),
}

_ENDPOINT_SUFFIX_DEVELOPMENT_POSITIVE_TEXTS = {
    "es": (
        "Baxy abre el explorador de archivos",
        "Basi muestrame los procesos activos",
        "Baxi sube el brillo de la pantalla",
        "Baxy take a screenshot for me",
        "Backsy busca vuelos para Santiago",
        "Basi crea una carpeta en documentos",
        "Baxi dime si Bluetooth esta encendido",
        "Baxy lee el ultimo mensaje",
    ),
    "en": (
        "Baxy open the settings window",
        "Backsy tell me how much memory is free",
        "Basi lower the screen brightness",
        "Baxy recuerdame revisar el correo",
        "Baxi show the downloads folder",
        "Backsy find my latest screenshot",
        "Basi turn on airplane mode",
        "Baxy what network am I using",
    ),
}

_ENDPOINT_SUFFIX_DEVELOPMENT_NEGATIVE_TEXTS = {
    "es": (
        "la receta basica necesita menos sal",
        "Betsy revisa el correo por la tarde",
        "el asiento trasero sigue libre",
        "casi todos llegaron temprano",
        "muestra los procesos activos",
        "sube el brillo de la pantalla",
        "abre el explorador de archivos",
        "lee el ultimo mensaje",
        "el vaso esta junto a la ventana",
        "el taxi espera fuera del edificio",
    ),
    "en": (
        "busy people often speak quickly",
        "back seat passengers should wait",
        "they see the settings window",
        "Bessie found the latest screenshot",
        "the basic network is still available",
        "open the downloads folder",
        "turn on airplane mode",
        "tell me how much memory is free",
        "boxing practice ends after sunset",
        "Maxi lowered the screen brightness",
    ),
}

_ENDPOINT_CONFUSABLE_DEVELOPMENT_POSITIVE_TEXTS = {
    "es": (
        "Basi muestrame los procesos activos",
        "Baxy take a screenshot for me",
        "Baxi baja el brillo de la pantalla",
        "Baxy abre la configuracion",
    ),
    "en": (
        "Basi lower the screen brightness",
        "Baxy take a screenshot for me",
        "Backsy show the active processes",
        "Baxi open the settings window",
    ),
}

_ENDPOINT_CONFUSABLE_DEVELOPMENT_NEGATIVE_TEXTS = {
    "es": (
        "Vas y muestrame los procesos activos",
        "Vas y muestra la pantalla despues",
        "Vas y toma una captura al final",
        "Vas y abre la configuracion luego",
        "Vas y bajas el volumen despacio",
        "Vasi toma el autobus manana",
        "Maxi toma una captura de la pantalla",
        "el taxi toma la siguiente salida",
        "Bessie baja el brillo de la pantalla",
        "la base y muestra otro resultado",
        "Basic lower the screen brightness",
        "Basic turn on airplane mode",
        "casi muestra los procesos activos",
    ),
    "en": (
        "Basic lower the screen brightness",
        "Basic lower the volume slowly",
        "Basic take a screenshot",
        "Basic turn on airplane mode",
        "back seat lower anchors are broken",
        "Maxi take a screenshot for me",
        "Bessie lower the screen brightness",
        "they see lower screen brightness",
        "the taxi takes a screenshot",
        "busy lower level processes remain active",
        "Betsy shows the active processes",
        "back seat passengers take the next exit",
        "the basic settings window remains open",
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_specs(
    *, label: str, count: int, seed: int, profile: str = "holdout"
) -> list[UtteranceSpec]:
    if label not in {"positive", "negative"} or count < 1:
        raise ValueError("sapi_wake_holdout_spec_invalid")
    profiles = {
        "holdout": (_POSITIVE_TEXTS, _NEGATIVE_TEXTS),
        "endpoint_suffix_development": (
            _ENDPOINT_SUFFIX_DEVELOPMENT_POSITIVE_TEXTS,
            _ENDPOINT_SUFFIX_DEVELOPMENT_NEGATIVE_TEXTS,
        ),
        "endpoint_confusable_development": (
            _ENDPOINT_CONFUSABLE_DEVELOPMENT_POSITIVE_TEXTS,
            _ENDPOINT_CONFUSABLE_DEVELOPMENT_NEGATIVE_TEXTS,
        ),
    }
    if profile not in profiles:
        raise ValueError("sapi_wake_holdout_profile_invalid")
    positive_texts, negative_texts = profiles[profile]
    texts = positive_texts if label == "positive" else negative_texts
    population = [
        UtteranceSpec(label, language, text, rate, volume)
        for language, language_texts in texts.items()
        for text in language_texts
        for rate in (-3, -1, 1, 3)
        for volume in (78, 90, 100)
    ]
    if count > len(population):
        raise ValueError("sapi_wake_holdout_population_insufficient")
    generator = random.Random(seed + (0 if label == "positive" else 1))
    return generator.sample(population, count)


def _language_code(token: Any) -> str:
    value = str(token.GetAttribute("Language")).split(";", maxsplit=1)[0]
    return value.upper().removeprefix("0X").zfill(4)


def _synthesize_group(
    *,
    output: Path,
    specs: list[UtteranceSpec],
    tokens: dict[str, Any],
    voice: Any,
    win32com_client: Any,
) -> list[dict[str, object]]:
    output.mkdir(parents=True)
    records: list[dict[str, object]] = []
    for index, spec in enumerate(specs):
        token = tokens[spec.language]
        path = output / f"clip_{index:06d}.wav"
        stream = win32com_client.Dispatch("SAPI.SpFileStream")
        stream.Open(str(path), 3, False)  # SSFMCreateForWrite
        try:
            voice.Voice = token
            voice.Rate = spec.rate
            voice.Volume = spec.volume
            voice.AudioOutputStream = stream
            voice.Speak(spec.text)
        finally:
            stream.Close()
        with wave.open(str(path), "rb") as source:
            if source.getsampwidth() != 2 or source.getnchannels() < 1:
                raise RuntimeError("sapi_wake_holdout_audio_invalid")
            seconds = source.getnframes() / source.getframerate()
        records.append(
            {
                "index": index,
                "audioSha256": _sha256(path),
                "textSha256": hashlib.sha256(spec.text.encode("utf-8")).hexdigest(),
                "language": spec.language,
                "rate": spec.rate,
                "volume": spec.volume,
                "seconds": seconds,
            }
        )
    return records


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--positive-count", type=int, default=96)
    parser.add_argument("--negative-count", type=int, default=192)
    parser.add_argument("--seed", type=int, default=20260810)
    parser.add_argument(
        "--profile",
        choices=(
            "holdout",
            "endpoint_suffix_development",
            "endpoint_confusable_development",
        ),
        default="holdout",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    candidate = args.candidate_manifest.resolve(strict=True)
    output = args.output_dir.resolve()
    if output.exists():
        raise SystemExit("Output directory already exists.")
    positive_specs = build_specs(
        label="positive",
        count=args.positive_count,
        seed=args.seed,
        profile=args.profile,
    )
    negative_specs = build_specs(
        label="negative",
        count=args.negative_count,
        seed=args.seed,
        profile=args.profile,
    )

    import pythoncom
    import win32com.client

    temporary = Path(tempfile.mkdtemp(prefix=f"{output.name}.", dir=output.parent))
    try:
        pythoncom.CoInitialize()
        try:
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            available = list(voice.GetVoices())
            tokens = {
                "es": next(
                    token for token in available if _language_code(token) == "080A"
                ),
                "en": next(
                    token for token in available if _language_code(token) == "0409"
                ),
            }
            positives = _synthesize_group(
                output=temporary / "positive",
                specs=positive_specs,
                tokens=tokens,
                voice=voice,
                win32com_client=win32com.client,
            )
            negatives = _synthesize_group(
                output=temporary / "negative",
                specs=negative_specs,
                tokens=tokens,
                voice=voice,
                win32com_client=win32com.client,
            )
            voices = {
                language: {
                    "description": str(token.GetDescription()),
                    "idSha256": hashlib.sha256(
                        str(token.Id).encode("utf-8")
                    ).hexdigest(),
                }
                for language, token in tokens.items()
            }
        finally:
            pythoncom.CoUninitialize()
        manifest = {
            "schema": SCHEMA,
            "createdAtUtc": datetime.now(timezone.utc).isoformat(),
            "candidateFrozenBeforeGeneration": True,
            "candidateManifestSha256": _sha256(candidate),
            "candidateLoadedOrScored": False,
            "seed": args.seed,
            "profile": args.profile,
            "voices": voices,
            "counts": {"positive": len(positives), "negative": len(negatives)},
            "specificationSha256": hashlib.sha256(
                json.dumps(
                    [
                        *(asdict(spec) for spec in positive_specs),
                        *(asdict(spec) for spec in negative_specs),
                    ],
                    ensure_ascii=False,
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest(),
            "records": {"positive": positives, "negative": negatives},
            "syntheticSpeech": True,
            "blindHumanPartitionAccessed": False,
            "developmentOnly": True,
            "effectsExecuted": 0,
        }
        (temporary / "manifest.v1.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temporary.replace(output)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    print(
        json.dumps(
            {
                "candidateManifestSha256": manifest["candidateManifestSha256"],
                "positive": len(positives),
                "negative": len(negatives),
                "output": str(output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
