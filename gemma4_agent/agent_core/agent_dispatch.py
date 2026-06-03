"""Tool-call execution helpers extracted from :mod:`gemma4_agent.agent`.

The two `_execute_calls_*` methods on Gemma4Agent
are nearly entirely about iterating a prepared-call list, dispatching
through `tools.execute`, and writing the result back into each
prep dict. They depend on `self.tools` and `self.trace` but not on
the rest of the agent's state, so they translate cleanly to pure
functions.

The methods on Gemma4Agent are now 5-line wrappers.
"""
from __future__ import annotations

import os
from typing import Any, Callable


# Tools whose handlers are bound to a specific thread (Playwright sync
# API can't be invoked from a worker thread because the runtime tracks
# the thread that called `sync_playwright().start()`). These must run
# inline on the dispatcher thread regardless of the parallel flag.
_THREAD_AFFINE_TOOLS = frozenset({"browser_real", "media", "browser"})


def _tool_timeout_seconds() -> float:
    try:
        return float(os.environ.get("GEMMA4_TOOL_TIMEOUT_S") or 60)
    except (TypeError, ValueError):
        return 60.0


def execute_calls_sequential(
    prepared: list[dict[str, Any]],
    *,
    tools_registry: Any,
    trace: Any,
    run_with_timeout: Callable[..., dict[str, Any]],
    progress_emit: Callable[[str, Any], None],
    base_count: int,
    turn_id: str = "",
) -> None:
    """Run prepared tool calls one by one, populating prep['result'].

    Mirrors the original single-thread behaviour: emit tool_start before
    each execute, short-circuit malformed-args preps with a synthetic
    result. Phase-3 in the caller handles tool_end / history append.
    """
    for index, prep in enumerate(prepared):
        name = prep["name"]
        args = prep["args"]
        parse_error = prep["parse_error"]
        if parse_error:
            prep["result"] = {
                "ok": False,
                "status": "failed",
                "verified": False,
                "error": (
                    f"tool args parse error: {parse_error}. Re-emit the call "
                    "with valid JSON for the 'arguments' field."
                ),
                "tool": name,
                "evidence": "malformed_json_args",
            }
            continue
        # Hotfix I 2026-05-17: the safety hook may have pre-blocked
        # this call (e.g. checkout-pattern URL or paid action with
        # safety_enabled=True). Honor the synthetic result and skip
        # execution.
        pre_result = prep.get("_pre_dispatch_result")
        if isinstance(pre_result, dict):
            prep["result"] = pre_result
            continue
        progress_emit("tool_start", {"name": name, "args": args, "index": base_count + index + 1})
        if name in _THREAD_AFFINE_TOOLS:
            try:
                prep["result"] = tools_registry.execute(name, args)
            except Exception as exc:
                prep["result"] = {
                    "ok": False, "status": "failed", "verified": False,
                    "error": f"{type(exc).__name__}: {exc}", "tool": name,
                }
            continue
        tool_timeout = _tool_timeout_seconds()
        wrapped = run_with_timeout(
            tools_registry.execute, name, args, timeout_s=tool_timeout,
        )
        if wrapped.get("_timed_out"):
            if turn_id:
                try:
                    trace.event(
                        turn_id, "tool_hard_timeout",
                        name=name, timeout_s=tool_timeout,
                    )
                except Exception:
                    pass
            prep["result"] = {
                "ok": False,
                "status": "failed",
                "verified": False,
                "error": (
                    f"tool {name!r} exceeded hard timeout of {tool_timeout:.0f}s. "
                    "Possible causes: Playwright lost browser, network hang, "
                    "or an infinite loop. The tool was abandoned."
                ),
                "tool": name,
                "evidence": "tool_hard_timeout",
            }
        elif wrapped.get("_error"):
            prep["result"] = {
                "ok": False, "status": "failed", "verified": False,
                "error": wrapped["_error"], "tool": name,
            }
        else:
            prep["result"] = wrapped["result"]


def execute_calls_parallel(
    prepared: list[dict[str, Any]],
    *,
    tools_registry: Any,
    trace: Any,
    progress_emit: Callable[[str, Any], None],
    base_count: int,
    turn_id: str = "",
) -> None:
    """Run prepared tool calls concurrently with a small thread pool.

    max_workers=4. Parse-error preps get a synthetic result without a
    thread submission. Order is preserved because phase-3 iterates
    `prepared` in original order; we just fill prep['result'] from each
    completed future.
    """
    import concurrent.futures

    valid_preps: list[tuple[int, dict[str, Any]]] = []
    for index, prep in enumerate(prepared):
        if prep["parse_error"]:
            prep["result"] = {
                "ok": False,
                "status": "failed",
                "verified": False,
                "error": (
                    f"tool args parse error: {prep['parse_error']}. Re-emit "
                    "the call with valid JSON for the 'arguments' field."
                ),
                "tool": prep["name"],
                "evidence": "malformed_json_args",
            }
            continue
        # Hotfix I 2026-05-17: safety hook pre-block (see
        # sequential executor for the same gate).
        pre_result = prep.get("_pre_dispatch_result")
        if isinstance(pre_result, dict):
            prep["result"] = pre_result
            continue
        valid_preps.append((index, prep))
    if not valid_preps:
        return
    tool_timeout = _tool_timeout_seconds()
    affine_preps = [(i, p) for i, p in valid_preps
                     if p["name"] in _THREAD_AFFINE_TOOLS]
    pool_preps = [(i, p) for i, p in valid_preps
                   if p["name"] not in _THREAD_AFFINE_TOOLS]
    for index, prep in affine_preps:
        progress_emit("tool_start", {
            "name": prep["name"], "args": prep["args"], "index": base_count + index + 1,
        })
        try:
            prep["result"] = tools_registry.execute(prep["name"], prep["args"])
        except Exception as exc:
            prep["result"] = {
                "ok": False, "status": "failed", "verified": False,
                "error": f"{type(exc).__name__}: {exc}",
                "tool": prep["name"],
            }
    if not pool_preps:
        return
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(4, len(pool_preps)),
        thread_name_prefix="gemma4_par_tool",
    ) as pool:
        future_to_prep: dict[Any, dict[str, Any]] = {}
        for index, prep in pool_preps:
            progress_emit("tool_start", {
                "name": prep["name"], "args": prep["args"], "index": base_count + index + 1,
            })
            future = pool.submit(tools_registry.execute, prep["name"], prep["args"])
            future_to_prep[future] = prep
        for future in concurrent.futures.as_completed(future_to_prep, timeout=tool_timeout * 2):
            prep = future_to_prep[future]
            try:
                prep["result"] = future.result(timeout=tool_timeout)
            except concurrent.futures.TimeoutError:
                if turn_id:
                    try:
                        trace.event(
                            turn_id, "tool_hard_timeout",
                            name=prep["name"], timeout_s=tool_timeout,
                        )
                    except Exception:
                        pass
                prep["result"] = {
                    "ok": False, "status": "failed", "verified": False,
                    "error": (f"tool {prep['name']!r} exceeded hard timeout "
                              f"of {tool_timeout:.0f}s and was abandoned."),
                    "tool": prep["name"],
                    "evidence": "tool_hard_timeout",
                }
                continue
            except Exception as exc:
                prep["result"] = {
                    "ok": False,
                    "status": "failed",
                    "verified": False,
                    "error": f"tool raised in parallel exec: {exc}",
                    "tool": prep["name"],
                    "evidence": "parallel_exception",
                }


__all__ = ["execute_calls_sequential", "execute_calls_parallel"]
