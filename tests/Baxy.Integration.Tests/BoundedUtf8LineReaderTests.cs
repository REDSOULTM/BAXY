using System.Text;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class BoundedUtf8LineReaderTests
{
    [Test]
    public async Task ReadsUtf8ByBytesAndPreservesTheFollowingLine()
    {
        byte[] input = Encoding.UTF8.GetBytes("café\r\n{}\n");
        await using var stream = new MemoryStream(input);
        var reader = new BoundedUtf8LineReader(stream, maximumLineBytes: 5);

        BoundedUtf8Line? first = await reader.ReadAsync(CancellationToken.None);
        BoundedUtf8Line? second = await reader.ReadAsync(CancellationToken.None);
        BoundedUtf8Line? end = await reader.ReadAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first, Is.Not.Null);
            Assert.That(first!.Value.TooLarge, Is.False);
            Assert.That(Encoding.UTF8.GetString(first.Value.Utf8!), Is.EqualTo("café"));
            Assert.That(second, Is.Not.Null);
            Assert.That(Encoding.UTF8.GetString(second!.Value.Utf8!), Is.EqualTo("{}"));
            Assert.That(end, Is.Null);
        });
    }

    [Test]
    public async Task DrainsAnOversizedLineWithoutRetainingItsPayload()
    {
        byte[] input = Encoding.UTF8.GetBytes(new string('x', 100) + "\n{}\n");
        await using var stream = new MemoryStream(input);
        var reader = new BoundedUtf8LineReader(stream, maximumLineBytes: 16);

        BoundedUtf8Line? oversized = await reader.ReadAsync(CancellationToken.None);
        BoundedUtf8Line? recovered = await reader.ReadAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(oversized, Is.Not.Null);
            Assert.That(oversized!.Value.TooLarge, Is.True);
            Assert.That(oversized.Value.Utf8, Is.Null);
            Assert.That(recovered, Is.Not.Null);
            Assert.That(Encoding.UTF8.GetString(recovered!.Value.Utf8!), Is.EqualTo("{}"));
        });
    }

    [Test]
    public async Task RejectsMoreThanOneMebibyteEvenWithoutANewline()
    {
        const int maximum = 1024 * 1024;
        await using var stream = new MemoryStream(new byte[maximum + 1]);
        var reader = new BoundedUtf8LineReader(stream, maximum);

        BoundedUtf8Line? received = await reader.ReadAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(received, Is.Not.Null);
            Assert.That(received!.Value.TooLarge, Is.True);
            Assert.That(received.Value.Utf8, Is.Null);
        });
    }

    [Test]
    public async Task AppliesTheLimitToUtf8BytesInsteadOfUtf16Characters()
    {
        await using var stream = new MemoryStream(Encoding.UTF8.GetBytes("ééé\n"));
        var reader = new BoundedUtf8LineReader(stream, maximumLineBytes: 4);

        BoundedUtf8Line? received = await reader.ReadAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(received, Is.Not.Null);
            Assert.That(received!.Value.TooLarge, Is.True);
            Assert.That(received.Value.Utf8, Is.Null);
        });
    }

    [Test]
    public async Task PreservesAValidLineSplitAcrossMultipleReads()
    {
        await using var stream = new ChunkedReadStream(
            Encoding.UTF8.GetBytes("caf\u00e9\r\nnext\n"),
            maximumReadBytes: 2);
        var reader = new BoundedUtf8LineReader(stream, maximumLineBytes: 16);

        BoundedUtf8Line? first = await reader.ReadAsync(CancellationToken.None);
        BoundedUtf8Line? second = await reader.ReadAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first, Is.Not.Null);
            Assert.That(Encoding.UTF8.GetString(first!.Value.Utf8!), Is.EqualTo("caf\u00e9"));
            Assert.That(second, Is.Not.Null);
            Assert.That(Encoding.UTF8.GetString(second!.Value.Utf8!), Is.EqualTo("next"));
        });
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
}
