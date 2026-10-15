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
            Assert.That(receipt.Result?.GetProperty("foregroundTitleBefore").GetString(), Is.EqualTo("Documento - Editor"));
            Assert.That(receipt.Result?.GetProperty("foregroundProcessIdBefore").GetInt32(), Is.EqualTo(4242));
            Assert.That(receipt.Result?.GetProperty("action").GetString(), Is.EqualTo("key"));
        });
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

    // Safety review 2026-10-07: a mission's key goes to its window or nowhere. Goal v3 (point 0, fix 1): this is now
    // the keyboard path, taken only when no window message reaches the window's field (this adapter has no message
    // seam); the delivery without the front is pinned in TextDeliveryTests.
    [Test]
    public async Task AMissionKeyGoesOnlyToItsWindowBroughtToTheFront()
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
    public async Task AMissionWindowThatCannotBeFrontedGetsNothing()
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

    // Companion rule (GOAL_COMPUTER_USE_V3 point 0, fix 3): a mission's keys go inside a burst of the foreground
    // lease, after the person's pause, and the front is given back before the receipt, which says so.
    [Test]
    public async Task AMissionKeyGoesInABurstThatIsGivenBackAndReported()
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

    // Contracase: a key the person asked for in the window in front (no mission window) takes no burst.
    [Test]
    public async Task AKeyWithoutAMissionWindowTakesNoBurst()
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

    // Review of fable/cu-v3-rafaga: a key, a click or the wheel of the person while the mission's window held the
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
    // person stays still a mission's text goes whole in one burst; their input is what cuts it (the test above).
    [Test]
    public async Task ALongMissionTextGoesWholeInOneBurstWhileThePersonStaysStill()
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

    // Contracases: a text short enough for one burst, and a text without a mission window, go in one piece.
    [Test]
    public async Task AShortMissionTextOrATextWithoutAMissionWindowGoesInOnePiece()
    {
        var mission = new FakeDesktopKeyboard();
        var front = new FakeDesktopKeyboard();

        _ = await Keys(mission).InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":4660}"""), CancellationToken.None);
        _ = await Keys(front).InvokeAsync(
            "input.text.type", Json("""{"text":"abcdefghijklmnopqrst"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(mission.Texts, Is.EqualTo(new[] { "hola" }));
            Assert.That(mission.Fronted, Has.Count.EqualTo(1));
            Assert.That(front.Texts, Is.EqualTo(new[] { "abcdefghijklmnopqrst" }));
            Assert.That(front.Fronted, Is.Empty);
        });
    }

    // v3 point 0 review: the window was fronted, then lost the front before the press (an opened application's
    // hand-back guard, the person): the key goes nowhere instead of to the window in front.
    [Test]
    public async Task AMissionKeyIsNotSentWhenItsWindowLostTheFrontAfterBeingFronted()
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
    public async Task TypingStopsWhenTheMissionWindowLosesTheFront()
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
    public async Task AMissionTextWithALineBreakOrATabIsRefused(string text)
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
        var adapter = new WindowsVisibleControlAdapter(worker, null, null);

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
        var adapter = new WindowsVisibleControlAdapter(worker, null, null);

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
    public async Task ALookNeverFrontsTheOpenedApplicationAndABoundOneDoesNotLookForIt()
    {
        const long front = 0x7FFF_0F1E;
        string view =
            "{\"ok\":true,\"error\":\"\",\"hwnd\":" + front + ",\"window\":\"Inicio\",\"controls\":[" +
            "{\"i\":0,\"kind\":\"Button\",\"name\":\"Aceptar\",\"id\":\"4.2\",\"state\":\"\",\"value\":null," +
            "\"rect\":null,\"repeated\":0}],\"controlCount\":1,\"focused\":null}";
        var bound = new CountingFocus();
        var unbound = new CountingFocus();
        var browser = new FixedWindow(front);

        _ = await new WindowsVisibleControlAdapter(
                new ComputerUsePerceptionTests.ScriptedUiaWorker(view), null, null, bound, browserWindow: browser)
            .InvokeAsync("input.visible.controls", Json("""{"application":"el navegador","processId":4242}"""),
                CancellationToken.None);
        _ = await new WindowsVisibleControlAdapter(
                new ComputerUsePerceptionTests.ScriptedUiaWorker(view), null, null, unbound, browserWindow: browser)
            .InvokeAsync("input.visible.controls", Json("""{"application":"el navegador"}"""),
                CancellationToken.None);

        // v3 point 0: a look never brings a window to the front. The look bound to the mission's process does not
        // even look for the opened application; the unbound one finds it (to read it) and leaves it where it is.
        Assert.Multiple(() =>
        {
            Assert.That(bound.Located, Is.Zero);
            Assert.That(unbound.Located, Is.EqualTo(1));
            Assert.That(bound.Fronted, Is.Zero);
            Assert.That(unbound.Fronted, Is.Zero);
        });
    }

    [Test]
    public async Task ThePrewarmStartsTheWorkerAndTakesItsFirstLookAtTheShellWindowOutsideAnyTurn()
    {
        // Ronda 28: the prewarm used to start the worker only (no command) and the first whole look of the session
        // still cost 1 041–1 200 ms against 190–340 ms warm (banco Br27). It now asks the one read-only look that
        // pays that, of the shell's desktop window, with no operation invoked: nothing of it reaches a view.
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            """{"ok":true,"error":"","hwnd":4242,"window":"Program Manager","controls":[{"i":0,"kind":"List","name":"Desktop","id":"42.1","state":"","rect":[0,0,10,10]}],"controlCount":1}""");
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

        await host.PrewarmAsync(CancellationToken.None);

        Assert.That(host.ScriptExists, Is.False);
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
    // through the client-side providers it registers once at start, and says so. Nothing on the desktop is read.
    [Test]
    public async Task TheWorkerRegistersTheClientSideProvidersAndSaysSo()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        using var host = new UiaWorkerHost(worker);

        using JsonDocument? ping = await host.SendAsync("{\"cmd\":\"ping\"}", TimeSpan.FromSeconds(30), CancellationToken.None);

        Assert.That(ping?.RootElement.GetProperty("clientProviders").GetBoolean(), Is.True);
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
            "{\"i\":0,\"kind\":\"List\",\"name\":\"Canciones\",\"id\":\"7.1\",\"state\":\"\",\"value\":null," +
            "\"rect\":{\"x\":10,\"y\":10,\"w\":200,\"h\":300},\"repeated\":0}],\"controlCount\":1,\"focused\":null}");
        var controls = new WindowsVisibleControlAdapter(worker, null, null, browserWindow: new FixedWindow(front));
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

    // v3 point 0 review: a mission's scroll names its view's window; one Windows cannot bring to the front (here: one
    // that does not exist) gets no wheel, which would move whatever covers it.
    [Test]
    public async Task AMissionScrollWhoseWindowCannotBeFrontedMovesNothing()
    {
        ExternalCapabilityReceipt receipt = await new WindowsScrollAdapter().InvokeAsync(
            "input.scroll", Json("""{"direction":"down","amount":2,"window":4026531839}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_window_not_in_front"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
        });
    }

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

    private sealed class FixedWindow(long handle) : IUserBrowserWindowLocator
    {
        public nint FrontWindow() => (nint)handle;
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

    // The mission's window for a click: whether it is the one in front (the premise of the test; the adapter no
    // longer asks, v3 point 0: the click reaches the window by its handle either way).
    private sealed class MissionWindowFocus(bool frontable) : IOpenedApplicationFocus
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

    // v3 point 0 review: a mission's click names its view's window, and goes to that window only. Merge of round 1
    // (fable/cu-v3-clic over fable/cu-v3-vista): the click is not preceded by taking the front any more. The accessible
    // tree reaches the window behind the person's, and the pointer, the only way that needs the front, takes it inside
    // a burst of the foreground lease after the person's pause (ComputerUseClickMethodTests pins that path). Whether
    // the mission's window is in front or behind, the press goes to it and nothing is brought up for it.
    [TestCase(false)]
    [TestCase(true)]
    public async Task AMissionClickGoesToItsWindowWithoutTakingTheFront(bool inFront)
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(PendingClick, UnchangedControl);
        var focus = new MissionWindowFocus(frontable: inFront);
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
                "only the mission's window is read or pressed (a post-read reads the control just pressed)");
        });
    }

    [TestCase("0")]
    [TestCase("\"4660\"")]
    public async Task AMissionClickWithAnInvalidWindowIsRefused(string window)
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(PendingClick);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, new MissionWindowFocus(true), capture: NoCapture);

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
            worker, null, null, new MissionWindowFocus(true), capture: Capture);

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

    // Contracase: a click that did change the window is still verified by its surface.
    [Test]
    public async Task AClickThatChangedTheWindowIsVerifiedByItsSurface()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(PendingClick, UnchangedControl);
        int captures = 0;
        ValueTask<VisibleControlSurface.CapturedWindow?> Capture(nint window, bool? selfDrawn, CancellationToken token) =>
            ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
                new VisibleControlSurface.CapturedWindow(window, [], 0, 0, 10, 10, captures++ == 0 ? "before" : "after"));

        var adapter = new WindowsVisibleControlAdapter(
            worker, null, null, new MissionWindowFocus(true), capture: Capture);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Aceptar","window":4660}"""), CancellationToken.None);

        Assert.That(receipt.Verified, Is.True);
    }

    private static ValueTask<VisibleControlSurface.CapturedWindow?> NoCapture(
        nint window, bool? selfDrawn, CancellationToken cancellationToken) =>
        ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null);

    private sealed class CountingClickLocator : IVisibleControlLocator
    {
        internal int Calls { get; private set; }

        public string Stage => "ocr";

        public ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
            string operation,
            string label,
            CancellationToken cancellationToken)
        {
            Calls++;
            return ValueTask.FromResult<ExternalCapabilityReceipt?>(null);
        }
    }
}

/// <summary>A keyboard that records what it was asked to send and accepts every event (or the first few).</summary>
internal sealed class FakeDesktopKeyboard : IDesktopKeyboard
{
    internal DesktopForeground Front { get; init; } = new(0x1234, 4242, "Documento - Editor");

    internal int? AcceptOnly { get; init; }

    internal List<ushort[]> Chords { get; } = [];

    internal List<string> Texts { get; } = [];

    public int InputSize => IntPtr.Size == 8 ? 40 : 28;

    public uint PressChord(IReadOnlyList<ushort> virtualKeys)
    {
        Chords.Add(virtualKeys.ToArray());
        return Accept(virtualKeys.Count * 2);
    }

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
