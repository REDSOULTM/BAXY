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
            new DesktopRecipientObservation(true, true, (nint)42, 7, null),
            new DesktopMessageObservation(true, true, "evidence_hash", null));
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
            Assert.That(sent.Verified, Is.True);
            Assert.That(sent.EffectObserved, Is.True);
            Assert.That(sent.Result?.GetProperty("delivery").GetString(),
                Is.EqualTo("visible_postcondition"));
            Assert.That(automation.SentRecipient?.DisplayName, Is.EqualTo("CbaYeah"));
            Assert.That(automation.SentText, Is.EqualTo("Hola"));
        });
    }

    [Test]
    public async Task ExpiredIdentityFailsBeforeAnyPhysicalSend()
    {
        var automation = new StubAutomation(
            new DesktopRecipientObservation(true, true, (nint)42, 7, null),
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
            new DesktopRecipientObservation(true, true, (nint)42, 7, null),
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
