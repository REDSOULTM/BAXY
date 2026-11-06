using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo 98: a Ctrl+letter belongs to the application, and its language binds it (Windows 11's Notepad in Spanish: Ctrl+A
/// «Abrir», Ctrl+T «Ir a»; Word in Spanish: Ctrl+S underline, Ctrl+T center). What UI Automation can do goes by UI
/// Automation and the keys are the last resort; a dialog they raise is said, and closed when the key is not meant to open
/// any. Everything goes to fakes: nothing is pressed on the desktop.
/// </summary>
[TestFixture]
public sealed class LanguageBoundShortcutTests
{
    private static readonly ushort[] ControlA = [0x11, 0x41];
    private static readonly WindowWitness Before = new("nota.txt: Editor", true, "4660", 4660);
    private static readonly WindowWitness WithDialog = Before with { Enabled = false, Windows = "4660,5120", Front = 5120 };

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private static WindowsDesktopInteractionAdapter Adapter(FakeDesktopKeyboard keyboard, FakeViewedFields? fields = null) =>
        new(new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard, fields);

    private static ValueTask<ExternalCapabilityReceipt> Press(WindowsDesktopInteractionAdapter adapter, string key) =>
        adapter.InvokeAsync("input.key.press", Json($$"""{"key":"{{key}}","window":4660}"""), CancellationToken.None);

    [Test]
    public async Task ControlAOnAFocusWithTextIsAskedOfUiAutomationAndSendsNoKey()
    {
        var keyboard = new FakeDesktopKeyboard { WitnessBefore = Before, WitnessAfter = Before };
        var fields = new FakeViewedFields("""{"ok":true}""") { SelectsFocusedText = true };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_a");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(keyboard.Chords, Is.Empty);
            Assert.That(fields.FocusSelections, Is.EqualTo(new nint[] { 0x1234 }));
            JsonElement result = receipt.Result!.Value;
            Assert.That(result.GetProperty("method").GetString(), Is.EqualTo("ui_automation"));
            Assert.That(result.GetProperty("selectedBy").GetString(), Is.EqualTo("ui_automation"));
            Assert.That(result.GetProperty("authority").GetString(), Is.EqualTo("uia_textpattern_selection_postread"));
            Assert.That(result.TryGetProperty("next", out _), Is.False);
        });
    }

    // Contracase: a list of files or a focus with no text has no TextPattern to ask, and takes the keys as it always did.
    [Test]
    public async Task ControlAOnAFocusUiAutomationCannotSelectStillTakesTheKeys()
    {
        var keyboard = new FakeDesktopKeyboard { WitnessBefore = Before, WitnessAfter = Before with { Title = "2 elementos" } };
        var fields = new FakeViewedFields("""{"ok":true}""") { SelectsFocusedText = false };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_a");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(keyboard.Chords, Has.Count.EqualTo(1));
            Assert.That(keyboard.Chords[0], Is.EqualTo(ControlA));
            Assert.That(receipt.Result!.Value.GetProperty("method").GetString(), Is.EqualTo("keyboard"));
            Assert.That(receipt.Result!.Value.TryGetProperty("selectedBy", out _), Is.False);
        });
    }

    // The failure seen live: the key is another command here and leaves a dialog over the person's document. A key not
    // meant to open any window never counts as done, and what it opened is closed.
    [TestCase("ctrl_a")]
    [TestCase("ctrl_t")]
    [TestCase("ctrl_l")]
    [TestCase("ctrl_z")]
    public async Task AKeyNotMeantToOpenAWindowThatRaisedADialogSaysItAndClosesIt(string key)
    {
        var keyboard = new FakeDesktopKeyboard
        {
            WitnessBefore = Before,
            WitnessAfter = WithDialog,
            Raised = new RaisedWindow(5120, "Ir a la línea"),
        };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard), key);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsDesktopInteractionAdapter.ShortcutOpenedDialog));
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(keyboard.ClosedRaised, Is.EqualTo(new nint[] { 5120 }));
            JsonElement dialog = receipt.Result!.Value.GetProperty("dialogOpened");
            Assert.That(dialog.GetProperty("title").GetString(), Is.EqualTo("Ir a la línea"));
            Assert.That(dialog.GetProperty("closed").GetBoolean(), Is.True);
            string next = receipt.Result!.Value.GetProperty("next").GetString()!;
            Assert.That(next, Does.Contain("«Ir a la línea»").And.Contain("closed again"));
        });
    }

    [Test]
    public async Task ADialogThatDoesNotCloseIsSaidStillOpen()
    {
        var keyboard = new FakeDesktopKeyboard
        {
            WitnessBefore = Before,
            WitnessAfter = WithDialog,
            Raised = new RaisedWindow(5120, "Abrir"),
            ClosesRaised = false,
        };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard), "ctrl_a");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsDesktopInteractionAdapter.ShortcutOpenedDialog));
            Assert.That(receipt.Result!.Value.GetProperty("dialogOpened").GetProperty("closed").GetBoolean(), Is.False);
            Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Does.Contain("still open"));
        });
    }

    // Contracase: opening a dialog is what these keys are for (Guardar como, Abrir, Buscar). It is said by its title, so
    // the model reads which one it is, and left open.
    [TestCase("ctrl_o")]
    [TestCase("ctrl_s")]
    [TestCase("ctrl_shift_s")]
    [TestCase("ctrl_f")]
    [TestCase("ctrl_h")]
    [TestCase("ctrl_w")]
    public async Task AKeyMeantToOpenADialogLeavesItOpenAndSaysWhichOne(string key)
    {
        var keyboard = new FakeDesktopKeyboard
        {
            WitnessBefore = Before,
            WitnessAfter = WithDialog,
            Raised = new RaisedWindow(5120, "Guardar como"),
        };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard), key);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(keyboard.ClosedRaised, Is.Empty);
            JsonElement dialog = receipt.Result!.Value.GetProperty("dialogOpened");
            Assert.That(dialog.GetProperty("title").GetString(), Is.EqualTo("Guardar como"));
            Assert.That(dialog.GetProperty("closed").GetBoolean(), Is.False);
        });
    }

    // Windows 11's Notepad in Spanish: Ctrl+T is «Ir a la línea», a dialog drawn inside the window, with no window of its
    // own: only the focus tells it. Measured live: windowChanged false, ok true, and the next keys typed into it. Neither
    // Escape nor WindowPattern.Close closes it there; its CloseButton, by Invoke, does: UI Automation first, no key.
    [Test]
    public async Task ADialogDrawnInsideTheWindowIsSaidAndClosedByUiAutomation()
    {
        var keyboard = new FakeDesktopKeyboard { WitnessBefore = Before, WitnessAfter = Before };
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            FocusStates = [new FocusState(null, null), new FocusState("Ir a la línea", null), new FocusState(null, null)],
            ClosesFocusedDialog = true,
        };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_t");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsDesktopInteractionAdapter.ShortcutOpenedDialog));
            Assert.That(keyboard.Chords, Has.Count.EqualTo(1), "only the shortcut: the closing took no key");
            Assert.That(fields.DialogCloses, Is.EqualTo(1));
            JsonElement dialog = receipt.Result!.Value.GetProperty("dialogOpened");
            Assert.That(dialog.GetProperty("title").GetString(), Is.EqualTo("Ir a la línea"));
            Assert.That(dialog.GetProperty("closed").GetBoolean(), Is.True);
        });
    }

    // Its last resort: a dialog UI Automation cannot close gets Escape, and is told by what the focus reads after it.
    [TestCase(true)]
    [TestCase(false)]
    public async Task ADialogUiAutomationCannotCloseGetsEscapeAsALastResort(bool escapeCloses)
    {
        var keyboard = new FakeDesktopKeyboard { WitnessBefore = Before, WitnessAfter = Before };
        FocusState shown = new("Ir a la línea", null);
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            FocusStates = escapeCloses ? [new FocusState(null, null), shown, new FocusState(null, null)] : [new FocusState(null, null), shown],
            ClosesFocusedDialog = false,
        };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_t");

        Assert.Multiple(() =>
        {
            Assert.That(keyboard.Chords, Has.Count.EqualTo(2));
            Assert.That(keyboard.Chords[1], Is.EqualTo(new ushort[] { 0x1B }));
            Assert.That(receipt.Result!.Value.GetProperty("dialogOpened").GetProperty("closed").GetBoolean(), Is.EqualTo(escapeCloses));
        });
    }

    // Measured live: Ctrl+Shift+S raised «Guardar como» a moment late, the focus went to its name field, whose attributes
    // differ, and a Ctrl+Z was sent. A format counts only on the same element with the same selection: Ctrl+Z may undo
    // something of the person's.
    [TestCase("foco1|0|7", "foco2|0|7")]
    [TestCase("foco1|0|7", "foco1|3|7")]
    [TestCase("foco1|0|7", "foco1|0|2")]
    public async Task AnotherFocusOrSelectionIsNoFormatChangeAndGetsNoUndo(string placeBefore, string placeAfter)
    {
        var keyboard = new FakeDesktopKeyboard { WitnessBefore = Before, WitnessAfter = Before };
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            FocusStates = [new FocusState(null, "400|None", placeBefore), new FocusState(null, "700|Single", placeAfter)],
        };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_s");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(keyboard.Chords, Has.Count.EqualTo(1), "no Ctrl+Z");
        });
    }

    // Contracase: a find box is what Ctrl+F is for: no Escape, and said by its name.
    [Test]
    public async Task AnInsideDialogAKeyIsMeantToOpenStaysAndIsSaid()
    {
        var keyboard = new FakeDesktopKeyboard { WitnessBefore = Before, WitnessAfter = Before };
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            FocusStates = [new FocusState(null, null), new FocusState("Buscar", null)],
        };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_f");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(keyboard.Chords, Has.Count.EqualTo(1));
            Assert.That(receipt.Result!.Value.GetProperty("dialogOpened").GetProperty("title").GetString(), Is.EqualTo("Buscar"));
            Assert.That(receipt.Result!.Value.TryGetProperty("next", out _), Is.False, "«nothing changed» would be false");
        });
    }

    // Contracase: the focus was already in that dialog before the key: this key raised nothing.
    [Test]
    public async Task AnInsideDialogAlreadyThereIsNotThisKeys()
    {
        var keyboard = new FakeDesktopKeyboard { WitnessBefore = Before, WitnessAfter = Before };
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            FocusStates = [new FocusState("Ir a la línea", null), new FocusState("Ir a la línea", null)],
        };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_t");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(keyboard.Chords, Has.Count.EqualTo(1));
            Assert.That(receipt.Result!.Value.TryGetProperty("dialogOpened", out _), Is.False);
        });
    }

    // Word in Spanish, measured live: Ctrl+S underlines, Ctrl+T centers, Ctrl+K italics, Ctrl+H indents, all told ok with
    // nothing a witness sees. Read by UI Automation's text attributes, undone with Ctrl+Z (which every map measured keeps),
    // and said: a save that underlined is no success.
    [TestCase("ctrl_s")]
    [TestCase("ctrl_t")]
    [TestCase("ctrl_k")]
    [TestCase("ctrl_h")]
    public async Task AKeyThatChangedTheFormatInsteadIsUndoneAndSaid(string key)
    {
        var keyboard = new FakeDesktopKeyboard { WitnessBefore = Before, WitnessAfter = Before };
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            FocusStates = [new FocusState(null, "400|None"), new FocusState(null, "400|Single"), new FocusState(null, "400|None")],
        };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), key);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsDesktopInteractionAdapter.ShortcutChangedFormat));
            Assert.That(keyboard.Chords, Has.Count.EqualTo(2));
            Assert.That(keyboard.Chords[1], Is.EqualTo(new ushort[] { 0x11, 0x5A }));
            JsonElement result = receipt.Result!.Value;
            Assert.That(result.GetProperty("formatChanged").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("formatUndone").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("next").GetString(), Does.Contain("undone"));
        });
    }

    [Test]
    public async Task AFormatThatDidNotComeBackIsSaidNotUndone()
    {
        var keyboard = new FakeDesktopKeyboard { WitnessBefore = Before, WitnessAfter = Before };
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            FocusStates = [new FocusState(null, "400|None"), new FocusState(null, "400|Single")],
        };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_s");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsDesktopInteractionAdapter.ShortcutChangedFormat));
            Assert.That(receipt.Result!.Value.GetProperty("formatUndone").GetBoolean(), Is.False);
            Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Does.Contain("still changed"));
        });
    }

    // Contracase: a key whose job touches the text (Ctrl+Z undoes a format; Ctrl+X, Ctrl+V) is never undone by this watch.
    [TestCase("ctrl_z")]
    [TestCase("ctrl_v")]
    public async Task AKeyThatEditsTheTextIsNotWatchedForFormat(string key)
    {
        var keyboard = new FakeDesktopKeyboard { WitnessBefore = Before, WitnessAfter = Before };
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            FocusStates = [new FocusState(null, "400|None"), new FocusState(null, "400|Single")],
        };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), key);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(keyboard.Chords, Has.Count.EqualTo(1));
        });
    }

    // Word in Spanish takes Ctrl+S as underline and changes nothing a witness sees: the receipt says it may have been that.
    [Test]
    public void AShortcutThatChangedNothingSaysItMayHaveAppliedAnotherCommand() =>
        Assert.That(WindowsDesktopInteractionAdapter.ShortcutUnchanged, Does.Contain("another command").And.Contain("format"));

    [Test]
    public async Task AFieldUiAutomationSelectsGetsNoKey()
    {
        var keyboard = new FakeDesktopKeyboard { WitnessBefore = Before, WitnessAfter = WithDialog };
        var keys = new List<string>();

        FieldSelection selection = await FocusedFieldSelection.SelectAsync(
            4660, static (_, _) => ValueTask.FromResult(true), () => keys.Add("ctrl_a"), keyboard, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(selection.ByUiAutomation, Is.True);
            Assert.That(selection.DialogTitle, Is.Null);
            Assert.That(keys, Is.Empty);
        });
    }

    [Test]
    public async Task AFieldUiAutomationCannotSelectTakesTheKeysAndNoDialogIsNothingToSay()
    {
        var keyboard = new FakeDesktopKeyboard { WitnessBefore = Before, WitnessAfter = Before };
        var keys = new List<string>();

        FieldSelection selection = await FocusedFieldSelection.SelectAsync(
            4660, static (_, _) => ValueTask.FromResult(false), () => keys.Add("ctrl_a"), keyboard, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(selection.ByUiAutomation, Is.False);
            Assert.That(selection.DialogTitle, Is.Null);
            Assert.That(keys, Has.Count.EqualTo(1));
        });
    }

    [TestCase(true)]
    [TestCase(false)]
    public async Task ADialogTheFieldsLastResortRaisedIsClosedAndTold(bool closes)
    {
        var keyboard = new FakeDesktopKeyboard
        {
            WitnessBefore = Before,
            WitnessAfter = WithDialog,
            Raised = new RaisedWindow(5120, "Abrir"),
            ClosesRaised = closes,
            RaisesWithoutChord = true,
        };

        FieldSelection selection = await FocusedFieldSelection.SelectAsync(
            4660, static (_, _) => ValueTask.FromResult(false), static () => { }, keyboard, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(selection.DialogTitle, Is.EqualTo("Abrir"));
            Assert.That(selection.DialogClosed, Is.EqualTo(closes));
            Assert.That(keyboard.ClosedRaised, Is.EqualTo(new nint[] { 5120 }));
        });
    }

    // The worker's answer as the probe takes it: only a selection read back counts, and a worker still starting (or that
    // does not answer) is no selection, so the keys remain.
    [TestCase("""{"ok":true,"selected":true}""", true)]
    [TestCase("""{"ok":true,"selected":false,"why":"no_text_pattern"}""", false)]
    [TestCase("""{"ok":false,"error":"focus_not_found"}""", false)]
    [TestCase(null, false)]
    public async Task TheProbesSelectionIsTheOneTheWorkerReadBack(string? answer, bool selected)
    {
        var worker = new OneAnswerWorker(answer);
        var probe = new UiaClientInteractionProbe(worker);
        probe.Prewarm();

        bool said = await probe.SelectFocusedTextAsync(4660, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(said, Is.EqualTo(selected));
            JsonNode command = JsonNode.Parse(worker.Commands.Single())!;
            Assert.That(command["cmd"]!.GetValue<string>(), Is.EqualTo("focusselect"));
            Assert.That(command["hwnd"]!.GetValue<long>(), Is.EqualTo(4660));
        });
    }

    [Test]
    public void TheNewWindowsAreTheOnesTheWitnessBeforeDidNotShow() =>
        Assert.That(WindowWitness.NewWindows(Before, WithDialog), Is.EqualTo(new long[] { 5120 }));

    // Every Ctrl+A of the messaging flows goes through the one selection, so each clearing Backspace follows it.
    [Test]
    public void TheMessagingFlowsSelectOnlyThroughTheFieldSelection()
    {
        string source = Source("External", "DesktopMessagingAdapter.cs");
        string helper = source[source.IndexOf("private static async ValueTask SelectFocusedFieldAsync(", StringComparison.Ordinal)..];
        helper = helper[..helper.IndexOf("\n    }\n", StringComparison.Ordinal)];

        Assert.Multiple(() =>
        {
            Assert.That(Count(source, "SendChord(VirtualKeyControl, VirtualKeyA)"), Is.EqualTo(1));
            Assert.That(helper, Does.Contain("SendChord(VirtualKeyControl, VirtualKeyA)"));
            Assert.That(helper, Does.Contain("FocusedFieldSelection.SelectAsync("));
            Assert.That(Count(source, "await SelectFocusedFieldAsync("), Is.EqualTo(5), "the composer's read and four clears");
        });
    }

    [Test]
    public void TheWorkerAnswersTheFocusSelection()
    {
        string source = Source("External", "DesktopUiaWorker.ps1");

        Assert.Multiple(() =>
        {
            Assert.That(source, Does.Contain("elseif($cmd -eq 'focusselect'){ Send-Line (Do-FocusSelect $request) }"));
            Assert.That(source, Does.Contain("function Do-FocusSelect($request){"));
            Assert.That(source, Does.Contain("elseif($cmd -eq 'focusstate'){ Send-Line (Do-FocusState $request) }"));
            Assert.That(source, Does.Contain("function Do-FocusState($request){"));
        });
    }

    [TestCase("""{"ok":true,"inside":true,"innerWindow":"Ir a la línea","format":"400|None","place":"7|0|5"}""", "Ir a la línea", "400|None", "7|0|5")]
    [TestCase("""{"ok":true,"inside":true,"innerWindow":"","format":"","place":""}""", null, null, null)]
    public void TheFocusStateIsReadFromTheWorkersAnswer(string answer, string? inner, string? format, string? place)
    {
        using JsonDocument document = JsonDocument.Parse(answer);

        Assert.That(FocusState.Read(document), Is.EqualTo(new FocusState(inner, format, place)));
    }

    [Test]
    public void TheWorkerClosesADialogDrawnInsideTheWindowByItsCloseButton()
    {
        string source = Source("External", "DesktopUiaWorker.ps1");

        Assert.Multiple(() =>
        {
            Assert.That(source, Does.Contain("elseif($cmd -eq 'focusdialogclose'){ Send-Line (Do-FocusDialogClose $request) }"));
            string body = source[source.IndexOf("function Do-FocusDialogClose($request){", StringComparison.Ordinal)..];
            Assert.That(body[..body.IndexOf("WindowPattern", StringComparison.Ordinal)], Does.Contain("'CloseButton'"), "the button first");
        });
    }

    [TestCase("""{"ok":false,"error":"focus_not_found"}""")]
    [TestCase("""{"ok":true,"inside":false,"innerWindow":"Otra","format":"400"}""")]
    public void AFocusNotReadOrOutsideTheWindowIsNoState(string answer)
    {
        using JsonDocument document = JsonDocument.Parse(answer);

        Assert.That(FocusState.Read(document), Is.Null);
    }

    private static int Count(string source, string text) => source.Split(text).Length - 1;

    private static string Source(params string[] parts)
    {
        DirectoryInfo? root = new(AppContext.BaseDirectory);
        while (root is not null && !File.Exists(Path.Combine(root.FullName, "Baxy.slnx")))
            root = root.Parent;
        return File.ReadAllText(Path.Combine([root!.FullName, "src", "Baxy.Providers.Windows", .. parts]));
    }

    private sealed class OneAnswerWorker(string? answer) : IUiaWorker
    {
        internal List<string> Commands { get; } = [];

        public ValueTask<JsonDocument?> SendAsync(string commandJson, TimeSpan timeout, CancellationToken cancellationToken)
        {
            Commands.Add(commandJson);
            return ValueTask.FromResult(answer is null ? null : JsonDocument.Parse(answer));
        }
    }

    private sealed class NoProcessRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken) =>
            throw new AssertionException("a key press starts no process");
    }
}
