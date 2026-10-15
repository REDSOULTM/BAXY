using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Ronda 19 «app-cerrada-se-abre» (uso real r17: t1-c09 «mandale a Ron92 por discord que hoy no llego a
/// jugar…», t2-c07 «… que llego en 10 min…», t3-c07 «mandale a ron92 por discord que ya voy saliendo…»,
/// Discord closed): message.recipient.resolve with a named client opens it first (D59 §1, as the draft and
/// the reviewed send do) instead of answering «discord_client_not_running». A client nobody named is never
/// opened. Fake automation only: nothing here clicks.
/// </summary>
[TestFixture]
public sealed class R19ClienteCerradoSeAbreTests
{
    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    private static string TemporaryStore() =>
        Path.Combine(Path.GetTempPath(), "baxy-r19-" + Guid.NewGuid().ToString("N"), "recipient-channels.v1.json");

    // A client is running only after EnsureClientOpenAsync opened it (or when it starts open).
    private sealed class ClosedClients(DesktopClientReadiness opening, params string[] openAtStart)
        : IDesktopMessagingAutomation
    {
        private readonly HashSet<string> _running = new(openAtStart, StringComparer.Ordinal);

        internal List<string> Steps { get; } = [];

        public ValueTask<DesktopClientReadiness> EnsureClientOpenAsync(string channel, CancellationToken cancellationToken)
        {
            Steps.Add("ensure:" + channel);
            if (_running.Contains(channel))
            {
                return ValueTask.FromResult(DesktopClientReadiness.AlreadyOpen);
            }

            if (opening.Ready)
            {
                _running.Add(channel);
            }

            return ValueTask.FromResult(opening);
        }

        public ValueTask<DesktopRecipientObservation> ResolveAsync(string channel, string recipient, CancellationToken cancellationToken)
        {
            Steps.Add($"resolve:{channel}:{recipient}");
            return ValueTask.FromResult(_running.Contains(channel)
                ? new DesktopRecipientObservation(true, true, (nint)42, 7, null)
                : new DesktopRecipientObservation(false, false, 0, 0, channel + "_client_not_running"));
        }

        public ValueTask<DesktopMessageObservation> SendAsync(ResolvedRecipient recipient, string text, CancellationToken cancellationToken)
        {
            Steps.Add("send:" + recipient.DisplayName);
            return ValueTask.FromResult(new DesktopMessageObservation(true, true, "hash", null));
        }
    }

    private static async Task<(ExternalCapabilityReceipt Receipt, List<string> Steps)> ResolveAsync(
        ClosedClients automation, string channel, string recipient)
    {
        using var adapter = new DesktopMessagingAdapter(automation, TemporaryStore());
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "message.recipient.resolve",
            Json($$"""{"channel":"{{channel}}","recipient":"{{recipient}}"}"""),
            CancellationToken.None);
        return (receipt, automation.Steps);
    }

    // t1-c09, t2-c07 («Ron92») and t3-c07 («ron92»): Discord closed, named in the request.
    [TestCase("Ron92")]
    [TestCase("ron92")]
    public async Task ANamedClosedClientIsOpenedBeforeItsRecipientIsLookedFor(string recipient)
    {
        var automation = new ClosedClients(new DesktopClientReadiness(true, true, null));
        (ExternalCapabilityReceipt receipt, List<string> steps) = await ResolveAsync(automation, "discord", recipient);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("channel").GetString(), Is.EqualTo("discord"));
            Assert.That(steps, Is.EqualTo(new[] { "ensure:discord", "resolve:discord:" + recipient }));
        });
    }

    [Test]
    public async Task ANamedClientAlreadyOpenIsResolvedAsBefore()
    {
        var automation = new ClosedClients(new DesktopClientReadiness(true, true, null), "discord");
        (ExternalCapabilityReceipt receipt, List<string> steps) = await ResolveAsync(automation, "discord", "Ron92");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(steps, Is.EqualTo(new[] { "ensure:discord", "resolve:discord:Ron92" }));
        });
    }

    // Contracaso: a client that is not installed is said as such and nothing else is touched.
    [Test]
    public async Task ANamedClientThatIsNotInstalledIsSaidAndNothingIsLookedFor()
    {
        var automation = new ClosedClients(new DesktopClientReadiness(false, false, "discord_client_not_installed"));
        (ExternalCapabilityReceipt receipt, List<string> steps) = await ResolveAsync(automation, "discord", "Ron92");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("discord_client_not_installed"));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(steps, Is.EqualTo(new[] { "ensure:discord" }));
        });
    }

    // A launch that did not get ready in time keeps the effect undenied and its own cause.
    [Test]
    public async Task ANamedClientOpenedButNotReadyIsAnHonestFailure()
    {
        var automation = new ClosedClients(new DesktopClientReadiness(false, true, null));
        (ExternalCapabilityReceipt receipt, List<string> steps) = await ResolveAsync(automation, "discord", "Ron92");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("discord_client_not_running"));
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(steps, Is.EqualTo(new[] { "ensure:discord" }));
        });
    }

    // Contracaso: no client named and none open: still «not found», and neither client is opened.
    [Test]
    public async Task NoClientNamedAndNoneOpenIsNotFoundWithoutOpeningEither()
    {
        var automation = new ClosedClients(new DesktopClientReadiness(true, true, null));
        (ExternalCapabilityReceipt receipt, List<string> steps) = await ResolveAsync(automation, "any", "Ron92");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("recipient_not_found_in_clients"));
            Assert.That(steps.Where(static step => step.StartsWith("ensure:", StringComparison.Ordinal)), Is.Empty);
        });
    }
}
