"""What every test of the suite starts from (calidad del PC, 2026-10-25): the product's defaults, not the shell's.

The mind, the voice and the bench tools read their switches from BAXY_* variables (BAXY_RENEW_PREFILL,
BAXY_RENEW_TTS_CLAUSE, BAXY_S1_LOOK_TOWARD, BAXY_RENEW_CTX…). A shell of this PC that ran a bench keeps them, and the
same suite then failed there and passed elsewhere: 16 tests with BAXY_RENEW_PREFILL=0, two with the clause switches,
two with BAXY_S1_LOOK_TOWARD and BAXY_S1_DOUBT_DONE, one with BAXY_RENEW_CTX. Each test sets what it needs itself
(monkeypatch.setenv), so none of them is taken from outside.
"""
import os

import pytest


@pytest.fixture(autouse=True)
def _no_baxy_switch_from_the_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [name for name in os.environ if name.upper().startswith("BAXY_")]:
        monkeypatch.delenv(name, raising=False)
