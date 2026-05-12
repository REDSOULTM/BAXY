"""Lightweight mission planning for tool-using turns."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


STEP_SPLIT_RE = re.compile(r"\b(?:luego|despues|después|entonces|y luego|y despues|y después|,\s*luego)\b|[;]\s*", re.IGNORECASE)


@dataclass
class MissionStep:
    index: int
    text: str
    suggested_tools: list[str] = field(default_factory=list)
    verification_hint: str = ""


@dataclass
class MissionPlan:
    goal: str
    steps: list[MissionStep]
    cleanup_expected: bool = False
    needs_pc_action: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "cleanup_expected": self.cleanup_expected,
            "needs_pc_action": self.needs_pc_action,
            "steps": [
                {
                    "index": step.index,
                    "text": step.text,
                    "suggested_tools": step.suggested_tools,
                    "verification_hint": step.verification_hint,
                }
                for step in self.steps
            ],
        }

    def prompt_hint(self) -> str:
        if not self.steps:
            return ""
        lines = [
            "# Current Mission Draft",
            "This is a deterministic draft from the user request. Follow it when it matches the user's intent; do not expose it.",
            f"Goal: {self.goal}",
        ]
        for step in self.steps:
            tools = ", ".join(step.suggested_tools) if step.suggested_tools else "none"
            lines.append(f"{step.index}. {step.text} | suggested_tools={tools} | verify={step.verification_hint or 'result evidence'}")
        if self.cleanup_expected:
            lines.append("Cleanup expected: use state(action='cleanup') or targeted close/delete after completing the mission.")
        return "\n".join(lines)


def plan_mission(content: str | list[dict[str, Any]]) -> MissionPlan:
    text = _content_text(content)
    parts = _split_steps(text)
    steps = [MissionStep(index=i + 1, text=part, suggested_tools=_suggest_tools(part), verification_hint=_verify_hint(part)) for i, part in enumerate(parts)]
    cleanup_expected = bool(re.search(r"\b(limpia|limpiar|cleanup|cierra todo lo que abriste|cerrar al final)\b", text, re.IGNORECASE))
    needs_pc_action = any(step.suggested_tools for step in steps)
    if len(steps) == 1 and not needs_pc_action:
        steps = []
    return MissionPlan(goal=text[:500], steps=steps, cleanup_expected=cleanup_expected, needs_pc_action=needs_pc_action)


def _content_text(content: str | list[dict[str, Any]]) -> str:
    if isinstance(content, str):
        return content.strip()
    chunks: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            chunks.append(str(item.get("text") or ""))
    return " ".join(chunks).strip()


def _split_steps(text: str) -> list[str]:
    raw_parts = [part.strip(" ,.") for part in STEP_SPLIT_RE.split(text) if part.strip(" ,.")]
    if len(raw_parts) <= 1:
        return [text.strip()] if text.strip() else []
    merged: list[str] = []
    for part in raw_parts:
        if len(part.split()) <= 2 and merged:
            merged[-1] = f"{merged[-1]} {part}".strip()
        else:
            merged.append(part)
    return merged[:8]


def _suggest_tools(step: str) -> list[str]:
    low = step.casefold()
    tools: list[str] = []
    if "steam" in low or re.search(r"\bbiblioteca\b|\btienda\b", low):
        tools.append("steam")
    if re.search(r"\b(opera|chrome|edge|firefox|youtube|google|navegador|web|pagina|página|url)\b", low):
        tools.append("browser")
        if re.search(r"\blee\b|\binvestiga\b|\bextrae\b|\bcontenido\b", low):
            tools.append("web")
            tools.append("browser_real")
    if re.search(r"\barchivo|carpeta|directorio|escribe|crea|borra|copia|mueve|renombra|zip\b", low):
        tools.append("filesystem")
    if re.search(r"\bvolumen|audio|musica|música|video|pausa|reanuda|para\b", low):
        tools.append("audio")
    if re.search(r"\babre|abrir|cierra|cerrar|app|programa|juego\b", low) and "steam" not in low:
        tools.append("app")
    if re.search(r"\bclick|clic|teclea|escribe en pantalla|pantalla|boton|botón\b", low):
        tools.extend(["uia", "gui", "vision"])
    if re.search(r"\bregistro|registry|regedit\b", low):
        tools.append("registry")
    if re.search(r"\bvariable de entorno|env\b", low):
        tools.append("env")
    if re.search(r"\bdescarga|download|sha256|hash|firma\b", low):
        tools.append("download")
    if re.search(r"\brecuerda|recorda|guarda en memoria|memoria|documento|rag|conocimiento\b", low):
        tools.extend(["memory", "knowledge"])
    if re.search(r"\bproceso|cpu|ram|gpu|disco|bateria|batería|hora\b", low):
        tools.append("system")
    return _dedupe(tools)


def _verify_hint(step: str) -> str:
    low = step.casefold()
    if "steam" in low:
        return "steam result, window focus, screenshot if GUI state is unclear"
    if "youtube" in low or "video" in low or "musica" in low or "música" in low:
        return "direct URL plus screenshot; playback may remain unverified"
    if "archivo" in low or "carpeta" in low:
        return "verify(action='file_exists') or filesystem diff/list"
    if "navegador" in low or "google" in low or "web" in low:
        return "browser_real/web content for reading; browser result only for navigation"
    if "cierra" in low or "cerrar" in low:
        return "verify app/window/process no longer exists"
    return "tool status/evidence"


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
