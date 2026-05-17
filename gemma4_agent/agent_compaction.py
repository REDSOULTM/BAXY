"""History-compaction helpers extracted from :mod:`gemma4_agent.agent`.

Sprint 6.3 split: the eight pure helpers below (plus the three
character-budget constants they use) live here so the
Gemma4Agent's compaction methods read like orchestration on top of
named primitives instead of inline blobs.

The methods themselves (`_compact_completed_history`,
`_compact_active_history_for_retry`, `_extract_facts`,
`_summarize_history_block`) still live on Gemma4Agent because they
mutate `self.history`, call the LLM via `self.client`, and emit
trace events through `self.trace`. Splitting those would require
threading too much state through, with risk that the existing 8-test
context_overflow net does not cover.
"""
from __future__ import annotations

import json
from typing import Any


# Char budgets the helpers respect when truncating message content.
LIVE_TEXT_LIMIT = 10000
HISTORY_TEXT_LIMIT = 3500
TOOL_RESULT_LIMIT = 3500


def compute_context_budget(context_size: int) -> dict[str, int]:
    """Proportional context budget that adapts to the model size.

    Reserves ~30% of the context window for the *next* turn (system prompt,
    new user input, fresh tool results, and the assistant reply). The other
    ~70% is available for retained history. From that 70% we derive:

      - soft_cap_messages: post cheap-pass truncation (drop tool roles).
      - hard_cap_messages: final fallback truncation when summarization is
        off, fails, or is in cooldown.
      - keep_tail_messages: how many last messages to keep verbatim around
        the LLM-generated summary.
      - summarize_threshold_chars: when total history exceeds this many
        chars we trigger a Stage-2 summarization.

    The formulas scale roughly linearly with `context_size` but stay bounded
    so very small (1K) or very large (1M) models still produce sensible
    numbers. Char-to-token ratio is conservative (~3 chars/token).
    """
    ctx = max(1024, int(context_size or 16384))
    history_tokens = int(ctx * 0.70)
    history_chars = history_tokens * 3
    # 1 conversational round (user+assistant) averages ~300-1200 chars after
    # the cheap-pass. Use a soft anchor of 500 chars/message for budgeting.
    avg_msg_chars = 500
    soft_cap = max(10, min(history_chars // avg_msg_chars, 200))
    hard_cap = max(6, soft_cap // 2)
    keep_tail = max(4, min(soft_cap // 5, 30))
    threshold = int(history_chars * 0.75)
    return {
        "context_size": ctx,
        "history_tokens": history_tokens,
        "history_chars": history_chars,
        "soft_cap_messages": soft_cap,
        "hard_cap_messages": hard_cap,
        "keep_tail_messages": keep_tail,
        "summarize_threshold_chars": threshold,
    }


def message_text_estimate(message: dict[str, Any]) -> str:
    """Return a flat string representation of a chat message for token budgeting."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    chunks.append(str(item.get("text") or ""))
                elif item.get("type") == "image_url":
                    chunks.append("[image]")
                elif item.get("type") == "input_audio":
                    chunks.append("[audio]")
        return " ".join(chunks)
    if content is None:
        return ""
    return str(content)


def middle_ellipsis(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    keep_start = max(0, limit // 2)
    keep_end = max(0, limit - keep_start - 80)
    return (
        text[:keep_start].rstrip()
        + f"\n...[omitted {len(text) - keep_start - keep_end} chars to keep context under limit]...\n"
        + text[-keep_end:].lstrip()
    )


def compact_live_content(content: str | list[dict[str, Any]]) -> str | list[dict[str, Any]]:
    if isinstance(content, str):
        return middle_ellipsis(content, LIVE_TEXT_LIMIT)
    out: list[dict[str, Any]] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text":
            out.append({"type": "text", "text": middle_ellipsis(str(item.get("text") or ""), LIVE_TEXT_LIMIT)})
        else:
            out.append(item)
    return out


def compact_history_content(content: Any) -> str:
    if isinstance(content, str):
        return middle_ellipsis(content, HISTORY_TEXT_LIMIT)
    if isinstance(content, list):
        parts: list[str] = []
        omitted_media = 0
        for item in content:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("type") or "")
            if kind == "text":
                parts.append(str(item.get("text") or ""))
            elif kind in {"image_url", "input_audio"}:
                omitted_media += 1
        suffix = f"\n[{omitted_media} multimodal item(s) omitted from history]" if omitted_media else ""
        return middle_ellipsis("\n".join(parts).strip() + suffix, HISTORY_TEXT_LIMIT)
    return middle_ellipsis(str(content or ""), HISTORY_TEXT_LIMIT)


def compact_json(value: Any, *, max_items: int, max_string: int, depth: int = 0) -> Any:
    if depth > 5:
        return middle_ellipsis(str(value), max_string)
    if isinstance(value, str):
        return middle_ellipsis(value, max_string)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, list):
        list_out: list[Any] = [compact_json(item, max_items=max_items, max_string=max_string, depth=depth + 1) for item in value[:max_items]]
        if len(value) > max_items:
            list_out.append({"_omitted": len(value) - max_items})
        return list_out
    if isinstance(value, dict):
        limit = 80 if depth == 0 else max_items
        items = list(value.items())
        dict_out: dict[str, Any] = {}
        for key, item in items[:limit]:
            dict_out[str(key)] = compact_json(item, max_items=max_items, max_string=max_string, depth=depth + 1)
        if len(items) > limit:
            dict_out["_omitted_keys"] = len(items) - limit
        return dict_out
    return middle_ellipsis(str(value), max_string)


def json_len(value: Any) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, default=str))
    except TypeError:
        return len(str(value))


def compact_tool_result(name: str, args: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    compacted = compact_json(result, max_items=5, max_string=700)
    if json_len(compacted) <= TOOL_RESULT_LIMIT:
        return compacted if isinstance(compacted, dict) else {"value": compacted}

    core_keys = (
        "ok",
        "status",
        "verified",
        "completion_status",
        "error",
        "tool",
        "action",
        "evidence",
        "path",
        "url",
        "image_path",
        "title",
        "selected_title",
        "level",
        "query",
        "matched_game",
        "local_match_verified",
        "visual_verified",
        "playback_verified",
        "content_verified",
        "resource",
        "checkpoint",
    )
    core: dict[str, Any] = {
        "tool": name,
        "args": compact_json(args, max_items=5, max_string=300),
        "context_compacted": True,
    }
    for key in core_keys:
        if key in result:
            core[key] = compact_json(result[key], max_items=4, max_string=500)
    for key, value in result.items():
        if isinstance(value, list):
            core[f"{key}_count"] = len(value)
            core[key] = compact_json(value[:3], max_items=3, max_string=350)
        elif isinstance(value, dict) and key not in core:
            core[f"{key}_keys"] = list(value.keys())[:12]
    return compact_json(core, max_items=6, max_string=600)


# Locator keys whose values must survive history compaction. These are
# the same fields compact_tool_result preserves verbatim under core_keys.
# Kept here (not in config) because they're closely tied to the prompt
# rule in core.md (EVIDENCE CITATION) and we want them to drift together.
_LOCATOR_KEYS: tuple[str, ...] = ("path", "url", "selected_title", "image_path", "deeplink")

# Compact "tabular evidence" pre-pass — hotfix D 2026-05-17.
# The scalar-locator breadcrumb above (path/url/...) survives turns but
# small tabular results (e.g. disks list from system.disk) do not. When
# we see such tables in a tool_result, summarize each row as
# "k=v k=v ..." with a small char budget per row. Bug repro:
#   user "cuánto espacio en C" -> tool returned disks list (C,D,E,F,...)
#   reply "74 GB en C" — only C was verbalized
#   user "y en F?" -> next turn had no F data -> LLM hallucinated 350 GB.
_TABULAR_KEYS: tuple[str, ...] = (
    "disks", "processes", "devices", "results", "items", "windows", "tabs",
)
_TABULAR_MAX_ROWS = 20
_TABULAR_MAX_ROW_CHARS = 200
_TABULAR_MAX_TOTAL_CHARS = 1200
# Overall cap on the breadcrumb suffix — must fit locators + at most
# one tabular blob comfortably. Raised from 600 -> 1800 in hotfix D.
_BREADCRUMB_MAX_CHARS = 1800


def stitch_breadcrumbs(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stitch locator-key breadcrumbs onto assistant replies pre-drop.

    Hotfix C 2026-05-17 (scalar locators) + hotfix D 2026-05-17 (tabular
    evidence). Before `_compact_completed_history` drops the role="tool"
    messages, harvest:
      - scalar locator keys (`path`, `url`, `selected_title`,
        `image_path`, `deeplink`),
      - tabular keys (`disks`, `processes`, `devices`, `results`,
        `items`, `windows`, `tabs`) — each rendered as a compact
        ``k=v k=v ; ...`` blob with bounded per-row and total chars.

    The harvested values are appended as a single
    ``\\n[breadcrumb: key=value ...]`` suffix to the assistant reply of
    the same turn. The reply is the only thing that survives the drop,
    so without this the data "vanishes" between turns.

    Idempotent: if the assistant content already contains a locator
    value verbatim, that value is skipped. Bounded: suffix capped at
    ~1800 chars so it can't blow up the prompt.

    Returns a new history list (does NOT mutate the input dict
    structure aside from the assistant ``content`` field of the turn
    that needs stitching). Safe to call when there are no tool
    messages — falls through as a no-op.
    """
    out: list[dict[str, Any]] = list(history)
    pending: list[tuple[str, str]] = []
    for idx, msg in enumerate(out):
        role = str(msg.get("role") or "")
        if role == "tool":
            raw = msg.get("content")
            parsed: Any = None
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = None
            elif isinstance(raw, dict):
                parsed = raw
            if isinstance(parsed, dict):
                # Scalar locator harvest.
                for k in _LOCATOR_KEYS:
                    v = parsed.get(k)
                    if isinstance(v, str) and v.strip() and len(v) <= 400:
                        pending.append((k, v.strip()))
                # Tabular harvest (hotfix D). Bound each row, each table,
                # and the total — small tables only.
                for tk in _TABULAR_KEYS:
                    rows = parsed.get(tk)
                    if not isinstance(rows, list) or not rows:
                        continue
                    summary_rows: list[str] = []
                    for row in rows[:_TABULAR_MAX_ROWS]:
                        if not isinstance(row, dict):
                            continue
                        parts: list[str] = []
                        for k, v in list(row.items())[:6]:
                            if isinstance(v, (str, int, float, bool)):
                                parts.append(f"{k}={v}")
                        rendered = " ".join(parts)
                        if len(rendered) > _TABULAR_MAX_ROW_CHARS:
                            rendered = rendered[:_TABULAR_MAX_ROW_CHARS] + "..."
                        if rendered:
                            summary_rows.append(rendered)
                    if summary_rows:
                        joined = " ; ".join(summary_rows)
                        if len(joined) > _TABULAR_MAX_TOTAL_CHARS:
                            joined = joined[:_TABULAR_MAX_TOTAL_CHARS] + "..."
                        pending.append((tk, joined))
            continue
        if role == "assistant" and not msg.get("tool_calls") and pending:
            existing = msg.get("content")
            if isinstance(existing, list):
                existing_text = "".join(
                    str(it.get("text", "")) for it in existing
                    if isinstance(it, dict)
                )
            else:
                existing_text = "" if existing is None else str(existing)
            missing = [(k, v) for k, v in pending if v not in existing_text]
            if missing:
                trail = " ".join(f"{k}={v}" for k, v in missing)
                breadcrumb = f"\n[breadcrumb: {trail}]"
                if len(breadcrumb) > _BREADCRUMB_MAX_CHARS:
                    breadcrumb = breadcrumb[:_BREADCRUMB_MAX_CHARS] + "...]"
                new_msg = dict(msg)
                new_msg["content"] = existing_text + breadcrumb
                out[idx] = new_msg
            pending = []
    return out


__all__ = [
    "LIVE_TEXT_LIMIT",
    "HISTORY_TEXT_LIMIT",
    "TOOL_RESULT_LIMIT",
    "compute_context_budget",
    "message_text_estimate",
    "middle_ellipsis",
    "compact_live_content",
    "compact_history_content",
    "compact_json",
    "json_len",
    "compact_tool_result",
    "stitch_breadcrumbs",
]
