"""Tool-selection validator using an in-band <intent>{...}</intent> tag.

When the selected_tool_subset contains two tools that are easy to confuse
(audio.media_stop vs window.close, etc.), the LLM is asked to declare its
intent first. If the declared intent and the chosen (tool, action) form a
known mis-pairing, the dispatcher rejects the call and retries once with
a corrective hint.

The "needs_intent_tag" set is intentionally tiny — only entries observed
in real bug logs go in. Adding pairs preemptively risks creating new
false rejects.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable

# (declared_intent_type, chosen_tool_name, chosen_action) -> reject reason.
# Keep this dict honest: each entry must be backed by a real failing case.
CROSS_REJECT_PAIRS: dict[tuple[str, str, str], str] = {
    ("close", "audio", "media_stop"):
        "Intent is to close a window/tab/app — audio.media_stop only mutes playback, it does not close anything.",
    ("close", "audio", "media_play_pause"):
        "Intent is to close a window/tab/app — audio.media_play_pause only toggles playback, it does not close anything.",
    ("stop_media", "window", "close"):
        "Intent is to stop media playback — window.close removes the player from screen entirely. Use audio.media_stop or audio.media_play_pause.",
    ("stop_media", "app", "close"):
        "Intent is to stop media playback — app.close kills the host app. Use audio.media_stop or audio.media_play_pause.",
    ("set_volume", "audio", "media_stop"):
        "Intent is to change volume — media_stop sends a global media key, not a volume level.",
    ("set_volume", "audio", "media_play_pause"):
        "Intent is to change volume — media_play_pause sends a global media key, not a volume level.",
}

# Subset pairs that, when both present in a turn, trigger the intent-tag
# instruction. Ordered alphabetically inside the tuple.
_AMBIGUOUS_SUBSETS: tuple[tuple[str, str], ...] = (
    ("audio", "window"),
    ("audio", "browser_real"),
    ("audio", "app"),
    ("audio", "media"),
)


def needs_intent_tag(selected_tool_names: Iterable[str]) -> bool:
    names = set(selected_tool_names)
    return any(a in names and b in names for a, b in _AMBIGUOUS_SUBSETS)


INTENT_TAG_INSTRUCTION = (
    "\n\n# Intent declaration (required this turn)\n"
    "Before your tool_call, emit ONE line:\n"
    "  <intent>{\"intent_type\":\"<verb>\",\"target\":\"<noun or empty>\"}</intent>\n"
    "Where intent_type is a short verb like 'close', 'stop_media', 'set_volume', "
    "'open', 'play', 'send_message', 'cancel'. The tag will be stripped before "
    "the user sees the reply; it is only used by the validator to confirm the "
    "tool you pick matches what you said you wanted to do."
)


_INTENT_TAG_RE = re.compile(r"<intent>\s*(\{.*?\})\s*</intent>", re.DOTALL)


@dataclass
class IntentTag:
    intent_type: str
    target: str
    raw: str  # the matched substring, including the tags


def extract_intent_tag(content: str) -> IntentTag | None:
    if not content:
        return None
    match = _INTENT_TAG_RE.search(content)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    intent_type = str(payload.get("intent_type") or "").strip().lower()
    target = str(payload.get("target") or "").strip()
    if not intent_type:
        return None
    return IntentTag(intent_type=intent_type, target=target, raw=match.group(0))


def strip_intent_tag(content: str) -> str:
    if not content:
        return content
    return _INTENT_TAG_RE.sub("", content).strip()


@dataclass
class ValidationResult:
    rejected: bool
    reason: str = ""
    declared_intent: str = ""
    chosen_tool: str = ""
    chosen_action: str = ""


def validate_call(
    intent: IntentTag | None,
    tool_name: str,
    args: dict,
) -> ValidationResult:
    """Return ValidationResult(rejected=True, ...) when the chosen
    (tool, action) is on the reject list for the declared intent."""
    if intent is None:
        return ValidationResult(rejected=False)
    action = str(args.get("action") or "").strip().lower()
    key = (intent.intent_type, tool_name, action)
    reason = CROSS_REJECT_PAIRS.get(key)
    if reason is None:
        return ValidationResult(
            rejected=False,
            declared_intent=intent.intent_type,
            chosen_tool=tool_name,
            chosen_action=action,
        )
    return ValidationResult(
        rejected=True,
        reason=reason,
        declared_intent=intent.intent_type,
        chosen_tool=tool_name,
        chosen_action=action,
    )


def corrective_message(result: ValidationResult) -> str:
    return (
        f"[validator] You declared intent_type='{result.declared_intent}' but "
        f"chose {result.chosen_tool}({result.chosen_action}). That pairing is "
        f"rejected: {result.reason} Pick a different tool from the same subset. "
        f"Emit a new <intent>{{...}}</intent> tag and one tool_call."
    )
