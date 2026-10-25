using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Práctica V5E061 («abre el bloc de notas y escribe: reunión con Pedro el martes», then «cámbialo, era el miércoles, no
/// el martes»: the new text went in at the caret, «…el martesreunión con Pedro el miércoles», or replace was refused for a
/// document): input.text.type with <c>replacing</c> changes that one part of the field's text. The old text is found in
/// the field's whole text exactly once, selected (EM_SETSEL) and typed over (EM_REPLACESEL), and the whole text read back
/// must be the old one with only that part changed. Not there, there more than once, a field whose text is not read or a
/// password: refused before anything is sent. Every effect goes to fakes; nothing is sent on the desktop.
/// </summary>
[TestFixture]
public sealed class TextReplacingTests
{
    private static readonly nint Edit = 4661;

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private static WindowsDesktopInteractionAdapter Adapter(
        FakeDesktopKeyboard keyboard, FakeFieldMessages messages, FakeViewedFields? fields = null) =>
        new(new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard, fields, messages);

    private static FakeFieldMessages Notepad(string content, bool breaksCountOne = false) =>
        new FakeFieldMessages { BreaksCountOne = breaksCountOne }.WithField(Edit, "RichEditD2DPT", content);

    private static Task<ExternalCapabilityReceipt> Replace(
        FakeDesktopKeyboard keyboard, FakeFieldMessages messages, string arguments, FakeViewedFields? fields = null) =>
        Adapter(keyboard, messages, fields).InvokeAsync("input.text.type", Json(arguments), CancellationToken.None).AsTask();

    [Test]
    public async Task TheOldTextFoundOnceIsTypedOverAndTheWholeTextIsReadBack()
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = Notepad("reunión con Pedro el martes");
        messages.Selected[Edit] = (27, 27);

        ExternalCapabilityReceipt receipt = await Replace(keyboard, messages,
            """{"text":"miércoles","replacing":"martes","window":4660}""");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(messages.Content[Edit], Is.EqualTo("reunión con Pedro el miércoles"));
            Assert.That(messages.Selects.Single(), Is.EqualTo((Edit, 21, 27)));
            Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("em_replacesel"));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("win32_edit_text_reread_whole"));
            Assert.That(receipt.Result?.GetProperty("replaced").GetString(), Is.EqualTo(
                "«martes» was replaced by «miércoles» at its one place in the text; the whole text was read back "
                + "after it: it holds «miércoles» there and nothing else in it changed"));
            Assert.That(receipt.Result?.TryGetProperty("landed", out _), Is.False);
            Assert.That(keyboard.Texts, Is.Empty, "nothing was typed on the keyboard");
            Assert.That(keyboard.Fronted, Is.Empty, "nothing was brought to the front");
        });
    }

    // With no window named, the focused edit control of the window in front, as a text with no window goes there.
    [Test]
    public async Task WithNoWindowNamedTheFocusOfTheWindowInFrontIsChanged()
    {
        var keyboard = new FakeDesktopKeyboard { Front = new DesktopForeground(4660, 4242, "Sin título: Bloc de notas") };
        FakeFieldMessages messages = Notepad("reunión con Pedro el martes");

        ExternalCapabilityReceipt receipt = await Replace(keyboard, messages,
            """{"text":"miércoles","replacing":"martes"}""");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(messages.Content[Edit], Is.EqualTo("reunión con Pedro el miércoles"));
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // A rich edit's positions count a line break as one character, where WM_GETTEXT gives «\r\n».
    [Test]
    public async Task TheOldTextIsSelectedAtTheRichEditsOwnPositionAfterLineBreaks()
    {
        FakeFieldMessages messages = Notepad("lista\r\nreunión el martes\r\nfin", breaksCountOne: true);

        ExternalCapabilityReceipt receipt = await Replace(new FakeDesktopKeyboard(), messages,
            """{"text":"miércoles","replacing":"martes","window":4660}""");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(messages.Selects.Single(), Is.EqualTo((Edit, 17, 23)));
            Assert.That(messages.Content[Edit], Is.EqualTo("lista\r\nreunión el miércoles\r\nfin"));
        });
    }

    // A classic edit control counts «\r\n» as two, as its WM_GETTEXT gives it.
    [Test]
    public async Task AClassicEditControlIsSelectedAtTheTextsOwnIndex()
    {
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "Edit", "lista\r\nel martes");

        ExternalCapabilityReceipt receipt = await Replace(new FakeDesktopKeyboard(), messages,
            """{"text":"miércoles","replacing":"martes","window":4660}""");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(messages.Selects.Single(), Is.EqualTo((Edit, 10, 16)));
            Assert.That(messages.Content[Edit], Is.EqualTo("lista\r\nel miércoles"));
        });
    }

    // Revisión w11-rev4: the person writes in the field between the read and the selection; the range selected no
    // longer holds the old text, so nothing is typed over it.
    [Test]
    public async Task ATextChangedBeforeTheSelectionIsNotTypedOver()
    {
        FakeFieldMessages messages = Notepad("reunión con Pedro el martes");
        messages.OnSelect = field => messages.Content[field] = "Hoy " + messages.Content[field];

        ExternalCapabilityReceipt receipt = await Replace(new FakeDesktopKeyboard(), messages,
            """{"text":"miércoles","replacing":"martes","window":4660}""");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_effect_not_verified"));
            Assert.That(messages.Content[Edit], Is.EqualTo("Hoy reunión con Pedro el martes"), "nothing was typed over");
        });
    }

    [Test]
    public async Task AnOldTextThatIsNotThereChangesNothing()
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = Notepad("reunión con Pedro el martes");

        ExternalCapabilityReceipt receipt = await Replace(keyboard, messages,
            """{"text":"miércoles","replacing":"Martes","window":4660}""");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_text_replacing_not_found"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.Result?.GetProperty("occurrences").GetInt32(), Is.EqualTo(0));
            Assert.That(receipt.Result?.GetProperty("next").GetString(), Does.Contain("nothing was changed"));
            Assert.That(messages.Selects, Is.Empty);
            Assert.That(messages.Content[Edit], Is.EqualTo("reunión con Pedro el martes"));
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    [Test]
    public async Task AnOldTextThatIsThereMoreThanOnceChangesNothingAndSaysHowManyTimes()
    {
        FakeFieldMessages messages = Notepad("el martes con Pedro, el martes con Ana");

        ExternalCapabilityReceipt receipt = await Replace(new FakeDesktopKeyboard(), messages,
            """{"text":"miércoles","replacing":"martes","window":4660}""");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_text_replacing_ambiguous"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.Result?.GetProperty("occurrences").GetInt32(), Is.EqualTo(2));
            Assert.That(receipt.Result?.GetProperty("next").GetString(), Does.Contain("2 times"));
            Assert.That(messages.Selects, Is.Empty);
            Assert.That(messages.Content[Edit], Is.EqualTo("el martes con Pedro, el martes con Ana"));
        });
    }

    [TestCase(0x0020L)]
    [TestCase(0x0800L)]
    public async Task APasswordOrReadOnlyFieldIsNeverChanged(long style)
    {
        FakeFieldMessages messages = Notepad("clave martes");
        messages.Styles[Edit] = style;

        ExternalCapabilityReceipt receipt = await Replace(new FakeDesktopKeyboard(), messages,
            """{"text":"miércoles","replacing":"martes","window":4660}""");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_field_not_writable"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(messages.Selects, Is.Empty);
            Assert.That(messages.Content[Edit], Is.EqualTo("clave martes"));
        });
    }

    // A focus that is no edit control (a document drawn by the application itself): its text is not read by messages,
    // and the keyboard would add the text at its caret. Nothing is sent.
    [Test]
    public async Task AFieldWhoseTextIsNotReadIsRefusedBeforeAnything()
    {
        var keyboard = new FakeDesktopKeyboard { Front = new DesktopForeground(4660, 4242, "Documento - Word") };
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "_WwG", "el martes");

        ExternalCapabilityReceipt receipt = await Replace(keyboard, messages,
            """{"text":"miércoles","replacing":"martes"}""");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_field_not_readable"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(keyboard.Texts, Is.Empty);
            Assert.That(keyboard.Chords, Is.Empty);
            Assert.That(messages.Content[Edit], Is.EqualTo("el martes"));
        });
    }

    // The control took the replacement elsewhere (or not at all): the read-back is not the old text with that part
    // changed, and the receipt never says it was.
    [Test]
    public async Task AReadBackThatIsNotTheOldTextWithThatPartChangedIsNotVerified()
    {
        FakeFieldMessages messages = new FakeFieldMessages { TakesReplace = false }
            .WithField(Edit, "RichEditD2DPT", "reunión con Pedro el martes");

        ExternalCapabilityReceipt receipt = await Replace(new FakeDesktopKeyboard(), messages,
            """{"text":"miércoles","replacing":"martes","window":4660}""");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_effect_not_verified"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
        });
    }

    // A field of the last view (index) is read by the worker without writing anything (no text), and its own edit
    // control's window is the one changed: a document too, since only that part of it changes.
    [Test]
    public async Task AViewedDocumentIsChangedThroughItsOwnEditControlAfterAReadOfTheField()
    {
        FakeFieldMessages messages = Notepad("reunión con Pedro el martes");
        var fields = new FakeViewedFields(
            """{"ok":true,"error":"","kind":"Document","className":"RichEditD2DPT","nativeHwnd":4661,"focused":true,"password":false,"readOnly":false,"enabled":true,"valueLength":27,"method":"","delivered":false}""");

        ExternalCapabilityReceipt receipt = await Replace(new FakeDesktopKeyboard(), messages,
            """{"text":"miércoles","replacing":"martes","window":4660,"index":3}""", fields);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(fields.Requests.Single(), Is.EqualTo(("4.2.7", (string?)null)), "the field is only read");
            Assert.That(messages.Content[Edit], Is.EqualTo("reunión con Pedro el miércoles"));
        });
    }

    [Test]
    public async Task AViewedPasswordFieldIsNeverChanged()
    {
        FakeFieldMessages messages = Notepad("martes");
        var fields = new FakeViewedFields(
            """{"ok":true,"error":"","kind":"Edit","className":"Edit","nativeHwnd":4661,"password":true,"readOnly":false,"enabled":true,"method":"","delivered":false}""");

        ExternalCapabilityReceipt receipt = await Replace(new FakeDesktopKeyboard(), messages,
            """{"text":"miércoles","replacing":"martes","window":4660,"index":3}""", fields);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_field_not_writable"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(messages.Selects, Is.Empty);
        });
    }

    // replacing changes a part: never with the whole value (replace) nor a list's entry; an old text carries no control
    // character, as a typed one (a line break is a key of its own).
    [TestCase("""{"text":"miércoles","replacing":"martes","replace":true,"window":4660}""")]
    [TestCase("""{"text":"miércoles","replacing":"martes","entry":true,"window":4660,"index":3}""")]
    [TestCase("""{"text":"miércoles","replacing":"el\nmartes","window":4660}""")]
    [TestCase("""{"text":"miércoles","replacing":"  ","window":4660}""")]
    [TestCase("""{"text":"miércoles","replacing":5,"window":4660}""")]
    public async Task AReplacingThatIsNoPartOfATextIsInvalid(string arguments)
    {
        FakeFieldMessages messages = Notepad("el\r\nmartes");

        ExternalCapabilityReceipt receipt = await Replace(new FakeDesktopKeyboard(), messages, arguments,
            new FakeViewedFields("""{"ok":true}"""));

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("desktop_interaction_argument_invalid"));
            Assert.That(messages.Selects, Is.Empty);
        });
    }

    private sealed class NoProcessRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken) =>
            throw new AssertionException("a replacement starts no process");
    }
}
