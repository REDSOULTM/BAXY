using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// lat-apertura-clic (r13a, 104 missions: a click's receipt and its cascade, ≈150 s in 37 failed clicks and ≈94 s in
/// 33 right ones): the receipt answers «changed» at the first image that differs, a press the tree made and saw no
/// change from is never handed to OCR, and a click decided on a look of the opened application does not wait for it to
/// finish opening again.
/// </summary>
[TestFixture]
public sealed class ComputerUseOpeningClickLatencyTests
{
    private const string PendingClick =
        "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_pending\"," +
        "\"pending\":true,\"name\":\"Aceptar\",\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false," +
        "\"selected\":false,\"toggled\":false}";

    private const string UnchangedControl =
        "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_unchanged\"," +
        "\"name\":\"Aceptar\",\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false,\"selected\":false}";

    private const string SelectedControl =
        "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\"," +
        "\"name\":\"Aceptar\",\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false,\"selected\":true,\"toggled\":false}";

    private const string NotFoundByUia =
        "{\"version\":1,\"ok\":false,\"effectObserved\":false," +
        "\"error\":\"visible_button_not_found\",\"name\":\"\"," +
        "\"controlIdentity\":\"\",\"absentOrDisabled\":false}";

    // The worker's answers to a point («at»): refused on the control the tree already pressed, or pressed by its way.
    private const string AlreadyPressedAt =
        "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_point_already_pressed\",\"name\":\"\"," +
        "\"controlIdentity\":\"\",\"absentOrDisabled\":false,\"selected\":false,\"toggled\":false}";

    private const string PendingAt =
        "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_pending\"," +
        "\"pending\":true,\"method\":\"invoke\",\"name\":\"Aceptar\",\"kind\":\"Button\",\"controlIdentity\":\"9.9\"," +
        "\"absentOrDisabled\":false,\"selected\":false,\"toggled\":false}";

    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    // A window that animates (a caret, a spinner): every image differs from the one before. Before, the receipt waited
    // for two equal images and paid the whole SurfacePostread (1.5 s); now the first different image answers.
    [Test]
    public async Task AClickOnAnAnimatedWindowIsVerifiedAtTheFirstDifferentImage()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(PendingClick, UnchangedControl);
        int captures = 0;
        ValueTask<VisibleControlSurface.CapturedWindow?> Capture(nint window, bool? selfDrawn, CancellationToken token) =>
            ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
                new VisibleControlSurface.CapturedWindow(window, [], 0, 0, 10, 10, "frame" + captures++));
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, capture: Capture);
        var clock = Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Aceptar","window":4660}"""), CancellationToken.None);

        TestContext.Out.WriteLine($"animated window receipt: {clock.ElapsedMilliseconds} ms (budget {VisibleClickTiming.Default.SurfacePostread.TotalMilliseconds} ms)");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("surfaceChanged").GetBoolean(), Is.True);
            Assert.That(captures, Is.EqualTo(2), "the image before and the first one after");
            Assert.That(clock.Elapsed, Is.LessThan(VisibleClickTiming.Default.SurfacePostread / 2));
        });
    }

    // Review of the branch (finding 7): the first image that differs does not hand back the control's state from before
    // the press: the control is asked once more, and a selection it reports now is the receipt's.
    [Test]
    public async Task AnEarlyChangedReceiptCarriesTheControlsStateAfterThePress()
    {
        int captures = 0;
        var worker = new RoutedWorker(request => (string?)request["cmd"] switch
        {
            "click" => PendingClick,
            "postread" when captures > 1 => SelectedControl,
            "postread" => UnchangedControl,
            _ => null,
        });
        ValueTask<VisibleControlSurface.CapturedWindow?> Capture(nint window, bool? selfDrawn, CancellationToken token) =>
            ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
                new VisibleControlSurface.CapturedWindow(window, [], 0, 0, 10, 10, "frame" + captures++));
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, capture: Capture);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Aceptar","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("selected").GetBoolean(), Is.True);
            Assert.That(captures, Is.EqualTo(2), "still answered at the first different image");
        });
    }

    // Counter-case: a window that never changes is still watched the whole budget before «unchanged» is said.
    [Test]
    public async Task AClickThatChangedNothingIsWatchedTheWholeBudget()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(PendingClick, UnchangedControl);
        ValueTask<VisibleControlSurface.CapturedWindow?> Capture(nint window, bool? selfDrawn, CancellationToken token) =>
            ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
                new VisibleControlSurface.CapturedWindow(window, [], 0, 0, 10, 10, "same"));
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, capture: Capture);
        var clock = Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Aceptar","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_postread_unchanged"));
            Assert.That(clock.Elapsed, Is.GreaterThanOrEqualTo(VisibleClickTiming.Default.SurfacePostread));
        });
    }

    // The tree found the control, pressed it by its pattern and saw nothing change. Review of the branch (finding 4):
    // the OCR stage still looks for the label (since 956a89ace it rescued a hidden duplicate the tree chose, or an
    // Invoke the application ignored), but its point on that same control is refused by the worker before any effect,
    // and the click answers with the tree's press: pressed once, without the stage's own post-read.
    [Test]
    public async Task APressTheTreeMadeThatChangedNothingIsNeverPressedAgainByOcr()
    {
        var worker = new RoutedWorker(request => (string?)request["cmd"] switch
        {
            "click" => PendingClick,
            "postread" => UnchangedControl,
            "at" when (string?)request["pressed"] == "1.2.3" => AlreadyPressedAt,
            "at" => PendingAt,
            _ => null,
        });
        var ocr = new PointLocator("ocr");
        var adapter = new WindowsVisibleControlAdapter(worker, ocr, null, capture: NoCapture);
        var clock = Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Aceptar","window":4660}"""), CancellationToken.None);

        TestContext.Out.WriteLine($"tree's press unchanged, OCR refused on it: {clock.ElapsedMilliseconds} ms");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_postread_unchanged"));
            Assert.That(receipt.EffectObserved, Is.True, "it pressed");
            Assert.That(ocr.Calls, Is.EqualTo(1));
            Assert.That(worker.Commands.Count(command => (string?)command["cmd"] == "click"), Is.EqualTo(1));
            Assert.That(worker.Commands.Single(command => (string?)command["cmd"] == "at")["pressed"]?.GetValue<string>(),
                Is.EqualTo("1.2.3"), "the stage's point names the control the tree pressed");
            Assert.That(worker.Pressed, Is.Zero, "no second press");
        });
    }

    // Review of fable/cu-v3-recibo-del-clic-por-estado (finding 1, double press): the worker answered the press as done
    // with nothing the adapter takes as proof («visible_click_postread_invalid»). The OCR stage still looks for the label,
    // but its point on that same control is refused: pressed once, as for a press seen unchanged.
    [Test]
    public async Task APressWhosePostreadIsInvalidIsNeverPressedAgainByOcr()
    {
        const string DoneWithoutProof =
            "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Aceptar\"," +
            "\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false,\"selected\":false,\"toggled\":false," +
            "\"surfaceChanged\":false,\"focused\":true}";
        var worker = new RoutedWorker(request => (string?)request["cmd"] switch
        {
            "click" => PendingClick,
            "postread" => DoneWithoutProof,
            "at" when (string?)request["pressed"] == "1.2.3" => AlreadyPressedAt,
            "at" => PendingAt,
            _ => null,
        });
        var ocr = new PointLocator("ocr");
        var adapter = new WindowsVisibleControlAdapter(worker, ocr, null, capture: NoCapture);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Aceptar","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_click_postread_invalid"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True, "it pressed");
            Assert.That(ocr.Calls, Is.GreaterThanOrEqualTo(1), "the OCR stage still looked");
            Assert.That(worker.Commands.Count(command => command["cmd"]?.GetValue<string>() == "at"), Is.GreaterThanOrEqualTo(1));
            Assert.That(worker.Commands.Count(command => (string?)command["cmd"] == "click"), Is.EqualTo(1));
            Assert.That(worker.Commands.Where(command => (string?)command["cmd"] == "at")
                    .Select(command => command["pressed"]?.GetValue<string>()),
                Is.All.EqualTo("1.2.3"), "every later point names the control the tree pressed");
            Assert.That(worker.Pressed, Is.Zero, "no second press");
        });
    }

    // Counter-case (the rescue kept): the OCR stage's point is on another control with the same name (the visible one,
    // the tree having pressed a hidden duplicate): it is pressed, and the click is the stage's.
    [Test]
    public async Task AnotherControlWithTheSameNameIsStillRescuedByOcr()
    {
        var worker = new RoutedWorker(request => (string?)request["cmd"] switch
        {
            "click" => PendingClick,
            "postread" => UnchangedControl,
            "at" => PendingAt,
            _ => null,
        });
        var ocr = new PointLocator("ocr");
        var adapter = new WindowsVisibleControlAdapter(worker, ocr, null, capture: NoCapture);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Aceptar","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("cascadeStage").GetString(), Is.EqualTo("ocr"));
            Assert.That(worker.Pressed, Is.EqualTo(1));
        });
    }

    // Counter-case: a later click (another act) carries no memory of the earlier click's press.
    [Test]
    public async Task TheControlPressedInOneClickIsForgottenByTheNext()
    {
        var worker = new RoutedWorker(request => (string?)request["cmd"] switch
        {
            "click" => PendingClick,
            "postread" => UnchangedControl,
            "at" => PendingAt,
            _ => null,
        });
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, capture: NoCapture);
        _ = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Aceptar","window":4660}"""), CancellationToken.None);

        PointPressed pressed = await adapter.PressAtAsync(4660, 5, 5, "Aceptar", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Outcome, Is.EqualTo(PointPressOutcome.Pressed));
            Assert.That(worker.Commands.Last()["pressed"], Is.Null);
        });
    }

    // Counter-case: a label the tree did not find (nothing pressed) still goes on to OCR, which presses it.
    [Test]
    public async Task ALabelTheTreeDidNotFindStillGoesToOcr()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var ocr = new Locator("ocr", hit: true);
        var adapter = new WindowsVisibleControlAdapter(worker, ocr, null, capture: NoCapture);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Biblioteca","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(ocr.Calls, Is.EqualTo(1));
        });
    }

    private static readonly VisibleClickTiming OpeningTiming = VisibleClickTiming.Default with
    {
        LaunchSurface = TimeSpan.FromSeconds(3),
        OpenedLabel = TimeSpan.FromSeconds(2),
        SettledLabel = TimeSpan.FromMilliseconds(600),
        Interval = TimeSpan.FromMilliseconds(300),
        StillSample = TimeSpan.FromMilliseconds(30),
        StillFor = TimeSpan.FromMilliseconds(90),
    };

    private static ExternalCapabilityReceipt LookOf(int processId) => new(
        "input.visible.controls", false, true,
        Json("{\"version\":2,\"ok\":true,\"window\":{\"title\":\"Epic Games Launcher\",\"processId\":" + processId +
             ",\"hwnd\":4660,\"requested\":true},\"controls\":[]}"),
        null);

    // Epic, r13a: 27.3 s for a click by label right after app.open, its view of 0 controls. The mission had already
    // waited for the window and decided the click on a look of it: the click no longer waits LaunchSurface + OpenedLabel
    // (here 3 s + 2 s) on a window whose application is still «opening»; a still window answers «not found» at once.
    [Test]
    public async Task AClickDecidedOnALookOfTheOpenedApplicationDoesNotWaitForItToOpenAgain()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var focus = new FixedOpening(4242);
        var adapter = new WindowsVisibleControlAdapter(
            worker, new Locator("ocr"), null, focus, OpeningTiming,
            surfaceHash: (_, _) => ValueTask.FromResult<string?>("same"));
        adapter.NoteOpenedLooked(LookOf(4242), 4242, ["Biblioteca"]);
        var clock = Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Biblioteca","window":4660}"""), CancellationToken.None);

        TestContext.Out.WriteLine($"click after a look of the opened application: {clock.ElapsedMilliseconds} ms (before: ≥ {(OpeningTiming.LaunchSurface + OpeningTiming.OpenedLabel).TotalMilliseconds} ms)");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_not_found"));
            Assert.That(clock.Elapsed, Is.LessThan(OpeningTiming.LaunchSurface));
            Assert.That(focus.FrontCalls, Is.Zero, "the opened application's surface is not waited on");
            Assert.That(worker.Commands[0], Does.Contain("\"hwnd\":4660"), "the label is looked for on the window the click names");
        });
    }

    // Counter-case: a click with no look of the opened application (or one of another process) keeps the opening's
    // wait (a client launched cold draws its navigation seconds after its window, UI1731).
    [TestCase(false)]
    [TestCase(true)]
    public async Task AClickWithoutALookOfTheOpenedApplicationKeepsTheOpeningsWait(bool lookOfAnother)
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var focus = new FixedOpening(4242);
        var adapter = new WindowsVisibleControlAdapter(
            worker, new Locator("ocr"), null, focus, OpeningTiming,
            surfaceHash: (_, _) => ValueTask.FromResult<string?>("same"));
        if (lookOfAnother)
            adapter.NoteOpenedLooked(LookOf(777), 0, ["Biblioteca"]);
        var clock = Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Biblioteca","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_not_found"));
            Assert.That(focus.FrontCalls, Is.GreaterThan(0));
            Assert.That(clock.Elapsed, Is.GreaterThanOrEqualTo(OpeningTiming.LaunchSurface - TimeSpan.FromMilliseconds(50)));
        });
    }

    // Counter-case: a click that names no window (not a mission's) keeps the opening's wait too: it would otherwise be
    // bound to whatever holds the front.
    [Test]
    public async Task AClickWithoutItsWindowKeepsTheOpeningsWait()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var focus = new FixedOpening(4242);
        var adapter = new WindowsVisibleControlAdapter(
            worker, new Locator("ocr"), null, focus, OpeningTiming,
            surfaceHash: (_, _) => ValueTask.FromResult<string?>("same"));
        adapter.NoteOpenedLooked(LookOf(4242), 4242, ["Biblioteca"]);

        _ = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Biblioteca"}"""), CancellationToken.None);

        Assert.That(focus.FrontCalls, Is.GreaterThan(0));
    }

    // Review of the branch (finding 6): a look of a splash that does not show the label (its navigation drawn seconds
    // later, UI1731; «Cargando tu biblioteca» is not the «Biblioteca» of the navigation), or a click on another window
    // than the one looked at, keeps the opening's wait.
    [TestCase("Cargando tu biblioteca", 4660)]
    [TestCase("Biblioteca", 9999)]
    public async Task ALookThatDoesNotShowTheLabelOnTheClicksWindowKeepsTheOpeningsWait(string shown, int clickWindow)
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var focus = new FixedOpening(4242);
        var adapter = new WindowsVisibleControlAdapter(
            worker, new Locator("ocr"), null, focus, OpeningTiming,
            surfaceHash: (_, _) => ValueTask.FromResult<string?>("same"));
        adapter.NoteOpenedLooked(LookOf(4242), 4242, [shown]);
        var clock = Stopwatch.StartNew();

        _ = await adapter.InvokeAsync(
            "input.visible.click", Json("{\"label\":\"Biblioteca\",\"window\":" + clickWindow + "}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(focus.FrontCalls, Is.GreaterThan(0));
            Assert.That(clock.Elapsed, Is.GreaterThanOrEqualTo(OpeningTiming.LaunchSurface - TimeSpan.FromMilliseconds(50)));
        });
    }

    // Finding 6: the note is taken by the look itself (input.visible.controls with the fields it really writes: the
    // window's handle, «requested», its controls' names), not called by the test.
    [TestCase("Biblioteca", true)]
    [TestCase("Tienda", false)]
    public async Task TheLookItselfNotesTheOpenedWindowAndWhatItShowed(string label, bool skipsTheWait)
    {
        const long front = 0x7FFF_0F1E;
        string view = "{\"ok\":true,\"error\":\"\",\"hwnd\":" + front + ",\"window\":\"Iniciador\",\"controls\":[" +
            "{\"i\":0,\"kind\":\"Hyperlink\",\"name\":\"Biblioteca\",\"id\":\"4.2\",\"state\":\"\",\"value\":null,\"rect\":null,\"repeated\":0}," +
            "{\"i\":1,\"kind\":\"Hyperlink\",\"name\":\"Inicio\",\"id\":\"4.3\",\"state\":\"\",\"value\":null,\"rect\":null,\"repeated\":0}]," +
            "\"controlCount\":2,\"focused\":null}";
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(view, NotFoundByUia);
        var focus = new FixedOpening(4242);
        var adapter = new WindowsVisibleControlAdapter(
            worker, new Locator("ocr"), null, focus, OpeningTiming, browserWindow: new FrontBrowser(front),
            surfaceHash: (_, _) => ValueTask.FromResult<string?>("same"));
        ExternalCapabilityReceipt looked = await adapter.InvokeAsync(
            "input.visible.controls", Json("""{"application":"el navegador","processId":4242}"""), CancellationToken.None);
        Assume.That(looked.Result?.GetProperty("window").GetProperty("requested").GetBoolean(), Is.True);
        var clock = Stopwatch.StartNew();

        _ = await adapter.InvokeAsync(
            "input.visible.click", Json("{\"label\":\"" + label + "\",\"window\":" + front + "}"), CancellationToken.None);

        TestContext.Out.WriteLine($"click «{label}» after the look: {clock.ElapsedMilliseconds} ms");
        Assert.That(focus.FrontCalls, skipsTheWait ? Is.Zero : Is.GreaterThan(0));
    }

    private sealed class FrontBrowser(long handle) : IUserBrowserWindowLocator
    {
        public nint FrontWindow() => (nint)handle;
    }

    private static ValueTask<VisibleControlSurface.CapturedWindow?> NoCapture(
        nint window, bool? selfDrawn, CancellationToken cancellationToken) =>
        ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null);

    // One opening, the same one peeked by a look and taken by the click; its window never shows (a launcher still
    // opening), so a click that waits for it waits the whole LaunchSurface.
    private sealed class FixedOpening(int processId) : IOpenedApplicationFocus
    {
        private readonly VisibleControlSurface.OpenedApplication _opening =
            new(processId, DateTime.UtcNow.AddSeconds(-1), DateTime.UtcNow, true);

        private bool _taken;

        internal int FrontCalls { get; private set; }

        public VisibleControlSurface.OpenedApplication? TakeOpened()
        {
            if (_taken)
                return null;
            _taken = true;
            return _opening;
        }

        public VisibleControlSurface.OpenedApplication? PeekOpened() => _taken ? null : _opening;

        public ValueTask<VisibleControlSurface.OpenedSurface> FrontAsync(
            VisibleControlSurface.OpenedApplication opened,
            bool judgeDrawn,
            CancellationToken cancellationToken,
            bool bringToFront = false)
        {
            FrontCalls++;
            return ValueTask.FromResult(default(VisibleControlSurface.OpenedSurface));
        }
    }

    // A worker that answers by command; it counts the points it accepted to press.
    private sealed class RoutedWorker(Func<JsonObject, string?> answer) : IUiaWorker
    {
        internal List<JsonObject> Commands { get; } = [];

        internal int Pressed { get; private set; }

        public ValueTask PrewarmAsync(CancellationToken cancellationToken) => ValueTask.CompletedTask;

        public ValueTask<JsonDocument?> SendAsync(string commandJson, TimeSpan timeout, CancellationToken cancellationToken)
        {
            var command = (JsonObject)JsonNode.Parse(commandJson)!;
            Commands.Add(command);
            string? text = answer(command);
            if ((string?)command["cmd"] == "at" && text is not null && text.Contains("\"pending\":true", StringComparison.Ordinal))
                Pressed++;
            return ValueTask.FromResult(text is null ? null : JsonDocument.Parse(text));
        }
    }

    // A stage that locates the label at a point and presses it there through the adapter (the way OCR does).
    private sealed class PointLocator(string stage) : IVisibleControlLocator
    {
        internal int Calls { get; private set; }

        public string Stage => stage;

        public ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
            string operation, string label, CancellationToken cancellationToken) =>
            TryClickAsync(operation, label, null, cancellationToken);

        public async ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
            string operation, string label, IPointPress? press, CancellationToken cancellationToken)
        {
            Calls++;
            LocatedPointPress.Outcome pressed = await LocatedPointPress.PressAsync(
                press, operation, 4660, 5, 5, label, cancellationToken);
            if (pressed.Failure is { } refused)
                return refused;
            JsonElement result = Json(
                "{\"version\":1,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"" + label + "\"," +
                "\"surfaceChanged\":true,\"cascadeStage\":\"" + stage + "\"}");
            return new ExternalCapabilityReceipt(operation, true, true, result, null);
        }
    }

    private sealed class Locator(string stage, bool hit = false) : IVisibleControlLocator
    {
        internal int Calls { get; private set; }

        public string Stage => stage;

        public ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
            string operation, string label, CancellationToken cancellationToken)
        {
            Calls++;
            if (!hit)
                return ValueTask.FromResult<ExternalCapabilityReceipt?>(null);
            JsonElement result = Json(
                "{\"version\":1,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"" + label + "\"," +
                "\"surfaceChanged\":true,\"cascadeStage\":\"" + stage + "\"}");
            return ValueTask.FromResult<ExternalCapabilityReceipt?>(
                new ExternalCapabilityReceipt(operation, true, true, result, null));
        }
    }
}
