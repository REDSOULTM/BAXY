using System.Buffers;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Core;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class CoreJsonlProtocolTests
{
    private static readonly JsonSerializerOptions VisibleFactOptions = new()
    {
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    [Test]
    public async Task DenseUnicodeResponseCrossesCoreWriterAndAppReaderWithoutLosingFollowingFrame()
    {
        string message = JsonSerializer.Serialize(new
        {
            observed = new
            {
                text = string.Concat(Enumerable.Repeat("á中🙂\"\\\n", 1000)),
                layout = new { available = true, lines = Array.Empty<object>() },
            },
        }, VisibleFactOptions);
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"), Guid.NewGuid().ToString("D"),
            OperationStatuses.Completed, message, true, false, JsonSerializer.SerializeToElement(new { text = message }), null);
        OperationResponse following = response with { RequestId = Guid.NewGuid().ToString("D"), Message = "next", Result = null };
        byte[] firstWire = ProtocolJson.SerializeBoundedToUtf8Bytes(response, CoreProcessClient.MaximumProtocolLineLength);
        byte[] nextWire = ProtocolJson.SerializeBoundedToUtf8Bytes(following, CoreProcessClient.MaximumProtocolLineLength);
        await using var output = new RecordingMemoryStream();
        await Program.WriteMessageAsync(output, firstWire, CancellationToken.None);
        await Program.WriteMessageAsync(output, nextWire, CancellationToken.None);
        await using var input = new ChunkedReadStream(output.ToArray(), maximumReadBytes: 7);
        var reader = new BoundedUtf8LineReader(input, CoreProcessClient.MaximumProtocolLineLength);

        BoundedUtf8Line? first = await reader.ReadAsync(CancellationToken.None);
        BoundedUtf8Line? next = await reader.ReadAsync(CancellationToken.None);
        BoundedUtf8Line? end = await reader.ReadAsync(CancellationToken.None);
        OperationResponse restored = ProtocolJson.DeserializeResponse(first!.Value.Utf8!);

        Assert.Multiple(() =>
        {
            Assert.That(message.Length, Is.GreaterThan(4096).And.LessThanOrEqualTo(48_000));
            Assert.That(first.Value.TooLarge, Is.False);
            Assert.That(first.Value.Utf8, Is.EqualTo(firstWire));
            Assert.That(restored.Message, Is.EqualTo(message));
            Assert.That(JsonElement.DeepEquals(restored.Result!.Value, response.Result!.Value), Is.True);
            Assert.That(restored.InvocationId, Is.EqualTo(response.InvocationId));
            Assert.That(restored.Verified, Is.True);
            Assert.That(ProtocolJson.DeserializeResponse(next!.Value.Utf8!).RequestId, Is.EqualTo(following.RequestId));
            Assert.That(next.Value.Utf8, Is.EqualTo(nextWire));
            Assert.That(output.WriteCalls, Is.EqualTo(2));
            Assert.That(output.FlushCalls, Is.EqualTo(2));
            Assert.That(end, Is.Null);
        });
    }

    [Test]
    public async Task ReaderPreservesLfCrLfLimitsAndFollowingFrames()
    {
        const int maximumLineBytes = 8;
        byte[] input = Encoding.UTF8.GetBytes(
            "12345678\nabcdefgh\r\n123456789\n\nnext\n");
        await using var stream = new MemoryStream(input);
        var reader = new Program.BoundedLineReader(stream, maximumLineBytes);

        Program.ProtocolLine? exactLf = await reader.ReadAsync(CancellationToken.None);
        Program.ProtocolLine? exactCrLf = await reader.ReadAsync(CancellationToken.None);
        Program.ProtocolLine? tooLarge = await reader.ReadAsync(CancellationToken.None);
        Program.ProtocolLine? empty = await reader.ReadAsync(CancellationToken.None);
        Program.ProtocolLine? following = await reader.ReadAsync(CancellationToken.None);
        Program.ProtocolLine? end = await reader.ReadAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            AssertLine(exactLf, "12345678");
            AssertLine(exactCrLf, "abcdefgh");
            Assert.That(tooLarge, Is.Not.Null);
            Assert.That(tooLarge!.Value.TooLarge, Is.True);
            Assert.That(tooLarge.Value.Utf8, Is.Null);
            AssertLine(empty, string.Empty);
            AssertLine(following, "next");
            Assert.That(end, Is.Null);
        });
    }

    [Test]
    public async Task ReaderPreservesSplitCrLfAndUnterminatedEof()
    {
        await using var stream = new ChunkedReadStream(
            Encoding.UTF8.GetBytes("caf\u00e9\r\nunterminated"),
            maximumReadBytes: 2);
        var reader = new Program.BoundedLineReader(stream, maximumLineBytes: 32);

        Program.ProtocolLine? first = await reader.ReadAsync(CancellationToken.None);
        Program.ProtocolLine? second = await reader.ReadAsync(CancellationToken.None);
        Program.ProtocolLine? end = await reader.ReadAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            AssertLine(first, "caf\u00e9");
            AssertLine(second, "unterminated");
            Assert.That(end, Is.Null);
        });
    }

    [Test]
    public async Task ReaderDrainsOversizedFrameBeforeReturningFollowingFrame()
    {
        byte[] input = Encoding.UTF8.GetBytes(new string('x', 20_000) + "\n{}\n");
        await using var stream = new ChunkedReadStream(input, maximumReadBytes: 127);
        var reader = new Program.BoundedLineReader(stream, maximumLineBytes: 64);

        Program.ProtocolLine? oversized = await reader.ReadAsync(CancellationToken.None);
        Program.ProtocolLine? recovered = await reader.ReadAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(oversized, Is.Not.Null);
            Assert.That(oversized!.Value.TooLarge, Is.True);
            Assert.That(oversized.Value.Utf8, Is.Null);
            AssertLine(recovered, "{}");
        });
    }

    [Test]
    public async Task ReaderRejectsOversizedUnterminatedFrameAtEof()
    {
        await using var stream = new MemoryStream(new byte[65]);
        var reader = new Program.BoundedLineReader(stream, maximumLineBytes: 64);

        Program.ProtocolLine? oversized = await reader.ReadAsync(CancellationToken.None);
        Program.ProtocolLine? end = await reader.ReadAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(oversized, Is.Not.Null);
            Assert.That(oversized!.Value.TooLarge, Is.True);
            Assert.That(oversized.Value.Utf8, Is.Null);
            Assert.That(end, Is.Null);
        });
    }

    [Test]
    public async Task WriterPublishesPayloadAndLfWithOneWriteAndOneFlush()
    {
        byte[] payload = Encoding.UTF8.GetBytes("{\"message\":\"caf\u00e9\"}");
        var pool = new TrackingArrayPool();
        await using var output = new RecordingMemoryStream();

        await Program.WriteMessageAsync(
            output,
            payload,
            pool,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(
                output.ToArray(),
                Is.EqualTo(Encoding.UTF8.GetBytes("{\"message\":\"caf\u00e9\"}\n")));
            Assert.That(output.WriteCalls, Is.EqualTo(1));
            Assert.That(output.FlushCalls, Is.EqualTo(1));
            Assert.That(pool.RentCalls, Is.EqualTo(1));
            Assert.That(pool.ReturnCalls, Is.EqualTo(1));
            AssertUsedRangeWasZeroed(pool, payload.Length + 1);
        });
    }

    [Test]
    public void WriterZeroesAndReturnsRentedFrameWhenFlushFails()
    {
        byte[] payload = Encoding.UTF8.GetBytes("{\"secret\":\"value\"}");
        var pool = new TrackingArrayPool();
        using var output = new RecordingMemoryStream(failFlush: true);

        Assert.ThrowsAsync<IOException>(
            async () => await Program.WriteMessageAsync(
                output,
                payload,
                pool,
                CancellationToken.None));

        Assert.Multiple(() =>
        {
            Assert.That(output.WriteCalls, Is.EqualTo(1));
            Assert.That(output.FlushCalls, Is.EqualTo(1));
            Assert.That(pool.ReturnCalls, Is.EqualTo(1));
            AssertUsedRangeWasZeroed(pool, payload.Length + 1);
        });
    }

    [Test]
    public void WriterHonorsPreCanceledTokenBeforeRentingOrPublishing()
    {
        using var cancellation = new CancellationTokenSource();
        cancellation.Cancel();
        var pool = new TrackingArrayPool();
        using var output = new RecordingMemoryStream();

        Assert.ThrowsAsync<OperationCanceledException>(
            async () => await Program.WriteMessageAsync(
                output,
                Encoding.UTF8.GetBytes("{}"),
                pool,
                cancellation.Token));

        Assert.Multiple(() =>
        {
            Assert.That(pool.RentCalls, Is.Zero);
            Assert.That(output.WriteCalls, Is.Zero);
            Assert.That(output.FlushCalls, Is.Zero);
        });
    }

    private static void AssertLine(Program.ProtocolLine? line, string expected)
    {
        Assert.That(line, Is.Not.Null);
        Assert.That(line!.Value.TooLarge, Is.False);
        Assert.That(Encoding.UTF8.GetString(line.Value.Utf8!), Is.EqualTo(expected));
    }

    private static void AssertUsedRangeWasZeroed(TrackingArrayPool pool, int wireLength)
    {
        Assert.That(pool.ReturnedArray, Is.Not.Null);
        byte[] returnedArray = pool.ReturnedArray!;
        Assert.That(
            returnedArray.AsSpan(0, wireLength).ToArray(),
            Is.All.EqualTo((byte)0));
        Assert.That(returnedArray[wireLength], Is.EqualTo((byte)0xA5));
    }

    private sealed class ChunkedReadStream(byte[] buffer, int maximumReadBytes)
        : MemoryStream(buffer)
    {
        public override ValueTask<int> ReadAsync(
            Memory<byte> destination,
            CancellationToken cancellationToken = default) =>
            base.ReadAsync(
                destination[..Math.Min(destination.Length, maximumReadBytes)],
                cancellationToken);
    }

    private sealed class RecordingMemoryStream(bool failFlush = false) : MemoryStream
    {
        public int WriteCalls { get; private set; }

        public int FlushCalls { get; private set; }

        public override ValueTask WriteAsync(
            ReadOnlyMemory<byte> buffer,
            CancellationToken cancellationToken = default)
        {
            WriteCalls++;
            return base.WriteAsync(buffer, cancellationToken);
        }

        public override Task FlushAsync(CancellationToken cancellationToken)
        {
            FlushCalls++;
            return failFlush
                ? Task.FromException(new IOException("Injected flush failure."))
                : base.FlushAsync(cancellationToken);
        }
    }

    private sealed class TrackingArrayPool : ArrayPool<byte>
    {
        public int RentCalls { get; private set; }

        public int ReturnCalls { get; private set; }

        public byte[]? ReturnedArray { get; private set; }

        public override byte[] Rent(int minimumLength)
        {
            RentCalls++;
            byte[] buffer = new byte[checked(minimumLength + 16)];
            buffer.AsSpan().Fill(0xA5);
            return buffer;
        }

        public override void Return(byte[] array, bool clearArray = false)
        {
            ReturnCalls++;
            ReturnedArray = array;
        }
    }
}
