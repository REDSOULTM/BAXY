using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

// Uso real 2026-11-03 (G6): «abre el chat con X en Discord» found the chat with client.channel.locate (which opens nothing)
// and then a click on a visible row opened another person's chat of a similar name. client.channel.open opens it by the
// lookup message.draft makes and verifies it by the window title; nothing is typed. Names invented.
[TestFixture]
public sealed class G6AbrirConversacionPorNombreTests
{
    [TestCase("Discord | @Rocío Valdebenito", "rocio valdebenito", null, true)]
    [TestCase("Rocío Valdebenito - Discord", "Rocío Valdebenito", null, true)]
    [TestCase("Discord | @Rocío Valdés", "Rocío", null, false)]
    [TestCase("Discord | #anuncios | Gremio Lechuza", "anuncios", null, true)]
    [TestCase("#anuncios | Gremio Lechuza - Discord", "anuncios", "Gremio Lechuza", true)]
    [TestCase("Discord | #anuncios | Otro Gremio", "anuncios", "Gremio Lechuza", false)]
    [TestCase("Discord | #anuncios-viejos | Gremio Lechuza", "anuncios", "Gremio Lechuza", false)]
    [TestCase("Discord | @Rocío Valdebenito", "Rocío Valdebenito", "Gremio Lechuza", false)]
    [TestCase("Discord | #tareas-calculo | Ingeniería 2026", "tareas-calculo", "Ingenieria 2026", true)]
    public void AConversationIsOpenOnlyWhenTheTitleIsItsNameAndItsServer(
        string title, string name, string? server, bool expected) =>
        Assert.That(WindowsDesktopMessagingAutomation.TitleNamesConversation(title, name, server), Is.EqualTo(expected));

    [Test]
    public void AMessageRecipientKeepsItsOneNameTitleAndAServerRowMustNameTheServer()
    {
        var channel = new ChatTarget("anuncios", Conversation: true, "Gremio Lechuza");
        Assert.Multiple(() =>
        {
            // message.draft's rule is unchanged: a channel's title, with its server, is not a person's chat.
            Assert.That(new ChatTarget("anuncios").TitleNames("Discord | #anuncios | Gremio Lechuza"), Is.False);
            Assert.That(channel.RowNames("anuncios, Canal de texto, Gremio Lechuza"), Is.True);
            Assert.That(channel.RowNames("anuncios, Canal de texto, Otro Gremio"), Is.False);
            // Uso-128: a voice channel's row is a result of its own; pressing it is what asks (Uso128CanalDeVozTests), and a
            // message's recipient is still never one.
            Assert.That(channel.RowNames("anuncios, Canal de voz, Gremio Lechuza"), Is.True);
            Assert.That(new ChatTarget("anuncios").RowNames("anuncios, Canal de voz, Gremio Lechuza"), Is.False);
        });
    }

    [Test]
    public async Task TheConversationIsOpenedByTheLookupAndItsTitleComesBack()
    {
        var automation = new Opening(new DesktopRecipientObservation(
            true, true, (nint)42, 7, null, "Discord | #anuncios | Gremio Lechuza"));
        using var adapter = new DesktopMessagingAdapter(automation);
        Assert.That(adapter.CanHandle("client.channel.open"), Is.True);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "client.channel.open",
            Json("""{"client":"discord","name":"anuncios","server":"Gremio Lechuza"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(automation.Asked, Is.EqualTo(("discord", "anuncios", "Gremio Lechuza")));
            Assert.That(receipt.Result?.GetProperty("opened").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("openedTitle").GetString(), Is.EqualTo("Discord | #anuncios | Gremio Lechuza"));
            Assert.That(receipt.Result?.GetProperty("typed").GetBoolean(), Is.False);
        });
    }

    // Already on screen: nothing is pressed, and that is the state already reached, not an effect.
    [Test]
    public async Task AConversationAlreadyOpenIsItsStateAlreadyReached()
    {
        var automation = new Opening(new DesktopRecipientObservation(true, false, (nint)42, 7, null, "Discord | @Rocío Valdebenito"));
        using var adapter = new DesktopMessagingAdapter(automation);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "client.channel.open", Json("""{"client":"discord","name":"Rocío Valdebenito"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.StateAlreadyReached, Is.True);
            Assert.That(receipt.Result?.GetProperty("alreadyOpen").GetBoolean(), Is.True);
        });
    }

    // The click on a row of a similar name: the chat on screen is said by its title and the row clicked, never «opened».
    [Test]
    public async Task AChatThatIsNotTheOneAskedForComesBackByItsTitle()
    {
        var automation = new Opening(new DesktopRecipientObservation(
            false, true, (nint)42, 7, "recipient_identity_not_verified")
        {
            HeaderRead = ["Discord | @Rocío Valdés"],
            OpenedRow = "Rocío Valdés rociov",
        });
        using var adapter = new DesktopMessagingAdapter(automation);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "client.channel.open", Json("""{"client":"discord","name":"Rocío"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("recipient_identity_not_verified"));
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("opened").GetBoolean(), Is.False);
            Assert.That(receipt.Result?.GetProperty("headerRead")[0].GetString(), Is.EqualTo("Discord | @Rocío Valdés"));
            Assert.That(receipt.Result?.GetProperty("openedRow").GetString(), Is.EqualTo("Rocío Valdés rociov"));
        });
    }

    [Test]
    public async Task AServerIsOnlyADiscordChannels()
    {
        var automation = new Opening(new DesktopRecipientObservation(true, true, (nint)42, 7, null, "Feña"));
        using var adapter = new DesktopMessagingAdapter(automation);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "client.channel.open", Json("""{"client":"whatsapp","name":"Feña","server":"Gremio Lechuza"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("server_only_in_discord"));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(automation.Asked, Is.Null, "the client is not touched");
        });
    }

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private sealed class Opening(DesktopRecipientObservation open) : IDesktopMessagingAutomation
    {
        internal (string Channel, string Name, string? Server)? Asked { get; private set; }

        public ValueTask<DesktopClientReadiness> EnsureClientOpenAsync(string channel, CancellationToken cancellationToken) =>
            ValueTask.FromResult(DesktopClientReadiness.AlreadyOpen);

        public ValueTask<DesktopRecipientObservation> ResolveAsync(
            string channel, string recipient, CancellationToken cancellationToken) =>
            throw new AssertionException("a conversation is opened by its own lookup");

        public ValueTask<DesktopRecipientObservation> OpenConversationAsync(
            string channel, string name, string? server, CancellationToken cancellationToken)
        {
            Asked = (channel, name, server);
            return ValueTask.FromResult(open);
        }

        public ValueTask<DesktopMessageObservation> SendAsync(
            ResolvedRecipient recipient, string text, CancellationToken cancellationToken) =>
            throw new AssertionException("nothing is sent");

        public ValueTask<DesktopMessageObservation> DraftAsync(
            ResolvedRecipient recipient, string text, CancellationToken cancellationToken) =>
            throw new AssertionException("nothing is written");
    }
}
