"""Agent loop: Gemma 4 decides, tools execute, results are fed back."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .config import AgentConfig
from .evaluator import evaluate_mission
from .llm_client import LLMClient
from .memory import MemoryStore
from .modes import AgentMode, choose_mode
from .multimodal import image_part, user_content
from .planner import MissionPlan, plan_mission, select_tool_names
from .reasoning import sanitize_assistant_message, sanitize_text
from .state import AgentState
from .tools import ToolRegistry
from .tracing import TraceLogger, summarize_content


ProgressCallback = Callable[[str, dict[str, Any]], None]


SYSTEM_PROMPT = """You are a local Windows agent powered by Gemma 4.

Speak Spanish to the user by default. Be brief, concrete, and honest.
For general knowledge, identity, explanations, pop culture, definitions, and
normal conversation, answer directly without tools. Do not say "no tengo
herramienta para eso" for questions like "quien es Batman", "que es Python",
or "quien eres"; tools are only needed for live PC state or actions.

You control the computer only through the tools provided in the API `tools`
parameter. When the user asks for an action and a relevant tool exists, call
the tool. Do not describe a tool call as text. Use the native tool_call
mechanism.

Multi-step missions are allowed and expected. If the user asks "do A, then B,
then C", execute the steps in order using multiple tool calls across turns.
Do not stop after the first successful tool if there are pending steps. Keep
going until the requested sequence is complete, a tool fails, or you need a
missing argument.

For PC actions use a compact private cycle: decide intent, act with tools,
observe the returned state/evidence, verify when needed, then report. Do not
print the private plan or chain-of-thought. If an action affects visible UI,
prefer uia(...) first, then gui/vision screenshots when UI Automation cannot
reach the control.

The runtime sends only the relevant compound tools for the current turn. Tool
schemas are authoritative: choose the group whose name matches the user's
domain, set its `action`, and do not invent tools. Common groups include:
app, steam, browser, browser_real, web, media, audio, audio_device, office,
filesystem, gui, uia, vision, window, system, clipboard, terminal, memory,
state, verify, input, env, registry, download, email, reminder, knowledge,
notification, routine, source_manager, dependency, contacts, notes_tasks,
local_calendar, habit_tracker, local_search, printer_scanner, desktop_layout,
backup_sync, package, and safety.

For apps and games, use app(action="open", name="<user-facing name>") or
steam(action="launch_game", query="<game>") for installed Steam games. The
runtime discovers installed apps dynamically from Windows sources, Start Menu
shortcuts, PATH, registry, Steam and Epic. Do not require hardcoded exe names
unless the user gives one.
If the user says "abre Steam y ve a mi biblioteca", use
steam(action="library"), not steam(action="open"). If the user says "busca X
en mi biblioteca de Steam", use steam(action="search_library", query="X").
If the user asks for the Steam store page of a game/app, use
steam(action="store_page", query="X") or steam(action="search_store", query="X").
Do not open a normal web browser for Steam store tasks unless the user asks for
the web browser specifically. Do not split "ponme en la pagina de la tienda de
X" into store then ask; open the target page in the Steam client directly when
possible.

For internet research, current facts, sources, or requests like "investiga",
use web(action="research", query="<topic>") and answer from the returned source
excerpts. browser(action="search"|"open") only navigates a visible browser; it
does not mean you have read or researched the content.
For precise web page control or reading page text, prefer browser_real(...).
If browser_real says Playwright is missing, report that dependency honestly and
fall back to browser/web only if that still satisfies the user's request.

For YouTube/music requests, distinguish searching from playing. If the user
asks to play/put/reproduce a song, music, or a video on YouTube, use
media(action="play", provider="youtube", query="<song or generic request>").
If media is unavailable, fall back to browser(action="youtube_play", query=...).
If the user
says "ve a YouTube y pon una cancion, tu eligela", choose a concrete song in
the query or pass a generic song request. Do not use browser="YouTube"; YouTube
is the site/content target, not the browser app.
If the user says "para el video", "pausa el video", "para la musica", or
"pausa la cancion", they mean stop/pause current playback. Use
media(action="pause") or audio(action="media_play_pause"). Do not search for a
video.
The Spanish word "para" is ambiguous. Do not hard-code every phrase containing
"para" as a stop command. Use playback controls only when the user clearly means
pause/stop media from context or wording. If ambiguous, ask a brief clarification.
Never reinterpret "para el video" as "search for a video" unless the user
explicitly asks to search/find/open a video.

After a tool result, answer from the real result. Never claim that something
was completed if no tool ran or if the tool returned an error.
Every tool result has status, verified and evidence. Treat ok=true as "the
tool ran", not automatically "the user goal is complete". If status is failed,
attempted, or needs_verification, or verified=false, do not claim completion.
Either continue with verify/uia/gui/vision/web as appropriate, or tell the user
exactly what was attempted and what evidence is missing. If browser(search/open)
returns content_verified=false, say that you opened the URL or search results;
do not claim that you researched, read, watched, or found specific content
unless web(...) or another tool returned extracted content.

Example multi-step:
User: "abre Steam, ve a mi biblioteca y busca Doom Eternal ahi dentro, luego ve
a Opera y busca Doom en Google"
Tool sequence:
1. steam(action="search_library", query="Doom Eternal")
2. browser(action="search", browser="Opera", engine="google", query="Doom")
3. reply with what was attempted and any unverified GUI state.

The safety layer is configurable. If a tool returns needs_confirmation, stop
and ask the user to confirm the specific pending action. Do not bypass it. If
safety is disabled by configuration, tools execute directly.
Even without confirmation prompts, use the technical rollback/cleanup tools
when state is changed: filesystem/env/registry/download create checkpoints or
resources; state(action="cleanup") and state(action="rollback") can undo known
resources/checkpoints when a mission asks for cleanup or recovery. Do not
promise perfect rollback if a tool result only provides a partial rollback plan.

Email and Graph-backed reminders require an existing Microsoft Graph token in
GEMMA4_GRAPH_TOKEN or MS_GRAPH_TOKEN. If auth is missing, email/reminder must
return NEEDS_USER; never pretend a message or reminder was sent.

Office/document rule: if the user asks for a PowerPoint, Word document, Excel
file, spreadsheet, or PDF export, use office(...). Do not say there is no tool
for PowerPoint. If office returns needs_dependency, report the missing local
dependency and the install hint.

Audio device rule: for requests like "cambia a AUX", "usa Focusrite", "cambia
el dispositivo de audio", use audio_device(...), not audio(set_default). If a
helper such as SoundVolumeView is missing, report needs_dependency and do not
pretend the device changed.

Timers/alarms/routines rule: use notification(...) for local timers, alarms,
reminders and immediate notifications. Use routine(...) when the user asks for
a reusable automation or a sequence to run now/later.

Small local organization rule: use contacts(...) for local contacts,
notes_tasks(...) for notes/lists/tasks, local_calendar(...) for offline events
and ICS export, habit_tracker(...) for habits, source_manager(...) for saving
sources/citations, local_search(...) for local file search, dependency(...) for
missing tool dependencies, printer_scanner(...) for printer discovery/queues,
desktop_layout(...) for window/monitor snapshots, and backup_sync(...) for ZIP
backups. If an action returns needs_implementation, say exactly what is missing.

Persistent memory rule: call memory(action="save") only when the user
explicitly says "remember", "recorda", "guarda en memoria", "mi preferencia
es", or equivalent. Do not save casual chat, temporary facts, secrets, or
one-off instructions unless the user explicitly asks. Use memory(action="recall")
or memory(action="list") when the user asks what you remember.
Knowledge/RAG rule: use knowledge(action="ingest") only when the user asks to
store documents or build a local knowledge base. Use knowledge(action="search")
when the user asks about previously ingested local documents.

Multimodal rule: if the user attaches an image or audio, use that input as
evidence. If you call gui(action="screenshot") or vision(...), the runtime will
send the screenshot image back to you in the next message; inspect it before
clicking or typing.

If a necessary tool is missing, say "no tengo herramienta para eso" and stop.
Never output special tokens or thinking tags."""


@dataclass
class ToolEvent:
    name: str
    args: dict[str, Any]
    result: dict[str, Any]


@dataclass
class AgentReply:
    content: str
    tool_events: list[ToolEvent] = field(default_factory=list)
    error: str | None = None
    mission: dict[str, Any] | None = None


class Gemma4Agent:
    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig.from_env()
        self.memory = MemoryStore(self.config.memory_path)
        self.state = AgentState(self.config.state_path)
        self.client = LLMClient(self.config)
        self.tools = ToolRegistry(self.memory, self.config.captures_dir, self.state, safety_enabled=self.config.enable_safety)
        self.trace = TraceLogger(self.config.trace_path, self.config.enable_tracing)
        self.history: list[dict[str, Any]] = []

    def clear(self) -> None:
        self.history.clear()

    def _system_message(self, mode: AgentMode | None = None, plan: MissionPlan | None = None) -> dict[str, str]:
        mode_hint = f"\n\n# Current mode\n{mode.system_hint}" if mode else ""
        plan_hint = f"\n\n{plan.prompt_hint()}" if plan and plan.prompt_hint() else ""
        return {
            "role": "system",
            "content": f"{SYSTEM_PROMPT}{mode_hint}{plan_hint}\n\n# Persistent memory\n{self.memory.prompt_summary()}",
        }

    def _messages(self, mode: AgentMode | None = None, plan: MissionPlan | None = None) -> list[dict[str, Any]]:
        return [self._system_message(mode, plan), *self.history]

    def run_text(
        self,
        text: str,
        images: list[Path] | None = None,
        audios: list[Path] | None = None,
        progress: ProgressCallback | None = None,
    ) -> AgentReply:
        content = user_content(text, images=images, audios=audios)
        return self.run_content(content, progress=progress)

    def run_content(self, content: str | list[dict[str, Any]], progress: ProgressCallback | None = None) -> AgentReply:
        mode = choose_mode(content, self.config.agent_mode, self.config.max_tokens)
        plan = plan_mission(content)
        turn_id = self.trace.new_turn_id()
        _progress(
            progress,
            "start",
            mode=mode.name,
            steps=len(plan.steps),
            thinking=mode.enable_thinking,
            max_turns=self.config.max_agent_turns,
        )
        self.trace.event(
            turn_id,
            "request_start",
            mode=mode.name,
            content=summarize_content(content),
            mission_plan=plan.as_dict(),
            thinking=mode.enable_thinking,
            parallel_tool_calls=mode.parallel_tool_calls,
            max_tokens=mode.max_tokens,
        )
        selected_tool_names = select_tool_names(content, plan, safety_enabled=self.config.enable_safety)
        selected_schemas = self.tools.schemas_for_names(selected_tool_names)
        self.trace.event(turn_id, "tool_subset", tools=selected_tool_names, schema_count=len(selected_schemas))
        _progress(progress, "tool_subset", tools=selected_tool_names, schema_count=len(selected_schemas))
        self._compact_completed_history()
        self.history.append({"role": "user", "content": _compact_live_content(content)})
        events: list[ToolEvent] = []

        for _turn in range(self.config.max_agent_turns):
            _progress(
                progress,
                "llm_start",
                turn=_turn + 1,
                max_turns=self.config.max_agent_turns,
                tools=len(events),
            )
            try:
                resp = self.client.chat(
                    self._messages(mode, plan),
                    tools=selected_schemas,
                    enable_thinking=mode.enable_thinking,
                    parallel_tool_calls=mode.parallel_tool_calls,
                    max_tokens=mode.max_tokens,
                )
            except Exception as exc:
                if _looks_like_context_overflow(str(exc)):
                    _progress(progress, "context_retry", error=str(exc), tools=len(events))
                    self.trace.event(turn_id, "context_retry", error=str(exc), tool_events=len(events))
                    self._compact_active_history_for_retry()
                    selected_schemas = self.tools.schemas_for_names(selected_tool_names[:8])
                    try:
                        resp = self.client.chat(
                            self._messages(mode, plan),
                            tools=selected_schemas,
                            enable_thinking=mode.enable_thinking,
                            parallel_tool_calls=mode.parallel_tool_calls,
                            max_tokens=mode.max_tokens,
                        )
                    except Exception as retry_exc:
                        _progress(progress, "error", error=str(retry_exc), tools=len(events))
                        self.trace.event(turn_id, "llm_error", error=str(retry_exc), tool_events=len(events), after_context_retry=True)
                        return AgentReply(content="", tool_events=events, error=str(retry_exc))
                    else:
                        self.trace.event(turn_id, "context_retry_ok", schema_count=len(selected_schemas))
                        _progress(progress, "context_retry_ok", tools=len(events), schema_count=len(selected_schemas))
                else:
                    _progress(progress, "error", error=str(exc), tools=len(events))
                    self.trace.event(turn_id, "llm_error", error=str(exc), tool_events=len(events))
                    return AgentReply(content="", tool_events=events, error=str(exc))

            choice = (resp.get("choices") or [{}])[0]
            raw_msg = choice.get("message") or {}
            msg = sanitize_assistant_message(raw_msg)
            assistant_content = msg.get("content") or ""
            raw_tool_calls = msg.get("tool_calls") or []
            self.trace.event(
                turn_id,
                "llm_response",
                finish_reason=choice.get("finish_reason"),
                content_chars=len(assistant_content),
                tool_call_count=len(raw_tool_calls),
                stripped_reasoning=any(k in raw_msg for k in ("reasoning", "reasoning_content", "reasoning_details")),
            )
            _progress(
                progress,
                "llm_response",
                turn=_turn + 1,
                tool_calls=len(raw_tool_calls),
                tools=len(events),
            )

            if not raw_tool_calls:
                assistant_content = sanitize_text(assistant_content)
                assistant_content = self._guard_unverified_final(assistant_content, events)
                mission = evaluate_mission(events, assistant_content, plan)
                self.history.append({"role": "assistant", "content": assistant_content})
                self.trace.event(turn_id, "final", content=assistant_content, tool_events=len(events), mission=mission)
                self._compact_completed_history()
                _progress(progress, "final", tools=len(events), mission=mission)
                return AgentReply(content=assistant_content, tool_events=events, mission=mission)

            self.history.append(msg)

            image_results: list[tuple[Path, dict[str, Any]]] = []
            for raw_call in raw_tool_calls:
                fn = raw_call.get("function") or {}
                name = fn.get("name", "")
                args = _parse_args(fn.get("arguments", {}))
                self.trace.event(turn_id, "tool_call", name=name, args=args)
                _progress(progress, "tool_start", name=name, args=args, index=len(events) + 1)
                result = self.tools.execute(name, args)
                events.append(ToolEvent(name=name, args=args, result=result))
                self.trace.event(turn_id, "tool_result", name=name, result=result)
                _progress(
                    progress,
                    "tool_end",
                    name=name,
                    ok=bool(result.get("ok")),
                    status=str(result.get("status") or ""),
                    verified=result.get("verified"),
                    index=len(events),
                )
                self.history.append({
                    "role": "tool",
                    "tool_call_id": raw_call.get("id", f"call_{name}"),
                    "content": json.dumps(_compact_tool_result(name, args, result), ensure_ascii=False),
                })

                image_path = result.get("image_path")
                if image_path:
                    image_results.append((Path(str(image_path)), result))

            for image_path, result in image_results:
                _progress(progress, "image_injected", path=str(image_path))
                self._inject_tool_image(image_path, result)

        final = "No pude terminar la tarea dentro del limite de turnos."
        mission = evaluate_mission(events, final, plan)
        self.history.append({"role": "assistant", "content": final})
        self.trace.event(turn_id, "max_turns", content=final, tool_events=len(events), mission=mission)
        self._compact_completed_history()
        _progress(progress, "max_turns", tools=len(events), mission=mission)
        return AgentReply(content=final, tool_events=events, mission=mission)

    def _inject_tool_image(self, path: Path, result: dict[str, Any]) -> None:
        if not path.exists():
            return
        text = (
            "Esta imagen fue capturada por una tool visual. "
            f"Tamano reportado: {result.get('width')}x{result.get('height')} px. "
            "Usala como evidencia visual para continuar."
        )
        self.history.append({
            "role": "user",
            "content": [image_part(path), {"type": "text", "text": text}],
        })

    def _compact_completed_history(self) -> None:
        """Keep future turns small after a completed tool cycle."""

        compacted: list[dict[str, Any]] = []
        for msg in self.history:
            role = str(msg.get("role") or "")
            if role == "tool":
                continue
            if role == "assistant" and msg.get("tool_calls"):
                continue
            if role not in {"user", "assistant"}:
                continue
            compacted.append({"role": role, "content": _compact_history_content(msg.get("content"))})
        self.history = compacted[-18:]

    def _compact_active_history_for_retry(self) -> None:
        """Aggressive fallback when llama-server reports context overflow."""

        trimmed: list[dict[str, Any]] = []
        for msg in self.history[-10:]:
            role = str(msg.get("role") or "")
            if role == "tool":
                trimmed.append({
                    "role": "tool",
                    "tool_call_id": str(msg.get("tool_call_id") or "call_compacted"),
                    "content": _middle_ellipsis(str(msg.get("content") or ""), 1200),
                })
            elif role == "assistant":
                clean = {"role": "assistant", "content": _middle_ellipsis(str(msg.get("content") or ""), 1200)}
                if msg.get("tool_calls"):
                    clean["tool_calls"] = _compact_json(msg.get("tool_calls"), max_items=4, max_string=500)
                trimmed.append(clean)
            elif role == "user":
                trimmed.append({"role": "user", "content": _compact_history_content(msg.get("content"))})
        while trimmed and trimmed[0].get("role") == "tool":
            trimmed.pop(0)
        self.history = trimmed

    def _guard_unverified_final(self, content: str, events: list[ToolEvent]) -> str:
        if not events:
            return content
        last = events[-1].result
        status = str(last.get("status") or "")
        verified = last.get("verified")
        if verified is not False and status not in {"attempted", "needs_verification", "failed"}:
            return content
        low = content.casefold()
        already_honest = any(token in low for token in ("intent", "verifi", "no pude", "no se pudo", "error", "fall"))
        if already_honest:
            return content
        evidence = last.get("evidence") or last.get("completion_status") or status or "sin evidencia"
        note = (
            "\n\nNota: la ultima tool no dejo evidencia suficiente de finalizacion "
            f"(status={status or 'desconocido'}, verified={verified}, evidence={evidence})."
        )
        return content.rstrip() + note


LIVE_TEXT_LIMIT = 10000
HISTORY_TEXT_LIMIT = 3500
TOOL_RESULT_LIMIT = 3500


def _compact_live_content(content: str | list[dict[str, Any]]) -> str | list[dict[str, Any]]:
    if isinstance(content, str):
        return _middle_ellipsis(content, LIVE_TEXT_LIMIT)
    out: list[dict[str, Any]] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text":
            out.append({"type": "text", "text": _middle_ellipsis(str(item.get("text") or ""), LIVE_TEXT_LIMIT)})
        else:
            out.append(item)
    return out


def _compact_history_content(content: Any) -> str:
    if isinstance(content, str):
        return _middle_ellipsis(content, HISTORY_TEXT_LIMIT)
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
        return _middle_ellipsis("\n".join(parts).strip() + suffix, HISTORY_TEXT_LIMIT)
    return _middle_ellipsis(str(content or ""), HISTORY_TEXT_LIMIT)


def _compact_tool_result(name: str, args: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    compacted = _compact_json(result, max_items=5, max_string=700)
    if _json_len(compacted) <= TOOL_RESULT_LIMIT:
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
        "args": _compact_json(args, max_items=5, max_string=300),
        "context_compacted": True,
    }
    for key in core_keys:
        if key in result:
            core[key] = _compact_json(result[key], max_items=4, max_string=500)
    for key, value in result.items():
        if isinstance(value, list):
            core[f"{key}_count"] = len(value)
            core[key] = _compact_json(value[:3], max_items=3, max_string=350)
        elif isinstance(value, dict) and key not in core:
            core[f"{key}_keys"] = list(value.keys())[:12]
    return _compact_json(core, max_items=6, max_string=600)


def _compact_json(value: Any, *, max_items: int, max_string: int, depth: int = 0) -> Any:
    if depth > 5:
        return _middle_ellipsis(str(value), max_string)
    if isinstance(value, str):
        return _middle_ellipsis(value, max_string)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, list):
        out = [_compact_json(item, max_items=max_items, max_string=max_string, depth=depth + 1) for item in value[:max_items]]
        if len(value) > max_items:
            out.append({"_omitted": len(value) - max_items})
        return out
    if isinstance(value, dict):
        limit = 80 if depth == 0 else max_items
        items = list(value.items())
        out: dict[str, Any] = {}
        for key, item in items[:limit]:
            out[str(key)] = _compact_json(item, max_items=max_items, max_string=max_string, depth=depth + 1)
        if len(items) > limit:
            out["_omitted_keys"] = len(items) - limit
        return out
    return _middle_ellipsis(str(value), max_string)


def _json_len(value: Any) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, default=str))
    except TypeError:
        return len(str(value))


def _looks_like_context_overflow(message: str) -> bool:
    low = message.casefold()
    return "exceeds the available context size" in low or "context size" in low and "exceed" in low


def _middle_ellipsis(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    keep_start = max(0, limit // 2)
    keep_end = max(0, limit - keep_start - 80)
    return (
        text[:keep_start].rstrip()
        + f"\n...[omitted {len(text) - keep_start - keep_end} chars to keep context under limit]...\n"
        + text[-keep_end:].lstrip()
    )


def _parse_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            return {"_raw": raw}
    return {"value": raw}


def _progress(callback: ProgressCallback | None, event: str, **payload: Any) -> None:
    if callback is None:
        return
    try:
        callback(event, payload)
    except Exception:
        pass
