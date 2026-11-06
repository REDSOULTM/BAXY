using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso real 05-11 (C2040): a look named one application and the click by a label it showed, with no window, went to the
/// window in front: refused as protected with BAXY's own in front, or pressed in another application that bore the same
/// name. And a look at an application opened a moment ago, whose first window had just gone, read as closed.
/// </summary>
[TestFixture]
public sealed class ClickOnLastLookTests
{
    private const long Looked = 0x7FFF_0A01;
    private const long Front = 0x7FFF_0A02;

    private const string Clicked =
        "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Curso de prueba\"," +
        "\"controlIdentity\":\"4.1\",\"absentOrDisabled\":false,\"selected\":true,\"toggled\":false}";

    private static string View(params string[] names) =>
        "{\"ok\":true,\"error\":\"\",\"hwnd\":" + Looked + ",\"window\":\"Correo\",\"controls\":["
        + string.Join(',', names.Select((name, at) =>
            "{\"kind\":\"Button\",\"name\":\"" + name + "\",\"id\":\"4." + at + "\",\"state\":\"\",\"value\":null,"
            + "\"rect\":null,\"repeated\":0}"))
        + "],\"controlCount\":" + names.Length + "}";

    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    private sealed class Worker(string view) : IUiaWorker
    {
        internal List<JsonObject> Clicks { get; } = [];

        public ValueTask PrewarmAsync(CancellationToken cancellationToken) => ValueTask.CompletedTask;

        public ValueTask<JsonDocument?> SendAsync(string commandJson, TimeSpan timeout, CancellationToken cancellationToken)
        {
            var command = (JsonObject)JsonNode.Parse(commandJson)!;
            string? answer = (string?)command["cmd"] switch
            {
                "view" => view,
                "click" => Clicked,
                _ => null,
            };
            if ((string?)command["cmd"] == "click")
                Clicks.Add(command);
            return ValueTask.FromResult(answer is null ? null : JsonDocument.Parse(answer));
        }
    }

    private sealed class Lease : IForegroundLease
    {
        internal List<nint> Taken { get; } = [];

        public ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken) =>
            throw new AssertionException("the provider acquires no burst");

        public ValueTask<IInputBurst> AcquireForHelperAsync(CancellationToken cancellationToken) =>
            throw new AssertionException("the provider runs no helper");

        public ValueTask<string?> TakeForMissionAsync(nint window, CancellationToken cancellationToken)
        {
            Taken.Add(window);
            return ValueTask.FromResult<string?>(null);
        }

        public void MissionActEnded(string operation)
        {
        }
    }

    private sealed class SteppedTime : TimeProvider
    {
        internal DateTimeOffset At { get; set; } = new(2026, 11, 5, 23, 0, 0, TimeSpan.Zero);

        public override DateTimeOffset GetUtcNow() => At;
    }

    private static WindowsVisibleControlAdapter Adapter(Worker worker, TimeProvider? time = null) =>
        new(worker, null, null,
            requestedWindow: (_, _) => ValueTask.FromResult((nint)Looked),
            capture: (_, _, _) => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null),
            time: time)
        {
            WindowInFront = _ => ValueTask.FromResult((nint)Front),
            WindowAlive = window => window == Looked,
        };

    private static ValueTask<ExternalCapabilityReceipt> LookAsync(WindowsExternalCapabilityProvider provider) =>
        provider.InvokeAsync("input.visible.controls", Json("""{"application":"Correo"}"""), CancellationToken.None);

    private static ValueTask<ExternalCapabilityReceipt> ClickAsync(WindowsExternalCapabilityProvider provider, string arguments) =>
        provider.InvokeAsync("input.visible.click", Json(arguments), CancellationToken.None);

    // The row of the look is pressed in the window looked at, the way a click that names it is: its window is taken for
    // the act, never the application in front that bears the same name.
    [Test]
    public async Task AClickByALabelTheLookShowedActsInTheWindowLookedAt()
    {
        var worker = new Worker(View("Curso de prueba", "Eliminar"));
        var lease = new Lease();
        using var provider = new WindowsExternalCapabilityProvider([Adapter(worker)], lease, (_, _) => false);

        await LookAsync(provider);
        await ClickAsync(provider, """{"label":"Curso de prueba"}""");

        Assert.Multiple(() =>
        {
            Assert.That(worker.Clicks.Single()["hwnd"]!.GetValue<long>(), Is.EqualTo(Looked));
            Assert.That(lease.Taken, Is.EqualTo(new[] { (nint)Looked }));
        });
    }

    // BAXY's own window in front: the refusal judged the front, though the click was for the window looked at.
    [Test]
    public async Task AProtectedWindowInFrontDoesNotRefuseAClickForTheWindowLookedAt()
    {
        var worker = new Worker(View("Curso de prueba"));
        using var provider = new WindowsExternalCapabilityProvider(
            [Adapter(worker)], new Lease(),
            (operation, arguments) => operation == "input.visible.click"
                && WindowsExternalCapabilityProvider.MissionWindow(arguments) == 0);

        await LookAsync(provider);
        ExternalCapabilityReceipt receipt = await ClickAsync(provider, """{"label":"Curso de prueba"}""");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Not.EqualTo("protected_window"));
            Assert.That(worker.Clicks, Has.Count.EqualTo(1));
        });
    }

    // A row's name holds more than the words read of it: the label inside it, as whole words, was shown by the look.
    [Test]
    public async Task ALabelInsideALongerNameIsShownByTheLook()
    {
        var worker = new Worker(View("De Curso de prueba Tarea calificada ayer"));
        var lease = new Lease();
        using var provider = new WindowsExternalCapabilityProvider([Adapter(worker)], lease, (_, _) => false);

        await LookAsync(provider);
        await ClickAsync(provider, """{"label":"curso de prueba"}""");

        Assert.That(lease.Taken, Is.EqualTo(new[] { (nint)Looked }));
    }

    // Controls. A label the look did not show, part of a word only, a look of minutes ago, a dead window: as before, the
    // window in front. A click that names its window keeps it.
    [TestCase("""{"label":"Aceptar"}""")]
    [TestCase("""{"label":"Curso de prueba"}""")]
    public async Task ALabelTheLookDidNotShowStaysInTheWindowInFront(string arguments)
    {
        var worker = new Worker(View("Curso de pruebas finales"));
        var lease = new Lease();
        using var provider = new WindowsExternalCapabilityProvider([Adapter(worker)], lease, (_, _) => false);

        await LookAsync(provider);
        await ClickAsync(provider, arguments);

        Assert.Multiple(() =>
        {
            Assert.That(lease.Taken, Is.Empty);
            Assert.That(worker.Clicks.Single()["hwnd"]!.GetValue<long>(), Is.EqualTo(Front));
        });
    }

    [Test]
    public async Task ALookOfMinutesAgoNamesNoWindow()
    {
        var worker = new Worker(View("Curso de prueba"));
        var time = new SteppedTime();
        var lease = new Lease();
        using var provider = new WindowsExternalCapabilityProvider([Adapter(worker, time)], lease, (_, _) => false);

        await LookAsync(provider);
        time.At += WindowsVisibleControlAdapter.LabelLookFreshness + TimeSpan.FromSeconds(1);
        await ClickAsync(provider, """{"label":"Curso de prueba"}""");

        Assert.Multiple(() =>
        {
            Assert.That(lease.Taken, Is.Empty);
            Assert.That(worker.Clicks.Single()["hwnd"]!.GetValue<long>(), Is.EqualTo(Front));
        });
    }

    // A manner or a search goes by its own identity, as before: no front is taken for it, nor a window named.
    [TestCase("""{"label":"Curso de prueba","manner":"menu"}""")]
    [TestCase("""{"label":"Curso de prueba","search":"algo"}""")]
    public async Task AMannerOrASearchIsNotBoundToTheLook(string arguments)
    {
        var worker = new Worker(View("Curso de prueba"));
        var lease = new Lease();
        using var provider = new WindowsExternalCapabilityProvider([Adapter(worker)], lease, (_, _) => false);

        await LookAsync(provider);
        await ClickAsync(provider, arguments);

        Assert.That(lease.Taken, Is.Empty);
    }

    // An application opened after the look is where a click by a label goes, as the descriptor says, though the older look
    // showed the same words.
    [Test]
    public async Task AnOpeningAfterTheLookWinsOverIt()
    {
        var worker = new Worker(View("Archivo"));
        var focus = new LateOpening();
        var time = new SteppedTime();
        var adapter = new WindowsVisibleControlAdapter(
            worker, null, null, focus, VisibleClickTiming.Default with { LaunchSurface = TimeSpan.Zero, OpenedLabel = TimeSpan.Zero },
            requestedWindow: (_, _) => ValueTask.FromResult((nint)Looked),
            capture: (_, _, _) => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null),
            time: time)
        {
            WindowInFront = _ => ValueTask.FromResult((nint)Front),
            WindowAlive = window => window == Looked,
        };

        await adapter.InvokeAsync("input.visible.controls", Json("""{"application":"Correo"}"""), CancellationToken.None);
        Assert.That(await adapter.WindowOfLastLookAsync("input.visible.click", Json("""{"label":"Archivo"}"""), CancellationToken.None), Is.EqualTo((nint)Looked));
        focus.Opening = new VisibleControlSurface.OpenedApplication(
            4242, time.At.UtcDateTime, time.At.UtcDateTime.AddSeconds(1), true);

        Assert.That(await adapter.WindowOfLastLookAsync("input.visible.click", Json("""{"label":"Archivo"}"""), CancellationToken.None), Is.EqualTo((nint)0));
    }

    private sealed class LateOpening : IOpenedApplicationFocus
    {
        internal VisibleControlSurface.OpenedApplication? Opening { get; set; }

        public VisibleControlSurface.OpenedApplication? TakeOpened() => Opening;

        public VisibleControlSurface.OpenedApplication? PeekOpened() => Opening;

        public ValueTask<VisibleControlSurface.OpenedSurface> FrontAsync(
            VisibleControlSurface.OpenedApplication opened,
            bool judgeDrawn,
            CancellationToken cancellationToken,
            bool bringToFront = false) =>
            ValueTask.FromResult(new VisibleControlSurface.OpenedSurface(0, false));
    }

    [Test]
    public async Task AClickThatNamesItsWindowKeepsIt()
    {
        var worker = new Worker(View("Curso de prueba"));
        var lease = new Lease();
        using var provider = new WindowsExternalCapabilityProvider([Adapter(worker)], lease, (_, _) => false);

        await LookAsync(provider);
        await ClickAsync(provider, """{"label":"Curso de prueba","window":4660}""");

        Assert.That(lease.Taken, Is.EqualTo(new[] { (nint)4660 }));
    }

    // The application just opened showed its dialog to the look: the click on the dialog's button acts at once, it does
    // not wait thirty seconds for a main window and say none showed (uso real: visible_opened_window_not_shown).
    // Its dialog drawn by the opened process, or by another of its family.
    [TestCase(true)]
    [TestCase(false)]
    public async Task AClickOnTheDialogALookOfTheOpenedApplicationShowedDoesNotWaitForAWindow(bool ofTheOpenedProcess)
    {
        var worker = new Worker(View("Aceptar"));
        var focus = new NoWindowOpening();
        var timing = VisibleClickTiming.Default with { LaunchSurface = TimeSpan.FromSeconds(5) };
        var adapter = new WindowsVisibleControlAdapter(
            worker, null, null, focus, timing,
            requestedWindow: (_, _) => ValueTask.FromResult((nint)Looked),
            capture: (_, _, _) => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null))
        {
            WindowInFront = _ => ValueTask.FromResult((nint)Front),
            WindowAlive = window => window == Looked,
            WindowOfProcess = (_, _) => ofTheOpenedProcess,
        };
        using var provider = new WindowsExternalCapabilityProvider([adapter], new Lease(), (_, _) => false);

        await LookAsync(provider);
        if (ofTheOpenedProcess)
        {
            adapter.NoteOpenedLooked(
                new ExternalCapabilityReceipt("input.visible.controls", false, true, Json(
                    "{\"window\":{\"processId\":4242,\"hwnd\":" + Looked + "}}"), null),
                ["Aceptar"]);
        }

        var clock = System.Diagnostics.Stopwatch.StartNew();
        ExternalCapabilityReceipt receipt = await ClickAsync(provider, """{"label":"Aceptar"}""");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Not.EqualTo("visible_opened_window_not_shown"));
            Assert.That(worker.Clicks.Single()["hwnd"]!.GetValue<long>(), Is.EqualTo(Looked));
            Assert.That(clock.Elapsed, Is.LessThan(timing.LaunchSurface));
        });
    }

    private sealed class NoWindowOpening : IOpenedApplicationFocus
    {
        private readonly VisibleControlSurface.OpenedApplication _opening =
            new(4242, DateTime.UtcNow.AddSeconds(-1), DateTime.UtcNow, true);

        private bool _taken;

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
            bool bringToFront = false) =>
            ValueTask.FromResult(new VisibleControlSurface.OpenedSurface(0, false));
    }

    private static readonly VisibleClickTiming ShortOpening = VisibleClickTiming.Default with
    {
        OpeningLook = TimeSpan.FromMilliseconds(900),
        OpeningGoneGrace = TimeSpan.FromMilliseconds(150),
        OpeningLookPoll = TimeSpan.FromMilliseconds(30),
    };

    private static WindowsVisibleControlAdapter OpeningAdapter(Func<nint> window, bool? runs) =>
        new(new Worker(View("Bandeja de entrada")), null, null, timing: ShortOpening,
            requestedWindow: (_, _) => ValueTask.FromResult(window()),
            capture: (_, _, _) => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null))
        {
            OpeningRuns = _ => runs,
        };

    // The first window of an application opened a moment ago went (its dialog was accepted) and the main one is not up:
    // the look waits for it.
    [Test]
    public async Task ALookAtAnApplicationJustOpenedWaitsForItsWindow()
    {
        int reads = 0;
        WindowsVisibleControlAdapter adapter = OpeningAdapter(() => ++reads < 4 ? 0 : (nint)Looked, runs: true);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.controls", Json("""{"application":"Correo"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(reads, Is.GreaterThanOrEqualTo(4));
        });
    }

    // Still none when the wait ends: the failure says its program runs, so it is never told as closed.
    [Test]
    public async Task AnOpeningThatStillShowsNoWindowIsSaidToBeRunning()
    {
        WindowsVisibleControlAdapter adapter = OpeningAdapter(() => 0, runs: true);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.controls", Json("""{"application":"Correo"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("application_window_not_found"));
            Assert.That(receipt.Result?.GetProperty("applicationRunning").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("next").GetString(), Does.Contain("still running"));
        });
    }

    // Its program gone: a short grace (a launcher hands over to the main program), and nothing said of running.
    [Test]
    public async Task AnOpeningWhoseProgramIsGoneWaitsOnlyItsGrace()
    {
        WindowsVisibleControlAdapter adapter = OpeningAdapter(() => 0, runs: false);
        var clock = System.Diagnostics.Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.controls", Json("""{"application":"Correo"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("application_window_not_found"));
            Assert.That(receipt.Result?.TryGetProperty("applicationRunning", out _), Is.False);
            Assert.That(clock.Elapsed, Is.GreaterThanOrEqualTo(ShortOpening.OpeningGoneGrace));
            Assert.That(clock.Elapsed, Is.LessThan(ShortOpening.OpeningLook));
        });
    }

    // A look that waits for a label has its own wait: the opening's is not added on each round.
    [Test]
    public async Task ALookThatWaitsForALabelDoesNotAddTheOpeningsWait()
    {
        WindowsVisibleControlAdapter adapter = OpeningAdapter(() => 0, runs: true);
        var clock = System.Diagnostics.Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.controls", Json("""{"application":"Correo","waitForLabel":"Aceptar"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("application_window_not_found"));
            Assert.That(clock.Elapsed, Is.LessThan(ShortOpening.OpeningLook));
        });
    }

    // Control: a name BAXY did not open now (a page's name, an application in the tray) answers at once, as before.
    [Test]
    public async Task ANameNotOpenedNowIsNotWaitedFor()
    {
        int reads = 0;
        WindowsVisibleControlAdapter adapter = OpeningAdapter(() => { reads++; return 0; }, runs: null);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.controls", Json("""{"application":"Portal de prueba"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("application_window_not_found"));
            Assert.That(reads, Is.LessThanOrEqualTo(2));
            Assert.That(receipt.Result?.TryGetProperty("applicationRunning", out _), Is.False);
        });
    }
}
