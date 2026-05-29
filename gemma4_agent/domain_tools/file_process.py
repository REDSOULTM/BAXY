"""B6 — file-processor unificado (adopción de Mark-XXXIX `file_processor`).

UNA entrada coherente: `file_process(path)` detecta el tipo de archivo y delega al
procesador correcto (data_analysis / document / vision-OCR), sin que el usuario ni
el 4B tengan que elegir la herramienta. Patrón "analizá este archivo".

Hoy el repo ya tiene los procesadores (document, data_analysis, vision) y un routing
por extensión (`_route_file_by_extension`, default-ON) que los ofrece al 4B. B6 agrega
el 20% que faltaba: la ENTRADA ÚNICA que auto-detecta y delega internamente.

Detección por EXTENSIÓN (guarda estructural, sin LLM ni keywords por idioma). Gated
`GEMMA4_FILE_PROCESSOR` (default-off hasta validar el flip en vivo, como los demás).
"""
from __future__ import annotations

import os
from pathlib import Path

_DATA_EXTS = frozenset({".csv", ".tsv", ".xlsx", ".xls"})
_DOC_EXTS = frozenset({".pdf", ".docx", ".doc", ".pptx", ".ppt", ".html", ".htm",
                       ".rtf", ".odt", ".epub"})
_TEXT_EXTS = frozenset({".txt", ".md", ".markdown", ".json", ".log", ".yaml", ".yml",
                        ".py", ".js", ".ts", ".java", ".c", ".cpp", ".cs", ".go",
                        ".rs", ".rb", ".php", ".sh", ".ps1", ".ini", ".cfg", ".toml",
                        ".xml", ".css", ".sql"})
_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif",
                         ".tiff", ".heic"})
_AUDIO_EXTS = frozenset({".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".opus"})


def file_processor_enabled() -> bool:
    """Gate B6. Default OFF (opt-in GEMMA4_FILE_PROCESSOR) hasta validar el flip."""
    return (os.environ.get("GEMMA4_FILE_PROCESSOR", "0") or "0").strip().lower() not in {
        "0", "false", "no", "off"}


def detect_file_kind(path: str | Path) -> str:
    """Clase del archivo por extensión: data|document|text|image|audio|unknown."""
    ext = Path(str(path)).suffix.lower()
    if ext in _DATA_EXTS:
        return "data"
    if ext in _DOC_EXTS:
        return "document"
    if ext in _TEXT_EXTS:
        return "text"
    if ext in _IMAGE_EXTS:
        return "image"
    if ext in _AUDIO_EXTS:
        return "audio"
    return "unknown"


# kind -> (tool, action, path_arg) para delegar vía ToolRegistry.execute().
# Las clases sin entrada (audio, unknown) NO son auto-procesables todavía -> error honesto.
_PLAN: dict[str, tuple[str, str, str]] = {
    "data": ("data_analysis", "csv_describe", "path"),     # CSV/XLSX -> stats
    "document": ("document", "extract_text", "path"),       # PDF/DOCX/PPTX/HTML -> texto
    "text": ("document", "extract_text", "path"),           # txt/código -> lectura plana
    "image": ("vision", "ocr", "image_path"),               # imagen -> OCR del archivo
}


def plan_for_kind(kind: str) -> tuple[str, str, str] | None:
    """(tool, action, path_arg) para delegar, o None si la clase no es auto-procesable
    todavía (audio: la STT del repo es de micrófono; unknown: tipo no reconocido)."""
    return _PLAN.get(kind)
