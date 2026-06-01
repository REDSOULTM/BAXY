"""Evaluador aritmético seguro (try_arithmetic): el 4B falla la aritmética; este
short-circuit la computa exacto (AST seguro, sin eval). Alta precisión: solo aritmética
clara; lo conversacional -> None."""
import unittest
from gemma4_agent.routing.arithmetic import try_arithmetic as f
from gemma4_agent.routing.arithmetic import arith_expr_for_calc as ec


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

    def test_word_numbers(self):
        # palabras-número es/en -> dígitos (mejora: antes "dos más dos" -> None)
        self.assertEqual(f("dos más dos"), "4")
        self.assertEqual(f("cuánto es cinco por tres"), "15")
        self.assertEqual(f("ten minus four"), "6")

    def test_percent_word_not_hijacked(self):
        # "ciento/cien" NO es número-palabra (colisiona con "por ciento") -> None
        self.assertIsNone(f("15 por ciento"))


class ArithExprForCalcTest(unittest.TestCase):
    """arith_expr_for_calc: la EXPRESIÓN compacta a TIPEAR en la calculadora."""

    def test_extracts_expression_to_type(self):
        cases = {
            "suma 2+2": "2+2",
            "Suma 2 más 2": "2+2",
            "Suma dos más dos": "2+2",       # palabras-número
            "5 por 3": "5*3",
            "escribí 10/2": "10/2",
            "calculá 7 menos 4": "7-4",
            "multiplicá 6 por 7": "6*7",
            "100 dividido 4": "100/4",
        }
        for q, exp in cases.items():
            self.assertEqual(ec(q), exp, msg=q)

    def test_none_when_not_arithmetic(self):
        for q in ("abrí la calculadora", "poné hola", "anotá la reunión", ""):
            self.assertIsNone(ec(q), msg=q)


if __name__ == "__main__":
    unittest.main()
