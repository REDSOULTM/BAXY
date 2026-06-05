"""Regresión de los 4 fixes de la auditoría del sistema de tools (2026-06-01).

La auditoría multi-agente (workflow gemma4-tools-audit) halló 4 defectos reales,
todos verificados adversarialmente contra el código. Este archivo congela su fix
para que no reaparezcan:

  1. CRÍTICO — `confirmed="false"` (STRING) salteaba el safety gate porque
     bool("false")==True. Mismo bug-class ya arreglado para `state` del mute pero
     NO propagado a `confirmed`. (tools.py:execute)
  2. CRÍTICO — smart_home set_state/call_service reportaban verified=True con solo
     HTTP 200, sin medir el cambio real de estado. (smart_home.py)
  3. MEDIUM — media.play de archivo local reportaba verified=True tras os.startfile
     (que NO indica éxito). (domain_tools/__init__.py:_media_play_local)
  4. HIGH — _looks_like_music_request / _is_generic_song_query usaban listas de
     keywords es/en que rompían a hablantes de it/pt/de/fr/sv/nl. Ahora delegan en
     el detector estructural multilingüe por raíces. (Ley de producto #1/#3.)
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("GEMMA4_LLAMA_AUTO_START", "0")

from ..tools_pkg.tools import (
    ToolRegistry,
    ACTION_ENUMS,
    COMPOUND_TOOL_SCHEMAS,
    _looks_like_music_request,
    _is_generic_song_query,
)
from ..safety_pkg.safety import classify_mcp_call
from ..safety_pkg.confirmation_policy import should_confirm
from ..memory_pkg.memory import MemoryStore
from ..memory_pkg.state import AgentState
from ..tools_pkg.ops_tools import registry_tool
import gemma4_agent.tools_pkg.ops_tools as ot
import gemma4_agent.domain_tools as dt
import gemma4_agent.tools_pkg.mcp_client as mc
# smart_home ELIMINADA 2026-06-02 — TestSmartHomeHonesty removida con la tool.


class TestConfirmedStringCoercion(unittest.TestCase):
    """Fix #1 (2026-06-01) — el flag `confirmed` como STRING no debe saltear el gate.
    Fix #2 (2026-06-05, juez cacería t1-4) — NINGÚN `confirmed` AUTO-EMITIDO por el LLM
    (ni "true") saltea el gate de operaciones irreversibles: el 4B aprendió a auto-
    confirmar (medido 15 casos, incl "borra todo en C:/"). La confirmación VÁLIDA solo
    llega por el canal interno `_confirmed_by_gate` (flujo safety(confirm) tras un
    round-trip real del usuario), que el LLM no puede falsificar."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.reg = ToolRegistry(
            MemoryStore(self.tmp / "mem.json"), self.tmp / "caps", safety_enabled=True
        )

    def _delete_call(self, confirmed_value):
        victim = self.tmp / f"victim_{id(confirmed_value)}_{confirmed_value!r}.txt"
        victim.write_text("data")
        res = self.reg.execute(
            "filesystem",
            {"action": "delete", "path": str(victim), "confirmed": confirmed_value},
        )
        return res, victim

    def test_string_false_blocks_and_preserves_file(self):
        res, victim = self._delete_call("false")
        self.assertEqual(res.get("status"), "needs_confirmation")
        self.assertTrue(victim.exists(), "el archivo NO debe borrarse con confirmed='false'")

    def test_string_negatives_block(self):
        for val in ("no", "0", "off", ""):
            res, victim = self._delete_call(val)
            self.assertEqual(res.get("status"), "needs_confirmation", f"confirmed={val!r}")
            self.assertTrue(victim.exists(), f"confirmed={val!r} no debe borrar")

    def test_bool_false_blocks(self):
        res, victim = self._delete_call(False)
        self.assertEqual(res.get("status"), "needs_confirmation")
        self.assertTrue(victim.exists())

    def test_llm_confirmed_true_still_gated(self):
        # FIX #2: el `confirmed` AUTO-EMITIDO por el LLM (incluso "true"/True) NO
        # saltea el gate de una op irreversible — pide confirmación real. Antes
        # procedía (bypass medido en la cacería).
        for val in ("true", True, "yes", "1"):
            res, victim = self._delete_call(val)
            self.assertEqual(res.get("status"), "needs_confirmation",
                              f"confirmed={val!r} del LLM NO debe saltear el gate")
            self.assertTrue(victim.exists(),
                            f"confirmed={val!r} del LLM no debe borrar sin confirmación real")

    def test_real_gate_confirmation_proceeds(self):
        # La confirmación REAL (canal interno `_confirmed_by_gate`, vía safety(confirm))
        # SÍ procede — es el round-trip legítimo del usuario, no falsificable por el LLM.
        victim = self.tmp / "victim_gate.txt"
        victim.write_text("data")
        res = self.reg.execute(
            "filesystem",
            {"action": "delete", "path": str(victim), "_confirmed_by_gate": True},
        )
        self.assertNotEqual(res.get("status"), "needs_confirmation")
        self.assertFalse(victim.exists(), "_confirmed_by_gate debe proceder con el borrado")


class TestMediaLocalHonesty(unittest.TestCase):
    """Fix #3 — os.startfile no es medible -> verified=None, no True."""

    def test_local_file_play_is_not_verified_true(self):
        tmp = Path(tempfile.mkdtemp())
        f = tmp / "song.mp3"
        f.write_bytes(b"\x00")
        with mock.patch("os.startfile", create=True) as ms:
            r = dt._media_play_local(str(f), {"path": str(f)})
        self.assertTrue(ms.called)
        self.assertIsNone(r.get("verified"), "os.startfile no es medible -> verified=None")
        self.assertEqual(r.get("status"), "dispatched")


class TestMusicDetectionMultilingual(unittest.TestCase):
    """Fix #4 — detección de música estructural multilingüe (no keywords es/en)."""

    def test_generic_music_query_covers_many_languages(self):
        generic = [
            "pon una cancion",        # es
            "play some music",        # en
            "riproduci una canzone",  # it
            "metti una canzone",      # it
            "reproduz uma musica",    # pt
            "spiele musik",           # de
            "spela musik",            # sv
            "",                       # vacío
            "musica",
        ]
        for q in generic:
            self.assertTrue(_is_generic_song_query(q), f"{q!r} debería ser genérico")

    def test_titled_query_is_not_generic(self):
        for q in ("pon despacito", "reproduce bohemian rhapsody de queen", "play bad bunny"):
            self.assertFalse(_is_generic_song_query(q), f"{q!r} tiene título -> NO genérico")

    def test_looks_like_music_covers_languages_by_noun(self):
        for q in (
            "una cancion", "some music", "una canzone", "uma musica",
            "musik", "une chanson",
        ):
            self.assertTrue(_looks_like_music_request(q), f"{q!r} menciona música")

    def test_looks_like_music_ignores_plain_play_verb_with_title(self):
        # 'pon bad bunny' = verbo + artista SIN sustantivo de música -> NO auto-play
        # (conserva la conducta vieja: abre resultados de búsqueda, no reproduce directo).
        for q in ("pon bad bunny", "abre el navegador", "que hora es"):
            self.assertFalse(_looks_like_music_request(q), f"{q!r} no es pedido de música")


class TestMcpSafetyGate(unittest.TestCase):
    """Fix #5 — las tools MCP YA NO saltean el safety classifier."""

    def test_classify_read_tools_no_confirm(self):
        for name in ("mcp__fs__read_file", "mcp__fs__list_directory", "mcp__db__query",
                     "mcp__x__search", "mcp__y__get_info"):
            d = classify_mcp_call(name, {})
            self.assertFalse(d.requires_confirmation, f"{name} es lectura -> sin confirmar")

    def test_classify_mutating_tools_confirm(self):
        for name in ("mcp__fs__delete_file", "mcp__fs__write_file",
                     "mcp__github__create_issue", "mcp__x__get_and_delete"):
            d = classify_mcp_call(name, {})
            self.assertTrue(d.requires_confirmation, f"{name} muta -> confirmar")

    def test_unknown_tool_fails_safe_confirm(self):
        d = classify_mcp_call("mcp__weird__frobnicate", {})
        self.assertTrue(d.requires_confirmation, "MCP desconocido -> fail-safe confirma")

    def test_annotations_override_name(self):
        # readOnlyHint gana aunque el nombre suene a mutación; destructiveHint también.
        self.assertFalse(classify_mcp_call("mcp__x__write_cache", {"readOnlyHint": True}).requires_confirmation)
        self.assertTrue(classify_mcp_call("mcp__x__get_info", {"destructiveHint": True}).requires_confirmation)

    def test_irreversible_mcp_confirms_under_never_policy(self):
        # Una mutación MCP es irreversible -> se confirma incluso bajo policy 'never'.
        d = classify_mcp_call("mcp__fs__delete_file", {})
        self.assertTrue(should_confirm(d, "never"))
        # pero una lectura MCP NO molesta bajo 'never'
        self.assertFalse(should_confirm(classify_mcp_call("mcp__fs__read_file", {}), "never"))

    def test_dispatch_gates_mcp_mutation(self):
        tmp = Path(tempfile.mkdtemp())
        reg = ToolRegistry(MemoryStore(tmp / "m.json"), tmp / "caps", safety_enabled=True)
        calls = {"n": 0}

        def fake_call(name, args):
            calls["n"] += 1
            return {"ok": True, "content": "done", "tool": name}

        with mock.patch.object(mc, "is_mcp_tool_name", lambda n: n.startswith("mcp__")), \
             mock.patch.object(mc, "call_mcp_by_id", fake_call), \
             mock.patch.object(mc, "mcp_tool_annotations", lambda n: {}):
            # mutación sin confirmar -> bloquea, 0 ejecuciones
            r1 = reg.execute("mcp__fs__delete_file", {"path": "/x"})
            self.assertEqual(r1.get("status"), "needs_confirmation")
            self.assertEqual(calls["n"], 0)
            # con confirmed=True -> ejecuta
            r2 = reg.execute("mcp__fs__delete_file", {"path": "/x", "confirmed": True})
            self.assertEqual(calls["n"], 1)
            # lectura -> sin confirmar, ejecuta
            reg.execute("mcp__fs__read_file", {"path": "/x"})
            self.assertEqual(calls["n"], 2)
            # confirmed='false' (string) en mutación -> bloquea (Fix #1 + #5 juntos)
            r4 = reg.execute("mcp__fs__write_file", {"path": "/x", "confirmed": "false"})
            self.assertEqual(r4.get("status"), "needs_confirmation")
            self.assertEqual(calls["n"], 2)


class TestActionEnums(unittest.TestCase):
    """Fix #6 — whatsapp y mcp ahora tienen ACTION_ENUMS (validación a nivel schema)."""

    def test_whatsapp_and_mcp_have_enums(self):
        self.assertIn("whatsapp", ACTION_ENUMS)
        self.assertIn("mcp", ACTION_ENUMS)
        self.assertEqual(ACTION_ENUMS["mcp"], ["list", "call"])

    def test_enum_injected_into_schema(self):
        for name in ("whatsapp", "mcp"):
            sch = next(s for s in COMPOUND_TOOL_SCHEMAS if s["function"]["name"] == name)
            enum = sch["function"]["parameters"]["properties"]["action"].get("enum")
            self.assertTrue(enum, f"{name}.action debe tener enum en el schema")

    def test_enum_covers_all_handler_actions(self):
        # las acciones que t_whatsapp/whatsapp_tool aceptan deben estar TODAS en el enum
        # (si falta una, el schema rechazaría una acción válida).
        wa = set(ACTION_ENUMS["whatsapp"])
        for needed in ("status", "send_message", "open_chat", "read_messages"):
            self.assertIn(needed, wa)

    def test_invalid_action_rejected_at_schema(self):
        tmp = Path(tempfile.mkdtemp())
        reg = ToolRegistry(MemoryStore(tmp / "m.json"), tmp / "caps", safety_enabled=True)
        r = reg.execute("whatsapp", {"action": "send_whatsapp", "contact": "x", "text": "y"})
        self.assertEqual(r.get("status"), "failed")
        self.assertIn("invalid", str(r.get("error", "")).lower())


class TestRegistryHardGate(unittest.TestCase):
    """Hallazgo menor — registry add/delete con hard_gate independiente de safety."""

    def _setup(self):
        tmp = Path(tempfile.mkdtemp())
        return AgentState(tmp / "state.json")

    def test_add_gated_without_confirm(self):
        ran = {"n": 0}

        def fake_run(cmd, timeout=20):
            ran["n"] += 1
            return {"ok": True, "stdout": "", "exit_code": 0}

        with mock.patch.object(ot, "_run_cmd", fake_run):
            st = self._setup()
            r = registry_tool({"action": "add", "key": "HKCU\\Software\\T", "name": "v", "data": "x"}, st)
            self.assertEqual(r.get("status"), "needs_confirmation")
            self.assertEqual(ran["n"], 0, "reg.exe NO debe correr sin confirmar")

    def test_delete_gated_without_confirm(self):
        ran = {"n": 0}

        def fake_run(cmd, timeout=20):
            ran["n"] += 1
            return {"ok": True, "stdout": "", "exit_code": 0}

        with mock.patch.object(ot, "_run_cmd", fake_run):
            st = self._setup()
            r = registry_tool({"action": "delete", "key": "HKCU\\Software\\T", "name": "v"}, st)
            self.assertEqual(r.get("status"), "needs_confirmation")
            self.assertEqual(ran["n"], 0)

    def test_string_false_confirmed_still_gates(self):
        # hard_gate también coerce el string 'false' (mismo bug-class).
        ran = {"n": 0}

        def fake_run(cmd, timeout=20):
            ran["n"] += 1
            return {"ok": True, "stdout": "", "exit_code": 0}

        with mock.patch.object(ot, "_run_cmd", fake_run):
            st = self._setup()
            r = registry_tool({"action": "delete", "key": "HKCU\\Software\\T", "confirmed": "false"}, st)
            self.assertEqual(r.get("status"), "needs_confirmation")
            self.assertEqual(ran["n"], 0)

    def test_confirmed_true_proceeds(self):
        ran = {"n": 0}

        def fake_run(cmd, timeout=20):
            ran["n"] += 1
            return {"ok": True, "stdout": "", "exit_code": 0}

        with mock.patch.object(ot, "_run_cmd", fake_run):
            st = self._setup()
            registry_tool({"action": "add", "key": "HKCU\\Software\\T", "name": "v", "data": "x", "confirmed": True}, st)
            self.assertGreater(ran["n"], 0, "con confirmed=True debe ejecutar reg.exe")


class TestDispatchLogsTraceback(unittest.TestCase):
    """Hallazgo menor — los except del dispatch loguean el traceback (DX)."""

    def test_tool_exception_is_logged_with_traceback(self):
        tmp = Path(tempfile.mkdtemp())
        reg = ToolRegistry(MemoryStore(tmp / "m.json"), tmp / "caps", safety_enabled=False)

        def boom(_args):
            raise ValueError("kaboom")

        reg._impls["system"] = boom
        with self.assertLogs("gemma4_agent.tools_pkg.tools", level="ERROR") as cm:
            r = reg.execute("system", {"action": "time"})
        # el LLM sigue recibiendo el mensaje conciso
        self.assertFalse(r.get("ok"))
        self.assertIn("kaboom", str(r.get("error", "")))
        # y el traceback quedó en el log
        joined = "\n".join(cm.output)
        self.assertIn("Traceback", joined)
        self.assertIn("kaboom", joined)


if __name__ == "__main__":
    unittest.main()
