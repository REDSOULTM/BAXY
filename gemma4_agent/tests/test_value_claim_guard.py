"""Guard de claim de VALOR sin evidencia (gates FT v3 2026-06-11).

Casos calcados de las fabricaciones medidas EN VIVO contra el candidato FT:
"Battery level is 78%" con has_battery:false del tool real; "CPU usage is 15
percent" ignorando LoadPercentage; valores afirmados SIN llamar tool. Y los
casos legítimos que NO deben flaggear (valor citado del result, del user_text,
o números sin unidad de medida).
"""
import os
import unittest

from gemma4_agent.safety_pkg.reply_validator import (
    strip_unfounded_value_sentences,
    system_value_claim_unfounded,
)


def _ev(name, args, result):
    return {"name": name, "args": args, "result": result}


_BATT_NONE = {"ok": True, "battery": None, "has_battery": False,
              "note": "No battery (desktop or no driver).",
              "tool": "system", "action": "battery", "status": "done"}
_CPU_REAL = {"ok": True, "info": {"cpu": {"Name": "Intel", "LoadPercentage": 3},
                                  "ram_free_gb": 8.7, "ram_total_gb": 16},
             "tool": "system", "action": "cpu_ram_gpu", "status": "done"}


class TestDetector(unittest.TestCase):
    def test_battery_percent_fabricado_con_result_sin_bateria(self):
        # caso vivo g2#17: "battery level?" -> "Battery level is 78%."
        self.assertTrue(system_value_claim_unfounded(
            "battery level?", "Battery level is 78%.",
            [_ev("system", {"action": "battery"}, _BATT_NONE)]))

    def test_cpu_percent_fabricado_ignorando_result(self):
        # caso vivo g2#14: result LoadPercentage=3, reply "15 percent"
        self.assertTrue(system_value_claim_unfounded(
            "what's the CPU usage", "CPU usage is 15 percent.",
            [_ev("system", {"action": "cpu_ram_gpu"}, _CPU_REAL)]))

    def test_valor_sin_ninguna_tool(self):
        # caso vivo g2#8: "cuánto le queda a la batería" sin tool
        self.assertTrue(system_value_claim_unfounded(
            "cuánto le queda a la batería",
            "La batería tiene un 28 por ciento de carga.", []))

    def test_multilingue_porcento(self):
        self.assertTrue(system_value_claim_unfounded(
            "quanta batteria rimane",
            "La percentuale della batteria è al 75 per cento.",
            [_ev("system", {"action": "battery"}, _BATT_NONE)]))

    def test_valor_citado_del_result_no_flaggea(self):
        res = {"ok": True, "battery": {"percent": 85, "plugged": True},
               "has_battery": True, "tool": "system", "action": "battery"}
        self.assertFalse(system_value_claim_unfounded(
            "cuánta batería queda", "La batería está al 85%, cargando.",
            [_ev("system", {"action": "battery"}, res)]))

    def test_cpu_citado_no_flaggea(self):
        self.assertFalse(system_value_claim_unfounded(
            "uso de CPU", "CPU al 3% y 8.7 GB de RAM libres.",
            [_ev("system", {"action": "cpu_ram_gpu"}, _CPU_REAL)]))

    def test_valor_del_user_text_no_flaggea(self):
        self.assertFalse(system_value_claim_unfounded(
            "poné el brillo al 40%", "Listo, brillo al 40%.", []))

    def test_numero_sin_unidad_no_flaggea(self):
        # números pelados (cantidades, títulos) no son claims de medida
        self.assertFalse(system_value_claim_unfounded(
            "abrí 3 ventanas", "Abrí las 3 ventanas que pediste.", []))

    def test_otras_tools_no_flaggea(self):
        # web con snippet: el caso queda fuera del scope (evidencia=payload)
        res = {"ok": True, "results": [{"snippet": "GPU prices fell"}],
               "tool": "web", "action": "search"}
        self.assertFalse(system_value_claim_unfounded(
            "precio de una GPU", "Cayeron un 20% según lo que encontré.",
            [_ev("web", {"action": "search"}, res)]))

    def test_coma_decimal_equivalente(self):
        res = {"ok": True, "info": {"ram_free_gb": 12.8}, "tool": "system",
               "action": "cpu_ram_gpu"}
        self.assertFalse(system_value_claim_unfounded(
            "memoria libre", "Tenés 12,8 GB libres.",
            [_ev("system", {"action": "cpu_ram_gpu"}, res)]))


class TestStrip(unittest.TestCase):
    def test_strip_quita_solo_la_oracion_fabricada(self):
        out = strip_unfounded_value_sentences(
            "Revisé el sistema. La batería está al 78%. Avisame si querés más.",
            "batería", [_ev("system", {"action": "battery"}, _BATT_NONE)])
        self.assertNotIn("78", out)
        self.assertIn("Revisé el sistema.", out)
        self.assertIn("Avisame", out)

    def test_strip_conserva_valor_sustentado(self):
        res = {"ok": True, "battery": {"percent": 64}, "has_battery": True,
               "tool": "system", "action": "battery"}
        out = strip_unfounded_value_sentences(
            "La batería está al 64%.", "batería",
            [_ev("system", {"action": "battery"}, res)])
        self.assertIn("64", out)


class TestRepairInline(unittest.TestCase):
    def test_regen_valida_reemplaza(self):
        from gemma4_agent.agent_core.agent_guards import (
            repair_unfounded_value_claim_inline)
        events = [_ev("system", {"action": "battery"}, _BATT_NONE)]
        out = repair_unfounded_value_claim_inline(
            "Battery level is 78%.", "battery level?", events, "t1",
            regen_action=lambda: "This PC has no battery — it's a desktop.",
            regen_knowledge=None)
        self.assertEqual(out, "This PC has no battery — it's a desktop.")

    def test_regen_tambien_fabricada_cae_a_strip(self):
        from gemma4_agent.agent_core.agent_guards import (
            repair_unfounded_value_claim_inline)
        events = [_ev("system", {"action": "battery"}, _BATT_NONE)]
        out = repair_unfounded_value_claim_inline(
            "Battery level is 78%.", "battery level?", events, "t1",
            regen_action=lambda: "Battery is at 92%.",
            regen_knowledge=None)
        self.assertNotIn("78", out)
        self.assertNotIn("92", out)

    def test_gate_env_apaga(self):
        from gemma4_agent.agent_core.agent_guards import (
            repair_unfounded_value_claim_inline)
        os.environ["GEMMA4_VALUE_CLAIM_GUARD"] = "0"
        try:
            out = repair_unfounded_value_claim_inline(
                "Battery level is 78%.", "battery level?",
                [_ev("system", {"action": "battery"}, _BATT_NONE)], "t1")
            self.assertEqual(out, "Battery level is 78%.")
        finally:
            os.environ.pop("GEMMA4_VALUE_CLAIM_GUARD", None)

    def test_reply_sano_intacto(self):
        from gemma4_agent.agent_core.agent_guards import (
            repair_unfounded_value_claim_inline)
        res = {"ok": True, "battery": {"percent": 85}, "has_battery": True,
               "tool": "system", "action": "battery"}
        out = repair_unfounded_value_claim_inline(
            "La batería está al 85%.", "batería",
            [_ev("system", {"action": "battery"}, res)], "t1")
        self.assertEqual(out, "La batería está al 85%.")


if __name__ == "__main__":
    unittest.main()
