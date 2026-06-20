"""La vista LLM de system.disk no debe exponer Size/FreeSpace en BYTES crudos cuando
existe el size_gb/free_gb legible: el 2B narraba "184080207872 bytes" en vez de GB."""
import unittest
from gemma4_agent.agent_core.agent_compaction import compact_tool_result


class DiskViewGbTest(unittest.TestCase):
    def test_bytes_dropped_gb_kept(self):
        res = {"ok": True, "tool": "system", "disks": [
            {"DeviceID": "C:", "Size": 1998835412992, "FreeSpace": 184080207872,
             "size_gb": 1862.0, "free_gb": 171.4}]}
        view = compact_tool_result("system", {"action": "disk"}, res)
        d = view["disks"][0]
        self.assertNotIn("Size", d)
        self.assertNotIn("FreeSpace", d)
        self.assertEqual(d["free_gb"], 171.4)
        # result original intacto (consumers/tests siguen viendo bytes)
        self.assertIn("Size", res["disks"][0])

    def test_bytes_kept_when_no_gb_sibling(self):
        # sin size_gb/free_gb (edge: augment falló) NO se dropea -> no perder el dato
        res = {"ok": True, "disks": [{"DeviceID": "C:", "Size": 100, "FreeSpace": 50}]}
        view = compact_tool_result("system", {"action": "disk"}, res)
        self.assertIn("Size", view["disks"][0])


if __name__ == "__main__":
    unittest.main()
