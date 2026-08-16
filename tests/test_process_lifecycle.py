from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from baxy_mind import llm as llm_module
from baxy_mind.llm import LlmRuntime
from baxy_mind.process_lifecycle import (
    ReapResource,
    ReapStatus,
    report_incomplete_reap,
    terminate_and_reap_bounded,
)


class _DelayedReapProcess:
    def __init__(self, *, persistent: bool) -> None:
        self.persistent = persistent
        self.kill_calls = 0
        self.wait_calls: list[float] = []

    @staticmethod
    def poll() -> None:
        return None

    def kill(self) -> None:
        self.kill_calls += 1

    def wait(self, timeout: float) -> int:
        self.wait_calls.append(timeout)
        if self.persistent or len(self.wait_calls) == 1:
            raise subprocess.TimeoutExpired(
                "private-model-path-and-arguments",
                timeout,
                output="private stdout",
                stderr="private stderr",
            )
        return 0


def test_bounded_process_reap_uses_reserved_final_wait() -> None:
    process = _DelayedReapProcess(persistent=False)

    status = terminate_and_reap_bounded(
        process,
        timeout=0.05,
        final_wait=0.02,
    )

    assert status is ReapStatus.REAPED
    assert process.kill_calls == 2
    assert len(process.wait_calls) == 2
    assert all(0.0 <= timeout <= 0.05 for timeout in process.wait_calls)


def test_bounded_process_reap_caps_each_phase_after_float_rounding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _DelayedReapProcess(persistent=True)
    monkeypatch.setattr(
        "baxy_mind.process_lifecycle.time.monotonic",
        lambda: 133_604.703,
    )

    status = terminate_and_reap_bounded(
        process,
        timeout=0.04,
        final_wait=0.02,
    )

    assert status is ReapStatus.TIMED_OUT
    assert process.wait_calls == [0.02, 0.02]
    assert sum(process.wait_calls) <= 0.04


def test_non_finite_timeout_cannot_create_an_unbounded_wait() -> None:
    process = _DelayedReapProcess(persistent=True)

    status = terminate_and_reap_bounded(
        process,
        timeout=float("inf"),
        final_wait=float("inf"),
    )

    assert status is ReapStatus.TIMED_OUT
    assert process.kill_calls == 1
    assert process.wait_calls == [0.0]


def test_persistent_reap_timeout_reports_only_closed_codes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    process = _DelayedReapProcess(persistent=True)

    status = terminate_and_reap_bounded(
        process,
        timeout=0.03,
        final_wait=0.01,
    )
    report_incomplete_reap(ReapResource.LLM_PROCESS, status)

    captured = capsys.readouterr()
    assert status is ReapStatus.TIMED_OUT
    assert process.kill_calls == 2
    assert len(process.wait_calls) == 2
    assert (
        captured.err
        == "baxy_mind_reap_incomplete:llm_process:timed_out\n"
    )
    assert "private" not in captured.err
    assert captured.out == ""


def test_llm_process_owner_propagates_bounded_reap_status(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    process = _DelayedReapProcess(persistent=True)
    monkeypatch.setattr(
        llm_module,
        "LLM_PROCESS_CLOSE_TIMEOUT_SECONDS",
        0.03,
    )
    monkeypatch.setattr(
        llm_module,
        "LLM_PROCESS_FINAL_REAP_TIMEOUT_SECONDS",
        0.01,
    )

    status = LlmRuntime._terminate_process(process)

    captured = capsys.readouterr()
    assert status is ReapStatus.TIMED_OUT
    assert (
        captured.err
        == "baxy_mind_reap_incomplete:llm_process:timed_out\n"
    )
    assert "private" not in captured.err
    assert captured.out == ""
