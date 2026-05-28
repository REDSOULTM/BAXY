"""Document parsing/extraction domain tool — extracted from domain_tools.py
(R2 sprint 2026-05-28).

Lectura de PDF/DOCX/XLSX/PPTX/HTML/texto plano + extracción de tablas/images
+ OCR (Tesseract). Soporte por capas, cada backend reporta needs_dependency
individual si falta (pypdf, python-docx, openpyxl, python-pptx, bs4,
pdfplumber, PyMuPDF/pdf2image, tesseract).

Funciones extraídas (12):
  document_tool                       (entry, 8 acciones)
  _document_extract_text              (router por extensión)
  _document_extract_pdf
  _document_extract_docx
  _document_extract_xlsx
  _document_extract_pptx
  _document_extract_html              (bs4 + regex fallback)
  _document_extract_tables            (pdfplumber + xlsx)
  _document_extract_images            (OOXML zip + PDF pypdf)
  _document_ocr_pdf                   (PyMuPDF/pdf2image -> tesseract)
  _document_ocr_pdf_with_fitz
  _document_ocr_pdf_with_pdf2image
  _document_compare                   (difflib SequenceMatcher)

Helpers desde domain_tools (lazy): _safe_name."""
from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any, Callable

from ._shared import _err, _ok
from .tool_result import ToolResult
from .state import AgentState


Executor = Callable[[str, dict[str, Any]], dict[str, Any]]


__all__ = [
    "document_tool",
    "_document_extract_text",
    "_document_extract_pdf",
    "_document_extract_docx",
    "_document_extract_xlsx",
    "_document_extract_pptx",
    "_document_extract_html",
    "_document_extract_tables",
    "_document_extract_images",
    "_document_ocr_pdf",
    "_document_ocr_pdf_with_fitz",
    "_document_ocr_pdf_with_pdf2image",
    "_document_compare",
]


# R4 sprint 2026-05-28: handler migrado a ToolResult con .to_dict().
def _ok_tr(**kw):
    return ToolResult.ok_result(**kw).to_dict()


def _err_tr(msg, **kw):
    return ToolResult.err(msg, **kw).to_dict()


def document_tool(args: dict[str, Any], state: AgentState, knowledge_executor: Executor | None = None) -> dict[str, Any]:
    """Compound tool for PDF/DOCX/XLSX/PPTX/HTML parsing and ingestion.

    Actions: status, extract_text, extract_tables, extract_images, ocr_pdf,
    summarize, ingest_to_knowledge, compare_documents.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok_tr(
            backends={
                "pdf_text": importlib.util.find_spec("pypdf") is not None,
                "pdf_tables": importlib.util.find_spec("pdfplumber") is not None,
                "docx": importlib.util.find_spec("docx") is not None,
                "xlsx": importlib.util.find_spec("openpyxl") is not None,
                "pptx": importlib.util.find_spec("pptx") is not None,
                "html": importlib.util.find_spec("bs4") is not None,
                "tesseract": bool(shutil.which("tesseract") or shutil.which("tesseract.exe")),
            },
            supported_extensions=[".pdf", ".docx", ".xlsx", ".pptx", ".html", ".htm", ".txt", ".md"],
            note="Each backend reports needs_dependency individually if missing.",
        )
    if action == "extract_text":
        return _document_extract_text(args)
    if action == "extract_tables":
        return _document_extract_tables(args)
    if action == "extract_images":
        return _document_extract_images(args, state)
    if action == "ocr_pdf":
        return _document_ocr_pdf(args, state)
    if action == "summarize":
        # Summarization is delegated to the calling LLM; this tool only extracts
        # enough text and reports basic stats so the agent can summarize.
        text_result = _document_extract_text(args)
        if not text_result.get("ok"):
            return text_result
        text = text_result.get("text") or ""
        return _ok_tr(
            path=text_result.get("path"),
            chars=len(text),
            word_count=len(text.split()),
            text_preview=text[: int(args.get("preview_chars", 4000))],
            note="Use the returned text_preview to write the summary; this tool does not call an LLM.",
        )
    if action == "ingest_to_knowledge":
        if not knowledge_executor:
            return _err_tr("ingest_to_knowledge requires the knowledge executor", status="needs_implementation")
        path_raw = str(args.get("path") or "").strip()
        if not path_raw:
            return _err_tr("missing path")
        # Extract first, then feed to knowledge tool.
        extracted = _document_extract_text({"path": path_raw, "max_chars": int(args.get("max_chars", 200000))})
        if not extracted.get("ok"):
            return extracted
        text = extracted.get("text") or ""
        if not text.strip():
            return _err_tr("no text extracted; cannot ingest", path=path_raw)
        title = str(args.get("title") or Path(path_raw).name)
        return knowledge_executor("knowledge", {"action": "ingest", "title": title, "source": path_raw, "text": text})
    if action == "compare_documents":
        return _document_compare(args)
    return _err_tr(
        "unknown document action", action=action,
        valid_actions=[
            "status", "extract_text", "extract_tables", "extract_images",
            "ocr_pdf", "summarize", "ingest_to_knowledge", "compare_documents",
        ],
        status="needs_user",
    )


def _document_extract_text(args: dict[str, Any]) -> dict[str, Any]:
    path_raw = str(args.get("path") or "").strip()
    if not path_raw:
        return _err_tr("missing path")
    path = Path(path_raw).expanduser()
    if not path.is_file():
        return _err_tr("file not found", path=str(path))
    suffix = path.suffix.casefold()
    max_chars = int(args.get("max_chars", 200000))
    if suffix in {".txt", ".md", ".csv", ".log", ".py", ".ps1", ".yaml", ".yml", ".json"}:
        text = path.read_text(encoding="utf-8", errors="replace")[:max_chars]
        return _ok_tr(path=str(path), suffix=suffix, text=text, chars=len(text), backend="plain")
    if suffix in {".html", ".htm"}:
        return _document_extract_html(path, max_chars)
    if suffix == ".pdf":
        return _document_extract_pdf(path, max_chars)
    if suffix == ".docx":
        return _document_extract_docx(path, max_chars)
    if suffix == ".xlsx":
        return _document_extract_xlsx(path, max_chars)
    if suffix == ".pptx":
        return _document_extract_pptx(path, max_chars)
    return _err_tr(f"unsupported extension: {suffix}", path=str(path))


def _document_extract_pdf(path: Path, max_chars: int) -> dict[str, Any]:
    if importlib.util.find_spec("pypdf") is None:
        return _err_tr(
            "pypdf is not installed",
            status="needs_dependency", verified=False,
            install_hint="python -m pip install pypdf",
        )
    from pypdf import PdfReader
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        return _err_tr(f"failed to open PDF: {exc}", path=str(path))
    pages_text: list[str] = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:
            pages_text.append("")
    text = "\n\n".join(pages_text)
    truncated = len(text) > max_chars
    return _ok_tr(
        path=str(path), suffix=".pdf", backend="pypdf",
        pages=len(reader.pages),
        text=text[:max_chars], chars=len(text), truncated=truncated,
    )


def _document_extract_docx(path: Path, max_chars: int) -> dict[str, Any]:
    if importlib.util.find_spec("docx") is None:
        return _err_tr(
            "python-docx is not installed",
            status="needs_dependency", verified=False,
            install_hint="python -m pip install python-docx",
        )
    from docx import Document
    try:
        doc = Document(str(path))
    except Exception as exc:
        return _err_tr(f"failed to open DOCX: {exc}", path=str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text]
    text = "\n".join(paragraphs)
    truncated = len(text) > max_chars
    return _ok_tr(
        path=str(path), suffix=".docx", backend="python-docx",
        paragraphs=len(paragraphs),
        text=text[:max_chars], chars=len(text), truncated=truncated,
    )


def _document_extract_xlsx(path: Path, max_chars: int) -> dict[str, Any]:
    if importlib.util.find_spec("openpyxl") is None:
        return _err_tr(
            "openpyxl is not installed",
            status="needs_dependency", verified=False,
            install_hint="python -m pip install openpyxl",
        )
    from openpyxl import load_workbook
    try:
        wb = load_workbook(str(path), read_only=True, data_only=True)
    except Exception as exc:
        return _err_tr(f"failed to open XLSX: {exc}", path=str(path))
    sheets: list[dict[str, Any]] = []
    text_lines: list[str] = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            cells = ["" if cell is None else str(cell) for cell in row]
            rows.append(cells)
            text_lines.append(f"[{sheet_name}] " + " | ".join(cells))
            if len("\n".join(text_lines)) > max_chars:
                break
        sheets.append({"name": sheet_name, "rows": len(rows), "preview": rows[:5]})
        if len("\n".join(text_lines)) > max_chars:
            break
    text = "\n".join(text_lines)[:max_chars]
    return _ok_tr(
        path=str(path), suffix=".xlsx", backend="openpyxl",
        sheets=sheets, sheet_count=len(sheets),
        text=text, chars=len(text),
    )


def _document_extract_pptx(path: Path, max_chars: int) -> dict[str, Any]:
    if importlib.util.find_spec("pptx") is None:
        return _err_tr(
            "python-pptx is not installed",
            status="needs_dependency", verified=False,
            install_hint="python -m pip install python-pptx",
        )
    from pptx import Presentation
    try:
        prs = Presentation(str(path))
    except Exception as exc:
        return _err_tr(f"failed to open PPTX: {exc}", path=str(path))
    slides_text: list[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            # BaseShape doesn't declare `text`; only specific subclasses (placeholder,
            # autoshape) expose it. Probe with getattr to dodge the static type wall.
            shape_text = getattr(shape, "text", None)
            if shape_text:
                slides_text.append(str(shape_text))
    text = "\n\n".join(slides_text)
    truncated = len(text) > max_chars
    return _ok_tr(
        path=str(path), suffix=".pptx", backend="python-pptx",
        slides=len(prs.slides),
        text=text[:max_chars], chars=len(text), truncated=truncated,
    )


def _document_extract_html(path: Path, max_chars: int) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if importlib.util.find_spec("bs4") is not None:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        title = soup.title.string if soup.title else None
        return _ok_tr(path=str(path), suffix=".html", backend="beautifulsoup4", title=title, text=text[:max_chars], chars=len(text))
    # Fallback: strip tags with regex.
    text = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return _ok_tr(path=str(path), suffix=".html", backend="regex_fallback", text=text[:max_chars], chars=len(text), note="Install beautifulsoup4 for better extraction.")


def _document_extract_tables(args: dict[str, Any]) -> dict[str, Any]:
    path_raw = str(args.get("path") or "").strip()
    if not path_raw:
        return _err_tr("missing path")
    path = Path(path_raw).expanduser()
    if not path.is_file():
        return _err_tr("file not found", path=str(path))
    suffix = path.suffix.casefold()
    if suffix == ".xlsx":
        return _document_extract_xlsx(path, max_chars=200000)
    if suffix == ".pdf":
        if importlib.util.find_spec("pdfplumber") is None:
            return _err_tr(
                "pdfplumber is not installed",
                status="needs_dependency", verified=False,
                install_hint="python -m pip install pdfplumber",
            )
        import pdfplumber  # type: ignore[import-not-found]
        try:
            tables_out: list[dict[str, Any]] = []
            with pdfplumber.open(str(path)) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    page_tables = page.extract_tables() or []
                    for tbl_idx, tbl in enumerate(page_tables):
                        tables_out.append({"page": page_idx + 1, "index": tbl_idx, "rows": len(tbl), "data": tbl[:200]})
            return _ok_tr(path=str(path), suffix=".pdf", backend="pdfplumber", tables=tables_out, table_count=len(tables_out))
        except Exception as exc:
            return _err_tr(f"pdfplumber failed: {exc}", path=str(path))
    return _err_tr(f"extract_tables does not support {suffix}", supported=[".pdf", ".xlsx"])


def _document_extract_images(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from .domain_tools_helpers import _safe_name
    path_raw = str(args.get("path") or "").strip()
    if not path_raw:
        return _err_tr("missing path")
    path = Path(path_raw).expanduser()
    if not path.is_file():
        return _err_tr("file not found", path=str(path))
    suffix = path.suffix.casefold()
    out_dir = Path(str(args.get("out_dir") or state.path.parent / "extracted" / f"{_safe_name(path.stem)}_{int(time.time())}")).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[str] = []
    if suffix in {".docx", ".pptx", ".xlsx"}:
        # Office Open XML files are zip archives; media lives in word/media/, ppt/media/, xl/media/.
        try:
            with zipfile.ZipFile(path, "r") as archive:
                for entry in archive.infolist():
                    if "/media/" in entry.filename and not entry.is_dir():
                        target = out_dir / Path(entry.filename).name
                        with archive.open(entry) as src, target.open("wb") as dst:
                            shutil.copyfileobj(src, dst)
                        extracted.append(str(target))
        except (zipfile.BadZipFile, OSError) as exc:
            return _err_tr(f"failed to read OOXML media: {exc}", path=str(path))
        return _ok_tr(path=str(path), suffix=suffix, backend="ooxml_zip", out_dir=str(out_dir), images=extracted, count=len(extracted))
    if suffix == ".pdf":
        if importlib.util.find_spec("pypdf") is None:
            return _err_tr("pypdf is not installed", status="needs_dependency", install_hint="python -m pip install pypdf")
        from pypdf import PdfReader
        try:
            reader = PdfReader(str(path))
            for page_idx, page in enumerate(reader.pages):
                for img_idx, img in enumerate(page.images):
                    target = out_dir / f"page{page_idx + 1}_img{img_idx + 1}_{img.name}"
                    target.write_bytes(img.data)
                    extracted.append(str(target))
        except Exception as exc:
            return _err_tr(f"pypdf image extraction failed: {exc}", path=str(path))
        return _ok_tr(path=str(path), suffix=".pdf", backend="pypdf", out_dir=str(out_dir), images=extracted, count=len(extracted))
    return _err_tr(f"extract_images does not support {suffix}", supported=[".pdf", ".docx", ".pptx", ".xlsx"])


def _document_ocr_pdf(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    path_raw = str(args.get("path") or "").strip()
    if not path_raw:
        return _err_tr("missing path")
    path = Path(path_raw).expanduser()
    if not path.is_file():
        return _err_tr("PDF not found", path=str(path))
    if path.suffix.casefold() != ".pdf":
        return _err_tr("ocr_pdf only accepts .pdf files", path=str(path))
    tesseract = shutil.which("tesseract") or shutil.which("tesseract.exe")
    if not tesseract:
        return _err_tr(
            "Tesseract OCR is not installed",
            status="needs_dependency", verified=False,
            install_hint="winget install UB-Mannheim.TesseractOCR",
        )
    # We need a backend to render PDF pages to PNG. pypdf does not render; we
    # need pdf2image+poppler OR PyMuPDF (fitz). Try fitz first (no external bin),
    # then pdf2image. If neither is available, return needs_dependency with the
    # full set of options.
    if importlib.util.find_spec("fitz") is not None:
        return _document_ocr_pdf_with_fitz(path, state, tesseract, args)
    if importlib.util.find_spec("pdf2image") is not None:
        return _document_ocr_pdf_with_pdf2image(path, state, tesseract, args)
    return _err_tr(
        "PDF rendering requires PyMuPDF (fitz) or pdf2image+poppler",
        status="needs_dependency", verified=False,
        install_hint="python -m pip install PyMuPDF (preferred, no external binary needed)",
    )


def _document_ocr_pdf_with_fitz(path: Path, state: AgentState, tesseract: str, args: dict[str, Any]) -> dict[str, Any]:
    from .domain_tools_helpers import _safe_name
    import fitz  # type: ignore[import-not-found]  # PyMuPDF
    lang = str(args.get("lang") or "spa+eng")
    out_dir = state.path.parent / "extracted" / f"ocr_{_safe_name(path.stem)}_{int(time.time())}"
    out_dir.mkdir(parents=True, exist_ok=True)
    pages_text: list[str] = []
    try:
        doc = fitz.open(str(path))
        for idx in range(len(doc)):
            pix = doc[idx].get_pixmap(dpi=200)
            png_path = out_dir / f"page_{idx + 1}.png"
            pix.save(str(png_path))
            proc = subprocess.run([tesseract, str(png_path), "stdout", "-l", lang, "--psm", "6"], capture_output=True, text=True, timeout=60)
            pages_text.append(proc.stdout if proc.returncode == 0 else "")
    except Exception as exc:
        return _err_tr(f"OCR failed: {exc}", path=str(path))
    text = "\n\n".join(pages_text)
    return _ok_tr(
        path=str(path), backend="fitz+tesseract", out_dir=str(out_dir),
        pages=len(pages_text), text=text[: int(args.get("max_chars", 200000))], chars=len(text), lang=lang,
    )


def _document_ocr_pdf_with_pdf2image(path: Path, state: AgentState, tesseract: str, args: dict[str, Any]) -> dict[str, Any]:
    from .domain_tools_helpers import _safe_name
    from pdf2image import convert_from_path
    lang = str(args.get("lang") or "spa+eng")
    out_dir = state.path.parent / "extracted" / f"ocr_{_safe_name(path.stem)}_{int(time.time())}"
    out_dir.mkdir(parents=True, exist_ok=True)
    pages_text: list[str] = []
    try:
        images = convert_from_path(str(path), dpi=200)
        for idx, img in enumerate(images):
            png_path = out_dir / f"page_{idx + 1}.png"
            img.save(png_path, "PNG")
            proc = subprocess.run([tesseract, str(png_path), "stdout", "-l", lang, "--psm", "6"], capture_output=True, text=True, timeout=60)
            pages_text.append(proc.stdout if proc.returncode == 0 else "")
    except Exception as exc:
        return _err_tr(f"OCR failed: {exc}", path=str(path), install_hint="pdf2image requires poppler; install with: winget install oschwartz10612.Poppler")
    text = "\n\n".join(pages_text)
    return _ok_tr(
        path=str(path), backend="pdf2image+tesseract", out_dir=str(out_dir),
        pages=len(pages_text), text=text[: int(args.get("max_chars", 200000))], chars=len(text), lang=lang,
    )


def _document_compare(args: dict[str, Any]) -> dict[str, Any]:
    a_raw = str(args.get("a") or args.get("left") or "").strip()
    b_raw = str(args.get("b") or args.get("right") or "").strip()
    if not a_raw or not b_raw:
        return _err_tr("compare_documents requires a/left and b/right paths")
    a = Path(a_raw).expanduser()
    b = Path(b_raw).expanduser()
    if not a.is_file() or not b.is_file():
        return _err_tr("one or both documents not found", a=str(a), b=str(b))
    ta = _document_extract_text({"path": str(a), "max_chars": 500000})
    tb = _document_extract_text({"path": str(b), "max_chars": 500000})
    if not ta.get("ok"):
        return ta
    if not tb.get("ok"):
        return tb
    import difflib
    seq_a = (ta.get("text") or "").splitlines()
    seq_b = (tb.get("text") or "").splitlines()
    diff = list(difflib.unified_diff(seq_a, seq_b, fromfile=a.name, tofile=b.name, lineterm=""))
    similarity = difflib.SequenceMatcher(None, ta.get("text") or "", tb.get("text") or "").ratio()
    return _ok_tr(
        a=str(a), b=str(b),
        a_chars=ta.get("chars", 0), b_chars=tb.get("chars", 0),
        similarity=round(similarity, 4),
        diff_lines=len(diff),
        diff_preview="\n".join(diff[:200]),
    )
