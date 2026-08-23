"""Goal 06: compose on the shipped sidecar, ugly paths included.

Writes compose_launch.json (two cases) and goal06_cien_respuestas.jsonl.
If the sidecar cannot start, writes compose_launch_unavailable.log instead.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    JsonLineProcess,
    sidecar_environment,
)
from baxy_mind.llm import (  # noqa: E402
    compose_visible_defect,
    visible_reply_invents_a_spanish_infinitive,
    visible_reply_is_a_fixed_stall,
)

CASES = [
    ("es-success-spotify", "abre Spotify", "status",
     {"kind": "operation", "operation": "app.open", "polarity": "success",
      "verified": True, "observed": {"app": "Spotify", "playing": True}}),
    ("es-fail-spotify", "abre Spotify", "error",
     {"kind": "failure", "cause": "provider_down", "polarity": "failure",
      "target": "Spotify"}),
    ("es-timeout", "cierra Chrome", "error",
     {"kind": "failure", "cause": "timeout", "polarity": "failure",
      "target": "Chrome"}),
    ("es-out-of-catalog", "pide una pizza", "error",
     {"kind": "failure", "cause": "out_of_catalog", "polarity": "failure"}),
    ("es-invalid-model", "sube el volumen", "error",
     {"kind": "failure", "cause": "model_invalid", "polarity": "failure"}),
    ("es-ambiguous", "ábrela", "clarification",
     {"kind": "clarification", "cause": "ambiguous_request", "polarity": "pending"}),
    ("es-deny", "hackea el wifi del vecino", "error",
     {"kind": "failure", "cause": "out_of_catalog", "polarity": "failure"}),
    ("es-welcome", "", "welcome",
     {"kind": "welcome", "polarity": "success"}),
    ("es-progress-acting", "abre Steam y ve a la biblioteca", "status",
     {"kind": "status", "cause": "acting", "polarity": "success"}),
    ("es-mission", "abre Steam y sube el volumen", "status",
     {"kind": "status", "cause": "mission_completed", "polarity": "success",
      "stepCount": 2, "steps": ["Abrí Steam.", "Puse el volumen en 40 %."]}),
    ("es-mission-fail", "abre Steam y borra el disco", "error",
     {"kind": "failure", "cause": "mission_failed", "polarity": "failure",
      "stepCount": 1, "steps": ["Abrí Steam."], "reason": "out_of_catalog"}),
    ("es-confirm", "borra la nota Compras", "confirmation",
     {"kind": "confirmation", "cause": "memory_forget_irreversible",
      "polarity": "pending", "choices": ["confirmar", "confirm", "cancelar", "cancel"]}),
    ("es-access", "cierra la ventana", "status",
     {"kind": "operation", "operation": "app.close", "polarity": "success",
      "verified": True}),
    ("en-success", "open Spotify", "status",
     {"kind": "operation", "operation": "app.open", "polarity": "success",
      "verified": True, "observed": {"app": "Spotify", "playing": True}}),
    ("en-fail", "open Spotify", "error",
     {"kind": "failure", "cause": "provider_down", "polarity": "failure",
      "target": "Spotify"}),
    ("en-clarify", "open it", "clarification",
     {"kind": "clarification", "cause": "ambiguous_request", "polarity": "pending"}),
    ("en-deny", "order a pizza", "error",
     {"kind": "failure", "cause": "out_of_catalog", "polarity": "failure"}),
    ("en-welcome", "hi", "welcome", {"kind": "welcome", "polarity": "success"}),
    ("mix-success", "abre Spotify and play", "status",
     {"kind": "operation", "operation": "app.open", "polarity": "success",
      "verified": True, "observed": {"app": "Spotify", "playing": True}}),
    ("mix-fail", "cierra Chrome please", "error",
     {"kind": "failure", "cause": "timeout", "polarity": "failure",
      "target": "Chrome"}),
]


def _expand_cases() -> list[tuple[str, str, str, dict]]:
    extras: list[tuple[str, str, str, dict]] = []
    apps = [
        ("Steam", "abre Steam", "open Steam"),
        ("Chrome", "abre Chrome", "open Chrome"),
        ("Notepad", "abre el Bloc de notas", "open Notepad"),
        ("Discord", "abre Discord", "open Discord"),
        ("VLC", "abre VLC", "open VLC"),
        ("Word", "abre Word", "open Word"),
        ("Excel", "abre Excel", "open Excel"),
        ("Firefox", "abre Firefox", "open Firefox"),
        ("Calculadora", "abre Calculadora", "open Calculator"),
        ("Terminal", "abre la terminal", "open Terminal"),
    ]
    for i, (app, es, en) in enumerate(apps):
        extras.append((
            f"open-ok-{app}", es, "status",
            {"kind": "operation", "operation": "app.open", "polarity": "success",
             "verified": True, "observed": {"app": app}},
        ))
        extras.append((
            f"open-fail-{app}", es, "error",
            {"kind": "failure", "cause": "app_not_found", "polarity": "failure",
             "target": app},
        ))
        extras.append((
            f"open-en-{app}", en, "status",
            {"kind": "operation", "operation": "app.open", "polarity": "success",
             "verified": True, "observed": {"app": app}},
        ))
        extras.append((
            f"timeout-{app}", es, "error",
            {"kind": "failure", "cause": "timeout", "polarity": "failure",
             "target": app},
        ))
    extras.extend([
        ("vol-10", "pon el volumen a 10", "status",
         {"kind": "operation", "operation": "audio.volume", "polarity": "success",
          "verified": True, "observed": {"level": 10}}),
        ("vol-80", "sube el volumen a 80", "status",
         {"kind": "operation", "operation": "audio.volume", "polarity": "success",
          "verified": True, "observed": {"level": 80}}),
        ("unmute", "reactiva el audio", "status",
         {"kind": "operation", "operation": "audio.mute", "polarity": "success",
          "verified": True, "observed": {"muted": False}}),
        ("note-ideas", "crea una nota Ideas", "status",
         {"kind": "operation", "operation": "note.create", "polarity": "success",
          "verified": True, "observed": {"title": "Ideas"}}),
        ("note-fail", "lee la nota Inexistente", "error",
         {"kind": "failure", "cause": "app_not_found", "polarity": "failure",
          "target": "Inexistente"}),
        ("deny-en", "order a pizza", "error",
         {"kind": "failure", "cause": "out_of_catalog", "polarity": "failure"}),
        ("clarify-en", "close it", "clarification",
         {"kind": "clarification", "cause": "ambiguous_request", "polarity": "pending"}),
        ("welcome-es2", "buenos días", "welcome",
         {"kind": "welcome", "polarity": "success"}),
        ("confirm-en", "delete the note Ideas", "confirmation",
         {"kind": "confirmation", "cause": "memory_forget_irreversible",
          "polarity": "pending",
          "choices": ["confirmar", "confirm", "cancelar", "cancel"]}),
        ("acting-en", "open Steam and go to the library", "status",
         {"kind": "status", "cause": "acting", "polarity": "success"}),
        ("mix-timeout", "pausa Chrome please", "error",
         {"kind": "failure", "cause": "timeout", "polarity": "failure",
          "target": "Chrome"}),
        ("mix-ok", "open Discord y silencia", "status",
         {"kind": "operation", "operation": "app.open", "polarity": "success",
          "verified": True, "observed": {"app": "Discord"}}),
        ("mission-ok2", "abre Word y crea una nota", "status",
         {"kind": "status", "cause": "mission_completed", "polarity": "success",
          "stepCount": 2, "steps": ["Abrí Word.", "Creé la nota «Borrador»."]}),
        ("provider-vlc", "abre VLC", "error",
         {"kind": "failure", "cause": "provider_down", "polarity": "failure",
          "target": "VLC"}),
        ("invalid-en", "turn the volume up", "error",
         {"kind": "failure", "cause": "model_invalid", "polarity": "failure"}),
        ("ask-which", "ábrela", "clarification",
         {"kind": "clarification", "cause": "ambiguous_request", "polarity": "pending"}),
        ("time-en", "what time is it", "status",
         {"kind": "operation", "operation": "system.time", "polarity": "success",
          "verified": True, "observed": {"localTime": "09:05"}}),
        ("close-ok", "cierra la ventana activa", "status",
         {"kind": "operation", "operation": "app.close", "polarity": "success",
          "verified": True}),
        ("close-steam", "cierra Steam", "status",
         {"kind": "operation", "operation": "app.close", "polarity": "success",
          "verified": True, "observed": {"app": "Steam"}}),
        ("vol-0", "silencia bajando el volumen a 0", "status",
         {"kind": "operation", "operation": "audio.volume", "polarity": "success",
          "verified": True, "observed": {"level": 0}}),
        ("vol-50", "pon el volumen a 50", "status",
         {"kind": "operation", "operation": "audio.volume", "polarity": "success",
          "verified": True, "observed": {"level": 50}}),
        ("note-alfa", "guarda la nota Alfa", "status",
         {"kind": "operation", "operation": "note.create", "polarity": "success",
          "verified": True, "observed": {"title": "Alfa"}}),
        ("note-beta", "crea la nota Beta", "status",
         {"kind": "operation", "operation": "note.create", "polarity": "success",
          "verified": True, "observed": {"title": "Beta"}}),
        ("deny-es2", "compra bitcoins", "error",
         {"kind": "failure", "cause": "out_of_catalog", "polarity": "failure"}),
        ("deny-en2", "send this email to everyone", "error",
         {"kind": "failure", "cause": "out_of_catalog", "polarity": "failure"}),
        ("timeout-en", "close Chrome", "error",
         {"kind": "failure", "cause": "timeout", "polarity": "failure",
          "target": "Chrome"}),
        ("provider-en", "open Discord", "error",
         {"kind": "failure", "cause": "provider_down", "polarity": "failure",
          "target": "Discord"}),
        ("welcome-en2", "hello there", "welcome",
         {"kind": "welcome", "polarity": "success"}),
        ("confirm-es2", "borra la nota Ideas", "confirmation",
         {"kind": "confirmation", "cause": "memory_forget_irreversible",
          "polarity": "pending",
          "choices": ["confirmar", "confirm", "cancelar", "cancel"]}),
        ("mix-fail2", "abre Firefox please", "error",
         {"kind": "failure", "cause": "app_not_found", "polarity": "failure",
          "target": "Firefox"}),
        ("acting-es2", "abre Excel y ve a hoja 2", "status",
         {"kind": "status", "cause": "acting", "polarity": "success"}),
        ("time-es2", "qué hora es ahora", "status",
         {"kind": "operation", "operation": "system.time", "polarity": "success",
          "verified": True, "observed": {"localTime": "22:10"}}),
        ("close-en", "close the window", "status",
         {"kind": "operation", "operation": "app.close", "polarity": "success",
          "verified": True}),
        ("unmute-en", "unmute the audio", "status",
         {"kind": "operation", "operation": "audio.mute", "polarity": "success",
          "verified": True, "observed": {"muted": False}}),
        ("mute-en", "mute the speakers", "status",
         {"kind": "operation", "operation": "audio.mute", "polarity": "success",
          "verified": True, "observed": {"muted": True}}),
        ("mission-fail-en", "open Word and wipe the disk", "error",
         {"kind": "failure", "cause": "mission_failed", "polarity": "failure",
          "reason": "out_of_catalog", "stepCount": 1,
          "steps": ["I opened Word."]}),
        ("clarify-es2", "cierra eso", "clarification",
         {"kind": "clarification", "cause": "ambiguous_request",
          "polarity": "pending"}),
        ("vol-en", "set volume to 25", "status",
         {"kind": "operation", "operation": "audio.volume", "polarity": "success",
          "verified": True, "observed": {"level": 25}}),
        ("mute-es", "silencia los altavoces", "status",
         {"kind": "operation", "operation": "audio.mute", "polarity": "success",
          "verified": True, "observed": {"muted": True}}),
        ("note-gamma", "crea la nota Gamma", "status",
         {"kind": "operation", "operation": "note.create", "polarity": "success",
          "verified": True, "observed": {"title": "Gamma"}}),
    ])
    combined = CASES + extras
    if len(combined) != 100:
        raise RuntimeError(f"goal 06 sample must be 100 cases, got {len(combined)}")
    return combined


def _score(text: str, intent: str, user_text: str, facts: dict) -> dict[str, object]:
    stripped = (text or "").strip()
    sentences = [part for part in stripped.replace("?", ".").replace("!", ".").split(".") if part.strip()]
    defect = compose_visible_defect(
        stripped, intent, user_text, {"situation": json.dumps(facts, ensure_ascii=False)}
    )
    return {
        "empty": not stripped,
        "invented": visible_reply_invents_a_spanish_infinitive(stripped),
        "stall": visible_reply_is_a_fixed_stall(stripped),
        "json": stripped.startswith("{"),
        "sentences": len(sentences) if stripped else 0,
        "defect": defect,
        "known_constant": stripped.casefold() in {
            "un momento…", "un momento...", "estoy lista para ayudarte con este equipo.",
            "estoy entendiendo tu petición.",
        },
    }


def main() -> int:
    out_dir = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else REPO / "artifacts" / "development"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    launch_path = out_dir / "compose_launch.json"
    sample_path = out_dir / "goal06_cien_respuestas.jsonl"
    unavailable = out_dir / "compose_launch_unavailable.log"
    ab_path = out_dir / "goal06_prosa_ab.json"
    try:
        runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    except Exception as error:  # noqa: BLE001
        unavailable.write_text(f"runtime: {error}\n", encoding="utf-8")
        print(error)
        return 1

    env = sidecar_environment(runtime, gpu_layers=runtime.gpu_layers, llm_http_timeout=60.0)
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=env,
        cwd=REPO,
    )
    try:
        hello = client.next_message(120.0)
        if hello.get("type") != "hello":
            raise RuntimeError(f"handshake={hello!r}")
        rows = []
        cases = _expand_cases()[:100]
        for case_id, user, intent, facts in cases:
            started = time.perf_counter()
            reply = client.request(
                {
                    "type": "message.compose",
                    "id": f"goal06-{case_id}",
                    "userText": user,
                    "intent": intent,
                    "facts": {"situation": json.dumps(facts, ensure_ascii=False)},
                },
                45.0,
            )
            text = str(reply.get("text") or "")
            row = {
                "case_id": case_id,
                "user_text": user,
                "intent": intent,
                "facts": facts,
                "reply_type": reply.get("type"),
                "reply_text": text,
                "latency_s": round(time.perf_counter() - started, 3),
                "score": _score(text, intent, user, facts),
            }
            rows.append(row)
        sample_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
        launch_path.write_text(
            json.dumps({"hello": hello.get("type"), "rows": rows[:2]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        invented = sum(
            1
            for row in rows
            if row["score"]["invented"]
            or row["score"]["stall"]
            or row["score"]["known_constant"]
            or row["score"]["json"]
            or row["score"]["empty"]
            or row["score"]["defect"]
        )
        ab_path.write_text(
            json.dumps(
                {
                    "date": time.strftime("%Y-%m-%d"),
                    "gguf": str(runtime.gguf),
                    "candidate": "Qwen3-4B-Q4_K_M",
                    "n": len(rows),
                    "bad": invented,
                    "p50_latency_s": sorted(row["latency_s"] for row in rows)[len(rows) // 2],
                    "lighter_on_disk": False,
                    "why_not_lighter": (
                        "No hay un GGUF más ligero del mismo modelo en disco. "
                        "Q2 de Gemma 4 inventaba «fysico»/«lumínar» (FunctionGemma, 2026-06). "
                        "Se conserva Q4_K_M y la guarda de infinitivos inventados."
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"wrote {len(rows)} rows, bad={invented}")
        return 0
    except Exception as error:  # noqa: BLE001
        unavailable.write_text(str(error), encoding="utf-8")
        print(error)
        return 1
    finally:
        client.close(graceful_message={"type": "shutdown", "id": "goal06-stop"}, timeout=15.0)


if __name__ == "__main__":
    raise SystemExit(main())
