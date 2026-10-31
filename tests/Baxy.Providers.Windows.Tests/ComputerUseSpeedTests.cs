using System.Runtime.InteropServices;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// The fast paths of the computer-use engine (documentacion/computer-use/MEDICIONES.md): keys and text sent from this
/// process, the click post-read asked while the window is compared, the view that does not front an opened
/// application twice, the worker started ahead of the first view and the scroll of a viewed control. Every effect
/// goes to a fake; nothing is pressed on the desktop.
/// </summary>
[TestFixture]
public sealed class ComputerUseSpeedTests
{
    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private static WindowsDesktopInteractionAdapter Keys(FakeDesktopKeyboard keyboard) =>
        new(new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard);

    // v2-s04 «en el Explorador de archivos andá a Descargas»: the folder window opened inside the shell's explorer.exe,
    // running for hours; that opening is no launch to wait 30 s on, nor a process family to search for the window.
    [TestCase(-2 * 3600, true, false)]
    [TestCase(-3, true, true)]
    [TestCase(-3, false, false)]
    public void OnlyAProcessStartedByTheOpeningIsALaunch(int startedSecondsAgo, bool launched, bool expected)
    {
        DateTime noted = new(2026, 10, 7, 4, 0, 0, DateTimeKind.Utc);

        Assert.That(
            VisibleControlSurface.LaunchedNow(noted.AddSeconds(startedSecondsAgo), noted, launched),
            Is.EqualTo(expected));
    }

    [TestCase("ctrl_shift_escape", new ushort[] { 0x11, 0x10, 0x1B })]
    [TestCase("ctrl_l", new ushort[] { 0x11, 0x4C })]
    [TestCase("alt_tab", new ushort[] { 0x12, 0x09 })]
    [TestCase("enter", new ushort[] { 0x0D })]
    [TestCase("win", new ushort[] { 0x5B })]
    [TestCase("ctrl_s", new ushort[] { 0x11, 0x53 })]
    [TestCase("ctrl_shift_s", new ushort[] { 0x11, 0x10, 0x53 })]
    [TestCase("ctrl_o", new ushort[] { 0x11, 0x4F })]
    [TestCase("ctrl_h", new ushort[] { 0x11, 0x48 })]
    [TestCase("ctrl_x", new ushort[] { 0x11, 0x58 })]
    [TestCase("f10", new ushort[] { 0x79 })]
    [TestCase("shift_f10", new ushort[] { 0x10, 0x79 })]
    // Holdout v5 V5E023: the end and the start of the whole text.
    [TestCase("ctrl_end", new ushort[] { 0x11, 0x23 })]
    [TestCase("ctrl_home", new ushort[] { 0x11, 0x24 })]
    public async Task EveryCatalogKeyIsTheSameChordTheScriptPressed(string key, ushort[] chord)
    {
        var keyboard = new FakeDesktopKeyboard();

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.key.press", Json($$"""{"key":"{{key}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(keyboard.Chords.Single(), Is.EqualTo(chord));
            Assert.That(receipt.Result?.GetProperty("expectedEvents").GetInt32(), Is.EqualTo(chord.Length * 2));
            Assert.That(receipt.Result?.GetProperty("sentTo").GetProperty("title").GetString(), Is.EqualTo("Documento - Editor"));
            Assert.That(receipt.Result?.GetProperty("sentTo").GetProperty("process").GetString(), Is.EqualTo("Editor"));
            Assert.That(receipt.Result?.GetProperty("foregroundProcessIdBefore").GetInt32(), Is.EqualTo(4242));
            Assert.That(receipt.Result?.GetProperty("action").GetString(), Is.EqualTo("key"));
        });
    }

    // An Enter that closes its dialog, or a text whose window closes as it ends: once sent there is no program left to
    // name, and the receipt names the one read before the first key.
    [TestCase("input.key.press", """{"key":"enter"}""")]
    [TestCase("input.text.type", """{"text":"hola"}""")]
    public async Task TheWindowTheKeysWereSentToIsNamedAsItWasBeforeThem(string operation, string arguments)
    {
        var keyboard = new FakeDesktopKeyboard
        {
            Front = new DesktopForeground(0x2222, 4242, "Guardar como"),
            FrontProcess = "Notepad",
            ProcessOnceSent = string.Empty,
        };

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(keyboard.ProcessName(0x2222), Is.Empty, "the window is gone once the keys went");
            Assert.That(receipt.Result?.GetProperty("sentTo").GetProperty("title").GetString(), Is.EqualTo("Guardar como"));
            Assert.That(receipt.Result?.GetProperty("sentTo").GetProperty("process").GetString(), Is.EqualTo("Notepad"));
        });
    }

    // Holdout v6 V6E024 («on the calculator, hit the C button», both seeds): «control» was pressed alone and the reply
    // said it was pressed, the display unchecked. A modifier alone says, beside its receipt, that it writes nothing and
    // how a window's button is pressed; another key, or the aids off, says nothing of it.
    [TestCase("all", "control", true)]
    [TestCase("all", "shift", true)]
    [TestCase("all", "ctrl_c", false)]
    [TestCase("none", "control", false)]
    public async Task AModifierPressedAloneSaysItWritesNothingAndHowAButtonIsPressed(string aids, string key, bool told)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        var keyboard = new FakeDesktopKeyboard();

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.key.press", Json($$"""{"key":"{{key}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("key").GetString(), Is.EqualTo(key), "the receipt stays");
            Assert.That(receipt.Result?.TryGetProperty("next", out _), Is.EqualTo(told));
            if (told)
                Assert.That(receipt.Result?.GetProperty("next").GetString(), Does.StartWith(key + " was pressed by itself")
                    .And.Contain("input_visible_click"));
        });
    }

    // Ajuste c3 (e2e E017: Ctrl+S «delivered» to Windows 11 Notepad 16 of 16 times, and no «Guardar como» opened): a
    // chord is held as a person holds it. Each key goes down in order with the keyboard's pace after it, so the last one
    // is still down, with the ones before it, when the window reads it; then all go up in reverse. Never four events at
    // once.
    [Test]
    public void AChordIsHeldTheKeyboardsPaceBeforeItIsReleased()
    {
        (uint accepted, string[] events) = Held([0x11, 0x53], goOn: 2);
        (uint single, string[] escape) = Held([0x1B], goOn: 1);

        Assert.Multiple(() =>
        {
            Assert.That(events, Is.EqualTo(new[] { "11 down", "pause", "53 down", "pause", "53 up", "11 up" }));
            Assert.That(accepted, Is.EqualTo(4u));
            Assert.That(escape, Is.EqualTo(new[] { "1B down", "pause", "1B up" }), "a single key is held too");
            Assert.That(single, Is.EqualTo(2u));
        });
    }

    // Review of this change (revisor de privacidad): held key by key, a chord is no longer one indivisible SendInput, so
    // each key goes down only while the window still holds the front and the person has not acted; what went down
    // always goes up, and the count says the chord was not whole.
    [Test]
    public void AChordStopsWhereTheWindowLostTheFrontAndReleasesWhatWentDown()
    {
        (uint accepted, string[] events) = Held([0x11, 0x53], goOn: 1);
        (uint none, string[] nothing) = Held([0x11, 0x53], goOn: 0);

        Assert.Multiple(() =>
        {
            Assert.That(events, Is.EqualTo(new[] { "11 down", "pause", "11 up" }));
            Assert.That(accepted, Is.EqualTo(2u));
            Assert.That(nothing, Is.Empty);
            Assert.That(none, Is.Zero);
        });
    }

    private static (uint Accepted, string[] Events) Held(ushort[] keys, int goOn)
    {
        var events = new List<string>();
        int asked = 0;
        uint accepted = WindowsDesktopKeyboard.HoldChord(
            keys,
            () => asked++ < goOn,
            (key, up) =>
            {
                events.Add($"{key:X2} {(up ? "up" : "down")}");
                return 1;
            },
            () => events.Add("pause"));
        return (accepted, [.. events]);
    }

    [Test]
    public async Task AKeyOutsideTheCatalogIsRefusedBeforeAnythingIsSent()
    {
        var keyboard = new FakeDesktopKeyboard();

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.key.press", Json("""{"key":"alt_f4"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("desktop_interaction_argument_invalid"));
            Assert.That(keyboard.Chords, Is.Empty);
        });
    }

    [Test]
    public async Task NoWindowInFrontMeansNothingIsSent()
    {
        var keyboard = new FakeDesktopKeyboard { Front = default };

        ExternalCapabilityReceipt key = await Keys(keyboard).InvokeAsync(
            "input.key.press", Json("""{"key":"enter"}"""), CancellationToken.None);
        ExternalCapabilityReceipt text = await Keys(keyboard).InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(key.ErrorCode, Is.EqualTo("key_press_sendinput_failed"));
            Assert.That(key.EffectMayHaveOccurred, Is.False);
            Assert.That(text.ErrorCode, Is.EqualTo("key_press_sendinput_failed"));
            Assert.That(keyboard.Chords, Is.Empty);
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    [Test]
    public async Task EventsWindowsDidNotAcceptLeaveAnUnverifiedEffect()
    {
        var keyboard = new FakeDesktopKeyboard { AcceptOnly = 3 };

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_effect_not_verified"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            // The keys went somewhere: the failure still names where.
            Assert.That(receipt.Result?.GetProperty("sentTo").GetProperty("title").GetString(), Is.EqualTo("Documento - Editor"));
            Assert.That(receipt.Result?.GetProperty("sentTo").GetProperty("process").GetString(), Is.EqualTo("Editor"));
        });
    }

    [Test]
    public async Task TextLongerThanTheTypingBoundIsRefused()
    {
        var keyboard = new FakeDesktopKeyboard();

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.text.type", Json("{\"text\":\"" + new string('a', 4097) + "\"}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("desktop_interaction_argument_invalid"));
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // Safety review 2026-10-07: a key for a named window goes to that window or nowhere. Goal v3 (point 0, fix 1): this
    // is now the keyboard path, taken only when no window message reaches the window's field (this adapter has no
    // message seam); the delivery without the front is pinned in TextDeliveryTests.
    [Test]
    public async Task ANamedWindowsKeyGoesOnlyToItBroughtToTheFront()
    {
        var keyboard = new FakeDesktopKeyboard();

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.key.press", Json("""{"key":"enter","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(keyboard.Fronted, Is.EqualTo(new nint[] { 4660 }));
            Assert.That(keyboard.Chords, Has.Count.EqualTo(1));
        });
    }

    [Test]
    public async Task ANamedWindowThatCannotBeFrontedGetsNothing()
    {
        var keyboard = new FakeDesktopKeyboard { Frontable = false };

        ExternalCapabilityReceipt key = await Keys(keyboard).InvokeAsync(
            "input.key.press", Json("""{"key":"enter","window":4660}"""), CancellationToken.None);
        ExternalCapabilityReceipt text = await Keys(keyboard).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(key.ErrorCode, Is.EqualTo("input_window_not_in_front"));
            Assert.That(key.EffectMayHaveOccurred, Is.False);
            Assert.That(text.ErrorCode, Is.EqualTo("input_window_not_in_front"));
            Assert.That(keyboard.Chords, Is.Empty);
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // Companion rule (GOAL_COMPUTER_USE_V3 point 0, fix 3): the keys for a named window go inside a burst of the
    // foreground lease, after the person's pause, and the front is given back before the receipt, which says so.
    [Test]
    public async Task ANamedWindowsKeyGoesInABurstThatIsGivenBackAndReported()
    {
        var keyboard = new FakeDesktopKeyboard { WaitedMs = 640 };

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.key.press", Json("""{"key":"enter","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(keyboard.Burst!.Restores, Is.GreaterThanOrEqualTo(1));
            Assert.That(receipt.Result?.GetProperty("waitedMs").GetInt64(), Is.EqualTo(640));
            Assert.That(receipt.Result?.GetProperty("restored").GetBoolean(), Is.True);
        });
    }

    // Contracase: a key the person asked for in the window in front (no named window) takes no burst.
    [Test]
    public async Task AKeyWithoutANamedWindowTakesNoBurst()
    {
        var keyboard = new FakeDesktopKeyboard();

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.key.press", Json("""{"key":"enter"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(keyboard.Burst, Is.Null);
            Assert.That(receipt.Result?.TryGetProperty("waitedMs", out _), Is.False);
        });
    }

    [Test]
    public async Task APersonWhoNeverPausesGetsNothingSentOverThem()
    {
        var keyboard = new FakeDesktopKeyboard { PauseRefusal = "input_user_not_paused", WaitedMs = 8000 };

        ExternalCapabilityReceipt key = await Keys(keyboard).InvokeAsync(
            "input.key.press", Json("""{"key":"enter","window":4660}"""), CancellationToken.None);
        ExternalCapabilityReceipt text = await Keys(keyboard).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(key.ErrorCode, Is.EqualTo("input_user_not_paused"));
            Assert.That(key.EffectMayHaveOccurred, Is.False);
            Assert.That(text.ErrorCode, Is.EqualTo("input_user_not_paused"));
            Assert.That(keyboard.Chords, Is.Empty);
            Assert.That(keyboard.Texts, Is.Empty);
            Assert.That(keyboard.Fronted, Is.Empty);
        });
    }

    // Review of fable/cu-v3-rafaga: a key, a click or the wheel of the person while the named window held the
    // front went into its field, mixed with the text; the text ends there, interrupted with its effect, never verified
    // (back to what it was before r4a M1 made it go on after the person's pause).
    [Test]
    public async Task TypingStopsAtThePersonsFirstInputAndGivesTheFrontBack()
    {
        var keyboard = new FakeDesktopKeyboard { PersonActsAfter = 4, PersonActsInBursts = 1 };

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.text.type", Json("""{"text":"hola mundo","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_user_interrupted"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(keyboard.Texts, Is.EqualTo(new[] { "hola" }));
            // FT/proveedores goal (review of receipts): how much went in, so a retry does not type it twice.
            Assert.That(receipt.Result?.GetProperty("charactersTyped").GetInt32(), Is.EqualTo(4));
            Assert.That(receipt.Result?.GetProperty("charactersAsked").GetInt32(), Is.EqualTo(10));
            Assert.That(keyboard.Fronted, Has.Count.EqualTo(1), "not brought up again over the person");
            Assert.That(keyboard.Burst!.Restores, Is.GreaterThanOrEqualTo(1));
        });
    }

    // r4a M1 (c6): a bare move of the person's mouse reaches no field; the front goes back to them at once and the
    // rest of the text waits for their next pause.
    [Test]
    public async Task TypingStopsAtThePersonsMouseMoveGivesTheFrontBackAndGoesOnAfterTheirPause()
    {
        var keyboard = new FakeDesktopKeyboard { PersonActsAfter = 4, PersonActsInBursts = 1, PersonOnlyMoves = true };

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.text.type", Json("""{"text":"hola mundo","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(keyboard.Texts, Is.EqualTo(new[] { "hola", " mundo" }));
            Assert.That(keyboard.Fronted, Has.Count.EqualTo(2));
            Assert.That(keyboard.EarlierRestoredAtFront, Is.EqualTo(new[] { true, true }),
                "the first burst is given back before the second is asked for");
            Assert.That(keyboard.Bursts.All(burst => burst.Restores >= 1), Is.True);
            Assert.That(receipt.Result?.GetProperty("pausesWaited").GetInt32(), Is.EqualTo(1));
        });
    }

    // FT/proveedores goal (review of receipts): Ctrl+C as a key press is done when the clipboard moved on (something
    // was copied), not by the count of keys Windows accepted; with nothing selected it says nothing was copied.
    [TestCase(true, true, null)]
    [TestCase(false, false, "clipboard_not_changed")]
    public async Task ACopyByKeyIsCheckedOnTheClipboard(bool copies, bool verified, string? error)
    {
        var keyboard = new FakeDesktopKeyboard { Clipboard = 7, CopyChanges = copies };

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.key.press", Json("""{"key":"ctrl_c","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.EqualTo(verified), receipt.ErrorCode);
            Assert.That(receipt.ErrorCode, Is.EqualTo(error));
        });
    }

    // Ajuste c3 (E017, live on the PC and the notebook): Ctrl+S to a Spanish Windows 11 Notepad, whose «Guardar» is Ctrl+G,
    // came back completed with nothing opened. A shortcut after which nothing of its window changed (title, enabled
    // state, its windows, the front) says so beside the delivery; one that opened a dialog says it changed; a key that is
    // no shortcut (Enter) is not watched.
    [TestCase("ctrl_s", null, false)]
    [TestCase("ctrl_s", "disabled", true)]
    [TestCase("ctrl_shift_s", "windows", true)]
    [TestCase("ctrl_w", "title", true)]
    [TestCase("enter", "title", null)]
    public async Task AShortcutSaysWhetherAnythingOfItsWindowChanged(string key, string? what, bool? changed)
    {
        var before = new WindowWitness("*lista: Bloc de notas", true, "4660", 4660);
        var keyboard = new FakeDesktopKeyboard
        {
            WitnessBefore = before,
            WitnessAfter = what switch
            {
                "disabled" => before with { Enabled = false },
                "windows" => before with { Windows = "4660,5120" },
                "title" => before with { Title = "lista.txt: Bloc de notas" },
                _ => before,
            },
        };

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.key.press", Json($$"""{"key":"{{key}}","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result!.Value.TryGetProperty("windowChanged", out JsonElement said)
                ? said.GetBoolean() : (bool?)null, Is.EqualTo(changed));
            Assert.That(receipt.Result!.Value.TryGetProperty("next", out JsonElement next)
                && next.GetString() == WindowsDesktopInteractionAdapter.ShortcutUnchanged, Is.EqualTo(changed == false));
        });
    }

    [Test]
    public async Task AKeyIsNotPressedWhenThePersonActedRightAfterThePause()
    {
        var keyboard = new FakeDesktopKeyboard { PersonActsAfter = 0 };

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.key.press", Json("""{"key":"enter","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_user_interrupted"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(keyboard.Chords, Is.Empty);
            Assert.That(keyboard.Burst!.Restores, Is.GreaterThanOrEqualTo(1));
        });
    }

    // r4a M1 (c6): the fixed bursts of 8 characters cut every keyboard text at its 8th character (the next burst was
    // asked for before the previous one gave the front back, and that restore took it from the next). While the
    // person stays still a text for a named window goes whole in one burst; their input is what cuts it (the test
    // above).
    [Test]
    public async Task ALongTextForANamedWindowGoesWholeInOneBurstWhileThePersonStaysStill()
    {
        var keyboard = new FakeDesktopKeyboard { WaitedMs = 100 };

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.text.type", Json("""{"text":"abcdefghijklmnopqrst","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(keyboard.Texts, Is.EqualTo(new[] { "abcdefghijklmnopqrst" }));
            Assert.That(keyboard.Fronted, Has.Count.EqualTo(1));
            Assert.That(keyboard.Bursts.All(burst => burst.Restores >= 1), Is.True);
            Assert.That(receipt.Result?.GetProperty("waitedMs").GetInt64(), Is.EqualTo(100));
            Assert.That(receipt.Result?.GetProperty("restored").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.TryGetProperty("pausesWaited", out _), Is.False);
        });
    }

    // Contracase: the person acted in the middle and then never paused: the rest is not sent over them.
    [Test]
    public async Task APersonWhoDoesNotPauseBetweenBurstsStopsTheTextThere()
    {
        var keyboard = new FakeDesktopKeyboard
        {
            PersonActsAfter = 8,
            PersonActsInBursts = 1,
            PersonOnlyMoves = true,
            RefusedFromFront = 2,
        };

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.text.type", Json("""{"text":"abcdefghijklmnopqrst","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_user_not_paused"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(keyboard.Texts, Is.EqualTo(new[] { "abcdefgh" }));
            Assert.That(keyboard.Bursts.All(burst => burst.Restores >= 1), Is.True);
        });
    }

    // Contracases: a text short enough for one burst, and a text without a named window, go in one piece.
    [Test]
    public async Task AShortTextForANamedWindowOrATextWithoutOneGoesInOnePiece()
    {
        var named = new FakeDesktopKeyboard();
        var front = new FakeDesktopKeyboard();

        _ = await Keys(named).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660}"""), CancellationToken.None);
        _ = await Keys(front).InvokeAsync(
            "input.text.type", Json("""{"text":"abcdefghijklmnopqrst"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(named.Texts, Is.EqualTo(new[] { "hola" }));
            Assert.That(named.Fronted, Has.Count.EqualTo(1));
            Assert.That(front.Texts, Is.EqualTo(new[] { "abcdefghijklmnopqrst" }));
            Assert.That(front.Fronted, Is.Empty);
        });
    }

    // v3 point 0 review: the window was fronted, then lost the front before the press (an opened application's
    // hand-back guard, the person): the key goes nowhere instead of to the window in front.
    [Test]
    public async Task ANamedWindowsKeyIsNotSentWhenItLostTheFrontAfterBeingFronted()
    {
        var keyboard = new FakeDesktopKeyboard { LosesFrontOnceFronted = true };

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.key.press", Json("""{"key":"enter","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_window_changed"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(keyboard.Chords, Is.Empty);
        });
    }

    [Test]
    public async Task TypingStopsWhenTheNamedWindowLosesTheFront()
    {
        var keyboard = new FakeDesktopKeyboard { LosesFrontAfter = 3 };

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.text.type", Json("""{"text":"hola mundo","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_window_changed"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(keyboard.Texts.Single(), Is.EqualTo("hol"));
        });
    }

    [Test]
    public async Task TypingStopsWhenTheRequestIsCancelled()
    {
        using var cancellation = new CancellationTokenSource();
        var keyboard = new FakeDesktopKeyboard { EachCharacter = typed => { if (typed == 2) cancellation.Cancel(); } };

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), cancellation.Token);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(keyboard.Texts.Single(), Is.EqualTo("ho"));
        });
    }

    [Test]
    public async Task AWholeTextIsNotVerifiedWhenAnotherProcessTookTheFrontMeanwhile()
    {
        var keyboard = new FakeDesktopKeyboard { ProcessAfterTyping = 777 };

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_window_changed"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
        });
    }

    [TestCase("hola\\nchau")]
    [TestCase("hola\\tchau")]
    public async Task ATextForANamedWindowWithALineBreakOrATabIsRefused(string text)
    {
        var keyboard = new FakeDesktopKeyboard();

        ExternalCapabilityReceipt receipt = await Keys(keyboard).InvokeAsync(
            "input.text.type", Json("{\"text\":\"" + text + "\",\"window\":4660}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("desktop_interaction_argument_invalid"));
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    [Test]
    public void TheNativeInputRecordHasItsNativeSize() =>
        Assert.That(new WindowsDesktopKeyboard().InputSize, Is.EqualTo(IntPtr.Size == 8 ? 40 : 28));

    [Test]
    public async Task APendingClickIsSettledByTheFirstPostreadThatSeesTheControlChange()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_pending\"," +
            "\"pending\":true,\"name\":\"Library\",\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false," +
            "\"selected\":false,\"toggled\":false}",
            "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_unchanged\"," +
            "\"name\":\"Library\",\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false,\"selected\":false}",
            "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Library\"," +
            "\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false,\"selected\":true,\"toggled\":false}");
        var adapter = new WindowsVisibleControlAdapter(worker, null, null)
        {
            WindowInFront = ComputerUsePerceptionTests.TestFront,
        };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Library"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("selected").GetBoolean(), Is.True);
            Assert.That(worker.Commands.Count(command => command.Contains("\"cmd\":\"postread\"", StringComparison.Ordinal)),
                Is.EqualTo(2));
        });
    }

    [Test]
    public async Task APostreadThatGoesUnansweredLeavesAnHonestClickReceipt()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_pending\"," +
            "\"pending\":true,\"name\":\"Aceptar\",\"controlIdentity\":\"1.2.3\"}");
        worker.FallSilentAfter = 1;
        var adapter = new WindowsVisibleControlAdapter(worker, null, null)
        {
            WindowInFront = ComputerUsePerceptionTests.TestFront,
        };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Aceptar"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.AnyOf("visible_click_postread_no_receipt", "active_window_not_found"));
            if (receipt.ErrorCode == "visible_click_postread_no_receipt")
            {
                Assert.That(receipt.EffectMayHaveOccurred, Is.True, "the control was invoked before the silence");
                Assert.That(worker.Commands.Count(command => command.Contains("\"cmd\":\"click\"", StringComparison.Ordinal)),
                    Is.EqualTo(1), "an invoked control is never pressed again");
            }
        });
    }

    [Test]
    public async Task ALookNeverFrontsTheOpenedApplication()
    {
        const long front = 0x7FFF_0F1E;
        string view =
            "{\"ok\":true,\"error\":\"\",\"hwnd\":" + front + ",\"window\":\"Inicio\",\"controls\":[" +
            "{\"kind\":\"Button\",\"name\":\"Aceptar\",\"id\":\"4.2\",\"state\":\"\",\"value\":null," +
            "\"rect\":null,\"repeated\":0}],\"controlCount\":1,\"focused\":null}";
        var focus = new CountingFocus();

        _ = await new WindowsVisibleControlAdapter(
                new ComputerUsePerceptionTests.ScriptedUiaWorker(view), null, null, focus, requestedWindow: (_, _) => ValueTask.FromResult((nint)front))
            .InvokeAsync("input.visible.controls", Json("""{"application":"el navegador"}"""),
                CancellationToken.None);

        // v3 point 0: a look never brings a window to the front. It finds the opened application (to read it) and
        // leaves it where it is.
        Assert.Multiple(() =>
        {
            Assert.That(focus.Located, Is.EqualTo(1));
            Assert.That(focus.Fronted, Is.Zero);
        });
    }

    [Test]
    public async Task ThePrewarmStartsTheWorkerAndTakesItsFirstLookAtTheShellWindowOutsideAnyTurn()
    {
        // Ronda 28: the prewarm used to start the worker only (no command) and the first whole look of the session
        // still cost 1 041–1 200 ms against 190–340 ms warm (banco Br27). It now asks the one read-only look that
        // pays that, of the shell's desktop window, with no operation invoked: nothing of it reaches a view.
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            """{"ok":true,"error":"","hwnd":4242,"window":"Program Manager","controls":[{"kind":"List","name":"Desktop","id":"42.1","state":"","rect":[0,0,10,10]}],"controlCount":1}""");
        var adapter = new WindowsVisibleControlAdapter(worker, null, null) { WarmupWindow = static () => 4242 };

        await adapter.PrewarmAsync();

        Assert.Multiple(() =>
        {
            Assert.That(worker.Prewarmed, Is.EqualTo(1));
            // One look and nothing else: no click, no focus, no field, no key; one control asked for.
            Assert.That(worker.Commands, Is.EqualTo(new[] { """{"cmd":"view","hwnd":4242,"limit":1}""" }));
            // Its answer is dropped: the adapter holds no view a later act could name.
            Assert.That(adapter.TryViewedControl(0, out _, out _, out _), Is.False);
        });
    }

    [Test]
    public async Task ThePrewarmLooksAtNothingWhenThereIsNoShellWindow()
    {
        // Contracase: a look without a window reads the one in front (the worker's Get-Root), which is the person's.
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker("""{"ok":true,"controls":[]}""");
        var adapter = new WindowsVisibleControlAdapter(worker, null, null) { WarmupWindow = static () => 0 };

        await adapter.PrewarmAsync();

        Assert.Multiple(() =>
        {
            Assert.That(worker.Prewarmed, Is.EqualTo(1));
            Assert.That(worker.Commands, Is.Empty);
        });
    }

    [Test]
    public void TheWarmupWindowIsTheShellsDesktopNeverTheOneInFront()
    {
        // The default seam: the shell's own desktop window (0 in a session without a desktop, as over SSH).
        var adapter = new WindowsVisibleControlAdapter(new ComputerUsePerceptionTests.ScriptedUiaWorker(), null, null);

        Assert.That(adapter.WarmupWindow(), Is.EqualTo(VisibleControlSurface.ShellWindow()));
    }

    [Test]
    public async Task AWorkerWithoutItsScriptPrewarmsToNothing()
    {
        using var host = new UiaWorkerHost(Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"), "missing.ps1"));

        Assert.DoesNotThrowAsync(async () => await host.PrewarmAsync(CancellationToken.None));
    }

    [Test]
    public async Task BrowserScriptsRunInOnePersistentWorkerWhoseExitEndsOnlyTheScript()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        using var host = new UiaWorkerHost(worker, "-DpiUnaware");
        var platform = new WindowsUserBrowserPlatform(host);
        const string script = """
            function Emit([bool]$ok, [string]$value) { [pscustomobject]@{ ok = $ok; value = $value } | ConvertTo-Json -Compress }
            if ($args[0] -eq 'early') { Emit $true ('early ' + $args[1]); exit 0 }
            Emit $true ('late ' + $args[0])
            """;

        using JsonDocument? first = await host.SendAsync(
            "{\"cmd\":\"script\",\"script\":" + JsonSerializer.Serialize(script) + ",\"args\":[\"early\",\"á\"]}",
            TimeSpan.FromSeconds(30), CancellationToken.None);
        var watch = System.Diagnostics.Stopwatch.StartNew();
        using JsonDocument? second = await host.SendAsync(
            "{\"cmd\":\"script\",\"script\":" + JsonSerializer.Serialize(script) + ",\"args\":[\"x\"]}",
            TimeSpan.FromSeconds(30), CancellationToken.None);
        long warm = watch.ElapsedMilliseconds;
        string? address = await platform.ReadAddressAsync(0, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first?.RootElement.GetProperty("line").GetString(), Does.Contain("early á"));
            Assert.That(second?.RootElement.GetProperty("line").GetString(), Does.Contain("late x"),
                "the worker outlives a script's exit");
            Assert.That(warm, Is.LessThan(1000), "a warm script call starts no PowerShell");
            Assert.That(address, Is.Null, "the address script answers «window missing» for no window");
        });
    }

    // Goal v3, analysis r3a M1: the worker reads the classic Win32 controls (combo boxes, trees, lists) as themselves,
    // through the client-side providers it registers once at start (without them, an opaque Pane). Only a combo box of
    // this test, off the screen, is read. The test waits on the thread that made the combo box: only that thread can
    // destroy it, and one left behind (owned by a test thread that pumps no messages) hangs a later GetWindowText.
    [Test]
    public void TheWorkerReadsAClassicComboBoxAsItself()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        nint combo = CreateWindowEx(0x08000080, "COMBOBOX", "", 0x90000003u, -31000, -31000, 120, 200, 0, 0, 0, 0);
        Assert.That(combo, Is.Not.Zero, $"CreateWindowEx failed: {Marshal.GetLastPInvokeError()}");
        try
        {
            using var host = new UiaWorkerHost(worker);
            const string probe = """
                $el=[System.Windows.Automation.AutomationElement]::FromHandle([IntPtr][long]$args[0])
                [pscustomobject]@{ ok=$true; value=[string]$el.Current.ControlType.ProgrammaticName } | ConvertTo-Json -Compress
                """;
            using JsonDocument? read = host.SendAsync(
                    "{\"cmd\":\"script\",\"script\":" + JsonSerializer.Serialize(probe) + ",\"args\":[\"" + (long)combo + "\"]}",
                    TimeSpan.FromSeconds(30), CancellationToken.None)
                .AsTask().GetAwaiter().GetResult();

            Assert.That(read?.RootElement.GetProperty("line").GetString(), Does.Contain("ControlType.ComboBox"));
        }
        finally
        {
            Assert.That(DestroyWindow(combo), Is.True, "the combo box is destroyed by the thread that made it");
        }
    }

    [Test]
    public async Task AScrollByIndexWithoutAViewIsRefusedBeforeAnyEffect()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker("{\"ok\":true,\"scrolled\":true}");
        var scroll = new WindowsScrollAdapter(new WindowsVisibleControlAdapter(worker, null, null));

        ExternalCapabilityReceipt receipt = await scroll.InvokeAsync(
            "input.scroll", Json("""{"direction":"down","amount":3,"index":4}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_control_identity_stale"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(worker.Commands, Is.Empty);
        });
    }

    [Test]
    public async Task AScrollByIndexOnAViewWhoseWindowIsGoneIsRefusedBeforeAnyEffect()
    {
        // The handle of a window that is gone: the view is answered by the scripted worker, the window is not alive.
        // A made-up constant is not enough (Full of 6d554a246 on redpc: 0x7FFF0F1E was a visible VS Code window there,
        // so the scroll went on to the pattern); a window this test creates and destroys has a handle Windows does not
        // hand out again (the slot comes back with another uniqueness).
        long front = GoneWindow();
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            "{\"ok\":true,\"error\":\"\",\"hwnd\":" + front + ",\"window\":\"Lista\",\"controls\":[" +
            "{\"kind\":\"List\",\"name\":\"Canciones\",\"id\":\"7.1\",\"state\":\"\",\"value\":null," +
            "\"rect\":{\"x\":10,\"y\":10,\"w\":200,\"h\":300},\"repeated\":0}],\"controlCount\":1,\"focused\":null}");
        var controls = new WindowsVisibleControlAdapter(worker, null, null, requestedWindow: (_, _) => ValueTask.FromResult((nint)front));
        _ = await controls.InvokeAsync(
            "input.visible.controls", Json("""{"application":"el navegador"}"""), CancellationToken.None);
        var scroll = new WindowsScrollAdapter(controls);

        ExternalCapabilityReceipt receipt = await scroll.InvokeAsync(
            "input.scroll", Json("""{"direction":"down","index":0}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.IsAlive((nint)front), Is.False, "the fixture's window is gone");
            Assert.That(controls.TryViewedControl(0, out nint window, out string id, out _), Is.True);
            Assert.That((long)window, Is.EqualTo(front));
            Assert.That(id, Is.EqualTo("7.1"));
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_control_identity_stale"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(worker.Commands.Any(command => command.Contains("\"cmd\":\"scroll\"", StringComparison.Ordinal)),
                Is.False);
        });
    }

    // Renew al máximo (B-CU-3): a turn cancelled while the worker said its hello left that hello in the pipe, and every
    // later command read the answer of the one before it (a click taken as invalid though it was pressed, the cascade
    // pressing again). A worker of this test answers its hello late and echoes each command's number.
    [Test]
    public void ACancelDuringTheWorkersHelloNeverLeavesItsAnswerForTheNextCommand()
    {
        string script = Path.Combine(Path.GetTempPath(), "baxy-slow-hello-" + Guid.NewGuid().ToString("N") + ".ps1");
        File.WriteAllText(script, """
            while($true){
              $line=[Console]::In.ReadLine(); if($null -eq $line){ break }
              $command=$line | ConvertFrom-Json
              if($command.cmd -eq 'exit'){ break }
              if($command.cmd -eq 'ping'){ Start-Sleep -Milliseconds 1500; [Console]::Out.WriteLine('{"ok":true,"hello":true}') }
              else { [Console]::Out.WriteLine('{"ok":true,"n":' + $command.n + '}') }
              [Console]::Out.Flush()
            }
            """);
        try
        {
            using var host = new UiaWorkerHost(script);
            using var cancelled = new CancellationTokenSource(TimeSpan.FromMilliseconds(400));
            Assert.That(async () => await host.SendAsync("{\"cmd\":\"view\",\"n\":1}", TimeSpan.FromSeconds(30), cancelled.Token),
                Throws.InstanceOf<OperationCanceledException>());

            using JsonDocument? second = host.SendAsync("{\"cmd\":\"view\",\"n\":2}", TimeSpan.FromSeconds(30), CancellationToken.None)
                .AsTask().GetAwaiter().GetResult();

            Assert.That(second?.RootElement.TryGetProperty("n", out JsonElement n) == true ? n.GetInt32() : -1, Is.EqualTo(2),
                second?.RootElement.GetRawText());
        }
        finally
        {
            File.Delete(script);
        }
    }

    // Renew al máximo (B-CU-1): an index of the last look, of window B, with the scroll naming window A is B's control,
    // never A's: refused before any effect, as input.text.type refuses it (B may be the person's window). Synchronous,
    // so the windows are destroyed by the thread that made them; while it waits for each call that thread answers the
    // messages sent to its windows (reading a window's title sends WM_GETTEXT to its thread: blocked, it hung the run).
    [Test]
    public void AScrollByIndexOfAnotherWindowsViewIsRefusedBeforeAnyEffect()
    {
        nint viewed = CreateWindowEx(0x08000080, "STATIC", "BAXY scroll fixture viewed", 0x90000000u, -31000, -31000, 200, 120, 0, 0, 0, 0);
        nint named = CreateWindowEx(0x08000080, "STATIC", "BAXY scroll fixture named", 0x90000000u, -31000, -31000, 200, 120, 0, 0, 0, 0);
        Assert.That(viewed != 0 && named != 0, Is.True, $"CreateWindowEx failed: {Marshal.GetLastPInvokeError()}");
        try
        {
            var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
                "{\"ok\":true,\"error\":\"\",\"hwnd\":" + (long)viewed + ",\"window\":\"Lista\",\"controls\":[" +
                "{\"kind\":\"List\",\"name\":\"Canciones\",\"id\":\"7.1\",\"state\":\"\",\"value\":null," +
                "\"rect\":{\"x\":10,\"y\":10,\"w\":200,\"h\":300},\"repeated\":0}],\"controlCount\":1,\"focused\":null}");
            var controls = new WindowsVisibleControlAdapter(worker, null, null, requestedWindow: (_, _) => ValueTask.FromResult(viewed));
            _ = Pumped(() => controls.InvokeAsync("input.visible.controls", Json("""{"application":"la lista"}"""),
                CancellationToken.None).AsTask());
            int looked = worker.Commands.Count;
            var scroll = new WindowsScrollAdapter(controls);

            ExternalCapabilityReceipt receipt = Pumped(() => scroll.InvokeAsync(
                "input.scroll", Json("{\"direction\":\"down\",\"index\":0,\"window\":" + (long)named + "}"),
                CancellationToken.None).AsTask());

            Assert.Multiple(() =>
            {
                Assert.That(receipt.ErrorCode, Is.EqualTo("visible_control_identity_stale"));
                Assert.That(receipt.EffectMayHaveOccurred, Is.False);
                Assert.That(worker.Commands.Skip(looked), Is.Empty, string.Join(" | ", worker.Commands));
            });
        }
        finally
        {
            _ = DestroyWindow(viewed);
            _ = DestroyWindow(named);
        }
    }

    [TestCase("""{"direction":"down","index":"cuatro"}""")]
    [TestCase("""{"direction":"down","index":1.5}""")]
    [TestCase("""{"direction":"sideways","index":1}""")]
    [TestCase("""{"direction":"down","window":0}""")]
    [TestCase("""{"direction":"down","window":"ventana"}""")]
    public async Task AScrollWithAnInvalidIndexOrDirectionIsRefused(string arguments)
    {
        ExternalCapabilityReceipt receipt = await new WindowsScrollAdapter().InvokeAsync(
            "input.scroll", Json(arguments), CancellationToken.None);

        Assert.That(receipt.ErrorCode, Is.EqualTo("scroll_argument_invalid"));
    }

    // v3 point 0 review: a scroll names its view's window; one Windows cannot bring to the front (here: one
    // that does not exist) gets no wheel, which would move whatever covers it. Renew al máximo (w8): one that does not
    // exist is said gone (input_window_not_found), never «not in front».
    [Test]
    public async Task AScrollWhoseNamedWindowCannotBeFrontedMovesNothing()
    {
        ExternalCapabilityReceipt receipt = await new WindowsScrollAdapter().InvokeAsync(
            "input.scroll", Json("""{"direction":"down","amount":2,"window":4026531839}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_window_not_found"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
        });
    }

    // A call run elsewhere while this thread answers what is sent to the windows it made, until the call ends.
    internal static T Pumped<T>(Func<Task<T>> call)
    {
        Task<T> running = Task.Run(call);
        while (!running.Wait(10))
        {
            while (PeekMessage(out PumpedMessage message, 0, 0, 0, 1))
            {
                _ = TranslateMessage(message);
                _ = DispatchMessage(message);
            }
        }

        return running.GetAwaiter().GetResult();
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct PumpedMessage
    {
        public nint Window;
        public uint Message;
        public nint WParam;
        public nint LParam;
        public uint Time;
        public int X;
        public int Y;
    }

    [DllImport("user32.dll", EntryPoint = "PeekMessageW", ExactSpelling = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool PeekMessage(out PumpedMessage message, nint window, uint first, uint last, uint remove);

    [DllImport("user32.dll", ExactSpelling = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool TranslateMessage(in PumpedMessage message);

    [DllImport("user32.dll", EntryPoint = "DispatchMessageW", ExactSpelling = true)]
    private static extern nint DispatchMessage(in PumpedMessage message);

    private static long GoneWindow()
    {
        nint window = CreateWindowEx(0x08000080, "STATIC", "BAXY gone window fixture", 0u,
            0, 0, 10, 10, 0, 0, 0, 0);
        Assert.That(window, Is.Not.Zero, $"CreateWindowEx failed: {Marshal.GetLastPInvokeError()}");
        Assert.That(DestroyWindow(window), Is.True);
        return window;
    }

    [DllImport("user32.dll", EntryPoint = "CreateWindowExW",
        CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
    private static extern nint CreateWindowEx(uint extendedStyle, string className,
        string title, uint style, int x, int y, int width, int height,
        nint parent, nint menu, nint instance, nint parameter);

    [DllImport("user32.dll", ExactSpelling = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool DestroyWindow(nint window);

    private sealed class NoProcessRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken) =>
            throw new AssertionException("keys and text start no process");
    }

    private sealed class CountingFocus : IOpenedApplicationFocus
    {
        internal int Fronted { get; private set; }

        internal int Located { get; private set; }

        public VisibleControlSurface.OpenedApplication? TakeOpened() => null;

        public VisibleControlSurface.OpenedApplication? PeekOpened() =>
            new VisibleControlSurface.OpenedApplication(4242, DateTime.UtcNow, DateTime.UtcNow, Launched: true);

        public ValueTask<VisibleControlSurface.OpenedSurface> FrontAsync(
            VisibleControlSurface.OpenedApplication opened,
            bool judgeDrawn,
            CancellationToken cancellationToken,
            bool bringToFront = false)
        {
            Located++;
            if (bringToFront)
                Fronted++;
            return ValueTask.FromResult(default(VisibleControlSurface.OpenedSurface));
        }
    }

    // The named window for a click: whether it is the one in front (the premise of the test; the adapter no
    // longer asks, v3 point 0: the click reaches the window by its handle either way).
    private sealed class NamedWindowFocus(bool frontable) : IOpenedApplicationFocus
    {
        internal bool Frontable => frontable;

        public VisibleControlSurface.OpenedApplication? TakeOpened() => null;

        public VisibleControlSurface.OpenedApplication? PeekOpened() => null;

        public ValueTask<VisibleControlSurface.OpenedSurface> FrontAsync(
            VisibleControlSurface.OpenedApplication opened,
            bool judgeDrawn,
            CancellationToken cancellationToken,
            bool bringToFront = false) => ValueTask.FromResult(default(VisibleControlSurface.OpenedSurface));
    }

    private const string PendingClick =
        "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_pending\"," +
        "\"pending\":true,\"name\":\"Aceptar\",\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false," +
        "\"selected\":false,\"toggled\":false}";

    private const string UnchangedControl =
        "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_unchanged\"," +
        "\"name\":\"Aceptar\",\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false,\"selected\":false}";

    // v3 point 0 review: a click names its view's window, and goes to that window only. Merge of round 1
    // (fable/cu-v3-clic over fable/cu-v3-vista): the click is not preceded by taking the front any more. The accessible
    // tree reaches the window behind the person's, and the pointer, the only way that needs the front, takes it inside
    // a burst of the foreground lease after the person's pause (ComputerUseClickMethodTests pins that path). Whether
    // the named window is in front or behind, the press goes to it and nothing is brought up for it.
    [TestCase(false)]
    [TestCase(true)]
    public async Task ANamedWindowsClickGoesToItWithoutTakingTheFront(bool inFront)
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(PendingClick, UnchangedControl);
        var focus = new NamedWindowFocus(frontable: inFront);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, focus, capture: NoCapture);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Aceptar","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Not.EqualTo("input_window_not_in_front"));
            Assert.That(worker.Commands[0], Does.Contain("\"cmd\":\"click\"").And.Contain("\"hwnd\":4660"));
            Assert.That(
                worker.Commands.Where(command => !command.Contains("\"cmd\":\"postread\"", StringComparison.Ordinal)),
                Has.All.Contain("\"hwnd\":4660"),
                "only the named window is read or pressed (a post-read reads the control just pressed)");
        });
    }

    [TestCase("0")]
    [TestCase("\"4660\"")]
    public async Task AClickNamingAnInvalidWindowIsRefused(string window)
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(PendingClick);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, new NamedWindowFocus(true), capture: NoCapture);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("{\"label\":\"Aceptar\",\"window\":" + window + "}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_click_argument_invalid"));
            Assert.That(worker.Commands, Is.Empty);
        });
    }

    // v3 point 0 review: the image before a click was taken with the window covered (its own drawing) and the ones
    // after it with the window in front (the screen): the two ways differ on a window the click did not change, and
    // the click read as «surface changed». Every image after is taken the way the one before was.
    [Test]
    public async Task AClickThatChangedNothingIsNotVerifiedByADifferentWayOfCapturing()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(PendingClick, UnchangedControl);
        var asked = new List<bool?>();
        ValueTask<VisibleControlSurface.CapturedWindow?> Capture(nint window, bool? selfDrawn, CancellationToken token)
        {
            asked.Add(selfDrawn);
            // The first image: the window drew itself (it was covered). The same window copied from the screen differs.
            bool drawsItself = selfDrawn ?? true;
            string hash = drawsItself ? "own-drawing" : "screen-copy";
            return ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
                new VisibleControlSurface.CapturedWindow(window, [], 0, 0, 10, 10, hash) { SelfDrawn = drawsItself });
        }

        var adapter = new WindowsVisibleControlAdapter(
            worker, null, null, new NamedWindowFocus(true), capture: Capture);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Aceptar","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_postread_unchanged"));
            Assert.That(asked[0], Is.Null, "the image before chooses its way");
            Assert.That(asked.Skip(1), Is.Not.Empty.And.All.EqualTo(true), "the images after follow it");
        });
    }

    // Contracase: a click that did change the window is still verified by its surface (the three images before it, taken to
    // tell a window that changes by itself, are the same).
    [Test]
    public async Task AClickThatChangedTheWindowIsVerifiedByItsSurface()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(PendingClick, UnchangedControl);
        int captures = 0;
        ValueTask<VisibleControlSurface.CapturedWindow?> Capture(nint window, bool? selfDrawn, CancellationToken token) =>
            ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
                new VisibleControlSurface.CapturedWindow(window, [], 0, 0, 10, 10, captures++ < 3 ? "before" : "after"));

        var adapter = new WindowsVisibleControlAdapter(
            worker, null, null, new NamedWindowFocus(true), capture: Capture);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Aceptar","window":4660}"""), CancellationToken.None);

        Assert.That(receipt.Verified, Is.True);
    }

    private static ValueTask<VisibleControlSurface.CapturedWindow?> NoCapture(
        nint window, bool? selfDrawn, CancellationToken cancellationToken) =>
        ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null);
}

/// <summary>A keyboard that records what it was asked to send and accepts every event (or the first few).</summary>
internal sealed class FakeDesktopKeyboard : IDesktopKeyboard
{
    internal DesktopForeground Front { get; init; } = new(0x1234, 4242, "Documento - Editor");

    // The program a view names the window in front by.
    internal string FrontProcess { get; init; } = "Editor";

    // The program named once a key or a text was sent (null: FrontProcess still); a key that closes its window leaves
    // none to name.
    internal string? ProcessOnceSent { get; init; }

    public string ProcessName(nint window) =>
        Chords.Count + Texts.Count > 0 && ProcessOnceSent is string after ? after : FrontProcess;

    internal int? AcceptOnly { get; init; }

    internal List<ushort[]> Chords { get; } = [];

    internal List<string> Texts { get; } = [];

    public int InputSize => IntPtr.Size == 8 ? 40 : 28;

    public uint PressChord(IReadOnlyList<ushort> virtualKeys, Func<bool> keepGoing)
    {
        // As the real keyboard: a key goes down only while keepGoing holds before it.
        int pressed = 0;
        while (pressed < virtualKeys.Count && keepGoing())
            pressed++;
        if (pressed < virtualKeys.Count)
        {
            Chords.Add([.. virtualKeys.Take(pressed)]);
            return Accept(pressed * 2);
        }

        Chords.Add(virtualKeys.ToArray());
        if (CopyChanges && virtualKeys.Contains((ushort)0x43))
            Clipboard++;
        return Accept(virtualKeys.Count * 2);
    }

    // The clipboard's sequence (0: not known, as before); whether a Ctrl+C moves it (something was selected).
    internal uint Clipboard { get; set; }

    internal bool CopyChanges { get; init; }

    public uint ClipboardSequence() => Clipboard;

    // Ajuste c3 (E017): what a shortcut can change of the window, before any key and once one was sent (null: not read).
    internal WindowWitness? WitnessBefore { get; init; }

    internal WindowWitness? WitnessAfter { get; init; }

    public WindowWitness? Witness(nint window) => Chords.Count == 0 ? WitnessBefore : WitnessAfter;

    // The windows that hold the front, by handle; a window brought to the front holds it when Frontable says so.
    internal HashSet<nint> Holding { get; } = [];

    internal bool Frontable { get; init; } = true;

    internal List<nint> Fronted { get; } = [];

    // The windows the front was handed back to (the person's), outside any lease.
    internal List<nint> GivenBack { get; } = [];

    // The person's pause, as the foreground lease reports it: refused when the person never paused.
    internal string? PauseRefusal { get; init; }

    internal long WaitedMs { get; init; }

    // Characters typed before the person touches the keyboard or the mouse (null: never).
    internal int? PersonActsAfter { get; init; }

    // The bursts (counted from 1) in which the person acts after PersonActsAfter characters; later ones they leave be.
    internal int PersonActsInBursts { get; init; } = int.MaxValue;

    // Whether the person's input is a bare move of the mouse (it reaches no field).
    internal bool PersonOnlyMoves { get; init; }

    // Whether every earlier burst was already given back when each burst was asked for, in order.
    internal List<bool> EarlierRestoredAtFront { get; } = [];

    internal FakeInputBurst? Burst { get; private set; }

    // Every burst taken, in order.
    internal List<FakeInputBurst> Bursts { get; } = [];

    // From this call of FrontAsync on (counted from 1), the person does not pause: the burst is refused.
    internal int? RefusedFromFront { get; init; }

    // Characters typed before the window loses the front (null: it never does).
    internal int? LosesFrontAfter { get; init; }

    // The foreground process once the text is typed (null: the same as before).
    internal int? ProcessAfterTyping { get; init; }

    // Called with the characters typed so far, before each one.
    internal Action<int>? EachCharacter { get; init; }

    // Called with each character once it was sent (keepGoing let it go), in order.
    internal Action<char>? EachSent { get; init; }

    private bool _typed;

    // The window in front from now on, when something moved it (null: Front, as typing left it).
    internal DesktopForeground? Now { get; set; }

    // The window loses the front right after it was brought there, before anything is sent (the front handed back
    // by someone else in between).
    internal bool LosesFrontOnceFronted { get; init; }

    public DesktopForeground Foreground()
    {
        if (LosesFrontOnceFronted && Fronted.Count > 0)
            Holding.Clear();
        return Now ?? (_typed && ProcessAfterTyping is int after ? Front with { ProcessId = after } : Front);
    }

    public uint TypeText(string text, Func<bool> keepGoing)
    {
        int typed = 0;
        foreach (char _ in text)
        {
            EachCharacter?.Invoke(typed);
            if (LosesFrontAfter is int limit && typed >= limit)
                Holding.Clear();
            if (PersonActsAfter is int acts && typed >= acts && Burst is not null && Bursts.Count <= PersonActsInBursts)
            {
                Burst.UserActed = true;
                Burst.OnlyMoved = PersonOnlyMoves;
            }
            if (!keepGoing())
                break;
            EachSent?.Invoke(text[typed]);
            typed++;
        }

        Texts.Add(text[..typed]);
        _typed = true;
        return Accept(typed * 2);
    }

    public bool Holds(nint window) => Holding.Contains(window);

    public ValueTask<IInputBurst> FrontAsync(nint window, CancellationToken cancellationToken)
    {
        EarlierRestoredAtFront.Add(Bursts.All(burst => burst.Restores > 0));
        string? refused = PauseRefusal
            ?? (RefusedFromFront is int from && Bursts.Count + 1 >= from ? "input_user_not_paused" : null);
        if (refused is string refusal)
        {
            Burst = new FakeInputBurst { Refusal = refusal, WaitedMs = WaitedMs };
            Bursts.Add(Burst);
            return ValueTask.FromResult<IInputBurst>(Burst);
        }

        Fronted.Add(window);
        if (Frontable)
            Holding.Add(window);
        Burst = new FakeInputBurst
        {
            Refusal = Holds(window) ? null : "input_window_not_in_front",
            WaitedMs = WaitedMs,
            UserActed = PersonActsAfter == 0 && Bursts.Count < PersonActsInBursts,
        };
        Bursts.Add(Burst);
        return ValueTask.FromResult<IInputBurst>(Burst);
    }

    public bool GiveFront(nint window)
    {
        GivenBack.Add(window);
        return Frontable;
    }

    public int LastError() => 0;

    public ValueTask SettleAsync(CancellationToken cancellationToken) => ValueTask.CompletedTask;

    private uint Accept(int events) => (uint)Math.Min(events, AcceptOnly ?? events);
}

/// <summary>A burst of the foreground lease that records its restorations.</summary>
internal sealed class FakeInputBurst : IInputBurst
{
    public string? Refusal { get; init; }

    public long WaitedMs { get; init; }

    public bool UserActed { get; set; }

    // The person's input was a bare move of the mouse.
    public bool OnlyMoved { get; set; }

    public bool UserReached => UserActed && !OnlyMoved;

    public bool HoldsWindow { get; set; } = true;

    internal int Restores { get; private set; }

    public bool Restore()
    {
        Restores++;
        return true;
    }
}
