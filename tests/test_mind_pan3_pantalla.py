"""PAN3 (12-11-2026): con `pan2` (8728873a5) «apaga la pantalla» dejó de bloquear en Esencial y Diario, pero en Avanzado
(50 herramientas más a la vista, ninguna de pantalla ni de energía) las cuatro frases más directas seguían yendo a
system_power lock 5 de 5: su único ejemplo con «pantalla» era «bloquea la pantalla», y la acción lock no decía que no
apaga la pantalla. Sin fuente: medición propia (banco de decisiones, Qwen3.5-4B en el NB, mundo «voz», un monitor,
INFORME_PAN3.md): Avanzado «apaga la pantalla» ×8, semillas 0-4, bloquea 20 de 40 -> 0 de 40.

PAN4 (13-11-2026, INFORME_PAN4A.md): las frases que PAN3 añadió a lock y sleep («never to turn the screen off», «a screen
or display put to sleep is display_monitor_set») y las de pan2 en display_monitor_set y system_power movieron tres filas
de la puerta al otro lado de su borde (c129-R4 baxy_exit 1 -> 9 de 10, u121-B11 UTC 2 -> 9 de 10, c129-V4 la pantalla
0 -> 9 de 10). Se queda lo mínimo y verdadero: ninguna palabra de pantalla en lo que bloquea, y la frase de un solo monitor
dice lo que hace ahora. Sin fuente: medición propia.

PAN4B (13-11-2026, INFORME_PAN4B.md): con V3 (los textos de la 1.5.0 y esos tres cambios) «apaga la pantalla» seguía
bloqueando en Avanzado 15 de 40 y en Completo 10 de 40, y c129-V4 en Completo cerraba BAXY 9 de 10. Con V1 (la frase de
un solo monitor y el «Do not use when» de pan2 en system_power, sin las dos frases de PAN3 en lock y sleep): 0 de 40 y
0 de 10. Sin fuente: medición propia.

PAN6 (13-11-2026, INFORME_PAN6.md): con V1 y los catálogos de la 1.5.2, c129-V4 («el Belmora sigue ahí abajo con el
iconito, apágalo completo», una app) llamaba display_monitor_set {active false, monitor below} 7 de 10 en Esencial (9 de
10 en la puerta de INT35). Sin «nothing closes and the session is not locked» en la frase de un solo monitor (BAXY no lee
si la sesión se bloqueó: con Modern Standby, «Screen Off» lleva a la espera, REV20 P5-2, Microsoft Learn «Modern Standby
states»), el ejemplo sin monitor al final y uno en inglés sin monitor («turn the screen off») en vez de «turn off the
right screen»: 0 de 10, y «apaga la pantalla» sin bloquear. Sin quitar la frase, o sin el ejemplo en inglés, alguna de
las dos vuelve (variantes vC, vE, vI, vK, vK4 del informe). El orden de los ejemplos: sin fuente, medición propia.
Con eso, en Completo c129-V4 llamaba system_power shutdown 9 de 10 (la 1.5.2: baxy_exit 10 de 10; en Bypass los dos
corren sin el sí): «Turning the PC off is only for apaga/shut down» dejaba «apágalo» suelto en apagar el PC, la clase
que L3 ya vio («apágalo» de una app abierta → shutdown, 5 de 14). Con «apaga el PC»: 0 de 10 en Completo y en Esencial,
y «apaga el equipo» sigue en shutdown 12 de 12. Sin fuente: medición propia."""
import json
from pathlib import Path

DATA = json.loads((Path(__file__).resolve().parents[1] / "src" / "baxy_mind" / "data"
                   / "tool_descriptions.en.v1.json").read_bytes())
POWER = DATA["tools"]["system.power"]
ACTION = DATA["arguments"]["system.power"]["action"]
MONITOR = DATA["tools"]["display.monitor.set"]


def _action(name: str) -> str:
    start = ACTION.index(name + ":")
    ends = [i for i in (ACTION.find(f" {other}:", start) for other in ("lock", "signout", "sleep", "restart", "shutdown"))
            if i > start]
    return ACTION[start:min(ends, default=len(ACTION))]


def test_power_gives_no_screen_example() -> None:
    # The one example of system_power naming the screen was a lock; «apaga la pantalla» followed it with many tools.
    examples = POWER[POWER.index("Examples:"):]
    assert "pantalla" not in examples
    assert "«bloquea el equipo»" in examples


def test_turning_the_pc_off_names_the_pc() -> None:
    # «apágalo» said of an app matched «only for apaga/shut down» and shut the PC down.
    assert "Turning the PC off is only for apaga el PC or shut down." in POWER
    assert "only for apaga/shut down" not in POWER


def test_lock_says_the_session_locks() -> None:
    # «the screen locks» (the 1.5.0 text) put a screen word on what locks.
    assert "the screen locks" not in _action("lock")
    assert "the session locks" in _action("lock")


def test_the_only_monitor_says_it_goes_dark() -> None:
    # «Never turns off the only monitor on» is no longer true: WindowsMonitorAdapter darkens it.
    assert "Never turns off the only monitor on" not in MONITOR
    assert "the screen goes dark as Windows darkens it when idle" in MONITOR


def test_darkening_says_nothing_of_the_session_it_does_not_read() -> None:
    # REV20 P5-2: with Modern Standby the dark screen can lead to sleep and the password; BAXY does not read it.
    assert "the session is not locked" not in MONITOR
    assert "nothing closes" not in MONITOR


def test_the_examples_end_with_the_screen_turned_off_without_naming_one() -> None:
    # «apaga la pantalla» (active false) first was the example an «apágalo… ahí abajo» said of an app followed (below).
    examples = MONITOR[MONITOR.index("Examples:"):]
    assert examples.startswith("Examples: «apaga la pantalla de la izquierda» (active false, monitor left)")
    assert examples.endswith("«turn the screen off» (active false), «apaga la pantalla» (active false).")
