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
            return ValueTask.FromResult(new DesktopRecipientObservation(true, true, (nint)42, 7, null, recipient));
        }

        public ValueTask<DesktopMessageObservation> SendAsync(ResolvedRecipient recipient, string text, CancellationToken cancellationToken)
        {
            Steps.Add("send:" + recipient.Name);
            return ValueTask.FromResult(new DesktopMessageObservation(true, true, "hash", null));
        }

        public ValueTask<DesktopMessageObservation> DraftAsync(ResolvedRecipient recipient, string text, CancellationToken cancellationToken)
        {
            Steps.Add("draft:" + text);
            return ValueTask.FromResult(new DesktopMessageObservation(true, true, "hash", null));
        }
    }

    private static async Task<(ExternalCapabilityReceipt Receipt, List<string> Steps)> DraftAsync(
        DesktopClientReadiness readiness, string channel = "whatsapp")
    {
        var automation = new ClientAutomation(readiness);
        using var adapter = new DesktopMessagingAdapter(automation);
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

    // C6: the test destinations are the owner's private data (a file under the profile's data), never source.
    private static string TestDestinations(string? json)
    {
        string directory = Path.Combine(Path.GetTempPath(), "baxy-m120-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        string path = Path.Combine(directory, "test-destinations.v1.json");
        if (json is not null)
        {
            File.WriteAllText(path, json);
        }

        return path;
    }

    [Test]
    public async Task TheTestChannelsClientIsOpenedBeforeTheReviewedSend()
    {
        var automation = new ClientAutomation(new(true, true, null));
        string destinations = TestDestinations("""{"whatsapp":"Chat de prueba"}""");
        try
        {
            using var adapter = new DesktopMessagingAdapter(automation, destinations);
            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
                "message.send.test",
                Json("""{"channel":"whatsapp","requestedRecipient":"Tere","text":"hola"}"""),
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
                Assert.That(automation.Steps,
                    Is.EqualTo(new[] { "ensure:whatsapp", "resolve:Chat de prueba", "send:Chat de prueba" }));
                Assert.That(receipt.Result?.GetProperty("forcedDestination").GetString(), Is.EqualTo("Chat de prueba"));
                Assert.That(receipt.Result?.GetProperty("clientOpened").GetBoolean(), Is.True);
            });
        }
        finally
        {
            Directory.Delete(Path.GetDirectoryName(destinations)!, recursive: true);
        }
    }

    // C6 contracaso: without the private file, or without the channel in it, there is no test destination: the send
    // fails before any client is touched.
    [TestCase(null)]
    [TestCase("""{"discord":"Otro chat"}""")]
    [TestCase("not json")]
    public async Task WithoutAConfiguredTestDestinationNothingIsTouched(string? json)
    {
        var automation = new ClientAutomation(new(true, true, null));
        string destinations = TestDestinations(json);
        try
        {
            using var adapter = new DesktopMessagingAdapter(automation, destinations);
            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
                "message.send.test",
                Json("""{"channel":"whatsapp","requestedRecipient":"Tere","text":"hola"}"""),
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.False);
                Assert.That(receipt.ErrorCode, Is.EqualTo("test_destination_not_configured"));
                Assert.That(receipt.EffectObserved, Is.False);
                Assert.That(automation.Steps, Is.Empty);
            });
        }
        finally
        {
            Directory.Delete(Path.GetDirectoryName(destinations)!, recursive: true);
        }
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

    // Encargo CS (banco fz1 s14): Discord cold after a restart goes through its updater and took more than the 15 s of
    // D59 §1; its cold-start clock is data per application (client_cold_start.v1.json), any other keeps the default, and
    // a client still starting when it runs out is said as such (nothing written nor sent).
    [Test]
    public void EachClientWaitsItsOwnColdStartAndSaysItIsStillStarting()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ClientColdStart.For(WindowsDesktopMessagingAutomation.ClientApplicationName("discord")),
                Is.EqualTo(TimeSpan.FromSeconds(60)));
            Assert.That(ClientColdStart.For(WindowsDesktopMessagingAutomation.ClientApplicationName("whatsapp")),
                Is.EqualTo(TimeSpan.FromSeconds(15)), "not listed: the default of D59 §1");
            Assert.That(ClientColdStart.For("discord"), Is.EqualTo(TimeSpan.FromSeconds(60)), "matched without case");
            Assert.That(WindowsDesktopMessagingAutomation.ClientStillStarting("discord"), Is.EqualTo("discord_client_still_starting"));
            Assert.That(WindowsDesktopMessagingAutomation.ClientReadyUnread("discord"), Is.EqualTo("discord_client_ready_not_verified"));
        });
    }

    [TestCase("whatsapp", "WhatsApp")]
    [TestCase("discord", "Discord")]
    public void TheClientIsOpenedByItsInstalledName(string channel, string name)
    {
        Assert.That(WindowsDesktopMessagingAutomation.ClientApplicationName(channel), Is.EqualTo(name));
    }
}
