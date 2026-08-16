using System.IO;

namespace Baxy.App;

internal readonly record struct BoundedUtf8Line(byte[]? Utf8, bool TooLarge);

internal sealed class BoundedUtf8LineReader
{
    private readonly Stream _input;
    private readonly int _maximumLineBytes;
    private readonly byte[] _buffer = new byte[8192];
    private int _bufferOffset;
    private int _bufferCount;

    public BoundedUtf8LineReader(Stream input, int maximumLineBytes)
    {
        _input = input ?? throw new ArgumentNullException(nameof(input));
        ArgumentOutOfRangeException.ThrowIfNegativeOrZero(maximumLineBytes);
        _maximumLineBytes = maximumLineBytes;
    }

    public async ValueTask<BoundedUtf8Line?> ReadAsync(CancellationToken cancellationToken)
    {
        MemoryStream? payload = null;
        bool tooLarge = false;
        bool sawData = false;

        try
        {
            while (true)
            {
                if (_bufferCount == 0)
                {
                    _bufferOffset = 0;
                    _bufferCount = await _input.ReadAsync(_buffer, cancellationToken)
                        .ConfigureAwait(false);
                    if (_bufferCount == 0)
                    {
                        return sawData ? CreateResult(payload, tooLarge) : null;
                    }
                }

                ReadOnlySpan<byte> available = _buffer.AsSpan(_bufferOffset, _bufferCount);
                int newlineIndex = available.IndexOf((byte)'\n');
                int bytesBeforeNewline = newlineIndex >= 0 ? newlineIndex : available.Length;
                if (newlineIndex >= 0 && payload is null)
                {
                    int fastPathConsumed = bytesBeforeNewline + 1;
                    _bufferOffset += fastPathConsumed;
                    _bufferCount -= fastPathConsumed;
                    return CreateResult(available[..bytesBeforeNewline]);
                }

                if (bytesBeforeNewline > 0)
                {
                    sawData = true;
                    if (!tooLarge)
                    {
                        payload ??= new MemoryStream(
                            capacity: (int)Math.Min(
                                _maximumLineBytes + 1L,
                                _buffer.Length));
                        long remaining = _maximumLineBytes + 1L - payload.Length;
                        if (bytesBeforeNewline <= remaining)
                        {
                            payload.Write(available[..bytesBeforeNewline]);
                        }
                        else
                        {
                            tooLarge = true;
                        }
                    }
                }

                int consumed = bytesBeforeNewline + (newlineIndex >= 0 ? 1 : 0);
                _bufferOffset += consumed;
                _bufferCount -= consumed;
                if (newlineIndex >= 0)
                {
                    return CreateResult(payload, tooLarge);
                }
            }
        }
        finally
        {
            payload?.Dispose();
        }
    }

    private BoundedUtf8Line CreateResult(MemoryStream? payload, bool tooLarge)
    {
        if (tooLarge)
        {
            return new BoundedUtf8Line(null, TooLarge: true);
        }

        byte[] bytes = payload?.ToArray() ?? [];
        if (bytes.Length > 0 && bytes[^1] == (byte)'\r')
        {
            Array.Resize(ref bytes, bytes.Length - 1);
        }

        return bytes.Length <= _maximumLineBytes
            ? new BoundedUtf8Line(bytes, TooLarge: false)
            : new BoundedUtf8Line(null, TooLarge: true);
    }

    private BoundedUtf8Line CreateResult(ReadOnlySpan<byte> payload)
    {
        if (payload.Length > 0 && payload[^1] == (byte)'\r')
        {
            payload = payload[..^1];
        }

        return payload.Length <= _maximumLineBytes
            ? new BoundedUtf8Line(payload.ToArray(), TooLarge: false)
            : new BoundedUtf8Line(null, TooLarge: true);
    }
}
