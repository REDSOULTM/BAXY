using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;
using Windows.Media.Control;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Revisión nb-q-apps2: a turn canceled while Windows' media sessions are being asked for is the caller's cancel, never
/// «smtc_session_access_failed» (a failure that sends the request on to the next adapter). The manager is a fake.
/// </summary>
[TestFixture]
public sealed class MediaSessionCancelTests
{
    [TestCase("media.status")]
    [TestCase("media.control")]
    public void ACanceledTurnPropagatesItsCancel(string operation)
    {
        using var turn = new CancellationTokenSource();
        var adapter = new WindowsMediaSessionAdapter(static (_, _) => ValueTask.CompletedTask)
        {
            RequestManager = async token =>
            {
                turn.Cancel();
                await Task.Delay(Timeout.InfiniteTimeSpan, token);
                throw new AssertionException("the manager's wait ended without the cancel");
            },
        };

        Assert.CatchAsync<OperationCanceledException>(async () => await adapter.InvokeAsync(
            operation, JsonDocument.Parse("""{"action":"pause"}""").RootElement.Clone(), turn.Token));
    }

    [Test]
    public async Task AManagerThatFailsWithoutACancelIsStillAnAccessFailure()
    {
        var adapter = new WindowsMediaSessionAdapter(static (_, _) => ValueTask.CompletedTask)
        {
            RequestManager = static _ => Task.FromException<GlobalSystemMediaTransportControlsSessionManager>(
                new TimeoutException("unanswered")),
        };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.status", JsonDocument.Parse("{}").RootElement.Clone(), CancellationToken.None);

        Assert.That(receipt.ErrorCode, Is.EqualTo("smtc_session_access_failed"));
    }
}
