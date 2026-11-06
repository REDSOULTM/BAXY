using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// The keyboard's and the pointer's small traps found comparing with agent-desktop (tanda uso-108, its C and A rows):
/// a pair of surrogates cut in two, a text that cannot fit its budget, swapped mouse buttons, the keyboard not ready on a
/// window just brought up, a switch that flips back.
/// </summary>
[TestFixture]
internal sealed class KeysAndPointerInputTests
{
    private const string Emoji = "\U0001F600";

    // C14. agent-desktop never splits a pair at a chunk boundary (crates/windows/src/input/keyboard/keyboard_text.rs): an
    // interruption between the halves leaves a lone high surrogate in the person's text, a box on screen.
    [Test]
    public void TypingStopsBeforeOrAfterAPairNeverBetweenItsHalves()
    {
        var sent = new StringBuilder();
        int asked = 0;
        uint accepted = WindowsDesktopKeyboard.TypeUnits(
            "a" + Emoji + "b",
            () => ++asked <= 2,
            unit =>
            {
                sent.Append(unit);
                return 2;
            },
            () => { });

        Assert.Multiple(() =>
        {
            Assert.That(sent.ToString(), Is.EqualTo("a" + Emoji), "the second question lets the whole pair go");
            Assert.That(accepted, Is.EqualTo(6u));
            Assert.That(asked, Is.EqualTo(3), "asked once per character: a, the pair, b");
        });
    }

    // Contracase: a lone surrogate in the text is one unit of its own; plain letters are asked one by one.
    [Test]
    public void ALoneSurrogateAndPlainLettersAreAskedOneByOne()
    {
        var sent = new StringBuilder();
        int asked = 0;
        string text = "ab\uD83Dc";
        uint accepted = WindowsDesktopKeyboard.TypeUnits(
            text,
            () =>
            {
                asked++;
                return true;
            },
            unit =>
            {
                sent.Append(unit);
                return 2;
            },
            () => { });

        Assert.Multiple(() =>
        {
            Assert.That(sent.ToString(), Is.EqualTo(text));
            Assert.That(asked, Is.EqualTo(4));
            Assert.That(accepted, Is.EqualTo(8u));
        });
    }

    // C14 on the adapter: the characters it lets go are counted in units, so a text with a pair ends verified, and the
    // window that loses the front right after a pair leaves whole characters and an honest count.
    [Test]
    public async Task ATextWithAPairArrivesWholeAndItsCountIsInUnits()
    {
        var keyboard = new PairKeyboard();
        ExternalCapabilityReceipt receipt = await Adapter(keyboard).InvokeAsync(
            "input.text.type", Json($$"""{"text":"a{{Emoji}}b","window":18016}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(keyboard.Sent.ToString(), Is.EqualTo("a" + Emoji + "b"));
        });
    }

    [Test]
    public async Task AWindowLostRightAfterAPairStopsWithTheWholeCharacterIn()
    {
        var keyboard = new PairKeyboard { HoldsForQuestions = 3 };
        ExternalCapabilityReceipt receipt = await Adapter(keyboard).InvokeAsync(
            "input.text.type", Json($$"""{"text":"a{{Emoji}}b","window":18016}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_window_changed"));
            Assert.That(keyboard.Sent.ToString(), Is.EqualTo("a" + Emoji));
            Assert.That(receipt.Result?.GetProperty("charactersTyped").GetInt32(), Is.EqualTo(3));
        });
    }

    // Row A10. agent-desktop refuses before sending when the deadline cannot cover the text
    // (crates/windows/src/input/keyboard/keyboard_text.rs). At the keyboard's pace a text past the act's budget is known
    // to end half typed in the person's window before its first key.
    [Test]
    public async Task ATextThatCannotFitTheTypingBudgetIsRefusedBeforeItsFirstKey()
    {
        var keyboard = new FakeDesktopKeyboard();
        keyboard.Holding.Add(0x4660);
        string text = new('a', 3000);
        ExternalCapabilityReceipt receipt = await Adapter(keyboard).InvokeAsync(
            "input.text.type", Json($$"""{"text":"{{text}}","window":18016}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_text_too_long_to_type"));
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(keyboard.Texts, Is.Empty, "not one key");
            Assert.That(keyboard.Fronted, Is.Empty, "nor the front taken");
            Assert.That(
                receipt.Result?.GetProperty("charactersThatFit").GetInt32(),
                Is.EqualTo(WindowsDesktopInteractionAdapter.TypingBudgetMs / WindowsDesktopInteractionAdapter.TypedCharacterMs));
        });
    }

    // Contracase: a text that fits goes as before.
    [Test]
    public async Task ATextThatFitsIsTyped()
    {
        var keyboard = new FakeDesktopKeyboard();
        keyboard.Holding.Add(0x4660);
        string text = new('a', 1000);
        ExternalCapabilityReceipt receipt = await Adapter(keyboard).InvokeAsync(
            "input.text.type", Json($$"""{"text":"{{text}}","window":18016}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Not.EqualTo("input_text_too_long_to_type"));
            Assert.That(string.Concat(keyboard.Texts), Is.EqualTo(text));
        });
    }

    // Row C3. FlaUI's Mouse.cs swaps the button when SM_SWAPBUTTON is set; MOUSEEVENTF_LEFTDOWN names the physical button,
    // so on a left-handed mouse it arrives as a right click (docs of mouse_event and SwapMouseButton).
    [Test]
    public void SwappedButtonsPressThePhysicalRightToGiveALeftClick()
    {
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.LeftButtonEvents(swapped: true), Is.EqualTo((0x0008u, 0x0010u)));
            Assert.That(VisibleControlSurface.LeftButtonEvents(swapped: false), Is.EqualTo((0x0002u, 0x0004u)));
        });
    }

    [Test]
    public void ThePointerHelperAsksTheSameOfTheSwappedButtons()
    {
        string script = File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "DesktopKeyPress.ps1"));
        int start = script.IndexOf("@'", StringComparison.Ordinal);
        int end = script.IndexOf("'@", start, StringComparison.Ordinal);
        JsonElement answer = RunPowerShell(
            """
            Add-Type -TypeDefinition $env:BAXY_KEYS_SOURCE
            [Console]::Out.Write((ConvertTo-Json -Compress -InputObject @{
              swapped=@([BaxyKeyInput]::LeftButtonEvents($true) | ForEach-Object { [int]$_ })
              plain=@([BaxyKeyInput]::LeftButtonEvents($false) | ForEach-Object { [int]$_ })
            }))
            """,
            ("BAXY_KEYS_SOURCE", script[(start + 2)..end]));

        Assert.Multiple(() =>
        {
            Assert.That(answer.GetProperty("swapped").EnumerateArray().Select(item => item.GetInt32()), Is.EqualTo(new[] { 8, 0x10 }));
            Assert.That(answer.GetProperty("plain").EnumerateArray().Select(item => item.GetInt32()), Is.EqualTo(new[] { 2, 4 }));
        });
    }

    [Test]
    public void TheMediaClientsScriptAsksTheSameOfTheSwappedButtons()
    {
        string script = File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "SpotifyDesktopAutomation.ps1"));
        int start = script.IndexOf("$nativeSource=@'", StringComparison.Ordinal);
        int end = script.IndexOf("'@", start + 16, StringComparison.Ordinal);
        JsonElement answer = RunPowerShell(
            """
            Add-Type -TypeDefinition $env:BAXY_KEYS_SOURCE
            [Console]::Out.Write((ConvertTo-Json -Compress -InputObject @{
              swapped=@([BaxySpotifyNative]::LeftButtonEvents($true) | ForEach-Object { [int]$_ })
              plain=@([BaxySpotifyNative]::LeftButtonEvents($false) | ForEach-Object { [int]$_ })
            }))
            """,
            ("BAXY_KEYS_SOURCE", script[(start + 16)..end]));

        Assert.Multiple(() =>
        {
            Assert.That(answer.GetProperty("swapped").EnumerateArray().Select(item => item.GetInt32()), Is.EqualTo(new[] { 8, 0x10 }));
            Assert.That(answer.GetProperty("plain").EnumerateArray().Select(item => item.GetInt32()), Is.EqualTo(new[] { 2, 4 }));
        });
    }

    // A window of a higher level taking the front (measured 2026-11-05: a hidden window of GameInputSvc held it 80 minutes;
    // OpenProcess on it answers access denied): SendInput still counts the events and Windows drops them (MS docs of
    // SendInput: "neither GetLastError nor the return value will indicate the failure was caused by UIPI blocking"). The
    // provider refuses it before the act; this is the front that came between that check and the first key.
    [TestCase("input.key.press", """{"key":"enter"}""")]
    [TestCase("input.text.type", """{"text":"hola"}""")]
    public async Task AFrontAboveUsWhenTheKeysAreAboutToGoGetsNothing(string operation, string arguments)
    {
        var keyboard = new FakeDesktopKeyboard { FrontAbove = "window_elevation_unread" };
        ExternalCapabilityReceipt receipt = await Adapter(keyboard).InvokeAsync(operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("window_elevation_unread"));
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(keyboard.Chords, Is.Empty);
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // Contracase: an ordinary front gets its key.
    [Test]
    public async Task AFrontOfOurLevelGetsItsKey()
    {
        var keyboard = new FakeDesktopKeyboard();
        ExternalCapabilityReceipt receipt = await Adapter(keyboard).InvokeAsync(
            "input.key.press", Json("""{"key":"enter"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(keyboard.Chords, Has.Count.EqualTo(1));
        });
    }

    // A click of the pointer where it is: told «enviado» by the count of events, with the window under it or the front above
    // us. The window under the pointer can be ours while the front is not.
    [TestCase(1, 2, true, null, "window_elevated", TestName = "a pointer click over an elevated window")]
    [TestCase(1, 2, false, 2, "window_elevated", TestName = "a pointer click with an elevated window in front")]
    [TestCase(1, 2, false, null, null, TestName = "a pointer click with nothing above is not refused")]
    public void APointerClickIsRefusedAboveUs(int under, int front, bool underAbove, int? frontAbove, string? expected)
    {
        string? code = WindowsExternalCapabilityProvider.ElevatedActCode(
            "input.pointer.control",
            under,
            window => (int)window,
            process => (process == under && underAbove) || process == frontAbove,
            _ => true,
            front);
        Assert.That(code, Is.EqualTo(expected));
    }

    [Test]
    public void AKeyDoesNotAskForASecondWindow()
    {
        Assert.That(
            WindowsExternalCapabilityProvider.ElevatedActCode(
                "input.key.press", 1, window => (int)window, process => process == 2, _ => true, 2),
            Is.Null);
    }

    // Row C4: BAXY's own bench lost the first key on a window just brought up («125+75» arrived as «25+75»). Only the
    // mission's take waited for the keyboard: a burst for keys or a typed flow brought the window up and sent at once.
    [Test]
    public async Task ABurstForKeysWaitsForTheWindowItBroughtUpToTakeTheKeyboard()
    {
        var clock = new Clock { NowMs = 10_000 };
        long takesKeysAt = long.MaxValue;
        var desktop = new Desktop { OnBrought = () => takesKeysAt = clock.NowMs + 60 };
        desktop.TakesKeysWhen = () => clock.NowMs >= takesKeysAt;
        var lease = new ForegroundLease(new Pause(), clock, desktop, maxWaitMs: 8_000, watchMission: false);

        IInputBurst keys = await lease.AcquireForKeysAsync(Window, CancellationToken.None);
        bool keysReady = desktop.TakesKeysWhen();
        bool keysNotConfirmed = keys.KeysNotConfirmed;
        keys.Restore();

        desktop.Front = Person;
        takesKeysAt = long.MaxValue;
        IInputBurst flow = await lease.AcquireForFlowAsync(Window, CancellationToken.None);
        bool flowReady = desktop.TakesKeysWhen();
        flow.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(keysReady, Is.True, "the first key goes once the window takes the keyboard");
            Assert.That(keysNotConfirmed, Is.False);
            Assert.That(flowReady, Is.True, "a typed flow's too");
        });
    }

    [Test]
    public async Task TheWaitIsBoundedAndTheBurstSaysItRanOut()
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop { TakesKeysWhen = () => false };
        var lease = new ForegroundLease(new Pause(), clock, desktop, maxWaitMs: 8_000, watchMission: false);

        long before = clock.NowMs;
        IInputBurst keys = await lease.AcquireForKeysAsync(Window, CancellationToken.None);
        long waited = clock.NowMs - before;
        Assert.Multiple(() =>
        {
            Assert.That(waited, Is.InRange(ForegroundLease.KeysReadyCapMs, ForegroundLease.KeysReadyCapMs + 15));
            Assert.That(keys.MayAct, Is.True, "the act goes anyway, as it went before");
            Assert.That(keys.KeysNotConfirmed, Is.True);
        });
        keys.Restore();
    }

    // Contracases: a click's burst does not wait for a keyboard it does not use; a window already in front waits for
    // nothing; a mission's take that ran out is said by the burst its key goes in.
    [Test]
    public async Task APointerBurstAndAWindowAlreadyInFrontDoNotWait()
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop { TakesKeysWhen = () => false };
        var lease = new ForegroundLease(new Pause(), clock, desktop, maxWaitMs: 8_000, watchMission: false);

        IInputBurst pointer = await lease.AcquireAsync(Window, CancellationToken.None);
        long pointerAsked = desktop.KeysAsked;
        pointer.Restore();

        var inFront = new Desktop { Front = Window, TakesKeysWhen = () => true };
        var leaseInFront = new ForegroundLease(new Pause(), clock, inFront, maxWaitMs: 8_000, watchMission: false);
        long before = clock.NowMs;
        IInputBurst held = await leaseInFront.AcquireForKeysAsync(Window, CancellationToken.None);
        long heldWaited = clock.NowMs - before;
        held.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(pointerAsked, Is.Zero);
            Assert.That(heldWaited, Is.Zero);
            Assert.That(held.KeysNotConfirmed, Is.False);
        });
    }

    [Test]
    public async Task AMissionTakeThatRanOutIsSaidByTheBurstOfItsKey()
    {
        var clock = new Clock { NowMs = 10_000 };
        var desktop = new Desktop { TakesKeysWhen = () => false };
        var lease = new ForegroundLease(new Pause(), clock, desktop, maxWaitMs: 8_000, watchMission: false);

        Assert.That(await lease.TakeForMissionAsync(Window, CancellationToken.None), Is.Null);
        IInputBurst first = await lease.AcquireForKeysAsync(Window, CancellationToken.None);
        bool firstSays = first.KeysNotConfirmed;
        first.Restore();
        desktop.Front = Window;
        IInputBurst second = await lease.AcquireForKeysAsync(Window, CancellationToken.None);
        bool secondSays = second.KeysNotConfirmed;
        second.Restore();

        Assert.Multiple(() =>
        {
            Assert.That(firstSays, Is.True);
            Assert.That(secondSays, Is.False, "said once, by the first burst after the take");
        });
    }

    [Test]
    public async Task AKeyPressReceiptSaysTheKeyboardWasNotConfirmedOnlyWhenItRanOut()
    {
        var ranOut = new FakeDesktopKeyboard { BurstKeysNotConfirmed = true };
        ranOut.Holding.Add(0x4660);
        var ready = new FakeDesktopKeyboard();
        ready.Holding.Add(0x4660);
        JsonElement arguments = Json("""{"key":"enter","window":18016}""");

        ExternalCapabilityReceipt said = await Adapter(ranOut).InvokeAsync("input.key.press", arguments, CancellationToken.None);
        ExternalCapabilityReceipt plain = await Adapter(ready).InvokeAsync("input.key.press", arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(said.Verified, Is.True, said.ErrorCode);
            Assert.That(said.Result?.GetProperty("keysNotConfirmed").GetBoolean(), Is.True);
            Assert.That(plain.Verified, Is.True, plain.ErrorCode);
            Assert.That(plain.Result?.TryGetProperty("keysNotConfirmed", out _), Is.False);
        });
    }

    // Row C11. agent-desktop requires the new state to hold 200 ms inside a 600 ms window and a state that returns resets
    // the candidate (crates/windows/src/actions/toggle_state.rs): a switch that flips and flips back refused the change.
    [TestCase("On,On,On,On,On,On,On,On,On,On,On,On", true, TestName = "a state that holds counts as toggled")]
    [TestCase("On,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off", false, TestName = "a state that flips back does not")]
    [TestCase("On,Off,On,On,On,On,On,On,On,On,On,On,On,On", true, TestName = "a state that settles after a bounce does")]
    public void ASwitchCountsAsToggledOnlyWhenItsNewStateHolds(string states, bool expected)
    {
        JsonElement answer = RunWorker(
            """
            $script:States=@($env:BAXY_STATES -split ',')
            $script:At=0
            function Get-Toggle($el){ $state=$script:States[[math]::Min($script:At,$script:States.Count-1)]; $script:At++; return $state }
            [Console]::Out.Write((ConvertTo-Json -Compress -InputObject @([bool](Test-ToggleHeld $null 'Off'))))
            """,
            ["Test-ToggleHeld"],
            ("BAXY_STATES", states));
        Assert.That(answer[0].GetBoolean(), Is.EqualTo(expected));
    }

    private const nint Window = 0x4660;
    private const nint Person = 0x1111;

    private static WindowsDesktopInteractionAdapter Adapter(IDesktopKeyboard keyboard) =>
        new(new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard) { Ticks = static () => 1_000 };

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private static JsonElement RunWorker(string body, string[] wanted, params (string Name, string Value)[] more)
    {
        string names = string.Join(",", wanted.Select(name => "'" + name + "'"));
        return RunPowerShell(
            $$"""
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_WORKER_PATH,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            $wanted=@({{names}})
            $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $wanted -contains $node.Name },$true))
            if($found.Count -ne $wanted.Count){ throw 'worker functions missing' }
            foreach($definition in $found){ . ([scriptblock]::Create($definition.Extent.Text)) }

            """ + body,
            [("BAXY_WORKER_PATH", Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1")), .. more]);
    }

    private static JsonElement RunPowerShell(string body, params (string Name, string Value)[] variables)
    {
        string script = "$ErrorActionPreference='Stop'\n[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)\n" + body;
        var start = new ProcessStartInfo("powershell.exe")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand" })
            start.ArgumentList.Add(argument);
        start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes(script)));
        foreach ((string name, string value) in variables)
            start.Environment[name] = value;
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = ChildOutput.Read(process);
        Assert.That(process.WaitForExit(60_000), Is.True, "the script answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return JsonDocument.Parse(output).RootElement.Clone();
    }

    private sealed class NoProcessRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken) =>
            throw new AssertionException("keys and text start no process");
    }

    // The product's typing loop (TypeUnits) on a window in front, as the real keyboard runs it.
    private sealed class PairKeyboard : IDesktopKeyboard
    {
        internal StringBuilder Sent { get; } = new();

        // How many times the window still holds the front when asked (null: always).
        internal int? HoldsForQuestions { get; init; }

        private int _questions;

        public int InputSize => IntPtr.Size == 8 ? 40 : 28;

        public DesktopForeground Foreground() => new(Window, 4242, "ventana");

        public string ProcessName(nint window) => "programa";

        public uint PressChord(IReadOnlyList<ushort> virtualKeys, Func<bool> keepGoing) => 0;

        public uint TypeText(string text, Func<bool> keepGoing) =>
            WindowsDesktopKeyboard.TypeUnits(
                text,
                keepGoing,
                unit =>
                {
                    Sent.Append(unit);
                    return 2;
                },
                () => { });

        // Asked before the first key too (the adapter's own check): that one does not count as a question of the loop.
        public bool Holds(nint window)
        {
            _questions++;
            return HoldsForQuestions is not int limit || _questions <= limit + 1;
        }

        public ValueTask<IInputBurst> FrontAsync(nint window, CancellationToken cancellationToken) =>
            ValueTask.FromResult<IInputBurst>(new FakeInputBurst());

        public bool GiveFront(nint window) => true;

        public int LastError() => 0;

        public ValueTask SettleAsync(CancellationToken cancellationToken) => ValueTask.CompletedTask;
    }

    private sealed class Clock : ILeaseClock
    {
        public long NowMs { get; set; }

        public ValueTask DelayAsync(int milliseconds, CancellationToken cancellationToken)
        {
            NowMs += milliseconds;
            return ValueTask.CompletedTask;
        }
    }

    private sealed class Pause : IUserInputPause
    {
        public long LastForeignInputMs => 2_000;

        public long LastReachingInputMs => 2_000;

        public long OwnInputCount => 0;

        public bool HeldDown() => false;

        public bool TellsOwnInput => true;

        public string Source => "fake";
    }

    private sealed class Desktop : ILeaseDesktop
    {
        internal nint Front { get; set; } = Person;

        internal Action? OnBrought { get; init; }

        internal Func<bool>? TakesKeysWhen { get; set; }

        internal long KeysAsked { get; private set; }

        public nint Foreground() => Front;

        public bool Holds(nint window) => window == Front;

        public bool IsAlive(nint window) => true;

        public bool IsMinimized(nint window) => false;

        public nint WindowAbove(nint window) => 0;

        public (int X, int Y) Cursor() => default;

        public bool SetCursor(int x, int y) => true;

        public bool BringToFront(nint window)
        {
            Front = window;
            OnBrought?.Invoke();
            return true;
        }

        public bool TakesKeys(nint window)
        {
            KeysAsked++;
            return TakesKeysWhen?.Invoke() ?? true;
        }

        public void GiveFront(nint window) => Front = window;

        public void PlaceBelow(nint window, nint above)
        {
        }

        public void Minimize(nint window)
        {
        }
    }
}
