"""Build the Goal 9.5.1 unified manifest, queues and token-bounded batches.

Read-only against historical sibling trees. Versioned outputs use logical
paths only (Programacion/<source>/...) and never embed the operator profile.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

REPO = Path(__file__).resolve().parent.parent
PROGRAMACION = REPO.parent

GOAL = "09.5.1"
TOKEN_TARGET = 300_000
TOKEN_LIMIT = 350_000
METADATA_TOKENS = 256
PARSE_COMPLETE_CAP = 8_192
TEXT_CHUNK_BYTES = 600_000
ESTIMATOR = "bytes_div_2"
TOKENIZER_STATUS = "none_compatible_for_tree_inventory"

FROZEN_0950: dict[str, dict[str, Any]] = {
    "baxy": {
        "logical": "Programacion/BAXY",
        "folder": "BAXY",
        "files": 116641,
        "bytes": 25488709507,
        "identity": "git",
        "head": "203c34a968ee7890e3c1f4505b7a5d12a3d4d45f",
    },
    "carter": {
        "logical": "Programacion/Carter OS AI",
        "folder": "Carter OS AI",
        "files": 136316,
        "bytes": 14935292111,
        "identity": "git",
        "head": "9cf62d236cdef08012897d3c8c680b8afef0d62e",
    },
    "functiongemma": {
        "logical": "Programacion/FunctionGemma",
        "folder": "FunctionGemma",
        "files": 1090,
        "bytes": 34366705385,
        "identity": "sha256_manifest",
        "manifest_rel": "artifacts/goal095/sources/FunctionGemma.sha256.jsonl",
        "manifest_sha256": (
            "ff150df27808ca19c7a80fe40127011ef050be170b83bcd28bacf8d56f619eaa"
        ),
    },
    "probando_gemma4": {
        "logical": "Programacion/Probando Gemma 4",
        "folder": "Probando Gemma 4",
        "files": 36249,
        "bytes": 3690624981,
        "identity": "sha256_manifest",
        "manifest_sha256": (
            "72f9e5fc6597be5169c99e282d33749d6f7537813fb824809beb85e1b13c7e71"
        ),
        "manifest_rel": "artifacts/goal095/sources/Probando_Gemma_4.sha256.jsonl",
        "sparse": True,
    },
}

SCHEMA_AGENT_REFS: dict[str, str] = {
    "origin/Tools-Reduce": "e6f9c1e5130d17d8de2c1b9447c327e53f468948",
    "origin/vram4_lean": "c5f65e9ae04e6766acf3cdffcc0571b6d6bd89ec",
    "v0.9.2": "398f120c6a46265690684a6b479ffea075240251",
}

SOURCE_ORDER = ("carter", "probando_gemma4", "functiongemma", "baxy", "baxy_schema_agent")
KIND_ORDER = ("docs", "code_tests", "evidence_assets")

DOTNET_OBJ = "obj"
NODE_MODULES = "node_modules"
PYCACHE_DIRS = frozenset({"__pycache__"})
VENV_DIRS = frozenset({"venv", "env"})
EGG_INFO_SUFFIX = ".egg-info"

VENDOR_PREFIXES = (
    "Referencia OpenClaw/",
    "Extras/Competidores/",
)
VENDOR_DIR_NAMES = frozenset(
    {
        "mark-xxxix-main",
        "openclaw-main",
        "autogen-main",
        "autogpt-master",
        "goose-main",
        "langgraph-main",
        "open-interpreter-main",
        "openhands-main",
        "os-copilot-main",
        "agent-s-main",
        "hermes-agent-main",
        "hermes-function-calling-main",
        "hermes-optimization-guide-main",
        "llama.cpp-master",
        "lm-evaluation-harness-main",
        "promptfoo-main",
    }
)

DOC_SUFFIXES = frozenset({".md", ".rst", ".adoc", ".txt", ".markdown"})
CODE_SUFFIXES = frozenset(
    {
        ".py",
        ".pyi",
        ".cs",
        ".csproj",
        ".sln",
        ".slnx",
        ".fs",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".ps1",
        ".psm1",
        ".bat",
        ".cmd",
        ".sh",
        ".cpp",
        ".h",
        ".hpp",
        ".rs",
        ".go",
        ".java",
        ".ipynb",
        ".cmake",
        ".toml",
        ".in",
        ".props",
        ".targets",
    }
)
PARSE_COMPLETE_SUFFIXES = frozenset(
    {".jsonl", ".log", ".csv", ".tsv", ".parquet", ".ndjson"}
)
BINARY_SUFFIXES = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".bmp",
        ".wav",
        ".mp3",
        ".ogg",
        ".flac",
        ".mp4",
        ".webm",
        ".onnx",
        ".gguf",
        ".bin",
        ".pt",
        ".pth",
        ".safetensors",
        ".pkl",
        ".joblib",
        ".dll",
        ".exe",
        ".so",
        ".dylib",
        ".pdb",
        ".zip",
        ".7z",
        ".gz",
        ".tar",
        ".whl",
        ".msi",
        ".ttf",
        ".woff",
        ".woff2",
    ".pdf",
    ".ppt",
    ".pptx",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".pyc",
        ".pyo",
        ".pyd",
        ".dat",
        ".sqlite",
        ".db",
        ".npy",
        ".npz",
        ".ggml",
        ".safetensor",
    }
)
CONFIG_NAMES = frozenset(
    {
        "pyproject.toml",
        "requirements.txt",
        "pytest.ini",
        "ruff.toml",
        "conftest.py",
        "global.json",
        "directory.build.props",
        "directory.packages.props",
        ".gitignore",
        ".gitattributes",
        ".editorconfig",
        "makefile",
        "cmakelists.txt",
    }
)
DOC_DIR_NAMES = frozenset(
    {
        "docs",
        "doc",
        "documentacion",
        "documentation",
        "la razon de carter",
    }
)
CODE_DIR_NAMES = frozenset(
    {
        "src",
        "tests",
        "test",
        "scripts",
        "gemma4_agent",
        "carter_v5",
        "carter_v1",
        "carter_v2",
        "carter_v3",
        "carter_v4",
        "legacy",
        "finetune_llm",
        "router",
        "providers",
        "kernel",
        "microagents",
        "skills",
        "tools_pkg",
        "computer_use_pkg",
        "safety_pkg",
        "memory_pkg",
        "voice",
    }
)
EVIDENCE_DIR_NAMES = frozenset(
    {
        "artifacts",
        "experiments",
        "data",
        "dataset_finetune",
        "datasets",
        "eval",
        "evals",
        "logs",
        "captures",
        "checkpoints",
        "models",
        "archive",
        "ops",
    }
)

LANG_BY_SUFFIX = {
    ".py": "python",
    ".pyi": "python",
    ".cs": "csharp",
    ".csproj": "msbuild",
    ".sln": "msbuild",
    ".slnx": "csharp",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ps1": "powershell",
    ".psm1": "powershell",
    ".md": "markdown",
    ".rst": "rst",
    ".json": "json",
    ".jsonl": "jsonl",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".html": "html",
    ".css": "css",
    ".onnx": "onnx",
    ".gguf": "gguf",
    ".log": "log",
    ".csv": "csv",
}

INV_LINK_RE = re.compile(r"\[`[^`]+`\]\(([^)]+)\)")
BACKTICK_RE = re.compile(r"`([^`]+)`")
PERSONAL_PATH_RE = re.compile(
    r"(?i)(?:[c-z]:\\users\\|/users/|d:\\perfil\\|/home/[^/\s]+)",
)

OWNER_BY_KIND = {
    "docs": "documentacion/sprints/09.5.2_LEER_DOCUMENTACION_LOTE.md",
    "code_tests": "documentacion/sprints/09.5.3_AUDITAR_CODIGO_LOTE.md",
    "evidence_assets": "documentacion/sprints/09.5.4_AUDITAR_EVIDENCIA_LOTE.md",
}


def logical_posix(path: str) -> str:
    return path.replace("\\", "/")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, bufsize: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(bufsize)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(8 * 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def dump_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    hasher = hashlib.sha256()
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            line = json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n"
            handle.write(line)
            hasher.update(line.encode("utf-8"))
    return hasher.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def utc_from_mtime(mtime: float) -> str:
    return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def suffix_of(path: str) -> str:
    name = logical_posix(path).rsplit("/", 1)[-1]
    if "." not in name or name.startswith("."):
        lower = name.lower()
        if lower in CONFIG_NAMES:
            return ""
        return ""
    return "." + name.rsplit(".", 1)[-1].lower()


def exclusion_rule(rel: str) -> str | None:
    posix = logical_posix(rel)
    parts = posix.split("/")
    dirs = parts[:-1]
    name = parts[-1] if parts else posix
    lower_name = name.lower()
    for prefix in VENDOR_PREFIXES:
        if posix == prefix[:-1] or posix.startswith(prefix):
            return "vendor_snapshot"
    for part in dirs:
        if part.startswith("."):
            return "dot_directory"
        if part in PYCACHE_DIRS:
            return "python_cache"
        if part in VENV_DIRS:
            return "python_venv"
        if part == NODE_MODULES:
            return "node_modules"
        if part == DOTNET_OBJ:
            return "dotnet_obj"
        if part.endswith(EGG_INFO_SUFFIX):
            return "egg_info"
        if part.lower() in VENDOR_DIR_NAMES:
            return "vendor_snapshot"
    if posix.startswith("Extras/Optimizacion Hermes3/"):
        rest = posix[len("Extras/Optimizacion Hermes3/") :]
        if "/" in rest:
            return "vendor_snapshot"
    if lower_name.endswith(".pyc") or lower_name.endswith(".pyo"):
        return "python_cache"
    return None


EXCLUSION_REASONS = {
    "dot_directory": (
        "directorio cuyo nombre empieza por punto (.git, .venv, caches, IDE)"
    ),
    "python_cache": "bytecode o caches de pytest/ruff/mypy",
    "python_venv": "entorno virtual, no es fuente del linaje",
    "node_modules": "dependencias instaladas, no fuente propia",
    "dotnet_obj": "salida de compilacion MSBuild",
    "egg_info": "metadatos de instalacion pip",
    "vendor_snapshot": (
        "arbol de terceros clonado (competidores, OpenClaw, Hermes, llama.cpp)"
    ),
    "non_regular": "symlink o no-regular; no se hashea el blob",
}


def technical_language(path: str, binary: bool) -> str:
    if binary:
        return "binary"
    suffix = suffix_of(path)
    return LANG_BY_SUFFIX.get(suffix, "text")


def is_binary_path(path: str) -> bool:
    suffix = suffix_of(path)
    if suffix in BINARY_SUFFIXES:
        return True
    posix = logical_posix(path).lower()
    return posix.endswith(".dll") or posix.endswith(".exe")


def is_parse_complete(path: str, size: int) -> bool:
    suffix = suffix_of(path)
    if suffix in PARSE_COMPLETE_SUFFIXES:
        return True
    lower = logical_posix(path).lower()
    if ".log." in lower or lower.endswith(".err") or lower.endswith(".out"):
        return True
    posix = logical_posix(path).lower()
    parts = posix.split("/")
    if suffix == ".json" and (
        size >= 32 * 1024 or any(part in EVIDENCE_DIR_NAMES for part in parts)
    ):
        return True
    return False


def estimate_tokens(size: int, *, binary: bool, parse_complete: bool) -> int:
    if binary:
        return METADATA_TOKENS
    if parse_complete:
        return min(max(size // 2, 1), PARSE_COMPLETE_CAP)
    return max(size // 2, 1)


def classify_kind(path: str, *, binary: bool, parse_complete: bool) -> str:
    posix = logical_posix(path)
    parts = [part.lower() for part in posix.split("/")]
    name = parts[-1] if parts else posix
    suffix = suffix_of(path)
    if binary or parse_complete:
        return "evidence_assets"
    if suffix in DOC_SUFFIXES:
        return "docs"
    if any(part in DOC_DIR_NAMES for part in parts[:-1]):
        if suffix in CODE_SUFFIXES:
            return "code_tests"
        if suffix in DOC_SUFFIXES:
            return "docs"
        return "evidence_assets"
    if name.lower() in CONFIG_NAMES or suffix in {".toml", ".ini", ".lock"}:
        return "code_tests"
    if suffix in CODE_SUFFIXES or any(part in CODE_DIR_NAMES for part in parts):
        if suffix in {".json", ".yaml", ".yml"} and any(
            part in EVIDENCE_DIR_NAMES for part in parts
        ):
            return "evidence_assets"
        if suffix in {".json", ".yaml", ".yml"} and "test" not in parts:
            if any(part in EVIDENCE_DIR_NAMES for part in parts):
                return "evidence_assets"
        return "code_tests"
    if any(part in EVIDENCE_DIR_NAMES for part in parts):
        return "evidence_assets"
    if suffix in {".json", ".yaml", ".yml", ".xml"}:
        return "evidence_assets"
    if suffix == "":
        if name.lower().startswith("readme"):
            return "docs"
        return "evidence_assets"
    return "evidence_assets"


def subsystem_for(source_id: str, path: str) -> str:
    posix = logical_posix(path)
    parts = posix.split("/")
    suffix = suffix_of(path)
    name = parts[-1].lower() if parts else posix.lower()
    if len(parts) == 1:
        if suffix in DOC_SUFFIXES or name.startswith("readme"):
            return f"{source_id}_root_docs"
        if suffix in CODE_SUFFIXES or name in CONFIG_NAMES:
            return f"{source_id}_root_code"
        return f"{source_id}_root_assets"
    if source_id == "carter":
        top = parts[0]
        if top.lower() == "la razon de carter":
            return "carter_razon"
        if top.lower().startswith("carter"):
            return top.lower()
        if top == "legacy" and len(parts) > 1:
            return f"carter_legacy_{parts[1]}"
        if top in {"docs", "documentacion"}:
            return "carter_docs"
        return f"carter_{top.lower().replace(' ', '_')}"
    if source_id == "probando_gemma4":
        if parts[0] == "documentacion" and len(parts) > 1:
            return f"pg4_docs_{parts[1]}"
        if parts[0] == "gemma4_agent" and len(parts) > 1:
            return f"pg4_{parts[1]}"
        return f"pg4_{parts[0]}"
    if source_id == "functiongemma":
        if parts[0] == "finetune_llm" and len(parts) > 1:
            return f"fg_{parts[1]}"
        return f"fg_{parts[0]}"
    if source_id in {"baxy", "baxy_schema_agent"}:
        if parts[0] == "documentacion" and len(parts) > 1:
            return f"baxy_docs_{parts[1]}"
        if parts[0] == "src" and len(parts) > 1:
            return f"baxy_src_{parts[1]}"
        if parts[0] == "legacy" and len(parts) > 1:
            return f"baxy_legacy_{parts[1]}"
        if parts[0] == "artifacts" and len(parts) > 1:
            return f"baxy_art_{parts[1]}"
        if parts[0] == "experiments" and len(parts) > 1:
            return f"baxy_exp_{parts[1]}"
        if source_id == "baxy_schema_agent":
            return "baxy_schema_agent"
        return f"baxy_{parts[0]}"
    return f"{source_id}_{parts[0]}"


def kind_rank(kind: str) -> int:
    try:
        return KIND_ORDER.index(kind)
    except ValueError:
        return 99


def source_rank(source_id: str) -> int:
    try:
        return SOURCE_ORDER.index(source_id)
    except ValueError:
        return 99


def walk_tree(root: Path) -> Iterator[tuple[str, os.stat_result]]:
    for dirpath, dirnames, filenames in os.walk(
        root, topdown=True, followlinks=False
    ):
        dirnames.sort()
        filenames.sort()
        for name in filenames:
            full = Path(dirpath) / name
            try:
                info = os.lstat(full)
            except OSError:
                continue
            rel = os.path.relpath(full, root)
            yield logical_posix(rel), info


def load_frozen_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for row in load_jsonl(path):
        if row.get("kind") == "symlink":
            continue
        rows.append(
            {
                "path": logical_posix(str(row["path"])),
                "sha256": row["sha256"],
                "size": int(row["size"]),
                "mtime_unix": float(row.get("mtime_unix") or 0),
            }
        )
    rows.sort(key=lambda item: item["path"])
    return rows


def inventory_source(
    source_id: str,
    root: Path,
    *,
    frozen_rows: list[dict[str, Any]] | None = None,
    existing_keep: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]], int]:
    del source_id
    exclusions: dict[str, dict[str, int]] = defaultdict(
        lambda: {"files": 0, "bytes": 0}
    )
    keep: list[dict[str, Any]] = []
    total = 0
    cached = existing_keep or {}
    if frozen_rows is not None:
        for row in frozen_rows:
            total += 1
            rule = exclusion_rule(row["path"])
            if rule:
                exclusions[rule]["files"] += 1
                exclusions[rule]["bytes"] += int(row["size"])
                continue
            keep.append(row)
        return keep, dict(exclusions), total

    pending: list[dict[str, Any]] = []
    for rel, info in walk_tree(root):
        total += 1
        rule = exclusion_rule(rel)
        if rule:
            exclusions[rule]["files"] += 1
            exclusions[rule]["bytes"] += int(info.st_size)
            continue
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
            exclusions["non_regular"]["files"] += 1
            exclusions["non_regular"]["bytes"] += int(info.st_size)
            continue
        hit = cached.get(rel)
        if (
            hit
            and int(hit["size"]) == int(info.st_size)
            and hit.get("sha256")
        ):
            keep.append(
                {
                    "path": rel,
                    "size": int(info.st_size),
                    "mtime_unix": float(info.st_mtime),
                    "sha256": hit["sha256"],
                }
            )
            continue
        pending.append(
            {
                "path": rel,
                "size": int(info.st_size),
                "mtime_unix": float(info.st_mtime),
                "full": str(root / Path(*rel.split("/"))),
            }
        )
    for index, row in enumerate(pending, start=1):
        row["sha256"] = sha256_file(Path(row["full"]))
        del row["full"]
        keep.append(row)
        if index == 1 or index % 200 == 0 or index == len(pending):
            print(
                f"hash {root.name} {index}/{len(pending)}",
                flush=True,
            )
    keep.sort(key=lambda item: item["path"])
    return keep, dict(exclusions), total


def hash_git_blob(repo: Path, spec: str) -> tuple[bytes, str]:
    blob = subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(repo), "cat-file", "-p", spec],
        stderr=subprocess.DEVNULL,
    )
    return blob, sha256_bytes(blob)


def schema_agent_rows(baxy_root: Path) -> list[dict[str, Any]]:
    if not (baxy_root / ".git").exists():
        return []
    seen: dict[str, dict[str, Any]] = {}
    for ref, commit in SCHEMA_AGENT_REFS.items():
        listing = subprocess.check_output(
            [
                "git",
                "--no-optional-locks",
                "-C",
                str(baxy_root),
                "ls-tree",
                "-r",
                commit,
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        for line in listing.splitlines():
            _mode, kind, rest = line.split(" ", 2)
            if kind != "blob":
                continue
            blob_id, path = rest.split("\t", 1)
            posix = logical_posix(path)
            key = posix.lower()
            if "schema" not in key and "tool_schema" not in key:
                continue
            if posix in seen:
                seen[posix]["refs"].append(ref)
                continue
            data, digest = hash_git_blob(baxy_root, blob_id)
            seen[posix] = {
                "path": posix,
                "sha256": digest,
                "size": len(data),
                "mtime_unix": 0.0,
                "git_blob": blob_id,
                "git_commit": commit,
                "refs": [ref],
            }
    return [seen[key] for key in sorted(seen)]


def biblioteca_index(repo: Path) -> dict[str, dict[str, Any]]:
    inventory = (repo / "biblioteca" / "01_INVENTARIO.md").read_text(encoding="utf-8")
    listed: dict[str, str] = {}
    for match in INV_LINK_RE.finditer(inventory):
        rel = logical_posix(match.group(1))
        if rel.startswith("http"):
            continue
        listed[rel] = f"biblioteca/01_INVENTARIO.md:{match.start()}"
    hashes: dict[str, dict[str, Any]] = {}
    root = repo / "biblioteca"
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        filenames.sort()
        for name in filenames:
            full = Path(dirpath) / name
            rel = logical_posix(os.path.relpath(full, root))
            if rel in {"00_INDICE.md", "01_INVENTARIO.md"}:
                continue
            digest = sha256_file(full)
            listed_at = listed.get(rel)
            hashes[digest] = {
                "biblioteca_path": f"biblioteca/{rel}",
                "in_inventory_1350": rel in listed,
                "inventory_cite": listed_at,
            }
    return hashes


def goal01_cards(repo: Path) -> list[dict[str, str]]:
    mapa = repo / "documentacion" / "herencia" / "00_MAPA.md"
    text = mapa.read_text(encoding="utf-8")
    cards: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in BACKTICK_RE.finditer(text):
        raw = match.group(1).strip()
        if " " in raw or len(raw) < 4:
            continue
        posix = logical_posix(raw).lstrip("/")
        if posix.startswith("http"):
            continue
        has_ext = bool(re.search(r"\.[A-Za-z0-9]+$", posix))
        if not has_ext:
            continue
        if "/" not in posix and posix.lower() in {
            "agent.py",
            "set_volume",
        }:
            continue
        if posix.lower() in seen:
            continue
        # Bare filenames are not exact links unless unique later.
        seen.add(posix.lower())
        line_no = text.count("\n", 0, match.start()) + 1
        cards.append(
            {
                "path_suffix": posix,
                "evidence": f"documentacion/herencia/00_MAPA.md:{line_no}",
            }
        )
    annex = repo / "documentacion" / "herencia" / "D_ADAPTADORES_POR_APP.md"
    if annex.is_file():
        annex_text = annex.read_text(encoding="utf-8")
        for match in BACKTICK_RE.finditer(annex_text):
            raw = match.group(1).strip()
            posix = logical_posix(raw)
            if not posix.endswith(".cs") and not posix.endswith(".ps1"):
                continue
            if posix.lower() in seen:
                continue
            seen.add(posix.lower())
            line_no = annex_text.count("\n", 0, match.start()) + 1
            cards.append(
                {
                    "path_suffix": posix,
                    "evidence": (
                        "documentacion/herencia/D_ADAPTADORES_POR_APP.md:"
                        f"{line_no}"
                    ),
                }
            )
    return cards


def unique_suffix_index(
    files: list[dict[str, Any]],
) -> dict[str, list[tuple[str, str]]]:
    index: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row in files:
        posix = logical_posix(row["path"])
        source_id = row["source_id"]
        index[posix.lower()].append((source_id, posix))
        name = posix.rsplit("/", 1)[-1].lower()
        index[name].append((source_id, posix))
        parts = posix.split("/")
        for index_i in range(1, len(parts)):
            suffix = "/".join(parts[index_i:]).lower()
            index[suffix].append((source_id, posix))
    return index


def prior_coverage_for(
    row: dict[str, Any],
    *,
    biblioteca: dict[str, dict[str, Any]],
    cards: list[dict[str, str]],
    suffix_index: dict[str, list[tuple[str, str]]],
) -> dict[str, Any] | None:
    digest = row["sha256"]
    biblio = biblioteca.get(digest)
    if biblio and biblio.get("in_inventory_1350"):
        return {
            "kind": "hash_identical",
            "evidence": biblio["inventory_cite"] or biblio["biblioteca_path"],
            "biblioteca_path": biblio["biblioteca_path"],
            "sha256": digest,
        }
    posix = logical_posix(row["path"])
    hits: list[dict[str, str]] = []
    for card in cards:
        suffix = card["path_suffix"].lower().lstrip("./")
        matches = suffix_index.get(suffix, [])
        exact = [
            item
            for item in matches
            if item[0] == row["source_id"] and item[1] == posix
        ]
        if not exact:
            continue
        if len({item[1] for item in matches if item[0] == row["source_id"]}) != 1:
            continue
        hits.append(card)
    if len(hits) == 1:
        return {
            "kind": "goal01_card",
            "evidence": hits[0]["evidence"],
            "path_suffix": hits[0]["path_suffix"],
        }
    return None


def text_parts(size: int, *, binary: bool, parse_complete: bool) -> list[dict[str, int]]:
    if binary or parse_complete or size <= TEXT_CHUNK_BYTES:
        return [{"offset": 0, "length": size}]
    parts = []
    offset = 0
    while offset < size:
        length = min(TEXT_CHUNK_BYTES, size - offset)
        parts.append({"offset": offset, "length": length})
        offset += length
    return parts


def make_record(
    source_id: str,
    row: dict[str, Any],
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = logical_posix(row["path"])
    size = int(row["size"])
    binary = is_binary_path(path)
    parse_complete = is_parse_complete(path, size)
    kind = classify_kind(path, binary=binary, parse_complete=parse_complete)
    if kind == "evidence_assets" and not binary:
        parse_complete = True
    tokens = estimate_tokens(size, binary=binary, parse_complete=parse_complete)
    record = {
        "source_id": source_id,
        "path": path,
        "sha256": row["sha256"],
        "size": size,
        "tipo": suffix_of(path).lstrip(".") or "none",
        "fecha": utc_from_mtime(float(row.get("mtime_unix") or 0)),
        "lenguaje_tecnico": technical_language(path, binary),
        "binary": binary,
        "parse_complete": parse_complete,
        "queue_kind": kind,
        "subsystem": subsystem_for(source_id, path),
        "estimated_tokens": tokens if not binary else METADATA_TOKENS,
        "duplicado": None,
        "cobertura_previa": None,
        "assignment": None,
    }
    if extra:
        record.update(extra)
    if not binary and not parse_complete and size > TEXT_CHUNK_BYTES:
        record["byte_parts"] = text_parts(size, binary=binary, parse_complete=False)
        record["estimated_tokens"] = max(TEXT_CHUNK_BYTES // 2, 1)
    return record


def assign_records(
    records: list[dict[str, Any]],
    *,
    biblioteca: dict[str, dict[str, Any]],
    cards: list[dict[str, str]],
) -> list[dict[str, Any]]:
    ordered = sorted(records, key=lambda item: (item["source_id"], item["path"]))
    suffix_index = unique_suffix_index(ordered)
    first_by_hash: dict[str, dict[str, Any]] = {}
    for row in ordered:
        digest = row["sha256"]
        canonical = first_by_hash.get(digest)
        if canonical is not None:
            row["duplicado"] = {
                "canonical_source_id": canonical["source_id"],
                "canonical_path": canonical["path"],
                "sha256": digest,
            }
            row["assignment"] = "duplicate"
            continue
        first_by_hash[digest] = row
        coverage = prior_coverage_for(
            row, biblioteca=biblioteca, cards=cards, suffix_index=suffix_index
        )
        if coverage:
            row["cobertura_previa"] = coverage
            row["assignment"] = "prior_coverage"
        else:
            row["assignment"] = "queue"
    return ordered


def pack_batches(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queued = [row for row in records if row["assignment"] == "queue"]
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in queued:
        parts = row.get("byte_parts")
        if parts and len(parts) > 1:
            for part in parts:
                piece = dict(row)
                piece["byte_offset"] = part["offset"]
                piece["byte_length"] = part["length"]
                piece["estimated_tokens"] = max(part["length"] // 2, 1)
                groups[(row["queue_kind"], row["source_id"], row["subsystem"])].append(
                    piece
                )
        else:
            groups[(row["queue_kind"], row["source_id"], row["subsystem"])].append(row)

    group_keys = sorted(
        groups,
        key=lambda key: (kind_rank(key[0]), source_rank(key[1]), key[2]),
    )
    batches: list[dict[str, Any]] = []
    counters = {kind: 0 for kind in KIND_ORDER}

    def flush(
        kind: str,
        source_id: str,
        subsystems: list[str],
        files: list[dict[str, Any]],
    ) -> None:
        if not files:
            return
        counters[kind] += 1
        primary = subsystems[0]
        extra = len(dict.fromkeys(subsystems))
        batch_id = f"{kind}-{counters[kind]:03d}-{source_id}-{primary}"
        if extra > 1:
            batch_id = f"{kind}-{counters[kind]:03d}-{source_id}"
        tokens = sum(int(item["estimated_tokens"]) for item in files)
        if tokens > TOKEN_LIMIT:
            raise RuntimeError(f"batch {batch_id} exceeds {TOKEN_LIMIT}: {tokens}")
        batches.append(
            {
                "batch_id": batch_id,
                "kind": kind,
                "owner": OWNER_BY_KIND[kind],
                "source_id": source_id,
                "subsystem": primary,
                "subsystems": list(dict.fromkeys(subsystems)),
                "status": "pending",
                "estimated_tokens": tokens,
                "token_target": TOKEN_TARGET,
                "token_limit": TOKEN_LIMIT,
                "estimator": ESTIMATOR,
                "file_count": len(files),
                "files": [
                    {
                        "source_id": item["source_id"],
                        "path": item["path"],
                        "sha256": item["sha256"],
                        "size": item["size"],
                        "estimated_tokens": item["estimated_tokens"],
                        "binary": item["binary"],
                        "parse_complete": item["parse_complete"],
                        **(
                            {
                                "byte_offset": item["byte_offset"],
                                "byte_length": item["byte_length"],
                            }
                            if "byte_offset" in item
                            else {}
                        ),
                    }
                    for item in files
                ],
                "output": f"artifacts/goal095/ledger/{batch_id}.json",
            }
        )

    current: list[dict[str, Any]] = []
    current_tokens = 0
    current_kind = ""
    current_source = ""
    current_subs: list[str] = []
    for kind, source_id, subsystem in group_keys:
        files = sorted(
            groups[(kind, source_id, subsystem)],
            key=lambda item: (item["path"], item.get("byte_offset", 0)),
        )
        for item in files:
            cost = int(item["estimated_tokens"])
            if cost > TOKEN_LIMIT:
                raise RuntimeError(
                    f"file {source_id}:{item['path']} tokens {cost} exceed limit"
                )
            split = bool(current) and (
                kind != current_kind
                or source_id != current_source
                or current_tokens + cost > TOKEN_TARGET
            )
            if split:
                flush(current_kind, current_source, current_subs, current)
                current = []
                current_tokens = 0
                current_subs = []
            current.append(item)
            current_tokens += cost
            current_kind = kind
            current_source = source_id
            current_subs.append(subsystem)
    flush(current_kind, current_source, current_subs, current)
    return batches


def sparse_exclusions() -> dict[str, Any]:
    return {
        "note": (
            "Omisiones deliberadas del snapshot disperso de Probando Gemma 4. "
            "No hay rutas ni hashes individuales. No son faltantes fisicos de esta "
            "corrida ni archivos inspeccionados."
        ),
        "counted_as_physical_missing": False,
        "inspected": False,
        "entries": [
            {
                "asset_type": "gguf_models",
                "logical_prefix": "Programacion/Probando Gemma 4/models",
                "present_in_snapshot": "empty directory, 0 files",
                "historical_size": "~17 GiB GGUF",
                "historical_source": (
                    "documentacion/herencia/00_MAPA.md Goal 01 2026-08-16; "
                    "documentacion/herencia/09_5_FUENTES.md"
                ),
                "consumer": "runtime LLM (llama-server / gemma4_agent)",
                "recipe_or_evidence": (
                    "documentacion/herencia/00_MAPA.md section 2; "
                    "artifacts/goal095/run2/sparse_exclusions.json"
                ),
                "individual_paths": None,
                "individual_hashes": "not invented",
            },
            {
                "asset_type": "training_datasets",
                "logical_prefix": "Programacion/Probando Gemma 4/data",
                "present_in_snapshot": "1354 files, 247259115 bytes remain",
                "historical_size": "~39 GiB",
                "historical_source": (
                    "documentacion/herencia/00_MAPA.md Goal 01 2026-08-16; "
                    "documentacion/herencia/09_5_FUENTES.md"
                ),
                "consumer": (
                    "wake/STT training and eval "
                    "(wake_universal_eval, livekit, nemotron, voxcpm)"
                ),
                "recipe_or_evidence": (
                    "documentacion/herencia/00_MAPA.md section 2; "
                    "artifacts/goal095/run2/sparse_exclusions.json"
                ),
                "individual_paths": None,
                "individual_hashes": "not invented",
            },
            {
                "asset_type": "training_checkpoints",
                "logical_prefix": "Programacion/Probando Gemma 4/checkpoints/model",
                "present_in_snapshot": "empty directory",
                "historical_size": "Goal 01 already found checkpoints/ empty",
                "historical_source": "documentacion/herencia/00_MAPA.md Goal 01",
                "consumer": "fine-tune / resume scripts of gemma4_agent",
                "recipe_or_evidence": "documentacion/herencia/00_MAPA.md section 2",
                "individual_paths": None,
                "individual_hashes": "not invented",
            },
        ],
    }


def assert_no_personal_paths(text: str, label: str) -> None:
    if PERSONAL_PATH_RE.search(text):
        raise RuntimeError(f"personal path leaked in {label}")


def cobertura_markdown(
    *,
    summary: dict[str, Any],
    batches: list[dict[str, Any]],
    exclusions: dict[str, Any],
) -> str:
    lines = [
        "# Goal 9.5.1 — Cobertura y cola de auditoria",
        "",
        f"Generado por `scripts/build_goal095_queues.py`. Estimador: `{ESTIMATOR}`.",
        "Tokenizer compatible para el arbol: ninguno (no se vuelca contenido).",
        "No decide herencia. No lee cuerpos.",
        "",
        "## Manifiesto",
        "",
        f"- Archivos en manifiesto (con hash): **{summary['manifest_files']}**",
        f"- En cola: **{summary['queued']}**",
        f"- Duplicados por hash: **{summary['duplicates']}**",
        f"- Cobertura previa demostrable: **{summary['prior_coverage']}**",
        f"- Excluidos por regla (fuera del manifiesto hasheado): **{summary['excluded_files']}**",
        f"- Faltantes del manifiesto: **{summary['missing']}**",
        f"- Solapes: **{summary['overlaps']}**",
        "",
        "Union cola + duplicados + cobertura previa = manifiesto. Las exclusiones",
        "cierran el recuento 09.5.0 por fuente. `sparse_exclusions` no suma faltantes.",
        "",
        "## Hashes 09.5.0 reutilizados",
        "",
        "- FunctionGemma manifiesto "
        f"`{FROZEN_0950['functiongemma']['manifest_sha256']}`",
        "- Probando Gemma 4 manifiesto "
        f"`{FROZEN_0950['probando_gemma4']['manifest_sha256']}`",
        "",
        "## Exclusiones (reglas, no juicio)",
        "",
        "| Regla | Archivos | Bytes | Razon |",
        "|---|---:|---:|---|",
    ]
    for rule_id, reason in EXCLUSION_REASONS.items():
        rec = exclusions.get("by_rule", {}).get(rule_id, {"files": 0, "bytes": 0})
        lines.append(
            f"| `{rule_id}` | {rec['files']} | {rec['bytes']} | {reason} |"
        )
    lines.extend(
        [
            "",
            "## Snapshot disperso (no inspeccionado, no faltante)",
            "",
            "Ver `artifacts/goal095/queue/sparse_exclusions.json`.",
            "Categorias: `gguf_models`, `training_datasets`, `training_checkpoints`.",
            "",
            "## Lotes",
            "",
            f"Objetivo {TOKEN_TARGET} / limite {TOKEN_LIMIT} tokens de entrada.",
            "Binarios: solo metadatos. JSONL/logs/corpus: parseo por herramienta.",
            "Cola completa: `artifacts/goal095/queue/batches.json` y "
            "`artifacts/goal095/queue/ledger.json`.",
            "",
            "| kind | lotes | archivos | tokens max | owner |",
            "|---|---:|---:|---:|---|",
        ]
    )
    by_kind: dict[str, dict[str, int]] = {
        kind: {"batches": 0, "files": 0, "max_tokens": 0} for kind in KIND_ORDER
    }
    for batch in batches:
        rec = by_kind[batch["kind"]]
        rec["batches"] += 1
        rec["files"] += int(batch["file_count"])
        rec["max_tokens"] = max(rec["max_tokens"], int(batch["estimated_tokens"]))
    for kind in KIND_ORDER:
        rec = by_kind[kind]
        lines.append(
            f"| `{kind}` | {rec['batches']} | {rec['files']} | "
            f"{rec['max_tokens']} | `{OWNER_BY_KIND[kind]}` |"
        )
    first_docs = next((item for item in batches if item["kind"] == "docs"), None)
    if first_docs:
        lines.extend(
            [
                "",
                "Primer lote docs (subsistema, no alfabeto global):",
                "",
                f"- `batch_id`: `{first_docs['batch_id']}`",
                f"- archivos: {first_docs['file_count']}",
                f"- tokens estimados: {first_docs['estimated_tokens']}",
                f"- salida: `{first_docs['output']}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Siguiente",
            "",
        ]
    )
    if first_docs:
        lines.append(
            f"Primer lote docs pendiente: `{first_docs['batch_id']}` — "
            "prompt `documentacion/sprints/09.5.2_LEER_DOCUMENTACION_LOTE.md`."
        )
    else:
        lines.append(
            "No queda lote docs; siguiente "
            "`documentacion/sprints/09.5.3_AUDITAR_CODIGO_LOTE.md`."
        )
    lines.append("")
    return "\n".join(lines)


def partition_ok(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = defaultdict(int)
    keys: set[tuple[str, str]] = set()
    overlaps = 0
    for row in records:
        key = (row["source_id"], row["path"])
        if key in keys:
            overlaps += 1
        keys.add(key)
        counts[row["assignment"]] += 1
    queued = counts["queue"]
    duplicates = counts["duplicate"]
    prior = counts["prior_coverage"]
    missing = len(records) - queued - duplicates - prior
    return {
        "manifest_files": len(records),
        "queued": queued,
        "duplicates": duplicates,
        "prior_coverage": prior,
        "missing": missing,
        "overlaps": overlaps,
    }


def build(
    *,
    repo: Path,
    programacion: Path,
    out_dir: Path,
    cobertura_path: Path,
    hash_cache_dir: Path,
    specs: dict[str, dict[str, Any]] | None = None,
    require_frozen_hash: bool = True,
    include_schema_agent: bool = True,
) -> dict[str, Any]:
    biblioteca = biblioteca_index(repo)
    cards = goal01_cards(repo)
    records: list[dict[str, Any]] = []
    exclusion_by_source: dict[str, dict[str, dict[str, int]]] = {}
    exclusion_by_rule: dict[str, dict[str, int]] = defaultdict(
        lambda: {"files": 0, "bytes": 0}
    )
    source_totals: dict[str, dict[str, int]] = {}
    active_specs = specs or FROZEN_0950
    process_order = sorted(
        active_specs,
        key=lambda key: 0 if active_specs[key].get("manifest_rel") else 1,
    )

    for source_id in process_order:
        spec = active_specs[source_id]
        root = programacion / spec["folder"]
        frozen_rows = None
        if spec.get("manifest_rel"):
            frozen_path = repo / spec["manifest_rel"]
            frozen_rows = load_frozen_jsonl(frozen_path)
            if require_frozen_hash:
                actual_sha = sha256_path(frozen_path)
                if actual_sha != spec["manifest_sha256"]:
                    raise RuntimeError(
                        f"{source_id} manifest hash {actual_sha} != 09.5.0 "
                        f"{spec['manifest_sha256']}"
                    )
                if len(frozen_rows) != spec["files"]:
                    raise RuntimeError(
                        f"{source_id} jsonl lines {len(frozen_rows)} != 09.5.0 "
                        f"{spec['files']}"
                    )
        cache_path = hash_cache_dir / f"{source_id}.keep.sha256.jsonl"
        existing_keep = {}
        if cache_path.is_file() and frozen_rows is None:
            existing_keep = {item["path"]: item for item in load_jsonl(cache_path)}
        if frozen_rows is None and not root.is_dir():
            raise RuntimeError(f"missing source {spec['logical']}")
        keep, excluded, walked = inventory_source(
            source_id,
            root,
            frozen_rows=frozen_rows,
            existing_keep=existing_keep,
        )
        dump_jsonl(cache_path, keep)
        frozen_files = spec.get("files")
        if require_frozen_hash and frozen_files is not None and walked != frozen_files:
            raise RuntimeError(
                f"{source_id} walked {walked} != frozen {frozen_files}"
            )
        exclusion_by_source[source_id] = excluded
        for rule, rec in excluded.items():
            exclusion_by_rule[rule]["files"] += rec["files"]
            exclusion_by_rule[rule]["bytes"] += rec["bytes"]
        source_totals[source_id] = {
            "keep": len(keep),
            "excluded": sum(item["files"] for item in excluded.values()),
            "walked": walked,
            "frozen": frozen_files,
        }
        for row in keep:
            records.append(make_record(source_id, row))

    schema_root = programacion / "BAXY"
    schema_rows = (
        schema_agent_rows(schema_root)
        if include_schema_agent and schema_root.is_dir()
        else []
    )
    keep_paths = {
        (item["source_id"], item["path"])
        for item in records
        if item["source_id"] == "baxy"
    }
    schema_keep = []
    for row in schema_rows:
        if ("baxy", row["path"]) in keep_paths:
            continue
        extra = {
            "git_ref": row["refs"][0],
            "git_commit": row["git_commit"],
            "git_blob": row["git_blob"],
        }
        records.append(make_record("baxy_schema_agent", row, extra=extra))
        schema_keep.append(row)
    dump_jsonl(hash_cache_dir / "baxy_schema_agent.keep.sha256.jsonl", schema_keep)

    records = assign_records(records, biblioteca=biblioteca, cards=cards)
    partition = partition_ok(records)
    if partition["missing"] != 0 or partition["overlaps"] != 0:
        raise RuntimeError(f"partition failed: {partition}")
    batches = pack_batches(records)
    for batch in batches:
        if batch["estimated_tokens"] > TOKEN_LIMIT:
            raise RuntimeError(batch["batch_id"])

    first_docs = next((item["batch_id"] for item in batches if item["kind"] == "docs"), None)
    excluded_files = sum(item["files"] for item in exclusion_by_rule.values())
    summary = {
        **partition,
        "excluded_files": excluded_files,
        "batch_count": len(batches),
        "first_docs_batch_id": first_docs,
        "estimator": ESTIMATOR,
        "tokenizer": TOKENIZER_STATUS,
        "token_target": TOKEN_TARGET,
        "token_limit": TOKEN_LIMIT,
        "source_totals": source_totals,
        "biblioteca_hashed": len(biblioteca),
        "goal01_cards": len(cards),
        "schema_agent_files": len(schema_keep),
    }
    sparse = sparse_exclusions()
    exclusions_payload = {
        "rules": [
            {"id": rule_id, "reason": reason}
            for rule_id, reason in EXCLUSION_REASONS.items()
        ],
        "by_rule": dict(exclusion_by_rule),
        "by_source": exclusion_by_source,
    }
    queue_dir = out_dir / "queue"
    ledger_dir = out_dir / "ledger"
    queue_dir.mkdir(parents=True, exist_ok=True)
    ledger_dir.mkdir(parents=True, exist_ok=True)

    manifest_sha = dump_jsonl(queue_dir / "unified_manifest.jsonl", records)
    batches_path = queue_dir / "batches.json"
    dump_json(batches_path, batches)
    dump_json(queue_dir / "sparse_exclusions.json", sparse)
    dump_json(queue_dir / "exclusion_counts.json", exclusions_payload)
    dump_json(queue_dir / "summary.json", summary)
    dump_json(
        queue_dir / "ledger.json",
        {
            "goal": GOAL,
            "status": "queues_ready",
            "first_docs_batch_id": first_docs,
            "batches": [
                {
                    "batch_id": item["batch_id"],
                    "kind": item["kind"],
                    "owner": item["owner"],
                    "status": item["status"],
                    "file_count": item["file_count"],
                    "estimated_tokens": item["estimated_tokens"],
                    "output": item["output"],
                }
                for item in batches
            ],
        },
    )
    cobertura = cobertura_markdown(
        summary=summary, batches=batches, exclusions=exclusions_payload
    )
    assert_no_personal_paths(cobertura, "cobertura")
    cobertura_path.write_text(cobertura, encoding="utf-8", newline="\n")
    for path in queue_dir.glob("*.json"):
        assert_no_personal_paths(path.read_text(encoding="utf-8"), path.name)
    assert_no_personal_paths(
        (queue_dir / "unified_manifest.jsonl").read_text(encoding="utf-8"),
        "unified_manifest.jsonl",
    )

    seal = {
        "manifest_sha256": manifest_sha,
        "batches_sha256": sha256_path(batches_path),
        "summary_sha256": sha256_path(queue_dir / "summary.json"),
        "sparse_sha256": sha256_path(queue_dir / "sparse_exclusions.json"),
        "exclusions_sha256": sha256_path(queue_dir / "exclusion_counts.json"),
        "cobertura_sha256": sha256_path(cobertura_path),
        "ledger_sha256": sha256_path(queue_dir / "ledger.json"),
    }
    dump_json(queue_dir / "reconstruction.json", seal)
    return {"summary": summary, "seal": seal, "first_docs_batch_id": first_docs}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--programacion", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--cobertura",
        type=Path,
        default=None,
    )
    parser.add_argument("--repeat", type=int, default=1)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = args.repo.resolve()
    programacion = (args.programacion or repo.parent).resolve()
    out_dir = (args.out or (repo / "artifacts" / "goal095")).resolve()
    cobertura = (
        args.cobertura or (repo / "documentacion" / "herencia" / "09_5_COBERTURA.md")
    ).resolve()
    hash_cache = out_dir / "sources"
    seals = []
    last = None
    for _ in range(max(args.repeat, 1)):
        last = build(
            repo=repo,
            programacion=programacion,
            out_dir=out_dir,
            cobertura_path=cobertura,
            hash_cache_dir=hash_cache,
        )
        seals.append(last["seal"])
    if len(seals) > 1 and seals[0] != seals[-1]:
        raise RuntimeError("reconstructions diverged")
    assert last is not None
    print(json.dumps(last, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
