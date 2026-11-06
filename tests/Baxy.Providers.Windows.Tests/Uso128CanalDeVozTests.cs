using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

// Uso-128 (uso real 2026-11-05): a voice channel «not found», a call that could not be entered and a switcher left open. The
// row's kind comes inside its name's own part on the real client («General (canal de voz)»); pressing it joins its call, read
// by the voice panel; D15: the yes is asked, and the microphone and the call are left as they are.
[TestFixture]
public sealed class Uso128CanalDeVozTests
{
    [TestCase("General (canal de voz)", true)]
    [TestCase("Dofus (voice channel), Gremio", true)]
    [TestCase("Sala de Pedro, Canal de voz, Gremio", true)]
    [TestCase("Sala de Pedro — canal de voz, Gremio", true)]
    [TestCase("Ana (mensaje directo)", false)]
    [TestCase("Voz Antonio, usuario, voz.antonio", false)]
    [TestCase("Vozarrón (mensaje directo)", false)]
    [TestCase("general, Canal de texto, Gremio", false)]
    // Review R1: a kind is a whole mark in its place, never letters inside a name.
    [TestCase("Sala (voz alta), Canal de texto, Club", false)]
    [TestCase("Compras (invoices), Canal de texto, Club", false)]
    [TestCase("Sala (voz alta), Club", false)]
    [TestCase("Sala (canal de voz), Canal de texto, Club", false)]
    [TestCase("Sala (vieja) (canal de voz), Gremio", true)]
    [TestCase("Sala (vieja), Canal de voz, Gremio", true)]
    [TestCase("Sala — dos, Canal de voz, Gremio", true)]
    [TestCase("Sala — dos (Voice Channel)", true)]
    // A blind review of R1's fix: forms the client was not read writing fall on the side that asks the yes, never pressed without it.
    [TestCase("Sala, Canal de voz lleno, Gremio", true)]
    [TestCase("Sala (canal de voz lleno), Gremio", true)]
    [TestCase("Sala (canal de voz, lleno), Gremio", true)]
    [TestCase("Sala (canal de voz) 3, Gremio", true)]
    [TestCase("Sala (voz), Gremio", true)]
    [TestCase("Sala, Voz, Gremio", true)]
    [TestCase("Sala (canal de voz), Canal de texto Fans", true)]
    [TestCase("Música, juegos (canal de voz), Gremio", true)]
    [TestCase("Música, juegos, Canal de voz, Gremio", true)]
    [TestCase("Ana, usuario, voz", false)]
    [TestCase("Ana, usuario, voice.channel", false)] // An account, however it folds.
    [TestCase("Ana, usuario, mi_canal_de_voz", false)]
    [TestCase("Sala (canal de texto), Canal de voz, Gremio", true)]
    [TestCase("Ana (mensaje directo), Canal de voz, Gremio", true)]
    [TestCase("Sala (canal de voz) (lleno), Gremio", true)]
    [TestCase("Sala - canal de voz, Gremio", true)]
    [TestCase("Sala(canal de voz), Gremio", true)]
    [TestCase("General (canal de voz), Canal de texto", true)] // A server called so, with no kind of its own.
    public void TheRowsKindIsReadInAnyOfItsForms(string row, bool voice) =>
        Assert.That(WindowsDesktopMessagingAutomation.VoiceChannelRow(row), Is.EqualTo(voice));

    [TestCase("Sala Norte (canal de voz), Gremio", "Sala Norte", true)]
    [TestCase("Sala Norte (canal de voz), Gremio", "sala norte", true)]
    [TestCase("Sala Norte (canal de voz), Gremio", "Norte", false)] // Another channel's call is never joined by a word of its name.
    [TestCase("Ana Pérez, usuario, anap", "Ana", true)] // A person's row keeps its rule: the title decides after.
    // Review R1: the press would join this other call, with the panel refusing it only once inside.
    [TestCase("Sala (vieja) (canal de voz), Gremio", "Sala", false)]
    [TestCase("Sala (vieja), Canal de voz, Gremio", "Sala", false)]
    [TestCase("Sala — dos, Canal de voz, Gremio", "Sala", false)]
    [TestCase("Sala (vieja) (canal de voz), Gremio", "Sala vieja", true)]
    [TestCase("Sala — dos, Canal de voz, Gremio", "Sala dos", true)]
    [TestCase("Sala (canal de voz lleno), Gremio", "Sala", false)]
    [TestCase("Sala (voz), Gremio", "Sala", false)]
    [TestCase("Música, juegos (canal de voz), Gremio", "Música", false)]
    [TestCase("Música, juegos, Canal de voz, Gremio", "Música", false)]
    [TestCase("Música, juegos (canal de voz), Gremio", "Música juegos", true)]
    [TestCase("Sala (canal de voz) (lleno), Gremio", "Sala", false)]
    [TestCase("Sala - canal de voz, Gremio", "Sala", false)]
    [TestCase("Sala, Canal de voz lleno, Gremio", "Sala", false)]
    [TestCase("Ana, usuario, voice.channel", "Ana", true)] // A person's row keeps its rule.
    public void AVoiceRowMustBeTheNameAskedFor(string row, string name, bool named) =>
        Assert.That(new ChatTarget(name, Conversation: true).RowNames(row), Is.EqualTo(named));

    // Review R1: a row's own name loses its kind and what follows, never what the name itself holds.
    [TestCase("Ana (mensaje directo)", "Ana")]
    [TestCase("Ana (direct message)", "Ana")]
    [TestCase("Sala (canal de voz), Gremio", "Sala")]
    [TestCase("Sala de Pedro, Canal de voz, Gremio", "Sala de Pedro")]
    [TestCase("Sala de Pedro — canal de voz, Gremio", "Sala de Pedro")]
    [TestCase("Sala (vieja) (canal de voz), Gremio", "Sala (vieja)")]
    [TestCase("Sala (vieja), Canal de voz, Gremio", "Sala (vieja)")]
    [TestCase("Sala — dos, Canal de voz, Gremio", "Sala — dos")]
    [TestCase("Sala (voz alta), Club", "Sala (voz alta)")]
    public void ARowsOwnNameLosesOnlyItsKind(string row, string name) =>
        Assert.That(WindowsDesktopMessagingAutomation.RowOwnName(row), Is.EqualTo(name));

    // Review R1: what the panel names is read as the channel's server only when it is not the kind's own place.
    [TestCase("Sala (canal de voz), Voz alta", "Voz alta")]
    [TestCase("Sala, Canal de voz, Voz alta", "Voz alta")]
    [TestCase("Sala, Canal de voz", null)]
    [TestCase("Sala (canal de voz), Mi canal de voz", "Mi canal de voz")]
    [TestCase("Música, juegos (canal de voz), Gremio", "Gremio")]
    [TestCase("Sala (canal de voz), Canal de voz, Gremio", "Gremio")]
    public void AServerWithALetterOfTheKindIsStillTheServer(string row, string? server) =>
        Assert.That(WindowsDesktopMessagingAutomation.VoiceRowServer(row), Is.EqualTo(server));

    // A message's recipient is still never a voice channel.
    [Test]
    public void AMessageNeverGoesToAVoiceRow() =>
        Assert.That(new ChatTarget("Sala Norte").RowNames("Sala Norte (canal de voz), Gremio"), Is.False);

    [TestCase("Sala Norte / Gremio", "Sala Norte", null, true)]
    [TestCase("Sala Norte / Gremio", "Sala Norte", "Gremio", true)]
    [TestCase("Sala Norte / Gremio", "Sala Norte", "Otro", false)]
    [TestCase("Sala Sur / Gremio", "Sala Norte", null, false)]
    [TestCase(null, "Sala Norte", null, false)]
    public void ThePanelMustNameTheChannelAsked(string? place, string name, string? server, bool named) =>
        Assert.That(WindowsDesktopMessagingAutomation.PlaceNames(place, name, server), Is.EqualTo(named));

    [Test]
    public void ACloseNameIsOfferedAndAFarOneIsNot()
    {
        string[] rows = ["Ronaldo Pérez (mensaje directo)", "Club de lectura (mensaje directo)", "Sala Norte (canal de voz)"];
        Assert.Multiple(() =>
        {
            Assert.That(WindowsDesktopMessagingAutomation.AlikeNames("Ronaldino", rows), Is.EqualTo(new[] { "Ronaldo Pérez" }));
            Assert.That(WindowsDesktopMessagingAutomation.AlikeNames("Sala Nort", rows), Is.EqualTo(new[] { "Sala Norte" }));
            Assert.That(WindowsDesktopMessagingAutomation.AlikeNames("Xilófono", rows), Is.Empty);
            Assert.That(WindowsDesktopMessagingAutomation.AlikeNames("Yo", rows), Is.Empty);
        });
    }

    [Test]
    public void AVoicePanelIsParsed()
    {
        using JsonDocument connected = JsonDocument.Parse("""{"ok":true,"voiceConnected":true,"voicePlace":"Sala / Gremio"}""");
        using JsonDocument not = JsonDocument.Parse("""{"ok":true,"voiceConnected":false,"voicePlace":""}""");
        Assert.Multiple(() =>
        {
            Assert.That(UiaClientInteractionProbe.ParseVoicePanel(connected.RootElement), Is.EqualTo(new VoicePanel(true, "Sala / Gremio")));
            Assert.That(UiaClientInteractionProbe.ParseVoicePanel(not.RootElement).Connected, Is.False);
            Assert.That(UiaClientInteractionProbe.ParseVoicePanel(null).Connected, Is.False);
        });
    }

    [Test]
    public async Task EnteringIsSaidWithItsServerAndTheMicrophoneUntouched()
    {
        var automation = new Voice(new(true, true, (nint)42, 7, null, "Sala Norte / Gremio")
        {
            VoiceChannel = true,
            VoiceJoined = true,
            VoiceServer = "Gremio",
        });
        using var adapter = new DesktopMessagingAdapter(automation);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("client.channel.open", Open("Sala Norte"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("voiceChannel").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("joined").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("voiceServer").GetString(), Is.EqualTo("Gremio"));
            Assert.That(receipt.Result?.GetProperty("microphoneTouched").GetBoolean(), Is.False);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("discord_voice_panel_postread"));
        });
    }

    // Pressed, and the panel did not say it: neither «inside» nor «not found».
    [Test]
    public async Task APressThePanelDoesNotConfirmIsNotSaidIn()
    {
        var automation = new Voice(new(false, true, (nint)42, 7, WindowsDesktopMessagingAutomation.VoiceJoinNotVerified)
        {
            VoiceChannel = true,
            VoiceServer = "Gremio",
        });
        using var adapter = new DesktopMessagingAdapter(automation);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("client.channel.open", Open("Sala Norte"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("joined").GetString(), Is.EqualTo("unknown"));
            Assert.That(receipt.Result?.GetProperty("next").GetString(), Does.Contain("voice panel"));
        });
    }

    // D15: the yes is asked in normal mode, bound to this call, with what it is in its facts; a text channel asks nothing.
    [Test]
    public async Task AVoiceChannelAsksAndATextChannelDoesNot()
    {
        var automation = new Voice(new(true, true, (nint)42, 7, null, "x"))
        {
            Peeked = new(false, false, (nint)42, 7, null) { VoiceChannel = true, VoiceServer = "Gremio" },
        };
        using var adapter = new DesktopMessagingAdapter(automation);
        DesktopMessagingAdapter claiming = adapter;

        ExternalCapabilityReceipt? voice = await claiming.PreflightAsync("client.channel.open", Open("Sala Norte"), CancellationToken.None);
        automation.Peeked = new(false, false, (nint)42, 7, null);
        ExternalCapabilityReceipt? text = await claiming.PreflightAsync("client.channel.open", Open("general"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(claiming.PreflightMayRaise("client.channel.open", Open("Sala Norte")), Is.True);
            Assert.That(claiming.PreflightMayRaise("client.channel.open", Json("""{"client":"whatsapp","name":"Ana"}""")), Is.False);
            Assert.That(voice?.NeedsConfirmation, Is.True);
            Assert.That(voice?.Result?.GetProperty("voiceChannel").GetBoolean(), Is.True);
            Assert.That(voice?.Result?.GetProperty("server").GetString(), Is.EqualTo("Gremio"));
            Assert.That(text, Is.Null);
        });
    }

    // The run presses a voice row after the yes the read raised, or with no read at all (Bypass); after a read that saw no voice
    // channel under this name, the yes was never asked for one, and the row is not pressed.
    [Test]
    public async Task OnlyAYesAskedForItOrBypassMayPressAVoiceRow()
    {
        var automation = new Voice(new(true, true, (nint)42, 7, null, "x"));
        using var adapter = new DesktopMessagingAdapter(automation);
        DesktopMessagingAdapter claiming = adapter;

        _ = await adapter.InvokeAsync("client.channel.open", Open("Sala Norte"), CancellationToken.None);
        bool bypass = automation.VoiceAsked;

        automation.Peeked = new(false, false, (nint)42, 7, null) { VoiceChannel = true };
        _ = await claiming.PreflightAsync("client.channel.open", Open("Sala Norte"), CancellationToken.None);
        _ = await adapter.InvokeAsync("client.channel.open", Open("Sala Norte"), CancellationToken.None);
        bool afterYes = automation.VoiceAsked;

        automation.Peeked = new(false, false, (nint)42, 7, null);
        _ = await claiming.PreflightAsync("client.channel.open", Open("Sala Norte"), CancellationToken.None);
        _ = await adapter.InvokeAsync("client.channel.open", Open("Sala Norte"), CancellationToken.None);
        bool sawNone = automation.VoiceAsked;

        Assert.Multiple(() =>
        {
            Assert.That(bypass, Is.True);
            Assert.That(afterYes, Is.True);
            Assert.That(sawNone, Is.False);
        });
    }

    [Test]
    public async Task ANameNotFoundOffersWhatLooksLikeItAndOpensNothing()
    {
        var automation = new Voice(new(false, true, (nint)42, 7, WindowsDesktopMessagingAutomation.RecipientNotFound)
        {
            Alike = ["Ronaldo Pérez"],
        });
        using var adapter = new DesktopMessagingAdapter(automation);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("client.channel.open", Open("Ronaldino"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsDesktopMessagingAutomation.RecipientNotFound));
            Assert.That(receipt.Result?.GetProperty("opened").GetBoolean(), Is.False);
            Assert.That(receipt.Result?.GetProperty("alike")[0].GetString(), Is.EqualTo("Ronaldo Pérez"));
            Assert.That(receipt.Result?.GetProperty("next").GetString(), Does.StartWith("no result has the name"));
        });
    }

    private static JsonElement Open(string name) =>
        Json(JsonSerializer.Serialize(new { client = "discord", name }));

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private sealed class Voice(DesktopRecipientObservation open) : IDesktopMessagingAutomation
    {
        internal DesktopRecipientObservation? Peeked { get; set; }

        internal bool VoiceAsked { get; private set; }

        public ValueTask<DesktopClientReadiness> EnsureClientOpenAsync(string channel, CancellationToken cancellationToken) =>
            ValueTask.FromResult(DesktopClientReadiness.AlreadyOpen);

        public ValueTask<DesktopRecipientObservation> ResolveAsync(string channel, string recipient, CancellationToken cancellationToken) =>
            throw new AssertionException("a conversation is opened by its own lookup");

        public ValueTask<DesktopRecipientObservation> OpenConversationAsync(
            string channel, string name, string? server, CancellationToken cancellationToken) =>
            throw new AssertionException("the call says whether its yes covers a voice row");

        public ValueTask<DesktopRecipientObservation> OpenConversationAsync(
            string channel, string name, string? server, bool voiceAsked, CancellationToken cancellationToken)
        {
            VoiceAsked = voiceAsked;
            return ValueTask.FromResult(open);
        }

        public ValueTask<DesktopRecipientObservation?> PeekConversationAsync(
            string channel, string name, string? server, CancellationToken cancellationToken) =>
            ValueTask.FromResult(Peeked);

        public ValueTask<DesktopMessageObservation> SendAsync(ResolvedRecipient recipient, string text, CancellationToken cancellationToken) =>
            throw new AssertionException("nothing is sent");

        public ValueTask<DesktopMessageObservation> DraftAsync(ResolvedRecipient recipient, string text, CancellationToken cancellationToken) =>
            throw new AssertionException("nothing is written");
    }
}
