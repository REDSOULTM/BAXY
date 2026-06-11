"""Validación EN VIVO de los fixes de alucinación 2026-06-11 (LLM + agente reales).

Reproduce los 3 síntomas de la sesión 2026-06-10 21:55-21:56:
  (1) media: "pon una canción de Michael Jackson" → song fabricada "Bohemian Rhapsody"
  (2) reply post-tool: "Es las 10:42 de la mañana." (hora fabricada, non-sequitur)
  (3) "I guess it." → "De nada." (idioma equivocado)

Ejecución de tools: media devuelve la RÉPLICA del resultado attempted real de la
sesión (no abre Spotify); browser/app/steam/gui/web mock ok; system/session/safety
REALES (system.time da la hora real → el guard de hora debe dejarla pasar).
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DIAG", "1")
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

from gemma4_agent.tools_pkg.tools import ToolRegistry  # noqa: E402

executed: list[dict] = []
REAL_EXEC = ToolRegistry.execute

# Réplica del tool_result real de la sesión 2026-06-10 21:56 (trace bb5c0b0e).
def _media_attempted(args: dict) -> dict:
    q = (args or {}).get("query") or (args or {}).get("song") or ""
    return {
        "ok": True, "action": "play", "provider": (args or {}).get("provider") or "spotify",
        "query": q, "deeplink": f"spotify:search:{q}", "app_kind": "exe",
        "opened": True, "played": False, "auto_play_attempted": True,
        "auto_play_info": {"played": False, "focus_verified": True,
                           "abort_reason": "UIA play: no_play_button",
                           "attempts": 3, "was_already_open": True},
        "verified": False, "query_match": None, "status": "attempted",
        "completion_status": "opened_search_results_pending_play",
        "note": ("Spotify opened with search results. App does NOT auto-play. "
                 "User must press Enter / click a track."),
        "tool": "media", "evidence": "tool_result",
    }


_MOCK_OK = {"browser", "app", "steam", "gui", "web", "computer_use", "vision"}


def _exec(self, name, args):
    executed.append({"name": name, "args": args or {}})
    if name == "media":
        return _media_attempted(args or {})
    if name in _MOCK_OK:
        return {"ok": True, "status": "ok", "verified": True, "_eval_mock": True}
    return REAL_EXEC(self, name, args)


ToolRegistry.execute = _exec

from gemma4_agent.agent_core.agent import Gemma4Agent  # noqa: E402

agent = Gemma4Agent()
print("[live] warm...", flush=True)
agent.run_content("hola")

CASES = [
    # (id, user_text, checks)
    ("mj_es", "pon una canción de Michael Jackson", "media_args+no_time"),
    ("badbunny_es", "pon una canción de Bad Bunny en Spotify", "media_args+no_time"),
    ("mj_en", "play a Michael Jackson song on Spotify", "media_args+no_time"),
    ("title_control", "pon Bohemian Rhapsody en Spotify", "title_ok+no_time"),
    ("garble_en", "I guess it.", "lang_en"),
    ("hora_es", "qué hora es", "time_real"),
    ("time_en", "what time is it", "time_real"),
]

results = []
for cid, utext, check in CASES:
    try:
        agent.history.clear()
    except Exception:
        pass
    executed.clear()
    t0 = time.perf_counter()
    try:
        rep = agent.run_content(utext)
        reply = getattr(rep, "content", None) or str(rep)
        err = None
    except Exception as e:
        reply, err = "", f"{type(e).__name__}: {e}"
    dt = time.perf_counter() - t0
    media_calls = [e for e in executed if e["name"] == "media"]
    results.append({
        "id": cid, "user_text": utext, "reply": reply, "latency_s": round(dt, 2),
        "tools": [e["name"] for e in executed],
        "media_args": [e["args"] for e in media_calls],
        "error": err, "check": check,
    })
    print(f"[{cid}] {dt:.1f}s tools={[e['name'] for e in executed]} "
          f"media_args={[e['args'] for e in media_calls]}\n  reply: {reply!r}", flush=True)

out = ROOT / "documentacion" / "_live_fix_validation_20260611.json"
out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"[live] resultados -> {out}", flush=True)
