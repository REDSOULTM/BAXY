"""Conftest RAÍZ del repo — se carga para CUALQUIER corrida de pytest, desde
cualquier directorio o subconjunto de tests, sin flags ni comandos especiales.

Su única responsabilidad es instalar, por defecto, los guards de seguridad de la
suite: ningún test puede abrir programas, ventanas ni el navegador (os.startfile /
webbrowser / subprocess de apertura quedan neutralizados). Las LECTURAS siguen
ejecutándose de verdad, así la suite comprueba todo sin lanzar nada a la cara.

Esto vive en la raíz (no solo en gemma4_agent/tests/) para cubrir también
gemma4_agent/voice/tests/ y cualquier test futuro fuera de esa carpeta.
"""
from gemma4_agent.tests._suite_guards import install as _install_suite_guards

# Instalación a tiempo de import del conftest (antes de recolectar/ejecutar tests).
# Idempotente: si el conftest de gemma4_agent/tests/ también lo invoca, no duplica.
RECORDED_SIDE_EFFECTS = _install_suite_guards()
