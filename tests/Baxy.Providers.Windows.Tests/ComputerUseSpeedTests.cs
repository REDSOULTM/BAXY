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

    // Safety review 2026-10-07: a mission's key goes to its window or nowhere.
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
    public async Task AViewBoundToTheMissionsProcessDoesNotFrontTheOpenedApplicationFirst()
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

        Assert.Multiple(() =>
        {
            Assert.That(bound.Fronted, Is.Zero);
            Assert.That(unbound.Fronted, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task ThePrewarmStartsTheWorkerAheadOfTheFirstView()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker();
        var adapter = new WindowsVisibleControlAdapter(worker, null, null);

        await adapter.PrewarmAsync();

        Assert.Multiple(() =>
        {
            Assert.That(worker.Prewarmed, Is.EqualTo(1));
            Assert.That(worker.Commands, Is.Empty);
        });
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
        // A handle no window has: the view is answered by the scripted worker, the window is not alive.
        const long front = 0x7FFF_0F1E;
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
    public async Task AScrollWithAnInvalidIndexOrDirectionIsRefused(string arguments)
    {
        ExternalCapabilityReceipt receipt = await new WindowsScrollAdapter().InvokeAsync(
            "input.scroll", Json(arguments), CancellationToken.None);

        Assert.That(receipt.ErrorCode, Is.EqualTo("scroll_argument_invalid"));
    }

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

        public VisibleControlSurface.OpenedApplication? TakeOpened() => null;

        public VisibleControlSurface.OpenedApplication? PeekOpened() =>
            new VisibleControlSurface.OpenedApplication(4242, DateTime.UtcNow, DateTime.UtcNow, Launched: true);

        public ValueTask<VisibleControlSurface.OpenedSurface> FrontAsync(
            VisibleControlSurface.OpenedApplication opened,
            bool judgeDrawn,
            CancellationToken cancellationToken)
        {
            Fronted++;
            return ValueTask.FromResult(default(VisibleControlSurface.OpenedSurface));
        }

        public bool Holds(nint window) => true;
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

    // Characters typed before the window loses the front (null: it never does).
    internal int? LosesFrontAfter { get; init; }

    // The foreground process once the text is typed (null: the same as before).
    internal int? ProcessAfterTyping { get; init; }

    // Called with the characters typed so far, before each one.
    internal Action<int>? EachCharacter { get; init; }

    private bool _typed;

    public DesktopForeground Foreground() =>
        _typed && ProcessAfterTyping is int after ? Front with { ProcessId = after } : Front;

    public uint TypeText(string text, Func<bool> keepGoing)
    {
        int typed = 0;
        foreach (char _ in text)
        {
            EachCharacter?.Invoke(typed);
            if (LosesFrontAfter is int limit && typed >= limit)
                Holding.Clear();
            if (!keepGoing())
                break;
            typed++;
        }

        Texts.Add(text[..typed]);
        _typed = true;
        return Accept(typed * 2);
    }

    public bool Holds(nint window) => Holding.Contains(window);

    public ValueTask<bool> FrontAsync(nint window, CancellationToken cancellationToken)
    {
        Fronted.Add(window);
        if (Frontable)
            Holding.Add(window);
        return ValueTask.FromResult(Holds(window));
    }

    public int LastError() => 0;

    public ValueTask SettleAsync(CancellationToken cancellationToken) => ValueTask.CompletedTask;

    private uint Accept(int events) => (uint)Math.Min(events, AcceptOnly ?? events);
}
