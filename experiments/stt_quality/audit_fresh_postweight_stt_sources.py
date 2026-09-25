"""Audit fresh, post-weight STT sources without opening archive payloads.

The audit intentionally reads only public datasheets and repository metadata.
It never downloads audio archives, decodes audio, or emits the sample text that
Mozilla renders on its datasheets.  Those visible samples are reduced to a
normalized hash blocklist so a later reservation step can exclude them.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import unicodedata
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable


SCHEMA = "baxy.stt-fresh-source-audit.v1"
# Identity of the program tree a fresh STT source audit may bind itself to.
#
# The previous value belonged to the wake v17 physical campaign, which was
# opened once on 2026-08-11 and rejected (46/48 positives). That capture is
# consumed and can never be repeated, so its hash is now a historical record
# kept inside its own receipt, not a live freeze. The tree had in fact already
# moved past it before the request-completion repair landed: the roots below
# hold 396 Python files against the 344 the v17 preflight recorded. Goal 10.2.5
# added the shared power-efficient ONNX session policy and changed wake/voice
# loading without changing model, hop, score or corpus. Re-pinning
# is therefore a re-seal of an unmeasured expectation, never the reopening of
# a consumed one. C03 2026-09-03 re-sealed again after public compose started
# deriving the local clock from utc+offset; corpora and engines are unchanged.
# Any future physical campaign must re-seal against the tree it will actually
# measure.
WAKE_V17_HISTORICAL_PROGRAM_TREE_SHA256 = (
    "756a5b311b20ed833da182595766c9d577cca89f20d7a4355eb972576f0f90c0"
)
# C03 2026-09-05 (Opus): el árbol se movió al añadir
# src/baxy_mind/request_reading.py (lectura única del pedido), delegar en
# ella llm.py y __main__.py, y añadir dos ficheros de entrada al censo de
# prosa. Corpus, motores y hashes STT/TTS/wake del runtime registrado no
# cambian: esta actualización no afirma una medida de voz nueva.
# C03 2026-09-05 (Opus): el censo de prosa visible salta los docstrings de
# Python, como ya saltaba los comentarios. Corpus, motores y hashes
# STT/TTS/wake del runtime registrado no cambian: esta actualización no
# afirma una medida de voz nueva.
# C03 2026-09-05 (Opus): el compositor recibe el tema de un seguimiento
# elíptico y una explicación no puede ser sólo otra pregunta. Corpus,
# motores y hashes STT/TTS/wake del runtime registrado no cambian: esta
# actualización no afirma una medida de voz nueva.
# C03 2026-09-06 (Astra): pedido y contexto conservados en composicion;
# se retiran el saludo literal y el retorno de borradores rechazados.
# Cambia el arbol de programa esperado, no los corpus ni los motores
# STT/TTS/wake. No acredita una nueva aceptacion de voz.
# C03 Astra: hora AM/PM, tema y causa anidada conservados; lectura de explain.
# Prosa: conocimiento separado de observaciones, sin saludo recortado ni intro fija.
# C03 590: registered CPU prose adapter is isolated from other model roles.
# Historical STT/wake campaign pins remain unchanged; this declaration does
# not claim new audio acceptance.
# C03 post-goal 2026-09-20 (Fase 1): pytest verde sin relajar; 5pm/volumen de app/envoltura social/investigar el propio equipo reparados en la mente.
# C03 post-goal 2026-09-20 (Fase 1): pytest verde sin relajar; 5pm/volumen de app/envoltura social/investigar el propio equipo reparados en la mente.
# REOPEN1993: lecturas de la mente (candidato único, alarma de la sesión, otra ventana, mirar la pantalla, ponle texto)
# C03 REOPEN1957 typed tools (opus/typed-tools): re-pin after the mind readings of the fifteen typed capabilities.
# C03 post-goal: fusión de opus/typed-tools y BUILD2001 (nombre de app en app.open, turn.playback-then ordinario).
# C03 post-goal: fusión de Fase 6/7 y BUILD2003 (otra ventana, ventana activa).
# C03 post-goal: BUILD2005 (displayName en finales de app.open).
# C03 post-goal: BUILD2007 (finales de app.open y de tecleo; prohibición con clítico).
# C03 post-goal: BUILD2009 (alias bilingüe de apps).
# C03 post-goal: BUILD2011 (busqueda: clitico, cortesia, sitio).
# C03 post-goal: BUILD2013 (web.search en el shortlist; cortesia fuera del argumento).
# C03 post-goal: BUILD2017 (vocabulario propio del informe de busqueda).
# C03 post-goal: BUILD2021 (pista del veto de afirmacion sin fuente).
# C03 post-goal: BUILD2021b (guarda de get en el shortlist).
# C03 post-goal: BUILD2025 (frio/calor y clima del pasado).
# C03 post-goal: BUILD2027 (cabezas de pregunta en noticias).
# C03 post-goal: fusion opus/typed-tools 8c268599b + BUILD2029 (fuentes de titulares observadas).
# C03 post-goal: BUILD2031 (resultado de titulares sin enlace; fondo y zip).
# C03 post-goal: fusion e97802c9f + BUILD2033 (cabeza del lugar geocodificado).
# C03 Fase 8 (D18) audio.app.volume.set y verbos de desinstalación en Steam (b5fd9e50b + fusión 28432af9e): re-anclaje de identidad de programa.
# C03 notebook (cierre 2026-09-22): re-pin tras las tandas y reparaciones del notebook (WALLPAPER2039…WINGET2087)
# Fase 3.5 clase 1 (2026-09-22): dialogue_slot, reescritura contextual y harness semantic_replay/semantic_corpus.
# Fase 3.5 semantic S1–S2 (2026-09-23): normalize, lexicon, grammar, dialogue; guardas y veto.
# C03 Fase 3.5 semantic S3 (2026-09-23): trece dominios de effect_intent a src/baxy_mind/semantic/, oferta parcial de misiones compuestas, lectores de opinión/hecho fechado, vocativos, rechazo en el hueco.
# C03 Fase 3.5 semantic S3 (2026-09-23): trece dominios de effect_intent a src/baxy_mind/semantic/, oferta parcial de misiones compuestas, lectores de opinión/hecho fechado, vocativos, rechazo en el hueco.
# C03 Fase 3.5 semantic S4 (2026-09-23): acto de charla, deseo de escuchar, antecedente de pregunta pública, lecturas sin confirmar, volumen/brillo/medios/pantalla.
# C03 Fase 3.5 semantic S5 (2026-09-23): el orquestador del patrón pasa de effect_intent a src/baxy_mind/semantic/patterns.py (traslado puro).
# C03 Fase 3.5 semantic S5 (2026-09-23): orquestador a semantic/patterns.py; «averigua» fuera del lector de investigación (se usa para comprobaciones locales).
# C03 Fase 3.5 semantic S6 (2026-09-23): puerta semantic.reading.read(); verbo reproducir con voseo en un solo lugar (_PLAY_HEAD).
# C03 Fase 3.5 semantic S7 (2026-09-23): re-armado de destino por patrón.
# C03 Fase 3.5 semantic S8 (2026-09-23): lectura de la cien-99 (caché no es pretérito, hecho de request_analysis_failed natural, prohibición y asentimiento a un pedido vacío fuera del hueco).
# C03 Fase 3.5 semantic S8 (2026-09-23): lectura de la cien-99 y limpieza de ruff tras los traslados.
# C03 Fase 3.5 semantic S9 (2026-09-23): guardas de entrada sin pedido a semantic/guards.py (traslado puro).
# C03 Fase 3.5 semantic S9 (2026-09-23): guardas de entrada sin pedido a semantic/guards.py (traslado puro).
# C03 Fase 3.5 uso real 2026-09-23: guardia público/propio, vetos por familia, alarmas en hora local.
# C03 Fase 3.5 uso real 2026-09-23 (familia hechos/efectos): hora de otro lugar, identidad, escritorio, temporizador, límite llano, clima, edad y cargos.
# C03 Fase 3.5 uso real 2026-09-23: integración de los frentes composición, hechos, preguntas, niveles y latencia.
# C03 Fase 3.5 uso real 2026-09-23: lo que no sabe lo busca; evidencia de idioma de sustantivos del PC.
# C03 Fase 3.5 uso real 2026-09-23 (tanda 2): listas leídas, artículo al azar buscado, efectos y datos propios no afirmados en conversación.
# C03 Fase 3.5 uso real 2026-09-24: integración de la segunda ola (tanda 2).
# C03 Fase 3.5 uso real 2026-09-24: integración de la tercera ola (correo, medios, misc, agenda).
# C03 Fase 3.5 uso real 2026-09-24: integración de la cuarta ola (mecanismos de la tanda 3).
# C03 Fase 3.5 uso real 2026-09-24: integración de la quinta ola (tanda 4).
# C03 Fase 3.5 uso real 2026-09-24: correo compuesto y re-medición del veto.
# uso real sexta y séptima ola: agenda, correo/contactos/redes, composición 4c, lugar de la persona
# uso real: preguntas inútiles 4c y arreglos 4d
# uso real: web, hora de otro lugar, 4e
# uso real ola 8: tanda 5, latencia, concisión, búsqueda invisible
# uso real 5b y latencia estructural
# uso real 5c
# uso real ola 9: tanda 6
# uso real: 6b, menos llamadas, selector de un token
# uso real: contexto, sueltos 7, latencia 7, escritorio
# uso real ola 12: diálogo vivo, no inventar, vocabulario
# uso real ola 13: seguimientos
# uso real ola 14: tanda 9
# uso real: unificación de la lectura en semantic/
EXPECTED_PROGRAM_TREE_SHA256 = (
    "05d99e14ff2a8caea9779e7bebd318970d68c0525cd026e159d2077134d22b2d"
)
CONSUMED_BLIND_CONTRACT = (
    "artifacts/research/stt_real_audio_fusion_blind_preopen_contract_v1.json"
)
CONSUMED_BLIND_CONTRACT_SHA256 = (
    "24fb9ff12939968d9d951f8ca93c8d5268f102d6f3619e31016aecfbb18f297e"
)
PARAKEET_RELEASED_AT_UTC = "2025-08-14T00:00:00Z"
NEMOTRON_RELEASED_AT_UTC = "2026-06-04T00:00:00Z"
COMMON_VOICE_SNAPSHOT = "sps-corpus-4.0-2026-06-12"
MDC_FORBIDDEN_USAGE = (
    "It is forbidden to attempt to determine the identity of speakers in the "
    "Common Voice datasets. It is forbidden to re-host or re-share this dataset."
)
GIGASPEECHBENCH_API = "https://huggingface.co/api/datasets/speechcolab/GigaSpeechBench"
GIGASPEECHBENCH_COMMIT = "680d3057641b7507a1ef14974407c7b0a7964e64"
GIGASPEECHBENCH_LAST_MODIFIED = "2026-07-09T07:32:20.000Z"

MDC_EXPECTED: dict[str, dict[str, object]] = {
    "es": {
        "datasetId": "cmqi28y2v004imf076oh7e5zs",
        "url": ("https://mozilladatacollective.com/datasets/cmqi28y2v004imf076oh7e5zs"),
        "name": "Common Voice Spontaneous Speech 4.0 - Spanish",
        "citeAs": "common-voice-spontaneous-speech-4-0-span-c5b31fca",
        "dateCreated": "2026-06-17T12:41:58.663Z",
        "datePublished": "2026-06-17T12:41:58.662Z",
        "contentBytes": 28_931_716,
        "clips": 403,
        "recordedHours": 1.21,
        "validatedHours": 0.07,
        "speakers": 16,
        "validatedClips": 37,
        "pendingClips": 123,
        "untranscribedClips": 243,
        "trainClips": 0,
        "devClips": 0,
        "testClips": 0,
        "unassignedClips": 403,
    },
    "en": {
        "datasetId": "cmqialpeo0077nr077xqdqo0j",
        "url": ("https://mozilladatacollective.com/datasets/cmqialpeo0077nr077xqdqo0j"),
        "name": "Common Voice Spontaneous Speech 4.0 - English",
        "citeAs": "common-voice-spontaneous-speech-4-0-engl-c643378f",
        "dateCreated": "2026-06-17T16:35:50.880Z",
        "datePublished": "2026-06-17T16:35:50.879Z",
        "contentBytes": 522_005_930,
        "clips": 5_679,
        "recordedHours": 17.58,
        "validatedHours": 7.81,
        "speakers": 609,
        "validatedClips": 2_305,
        "pendingClips": 120,
        "untranscribedClips": 3_254,
        "trainClips": 1_519,
        "devClips": 409,
        "testClips": 377,
        "unassignedClips": 3_374,
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalized_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", html.unescape(value)).casefold()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


class _MdcPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.json_ld: list[str] = []
        self.sample_items: dict[str, list[str]] = {
            "questions": [],
            "responses": [],
        }
        self._script_is_json_ld = False
        self._script_parts: list[str] = []
        self._heading_tag: str | None = None
        self._heading_parts: list[str] = []
        self._sample_section: str | None = None
        self._list_item_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script":
            self._script_is_json_ld = (
                attributes.get("type", "").casefold() == "application/ld+json"
            )
            self._script_parts = []
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._heading_tag = tag
            self._heading_parts = []
        elif tag == "li" and self._sample_section is not None:
            self._list_item_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            if self._script_is_json_ld:
                self.json_ld.append("".join(self._script_parts))
            self._script_is_json_ld = False
            self._script_parts = []
            return
        if tag == self._heading_tag:
            heading = " ".join("".join(self._heading_parts).split()).casefold()
            if heading == "questions":
                self._sample_section = "questions"
            elif heading == "responses":
                self._sample_section = "responses"
            else:
                self._sample_section = None
            self._heading_tag = None
            self._heading_parts = []
        elif tag == "li" and self._list_item_parts is not None:
            item = " ".join("".join(self._list_item_parts).split())
            if item and self._sample_section is not None:
                self.sample_items[self._sample_section].append(item)
            self._list_item_parts = None

    def handle_data(self, data: str) -> None:
        if self._script_is_json_ld:
            self._script_parts.append(data)
            return
        if data.strip():
            self.text_parts.append(data)
        if self._heading_tag is not None:
            self._heading_parts.append(data)
        if self._list_item_parts is not None:
            self._list_item_parts.append(data)


def _integer(value: str) -> int:
    return int(value.replace(",", ""))


def _decode_embedded_text(value: str) -> str:
    value = re.sub(
        r"\\u([0-9a-fA-F]{4})",
        lambda match: chr(int(match.group(1), 16)),
        value,
    )
    return value.replace(r"\n", "\n").replace(r"\r", "\r").replace(r"\t", "\t")


def _section(text: str, start: str, end: str) -> str:
    start_index = text.index(start) + len(start)
    end_index = text.index(end, start_index)
    return text[start_index:end_index]


def _count(section: str, label: str) -> int:
    match = re.search(
        rf"{re.escape(label)}\s*(?:\|\s*)?([\d,]+)(?:\s*\|?\s*[\d.]+%)?",
        section,
        flags=re.IGNORECASE,
    )
    if match is None:
        raise RuntimeError(f"mdc_count_missing:{label}")
    return _integer(match.group(1))


def _sample_hashes(parser: _MdcPageParser) -> dict[str, object]:
    result: dict[str, object] = {}
    all_hashes: list[str] = []
    for section in ("questions", "responses"):
        items = parser.sample_items[section]
        if len(items) != 5:
            raise RuntimeError(f"mdc_sample_count_changed:{section}:{len(items)}")
        hashes = [
            hashlib.sha256(_normalized_text(item).encode("utf-8")).hexdigest()
            for item in items
        ]
        if len(set(hashes)) != len(hashes):
            raise RuntimeError(f"mdc_duplicate_page_samples:{section}")
        result[f"{section}Count"] = len(hashes)
        result[f"{section}NormalizedSha256"] = hashes
        all_hashes.extend(hashes)
    result["manifestSha256"] = _canonical_sha256(sorted(all_hashes))
    return result


def extract_mdc_page(page: str) -> dict[str, object]:
    parser = _MdcPageParser()
    parser.feed(page)
    datasets = []
    for payload in parser.json_ld:
        candidate = json.loads(payload)
        if candidate.get("@type") == "sc:Dataset":
            datasets.append(candidate)
    if len(datasets) != 1:
        raise RuntimeError(f"mdc_json_ld_dataset_count_changed:{len(datasets)}")
    dataset = datasets[0]
    text = _decode_embedded_text(" ".join(" ".join(parser.text_parts).split()))
    stats = re.search(
        r"dataset contains\s+([\d,]+)\s+clips representing\s+([\d.]+)\s+"
        r"hours of recorded speech\s+\(([\d.]+)\s+hours validated\)\s+from\s+"
        r"([\d,]+)\s+speakers",
        text,
        flags=re.IGNORECASE,
    )
    if stats is None:
        raise RuntimeError("mdc_summary_stats_missing")
    audio = _section(text, "Audio clips", "Training splits")
    training = _section(text, "Training splits", "Transcriptions")
    cite_as = str(dataset["citeAs"])
    filename = f"{cite_as}.tar.gz"
    if filename not in page:
        raise RuntimeError("mdc_archive_filename_missing")
    forbidden_usage_present = MDC_FORBIDDEN_USAGE in text
    if not forbidden_usage_present:
        raise RuntimeError("mdc_forbidden_usage_changed")
    result = {
        "datasetId": str(dataset["@id"]).rsplit("/", 1)[-1],
        "url": dataset["@id"],
        "name": dataset["name"],
        "citeAs": cite_as,
        "archiveFilename": filename,
        "dateCreated": dataset["dateCreated"],
        "datePublished": dataset["datePublished"],
        "language": dataset["inLanguage"],
        "license": dataset["license"],
        "version": dataset["version"],
        "contentBytes": int(dataset["contentSize"]),
        "snapshot": COMMON_VOICE_SNAPSHOT,
        "clips": _integer(stats.group(1)),
        "recordedHours": float(stats.group(2)),
        "validatedHours": float(stats.group(3)),
        "speakers": _integer(stats.group(4)),
        "validatedClips": _count(audio, "Transcribed & Validated"),
        "pendingClips": _count(audio, "Transcribed & Pending"),
        "untranscribedClips": _count(audio, "Not transcribed"),
        "trainClips": _count(training, "Train"),
        "devClips": _count(training, "Dev"),
        "testClips": _count(training, "Test"),
        "unassignedClips": _count(training, "Unassigned"),
        "realHumanSpeech": True,
        "speechStyle": "spontaneous_responses_to_questions",
        "forbiddenUsage": MDC_FORBIDDEN_USAGE,
        "pageSamples": _sample_hashes(parser),
    }
    result["normalizedSourceMetadataSha256"] = _canonical_sha256(result)
    return result


def _validate_mdc(language: str, observed: dict[str, object]) -> None:
    expected = MDC_EXPECTED[language]
    for key, value in expected.items():
        if observed.get(key) != value:
            raise RuntimeError(
                f"mdc_source_changed:{language}:{key}:{observed.get(key)!r}:{value!r}"
            )
    if observed["license"] != "https://spdx.org/licenses/CC0-1.0.html":
        raise RuntimeError(f"mdc_license_changed:{language}")
    if observed["language"] != language:
        raise RuntimeError(f"mdc_language_changed:{language}")


def _fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json,text/html;q=0.9",
            "User-Agent": "BAXY-STT-source-audit/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def _program_tree(repository_root: Path) -> dict[str, object]:
    roots = (
        repository_root / "experiments" / "voice_latency",
        repository_root / "scripts",
        repository_root / "src" / "baxy_mind",
    )
    files: dict[str, Path] = {}
    for root in roots:
        for path in root.rglob("*.py"):
            if path.is_file() and not path.is_symlink():
                files[path.relative_to(repository_root).as_posix()] = path
    digest = hashlib.sha256()
    for relative in sorted(files):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\n")
        digest.update(_sha256(files[relative]).encode("ascii"))
        digest.update(b"\n")
    result = {
        "schema": "baxy.wake-validation-program-tree.v1",
        "roots": [
            "experiments/voice_latency",
            "scripts",
            "src/baxy_mind",
        ],
        "pythonFiles": len(files),
        "sha256": digest.hexdigest(),
    }
    if result["sha256"] != EXPECTED_PROGRAM_TREE_SHA256:
        raise RuntimeError("wake_program_tree_changed")
    return result


def _model_binding(repository_root: Path) -> dict[str, object]:
    contract_path = repository_root / CONSUMED_BLIND_CONTRACT
    if _sha256(contract_path) != CONSUMED_BLIND_CONTRACT_SHA256:
        raise RuntimeError("consumed_blind_contract_changed")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    return {
        "consumedBlindContract": {
            "path": CONSUMED_BLIND_CONTRACT,
            "sha256": CONSUMED_BLIND_CONTRACT_SHA256,
        },
        "primary": {
            "model": "nvidia/parakeet-tdt-0.6b-v3",
            "releasedAtUtc": PARAKEET_RELEASED_AT_UTC,
            "localAssetDirectory": contract["runtime"]["sttDirectory"],
            "localAssetSha256": contract["runtime"]["sttSha256"],
        },
        "fallback": {
            "model": contract["nemotron"]["model"],
            "releasedAtUtc": NEMOTRON_RELEASED_AT_UTC,
            "conversion": contract["nemotron"]["conversion"],
            "files": contract["nemotron"]["files"],
        },
    }


def _audit_gigaspeechbench(payload: str) -> dict[str, object]:
    source = json.loads(payload)
    filenames = sorted(item["rfilename"] for item in source["siblings"])
    license_tags = sorted(
        tag for tag in source.get("tags", []) if tag.startswith("license:")
    )
    expected = {
        "sha": GIGASPEECHBENCH_COMMIT,
        "lastModified": GIGASPEECHBENCH_LAST_MODIFIED,
        "gated": False,
        "private": False,
    }
    for key, value in expected.items():
        if source.get(key) != value:
            raise RuntimeError(f"gigaspeechbench_source_changed:{key}")
    if len(filenames) != 155:
        raise RuntimeError("gigaspeechbench_file_count_changed")
    if any(
        name.casefold() in {"license", "license.txt", "license.md"}
        for name in filenames
    ):
        raise RuntimeError("gigaspeechbench_license_file_appeared_reaudit_required")
    if license_tags:
        raise RuntimeError("gigaspeechbench_license_tag_appeared_reaudit_required")
    return {
        "name": "GigaSpeechBench",
        "repository": "https://huggingface.co/datasets/speechcolab/GigaSpeechBench",
        "paper": "https://arxiv.org/abs/2606.28884",
        "commit": source["sha"],
        "lastModifiedAtUtc": source["lastModified"],
        "files": len(filenames),
        "gated": source["gated"],
        "private": source["private"],
        "paperReportedSource": "recent YouTube videos",
        "paperReportedSpeechStyle": "spontaneous",
        "paperReportedManualTranscriptionAccuracyAbove": 0.98,
        "repositoryLicenseFilePresent": False,
        "repositoryLicenseTagPresent": False,
        "eligibleForFinalCertifiedHoldout": False,
        "rejectionReason": "audio_data_license_absent_and_youtube_provenance",
        "audioDownloaded": False,
        "transcriptsOpenedByBaxyCampaign": False,
    }


def build_audit(
    *,
    repository_root: Path,
    audited_at_utc: str,
    fetch_text: Callable[[str], str] = _fetch_text,
) -> dict[str, object]:
    repository_root = repository_root.resolve(strict=True)
    common_voice: dict[str, object] = {}
    for language in ("es", "en"):
        source = MDC_EXPECTED[language]
        observed = extract_mdc_page(fetch_text(str(source["url"])))
        _validate_mdc(language, observed)
        observed["archiveAcquired"] = False
        observed["modelAudioDecoded"] = False
        observed["referenceTranscriptOpenedByBaxyCampaign"] = False
        observed["authenticatedDownloadRequired"] = True
        observed["pageSampleTextEmittedInAudit"] = False
        observed["pageSampleHashesMustBeExcludedFromReservation"] = True
        common_voice[language] = observed

    gigaspeechbench = _audit_gigaspeechbench(fetch_text(GIGASPEECHBENCH_API))
    model_binding = _model_binding(repository_root)
    return {
        "schema": SCHEMA,
        "auditedAtUtc": audited_at_utc,
        "generator": {
            "path": Path(__file__).resolve().relative_to(repository_root).as_posix(),
            "sha256": _sha256(Path(__file__).resolve()),
        },
        "role": "preacquisition_audit_for_fresh_independent_bilingual_stt_holdout",
        "status": "ready_pending_authenticated_common_voice_acquisition",
        "previousBlindCampaignConsumed": True,
        "previousBlindResultsMayBeUsedForTuning": False,
        "modelBinding": model_binding,
        "sources": {
            "commonVoiceSpontaneousSpeech4": common_voice,
            "gigaSpeechBench": gigaspeechbench,
        },
        "decision": {
            "selectedSource": "Common Voice Spontaneous Speech 4.0",
            "sourceSnapshotPostdatesBothModelReleases": True,
            "realHumanSpontaneousEnglish": True,
            "realHumanSpontaneousSpanish": True,
            "licenseClearForEvaluation": True,
            "englishEligibleAfterAcquisition": True,
            "spanishEligibleAfterAcquisition": True,
            "spanishValidatedClips": 37,
            "spanishSufficientAloneForFinalCertification": False,
            "containsNaturalSpanglish": False,
            "sufficientAloneForFinalBilingualAndSpanglishCertification": False,
            "gigaSpeechBenchRejectedRatherThanSilentlyAdopted": True,
            "nextRequiredSteps": [
                "authenticate_to_mozilla_data_collective_without_rehosting",
                "download_and_hash_exact_en_and_es_archives",
                "reserve_speaker_disjoint_validated_rows_before_any_model_decode",
                "exclude_every_datasheet_sample_by_normalized_sha256",
                "freeze_evaluator_and_exact_0.99_semantic_and_anchor_thresholds",
                "add_a_separate_real_human_spanglish_and_accent_holdout",
            ],
        },
        "auditContract": {
            "audioArchivesDownloaded": False,
            "audioDecoded": False,
            "referenceTranscriptsOpened": False,
            "caseIdsSelected": False,
            "thresholdsChanged": False,
            "candidatePromoted": False,
            "effectsExecuted": 0,
        },
        "wakeProgramTree": _program_tree(repository_root),
        "effectsExecuted": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--audited-at-utc", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    audit = build_audit(
        repository_root=arguments.repository_root,
        audited_at_utc=arguments.audited_at_utc,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(arguments.output),
                "status": audit["status"],
                "selectedSource": audit["decision"]["selectedSource"],
                "effectsExecuted": audit["effectsExecuted"],
                "programTreeSha256": audit["wakeProgramTree"]["sha256"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
