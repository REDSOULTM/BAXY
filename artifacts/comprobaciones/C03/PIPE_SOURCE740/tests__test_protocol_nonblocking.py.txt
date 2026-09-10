from __future__ import annotations

import errno
import os

import pytest

from baxy_mind import protocol


@pytest.mark.parametrize("empty_reads", [1, 3])
@pytest.mark.parametrize("terminated", [False, True])
def test_temporary_empty_pipe_preserves_split_utf8_and_final_eof(
    monkeypatch: pytest.MonkeyPatch, empty_reads: int, terminated: bool
) -> None:
    pending = iter([
        *[BlockingIOError(errno.EAGAIN, "not ready")] * empty_reads,
        b'{"type":"ping","text":"\xc3',
        BlockingIOError(errno.EAGAIN, "not ready"),
        b'\xb1"}' + (b"\n" if terminated else b""),
        b"",
    ])
    waits: list[float] = []
    monkeypatch.setattr(protocol.time, "sleep", waits.append)

    def read(_descriptor: int, limit: int) -> bytes:
        item = next(pending)
        if isinstance(item, Exception):
            raise item
        assert len(item) <= limit
        return item

    reader = protocol._BoundedFileDescriptorLineReader(7, read=read)
    assert protocol.read_message(reader) == {"type": "ping", "text": "ñ"}
    assert protocol.read_message(reader) is None
    assert len(waits) == empty_reads + 1
    assert all(0 < delay <= 0.05 for delay in waits)


def test_temporary_empty_pipe_does_not_reset_the_line_size_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    remaining = protocol.MAX_LINE_BYTES + 1
    calls = 0
    monkeypatch.setattr(protocol.time, "sleep", lambda _seconds: None)

    def read(_descriptor: int, limit: int) -> bytes:
        nonlocal remaining, calls
        calls += 1
        if calls % 2:
            raise BlockingIOError(errno.EAGAIN, "not ready")
        length = min(remaining, limit)
        remaining -= length
        return b"x" * length

    reader = protocol._BoundedFileDescriptorLineReader(7, read=read)
    with pytest.raises(protocol.ProtocolViolation) as raised:
        protocol.read_message(reader)
    assert raised.value.code == "line_too_large"
    assert remaining == 0


@pytest.mark.parametrize("code", [errno.EBADF, errno.EIO])
def test_pipe_failure_is_not_retried_or_reported_as_eof(
    monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    def no_wait(_seconds: float) -> None:
        pytest.fail("real read errors must be relayed immediately")

    def read(_descriptor: int, _limit: int) -> bytes:
        raise OSError(code, "read failed")

    monkeypatch.setattr(protocol.time, "sleep", no_wait)
    reader = protocol._BoundedFileDescriptorLineReader(7, read=read)
    with pytest.raises(OSError) as raised:
        protocol.read_message(reader)
    assert raised.value.errno == code


def test_open_protocol_reader_preserves_regular_file_input(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from baxy_mind import __main__ as sidecar

    path = tmp_path / "messages.jsonl"
    path.write_bytes(b'{"type":"ping"}\n')
    with path.open("rb") as source:
        monkeypatch.setattr(sidecar.sys, "stdin", source)
        reader = sidecar._open_protocol_reader()
        assert reader() == {"type": "ping"}
        assert reader() is None


def test_open_protocol_reader_uses_a_real_nonblocking_pipe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from baxy_mind import __main__ as sidecar

    read_fd, write_fd = os.pipe()
    try:
        with os.fdopen(read_fd, "rb", closefd=False) as source:
            monkeypatch.setattr(sidecar.sys, "stdin", source)
            reader = sidecar._open_protocol_reader()
            if os.name == "nt":
                assert not os.get_blocking(read_fd)
            os.write(write_fd, b'{"type":"ping"}\n')
            assert reader() == {"type": "ping"}
            os.close(write_fd)
            write_fd = -1
            assert reader() is None
    finally:
        os.close(read_fd)
        if write_fd >= 0:
            os.close(write_fd)
