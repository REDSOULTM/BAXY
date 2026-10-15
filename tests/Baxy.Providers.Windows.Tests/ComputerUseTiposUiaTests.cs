using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Goal v3 point 2, mouse-free primitives (cu-v3 r2 diag_tipos §2.B): a form's value replaced in its field (never in
/// a document, never without the field), a list-only combo box's entry chosen by pattern, an element brought into view
/// by UI Automation alone, and the surface of a window its own modal dialog disabled. Every effect goes to fakes.
/// </summary>
[TestFixture]
public sealed class ComputerUseTiposUiaTests
{
    private static readonly nint Edit = 4661;

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private static WindowsDesktopInteractionAdapter Adapter(
        FakeDesktopKeyboard keyboard, FakeFieldMessages messages, FakeViewedFields? fields = null) =>
        new(new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard, fields, messages);

    private static FakeViewedFields WorkerLeavesItToTheEditControl(string kind = "Edit") =>
        new($$"""{"ok":true,"error":"","kind":"{{kind}}","className":"Edit","nativeHwnd":4661,"method":"","delivered":false}""");

    // «poner el ancho en 800» on a field that holds «1366»: the value is replaced, not appended («1366800»).
    [Test]
    public async Task AReplacedValueTakesTheWholeFieldThroughItsEditControl()
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "Edit", "1366");
        FakeViewedFields fields = WorkerLeavesItToTheEditControl();

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, fields).InvokeAsync(
            "input.text.type", Json("""{"text":"800","window":4660,"index":2,"replace":true,"field":"Ancho"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(messages.Content[Edit], Is.EqualTo("800"));
            Assert.That(fields.Replaces.Single(), Is.True, "the worker is told the value is replaced");
            Assert.That(keyboard.Fronted, Is.Empty);
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // Contracase: without replace the same field keeps its text and the value goes at the caret.
    [Test]
    public async Task WithoutReplaceTheFieldKeepsItsText()
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "Edit", "1366");

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, WorkerLeavesItToTheEditControl()).InvokeAsync(
            "input.text.type", Json("""{"text":"800","window":4660,"index":2}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(messages.Content[Edit], Is.EqualTo("1366800"));
        });
    }

    // A control that does not take the whole selection would leave part of the old value: nothing is inserted.
    [Test]
    public async Task AFieldThatDoesNotSelectAllIsNotReplaced()
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages { TakesSelectAll = false }.WithField(Edit, "Edit", "1366");

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, WorkerLeavesItToTheEditControl()).InvokeAsync(
            "input.text.type", Json("""{"text":"800","window":4660,"index":2,"replace":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_field_not_replaced"));
            Assert.That(messages.Content[Edit], Is.EqualTo("1366"));
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // A document is the person's work: it is never replaced whole, by any path.
    [Test]
    public async Task ADocumentIsNeverReplaced()
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "RichEditD2DPT", "Querido Ron");

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, WorkerLeavesItToTheEditControl("Document"))
            .InvokeAsync("input.text.type", Json("""{"text":"hola","window":4660,"index":0,"replace":true}"""),
                CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_field_not_replaceable"));
            Assert.That(messages.Content[Edit], Is.EqualTo("Querido Ron"));
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // Pasada r15b (t-long-2): a «replace» on a field the worker read empty (the page of a new document) has nothing to
    // replace: the text goes in. Contracase: one that holds text (the person's work) is still never replaced.
    [TestCase("", 0, true, "hola")]
    [TestCase("Querido Ron", 11, false, "Querido Ron")]
    public async Task AReplaceOnAFieldReadEmptyIsAnInsertion(string held, int length, bool verified, string after)
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "RichEditD2DPT", held);
        var fields = new FakeViewedFields(
            $$"""{"ok":true,"error":"","kind":"Document","className":"RichEditD2DPT","nativeHwnd":4661,"valueLength":{{length}},"method":"","delivered":false}""");

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, fields).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660,"index":0,"replace":true,"field":"Contenido de la página 1"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.EqualTo(verified));
            Assert.That(messages.Content[Edit], Is.EqualTo(after));
            if (!verified)
            {
                Assert.That(receipt.ErrorCode, Is.EqualTo("input_field_not_replaceable"));
            }

            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // Review of cierre-de-subobjetivos (finding 2): a field read empty with no window of its own (a Document, WebView2,
    // XAML: no nativeHwnd; or an empty field whose SetValue was refused) is never «inserted» through the keyboard, whose
    // focus may be another control: the replacement stays refused and nothing is sent.
    [TestCase("""{"ok":true,"error":"","kind":"Document","className":"","valueLength":0,"method":"","delivered":false}""")]
    [TestCase("""{"ok":false,"error":"field_setvalue_refused","kind":"Edit","className":"","valueLength":0}""")]
    public async Task AFieldReadEmptyWithoutItsWindowIsNeverTypedByKeyboard(string worker)
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "Edit", "asunto");
        var fields = new FakeViewedFields(worker);

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, fields).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660,"index":0,"replace":true,"field":"Cuerpo"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_field_not_replaceable"));
            Assert.That(messages.Content[Edit], Is.EqualTo("asunto"));
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // Review of cierre-de-subobjetivos r2 (finding 1): a field read empty whose own window the messages cannot write (no
    // edit control: a word processor's body, a browser's render widget, a XAML host; or a window outside this one) is
    // not inserted either: the replacement stays refused, before any effect, and the keyboard never takes the text.
    // Contracase: the same empty field behind a classic edit control takes the text by its messages.
    [TestCase("_WwG", false, false, "")]
    [TestCase("Chrome_RenderWidgetHostHWND", false, false, "")]
    [TestCase("Windows.UI.Input.InputSite.WindowClass", false, false, "")]
    [TestCase("Edit", true, false, "")]
    [TestCase("Edit", false, true, "hola")]
    public async Task AFieldReadEmptyWhoseWindowTheMessagesCannotWriteIsNeverTypedByKeyboard(
        string fieldClass, bool outside, bool verified, string after)
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, fieldClass, string.Empty);
        if (outside)
        {
            messages.Outside.Add(Edit);
        }

        var fields = new FakeViewedFields(
            $$"""{"ok":true,"error":"","kind":"Document","className":"{{fieldClass}}","nativeHwnd":4661,"valueLength":0,"method":"","delivered":false}""");

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, fields).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660,"index":0,"replace":true,"field":"Cuerpo"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.EqualTo(verified));
            if (!verified)
            {
                Assert.That(receipt.ErrorCode, Is.EqualTo("input_field_not_replaceable"));
            }

            Assert.That(messages.Content[Edit], Is.EqualTo(after));
            Assert.That(keyboard.Texts, Is.Empty);
            Assert.That(keyboard.Fronted, Is.Empty);
        });
    }

    // r25 review (finding 1): a text aimed at a field (its index) that neither its value nor its messages reach (XAML,
    // WPF, a browser's bar: no window of its own) never goes by keyboard to the window's focus, which may be a password
    // or the page's search: refused before any effect. Contracase: the field that has the keyboard's focus takes it.
    [TestCase(false, false)]
    [TestCase(true, true)]
    public async Task ATextForAFieldNothingReachesGoesByKeyboardOnlyToThatFocusedField(bool focused, bool typed)
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "Edit", "asunto");
        var fields = new FakeViewedFields(
            $$"""{"ok":true,"error":"","kind":"Edit","className":"TextBox","nativeHwnd":0,"focused":{{(focused ? "true" : "false")}},"valueLength":4,"method":"","delivered":false}""");

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, fields).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660,"index":0,"field":"Usuario"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            if (typed)
            {
                Assert.That(receipt.ErrorCode, Is.Not.EqualTo("input_field_not_reachable"));
                Assert.That(keyboard.Fronted, Is.Not.Empty, "the keyboard path was taken");
            }
            else
            {
                Assert.That(receipt.Verified, Is.False);
                Assert.That(receipt.EffectMayHaveOccurred, Is.False);
                Assert.That(receipt.ErrorCode, Is.EqualTo("input_field_not_reachable"));
                Assert.That(keyboard.Texts, Is.Empty);
                Assert.That(keyboard.Fronted, Is.Empty);
            }

            Assert.That(messages.Content[Edit], Is.EqualTo("asunto"));
        });
    }

    // Replacing needs the field itself: neither the window's focus nor the keyboard (Ctrl+A could select a document).
    [Test]
    public async Task AReplaceWithoutItsFieldSendsNothing()
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "Edit", "1366");

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages).InvokeAsync(
            "input.text.type", Json("""{"text":"800","window":4660,"replace":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_field_not_replaceable"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(messages.Content[Edit], Is.EqualTo("1366"));
            Assert.That(keyboard.Texts, Is.Empty);
            Assert.That(keyboard.Fronted, Is.Empty);
        });
    }

    // A field named by its label that the mission found in no view (no index): the text goes nowhere, never to the
    // window's focus.
    [Test]
    public async Task ANamedFieldNotFoundTakesNothing()
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "Edit", string.Empty);

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages).InvokeAsync(
            "input.text.type", Json("""{"text":"800","window":4660,"field":"Alto"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_field_not_found"));
            Assert.That(messages.Content[Edit], Is.Empty);
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // A list-only combo box: the worker chose the entry of that name by pattern and re-read its selection.
    [TestCase(true, true)]
    [TestCase(false, false)]
    public async Task AComboEntryChosenByPatternIsProvedByItsSelection(bool selected, bool verified)
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields(
            $$"""{"ok":true,"error":"","kind":"ComboBox","className":"ComboBox","nativeHwnd":0,"method":"select","delivered":{{(selected ? "true" : "false")}}}""");

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, new FakeFieldMessages(), fields).InvokeAsync(
            "input.text.type", Json("""{"text":"Arial","window":4660,"index":5,"replace":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.EqualTo(verified));
            if (verified)
            {
                Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("select"));
                Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("windows_uia_selection_reread"));
            }
            else
            {
                Assert.That(receipt.ErrorCode, Is.EqualTo("input_effect_not_verified"));
            }

            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // Review of combos-galerias (findings 1, 2): an entry of a list («entry») is only chosen by pattern in that list,
    // read-only list or not; the worker's selection proves it.
    [Test]
    public async Task AListEntryIsChosenByPatternAndNeverWritten()
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields(
            """{"ok":true,"error":"","kind":"ComboBox","className":"ComboBox","entry":true,"method":"select","delivered":true}""");

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, new FakeFieldMessages(), fields).InvokeAsync(
            "input.text.type", Json("""{"text":"Wingdings","window":4660,"index":5,"replace":true,"entry":true,"field":"Fuente"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("select"));
            Assert.That(fields.Entries.Single(), Is.EqualTo(("4.2.5", "Wingdings")));
            Assert.That(fields.Requests, Is.Empty, "no text was written into the box");
            Assert.That(keyboard.Texts, Is.Empty);
            Assert.That(keyboard.Fronted, Is.Empty);
        });
    }

    // Contracase (finding 1): a list with no entry of that name (a goal misread: «Arial en el documento») changes
    // nothing: no SetValue, no edit-control message, no keyboard.
    [Test]
    public async Task AListWithoutThatEntryChangesNothing()
    {
        var keyboard = new FakeDesktopKeyboard();
        FakeFieldMessages messages = new FakeFieldMessages().WithField(Edit, "Edit", "Calibri");
        var fields = new FakeViewedFields(
            """{"ok":true,"error":"","kind":"ComboBox","className":"ComboBox","nativeHwnd":4661,"entry":true,"method":"","delivered":false}""");

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, messages, fields).InvokeAsync(
            "input.text.type", Json("""{"text":"Arial en el documento","window":4660,"index":5,"replace":true,"entry":true}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_entry_not_found"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(fields.Requests, Is.Empty);
            Assert.That(messages.Content[Edit], Is.EqualTo("Calibri"), "the box's edit control got no message");
            Assert.That(keyboard.Texts, Is.Empty);
            Assert.That(keyboard.Fronted, Is.Empty);
        });
    }

    // Contracase: an entry without its box in the view goes nowhere.
    [Test]
    public async Task AnEntryWithoutItsBoxGoesNowhere()
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields("""{"ok":true,"method":"select","delivered":true}""");

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, new FakeFieldMessages(), fields).InvokeAsync(
            "input.text.type", Json("""{"text":"Wingdings","window":4660,"entry":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_field_not_found"));
            Assert.That(fields.Entries, Is.Empty);
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    private static WindowsScrollAdapter Reveal(string answer, List<(nint Window, string Label, int Pages)> asked) =>
        new(reveal: (window, label, direction, pages, token) =>
        {
            asked.Add((window, label, pages));
            return ValueTask.FromResult<JsonDocument?>(JsonDocument.Parse(answer));
        });

    // «bajá en la lista hasta Omega»: brought into view by UI Automation, no wheel, no pointer, no front.
    [TestCase("scrollintoview", true)]
    [TestCase("itemcontainer", true)]
    [TestCase("scroll", true)]
    [TestCase("already", false)]
    public async Task AnElementOutOfViewIsRevealedWithoutTheWheel(string method, bool moved)
    {
        var asked = new List<(nint, string, int)>();
        ExternalCapabilityReceipt receipt = await Reveal(
            $$"""{"ok":true,"error":"","method":"{{method}}","name":"Omega","revealed":{{(moved ? "true" : "false")}},"visible":true}""",
            asked).InvokeAsync(
                "input.scroll", Json("""{"direction":"down","amount":5,"label":"Omega","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("uia_reveal_visible_postread"));
            Assert.That(receipt.Result?.GetProperty("revealed").GetBoolean(), Is.EqualTo(moved));
            Assert.That(receipt.Result?.GetProperty("surfaceChanged").GetBoolean(), Is.EqualTo(moved));
            Assert.That(asked.Single(), Is.EqualTo(((nint)4660, "Omega", 20)), "the mission's window, the label, 4 pages a step");
        });
    }

    // Contracases: not found after turning pages moved something (not verified, effect possible); not found by reading
    // the tree moved nothing; a reveal outside a mission's window is refused before anything.
    [Test]
    public async Task ARevealThatDoesNotSeeTheElementIsNotVerified()
    {
        var asked = new List<(nint, string, int)>();
        ExternalCapabilityReceipt paged = await Reveal(
            """{"ok":false,"error":"reveal_not_found","method":"scroll","name":"","revealed":false,"visible":false}""", asked)
            .InvokeAsync("input.scroll", Json("""{"direction":"down","amount":3,"label":"Zeta","window":4660}"""), CancellationToken.None);
        ExternalCapabilityReceipt read = await Reveal(
            """{"ok":false,"error":"reveal_not_found","method":"","name":"","revealed":false,"visible":false}""", asked)
            .InvokeAsync("input.scroll", Json("""{"direction":"down","amount":3,"label":"Zeta","window":4660}"""), CancellationToken.None);
        ExternalCapabilityReceipt unbound = await Reveal("""{"ok":true}""", asked)
            .InvokeAsync("input.scroll", Json("""{"direction":"down","amount":3,"label":"Zeta"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(paged.Verified, Is.False);
            Assert.That(paged.ErrorCode, Is.EqualTo("reveal_not_found"));
            Assert.That(paged.EffectMayHaveOccurred, Is.True);
            Assert.That(read.Verified, Is.False);
            Assert.That(read.EffectMayHaveOccurred, Is.False);
            Assert.That(unbound.ErrorCode, Is.EqualTo("scroll_argument_invalid"));
            Assert.That(asked, Has.Count.EqualTo(2), "the unbound reveal never reached the worker");
        });
    }

    // A window its own modal dialog disabled is seen through that dialog; the chain is followed while each is
    // disabled by another; another process's pop-up, or none, leaves the window itself.
    [Test]
    public void AWindowDisabledByItsDialogIsSeenThroughIt()
    {
        var enabled = new HashSet<nint> { 20, 30 };
        var popups = new Dictionary<nint, nint> { [10] = 20, [11] = 11, [12] = 40 };
        var process = new Dictionary<nint, uint> { [10] = 7, [11] = 7, [12] = 7, [20] = 7, [30] = 7, [40] = 9 };
        nint Surface(nint window) => VisibleControlSurface.ModalSurface(
            window, enabled.Contains, hwnd => popups.GetValueOrDefault(hwnd), _ => true, hwnd => process.GetValueOrDefault(hwnd));

        Assert.Multiple(() =>
        {
            Assert.That(Surface(10), Is.EqualTo((nint)20), "the dialog of the disabled window");
            Assert.That(Surface(30), Is.EqualTo((nint)30), "an enabled window is itself");
            Assert.That(Surface(11), Is.EqualTo((nint)11), "no pop-up: the window itself");
            Assert.That(Surface(12), Is.EqualTo((nint)12), "another process's pop-up is not its dialog");
        });
    }

    [Test]
    public void ADialogThatOpenedAnotherIsFollowedToTheEnabledOne()
    {
        var enabled = new HashSet<nint> { 30 };
        var popups = new Dictionary<nint, nint> { [10] = 20, [20] = 30 };

        nint surface = VisibleControlSurface.ModalSurface(
            10, enabled.Contains, hwnd => popups.GetValueOrDefault(hwnd), _ => true, _ => 7);

        Assert.That(surface, Is.EqualTo((nint)30));
    }

    private sealed class NoProcessRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken) =>
            throw new AssertionException("keys and text start no process");
    }
}
