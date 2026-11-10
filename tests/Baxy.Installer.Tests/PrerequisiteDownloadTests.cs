using System.Net;
using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// INS-6: the downloads of WebView2 and Visual C++ have the limit BAXY's own parts have. A server that stops sending is
/// given up on, as a network failure; one that sends slowly is waited for as long as it keeps sending.
/// </summary>
[TestFixture]
internal sealed class PrerequisiteDownloadTests
{
    private const string Address = "https://example.invalid/setup.exe";
    private static readonly TimeSpan Limit = TimeSpan.FromMilliseconds(300);
    private string directory = string.Empty;

    [SetUp]
    public void SetUp()
    {
        directory = Path.Combine(Path.GetTempPath(), "baxy-installer-tests", Path.GetRandomFileName());
        Directory.CreateDirectory(directory);
    }

    [TearDown]
    public void TearDown() => Directory.Delete(directory, recursive: true);

    [Test]
    public async Task A_server_that_never_answers_is_given_up_on()
    {
        using HttpClient http = Client(new Server(async cancellation =>
        {
            await Task.Delay(Timeout.Infinite, cancellation);
            return Stream.Null;
        }));

        Exception? failure = await Outcome(http, Limit);

        Assert.That(failure, Is.InstanceOf<HttpRequestException>());
        Assert.That(failure!.Message, Does.Contain(Address));
        Assert.That(Failures.Classify(failure, () => false), Is.EqualTo(FailureKind.Network));
    }

    [Test]
    public async Task A_download_that_stops_halfway_is_given_up_on()
    {
        using HttpClient http = Client(new Server(_ => Task.FromResult<Stream>(
            new Paced(new byte[1000], chunk: 100, pause: TimeSpan.Zero, stopAfter: 400))));

        Exception? failure = await Outcome(http, Limit);

        Assert.That(failure, Is.InstanceOf<HttpRequestException>());
        Assert.That(Failures.Classify(failure!, () => false), Is.EqualTo(FailureKind.Network));
    }

    // 8 pieces 300 ms apart take longer than the 2 s limit, and no piece does: the limit is on silence, not on the whole.
    [Test]
    public async Task A_slow_download_that_keeps_moving_arrives_whole()
    {
        byte[] content = new byte[800];
        Random.Shared.NextBytes(content);
        using HttpClient http = Client(new Server(_ => Task.FromResult<Stream>(
            new Paced(content, chunk: 100, pause: TimeSpan.FromMilliseconds(300), stopAfter: int.MaxValue))));

        Exception? failure = await Outcome(http, TimeSpan.FromSeconds(2));

        Assert.That(failure, Is.Null);
        Assert.That(File.ReadAllBytes(Path.Combine(directory, "setup.exe")), Is.EqualTo(content));
    }

    [Test]
    public void The_person_cancelling_is_not_a_network_failure()
    {
        using HttpClient http = Client(new Server(_ => Task.FromResult<Stream>(
            new Paced(new byte[1000], chunk: 100, pause: TimeSpan.Zero, stopAfter: 400))));
        using CancellationTokenSource person = new(TimeSpan.FromMilliseconds(100));

        Assert.That(
            () => Prerequisites.DownloadAsync(
                http, Address, Path.Combine(directory, "setup.exe"), TimeSpan.FromSeconds(30), person.Token),
            Throws.InstanceOf<OperationCanceledException>());
    }

    // What the download ended with; a download still waiting after 10 s has no limit, and is stopped here.
    private async Task<Exception?> Outcome(HttpClient http, TimeSpan limit)
    {
        using CancellationTokenSource test = new();
        Task download = Prerequisites.DownloadAsync(http, Address, Path.Combine(directory, "setup.exe"), limit, test.Token);
        bool limited = await Task.WhenAny(download, Task.Delay(TimeSpan.FromSeconds(10))) == download;
        if (!limited)
        {
            await test.CancelAsync();
        }

        await download.ContinueWith(_ => { }, TaskScheduler.Default);
        Assert.That(limited, Is.True, "the download was still waiting after 10 s: nothing limits it");
        return download.Exception?.InnerException;
    }

    private static HttpClient Client(HttpMessageHandler handler) => new(handler) { Timeout = Timeout.InfiniteTimeSpan };

    private sealed class Server(Func<CancellationToken, Task<Stream>> body) : HttpMessageHandler
    {
        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken) =>
            new(HttpStatusCode.OK) { Content = new StreamContent(await body(cancellationToken)) };
    }

    // Gives «chunk» bytes after each «pause»; after «stopAfter» bytes it gives no more and does not end either.
    private sealed class Paced(byte[] bytes, int chunk, TimeSpan pause, int stopAfter) : MemoryStream(bytes)
    {
        public override async ValueTask<int> ReadAsync(Memory<byte> buffer, CancellationToken cancellationToken = default)
        {
            if (Position >= stopAfter)
            {
                await Task.Delay(Timeout.Infinite, cancellationToken);
            }

            await Task.Delay(pause, cancellationToken);
            return Read(buffer.Span[..Math.Min(chunk, buffer.Length)]);
        }

        public override Task<int> ReadAsync(byte[] buffer, int offset, int count, CancellationToken cancellationToken) =>
            ReadAsync(buffer.AsMemory(offset, count), cancellationToken).AsTask();
    }
}
