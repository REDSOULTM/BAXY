"""Higher-level local domain tools for the Gemma4 agent."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import time
import webbrowser
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from .state import AgentState


Executor = Callable[[str, dict[str, Any]], dict[str, Any]]


def _ok(**kwargs: Any) -> dict[str, Any]:
    return {"ok": True, **kwargs}


def _err(message: str, **kwargs: Any) -> dict[str, Any]:
    return {"ok": False, "error": message, **kwargs}


def office_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
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
            return _err("missing or invalid path")
        os.startfile(path) if os.name == "nt" else webbrowser.open(path.as_uri())
        return _ok(path=str(path.resolve()), opened=True)
    if action in {"edit_presentation", "edit_document", "edit_spreadsheet", "export_pdf"}:
        return _err(
            f"office.{action} is not implemented yet",
            status="needs_dependency",
            verified=False,
            completion_status="needs_implementation",
            note="Creation and inspection are implemented first; editing/export need template-specific handling.",
        )
    return _err("unknown office action", action=action)


def audio_device_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action in {"status", "list"}:
        helper = _find_soundvolumeview()
        svv_devices = _svv_list_devices() if helper else []
        devices = svv_devices if svv_devices else _audio_endpoints()
        defaults = _svv_current_defaults(svv_devices) if svv_devices else {}
        return _ok(
            devices=devices,
            count=len(devices),
            defaults=defaults,
            soundvolumeview=str(helper) if helper else None,
            can_set_default=bool(helper),
            install_hint="Download SoundVolumeView.zip from NirSoft and set GEMMA4_SOUNDVOLUMEVIEW to the exe path.",
        )
    if action == "snapshot":
        helper = _find_soundvolumeview()
        svv_devices = _svv_list_devices() if helper else []
        defaults = _svv_current_defaults(svv_devices) if svv_devices else {}
        rollback = _audio_rollback_steps(defaults)
        checkpoint = state.checkpoint(
            "audio device snapshot",
            rollback=rollback,
            metadata={"devices": svv_devices or _audio_endpoints(), "defaults": defaults, "helper": str(helper) if helper else None},
        )
        return _ok(
            snapshot=checkpoint.get("checkpoint"),
            defaults=defaults,
            rollback_steps=len(rollback),
            note="Snapshot saves device list and per-role defaults. Restore replays /SetDefault using SoundVolumeView." if rollback else "Defaults not detected; install SoundVolumeView for restorable snapshots.",
        )
    if action == "restore":
        return _restore_audio_default(args, state)
    if action in {"set_default", "set_default_communications"}:
        return _set_default_audio_device(args, state, communications=action == "set_default_communications")
    if action in {"set_app_route", "get_app_routes"}:
        return _err(
            f"audio_device.{action} needs a dedicated local helper/API",
            status="needs_dependency",
            verified=False,
            completion_status="needs_dependency",
            install_hint="Per-app routing requires SoundVolumeView /SetAppDefault and a known target app; pass app and device names explicitly.",
        )
    return _err("unknown audio_device action", action=action)


def notification_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(windows=True, scheduled_tasks=shutil.which("powershell") is not None, backend="windows_scheduled_tasks")
    if action == "history":
        return _notification_history(args, state)
    if action in {"list", "timer_list", "alarm_list", "reminder_list"}:
        resources = state.list_resources(include_closed=bool(args.get("include_closed", True))).get("resources", [])
        items = [r for r in resources if r.get("kind") in {"notification", "timer", "alarm", "local_reminder"}]
        if action != "list":
            kind = _kind_for_notification_action(action)
            items = [r for r in items if r.get("kind") == kind]
        # Enrich with live ScheduledTask info when available.
        enriched = [_enrich_notification_resource(item) for item in items]
        return _ok(items=enriched, count=len(enriched))
    if action in {"toast_now", "notify_sound"}:
        title = str(args.get("title") or "Gemma4 Agent").strip()
        text = str(args.get("text") or args.get("message") or title).strip()
        result = _show_message_box(title, text)
        return _ok(title=title, text=text, attempted=True, verified=False, result=result, completion_status="notification_requested")
    if action in {"timer_start", "alarm_create", "reminder_create", "toast_schedule"}:
        return _schedule_notification(args, state, kind=_kind_for_notification_action(action))
    if action in {"timer_cancel", "alarm_cancel", "reminder_delete", "delete"}:
        return _delete_notification(args, state)
    if action == "reminder_update":
        return _update_notification(args, state, kind="local_reminder")
    if action in {"timer_update", "alarm_update", "notification_update"}:
        return _update_notification(args, state, kind=_kind_for_notification_action(action.replace("_update", "")))
    return _err("unknown notification action", action=action)


def routine_tool(args: dict[str, Any], state: AgentState, executor: Executor | None = None) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(
            local_state=True,
            run_now=bool(executor),
            triggers=["manual", "cron"],
            persistent_triggers=True,
            backend="windows_scheduled_tasks",
            deferred_triggers=["on_app_open", "on_file_change", "on_network_event"],
            deferred_reason="Process/file/network triggers need a long-running watcher process; not implemented in this iteration.",
        )
    if action == "list":
        resources = state.list_resources(include_closed=bool(args.get("include_closed", False))).get("resources", [])
        routines = [_enrich_routine_resource(r) for r in resources if r.get("kind") == "routine"]
        return _ok(routines=routines, count=len(routines))
    if action == "create":
        steps = args.get("steps") or []
        if isinstance(steps, str):
            try:
                steps = json.loads(steps)
            except json.JSONDecodeError:
                return _err("steps must be a JSON array of {tool,args}")
        if not isinstance(steps, list) or not steps:
            return _err("routine.create requires steps array")
        # Validate each step
        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                return _err(f"step {index} is not an object", step=step)
            if not str(step.get("tool") or "").strip():
                return _err(f"step {index} has no tool", step=step)
            if str(step.get("tool")).strip() == "routine":
                return _err(f"step {index} cannot call routine recursively")
        label = str(args.get("name") or args.get("label") or f"Routine {int(time.time())}")
        trigger = args.get("trigger") if isinstance(args.get("trigger"), dict) else {"type": str(args.get("trigger") or "manual")}
        trigger_type = str(trigger.get("type") or "manual").casefold()
        if trigger_type not in {"manual", "cron", "once"}:
            return _err(
                f"trigger type '{trigger_type}' is not implemented yet; supported: manual, cron, once",
                status="needs_implementation",
                deferred=trigger_type,
            )
        task_name = None
        if trigger_type in {"cron", "once"}:
            task_name = _routine_task_name(label)
            register = _register_routine_scheduled_task(task_name, label, trigger)
            if not register.get("ok"):
                return register
        resource = state.register_resource(
            "routine",
            label,
            cleanup_tool="routine",
            cleanup_args={"action": "delete", "name": label},
            metadata={
                "enabled": bool(args.get("enabled", True)),
                "trigger": trigger,
                "trigger_type": trigger_type,
                "task_name": task_name,
                "steps": steps,
            },
        )
        return _ok(routine=resource.get("resource"), trigger=trigger, task_name=task_name, status="done")
    if action == "run_now":
        routine = _find_routine(args, state)
        if not routine:
            return _err("routine not found")
        if not executor:
            return _err("routine.run_now requires an executor wired by the registry", status="needs_implementation", verified=False)
        if routine.get("metadata", {}).get("enabled") is False:
            return _err("routine is disabled", routine=routine)
        results = []
        steps = routine.get("metadata", {}).get("steps") or []
        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                results.append({"index": index, "ok": False, "error": "invalid step"})
                break
            tool = str(step.get("tool") or "").strip()
            step_args = step.get("args") if isinstance(step.get("args"), dict) else {}
            if not tool or tool == "routine":
                results.append({"index": index, "ok": False, "error": "invalid or recursive tool", "tool": tool})
                break
            result = executor(tool, step_args)
            results.append({"index": index, "tool": tool, "args": step_args, "result": result, "ok": bool(result.get("ok"))})
            if not result.get("ok"):
                break
        completed = bool(results) and all(item.get("ok") for item in results)
        run_record = {
            "ran_at": datetime.now().isoformat(),
            "steps_total": len(steps),
            "steps_executed": len(results),
            "completed": completed,
            "results": results,
        }
        _append_routine_run(state, str(routine["id"]), run_record)
        return _ok(routine=routine, results=results, completed=completed, run=run_record)
    if action in {"delete", "enable", "disable"}:
        routine = _find_routine(args, state)
        if not routine:
            return _err("routine not found")
        if action == "delete":
            task_name = str((routine.get("metadata") or {}).get("task_name") or "").strip()
            if task_name:
                _unregister_routine_scheduled_task(task_name)
            return state.mark_cleaned(str(routine["id"]), {"deleted": True})
        enabled = action == "enable"
        return _update_resource_metadata(state, str(routine["id"]), {"enabled": enabled})
    if action == "history":
        routine = _find_routine(args, state) if (args.get("id") or args.get("name")) else None
        return _routine_history(state, routine, limit=int(args.get("limit", 20)))
    if action == "simulate":
        routine = _find_routine(args, state)
        if not routine:
            return _err("routine not found")
        steps = routine.get("metadata", {}).get("steps") or []
        return _ok(routine=routine, would_run=[{"tool": s.get("tool"), "args": s.get("args")} for s in steps if isinstance(s, dict)], step_count=len(steps), note="dry-run; nothing was executed")
    return _err("unknown routine action", action=action)


def document_tool(args: dict[str, Any], state: AgentState, knowledge_executor: Executor | None = None) -> dict[str, Any]:
    """Compound tool for PDF/DOCX/XLSX/PPTX/HTML parsing and ingestion.

    Actions: status, extract_text, extract_tables, extract_images, ocr_pdf,
    summarize, ingest_to_knowledge, compare_documents.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(
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
        return _ok(
            path=text_result.get("path"),
            chars=len(text),
            word_count=len(text.split()),
            text_preview=text[: int(args.get("preview_chars", 4000))],
            note="Use the returned text_preview to write the summary; this tool does not call an LLM.",
        )
    if action == "ingest_to_knowledge":
        if not knowledge_executor:
            return _err("ingest_to_knowledge requires the knowledge executor", status="needs_implementation")
        path_raw = str(args.get("path") or "").strip()
        if not path_raw:
            return _err("missing path")
        # Extract first, then feed to knowledge tool.
        extracted = _document_extract_text({"path": path_raw, "max_chars": int(args.get("max_chars", 200000))})
        if not extracted.get("ok"):
            return extracted
        text = extracted.get("text") or ""
        if not text.strip():
            return _err("no text extracted; cannot ingest", path=path_raw)
        title = str(args.get("title") or Path(path_raw).name)
        return knowledge_executor("knowledge", {"action": "ingest", "title": title, "source": path_raw, "text": text})
    if action == "compare_documents":
        return _document_compare(args)
    return _err("unknown document action", action=action)


def _document_extract_text(args: dict[str, Any]) -> dict[str, Any]:
    path_raw = str(args.get("path") or "").strip()
    if not path_raw:
        return _err("missing path")
    path = Path(path_raw).expanduser()
    if not path.is_file():
        return _err("file not found", path=str(path))
    suffix = path.suffix.casefold()
    max_chars = int(args.get("max_chars", 200000))
    if suffix in {".txt", ".md", ".csv", ".log", ".py", ".ps1", ".yaml", ".yml", ".json"}:
        text = path.read_text(encoding="utf-8", errors="replace")[:max_chars]
        return _ok(path=str(path), suffix=suffix, text=text, chars=len(text), backend="plain")
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
    return _err(f"unsupported extension: {suffix}", path=str(path))


def _document_extract_pdf(path: Path, max_chars: int) -> dict[str, Any]:
    if importlib.util.find_spec("pypdf") is None:
        return _err(
            "pypdf is not installed",
            status="needs_dependency", verified=False,
            install_hint="python -m pip install pypdf",
        )
    from pypdf import PdfReader
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        return _err(f"failed to open PDF: {exc}", path=str(path))
    pages_text: list[str] = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:
            pages_text.append("")
    text = "\n\n".join(pages_text)
    truncated = len(text) > max_chars
    return _ok(
        path=str(path), suffix=".pdf", backend="pypdf",
        pages=len(reader.pages),
        text=text[:max_chars], chars=len(text), truncated=truncated,
    )


def _document_extract_docx(path: Path, max_chars: int) -> dict[str, Any]:
    if importlib.util.find_spec("docx") is None:
        return _err(
            "python-docx is not installed",
            status="needs_dependency", verified=False,
            install_hint="python -m pip install python-docx",
        )
    from docx import Document
    try:
        doc = Document(str(path))
    except Exception as exc:
        return _err(f"failed to open DOCX: {exc}", path=str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text]
    text = "\n".join(paragraphs)
    truncated = len(text) > max_chars
    return _ok(
        path=str(path), suffix=".docx", backend="python-docx",
        paragraphs=len(paragraphs),
        text=text[:max_chars], chars=len(text), truncated=truncated,
    )


def _document_extract_xlsx(path: Path, max_chars: int) -> dict[str, Any]:
    if importlib.util.find_spec("openpyxl") is None:
        return _err(
            "openpyxl is not installed",
            status="needs_dependency", verified=False,
            install_hint="python -m pip install openpyxl",
        )
    from openpyxl import load_workbook
    try:
        wb = load_workbook(str(path), read_only=True, data_only=True)
    except Exception as exc:
        return _err(f"failed to open XLSX: {exc}", path=str(path))
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
    return _ok(
        path=str(path), suffix=".xlsx", backend="openpyxl",
        sheets=sheets, sheet_count=len(sheets),
        text=text, chars=len(text),
    )


def _document_extract_pptx(path: Path, max_chars: int) -> dict[str, Any]:
    if importlib.util.find_spec("pptx") is None:
        return _err(
            "python-pptx is not installed",
            status="needs_dependency", verified=False,
            install_hint="python -m pip install python-pptx",
        )
    from pptx import Presentation
    try:
        prs = Presentation(str(path))
    except Exception as exc:
        return _err(f"failed to open PPTX: {exc}", path=str(path))
    slides_text: list[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                slides_text.append(str(shape.text))
    text = "\n\n".join(slides_text)
    truncated = len(text) > max_chars
    return _ok(
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
        return _ok(path=str(path), suffix=".html", backend="beautifulsoup4", title=title, text=text[:max_chars], chars=len(text))
    # Fallback: strip tags with regex.
    text = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return _ok(path=str(path), suffix=".html", backend="regex_fallback", text=text[:max_chars], chars=len(text), note="Install beautifulsoup4 for better extraction.")


def _document_extract_tables(args: dict[str, Any]) -> dict[str, Any]:
    path_raw = str(args.get("path") or "").strip()
    if not path_raw:
        return _err("missing path")
    path = Path(path_raw).expanduser()
    if not path.is_file():
        return _err("file not found", path=str(path))
    suffix = path.suffix.casefold()
    if suffix == ".xlsx":
        return _document_extract_xlsx(path, max_chars=200000)
    if suffix == ".pdf":
        if importlib.util.find_spec("pdfplumber") is None:
            return _err(
                "pdfplumber is not installed",
                status="needs_dependency", verified=False,
                install_hint="python -m pip install pdfplumber",
            )
        import pdfplumber
        try:
            tables_out: list[dict[str, Any]] = []
            with pdfplumber.open(str(path)) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    page_tables = page.extract_tables() or []
                    for tbl_idx, tbl in enumerate(page_tables):
                        tables_out.append({"page": page_idx + 1, "index": tbl_idx, "rows": len(tbl), "data": tbl[:200]})
            return _ok(path=str(path), suffix=".pdf", backend="pdfplumber", tables=tables_out, table_count=len(tables_out))
        except Exception as exc:
            return _err(f"pdfplumber failed: {exc}", path=str(path))
    return _err(f"extract_tables does not support {suffix}", supported=[".pdf", ".xlsx"])


def _document_extract_images(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    path_raw = str(args.get("path") or "").strip()
    if not path_raw:
        return _err("missing path")
    path = Path(path_raw).expanduser()
    if not path.is_file():
        return _err("file not found", path=str(path))
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
            return _err(f"failed to read OOXML media: {exc}", path=str(path))
        return _ok(path=str(path), suffix=suffix, backend="ooxml_zip", out_dir=str(out_dir), images=extracted, count=len(extracted))
    if suffix == ".pdf":
        if importlib.util.find_spec("pypdf") is None:
            return _err("pypdf is not installed", status="needs_dependency", install_hint="python -m pip install pypdf")
        from pypdf import PdfReader
        try:
            reader = PdfReader(str(path))
            for page_idx, page in enumerate(reader.pages):
                for img_idx, img in enumerate(page.images):
                    target = out_dir / f"page{page_idx + 1}_img{img_idx + 1}_{img.name}"
                    target.write_bytes(img.data)
                    extracted.append(str(target))
        except Exception as exc:
            return _err(f"pypdf image extraction failed: {exc}", path=str(path))
        return _ok(path=str(path), suffix=".pdf", backend="pypdf", out_dir=str(out_dir), images=extracted, count=len(extracted))
    return _err(f"extract_images does not support {suffix}", supported=[".pdf", ".docx", ".pptx", ".xlsx"])


def _document_ocr_pdf(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    path_raw = str(args.get("path") or "").strip()
    if not path_raw:
        return _err("missing path")
    path = Path(path_raw).expanduser()
    if not path.is_file():
        return _err("PDF not found", path=str(path))
    if path.suffix.casefold() != ".pdf":
        return _err("ocr_pdf only accepts .pdf files", path=str(path))
    tesseract = shutil.which("tesseract") or shutil.which("tesseract.exe")
    if not tesseract:
        return _err(
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
    return _err(
        "PDF rendering requires PyMuPDF (fitz) or pdf2image+poppler",
        status="needs_dependency", verified=False,
        install_hint="python -m pip install PyMuPDF (preferred, no external binary needed)",
    )


def _document_ocr_pdf_with_fitz(path: Path, state: AgentState, tesseract: str, args: dict[str, Any]) -> dict[str, Any]:
    import fitz  # PyMuPDF
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
        return _err(f"OCR failed: {exc}", path=str(path))
    text = "\n\n".join(pages_text)
    return _ok(
        path=str(path), backend="fitz+tesseract", out_dir=str(out_dir),
        pages=len(pages_text), text=text[: int(args.get("max_chars", 200000))], chars=len(text), lang=lang,
    )


def _document_ocr_pdf_with_pdf2image(path: Path, state: AgentState, tesseract: str, args: dict[str, Any]) -> dict[str, Any]:
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
        return _err(f"OCR failed: {exc}", path=str(path), install_hint="pdf2image requires poppler; install with: winget install oschwartz10612.Poppler")
    text = "\n\n".join(pages_text)
    return _ok(
        path=str(path), backend="pdf2image+tesseract", out_dir=str(out_dir),
        pages=len(pages_text), text=text[: int(args.get("max_chars", 200000))], chars=len(text), lang=lang,
    )


def _document_compare(args: dict[str, Any]) -> dict[str, Any]:
    a_raw = str(args.get("a") or args.get("left") or "").strip()
    b_raw = str(args.get("b") or args.get("right") or "").strip()
    if not a_raw or not b_raw:
        return _err("compare_documents requires a/left and b/right paths")
    a = Path(a_raw).expanduser()
    b = Path(b_raw).expanduser()
    if not a.is_file() or not b.is_file():
        return _err("one or both documents not found", a=str(a), b=str(b))
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
    return _ok(
        a=str(a), b=str(b),
        a_chars=ta.get("chars", 0), b_chars=tb.get("chars", 0),
        similarity=round(similarity, 4),
        diff_lines=len(diff),
        diff_preview="\n".join(diff[:200]),
    )


def _routine_task_name(label: str) -> str:
    return f"Gemma4Routine_{_safe_name(label)[:40]}_{int(time.time())}"


def _register_routine_scheduled_task(task_name: str, routine_label: str, trigger: dict[str, Any]) -> dict[str, Any]:
    """Register a Scheduled Task that invokes the routine_runner module."""
    python_exe = _detect_python_executable()
    if not python_exe:
        return _err("no python executable found for scheduled task", status="needs_dependency", verified=False)
    # Use label resolution at fire time; the runner accepts --label or --id.
    arg_line = f'-m gemma4_agent.routine_runner --label "{routine_label}"'
    trigger_ps = _build_routine_trigger_ps(trigger)
    if not trigger_ps:
        return _err(f"invalid routine trigger: {trigger}", trigger=trigger)
    ps = f"""
$Action = New-ScheduledTaskAction -Execute '{_ps_quote(python_exe)}' -Argument '{_ps_quote(arg_line)}'
$Trigger = {trigger_ps}
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName '{_ps_quote(task_name)}' -TaskPath '\\Gemma4Agent\\' -Action $Action -Trigger $Trigger -Settings $Settings -Description 'Gemma4 routine: {_ps_quote(routine_label)}' -Force | Out-Null
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return _err("failed to register routine scheduled task", stderr=proc.stderr, exit_code=proc.returncode)
    return _ok(task_name=task_name, trigger=trigger)


def _unregister_routine_scheduled_task(task_name: str) -> dict[str, Any]:
    ps = f"Unregister-ScheduledTask -TaskPath '\\Gemma4Agent\\' -TaskName '{_ps_quote(task_name)}' -Confirm:$false -ErrorAction SilentlyContinue"
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=20)
    return {"task_name": task_name, "exit_code": proc.returncode, "stderr": proc.stderr}


def _build_routine_trigger_ps(trigger: dict[str, Any]) -> str | None:
    """Translate a trigger dict into the PowerShell expression for the trigger."""
    ttype = str(trigger.get("type") or "manual").casefold()
    if ttype == "manual":
        return None
    if ttype == "once":
        at = str(trigger.get("at") or "").strip()
        if not at:
            return None
        return f"New-ScheduledTaskTrigger -Once -At (Get-Date '{at}')"
    if ttype == "cron":
        cadence = str(trigger.get("cadence") or trigger.get("every") or "daily").casefold()
        at = str(trigger.get("at") or "09:00").strip()
        if cadence == "daily":
            return f"New-ScheduledTaskTrigger -Daily -At '{at}'"
        if cadence == "weekly":
            days = trigger.get("days_of_week") if isinstance(trigger.get("days_of_week"), list) else ["Monday"]
            days_str = ",".join(str(d) for d in days)
            return f"New-ScheduledTaskTrigger -Weekly -DaysOfWeek {days_str} -At '{at}'"
        if cadence == "hourly":
            return f"New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1)"
        if cadence == "minutes":
            n = int(trigger.get("interval_minutes", 5))
            return f"New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes {n})"
    return None


def _detect_python_executable() -> str | None:
    import sys
    candidate = sys.executable
    if candidate and Path(candidate).is_file():
        return candidate
    for name in ("python.exe", "python3.exe", "python", "python3"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _enrich_routine_resource(resource: dict[str, Any]) -> dict[str, Any]:
    """Add live ScheduledTask info if the routine has a task_name."""
    metadata = resource.get("metadata") or {}
    task_name = str(metadata.get("task_name") or "").strip()
    if not task_name:
        return resource
    script = (
        f"$t = Get-ScheduledTask -TaskPath '\\Gemma4Agent\\' -TaskName '{_ps_quote(task_name)}' -ErrorAction SilentlyContinue; "
        f"if ($t) {{ "
        f"  $info = $t | Get-ScheduledTaskInfo; "
        f"  [PSCustomObject]@{{ State=$t.State.ToString(); LastRunTime=$info.LastRunTime; NextRunTime=$info.NextRunTime; LastTaskResult=$info.LastTaskResult }} | ConvertTo-Json -Depth 3 "
        f"}}"
    )
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=15)
    if proc.returncode == 0 and proc.stdout.strip():
        try:
            data = json.loads(proc.stdout)
            if isinstance(data, dict):
                resource = dict(resource)
                resource["scheduled_task_info"] = data
        except json.JSONDecodeError:
            pass
    return resource


def _append_routine_run(state: AgentState, resource_id: str, run_record: dict[str, Any]) -> None:
    data = state._load()
    resource = data.get("resources", {}).get(resource_id)
    if not resource:
        return
    metadata = resource.setdefault("metadata", {})
    history = list(metadata.get("history") or [])
    history.append(run_record)
    # Keep last 50 runs to avoid unbounded growth.
    metadata["history"] = history[-50:]
    metadata["last_run"] = run_record
    state._save(data)


def _routine_history(state: AgentState, routine: dict[str, Any] | None, *, limit: int = 20) -> dict[str, Any]:
    if routine:
        history = list((routine.get("metadata") or {}).get("history") or [])
        return _ok(routine_id=routine.get("id"), label=routine.get("label"), history=history[-limit:], count=len(history))
    # All routines
    out = []
    for res in state._load().get("resources", {}).values():
        if res.get("kind") != "routine":
            continue
        last = (res.get("metadata") or {}).get("last_run")
        if last:
            out.append({"routine_id": res.get("id"), "label": res.get("label"), "last_run": last})
    return _ok(runs=out, count=len(out))


def media_tool(args: dict[str, Any], executor: Executor, state: AgentState | None = None) -> dict[str, Any]:
    action = str(args.get("action") or "play").casefold()
    if action == "status":
        return _ok(
            backends=["browser_youtube", "windows_media_keys", "local_file", "vlc_cli", "winrt_smtc"],
            now_playing_supported=True,
            vlc_available=bool(shutil.which("vlc") or shutil.which("vlc.exe")),
            note="now_playing uses Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager via PowerShell.",
        )
    if action == "play":
        query = str(args.get("query") or args.get("song") or args.get("title") or "").strip()
        path = str(args.get("path") or "").strip()
        provider = str(args.get("provider") or "youtube").casefold()
        if path:
            return _media_play_local(path, args)
        if provider in {"youtube", "yt", "browser"}:
            return executor("browser", {"action": "youtube_play", "query": query or "musica"})
        if provider == "vlc":
            vlc = shutil.which("vlc") or shutil.which("vlc.exe")
            if not vlc:
                return _err(
                    "VLC is not installed",
                    status="needs_dependency", verified=False,
                    install_hint="winget install VideoLAN.VLC",
                )
            target = str(args.get("path") or args.get("url") or "").strip()
            if not target:
                return _err("vlc provider requires path or url")
            return _media_play_vlc(vlc, target)
        return _err("unsupported media provider", provider=provider, status="needs_dependency", verified=False)
    if action == "open_local":
        path = str(args.get("path") or "").strip()
        if not path:
            return _err("missing path")
        return _media_play_local(path, args)
    if action in {"pause", "resume", "play_pause"}:
        return executor("audio", {"action": "media_play_pause"})
    if action == "stop":
        return executor("audio", {"action": "media_stop"})
    if action == "next":
        return executor("audio", {"action": "next"})
    if action == "previous":
        return executor("audio", {"action": "previous"})
    if action == "now_playing":
        return _media_now_playing()
    if action in {"queue_add", "queue_clear", "queue_list"}:
        if not state:
            return _err("queue actions require state", status="needs_implementation")
        return _media_queue(action, args, state)
    if action == "search_local_library":
        return _media_search_local_library(args)
    if action in {"volume_for_app", "cast_lan"}:
        return _err(
            f"media.{action} is not implemented yet",
            status="needs_implementation", verified=False,
            note=("volume_for_app needs SoundVolumeView /SetAppVolume" if action == "volume_for_app" else "cast_lan needs UPnP/DLNA backend (deferred)"),
        )
    return _err("unknown media action", action=action)


def _media_play_local(path_raw: str, args: dict[str, Any]) -> dict[str, Any]:
    target = Path(path_raw).expanduser()
    if not target.exists():
        return _err("media file not found", path=path_raw)
    backend = str(args.get("backend") or "").casefold()
    if backend == "vlc":
        vlc = shutil.which("vlc") or shutil.which("vlc.exe")
        if vlc:
            return _media_play_vlc(vlc, str(target))
        return _err(
            "VLC backend requested but vlc not on PATH",
            status="needs_dependency", install_hint="winget install VideoLAN.VLC",
        )
    if os.name == "nt":
        os.startfile(target)
    else:
        webbrowser.open(target.as_uri())
    return _ok(action="play", provider="local_file", path=str(target.resolve()), opened=True, verified=True)


def _media_play_vlc(vlc: str, target: str) -> dict[str, Any]:
    proc = subprocess.Popen(
        [vlc, target, "--play-and-exit", "--no-video-title-show"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return _ok(action="play", provider="vlc", target=target, pid=proc.pid, verified=False, status="attempted", note="VLC launched; verify via now_playing or window list.")


def _media_now_playing() -> dict[str, Any]:
    """Query Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager.

    Pattern from Fleex (2018) and Microsoft Q&A; uses System.WindowsRuntimeSystemExtensions.AsTask
    to convert IAsyncOperation<T> to a Task<T> so PowerShell can wait synchronously.
    """
    script = r"""
$ErrorActionPreference = 'Stop'
try {
  Add-Type -AssemblyName System.Runtime.WindowsRuntime
  [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,Windows.Media.Control,ContentType=WindowsRuntime] > $null
  [Windows.Media.Control.GlobalSystemMediaTransportControlsSession,Windows.Media.Control,ContentType=WindowsRuntime] > $null
  [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties,Windows.Media.Control,ContentType=WindowsRuntime] > $null

  $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
  function Await($op, $resultType) {
    $task = $asTaskGeneric.MakeGenericMethod($resultType).Invoke($null, @($op))
    $task.Wait(-1) | Out-Null
    return $task.Result
  }

  $mgr = Await ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
  $session = $mgr.GetCurrentSession()
  if ($null -eq $session) {
    [PSCustomObject]@{ has_session=$false } | ConvertTo-Json
    exit 0
  }
  $props = Await ($session.TryGetMediaPropertiesAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties])
  $info = $session.GetPlaybackInfo()
  $timeline = $session.GetTimelineProperties()
  [PSCustomObject]@{
    has_session = $true
    source_app_user_model_id = $session.SourceAppUserModelId
    title = $props.Title
    artist = $props.Artist
    album_title = $props.AlbumTitle
    track_number = $props.TrackNumber
    genres = @($props.Genres)
    playback_status = $info.PlaybackStatus.ToString()
    playback_type = $info.PlaybackType.ToString()
    is_play_enabled = $info.Controls.IsPlayEnabled
    is_pause_enabled = $info.Controls.IsPauseEnabled
    is_next_enabled = $info.Controls.IsNextEnabled
    is_previous_enabled = $info.Controls.IsPreviousEnabled
    position_seconds = $timeline.Position.TotalSeconds
    end_seconds = $timeline.EndTime.TotalSeconds
  } | ConvertTo-Json -Depth 4
} catch {
  [PSCustomObject]@{ error = $_.Exception.Message; has_session = $false } | ConvertTo-Json
}
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        return _err("now_playing query failed", stderr=proc.stderr, exit_code=proc.returncode)
    raw = proc.stdout.strip()
    if not raw:
        return _ok(has_session=False, note="no active media session")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _err("now_playing returned invalid JSON", raw=raw[:1000])
    if not data.get("has_session"):
        return _ok(has_session=False, raw=data)
    return _ok(
        has_session=True,
        title=data.get("title"),
        artist=data.get("artist"),
        album=data.get("album_title"),
        source_app=data.get("source_app_user_model_id"),
        playback_status=data.get("playback_status"),
        playback_type=data.get("playback_type"),
        controls={
            "play": data.get("is_play_enabled"),
            "pause": data.get("is_pause_enabled"),
            "next": data.get("is_next_enabled"),
            "previous": data.get("is_previous_enabled"),
        },
        position_seconds=data.get("position_seconds"),
        end_seconds=data.get("end_seconds"),
        verified=True,
        evidence={"source": "Windows.Media.Control.GSMTCSM"},
    )


def _media_queue(action: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    if action == "queue_clear":
        for item in _resources_by_kind(state, "media_queue", include_closed=False):
            state.mark_cleaned(str(item["id"]), {"deleted": True})
        return _ok(cleared=True)
    if action == "queue_list":
        items = _resources_by_kind(state, "media_queue", include_closed=False)
        items.sort(key=lambda r: str(r.get("metadata", {}).get("added_at", "")))
        return _ok(queue=items, count=len(items))
    if action == "queue_add":
        item_query = str(args.get("query") or args.get("title") or "").strip()
        item_path = str(args.get("path") or "").strip()
        if not item_query and not item_path:
            return _err("queue_add requires query or path")
        label = item_query or Path(item_path).name
        resource = state.register_resource(
            "media_queue",
            label,
            metadata={
                "query": item_query or None,
                "path": item_path or None,
                "provider": args.get("provider"),
                "added_at": datetime.now().isoformat(),
            },
        )
        return _ok(queue_item=resource.get("resource"))
    return _err("unknown queue action", action=action)


def _media_search_local_library(args: dict[str, Any]) -> dict[str, Any]:
    root_raw = str(args.get("root") or "").strip()
    if not root_raw:
        # default user music folder
        root = Path.home() / "Music"
    else:
        root = Path(root_raw).expanduser()
    if not root.exists():
        return _err("library root not found", root=str(root))
    query = str(args.get("query") or "").casefold()
    extensions = {".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".wma"}
    limit = int(args.get("limit", 50))
    results = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in extensions:
            continue
        if query and query not in path.name.casefold() and query not in str(path.parent.name).casefold():
            continue
        try:
            results.append({"path": str(path), "name": path.name, "size": path.stat().st_size})
        except OSError:
            continue
        if len(results) >= limit:
            break
    return _ok(results=results, count=len(results), root=str(root))


def source_manager_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(local_state=True, source_count=len(_resources_by_kind(state, "source")))
    if action in {"list", "sources"}:
        return _ok(sources=_resources_by_kind(state, "source", include_closed=bool(args.get("include_closed", False))))
    if action in {"save", "add"}:
        title = str(args.get("title") or args.get("url") or args.get("source") or "source").strip()
        text = str(args.get("text") or args.get("content") or "").strip()
        url = str(args.get("url") or "").strip()
        resource = state.register_resource(
            "source",
            title,
            metadata={"title": title, "url": url, "source": args.get("source"), "text": text, "saved_at": datetime.now().isoformat()},
        )
        return _ok(source=resource.get("resource"))
    if action == "snapshot_file":
        path = _existing_path(args)
        if not path:
            return _err("missing or invalid path")
        max_chars = int(args.get("max_chars", 12000))
        text = path.read_text(encoding="utf-8", errors="replace")[:max_chars]
        resource = state.register_resource("source", path.name, metadata={"title": path.name, "path": str(path), "text": text, "saved_at": datetime.now().isoformat()})
        return _ok(source=resource.get("resource"), chars=len(text))
    if action == "search":
        query = str(args.get("query") or "").casefold()
        if not query:
            return _err("missing query")
        matches = []
        for source in _resources_by_kind(state, "source", include_closed=bool(args.get("include_closed", False))):
            haystack = json.dumps(source.get("metadata", {}), ensure_ascii=False).casefold() + " " + str(source.get("label", "")).casefold()
            if query in haystack:
                matches.append(source)
        return _ok(matches=matches[: int(args.get("limit", 10))], count=len(matches))
    if action in {"read", "get"}:
        source = _find_resource(args, state, "source")
        return _ok(source=source) if source else _err("source not found")
    if action == "delete":
        source = _find_resource(args, state, "source")
        return state.mark_cleaned(str(source["id"]), {"deleted": True}) if source else _err("source not found")
    return _err("unknown source_manager action", action=action)


def dependency_tool(args: dict[str, Any]) -> dict[str, Any]:
    action = str(args.get("action") or "status").casefold()
    catalog = _dependency_catalog()
    if action in {"status", "list"}:
        return _ok(dependencies=list(catalog.values()), missing=[d for d in catalog.values() if not d["available"]])
    if action in {"verify", "explain_missing"}:
        name = str(args.get("name") or args.get("dependency") or "").strip().casefold()
        matches = [item for key, item in catalog.items() if name in {key, item["name"].casefold()}] if name else [d for d in catalog.values() if not d["available"]]
        return _ok(matches=matches, count=len(matches))
    if action in {"install", "repair"}:
        name = str(args.get("name") or args.get("dependency") or "").strip().casefold()
        item = catalog.get(name)
        return _err(
            "dependency.install is advisory in this local tool",
            status="needs_user",
            verified=False,
            completion_status="needs_user_install",
            dependency=item or name,
            install_hint=(item or {}).get("install_hint") or "Use package/terminal explicitly if you want installation.",
        )
    return _err("unknown dependency action", action=action)


def contacts_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(local_state=True, count=len(_resources_by_kind(state, "contact")))
    if action == "list":
        return _ok(contacts=_resources_by_kind(state, "contact", include_closed=bool(args.get("include_closed", False))))
    if action in {"create", "add"}:
        name = str(args.get("name") or "").strip()
        if not name:
            return _err("missing contact name")
        resource = state.register_resource(
            "contact",
            name,
            metadata={"name": name, "email": args.get("email"), "phone": args.get("phone"), "notes": args.get("notes"), "created_at": datetime.now().isoformat()},
        )
        return _ok(contact=resource.get("resource"))
    if action == "search":
        query = str(args.get("query") or args.get("name") or "").casefold()
        matches = [c for c in _resources_by_kind(state, "contact", include_closed=True) if query in json.dumps(c, ensure_ascii=False).casefold()]
        return _ok(matches=matches[: int(args.get("limit", 10))], count=len(matches))
    if action == "delete":
        contact = _find_resource(args, state, "contact")
        return state.mark_cleaned(str(contact["id"]), {"deleted": True}) if contact else _err("contact not found")
    if action == "update":
        return _contacts_update(args, state)
    if action == "export_vcard":
        return _contacts_export_vcard(args, state)
    if action == "import_vcard":
        return _contacts_import_vcard(args, state)
    if action == "resolve_recipient":
        return _contacts_resolve_recipient(args, state)
    return _err("unknown contacts action", action=action)


def _contacts_update(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    contact = _find_resource(args, state, "contact")
    if not contact:
        return _err("contact not found")
    updates: dict[str, Any] = {}
    for key in ("name", "email", "phone", "notes"):
        if key in args and args[key] is not None:
            updates[key] = args[key]
    if not updates:
        return _err("no updatable fields provided", supported=["name", "email", "phone", "notes"])
    if "name" in updates:
        data = state._load()
        rec = data.get("resources", {}).get(str(contact["id"]))
        if rec:
            rec["label"] = str(updates["name"])
            state._save(data)
    return _update_resource_metadata(state, str(contact["id"]), updates)


def _contacts_export_vcard(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    contacts = _resources_by_kind(state, "contact", include_closed=False)
    if not contacts:
        return _err("no contacts to export")
    path_raw = str(args.get("path") or "").strip()
    if path_raw:
        path = Path(path_raw).expanduser()
    else:
        path = state.path.parent / "generated" / f"contacts_{time.strftime('%Y%m%d_%H%M%S')}.vcf"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\r\n".join(_contact_to_vcard(c) for c in contacts) + "\r\n"
    path.write_text(body, encoding="utf-8")
    return _ok(path=str(path.resolve()), exported=len(contacts))


def _contact_to_vcard(contact: dict[str, Any]) -> str:
    meta = contact.get("metadata") or {}
    name = str(meta.get("name") or contact.get("label") or "")
    email = str(meta.get("email") or "")
    phone = str(meta.get("phone") or "")
    notes = str(meta.get("notes") or "")
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{_vcard_escape(name)}", f"N:{_vcard_escape(name)};;;;"]
    if email:
        lines.append(f"EMAIL:{_vcard_escape(email)}")
    if phone:
        lines.append(f"TEL:{_vcard_escape(phone)}")
    if notes:
        lines.append(f"NOTE:{_vcard_escape(notes)}")
    lines.append("END:VCARD")
    return "\r\n".join(lines)


def _vcard_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def _vcard_unescape(text: str) -> str:
    return text.replace("\\,", ",").replace("\\;", ";").replace("\\n", "\n").replace("\\N", "\n").replace("\\\\", "\\")


def _contacts_import_vcard(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    path_raw = str(args.get("path") or args.get("file") or "").strip()
    text = str(args.get("content") or args.get("vcard") or "")
    if path_raw:
        p = Path(path_raw).expanduser()
        if not p.is_file():
            return _err("vCard file not found", path=str(p))
        text = p.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return _err("no vCard content provided")
    cards = _vcard_parse(text)
    if not cards:
        return _err("no VCARD blocks found")
    created = []
    for card in cards:
        name = card.get("fn") or card.get("n") or "Contact"
        resource = state.register_resource(
            "contact",
            name,
            metadata={
                "name": name,
                "email": card.get("email"),
                "phone": card.get("tel"),
                "notes": card.get("note"),
                "imported_from": path_raw or "<inline>",
                "created_at": datetime.now().isoformat(),
            },
        )
        created.append(resource.get("resource"))
    return _ok(imported=len(created), contacts=created[:50], total_parsed=len(cards))


def _vcard_parse(text: str) -> list[dict[str, Any]]:
    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded: list[str] = []
    for line in raw_lines:
        if unfolded and (line.startswith(" ") or line.startswith("\t")):
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    cards: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in unfolded:
        stripped = line.strip()
        if not stripped:
            continue
        upper = stripped.upper()
        if upper == "BEGIN:VCARD":
            current = {}
            continue
        if upper == "END:VCARD":
            if current is not None:
                cards.append(current)
            current = None
            continue
        if current is None:
            continue
        sep = stripped.find(":")
        if sep < 0:
            continue
        head, value = stripped[:sep], stripped[sep + 1:]
        name = head.split(";", 1)[0].upper()
        value = _vcard_unescape(value)
        if name == "FN":
            current["fn"] = value
        elif name == "N":
            # N: Family;Given;Additional;Prefix;Suffix
            parts = value.split(";")
            given = parts[1] if len(parts) > 1 else ""
            family = parts[0] if parts else ""
            current["n"] = (given + " " + family).strip() or value
        elif name == "EMAIL":
            current.setdefault("email", value)
        elif name == "TEL":
            current.setdefault("tel", value)
        elif name == "NOTE":
            current["note"] = value
    return cards


def _contacts_resolve_recipient(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    query = str(args.get("query") or args.get("name") or args.get("recipient") or "").strip()
    if not query:
        return _err("missing query")
    q = query.casefold()
    contacts = _resources_by_kind(state, "contact", include_closed=False)
    scored: list[tuple[int, dict[str, Any]]] = []
    for c in contacts:
        meta = c.get("metadata") or {}
        name = str(meta.get("name") or c.get("label") or "").casefold()
        email = str(meta.get("email") or "").casefold()
        phone = str(meta.get("phone") or "").casefold()
        score = 0
        if q == name:
            score += 100
        elif q in name:
            score += 50
        if q == email:
            score += 90
        elif q in email:
            score += 40
        if q == phone:
            score += 80
        elif q in phone:
            score += 30
        if score:
            scored.append((score, c))
    scored.sort(key=lambda t: -t[0])
    matches = [{"contact": c, "score": s} for s, c in scored[: int(args.get("limit", 5))]]
    return _ok(query=query, matches=matches, count=len(matches), best=matches[0] if matches else None)


def notes_tasks_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(notes=len(_resources_by_kind(state, "note")), tasks=len(_resources_by_kind(state, "task")))
    if action in {"note_create", "create_note"}:
        title = str(args.get("title") or "Nota").strip()
        text = str(args.get("text") or args.get("content") or "").strip()
        resource = state.register_resource("note", title, metadata={"title": title, "text": text, "tags": args.get("tags"), "created_at": datetime.now().isoformat()})
        return _ok(note=resource.get("resource"))
    if action in {"task_create", "create_task"}:
        title = str(args.get("title") or args.get("text") or "Tarea").strip()
        resource = state.register_resource("task", title, metadata={"title": title, "text": args.get("text"), "due": args.get("due"), "status": "open", "created_at": datetime.now().isoformat()})
        return _ok(task=resource.get("resource"))
    if action in {"note_list", "notes", "list"}:
        return _ok(notes=_resources_by_kind(state, "note", include_closed=bool(args.get("include_closed", False))))
    if action in {"task_list", "tasks"}:
        return _ok(tasks=_resources_by_kind(state, "task", include_closed=bool(args.get("include_closed", False))))
    if action in {"note_search", "task_search", "search"}:
        kinds = ["note", "task"] if action == "search" else ["note"] if action.startswith("note") else ["task"]
        query = str(args.get("query") or "").casefold()
        matches = [r for r in _resources_by_kind(state, kinds, include_closed=True) if query in json.dumps(r, ensure_ascii=False).casefold()]
        return _ok(matches=matches[: int(args.get("limit", 10))], count=len(matches))
    if action == "task_complete":
        task = _find_resource(args, state, "task")
        return _update_resource_metadata(state, str(task["id"]), {"status": "completed", "completed_at": datetime.now().isoformat()}) if task else _err("task not found")
    if action in {"note_delete", "task_delete", "delete"}:
        resource = _find_resource(args, state, ["note", "task"])
        return state.mark_cleaned(str(resource["id"]), {"deleted": True}) if resource else _err("note/task not found")
    if action in {"note_update", "task_update"}:
        resource = _find_resource(args, state, "note" if action.startswith("note") else "task")
        if not resource:
            return _err("note/task not found")
        updates = {k: args[k] for k in ("title", "text", "content", "due", "tags") if k in args}
        if "content" in updates and "text" not in updates:
            updates["text"] = updates.pop("content")
        return _update_resource_metadata(state, str(resource["id"]), updates)
    return _err("unknown notes_tasks action", action=action)


def local_calendar_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(local_state=True, event_count=len(_resources_by_kind(state, "calendar_event")))
    if action in {"event_list", "list"}:
        return _ok(events=_resources_by_kind(state, "calendar_event", include_closed=bool(args.get("include_closed", False))))
    if action == "event_create":
        title = str(args.get("title") or "Evento").strip()
        start = str(args.get("start") or args.get("due") or datetime.now().isoformat())
        end = str(args.get("end") or "")
        resource = state.register_resource("calendar_event", title, metadata={"title": title, "start": start, "end": end, "location": args.get("location"), "notes": args.get("notes")})
        return _ok(event=resource.get("resource"))
    if action in {"event_delete", "delete"}:
        event = _find_resource(args, state, "calendar_event")
        return state.mark_cleaned(str(event["id"]), {"deleted": True}) if event else _err("event not found")
    if action == "ics_export":
        events = _resources_by_kind(state, "calendar_event")
        path = _calendar_export_path(args, state)
        path.write_text(_events_to_ics(events), encoding="utf-8")
        return _ok(path=str(path.resolve()), events=len(events))
    if action == "event_update":
        return _calendar_event_update(args, state)
    if action == "ics_import":
        return _calendar_ics_import(args, state)
    return _err("unknown local_calendar action", action=action)


def _calendar_event_update(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    event = _find_resource(args, state, "calendar_event")
    if not event:
        return _err("event not found")
    updates: dict[str, Any] = {}
    for key in ("title", "start", "end", "location", "notes"):
        if key in args and args[key] is not None:
            updates[key] = args[key]
    if not updates:
        return _err("no updatable fields provided", supported=["title", "start", "end", "location", "notes"])
    if "title" in updates:
        # Also update label so listings reflect the new title.
        data = state._load()
        rec = data.get("resources", {}).get(str(event["id"]))
        if rec:
            rec["label"] = str(updates["title"])
            state._save(data)
    return _update_resource_metadata(state, str(event["id"]), updates)


def _calendar_ics_import(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    path_raw = str(args.get("path") or args.get("file") or "").strip()
    text = str(args.get("content") or args.get("ics") or "")
    if path_raw:
        p = Path(path_raw).expanduser()
        if not p.is_file():
            return _err("ICS file not found", path=str(p))
        text = p.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return _err("no ICS content provided (pass path or content)")
    events_parsed = _ics_parse_events(text)
    if not events_parsed:
        return _err("no VEVENT blocks found in input")
    created = []
    for evt in events_parsed:
        title = evt.get("summary") or "Evento"
        resource = state.register_resource(
            "calendar_event",
            title,
            metadata={
                "title": title,
                "start": evt.get("dtstart") or "",
                "end": evt.get("dtend") or evt.get("dtstart") or "",
                "location": evt.get("location"),
                "notes": evt.get("description"),
                "uid": evt.get("uid"),
                "imported_from": path_raw or "<inline>",
            },
        )
        created.append(resource.get("resource"))
    return _ok(imported=len(created), events=created[:50], total_parsed=len(events_parsed))


def _ics_parse_events(text: str) -> list[dict[str, Any]]:
    """Parse ICS into a flat list of {uid, summary, dtstart, dtend, location, description}.

    Handles line folding (CRLF + space/tab continues the previous line) and the three
    DATE-TIME forms in RFC 5545: floating, UTC (Z suffix), and TZID-prefixed.
    Property parameters (between ; and :) are dropped except for TZID which is
    preserved as a separate hint.
    """
    # Step 1: unfold continuation lines.
    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded: list[str] = []
    for line in raw_lines:
        if unfolded and (line.startswith(" ") or line.startswith("\t")):
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)

    events: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in unfolded:
        stripped = line.strip()
        if not stripped:
            continue
        upper = stripped.upper()
        if upper == "BEGIN:VEVENT":
            current = {}
            continue
        if upper == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
            continue
        if current is None:
            continue
        # Property name is everything before the first ':' or ';' (params).
        # Examples:
        #  DTSTART:20251231T230000Z
        #  DTSTART;TZID=America/New_York:20251231T180000
        #  SUMMARY:Some text with \\n escapes
        sep = stripped.find(":")
        if sep < 0:
            continue
        head, value = stripped[:sep], stripped[sep + 1:]
        name = head.split(";", 1)[0].upper()
        value = _ics_unescape(value)
        if name == "UID":
            current["uid"] = value
        elif name == "SUMMARY":
            current["summary"] = value
        elif name == "DESCRIPTION":
            current["description"] = value
        elif name == "LOCATION":
            current["location"] = value
        elif name == "DTSTART":
            current["dtstart"] = _ics_normalize_datetime(value)
        elif name == "DTEND":
            current["dtend"] = _ics_normalize_datetime(value)
        elif name == "DTSTAMP":
            current["dtstamp"] = _ics_normalize_datetime(value)
    return events


def _ics_unescape(text: str) -> str:
    return text.replace("\\,", ",").replace("\\;", ";").replace("\\n", "\n").replace("\\N", "\n").replace("\\\\", "\\")


def _ics_normalize_datetime(value: str) -> str:
    """Convert an ICS DATE-TIME to an ISO-8601 string when possible.

    - 20251231T230000Z  -> 2025-12-31T23:00:00+00:00
    - 20251231T230000   -> 2025-12-31T23:00:00 (floating)
    - 20251231          -> 2025-12-31
    """
    v = value.strip()
    if not v:
        return ""
    z = v.endswith("Z")
    body = v[:-1] if z else v
    try:
        if "T" in body:
            date_part, time_part = body.split("T", 1)
            iso = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}T{time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}"
            return iso + ("+00:00" if z else "")
        if len(body) == 8:
            return f"{body[:4]}-{body[4:6]}-{body[6:8]}"
    except (IndexError, ValueError):
        pass
    return v


def habit_tracker_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    if action == "status":
        return _ok(habits=len(_resources_by_kind(state, "habit")))
    if action == "list":
        return _ok(habits=_resources_by_kind(state, "habit", include_closed=bool(args.get("include_closed", False))))
    if action == "create":
        name = str(args.get("name") or args.get("title") or "").strip()
        if not name:
            return _err("missing habit name")
        resource = state.register_resource("habit", name, metadata={"name": name, "frequency": args.get("frequency") or "daily", "logs": []})
        return _ok(habit=resource.get("resource"))
    if action == "log":
        habit = _find_resource(args, state, "habit")
        if not habit:
            return _err("habit not found")
        logs = list(habit.setdefault("metadata", {}).get("logs") or [])
        logs.append({"at": str(args.get("at") or datetime.now().isoformat()), "value": args.get("value", True), "note": args.get("note")})
        return _update_resource_metadata(state, str(habit["id"]), {"logs": logs})
    if action == "stats":
        habit = _find_resource(args, state, "habit")
        if not habit:
            return _err("habit not found")
        logs = habit.get("metadata", {}).get("logs") or []
        return _ok(habit=habit, log_count=len(logs), last=logs[-1] if logs else None)
    if action == "delete":
        habit = _find_resource(args, state, "habit")
        return state.mark_cleaned(str(habit["id"]), {"deleted": True}) if habit else _err("habit not found")
    return _err("unknown habit_tracker action", action=action)


def local_search_tool(args: dict[str, Any]) -> dict[str, Any]:
    action = str(args.get("action") or "search").casefold()
    if action == "status":
        return _ok(everything_cli=bool(shutil.which("es.exe")), backend="python_rglob")
    if action == "search":
        root = Path(str(args.get("root") or Path.home())).expanduser()
        if not root.exists():
            return _err("root not found", root=str(root))
        query = str(args.get("query") or "").casefold()
        pattern = str(args.get("pattern") or "*")
        limit = int(args.get("limit", 50))
        include_content = bool(args.get("include_content", False))
        results = []
        try:
            iterator = root.rglob(pattern) if bool(args.get("recursive", True)) else root.glob(pattern)
            for path in iterator:
                if len(results) >= limit:
                    break
                name_hit = query in path.name.casefold() if query else True
                content_hit = False
                snippet = ""
                if include_content and path.is_file() and path.stat().st_size < int(args.get("max_bytes", 2_000_000)):
                    try:
                        text = path.read_text(encoding="utf-8", errors="replace")
                        idx = text.casefold().find(query)
                        content_hit = idx >= 0
                        snippet = text[max(0, idx - 80): idx + 180] if content_hit else ""
                    except OSError:
                        pass
                if name_hit or content_hit:
                    results.append({"path": str(path), "is_file": path.is_file(), "size": path.stat().st_size if path.is_file() else None, "snippet": snippet})
        except OSError as exc:
            return _err(f"search failed: {exc}", root=str(root))
        return _ok(results=results, count=len(results), root=str(root))
    if action == "recent":
        root = Path(str(args.get("root") or Path.home())).expanduser()
        files = []
        for path in root.rglob(str(args.get("pattern") or "*")):
            if path.is_file():
                try:
                    files.append((path.stat().st_mtime, path))
                except OSError:
                    pass
            if len(files) > 5000:
                break
        files.sort(reverse=True)
        return _ok(files=[{"path": str(p), "modified": datetime.fromtimestamp(ts).isoformat()} for ts, p in files[: int(args.get("limit", 20))]])
    return _err("unknown local_search action", action=action)


def printer_scanner_tool(args: dict[str, Any]) -> dict[str, Any]:
    action = str(args.get("action") or "printers_list").casefold()
    if action == "status":
        return _ok(powershell=bool(shutil.which("powershell")), backend="Windows PrintManagement")
    if action in {"printers_list", "list"}:
        return _powershell_json("Get-Printer | Select-Object Name,DriverName,PortName,PrinterStatus,Default | ConvertTo-Json -Depth 3", "printers")
    if action == "printer_default_get":
        return _powershell_json("Get-Printer | Where-Object Default -eq $true | Select-Object Name,DriverName,PortName,PrinterStatus,Default | ConvertTo-Json -Depth 3", "printer")
    if action == "print_queue":
        name = str(args.get("name") or args.get("printer") or "").strip()
        script = f"Get-PrintJob -PrinterName '{_ps_quote(name)}' | Select-Object ID,DocumentName,JobStatus,SubmittedTime | ConvertTo-Json -Depth 3" if name else "Get-Printer | ForEach-Object { Get-PrintJob -PrinterName $_.Name -ErrorAction SilentlyContinue } | Select-Object ID,PrinterName,DocumentName,JobStatus,SubmittedTime | ConvertTo-Json -Depth 3"
        return _powershell_json(script, "jobs")
    if action == "printer_default_set":
        return _printer_set_default(args)
    if action == "print_file":
        return _printer_print_file(args)
    if action == "cancel_job":
        return _printer_cancel_job(args)
    if action == "scanners_list":
        return _scanners_list()
    if action == "scan_document":
        return _scanner_scan(args)
    return _err("unknown printer_scanner action", action=action)


def _printer_set_default(args: dict[str, Any]) -> dict[str, Any]:
    name = str(args.get("name") or args.get("printer") or "").strip()
    if not name:
        return _err("missing printer name")
    # The standard mechanism is the WScript.Network COM object's SetDefaultPrinter,
    # because Set-Printer doesn't expose a -Default flag in all builds.
    env = os.environ.copy()
    env["GEMMA4_PRINTER"] = name
    script = (
        "$net = New-Object -ComObject WScript.Network; "
        "$net.SetDefaultPrinter($env:GEMMA4_PRINTER); "
        "$d = Get-CimInstance Win32_Printer | Where-Object { $_.Default -eq $true } | Select-Object Name; "
        "$d | ConvertTo-Json -Depth 3"
    )
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        return _err("failed to set default printer", stderr=proc.stderr, exit_code=proc.returncode)
    return _ok(printer=name, default=_json_or_none(proc.stdout), verified=True)


def _printer_print_file(args: dict[str, Any]) -> dict[str, Any]:
    path_raw = str(args.get("path") or args.get("file") or "").strip()
    if not path_raw:
        return _err("missing file path")
    path = Path(path_raw).expanduser()
    if not path.is_file():
        return _err("file not found", path=str(path))
    printer_name = str(args.get("printer") or "").strip()
    # Start-Process -Verb Print sends the document to the default printer using the
    # registered handler for the file extension. To target a non-default printer,
    # we briefly switch the system default, print, then restore. This is the
    # documented Windows-supported path for non-Office files.
    env = os.environ.copy()
    env["GEMMA4_PRINT_PATH"] = str(path)
    env["GEMMA4_PRINT_PRINTER"] = printer_name
    script = r"""
$ErrorActionPreference = 'Stop'
$prev = (Get-CimInstance Win32_Printer | Where-Object { $_.Default -eq $true } | Select-Object -First 1 -ExpandProperty Name)
$target = $env:GEMMA4_PRINT_PRINTER
$changed = $false
if ($target -and $target -ne $prev) {
  $net = New-Object -ComObject WScript.Network
  $net.SetDefaultPrinter($target)
  $changed = $true
}
try {
  Start-Process -FilePath $env:GEMMA4_PRINT_PATH -Verb Print -PassThru -WindowStyle Hidden | Out-Null
  Start-Sleep -Milliseconds 800
} finally {
  if ($changed -and $prev) {
    $net = New-Object -ComObject WScript.Network
    $net.SetDefaultPrinter($prev)
  }
}
[PSCustomObject]@{ ok=$true; path=$env:GEMMA4_PRINT_PATH; printer=$target; previous=$prev } | ConvertTo-Json
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        return _err("print_file failed", stderr=proc.stderr, exit_code=proc.returncode)
    data = _json_or_none(proc.stdout) or {}
    # Probe queue to confirm a job appeared (best-effort).
    queue_probe = _powershell_json(
        f"Get-PrintJob -PrinterName '{_ps_quote(printer_name)}' -ErrorAction SilentlyContinue | Select-Object ID,DocumentName,JobStatus | ConvertTo-Json -Depth 3" if printer_name else "Get-Printer | ForEach-Object { Get-PrintJob -PrinterName $_.Name -ErrorAction SilentlyContinue } | Select-Object ID,PrinterName,DocumentName,JobStatus | ConvertTo-Json -Depth 3",
        "jobs",
    )
    return _ok(path=str(path), printer=printer_name or data.get("previous"), verified=bool(queue_probe.get("ok")), queue=queue_probe, evidence=data)


def _printer_cancel_job(args: dict[str, Any]) -> dict[str, Any]:
    printer_name = str(args.get("printer") or "").strip()
    job_id = args.get("job_id") if args.get("job_id") is not None else args.get("id")
    if not printer_name:
        return _err("missing printer name")
    if job_id is None:
        # cancel all
        script = f"Get-PrintJob -PrinterName '{_ps_quote(printer_name)}' -ErrorAction SilentlyContinue | Remove-PrintJob -Confirm:$false; [PSCustomObject]@{{ ok=$true; printer='{_ps_quote(printer_name)}'; cancelled='all' }} | ConvertTo-Json"
    else:
        script = f"Remove-PrintJob -PrinterName '{_ps_quote(printer_name)}' -ID {int(job_id)} -Confirm:$false; [PSCustomObject]@{{ ok=$true; printer='{_ps_quote(printer_name)}'; cancelled={int(job_id)} }} | ConvertTo-Json"
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        return _err("cancel_job failed", stderr=proc.stderr, exit_code=proc.returncode)
    return _ok(printer=printer_name, cancelled=job_id if job_id is not None else "all", result=_json_or_none(proc.stdout), verified=True)


def _scanners_list() -> dict[str, Any]:
    """Use WIA via PowerShell to enumerate scanners."""
    script = r"""
$ErrorActionPreference = 'Stop'
try {
  $dm = New-Object -ComObject WIA.DeviceManager
  $items = @()
  foreach ($info in $dm.DeviceInfos) {
    $type = $info.Type
    # WiaDeviceType: 1=Scanner, 2=StreamingVideo, 0=Unspecified, 65536=Camera
    if ($type -eq 1) {
      $items += [PSCustomObject]@{
        DeviceID = $info.DeviceID
        Name = $info.Properties.Item('Name').Value
        Manufacturer = $info.Properties.Item('Manufacturer').Value
      }
    }
  }
  $items | ConvertTo-Json -Depth 3
} catch {
  [PSCustomObject]@{ error = $_.Exception.Message } | ConvertTo-Json
}
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
    raw = proc.stdout.strip()
    if not raw:
        return _ok(scanners=[], count=0, note="No WIA devices detected.")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _err("scanner enumeration returned invalid JSON", raw=raw[:1000])
    if isinstance(data, dict):
        if "error" in data:
            return _err(f"scanner enumeration failed: {data['error']}", status="needs_dependency", note="WIA may not be available; install scanner drivers.")
        data = [data]
    return _ok(scanners=data, count=len(data))


def _scanner_scan(args: dict[str, Any]) -> dict[str, Any]:
    out_raw = str(args.get("output") or args.get("path") or "").strip()
    if not out_raw:
        out = Path.home() / "Pictures" / f"scan_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
    else:
        out = Path(out_raw).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    device_id = str(args.get("device_id") or "").strip()
    env = os.environ.copy()
    env["GEMMA4_SCAN_OUT"] = str(out)
    env["GEMMA4_SCAN_DEVICE"] = device_id
    script = r"""
$ErrorActionPreference = 'Stop'
try {
  $dm = New-Object -ComObject WIA.DeviceManager
  $device = $null
  if ($env:GEMMA4_SCAN_DEVICE) {
    foreach ($info in $dm.DeviceInfos) {
      if ($info.DeviceID -eq $env:GEMMA4_SCAN_DEVICE) { $device = $info.Connect(); break }
    }
  }
  if (-not $device) {
    foreach ($info in $dm.DeviceInfos) {
      if ($info.Type -eq 1) { $device = $info.Connect(); break }
    }
  }
  if (-not $device) { throw "No scanner connected" }
  $item = $device.Items.Item(1)
  $image = $item.Transfer()
  if (Test-Path $env:GEMMA4_SCAN_OUT) { Remove-Item -LiteralPath $env:GEMMA4_SCAN_OUT -Force }
  $image.SaveFile($env:GEMMA4_SCAN_OUT)
  [PSCustomObject]@{ ok=$true; path=$env:GEMMA4_SCAN_OUT } | ConvertTo-Json
} catch {
  [PSCustomObject]@{ ok=$false; error=$_.Exception.Message } | ConvertTo-Json
}
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        return _err("scan failed", stderr=proc.stderr, exit_code=proc.returncode)
    data = _json_or_none(proc.stdout) or {}
    if not data.get("ok"):
        return _err(f"scan failed: {data.get('error')}", status="needs_dependency" if "No scanner" in str(data.get("error")) else None)
    return _ok(path=str(out), size=out.stat().st_size if out.exists() else 0, verified=out.exists())


def _json_or_none(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def desktop_layout_tool(args: dict[str, Any], state: AgentState, executor: Executor) -> dict[str, Any]:
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(can_snapshot_windows=True, restore_supported=True, backend="win32_user32_movewindow")
    if action in {"windows", "list_windows"}:
        rich = _enum_windows_with_rect(int(args.get("limit", 120)))
        if rich:
            return _ok(windows=rich, count=len(rich), source="win32_enum")
        return executor("window", {"action": "list", "limit": int(args.get("limit", 80))})
    if action == "displays":
        return _powershell_json("Get-CimInstance -Namespace root\\wmi -ClassName WmiMonitorBasicDisplayParams | Select-Object InstanceName,MaxHorizontalImageSize,MaxVerticalImageSize,Active | ConvertTo-Json -Depth 3", "displays")
    if action == "snapshot":
        windows = _enum_windows_with_rect(int(args.get("limit", 120)))
        rollback = [{"tool": "desktop_layout", "args": {"action": "restore", "windows": windows}}]
        checkpoint = state.checkpoint(
            "desktop layout snapshot",
            rollback=rollback,
            metadata={"windows": windows, "created_by": "desktop_layout"},
        )
        return _ok(snapshot=checkpoint.get("checkpoint"), windows=windows, count=len(windows))
    if action == "restore":
        return _desktop_layout_restore(args, state)
    return _err("unknown desktop_layout action", action=action)


def _enum_windows_with_rect(limit: int) -> list[dict[str, Any]]:
    """Use Win32 EnumWindows + GetWindowRect to list top-level windows with geometry."""
    env = os.environ.copy()
    env["GEMMA4_LIMIT"] = str(max(1, int(limit)))
    script = r"""
Add-Type @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public class WinEnum {
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc enumProc, IntPtr lParam);
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll", CharSet = CharSet.Auto)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern int GetWindowThreadProcessId(IntPtr hWnd, out int pid);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IsZoomed(IntPtr hWnd);

  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int left; public int top; public int right; public int bottom; }
}
"@
$results = New-Object 'System.Collections.Generic.List[Hashtable]'
$fg = [WinEnum]::GetForegroundWindow()
$cb = [WinEnum+EnumWindowsProc] {
  param($hWnd, $lParam)
  if (-not [WinEnum]::IsWindowVisible($hWnd)) { return $true }
  $len = [WinEnum]::GetWindowTextLength($hWnd)
  if ($len -le 0) { return $true }
  $sb = New-Object System.Text.StringBuilder ($len + 1)
  [WinEnum]::GetWindowText($hWnd, $sb, $sb.Capacity) | Out-Null
  $title = $sb.ToString()
  if ([string]::IsNullOrWhiteSpace($title)) { return $true }
  $rect = New-Object WinEnum+RECT
  [WinEnum]::GetWindowRect($hWnd, [ref]$rect) | Out-Null
  $pid_ = 0
  [WinEnum]::GetWindowThreadProcessId($hWnd, [ref]$pid_) | Out-Null
  $proc_name = ""
  try { $proc_name = (Get-Process -Id $pid_ -ErrorAction SilentlyContinue).ProcessName } catch {}
  $results.Add(@{
    hwnd = [int64]$hWnd
    title = $title
    pid = [int]$pid_
    process = $proc_name
    foreground = ($hWnd -eq $fg)
    minimized = [WinEnum]::IsIconic($hWnd)
    maximized = [WinEnum]::IsZoomed($hWnd)
    rect = @{ left=$rect.left; top=$rect.top; right=$rect.right; bottom=$rect.bottom; width=($rect.right - $rect.left); height=($rect.bottom - $rect.top) }
  })
  return $true
}
[WinEnum]::EnumWindows($cb, [IntPtr]::Zero) | Out-Null
$limit = [int]$env:GEMMA4_LIMIT
$results | Select-Object -First $limit | ConvertTo-Json -Depth 5
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    return data if isinstance(data, list) else []


def _desktop_layout_restore(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Restore windows to a snapshot's positions via Win32 MoveWindow."""
    snapshot_id = str(args.get("snapshot_id") or args.get("checkpoint_id") or "").strip()
    explicit_windows = args.get("windows") if isinstance(args.get("windows"), list) else None
    if explicit_windows:
        windows = explicit_windows
    else:
        data = state._load()
        checkpoints = data.get("checkpoints", {})
        checkpoint = None
        if snapshot_id and snapshot_id in checkpoints:
            checkpoint = checkpoints[snapshot_id]
        else:
            for cp in reversed(list(checkpoints.values())):
                if "desktop" in str(cp.get("label", "")).casefold():
                    checkpoint = cp
                    break
        if not checkpoint:
            return _err("no desktop layout snapshot available")
        windows = (checkpoint.get("metadata") or {}).get("windows") or []
    if not windows:
        return _err("snapshot has no windows to restore")

    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for w in windows:
        if not isinstance(w, dict):
            continue
        rect = w.get("rect") or {}
        title = str(w.get("title") or "").strip()
        try:
            x = int(rect.get("left", 0))
            y = int(rect.get("top", 0))
            width = int(rect.get("width") or (rect.get("right", 0) - rect.get("left", 0)))
            height = int(rect.get("height") or (rect.get("bottom", 0) - rect.get("top", 0)))
        except (TypeError, ValueError):
            skipped.append({"title": title, "reason": "invalid rect"})
            continue
        if width <= 0 or height <= 0:
            skipped.append({"title": title, "reason": "non-positive size"})
            continue
        result = _move_window_by_title(title, x, y, width, height)
        if result.get("ok"):
            applied.append({"title": title, "x": x, "y": y, "width": width, "height": height})
        else:
            skipped.append({"title": title, "reason": result.get("error") or "move failed"})
    return _ok(restored=len(applied), skipped=len(skipped), applied=applied, skipped_details=skipped, verified=bool(applied))


def _move_window_by_title(title: str, x: int, y: int, width: int, height: int) -> dict[str, Any]:
    env = os.environ.copy()
    env["GEMMA4_TITLE"] = title
    env["GEMMA4_X"] = str(x)
    env["GEMMA4_Y"] = str(y)
    env["GEMMA4_W"] = str(width)
    env["GEMMA4_H"] = str(height)
    script = r"""
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32MR {
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool repaint);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@
$q = $env:GEMMA4_TITLE
$p = Get-Process | Where-Object { $_.MainWindowTitle -and $_.MainWindowTitle.Equals($q, [System.StringComparison]::OrdinalIgnoreCase) } | Select-Object -First 1
if (-not $p) {
  $p = Get-Process | Where-Object { $_.MainWindowTitle -and $_.MainWindowTitle.ToLower().Contains($q.ToLower()) } | Select-Object -First 1
}
if (-not $p) { [PSCustomObject]@{ ok=$false; error="window not found"; title=$q } | ConvertTo-Json; exit 0 }
[Win32MR]::ShowWindow($p.MainWindowHandle, 9) | Out-Null  # SW_RESTORE
[Win32MR]::MoveWindow($p.MainWindowHandle,[int]$env:GEMMA4_X,[int]$env:GEMMA4_Y,[int]$env:GEMMA4_W,[int]$env:GEMMA4_H,$true) | Out-Null
[PSCustomObject]@{ ok=$true; title=$p.MainWindowTitle; process=$p.ProcessName } | ConvertTo-Json
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=10)
    if proc.returncode != 0:
        return _err("MoveWindow failed", stderr=proc.stderr)
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
        return data if isinstance(data, dict) else _err("invalid MoveWindow result")
    except json.JSONDecodeError:
        return _err("invalid MoveWindow JSON", stdout=proc.stdout[:1000])


def backup_sync_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(backend="zipfile", restore_supported=True, dedupe_supported=True, verify_supported=True)
    if action == "list":
        resources = _resources_by_kind(state, "backup", include_closed=bool(args.get("include_closed", False)))
        return _ok(backups=resources, count=len(resources))
    if action == "backup_create":
        src = Path(str(args.get("src") or args.get("path") or "")).expanduser()
        if not src.exists():
            return _err("source path not found", src=str(src))
        out_dir = state.path.parent / "backups"
        out_dir.mkdir(parents=True, exist_ok=True)
        dst = Path(str(args.get("dst") or out_dir / f"{_safe_name(src.name)}_{time.strftime('%Y%m%d_%H%M%S')}.zip")).expanduser()
        dst.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as archive:
            if src.is_file():
                archive.write(src, src.name)
            else:
                for child in src.rglob("*"):
                    if child.is_file():
                        archive.write(child, child.relative_to(src.parent))
        resource = state.register_resource("backup", dst.name, metadata={"src": str(src), "dst": str(dst), "created_at": datetime.now().isoformat(), "size": dst.stat().st_size})
        return _ok(backup=resource.get("resource"), path=str(dst.resolve()), size=dst.stat().st_size)
    if action == "restore":
        return _backup_restore(args, state)
    if action == "dedupe":
        return _backup_dedupe(args)
    if action == "verify":
        return _backup_verify(args, state)
    return _err("unknown backup_sync action", action=action)


def _backup_resolve(args: dict[str, Any], state: AgentState) -> tuple[Path | None, dict[str, Any] | None]:
    """Resolve a backup either from resource id or explicit path."""
    rid = str(args.get("id") or args.get("backup_id") or args.get("resource_id") or "").strip()
    if rid:
        resource = state._load().get("resources", {}).get(rid)
        if resource and resource.get("kind") == "backup":
            path_str = str((resource.get("metadata") or {}).get("dst") or "").strip()
            if path_str:
                p = Path(path_str)
                if p.is_file():
                    return p, resource
    explicit = str(args.get("path") or args.get("backup") or "").strip()
    if explicit:
        p = Path(explicit).expanduser()
        if p.is_file():
            return p, None
    return None, None


def _backup_restore(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    backup_path, resource = _backup_resolve(args, state)
    if not backup_path:
        return _err("backup not found; pass id (res_*) or path to ZIP")
    if backup_path.suffix.casefold() != ".zip":
        return _err("only .zip backups are supported", path=str(backup_path))
    dst_raw = str(args.get("dst") or args.get("to") or "").strip()
    if dst_raw:
        dst = Path(dst_raw).expanduser()
    else:
        original_src = str((resource or {}).get("metadata", {}).get("src") or "").strip()
        dst = Path(original_src).parent if original_src else Path.cwd()
    dst.mkdir(parents=True, exist_ok=True)
    conflict_policy = str(args.get("conflict") or args.get("on_conflict") or "rename").casefold()
    if conflict_policy not in {"overwrite", "skip", "rename"}:
        return _err("conflict policy must be overwrite|skip|rename")
    preview_only = bool(args.get("preview", False))

    extracted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    renamed: list[dict[str, Any]] = []
    overwritten: list[dict[str, Any]] = []

    try:
        with zipfile.ZipFile(backup_path, "r") as archive:
            entries = archive.infolist()
            if preview_only:
                return _ok(
                    preview=True, backup=str(backup_path), dst=str(dst),
                    entries=[{"name": e.filename, "size": e.file_size} for e in entries[:200]],
                    total_entries=len(entries),
                )
            for entry in entries:
                if entry.is_dir():
                    (dst / entry.filename).mkdir(parents=True, exist_ok=True)
                    continue
                final_target = dst / entry.filename
                final_target.parent.mkdir(parents=True, exist_ok=True)
                if final_target.exists():
                    if conflict_policy == "skip":
                        skipped.append({"name": entry.filename})
                        continue
                    if conflict_policy == "rename":
                        final_target = _next_available_path(final_target)
                        renamed.append({"from": entry.filename, "to": str(final_target.relative_to(dst))})
                    elif conflict_policy == "overwrite":
                        overwritten.append({"name": entry.filename})
                with archive.open(entry, "r") as src_fh, final_target.open("wb") as dst_fh:
                    shutil.copyfileobj(src_fh, dst_fh)
                extracted.append({"name": entry.filename, "size": entry.file_size, "dst": str(final_target)})
    except (zipfile.BadZipFile, OSError) as exc:
        return _err(f"restore failed: {exc}", backup=str(backup_path), dst=str(dst))

    return _ok(
        backup=str(backup_path), dst=str(dst), conflict_policy=conflict_policy,
        extracted_count=len(extracted), skipped_count=len(skipped),
        renamed_count=len(renamed), overwritten_count=len(overwritten),
        extracted=extracted[:50], skipped=skipped[:50], renamed=renamed[:50], overwritten=overwritten[:50],
        verified=True, evidence={"dst": str(dst), "entries": len(extracted)},
    )


def _next_available_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for n in range(1, 10000):
        candidate = path.with_name(f"{stem}_{n}{suffix}")
        if not candidate.exists():
            return candidate
    return path.with_name(f"{stem}_{int(time.time())}{suffix}")


def _backup_dedupe(args: dict[str, Any]) -> dict[str, Any]:
    import hashlib
    root_raw = str(args.get("path") or args.get("root") or "").strip()
    if not root_raw:
        return _err("dedupe requires path")
    root = Path(root_raw).expanduser()
    if not root.exists() or not root.is_dir():
        return _err("path is not an existing directory", path=str(root))
    min_size = int(args.get("min_size_bytes", 1))
    by_hash: dict[str, list[str]] = {}
    scanned = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            if path.stat().st_size < min_size:
                continue
            scanned += 1
            digest = hashlib.sha256()
            with path.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    digest.update(chunk)
            by_hash.setdefault(digest.hexdigest(), []).append(str(path))
        except OSError:
            continue
    duplicates = {h: paths for h, paths in by_hash.items() if len(paths) > 1}
    duplicate_count = sum(len(paths) - 1 for paths in duplicates.values())
    return _ok(
        root=str(root), scanned=scanned, unique_hashes=len(by_hash),
        duplicate_groups=len(duplicates), duplicate_files=duplicate_count,
        groups=[{"sha256": h, "paths": paths} for h, paths in list(duplicates.items())[:50]],
    )


def _backup_verify(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    backup_path, resource = _backup_resolve(args, state)
    if not backup_path:
        return _err("backup not found")
    try:
        with zipfile.ZipFile(backup_path, "r") as archive:
            bad = archive.testzip()
            return _ok(backup=str(backup_path), size=backup_path.stat().st_size, entries=len(archive.infolist()), corrupted=bool(bad), bad_file=bad, verified=not bad)
    except (zipfile.BadZipFile, OSError) as exc:
        return _err(f"verify failed: {exc}", backup=str(backup_path))


def _create_presentation(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
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
        slide.shapes.title.text = str(first.get("title") or title)
        slide.placeholders[1].text = str(first.get("subtitle") or first.get("body") or "")
        for item in slides[1:]:
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            slide.shapes.title.text = str(item.get("title") or "Slide")
            body = slide.placeholders[1].text_frame
            body.clear()
            bullets = item.get("bullets") if isinstance(item.get("bullets"), list) else None
            if bullets:
                for bullet in bullets:
                    p = body.add_paragraph()
                    p.text = str(bullet)
                    p.level = 0
            else:
                body.text = str(item.get("body") or "")
    prs.save(path)
    resource = state.register_resource(
        "office_file",
        path.name,
        cleanup_tool="filesystem",
        cleanup_args={"action": "delete", "path": str(path)},
        metadata={"kind": "presentation", "path": str(path), "slides": len(prs.slides)},
    )
    return _ok(path=str(path.resolve()), kind="presentation", slides=len(prs.slides), resource=resource.get("resource"))


def _create_document(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
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
    doc.save(path)
    resource = state.register_resource("office_file", path.name, cleanup_tool="filesystem", cleanup_args={"action": "delete", "path": str(path)}, metadata={"kind": "document", "path": str(path)})
    return _ok(path=str(path.resolve()), kind="document", resource=resource.get("resource"))


def _create_spreadsheet(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    if importlib.util.find_spec("openpyxl") is None:
        return _err("openpyxl is not installed", status="needs_dependency", verified=False, install_hint="python -m pip install openpyxl")
    from openpyxl import Workbook

    title = str(args.get("title") or "Hoja").strip()
    path = _output_path(args, state, _safe_name(title), ".xlsx")
    wb = Workbook()
    ws = wb.active
    ws.title = "Datos"
    rows = args.get("rows") if isinstance(args.get("rows"), list) else []
    if not rows:
        rows = [["Campo", "Valor"], ["Titulo", title]]
    for row in rows:
        ws.append(row if isinstance(row, list) else [str(row)])
    wb.save(path)
    resource = state.register_resource("office_file", path.name, cleanup_tool="filesystem", cleanup_args={"action": "delete", "path": str(path)}, metadata={"kind": "spreadsheet", "path": str(path), "rows": len(rows)})
    return _ok(path=str(path.resolve()), kind="spreadsheet", rows=len(rows), resource=resource.get("resource"))


def _inspect_office_file(args: dict[str, Any]) -> dict[str, Any]:
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


def _existing_path(args: dict[str, Any]) -> Path | None:
    raw = str(args.get("path") or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.exists() else None


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


def _safe_name(text: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip())[:50].strip("_")
    return clean or "archivo"


def _audio_endpoints() -> list[dict[str, Any]]:
    script = "Get-PnpDevice -Class AudioEndpoint | Select-Object FriendlyName,Status,InstanceId | ConvertTo-Json -Depth 3"
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    return data if isinstance(data, list) else []


def _find_soundvolumeview() -> Path | None:
    raw = os.environ.get("GEMMA4_SOUNDVOLUMEVIEW")
    candidates = [Path(raw)] if raw else []
    candidates.extend([
        Path.cwd() / "tools" / "SoundVolumeView.exe",
        Path.home() / "Downloads" / "SoundVolumeView.exe",
        Path("C:/Tools/SoundVolumeView/SoundVolumeView.exe"),
        Path("C:/Program Files/SoundVolumeView/SoundVolumeView.exe"),
    ])
    found = shutil.which("SoundVolumeView.exe")
    if found:
        candidates.append(Path(found))
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _set_default_audio_device(args: dict[str, Any], state: AgentState, *, communications: bool) -> dict[str, Any]:
    name = str(args.get("name") or args.get("device") or "").strip()
    if not name:
        return _err("missing device name")
    helper = _find_soundvolumeview()
    if not helper:
        return _err(
            "setting default audio device needs SoundVolumeView or a custom WASAPI policy helper",
            requested=name,
            status="needs_dependency",
            verified=False,
            completion_status="needs_dependency",
            install_hint="Download SoundVolumeView.zip from NirSoft and set GEMMA4_SOUNDVOLUMEVIEW to its exe path.",
        )

    devices_before = _svv_list_devices()
    target = _svv_find_device(devices_before, name)
    if not target:
        return _err(
            "audio device not found",
            requested=name,
            available=[d.get("Name") or d.get("Device Name") for d in devices_before],
            status="needs_user",
            verified=False,
        )

    defaults_before = _svv_current_defaults(devices_before)
    rollback = _audio_rollback_steps(defaults_before)
    checkpoint = state.checkpoint(
        "audio default device change",
        rollback=rollback,
        metadata={
            "requested": name,
            "helper": str(helper),
            "communications": communications,
            "defaults_before": defaults_before,
            "device_before": target.get("Name") or target.get("Device Name"),
        },
    )

    # Role mapping (SoundVolumeView): 0=Console, 1=Multimedia, 2=Communications.
    roles = ["2"] if communications else ["0", "1"]
    role_names = {"0": "Console", "1": "Multimedia", "2": "Communications"}
    results = []
    for role in roles:
        proc = subprocess.run(
            [str(helper), "/SetDefault", name, role],
            capture_output=True, text=True, timeout=20,
        )
        results.append({
            "role": role,
            "role_name": role_names.get(role, role),
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        })

    devices_after = _svv_list_devices()
    defaults_after = _svv_current_defaults(devices_after)
    expected_roles = ["Communications"] if communications else ["Console", "Multimedia"]
    verified = _audio_verify_default(defaults_after, name, expected_roles)
    return _ok(
        requested=name,
        helper=str(helper),
        roles=roles,
        results=results,
        defaults_before=defaults_before,
        defaults_after=defaults_after,
        checkpoint=checkpoint.get("checkpoint"),
        verified=verified,
        status="done" if verified else "needs_verification",
        evidence={"defaults_before": defaults_before, "defaults_after": defaults_after, "exit_codes": [r["exit_code"] for r in results]},
    )


def _restore_audio_default(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    checkpoint_id = str(args.get("checkpoint_id") or args.get("snapshot") or "").strip()
    data = state._load()
    checkpoints = data.get("checkpoints", {})
    checkpoint = None
    if checkpoint_id and checkpoint_id in checkpoints:
        checkpoint = checkpoints[checkpoint_id]
    else:
        # latest audio snapshot
        for cp in reversed(list(checkpoints.values())):
            if "audio" in str(cp.get("label", "")).casefold():
                checkpoint = cp
                break
    if not checkpoint:
        return _err("no audio checkpoint available; create one with audio_device(action=snapshot) first")

    helper = _find_soundvolumeview()
    if not helper:
        return _err(
            "audio_device.restore requires SoundVolumeView",
            status="needs_dependency",
            verified=False,
            install_hint="Download SoundVolumeView.zip from NirSoft and set GEMMA4_SOUNDVOLUMEVIEW.",
        )
    defaults = checkpoint.get("metadata", {}).get("defaults") or {}
    if not defaults:
        return _err("checkpoint has no defaults to restore", checkpoint_id=checkpoint.get("id"))

    role_to_int = {"Console": "0", "Multimedia": "1", "Communications": "2"}
    results = []
    for role_name, device_name in defaults.items():
        role_int = role_to_int.get(role_name)
        if not role_int or not device_name:
            continue
        proc = subprocess.run(
            [str(helper), "/SetDefault", device_name, role_int],
            capture_output=True, text=True, timeout=20,
        )
        results.append({
            "role": role_name,
            "device": device_name,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        })
    devices_after = _svv_list_devices()
    defaults_after = _svv_current_defaults(devices_after)
    verified = all(defaults_after.get(role) == device for role, device in defaults.items() if device)
    return _ok(
        restored_from=checkpoint.get("id"),
        defaults_requested=defaults,
        defaults_after=defaults_after,
        results=results,
        verified=verified,
        status="done" if verified else "needs_verification",
    )


def _svv_list_devices() -> list[dict[str, Any]]:
    """Use SoundVolumeView /sjson to dump full device table."""
    helper = _find_soundvolumeview()
    if not helper:
        return []
    import tempfile
    fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="svv_")
    os.close(fd)
    try:
        proc = subprocess.run(
            [str(helper), "/sjson", tmp_path],
            capture_output=True, text=True, timeout=20,
        )
        if proc.returncode != 0:
            return []
        raw = Path(tmp_path).read_text(encoding="utf-16", errors="replace").lstrip("﻿").strip()
        if not raw:
            # SoundVolumeView sometimes writes utf-8; retry.
            raw = Path(tmp_path).read_text(encoding="utf-8", errors="replace").lstrip("﻿").strip()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _svv_current_defaults(devices: list[dict[str, Any]]) -> dict[str, str]:
    """Read per-role default from SoundVolumeView output.

    The /sjson dump has a 'Default' column with values like 'Render', 'Capture'
    or empty, plus a 'Default Multimedia', 'Default Communications' set in some
    versions. We prefer the columns 'Default' and 'Default Multimedia' /
    'Default Communications' when present, otherwise we fall back to the
    composite 'Default' string.
    """
    defaults: dict[str, str] = {}
    for dev in devices:
        if not isinstance(dev, dict):
            continue
        name = str(dev.get("Name") or dev.get("Device Name") or "").strip()
        if not name:
            continue
        direction = str(dev.get("Direction") or "").strip()
        if direction and direction.casefold() != "render":
            # Only render devices count for default playback roles here.
            # Recording defaults are mirrored under same columns; the role
            # name itself disambiguates downstream consumers.
            pass
        for role, column in (("Console", "Default"), ("Multimedia", "Default Multimedia"), ("Communications", "Default Communications")):
            value = str(dev.get(column) or "").strip().casefold()
            if value in {"render", "capture", "yes", "true", "1"}:
                # Only set if not already taken (first device wins for the role).
                defaults.setdefault(role, name)
    # Some SoundVolumeView builds collapse roles into a single "Default" column
    # carrying values like "Render;Multimedia". Handle that fallback.
    if not defaults:
        for dev in devices:
            if not isinstance(dev, dict):
                continue
            name = str(dev.get("Name") or dev.get("Device Name") or "").strip()
            raw = str(dev.get("Default") or "").strip().casefold()
            if not name or not raw:
                continue
            if "render" in raw or "capture" in raw:
                defaults.setdefault("Console", name)
                defaults.setdefault("Multimedia", name)
    return defaults


def _svv_find_device(devices: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
    q = query.casefold().strip()
    if not q:
        return None
    # Exact match first
    for dev in devices:
        for key in ("Name", "Device Name", "Item ID"):
            if str(dev.get(key) or "").casefold() == q:
                return dev
    # Substring match second
    for dev in devices:
        for key in ("Name", "Device Name", "Item ID"):
            if q in str(dev.get(key) or "").casefold():
                return dev
    return None


def _audio_rollback_steps(defaults: dict[str, str]) -> list[dict[str, Any]]:
    """Build a list of {tool, args} rollback steps for the checkpoint."""
    steps: list[dict[str, Any]] = []
    if not defaults:
        return steps
    # Group Console+Multimedia under a single set_default (covers roles 0,1).
    normal_device = defaults.get("Multimedia") or defaults.get("Console")
    if normal_device:
        steps.append({"tool": "audio_device", "args": {"action": "set_default", "name": normal_device}})
    comm_device = defaults.get("Communications")
    if comm_device and comm_device != normal_device:
        steps.append({"tool": "audio_device", "args": {"action": "set_default_communications", "name": comm_device}})
    return steps


def _audio_verify_default(defaults_after: dict[str, str], requested_name: str, expected_roles: list[str]) -> bool:
    """Return True if the requested device matches all expected roles."""
    if not defaults_after:
        return False
    q = requested_name.casefold().strip()
    for role in expected_roles:
        current = str(defaults_after.get(role) or "").casefold()
        if not current:
            return False
        if q not in current and current not in q:
            return False
    return True


def _show_message_box(title: str, text: str) -> dict[str, Any]:
    script = f"Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('{_ps_quote(text)}','{_ps_quote(title)}')"
    return _run_detached_powershell(script)


def _schedule_notification(args: dict[str, Any], state: AgentState, *, kind: str) -> dict[str, Any]:
    title = str(args.get("title") or kind.title()).strip()
    text = str(args.get("text") or args.get("message") or title).strip()
    due = _notification_due(args)
    task_name = f"Gemma4Agent_{kind}_{int(time.time())}"
    display_script = f"Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('{_ps_quote(text)}','{_ps_quote(title)}')"
    ps = f"""
$Action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -WindowStyle Hidden -Command "{display_script}"'
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date '{due.strftime('%Y-%m-%d %H:%M:%S')}')
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName '{_ps_quote(task_name)}' -TaskPath '\\Gemma4Agent\\' -Action $Action -Trigger $Trigger -Settings $Settings -Description '{_ps_quote(text)}' -Force | Out-Null
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return _err("failed to register scheduled notification", stderr=proc.stderr, exit_code=proc.returncode)
    resource = state.register_resource(
        kind,
        title,
        cleanup_tool="notification",
        cleanup_args={"action": "delete", "task_name": task_name},
        metadata={"text": text, "due": due.isoformat(), "task_name": task_name},
    )
    return _ok(kind=kind, title=title, text=text, due=due.isoformat(), task_name=task_name, resource=resource.get("resource"))


def _delete_notification(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    rid = str(args.get("id") or args.get("resource_id") or "").strip()
    task_name = str(args.get("task_name") or "").strip()
    resource = None
    if rid:
        resources = state._load().get("resources", {})
        resource = resources.get(rid)
        task_name = task_name or str((resource or {}).get("metadata", {}).get("task_name") or "")
    if task_name:
        ps = f"Unregister-ScheduledTask -TaskPath '\\Gemma4Agent\\' -TaskName '{_ps_quote(task_name)}' -Confirm:$false"
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=20)
        result = {"task_name": task_name, "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    else:
        result = {"task_name": None, "note": "no scheduled task name provided"}
    if rid:
        marked = state.mark_cleaned(rid, result)
        return _ok(deleted=True, task=result, resource=marked.get("resource"))
    return _ok(deleted=True, task=result)


def _enrich_notification_resource(resource: dict[str, Any]) -> dict[str, Any]:
    """Augment a notification resource with live Scheduled Task info."""
    metadata = resource.get("metadata") or {}
    task_name = str(metadata.get("task_name") or "").strip()
    if not task_name:
        return resource
    script = (
        f"$t = Get-ScheduledTask -TaskPath '\\Gemma4Agent\\' -TaskName '{_ps_quote(task_name)}' -ErrorAction SilentlyContinue; "
        f"if ($t) {{ "
        f"  $info = $t | Get-ScheduledTaskInfo; "
        f"  [PSCustomObject]@{{ "
        f"    State=$t.State.ToString(); "
        f"    LastRunTime=$info.LastRunTime; "
        f"    NextRunTime=$info.NextRunTime; "
        f"    LastTaskResult=$info.LastTaskResult; "
        f"    NumberOfMissedRuns=$info.NumberOfMissedRuns; "
        f"  }} | ConvertTo-Json -Depth 3 "
        f"}}"
    )
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
    if proc.returncode == 0 and proc.stdout.strip():
        try:
            data = json.loads(proc.stdout)
            if isinstance(data, dict):
                resource = dict(resource)
                resource["scheduled_task_info"] = data
        except json.JSONDecodeError:
            pass
    return resource


def _notification_history(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Return notifications (open + closed) with scheduled-task last run info."""
    kinds = {"notification", "timer", "alarm", "local_reminder"}
    requested = str(args.get("kind") or "").strip().casefold()
    if requested:
        kinds = {_kind_for_notification_action(requested + "_create" if not requested.endswith("_create") else requested)}
    limit = int(args.get("limit", 50))
    resources = state.list_resources(include_closed=True).get("resources", [])
    items = [r for r in resources if r.get("kind") in kinds]
    items.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
    items = items[:limit]
    enriched = [_enrich_notification_resource(item) for item in items]
    return _ok(items=enriched, count=len(enriched), kinds=sorted(kinds))


def _update_notification(args: dict[str, Any], state: AgentState, *, kind: str) -> dict[str, Any]:
    """Cancel and re-register a Scheduled Task with updated trigger/text."""
    rid = str(args.get("id") or args.get("resource_id") or "").strip()
    name_query = str(args.get("name") or args.get("title") or "").strip().casefold()
    resources = state._load().get("resources", {})
    resource = None
    if rid and rid in resources:
        resource = resources[rid]
    elif name_query:
        for res in resources.values():
            if res.get("kind") == kind and name_query in str(res.get("label", "")).casefold():
                resource = res
                break
    if not resource:
        return _err("notification not found", kind=kind, status="needs_user")

    old_task_name = str((resource.get("metadata") or {}).get("task_name") or "").strip()
    # Build merged args from old metadata + updates.
    metadata = dict(resource.get("metadata") or {})
    merged_args = {
        "title": args.get("title") or resource.get("label") or metadata.get("text"),
        "text": args.get("text") or args.get("message") or metadata.get("text"),
        "due": args.get("due"),
        "seconds": args.get("seconds"),
        "minutes": args.get("minutes"),
        "time": args.get("time"),
    }
    # Only override "due" if any of the time keys is provided; else reuse old due.
    if not any(args.get(k) is not None for k in ("due", "seconds", "minutes", "time")):
        merged_args["due"] = metadata.get("due")

    # Unregister the old task (if any).
    cleanup = None
    if old_task_name:
        cleanup = _delete_notification({"id": resource.get("id"), "task_name": old_task_name}, state)
    new = _schedule_notification(merged_args, state, kind=kind)
    if not new.get("ok"):
        return new
    return _ok(updated=True, previous_task=old_task_name, previous_id=resource.get("id"), cleanup=cleanup, new=new)


def _kind_for_notification_action(action: str) -> str:
    if action.startswith("timer"):
        return "timer"
    if action.startswith("alarm"):
        return "alarm"
    if action.startswith("reminder"):
        return "local_reminder"
    return "notification"


def _notification_due(args: dict[str, Any]) -> datetime:
    seconds = args.get("seconds")
    minutes = args.get("minutes")
    if seconds is not None:
        return datetime.now() + timedelta(seconds=max(1, int(seconds)))
    if minutes is not None:
        return datetime.now() + timedelta(minutes=max(1, int(minutes)))
    raw = str(args.get("due") or args.get("time") or "").strip()
    if raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
        except ValueError:
            pass
    return datetime.now() + timedelta(minutes=5)


def _find_routine(args: dict[str, Any], state: AgentState) -> dict[str, Any] | None:
    rid = str(args.get("id") or args.get("resource_id") or "").strip()
    name = str(args.get("name") or args.get("label") or "").strip().casefold()
    resources = state._load().get("resources", {})
    if rid and rid in resources:
        return resources[rid]
    for resource in resources.values():
        if resource.get("kind") == "routine" and name and str(resource.get("label") or "").casefold() == name:
            return resource
    return None


def _update_resource_metadata(state: AgentState, resource_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    data = state._load()
    resource = data.get("resources", {}).get(resource_id)
    if not resource:
        return _err("resource not found", resource_id=resource_id)
    metadata = resource.setdefault("metadata", {})
    metadata.update(updates)
    state._save(data)
    return _ok(resource=resource)


def _resources_by_kind(state: AgentState, kinds: str | list[str], include_closed: bool = False) -> list[dict[str, Any]]:
    wanted = {kinds} if isinstance(kinds, str) else set(kinds)
    resources = state._load().get("resources", {}).values()
    out = []
    for resource in resources:
        if resource.get("kind") not in wanted:
            continue
        if not include_closed and resource.get("status") != "open":
            continue
        out.append(resource)
    return out


def _find_resource(args: dict[str, Any], state: AgentState, kinds: str | list[str]) -> dict[str, Any] | None:
    rid = str(args.get("id") or args.get("resource_id") or "").strip()
    query = str(args.get("query") or args.get("name") or args.get("title") or "").strip().casefold()
    resources = state._load().get("resources", {})
    wanted = {kinds} if isinstance(kinds, str) else set(kinds)
    if rid and rid in resources and resources[rid].get("kind") in wanted:
        return resources[rid]
    for resource in resources.values():
        if resource.get("kind") not in wanted:
            continue
        if query and query in json.dumps(resource, ensure_ascii=False).casefold():
            return resource
    return None


def _dependency_catalog() -> dict[str, dict[str, Any]]:
    items = [
        _module_dep("playwright", "Playwright", "python -m pip install playwright && python -m playwright install chromium"),
        _module_dep("pptx", "python-pptx", "python -m pip install python-pptx"),
        _module_dep("docx", "python-docx", "python -m pip install python-docx"),
        _module_dep("openpyxl", "openpyxl", "python -m pip install openpyxl"),
        _module_dep("pyautogui", "pyautogui", "python -m pip install pyautogui"),
        _module_dep("pycaw", "pycaw", "python -m pip install pycaw comtypes"),
        _binary_dep("tesseract", "Tesseract OCR", "winget install UB-Mannheim.TesseractOCR"),
        _binary_dep("ffmpeg", "FFmpeg", "winget install Gyan.FFmpeg"),
        _binary_dep("git", "Git", "winget install Git.Git"),
        _binary_dep("winget", "winget", "Install App Installer from Microsoft Store"),
        _binary_dep("soffice", "LibreOffice", "winget install TheDocumentFoundation.LibreOffice"),
        {
            "name": "SoundVolumeView",
            "key": "soundvolumeview",
            "type": "binary",
            "available": _find_soundvolumeview() is not None,
            "path": str(_find_soundvolumeview()) if _find_soundvolumeview() else None,
            "install_hint": "Download SoundVolumeView from NirSoft and set GEMMA4_SOUNDVOLUMEVIEW.",
        },
    ]
    return {item["key"]: item for item in items}


def _module_dep(module: str, name: str, hint: str) -> dict[str, Any]:
    available = importlib.util.find_spec(module) is not None
    return {"name": name, "key": module, "type": "python_module", "available": available, "install_hint": hint}


def _binary_dep(binary: str, name: str, hint: str) -> dict[str, Any]:
    path = shutil.which(binary) or shutil.which(f"{binary}.exe")
    return {"name": name, "key": binary, "type": "binary", "available": bool(path), "path": path, "install_hint": hint}


def _calendar_export_path(args: dict[str, Any], state: AgentState) -> Path:
    raw = str(args.get("path") or "").strip()
    if raw:
        path = Path(raw).expanduser()
    else:
        path = state.path.parent / "generated" / f"calendar_{time.strftime('%Y%m%d_%H%M%S')}.ics"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _events_to_ics(events: list[dict[str, Any]]) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Gemma4Agent//Local Calendar//ES"]
    for event in events:
        meta = event.get("metadata", {})
        uid = event.get("id", f"evt_{time.time()}")
        title = str(meta.get("title") or event.get("label") or "Evento")
        start = _ics_time(str(meta.get("start") or datetime.now().isoformat()))
        end = _ics_time(str(meta.get("end") or meta.get("start") or datetime.now().isoformat()))
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}@gemma4-agent",
            f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART:{start}",
            f"DTEND:{end}",
            f"SUMMARY:{_ics_escape(title)}",
        ])
        if meta.get("location"):
            lines.append(f"LOCATION:{_ics_escape(str(meta['location']))}")
        if meta.get("notes"):
            lines.append(f"DESCRIPTION:{_ics_escape(str(meta['notes']))}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _ics_time(raw: str) -> str:
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        value = datetime.now()
    return value.strftime("%Y%m%dT%H%M%S")


def _ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def _powershell_json(script: str, field: str) -> dict[str, Any]:
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return _err("powershell command failed", exit_code=proc.returncode, stderr=proc.stderr)
    raw = proc.stdout.strip()
    if not raw:
        data: Any = []
    else:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return _err("failed to parse PowerShell JSON", stdout=raw[:1000])
    if isinstance(data, dict) and field.endswith("s"):
        data = [data]
    return _ok(**{field: data, "count": len(data) if isinstance(data, list) else (1 if data else 0)})


def _run_detached_powershell(script: str) -> dict[str, Any]:
    proc = subprocess.Popen(
        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return {"pid": proc.pid}


def _ps_quote(text: str) -> str:
    return text.replace("'", "''")
