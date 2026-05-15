"""Dry-run del EventBusBridge — sin abrir GUI ni tocar VRAM.

Verifica que:
  1. Atachar el bridge al BUS y publicar eventos dispara las signals.
  2. Eventos clasificados correctamente por kind/type.
  3. Eventos desconocidos terminan en unknown_event.
  4. detach() detiene el flujo.

Corre con:
    python -m gemma4_agent.ui.test_bus_bridge_dryrun
"""
from __future__ import annotations

import sys


def main() -> int:
    # PyQt6 necesita un QApplication para que signals con slots funcionen,
    # incluso si nunca mostramos un widget.
    from PyQt6.QtCore import QCoreApplication
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)

    from gemma4_agent.events_bus import BUS
    from gemma4_agent.ui.bus_bridge import EventBusBridge

    captured: dict[str, list[dict]] = {
        "boot_stage": [],
        "vision_threshold": [],
        "activity": [],
        "agent_state": [],
        "unknown_event": [],
    }

    bridge = EventBusBridge()
    bridge.boot_stage.connect(lambda e: captured["boot_stage"].append(dict(e)))
    bridge.vision_threshold.connect(lambda e: captured["vision_threshold"].append(dict(e)))
    bridge.activity.connect(lambda e: captured["activity"].append(dict(e)))
    bridge.agent_state.connect(lambda e: captured["agent_state"].append(dict(e)))
    bridge.unknown_event.connect(lambda e: captured["unknown_event"].append(dict(e)))
    bridge.attach()

    # Publicar eventos representativos
    BUS.publish({
        "kind": "boot_stage",
        "stage": "prewarm_start",
        "system_prompt_chars": 1234,
    })
    BUS.publish({
        "kind": "boot_stage",
        "stage": "prewarm_done",
        "elapsed_s": 1.42,
        "ok": True,
    })
    BUS.publish({
        "type": "boot_stage",      # uses "type" not "kind" (boot_progress)
        "stage": "llama_offload",
        "label": "offloaded 36/36 layers to GPU",
        "progress": 1.0,
    })
    BUS.publish({
        "kind": "vision_threshold_reached",
        "image_count": 40,
        "threshold": 40,
        "issue": "ggml-org/llama.cpp#21690",
    })
    BUS.publish({
        "type": "activity",
        "entry": {"id": "abc12345", "src": "TOOL", "msg": "fs_read_file(...)", "ts": "12:00:00"},
    })
    BUS.publish({
        "type": "agent",
        "built": True, "healthy": True, "ready": True,
    })
    BUS.publish({
        "kind": "something_weird",
        "data": 42,
    })

    # processEvents() para que los QueuedConnection se dispatcheen
    QCoreApplication.processEvents()

    # Validar
    failures: list[str] = []
    def check(name: str, expected_count: int) -> None:
        got = len(captured[name])
        if got != expected_count:
            failures.append(f"{name}: expected {expected_count}, got {got}")

    check("boot_stage", 3)
    check("vision_threshold", 1)
    check("activity", 1)
    check("agent_state", 1)
    check("unknown_event", 1)

    # Detach y confirmar que no llega nada nuevo
    bridge.detach()
    BUS.publish({"kind": "boot_stage", "stage": "prewarm_start"})
    QCoreApplication.processEvents()
    if len(captured["boot_stage"]) != 3:
        failures.append(
            f"after detach: boot_stage expected 3, got {len(captured['boot_stage'])}"
        )

    print("=== captured ===")
    for k, v in captured.items():
        print(f"  {k}: {len(v)} events")
        for e in v:
            print(f"    - {e}")

    if failures:
        print("\n=== FAIL ===")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("\n=== PASS ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
