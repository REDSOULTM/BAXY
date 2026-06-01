"""Evaluador aritmético seguro (try_arithmetic): el 4B falla la aritmética; este
short-circuit la computa exacto (AST seguro, sin eval). Alta precisión: solo aritmética
clara; lo conversacional -> None."""
import unittest
from gemma4_agent.routing.arithmetic import try_arithmetic as f


class ArithmeticTest(unittest.TestCase):
    def test_computes_correct(self):
        cases = {
            "cuánto es 47 por 8": "376",
            "47 por 8": "376",
            "2 más 2": "4",
            "10 dividido 2": "5",
            "100 dividido por 8": "12.5",
            "8 entre 2": "4",
            "5 menos 3": "2",
            "3 al cuadrado": "9",
            "2 elevado a 10": "1024",
            "2 más 3 por 4": "14",          # precedencia
            "(2 más 3) por 4": "20",
            "how much is 6 times 7": "42",
            "cuánto es 15 dividido por 4": "3.75",
        }
        for q, exp in cases.items():
            self.assertEqual(f(q), exp, msg=q)

    def test_none_on_non_arithmetic(self):
        for q in ("qué hora es", "cuánto cuesta el pan", "hola cómo estás",
                  "abrí la calculadora", "contame del 9 de julio",
                  "a las 5 menos 10", "mostrame las tareas", "15 por ciento",
                  "subí el volumen", ""):
            self.assertIsNone(f(q), msg=q)

    def test_no_code_injection(self):
        # NUNCA ejecutar código: nombres/llamadas/atributos -> None (no eval/exec)
        for q in ("__import__('os').system('calc')", "2 + abrir()",
                  "print(5)", "x más 2", "os.getcwd()"):
            self.assertIsNone(f(q), msg=q)


if __name__ == "__main__":
    unittest.main()
