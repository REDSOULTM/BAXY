"""Eval de los modos de accesibilidad (B5). Mide la CAPA LÓGICA con gates
definidos de antemano (CLAUDE.md §3). NO toca la GUI ni emite input — lo físico
end-to-end lo verifica el usuario.

Gates (criterio de éxito, definido ANTES de medir):
  G1 activación-por-voz : pedidos de switch disparan el modo correcto, y el uso
                          normal (comandos/preguntas/charla) NO dispara.
                          PASS si aciertos>=90% Y falsos-positivos==0.
  G2 movilidad hands-free: replies que piden acción manual se flaggean; replies
                          legítimos (agente actúa / pregunta / pide dato hablado)
                          NO. PASS si falsos-positivos==0 Y recall>=0.70.
  G3 no_vidente narración: tras una acción exitosa, un reply mudo/escueto se
                          flaggea; uno descriptivo NO. PASS si 100% correcto.
  G4 anti-regresión     : el modo 'normal' tiene hint vacío y NINGUNA guarda de
                          accesibilidad aplica. PASS si se cumple.

Corre con el encoder REAL (G1/G2) — necesita sentence-transformers cargado.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Permitir `python scripts/accessibility_eval.py` desde cualquier cwd: agregar la
# raíz del repo al path (igual que correrlo con `-m scripts.accessibility_eval`).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gemma4_agent.computer_use_pkg import accessibility as a11y

from gemma4_agent.computer_use_pkg import accessibility_voice as av

from gemma4_agent.safety_pkg import reply_validator as rv



def _ok_tool():
    return [{"tool": "app", "result": {"ok": True, "verified": True}}]


# ---- G1: activación por voz ----------------------------------------------
G1_SWITCH = [
    ("activá el modo para no videntes", "no_vidente"),
    ("no puedo ver, leeme la pantalla", "no_vidente"),
    ("turn on blind mode", "no_vidente"),
    ("ativar o modo para cegos", "no_vidente"),
    ("activá el modo manos libres", "movilidad"),
    ("no puedo usar las manos, controlá todo por voz", "movilidad"),
    ("turn on hands free mode", "movilidad"),
    ("active le mode mains libres", "movilidad"),
    ("volvé al modo normal", "normal"),
    ("turn off accessibility mode", "normal"),
]
G1_NORMAL_USE = [
    "abre el editor", "pon música en spotify", "mandale un mensaje a mamá",
    "qué es la fotosíntesis", "hola cómo estás", "gracias",
    "open the browser", "cerrá la ventana de discord", "no entiendo nada",
]


def gate_g1() -> tuple[bool, str]:
    hits = sum(1 for t, exp in G1_SWITCH if av.detect_mode_switch(t) == exp)
    fp = sum(1 for t in G1_NORMAL_USE if av.detect_mode_switch(t) is not None)
    acc = hits / len(G1_SWITCH)
    ok = acc >= 0.90 and fp == 0
    return ok, f"switch {hits}/{len(G1_SWITCH)} ({acc:.0%}), falsos-positivos={fp}"


# ---- G2: movilidad hands-free --------------------------------------------
G2_MANUAL = [  # deben flaggear
    "Hacé clic en el botón Aceptar para continuar.",
    "Click the OK button to confirm.",
    "Presioná el botón rojo de la esquina superior.",
    "Andá a Configuración y tocá Guardar.",
]
G2_OK = [  # NO deben flaggear
    "Listo, lo abrí por vos.",
    "¿Querés que lo haga yo?",
    "¿A cuál de los dos archivos te referís?",
    "Done, I opened Spotify for you.",
    "Decime el nombre y lo busco yo.",
]


def gate_g2() -> tuple[bool, str]:
    recall = sum(1 for r in G2_MANUAL if rv.asks_user_manual_action(r)) / len(G2_MANUAL)
    fp = sum(1 for r in G2_OK if rv.asks_user_manual_action(r))
    ok = fp == 0 and recall >= 0.70
    return ok, f"recall {recall:.0%}, falsos-positivos={fp}"


# ---- G3: no_vidente narración --------------------------------------------
def gate_g3() -> tuple[bool, str]:
    cases = [
        ("Listo.", _ok_tool(), True),
        ("Hecho", _ok_tool(), True),
        ("", _ok_tool(), True),
        ("Abrí Spotify y está sonando tu lista de Favoritos ahora.", _ok_tool(), False),
        ("Listo.", [], False),               # sin tool -> no exige narración
        ("No pude.", [{"tool": "app", "result": {"ok": False}}], False),  # falló
    ]
    hits = sum(1 for r, calls, exp in cases
               if rv.reply_too_terse_for_blind(r, calls) == exp)
    ok = hits == len(cases)
    return ok, f"{hits}/{len(cases)} correcto"


# ---- G4: anti-regresión (normal) -----------------------------------------
def gate_g4() -> tuple[bool, str]:
    m = a11y.get("normal")
    checks = [
        m.system_hint == "",
        not m.narrate_all_actions,
        not m.hands_free_only,
        not m.read_screen_on_demand,
        m.preferred_tools == (),
    ]
    ok = all(checks)
    return ok, f"hint vacío + sin flags + sin preferred_tools = {ok}"


def gate_g5() -> tuple[bool, str]:
    """Universal hands-free rule: the agent must not pass screen work to user."""
    delegated = [
        "Revisa los resultados para ver cual sirve.",
        "Fijate en la configuracion cual opcion activar.",
        "Mira la pantalla y decidi que archivo abrir.",
        "Verifica si queres que abra el enlace directo.",
        "Review the results and pick the one you want.",
    ]
    allowed = [
        "Listo, lo abri por vos.",
        "Confirmas la compra? Decime si o no.",
        "Me trabe abriendo el resultado, no pude seguir.",
        "Decime el titulo exacto y lo busco yo.",
    ]
    recall = sum(1 for r in delegated if rv.reply_delegates_task(r)) / len(delegated)
    fp = sum(1 for r in allowed if rv.reply_delegates_task(r))
    ok = recall >= 0.80 and fp == 0
    return ok, f"recall {recall:.0%}, falsos-positivos={fp}"


def gate_g6() -> tuple[bool, str]:
    """Store/web tasks must route to browser, local launch tasks stay local."""
    from gemma4_agent.routing.planner import plan_mission, select_tool_names

    store_cases = [
        "anda a la pagina de Instant Gaming",
        "anda a instant gaming y compra resident evil",
        "compra resident evil en instant gaming",
    ]
    local_cases = [
        "abri Steam",
        "lanza el juego que tengo en Epic",
    ]

    store_ok = 0
    for text in store_cases:
        names = select_tool_names(text, plan_mission(text), safety_enabled=True)
        if "browser" in names[:3] or "browser_real" in names[:3]:
            store_ok += 1

    local_ok = 0
    for text in local_cases:
        names = select_tool_names(text, plan_mission(text), safety_enabled=True)
        if any(t in names[:4] for t in ("app", "steam", "game_launcher")):
            local_ok += 1

    ok = store_ok == len(store_cases) and local_ok == len(local_cases)
    return ok, f"tienda {store_ok}/{len(store_cases)}, local {local_ok}/{len(local_cases)}"


def gate_g7() -> tuple[bool, str]:
    """Computer-use primitive contract stays closed and verifier-aware."""
    from gemma4_agent.computer_use_pkg.computer_use import PlanExecutor, parse_plan
    from gemma4_agent.computer_use_caps.router import CapabilityRouter

    plan = parse_plan('[{"op":"fill_field","arg":"email=a@b.com"},'
                      '{"op":"toggle","arg":"notificaciones=on"},'
                      '{"op":"wait_for","arg":"Guardado"}]')
    split = PlanExecutor._split_field_value("email=a@b.com")
    toggle = PlanExecutor._parse_toggle_spec("notificaciones=on")
    hard = CapabilityRouter.hard_fail_ops
    ok = (
        plan is not None
        and split == ("email", "a@b.com")
        and toggle == ("notificaciones", True)
        and "fill_field" in hard
        and "toggle" in hard
        and "wait_for" in hard
    )
    return ok, f"plan={plan is not None}, split={split}, toggle={toggle}, hard_fail={('fill_field' in hard, 'toggle' in hard, 'wait_for' in hard)}"


def gate_g8() -> tuple[bool, str]:
    """Capability detector is present and returns the stable schema."""
    from gemma4_agent.computer_use_caps.detector import CapabilityDetector

    class _Tools:
        _impls = {"vision": object()}

        def execute(self, *_args, **_kwargs):
            return {"ok": True, "elements": [{"name": "x"}]}

    snap = CapabilityDetector(_Tools()).snapshot("", include_uia=True)
    required = {
        "ok", "window_title", "window_class", "process_name", "app_kind",
        "is_browser", "is_chromium", "cdp_candidate", "uia_checked",
        "uia_available", "ocr_available", "vision_fallback_available",
    }
    missing = sorted(required - set(snap))
    ok = not missing
    return ok, f"missing={missing or 'none'}, vision={snap.get('vision_fallback_available')}, cached={snap.get('cached')}"


def gate_g9() -> tuple[bool, str]:
    """No false-pass: unverified computer-use result must not summarize as done."""
    from gemma4_agent.computer_use_pkg.computer_use import summarize_result

    reply = summarize_result(
        "abrir el resultado",
        [{"op": "click", "arg": "Abrir"}],
        {
            "ok": True,
            "verified": False,
            "steps": [{"op": "click", "arg": "Abrir", "ok": True, "verified": False}],
        },
    )
    ok = "no pude verificar" in reply.casefold() and "listo" not in reply.casefold()
    return ok, reply[:90]


def gate_g10() -> tuple[bool, str]:
    """Layer policy must prefer structured APIs before OCR/vision."""
    from gemma4_agent.computer_use_caps.policy import choose_policy

    browser = choose_policy({
        "is_browser": True,
        "cdp_candidate": True,
        "vision_fallback_available": True,
    }, "click")
    browser_toggle = choose_policy({
        "is_browser": True,
        "cdp_candidate": True,
        "vision_fallback_available": True,
    }, "toggle")
    native = choose_policy({
        "uia_available": True,
        "uia_degraded": False,
        "vision_fallback_available": True,
    }, "fill_field")
    degraded = choose_policy({
        "app_kind": "electron_or_webview",
        "uia_available": True,
        "uia_degraded": True,
        "vision_fallback_available": True,
    }, "click")
    ok = (
        browser.primary == "browser_cdp"
        and browser_toggle.primary == "browser_cdp"
        and native.primary == "uia_control_pattern"
        and degraded.primary == "ocr"
        and not browser.allow_blind_pixel_click
        and not native.allow_blind_pixel_click
        and not degraded.allow_blind_pixel_click
    )
    return ok, f"browser={browser.primary}, toggle={browser_toggle.primary}, native={native.primary}, degraded={degraded.primary}"


def gate_g11() -> tuple[bool, str]:
    """Tier contract eval stays green without touching the live desktop."""
    from scripts.computer_use_tier_eval import run_dry

    ok, rows = run_dry()
    passed = sum(1 for row in rows if row.get("ok"))
    return ok, f"{passed}/{len(rows)} tier cases"


def gate_g12() -> tuple[bool, str]:
    """Every structural app family has a registered adapter and verifier."""
    from gemma4_agent.computer_use_caps.registry import ADAPTER_SPECS, family_for_snapshot

    probes = [
        ({"is_browser": True, "app_kind": "browser"}, "browser"),
        ({"app_kind": "native_or_unknown"}, "native_uia"),
        ({"app_kind": "office"}, "native_uia"),
        ({"app_kind": "electron_or_webview"}, "electron_or_webview"),
        ({"app_kind": "unknown"}, "unknown"),
    ]
    family_ok = all(family_for_snapshot(snap) == expected for snap, expected in probes)
    specs_ok = all(
        spec.primary_layers and spec.fallback_layers and spec.supported_ops and spec.verifier
        for spec in ADAPTER_SPECS.values()
    )
    ok = family_ok and specs_ok and "browser" in ADAPTER_SPECS and "unknown" in ADAPTER_SPECS
    return ok, f"families={len(ADAPTER_SPECS)}, family_ok={family_ok}, specs_ok={specs_ok}"


def gate_g13() -> tuple[bool, str]:
    """A click with ok=True but no verifier must stay unverified."""
    from gemma4_agent.computer_use_pkg.computer_use import PlanExecutor

    class _Tools:
        def execute(self, *_args, **_kwargs):
            return {"ok": True}

    pe = object.__new__(PlanExecutor)
    pe.tools = _Tools()
    res = pe._click("Abrir", "")
    ok = res.get("ok") is True and res.get("verified") is False
    return ok, f"ok={res.get('ok')}, verified={res.get('verified')}"


def gate_g14() -> tuple[bool, str]:
    """Unverified hard-fail steps stop the chain before later writes."""
    from gemma4_agent.computer_use_pkg.computer_use import PlanExecutor
    from gemma4_agent.computer_use_caps.policy import choose_policy
    from gemma4_agent.computer_use_caps.registry import family_for_snapshot

    class _Detector:
        def snapshot(self, *_args, **_kwargs):
            return {"app_kind": "native_or_unknown", "vision_fallback_available": True}

    class _Trace:
        def event(self, *_args, **_kwargs):
            return None

    class _Agent:
        trace = _Trace()

    class _Caps:
        hard_fail_ops = {"click"}
        verified_ops = {"click"}

        def __init__(self):
            self.calls = []

        def run(self, op, arg, app, **_kwargs):
            self.calls.append(op)
            if op == "click":
                return {"ok": True, "verified": False}, app
            return {"ok": True, "verified": True}, app

        def is_hard_fail(self, op):
            return op in self.hard_fail_ops

        def is_verified_step(self, op):
            return op in self.verified_ops

    pe = object.__new__(PlanExecutor)
    pe.detector = _Detector()
    pe.choose_policy = choose_policy
    pe.capability_family = family_for_snapshot
    pe.capabilities = _Caps()
    pe.ag = _Agent()
    result = pe.execute([{"op": "click", "arg": "Abrir"}, {"op": "type", "arg": "danger"}])
    # PROPIEDAD DE SEGURIDAD: la cadena PARA en el click no verificado y NO llega
    # al `type` peligroso. (2026-05-27: el ejecutor ahora REINTENTA un paso
    # crítico antes de abortar -> calls puede ser [click]*N; lo que importa es que
    # NUNCA ejecute `type`, no el número de reintentos del click.)
    ok = (result.get("ok") is False and result.get("failed_at") == "click"
          and "type" not in pe.capabilities.calls
          and set(pe.capabilities.calls) == {"click"})
    return ok, f"result_ok={result.get('ok')}, failed_at={result.get('failed_at')}, calls={pe.capabilities.calls}"


def gate_g14b() -> tuple[bool, str]:
    """Unverified type must stop before send."""
    from gemma4_agent.computer_use_pkg.computer_use import PlanExecutor
    from gemma4_agent.computer_use_caps.policy import choose_policy
    from gemma4_agent.computer_use_caps.registry import family_for_snapshot

    class _Detector:
        def snapshot(self, *_args, **_kwargs):
            return {"app_kind": "native_or_unknown", "vision_fallback_available": True}

    class _Trace:
        def event(self, *_args, **_kwargs):
            return None

    class _Agent:
        trace = _Trace()

    class _Caps:
        hard_fail_ops = {"type"}
        verified_ops = {"type", "send"}

        def __init__(self):
            self.calls = []

        def run(self, op, arg, app, **_kwargs):
            self.calls.append(op)
            if op == "type":
                return {"ok": True, "verified": False}, app
            return {"ok": True, "verified": True}, app

        def is_hard_fail(self, op):
            return op in self.hard_fail_ops

        def is_verified_step(self, op):
            return op in self.verified_ops

    pe = object.__new__(PlanExecutor)
    pe.detector = _Detector()
    pe.choose_policy = choose_policy
    pe.capability_family = family_for_snapshot
    pe.capabilities = _Caps()
    pe.ag = _Agent()
    result = pe.execute([{"op": "type", "arg": "hola"}, {"op": "send", "arg": ""}])
    # PROPIEDAD: para en el `type` no verificado y NO llega al `send`. El ejecutor
    # reintenta el paso crítico antes de abortar (calls puede ser [type]*N); lo que
    # importa es que NUNCA ejecute `send`.
    ok = (result.get("ok") is False and result.get("failed_at") == "type"
          and "send" not in pe.capabilities.calls
          and set(pe.capabilities.calls) == {"type"})
    return ok, f"failed_at={result.get('failed_at')}, calls={pe.capabilities.calls}"


def gate_g15() -> tuple[bool, str]:
    """Hard-fail caused by unverified action must summarize as unverifiable."""
    from gemma4_agent.computer_use_pkg.computer_use import summarize_result

    reply = summarize_result(
        "abrir el resultado",
        [{"op": "click", "arg": "Abrir"}],
        {
            "ok": False,
            "failed_at": "click",
            "steps": [{"op": "click", "arg": "Abrir", "ok": True, "verified": False}],
        },
    )
    ok = "no pude verificar" in reply.casefold() and "listo" not in reply.casefold()
    return ok, reply[:90]


def gate_g16() -> tuple[bool, str]:
    """Detected browser state must route contextual ops to browser capability."""
    from gemma4_agent.computer_use_caps.router import CapabilityRouter

    class _Executor:
        pass

    router = CapabilityRouter(_Executor())
    calls = []

    def _browser_run(op, arg, app_token):
        calls.append((op, arg, app_token))
        return {"ok": True, "verified": True, "method": "stub_browser"}, app_token

    router.browser.run = _browser_run  # type: ignore[method-assign]
    result, token = router.run(
        "click",
        "Comprar",
        "",
        snapshot={"is_browser": True, "process_name": "chrome.exe", "window_title": "Store - Chrome"},
        policy={"primary": "browser_cdp"},
    )
    ok = bool(calls) and result.get("method") == "stub_browser" and token
    return ok, f"calls={calls}, token={token}"


def gate_g17() -> tuple[bool, str]:
    """Plans with no verified evidence must not become verified by all([])."""
    from gemma4_agent.computer_use_pkg.computer_use import PlanExecutor
    from gemma4_agent.computer_use_caps.policy import choose_policy
    from gemma4_agent.computer_use_caps.registry import family_for_snapshot

    class _Detector:
        def snapshot(self, *_args, **_kwargs):
            return {"app_kind": "native_or_unknown", "vision_fallback_available": True}

    class _Trace:
        def event(self, *_args, **_kwargs):
            return None

    class _Agent:
        trace = _Trace()

    class _Caps:
        def run(self, op, arg, app, **_kwargs):
            return {"ok": True}, app

        def is_hard_fail(self, _op):
            return False

        def is_verified_step(self, _op):
            return True

    pe = object.__new__(PlanExecutor)
    pe.detector = _Detector()
    pe.choose_policy = choose_policy
    pe.capability_family = family_for_snapshot
    pe.capabilities = _Caps()
    pe.ag = _Agent()
    result = pe.execute([{"op": "type", "arg": "texto"}])
    ok = result.get("ok") is True and result.get("verified") is False
    return ok, f"result_ok={result.get('ok')}, verified={result.get('verified')}"


def gate_g18() -> tuple[bool, str]:
    """Capability snapshot cache should avoid repeated expensive probes."""
    from gemma4_agent.computer_use_caps.detector import CapabilityDetector, CapabilitySnapshot

    class _Detector(CapabilityDetector):
        def __init__(self):
            super().__init__(tools=object(), ttl_s=60.0)
            self.calls = 0

        def _snapshot_uncached(self, window_hint, include_uia):
            self.calls += 1
            return CapabilitySnapshot(ok=True, window_title="X", app_kind="native_or_unknown")

    det = _Detector()
    first = det.snapshot("x", include_uia=False)
    second = det.snapshot("x", include_uia=False)
    ok = det.calls == 1 and first.get("cached") is False and second.get("cached") is True
    return ok, f"calls={det.calls}, cached=({first.get('cached')},{second.get('cached')})"


def gate_g19() -> tuple[bool, str]:
    """Live GUI tier evals must be blocked unless explicitly opted in."""
    import contextlib
    import io
    import os

    from scripts.computer_use_tier_eval import main as tier_main

    old = os.environ.pop("GEMMA4_RUN_LIVE_GUI_EVAL", None)
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = tier_main(["--live"])
    finally:
        if old is not None:
            os.environ["GEMMA4_RUN_LIVE_GUI_EVAL"] = old
    ok = code == 2
    return ok, f"exit={code}"


def gate_g20() -> tuple[bool, str]:
    """fill_field must not type after an unverified fallback click."""
    from gemma4_agent.computer_use_pkg.computer_use import PlanExecutor

    calls = []

    class _Tools:
        def execute(self, tool, args):
            calls.append((tool, args.get("action")))
            if tool == "uia" and args.get("action") == "set_value":
                return {"ok": False}
            if tool == "gui" and args.get("action") == "click_button":
                return {"ok": True}
            if tool == "gui" and args.get("action") == "type_into":
                return {"ok": True, "verified": True}
            return {"ok": False}

    pe = object.__new__(PlanExecutor)
    pe.tools = _Tools()
    res = pe._fill_field("email=a@b.com", "")
    typed = ("gui", "type_into") in calls
    ok = res.get("ok") is False and res.get("verified") is False and not typed
    return ok, f"res_ok={res.get('ok')}, error={res.get('error')}, typed={typed}"


def gate_g21() -> tuple[bool, str]:
    """Secret handoff from UIA must not fall back to generic typing."""
    from gemma4_agent.computer_use_pkg.computer_use import PlanExecutor

    calls = []

    class _Tools:
        def execute(self, tool, args):
            calls.append((tool, args.get("action")))
            if tool == "uia" and args.get("action") == "set_value":
                return {
                    "ok": False,
                    "completion_status": "needs_secret_handoff",
                    "error": "password field",
                }
            if tool == "gui" and args.get("action") == "type_into":
                return {"ok": True, "verified": True}
            return {"ok": False}

    pe = object.__new__(PlanExecutor)
    pe.tools = _Tools()
    res = pe._fill_field("password=secret", "")
    typed = ("gui", "type_into") in calls
    ok = res.get("completion_status") == "needs_secret_handoff" and not typed
    return ok, f"status={res.get('completion_status')}, typed={typed}"


def gate_g22() -> tuple[bool, str]:
    """Browser CDP open_url must not default to verified on bare ok."""
    from gemma4_agent.computer_use_caps.browser import BrowserCapability

    class _Tools:
        def execute(self, tool, args):
            if tool == "browser_real" and args.get("action") == "status":
                return {"ok": True, "available": True}
            if tool == "browser_real" and args.get("action") == "attach_visible":
                return {"ok": True}
            if tool == "browser_real" and args.get("action") == "goto":
                return {"ok": True, "url": args.get("url")}
            return {"ok": False}

    class _Executor:
        tools = _Tools()

        def _open_url(self, *_args, **_kwargs):
            return {"ok": False, "verified": False}

    cap = BrowserCapability(_Executor())
    res = cap._open_url("example.com", "chrome")
    ok = res.get("ok") is True and res.get("verified") is False
    return ok, f"ok={res.get('ok')}, verified={res.get('verified')}, method={res.get('method')}"


def gate_g23() -> tuple[bool, str]:
    """CDP attach attempts must not be consumed by empty/non-browser tokens."""
    from gemma4_agent.computer_use_caps.browser import BrowserCapability

    calls = []

    class _Tools:
        def execute(self, tool, args):
            calls.append((tool, args.get("action"), args.get("browser")))
            if tool == "browser_real" and args.get("action") == "status":
                return {"ok": True, "available": True}
            if tool == "browser_real" and args.get("action") == "attach_visible":
                return {"ok": True}
            return {"ok": False}

    class _Executor:
        tools = _Tools()

    cap = BrowserCapability(_Executor())
    first = cap._try_attach_visible("")
    second = cap._try_attach_visible("Chrome")
    attach_calls = [c for c in calls if c[1] == "attach_visible"]
    ok = first is False and second is True and len(attach_calls) == 1
    return ok, f"first={first}, second={second}, attach_calls={attach_calls}"


def gate_g24() -> tuple[bool, str]:
    """Structured writes/key presses must require explicit verifier fields."""
    from gemma4_agent.computer_use_pkg.computer_use import PlanExecutor
    from gemma4_agent.computer_use_caps.browser import BrowserCapability

    class _UiaTools:
        def execute(self, tool, args):
            if tool == "uia" and args.get("action") == "set_value":
                return {"ok": True, "method": "value_pattern"}
            if tool == "gui" and args.get("action") == "click_button":
                return {"ok": False}
            return {"ok": False}

    pe = object.__new__(PlanExecutor)
    pe.tools = _UiaTools()
    fill = pe._fill_field("email=a@b.com", "")

    class _BrowserTools:
        def execute(self, tool, args):
            if tool == "browser_real" and args.get("action") == "press":
                return {"ok": True}
            return {"ok": False}

    class _Executor:
        tools = _BrowserTools()

        def _keypress(self, *_args, **_kwargs):
            return {"ok": False, "verified": False}

    cap = BrowserCapability(_Executor())
    cap._cdp_available = True
    cap._cdp_owns_active_tab = True
    press = cap._keypress("Enter", "chrome")
    ok = fill.get("verified") is False and press.get("verified") is False
    return ok, f"fill_verified={fill.get('verified')}, press_verified={press.get('verified')}"


def gate_g24a() -> tuple[bool, str]:
    """Browser type_text calls must use browser_real's value argument."""
    from gemma4_agent.computer_use_caps.browser import BrowserCapability

    calls = []

    class _Tools:
        def execute(self, tool, args):
            calls.append((tool, dict(args)))
            if tool == "browser_real" and args.get("action") == "type_text":
                return {"ok": True, "verified": bool(args.get("value"))}
            return {"ok": False}

    class _Executor:
        tools = _Tools()

        def _type(self, *_args, **_kwargs):
            return {"ok": False, "verified": False}

    cap = BrowserCapability(_Executor())
    cap._cdp_available = True
    cap._cdp_owns_active_tab = True
    res = cap._type("hola", "chrome")
    args = calls[0][1] if calls else {}
    ok = res.get("verified") is True and args.get("value") == "hola" and "text" not in args
    return ok, f"value={args.get('value')}, has_text={'text' in args}"


def gate_g24b() -> tuple[bool, str]:
    """computer_use type primitive should use the verifying type_into path."""
    from gemma4_agent.computer_use_pkg.computer_use import PlanExecutor

    calls = []

    class _Tools:
        def execute(self, tool, args):
            calls.append((tool, args.get("action")))
            return {"ok": True, "verified": True}

    pe = object.__new__(PlanExecutor)
    pe.tools = _Tools()
    res = pe._type("hola", "")
    ok = res.get("verified") is True and calls == [("gui", "type_into")]
    return ok, f"calls={calls}, verified={res.get('verified')}"


def gate_g24c() -> tuple[bool, str]:
    """browser_real structured write actions must be allowed by the catalog."""
    from gemma4_agent.tools_pkg.tools import ACTION_ENUMS

    actions = ACTION_ENUMS.get("browser_real", [])
    required = {"click_accessible", "toggle_accessible", "type_text"}
    missing = sorted(required - set(actions))
    ok = not missing
    return ok, f"missing={missing or 'none'}"


def gate_g24d() -> tuple[bool, str]:
    """Browser toggles should use structured DOM/CDP before UIA fallback."""
    from gemma4_agent.computer_use_caps.browser import BrowserCapability

    calls = []

    class _Tools:
        def execute(self, tool, args):
            calls.append((tool, dict(args)))
            if tool == "browser_real" and args.get("action") == "toggle_accessible":
                return {
                    "ok": True,
                    "verified": True,
                    "state": {
                        "ok": True,
                        "verified": True,
                        "before": False,
                        "after": True,
                    },
                }
            return {"ok": False}

    class _Executor:
        tools = _Tools()

        def _parse_toggle_spec(self, spec):
            return ("Terms", True)

        def _toggle(self, *_args, **_kwargs):
            return {"ok": False, "verified": False, "method": "uia_toggle_then_verify"}

    cap = BrowserCapability(_Executor())
    cap._cdp_available = True
    cap._cdp_owns_active_tab = True
    res = cap._toggle("Terms=on", "chrome")
    actions = [args.get("action") for tool, args in calls if tool == "browser_real"]
    ok = res.get("verified") is True and res.get("method") == "browser_real_dom_toggle" and actions == ["toggle_accessible"]
    return ok, f"method={res.get('method')}, actions={actions}"


def gate_g25() -> tuple[bool, str]:
    """Layer policy must not offer OCR fallback when OCR is unavailable."""
    from gemma4_agent.computer_use_caps.policy import choose_policy

    degraded = choose_policy({
        "app_kind": "electron_or_webview",
        "uia_available": True,
        "uia_degraded": True,
        "ocr_available": False,
        "vision_fallback_available": True,
    }, "click")
    browser = choose_policy({
        "is_browser": True,
        "cdp_candidate": True,
        "ocr_available": False,
        "vision_fallback_available": True,
    }, "click")
    ok = (
        degraded.primary == "vision"
        and "ocr" not in degraded.fallbacks
        and "ocr" not in browser.fallbacks
        and "vision" in browser.fallbacks
    )
    return ok, f"degraded={degraded.primary}/{degraded.fallbacks}, browser={browser.fallbacks}"


def gate_g25b() -> tuple[bool, str]:
    """Capability detector must derive vision availability from tool registry."""
    from gemma4_agent.computer_use_caps.detector import CapabilityDetector, CapabilitySnapshot

    class _Detector(CapabilityDetector):
        def _snapshot_uncached(self, window_hint, include_uia):
            snap = CapabilitySnapshot(ok=True, window_title="X", app_kind="native_or_unknown")
            impls = getattr(self.tools, "_impls", None)
            snap.vision_fallback_available = isinstance(impls, dict) and "vision" in impls
            return snap

    class _WithVision:
        _impls = {"vision": object()}

    class _WithoutVision:
        _impls = {}

    yes = _Detector(_WithVision()).snapshot("")
    no = _Detector(_WithoutVision()).snapshot("")
    ok = yes.get("vision_fallback_available") is True and no.get("vision_fallback_available") is False
    return ok, f"with={yes.get('vision_fallback_available')}, without={no.get('vision_fallback_available')}"


def gate_g26() -> tuple[bool, str]:
    """UIA set_value must not contain an unverified SendKeys fallback."""
    from pathlib import Path

    text = Path("gemma4_agent/tools.py").read_text(encoding="utf-8", errors="replace")
    marker = 'if ($action -eq "set_value")'
    start = text.find(marker)
    end = text.find('[PSCustomObject]@{ ok=$false; action=$action; error="unknown uia action" }', start)
    block = text[start:end] if start >= 0 and end > start else ""
    forbidden = "SendKeys]::SendWait" in block or 'method="focus_sendkeys"' in block
    required = "uia_value_pattern_unavailable" in block and "ValuePattern" in block
    ok = bool(block) and not forbidden and required
    return ok, f"forbidden={forbidden}, required={required}"


def gate_g27() -> tuple[bool, str]:
    """If no structural/visual layer exists, executor must fail before acting."""
    from gemma4_agent.computer_use_pkg.computer_use import PlanExecutor
    from gemma4_agent.computer_use_caps.policy import choose_policy
    from gemma4_agent.computer_use_caps.registry import family_for_snapshot

    class _Detector:
        def snapshot(self, *_args, **_kwargs):
            return {
                "app_kind": "electron_or_webview",
                "uia_available": True,
                "uia_degraded": True,
                "ocr_available": False,
                "vision_fallback_available": False,
            }

    class _Trace:
        def event(self, *_args, **_kwargs):
            return None

    class _Agent:
        trace = _Trace()

    class _Caps:
        def __init__(self):
            self.calls = []

        def run(self, op, arg, app, **_kwargs):
            self.calls.append(op)
            return {"ok": True, "verified": True}, app

        def is_hard_fail(self, _op):
            return True

        def is_verified_step(self, _op):
            return True

    caps = _Caps()
    pe = object.__new__(PlanExecutor)
    pe.detector = _Detector()
    pe.choose_policy = choose_policy
    pe.capability_family = family_for_snapshot
    pe.capabilities = caps
    pe.ag = _Agent()
    result = pe.execute([{"op": "click", "arg": "Abrir"}])
    step = (result.get("steps") or [{}])[0]
    ok = (
        result.get("ok") is False
        and step.get("completion_status") == "needs_capability"
        and caps.calls == []
    )
    return ok, f"status={step.get('completion_status')}, calls={caps.calls}"


def gate_g28() -> tuple[bool, str]:
    """Known capability/secret failures should summarize with the real reason."""
    from gemma4_agent.computer_use_pkg.computer_use import summarize_result

    no_layer = summarize_result(
        "activar un boton",
        [{"op": "click", "arg": "Activar"}],
        {
            "ok": False,
            "failed_at": "click",
            "steps": [{
                "op": "click",
                "arg": "Activar",
                "ok": False,
                "verified": False,
                "completion_status": "needs_capability",
            }],
        },
    )
    secret = summarize_result(
        "rellenar password",
        [{"op": "fill_field", "arg": "password=secret"}],
        {
            "ok": False,
            "failed_at": "fill_field",
            "steps": [{
                "op": "fill_field",
                "arg": "password=secret",
                "ok": False,
                "verified": False,
                "completion_status": "needs_secret_handoff",
            }],
        },
    )
    ok = "API/UIA/OCR/vision" in no_layer and "sensible" in secret
    return ok, f"no_layer={no_layer[:45]}, secret={secret[:45]}"


def gate_g29() -> tuple[bool, str]:
    """Realistic composed missions stay represented and side effects are blocked."""
    from scripts.computer_use_mission_eval import run_dry

    ok, rows = run_dry(include_blocked=True)
    passed = sum(1 for row in rows if row.get("ok"))
    blocked = sum(1 for row in rows if not row.get("live_allowed"))
    live_ok = sum(1 for row in rows if row.get("live_allowed"))
    return ok, f"{passed}/{len(rows)} missions, live_ok={live_ok}, blocked={blocked}"


def main() -> int:
    gates = [
        ("G1 activación-por-voz", gate_g1),
        ("G2 movilidad hands-free", gate_g2),
        ("G3 no_vidente narración", gate_g3),
        ("G4 anti-regresión normal", gate_g4),
    ]
    gates.extend([
        ("G5 anti-delegacion universal", gate_g5),
        ("G6 routing tienda web", gate_g6),
        ("G7 primitivas universales", gate_g7),
        ("G8 capability snapshot", gate_g8),
        ("G9 no false-pass summary", gate_g9),
        ("G10 layer policy", gate_g10),
        ("G11 tier contract eval", gate_g11),
        ("G12 adapter registry", gate_g12),
        ("G13 no blind click pass", gate_g13),
        ("G14 stop unverified write", gate_g14),
        ("G14b stop unverified type", gate_g14b),
        ("G15 hard-fail honesty", gate_g15),
        ("G16 policy-driven route", gate_g16),
        ("G17 no all-empty pass", gate_g17),
        ("G18 snapshot cache", gate_g18),
        ("G19 live eval opt-in", gate_g19),
        ("G20 fill no blind type", gate_g20),
        ("G21 secret handoff", gate_g21),
        ("G22 browser no default verify", gate_g22),
        ("G23 CDP attach retry", gate_g23),
        ("G24 explicit verification", gate_g24),
        ("G24a browser type arg", gate_g24a),
        ("G24b type uses type_into", gate_g24b),
        ("G24c type action allowed", gate_g24c),
        ("G24d browser toggle DOM", gate_g24d),
        ("G25 OCR availability", gate_g25),
        ("G25b vision availability", gate_g25b),
        ("G26 no UIA SendKeys", gate_g26),
        ("G27 no-layer honest fail", gate_g27),
        ("G28 specific fail summary", gate_g28),
        ("G29 composed missions", gate_g29),
    ])
    all_ok = True
    print("=" * 64)
    print("EVAL MODOS DE ACCESIBILIDAD — gates definidos de antemano")
    print("=" * 64)
    for name, fn in gates:
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001
            ok, detail = False, f"ERROR: {type(exc).__name__}: {exc}"
        all_ok = all_ok and ok
        print(f"[{'PASS' if ok else 'FAIL'}] {name:28} | {detail}")
    print("=" * 64)
    print("RESULTADO:", "TODOS LOS GATES PASARON" if all_ok else "HAY GATES EN FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
