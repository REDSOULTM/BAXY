using System.Text.Json;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// M120 (owner decision D59 §1, 2026-10-02): WhatsApp and Discord are installed
/// and signed in on this PC, so a message left written that finds the client
/// closed opens it first (the app.open of that client, its window waited for on a
/// bounded clock) and then drafts; nothing is ever sent from here, and a client
/// that is not installed is said as such.
/// </summary>
[TestFixture]
public sealed class M120ClienteCerradoTests
{
    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    private sealed class ClientAutomation(DesktopClientReadiness readiness) : IDesktopMessagingAutomation
    {
        internal List<string> Steps { get; } = [];

        public ValueTask<DesktopClientReadiness> EnsureClientOpenAsync(string channel, CancellationToken cancellationToken)
        {
            Steps.Add("ensure:" + channel);
            return ValueTask.FromResult(readiness);
        }

        public ValueTask<DesktopRecipientObservation> ResolveAsync(string channel, string recipient, CancellationToken cancellationToken)
        {
            Steps.Add("resolve:" + recipient);
            return ValueTask.FromResult(new DesktopRecipientObservation(true, true, (nint)42, 7, null));
        }

        public ValueTask<DesktopMessageObservation> SendAsync(ResolvedRecipient recipient, string text, CancellationToken cancellationToken)
        {
            Steps.Add("send:" + recipient.DisplayName);
            return ValueTask.FromResult(new DesktopMessageObservation(true, true, "hash", null));
        }

        public ValueTask<DesktopMessageObservation> DraftAsync(ResolvedRecipient recipient, string text, CancellationToken cancellationToken)
        {
            Steps.Add("draft:" + text);
            return ValueTask.FromResult(new DesktopMessageObservation(true, true, "hash", null));
        }
    }

    private static string TemporaryStore() =>
        Path.Combine(Path.GetTempPath(), "baxy-m120-" + Guid.NewGuid().ToString("N"), "recipient-channels.v1.json");

    private static async Task<(ExternalCapabilityReceipt Receipt, List<string> Steps)> DraftAsync(
        DesktopClientReadiness readiness, string channel = "whatsapp")
    {
        var automation = new ClientAutomation(readiness);
        using var adapter = new DesktopMessagingAdapter(automation, TemporaryStore());
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "message.draft",
            Json($$"""{"channel":"{{channel}}","recipient":"Tere","text":"llego en diez"}"""),
            CancellationToken.None);
        return (receipt, automation.Steps);
    }

    [Test]
    public async Task AClosedClientIsOpenedBeforeTheDraftAndNothingIsSent()
    {
        (ExternalCapabilityReceipt receipt, List<string> steps) = await DraftAsync(new(true, true, null));

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(steps, Is.EqualTo(new[] { "ensure:whatsapp", "resolve:Tere", "draft:llego en diez" }));
            Assert.That(receipt.Result?.GetProperty("clientOpened").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("sent").GetBoolean(), Is.False);
        });
    }

    [Test]
    public async Task AClientAlreadyOpenIsNotOpenedAgain()
    {
        (ExternalCapabilityReceipt receipt, _) = await DraftAsync(DesktopClientReadiness.AlreadyOpen, "discord");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("clientOpened").GetBoolean(), Is.False);
        });
    }

    [Test]
    public async Task AClientThatIsNotInstalledIsSaidAndNothingIsTouched()
    {
        (ExternalCapabilityReceipt receipt, List<string> steps) =
            await DraftAsync(new(false, false, "whatsapp_client_not_installed"));

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("whatsapp_client_not_installed"));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(steps, Is.EqualTo(new[] { "ensure:whatsapp" }));
        });
    }

    [Test]
    public async Task AClientOpenedButNotReadyInTimeIsAnHonestFailure()
    {
        (ExternalCapabilityReceipt receipt, List<string> steps) =
            await DraftAsync(new(false, true, "discord_client_open_not_verified"), "discord");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("discord_client_open_not_verified"));
            // The launch may have happened: the effect is not denied.
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(steps, Is.EqualTo(new[] { "ensure:discord" }));
        });
    }

    [Test]
    public async Task TheTestChannelsClientIsOpenedBeforeTheReviewedSend()
    {
        var automation = new ClientAutomation(new(true, true, null));
        using var adapter = new DesktopMessagingAdapter(automation, TemporaryStore());
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "message.send.test",
            Json("""{"channel":"whatsapp","requestedRecipient":"Tere","text":"hola"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(automation.Steps, Is.EqualTo(new[] { "ensure:whatsapp", "resolve:Música", "send:Música" }));
            Assert.That(receipt.Result?.GetProperty("clientOpened").GetBoolean(), Is.True);
        });
    }

    private static ApplicationOpenResult Opened(bool succeeded, string? error, bool launchIssued) =>
        new(succeeded, succeeded, "WhatsApp", false, succeeded ? 9 : null, succeeded ? 99 : null, error,
            new ApplicationLaunchReceipt("msgclient_x", "WhatsApp", launchIssued, false, null, null, null, null, null,
                null, error));

    [Test]
    public void TheOpenResultSaysWhyThereIsNoClient()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsDesktopMessagingAutomation.ClientOpenFailure("whatsapp", Opened(true, null, true)), Is.Null);
            Assert.That(
                WindowsDesktopMessagingAutomation.ClientOpenFailure(
                    "whatsapp", Opened(false, ApplicationOpenErrorCodes.ApplicationNotFound, false)),
                Is.EqualTo(new DesktopClientReadiness(false, false, "whatsapp_client_not_installed")));
            Assert.That(
                WindowsDesktopMessagingAutomation.ClientOpenFailure(
                    "discord", Opened(false, ApplicationOpenErrorCodes.VerificationFailed, true)),
                Is.EqualTo(new DesktopClientReadiness(false, true, "discord_client_open_not_verified")));
            Assert.That(
                WindowsDesktopMessagingAutomation.ClientOpenFailure(
                    "discord", Opened(false, ApplicationOpenErrorCodes.LaunchFailed, false)),
                Is.EqualTo(new DesktopClientReadiness(false, false, "discord_client_open_not_verified")));
        });
    }

    [TestCase("WhatsApp", true)]
    [TestCase("#general | Amigos - Discord", true)]
    [TestCase("Discord", true)]
    [TestCase("Discord Updater", false)]
    [TestCase("", false)]
    public void OnlyTheClientsMainWindowIsReady(string title, bool ready)
    {
        Assert.That(WindowsDesktopMessagingAutomation.ClientWindowReady(title), Is.EqualTo(ready));
    }

    [TestCase("whatsapp", "WhatsApp")]
    [TestCase("discord", "Discord")]
    public void TheClientIsOpenedByItsInstalledName(string channel, string name)
    {
        Assert.That(WindowsDesktopMessagingAutomation.ClientApplicationName(channel), Is.EqualTo(name));
    }
}
