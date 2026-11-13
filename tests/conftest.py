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
def _no_card_asked(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    # VRAM4: a server's start asks the card for its free memory (LlmServer.start, one --list-devices). No test asks this
    # PC's: the ones about it say what the card answers (test_mind_vision_gpu, the server's own --list-devices).
    from baxy_mind import llm_server

    if request.module.__name__.rpartition(".")[2] == "test_mind_vision_gpu":
        return
    monkeypatch.setattr(llm_server.LlmServer, "_card_free", lambda self: None, raising=False)
    monkeypatch.setattr(llm_server.LlmServer, "_card_total", lambda self: None, raising=False)


@pytest.fixture(autouse=True)
def _no_baxy_switch_from_the_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [name for name in os.environ if name.upper().startswith("BAXY_")]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(mind, "system_one_off",
                        lambda: os.environ.get("LOCALAPPDATA") != _OWNERS_LOCALAPPDATA and _system_one_off())


# Public repository only: some tests also read documents that are not published (`documentacion/`: the store pages, the
# Steam agreement and itch.io's legal document) and the license texts' tests read the internal README, which is another
# document here. A test that needs one of them is skipped instead of failing; the tests of what is published run as
# they are.
@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item: pytest.Item):
    try:
        return (yield)
    except (FileNotFoundError, IndexError, AssertionError) as error:
        last = error.__traceback__
        while last.tb_next is not None:
            last = last.tb_next
        unpublished = (isinstance(error, FileNotFoundError)
                       and "documentacion" in str(error.filename).replace("\\", "/").split("/"))
        # A script the test runs stopped on the same missing document, and the test read that in its output.
        output = str(getattr(last.tb_frame.f_locals.get("done"), "stderr", ""))
        through_a_script = (isinstance(error, AssertionError) and "No such file or directory" in output
                            and "documentacion" in output)
        internal_readme = (isinstance(error, IndexError) and item.module.__name__.rsplit(".", 1)[-1] == "test_license_texts"
                           and last.tb_frame.f_code.co_name == "_privacy"
                           and last.tb_frame.f_locals.get("path") == "README.md")
        if not (unpublished or through_a_script or internal_readme):
            raise
        pytest.skip("needs a document that is not in the public repository")
