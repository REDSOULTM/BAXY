"""Guard: every third-party runtime import of gemma4_agent is declared in
requirements.txt.

WHY: requirements.txt was generated once and silently drifted —
10 packages imported by the package (sherpa-onnx, rapidfuzz, jellyfish, mss,
uiautomation, onnxruntime, dateparser, mcp, ...) were missing, so a fresh
`pip install -r requirements.txt` produced an env that ImportErrors at runtime.
This test makes that drift a RED instead of a runtime surprise.

Scope (matches the project's reproducibility rule — "nada sin su receta"):
  - Scans NON-TEST .py files under gemma4_agent/ (tests pull pytest etc.).
  - SKIPS gemma4_agent/vision_input/ (owned by Codex).
  - Excludes the stdlib and the package's own modules.
  - torchvision is deliberately EXCLUDED: it is imported ONLY by a health
    test that asserts it must be absent/aligned (test_router_load_health.py),
    never in runtime code, and installing it drags torch upgrades
    (project memory: grounding_omniparser_not_viable).

If this fails: add the missing dist to requirements.txt (pin to the version
the env actually has, with a one-line source comment), OR — if the import is
truly test-only/optional — add its IMPORT name to _IMPORT_ALLOWLIST below with
a justification.
"""
from __future__ import annotations

import ast
import os
import re
import sys
import unittest
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent          # gemma4_agent/
_REPO_ROOT = _PKG_ROOT.parent
_REQ_FILE = _REPO_ROOT / "requirements.txt"

# Import-name -> a substring that, if present in requirements.txt (lowercased),
# proves the dist is declared. Keys are the TOP-LEVEL import names found by the
# AST scan; values are the canonical PyPI dist (or a unique substring of it).
_IMPORT_TO_DIST = {
    "PIL": "pillow", "PyQt6": "pyqt6", "bs4": "beautifulsoup4",
    "comtypes": "comtypes", "ctranslate2": "ctranslate2",
    "dateparser": "dateparser", "docx": "python-docx", "fastapi": "fastapi",
    "faster_whisper": "faster-whisper", "fitz": "pymupdf",
    "jellyfish": "jellyfish", "matplotlib": "matplotlib", "mcp": "mcp",
    "mss": "mss", "mysql": "mysql-connector-python", "numpy": "numpy",
    "onnxruntime": "onnxruntime", "openpyxl": "openpyxl",
    "openwakeword": "openwakeword", "paho": "paho-mqtt", "pandas": "pandas",
    "pdf2image": "pdf2image", "pdfplumber": "pdfplumber", "piper": "piper-tts",
    "playwright": "playwright", "pptx": "python-pptx", "psutil": "psutil",
    "psycopg": "psycopg", "psycopg2": "psycopg2-binary", "pycaw": "pycaw",
    "pydantic": "pydantic", "pymysql": "pymysql", "pynvml": "nvidia-ml-py",
    "pypdf": "pypdf", "rapidfuzz": "rapidfuzz",
    "sentence_transformers": "sentence-transformers",
    "sherpa_onnx": "sherpa-onnx", "silero_vad": "silero-vad",
    "sounddevice": "sounddevice", "sqlite_vec": "sqlite-vec",
    "scipy": "scipy", "torch": "torch", "uiautomation": "uiautomation",
    "uvicorn": "uvicorn", "webview": "pywebview",
    # pywin32 family (all map to the same dist):
    "win32api": "pywin32", "win32com": "pywin32", "win32con": "pywin32",
    "win32gui": "pywin32", "win32process": "pywin32", "pythoncom": "pywin32",
    "win32clipboard": "pywin32", "win32event": "pywin32",
    "winsdk": "winsdk", "jiwer": "jiwer",
    "ddgs": "ddgs", "py3langid": "py3langid",
    "windows_toasts": "windows-toasts",
    "pyaudiowpatch": "pyaudiowpatch",  # WASAPI loopback mic (reescritura de voz)
    "tokenizers": "tokenizers",        # import directo en semantic_router (Tokenizer)
}

# Import names that are intentionally NOT in requirements.txt.
_IMPORT_ALLOWLIST = {
    # test-only deps:
    "pytest",
    # imported only by a health test asserting it should be absent; pulling it
    # in upgrades torch (project memory: grounding_omniparser_not_viable):
    "torchvision", "torchcodec",
}


def _iter_runtime_py() -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(_PKG_ROOT):
        norm = dirpath.replace("\\", "/")
        # workstream de cámara/gestos, fuera del alcance de este chequeo:
        if "/vision_input" in norm or norm.endswith("/vision_input"):
            continue
        if "/node_modules" in norm or "/dist" in norm:
            continue
        # Skip test packages — they legitimately import pytest/test-only deps.
        if norm.endswith("/tests") or "/tests/" in norm:
            continue
        for fn in filenames:
            if fn.endswith(".py"):
                files.append(Path(dirpath) / fn)
    return files


def _top_level_imports(files: list[Path]) -> set[str]:
    mods: set[str] = set()
    for p in files:
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"), str(p))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mods.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    mods.add(node.module.split(".")[0])
    return mods


class TestRequirementsCoverage(unittest.TestCase):

    def test_every_runtime_import_is_declared(self) -> None:
        self.assertTrue(_REQ_FILE.exists(), f"missing {_REQ_FILE}")
        req = _REQ_FILE.read_text(encoding="utf-8").lower()

        stdlib = set(getattr(sys, "stdlib_module_names", set()))
        third_party: set[str] = set()
        for mod in _top_level_imports(_iter_runtime_py()):
            if mod in stdlib or mod == "gemma4_agent" or mod.startswith("_"):
                continue
            if mod in _IMPORT_ALLOWLIST:
                continue
            third_party.add(mod)

        unmapped, undeclared = [], []
        for mod in sorted(third_party):
            dist = _IMPORT_TO_DIST.get(mod)
            if dist is None:
                unmapped.append(mod)
                continue
            # Match the dist name as a standalone token at a line start so we
            # don't false-pass on a comment substring.
            base = re.escape(dist)
            if not re.search(rf"(?mi)^{base}(\b|[<>=!~ ])", req):
                undeclared.append(f"{mod} (-> {dist})")

        msg = []
        if unmapped:
            msg.append(
                "Imports with no known PyPI mapping (add to _IMPORT_TO_DIST or "
                f"_IMPORT_ALLOWLIST with justification): {unmapped}")
        if undeclared:
            msg.append(
                "Runtime imports MISSING from requirements.txt "
                f"(add a pinned entry): {undeclared}")
        self.assertFalse(msg, "\n".join(msg))


if __name__ == "__main__":
    unittest.main()
