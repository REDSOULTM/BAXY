"""What every test of the suite starts from (calidad del PC, 2026-10-25): the product's defaults, not the shell's.

The mind, the voice and the bench tools read their switches from BAXY_* variables (BAXY_RENEW_PREFILL,
BAXY_RENEW_TTS_JOIN_ALL, BAXY_RENEW_CTX…). A shell of this PC that ran a bench keeps them, and the
same suite then failed there and passed elsewhere: 16 tests with BAXY_RENEW_PREFILL=0, two with the clause switches,
two with System One switches, one with BAXY_RENEW_CTX. Each test sets what it needs itself
(monkeypatch.setenv), so none of them is taken from outside.
"""
import os

import pytest

from baxy_mind import mind

# The owner's System One switch is machine state too (%LOCALAPPDATA%\BAXY\renew\system_one.off, scripts\system_one.cmd
# off): entrega 1.1.0 made System One the mind's default, so a PC with it off failed the tests of the defaults. Only a
# switch a test makes under its own LOCALAPPDATA counts.
_OWNERS_LOCALAPPDATA = os.environ.get("LOCALAPPDATA")
_system_one_off = mind.system_one_off


@pytest.fixture(autouse=True)
def _no_baxy_switch_from_the_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [name for name in os.environ if name.upper().startswith("BAXY_")]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(mind, "system_one_off",
                        lambda: os.environ.get("LOCALAPPDATA") != _OWNERS_LOCALAPPDATA and _system_one_off())
