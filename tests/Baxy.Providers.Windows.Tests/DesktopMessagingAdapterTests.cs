using System.Diagnostics;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class DesktopMessagingAdapterTests
{
    [TestCase("Hola", "Hola", true)]
    [TestCase("Tú: Hola", "Hola", true)]
    [TestCase("ecHola", "Hola", false)]
    [TestCase("HolaMundo", "Hola", false)]
    [TestCase("Hóla", "hola", true)]
    public void VisibleEvidenceRequiresACompleteFoldedPhrase(
        string source,
        string expected,
        bool result) =>
        Assert.That(
            WindowsDesktopMessagingAutomation.ContainsPhrase(source, expected),
            Is.EqualTo(result));

    // C1: a shown name (title, search row, header line) names the recipient only with its whole words, folded.
    [TestCase("Ron92", "ron", false)]
    [TestCase("Juana", "ana", false)]
    [TestCase("Discord | @Ron92", "ron92", true)]
    [TestCase("Ron92 .wolfsoultm.4191", "Ron92", true)]
    [TestCase("Ana María", "ana maria", true)]
    [TestCase("María Ana", "ana maria", false)]
    [TestCase("Mario", "Maria", false)]
    [TestCase("Ron92", "!!!", false)]
    public void ARecipientIsNamedOnlyByItsWholeWords(string shown, string recipient, bool named) =>
        Assert.That(WindowsDesktopMessagingAutomation.NamesRecipient(shown, recipient), Is.EqualTo(named));

    // C2: the header line that names the recipient is what is said, with no letter of tolerance.
    [Test]
    public void TheHeaderLineThatNamesTheRecipientIsTheOneSaid()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsDesktopMessagingAutomation.HeaderLine("Misica\nMúsica  \nMusica", "Música"), Is.EqualTo("Música"));
            Assert.That(WindowsDesktopMessagingAutomation.HeaderLine("Misica\nMarios", "Música"), Is.Null);
            Assert.That(WindowsDesktopMessagingAutomation.HeaderLine("Mario\nMario", "Maria"), Is.Null);
        });
    }

    // C3: a search whose rows never named the recipient is «recipient_not_found» with the row it showed; text that may
    // have reached a composer keeps its possible effect and code.
    [Test]
    public void ASearchThatNamedNobodySaysTheRowItShowed()
    {
        DesktopRecipientObservation untouched = WindowsDesktopMessagingAutomation.NotNamedInSearch(
            WindowsDesktopMessagingAutomation.UnverifiedChat(42, 7, composerUntouched: true), "Ronaldo");
        DesktopRecipientObservation touched = WindowsDesktopMessagingAutomation.NotNamedInSearch(
            WindowsDesktopMessagingAutomation.UnverifiedChat(42, 7, composerUntouched: false), null);
        Assert.Multiple(() =>
        {
            Assert.That(untouched.ErrorCode, Is.EqualTo(WindowsDesktopMessagingAutomation.RecipientNotFound));
            Assert.That(untouched.EffectObserved, Is.False);
            Assert.That(untouched.Shown, Is.EqualTo("Ronaldo"));
            Assert.That(touched.ErrorCode, Is.EqualTo("recipient_identity_not_verified"));
            Assert.That(touched.EffectObserved, Is.True);
            Assert.That(touched.Shown, Is.Null);
        });
    }

    [Test]
    public async Task AFailedLookupCarriesTheRowItSaw()
    {
        var automation = new StubAutomation(
            new DesktopRecipientObservation(false, false, (nint)42, 7, "recipient_not_found", "Ronaldo"),
            new DesktopMessageObservation(true, true, "hash", null));
        using var adapter = new DesktopMessagingAdapter(automation);

        ExternalCapabilityReceipt resolved = await adapter.InvokeAsync(
            "message.recipient.resolve",
            Json("""{"channel":"discord","recipient":"Ron"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(resolved.Verified, Is.False);
            Assert.That(resolved.ErrorCode, Is.EqualTo("recipient_not_found"));
            Assert.That(resolved.Result?.GetProperty("observed").GetString(), Is.EqualTo("Ronaldo"));
        });
    }

    // C4: a delivery read says whether it matched exactly or only with the OCR tolerance.
    [TestCase("Tú: hola test 15:32", "hola test", "exact")]
    [TestCase("Holatest 15:32", "hola test", "tolerant")]
    [TestCase("probanda", "probando", "tolerant")]
    [TestCase("otra cosa", "probando", null)]
    public void ADeliveryReadSaysHowItMatched(string observed, string expected, string? match) =>
        Assert.That(WindowsDesktopMessagingAutomation.TextMatch(observed, expected), Is.EqualTo(match));

    // G1 (2026-10-11): the typed draft is read only once the composer band's
    // content changed; a blinking caret (one or two columns) is not a change, so
    // it never starts an OCR pass that holds the CPU the client needs to draw.
    [Test]
    public void CaretBlinkIsNotAContentChange()
    {
        byte[] before = Band(static (_, _) => false);
        byte[] caret = Band(static (x, y) => x is 40 or 41 && y is > 5 and < 25);

        Assert.Multiple(() =>
        {
            Assert.That(WindowsDesktopMessagingAutomation.ContentChanged(before, caret), Is.False);
            Assert.That(WindowsDesktopMessagingAutomation.ContentChanged(before, before), Is.False);
        });
    }

    [Test]
    public void TypedGlyphsAreAContentChange()
    {
        byte[] before = Band(static (x, y) => x is 40 && y is > 5 and < 25);
        byte[] typed = Band(static (x, y) => x is >= 40 and < 52 && y is > 8 and < 20);
        byte[] resized = WindowsDesktopMessagingAutomation.EncodeBmp(100, 31, new byte[100 * 31 * 4]);

        Assert.Multiple(() =>
        {
            Assert.That(WindowsDesktopMessagingAutomation.ContentChanged(before, typed), Is.True);
            Assert.That(WindowsDesktopMessagingAutomation.ContentChanged(before, resized), Is.True);
        });
    }

    private static byte[] Band(Func<int, int, bool> lit)
    {
        const int width = 100;
        const int height = 30;
        byte[] pixels = new byte[width * height * 4];
        for (int y = 0; y < height; y++)
        {
            for (int x = 0; x < width; x++)
            {
                if (lit(x, y))
                {
                    pixels.AsSpan((y * width + x) * 4, 3).Fill(220);
                }
            }
        }

        return WindowsDesktopMessagingAutomation.EncodeBmp(width, height, pixels);
    }

    [Test]
    public async Task RedirectedOcrProcessDrainsStandardErrorConcurrently()
    {
        var start = new ProcessStartInfo("cmd.exe")
        {
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
        start.ArgumentList.Add("/d");
        start.ArgumentList.Add("/s");
        start.ArgumentList.Add("/c");
        start.ArgumentList.Add(
            "(for /L %i in (1,1,8192) do @echo 012345678901234567890123456789 1>&2)"
            + " & @echo expected");
        using Process process = Process.Start(start)
            ?? throw new IOException("Test process did not start.");
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(10));

        string output =
            await WindowsDesktopMessagingAutomation.ReadRedirectedOutputAsync(
                process,
                timeout.Token);

        Assert.That(output.Trim(), Is.EqualTo("expected"));
    }

    [Test]
    public async Task ResolveThenSendUsesObservedOpaqueIdentityAndVerifiedReceipt()
    {
        var automation = new StubAutomation(
            new DesktopRecipientObservation(true, true, (nint)42, 7, null, "Discord | @CbaYeah"),
            new DesktopMessageObservation(true, true, "evidence_hash", null, "Holatest 15:32", "tolerant"));
        using var adapter = new DesktopMessagingAdapter(automation);

        ExternalCapabilityReceipt resolved = await adapter.InvokeAsync(
            "message.recipient.resolve",
            Json("""{"channel":"discord","recipient":"CbaYeah"}"""),
            CancellationToken.None);
        string recipientId = resolved.Result!.Value.GetProperty("recipientId").GetString()!;
        ExternalCapabilityReceipt sent = await adapter.InvokeAsync(
            "message.send",
            Json($$"""{"recipientId":"{{recipientId}}","text":"Hola"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(resolved.Verified, Is.True);
            Assert.That(recipientId, Does.StartWith("recipient_"));
            // C2: what the client showed is said, next to what was asked for.
            Assert.That(resolved.Result?.GetProperty("displayName").GetString(), Is.EqualTo("Discord | @CbaYeah"));
            Assert.That(resolved.Result?.GetProperty("recipient").GetString(), Is.EqualTo("CbaYeah"));
            Assert.That(sent.Result?.GetProperty("displayName").GetString(), Is.EqualTo("Discord | @CbaYeah"));
            Assert.That(sent.Verified, Is.True);
            Assert.That(sent.EffectObserved, Is.True);
            Assert.That(sent.Result?.GetProperty("delivery").GetString(),
                Is.EqualTo("visible_postcondition"));
            // C4: the text read and how it matched travel with the receipt.
            Assert.That(sent.Result?.GetProperty("deliveryRead").GetString(), Is.EqualTo("Holatest 15:32"));
            Assert.That(sent.Result?.GetProperty("deliveryMatch").GetString(), Is.EqualTo("tolerant"));
            Assert.That(automation.SentRecipient?.Name, Is.EqualTo("CbaYeah"));
            Assert.That(automation.SentText, Is.EqualTo("Hola"));
        });
    }

    [Test]
    public async Task ExpiredIdentityFailsBeforeAnyPhysicalSend()
    {
        var automation = new StubAutomation(
            new DesktopRecipientObservation(true, true, (nint)42, 7, null, "Letras"),
            new DesktopMessageObservation(true, true, "hash", null));
        using var adapter = new DesktopMessagingAdapter(automation);

        ExternalCapabilityReceipt sent = await adapter.InvokeAsync(
            "message.send",
            Json("""{"recipientId":"recipient_unknown","text":"Hola"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(sent.Verified, Is.False);
            Assert.That(sent.EffectObserved, Is.False);
            Assert.That(sent.ErrorCode, Is.EqualTo("recipient_identity_expired"));
            Assert.That(automation.SentRecipient, Is.Null);
        });
    }

    [Test]
    public async Task AmbiguousPostSendEvidencePreservesPossibleEffect()
    {
        var automation = new StubAutomation(
            new DesktopRecipientObservation(true, true, (nint)42, 7, null, "Letras"),
            new DesktopMessageObservation(
                false,
                true,
                "ambiguous_hash",
                "message_delivery_not_verified"));
        using var adapter = new DesktopMessagingAdapter(automation);
        ExternalCapabilityReceipt resolved = await adapter.InvokeAsync(
            "message.recipient.resolve",
            Json("""{"channel":"whatsapp","recipient":"Letras"}"""),
            CancellationToken.None);
        string recipientId = resolved.Result!.Value.GetProperty("recipientId").GetString()!;

        ExternalCapabilityReceipt sent = await adapter.InvokeAsync(
            "message.send",
            Json($$"""{"recipientId":"{{recipientId}}","text":"Hola"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(sent.Verified, Is.False);
            Assert.That(sent.EffectObserved, Is.True);
            Assert.That(sent.ErrorCode, Is.EqualTo("message_delivery_not_verified"));
        });
    }

    private static JsonElement Json(string value) =>
        JsonDocument.Parse(value).RootElement.Clone();

    private sealed class StubAutomation(
        DesktopRecipientObservation resolve,
        DesktopMessageObservation send) : IDesktopMessagingAutomation
    {
        internal ResolvedRecipient? SentRecipient { get; private set; }
        internal string? SentText { get; private set; }

        public ValueTask<DesktopRecipientObservation> ResolveAsync(
            string channel,
            string recipient,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(resolve);
        }

        public ValueTask<DesktopMessageObservation> SendAsync(
            ResolvedRecipient recipient,
            string text,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            SentRecipient = recipient;
            SentText = text;
            return ValueTask.FromResult(send);
        }
    }
}
