"""Office (PPTX/DOCX/XLSX) domain tool — extracted from domain_tools.py
(R2 sprint 2026-05-28).

Creación local de archivos Office via python-pptx / python-docx / openpyxl.
inspect/open son read-only (size + suffix). edit/export PDF DEFERRED (necesitan
handling template-específico).

Funciones extraídas (5):
  office_tool                     (entry, 9 acciones)
  _create_presentation            (PPTX con title slide + content slides)
  _create_document                (DOCX con heading + paragraphs)
  _create_spreadsheet             (XLSX, default 2 cols Campo/Valor)
  _inspect_office_file
  _output_path                    (genera path en state/generated/)
  _slides_from_args               (parse args.slides o template default ES)

Helpers desde domain_tools (lazy):
  _safe_name (cross-area), _existing_path (cross-area, lo usa source_manager)."""
from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from typing import Any

from .._shared import _err, _ok
from ..memory_pkg.state import AgentState


__all__ = [
    "office_tool",
    "_create_presentation",
    "_create_document",
    "_create_spreadsheet",
    "_inspect_office_file",
    "_output_path",
    "_slides_from_args",
]


def office_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from .helpers import _existing_path
    import os
    import shutil
    import webbrowser
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(
            python_pptx=importlib.util.find_spec("pptx") is not None,
            python_docx=importlib.util.find_spec("docx") is not None,
            openpyxl=importlib.util.find_spec("openpyxl") is not None,
            libreoffice=bool(shutil.which("soffice") or shutil.which("libreoffice")),
        )
    if action == "create_presentation":
        return _create_presentation(args, state)
    if action == "create_document":
        return _create_document(args, state)
    if action == "create_spreadsheet":
        return _create_spreadsheet(args, state)
    if action == "inspect":
        return _inspect_office_file(args)
    if action == "open":
        path = _existing_path(args)
        if not path:
            return _err("missing or invalid path", status="needs_user")
        try:
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                webbrowser.open(path.as_uri())
        except OSError as exc:
            return _err(
                f"failed to open office file: {exc}",
                path=str(path), status="failed",
                hint="no application registered to open this extension?",
            )
        return _ok(path=str(path.resolve()), opened=True, verified=False,
                   note="Open requested; verification not performed (would require UIA).")
    if action in {"edit_presentation", "edit_document", "edit_spreadsheet", "export_pdf"}:
        return _err(
            f"office.{action} is not implemented yet",
            status="needs_dependency",
            verified=False,
            completion_status="needs_implementation",
            note="Creation and inspection are implemented first; editing/export need template-specific handling.",
        )
    return _err(
        "unknown office action", action=action,
        valid_actions=[
            "status", "create_presentation", "create_document",
            "create_spreadsheet", "inspect", "open",
            "edit_presentation", "edit_document", "edit_spreadsheet", "export_pdf",
        ],
        status="needs_user",
    )


def _create_presentation(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from .helpers import _safe_name
    if importlib.util.find_spec("pptx") is None:
        return _err(
            "python-pptx is not installed",
            status="needs_dependency",
            verified=False,
            completion_status="needs_dependency",
            install_hint="python -m pip install python-pptx",
        )
    from pptx import Presentation

    title = str(args.get("title") or args.get("topic") or "Presentacion").strip()
    path = _output_path(args, state, _safe_name(title), ".pptx")
    slides = _slides_from_args(args, title)
    prs = Presentation()
    if slides:
        first = slides[0]
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        # python-pptx exposes `text` and `text_frame` on specific shape subclasses
        # (placeholders, autoshapes) but the abstract BaseShape type doesn't
        # declare them. Use setattr/getattr to bypass the static-type wall.
        title_shape: Any = slide.shapes.title
        if title_shape is not None:
            title_shape.text = str(first.get("title") or title)
        sub_shape: Any = slide.placeholders[1]
        sub_shape.text = str(first.get("subtitle") or first.get("body") or "")
        for item in slides[1:]:
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            t_shape: Any = slide.shapes.title
            if t_shape is not None:
                t_shape.text = str(item.get("title") or "Slide")
            body_shape: Any = slide.placeholders[1]
            body = body_shape.text_frame
            body.clear()
            raw_bullets = item.get("bullets")
            bullets: list[Any] | None = raw_bullets if isinstance(raw_bullets, list) else None
            if bullets:
                for bullet in bullets:
                    p = body.add_paragraph()
                    p.text = str(bullet)
                    p.level = 0
            else:
                body.text = str(item.get("body") or "")
    prs.save(str(path))
    resource = state.register_resource(
        "office_file",
        path.name,
        cleanup_tool="filesystem",
        cleanup_args={"action": "delete", "path": str(path)},
        metadata={"kind": "presentation", "path": str(path), "slides": len(prs.slides)},
    )
    return _ok(path=str(path.resolve()), kind="presentation", slides=len(prs.slides), resource=resource.get("resource"))


def _create_document(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from .helpers import _safe_name
    if importlib.util.find_spec("docx") is None:
        return _err("python-docx is not installed", status="needs_dependency", verified=False, install_hint="python -m pip install python-docx")
    from docx import Document

    title = str(args.get("title") or "Documento").strip()
    path = _output_path(args, state, _safe_name(title), ".docx")
    doc = Document()
    doc.add_heading(title, 0)
    content = str(args.get("content") or args.get("body") or "")
    for paragraph in [p.strip() for p in content.splitlines() if p.strip()]:
        doc.add_paragraph(paragraph)
    doc.save(str(path))
    resource = state.register_resource("office_file", path.name, cleanup_tool="filesystem", cleanup_args={"action": "delete", "path": str(path)}, metadata={"kind": "document", "path": str(path)})
    return _ok(path=str(path.resolve()), kind="document", resource=resource.get("resource"))


def _create_spreadsheet(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from .helpers import _safe_name
    if importlib.util.find_spec("openpyxl") is None:
        return _err("openpyxl is not installed", status="needs_dependency", verified=False, install_hint="python -m pip install openpyxl")
    from openpyxl import Workbook

    title = str(args.get("title") or "Hoja").strip()
    path = _output_path(args, state, _safe_name(title), ".xlsx")
    wb = Workbook()
    ws = wb.active
    if ws is None:
        return _err("openpyxl Workbook has no active sheet", verified=False)
    ws.title = "Datos"
    raw_rows = args.get("rows")
    rows: list[Any] = raw_rows if isinstance(raw_rows, list) else []
    if not rows:
        rows = [["Campo", "Valor"], ["Titulo", title]]
    for row in rows:
        ws.append(row if isinstance(row, list) else [str(row)])
    wb.save(str(path))
    resource = state.register_resource("office_file", path.name, cleanup_tool="filesystem", cleanup_args={"action": "delete", "path": str(path)}, metadata={"kind": "spreadsheet", "path": str(path), "rows": len(rows)})
    return _ok(path=str(path.resolve()), kind="spreadsheet", rows=len(rows), resource=resource.get("resource"))


def _inspect_office_file(args: dict[str, Any]) -> dict[str, Any]:
    from .helpers import _existing_path
    path = _existing_path(args)
    if not path:
        return _err("missing or invalid path")
    return _ok(path=str(path.resolve()), suffix=path.suffix.casefold(), size=path.stat().st_size)


def _output_path(args: dict[str, Any], state: AgentState, stem: str, suffix: str) -> Path:
    raw = str(args.get("path") or "").strip()
    if raw:
        path = Path(raw).expanduser()
    else:
        out_dir = state.path.parent / "generated"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{stem}_{time.strftime('%Y%m%d_%H%M%S')}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.casefold() != suffix:
        path = path.with_suffix(suffix)
    return path


def _slides_from_args(args: dict[str, Any], title: str) -> list[dict[str, Any]]:
    slides = args.get("slides")
    if isinstance(slides, str):
        try:
            slides = json.loads(slides)
        except json.JSONDecodeError:
            slides = None
    if isinstance(slides, list) and slides:
        return [item if isinstance(item, dict) else {"title": str(item)} for item in slides]
    topic = str(args.get("topic") or title)
    return [
        {"title": title, "subtitle": topic},
        {"title": "Resumen", "bullets": [f"Contexto de {topic}", "Puntos clave", "Siguiente paso"]},
        {"title": "Conclusiones", "bullets": ["Idea principal", "Impacto", "Acciones recomendadas"]},
    ]
