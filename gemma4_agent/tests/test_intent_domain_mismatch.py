"""Guard cruzado intención↔dominio: cierra la mentira "moví la ventana y la
renombré a X.txt" — el usuario pidió una op de VENTANA pero corrió una tool de
ARCHIVO y el reply afirma haberlo hecho. is_unverified_claim NO lo atrapa porque
la tool (equivocada) "tuvo éxito". Bug real del eval run3 (window_vs_filesystem).
"""
from __future__ import annotations

import unittest

from gemma4_agent.safety_pkg.reply_validator import intent_domain_mismatch as idm


def _call(name, ok=True, status="done", verified=True):
    return {"name": name, "result": {"ok": ok, "status": status, "verified": verified}}


class IntentDomainMismatchTest(unittest.TestCase):
    def test_flags_window_intent_with_file_tool(self):
        # La mentira medida: pidió mover ventana, corrió filesystem, afirma efecto.
        self.assertTrue(idm(
            "mueve Notepad a la izquierda",
            "Listo, moví Notepad a la izquierda y lo renombré a Notepad_Left.txt",
            [_call("filesystem")]))

    def test_does_not_flag_genuine_file_op(self):
        # Operación de archivo REAL (no intención-ventana) -> NO flagear.
        for u, r in [
            ("renombrá informe.txt a final.txt", "Listo, renombré informe.txt a final.txt"),
            ("mové informe.txt a Documentos", "Listo, moví informe.txt a Documentos"),
        ]:
            self.assertFalse(idm(u, r, [_call("filesystem")]), msg=u)

    def test_does_not_flag_when_window_tool_ran(self):
        # Movió la ventana CON la tool correcta -> no es mismatch.
        self.assertFalse(idm("mueve Notepad a la izquierda",
                             "Listo, moví Notepad a la izquierda", [_call("window")]))

    def test_does_not_flag_when_computer_use_ran(self):
        # computer_use SÍ puede operar ventanas -> no flagear.
        self.assertFalse(idm("mueve Notepad a la izquierda", "Listo", [_call("computer_use")]))

    def test_does_not_flag_without_window_intent(self):
        self.assertFalse(idm("buscá el clima", "Listo, busqué el clima", [_call("web")]))

    def test_no_successful_tool_is_handled_elsewhere(self):
        # Sin tool exitosa lo cubre is_unverified_claim, no este guard.
        self.assertFalse(idm("mueve Notepad a la izquierda", "Listo, moví la ventana",
                             [_call("filesystem", ok=False, status="failed")]))

    def test_focus_intent(self):
        self.assertTrue(idm("pon foco en Bloc de notas",
                            "Listo, enfoqué y renombré la nota", [_call("filesystem")]))


if __name__ == "__main__":
    unittest.main()
