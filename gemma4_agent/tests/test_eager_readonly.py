"""Pre-ejecución EAGER de tools READ-ONLY (opt-in, 2026-06-02).

GATE (medido, sin LLM físico — todo mock/unit):
  1. NINGUNA tool con efectos se pre-ejecuta JAMÁS (tabla + clasificador de
     seguridad). Test que intenta colar una ESCRITURA y confirma que NO se
     dispara eager.
  2. El resultado eager se DESCARTA cuando el LLM elige otra tool/acción.
  3. FAIL-SAFE: si el eager falla/no terminó, el turno corre la tool normal
     (resultado idéntico al actual).
  4. Ahorro: el eager solapa la tool lenta con el pase-1 (simulado con sleeps).
  5. Gate GEMMA4_EAGER_READONLY default OFF (opt-in).

NO LLM, NO GUI/SendInput. Las tools read-only que se ejecutan son inocuas
(system.time/disk/battery via execute mockeado o real-pero-puro).
"""
from __future__ import annotations

import os
import threading
import time
import unittest
from unittest import mock

from gemma4_agent.agent_core import eager_readonly as E
from gemma4_agent.safety_pkg.safety import classify_tool_call


# Toda (tool, action) que el classifier de seguridad marca riesgosa (escritura).
# Probamos un muestreo amplio que cubre cada categoría de efecto del classifier.
WRITE_CALLS = [
    ("system", "shutdown", {}),
    ("system", "restart", {}),
    ("system", "sleep", {}),
    ("system", "brightness_set", {"level": 50}),
    ("audio", "set_volume", {"level": 30}),
    ("audio", "mute", {"state": True}),
    ("audio", "set_default", {"name": "x"}),
    ("filesystem", "delete", {"path": "x"}),
    ("filesystem", "write", {"path": "x", "content": "y"}),
    ("filesystem", "move", {"src": "a", "dst": "b"}),
    ("whatsapp", "send_message", {"contact": "mama", "text": "hola"}),
    ("email", "send", {"to": "a@b.c", "subject": "s", "body": "b"}),
    ("package", "install", {"name": "vlc"}),
    ("package", "uninstall", {"name": "vlc"}),
    ("app", "close", {"name": "steam"}),
    ("app", "uninstall", {"name": "steam"}),
    ("terminal", "run", {"command": "del", "args": ["x"]}),
    ("registry", "delete", {"key": "HKCU\\x"}),
    ("registry", "add", {"key": "HKCU\\x", "value": "1"}),
    ("notification", "alarm_create", {"time": "09:00"}),
    ("routine", "create", {"name": "r"}),
    ("contacts", "create", {"name": "x"}),
    ("notes_tasks", "note_create", {"text": "x"}),
    ("backup_sync", "restore", {"backup_id": "1"}),
    ("download", "fetch", {"url": "http://x"}),
    ("steam", "install", {"appid": "440"}),
    ("media", "play", {"query": "rock"}),
    ("browser", "open", {"url": "http://x"}),
    ("gui", "click", {"x": 1, "y": 1}),
    ("gui", "type", {"text": "rm -rf"}),
]


class TableIsTrulyReadOnly(unittest.TestCase):
    """Toda entrada de la tabla read-only DEBE ser clasificada NO-riesgosa por
    el clasificador de seguridad INDEPENDIENTE. Si esta falla, alguien metió en
    la tabla algo que el safety considera una escritura -> bug grave."""

    def test_every_table_entry_clears_safety_classifier(self) -> None:
        for (tool, action) in E.EAGER_READONLY_CALLS:
            decision = classify_tool_call(tool, {"action": action})
            self.assertFalse(
                decision.requires_confirmation,
                f"{tool}.{action} está en la tabla eager pero el classifier la "
                f"marca riesgosa: {decision.reason}")

    def test_table_is_small_and_only_system_reads(self) -> None:
        # Anti-creep: la tabla es chica a propósito. Si crece sin pasar este
        # gate, alguien debe re-justificar entrada por entrada.
        self.assertLessEqual(len(E.EAGER_READONLY_CALLS), 6)
        for (tool, action) in E.EAGER_READONLY_CALLS:
            self.assertEqual(tool, "system")
            self.assertIn(action, {"time", "cpu_ram_gpu", "disk", "battery"})


class NoWriteEverEager(unittest.TestCase):
    """REGLA DURA: ninguna escritura se pre-ejecuta JAMÁS."""

    def setUp(self) -> None:
        self._prev = os.environ.get("GEMMA4_EAGER_READONLY")
        os.environ["GEMMA4_EAGER_READONLY"] = "1"  # flag ON: el peor caso

    def tearDown(self) -> None:
        if self._prev is None:
            os.environ.pop("GEMMA4_EAGER_READONLY", None)
        else:
            os.environ["GEMMA4_EAGER_READONLY"] = self._prev

    def test_no_write_is_eager_safe(self) -> None:
        for (tool, action, args) in WRITE_CALLS:
            self.assertFalse(
                E.is_eager_safe(tool, action, args),
                f"{tool}.{action} fue marcada eager-safe — es una ESCRITURA")

    def test_no_write_appears_as_eager_candidate(self) -> None:
        # Aunque el router ofrezca la tool, ninguna ACCIÓN de escritura aparece
        # como candidata (las candidatas son solo las (tool, action) read-only).
        offered = {"system", "audio", "filesystem", "whatsapp", "email",
                   "package", "app", "terminal", "registry", "gui", "media",
                   "browser", "steam"}
        cands = E.eager_candidates(offered)
        for (tool, action) in cands:
            self.assertIn((tool, action), E.EAGER_READONLY_CALLS)
        # ninguna candidata es una de las escrituras conocidas
        write_pairs = {(t, a) for (t, a, _) in WRITE_CALLS}
        self.assertEqual(set(cands) & write_pairs, set())

    def test_smuggled_write_via_extra_args_is_rejected(self) -> None:
        # Intento de colar una escritura abusando de una accion read-only +
        # args con efecto (p.ej. system.time + level): NO debe ser eager-safe.
        self.assertFalse(E.is_eager_safe("system", "time", {"level": 50}))
        self.assertFalse(E.is_eager_safe("system", "battery", {"delay_sec": 10}))

    def test_cache_fire_never_executes_a_write(self) -> None:
        # El EagerReadOnlyCache.fire SOLO debe ejecutar (tool, action) read-only,
        # aunque le pasemos a la fuerza una lista con escrituras dentro.
        executed: list[tuple[str, str]] = []
        lock = threading.Lock()

        def fake_execute(name, args):
            with lock:
                executed.append((name, str(args.get("action"))))
            return {"ok": True}

        cache = E.EagerReadOnlyCache(fake_execute)
        # mezcla maliciosa: lecturas válidas + escrituras
        cache.fire([("system", "time"), ("system", "shutdown"),
                    ("filesystem", "delete"), ("audio", "set_volume")])
        for t in cache._threads:
            t.join(timeout=5)
        # SOLO la lectura válida se ejecutó
        self.assertIn(("system", "time"), executed)
        self.assertNotIn(("system", "shutdown"), executed)
        self.assertNotIn(("filesystem", "delete"), executed)
        self.assertNotIn(("audio", "set_volume"), executed)


class DefenseInDepthAgainstPoisonedTable(unittest.TestCase):
    """Si por bug/regresión alguien METE una escritura en la tabla read-only, la
    2da barrera (verbo-de-lectura estructural) DEBE bloquearla igual — porque el
    clasificador de seguridad SÓLO decide confirmación y deja pasar escrituras de
    bajo riesgo (audio.set_volume, media.play). Finding 2026-06-02."""

    def setUp(self) -> None:
        os.environ["GEMMA4_EAGER_READONLY"] = "1"
        self._orig = E.EAGER_READONLY_CALLS
        # envenenar la tabla con escrituras de distintos niveles de riesgo
        E.EAGER_READONLY_CALLS = frozenset(self._orig | {
            ("system", "shutdown"),         # alto riesgo
            ("audio", "set_volume"),        # BAJO riesgo (el classifier la deja pasar)
            ("media", "play"),              # bajo riesgo
            ("system", "brightness_set"),   # cambia un setting
            ("app", "open"),                # efecto observable
        })

    def tearDown(self) -> None:
        E.EAGER_READONLY_CALLS = self._orig
        os.environ.pop("GEMMA4_EAGER_READONLY", None)

    def test_poisoned_writes_are_not_eager_safe(self) -> None:
        for (tool, action) in [("system", "shutdown"), ("audio", "set_volume"),
                               ("media", "play"), ("system", "brightness_set"),
                               ("app", "open")]:
            self.assertFalse(
                E.is_eager_safe(tool, action, {}),
                f"{tool}.{action} pasó eager-safe pese a estar envenenada — la "
                f"2da barrera (verbo de lectura) falló")

    def test_fire_executes_only_pure_reads_from_poisoned_list(self) -> None:
        executed: list[tuple[str, str]] = []
        lock = threading.Lock()

        def fake_execute(name, args):
            with lock:
                executed.append((name, str(args.get("action"))))
            return {"ok": True}

        cache = E.EagerReadOnlyCache(fake_execute)
        cache.fire([("system", "shutdown"), ("audio", "set_volume"),
                    ("media", "play"), ("system", "brightness_set"),
                    ("app", "open"), ("system", "time"), ("system", "battery")])
        for t in cache._threads:
            t.join(timeout=5)
        # SOLO las lecturas puras se ejecutaron.
        self.assertEqual(set(executed), {("system", "time"), ("system", "battery")})


class EagerDiscardedWhenLLMPicksElse(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["GEMMA4_EAGER_READONLY"] = "1"

    def tearDown(self) -> None:
        os.environ.pop("GEMMA4_EAGER_READONLY", None)

    def test_get_returns_none_for_a_different_tool(self) -> None:
        cache = E.EagerReadOnlyCache(lambda n, a: {"ok": True, "iso": "now"})
        cache.fire([("system", "time")])
        for t in cache._threads:
            t.join(timeout=5)
        # el LLM pidió otra cosa -> no hay hit
        self.assertIsNone(cache.get("audio", "get_volume", {"action": "get_volume"}))
        self.assertIsNone(cache.get("system", "battery", {"action": "battery"}))
        # pero la que SÍ pre-ejecutamos da hit
        hit = cache.get("system", "time", {"action": "time"})
        self.assertIsInstance(hit, dict)
        self.assertEqual(hit.get("iso"), "now")

    def test_get_returns_none_when_args_carry_effects(self) -> None:
        cache = E.EagerReadOnlyCache(lambda n, a: {"ok": True})
        cache.fire([("system", "time")])
        for t in cache._threads:
            t.join(timeout=5)
        # el LLM pidió system.time pero con un arg con efecto -> NO servir cache
        self.assertIsNone(cache.get("system", "time", {"action": "time", "level": 9}))


class FailSafe(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["GEMMA4_EAGER_READONLY"] = "1"

    def tearDown(self) -> None:
        os.environ.pop("GEMMA4_EAGER_READONLY", None)

    def test_eager_exception_yields_no_cache_hit(self) -> None:
        # Si la tool eager revienta, NO hay resultado cacheado -> get() None ->
        # el caller corre la tool normal (turno idéntico al actual).
        def boom(name, args):
            raise RuntimeError("simulated tool failure")

        cache = E.EagerReadOnlyCache(boom)
        cache.fire([("system", "time")])
        for t in cache._threads:
            t.join(timeout=5)
        self.assertIsNone(cache.get("system", "time", {"action": "time"}))

    def test_get_before_thread_finishes_is_none(self) -> None:
        # El future aún no terminó -> get() None (no bloquea, no inventa).
        started = threading.Event()
        release = threading.Event()

        def slow(name, args):
            started.set()
            release.wait(timeout=5)
            return {"ok": True}

        cache = E.EagerReadOnlyCache(slow)
        cache.fire([("system", "time")])
        self.assertTrue(started.wait(timeout=5))
        self.assertIsNone(cache.get("system", "time", {"action": "time"}))
        release.set()
        for t in cache._threads:
            t.join(timeout=5)
        # ya terminó -> ahora sí hay hit
        self.assertIsInstance(cache.get("system", "time", {"action": "time"}), dict)


class Gating(unittest.TestCase):
    def test_default_off(self) -> None:
        os.environ.pop("GEMMA4_EAGER_READONLY", None)
        self.assertFalse(E.is_enabled())
        # con el flag OFF no hay candidatas, aunque la tool esté ofrecida
        self.assertEqual(E.eager_candidates(["system"]), [])

    def test_explicit_off_values(self) -> None:
        for val in ("0", "false", "no", "off", ""):
            os.environ["GEMMA4_EAGER_READONLY"] = val
            self.assertFalse(E.is_enabled(), f"{val!r} debería ser OFF")
        os.environ.pop("GEMMA4_EAGER_READONLY", None)

    def test_on_values(self) -> None:
        for val in ("1", "true", "yes", "on", "ON", "True"):
            os.environ["GEMMA4_EAGER_READONLY"] = val
            self.assertTrue(E.is_enabled(), f"{val!r} debería ser ON")
        os.environ.pop("GEMMA4_EAGER_READONLY", None)


def _encoder_available() -> bool:
    """True si el encoder multilingüe carga (sentence-transformers presente y
    descargable). Sin él, el afinamiento por intent cae al fallback (todas) — los
    tests de discriminación se saltan, NO fallan."""
    try:
        from gemma4_agent.routing.semantic_router import embed
        return embed("ping") is not None
    except Exception:
        return False


class IntentFilterFallsBackSafely(unittest.TestCase):
    """El afinamiento por intent NUNCA es peor que la versión previa: sin texto o
    sin encoder dispara TODAS las eager-safe del subset (no-op respecto al merge
    ya validado). No depende del encoder."""

    def setUp(self) -> None:
        os.environ["GEMMA4_EAGER_READONLY"] = "1"

    def tearDown(self) -> None:
        os.environ.pop("GEMMA4_EAGER_READONLY", None)

    def test_no_text_keeps_all_eager_safe(self) -> None:
        # Sin turn_text -> comportamiento previo: las 4 reads de system.
        cands = E.eager_candidates(["system"])
        self.assertEqual(
            set(cands),
            {("system", "time"), ("system", "cpu_ram_gpu"),
             ("system", "disk"), ("system", "battery")})

    def test_encoder_absent_keeps_all_eager_safe(self) -> None:
        # Si embed() devuelve None (encoder ausente), fallback a TODAS.
        with mock.patch("gemma4_agent.routing.semantic_router.embed",
                        return_value=None):
            cands = E.eager_candidates(["system"], "qué hora es")
        self.assertEqual(len(cands), 4)

    def test_filter_never_invents_a_candidate(self) -> None:
        # El filtro SOLO puede REDUCIR el set, nunca agregar algo fuera de la
        # tabla (defensa: ninguna escritura puede entrar por el intent).
        cands = E.eager_candidates(["system"], "cuánta batería queda")
        for c in cands:
            self.assertIn(c, E.EAGER_READONLY_CALLS)


@unittest.skipUnless(_encoder_available(),
                     "encoder multilingüe no disponible -> intent filter en fallback")
class IntentFilterFiresOnlyRelevantRead(unittest.TestCase):
    """GATE medido: el afinamiento dispara SOLO la(s) read que el turno sugiere,
    no las 4 de system siempre. Embeddings multilingües (no keywords es-only)."""

    def setUp(self) -> None:
        os.environ["GEMMA4_EAGER_READONLY"] = "1"

    def tearDown(self) -> None:
        os.environ.pop("GEMMA4_EAGER_READONLY", None)

    def test_time_question_fires_only_time(self) -> None:
        # GATE: "qué hora es" -> SOLO system.time (no las 4).
        for q in ("qué hora es", "what time is it", "quelle heure est-il"):
            cands = E.eager_candidates(["system"], q)
            self.assertEqual(
                cands, [("system", "time")],
                f"{q!r} disparó {cands}, esperaba solo system.time")

    def test_volume_turn_fires_zero_reads(self) -> None:
        # GATE: "subí el volumen" — system viaja en el subset junto a audio por
        # ser compound, pero el turno NO pide ninguna lectura -> 0 reads.
        for q in ("subí el volumen", "turn up the volume", "bajá el volumen"):
            cands = E.eager_candidates(["system", "audio"], q)
            self.assertEqual(cands, [], f"{q!r} disparó {cands}, esperaba 0 reads")

    def test_smalltalk_fires_zero_reads(self) -> None:
        # Smalltalk no se parece a ninguna lectura -> 0 (no desperdiciar).
        for q in ("hola cómo estás", "contame un chiste"):
            cands = E.eager_candidates(["system"], q)
            self.assertEqual(cands, [], f"{q!r} disparó {cands}, esperaba 0 reads")

    def test_shutdown_turn_fires_zero_reads(self) -> None:
        # Un pedido de apagar (escritura) no matchea ninguna lectura -> 0.
        cands = E.eager_candidates(["system"], "apaga la computadora")
        self.assertEqual(cands, [])

    def test_resource_questions_fire_their_own_read(self) -> None:
        # Cada consulta de recurso dispara SU lectura (no las 4).
        ram = E.eager_candidates(["system"], "cuánta RAM tengo")
        self.assertIn(("system", "cpu_ram_gpu"), ram)
        self.assertNotIn(("system", "time"), ram)
        disk = E.eager_candidates(["system"], "cuánto espacio libre en disco queda")
        self.assertIn(("system", "disk"), disk)
        bat = E.eager_candidates(["system"], "cuánta batería queda")
        self.assertIn(("system", "battery"), bat)

    def test_a_write_never_fires_even_with_matching_text(self) -> None:
        # SEGURIDAD: aunque el texto sea de "apagar", el intent jamás puede
        # introducir una escritura (shutdown no está en la tabla read-only).
        cands = E.eager_candidates(
            ["system"], "apaga reinicia suspende apaga la pc shutdown")
        write_pairs = {(t, a) for (t, a, _) in WRITE_CALLS}
        self.assertEqual(set(cands) & write_pairs, set())


class SavingsSimulation(unittest.TestCase):
    """Mide el AHORRO: la tool read-only (lenta) se solapa con el 'pase-1' del
    LLM, así que cuando el dispatch la pide el resultado ya está -> ~0 espera
    en vez de pagar la latencia de la tool."""

    def setUp(self) -> None:
        os.environ["GEMMA4_EAGER_READONLY"] = "1"

    def tearDown(self) -> None:
        os.environ.pop("GEMMA4_EAGER_READONLY", None)

    def test_eager_overlaps_tool_with_pass1(self) -> None:
        TOOL_COST = 0.25  # la tool read-only tarda 250ms
        PASS1_COST = 0.25  # el pase-1 del LLM tarda 250ms

        def slow_tool(name, args):
            time.sleep(TOOL_COST)
            return {"ok": True, "action": str(args.get("action"))}

        # --- camino EAGER ---
        cache = E.EagerReadOnlyCache(slow_tool)
        t0 = time.monotonic()
        cache.fire([("system", "time")])          # arranca en background
        time.sleep(PASS1_COST)                      # simula el pase-1 del LLM
        # el LLM pidió system.time: ya debería estar listo
        for t in cache._threads:
            t.join(timeout=5)
        hit = cache.get("system", "time", {"action": "time"})
        eager_total = time.monotonic() - t0
        self.assertIsInstance(hit, dict)

        # --- camino SIN eager (secuencial) ---
        t0 = time.monotonic()
        time.sleep(PASS1_COST)                      # pase-1
        slow_tool("system", {"action": "time"})     # luego la tool
        serial_total = time.monotonic() - t0

        # el eager debe ser MÁS RÁPIDO (la tool se solapó con el pase-1).
        self.assertLess(eager_total, serial_total)
        # ahorro >= ~la mitad del costo de la tool (margen por jitter de la box)
        self.assertGreater(serial_total - eager_total, TOOL_COST * 0.4)


class AgentIntegration(unittest.TestCase):
    """End-to-end por el agente real (LLM mockeado, sin GUI/SendInput): el
    resultado eager se SIRVE en el dispatch (la tool no se re-ejecuta) para una
    lectura, y NUNCA para una escritura."""

    def _make_agent(self, *, tool_call):
        import dataclasses
        import tempfile
        from pathlib import Path
        from gemma4_agent.agent_core.agent import Gemma4Agent
        from gemma4_agent.infra.config import AgentConfig

        tmp = Path(tempfile.mkdtemp(prefix="gemma4_eager_"))
        cfg = dataclasses.replace(
            AgentConfig.from_env(),
            memory_path=tmp / "m.json", captures_dir=tmp / "cap",
            trace_path=tmp / "t.jsonl", state_path=tmp / "s.json",
            enable_tracing=False, enable_safety=False,
        )
        a = Gemma4Agent(cfg)

        # primer pase: emite el tool_call; pases siguientes: prosa de cierre.
        state = {"calls": 0}

        def chat(messages, **kw):
            state["calls"] += 1
            if state["calls"] == 1 and tool_call is not None:
                return {"choices": [{
                    "message": {"role": "assistant", "content": "",
                                "tool_calls": [tool_call]},
                    "finish_reason": "tool_calls",
                }]}
            return {"choices": [{
                "message": {"role": "assistant", "content": "Listo.",
                            "tool_calls": []},
                "finish_reason": "stop",
            }]}

        a.client.chat = chat
        return a

    def setUp(self) -> None:
        os.environ["GEMMA4_EAGER_READONLY"] = "1"

    def tearDown(self) -> None:
        os.environ.pop("GEMMA4_EAGER_READONLY", None)

    def test_readonly_call_served_from_eager_not_reexecuted(self) -> None:
        tc = {"id": "c1", "type": "function",
              "function": {"name": "system", "arguments": '{"action": "time"}'}}
        a = self._make_agent(tool_call=tc)

        # contar cuántas veces execute('system', {action:time}) realmente corre.
        real_execute = a.tools.execute
        counts = {"time": 0}
        lock = threading.Lock()

        def counting_execute(name, args):
            if name == "system" and (args or {}).get("action") == "time":
                with lock:
                    counts["time"] += 1
            return real_execute(name, args)

        a.tools.execute = counting_execute
        # forzar que el router ofrezca `system` (sin depender del encoder).
        from gemma4_agent.agent_core import eager_readonly as _E
        orig_cands = _E.eager_candidates
        try:
            _E.eager_candidates = lambda subset: [("system", "time")]
            reply = a.run_content("qué hora es")
        finally:
            _E.eager_candidates = orig_cands

        # la lectura se ejecutó UNA sola vez (el eager precompute); el dispatch
        # sirvió ese resultado en vez de re-ejecutar -> count == 1, no 2.
        self.assertEqual(counts["time"], 1,
                         "system.time se ejecutó 2 veces -> el cache eager no se usó")
        # y el turno produjo un resultado de la tool (no se rompió).
        names = [e.name for e in reply.tool_events]
        self.assertIn("system", names)

    def test_write_call_is_always_dispatched_never_eager(self) -> None:
        # El LLM pide una ESCRITURA (brightness_set). Aunque el flag esté ON,
        # el eager JAMÁS la pre-ejecuta; el dispatch la corre normal (1 vez).
        tc = {"id": "c2", "type": "function",
              "function": {"name": "system",
                           "arguments": '{"action": "brightness_set", "level": 30}'}}
        a = self._make_agent(tool_call=tc)

        executed: list[tuple[str, str]] = []
        real_execute = a.tools.execute

        def recording_execute(name, args):
            executed.append((name, str((args or {}).get("action"))))
            # NO ejecutar de verdad el brillo: devolvemos un stub honesto.
            if name == "system" and (args or {}).get("action") == "brightness_set":
                return {"ok": False, "verified": False, "status": "attempted",
                        "tool": "system"}
            return real_execute(name, args)

        a.tools.execute = recording_execute
        from gemma4_agent.agent_core import eager_readonly as _E
        orig_cands = _E.eager_candidates
        try:
            # Forzamos candidatas REALES de la tool `system` pero acotadas a la
            # lectura instantánea time (para que el test sea rápido): el punto es
            # que brightness_set (escritura) NUNCA está entre las candidatas.
            _real = orig_cands(["system"])
            self.assertNotIn(("system", "brightness_set"), _real)
            _E.eager_candidates = lambda subset: [("system", "time")]
            reply = a.run_content("bajá el brillo a 30")
        finally:
            _E.eager_candidates = orig_cands

        # brightness_set se ejecutó EXACTAMENTE una vez (el dispatch normal),
        # nunca de forma eager (que habría sido una 2da ejecución o un cambio
        # de brillo durante el pase-1). El eager pudo precomputar lecturas
        # inocuas (time/battery) pero NUNCA la escritura.
        bset = [e for e in executed if e == ("system", "brightness_set")]
        self.assertEqual(len(bset), 1,
                         "brightness_set se ejecutó != 1 vez (eager tocó una escritura)")


if __name__ == "__main__":
    unittest.main()
