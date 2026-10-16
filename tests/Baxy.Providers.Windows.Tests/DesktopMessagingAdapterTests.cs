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

    // Auditoría final: a shown name (a header line, a chat-list row) names the recipient only when it is the recipient,
    // folded; more words around it make another name.
    [TestCase("Ron92", "ron", false)]
    [TestCase("Juana", "ana", false)]
    [TestCase("@Ron92", "ron92", true)]
    [TestCase("Ron92 Fan", "Ron92", false)]
    [TestCase("Ana María", "ana maria", true)]
    [TestCase("María Ana", "ana maria", false)]
    [TestCase("Mario", "Maria", false)]
    [TestCase("Ron92", "!!!", false)]
    public void ARecipientIsNamedOnlyByItsWholeName(string shown, string recipient, bool named) =>
        Assert.That(WindowsDesktopMessagingAutomation.NamesRecipient(shown, recipient), Is.EqualTo(named));

    // Discord's title: with the client's own part taken away, the one part left is the recipient.
    [TestCase("Discord | @Ron92", "ron92", true)]
    [TestCase("Ron92 - Discord", "Ron92", true)]
    [TestCase("Discord | @Ron92 Fan", "Ron92", false)]
    [TestCase("#general | BAXY - Discord", "BAXY", false)]
    [TestCase("Discord", "Discord", false)]
    public void ADiscordTitleNamesTheRecipientOnlyAsItsConversation(string title, string recipient, bool named) =>
        Assert.That(WindowsDesktopMessagingAutomation.TitleNamesRecipient(title, recipient), Is.EqualTo(named));

    // A quick-switcher row writes the account after the name; it is opened on the name's whole words (C1).
    [TestCase("Ron92 .wolfsoultm.4191", "Ron92", true)]
    [TestCase("Ronaldo", "Ron", false)]
    public void ASwitcherRowHoldsTheRecipientsWholeWords(string row, string recipient, bool named) =>
        Assert.That(WindowsDesktopMessagingAutomation.RowNamesRecipient(row, recipient), Is.EqualTo(named));

    // Auditoría final: the WhatsApp chat list is read before anything is opened; only a row that is the recipient,
    // apart from the time at its right end, is a hit. A preview that begins with the name is not.
    [Test]
    public void TheChatListRowThatIsTheRecipientIsTheOnlyHit()
    {
        static WindowsVisibleOcrLocator.LayoutLine Line(params (string Text, double X)[] words) => new(
            string.Join(' ', words.Select(word => word.Text)), words[0].X, 200, 300, 16,
            [.. words.Select(word => new WindowsVisibleOcrLocator.LayoutWord(word.Text, word.X, 200, word.Text.Length * 8, 16))]);
        WindowsVisibleOcrLocator.LayoutLine[] rows =
        [
            Line(("Juan", 140), ("Pérez", 180), ("12:30", 340)),
            Line(("Juan", 140), ("Pérez:", 180), ("hola", 232)),
            Line(("Juan", 140), ("Pérez", 180), ("Soto", 224), ("ayer", 340)),
        ];
        IReadOnlyList<(double X, double Y)> hits = WindowsDesktopMessagingAutomation.RowsNamingRecipient(rows, "juan perez");
        Assert.Multiple(() =>
        {
            Assert.That(hits, Has.Count.EqualTo(1));
            Assert.That(hits[0].X, Is.EqualTo(180).Within(1));
            Assert.That(hits[0].Y, Is.EqualTo(208).Within(1));
        });
    }

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
            "message.draft",
            Json("""{"channel":"discord","recipient":"Ron","text":"hola"}"""),
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

    // C5: the send and the draft read the composer before typing and never clear it first; the read (a select-all
    // whose picture shows text) deletes nothing and stops on the person's draft.
    [TestCase("SendInBurstAsync(")]
    [TestCase("DraftInBurstAsync(")]
    public void TheComposerIsReadBeforeTypingAndNeverClearedFirst(string flow)
    {
        string source = AdapterSource();
        int start = source.IndexOf("private static async ValueTask<DesktopMessageObservation> " + flow, StringComparison.Ordinal);
        int typed = source.IndexOf("SendText(text);", Math.Max(start, 0), StringComparison.Ordinal);
        int read = source.IndexOf("private static async ValueTask<bool> ComposerHoldsTextAsync(", StringComparison.Ordinal);
        int readEnd = source.IndexOf("\n    }\n", Math.Max(read, 0), StringComparison.Ordinal);
        Assert.Multiple(() =>
        {
            Assert.That(start, Is.GreaterThan(0));
            Assert.That(read, Is.GreaterThan(0));
            Assert.That(source[start..typed], Does.Contain("ComposerHoldsTextAsync("));
            Assert.That(source[start..typed], Does.Contain("return new(false, false, string.Empty, ComposerHasPersonDraft);"));
            Assert.That(source[start..typed], Does.Not.Contain("VirtualKeyBack"));
            Assert.That(source[read..readEnd], Does.Not.Contain("VirtualKeyBack"));
        });
    }

    // C7: every flow that resizes the person's window to the normalized layout runs inside InNormalizedWindowAsync,
    // which gives the window its size back in a finally.
    [Test]
    public void EveryResizedFlowGivesThePersonsWindowItsSizeBack()
    {
        string source = AdapterSource();
        int wrapper = source.IndexOf("private static async ValueTask<T> InNormalizedWindowAsync<T>(", StringComparison.Ordinal);
        int wrapperEnd = source.IndexOf("\n    }\n", Math.Max(wrapper, 0), StringComparison.Ordinal);
        Assert.Multiple(() =>
        {
            Assert.That(wrapper, Is.GreaterThan(0));
            Assert.That(source[wrapper..wrapperEnd], Does.Contain("finally"));
            Assert.That(source[wrapper..wrapperEnd], Does.Contain("ResizeWindow(handle, size);"));
            Assert.That(source, Does.Contain("flow => ResolveInBurstAsync("));
            Assert.That(source, Does.Contain("flow => SendInBurstAsync("));
            Assert.That(source, Does.Contain("flow => DraftInBurstAsync("));
            Assert.That(source.Split("NormalizeWindow(channel, handle)").Length - 1, Is.EqualTo(1));
        });
    }

    private static string AdapterSource()
    {
        DirectoryInfo? root = new(AppContext.BaseDirectory);
        while (root is not null && !File.Exists(Path.Combine(root.FullName, "Baxy.slnx")))
        {
            root = root.Parent;
        }

        Assert.That(root, Is.Not.Null, "Baxy.slnx was not found.");
        return File.ReadAllText(Path.Combine(
            root!.FullName, "src", "Baxy.Providers.Windows", "External", "DesktopMessagingAdapter.cs"));
    }

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
    public async Task ATestSendCarriesWhatTheClientShowedAndHowTheDeliveryMatched()
    {
        var automation = new StubAutomation(
            new DesktopRecipientObservation(true, true, (nint)42, 7, null, "Discord | @CbaYeah"),
            new DesktopMessageObservation(true, true, "evidence_hash", null, "Holatest 15:32", "tolerant"));
        string destinations = TestDestinations("""{"discord":"CbaYeah"}""");
        try
        {
            using var adapter = new DesktopMessagingAdapter(automation, destinations);

            ExternalCapabilityReceipt sent = await adapter.InvokeAsync(
                "message.send.test",
                Json("""{"channel":"discord","requestedRecipient":"Lucas","text":"Hola"}"""),
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                // C2: what the client showed is said, next to what was asked for.
                Assert.That(sent.Result?.GetProperty("displayName").GetString(), Is.EqualTo("Discord | @CbaYeah"));
                Assert.That(sent.Result?.GetProperty("requestedRecipient").GetString(), Is.EqualTo("Lucas"));
                Assert.That(sent.Verified, Is.True);
                Assert.That(sent.EffectObserved, Is.True);
                // C4: the text read and how it matched travel with the receipt.
                Assert.That(sent.Result?.GetProperty("deliveryRead").GetString(), Is.EqualTo("Holatest 15:32"));
                Assert.That(sent.Result?.GetProperty("deliveryMatch").GetString(), Is.EqualTo("tolerant"));
                Assert.That(automation.SentRecipient?.Name, Is.EqualTo("CbaYeah"));
                Assert.That(automation.SentText, Is.EqualTo("Hola"));
            });
        }
        finally
        {
            Directory.Delete(Path.GetDirectoryName(destinations)!, recursive: true);
        }
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
        string destinations = TestDestinations("""{"whatsapp":"Letras"}""");
        try
        {
            using var adapter = new DesktopMessagingAdapter(automation, destinations);

            ExternalCapabilityReceipt sent = await adapter.InvokeAsync(
                "message.send.test",
                Json("""{"channel":"whatsapp","requestedRecipient":"Letras","text":"Hola"}"""),
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(sent.Verified, Is.False);
                Assert.That(sent.EffectObserved, Is.True);
                Assert.That(sent.ErrorCode, Is.EqualTo("message_delivery_not_verified"));
            });
        }
        finally
        {
            Directory.Delete(Path.GetDirectoryName(destinations)!, recursive: true);
        }
    }

    // Ronda B: a draft typed and not seen in the composer is cleared; the keys reached it, so the send and the draft
    // both say an effect may have occurred (never a clean failure, never an observed effect).
    [TestCase("message.send.test", """{"channel":"whatsapp","requestedRecipient":"Letras","text":"Hola"}""")]
    [TestCase("message.draft", """{"channel":"whatsapp","recipient":"Letras","text":"Hola"}""")]
    public async Task ADraftTypedAndNotSeenSaysAnEffectMayHaveOccurred(string operation, string arguments)
    {
        var automation = new StubAutomation(
            new DesktopRecipientObservation(true, true, (nint)42, 7, null, "Letras"),
            DesktopMessageObservation.DraftNotVerified());
        string destinations = TestDestinations("""{"whatsapp":"Letras"}""");
        try
        {
            using var adapter = new DesktopMessagingAdapter(automation, destinations);

            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(operation, Json(arguments), CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.False);
                Assert.That(receipt.EffectObserved, Is.False);
                Assert.That(receipt.EffectMayHaveOccurred, Is.True);
                Assert.That(receipt.ErrorCode, Is.EqualTo("message_draft_not_verified"));
            });
        }
        finally
        {
            Directory.Delete(Path.GetDirectoryName(destinations)!, recursive: true);
        }
    }

    [TestCase("SendInBurstAsync(")]
    [TestCase("DraftInBurstAsync(")]
    public void BothFlowsClearAnUnseenDraftWithThePossibleEffect(string flow)
    {
        string source = AdapterSource();
        int start = source.IndexOf("private static async ValueTask<DesktopMessageObservation> " + flow, StringComparison.Ordinal);
        int cleared = source.IndexOf("SendKey(VirtualKeyBack);", Math.Max(start, 0), StringComparison.Ordinal);
        int returned = source.IndexOf("return ", Math.Max(cleared, 0), StringComparison.Ordinal);
        Assert.Multiple(() =>
        {
            Assert.That(start, Is.GreaterThan(0));
            Assert.That(cleared, Is.GreaterThan(start));
            Assert.That(source[returned..], Does.StartWith("return DesktopMessageObservation.DraftNotVerified();"));
        });
    }

    // C6: the owner's test destinations, a private file the adapter is pointed at.
    private static string TestDestinations(string json)
    {
        string directory = Path.Combine(Path.GetTempPath(), "baxy-messaging-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        string path = Path.Combine(directory, "test-destinations.v1.json");
        File.WriteAllText(path, json);
        return path;
    }

    private static JsonElement Json(string value) =>
        JsonDocument.Parse(value).RootElement.Clone();

    private sealed class StubAutomation(
        DesktopRecipientObservation resolve,
        DesktopMessageObservation send) : IDesktopMessagingAutomation
    {
        internal ResolvedRecipient? SentRecipient { get; private set; }
        internal string? SentText { get; private set; }

        public ValueTask<DesktopClientReadiness> EnsureClientOpenAsync(
            string channel,
            CancellationToken cancellationToken) =>
            ValueTask.FromResult(DesktopClientReadiness.AlreadyOpen);

        public ValueTask<DesktopMessageObservation> DraftAsync(
            ResolvedRecipient recipient,
            string text,
            CancellationToken cancellationToken) =>
            ValueTask.FromResult(send);

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
