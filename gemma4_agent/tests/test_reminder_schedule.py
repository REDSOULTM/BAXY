"""B8 (competidores): reminders confiables. El tool `reminder` con HORA delega al
backend de Task Scheduler (notification_tool) para que DISPARE aunque la app
reinicie. Tests de la lógica de cableado con notification_tool MOCKEADO (sin tocar
el SO). Gate GEMMA4_REMINDER_SCHEDULE. La validación del disparo real es en vivo.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ..tools_pkg.ops_tools import reminder_tool, _reminder_schedule_enabled
from ..memory_pkg.state import AgentState

_NT = "gemma4_agent.domain_tools.notifications.notification_tool"


def _state():
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    p = Path(tmp.name)
    p.unlink(missing_ok=True)
    return AgentState(path=p)


class _Env:
    def __init__(self, on):
        self.on = on

    def __enter__(self):
        self._prev = os.environ.get("GEMMA4_REMINDER_SCHEDULE")
        os.environ["GEMMA4_REMINDER_SCHEDULE"] = "1" if self.on else "0"

    def __exit__(self, *a):
        if self._prev is None:
            os.environ.pop("GEMMA4_REMINDER_SCHEDULE", None)
        else:
            os.environ["GEMMA4_REMINDER_SCHEDULE"] = self._prev


class TestReminderSchedule(unittest.TestCase):
    def test_create_with_due_delegates_when_on(self):
        with _Env(True), mock.patch(
                _NT, return_value={"ok": True, "kind": "local_reminder", "task_name": "X"}) as nt:
            r = reminder_tool({"action": "create", "title": "tomar agua",
                               "due": "2099-01-01T15:00:00"}, _state())
        self.assertTrue(r.get("ok"))
        nt.assert_called_once()
        sent = nt.call_args[0][0]
        self.assertEqual(sent["action"], "reminder_create")
        self.assertEqual(sent["due"], "2099-01-01T15:00:00")
        self.assertEqual(sent["title"], "tomar agua")

    def test_create_with_due_state_only_when_off(self):
        with _Env(False), mock.patch(_NT) as nt:
            r = reminder_tool({"action": "create", "title": "x",
                               "due": "2099-01-01T15:00:00"}, _state())
        nt.assert_not_called()
        self.assertEqual(r.get("backend"), "state")

    def test_create_without_due_is_state_only_even_when_on(self):
        with _Env(True), mock.patch(_NT) as nt:
            r = reminder_tool({"action": "create", "title": "comprar pan"}, _state())
        nt.assert_not_called()  # sin hora no hay nada que programar
        self.assertEqual(r.get("backend"), "state")

    def test_schedule_failure_falls_back_to_state(self):
        with _Env(True), mock.patch(
                _NT, return_value={"ok": False, "error": "powershell missing"}) as nt:
            r = reminder_tool({"action": "create", "title": "x",
                               "due": "2099-01-01T15:00:00"}, _state())
        nt.assert_called_once()
        self.assertEqual(r.get("backend"), "state")  # no perdemos el reminder

    def test_list_includes_local_reminder(self):
        st = _state()
        st.register_resource("local_reminder", "alarma prog",
                             metadata={"task_name": "T1", "due": "2099-01-01T09:00:00"})
        st.register_resource("reminder", "nota suelta", metadata={"backend": "state"})
        r = reminder_tool({"action": "list"}, st)
        labels = {res.get("label") for res in r.get("reminders", [])}
        self.assertIn("alarma prog", labels)
        self.assertIn("nota suelta", labels)

    def test_delete_local_reminder_delegates_to_notification(self):
        st = _state()
        reg = st.register_resource("local_reminder", "x", metadata={"task_name": "T1"})
        rid = reg.get("resource", {}).get("id")
        with mock.patch(_NT, return_value={"ok": True, "deleted": True}) as nt:
            reminder_tool({"action": "delete", "id": rid}, st)
        nt.assert_called_once()
        self.assertEqual(nt.call_args[0][0]["action"], "reminder_delete")

    def test_delete_plain_reminder_does_not_delegate(self):
        st = _state()
        reg = st.register_resource("reminder", "nota", metadata={"backend": "state"})
        rid = reg.get("resource", {}).get("id")
        with mock.patch(_NT) as nt:
            reminder_tool({"action": "delete", "id": rid}, st)
        nt.assert_not_called()  # sin task_name -> mark_cleaned directo

    def test_gate_default_on_with_killswitch(self):
        # B8 flipeado a default-ON tras validar en vivo (2026-05-29: el Scheduled
        # Task se crea en el SO). Kill-switch GEMMA4_REMINDER_SCHEDULE=0.
        prev = os.environ.pop("GEMMA4_REMINDER_SCHEDULE", None)
        try:
            self.assertTrue(_reminder_schedule_enabled())   # default ON
            os.environ["GEMMA4_REMINDER_SCHEDULE"] = "0"
            self.assertFalse(_reminder_schedule_enabled())  # kill-switch
            os.environ["GEMMA4_REMINDER_SCHEDULE"] = "1"
            self.assertTrue(_reminder_schedule_enabled())
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_REMINDER_SCHEDULE", None)
            else:
                os.environ["GEMMA4_REMINDER_SCHEDULE"] = prev


if __name__ == "__main__":
    unittest.main()
