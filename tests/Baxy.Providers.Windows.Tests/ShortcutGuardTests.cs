using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo 100: a Ctrl+letter may run a command that sends the person's text out: an editor in Spanish binds Ctrl+F to a web
/// search (read by UI Automation: enabled with and without a selection). The find key does not go blind where the window can be
/// asked otherwise; whatever a shortcut opened in a browser is closed and said; and an undo only stands when it gave back exactly
/// what this key changed. Everything goes to fakes: nothing is pressed on the desktop.
/// </summary>
[TestFixture]
public sealed class ShortcutGuardTests
{
    private static readonly WindowWitness Before = new("nota.txt: Editor", true, "4660", 4660);
    private static readonly ushort[] Undo = [0x11, 0x5A];
    private static readonly ushort[] Redo = [0x11, 0x59];
    private static readonly ushort[] CloseTab = [0x11, 0x57];

    private static readonly BrowserWitness NoBrowser = new([], new HashSet<string>(), 4660);

    private sealed class NoProcessRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken) =>
            throw new AssertionException("keys start no process");
    }

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private static WindowsDesktopInteractionAdapter Adapter(FakeDesktopKeyboard keyboard, FakeViewedFields? fields = null) =>
        new(new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard, fields);

    private static ValueTask<ExternalCapabilityReceipt> Press(WindowsDesktopInteractionAdapter adapter, string key) =>
        adapter.InvokeAsync("input.key.press", Json($$"""{"key":"{{key}}","window":4660}"""), CancellationToken.None);

    private static FakeDesktopKeyboard Keyboard(params BrowserSighting[] sightings) => new()
    {
        WitnessBefore = Before,
        WitnessAfter = Before,
        BrowsersBefore = NoBrowser,
        Sightings = sightings,
    };

    // A window with its own menu (the find entry is pressed by its label), an editable document, or a selection, which the
    // key could send out: Ctrl+F does not go, in any of them, and the receipt says nothing happened and what can be done.
    [TestCase(true, false, 0)]
    [TestCase(false, true, 0)]
    [TestCase(false, false, 7)]
    public async Task TheFindKeyDoesNotGoBlindWhereTheWindowCanBeAskedOtherwise(bool menuBar, bool editable, int selected)
    {
        var keyboard = Keyboard();
        var fields = new FakeViewedFields("""{"ok":true}""") { Reach = new FindReach(menuBar, editable, selected) };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_f");

        Assert.Multiple(() =>
        {
            Assert.That(keyboard.Chords, Is.Empty, "no key at all");
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsDesktopInteractionAdapter.FindKeyNotSent));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            JsonElement result = receipt.Result!.Value;
            Assert.That(result.GetProperty("keySent").GetBoolean(), Is.False);
            Assert.That(result.GetProperty("selectedCharacters").GetInt32(), Is.EqualTo(selected));
            string next = result.GetProperty("next").GetString()!;
            Assert.That(next, Does.Contain("not sent").And.Contain("input_visible_controls").And.Contain("includeText"));
            Assert.That(next, Does.Not.Contain("menu").And.Not.Contain("web").And.Not.Contain("input_visible_click"),
                "measured: naming the menus or the web takes the model to the entry that sends the text out");
        });
    }

    // Contracase: a page or a chat's field with nothing selected, whose window has no menu of its own: the key is its way to
    // find, and its effect is watched as any shortcut's.
    [Test]
    public async Task TheFindKeyGoesWhereNothingElseAsksAndNothingIsSelected()
    {
        var keyboard = Keyboard();
        var fields = new FakeViewedFields("""{"ok":true}""") { Reach = new FindReach(false, false, 0) };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_f");

        Assert.Multiple(() =>
        {
            Assert.That(keyboard.Chords, Has.Count.EqualTo(1));
            Assert.That(receipt.ErrorCode, Is.Null);
        });
    }

    // Contracase: nothing answers: the key goes as before, and its effect is what is watched.
    [Test]
    public async Task TheFindKeyGoesWhenTheReadDoesNotAnswer()
    {
        var keyboard = Keyboard();
        var fields = new FakeViewedFields("""{"ok":true}""");

        await Press(Adapter(keyboard, fields), "ctrl_f");

        Assert.Multiple(() =>
        {
            Assert.That(fields.ReachReads, Is.EqualTo(1));
            Assert.That(keyboard.Chords, Has.Count.EqualTo(1));
        });
    }

    // Contracase: the read is for this key: the others take no extra read and no refusal.
    [TestCase("ctrl_s")]
    [TestCase("ctrl_h")]
    [TestCase("ctrl_l")]
    public async Task AnotherKeyIsNotHeldByTheFindRead(string key)
    {
        var keyboard = Keyboard();
        var fields = new FakeViewedFields("""{"ok":true}""") { Reach = new FindReach(true, true, 7) };

        await Press(Adapter(keyboard, fields), key);

        Assert.Multiple(() =>
        {
            Assert.That(fields.ReachReads, Is.Zero);
            Assert.That(keyboard.Chords, Has.Count.EqualTo(1));
        });
    }

    [Test]
    public async Task ABrowserWindowAShortcutOpenedIsClosedAndSaid()
    {
        var keyboard = Keyboard(new BrowserSighting(new BrowserOpened(7777, "palabra - Buscar", true), false, false));

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard), "ctrl_o");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsDesktopInteractionAdapter.ShortcutOpenedBrowser));
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(keyboard.ClosedRaised, Is.EqualTo(new nint[] { 7777 }));
            Assert.That(keyboard.GivenBack, Does.Contain((nint)0x1234));
            JsonElement opened = receipt.Result!.Value.GetProperty("browserOpened");
            Assert.That(opened.GetProperty("title").GetString(), Is.EqualTo("palabra - Buscar"));
            Assert.That(opened.GetProperty("closed").GetBoolean(), Is.True);
            Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Does.Contain("«palabra - Buscar»").And.Contain("closed again"));
        });
    }

    // A tab in the person's own browser: only that one goes (Ctrl+W to it, read by the tabs it shows: one less).
    [Test]
    public async Task ABrowserTabAShortcutOpenedIsClosedByItsKeyAndCounted()
    {
        var keyboard = Keyboard(new BrowserSighting(new BrowserOpened(7777, "palabra - Buscar", false), false, false));
        keyboard.Holding.Add(7777);
        var fields = new FakeViewedFields("""{"ok":true}""") { TabCounts = [5, 4] };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_o");

        Assert.Multiple(() =>
        {
            Assert.That(keyboard.Chords, Has.Count.EqualTo(2));
            Assert.That(keyboard.Chords[1], Is.EqualTo(CloseTab));
            Assert.That(keyboard.ClosedRaised, Is.Empty, "never the whole window: it holds the person's tabs");
            Assert.That(receipt.Result!.Value.GetProperty("browserOpened").GetProperty("closed").GetBoolean(), Is.True);
        });
    }

    [Test]
    public async Task ABrowserTabThatDidNotCloseIsSaidStillOpen()
    {
        var keyboard = Keyboard(new BrowserSighting(new BrowserOpened(7777, "palabra - Buscar", false), false, false));
        keyboard.Holding.Add(7777);
        var fields = new FakeViewedFields("""{"ok":true}""") { TabCounts = [5, 5] };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_o");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsDesktopInteractionAdapter.ShortcutOpenedBrowser));
            Assert.That(receipt.Result!.Value.GetProperty("browserOpened").GetProperty("closed").GetBoolean(), Is.False);
            Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Does.Contain("still open"));
        });
    }

    // The front may have left it, or its tabs may not be read: no key goes to a window that may be another's.
    [Test]
    public async Task NoKeyGoesToABrowserTabThatNoLongerHoldsTheFrontOrThatCannotBeCounted()
    {
        var keyboard = Keyboard(new BrowserSighting(new BrowserOpened(7777, "palabra - Buscar", false), false, false));
        var fields = new FakeViewedFields("""{"ok":true}""") { TabCounts = [5] };
        var unread = Keyboard(new BrowserSighting(new BrowserOpened(7777, "palabra - Buscar", false), false, false));
        unread.Holding.Add(7777);

        await Press(Adapter(keyboard, fields), "ctrl_o");
        ExternalCapabilityReceipt receipt = await Press(Adapter(unread, new FakeViewedFields("""{"ok":true}""")), "ctrl_o");

        Assert.Multiple(() =>
        {
            Assert.That(keyboard.Chords, Has.Count.EqualTo(1));
            Assert.That(unread.Chords, Has.Count.EqualTo(1));
            Assert.That(receipt.Result!.Value.GetProperty("browserOpened").GetProperty("closed").GetBoolean(), Is.False);
        });
    }

    // The person acted while it opened: it may be theirs. Said, and left alone.
    [Test]
    public async Task WhatOpenedWhileThePersonActedIsNotClosed()
    {
        var keyboard = new FakeDesktopKeyboard
        {
            WitnessBefore = Before,
            WitnessAfter = Before,
            BrowsersBefore = NoBrowser,
            Sightings = [new BrowserSighting(new BrowserOpened(7777, "palabra - Buscar", true), false, false)],
            PersonActsOnceSent = true,
        };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard), "ctrl_o");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsDesktopInteractionAdapter.ShortcutOpenedBrowser));
            Assert.That(keyboard.ClosedRaised, Is.Empty);
            Assert.That(receipt.Result!.Value.GetProperty("browserOpened").GetProperty("closed").GetBoolean(), Is.False);
        });
    }

    // A selection at the key's moment may have left in the address: closing does not take that back, and it is said.
    [Test]
    public async Task ASelectionHeldWhenTheBrowserOpenedIsSaidToMayHaveGoneOut()
    {
        var keyboard = Keyboard(new BrowserSighting(new BrowserOpened(7777, "palabra - Buscar", true), false, false));
        var fields = new FakeViewedFields("""{"ok":true}""") { FocusStates = [new FocusState(null, "400|None", "foco|3|7")] };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_o");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result!.Value.GetProperty("selectedCharacters").GetInt32(), Is.EqualTo(7));
            Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Does.Contain("7 selected characters").And.Contain("may have gone out"));
        });
    }

    // Measured live: with nothing selected the command still sent the word at the caret.
    [Test]
    public async Task WithNothingSelectedTheWordAtTheCaretIsSaidToMayHaveGoneOut()
    {
        var keyboard = Keyboard(new BrowserSighting(new BrowserOpened(7777, "palabra - Buscar", true), false, false));
        var fields = new FakeViewedFields("""{"ok":true}""") { FocusStates = [new FocusState(null, "400|None", "foco|3|0")] };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_o");

        Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Does.Contain("word at the caret").And.Contain("may have gone out"));
    }

    // Measured live: a format the person asked for, by the key named, was undone and the model pressed «redo» in a loop. Naming the
    // call instead left a save underlined. The receipt says the text is as it was, and names no call.
    [Test]
    public async Task AFormatUndoneSaysTheTextIsAsItWasAndNamesNoCall()
    {
        var keyboard = Keyboard();
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            FocusStates = [new FocusState(null, "400|None"), new FocusState(null, "400|Single"), new FocusState(null, "400|None")],
        };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_k");

        Assert.That(receipt.Result!.Value.GetProperty("next").GetString(),
            Does.Contain("as it was").And.Contain("was not done").And.Not.Contain("office_format_apply"));
    }

    // Measured: the same text with what changed tells «italic» asked by its key from a save that underlined.
    [TestCase("400|False|None|None|Left|0|0|12|Calibri|0", "400|True|None|None|Left|0|0|12|Calibri|0", "italic")]
    [TestCase("400|False|None|None|Left|0|0|12|Calibri|0", "400|False|Single|None|Left|0|0|12|Calibri|0", "underline")]
    [TestCase("400|False|None|None|Left|0|0|12|Calibri|0", "400|False|None|None|Center|0|0|12|Calibri|0", "alignment")]
    [TestCase("400|False|None|None|Left|0|0|12|Calibri|0", "700|True|None|None|Left|0|0|12|Calibri|0", "weight and italic")]
    [TestCase("400|None", "400|Single", "format")]
    public void WhatChangedIsReadFromTheAttributes(string before, string after, string changed) =>
        Assert.That(FocusState.FormatChange(before, after), Is.EqualTo(changed));

    [Test]
    public async Task TheFormatThatChangedIsNamedInTheReceipt()
    {
        var keyboard = Keyboard();
        const string Plain = "400|False|None|None|Left|0|0|12|Calibri|0";
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            FocusStates = [new FocusState(null, Plain), new FocusState(null, "400|True|None|None|Left|0|0|12|Calibri|0"), new FocusState(null, Plain)],
        };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_k");

        Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Does.Contain("changed the italic of the text"));
    }

    // A browser takes the front a moment before its new page names the window, and a cold one has no window at first.
    [Test]
    public async Task ABrowserOnItsWayIsWaitedFor()
    {
        var keyboard = Keyboard(
            new BrowserSighting(null, false, true),
            new BrowserSighting(null, true, false),
            new BrowserSighting(new BrowserOpened(7777, "palabra - Buscar", true), false, false));

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard), "ctrl_o");

        Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsDesktopInteractionAdapter.ShortcutOpenedBrowser));
    }

    // Contracase: the keys whose job moves the front or starts things are not this watch's.
    [TestCase("alt_tab")]
    [TestCase("ctrl_shift_escape")]
    public async Task TheKeysThatMoveTheFrontAreNotWatched(string key)
    {
        var keyboard = Keyboard(new BrowserSighting(new BrowserOpened(7777, "otra", true), false, false));

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard), key);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(keyboard.ClosedRaised, Is.Empty);
        });
    }

    private static BrowserWitness Browsers(long front, string[] running, params BrowserWindow[] windows) =>
        new(windows, new HashSet<string>(running), front);

    [Test]
    public void ANewBrowserWindowIsWhatTheKeyOpened()
    {
        BrowserSighting seen = BrowserWitness.Since(
            Browsers(4660, ["navegador"], new BrowserWindow(10, 50, "Mi página")),
            Browsers(4660, ["navegador"], new BrowserWindow(10, 50, "Mi página"), new BrowserWindow(20, 50, "palabra")),
            4242);

        Assert.That(seen.Opened, Is.EqualTo(new BrowserOpened(20, "palabra", true)));
    }

    [Test]
    public void AWindowThatTookTheFrontWithAnotherTitleHoldsANewTab()
    {
        BrowserSighting seen = BrowserWitness.Since(
            Browsers(4660, ["navegador"], new BrowserWindow(10, 50, "Mi página")),
            Browsers(10, ["navegador"], new BrowserWindow(10, 50, "palabra")),
            4242);

        Assert.That(seen.Opened, Is.EqualTo(new BrowserOpened(10, "palabra", false)));
    }

    // Behind the front a title alone proves nothing: a chat's tab counts unread messages in it by itself.
    [Test]
    public void ATitleThatChangedBehindTheFrontIsOnlyReported()
    {
        BrowserSighting seen = BrowserWitness.Since(
            Browsers(4660, ["navegador"], new BrowserWindow(10, 50, "Mi chat")),
            Browsers(4660, ["navegador"], new BrowserWindow(10, 50, "(3) Mi chat")),
            4242);

        Assert.Multiple(() =>
        {
            Assert.That(seen.Opened, Is.Null);
            Assert.That(seen.Retitled, Is.EqualTo(new[] { new BrowserWindow(10, 50, "(3) Mi chat") }));
        });
    }

    private static readonly BrowserWitness OneBrowserBehind = new([new BrowserWindow(10, 50, "Mi página")], new HashSet<string> { "navegador" }, 4660);

    private static FakeDesktopKeyboard KeyboardWithBrowserBehind() => new()
    {
        WitnessBefore = Before,
        WitnessAfter = Before,
        BrowsersBefore = OneBrowserBehind,
        Sightings = [new BrowserSighting(null, false, false, [new BrowserWindow(10, 50, "palabra - Buscar")])],
    };

    // Measured live with the browser already open: half a second after the key its window has one tab more and another title,
    // and the front never left. It is brought up only to close that tab, and given back.
    [Test]
    public async Task ATabOpenedBehindTheFrontIsToldByOneTabMoreAndClosed()
    {
        var keyboard = KeyboardWithBrowserBehind();
        keyboard.Holding.Add(10);
        var fields = new FakeViewedFields("""{"ok":true}""") { TabCounts = [3, 4, 4, 3] };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_o");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsDesktopInteractionAdapter.ShortcutOpenedBrowser));
            Assert.That(keyboard.Chords, Has.Count.EqualTo(2));
            Assert.That(keyboard.Chords[1], Is.EqualTo(CloseTab));
            Assert.That(keyboard.GivenBack, Is.EqualTo(new nint[] { 10, 0x1234 }), "up to close it, and back");
            Assert.That(receipt.Result!.Value.GetProperty("browserOpened").GetProperty("closed").GetBoolean(), Is.True);
        });
    }

    // The chat counting messages: its title changed in the second the key was watched, with the same tabs. Nothing of the key's.
    [Test]
    public async Task ATitleBehindTheFrontWithTheSameTabsClosesNothing()
    {
        var keyboard = KeyboardWithBrowserBehind();
        keyboard.Holding.Add(10);
        var fields = new FakeViewedFields("""{"ok":true}""") { TabCounts = [3, 3] };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_o");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(keyboard.Chords, Has.Count.EqualTo(1), "no Ctrl+W");
            Assert.That(keyboard.GivenBack, Is.Empty);
        });
    }

    // A window the front moved to and that did not close is given back too: the person's document goes on in front.
    [Test]
    public async Task TheFrontComesBackEvenIfTheTabDidNotClose()
    {
        var keyboard = KeyboardWithBrowserBehind();
        keyboard.Holding.Add(10);
        var fields = new FakeViewedFields("""{"ok":true}""") { TabCounts = [3, 4, 4, 4] };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_o");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result!.Value.GetProperty("browserOpened").GetProperty("closed").GetBoolean(), Is.False);
            Assert.That(keyboard.GivenBack, Is.EqualTo(new nint[] { 10, 0x1234 }));
        });
    }

    // The window the key went to may be a browser: its new tab is what Ctrl+T is for.
    [Test]
    public void TheProcessTheKeyWentToIsNotWatched()
    {
        BrowserSighting seen = BrowserWitness.Since(
            Browsers(10, ["navegador"], new BrowserWindow(10, 4242, "Mi página")),
            Browsers(10, ["navegador"], new BrowserWindow(10, 4242, "Nueva pestaña"), new BrowserWindow(20, 4242, "Otra")),
            4242);

        Assert.That(seen, Is.EqualTo(default(BrowserSighting)));
    }

    [Test]
    public void AWindowThatTookTheFrontWithItsTitleMayStillBeLoading()
    {
        BrowserSighting seen = BrowserWitness.Since(
            Browsers(4660, ["navegador"], new BrowserWindow(10, 50, "Mi página")),
            Browsers(10, ["navegador"], new BrowserWindow(10, 50, "Mi página")),
            4242);

        Assert.Multiple(() =>
        {
            Assert.That(seen.Opened, Is.Null);
            Assert.That(seen.FrontMoved, Is.True);
        });
    }

    [Test]
    public void ABrowserThatWasNotRunningIsStarting()
    {
        BrowserSighting seen = BrowserWitness.Since(Browsers(4660, []), Browsers(4660, ["navegador"]), 4242);

        Assert.That(seen.Starting, Is.True);
    }

    // A new process of a browser already running is one of its tabs' helpers: nothing to wait for.
    [Test]
    public void ABrowserAlreadyRunningIsNotStarting()
    {
        BrowserSighting seen = BrowserWitness.Since(Browsers(4660, ["navegador"]), Browsers(4660, ["navegador"]), 4242);

        Assert.That(seen.Starting, Is.False);
    }

    // Punto 3 del encargo: Ctrl+Z only for what this key just did. Measured in a word processor: the person's text stays, the format
    // comes back. Anything else, and the undo would be taking something of theirs.
    [Test]
    public async Task AnUndoThatGaveBackTheFormatAndTheTextStands()
    {
        var keyboard = Keyboard();
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            FocusStates =
            [
                new FocusState(null, "400|None", "foco|0|7", "60.1"),
                new FocusState(null, "400|Single", "foco|0|7", "60.1"),
                new FocusState(null, "400|None", "foco|0|7", "60.1"),
            ],
        };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_s");

        Assert.Multiple(() =>
        {
            Assert.That(keyboard.Chords, Has.Count.EqualTo(2));
            Assert.That(keyboard.Chords[1], Is.EqualTo(Undo));
            Assert.That(receipt.Result!.Value.GetProperty("formatUndone").GetBoolean(), Is.True);
        });
    }

    // The text changed along with the format: it was not this key alone (the person typed, or the command did more). The top
    // of the undo is not known to be this key's: no Ctrl+Z.
    [Test]
    public async Task AFormatThatCameWithAnotherTextGetsNoUndo()
    {
        var keyboard = Keyboard();
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            FocusStates =
            [
                new FocusState(null, "400|None", "foco|0|7", "60.1"),
                new FocusState(null, "400|Single", "foco|0|7", "68.2"),
            ],
        };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_s");

        Assert.Multiple(() =>
        {
            Assert.That(keyboard.Chords, Has.Count.EqualTo(1), "no Ctrl+Z");
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsDesktopInteractionAdapter.ShortcutChangedFormat));
            Assert.That(receipt.Result!.Value.GetProperty("formatUndone").GetBoolean(), Is.False);
        });
    }

    // A format with no undo of its own (a caret's pending format, in an editor that does not record it): the Ctrl+Z took the
    // person's last edit instead. The redo gives it back, and the format is said still changed.
    [Test]
    public async Task AnUndoThatTookAnotherEditIsRedone()
    {
        var keyboard = Keyboard();
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            FocusStates =
            [
                new FocusState(null, "400|None", "foco|60|0", "60.1"),
                new FocusState(null, "400|Single", "foco|60|0", "60.1"),
                new FocusState(null, "400|Single", "foco|53|0", "53.9"),
            ],
        };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_s");

        Assert.Multiple(() =>
        {
            Assert.That(keyboard.Chords, Has.Count.EqualTo(3));
            Assert.That(keyboard.Chords[1], Is.EqualTo(Undo));
            Assert.That(keyboard.Chords[2], Is.EqualTo(Redo));
            Assert.That(receipt.Result!.Value.GetProperty("formatUndone").GetBoolean(), Is.False);
            Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Does.Contain("still changed"));
        });
    }

    // Format back, but the text moved too: not what this key did alone. Redone as well.
    [Test]
    public async Task AnUndoThatGaveBackTheFormatButMovedTheTextIsRedone()
    {
        var keyboard = Keyboard();
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            FocusStates =
            [
                new FocusState(null, "400|None", "foco|0|7", "60.1"),
                new FocusState(null, "400|Single", "foco|0|7", "60.1"),
                new FocusState(null, "400|None", "foco|0|7", "53.9"),
            ],
        };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_s");

        Assert.Multiple(() =>
        {
            Assert.That(keyboard.Chords, Has.Count.EqualTo(3));
            Assert.That(keyboard.Chords[2], Is.EqualTo(Redo));
            Assert.That(receipt.Result!.Value.GetProperty("formatUndone").GetBoolean(), Is.False);
        });
    }

    // The person acted once the key went: the Ctrl+Z would land among their edits, so it does not go.
    [Test]
    public async Task NoUndoGoesOnceThePersonActed()
    {
        var keyboard = new FakeDesktopKeyboard { WitnessBefore = Before, WitnessAfter = Before, PersonActsOnceSent = true };
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            FocusStates =
            [
                new FocusState(null, "400|None", "foco|0|7", "60.1"),
                new FocusState(null, "400|Single", "foco|0|7", "60.1"),
            ],
        };

        ExternalCapabilityReceipt receipt = await Press(Adapter(keyboard, fields), "ctrl_s");

        Assert.Multiple(() =>
        {
            Assert.That(keyboard.Chords.Where(chord => chord.SequenceEqual(Undo)), Is.Empty);
            Assert.That(keyboard.Chords.Where(chord => chord.SequenceEqual(Redo)), Is.Empty);
            Assert.That(receipt.Result!.Value.GetProperty("formatUndone").GetBoolean(), Is.False);
        });
    }

    [TestCase("""{"ok":true,"menuBar":true,"editableDocument":false,"selected":7}""", true, false, 7)]
    [TestCase("""{"ok":true,"menuBar":false,"editableDocument":true,"selected":0}""", false, true, 0)]
    public void TheFindReachIsReadFromTheWorkersAnswer(string answer, bool menuBar, bool editable, int selected)
    {
        using JsonDocument document = JsonDocument.Parse(answer);

        Assert.That(FindReach.Read(document), Is.EqualTo(new FindReach(menuBar, editable, selected)));
    }

    [TestCase("""{"ok":false,"error":"focus_window_not_found"}""")]
    [TestCase("""{"ok":true}""")]
    public void AnAnswerWithoutTheFactsIsNoFindReach(string answer)
    {
        using JsonDocument document = JsonDocument.Parse(answer);

        Assert.That(FindReach.Read(document), Is.Null);
    }

    [TestCase("""{"ok":true,"tabs":4}""", 4)]
    [TestCase("""{"ok":false}""", null)]
    public void TheTabCountIsReadFromTheWorkersAnswer(string answer, int? tabs)
    {
        using JsonDocument document = JsonDocument.Parse(answer);

        Assert.That(FindReach.TabCount(document), Is.EqualTo(tabs));
    }

    [TestCase("foco|3|7", 7)]
    [TestCase("foco|0|0", 0)]
    [TestCase(null, 0)]
    public void TheSelectionsLengthIsTheLastPartOfThePlace(string? place, int selected) =>
        Assert.That(new FocusState(null, null, place).SelectedLength, Is.EqualTo(selected));

    [Test]
    public void TheWorkerAnswersTheFindReachAndTheTabCount()
    {
        string source = File.ReadAllText(Path.Combine(TestContext.CurrentContext.TestDirectory,
            "..", "..", "..", "..", "..", "src", "Baxy.Providers.Windows", "External", "DesktopUiaWorker.ps1"));

        Assert.Multiple(() =>
        {
            Assert.That(source, Does.Contain("elseif($cmd -eq 'focusfind'){ Send-Line (Do-FocusFind $request) }"));
            Assert.That(source, Does.Contain("function Do-FocusFind($request){"));
            Assert.That(source, Does.Contain("elseif($cmd -eq 'tabcount'){ Send-Line (Do-TabCount $request) }"));
            Assert.That(source, Does.Contain("function Do-TabCount($request){"));
            Assert.That(source, Does.Contain("content="), "the text's mark goes with the focus state");
        });
    }

    // No app names in what decides: registered browsers come from Windows, the find read from UI Automation.
    [Test]
    public void TheWitnessNamesNoBrowser()
    {
        string source = File.ReadAllText(Path.Combine(TestContext.CurrentContext.TestDirectory,
            "..", "..", "..", "..", "..", "src", "Baxy.Providers.Windows", "External", "BrowserWitness.cs"));

        Assert.That(source, Does.Not.Match("(?i)chrome|edge|opera|firefox|brave|bing|notepad"));
    }
}
