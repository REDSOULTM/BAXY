"""Streaming parsers and binary inventory for Goal 09.5.4.

Processes structured files whole (hash + counts + schema + extremes +
errors + head/tail samples) without loading bodies into chat. Binary
inventory records identity; existence is not 'works'.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
import shutil
import sqlite3
import struct
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, deque
from pathlib import Path
from typing import Any

CHUNK = 1024 * 1024
JSON_DOM_CAP = 64 * 1024 * 1024
LINE_PARSE_CAP = 1_048_576
SAMPLE_CHARS = 240
HEAD_N = 2
TAIL_N = 2
SAFETENSORS_HEADER_CAP = 16 * 1024 * 1024

PERSONAL_RE = re.compile(
    r"(?i)(?:[a-z]:\\(?:users|perfil)\\[^\\]+)|(?:/users/[^/]+)|(?:/home/[^/]+)"
)

STRUCT_SUFFIXES = frozenset(
    {
        ".json",
        ".jsonl",
        ".log",
        ".err",
        ".csv",
        ".tsv",
        ".yaml",
        ".yml",
        ".xml",
        ".trx",
        ".html",
        ".css",
        ".sha256",
        ".toc",
        ".txt",
        ".md",
        ".sums",
    }
)
SQLITE_SUFFIXES = frozenset({".db", ".sqlite", ".sqlite3"})
AUDIO_SUFFIXES = frozenset({".wav", ".ogg", ".mp3", ".flac"})
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"})
MODEL_SUFFIXES = frozenset(
    {".gguf", ".safetensors", ".pt", ".pth", ".npz", ".npy", ".onnx", ".bin"}
)
ARCHIVE_SUFFIXES = frozenset({".zip", ".7z", ".rar", ".tar"})
DOC_BIN_SUFFIXES = frozenset({".pdf", ".docx", ".pptx", ".xlsx"})
NATIVE_SUFFIXES = frozenset({".dll", ".exe", ".pyd", ".so", ".dylib"})
RUST_BUILD_SUFFIXES = frozenset({".rlib", ".rmeta"})
DOTNET_BUILD_SUFFIXES = frozenset({".dll", ".exe", ".pyd", ".lib", ".exp", ".pdb"})
RUST_CACHE_NAMES = frozenset(
    {"root-output", "the-real-index", "log", "output", "index"}
)
BROWSER_CACHE_NAMES = frozenset(
    {
        "preferences",
        "secure preferences",
        "local state",
        "history",
        "web data",
        "network persistent state",
        "edgesettings",
        "toptraffic",
    }
)


def strip_personal(value: Any) -> Any:
    if isinstance(value, str):
        return PERSONAL_RE.sub("<home>", value)
    if isinstance(value, list):
        return [strip_personal(item) for item in value]
    if isinstance(value, dict):
        return {key: strip_personal(item) for key, item in value.items()}
    return value


def _clip(value: str, limit: int = SAMPLE_CHARS) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def sha256_and_size(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def sniff_magic(path: Path, n: int = 256) -> bytes:
    with path.open("rb") as handle:
        return handle.read(n)


def sniff_encoding(prefix: bytes) -> str:
    if prefix.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if prefix.startswith(b"\xfe\xff"):
        return "utf-16-be"
    if prefix.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    return "utf-8"


def format_from_magic(magic: bytes, suffix: str) -> str:
    if magic.startswith(b"GGUF"):
        return "gguf"
    if magic.startswith(b"RIFF") and magic[8:12] == b"WAVE":
        return "wav"
    if magic.startswith(b"\x89PNG"):
        return "png"
    if magic.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if magic.startswith(b"SQLite format 3"):
        return "sqlite"
    if magic.startswith(b"\x1f\x8b"):
        return "gzip"
    if magic.startswith(b"PK\x03\x04"):
        return "zip"
    if magic.startswith(b"MZ"):
        return "pe"
    if magic.startswith(b"%PDF"):
        return "pdf"
    if magic.startswith(b"\x7fELF"):
        return "elf"
    if suffix:
        return suffix.lstrip(".")
    return "unknown"


def consumers_for(rel: str) -> str:
    lower = rel.replace("\\", "/").lower()
    if "wake_false_positive" in lower:
        return "wake negative eval (false positives; preserve, do not drop)"
    if "voice_recording" in lower or "/stt" in lower or "wake" in lower:
        return "wake/STT training or eval"
    if "/rirs/" in lower or "/rir" in lower:
        return "acoustic augmentation (RIR)"
    if "functiongemma" in lower or "finetune_llm" in lower:
        return "FunctionGemma finetune / llama-server tool-calling"
    if "gemma4" in lower or "llama-server" in lower or ".gguf" in lower:
        return "runtime LLM (llama-server / gemma4_agent)"
    if "technology_tournament" in lower:
        return "technology tournament experiment (not product runtime)"
    if "holdout" in lower or "/eval" in lower:
        return "historical eval/holdout; check train/eval split before reuse"
    if "router" in lower:
        return "mind router / language routing experiments"
    if "memory" in lower or lower.endswith(".db") or lower.endswith(".sqlite"):
        return "historical sqlite memory/store"
    if "agentes/privado" in lower:
        return "prior-agent session traces (sensitive; metadata only)"
    return "historical artifact; consumers pending 09.5.9"


def recipe_for(rel: str) -> str:
    lower = rel.replace("\\", "/").lower()
    if lower.endswith(".gguf"):
        return "quantized GGUF from sibling snapshot; recipe not re-run"
    if lower.endswith(".safetensors") or "/ckpt/" in lower or "checkpoint" in lower:
        return "training checkpoint in sibling tree; do not resume here"
    if lower.endswith(".wav"):
        return "captured or corpus audio in sibling snapshot"
    if "optimizer.pt" in lower:
        return "Adam (or peer) optimizer state from a finetune run; not a model"
    return "identity from 09.5.1 queued hash + on-disk inventory; no retraining"


def benchmark_for(rel: str) -> str:
    lower = rel.replace("\\", "/").lower()
    if "holdout" in lower:
        return "holdout named by path; denominator must come from the eval record"
    if "false_positive" in lower:
        return "negative/false-positive set; not an accuracy headline"
    if "tournament" in lower:
        return "technology_tournament round artifacts"
    if "eval" in lower or "gate" in lower:
        return "historical gate/eval beside this file, if any"
    return "none recovered in this campaign"


def owner_for(rel: str) -> str:
    lower = rel.replace("\\", "/").lower()
    if any(key in lower for key in ("wake", "stt", "tts", "voice", "audio", "piper")):
        return "src/baxy_mind/ (voz; Goal 09.5.6) + 09.5.9"
    if any(key in lower for key in ("router", "prompt", "mind", "llm", "gemma")):
        return "src/baxy_mind/ + Goal 09.5.5"
    if any(key in lower for key in ("catalog", "tool", "schema", "mission")):
        return "src/Baxy.Kernel/ + Goal 09.5.7"
    if any(key in lower for key in ("memory", "sqlite", "jarvis")):
        return "src/Baxy.Providers.Windows/Memory/ + Goal 09.5.8"
    return "documentacion/herencia/ (mapa Goal 01) + owner por pieza en 09.5.9"


def classify_action(rel: str) -> dict[str, str]:
    posix = rel.replace("\\", "/")
    lower = posix.lower()
    name = posix.rsplit("/", 1)[-1]
    suffix = Path(name).suffix.lower()
    stem_l = name.lower()

    if suffix in RUST_BUILD_SUFFIXES:
        return {"action": "exclude", "rule": "rust_build_artifact"}
    if suffix == ".d" and (
        "/round_b/" in lower
        or "/rust_core/" in lower
        or "baxy-rust" in lower
        or "baxy_rust" in lower
        or re.search(r"[a-z]-[0-9a-f]{16}\.d$", stem_l)
    ):
        return {"action": "exclude", "rule": "rust_depfile"}
    if suffix == ".pdb":
        return {"action": "exclude", "rule": "debug_symbol"}
    if ("/bin/" in lower or "/obj/" in lower) and suffix in DOTNET_BUILD_SUFFIXES:
        return {"action": "exclude", "rule": "dotnet_build_output"}
    if stem_l in RUST_CACHE_NAMES and (
        "technology_tournament" in lower or "rust_core" in lower
    ):
        return {"action": "exclude", "rule": "rust_incremental_cache"}
    if stem_l in BROWSER_CACHE_NAMES:
        return {"action": "exclude", "rule": "browser_profile_cache"}
    if stem_l.startswith("data_") and stem_l[5:].isdigit() and (
        "technology_tournament" in lower or "rust_core" in lower
    ):
        return {"action": "exclude", "rule": "rust_incremental_cache"}
    if name.endswith(".db-shm"):
        return {"action": "exclude", "rule": "sqlite_runtime_shm"}

    if (
        suffix in STRUCT_SUFFIXES
        or ".jsonl" in stem_l
        or suffix in {".yaml", ".yml"}
        or name.lower() in {"sha256sums", "modelfile", "license", "copying"}
    ):
        return {"action": "parse"}
    if suffix in SQLITE_SUFFIXES or name.endswith(".db-wal"):
        return {"action": "parse"}
    if suffix == ".gz":
        return {"action": "parse"}
    if suffix in (
        AUDIO_SUFFIXES
        | IMAGE_SUFFIXES
        | MODEL_SUFFIXES
        | ARCHIVE_SUFFIXES
        | DOC_BIN_SUFFIXES
        | NATIVE_SUFFIXES
        | {".dat", ".lib", ".exp", ".pma"}
    ):
        return {"action": "inventory"}
    if suffix == "":
        if stem_l in {"license", "copying", "notice", "modelfile", "sha256sums"}:
            return {"action": "parse"}
        return {"action": "inventory"}
    return {"action": "inventory"}


def _sample(offset: int, line: int, text: str) -> dict[str, Any]:
    return {
        "offset": offset,
        "line": line,
        "text": _clip(strip_personal(text), SAMPLE_CHARS),
    }


def parse_jsonl(path: Path) -> dict[str, Any]:
    prefix = sniff_magic(path, 4)
    encoding = sniff_encoding(prefix)
    digest = hashlib.sha256()
    size = 0
    rows = 0
    empty = 0
    errors: list[dict[str, Any]] = []
    key_freq: Counter[str] = Counter()
    status_freq: Counter[str] = Counter()
    numeric: dict[str, dict[str, float]] = {}
    head: list[dict[str, Any]] = []
    tail: deque[dict[str, Any]] = deque(maxlen=TAIL_N)
    first_offset = 0
    last_offset = 0
    max_line = 0
    min_line: int | None = None
    line_no = 0
    newline = b"\n"
    if encoding == "utf-16-le":
        newline = b"\n\x00"
    elif encoding == "utf-16-be":
        newline = b"\x00\n"

    def handle_line(offset: int, raw: bytes) -> None:
        nonlocal rows, empty, line_no, last_offset, max_line, min_line
        line_no += 1
        last_offset = offset
        max_line = max(max_line, len(raw))
        min_line = len(raw) if min_line is None else min(min_line, len(raw))
        body = raw[:-1] if raw.endswith(b"\n") else raw
        if encoding.startswith("utf-16") and body.endswith(b"\x00"):
            body = body[:-1]
        if not body.strip():
            empty += 1
            return
        try:
            text = body.decode(encoding, errors="replace")
        except LookupError:
            text = body.decode("utf-8", errors="replace")
        if len(body) > LINE_PARSE_CAP:
            errors.append(
                {"line": line_no, "offset": offset, "error": "line_too_long"}
            )
            sample = _sample(offset, line_no, text)
            if len(head) < HEAD_N:
                head.append(sample)
            tail.append(sample)
            return
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            errors.append(
                {
                    "line": line_no,
                    "offset": offset,
                    "error": strip_personal(str(exc)),
                }
            )
            parsed = None
        rows += 1
        if isinstance(parsed, dict):
            for key in parsed:
                key_freq[str(key)] += 1
            for status_key in ("ok", "pass", "passed", "status", "result", "verdict"):
                if status_key in parsed:
                    status_freq[f"{status_key}={parsed[status_key]}"] += 1
            for key, value in parsed.items():
                if isinstance(value, bool):
                    continue
                if isinstance(value, (int, float)):
                    slot = numeric.setdefault(
                        str(key), {"min": float(value), "max": float(value)}
                    )
                    slot["min"] = min(slot["min"], float(value))
                    slot["max"] = max(slot["max"], float(value))
        sample = _sample(offset, line_no, text)
        if len(head) < HEAD_N:
            head.append(sample)
        tail.append(sample)

    with path.open("rb") as handle:
        leftover = b""
        offset = 0
        while True:
            chunk = handle.read(CHUNK)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
            leftover += chunk
            *parts, leftover = leftover.split(newline)
            for raw in parts:
                handle_line(offset, raw + newline)
                offset += len(raw) + len(newline)
        if leftover:
            handle_line(offset, leftover)

    schema_keys = [key for key, _ in key_freq.most_common(80)]
    return strip_personal(
        {
            "parser": "jsonl",
            "encoding": encoding,
            "bytes": size,
            "sha256": digest.hexdigest(),
            "rows": rows,
            "empty_lines": empty,
            "schema": {
                "keys": schema_keys,
                "key_freq": dict(key_freq.most_common(80)),
            },
            "distribution": {
                "status": dict(status_freq.most_common(40)),
                "error_rows": len(errors),
            },
            "extremes": {
                "first_offset": first_offset,
                "last_offset": last_offset,
                "min_line_bytes": min_line if min_line is not None else 0,
                "max_line_bytes": max_line,
                "numeric": {key: numeric[key] for key in list(numeric)[:40]},
            },
            "errors": errors[:50],
            "samples": {"head": head, "tail": list(tail)},
        }
    )


def parse_text_log(path: Path) -> dict[str, Any]:
    prefix = sniff_magic(path, 4)
    encoding = sniff_encoding(prefix)
    digest = hashlib.sha256()
    size = 0
    rows = 0
    errors: list[dict[str, Any]] = []
    fail = 0
    pass_n = 0
    head: list[dict[str, Any]] = []
    tail: deque[dict[str, Any]] = deque(maxlen=TAIL_N)
    last_offset = 0
    max_line = 0
    min_line: int | None = None
    newline = b"\n"
    if encoding == "utf-16-le":
        newline = b"\n\x00"
    elif encoding == "utf-16-be":
        newline = b"\x00\n"
    fail_re = re.compile(rb"fail|error|traceback|exception", re.I)
    pass_re = re.compile(rb"\bpass(?:ed)?\b|\bok\b", re.I)

    def handle_line(offset: int, raw: bytes) -> None:
        nonlocal rows, last_offset, max_line, min_line, fail, pass_n
        rows += 1
        last_offset = offset
        max_line = max(max_line, len(raw))
        min_line = len(raw) if min_line is None else min(min_line, len(raw))
        if fail_re.search(raw):
            fail += 1
        if pass_re.search(raw):
            pass_n += 1
        try:
            text = raw.decode(encoding, errors="replace")
        except LookupError:
            text = raw.decode("utf-8", errors="replace")
        sample = _sample(offset, rows, text)
        if len(head) < HEAD_N:
            head.append(sample)
        tail.append(sample)

    with path.open("rb") as handle:
        leftover = b""
        offset = 0
        while True:
            chunk = handle.read(CHUNK)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
            leftover += chunk
            *parts, leftover = leftover.split(newline)
            for raw in parts:
                handle_line(offset, raw + newline)
                offset += len(raw) + len(newline)
        if leftover:
            handle_line(offset, leftover)

    return strip_personal(
        {
            "parser": "log",
            "encoding": encoding,
            "bytes": size,
            "sha256": digest.hexdigest(),
            "rows": rows,
            "schema": {"keys": ["line"], "kind": "text-log"},
            "distribution": {"fail_like": fail, "pass_like": pass_n},
            "extremes": {
                "first_offset": 0,
                "last_offset": last_offset,
                "min_line_bytes": min_line if min_line is not None else 0,
                "max_line_bytes": max_line,
            },
            "errors": errors[:20],
            "samples": {"head": head, "tail": list(tail)},
        }
    )


def parse_json_dom(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        chunks: list[bytes] = []
        while True:
            chunk = handle.read(CHUNK)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
            if size <= JSON_DOM_CAP:
                chunks.append(chunk)
        raw = b"".join(chunks) if size <= JSON_DOM_CAP else b""
    encoding = sniff_encoding(raw[:4] if raw else sniff_magic(path, 4))
    errors: list[dict[str, Any]] = []
    schema: dict[str, Any] = {}
    distribution: dict[str, Any] = {}
    extremes: dict[str, Any] = {"first_offset": 0, "last_offset": max(size - 1, 0)}
    samples: dict[str, Any] = {"head": [], "tail": []}
    rows = 0
    if size > JSON_DOM_CAP:
        errors.append({"error": "dom_too_large", "bytes": size})
        with path.open("rb") as handle:
            head_b = handle.read(SAMPLE_CHARS * 4)
            handle.seek(max(size - SAMPLE_CHARS * 4, 0))
            tail_b = handle.read(SAMPLE_CHARS * 4)
        samples["head"] = [
            _sample(0, 1, head_b.decode(encoding, errors="replace"))
        ]
        samples["tail"] = [
            _sample(
                max(size - len(tail_b), 0),
                1,
                tail_b.decode(encoding, errors="replace"),
            )
        ]
    else:
        text = raw.decode(encoding, errors="replace")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            errors.append({"error": strip_personal(str(exc))})
            data = None
            samples["head"] = [_sample(0, 1, text)]
            samples["tail"] = [_sample(max(size - SAMPLE_CHARS, 0), 1, text[-SAMPLE_CHARS:])]
        if isinstance(data, dict):
            rows = 1
            schema = {
                "keys": sorted(data.keys(), key=str)[:80],
                "n_keys": len(data),
                "root": "object",
            }
            scalars = {
                str(key): value
                for key, value in data.items()
                if not isinstance(value, (dict, list))
            }
            distribution = {
                "scalar_keys": sorted(scalars)[:40],
                "list_lengths": {
                    str(key): len(value)
                    for key, value in data.items()
                    if isinstance(value, list)
                },
            }
            samples["head"] = [_sample(0, 1, json.dumps(schema, ensure_ascii=False))]
            samples["tail"] = samples["head"]
            for key, value in data.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    extremes[str(key)] = {"min": value, "max": value}
        elif isinstance(data, list):
            rows = len(data)
            schema = {"root": "array", "n": rows}
            if data and isinstance(data[0], dict):
                schema["elem_keys"] = sorted(data[0].keys(), key=str)[:80]
            samples["head"] = [
                _sample(0, 1, json.dumps(data[0], ensure_ascii=False) if data else "[]")
            ]
            samples["tail"] = [
                _sample(
                    max(size - 1, 0),
                    rows,
                    json.dumps(data[-1], ensure_ascii=False) if data else "[]",
                )
            ]
        elif data is not None:
            rows = 1
            schema = {"root": type(data).__name__}
            samples["head"] = [_sample(0, 1, str(data))]
            samples["tail"] = samples["head"]
    return strip_personal(
        {
            "parser": "json",
            "encoding": encoding,
            "bytes": size,
            "sha256": digest.hexdigest(),
            "rows": rows,
            "schema": schema,
            "distribution": distribution,
            "extremes": extremes,
            "errors": errors[:20],
            "samples": samples,
        }
    )


def parse_csv(path: Path, *, delimiter: str = ",") -> dict[str, Any]:
    digest, size = sha256_and_size(path)
    encoding = sniff_encoding(sniff_magic(path, 4))
    errors: list[dict[str, Any]] = []
    rows = 0
    header: list[str] = []
    head: list[dict[str, Any]] = []
    tail: deque[dict[str, Any]] = deque(maxlen=TAIL_N)
    with path.open("r", encoding=encoding, errors="replace", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        offset = 0
        for index, row in enumerate(reader, start=1):
            rows += 1
            text = delimiter.join(row)
            if index == 1:
                header = [str(col) for col in row[:80]]
            sample = _sample(offset, index, text)
            if len(head) < HEAD_N:
                head.append(sample)
            tail.append(sample)
            offset += len(text) + 1
    return strip_personal(
        {
            "parser": "csv",
            "encoding": encoding,
            "bytes": size,
            "sha256": digest,
            "rows": max(rows - 1, 0) if header else rows,
            "schema": {"keys": header, "delimiter": delimiter},
            "distribution": {"header_cols": len(header)},
            "extremes": {"first_offset": 0, "last_offset": max(size - 1, 0)},
            "errors": errors,
            "samples": {"head": head, "tail": list(tail)},
        }
    )


def parse_xml(path: Path) -> dict[str, Any]:
    digest, size = sha256_and_size(path)
    tags: Counter[str] = Counter()
    errors: list[dict[str, Any]] = []
    rows = 0
    head: list[dict[str, Any]] = []
    tail: deque[dict[str, Any]] = deque(maxlen=TAIL_N)
    try:
        for event, elem in ET.iterparse(path, events=("end",)):
            tag = elem.tag.split("}", 1)[-1]
            tags[tag] += 1
            rows += 1
            sample = _sample(0, rows, f"<{tag}>")
            if len(head) < HEAD_N:
                head.append(sample)
            tail.append(sample)
            elem.clear()
    except ET.ParseError as exc:
        errors.append({"error": strip_personal(str(exc))})
    return strip_personal(
        {
            "parser": "xml",
            "bytes": size,
            "sha256": digest,
            "rows": rows,
            "schema": {"keys": [key for key, _ in tags.most_common(40)]},
            "distribution": {"tags": dict(tags.most_common(40))},
            "extremes": {"first_offset": 0, "last_offset": max(size - 1, 0)},
            "errors": errors[:20],
            "samples": {"head": head, "tail": list(tail)},
        }
    )


def parse_sqlite(path: Path) -> dict[str, Any]:
    digest, size = sha256_and_size(path)
    tmp = Path(tempfile.mkdtemp(prefix="goal095_ev_sqlite_"))
    copied = tmp / path.name
    shutil.copy2(path, copied)
    wal = Path(str(path) + "-wal")
    shm = Path(str(path) + "-shm")
    if wal.is_file():
        shutil.copy2(wal, tmp / (path.name + "-wal"))
    if shm.is_file():
        shutil.copy2(shm, tmp / (path.name + "-shm"))
    uri = copied.resolve().as_uri() + "?mode=ro"
    errors: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    rows_total = 0
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(uri, uri=True)
        names = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        for name in names:
            info: dict[str, Any] = {"name": name}
            try:
                info["rows"] = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                rows_total += int(info["rows"] or 0)
            except sqlite3.Error as exc:
                info["rows_error"] = strip_personal(str(exc))
            try:
                cols = conn.execute(f'PRAGMA table_info("{name}")').fetchall()
                info["columns"] = [col[1] for col in cols]
            except sqlite3.Error as exc:
                info["columns_error"] = strip_personal(str(exc))
            tables.append(info)
    except sqlite3.Error as exc:
        errors.append({"error": strip_personal(str(exc))})
    finally:
        if conn is not None:
            conn.close()
        shutil.rmtree(tmp, ignore_errors=True)
    samples = {
        "head": [
            _sample(0, 1, json.dumps(tables[:2], ensure_ascii=False) if tables else "[]")
        ],
        "tail": [
            _sample(
                max(size - 1, 0),
                1,
                json.dumps(tables[-1:], ensure_ascii=False) if tables else "[]",
            )
        ],
    }
    return strip_personal(
        {
            "parser": "sqlite",
            "bytes": size,
            "sha256": digest,
            "rows": rows_total,
            "schema": {"tables": [item["name"] for item in tables], "detail": tables[:40]},
            "distribution": {"table_count": len(tables), "rows_total": rows_total},
            "extremes": {"first_offset": 0, "last_offset": max(size - 1, 0)},
            "errors": errors,
            "samples": samples,
        }
    )


def parse_gzip_wrapped(path: Path) -> dict[str, Any]:
    digest, size = sha256_and_size(path)
    name = path.name.lower()
    errors: list[dict[str, Any]] = []
    inner: dict[str, Any] = {}
    try:
        with gzip.open(path, "rb") as handle:
            first = handle.read(8)
    except OSError as exc:
        errors.append({"error": strip_personal(str(exc))})
        first = b""
    looks_jsonl = (
        name.endswith(".jsonl.gz")
        or name.endswith(".json.gz")
        or first.strip().startswith(b"{")
        or first.strip().startswith(b"[")
    )
    if looks_jsonl and not errors:
        tmp = Path(tempfile.mkdtemp(prefix="goal095_ev_gz_"))
        dest = tmp / (path.stem + (".jsonl" if looks_jsonl else ".bin"))
        try:
            with gzip.open(path, "rb") as src, dest.open("wb") as out:
                while True:
                    chunk = src.read(CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
            if dest.stat().st_size <= JSON_DOM_CAP and not name.endswith(".jsonl.gz"):
                inner = parse_json_dom(dest)
            else:
                inner = parse_jsonl(dest)
        except OSError as exc:
            errors.append({"error": strip_personal(str(exc))})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    elif not errors:
        inner = {
            "parser": "gzip-inner",
            "note": "decompressed magic not json; hashed container only",
        }
    extract = {
        "parser": "gzip",
        "bytes": size,
        "sha256": digest,
        "rows": inner.get("rows", 0),
        "schema": inner.get("schema", {}),
        "distribution": inner.get("distribution", {}),
        "extremes": inner.get("extremes", {"first_offset": 0, "last_offset": max(size - 1, 0)}),
        "errors": errors + list(inner.get("errors") or [])[:20],
        "samples": inner.get("samples", {"head": [], "tail": []}),
        "inner_parser": inner.get("parser"),
    }
    return strip_personal(extract)


def parse_structured(path: Path) -> dict[str, Any]:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix == ".gz" or name.endswith(".gz"):
        return parse_gzip_wrapped(path)
    if ".jsonl" in name or name.endswith(".jsonl"):
        return parse_jsonl(path)
    if suffix == ".json":
        return parse_json_dom(path)
    if suffix in {".csv", ".tsv"}:
        return parse_csv(path, delimiter="\t" if suffix == ".tsv" else ",")
    if suffix in {".xml", ".trx", ".html"}:
        return parse_xml(path)
    if suffix in SQLITE_SUFFIXES or name.endswith(".db-wal"):
        if name.endswith(".db-wal"):
            parent = path.with_name(name[: -len(".db-wal")] + ".db")
            if parent.is_file():
                extract = parse_sqlite(parent)
                extract["parser"] = "sqlite-wal-with-parent"
                extract["wal_bytes"], extract["wal_note"] = (
                    path.stat().st_size,
                    "parsed parent db with wal copied",
                )
                digest, size = sha256_and_size(path)
                extract["bytes"] = size
                extract["sha256"] = digest
                return extract
        return parse_sqlite(path)
    return parse_text_log(path)


def _wav_header(magic: bytes) -> dict[str, Any]:
    info: dict[str, Any] = {"container": "riff"}
    if len(magic) >= 44 and magic[8:12] == b"WAVE":
        try:
            audio_format, channels, rate, _byte_rate, _align, bits = struct.unpack_from(
                "<HHIIHH", magic, 20
            )
            info.update(
                {
                    "audio_format": audio_format,
                    "channels": channels,
                    "sample_rate": rate,
                    "bits": bits,
                }
            )
        except struct.error:
            pass
    return info


def _gguf_header(magic: bytes) -> dict[str, Any]:
    info: dict[str, Any] = {"magic": "GGUF"}
    if len(magic) >= 8:
        info["version"] = struct.unpack_from("<I", magic, 4)[0]
    return info


def _safetensors_header(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        size_bytes = handle.read(8)
        if len(size_bytes) < 8:
            return {"error": "truncated"}
        header_len = struct.unpack("<Q", size_bytes)[0]
        if header_len > SAFETENSORS_HEADER_CAP:
            return {"header_len": header_len, "error": "header_too_large"}
        raw = handle.read(header_len)
    try:
        header = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {"header_len": header_len, "error": strip_personal(str(exc))}
    tensors = [key for key in header.keys() if key != "__metadata__"]
    return {
        "header_len": header_len,
        "tensor_count": len(tensors),
        "tensor_names_head": tensors[:20],
        "metadata_keys": sorted((header.get("__metadata__") or {}).keys(), key=str)[:20]
        if isinstance(header.get("__metadata__"), dict)
        else [],
    }


def inventory_binary(
    path: Path, *, source_id: str, rel: str
) -> dict[str, Any]:
    magic = sniff_magic(path, 256)
    digest, size = sha256_and_size(path)
    suffix = path.suffix.lower()
    fmt = format_from_magic(magic, suffix)
    extra: dict[str, Any] = {}
    if fmt == "wav":
        extra = _wav_header(magic)
    elif fmt == "gguf":
        extra = _gguf_header(magic)
    elif suffix == ".safetensors" or fmt == "safetensors":
        extra = _safetensors_header(path)
        fmt = "safetensors"
    elif fmt == "png" and len(magic) >= 24:
        extra = {
            "width": struct.unpack(">I", magic[16:20])[0],
            "height": struct.unpack(">I", magic[20:24])[0],
        }
    return strip_personal(
        {
            "parser": "binary_inventory",
            "bytes": size,
            "sha256": digest,
            "format": fmt,
            "magic_hex": magic[:16].hex(),
            "provenance": {
                "source_id": source_id,
                "path": rel.replace("\\", "/"),
            },
            "recipe": recipe_for(rel),
            "consumers": consumers_for(rel),
            "associated_benchmark": benchmark_for(rel),
            "exists": True,
            "works": False,
            "existence_means_works": False,
            "smoke": "skipped",
            "extra": extra,
            "rows": 0,
            "schema": {"format": fmt},
            "distribution": {},
            "extremes": {"first_offset": 0, "last_offset": max(size - 1, 0)},
            "errors": [],
            "samples": {
                "head": [
                    {
                        "offset": 0,
                        "line": 0,
                        "text": f"magic={magic[:16].hex()} format={fmt}",
                    }
                ],
                "tail": [
                    {
                        "offset": max(size - 1, 0),
                        "line": 0,
                        "text": f"eof bytes={size}",
                    }
                ],
            },
        }
    )


def process_file(
    path: Path, *, source_id: str, rel: str
) -> dict[str, Any]:
    """Classify, parse or inventory one on-disk file. Does not dump bodies."""
    decision = classify_action(rel)
    action = decision["action"]
    if action == "exclude":
        size = path.stat().st_size if path.is_file() else 0
        return {
            "terminal": "excluido_razonado",
            "exclusion_rule": decision["rule"],
            "ranges": [decision["rule"]],
            "extract": {
                "parser": "exclude",
                "bytes": size,
                "sha256": None,
                "rows": 0,
                "schema": {},
                "distribution": {},
                "extremes": {},
                "errors": [],
                "samples": {"head": [], "tail": []},
                "exclusion_rule": decision["rule"],
            },
        }
    if not path.is_file():
        return {
            "terminal": "excluido_razonado",
            "exclusion_rule": "missing_on_disk",
            "ranges": ["missing"],
            "missing": True,
            "extract": {
                "parser": "missing",
                "bytes": 0,
                "sha256": None,
                "rows": 0,
                "schema": {},
                "distribution": {},
                "extremes": {},
                "errors": [{"error": "missing_on_disk"}],
                "samples": {"head": [], "tail": []},
            },
        }
    if action == "parse":
        extract = parse_structured(path)
        return {
            "terminal": "parseado_completo",
            "ranges": [f"{extract.get('parser')}:schema+counts+samples"],
            "extract": extract,
        }
    extract = inventory_binary(path, source_id=source_id, rel=rel)
    return {
        "terminal": "binario_inventariado",
        "ranges": ["blob-meta"],
        "binary_format": extract.get("format"),
        "extract": extract,
    }
