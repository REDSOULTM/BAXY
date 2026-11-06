using Baxy.Providers.Windows.Clipboard;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class OfficeNewDocumentPasteTests
{
    // A8: the script's Get-Clipboard had no limit but the 30 s of the whole script, and every failure of it read as empty.
    [TestCase("clipboard_owner_not_responding", "clipboard_owner_not_responding")]
    [TestCase("clipboard_busy", "clipboard_busy")]
    [TestCase("clipboard_has_no_text", "clipboard_empty")]
    public async Task TheScriptIsToldTheStateOfABoundedRead(string read, string told)
    {
        var runner = new RecordingRunner("{\"ok\":false,\"running\":true,\"effectObserved\":false,\"error\":\"" + told + "\"}");

        OfficePasteResult? result = await OfficeNewDocumentPaste.TryAsync(
            "word", runner, new Clipboard(new ClipboardProviderException(read)), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(runner.Arguments![^1], Is.EqualTo(told));
            Assert.That(runner.Arguments[^2], Is.EqualTo("word"));
            Assert.That(runner.Arguments[3], Does.Not.Contain("Get-Clipboard"));
            Assert.That(result!.ErrorCode, Is.EqualTo(told));
            Assert.That(result.EffectObserved, Is.False);
        });
    }

    [Test]
    public async Task TextGoesOnToThePaste()
    {
        var runner = new RecordingRunner("{\"ok\":true,\"running\":true,\"effectObserved\":true,\"document\":\"Documento1\",\"characters\":4}");

        OfficePasteResult? result = await OfficeNewDocumentPaste.TryAsync(
            "excel", runner, new Clipboard(null), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(runner.Arguments![^1], Is.EqualTo("text"));
            Assert.That(result!.Verified, Is.True);
        });
    }

    // Control: a closed application still goes the ordinary way, whatever the clipboard holds.
    [Test]
    public async Task AClosedApplicationGoesTheOrdinaryWayWithoutReadingTheAnswer()
    {
        var runner = new RecordingRunner("{\"ok\":false,\"running\":false,\"effectObserved\":false,\"error\":\"office_app_not_open\"}");

        OfficePasteResult? result = await OfficeNewDocumentPaste.TryAsync(
            "word", runner, new Clipboard(new ClipboardProviderException("clipboard_owner_not_responding")), CancellationToken.None);

        Assert.That(result, Is.Null);
    }

    [Test]
    public async Task AnyOtherApplicationNeverReadsTheClipboard()
    {
        var clipboard = new Clipboard(null);

        OfficePasteResult? result = await OfficeNewDocumentPaste.TryAsync(
            "Bloc de notas", new RecordingRunner(string.Empty), clipboard, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result, Is.Null);
            Assert.That(clipboard.Reads, Is.Zero);
        });
    }

    // The real script, on the real PowerShell, with the running application stubbed: what it was told is what it answers.
    [TestCase("clipboard_owner_not_responding")]
    [TestCase("clipboard_empty")]
    public async Task TheScriptAnswersWhatItWasTold(string held)
    {
        const string RunningApplication = "$office=$true";
        string script = System.Text.RegularExpressions.Regex.Replace(
            OfficeNewDocumentPaste.Script,
            @"try \{ \$office=.*?\}\s*catch \{.*?\}\s*\}",
            RunningApplication,
            System.Text.RegularExpressions.RegexOptions.Singleline);
        Assert.That(script, Does.Contain(RunningApplication));

        ExternalProcessResult process = await new ExternalProcessRunner().RunPowerShellAsync(
            script, ["word", held], TimeSpan.FromSeconds(30), CancellationToken.None);

        Assert.That(process.Output, Does.Contain("\"error\":\"" + held + "\"").And.Contain("\"effectObserved\":false"));
    }

    private sealed class Clipboard(ClipboardProviderException? failure) : IClipboardProvider
    {
        public int Reads { get; private set; }

        public ValueTask<ClipboardTextSnapshot> ReadTextAsync(int maximumCharacters, CancellationToken cancellationToken)
        {
            Reads++;
            return failure is null
                ? ValueTask.FromResult(new ClipboardTextSnapshot("h", 1, true, 1))
                : throw failure;
        }

        public ValueTask<ClipboardWriteResult> WriteTextAsync(string text, CancellationToken cancellationToken) =>
            throw new InvalidOperationException();
    }

    private sealed class RecordingRunner(string output) : IExternalProcessRunner
    {
        public IReadOnlyList<string>? Arguments { get; private set; }

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable,
            IReadOnlyList<string> arguments,
            TimeSpan timeout,
            CancellationToken cancellationToken)
        {
            Arguments = arguments;
            return ValueTask.FromResult(new ExternalProcessResult(0, output, string.Empty));
        }
    }
}
