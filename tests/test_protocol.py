from __future__ import annotations

import io

import pytest

from baxy_mind.protocol import MAX_LINE_BYTES, ProtocolViolation, read_message


class _BoundedReadProbe:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.requested_limit: int | None = None

    def readline(self, limit: int = -1) -> bytes:
        self.requested_limit = limit
        if limit < 0:
            raise AssertionError("read_message intentó leer una línea sin límite")
        return self._payload[:limit]


class _ChunkedDescriptorRead:
    def __init__(self, *chunks: bytes) -> None:
        self._chunks = list(chunks)
        self.requested_limits: list[int] = []

    def __call__(self, descriptor: int, limit: int) -> bytes:
        assert descriptor == 7
        self.requested_limits.append(limit)
        if not self._chunks:
            return b""
        chunk = self._chunks[0]
        result = chunk[:limit]
        remainder = chunk[limit:]
        if remainder:
            self._chunks[0] = remainder
        else:
            self._chunks.pop(0)
        return result


def test_protocol_bounds_the_stream_read_before_allocating_the_line() -> None:
    stream = _BoundedReadProbe(b"x" * (MAX_LINE_BYTES + 2))

    with pytest.raises(ProtocolViolation) as raised:
        read_message(stream)

    assert stream.requested_limit == MAX_LINE_BYTES + 1
    assert raised.value.code == "line_too_large"


def test_protocol_accepts_a_valid_message_at_the_existing_boundary() -> None:
    padding = MAX_LINE_BYTES - len(b'{"type":"ping","padding":""}')
    payload = b'{"type":"ping","padding":"' + (b"x" * padding) + b'"}'
    assert len(payload) == MAX_LINE_BYTES

    message = read_message(io.BytesIO(payload))

    assert message is not None
    assert message["type"] == "ping"
    assert len(message["padding"]) == padding


def test_descriptor_reader_preserves_split_and_buffered_lines() -> None:
    from baxy_mind import protocol

    source = _ChunkedDescriptorRead(
        b'{"type":"fir',
        b'st"}\n{"type":"second"}\n',
    )
    reader = protocol._BoundedFileDescriptorLineReader(
        7,
        read=source,
        chunk_bytes=64,
    )

    assert read_message(reader) == {"type": "first"}
    assert read_message(reader) == {"type": "second"}
    assert read_message(reader) is None
    assert source.requested_limits
    assert max(source.requested_limits) <= 64


def test_descriptor_reader_accepts_eof_without_a_newline() -> None:
    from baxy_mind import protocol

    source = _ChunkedDescriptorRead(b'{"type":"ping"}')
    reader = protocol._BoundedFileDescriptorLineReader(7, read=source)

    assert read_message(reader) == {"type": "ping"}
    assert read_message(reader) is None


@pytest.mark.parametrize(
    ("suffix", "expected_code"),
    [
        (b"", None),
        (b"\n", "line_too_large"),
        (b"x", "line_too_large"),
    ],
)
def test_descriptor_reader_enforces_the_exact_protocol_boundary(
    suffix: bytes,
    expected_code: str | None,
) -> None:
    from baxy_mind import protocol

    padding = MAX_LINE_BYTES - len(b'{"type":"ping","padding":""}')
    payload = b'{"type":"ping","padding":"' + (b"x" * padding) + b'"}'
    source = _ChunkedDescriptorRead(payload + suffix)
    reader = protocol._BoundedFileDescriptorLineReader(7, read=source)

    if expected_code is None:
        message = read_message(reader)
        assert message is not None
        assert message["type"] == "ping"
    else:
        with pytest.raises(ProtocolViolation) as raised:
            read_message(reader)
        assert raised.value.code == expected_code


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        (b"\xff\n", "malformed_utf8"),
        (b"{\n", "malformed_json"),
        (b"{}\n", "missing_type"),
    ],
)
def test_descriptor_reader_preserves_malformed_message_codes(
    payload: bytes,
    expected_code: str,
) -> None:
    from baxy_mind import protocol

    source = _ChunkedDescriptorRead(payload)
    reader = protocol._BoundedFileDescriptorLineReader(7, read=source)

    with pytest.raises(ProtocolViolation) as raised:
        read_message(reader)

    assert raised.value.code == expected_code
