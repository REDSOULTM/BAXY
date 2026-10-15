using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// cu-v3-scroll-pegar-direccion, t-long-1 (pasada r9): «copiá el resultado, abrí el bloc de notas y pegalo». Measured in
/// the journal: the Calculator's Ctrl+C went through (17:18:31), the editor opened behind the person's window
/// (app.open ok, 17:18:32) and its Ctrl+V was refused with <c>input_window_not_in_front</c> 1.5 s later: the keyboard
/// path asks for the front, and an application opened behind does not get it. The paste now goes without keyboard or
/// front: the clipboard's text BAXY reads, inserted at the caret of the window's edit control and re-read there.
/// Every effect goes to fakes; nothing is sent on the desktop.
/// </summary>
[TestFixture]
public sealed class PasteDeliveryTests
{
    private static readonly nint Edit = 4661;

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private static WindowsDesktopInteractionAdapter Adapter(
        FakeDesktopKeyboard keyboard, FakeFieldMessages messages, string? clipboard) =>
        new(new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard, null, messages,
            () => clipboard);

    [Test]
    public async Task ThePasteReachesAnEditorOpenedBehindWithoutTheFront()
    {
        // The window the person holds stays in front: the editor would not get it (t-long-1's refusal).
        var keyboard = new FakeDesktopKeyboard { Frontable = false };
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "RichEditD2DPT", string.Empty);

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, "1024").InvokeAsync(
            "input.key.press", Json("""{"key":"ctrl_v","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("em_replacesel"));
            Assert.That(receipt.Result?.GetProperty("key").GetString(), Is.EqualTo("ctrl_v"));
            Assert.That(receipt.Result?.GetProperty("textLength").GetInt32(), Is.EqualTo(4));
            Assert.That(messages.Content[Edit], Is.EqualTo("1024"));
            Assert.That(keyboard.Fronted, Is.Empty, "nothing was brought to the front");
            Assert.That(keyboard.Chords, Is.Empty, "no chord on the keyboard");
        });
    }

    [Test]
    public async Task AWindowThatReportsNoFocusTakesThePasteInItsOnlyEditControl()
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages { ReportsFocus = false }.WithField(Edit, "RichEditD2DPT", "nota: ");

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, "1024").InvokeAsync(
            "input.key.press", Json("""{"key":"ctrl_v","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(messages.Content[Edit], Is.EqualTo("nota: 1024"));
            Assert.That(keyboard.Chords, Is.Empty);
        });
    }

    [Test]
    public async Task CounterCaseTwoEditControlsWithoutFocusLeaveThePasteToTheKeyboard()
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages { ReportsFocus = false }
            .WithField(Edit, "Edit", string.Empty)
            .WithField(4662, "Edit", string.Empty);

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, "1024").InvokeAsync(
            "input.key.press", Json("""{"key":"ctrl_v","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("keyboard"));
            Assert.That(messages.Content[Edit], Is.Empty, "no field was guessed");
            Assert.That(messages.Content[4662], Is.Empty);
            Assert.That(keyboard.Chords, Has.Count.EqualTo(1));
        });
    }

    [Test]
    public async Task CounterCaseAFocusThatIsNoEditControlNeverSendsThePasteToAnotherField()
    {
        // A hybrid window: the text box with the keyboard is inside a web view (no edit class) and a classic filter box
        // is the window's only edit control. A keyboard's Ctrl+V goes to the focus, never to the filter.
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages()
            .WithField(Edit, "Edit", string.Empty)
            .WithField(4663, "Chrome_RenderWidgetHostHWND", string.Empty);

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, "1024").InvokeAsync(
            "input.key.press", Json("""{"key":"ctrl_v","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(messages.Focus, Is.EqualTo((nint)4663));
            Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("keyboard"));
            Assert.That(messages.Content[Edit], Is.Empty, "the filter box got nothing");
            Assert.That(keyboard.Chords, Has.Count.EqualTo(1));
        });
    }

    [Test]
    public async Task CounterCaseAClipboardLongerThanATypedTextKeepsTheKeyboardPaste()
    {
        // Character by character past the typed limit the window's queue fills and a part would be left pasted.
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "RichEditD2DPT", string.Empty);

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, new string('7', 4097)).InvokeAsync(
            "input.key.press", Json("""{"key":"ctrl_v","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("keyboard"));
            Assert.That(messages.Content[Edit], Is.Empty);
            Assert.That(keyboard.Chords, Has.Count.EqualTo(1));
        });
    }

    [Test]
    public async Task AClipboardAtTheTypedLimitStillGoesWithoutTheFront()
    {
        var keyboard = new FakeDesktopKeyboard { Frontable = false };
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "RichEditD2DPT", string.Empty);
        string pasted = new('7', 4096);

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, pasted).InvokeAsync(
            "input.key.press", Json("""{"key":"ctrl_v","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(messages.Content[Edit], Is.EqualTo(pasted));
            Assert.That(keyboard.Chords, Is.Empty);
        });
    }

    [TestCase(null)]
    [TestCase("")]
    [TestCase("línea uno\r\nlínea dos")]
    public async Task CounterCaseAClipboardWithoutOneLineOfTextKeepsTheKeyboardPaste(string? clipboard)
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "RichEditD2DPT", string.Empty);

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, clipboard).InvokeAsync(
            "input.key.press", Json("""{"key":"ctrl_v","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("keyboard"));
            Assert.That(messages.Content[Edit], Is.Empty);
            Assert.That(keyboard.Chords, Has.Count.EqualTo(1));
        });
    }

    [Test]
    public async Task CounterCaseAReadOnlyEditGetsNothingByAnyPath()
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "Edit", "registro");
        messages.Styles[Edit] = 0x0800;

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, "1024").InvokeAsync(
            "input.key.press", Json("""{"key":"ctrl_v","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_field_not_writable"));
            Assert.That(messages.Content[Edit], Is.EqualTo("registro"));
            Assert.That(keyboard.Chords, Is.Empty);
        });
    }

    [Test]
    public async Task CounterCaseAnotherKeyChordStillGoesByTheKeyboard()
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "RichEditD2DPT", "texto");

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, "1024").InvokeAsync(
            "input.key.press", Json("""{"key":"ctrl_c","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("keyboard"));
            Assert.That(messages.Content[Edit], Is.EqualTo("texto"));
        });
    }

    private sealed class NoProcessRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken) =>
            throw new AssertionException("keys start no process");
    }
}
