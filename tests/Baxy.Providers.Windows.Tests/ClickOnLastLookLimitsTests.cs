using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Revisión a ciegas R2 de C2040: when a click by a label the last look showed stops being decided on that look. The look
/// holds while nothing else came: not once the click acted elsewhere or something opened after it (H1), not once the
/// person brought another window (H2), whatever nulls the call writes (H3). A yes holds for the window it was asked for
/// (H4). A dialog no look read is not pressed (H5).
/// </summary>
[TestFixture]
public sealed class ClickOnLastLookLimitsTests
{
    private const long Looked = 0x7FFF_0A01;
    private const long Front = 0x7FFF_0A02;
    private const long Opened = 0x7FFF_0A03;
    private const long Dialog = 0x7FFF_0A04;
    private const long Other = 0x7FFF_0A05;

    private const string Clicked =
        "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"x\"," +
        "\"controlIdentity\":\"4.1\",\"absentOrDisabled\":false,\"selected\":true,\"toggled\":false}";

    private const string NotFound =
        "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_button_not_found\"}";

    private static string View(params string[] names) =>
        "{\"ok\":true,\"error\":\"\",\"hwnd\":" + Looked + ",\"window\":\"Correo\",\"controls\":["
        + string.Join(',', names.Select((name, at) =>
            "{\"kind\":\"Button\",\"name\":\"" + name + "\",\"id\":\"4." + at + "\",\"state\":\"\",\"value\":null,"
            + "\"rect\":null,\"repeated\":0}"))
        + "],\"controlCount\":" + names.Length + "}";

    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    private sealed class Worker(string view) : IUiaWorker
    {
        internal string ClickAnswer { get; set; } = Clicked;

        internal Action? OnClick { get; set; }

        internal List<JsonObject> Clicks { get; } = [];

        internal long LastClicked => Clicks[^1]["hwnd"]!.GetValue<long>();

        public ValueTask PrewarmAsync(CancellationToken cancellationToken) => ValueTask.CompletedTask;

        public ValueTask<JsonDocument?> SendAsync(string commandJson, TimeSpan timeout, CancellationToken cancellationToken)
        {
            var command = (JsonObject)JsonNode.Parse(commandJson)!;
            string? answer = (string?)command["cmd"] switch
            {
                "view" => view,
                "click" => ClickAnswer,
                _ => null,
            };
            if ((string?)command["cmd"] == "click")
            {
                Clicks.Add(command);
                OnClick?.Invoke();
            }

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

    // As the product's: taking the opening spends it and it is fresh for 90 s, but when the last one came stays known.
    private sealed class Openings(TimeProvider time) : IOpenedApplicationFocus
    {
        private VisibleControlSurface.OpenedApplication? _opening;
        private DateTime? _last;

        internal void Open()
        {
            DateTime now = time.GetUtcNow().UtcDateTime;
            _opening = new VisibleControlSurface.OpenedApplication(4242, now, now, true);
            _last = now;
        }

        private bool Fresh => _opening is { } opening && time.GetUtcNow().UtcDateTime - opening.NotedUtc <= TimeSpan.FromSeconds(90);

        public VisibleControlSurface.OpenedApplication? TakeOpened()
        {
            VisibleControlSurface.OpenedApplication? taken = Fresh ? _opening : null;
            _opening = null;
            return taken;
        }

        public VisibleControlSurface.OpenedApplication? PeekOpened() => Fresh ? _opening : null;

        public DateTime? LastOpenedUtc() => _last;

        public ValueTask<VisibleControlSurface.OpenedSurface> FrontAsync(
            VisibleControlSurface.OpenedApplication opened,
            bool judgeDrawn,
            CancellationToken cancellationToken,
            bool bringToFront = false) =>
            ValueTask.FromResult(new VisibleControlSurface.OpenedSurface((nint)Opened, true));
    }

    // One desktop for the adapter and the provider: what is in front, what lives, what dialog the look's window holds.
    private sealed class Desktop : IDisposable
    {
        internal Desktop(bool readsAfterAct = false, long looked = Looked, TimeSpan openedLabel = default)
        {
            Worker = new Worker(View("Siguiente", "Enviar"));
            Focus = new Openings(Time);
            Adapter = new WindowsVisibleControlAdapter(
                Worker, null, null, Focus,
                VisibleClickTiming.Default with { LaunchSurface = TimeSpan.Zero, OpenedLabel = openedLabel, SettledLabel = TimeSpan.Zero },
                requestedWindow: (_, _) => ValueTask.FromResult((nint)looked),
                capture: (_, _, _) => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null),
                time: Time)
            {
                ReadsAfterAct = readsAfterAct,
                WindowInFront = token =>
                {
                    token.ThrowIfCancellationRequested();
                    return ValueTask.FromResult((nint)InFront);
                },
                WindowAlive = window => Alive.Contains(window),
                ModalOf = window => window == looked ? (nint)ModalOfLooked : window,
                SystemSurface = window => window == SettingsWindow,
                RawFront = () => (nint)InFront,
            };
            Provider = new WindowsExternalCapabilityProvider([Adapter], Lease, (_, _) => false);
            ModalOfLooked = looked;
        }

        internal Worker Worker { get; }

        internal SteppedTime Time { get; } = new();

        internal Openings Focus { get; }

        internal Lease Lease { get; } = new();

        internal WindowsVisibleControlAdapter Adapter { get; }

        internal WindowsExternalCapabilityProvider Provider { get; }

        internal long InFront { get; set; } = Front;

        internal long ModalOfLooked { get; set; }

        internal long SettingsWindow { get; set; }

        internal HashSet<nint> Alive { get; } = [(nint)Looked, (nint)Dialog];

        internal ValueTask<ExternalCapabilityReceipt> LookAsync() =>
            Provider.InvokeAsync("input.visible.controls", Json("""{"application":"Correo"}"""), CancellationToken.None);

        internal ValueTask<ExternalCapabilityReceipt> ClickAsync(string label) =>
            Provider.InvokeAsync("input.visible.click", Json("{\"label\":\"" + label + "\"}"), CancellationToken.None);

        internal ValueTask AskAsync(string label) =>
            Provider.NoteAskedAsync("input.visible.click", Json("{\"label\":\"" + label + "\"}"), CancellationToken.None);

        public void Dispose() => Provider.Dispose();
    }

    // H1: the first click falls in the application opened after the look; the next, by a label the old look also showed,
    // never goes back there nor brings it up.
    [Test]
    public async Task AClickDoesNotGoBackToTheLookOnceAnOpeningWasSpent()
    {
        using var desktop = new Desktop(openedLabel: TimeSpan.FromSeconds(1));

        await desktop.LookAsync();
        desktop.Time.At += TimeSpan.FromSeconds(5);
        desktop.Focus.Open();
        desktop.Time.At += TimeSpan.FromSeconds(5);
        await desktop.ClickAsync("Empezar");
        long first = desktop.Worker.LastClicked;
        await desktop.ClickAsync("Siguiente");

        Assert.Multiple(() =>
        {
            Assert.That(first, Is.EqualTo(Opened));
            Assert.That(desktop.Worker.LastClicked, Is.Not.EqualTo(Looked));
            Assert.That(desktop.Lease.Taken, Does.Not.Contain((nint)Looked));
        });
    }

    // H1: spent by a click that pressed nothing, the look is still older than what opened after it.
    [Test]
    public async Task AnOpeningSpentByAClickThatPressedNothingStillEndsTheLook()
    {
        using var desktop = new Desktop();

        await desktop.LookAsync();
        desktop.Time.At += TimeSpan.FromSeconds(5);
        desktop.Focus.Open();
        desktop.Worker.ClickAnswer = NotFound;
        await desktop.ClickAsync("Empezar");
        desktop.Worker.ClickAnswer = Clicked;
        await desktop.ClickAsync("Siguiente");

        Assert.That(desktop.Lease.Taken, Does.Not.Contain((nint)Looked));
    }

    // H1: an opening is taken for 90 s and a look lasts 120 s: between the two the opening still came after the look.
    [Test]
    public async Task AnOpeningPastItsFreshnessStillEndsTheLook()
    {
        using var desktop = new Desktop();

        await desktop.LookAsync();
        desktop.Time.At += TimeSpan.FromSeconds(5);
        desktop.Focus.Open();
        desktop.Time.At += TimeSpan.FromSeconds(100);
        await desktop.ClickAsync("Siguiente");

        Assert.Multiple(() =>
        {
            Assert.That(desktop.Lease.Taken, Is.Empty);
            Assert.That(desktop.Worker.LastClicked, Is.EqualTo(Front));
        });
    }

    // A look after the opening is the one decided on.
    [Test]
    public async Task ALookAfterTheOpeningBindsAgain()
    {
        using var desktop = new Desktop();

        desktop.Focus.Open();
        desktop.Time.At += TimeSpan.FromSeconds(1);
        await desktop.LookAsync();
        await desktop.ClickAsync("Siguiente");

        Assert.That(desktop.Lease.Taken, Is.EqualTo(new[] { (nint)Looked }));
    }

    // H1: a click that pressed in the window in front ends the look; the next stays there.
    [Test]
    public async Task AClickThatPressedElsewhereEndsTheLook()
    {
        using var desktop = new Desktop();

        await desktop.LookAsync();
        await desktop.ClickAsync("Empezar");
        await desktop.ClickAsync("Siguiente");

        Assert.Multiple(() =>
        {
            Assert.That(desktop.Worker.Clicks.Select(click => click["hwnd"]!.GetValue<long>()), Is.EqualTo(new[] { Front, Front }));
            Assert.That(desktop.Lease.Taken, Is.Empty);
        });
    }

    // Control: a label found nowhere pressed nothing, and the look still holds for the next (the model's misnamed label).
    [Test]
    public async Task AClickThatPressedNothingLeavesTheLook()
    {
        using var desktop = new Desktop();

        await desktop.LookAsync();
        desktop.Worker.ClickAnswer = NotFound;
        await desktop.ClickAsync("Empezar");
        desktop.Worker.ClickAnswer = Clicked;
        await desktop.ClickAsync("Siguiente");

        Assert.That(desktop.Lease.Taken, Is.EqualTo(new[] { (nint)Looked }));
    }

    // H2: the person brought another window up since the look: the click goes to it, as the descriptor says.
    [Test]
    public async Task AWindowThePersonBroughtTakesTheClick()
    {
        using var desktop = new Desktop();

        await desktop.LookAsync();
        desktop.InFront = Other;
        await desktop.ClickAsync("Siguiente");

        Assert.Multiple(() =>
        {
            Assert.That(desktop.Lease.Taken, Is.Empty);
            Assert.That(desktop.Worker.LastClicked, Is.EqualTo(Other));
        });
    }

    // Control: the window in front is the one that was there at the look, or the looked one itself: the look holds.
    [TestCase(Front)]
    [TestCase(Looked)]
    public async Task TheSameWindowInFrontLeavesTheLook(long inFront)
    {
        using var desktop = new Desktop();

        await desktop.LookAsync();
        desktop.InFront = inFront;
        await desktop.ClickAsync("Siguiente");

        Assert.That(desktop.Lease.Taken, Is.EqualTo(new[] { (nint)Looked }));
    }

    // Revisión de los arreglos: a window the bound click itself brought in front is no window the person brought; the next
    // click, by what the look showed, still goes to the window looked at.
    [Test]
    public async Task AWindowTheClickItselfBroughtLeavesTheLook()
    {
        using var desktop = new Desktop(readsAfterAct: true);

        await desktop.LookAsync();
        desktop.Worker.OnClick = () => desktop.InFront = Other;
        await desktop.ClickAsync("Siguiente");
        desktop.Worker.OnClick = null;
        await desktop.ClickAsync("Enviar");

        Assert.Multiple(() =>
        {
            Assert.That(desktop.Lease.Taken, Is.EqualTo(new[] { (nint)Looked, (nint)Looked }));
            Assert.That(desktop.Worker.LastClicked, Is.EqualTo(Looked));
        });
    }

    // Control: the read after a bound click refreshes the look, not what was in front at it: the lease gave the front back.
    [Test]
    public async Task TheReadAfterABoundClickKeepsWhatWasInFront()
    {
        using var desktop = new Desktop(readsAfterAct: true);

        await desktop.LookAsync();
        desktop.InFront = Looked;
        await desktop.ClickAsync("Siguiente");
        desktop.InFront = Front;
        await desktop.ClickAsync("Enviar");

        Assert.That(desktop.Lease.Taken, Is.EqualTo(new[] { (nint)Looked, (nint)Looked }));
    }

    // H3: the catalog declares these nullable and the click reads them as absent: the look binds the same as without them.
    [TestCase("""{"label":"Siguiente","index":null}""")]
    [TestCase("""{"label":"Siguiente","controlId":null}""")]
    [TestCase("""{"label":"Siguiente","manner":null}""")]
    [TestCase("""{"label":"Siguiente","search":null}""")]
    [TestCase("""{"label":"Siguiente","controlId":""}""")]
    [TestCase("""{"label":"Siguiente","search":" "}""")]
    public async Task AnArgumentWrittenEmptyIsAbsent(string arguments)
    {
        using var desktop = new Desktop();

        await desktop.LookAsync();
        await desktop.Provider.InvokeAsync("input.visible.click", Json(arguments), CancellationToken.None);

        Assert.That(desktop.Worker.LastClicked, Is.EqualTo(Looked));
    }

    // H4: asked with the look still good; the yes comes past its age, with another window in front: the yes was for the
    // window looked at.
    [Test]
    public async Task AYesHoldsForTheWindowItWasAskedFor()
    {
        using var desktop = new Desktop();

        await desktop.LookAsync();
        desktop.Time.At += TimeSpan.FromSeconds(60);
        await desktop.AskAsync("Enviar");
        desktop.Time.At += TimeSpan.FromSeconds(90);
        desktop.InFront = Other;
        await desktop.ClickAsync("Enviar");

        Assert.Multiple(() =>
        {
            Assert.That(desktop.Lease.Taken, Is.EqualTo(new[] { (nint)Looked }));
            Assert.That(desktop.Worker.LastClicked, Is.EqualTo(Looked));
        });
    }

    // H4: that window closed while the yes was pending: nothing is pressed anywhere else.
    [Test]
    public async Task AYesForAWindowThatClosedPressesNothing()
    {
        using var desktop = new Desktop();

        await desktop.LookAsync();
        await desktop.AskAsync("Enviar");
        desktop.Alive.Remove((nint)Looked);
        ExternalCapabilityReceipt receipt = await desktop.ClickAsync("Enviar");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsVisibleControlAdapter.AskedWindowGone));
            Assert.That(receipt.Result?.GetProperty("next").GetString(), Does.Contain("nothing was pressed"));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(desktop.Worker.Clicks, Is.Empty);
        });
    }

    // H4: asked for a label no look showed, which goes to the window in front; another came in front: nothing is pressed.
    [Test]
    public async Task AYesForTheWindowInFrontPressesNothingOnceAnotherCame()
    {
        using var desktop = new Desktop();

        await desktop.LookAsync();
        await desktop.AskAsync("Publicar");
        desktop.InFront = Other;
        ExternalCapabilityReceipt receipt = await desktop.ClickAsync("Publicar");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsVisibleControlAdapter.AskedWindowGone));
            Assert.That(desktop.Worker.Clicks, Is.Empty);
        });
    }

    // Control: the same window in front: the yes presses there, as ever.
    [Test]
    public async Task AYesForTheWindowInFrontPressesThereWhileItStays()
    {
        using var desktop = new Desktop();

        await desktop.LookAsync();
        await desktop.AskAsync("Publicar");
        ExternalCapabilityReceipt receipt = await desktop.ClickAsync("Publicar");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Not.EqualTo(WindowsVisibleControlAdapter.AskedWindowGone));
            Assert.That(desktop.Worker.LastClicked, Is.EqualTo(Front));
        });
    }

    // H4: asked for the application just opened; past its freshness the click would go to the window in front.
    [Test]
    public async Task AYesForAnOpeningPastItsFreshnessPressesNothing()
    {
        using var desktop = new Desktop();

        desktop.Focus.Open();
        await desktop.AskAsync("Publicar");
        desktop.Time.At += TimeSpan.FromSeconds(100);
        ExternalCapabilityReceipt receipt = await desktop.ClickAsync("Publicar");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsVisibleControlAdapter.AskedWindowGone));
            Assert.That(desktop.Worker.Clicks, Is.Empty);
        });
    }

    // Revisión de los arreglos: another opening came after the question: the yes was not for it.
    [Test]
    public async Task AYesForAnOpeningIsNotForALaterOne()
    {
        using var desktop = new Desktop();

        desktop.Focus.Open();
        await desktop.AskAsync("Publicar");
        desktop.Time.At += TimeSpan.FromSeconds(1);
        desktop.Focus.Open();
        ExternalCapabilityReceipt receipt = await desktop.ClickAsync("Publicar");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsVisibleControlAdapter.AskedWindowGone));
            Assert.That(desktop.Worker.Clicks, Is.Empty);
        });
    }

    // Revisión de los arreglos: asked for the window in front; an opening since would take the click.
    [Test]
    public async Task AYesForTheWindowInFrontIsNotForAnOpeningSince()
    {
        using var desktop = new Desktop();

        await desktop.AskAsync("Publicar");
        desktop.Focus.Open();
        ExternalCapabilityReceipt receipt = await desktop.ClickAsync("Publicar");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsVisibleControlAdapter.AskedWindowGone));
            Assert.That(desktop.Worker.Clicks, Is.Empty);
        });
    }

    // Revisión de los arreglos: asked, the person said no, and the same words run with no yes (the guard found no reason to
    // ask now): the old question does not decide where it goes.
    [Test]
    public async Task ARunWithNoYesDoesNotGoByAnOldQuestion()
    {
        using var desktop = new Desktop();

        await desktop.LookAsync();
        await desktop.AskAsync("Siguiente");
        desktop.Provider.ForgetAsked("input.visible.click", Json("""{"label":"Siguiente"}"""));
        desktop.InFront = Other;
        await desktop.ClickAsync("Siguiente");

        Assert.Multiple(() =>
        {
            Assert.That(desktop.Lease.Taken, Is.Empty);
            Assert.That(desktop.Worker.LastClicked, Is.EqualTo(Other));
        });
    }

    // Control: only that very call forgets it.
    [Test]
    public async Task AnotherCallWithNoYesLeavesTheQuestion()
    {
        using var desktop = new Desktop();

        await desktop.LookAsync();
        desktop.Time.At += TimeSpan.FromSeconds(60);
        await desktop.AskAsync("Enviar");
        desktop.Provider.ForgetAsked("input.visible.click", Json("""{"label":"Otra"}"""));
        desktop.Time.At += TimeSpan.FromSeconds(90);
        await desktop.ClickAsync("Enviar");

        Assert.That(desktop.Worker.LastClicked, Is.EqualTo(Looked));
    }

    // The kernel and the adapter together: the question is noted when the engine asks, and the run its yes starts goes there.
    [Test]
    public async Task TheEngineAsksAndItsYesGoesToTheWindowAskedFor()
    {
        using var desktop = new Desktop();
        var handler = new ExternalCapabilityHandler("input.visible.click", desktop.Provider);
        string root = Path.Combine(Path.GetTempPath(), "baxy-asked-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        await using FileInvocationJournal journal = await FileInvocationJournal.OpenAsync(
            Path.Combine(root, "journal.jsonl"),
            new JournalHmacAuthenticator(RandomNumberGenerator.GetBytes(JournalHmacAuthenticator.KeyLength)));
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        var request = new OperationRequest(
            ProtocolTypes.OperationRequest,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            "input.visible.click",
            Json("""{"label":"Enviar"}"""));

        await desktop.LookAsync();
        desktop.Time.At += TimeSpan.FromSeconds(60);
        OperationResponse asked = await engine.ExecuteAsync(request, CancellationToken.None);
        desktop.Time.At += TimeSpan.FromSeconds(90);
        desktop.InFront = Other;
        await engine.ExecuteAsync(
            request with { ConfirmationToken = asked.Result!.Value.GetProperty("token").GetString() },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(desktop.Worker.LastClicked, Is.EqualTo(Looked));
        });

        await journal.DisposeAsync();
        Directory.Delete(root, recursive: true);
    }

    // Segunda revisión de los arreglos: asked because of the surface looked at; it closed before the yes, so the guard has no
    // reason to ask on that run and nothing is granted: the question still decides, and nothing is pressed in front.
    [Test]
    public async Task AYesWhoseGuardNoLongerAsksStillGoesByTheQuestion()
    {
        using var desktop = new Desktop();
        desktop.SettingsWindow = Looked;
        var handler = new ExternalCapabilityHandler("input.visible.click", desktop.Provider);
        string root = Path.Combine(Path.GetTempPath(), "baxy-asked-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        await using FileInvocationJournal journal = await FileInvocationJournal.OpenAsync(
            Path.Combine(root, "journal.jsonl"),
            new JournalHmacAuthenticator(RandomNumberGenerator.GetBytes(JournalHmacAuthenticator.KeyLength)));
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        var request = new OperationRequest(
            ProtocolTypes.OperationRequest,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            "input.visible.click",
            Json("""{"label":"Siguiente"}"""));

        await desktop.LookAsync();
        OperationResponse asked = await engine.ExecuteAsync(request, CancellationToken.None);
        desktop.Alive.Remove((nint)Looked);
        desktop.SettingsWindow = 0;
        OperationResponse ran = await engine.ExecuteAsync(
            request with { ConfirmationToken = asked.Result!.Value.GetProperty("token").GetString() },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(ran.ErrorCode, Is.EqualTo(WindowsVisibleControlAdapter.AskedWindowGone));
            Assert.That(desktop.Worker.Clicks, Is.Empty);
        });

        await journal.DisposeAsync();
        Directory.Delete(root, recursive: true);
    }

    // Segunda revisión: with BAXY's own in front the yes names the person's window it was asked for, or the guard refuses
    // BAXY's: the click named it, so it is judged and pressed there.
    [Test]
    public async Task AYesForTheWindowInFrontNamesIt()
    {
        using var desktop = new Desktop();

        await desktop.AskAsync("Publicar");
        await desktop.ClickAsync("Publicar");

        Assert.That(desktop.Lease.Taken, Is.EqualTo(new[] { (nint)Front }));
    }

    // Segunda revisión: a cancellation once the click has pressed does not lose its receipt.
    [Test]
    public async Task ACancellationAfterThePressKeepsTheReceipt()
    {
        using var desktop = new Desktop();
        using var cancel = new CancellationTokenSource();

        await desktop.LookAsync();
        desktop.Worker.OnClick = cancel.Cancel;
        ExternalCapabilityReceipt receipt = await desktop.Provider.InvokeAsync(
            "input.visible.click", Json("""{"label":"Siguiente"}"""), cancel.Token);

        Assert.That(receipt.EffectObserved || receipt.EffectMayHaveOccurred, Is.True);
    }

    // Revisión de los arreglos: the guard judges the window the click goes to, not the look it left: the person brought up
    // a surface that changes the system; the click goes there, so it asks.
    [Test]
    public async Task TheGuardJudgesTheWindowTheClickGoesTo()
    {
        using var desktop = new Desktop();

        await desktop.LookAsync();
        desktop.InFront = Other;
        desktop.SettingsWindow = Other;
        JsonElement click = Json("""{"label":"Siguiente"}""");
        bool mayRaise = desktop.Provider.PreflightMayRaise("input.visible.click", click);
        ExternalCapabilityReceipt? read = await desktop.Provider.PreflightAsync("input.visible.click", click, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(mayRaise, Is.True);
            Assert.That(read?.NeedsConfirmation, Is.True);
        });
    }

    // Control: bound to the look, a surface in front that the click will not reach asks nothing.
    [Test]
    public async Task TheGuardLeavesAWindowTheClickDoesNotReach()
    {
        using var desktop = new Desktop();

        desktop.SettingsWindow = Front;
        await desktop.LookAsync();
        ExternalCapabilityReceipt? read = await desktop.Provider.PreflightAsync(
            "input.visible.click", Json("""{"label":"Siguiente"}"""), CancellationToken.None);

        Assert.That(read?.NeedsConfirmation ?? false, Is.False);
    }

    // The product's own record of openings: a take leaves when it was.
    [Test]
    public void TheLastOpeningStaysKnownOnceTaken()
    {
        DateTime before = DateTime.UtcNow.AddSeconds(-1);
        VisibleControlSurface.NoteOpened(Environment.ProcessId, launched: false);
        var focus = new OpenedApplicationFocus();
        _ = focus.TakeOpened();

        Assert.That(focus.LastOpenedUtc(), Is.GreaterThan(before));
    }

    // A yes is spent by its run; a later click with the same words and no question is judged as any other.
    [Test]
    public async Task AYesIsSpentByItsClick()
    {
        using var desktop = new Desktop();

        await desktop.LookAsync();
        await desktop.AskAsync("Publicar");
        await desktop.ClickAsync("Publicar");
        desktop.InFront = Other;
        ExternalCapabilityReceipt receipt = await desktop.ClickAsync("Publicar");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Not.EqualTo(WindowsVisibleControlAdapter.AskedWindowGone));
            Assert.That(desktop.Worker.LastClicked, Is.EqualTo(Other));
        });
    }

    // A question asked again, after another look, is for what that look decides: the latest question holds.
    [Test]
    public async Task TheLatestQuestionHolds()
    {
        using var desktop = new Desktop();

        await desktop.LookAsync();
        await desktop.AskAsync("Publicar");
        desktop.InFront = Other;
        await desktop.AskAsync("Publicar");
        ExternalCapabilityReceipt receipt = await desktop.ClickAsync("Publicar");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Not.EqualTo(WindowsVisibleControlAdapter.AskedWindowGone));
            Assert.That(desktop.Worker.LastClicked, Is.EqualTo(Other));
        });
    }

    // Control: no question was asked (Bypass, or nothing to ask): nothing is held, as before.
    [Test]
    public async Task WithNoQuestionTheClickIsJudgedWhenItRuns()
    {
        using var desktop = new Desktop();

        await desktop.LookAsync();
        desktop.InFront = Other;
        ExternalCapabilityReceipt receipt = await desktop.ClickAsync("Publicar");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Not.EqualTo(WindowsVisibleControlAdapter.AskedWindowGone));
            Assert.That(desktop.Worker.LastClicked, Is.EqualTo(Other));
        });
    }

    // H5: the looked window holds a dialog that came after the look: the words were the window's, the dialog asks its own.
    [Test]
    public async Task ADialogNoLookReadIsNotPressed()
    {
        using var desktop = new Desktop();

        await desktop.LookAsync();
        desktop.ModalOfLooked = Dialog;
        ExternalCapabilityReceipt receipt = await desktop.ClickAsync("Siguiente");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsVisibleControlAdapter.DialogNotRead));
            Assert.That(receipt.Result?.GetProperty("next").GetString(), Does.Contain("nothing was pressed"));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(desktop.Worker.Clicks, Is.Empty);
            Assert.That(desktop.Lease.Taken, Is.Empty);
        });
    }

    // H5: said before the person is asked: no yes for what will not run.
    [Test]
    public async Task ADialogNoLookReadIsSaidBeforeAskingForAYes()
    {
        using var desktop = new Desktop();

        await desktop.LookAsync();
        desktop.ModalOfLooked = Dialog;
        ExternalCapabilityReceipt? read = await desktop.Provider.PreflightAsync(
            "input.visible.click", Json("""{"label":"Enviar"}"""), CancellationToken.None);

        Assert.That(read?.ErrorCode, Is.EqualTo(WindowsVisibleControlAdapter.DialogNotRead));
    }

    // Control: the look that read the dialog is decided on it: its button is pressed there.
    [Test]
    public async Task TheDialogALookReadIsPressed()
    {
        using var desktop = new Desktop(looked: Dialog);

        await desktop.LookAsync();
        ExternalCapabilityReceipt receipt = await desktop.ClickAsync("Siguiente");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Not.EqualTo(WindowsVisibleControlAdapter.DialogNotRead));
            Assert.That(desktop.Worker.LastClicked, Is.EqualTo(Dialog));
        });
    }
}
