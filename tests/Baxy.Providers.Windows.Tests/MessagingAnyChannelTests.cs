using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// REOPEN1993 grupo E (D24): with channel «any» the recipient is looked up in
/// the clients — the remembered one first, then WhatsApp and Discord; a single
/// hit resolves and is remembered; none or both is said before any send.
/// </summary>
[TestFixture]
public sealed class MessagingAnyChannelTests
{
    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    private sealed class ChannelAutomation(IReadOnlySet<string> present) : IDesktopMessagingAutomation
    {
        internal List<string> Asked { get; } = [];

        public ValueTask<DesktopRecipientObservation> ResolveAsync(string channel, string recipient, CancellationToken cancellationToken)
        {
            Asked.Add(channel);
            return ValueTask.FromResult(present.Contains(channel)
                ? new DesktopRecipientObservation(true, true, (nint)42, 7, null)
                : new DesktopRecipientObservation(false, true, 0, 0, "recipient_not_found"));
        }

        public ValueTask<DesktopMessageObservation> SendAsync(ResolvedRecipient recipient, string text, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new DesktopMessageObservation(true, true, "hash", null));

        public ValueTask<DesktopMessageObservation> DraftAsync(ResolvedRecipient recipient, string text, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new DesktopMessageObservation(true, true, "hash", null));
    }

    private static string TemporaryStore() =>
        Path.Combine(Path.GetTempPath(), "baxy-msg-any-" + Guid.NewGuid().ToString("N"), "recipient-channels.v1.json");

    [Test]
    public async Task AUniqueHitResolvesRemembersAndIsReadFirstNextTime()
    {
        string store = TemporaryStore();
        try
        {
            var automation = new ChannelAutomation(new HashSet<string> { "whatsapp" });
            using var adapter = new DesktopMessagingAdapter(automation, store);

            ExternalCapabilityReceipt first = await adapter.InvokeAsync(
                "message.recipient.resolve", Json("""{"channel":"any","recipient":"Música"}"""), CancellationToken.None);
            ExternalCapabilityReceipt second = await adapter.InvokeAsync(
                "message.recipient.resolve", Json("""{"channel":"any","recipient":"musica"}"""), CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(first.Verified, Is.True, first.ErrorCode);
                Assert.That(first.Result?.GetProperty("channel").GetString(), Is.EqualTo("whatsapp"));
                Assert.That(first.Result?.GetProperty("displayName").GetString(), Is.EqualTo("Música"));
                Assert.That(File.ReadAllText(store), Does.Contain("whatsapp"));
                Assert.That(second.Verified, Is.True, second.ErrorCode);
                // first resolve asked both clients; the second went straight to the remembered one
                Assert.That(automation.Asked, Is.EqualTo(new[] { "whatsapp", "discord", "whatsapp" }));
            });
        }
        finally
        {
            try { Directory.Delete(Path.GetDirectoryName(store)!, recursive: true); } catch (IOException) { }
        }
    }

    [Test]
    public async Task NoneOrBothClientsFailBeforeAnySend()
    {
        string store = TemporaryStore();
        try
        {
            using var none = new DesktopMessagingAdapter(new ChannelAutomation(new HashSet<string>()), store);
            using var both = new DesktopMessagingAdapter(new ChannelAutomation(new HashSet<string> { "whatsapp", "discord" }), store);

            ExternalCapabilityReceipt missing = await none.InvokeAsync(
                "message.recipient.resolve", Json("""{"channel":"any","recipient":"Lucas"}"""), CancellationToken.None);
            ExternalCapabilityReceipt ambiguous = await both.InvokeAsync(
                "message.recipient.resolve", Json("""{"channel":"any","recipient":"Lucas"}"""), CancellationToken.None);
            ExternalCapabilityReceipt named = await both.InvokeAsync(
                "message.recipient.resolve", Json("""{"channel":"discord","recipient":"Lucas"}"""), CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(missing.Verified, Is.False);
                Assert.That(missing.ErrorCode, Is.EqualTo("recipient_not_found_in_clients"));
                Assert.That(ambiguous.Verified, Is.False);
                Assert.That(ambiguous.ErrorCode, Is.EqualTo("recipient_channel_ambiguous"));
                Assert.That(File.Exists(store), Is.False);
                Assert.That(named.Verified, Is.True);
                Assert.That(named.Result?.GetProperty("channel").GetString(), Is.EqualTo("discord"));
            });
        }
        finally
        {
            try { Directory.Delete(Path.GetDirectoryName(store)!, recursive: true); } catch (IOException) { }
        }
    }
}
