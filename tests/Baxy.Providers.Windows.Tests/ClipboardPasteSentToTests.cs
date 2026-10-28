using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew cu (C18): a clipboard.paste with no app opened first went into the window in front (a mail draft) and the
/// reply named the app asked for. Its receipt now says which window took it (sentTo: title and program), read from the
/// script's own measure of the front before the keys. No window is touched.
/// </summary>
[TestFixture]
public sealed class ClipboardPasteSentToTests
{
    [Test]
    public void ThePasteSaysTheWindowInFrontThatTookIt()
    {
        int self = Environment.ProcessId;
        using JsonDocument script = JsonDocument.Parse(
            $$"""{"ok":true,"effectObserved":true,"action":"paste","foregroundTitleBefore":"Borrador - Correo","foregroundProcessIdBefore":{{self}}}""");

        (string Title, string Process)? sentTo = WindowsDesktopInteractionAdapter.PastedInto(script.RootElement);

        Assert.That(sentTo, Is.EqualTo(("Borrador - Correo", System.Diagnostics.Process.GetCurrentProcess().ProcessName)));
    }

    // The model still named the app asked for with sentTo there (PC, C18): with the aid paste_target_next the same fact
    // goes as a sentence; with the aids off only sentTo.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public void ThePasteSaysAsASentenceTheOneWindowThatReceivedIt(string aids, bool said)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        using JsonDocument script = JsonDocument.Parse("""{"ok":true,"effectObserved":true,"action":"paste"}""");

        JsonElement receipt = WindowsDesktopInteractionAdapter.AsDelivered(script.RootElement, ("Steam", "steamwebhelper"));

        Assert.Multiple(() =>
        {
            Assert.That(receipt.GetProperty("sentTo").GetProperty("process").GetString(), Is.EqualTo("steamwebhelper"));
            Assert.That(receipt.GetProperty("delivered").GetBoolean(), Is.True);
            Assert.That(receipt.TryGetProperty("next", out JsonElement next), Is.EqualTo(said));
            if (said)
                Assert.That(next.GetString(), Is.EqualTo("it went into the window of Steam (steamwebhelper); no other application received it"));
        });
    }

    // Contracase: with no front measured (no window, or a process gone) nothing is said.
    [TestCase("""{"ok":true,"foregroundTitleBefore":"x","foregroundProcessIdBefore":0}""")]
    [TestCase("""{"ok":true}""")]
    public void WithNoFrontMeasuredNothingIsSaid(string json)
    {
        using JsonDocument script = JsonDocument.Parse(json);

        Assert.That(WindowsDesktopInteractionAdapter.PastedInto(script.RootElement), Is.Null);
    }

    // R6-NB-3 (CU 36 C18): the paste was said delivered and nothing read whether the copied text landed. It is read back
    // where it went as a typed text is: the focused edit control of the window in front, marked before the keys.
    private const string Copied = "Texto de prueba copiado";
    private static readonly nint Edit = 4661;

    [Test]
    public async Task APasteIsReadBackInTheFocusedEditControlAsATypedTextIs()
    {
        FakeFieldMessages notepad = new FakeFieldMessages().WithField(Edit, "RichEditD2DPT", "lista: ");
        using var scripts = new KeyScript();

        ExternalCapabilityReceipt receipt = await scripts.Adapter(
                () => notepad.Content[Edit] += Copied, notepad, clipboard: Copied)
            .InvokeAsync("clipboard.paste", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("readBack").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("delivered").GetBoolean(), Is.True);
            Assert.That(Baxy.Kernel.Operations.OperationVisibleFacts.Verification("clipboard.paste", receipt.Result),
                Is.EqualTo(Baxy.Kernel.Operations.OperationVisibleFacts.VerificationReadback));
        });
    }

    // Contracase: the keys went in and the control does not hold the copied text: not verified, its effect possible, the
    // read said (readBack false), never «delivered» as if nobody had looked.
    [Test]
    public async Task APasteTheEditControlDoesNotHoldIsNotVerified()
    {
        FakeFieldMessages notepad = new FakeFieldMessages().WithField(Edit, "RichEditD2DPT", "lista: ");
        using var scripts = new KeyScript();

        ExternalCapabilityReceipt receipt = await scripts.Adapter(static () => { }, notepad, clipboard: Copied)
            .InvokeAsync("clipboard.paste", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("paste_not_read_back"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.Result?.GetProperty("readBack").GetBoolean(), Is.False);
            Assert.That(receipt.Result?.GetProperty("ok").GetBoolean(), Is.False);
        });
    }

    // A document that is no edit control: the paragraph at its caret, read by UI Automation before and after the keys.
    [Test]
    public async Task APasteIntoADocumentIsReadBackInTheParagraphAtItsCaret()
    {
        string paragraph = "Querida Ana, ";
        var fields = new FakeViewedFields("{}")
        {
            CaretAnswer = () =>
                $$"""{"ok":true,"processId":{{Environment.ProcessId}},"text":"{{paragraph}}","unit":"paragraph","bounded":false,"selectionLength":0}""",
        };
        using var scripts = new KeyScript();

        ExternalCapabilityReceipt receipt = await scripts.Adapter(
                () => paragraph += Copied, new FakeFieldMessages(), clipboard: Copied, fields: fields)
            .InvokeAsync("clipboard.paste", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("readBack").GetBoolean(), Is.True);
            Assert.That(fields.CaretRequests, Has.Count.GreaterThanOrEqualTo(2));
        });
    }

    // Where nothing can read it (a text of several lines, which an edit control counts its own way; no clipboard text;
    // no edit control and no caret answer), the receipt says so as a typed fact, the paste stays delivered only.
    [TestCase("primera línea\r\nsegunda línea", true)]
    [TestCase(null, true)]
    [TestCase(Copied, false)]
    public async Task APasteNothingCanReadBackSaysNotReadable(string? clipboard, bool withEditControl)
    {
        FakeFieldMessages messages = withEditControl
            ? new FakeFieldMessages().WithField(Edit, "RichEditD2DPT", string.Empty)
            : new FakeFieldMessages();
        using var scripts = new KeyScript();

        ExternalCapabilityReceipt receipt = await scripts.Adapter(static () => { }, messages, clipboard)
            .InvokeAsync("clipboard.paste", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("readBack").GetString(),
                Is.EqualTo("not_readable"));
            Assert.That(Baxy.Kernel.Operations.OperationVisibleFacts.Verification("clipboard.paste", receipt.Result),
                Is.EqualTo(Baxy.Kernel.Operations.OperationVisibleFacts.VerificationDeliveredOnly));
        });
    }

    // Review of R6-NB-3: a read that proves nothing is never «not there». The caret's re-read that does not answer, an
    // edit control whose text no longer answers, and a mark of another window than the one the script pasted into
    // (the person changed the front in between) all say not_readable, never paste_not_read_back.
    [TestCase("caret")]
    [TestCase("edit")]
    [TestCase("front")]
    public async Task AReadThatProvesNothingIsNotReadableNeverNotThere(string unread)
    {
        bool pasted = false;
        var fields = new FakeViewedFields("{}")
        {
            CaretAnswer = () => pasted
                ? """{"ok":false}"""
                : $$"""{"ok":true,"processId":{{Environment.ProcessId}},"text":"Hola","unit":"paragraph","bounded":false,"selectionLength":0}""",
        };
        FakeFieldMessages messages = unread == "caret"
            ? new FakeFieldMessages()
            : new FakeFieldMessages().WithField(Edit, "RichEditD2DPT", "lista: ");
        using var scripts = new KeyScript();
        Action paste = unread == "edit" ? () => messages.Content.Remove(Edit) : () => pasted = true;

        ExternalCapabilityReceipt receipt = await scripts.Adapter(
                paste, messages, Copied, unread == "caret" ? fields : null,
                scriptFront: unread == "front" ? Environment.ProcessId + 1 : null)
            .InvokeAsync("clipboard.paste", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("readBack").GetString(), Is.EqualTo("not_readable"));
        });
    }

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    // The key script on disk (the adapter checks it exists) and its answer, with the paste's effect on the fakes.
    private sealed class KeyScript : IDisposable
    {
        private readonly string _directory = Directory.CreateTempSubdirectory("baxy-paste-").FullName;

        internal WindowsDesktopInteractionAdapter Adapter(
            Action paste, FakeFieldMessages messages, string? clipboard, FakeViewedFields? fields = null,
            int? scriptFront = null)
        {
            string script = Path.Combine(_directory, "DesktopKeyPress.ps1");
            File.WriteAllText(script, "# test fixture");
            return new WindowsDesktopInteractionAdapter(
                new PastingRunner(paste, scriptFront ?? Environment.ProcessId), script, script, script, script,
                new FakeDesktopKeyboard { Front = new DesktopForeground(4660, Environment.ProcessId, "Sin título: Bloc de notas") },
                fields, messages, () => clipboard);
        }

        public void Dispose() => Directory.Delete(_directory, recursive: true);
    }

    // The script's answer names the process it found in front before its keys (scriptFront).
    private sealed class PastingRunner(Action paste, int scriptFront) : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken)
        {
            Assert.That(arguments, Does.Contain("-PasteClipboard"));
            paste();
            return ValueTask.FromResult(new ExternalProcessResult(0,
                $$"""{"version":1,"ok":true,"effectObserved":true,"action":"paste","foregroundTitleBefore":"Sin título: Bloc de notas","foregroundProcessIdBefore":{{scriptFront}},"error":null}""",
                string.Empty));
        }
    }
}
