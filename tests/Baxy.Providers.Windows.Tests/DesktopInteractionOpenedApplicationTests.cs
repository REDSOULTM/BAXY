using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// FT/proveedores goal (E6): a keyboard act with no window (a key, a text, a select-all, a copy, a paste) right after
/// app.open opened an application that is no longer in front goes to that application's window as if it named it: the
/// mission lease brings it up after the person's pause or refuses with nothing sent, and the receipt says the window
/// came from the opened application (<c>windowFrom</c>). Measured: the Notepad opened and verified, Steam back in front,
/// and the text and the select-all went to Steam.
/// </summary>
[TestFixture]
public sealed class DesktopInteractionOpenedApplicationTests
{
    private const long Opened = 555;
    private const long Steam = 999;

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private static OpenedApplicationKeyboard Keyboard(Opening focus, long front) => new(
        focus,
        () => (nint)front,
        (window, _) => window == (nint)Opened,
        window => window == (nint)Opened ? "Sin título: Bloc de notas" : "Steam");

    [TestCase("input.text.type", """{"text":"hola"}""")]
    [TestCase("input.key.press", """{"key":"enter"}""")]
    public async Task AKeyboardActWithNoWindowGoesToTheOpenedApplicationWhenAnotherIsInFront(
        string operation, string arguments)
    {
        var focus = new Opening();
        var lease = new TakingLease();
        var adapter = new RecordingAdapter(operation, lease);
        using var provider = new WindowsExternalCapabilityProvider(
            [adapter], lease, null, Keyboard(focus, Steam));

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(lease.Taken, Is.EqualTo(new nint[] { (nint)Opened }), "the lease is asked for the opened window");
            Assert.That(adapter.Window, Is.EqualTo(Opened), "the act names the opened window");
            Assert.That(receipt.Result?.GetProperty("windowFrom").GetString(), Is.EqualTo("opened_application"));
            Assert.That(receipt.Result?.GetProperty("openedWindow").GetInt64(), Is.EqualTo(Opened));
            Assert.That(receipt.Result?.GetProperty("openedWindowTitle").GetString(),
                Is.EqualTo("Sin título: Bloc de notas"));
            Assert.That(receipt.Result?.GetProperty("ok").GetBoolean(), Is.True, "the adapter's own receipt is kept");
            Assert.That(focus.Takes, Is.Zero, "peeked, never taken: the click right after still finds the opening");
        });
    }

    // The product's adapter on the keyboard path: the text goes to the opened window, brought up, never to Steam.
    [Test]
    public async Task ATextWithNoWindowIsTypedInTheOpenedWindowBroughtUp()
    {
        var keyboard = new FakeDesktopKeyboard();
        var lease = new TakingLease();
        using var provider = new WindowsExternalCapabilityProvider(
            [Adapter(keyboard)], lease, null, Keyboard(new Opening(), Steam));

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        // Review of E6: a text sent to the opened application is read back like one with no window (F004); with nothing
        // to read it back with here, it is honestly unverified, never verified on the keys Windows accepted.
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_text_not_read_back"));
            Assert.That(lease.Taken, Is.EqualTo(new nint[] { (nint)Opened }));
            Assert.That(keyboard.Fronted, Is.EqualTo(new nint[] { (nint)Opened }), "typed bound to the opened window");
            Assert.That(keyboard.Texts, Is.EqualTo(new[] { "hola" }));
            Assert.That(receipt.Result?.GetProperty("windowFrom").GetString(), Is.EqualTo("opened_application"));
        });
    }

    // No opening, or one gone stale: the window in front, as before; nothing is asked of the lease.
    [Test]
    public async Task WithNoFreshOpeningTheActGoesToTheFrontAsBefore()
    {
        var focus = new Opening { Fresh = false };
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.text.type", lease);
        using var provider = new WindowsExternalCapabilityProvider(
            [adapter], lease, null, Keyboard(focus, Steam));

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(lease.Taken, Is.Empty);
            Assert.That(adapter.Window, Is.Null, "no window added");
            Assert.That(receipt.Result?.TryGetProperty("windowFrom", out _), Is.False);
            Assert.That(focus.Fronts, Is.Zero);
        });
    }

    // The opened application already in front (one of its windows): the path of an act with no window, unchanged.
    [Test]
    public async Task AnOpenedApplicationAlreadyInFrontChangesNothing()
    {
        var focus = new Opening();
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.select.all", lease);
        using var provider = new WindowsExternalCapabilityProvider(
            [adapter], lease, null, Keyboard(focus, Opened));

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "input.select.all", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(lease.Taken, Is.Empty);
            Assert.That(adapter.Window, Is.Null);
            Assert.That(receipt.Result?.TryGetProperty("windowFrom", out _), Is.False);
        });
    }

    // An opened application with no usable window (closed, or only a splash): the front, as before.
    [Test]
    public async Task AnOpenedApplicationWithNoWindowChangesNothing()
    {
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.text.type", lease);
        using var provider = new WindowsExternalCapabilityProvider(
            [adapter], lease, null, Keyboard(new Opening { Window = 0 }, Steam));

        _ = await provider.InvokeAsync("input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(lease.Taken, Is.Empty);
            Assert.That(adapter.Window, Is.Null);
        });
    }

    // FT/proveedores goal (E6): the opened application minimized (no usable window, only its minimized one): the act goes
    // to that window, which the lease brings up (restoring it), not to the front.
    [Test]
    public async Task AMinimizedOpenedApplicationGetsTheActThroughTheLease()
    {
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.text.type", lease);
        using var provider = new WindowsExternalCapabilityProvider(
            [adapter], lease, null, Keyboard(new Opening { Window = 0, Minimized = Opened }, Steam));

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(lease.Taken, Is.EqualTo(new nint[] { (nint)Opened }), "the lease restores the minimized window");
            Assert.That(adapter.Window, Is.EqualTo(Opened));
        });
    }

    // The opened window cannot be brought up (the person does not pause, or Windows does not give it the front): no key
    // goes, and the receipt says which window it was for.
    [TestCase("input_user_not_paused")]
    [TestCase("input_window_not_in_front")]
    public async Task AnOpenedWindowThatCannotComeUpGetsNothingAndSaysSo(string refusal)
    {
        var keyboard = new FakeDesktopKeyboard();
        var lease = new TakingLease { Refusal = refusal };
        using var provider = new WindowsExternalCapabilityProvider(
            [Adapter(keyboard)], lease, null, Keyboard(new Opening(), Steam));

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(refusal));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(keyboard.Texts, Is.Empty, "no key sent");
            Assert.That(keyboard.Chords, Is.Empty);
            Assert.That(keyboard.Fronted, Is.Empty, "never typed behind the person's window");
            Assert.That(lease.Taken, Is.EqualTo(new nint[] { (nint)Opened }));
            Assert.That(receipt.Result?.GetProperty("windowFrom").GetString(), Is.EqualTo("opened_application"));
            Assert.That(receipt.Result?.GetProperty("openedWindow").GetInt64(), Is.EqualTo(Opened));
        });
    }

    // A window the act names always wins: the opening is not even looked at.
    [Test]
    public async Task ANamedWindowAlwaysWins()
    {
        var focus = new Opening();
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.text.type", lease);
        using var provider = new WindowsExternalCapabilityProvider(
            [adapter], lease, null, Keyboard(focus, Steam));

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":18016}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(lease.Taken, Is.EqualTo(new nint[] { 18016 }));
            Assert.That(adapter.Window, Is.EqualTo(18016));
            Assert.That(receipt.Result?.TryGetProperty("windowFrom", out _), Is.False);
            Assert.That(focus.Peeks, Is.Zero);
        });
    }

    // A window named but invalid is the adapter's to refuse, never replaced by the opened one.
    [Test]
    public async Task AnInvalidNamedWindowIsNeverReplaced()
    {
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.text.type", lease);
        using var provider = new WindowsExternalCapabilityProvider(
            [adapter], lease, null, Keyboard(new Opening(), Steam));

        _ = await provider.InvokeAsync(
            "input.text.type", Json("""{"text":"hola","window":-4}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(lease.Taken, Is.Empty);
            Assert.That(adapter.Window, Is.EqualTo(-4));
        });
    }

    // The protected-window refusal judges the window the act would actually reach: the opened one.
    [Test]
    public async Task TheProtectedWindowRefusalJudgesTheOpenedWindow()
    {
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.text.type", lease);
        var judged = new List<nint>();
        using var provider = new WindowsExternalCapabilityProvider(
            [adapter],
            lease,
            (_, arguments) =>
            {
                nint window = WindowsExternalCapabilityProvider.MissionWindow(arguments);
                judged.Add(window);
                return window == (nint)Opened;
            },
            Keyboard(new Opening(), Steam));

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("protected_window"));
            Assert.That(judged, Is.EqualTo(new nint[] { (nint)Opened }));
            Assert.That(adapter.Calls, Is.Zero);
            Assert.That(lease.Taken, Is.Empty);
            Assert.That(receipt.Result?.GetProperty("windowFrom").GetString(), Is.EqualTo("opened_application"));
        });
    }

    // A key of the system's (switching windows, the Start menu, the Task Manager) is what it is from the front, and a
    // look or a click is not a keyboard act: neither is sent to the opened application.
    [TestCase("input.key.press", """{"key":"alt_tab"}""")]
    [TestCase("input.key.press", """{"key":"win"}""")]
    [TestCase("input.key.press", """{"key":"ctrl_shift_escape"}""")]
    [TestCase("input.visible.click", """{"label":"Biblioteca"}""")]
    [TestCase("input.keyboard.layout", """{"language":"es"}""")]
    // Review of E6: their helpers act on whatever is in front when they run, so they take no window to be sent to.
    [TestCase("input.select.all", """{}""")]
    [TestCase("clipboard.copy", """{}""")]
    [TestCase("clipboard.paste", """{"window":null}""")]
    public async Task ASystemKeyOrAnActOfNoKeyboardIsNotRedirected(string operation, string arguments)
    {
        var focus = new Opening();
        var lease = new TakingLease();
        var adapter = new RecordingAdapter(operation, lease);
        using var provider = new WindowsExternalCapabilityProvider(
            [adapter], lease, null, Keyboard(focus, Steam));

        _ = await provider.InvokeAsync(operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(lease.Taken, Is.Empty);
            Assert.That(adapter.Window, Is.Null);
            Assert.That(focus.Peeks, Is.Zero);
        });
    }

    // Feria (writing with no window): BAXY's own window, where the request was just written, was in front; the text was
    // judged there and refused, while a look and a click land on the person's window below it. The text now goes there
    // too, through the lease, and the receipt says where it went and why.
    [Test]
    public async Task ATextWithNoWindowGoesToThePersonsWindowBelowBaxy()
    {
        var focus = new Opening { Fresh = false };
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.text.type", lease);
        using var provider = new WindowsExternalCapabilityProvider(
            [adapter], lease, null, Keyboard(focus, Steam), () => new OpenedKeyboardWindow((nint)Steam, "Steam"));

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(lease.Taken, Is.EqualTo(new nint[] { (nint)Steam }));
            Assert.That(adapter.Window, Is.EqualTo(Steam));
            Assert.That(receipt.Result?.GetProperty("windowFrom").GetString(), Is.EqualTo("persons_surface"));
            Assert.That(receipt.Result?.GetProperty("surfaceWindow").GetInt64(), Is.EqualTo(Steam));
            Assert.That(receipt.Result?.GetProperty("surfaceWindowTitle").GetString(), Is.EqualTo("Steam"));
        });
    }

    // A fresh opening still wins over the window below BAXY, and a window named wins over both.
    [TestCase("""{"text":"hola"}""", Opened)]
    [TestCase("""{"text":"hola","window":-4}""", -4L)]
    public async Task TheOpenedOrTheNamedWindowWinsOverTheOneBelowBaxy(string arguments, long expected)
    {
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.text.type", lease);
        using var provider = new WindowsExternalCapabilityProvider(
            [adapter], lease, null, Keyboard(new Opening(), Steam),
            () => throw new AssertionException("the window below BAXY is not read"));

        _ = await provider.InvokeAsync("input.text.type", Json(arguments), CancellationToken.None);

        Assert.That(adapter.Window, Is.EqualTo(expected));
    }

    // A key keeps the front: whether its Enter needs the person's yes is read before, on the window in front.
    [Test]
    public async Task AKeyWithNoWindowIsNotSentBelowBaxy()
    {
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.key.press", lease);
        using var provider = new WindowsExternalCapabilityProvider(
            [adapter], lease, null, Keyboard(new Opening { Fresh = false }, Steam),
            () => throw new AssertionException("the window below BAXY is not read for a key"));

        _ = await provider.InvokeAsync("input.key.press", Json("""{"key":"enter"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(adapter.Window, Is.Null);
            Assert.That(lease.Taken, Is.Empty);
        });
    }

    // A protected window below BAXY's own is refused as any other, and the refusal names the front apart from it.
    [Test]
    public async Task AProtectedWindowBelowBaxyIsRefusedNamingTheFrontApart()
    {
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.text.type", lease);
        using var provider = new WindowsExternalCapabilityProvider(
            [adapter], lease,
            (_, arguments) => WindowsExternalCapabilityProvider.MissionWindow(arguments) == (nint)Steam,
            Keyboard(new Opening { Fresh = false }, Steam), () => new OpenedKeyboardWindow((nint)Steam, "terminal"))
        {
            RefusedProcessOf = (_, _) => "WindowsTerminal",
            FrontProcessOf = () => "Baxy",
        };

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("protected_window"));
            Assert.That(receipt.Result?.GetProperty("refusedProcess").GetString(), Is.EqualTo("WindowsTerminal"));
            Assert.That(receipt.Result?.GetProperty("frontProcess").GetString(), Is.EqualTo("Baxy"));
            Assert.That(receipt.Result?.GetProperty("windowFrom").GetString(), Is.EqualTo("persons_surface"));
            Assert.That(adapter.Calls, Is.Zero);
            Assert.That(lease.Taken, Is.Empty);
        });
    }

    // With no window of the person's below BAXY's own, the text goes to the front, as before (and is refused there).
    [Test]
    public async Task WithNoWindowBelowBaxyTheTextGoesToTheFront()
    {
        var lease = new TakingLease();
        var adapter = new RecordingAdapter("input.text.type", lease);
        using var provider = new WindowsExternalCapabilityProvider(
            [adapter], lease, null, Keyboard(new Opening { Fresh = false }, Steam), () => null);

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(adapter.Window, Is.Null);
            Assert.That(lease.Taken, Is.Empty);
            Assert.That(receipt.Result?.TryGetProperty("windowFrom", out _), Is.False);
        });
    }

    // The product's rule: only with BAXY's own window in front, the person's surface below it (PersonsSurface), never
    // the desktop's.
    [Test]
    public void ThePersonsWindowBelowIsTakenOnlyWithBaxyInFront()
    {
        nint chat = 11, below = 22, desktop = 33;
        var processes = new Dictionary<nint, uint> { [0] = 0, [chat] = 4242, [below] = 5151, [desktop] = 6161 };
        var images = new Dictionary<int, string>
        {
            [4242] = @"C:\Program Files\BAXY\Baxy.exe",
            [5151] = @"C:\Apps\editor.exe",
            [6161] = @"C:\Windows\explorer.exe",
        };
        nint Below(nint front, IEnumerable<nint> topDown) => VisibleControlSurface.SurfaceBelowProduct(
            front, window => processes[window], _ => true, window => window == desktop, () => topDown,
            process => images.GetValueOrDefault(process));

        Assert.Multiple(() =>
        {
            Assert.That(Below(chat, [chat, below, desktop]), Is.EqualTo(below));
            Assert.That(Below(below, [below, chat]), Is.EqualTo(nint.Zero), "another window in front");
            Assert.That(Below(chat, [chat]), Is.EqualTo(nint.Zero), "nothing below");
            Assert.That(Below(chat, [chat, desktop]), Is.EqualTo(nint.Zero), "only the desktop below");
            Assert.That(Below(0, [below]), Is.EqualTo(nint.Zero), "nobody's front");
        });
    }

    private static WindowsDesktopInteractionAdapter Adapter(FakeDesktopKeyboard keyboard) => new(
        new NoRunner(),
        "KnownFolderOpen.ps1",
        "KnownFileOpen.ps1",
        "DesktopSelectAll.ps1",
        "DesktopKeyPress.ps1",
        keyboard);

    // The opening app.open noted, fresh or not, and its largest usable window.
    private sealed class Opening : IOpenedApplicationFocus
    {
        internal bool Fresh { get; init; } = true;

        internal long Window { get; init; } = Opened;

        internal long Minimized { get; init; }

        internal int Peeks { get; private set; }

        internal int Takes { get; private set; }

        internal int Fronts { get; private set; }

        private VisibleControlSurface.OpenedApplication? Noted => Fresh
            ? new VisibleControlSurface.OpenedApplication(4242, DateTime.UtcNow.AddSeconds(-2), DateTime.UtcNow, true)
            : null;

        public VisibleControlSurface.OpenedApplication? TakeOpened()
        {
            Takes++;
            return Noted;
        }

        public VisibleControlSurface.OpenedApplication? PeekOpened()
        {
            Peeks++;
            return Noted;
        }

        public ValueTask<VisibleControlSurface.OpenedSurface> FrontAsync(
            VisibleControlSurface.OpenedApplication opened,
            bool judgeDrawn,
            CancellationToken cancellationToken,
            bool bringToFront = false)
        {
            Fronts++;
            Assert.That(bringToFront, Is.False, "the lease brings it up, never the lookup");
            return ValueTask.FromResult(new VisibleControlSurface.OpenedSurface((nint)Window, Drawn: true));
        }

        public nint MinimizedWindow(VisibleControlSurface.OpenedApplication opened) => (nint)Minimized;
    }

    private sealed class TakingLease : IForegroundLease
    {
        internal List<nint> Taken { get; } = [];

        internal string? Refusal { get; init; }

        public ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken) =>
            throw new AssertionException("the provider acquires no burst");

        public ValueTask<IInputBurst> AcquireForHelperAsync(CancellationToken cancellationToken) =>
            throw new AssertionException("the provider runs no helper");

        public ValueTask<string?> TakeForMissionAsync(nint window, CancellationToken cancellationToken)
        {
            Taken.Add(window);
            return ValueTask.FromResult(Refusal);
        }

        public void MissionActEnded(string operation)
        {
        }
    }

    private sealed class RecordingAdapter(string operation, TakingLease lease) : IExternalOperationAdapter
    {
        internal int Calls { get; private set; }

        // The «window» the act was sent with (null: none).
        internal long? Window { get; private set; }

        public bool CanHandle(string name) => name == operation;

        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string name, JsonElement arguments, CancellationToken cancellationToken)
        {
            Calls++;
            Window = arguments.TryGetProperty("window", out JsonElement window) && window.ValueKind == JsonValueKind.Number
                ? window.GetInt64()
                : null;
            Assert.That(lease.Taken.Count, Is.EqualTo(Window is > 0 ? 1 : 0), "the front taken before the act");
            return ValueTask.FromResult(new ExternalCapabilityReceipt(name, true, true, Json("""{"ok":true}"""), null));
        }
    }

    private sealed class NoRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken) =>
            throw new AssertionException("no helper script runs for a key or a text");
    }
}
