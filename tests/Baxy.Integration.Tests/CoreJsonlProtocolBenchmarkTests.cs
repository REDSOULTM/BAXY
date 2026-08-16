using System.Diagnostics;
using System.IO.Pipes;
using System.Text;
using Baxy.Core;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class CoreJsonlProtocolBenchmarkTests
{
    private const int ReaderFrameCount = 25_000;
    private const int WriterFrameCount = 20_000;
    private static readonly byte[] Newline = [(byte)'\n'];

    [Test]
    [Explicit("Microbenchmark reproducible del transporte JSONL del Core; no es una compuerta temporal.")]
    public async Task CompareLegacyAndCurrentCoreJsonlTransport()
    {
        byte[] readerFixture = CreateReaderFixture(ReaderFrameCount);
        byte[] readerWarmup = CreateReaderFixture(256);
        byte[] writerPayload = Encoding.UTF8.GetBytes(
            $"{{\"message\":\"{new string('x', 1_000)}\"}}");

        await ConsumeLegacyReaderAsync(readerWarmup, 2048, 256);
        await ConsumeCurrentReaderAsync(readerWarmup, 2048, 256);
        await WriteLegacyFramesAsync(writerPayload, 256);
        await WriteCurrentFramesAsync(writerPayload, 256);

        Measurement legacyReader = await MeasureAsync(
            () => ConsumeLegacyReaderAsync(readerFixture, 2048, ReaderFrameCount));
        Measurement currentReader = await MeasureAsync(
            () => ConsumeCurrentReaderAsync(readerFixture, 2048, ReaderFrameCount));
        WriteMeasurement legacyWriter = await MeasureWritesAsync(
            writerPayload,
            WriterFrameCount,
            useLegacyWriter: true);
        WriteMeasurement currentWriter = await MeasureWritesAsync(
            writerPayload,
            WriterFrameCount,
            useLegacyWriter: false);

        TestContext.Out.WriteLine(
            $"reader legacy: {legacyReader.Elapsed.TotalMilliseconds:F2} ms, " +
            $"{legacyReader.AllocatedBytes:N0} B allocated");
        TestContext.Out.WriteLine(
            $"reader current: {currentReader.Elapsed.TotalMilliseconds:F2} ms, " +
            $"{currentReader.AllocatedBytes:N0} B allocated");
        TestContext.Out.WriteLine(
            $"writer legacy: {legacyWriter.Elapsed.TotalMilliseconds:F2} ms, " +
            $"{legacyWriter.WriteCalls:N0} writes, {legacyWriter.FlushCalls:N0} flushes");
        TestContext.Out.WriteLine(
            $"writer current: {currentWriter.Elapsed.TotalMilliseconds:F2} ms, " +
            $"{currentWriter.WriteCalls:N0} writes, {currentWriter.FlushCalls:N0} flushes");

        Assert.Multiple(() =>
        {
            Assert.That(legacyWriter.WriteCalls, Is.EqualTo(WriterFrameCount * 2L));
            Assert.That(currentWriter.WriteCalls, Is.EqualTo(WriterFrameCount));
            Assert.That(currentWriter.FlushCalls, Is.EqualTo(WriterFrameCount));
        });
    }

    private static byte[] CreateReaderFixture(int frameCount)
    {
        byte[] frame = Encoding.UTF8.GetBytes(
            $"{{\"message\":\"{new string('x', 240)}\"}}\n");
        byte[] fixture = GC.AllocateUninitializedArray<byte>(frame.Length * frameCount);
        for (int offset = 0; offset < fixture.Length; offset += frame.Length)
        {
            frame.CopyTo(fixture, offset);
        }

        return fixture;
    }

    private static async Task ConsumeLegacyReaderAsync(
        byte[] fixture,
        int maximumLineBytes,
        int expectedFrameCount)
    {
        await using var input = new MemoryStream(fixture, writable: false);
        var reader = new LegacyBoundedLineReader(input, maximumLineBytes);
        int count = 0;
        while (await reader.ReadAsync(CancellationToken.None) is not null)
        {
            count++;
        }

        Assert.That(count, Is.EqualTo(expectedFrameCount));
    }

    private static async Task ConsumeCurrentReaderAsync(
        byte[] fixture,
        int maximumLineBytes,
        int expectedFrameCount)
    {
        await using var input = new MemoryStream(fixture, writable: false);
        var reader = new Program.BoundedLineReader(input, maximumLineBytes);
        int count = 0;
        while (await reader.ReadAsync(CancellationToken.None) is not null)
        {
            count++;
        }

        Assert.That(count, Is.EqualTo(expectedFrameCount));
    }

    private static Task WriteLegacyFramesAsync(byte[] payload, int frameCount) =>
        WriteFramesAsync(payload, frameCount, useLegacyWriter: true);

    private static Task WriteCurrentFramesAsync(byte[] payload, int frameCount) =>
        WriteFramesAsync(payload, frameCount, useLegacyWriter: false);

    private static async Task WriteFramesAsync(
        byte[] payload,
        int frameCount,
        bool useLegacyWriter,
        CountingWriteStream? output = null)
    {
        output ??= new CountingWriteStream();
        for (int index = 0; index < frameCount; index++)
        {
            if (useLegacyWriter)
            {
                await WriteLegacyMessageAsync(output, payload, CancellationToken.None)
                    .ConfigureAwait(false);
            }
            else
            {
                await Program.WriteMessageAsync(output, payload, CancellationToken.None)
                    .ConfigureAwait(false);
            }
        }
    }

    private static async ValueTask WriteLegacyMessageAsync(
        Stream output,
        ReadOnlyMemory<byte> message,
        CancellationToken cancellationToken)
    {
        await output.WriteAsync(message, cancellationToken).ConfigureAwait(false);
        await output.WriteAsync(Newline, cancellationToken).ConfigureAwait(false);
        await output.FlushAsync(cancellationToken).ConfigureAwait(false);
    }

    private static async Task<Measurement> MeasureAsync(Func<Task> operation)
    {
        CollectGarbage();
        long allocationStart = GC.GetAllocatedBytesForCurrentThread();
        var stopwatch = Stopwatch.StartNew();
        await operation();
        stopwatch.Stop();
        long allocatedBytes = GC.GetAllocatedBytesForCurrentThread() - allocationStart;
        return new Measurement(stopwatch.Elapsed, allocatedBytes);
    }

    private static async Task<WriteMeasurement> MeasureWritesAsync(
        byte[] payload,
        int frameCount,
        bool useLegacyWriter)
    {
        string pipeName = $"baxy-core-jsonl-benchmark-{Guid.NewGuid():N}";
        await using var server = new NamedPipeServerStream(
            pipeName,
            PipeDirection.Out,
            maxNumberOfServerInstances: 1,
            PipeTransmissionMode.Byte,
            PipeOptions.Asynchronous);
        await using var client = new NamedPipeClientStream(
            ".",
            pipeName,
            PipeDirection.In,
            PipeOptions.Asynchronous);
        Task connection = server.WaitForConnectionAsync();
        await client.ConnectAsync().ConfigureAwait(false);
        await connection.ConfigureAwait(false);

        var output = new CountingWriteStream(server);
        long expectedBytes = checked((long)(payload.Length + 1) * frameCount);
        Task drain = DrainExactlyAsync(client, expectedBytes);
        CollectGarbage();
        long allocationStart = GC.GetAllocatedBytesForCurrentThread();
        var stopwatch = Stopwatch.StartNew();
        await WriteFramesAsync(payload, frameCount, useLegacyWriter, output)
            .ConfigureAwait(false);
        stopwatch.Stop();
        long allocatedBytes = GC.GetAllocatedBytesForCurrentThread() - allocationStart;
        await drain.ConfigureAwait(false);

        return new WriteMeasurement(
            stopwatch.Elapsed,
            allocatedBytes,
            output.WriteCalls,
            output.FlushCalls);
    }

    private static async Task DrainExactlyAsync(Stream input, long expectedBytes)
    {
        byte[] buffer = new byte[64 * 1024];
        long receivedBytes = 0;
        while (receivedBytes < expectedBytes)
        {
            int read = await input.ReadAsync(buffer, CancellationToken.None)
                .ConfigureAwait(false);
            if (read == 0)
            {
                throw new EndOfStreamException(
                    $"Expected {expectedBytes} bytes but received {receivedBytes}.");
            }

            receivedBytes += read;
        }

        Assert.That(receivedBytes, Is.EqualTo(expectedBytes));
    }

    private static void CollectGarbage()
    {
        GC.Collect();
        GC.WaitForPendingFinalizers();
        GC.Collect();
    }

    private readonly record struct Measurement(TimeSpan Elapsed, long AllocatedBytes);

    private readonly record struct WriteMeasurement(
        TimeSpan Elapsed,
        long AllocatedBytes,
        long WriteCalls,
        long FlushCalls);

    private sealed class CountingWriteStream(Stream? inner = null) : Stream
    {
        public long WriteCalls { get; private set; }

        public long FlushCalls { get; private set; }

        public override bool CanRead => false;

        public override bool CanSeek => false;

        public override bool CanWrite => true;

        public override long Length => throw new NotSupportedException();

        public override long Position
        {
            get => throw new NotSupportedException();
            set => throw new NotSupportedException();
        }

        public override void Flush()
        {
            FlushCalls++;
            inner?.Flush();
        }

        public override Task FlushAsync(CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            FlushCalls++;
            return inner?.FlushAsync(cancellationToken) ?? Task.CompletedTask;
        }

        public override int Read(byte[] buffer, int offset, int count) =>
            throw new NotSupportedException();

        public override long Seek(long offset, SeekOrigin origin) =>
            throw new NotSupportedException();

        public override void SetLength(long value) =>
            throw new NotSupportedException();

        public override void Write(byte[] buffer, int offset, int count)
        {
            WriteCalls++;
            inner?.Write(buffer, offset, count);
        }

        public override ValueTask WriteAsync(
            ReadOnlyMemory<byte> buffer,
            CancellationToken cancellationToken = default)
        {
            cancellationToken.ThrowIfCancellationRequested();
            WriteCalls++;
            return inner?.WriteAsync(buffer, cancellationToken) ?? ValueTask.CompletedTask;
        }
    }

    private sealed class LegacyBoundedLineReader(Stream input, int maximumLineBytes)
    {
        private readonly byte[] _buffer = new byte[8192];
        private int _bufferOffset;
        private int _bufferCount;

        public async ValueTask<byte[]?> ReadAsync(CancellationToken cancellationToken)
        {
            using var payload = new MemoryStream(
                capacity: Math.Min(maximumLineBytes + 1, _buffer.Length));
            bool sawData = false;

            while (true)
            {
                if (_bufferCount == 0)
                {
                    _bufferOffset = 0;
                    _bufferCount = await input.ReadAsync(_buffer, cancellationToken)
                        .ConfigureAwait(false);
                    if (_bufferCount == 0)
                    {
                        return sawData ? payload.ToArray() : null;
                    }
                }

                ReadOnlySpan<byte> available = _buffer.AsSpan(_bufferOffset, _bufferCount);
                int newlineIndex = available.IndexOf((byte)'\n');
                int bytesBeforeNewline = newlineIndex >= 0 ? newlineIndex : available.Length;
                if (bytesBeforeNewline > 0)
                {
                    sawData = true;
                    payload.Write(available[..bytesBeforeNewline]);
                }

                int consumed = bytesBeforeNewline + (newlineIndex >= 0 ? 1 : 0);
                _bufferOffset += consumed;
                _bufferCount -= consumed;
                if (newlineIndex >= 0)
                {
                    return payload.ToArray();
                }
            }
        }
    }
}
