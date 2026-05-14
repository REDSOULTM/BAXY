"""Run a tool on a worker thread without freezing the UI.

`run_tool_async(tool_exec, name, args, on_done)` schedules the call on a
QThreadPool and invokes `on_done(result_dict)` on the Qt event loop when it
completes (or on exception). Use this from any modal dialog that wants to
trigger a tool — the dialog stays responsive while the call runs.

For very short tools (state/list/status), calling synchronously is still fine;
this helper is only worth it for tools that may take seconds (web, knowledge
search with rerank cold-load, browser_real, routine.run_now).
"""
from __future__ import annotations

from typing import Any, Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot


ToolExecFn = Callable[[str, dict[str, Any]], dict[str, Any]]
ResultCallback = Callable[[dict[str, Any]], None]


class _Signals(QObject):
    finished = pyqtSignal(dict)


class _Worker(QRunnable):
    def __init__(self, tool_exec: ToolExecFn, name: str, args: dict[str, Any]) -> None:
        super().__init__()
        self.tool_exec = tool_exec
        self.name = name
        self.args = dict(args)
        self.signals = _Signals()

    @pyqtSlot()
    def run(self) -> None:
        try:
            result = self.tool_exec(self.name, self.args)
        except Exception as exc:
            result = {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "tool": self.name,
                "evidence": "ui_async_exception",
            }
        try:
            self.signals.finished.emit(result if isinstance(result, dict) else {"ok": False, "raw": str(result)})
        except RuntimeError:
            # Receiver was deleted before we finished — silently drop.
            pass


def run_tool_async(
    tool_exec: ToolExecFn,
    name: str,
    args: dict[str, Any],
    on_done: ResultCallback,
) -> None:
    """Submit a tool call to the global QThreadPool. `on_done` fires on UI thread."""
    worker = _Worker(tool_exec, name, args)
    worker.signals.finished.connect(on_done)
    pool = QThreadPool.globalInstance()
    if pool is None:
        # Should never happen once a QApplication exists; fall back to inline.
        try:
            on_done(tool_exec(name, dict(args)))
        except Exception as exc:
            on_done({"ok": False, "error": str(exc), "tool": name})
        return
    pool.start(worker)
