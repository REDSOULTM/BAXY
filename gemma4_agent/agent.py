"""Agent loop: Gemma 4 decides, tools execute, results are fed back."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import AgentConfig
from .llm_client import LLMClient
from .memory import MemoryStore
from .modes import AgentMode, choose_mode
from .multimodal import image_part, user_content
from .reasoning import sanitize_assistant_message, sanitize_text
from .tools import ToolRegistry
from .tracing import TraceLogger, summarize_content


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

The tool catalog is intentionally compound to reduce context. Choose the
correct group and set `action`:
- app(action=search/open/close/uninstall)
- steam(action=open/library/store/list_games/launch_game/search_library/search_store/store_page/install)
- filesystem(action=list/read/write/search/delete/copy/move/rename/mkdir/diff/archive/unarchive/open)
- gui(action=screenshot/click/double_click/right_click/type/keypress/hotkey/scroll/drag/wait_for/locate_text/click_text)
- window(action=list/active/focus/close/minimize/maximize/restore/move_resize)
- vision(action=describe_screen/find_element/ocr/compare_before_after)
- browser(action=open/search/youtube_play/media_pause/media_stop/active_tab_title/click/find)
- web(action=search/read/research/open)
- uia(action=tree/find/click/focus/set_value)
- system(action=time/processes/cpu_ram_gpu/disk/battery/brightness_get/brightness_set/shutdown/restart/sleep)
- audio(action=get_volume/set_volume/mute/devices/set_default/media_play_pause/media_stop/next/previous)
- package(action=list/search/install/uninstall)
- clipboard(action=read/write)
- terminal(action=run)
- memory(action=save/recall/list/delete)
- verify(action=app_opened/file_exists/window_exists/clipboard_contains)

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

For YouTube/music requests, distinguish searching from playing. If the user
asks to play/put/reproduce a song, music, or a video on YouTube, use
browser(action="youtube_play", query="<song or generic request>"). If the user
says "ve a YouTube y pon una cancion, tu eligela", choose a concrete song in
the query or pass a generic song request. Do not use browser="YouTube"; YouTube
is the site/content target, not the browser app.
If the user says "para el video", "pausa el video", "para la musica", or
"pausa la cancion", they mean stop/pause current playback. Use
audio(action="media_play_pause") or browser(action="media_pause"). Do not search
for a video.
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

This prototype intentionally has NO safety confirmation layer. Do not ask for
confirmation only because an action is destructive. If the user asks for an
available action, execute it directly. Ask for clarification only when the
target or arguments are actually missing.

Persistent memory rule: call memory(action="save") only when the user
explicitly says "remember", "recorda", "guarda en memoria", "mi preferencia
es", or equivalent. Do not save casual chat, temporary facts, secrets, or
one-off instructions unless the user explicitly asks. Use memory(action="recall")
or memory(action="list") when the user asks what you remember.

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


class Gemma4Agent:
    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig.from_env()
        self.memory = MemoryStore(self.config.memory_path)
        self.client = LLMClient(self.config)
        self.tools = ToolRegistry(self.memory, self.config.captures_dir)
        self.trace = TraceLogger(self.config.trace_path, self.config.enable_tracing)
        self.history: list[dict[str, Any]] = []

    def clear(self) -> None:
        self.history.clear()

    def _system_message(self, mode: AgentMode | None = None) -> dict[str, str]:
        mode_hint = f"\n\n# Current mode\n{mode.system_hint}" if mode else ""
        return {
            "role": "system",
            "content": f"{SYSTEM_PROMPT}{mode_hint}\n\n# Persistent memory\n{self.memory.prompt_summary()}",
        }

    def _messages(self, mode: AgentMode | None = None) -> list[dict[str, Any]]:
        return [self._system_message(mode), *self.history]

    def run_text(
        self,
        text: str,
        images: list[Path] | None = None,
        audios: list[Path] | None = None,
    ) -> AgentReply:
        content = user_content(text, images=images, audios=audios)
        return self.run_content(content)

    def run_content(self, content: str | list[dict[str, Any]]) -> AgentReply:
        mode = choose_mode(content, self.config.agent_mode, self.config.max_tokens)
        turn_id = self.trace.new_turn_id()
        self.trace.event(
            turn_id,
            "request_start",
            mode=mode.name,
            content=summarize_content(content),
            thinking=mode.enable_thinking,
            parallel_tool_calls=mode.parallel_tool_calls,
            max_tokens=mode.max_tokens,
        )
        self.history.append({"role": "user", "content": content})
        events: list[ToolEvent] = []

        for _turn in range(self.config.max_agent_turns):
            try:
                resp = self.client.chat(
                    self._messages(mode),
                    tools=self.tools.schemas,
                    enable_thinking=mode.enable_thinking,
                    parallel_tool_calls=mode.parallel_tool_calls,
                    max_tokens=mode.max_tokens,
                )
            except Exception as exc:
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

            if not raw_tool_calls:
                assistant_content = sanitize_text(assistant_content)
                assistant_content = self._guard_unverified_final(assistant_content, events)
                self.history.append({"role": "assistant", "content": assistant_content})
                self.trace.event(turn_id, "final", content=assistant_content, tool_events=len(events))
                return AgentReply(content=assistant_content, tool_events=events)

            self.history.append(msg)

            image_results: list[tuple[Path, dict[str, Any]]] = []
            for raw_call in raw_tool_calls:
                fn = raw_call.get("function") or {}
                name = fn.get("name", "")
                args = _parse_args(fn.get("arguments", {}))
                self.trace.event(turn_id, "tool_call", name=name, args=args)
                result = self.tools.execute(name, args)
                events.append(ToolEvent(name=name, args=args, result=result))
                self.trace.event(turn_id, "tool_result", name=name, result=result)
                self.history.append({
                    "role": "tool",
                    "tool_call_id": raw_call.get("id", f"call_{name}"),
                    "content": json.dumps(result, ensure_ascii=False),
                })

                image_path = result.get("image_path")
                if image_path:
                    image_results.append((Path(str(image_path)), result))

            for image_path, result in image_results:
                self._inject_tool_image(image_path, result)

        final = "No pude terminar la tarea dentro del limite de turnos."
        self.history.append({"role": "assistant", "content": final})
        self.trace.event(turn_id, "max_turns", content=final, tool_events=len(events))
        return AgentReply(content=final, tool_events=events)

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
